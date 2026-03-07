"""Phase 3: DECIDE — Select action based on plan and governance."""
from lib.brain.constants import GOVERNANCE_LEVELS
from lib.brain.helpers import _trace_id


def decide_phase(plan: dict, governance_level: int, memory, retrieved_memory_ids: dict | None = None) -> dict:
    """Select the specific action to execute; record decision."""
    trace_id = plan.get("_trace_id", _trace_id())
    actions = plan.get("plan", [])
    actions = [a for a in actions if (a.get("action") or "") != "research-init"]

    if not actions:
        decision = {
            "action": "none",
            "reason": "No actions in plan",
            "approved": False,
            "governance_check": GOVERNANCE_LEVELS.get(governance_level),
        }
    else:
        top_action = actions[0]
        governance_mode = GOVERNANCE_LEVELS.get(governance_level)
        if governance_level == 0:
            approved = False
            note = "Report-only mode: action logged but not executed"
        elif governance_level == 1:
            approved = False
            note = "Suggest mode: action proposed, awaiting human approval"
        elif governance_level == 2:
            approved = True
            note = "Act+Report mode: executing and reporting"
        else:
            approved = True
            note = "Full autonomous mode: executing"
        decision = {
            "action": top_action.get("action", "unknown"),
            "reason": top_action.get("reason", ""),
            "urgency": top_action.get("urgency", "medium"),
            "approved": approved,
            "governance_check": governance_mode,
            "governance_note": note,
            "all_planned": [a.get("action") for a in actions],
        }

    meta = None
    if retrieved_memory_ids:
        meta = {"retrieved_memory_ids": retrieved_memory_ids}
    memory.record_decision(
        phase="decide",
        inputs={"plan_actions": [a.get("action") for a in actions], "governance_level": governance_level},
        reasoning=decision.get("reason", ""),
        decision=decision.get("action", "none"),
        confidence=float(plan.get("confidence", 0.5)),
        trace_id=trace_id,
        metadata=meta,
    )

    decision["_trace_id"] = trace_id
    return decision
