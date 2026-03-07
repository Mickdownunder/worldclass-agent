"""Phase 5: REFLECT — Evaluate outcome and extract learnings."""
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

from lib.brain.constants import REFLECT_LLM_TIMEOUT_SEC
from lib.brain.helpers import _reflection_is_low_signal, _trace_id


def reflect_phase(
    action_result: dict,
    goal: str,
    memory,
    retrieved_principle_ids: list | None,
    llm_json_fn,
) -> dict:
    """Use LLM to reflect on the action's outcome; record reflection, quality, playbook, principles."""
    trace_id = action_result.get("_trace_id", _trace_id())
    job_id = action_result.get("job_id", "unknown")

    job_context = ""
    if action_result.get("job_dir"):
        log_path = Path(action_result["job_dir"]) / "log.txt"
        if log_path.exists():
            job_context = log_path.read_text()[-2000:]
        artifacts_dir = Path(action_result["job_dir"]) / "artifacts"
        if artifacts_dir.exists():
            art_names = [f.name for f in artifacts_dir.iterdir() if f.is_file()]
            job_context += f"\nArtifacts: {art_names}"

    system_prompt = """You are reflecting on a completed action. Evaluate it honestly.

Output valid JSON:
{
  "outcome_summary": "What happened in 1-2 sentences",
  "went_well": "What worked",
  "went_wrong": "What didn't work (or 'nothing' if all good)",
  "learnings": "Key takeaway for future runs",
  "quality_score": 0.0-1.0,
  "should_retry": false,
  "playbook_update": "Strategy suggestion for this type of task (or null)"
}

Be honest and specific. A failed job with useful error info is more valuable than a vague success."""

    user_prompt = f"GOAL: {goal}\n\nACTION RESULT:\n{json.dumps(action_result, indent=2, default=str)}\n\nJOB LOG (tail):\n{job_context[-3000:]}"

    llm_error = None
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(llm_json_fn, system_prompt, user_prompt)
            reflection = future.result(timeout=REFLECT_LLM_TIMEOUT_SEC)
    except (FuturesTimeoutError, TimeoutError):
        reflection = None
        llm_error = Exception(f"LLM reflection timed out after {REFLECT_LLM_TIMEOUT_SEC}s")
    except Exception as exc:
        reflection = None
        llm_error = exc

    if reflection is None:
        status = action_result.get("status", "unknown")
        exit_code = action_result.get("exit_code", -1)
        job_dir = action_result.get("job_dir", "")
        log_text = ""
        if job_dir:
            log_path = Path(job_dir) / "log.txt"
            if log_path.exists():
                try:
                    log_text = log_path.read_text()[-500:]
                except Exception:
                    pass
        if status == "DONE" and exit_code == 0:
            q = 0.75
            outcome = "Job completed successfully"
            went_well = "Execution completed without errors"
            went_wrong = "LLM reflection unavailable — using metrics-based assessment"
        elif status == "FAILED":
            q = 0.25
            outcome = f"Job failed (exit code {exit_code})"
            went_well = "none"
            went_wrong = f"Job failed: {log_text[-200:]}" if log_text else "Unknown failure"
        else:
            q = 0.4
            outcome = f"Job status: {status}"
            went_well = "Partial completion"
            went_wrong = "Unclear outcome"
        err_msg = str(llm_error or "").lower()
        if "429" in err_msg or "quota" in err_msg or "exceeded your current quota" in err_msg:
            llm_reason = "API quota / rate limit"
        elif "timeout" in err_msg:
            llm_reason = "timeout"
        else:
            llm_reason = "temporarily unavailable"
        reflection = {
            "outcome_summary": outcome,
            "went_well": went_well,
            "went_wrong": went_wrong,
            "learnings": f"Metrik-basierte Bewertung (Reflection-LLM {llm_reason}).",
            "quality_score": q,
            "should_retry": status == "FAILED",
            "playbook_update": None,
        }

    quality = float(reflection.get("quality_score", 0.5))
    outcome_summary = (reflection.get("outcome_summary") or "").strip()
    learnings = (reflection.get("learnings") or "").strip()
    low_signal = _reflection_is_low_signal(outcome_summary, learnings, quality)
    reflection_metadata = {"low_signal": low_signal} if low_signal else None

    memory.record_reflection(
        job_id=job_id,
        outcome=outcome_summary,
        quality=quality,
        workflow_id=action_result.get("workflow"),
        goal=goal,
        went_well=reflection.get("went_well"),
        went_wrong=reflection.get("went_wrong"),
        learnings=reflection.get("learnings"),
        metadata=reflection_metadata,
    )
    memory.record_quality(
        job_id=job_id,
        score=quality,
        workflow_id=action_result.get("workflow"),
        notes=reflection.get("learnings", ""),
    )

    if reflection.get("playbook_update"):
        domain = action_result.get("workflow", "general")
        memory.upsert_playbook(
            domain=domain,
            strategy=reflection["playbook_update"],
            evidence=[f"job:{job_id}"],
            success_rate=quality,
        )

    learnings = (reflection.get("learnings") or "").strip()
    if learnings and len(learnings) > 20 and quality >= 0.7:
        memory.insert_principle(
            principle_type="guiding",
            description=learnings[:300],
            source_project_id=job_id,
            domain=action_result.get("workflow", ""),
            metric_score=quality,
        )
    elif learnings and len(learnings) > 20 and quality <= 0.3:
        memory.insert_principle(
            principle_type="cautionary",
            description=learnings[:300],
            source_project_id=job_id,
            domain=action_result.get("workflow", ""),
            metric_score=1 - quality,
        )

    memory.record_decision(
        phase="reflect",
        inputs={"job_id": job_id, "status": action_result.get("status")},
        reasoning=reflection.get("outcome_summary", ""),
        decision="quality=%s, retry=%s" % (quality, reflection.get("should_retry", False)),
        confidence=quality,
        trace_id=trace_id,
        job_id=job_id,
    )

    if retrieved_principle_ids:
        try:
            memory.update_utilities_from_outcome(
                "principle", retrieved_principle_ids, quality, context_key=(goal or None)
            )
        except Exception:
            pass

    reflection["_trace_id"] = trace_id
    return reflection
