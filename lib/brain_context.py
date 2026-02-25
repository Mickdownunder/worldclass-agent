"""
Brain Context Compiler — High-signal context for the planner only.

Builds a compact context from:
- Accepted research findings only (admission_state = 'accepted')
- Reflections with quality >= min_reflection_quality (default 0.6)

Low-quality reflections are not included in planning context (telemetry only elsewhere).
"""
from __future__ import annotations

# Hard budget (single source of truth for context size)
MAX_FINDINGS_PER_PROJECT = 5
MAX_PROJECTS = 10
MAX_REFLECTIONS = 10
MIN_REFLECTION_QUALITY = 0.6


def compile(memory, *, max_findings_per_project: int = MAX_FINDINGS_PER_PROJECT,
            max_projects: int = MAX_PROJECTS, max_reflections: int = MAX_REFLECTIONS,
            min_reflection_quality: float = MIN_REFLECTION_QUALITY) -> dict:
    """
    Build planning context from accepted findings and high-quality reflections.
    Returns dict: accepted_findings_by_project, high_quality_reflections, totals.
    """
    # Accepted findings: top N per project, then first max_projects
    all_accepted = memory.get_research_findings_accepted(project_id=None, limit=max_projects * max_findings_per_project * 2)
    by_project: dict[str, list] = {}
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

    # High-quality reflections only (>= threshold)
    recent = memory.recent_reflections(limit=max_reflections * 2)
    high_reflections = [r for r in recent if (r.get("quality") or 0) >= min_reflection_quality][:max_reflections]

    return {
        "accepted_findings_by_project": by_project,
        "high_quality_reflections": [
            {"job_id": r.get("job_id"), "quality": r.get("quality"), "learnings": (r.get("learnings") or "")[:150]}
            for r in high_reflections
        ],
        "totals": {
            "accepted_projects": len(by_project),
            "accepted_findings": sum(len(v) for v in by_project.values()),
            "reflections_above_threshold": len(high_reflections),
        },
    }
