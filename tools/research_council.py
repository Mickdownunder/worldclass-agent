#!/usr/bin/env python3
"""
The Principal Investigator (PI) Agent - V2 (Recursive Planning & Synthesis).
Reads the parent report and all child reports + experiment.json files.
Evaluates if the research question is solved.
If NOT SOLVED: spawns new children (Research Missions) and waits.
If SOLVED: Generates Master Dossier and reports back to Brain.
"""
import json
import os
import sys
import subprocess
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
sys.path.insert(0, str(OPERATOR_ROOT))
from tools.research_common import llm_call, model_for_lane
from lib.memory import Memory

RESEARCH = OPERATOR_ROOT / "research"
MAX_GENERATIONS = 3

def load_text(path: Path, max_len=15000):
    if not path.is_file(): return ""
    try:
        return path.read_text(encoding="utf-8")[:max_len]
    except Exception:
        return ""

def load_json(path: Path):
    if not path.is_file(): return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def spawn_followups(parent_id: str, missions: list):
    """Spawns follow-up agents asynchronously and links them to the parent."""
    for mission in missions:
        q = mission.get("question", "").strip()
        h = mission.get("hypothesis_to_test", "").strip()
        if not q: continue
        
        print(f"Spawning follow-up: {q[:60]}...")
        # Discovery gate: no verified_claim_count requirement (research often can't verify claims)
        req = json.dumps({"question": q, "hypothesis_to_test": h, "research_mode": "discovery"})
        
        # 1. Create and run init job (synchronously, it's fast)
        cmd_init = ["python3", str(OPERATOR_ROOT/"bin"/"op"), "job", "new", "--workflow", "research-init", "--request", req]
        r1 = subprocess.run(cmd_init, capture_output=True, text=True, cwd=str(OPERATOR_ROOT))
        if r1.returncode != 0:
            print(f"Init failed: {r1.stderr}")
            continue
            
        job_init_dir = Path(r1.stdout.strip().split("\n")[-1])
        env = os.environ.copy()
        subprocess.run(["python3", str(OPERATOR_ROOT/"bin"/"op"), "run", str(job_init_dir)], env=env, cwd=str(OPERATOR_ROOT), capture_output=True)
        
        # Get project ID
        pid_file = job_init_dir / "artifacts" / "project_id.txt"
        if not pid_file.exists():
            print("Failed to read project_id from follow-up init.")
            continue
            
        child_id = pid_file.read_text().strip()
        
        # 2. Link child to parent
        c_json_path = RESEARCH / child_id / "project.json"
        if c_json_path.exists():
            try:
                c_data = json.loads(c_json_path.read_text())
                c_data["parent_project_id"] = parent_id
                c_json_path.write_text(json.dumps(c_data, indent=2))
            except:
                pass
                
        # 3. Run the complete cycle asynchronously
        run_until_done_script = OPERATOR_ROOT / "tools" / "run-research-cycle-until-done.sh"
        if run_until_done_script.exists():
            subprocess.Popen(
                ["nohup", "bash", str(run_until_done_script), child_id],
                cwd=str(OPERATOR_ROOT), start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            # Fallback to single run if script is missing
            cmd_cycle = ["python3", str(OPERATOR_ROOT/"bin"/"op"), "job", "new", "--workflow", "research-cycle", "--request", child_id]
            r2 = subprocess.run(cmd_cycle, capture_output=True, text=True, cwd=str(OPERATOR_ROOT))
            if r2.returncode == 0:
                job_cycle_dir = r2.stdout.strip().split("\n")[-1]
                subprocess.Popen(["nohup", "python3", str(OPERATOR_ROOT/"bin"/"op"), "run", job_cycle_dir], 
                                 cwd=str(OPERATOR_ROOT), start_new_session=True, 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"-> Dispatched agent {child_id}")

def main():
    if len(sys.argv) < 2:
        print("Usage: research_council.py <parent_id>")
        sys.exit(1)
        
    parent_id = sys.argv[1].strip()
    parent_dir = RESEARCH / parent_id
    if not parent_dir.is_dir():
        sys.exit(1)
        
    p_json = load_json(parent_dir / "project.json")
    gen = p_json.get("council_generation", 0) + 1
    print(f"--- CONVENING RESEARCH COUNCIL FOR {parent_id} (Generation {gen}) ---")
    
    # Update generation
    p_json["council_generation"] = gen
    (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
    
    # 1. Gather Parent Data
    parent_report = ""
    reports_dir = parent_dir / "reports"
    if reports_dir.is_dir():
        mds = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if mds: parent_report = load_text(mds[0], 25000)
    parent_exp = load_json(parent_dir / "experiment.json")
    
    # 2. Gather Child Data (from all past generations)
    children_data = []
    for d in RESEARCH.glob("proj-*"):
        if not d.is_dir() or d.name == parent_id: continue
        c_json = load_json(d / "project.json")
        if c_json.get("parent_project_id") == parent_id:
            # We only look at terminal ones (or failed ones)
            if c_json.get("status") not in ["done", "cancelled", "abandoned", "aem_blocked"] and not c_json.get("status", "").startswith("failed"):
                continue
            
            c_report = ""
            c_reports_dir = d / "reports"
            if c_reports_dir.is_dir():
                cmds = sorted(c_reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                if cmds: c_report = load_text(cmds[0], 15000)
            
            c_exp = load_json(d / "experiment.json")
            children_data.append({
                "id": d.name,
                "question": c_json.get("question", ""),
                "hypothesis": c_json.get("hypothesis_to_test", ""),
                "report": c_report,
                "experiment": c_exp
            })
            
    # 3. Build Prompt for PI Agent
    sys_prompt = f"""You are the Principal Investigator (PI) of an elite AI research lab.
You are orchestrating an autonomous recursive research loop.

You will receive:
1. The Main Parent Research Report
2. Reports and Sandbox Experiment Logs from your Field Agents (if any have run yet).

You are in Generation {gen} of max {MAX_GENERATIONS} generations.

MANDATORY: EXAMINE EACH FIELD AGENT IN DETAIL.
- You MUST look at every Field Agent report and its sandbox results. Do not skip or gloss over any agent.
- For EACH agent, you must explicitly: (1) state the hypothesis tested, (2) state the outcome (supported / not supported / mixed) with key numbers from the report or experiment.json, (3) note any limitations or caveats the agent reported. Use exact figures (scores, counts, percentages) where the report or experiment provides them.
- Only after this per-agent evaluation, write your cross-agent synthesis. The synthesis must be grounded in what each agent actually found; do not drop findings that contradict a simple narrative.

YOUR TASK:
Evaluate the evidence. Is the overarching research question fully solved, proven, and validated by robust sandbox experiments?

IF NO (Needs more research):
- Write an 'Interim Synthesis' that first includes a clear "Evaluation per Field Agent" section (one subsection per agent with hypothesis, outcome, key numbers, caveats), then your synthesis and what failed.
- Define 1 to 4 specific 'Research Missions' for the next generation of Field Agents. Each mission must have a concrete `hypothesis_to_test` for the sandbox.

IF YES (Solved) OR if Generation >= {MAX_GENERATIONS}:
- Write the ultimate 'Bundle Synthesis Dossier' (MASTER_DOSSIER.md). Again, first include "Evaluation per Field Agent" with hypothesis, outcome, key numbers, and caveats for each agent; then cross-pollinate and synthesize new architectural rules.
- Define 1-3 'mega_principles'.

FORMAT REQUIREMENT:
Write your full markdown report first (Interim or Master Dossier). The report MUST contain an "Evaluation per Field Agent" (or equivalent) section where each agent is examined in detail.
At the very end of your output, append a single JSON block wrapped in ```json ... ``` exactly like this:
{{
  "status": "SOLVED" or "NEEDS_MORE_RESEARCH",
  "mega_principles": ["Principle 1", "Principle 2"], 
  "next_missions": [
    {{
      "question": "Topic for Agent to research",
      "hypothesis_to_test": "Concrete thesis the agent MUST prove via Python sandbox code"
    }}
  ]
}}
"""
    
    user_content = f"# PARENT RESEARCH\n\n## Main Report\n{parent_report[:10000]}\n\n## Main Experiment Logs\n{json.dumps(parent_exp, indent=2)}\n\n"
    user_content += f"# FIELD AGENT REPORTS (Past Generations)\n\n"
    
    if children_data:
        user_content += "Examine each agent below in detail. You must address every agent in your 'Evaluation per Field Agent' section with hypothesis, outcome (supported/not supported/mixed), key numbers, and caveats.\n\n"
        for i, c in enumerate(children_data):
            user_content += f"## Agent {i+1} ({c['id']})\nTopic: {c['question']}\nHypothesis: {c['hypothesis']}\n"
            user_content += f"### Full Report Excerpt (examine carefully)\n{c['report'][:12000]}\n"
            if c['experiment']:
                user_content += f"### Sandbox Experiment Results\n{json.dumps(c['experiment'], indent=2)}\n"
            user_content += "\n"
    else:
        user_content += "No field agents have run yet. This is your first evaluation of the parent report.\n"
        
    user_content += "\nNow, write your Dossier. First: 'Evaluation per Field Agent' (each agent: hypothesis, outcome, key numbers, caveats). Then: your synthesis. Then: the JSON block at the end."
    
    print("Calling PI Agent (LLM)...")
    try:
        model = model_for_lane("synthesize")
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use a slightly less constrained model if the strongest is failing repeatedly
                current_model = model if attempt == 0 else "gemini-2.5-flash"
                res = llm_call(current_model, sys_prompt, user_content, project_id=parent_id)
                text = res.text or ""
                break
            except Exception as e:
                if "503" in str(e) and attempt < max_retries - 1:
                    print(f"LLM overloaded (503), retrying in 30s with fallback model... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(30)
                else:
                    raise e
    except Exception as e:
        print(f"LLM call failed: {e}")
        p_json = load_json(parent_dir / "project.json")
        p_json["council_status"] = "failed"
        (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
        sys.exit(1)
        
    # 4. Parse output
    dossier_text = text
    parsed_json = {}
    
    import re
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            parsed_json = json.loads(json_match.group(1))
            dossier_text = text[:json_match.start()].strip()
        except Exception as e:
            print(f"Failed to parse JSON instructions from PI: {e}")
            
    decision_status = parsed_json.get("status", "SOLVED")
    
    if gen >= MAX_GENERATIONS:
        decision_status = "SOLVED"
        
    if decision_status == "SOLVED":
        # WRITE MASTER DOSSIER
        (parent_dir / "MASTER_DOSSIER.md").write_text(dossier_text, encoding="utf-8")
        
        # Sandbox Validation
        try:
            r = subprocess.run(
                [sys.executable, str(OPERATOR_ROOT / "tools" / "research_council_sandbox.py"), parent_id],
                cwd=str(OPERATOR_ROOT), capture_output=True, text=True, timeout=120
            )
            if r.returncode != 0:
                print(f"Council sandbox validation failed (non-fatal): {r.stderr or r.stdout}")
            elif r.stdout:
                print(r.stdout.strip())
        except Exception as e:
            print(f"Council sandbox validation failed (non-fatal): {e}")

        # Report to Brain
        principles = parsed_json.get("mega_principles", [])
        council_result = {"brain_injected": False, "brain_error": None}
        if principles:
            try:
                mem = Memory()
                domain = p_json.get("domain", "general")
                evidence_json = json.dumps([f"Derived from Recursive Research Council (Gen {gen}) synthesis."])
                for p in principles:
                    desc = p if isinstance(p, str) else str(p.get("description", p))
                    mem.insert_principle(
                        principle_type="council_synthesis",
                        description=desc,
                        source_project_id=parent_id,
                        domain=domain,
                        evidence_json=evidence_json,
                        metric_score=0.9,
                    )
                mem.close()
                council_result["brain_injected"] = True
                print("Successfully injected mega-principles into Brain.")
            except Exception as e:
                council_result["brain_error"] = str(e)[:500]
                print(f"Brain injection failed: {e}")
        try:
            (parent_dir / "council_result.json").write_text(
                json.dumps(council_result, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
                
        # Update Status
        p_json = load_json(parent_dir / "project.json")
        p_json["council_status"] = "done"
        (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
        print("Research Council concluded successfully with MASTER_DOSSIER!")
        
    else:
        # NEEDS MORE RESEARCH -> Spawn Gen X+1
        interim_file = parent_dir / f"INTERIM_DOSSIER_GEN_{gen}.md"
        interim_file.write_text(dossier_text, encoding="utf-8")
        missions = parsed_json.get("next_missions", [])
        
        if not missions:
            # Fallback if LLM failed to provide missions but asked for more research
            missions = [{"question": "Investigate remaining edge cases", "hypothesis_to_test": "Edge cases can be solved."}]
            
        print(f"Council demands {len(missions)} new missions. Writing Interim Dossier {gen} and waiting.")
        
        # Update Status
        p_json = load_json(parent_dir / "project.json")
        p_json["council_status"] = "waiting"
        (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
        
        spawn_followups(parent_id, missions)
        print("Council adjourned until next generation finishes.")

if __name__ == "__main__":
    main()
