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
from tools.research_common import project_dir, load_project, llm_call, get_principles_for_research


def _model():
    return os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")


def _hypothesis_model():
    """Model used only for hypothesis_formation; default gemini-3.1-pro-preview for deeper theses."""
    return os.environ.get("RESEARCH_HYPOTHESIS_MODEL", "gemini-3.1-pro-preview")


def _load_findings(proj_path: Path, max_items: int = 40) -> list[dict]:
    findings = []
    for f in (proj_path / "findings").glob("*.json"):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    return findings[:max_items]


def _llm_json(system: str, user: str, project_id: str = "", *, model: str | None = None) -> dict | list:
    """Call LLM with retry and optional budget tracking. model= overrides default (_model())."""
    import re
    model = model if model is not None else _model()
    result = llm_call(model, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def gap_analysis(proj_path: Path, project: dict, project_id: str = "") -> dict:
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "Analyzing gaps")
    except Exception:
        pass
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    items = json.dumps([{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings], indent=2)[:8000]
    principles_block = get_principles_for_research(question, domain=project.get("domain"), limit=5)
    system = """You are a research analyst. Given the research question and current findings, list GAPS: what is still unknown or under-sourced.
Return JSON: {"gaps": [{"description": "...", "priority": "high|medium|low", "suggested_search": "query"}]}"""
    if principles_block:
        system += "\n\n" + principles_block
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}\n\nList 3-7 gaps. Be specific."
    out = _llm_json(system, user, project_id=project_id)
    return out if isinstance(out, dict) else {"gaps": out}


def hypothesis_formation(proj_path: Path, project: dict, project_id: str = "") -> dict:
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "KI: Forming hypotheses")
    except Exception:
        pass
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    items = json.dumps([{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings], indent=2)[:8000]
    system = """You are a research analyst. Form 1-3 testable hypotheses that answer the research question based on current findings.
Return JSON: {"hypotheses": [{"statement": "...", "confidence": 0.0-1.0, "evidence_summary": "..."}]}"""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}"
    out = _llm_json(system, user, project_id=project_id, model=_hypothesis_model())
    return out if isinstance(out, dict) else {"hypotheses": out}


def contradiction_detection(proj_path: Path, project: dict, project_id: str = "") -> dict:
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "KI: Detecting contradictions")
    except Exception:
        pass
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
