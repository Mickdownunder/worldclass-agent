"""
Brain Context Compiler — High-signal context for the planner only.

Builds a compact context from:
- Accepted research findings only (admission_state = 'accepted')
- Reflections with quality >= min_reflection_quality (default 0.35)

Low-quality reflections are not included in planning context (telemetry only elsewhere).
- Strategic principles: causal type is prioritized over generic when injecting into think-context.
"""
from __future__ import annotations

# Hard budget (single source of truth for context size)
MAX_FINDINGS_PER_PROJECT = 5
MAX_PROJECTS = 10
MAX_REFLECTIONS = 10
MIN_REFLECTION_QUALITY = 0.35


def compile(memory, *, max_findings_per_project: int = MAX_FINDINGS_PER_PROJECT,
            max_projects: int = MAX_PROJECTS, max_reflections: int = MAX_REFLECTIONS,
            min_reflection_quality: float = MIN_REFLECTION_QUALITY,
            query: str | None = None) -> dict:
    """
    Build planning context from accepted findings and high-quality reflections.
    If query is provided, uses utility-ranked retrieval (MemRL-inspired) for reflections,
    findings, and strategic principles. Otherwise uses static retrieval (backward compatible).
    Returns dict: accepted_findings_by_project, high_quality_reflections, totals, [strategic_principles].
    """
    if query and hasattr(memory, "retrieve_with_utility"):
        # Utility-ranked retrieval: two-phase semantic + utility re-rank
        reflections = memory.retrieve_with_utility(query, "reflection", k=max_reflections)
        findings = memory.retrieve_with_utility(query, "finding", k=20)
        principles = memory.retrieve_with_utility(query, "principle", k=5)
        by_project: dict[str, list] = {}
        for f in findings:
            pid = f.get("project_id") or ""
            if pid not in by_project:
                by_project[pid] = []
            if len(by_project[pid]) >= max_findings_per_project:
                continue
            by_project[pid].append({
                "finding_key": f.get("finding_key"),
                "preview": (f.get("content_preview") or "")[:200],
                "url": f.get("url"),
            })
        keys = list(by_project.keys())[:max_projects]
        by_project = {k: by_project[k] for k in keys}
        # Prioritize causal principles (do/avoid from experience) over generic
        principles_sorted = sorted(principles, key=lambda p: (0 if (p.get("principle_type") or "").lower() == "causal" else 1, -(p.get("metric_score") or 0)))
        return {
            "accepted_findings_by_project": by_project,
            "high_quality_reflections": [
                {"job_id": r.get("job_id"), "quality": r.get("quality"), "learnings": (r.get("learnings") or "")[:150]}
                for r in reflections
            ],
            "strategic_principles": [
                {"description": (p.get("description") or "")[:200], "principle_type": p.get("principle_type"), "metric_score": p.get("metric_score")}
                for p in principles_sorted
            ],
            "totals": {
                "accepted_projects": len(by_project),
                "accepted_findings": sum(len(v) for v in by_project.values()),
                "reflections_above_threshold": len(reflections),
                "principles_count": len(principles),
            },
        }
    # Fallback: static retrieval (no query or no retrieve_with_utility)
    all_accepted = memory.get_research_findings_accepted(project_id=None, limit=max_projects * max_findings_per_project * 2)
    by_project = {}
    for f in all_accepted:
        pid = f.get("project_id") or ""
        if pid not in by_project:
            by_project[pid] = []
        if len(by_project[pid]) >= max_findings_per_project:
            continue
        by_project[pid].append({
            "finding_key": f.get("finding_key"),
            "preview": (f.get("content_preview") or "")[:200],
            "url": f.get("url"),
        })
    keys = list(by_project.keys())[:max_projects]
    by_project = {k: by_project[k] for k in keys}
    recent = memory.recent_reflections(limit=max_reflections * 2)
    high_reflections = [r for r in recent if (r.get("quality") or 0) >= min_reflection_quality][:max_reflections]

    # Cross-workflow principles: retrieve top-scoring regardless of domain; prioritize causal
    principles = []
    if hasattr(memory, "list_principles"):
        principles = memory.list_principles(limit=10)
    principles_sorted = sorted(principles, key=lambda p: (0 if (p.get("principle_type") or "").lower() == "causal" else 1, -(p.get("metric_score") or 0)))

    return {
        "accepted_findings_by_project": by_project,
        "high_quality_reflections": [
            {"job_id": r.get("job_id"), "quality": r.get("quality"), "learnings": (r.get("learnings") or "")[:150]}
            for r in high_reflections
        ],
        "strategic_principles": [
            {"description": (p.get("description") or "")[:200], "principle_type": p.get("principle_type"),
             "metric_score": p.get("metric_score"), "domain": p.get("domain", "")}
            for p in principles_sorted
        ],
        "totals": {
            "accepted_projects": len(by_project),
            "accepted_findings": sum(len(v) for v in by_project.values()),
            "reflections_above_threshold": len(high_reflections),
            "principles_count": len(principles),
        },
    }
