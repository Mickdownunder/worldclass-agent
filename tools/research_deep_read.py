#!/usr/bin/env python3
"""
Multi-pass deep reading for important sources: full text -> LLM extract facts -> relevance.
Used optionally in explore for top sources.

Usage:
  research_deep_read.py <url> <question>
Output: JSON { "facts": [...], "arguments": [...], "data_points": [...], "relevance_score": 0.0-1.0, "text_preview": "..." }
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _get_full_text(url: str) -> dict:
    """Pass 1: Get full text (web reader or PDF reader for .pdf)."""
    tools = Path(__file__).resolve().parent
    if url.strip().lower().endswith(".pdf"):
        import subprocess
        r = subprocess.run(
            [sys.executable, str(tools / "research_pdf_reader.py"), url],
            capture_output=True, text=True, timeout=90,
        )
        if r.returncode != 0:
            return {"text": "", "title": "", "error": r.stderr or "PDF read failed"}
        try:
            data = json.loads(r.stdout)
            return {"text": (data.get("text") or "")[:80000], "title": data.get("title", ""), "error": data.get("error", "")}
        except Exception:
            return {"text": "", "title": "", "error": "Invalid PDF response"}
    r = __import__("subprocess").run(
        [sys.executable, str(tools / "research_web_reader.py"), url],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return {"text": "", "title": "", "error": "Web read failed"}
    try:
        data = json.loads(r.stdout)
        return {"text": (data.get("text") or "")[:80000], "title": data.get("title", ""), "error": data.get("error", "")}
    except Exception:
        return {"text": "", "title": "", "error": "Invalid response"}


def _llm_json(system: str, user: str) -> dict:
    from openai import OpenAI
    from tools.research_common import load_secrets
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    model = os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")
    resp = client.responses.create(model=model, instructions=system, input=user)
    text = (resp.output_text or "").strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def deep_read(url: str, question: str) -> dict:
    """Multi-pass: extract text -> LLM facts/arguments/data -> LLM relevance."""
    raw = _get_full_text(url)
    text = (raw.get("text") or "").strip()
    if not text or raw.get("error"):
        return {
            "facts": [], "arguments": [], "data_points": [],
            "relevance_score": 0.0, "text_preview": "", "error": raw.get("error", "No text"),
        }
    text_preview = text[:2000]
    system = """You are a research analyst. From the given text, extract structured information relevant to the research question.
Return JSON only: {"facts": ["fact1", "fact2"], "arguments": ["argument or claim"], "data_points": ["number or statistic with context"], "relevance_score": 0.0-1.0}
relevance_score = how relevant this source is to the question (0.5 = somewhat, 0.8+ = highly relevant)."""
    user = f"RESEARCH QUESTION: {question}\n\nTEXT (excerpt):\n{text[:12000]}\n\nExtract and score. Return only valid JSON."
    try:
        out = _llm_json(system, user)
    except Exception as e:
        return {"facts": [], "arguments": [], "data_points": [], "relevance_score": 0.0, "text_preview": text_preview, "error": str(e)}
    out.setdefault("facts", [])
    out.setdefault("arguments", [])
    out.setdefault("data_points", [])
    out.setdefault("relevance_score", 0.5)
    out["text_preview"] = text_preview
    return out


def main():
    if len(sys.argv) < 3:
        print("Usage: research_deep_read.py <url> <question>", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1].strip()
    question = sys.argv[2].strip()
    result = deep_read(url, question)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
