#!/usr/bin/env python3
"""
The Principal Investigator (PI) Agent.
Reads the parent report and all child reports + experiment.json files.
Generates a Master Dossier and reports back to the Brain (Memory).
"""
import json
import os
import sys
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
sys.path.insert(0, str(OPERATOR_ROOT))
from tools.research_common import llm_call, model_for_lane
from lib.memory import Memory

RESEARCH = OPERATOR_ROOT / "research"

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

def main():
    if len(sys.argv) < 2:
        print("Usage: research_council.py <parent_id>")
        sys.exit(1)
        
    parent_id = sys.argv[1].strip()
    parent_dir = RESEARCH / parent_id
    if not parent_dir.is_dir():
        sys.exit(1)
        
    print(f"--- CONVENING RESEARCH COUNCIL FOR {parent_id} ---")
    
    # 1. Gather Parent Data
    parent_report = ""
    reports_dir = parent_dir / "reports"
    if reports_dir.is_dir():
        mds = sorted(reports_dir.glob("*.md"), reverse=True)
        if mds: parent_report = load_text(mds[0], 25000)
    
    parent_exp = load_json(parent_dir / "experiment.json")
    
    # 2. Gather Child Data
    children_data = []
    for d in RESEARCH.glob("proj-*"):
        if not d.is_dir() or d.name == parent_id: continue
        p_json = load_json(d / "project.json")
        if p_json.get("parent_project_id") == parent_id:
            child_report = ""
            c_reports = d / "reports"
            if c_reports.is_dir():
                cmds = sorted(c_reports.glob("*.md"), reverse=True)
                if cmds: child_report = load_text(cmds[0], 15000)
            
            child_exp = load_json(d / "experiment.json")
            children_data.append({
                "id": d.name,
                "question": p_json.get("question", ""),
                "report": child_report,
                "experiment": child_exp
            })
            
    if not children_data:
        print("No children found. Council adjourned.")
        sys.exit(0)
        
    # 3. Build Prompt for PI Agent
    sys_prompt = (
        "You are the Principal Investigator (PI) of an elite AI research lab. "
        "You assigned a main research topic, and then sent out field agents to do follow-up deep dives and code experiments. "
        "Your goal is to write the ultimate 'Bundle Synthesis Dossier' (MASTER_DOSSIER.md). "
        "Do NOT just summarize. Cross-pollinate the findings. If Agent A found a problem in an experiment, and Agent B's theory solves it, highlight that. "
        "Produce a highly professional, cohesive markdown report (min 800 words) that represents the pinnacle of this research bundle. "
        "Also, at the very end of your response, output a single JSON block wrapped in ```json ... ``` containing 1-3 'mega_principles' we should remember for the future."
    )
    
    user_content = f"# PARENT RESEARCH\n\n## Main Report\n{parent_report[:10000]}\n\n## Main Experiment Logs\n{json.dumps(parent_exp, indent=2)}\n\n"
    user_content += "# FIELD AGENT REPORTS\n\n"
    
    for i, c in enumerate(children_data):
        user_content += f"## Agent {i+1} (Topic: {c['question']})\n"
        user_content += f"### Report Excerpt\n{c['report'][:8000]}\n"
        if c['experiment']:
            user_content += f"### Sandbox Experiment Results\n{json.dumps(c['experiment'], indent=2)}\n"
        user_content += "\n"
        
    user_content += "\nNow, synthesize the Master Dossier and include the JSON block at the end."
    
    print("Calling PI Agent (LLM)...")
    try:
        model = model_for_lane("synthesize") # usually a smart model
        res = llm_call(model, sys_prompt, user_content, project_id=parent_id)
        text = res.text or ""
    except Exception as e:
        print(f"LLM call failed: {e}")
        # Reset status so it can be retried
        p_json = load_json(parent_dir / "project.json")
        p_json["council_status"] = "failed"
        (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
        sys.exit(1)
        
    # Parse output
    dossier_text = text
    principles = []
    
    import re
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            principles = data.get("mega_principles", [])
            dossier_text = text[:json_match.start()].strip()
        except Exception as e:
            print(f"Failed to parse JSON principles: {e}")
            
    # Save Master Dossier
    (parent_dir / "MASTER_DOSSIER.md").write_text(dossier_text, encoding="utf-8")

    # Validate core thesis in sandbox (extract claim → run Python in Docker → append result to dossier)
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, str(OPERATOR_ROOT / "tools" / "research_council_sandbox.py"), parent_id],
            cwd=str(OPERATOR_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode != 0:
            print(f"Council sandbox validation failed (non-fatal): {r.stderr or r.stdout}")
        elif r.stdout:
            print(r.stdout.strip())
    except Exception as e:
        print(f"Council sandbox validation failed (non-fatal): {e}")

    # Report to Brain
    if principles:
        try:
            mem = Memory()
            domain = load_json(parent_dir / "project.json").get("domain", "general")
            for p in principles:
                desc = p if isinstance(p, str) else str(p.get("description", p))
                mem.insert_principle(
                    domain=domain,
                    description=desc,
                    evidence="Derived from Research Council cross-pollination of multiple runs and sandbox experiments.",
                    confidence=0.9,
                    principle_type="council_synthesis"
                )
            mem.close()
            print("Successfully injected mega-principles into Brain.")
        except Exception as e:
            print(f"Brain injection failed: {e}")
            
    # Update Status
    p_json = load_json(parent_dir / "project.json")
    p_json["council_status"] = "done"
    (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
    print("Research Council concluded successfully!")

if __name__ == "__main__":
    main()
