#!/usr/bin/env python3
"""
Post-read relevance gate: checks if a fetched source is actually relevant
to the research question before saving it as a finding.

Returns JSON: {"relevant": bool, "score": int, "reason": str}
Score 0-10. Only sources scoring >= 7 are considered relevant.

Usage:
  research_relevance_gate.py <project_id> <source_text_file>
  research_relevance_gate.py batch <project_id>   # score all findings, write explore/relevance_gate_results.json
  # or import and call: check_relevance(question, title, text) -> dict
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import llm_call, load_project, project_dir

GATE_MODEL = os.environ.get("RESEARCH_GATE_MODEL", "gpt-4.1-mini")
RELEVANCE_THRESHOLD = int(os.environ.get("RESEARCH_RELEVANCE_THRESHOLD", "7"))

_SYSTEM = """You are a research relevance judge. Given a research question and a source text,
determine whether the source contains information that DIRECTLY helps answer the research question.

Scoring rubric:
- 9-10: Primary source. Directly addresses the core question with specific data, findings, or expert analysis.
- 7-8: Strong supporting source. Contains relevant context, background, or partial answers.
- 4-6: Tangentially related. Mentions the topic but doesn't contribute meaningfully to answering the question.
- 1-3: Irrelevant. Wrong topic, outdated, or only superficial keyword overlap.
- 0: Completely unrelated.

Return ONLY valid JSON: {"score": <int 0-10>, "reason": "<1 sentence>"}"""


def check_relevance(question: str, title: str, text: str, project_id: str = "") -> dict:
    """Check if source content is relevant to the research question.
    Returns {"relevant": bool, "score": int, "reason": str}."""
    snippet = text[:3000]
    user_msg = f"RESEARCH QUESTION: {question}\n\nSOURCE TITLE: {title}\n\nSOURCE TEXT (first 3000 chars):\n{snippet}"

    try:
        result = llm_call(GATE_MODEL, _SYSTEM, user_msg, project_id=project_id)
        raw = (result.text or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw).split("```")[0].strip()
        parsed = json.loads(raw)
        score = int(parsed.get("score", 0))
        reason = str(parsed.get("reason", ""))
    except Exception as e:
        # On failure, default to keeping the source (don't lose data on LLM errors)
        return {"relevant": True, "score": RELEVANCE_THRESHOLD, "reason": f"gate_error: {e}"}

    return {
        "relevant": score >= RELEVANCE_THRESHOLD,
        "score": score,
        "reason": reason,
    }


def run_batch(project_id: str) -> dict:
    """Score all findings in project; write explore/relevance_gate_results.json. Fail-open."""
    proj_path = project_dir(project_id)
    proj = load_project(proj_path)
    question = (proj.get("question") or "").strip()
    findings_dir = proj_path / "findings"
    out_path = proj_path / "explore" / "relevance_gate_results.json"
    results: list[dict] = []
    try:
        if not question or not findings_dir.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps({"findings": [], "question": question or ""}, indent=2))
            return {"ok": True, "count": 0}
        for f in sorted(findings_dir.glob("*.json")):
            if "_content" in f.name:
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                results.append({"finding_id": f.name, "relevant": True, "score": 7, "reason": "parse_skip"})
                continue
            title = (data.get("title") or "")[:500]
            text = (data.get("text") or data.get("excerpt") or data.get("abstract") or "").strip()[:8000]
            if not text:
                results.append({"finding_id": f.name, "relevant": True, "score": 7, "reason": "no_text"})
                continue
            rec = check_relevance(question, title, text, project_id=project_id)
            results.append({
                "finding_id": f.name,
                "relevant": rec["relevant"],
                "score": rec["score"],
                "reason": rec["reason"],
            })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"findings": results, "question": question}, indent=2, ensure_ascii=False))
        return {"ok": True, "count": len(results)}
    except Exception as e:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"findings": [], "error": str(e), "question": question or ""}, indent=2))
        return {"ok": False, "count": 0, "error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage: research_relevance_gate.py batch <project_id> | <project_id> <source_json>", file=sys.stderr)
        sys.exit(2)

    if sys.argv[1].strip().lower() == "batch":
        if len(sys.argv) < 3:
            print("Usage: research_relevance_gate.py batch <project_id>", file=sys.stderr)
            sys.exit(2)
        out = run_batch(sys.argv[2].strip())
        print(json.dumps(out))
        sys.exit(0)  # fail-open: do not break pipeline

    pid = sys.argv[1]
    source_path = Path(sys.argv[2])

    proj_path = project_dir(pid)
    proj = load_project(proj_path)
    question = proj.get("question", "")
    if not question:
        print(json.dumps({"relevant": True, "score": 10, "reason": "no_question"}))
        return

    try:
        data = json.loads(source_path.read_text())
    except Exception as e:
        print(json.dumps({"relevant": False, "score": 0, "reason": f"read_error: {e}"}))
        return

    title = data.get("title", "")
    text = (data.get("text") or data.get("abstract") or "").strip()
    if not text:
        print(json.dumps({"relevant": False, "score": 0, "reason": "empty_content"}))
        return

    result = check_relevance(question, title, text, project_id=pid)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
