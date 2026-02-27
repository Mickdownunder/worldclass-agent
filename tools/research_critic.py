#!/usr/bin/env python3
"""
Report critic: self-assessment and revision of research reports.
Used after synthesize for quality gate.

Usage:
  research_critic.py <project_id> critique
  research_critic.py <project_id> revise
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, ensure_project_layout, llm_call


def _model():
    return os.environ.get("RESEARCH_CRITIQUE_MODEL", "gpt-5.2")


def _threshold() -> float:
    try:
        return float(os.environ.get("RESEARCH_CRITIC_THRESHOLD", "0.55"))
    except ValueError:
        return 0.55


def _load_report(proj_path: Path, art_path: Path | None) -> str:
    # Prefer latest report from project reports/ or artifacts
    reports_dir = proj_path / "reports"
    if reports_dir.exists():
        reports = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            return reports[0].read_text(encoding="utf-8", errors="replace")
    if art_path and (art_path / "report.md").exists():
        return (art_path / "report.md").read_text(encoding="utf-8", errors="replace")
    return ""


def _llm_json(system: str, user: str, project_id: str = "") -> dict:
    """Call LLM for JSON output with retry and optional budget tracking."""
    import re
    model = _model()
    result = llm_call(model, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _llm_text(system: str, user: str, project_id: str = "") -> str:
    """Call LLM for text output with retry and optional budget tracking."""
    model = _model()
    result = llm_call(model, system, user, project_id=project_id)
    return (result.text or "").strip()


def critique_report(proj_path: Path, project: dict, art_path: Path | None = None, project_id: str = "") -> dict:
    """LLM evaluates the report: completeness, source coverage, consistency, depth, actionability."""
    ensure_project_layout(proj_path)
    report = _load_report(proj_path, art_path)
    if not report:
        return {"score": 0.0, "weaknesses": ["No report found"], "suggestions": [], "pass": False}
    question = project.get("question", "")
    thresh = _threshold()
    system = f"""You are a research quality reviewer. Evaluate the report and return JSON only:
{{"score": 0.0-1.0, "weaknesses": ["list of specific weaknesses"], "suggestions": ["list of concrete improvements"], "pass": true/false}}

Calibration: Score 0.6 = adequate report that answers the research question with cited sources and no major flaws. Use scores below 0.5 only for missing content, major contradictions, or no/fake sources. A solid frontier-style report with good coverage should get 0.65-0.85.

Criteria: completeness (answers the question?), source coverage (diverse sources?), logical consistency (contradictions?), depth (substantial vs superficial?), actionability (clear next steps?).
pass = true if score >= {thresh:.2f}."""
    user = f"RESEARCH QUESTION: {question}\n\nREPORT:\n{report[:12000]}\n\nEvaluate and return only valid JSON."
    out = _llm_json(system, user, project_id=project_id)
    if not isinstance(out, dict):
        return {"score": 0.5, "weaknesses": [], "suggestions": [], "pass": False}
    out.setdefault("score", 0.5)
    out.setdefault("pass", out["score"] >= _threshold())
    from tools.research_common import audit_log
    audit_log(proj_path, "critic_evaluation", {
        "score": out.get("score", 0),
        "passed": out.get("pass", False),
        "weaknesses_count": len(out.get("weaknesses", [])),
    })
    return out


def revise_report(proj_path: Path, critique: dict, art_path: Path | None = None, project_id: str = "") -> str:
    """Revise the report based on critique feedback. Returns revised markdown."""
    ensure_project_layout(proj_path)
    report = _load_report(proj_path, art_path)
    if not report:
        return "# Report\n\nNo report to revise."
    weaknesses = critique.get("weaknesses", [])
    suggestions = critique.get("suggestions", [])
    system = """You are a research analyst. Revise the report to address the listed weaknesses and suggestions.
Output only the revised markdown report. Keep the same structure (Executive Summary, Key Findings, etc.)."""
    user = f"CURRENT REPORT:\n{report[:14000]}\n\nWEAKNESSES TO ADDRESS: {json.dumps(weaknesses)}\n\nSUGGESTIONS: {json.dumps(suggestions)}\n\nProduce the revised markdown only."
    return _llm_text(system, user, project_id=project_id)


def main():
    if len(sys.argv) < 3:
        print("Usage: research_critic.py <project_id> <critique|revise> [artifacts_dir]", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    mode = sys.argv[2].lower()
    art_path = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    project = load_project(proj_path)
    if mode == "critique":
        result = critique_report(proj_path, project, art_path, project_id=project_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif mode == "revise":
        critique_file = proj_path / "verify" / "critique.json"
        if art_path and (art_path / "critique.json").exists():
            critique = json.loads((art_path / "critique.json").read_text())
        elif critique_file.exists():
            critique = json.loads(critique_file.read_text())
        else:
            critique = critique_report(proj_path, project, art_path, project_id=project_id)
        revised = revise_report(proj_path, critique, art_path, project_id=project_id)
        print(revised)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
