#!/usr/bin/env python3
"""
Checks if a project completing should trigger the Research Council.
Supports recursive Council V2: 
1. If Parent is done and has no council_status -> Trigger Gen 1.
2. If Child is terminal, checks if all siblings are terminal. If yes, checks parent. -> Trigger Gen X.
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

def get_mode(proj_json: dict) -> str:
    cfg = proj_json.get("config") or {}
    if isinstance(cfg, dict):
        return str(cfg.get("research_mode") or "standard").strip().lower()
    return "standard"

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    project_id = sys.argv[1].strip()
    proj_dir = RESEARCH / project_id
    if not proj_dir.is_dir():
        sys.exit(1)
    
    try:
        p_json = json.loads((proj_dir / "project.json").read_text())
    except Exception:
        sys.exit(1)
        
    parent_id = p_json.get("parent_project_id")
    is_parent = not parent_id

    if is_parent:
        parent_id = project_id
        parent_dir = proj_dir
        # Parent itself just finished. Ensure it is fully done or failed
        st = p_json.get("status", "")
        mode = get_mode(p_json)
        # Discovery: trigger council only on terminal success (done), never on failed_quality_gate etc.
        if mode == "discovery":
            if st != "done":
                sys.exit(0)
        elif st != "done" and not st.startswith("failed"):
            sys.exit(0)
        # Check if council is already active or done (we only want to trigger it once for the parent's own completion)
        c_status = p_json.get("council_status")
        if c_status in ["active", "done", "waiting"]:
            sys.exit(0)
    else:
        # A child finished. Check siblings.
        parent_dir = RESEARCH / parent_id
        if not parent_dir.is_dir():
            sys.exit(0)
            
        all_terminal = True
        for d in RESEARCH.glob("proj-*"):
            if not d.is_dir():
                continue
            try:
                c_json = json.loads((d / "project.json").read_text())
                if c_json.get("parent_project_id") == parent_id:
                    st = c_json.get("status", "unknown")
                    # Needs to be terminal
                    if st not in ["done", "cancelled", "abandoned", "aem_blocked"] and not st.startswith("failed"):
                        all_terminal = False
                        break
            except Exception:
                pass
                
        if not all_terminal:
            print(f"[Council] Not all follow-ups of {parent_id} are done yet.")
            sys.exit(0)
            
        # All children are terminal. Ensure council is not already active/done.
        try:
            parent_json = json.loads((parent_dir / "project.json").read_text())
            c_status = parent_json.get("council_status")
            mode = get_mode(parent_json)
            # Discovery: only trigger when parent completed successfully (done)
            if mode == "discovery" and parent_json.get("status") != "done":
                print(f"[Council] Discovery parent {parent_id} not done; skipping council trigger.")
                sys.exit(0)
            if c_status in ["active", "done"]:
                print(f"[Council] Council for {parent_id} is already {c_status}.")
                sys.exit(0)
        except Exception:
            pass

    # Trigger council async
    print(f"[Council] Conditions met for {parent_id}. Triggering Research Council.")
    try:
        p_json = json.loads((parent_dir / "project.json").read_text())
        p_json["council_status"] = "active"
        (parent_dir / "project.json").write_text(json.dumps(p_json, indent=2))
    except Exception:
        pass

    council_script = OPERATOR_ROOT / "tools" / "research_council.py"
    log_file = parent_dir / "council.log"
    # Use full python path and detach properly, unsetting sandbox proxies to avoid Connection Refused
    cmd = f"env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy nohup python3 {council_script} {parent_id} >> {log_file} 2>&1 < /dev/null &"
    subprocess.run(cmd, shell=True, cwd=str(OPERATOR_ROOT))

if __name__ == "__main__":
    main()
