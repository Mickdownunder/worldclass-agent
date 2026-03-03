#!/usr/bin/env python3
"""
Research Experiment Loop (Trial & Error Code Execution)
Reads the synthesized report, writes a Python script to prove/simulate the core concept,
executes it in the sandbox, and iterates on errors.

Phase 3: Sub-Agent Spawning with Guardrails
Allows the agent to pause and spawn a search job if it lacks specific knowledge.
"""

import sys
import json
import os
import subprocess
import re
from pathlib import Path

# Ensure operator root is in path
_OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", Path.home() / "operator"))
sys.path.insert(0, str(_OPERATOR_ROOT))

from tools.research_common import llm_call, model_for_lane, load_project
from tools.research_sandbox import run_in_sandbox


def _parse_bool_from_stdout(stdout: str, label_regex: str) -> bool | None:
    m = re.search(label_regex + r"\s*(True|False)\b", stdout, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower() == "true"


def _parse_percent_from_stdout(stdout: str, label_regex: str) -> float | None:
    m = re.search(label_regex + r"\s*(-?\d+(?:\.\d+)?)\s*%", stdout, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def derive_experiment_gate(stdout: str, execution_success: bool) -> dict:
    """
    Derive strict experiment gate signals from sandbox stdout.
    Execution success (exit_code=0) is necessary but not sufficient.
    """
    success_declared = bool(re.search(r"^\s*SUCCESS:", stdout, flags=re.MULTILINE))
    failure_declared = bool(re.search(r"^\s*FAILURE:", stdout, flags=re.MULTILINE))
    hypothesis_proven = bool(re.search(r"^\s*Hypothesis\s+PROVEN\b", stdout, flags=re.MULTILINE | re.IGNORECASE))
    hypothesis_not_proven = bool(re.search(r"^\s*Hypothesis\s+NOT\s+PROVEN\b", stdout, flags=re.MULTILINE | re.IGNORECASE))
    hypothesis_partially_proven = bool(re.search(r"^\s*Hypothesis\s+PARTIALLY\s+PROVEN\b", stdout, flags=re.MULTILINE | re.IGNORECASE))
    conclusion_supported = bool(re.search(r"^\s*[*_]*\s*CONCLUSION\s*:\s*.*\bSUPPORTED\b", stdout, flags=re.MULTILINE | re.IGNORECASE))
    conclusion_not_supported = bool(re.search(r"^\s*[*_]*\s*CONCLUSION\s*:\s*.*\bNOT\s+(?:STRONGLY\s+)?SUPPORTED\b", stdout, flags=re.MULTILINE | re.IGNORECASE))
    criterion_pass_count = len(
        re.findall(r"^\s*PASS:\s*Criterion\s+\d+\b", stdout, flags=re.MULTILINE | re.IGNORECASE)
    )
    criterion_fail_count = len(
        re.findall(r"^\s*FAIL:\s*Criterion\s+\d+\b", stdout, flags=re.MULTILINE | re.IGNORECASE)
    )
    performance_met = _parse_bool_from_stdout(stdout, r"Performance Met\s*\([^)]+\):")
    replication_met = _parse_bool_from_stdout(stdout, r"Robustness \(all replications[^)]*\):")
    std_met = _parse_bool_from_stdout(stdout, r"Robustness \(std dev acceptable\):")
    achieved_improvement_percent = _parse_percent_from_stdout(stdout, r"Achieved mean improvement:")

    # Objective is met only when execution is successful and either:
    # - explicit SUCCESS marker exists and no FAILURE marker, or
    # - explicit "Hypothesis PROVEN" marker exists and no negative hypothesis marker, or
    # - conclusion explicitly states SUPPORTED (and not NOT SUPPORTED), or
    # - all listed criteria are PASS with no FAILs, or
    # - all machine-readable gate booleans are true.
    bool_triplet_available = (
        performance_met is not None and replication_met is not None and std_met is not None
    )
    bool_triplet_passed = bool_triplet_available and performance_met and replication_met and std_met
    objective_met = execution_success and (
        (success_declared and not failure_declared) or
        (hypothesis_proven and not hypothesis_not_proven and not hypothesis_partially_proven) or
        (conclusion_supported and not conclusion_not_supported) or
        (criterion_pass_count > 0 and criterion_fail_count == 0) or
        bool_triplet_passed
    )

    reasons: list[str] = []
    if not execution_success:
        reasons.append("sandbox_execution_failed")
    if failure_declared:
        reasons.append("explicit_failure_marker")
    if hypothesis_not_proven:
        reasons.append("hypothesis_not_proven")
    if hypothesis_partially_proven:
        reasons.append("hypothesis_only_partially_proven")
    if conclusion_not_supported:
        reasons.append("hypothesis_not_supported_by_conclusion")
    if criterion_fail_count > 0:
        reasons.append("one_or_more_validation_criteria_failed")
    if performance_met is False:
        reasons.append("performance_threshold_not_met")
    if replication_met is False:
        reasons.append("replication_gate_not_met")
    if std_met is False:
        reasons.append("stability_gate_not_met")
    if execution_success and not objective_met and not reasons:
        reasons.append("objective_not_demonstrated")

    return {
        "objective_met": objective_met,
        "execution_success": execution_success,
        "performance_gate_passed": performance_met,
        "replication_gate_passed": replication_met,
        "stability_gate_passed": std_met,
        "achieved_improvement_percent": achieved_improvement_percent,
        "success_marker_present": success_declared,
        "failure_marker_present": failure_declared,
        "hypothesis_proven_marker_present": hypothesis_proven,
        "hypothesis_not_proven_marker_present": hypothesis_not_proven,
        "hypothesis_partially_proven_marker_present": hypothesis_partially_proven,
        "conclusion_supported_marker_present": conclusion_supported,
        "conclusion_not_supported_marker_present": conclusion_not_supported,
        "criterion_pass_count": criterion_pass_count,
        "criterion_fail_count": criterion_fail_count,
        "reasons": reasons,
    }

def spawn_subagent(parent_id: str, question: str) -> str:
    """Spawns a sub-agent to answer a specific technical question: research-init (creates project from question) then research-cycle (runs full pipeline)."""
    print(f"[Sub-Agent] Spawning for question: {question}")
    env = os.environ.copy()
    env["RESEARCH_ENABLE_EXPERIMENT_LOOP"] = "0"
    env["RESEARCH_GOVERNOR_LANE"] = "mid"
    op = str(_OPERATOR_ROOT / "bin" / "op")

    # 1. Create and run research-init so we get a real project_id (research-cycle expects project_id, not the question)
    cmd_new = ["python3", op, "job", "new", "--workflow", "research-init", "--request", question]
    res_new = subprocess.run(cmd_new, capture_output=True, text=True, cwd=str(_OPERATOR_ROOT))
    if res_new.returncode != 0:
        return f"Failed to create init job: {res_new.stderr}"
    job_init_dir = Path(res_new.stdout.strip().split("\n")[-1])
    if not job_init_dir.is_dir():
        return "Failed to create init job dir."
    print(f"[Sub-Agent] Running research-init (create project from question)...")
    res_init = subprocess.run(["python3", op, "run", str(job_init_dir)], capture_output=True, text=True, env=env, cwd=str(_OPERATOR_ROOT))
    project_id_file = job_init_dir / "artifacts" / "project_id.txt"
    if not project_id_file.exists():
        return f"Sub-agent init failed (no project_id). stderr: {(res_init.stderr or '')[-500:]}"
    sub_project_id = project_id_file.read_text().strip()
    if not sub_project_id:
        return "Sub-agent init failed (empty project_id)."

    # Link sub-agent project to parent so UI/graph show it as follow-up, not a first-round project
    sub_proj_dir = _OPERATOR_ROOT / "research" / sub_project_id
    if sub_proj_dir.exists():
        try:
            from tools.research_common import load_project, save_project
            sub_data = load_project(sub_proj_dir)
            sub_data["parent_project_id"] = parent_id
            save_project(sub_proj_dir, sub_data)
        except Exception:
            pass

    # 2. Run research-cycle for that project_id so the report is generated
    cmd_cycle = ["python3", op, "job", "new", "--workflow", "research-cycle", "--request", sub_project_id]
    res_cycle_new = subprocess.run(cmd_cycle, capture_output=True, text=True, cwd=str(_OPERATOR_ROOT))
    if res_cycle_new.returncode != 0:
        return f"Failed to create cycle job: {res_cycle_new.stderr}"
    job_cycle_dir = Path(res_cycle_new.stdout.strip().split("\n")[-1])
    if not job_cycle_dir.is_dir():
        return "Failed to create cycle job dir."
    try:
        jdata = json.loads((job_cycle_dir / "job.json").read_text())
        jdata["parent_job_id"] = parent_id
        (job_cycle_dir / "job.json").write_text(json.dumps(jdata, indent=2))
    except Exception:
        pass
    print(f"[Sub-Agent] Running research-cycle for {sub_project_id} (this may take 1–2 minutes)...")
    subprocess.run(["python3", op, "run", str(job_cycle_dir)], capture_output=True, text=True, env=env, cwd=str(_OPERATOR_ROOT))

    # 3. Roll up spend from the sub research project to parent
    try:
        from tools.research_common import project_dir, save_project
        sub_proj_dir = _OPERATOR_ROOT / "research" / sub_project_id
        if sub_proj_dir.exists():
            sub_data = load_project(sub_proj_dir)
            sub_spend = sub_data.get("current_spend", 0.0)
            if sub_spend > 0:
                parent_dir = project_dir(parent_id)
                parent_data = load_project(parent_dir)
                parent_data["current_spend"] = round(parent_data.get("current_spend", 0.0) + sub_spend, 8)
                parent_data.setdefault("spend_breakdown", {})
                for k, v in sub_data.get("spend_breakdown", {}).items():
                    parent_data["spend_breakdown"][k] = round(parent_data["spend_breakdown"].get(k, 0.0) + v, 8)
                save_project(parent_dir, parent_data)
                print(f"[Sub-Agent] Rolled up ${sub_spend:.4f} spend to parent {parent_id}")
    except Exception as e:
        print(f"[Sub-Agent] Failed to roll up spend: {e}")

    # 4. Read report: cycle job writes to artifacts/report.md; fallback to research project reports/
    report_path = job_cycle_dir / "artifacts" / "report.md"
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")
    proj_reports = _OPERATOR_ROOT / "research" / sub_project_id / "reports"
    if proj_reports.exists():
        md_files = sorted(proj_reports.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if md_files:
            return md_files[0].read_text(encoding="utf-8")
    log_path = job_cycle_dir / "log.txt"
    if log_path.exists():
        return f"Sub-agent report not found. Tail of logs:\n{log_path.read_text()[-1000:]}"
    return "Sub-agent failed to produce a report."

def run_experiment_loop(project_id: str, max_iterations: int = 5, max_subagents: int = 3):
    proj_dir = _OPERATOR_ROOT / "research" / project_id
    if not proj_dir.exists():
        print(f"Project directory not found: {proj_dir}", file=sys.stderr)
        sys.exit(1)

    # Prevent recursive experiments (if this is a subagent)
    if os.environ.get("RESEARCH_ENABLE_EXPERIMENT_LOOP") == "0":
        print("Experiment loop disabled by environment (likely a sub-agent). Exiting.")
        sys.exit(0)

    # 1. Get the synthesized report (from project reports/ or job artifacts)
    report_path = proj_dir / "artifacts" / "report.md"
    if not report_path.exists():
        reports_dir = proj_dir / "reports"
        if reports_dir.exists():
            md_files = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                report_path = md_files[0]
    if not report_path.exists():
        print("No report.md found to experiment on.", file=sys.stderr)
        sys.exit(1)

    report_text = report_path.read_text(encoding="utf-8")
    project_data = load_project(proj_dir)
    question = project_data.get("question", "")
    hypothesis = project_data.get("hypothesis_to_test", "")

    # We use the strong lane for writing code
    model = model_for_lane("synthesize")
    if "gemini" not in model and "gpt" not in model:
        model = "gemini-3.1-pro-preview" # Default fallback for strong coding

    system_prompt = f"""You are an Autonomous AI Researcher and Senior Python Engineer.
Your task is to read the research report and the user's original question, and write a self-contained Python script to PROVE, SIMULATE, or TEST the core hypothesis or architecture proposed in the report.

CRITICAL RULES FOR THE PYTHON CODE:
1. It MUST be 100% self-contained (no external APIs, no internet access).
2. It MUST execute quickly (timeout is 30 seconds).
3. If it requires data, simulate or mock the data within the script.
4. It MUST print clear success criteria or metrics to stdout.
5. Do NOT use UI libraries or web frameworks. Just pure CLI/logic.
6. OUTPUT ONLY VALID PYTHON CODE. No markdown formatting like ```python ... ``` around the final answer, JUST the raw code text starting with import. If you must explain, use python comments.
7. The sandbox has Python 3.11 with numpy and scipy available (no torch, no pip at runtime, no network). Use numpy/scipy for arrays, math, stats, and simulations. If you get an import or runtime error, fix the code within these constraints. You cannot start further research rounds from here; only the Research Council may start new research rounds.
"""
    if hypothesis:
        system_prompt += f"\n\nPI DIRECTIVE (CRITICAL): Your specific mission from the Council is to test this exact hypothesis in the sandbox:\n'{hypothesis}'\nYou must structure your code to actively prove or disprove this specific claim."

    user_prompt = f"""Original Question: {question}

Research Report:
{report_text}

Write the Python code to test the core ideas from this report.
"""

    print(f"Starting Experiment Loop for {project_id} (max {max_iterations} iterations)...")
    
    experiment_history = []
    current_code = ""
    subagents_spawned = 0
    sandbox_result = None
    
    for iteration in range(1, max_iterations + 1):
        print(f"\n--- Iteration {iteration} ---")
        
        # Generate code
        if iteration == 1:
            print("Generating initial code hypothesis...")
            result = llm_call(model, system_prompt, user_prompt, project_id=project_id)
            current_code = result.text.strip()
        else:
            print("Refining code based on error...")
            error_feedback = f"""The previous code failed or had issues. 
Previous Code:
```python
{current_code}
```

Sandbox Error Output:
```
{sandbox_result.stderr if sandbox_result else 'Unknown'}
```
Sandbox Exit Code: {sandbox_result.exit_code if sandbox_result else 'Unknown'}

Please fix the error and provide the updated complete, raw Python code. Sandbox has numpy and scipy (no torch, no network).
"""
            result = llm_call(model, system_prompt, error_feedback, project_id=project_id)
            current_code = result.text.strip()

        # No sub-agent spawning: further research rounds may only be initiated by the Council.
        if "SPAWN_AGENT:" in current_code:
            print("LLM requested sub-agent; not allowed. Only the Council may start new research rounds.")
            error_feedback = "You attempted to spawn a sub-agent. That is disabled. The sandbox has numpy and scipy (no torch). Rewrite the code using numpy/scipy or stdlib. Output only valid Python code."
            result = llm_call(model, system_prompt, error_feedback, project_id=project_id)
            current_code = result.text.strip()

        # Clean the output just in case the LLM ignored the instruction
        if current_code.startswith("```python"):
            current_code = current_code[9:]
        if current_code.startswith("```"):
            current_code = current_code[3:]
        if current_code.endswith("```"):
            current_code = current_code[:-3]
        current_code = current_code.strip()

        print("Executing code in secure sandbox...")
        sandbox_result = run_in_sandbox(current_code, timeout_seconds=30)
        
        entry = {
            "iteration": iteration,
            "code": current_code,
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "exit_code": sandbox_result.exit_code,
            "timeout": sandbox_result.timeout
        }
        experiment_history.append(entry)
        
        if sandbox_result.exit_code == 0:
            print("SUCCESS! The code executed perfectly.")
            print(f"Output:\n{sandbox_result.stdout.strip()}")
            break
        else:
            print(f"FAILED (Exit code {sandbox_result.exit_code}).")
            print(f"Error:\n{sandbox_result.stderr.strip()}")

    # Save experiment results
    out_file = proj_dir / "experiment.json"
    execution_success = (sandbox_result.exit_code == 0 if sandbox_result else False)
    final_stdout = (sandbox_result.stdout if sandbox_result else "") or ""
    gate = derive_experiment_gate(final_stdout, execution_success)
    out_file.write_text(json.dumps({
        "success": execution_success,
        "objective_met": gate.get("objective_met", False),
        "gate": gate,
        "iterations": iteration,
        "subagents_spawned": subagents_spawned,
        "history": experiment_history
    }, indent=2))
    print(f"\nExperiment saved to {out_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: research_experiment.py <project_id>")
        sys.exit(1)
    run_experiment_loop(sys.argv[1])
