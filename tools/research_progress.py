#!/usr/bin/env python3
import sys
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone

def _get_progress_file(project_id: str) -> Path:
    from tools.research_common import project_dir
    return project_dir(project_id) / "progress.json"

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def _read_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        try:
            return json.loads(progress_file.read_text())
        except Exception:
            return {}
    return {}

def _write_progress(progress_file: Path, data: dict):
    tmp_file = progress_file.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(data, indent=2))
    tmp_file.replace(progress_file)

def start(project_id: str, phase: str):
    progress_file = _get_progress_file(project_id)
    data = {
        "pid": os.getpid(),
        "alive": True,
        "heartbeat": _now_iso(),
        "phase": phase,
        "step": f"Starting {phase} phase...",
        "step_index": 0,
        "step_total": 0,
        "steps_completed": [],
        "started_at": _now_iso()
    }
    _write_progress(progress_file, data)

def step(project_id: str, message: str, index: int = None, total: int = None):
    progress_file = _get_progress_file(project_id)
    data = _read_progress(progress_file)
    if not data:
        data = {
            "pid": os.getpid(),
            "alive": True,
            "started_at": _now_iso(),
            "steps_completed": []
        }
    
    now = _now_iso()
    
    # Save the previous step to steps_completed if it exists
    prev_step = data.get("step")
    prev_heartbeat = data.get("heartbeat", data.get("started_at", now))
    
    if prev_step:
        try:
            # simple duration calculation
            t1 = datetime.strptime(prev_heartbeat, '%Y-%m-%dT%H:%M:%SZ')
            t2 = datetime.strptime(now, '%Y-%m-%dT%H:%M:%SZ')
            duration = int((t2 - t1).total_seconds())
        except Exception:
            duration = 0
            
        data.setdefault("steps_completed", []).append({
            "ts": prev_heartbeat,
            "step": prev_step,
            "duration_s": max(0, duration)
        })
        
        # Keep only the last 10 completed steps to prevent unbounded growth
        data["steps_completed"] = data["steps_completed"][-10:]

    data["alive"] = True
    data["heartbeat"] = now
    data["step"] = message
    if index is not None:
        data["step_index"] = index
    if total is not None:
        data["step_total"] = total
        
    _write_progress(progress_file, data)

def done(project_id: str):
    progress_file = _get_progress_file(project_id)
    data = _read_progress(progress_file)
    if data:
        data["alive"] = False
        data["heartbeat"] = _now_iso()
        data["step"] = "Done"
        _write_progress(progress_file, data)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: research_progress.py <cmd> <project_id> [args...]")
        sys.exit(1)
        
    # Must run from operator root so `tools.` import works
    op_root = Path(__file__).parent.parent
    sys.path.insert(0, str(op_root))
        
    cmd = sys.argv[1]
    project_id = sys.argv[2]
    
    if cmd == "start" and len(sys.argv) >= 4:
        start(project_id, sys.argv[3])
    elif cmd == "step" and len(sys.argv) >= 4:
        msg = sys.argv[3]
        idx = int(sys.argv[4]) if len(sys.argv) >= 5 else None
        tot = int(sys.argv[5]) if len(sys.argv) >= 6 else None
        step(project_id, msg, idx, tot)
    elif cmd == "done":
        done(project_id)
    else:
        print(f"Unknown or invalid command: {cmd}")
        sys.exit(1)
