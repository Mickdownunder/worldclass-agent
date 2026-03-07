"""Gap-fill and refinement queries from coverage JSON."""
import json
from pathlib import Path
from typing import Any

from tools.planner.plan import load_project_plan
from tools.planner.helpers import parse_priority
from tools.research_common import research_root


def build_gap_fill_queries(coverage_path: str, project_id: str) -> dict[str, Any]:
    if project_id:
        try:
            from tools.research_progress import step as progress_step
            progress_step(project_id, "Planning focus queries")
        except Exception:
            pass
    p = Path(coverage_path)
    if not p.exists():
        return {"queries": []}
    cov = json.loads(p.read_text())
    uncovered = cov.get("uncovered_topics", [])
    plan = load_project_plan(project_id)
    perspectives = plan.get("perspectives") or ["AI researcher", "framework developer", "enterprise user"]
    entities = [str(e) for e in (plan.get("entities") or [])]
    out_queries: list[dict[str, Any]] = []
    for i, t in enumerate(uncovered[:8]):
        tid = str(t.get("id") or f"gap-{i+1}")
        name = str(t.get("name") or "topic").strip()
        desc = str(t.get("description") or "").strip()
        prio = parse_priority(t.get("priority"))
        pset = perspectives[:3] if prio == 1 else perspectives[:2]
        for p in pset:
            q = f"{name} {desc[:40]} evidence comparison".strip()
            out_queries.append(
                {
                    "query": " ".join(q.split())[:180],
                    "topic_id": tid,
                    "type": "academic" if prio == 1 else "web",
                    "perspective": p,
                }
            )
        for e in entities[:4]:
            if e.lower() in f"{name} {desc}".lower():
                out_queries.append(
                    {
                        "query": f"{e} {name} benchmark study",
                        "topic_id": tid,
                        "type": "academic",
                        "perspective": "AI researcher",
                    }
                )
    return {"queries": out_queries[:40]}


def build_refinement_plan(coverage_path: str, project_id: str) -> dict[str, Any]:
    """After explore reads: re-plan with findings summary to generate 5-10 precision queries for gaps."""
    if project_id:
        try:
            from tools.research_progress import step as progress_step
            progress_step(project_id, "Planner Round 2: precision queries")
        except Exception:
            pass
    p = Path(coverage_path)
    if not p.exists():
        return {"queries": []}
    cov = json.loads(p.read_text())
    plan = load_project_plan(project_id)
    question = (plan.get("question") or "").strip()
    if not question:
        proj_dir = research_root() / project_id
        try:
            proj = json.loads((proj_dir / "project.json").read_text())
            question = (proj.get("question") or "").strip()
        except Exception:
            pass
    covered = [t for t in (cov.get("topics") or []) if (t.get("coverage") or {}).get("is_covered")]
    uncovered = cov.get("uncovered_topics", [])
    findings_summary_parts = []
    for t in covered[:5]:
        name = str(t.get("name") or "")
        cnt = (t.get("coverage") or {}).get("sources_count", 0)
        findings_summary_parts.append(f"- {name}: {cnt} sources")
    gaps_parts = [str(t.get("name") or t.get("id") or "topic") for t in uncovered[:8]]
    findings_summary = "\n".join(findings_summary_parts) if findings_summary_parts else "None yet."
    gaps_summary = "; ".join(gaps_parts) if gaps_parts else "None."
    system = """You are a research strategist. Given the research question, what was already found, and what is still missing, output 5-10 precise search queries to fill the gaps. Each query should target a specific gap. Return ONLY valid JSON: {"queries": [{"query": "...", "topic_id": "gap-1", "type": "web|academic|medical"}]}. Keep queries under 12 words each."""
    user = f"""QUESTION: {question}

FOUND (covered): {findings_summary}
MISSING (gaps): {gaps_summary}

Generate 5-10 precision queries targeting the gaps. Return only JSON with key "queries"."""
    try:
        from tools.research_common import llm_call
        from tools.planner.constants import PLANNER_MODEL
        from tools.planner.helpers import json_only
        resp = llm_call(PLANNER_MODEL, system, user, project_id=project_id)
        out = json_only(resp.text or "{}")
        queries = out.get("queries") if isinstance(out.get("queries"), list) else []
        return {"queries": [q for q in queries if isinstance(q, dict) and (q.get("query") or "").strip()][:10]}
    except Exception:
        return {"queries": []}
