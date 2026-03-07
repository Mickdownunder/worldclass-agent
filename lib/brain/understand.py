"""Phase 1.5: UNDERSTAND — Build structured understanding from state + memory."""
import json

from lib.brain.helpers import _trace_id


def understand_phase(state: dict, goal: str, memory) -> dict:
    """Build situation, relevant past, uncertainties, options; record decision."""
    trace_id = _trace_id()
    research_ctx = state.get("research_context") or {}
    principles = list((research_ctx.get("strategic_principles") or [])[:10])
    reflections = list((research_ctx.get("high_quality_reflections") or [])[:8])
    findings_by_project = research_ctx.get("accepted_findings_by_project") or {}
    trace = research_ctx.get("memory_trace") or {}
    retrieved_principle_ids = [str(x) for x in (trace.get("principle_ids") or []) if x]
    retrieved_finding_ids = [str(x) for x in (trace.get("finding_ids") or []) if x]
    if not retrieved_principle_ids:
        for p in principles:
            if p.get("id"):
                retrieved_principle_ids.append(str(p["id"]))
    if not retrieved_finding_ids:
        for _proj, findings in findings_by_project.items():
            for f in (findings or [])[:5]:
                if f.get("id"):
                    retrieved_finding_ids.append(str(f["id"]))
    n_projects = len(state.get("research_projects") or [])
    n_not_done = sum(1 for p in (state.get("research_projects") or []) if p.get("status") != "done")
    active_goal = goal or ""
    if not active_goal and n_not_done and state.get("research_projects"):
        for p in state.get("research_projects", []):
            if p.get("status") != "done" and (p.get("question") or "").strip():
                active_goal = (p.get("question") or "").strip()[:500]
                break
    situation = {
        "summary": f"{n_projects} research projects, {n_not_done} not done; recent jobs and workflows available.",
        "goal": active_goal[:400] if active_goal else "Decide the most impactful next action",
        "domain_hint": "",
    }
    if (state.get("research_projects") or []) and n_not_done:
        first = next((p for p in state.get("research_projects", []) if p.get("status") != "done"), None)
        if first:
            situation["domain_hint"] = str(first.get("phase", ""))[:80]
    relevant_episodes_summary = []
    for r in reflections[:5]:
        relevant_episodes_summary.append({"quality": r.get("quality"), "learnings": (r.get("learnings") or "")[:150]})
    why_helped_hurt = []
    if research_ctx.get("totals"):
        t = research_ctx["totals"]
        why_helped_hurt.append(
            "Accepted findings: %s; reflections above threshold: %s; principles: %s."
            % (t.get("accepted_findings", 0), t.get("reflections_above_threshold", 0), t.get("principles_count", 0))
        )
    for r in reflections[:3]:
        if (r.get("learnings") or "").strip():
            why_helped_hurt.append((r.get("learnings") or "").strip()[:200])
    uncertainties = []
    if n_not_done and not principles and not reflections:
        uncertainties.append("No strategic principles or high-quality reflections yet; first runs in this context.")
    if not active_goal.strip():
        uncertainties.append("No explicit goal from open research project; using default goal.")
    options = []
    for w in state.get("workflows") or []:
        options.append({"action": w, "type": "workflow"})
    if (state.get("workflow_health") or {}).get("sick_workflows"):
        options.append({"action": "plumber:diagnose-and-fix", "type": "self_healing", "reason": "Repeated workflow failures"})
    understand_output = {
        "situation": situation,
        "relevant_episodes_summary": relevant_episodes_summary,
        "why_helped_hurt": why_helped_hurt[:10],
        "uncertainties": uncertainties,
        "options": options[:15],
        "retrieved_memory_ids": {
            "principle_ids": retrieved_principle_ids[:30],
            "finding_ids": retrieved_finding_ids[:50],
        },
        "_trace_id": trace_id,
    }
    memory.record_decision(
        phase="understand",
        inputs={"state_keys": list(state.keys()), "goal": (goal or active_goal or "")[:200]},
        reasoning=json.dumps(situation, ensure_ascii=False)[:1500],
        decision="understanding_built",
        confidence=0.9,
        trace_id=trace_id,
        metadata={"retrieved_memory_ids": understand_output["retrieved_memory_ids"]},
    )
    return understand_output
