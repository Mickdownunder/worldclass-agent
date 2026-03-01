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
from pathlib import Path

# Ensure operator root is in path
_OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", Path.home() / "operator"))
sys.path.insert(0, str(_OPERATOR_ROOT))

from tools.research_common import llm_call, model_for_lane, load_project
from tools.research_sandbox import run_in_sandbox

def spawn_subagent(parent_id: str, question: str) -> str:
    """Spawns a sub-agent to answer a specific technical question using op job new."""
    print(f"[Sub-Agent] Spawning for question: {question}")
    
    # 1. Create job
    cmd_new = ["python3", str(_OPERATOR_ROOT / "bin" / "op"), "job", "new", "--workflow", "research-cycle", "--request", question, "--timeout", "300"]
    res_new = subprocess.run(cmd_new, capture_output=True, text=True)
    if res_new.returncode != 0:
        return f"Failed to spawn sub-agent: {res_new.stderr}"
    
    # Parse the job directory from op job new output
    job_dir_str = res_new.stdout.strip().split("\n")[-1]
    job_dir = Path(job_dir_str)
    
    # Link it to parent for debugging
    try:
        jdata = json.loads((job_dir / "job.json").read_text())
        jdata["parent_job_id"] = parent_id
        (job_dir / "job.json").write_text(json.dumps(jdata, indent=2))
    except Exception:
        pass

    # 2. Run job synchronously
    # Apply Guardrails: No nested experiments, run on mid lane for speed/cost
    env = os.environ.copy()
    env["RESEARCH_ENABLE_EXPERIMENT_LOOP"] = "0" 
    env["RESEARCH_GOVERNOR_LANE"] = "mid"
    
    print(f"[Sub-Agent] Running job at {job_dir.name} (this might take 1-2 minutes)...")
    cmd_run = ["python3", str(_OPERATOR_ROOT / "bin" / "op"), "run", str(job_dir)]
    res_run = subprocess.run(cmd_run, capture_output=True, text=True, env=env)
    
    # --- Roll up spend from subagent to parent ---
    try:
        from tools.research_common import project_dir, save_project
        sub_data = load_project(job_dir)
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
        
    # 3. Read report
    report_path = job_dir / "artifacts" / "report.md"
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")
    
    # Fallback to logs if report failed
    log_path = job_dir / "log.txt"
    if log_path.exists():
        return f"Sub-agent failed to produce a report. Tail of logs:\n{log_path.read_text()[-1000:]}"
        
    return "Sub-agent failed completely."

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

SUB-AGENT CAPABILITY (ASK FOR HELP):
If you get stuck with an error that you cannot fix because you lack specific API knowledge or documentation, you can spawn a sub-agent to search the web for the solution.
To do this, DO NOT write Python code. Instead, output exactly this format:
SPAWN_AGENT: <your specific question here>

Example:
SPAWN_AGENT: What is the correct syntax for the forward() method in PyTorch 2.0?

You can only spawn a maximum of {max_subagents} sub-agents per experiment.
"""

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

Please fix the error and provide the updated complete, raw Python code. Or use SPAWN_AGENT if you need to research the error.
"""
            result = llm_call(model, system_prompt, error_feedback, project_id=project_id)
            current_code = result.text.strip()

        # Check for sub-agent request
        if "SPAWN_AGENT:" in current_code:
            subagent_question = ""
            for line in current_code.split("\n"):
                if line.strip().startswith("SPAWN_AGENT:"):
                    subagent_question = line.replace("SPAWN_AGENT:", "").strip()
                    break
            
            if subagent_question:
                if subagents_spawned >= max_subagents:
                    print(f"LLM requested sub-agent for '{subagent_question}', but MAX ({max_subagents}) reached. Forcing guess.")
                    error_feedback = f"You requested a sub-agent to ask: '{subagent_question}'. However, you have reached the maximum limit of {max_subagents} sub-agents. You must make your best guess and write the Python code now."
                    result = llm_call(model, system_prompt, error_feedback, project_id=project_id)
                    current_code = result.text.strip()
                else:
                    subagents_spawned += 1
                    subagent_report = spawn_subagent(project_id, subagent_question)
                    
                    error_feedback = f"""You spawned a sub-agent to ask: '{subagent_question}'.
Here is the research report returned by the sub-agent:

========================================
{subagent_report}
========================================

Now, using this new knowledge, please write the corrected complete Python code."""
                    
                    print("Feeding sub-agent knowledge back to LLM to write code...")
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
    out_file.write_text(json.dumps({
        "success": (sandbox_result.exit_code == 0 if sandbox_result else False),
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
