#!/usr/bin/env python3
"""
Checks if a project completing should trigger the Research Council.
If it's a child, it checks the parent. If all children are done/failed, triggers the council.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
RESEARCH = OPERATOR_ROOT / "research"

def get_status(proj_dir: Path) -> str:
    try:
        d = json.loads((proj_dir / "project.json").read_text())
        return d.get("status", "unknown")
    except Exception:
        return "unknown"

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    project_id = sys.argv[1].strip()
    proj_dir = RESEARCH / project_id
    if not proj_dir.is_dir():
        sys.exit(1)
    
    # Is it a child or a parent?
    parent_id = None
    try:
        d = json.loads((proj_dir / "project.json").read_text())
        parent_id = d.get("parent_project_id")
    except Exception:
        pass
    
    if not parent_id:
        parent_id = project_id # Maybe this is the parent itself completing later?
    
    parent_dir = RESEARCH / parent_id
    if not parent_dir.is_dir():
        sys.exit(0)
    
    # Get all children
    children = []
    for d in RESEARCH.glob("proj-*"):
        if not d.is_dir() or d.name == parent_id:
            continue
        try:
            p_json = json.loads((d / "project.json").read_text())
            if p_json.get("parent_project_id") == parent_id:
                children.append(d)
        except Exception:
            pass
            
    if not children:
        sys.exit(0) # No follow-ups, no council needed
        
    # Check if all children are terminal
    all_terminal = True
    for child in children:
        st = get_status(child)
        if st not in ["done", "cancelled", "abandoned", "aem_blocked"] and not st.startswith("failed"):
            all_terminal = False
            break
            
    if not all_terminal:
        print(f"[Council] Not all follow-ups of {parent_id} are done yet.")
        sys.exit(0)
        
    # Check if council already ran
    try:
        p_json = json.loads((parent_dir / "project.json").read_text())
        if p_json.get("council_status") in ["active", "done"]:
            print(f"[Council] Council for {parent_id} already active/done.")
            sys.exit(0)
            
        p_json["council_status"] = "active"
        (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
    except Exception as e:
        pass

    print(f"[Council] All children of {parent_id} are terminal! Triggering Research Council.")
    # Trigger council async
    # We will use bash nohup to let it run in the background
    council_script = OPERATOR_ROOT / "tools" / "research_council.py"
    log_file = parent_dir / "council.log"
    cmd = f"nohup python3 {council_script} {parent_id} > {log_file} 2>&1 &"
    subprocess.run(cmd, shell=True, cwd=str(OPERATOR_ROOT))

if __name__ == "__main__":
    main()
