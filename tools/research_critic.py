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
from tools.research_common import project_dir, load_project, ensure_project_layout, llm_call, model_for_lane


def _model():
    return model_for_lane("critic")


def _threshold() -> float:
    try:
        return float(os.environ.get("RESEARCH_CRITIC_THRESHOLD", "0.50"))
    except ValueError:
        return 0.50


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
    from tools.research_common import audit_log
    model = _model()
    try:
        result = llm_call(model, system, user, project_id=project_id)
    except Exception as e:
        proj = project_dir(project_id) if project_id else None
        if proj:
            audit_log(proj, "critic_llm_failed", {"error": str(e), "model": model})
        return {"score": 0.0, "error": str(e), "weaknesses": [], "suggestions": [], "pass": False, "dimensions": []}
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


# Multi-dimensional critic: each dimension has score + remediation_action for conductor
CRITIC_DIMENSIONS = [
    "coverage",         # topic/source coverage -> search_more on weak topics
    "depth",            # substantive vs superficial -> read_more / deep-read
    "accuracy",         # factuality, verification -> verify
    "novelty",          # non-obvious insights -> search_more / read_more
    "coherence",        # logical flow, contradictions -> revise sections
    "citation_quality", # proper sourcing -> verify / add citations
]


def critique_report(proj_path: Path, project: dict, art_path: Path | None = None, project_id: str = "") -> dict:
    """LLM evaluates the report: single score + 6 dimensions with remediation actions."""
    ensure_project_layout(proj_path)
    report = _load_report(proj_path, art_path)
    if not report:
        return {
            "score": 0.0, "weaknesses": ["No report found"], "suggestions": [], "pass": False,
            "dimensions": [{"dimension": d, "score": 0.0, "remediation_action": "synthesize"} for d in CRITIC_DIMENSIONS],
        }
    question = project.get("question", "")
    thresh = _threshold()
    research_mode = ((project.get("config") or {}).get("research_mode") or "standard").strip().lower()
    if research_mode == "discovery":
        system = f"""You are a research innovation reviewer. Evaluate the discovery report. Return JSON only.

Dimensions (weighted for discovery):
- novelty (weight 3x): Are the insights genuinely new? Non-obvious connections?
- coverage (weight 2x): Breadth of perspectives explored
- depth (weight 1x): Are hypotheses well-reasoned?
- coherence (weight 1x): Logical flow
- accuracy (weight 1x): Are ESTABLISHED claims actually verifiable?
- citation_quality (weight 1x): Source diversity, not just count

1) Overall: "score" (0.0-1.0), "weaknesses" (list), "suggestions" (list), "pass" (true if score >= {thresh:.2f}).
2) Per-dimension (array "dimensions"): "dimension", "score" (0-1), "remediation_action" (search_more, read_more, verify, or synthesize).

A discovery report scoring 0.5 with high novelty is better than 0.7 with no novel insights.
Return only valid JSON with keys: score, weaknesses, suggestions, pass, dimensions."""
    else:
        system = f"""You are a research quality reviewer. Evaluate the report and return JSON only.

1) Overall: "score" (0.0-1.0), "weaknesses" (list), "suggestions" (list), "pass" (true if score >= {thresh:.2f}).
2) For weaknesses that refer to a specific section, prefix with "Section N: " or "Section <title>: " (e.g. "Section 3: fehlende Tiefe", "Section Executive Summary: zu lang") so revision can target them.
3) Per-dimension (array "dimensions"): for each dimension give "dimension", "score" (0-1), "remediation_action" (exactly one of: search_more, read_more, verify, synthesize).
Dimensions and suggested actions:
- coverage: topic/source coverage; low -> search_more
- depth: substantive vs superficial; low -> read_more
- accuracy: factuality/verification; low -> verify
- novelty: non-obvious insights; low -> search_more or read_more
- coherence: logical flow, no contradictions; low -> synthesize (rewrite sections)
- citation_quality: proper sourcing; low -> verify

Calibration: Overall 0.6 = adequate report. Use scores below 0.5 for major flaws.
Return only valid JSON with keys: score, weaknesses, suggestions, pass, dimensions (array of {{dimension, score, remediation_action}})."""
    user = f"RESEARCH QUESTION: {question}\n\nREPORT:\n{report[:12000]}\n\nEvaluate and return only valid JSON."
    out = _llm_json(system, user, project_id=project_id)
    if not isinstance(out, dict):
        return {"score": 0.5, "weaknesses": [], "suggestions": [], "pass": False, "dimensions": []}
    out.setdefault("score", 0.5)
    out.setdefault("pass", out["score"] >= _threshold())
    if "dimensions" not in out or not isinstance(out["dimensions"], list):
        out["dimensions"] = [
            {"dimension": d, "score": out.get("score", 0.5), "remediation_action": "synthesize"}
            for d in CRITIC_DIMENSIONS
        ]
    # Normalize remediation_action to conductor actions
    for dim in out["dimensions"]:
        if isinstance(dim, dict):
            dim.setdefault("remediation_action", "synthesize")
            a = str(dim.get("remediation_action", "")).lower()
            if a not in ("search_more", "read_more", "verify", "synthesize"):
                dim["remediation_action"] = "synthesize"
    from tools.research_common import audit_log
    audit_log(proj_path, "critic_evaluation", {
        "score": out.get("score", 0),
        "passed": out.get("pass", False),
        "weaknesses_count": len(out.get("weaknesses", [])),
        "dimensions": len(out.get("dimensions", [])),
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
CRITICAL RULES:
- Output the COMPLETE revised markdown report. Do NOT omit or drop any sections.
- Keep ALL existing sections. Only modify the content within sections that need improvement.
- If a weakness is prefixed with "Section N: " or "Section <title>: ", address that section first and explicitly.
- If a section is fine, include it unchanged.
- The revised report must have AT LEAST as many sections as the original.
- Never create tables with "TBD" or empty placeholders. Use prose instead."""
    report_text = report[:50000]
    user = f"CURRENT REPORT:\n{report_text}\n\nWEAKNESSES TO ADDRESS: {json.dumps(weaknesses)}\n\nSUGGESTIONS: {json.dumps(suggestions)}\n\nProduce the COMPLETE revised markdown. Include ALL sections from the original."
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
