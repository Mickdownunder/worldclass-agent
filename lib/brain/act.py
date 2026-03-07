"""Phase 4: ACT — Execute the decided action (workflow or plumber)."""
import os
import re
import subprocess
from pathlib import Path

from lib.brain.constants import BASE, WORKFLOWS
from lib.brain.helpers import _trace_id


def _act_plumber_phase(
    action: str,
    decision: dict,
    trace_id: str,
    memory,
    governance_level: int,
    run_plumber_fn,
    llm_json_fn,
) -> dict:
    """Run the plumber self-healing subsystem."""
    reason = (decision.get("reason") or "").strip()
    target = None
    for pattern in [r"([\w-]+)-failures", r"workflow[:\s]+(\S+)", r"([\w-]+)\.sh"]:
        m = re.search(pattern, f"{action} {reason}")
        if m:
            target = m.group(1)
            break
    try:
        report = run_plumber_fn(
            intent=action,
            target=target,
            governance_level=governance_level,
            llm_fn=llm_json_fn,
        )
        issues = report.get("issues_found", 0)
        fixed = report.get("issues_fixed", 0)
        summary_parts = []
        for r in report.get("results", [])[:5]:
            summary_parts.append(
                "[%s] %s: %s -> %s"
                % (r.get("type"), r.get("target", "?"), (r.get("diagnosis", ""))[:100], r.get("action", "?"))
            )
        summary = "; ".join(summary_parts) or "No issues detected"
        result = {
            "executed": True,
            "action": action,
            "handler": "plumber",
            "issues_found": issues,
            "issues_fixed": fixed,
            "status": "DONE" if issues == 0 or fixed > 0 else "PARTIAL",
            "summary": summary,
            "results": report.get("results", []),
        }
        memory.record_episode(
            "act_plumber",
            f"Plumber ran: {issues} issues found, {fixed} fixed. {summary[:200]}",
            metadata={"issues_found": issues, "issues_fixed": fixed, "governance_level": governance_level},
        )
    except Exception as e:
        result = {
            "executed": True,
            "action": action,
            "handler": "plumber",
            "status": "FAILED",
            "error": str(e),
        }
        memory.record_episode("act_plumber_error", f"Plumber failed: {e}")
    result["_trace_id"] = trace_id
    return result


def act_phase(
    decision: dict,
    memory,
    governance_level: int,
    run_plumber_fn,
    llm_json_fn=None,
) -> dict:
    """Execute the decided action through the job engine or plumber."""
    trace_id = decision.get("_trace_id", _trace_id())
    action = decision.get("action", "none")

    if not decision.get("approved", False):
        result = {
            "executed": False,
            "reason": decision.get("governance_note", "Not approved"),
            "action": action,
        }
        memory.record_episode("act_skipped", f"Action '{action}' not executed: {result['reason']}")
        result["_trace_id"] = trace_id
        return result

    if action.startswith("plumber:") or action in (
        "diagnose-and-fix",
        "diagnose-and-fix-research-cycle-failures",
        "self-heal",
        "plumber",
    ):
        return _act_plumber_phase(
            action, decision, trace_id, memory, governance_level, run_plumber_fn, llm_json_fn
        )

    if action == "research-init":
        result = {
            "executed": False,
            "reason": "Brain is not allowed to start new research runs; only UI/Telegram or explicit triggers may do so.",
            "action": action,
        }
        memory.record_episode("act_skipped", "research-init blocked: Brain may not start new research projects")
        result["_trace_id"] = trace_id
        return result

    workflow = action if (WORKFLOWS / f"{action}.sh").exists() else None

    if workflow:
        try:
            op = str(BASE / "bin" / "op")
            reason = (decision.get("reason") or "").strip()
            if workflow == "research-cycle":
                if reason.startswith("proj-"):
                    request = reason
                else:
                    m = re.search(r"proj-[a-zA-Z0-9_-]+", reason)
                    request = m.group(0) if m else reason or "unknown"
            else:
                request = f"brain::{reason}"
            job_dir = subprocess.check_output(
                [op, "job", "new", "--workflow", workflow, "--request", request],
                text=True,
            ).strip()

            if workflow == "research-cycle":
                subprocess.Popen(
                    [op, "run", job_dir],
                    cwd=str(BASE),
                    env=dict(os.environ),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                job_id = Path(job_dir).name
                result = {
                    "executed": True,
                    "workflow": workflow,
                    "job_id": job_id,
                    "job_dir": job_dir,
                    "status": "RUNNING",
                    "exit_code": None,
                }
                result["_note"] = "research-cycle started in background (all phases until done)"
                memory.record_episode(
                    "act",
                    f"Started workflow '{workflow}' -> job {job_id} in background (runs until done)",
                    job_id=job_id,
                    workflow_id=workflow,
                )
            else:
                run_result = subprocess.run(
                    [op, "run", job_dir, "--timeout", "180"],
                    capture_output=True,
                    text=True,
                    timeout=200,
                )
                job_id = Path(job_dir).name
                status = run_result.stdout.strip()
                result = {
                    "executed": True,
                    "workflow": workflow,
                    "job_id": job_id,
                    "job_dir": job_dir,
                    "status": status,
                    "exit_code": run_result.returncode,
                }
                memory.record_episode(
                    "act",
                    f"Executed workflow '{workflow}' -> job {job_id} -> {status}",
                    job_id=job_id,
                    workflow_id=workflow,
                )
        except Exception as e:
            result = {
                "executed": True,
                "workflow": workflow,
                "status": "FAILED",
                "error": str(e),
            }
            memory.record_episode("act_error", f"Workflow '{workflow}' failed: {e}", workflow_id=workflow)
    else:
        result = {
            "executed": False,
            "reason": f"No workflow found for action: {action}",
            "action": action,
        }
        memory.record_episode("act_no_workflow", f"No workflow for: {action}")

    result["_trace_id"] = trace_id
    return result
