#!/usr/bin/env python3
"""
Research-specific reasoning: gap_analysis, hypothesis_formation, contradiction_detection.
Reads project findings and returns structured JSON (gaps, hypotheses, or contradiction pairs).
Uses RESEARCH_EXTRACT_MODEL (default gpt-4.1-mini) for cost efficiency.

Usage:
  research_reason.py <project_id> gap_analysis
  research_reason.py <project_id> hypothesis_formation
  research_reason.py <project_id> contradiction_detection
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import load_secrets, project_dir, load_project, llm_retry


def _model():
    return os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")


def _load_findings(proj_path: Path, max_items: int = 40) -> list[dict]:
    findings = []
    for f in (proj_path / "findings").glob("*.json"):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    return findings[:max_items]


def _llm_json(system: str, user: str, project_id: str = "") -> dict | list:
    """Call LLM with retry and optional budget tracking."""
    from openai import OpenAI
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    model = _model()

    @llm_retry()
    def _call():
        return client.responses.create(model=model, instructions=system, input=user)

    resp = _call()

    if project_id:
        try:
            from tools.research_budget import track_usage
            track_usage(project_id, model, resp.usage.input_tokens, resp.usage.output_tokens)
        except Exception:
            pass

    text = (resp.output_text or "").strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def gap_analysis(proj_path: Path, project: dict, project_id: str = "") -> dict:
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    items = json.dumps([{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings], indent=2)[:8000]
    system = """You are a research analyst. Given the research question and current findings, list GAPS: what is still unknown or under-sourced.
Return JSON: {"gaps": [{"description": "...", "priority": "high|medium|low", "suggested_search": "query"}]}"""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}\n\nList 3-7 gaps. Be specific."
    out = _llm_json(system, user, project_id=project_id)
    return out if isinstance(out, dict) else {"gaps": out}


def hypothesis_formation(proj_path: Path, project: dict, project_id: str = "") -> dict:
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    items = json.dumps([{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings], indent=2)[:8000]
    system = """You are a research analyst. Form 1-3 testable hypotheses that answer the research question based on current findings.
Return JSON: {"hypotheses": [{"statement": "...", "confidence": 0.0-1.0, "evidence_summary": "..."}]}"""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}"
    out = _llm_json(system, user, project_id=project_id)
    return out if isinstance(out, dict) else {"hypotheses": out}


def contradiction_detection(proj_path: Path, project: dict, project_id: str = "") -> dict:
    findings = _load_findings(proj_path)
    items = json.dumps([{"url": f.get("url"), "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:400]} for f in findings], indent=2)[:10000]
    system = """You are a research analyst. Identify CONTRADICTIONS: pairs of findings that disagree on the same fact or claim.
Return JSON: {"contradictions": [{"claim": "what they disagree on", "source_a": "url or title", "source_b": "url or title", "summary": "brief"}]}"""
    user = "FINDINGS:\n" + items + '\n\nList 0-5 contradictions. If none, return {"contradictions": []}.'
    out = _llm_json(system, user, project_id=project_id)
    return out if isinstance(out, dict) else {"contradictions": out}


def main():
    if len(sys.argv) < 3:
        print("Usage: research_reason.py <project_id> <gap_analysis|hypothesis_formation|contradiction_detection>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    mode = sys.argv[2].lower()
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    project = load_project(proj_path)
    if mode == "gap_analysis":
        result = gap_analysis(proj_path, project, project_id=project_id)
    elif mode == "hypothesis_formation":
        result = hypothesis_formation(proj_path, project, project_id=project_id)
    elif mode == "contradiction_detection":
        result = contradiction_detection(proj_path, project, project_id=project_id)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
