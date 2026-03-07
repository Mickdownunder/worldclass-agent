"""Phase 2: THINK — Reason about what to do (LLM plan)."""
import json

from lib.brain.helpers import _trace_id


def think_phase(state: dict, goal: str, understanding: dict, memory, llm_json_fn) -> dict:
    """Use LLM to produce plan; record decision; return plan with _trace_id."""
    trace_id = _trace_id()
    understanding = understanding or {}
    ctx_for_think = {
        "understanding": {
            "situation": understanding.get("situation", {}),
            "relevant_episodes_summary": understanding.get("relevant_episodes_summary", [])[:5],
            "why_helped_hurt": understanding.get("why_helped_hurt", [])[:5],
            "uncertainties": understanding.get("uncertainties", [])[:5],
            "options": understanding.get("options", [])[:10],
        },
        "state_summary": {
            "research_projects": state.get("research_projects", [])[:8],
            "recent_jobs": state.get("recent_jobs", [])[:6],
            "workflows": state.get("workflows", []),
            "governance": state.get("governance", {}),
            "workflow_health": state.get("workflow_health"),
            "workflow_trends": state.get("workflow_trends"),
        },
    }

    system_prompt = """You are the cognitive core of an autonomous operator system.
You THINK about the current state and a given goal, then produce a structured plan.

Your output MUST be valid JSON with this structure:
{
  "analysis": "2-3 sentence analysis of the current situation",
  "priorities": ["most important thing", "second", "third"],
  "plan": [
    {"action": "workflow_id or description", "reason": "why this action", "urgency": "high|medium|low"}
  ],
  "risks": ["potential risk 1"],
  "confidence": 0.0-1.0
}

Be specific. Reference actual workflows, clients, and data from the state.
If memory shows past failures, account for them.
If playbooks exist for relevant domains, follow their strategies.

Research: If state contains "research_projects" with projects where status != "done" and phase is not "done", consider suggesting "research-cycle" as an action with the project id as reason/context (e.g. action "research-cycle", reason "advance project <project_id>"). Prefer one research-cycle per plan step. Use the workflow id "research-cycle" and the request must be the project id. Research playbooks in state (research_playbooks) describe strategies for different research domains; use them when planning research-related actions.
COUNCIL WAITING: If a project has council_status in ["active","waiting"] and council_children_running > 0, do NOT suggest "research-cycle" for that project — the Research Council has started follow-up runs (children); it will reconvene only when all children are done, which can take days. June will be notified when the Council reports back. Suggest research-cycle only for projects that are not in this council-waiting state (or for child projects that are still advancing).
When state.last_research_complete is set, a research run just finished; consider reading the report (if phase was done) and deciding the next action (e.g. advance another project or wait for Council).
Do NOT suggest "research-init". The Brain is not allowed to start new research projects; only advance existing ones via "research-cycle". New research runs are started only via UI/Telegram or other explicit triggers.

SELF-HEALING (Plumber): If you observe repeated job failures (2+ failures in the same workflow), suggest action "plumber:diagnose-and-fix" with reason describing the failing workflow (e.g. "research-cycle repeated failures, likely script error"). The Plumber can:
- Detect and fix shell syntax errors in workflow scripts
- Analyze job logs for root causes (missing files, modules, timeouts)
- Create patches with full audit trail
At governance level ≤1 it only diagnoses; at level 2 it creates dry-run patches; at level 3 it applies fixes automatically.
Prefer plumber when you see the same workflow failing 2+ times — fixing the root cause is higher impact than retrying.

FINGERPRINT LEARNING: The Plumber tracks every error with a persistent fingerprint. Check state.plumber_last_scan.fingerprints for learning data:
- "non_repairable" count: errors classified as unfixable (e.g. external API outages, rate limits, disk full, OOM). Do NOT run plumber for these — they need human/infra intervention.
- "on_cooldown" count: errors where fix attempts failed repeatedly. Plumber will skip these automatically.
- "fix_success_rate_pct": overall fix success rate — use this to gauge plumber effectiveness.
- "top_recurring": most frequent error patterns with their workflow and snippet.
When a workflow's errors are non-repairable, skip it and focus on other productive actions instead of wasting cycles on unfixable issues.

WORKFLOW TRENDS: If state contains "workflow_trends", use it to understand whether workflows are improving or declining:
- "improving" (delta > 0.05): workflow quality is getting better — keep the current approach.
- "declining" (delta < -0.05): workflow quality is dropping — investigate or use plumber.
- "stable": no significant change.
Prioritize investigating declining workflows over running more cycles on them.

LEARNED PLAYBOOKS: state.research_playbooks may contain entries with "source": "learned". These were generated by the system's own reflect() phase from past successful projects. Treat learned playbooks as valuable — they represent strategies that worked before.

STRATEGIC PRINCIPLES: If state.research_context contains strategic_principles, treat them as hard-won lessons from past projects:
- GUIDING principles are proven strategies — follow them when applicable.
- CAUTIONARY principles are past failures — actively avoid repeating them.
- Higher metric_score = more validated through repeated success.
Incorporate applicable principles into your plan reasoning."""

    principles_block = ""
    sp = state.get("research_context", {}).get("strategic_principles", [])
    if sp:
        lines = []
        for p in sp[:10]:
            tag = (p.get("principle_type") or "guiding").upper()
            score = p.get("metric_score", 0.5)
            desc = (p.get("description") or "")[:200]
            lines.append(f"- [{tag}] (score: {score:.2f}) {desc}")
        principles_block = "\n\nSTRATEGIC PRINCIPLES:\n" + "\n".join(lines)

    understand_compact = json.dumps(ctx_for_think, indent=2, default=str)
    if len(understand_compact) > 8000:
        understand_compact = understand_compact[:8000] + "\n... (truncated)"
    user_prompt = f"GOAL: {goal}\n\nUNDERSTANDING (situation, relevant past, uncertainties, options):\n{understand_compact}{principles_block}"

    try:
        plan = llm_json_fn(system_prompt, user_prompt)
    except Exception as e:
        plan = {
            "analysis": f"LLM reasoning failed: {e}",
            "priorities": ["fix LLM connectivity"],
            "plan": [],
            "risks": ["cannot reason without LLM"],
            "confidence": 0.1,
        }
        memory.record_episode(
            "think_llm_failed",
            f"Think phase LLM failed: {e}",
            metadata={"trace_id": trace_id, "goal": goal[:200]},
        )

    meta = {"llm_failed": "LLM reasoning failed" in plan.get("analysis", "")}
    if understanding and understanding.get("retrieved_memory_ids"):
        meta["retrieved_memory_ids"] = understanding["retrieved_memory_ids"]
    memory.record_decision(
        phase="think",
        inputs={"goal": goal, "state_keys": list(state.keys()), **meta},
        reasoning=plan.get("analysis", ""),
        decision=json.dumps(plan.get("plan", [])[:3]),
        confidence=float(plan.get("confidence", 0.5)),
        trace_id=trace_id,
        metadata=meta,
    )

    plan["_trace_id"] = trace_id
    return plan
