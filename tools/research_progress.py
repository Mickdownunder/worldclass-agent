#!/usr/bin/env python3
"""Progress and event logging for research runs. Writes progress.json and events.jsonl."""
import sys
import json
import os
import fcntl
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

EVENTS_FILE_NAME = "events.jsonl"
STUCK_THRESHOLD_S = 300
HEARTBEAT_FRESH_S = 30

def _get_progress_file(project_id: str) -> Path:
    from tools.research_common import project_dir
    return project_dir(project_id) / "progress.json"

def _get_progress_lock_file(project_id: str) -> Path:
    from tools.research_common import project_dir
    return project_dir(project_id) / "progress.json.lock"

@contextmanager
def _progress_lock(project_id: str):
    """Hold exclusive lock on progress so only one writer at a time."""
    lock_file = _get_progress_lock_file(project_id)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_file, "a")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()

def _get_events_file(project_id: str) -> Path:
    from tools.research_common import project_dir
    return project_dir(project_id) / EVENTS_FILE_NAME

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _read_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        try:
            return json.loads(progress_file.read_text())
        except Exception:
            return {}
    return {}

def _write_progress(progress_file: Path, data: dict) -> None:
    tmp_file = progress_file.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(data, indent=2))
    tmp_file.replace(progress_file)


def _append_event(project_id: str, event_type: str, payload: dict) -> None:
    """Append one JSON line to events.jsonl. Payload must be JSON-serializable."""
    events_file = _get_events_file(project_id)
    events_file.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": _now_iso(), "event": event_type, **payload}, ensure_ascii=False) + "\n"
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(line)


def start(project_id: str, phase: str) -> None:
    progress_file = _get_progress_file(project_id)
    with _progress_lock(project_id):
        now = _now_iso()
        data = {
            "pid": os.getpid(),
            "alive": True,
            "heartbeat": now,
            "phase": phase,
            "step": f"Starting {phase} phase...",
            "step_started_at": now,
            "step_index": 0,
            "step_total": 0,
            "steps_completed": [],
            "started_at": now,
        }
        _write_progress(progress_file, data)
    _append_event(project_id, "phase_started", {"phase": phase})


def step(project_id: str, message: str, index: int = None, total: int = None) -> None:
    progress_file = _get_progress_file(project_id)
    with _progress_lock(project_id):
        data = _read_progress(progress_file)
        if not data:
            data = {
                "pid": os.getpid(),
                "alive": True,
                "started_at": _now_iso(),
                "steps_completed": [],
            }

        now = _now_iso()
        prev_step = data.get("step")
        prev_heartbeat = data.get("heartbeat", data.get("started_at", now))

        if prev_step:
            try:
                t1 = datetime.strptime(prev_heartbeat, "%Y-%m-%dT%H:%M:%SZ")
                t2 = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")
                duration = int((t2 - t1).total_seconds())
            except Exception:
                duration = 0
            data.setdefault("steps_completed", []).append({
                "ts": prev_heartbeat,
                "step": prev_step,
                "duration_s": max(0, duration),
            })
            data["steps_completed"] = data["steps_completed"][-10:]
            _append_event(project_id, "step_done", {"step": prev_step, "duration_s": duration})

        data["alive"] = True
        data["heartbeat"] = now
        data["step"] = message
        data["step_started_at"] = now
        if index is not None:
            data["step_index"] = index
        if total is not None:
            data["step_total"] = total
        _write_progress(progress_file, data)
    _append_event(project_id, "step_started", {"step": message, "step_index": index, "step_total": total})


def done(project_id: str) -> None:
    progress_file = _get_progress_file(project_id)
    with _progress_lock(project_id):
        data = _read_progress(progress_file)
        if data:
            data["alive"] = False
            data["heartbeat"] = _now_iso()
            data["step"] = "Done"
            _write_progress(progress_file, data)
    if data:
        _append_event(project_id, "phase_done", {"phase": data.get("phase", "")})


def error(project_id: str, code: str, message: str) -> None:
    """Record an error for this run (updates progress.json last_error and appends to events)."""
    progress_file = _get_progress_file(project_id)
    with _progress_lock(project_id):
        data = _read_progress(progress_file)
        if not data:
            data = {"pid": os.getpid(), "started_at": _now_iso(), "steps_completed": []}
        now = _now_iso()
        data["last_error"] = {"code": code, "message": (message or "")[:500], "at": now}
        data["heartbeat"] = now
        _write_progress(progress_file, data)
    _append_event(project_id, "error", {"code": code, "message": (message or "")[:500]})

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: research_progress.py <cmd> <project_id> [args...]")
        sys.exit(1)

    op_root = Path(__file__).parent.parent
    sys.path.insert(0, str(op_root))

    cmd = sys.argv[1]
    project_id = sys.argv[2]

    if cmd == "start" and len(sys.argv) >= 4:
        start(project_id, sys.argv[3])
    elif cmd == "step" and len(sys.argv) >= 4:
        msg = sys.argv[3]
        idx = int(sys.argv[4]) if len(sys.argv) >= 5 and sys.argv[4].isdigit() else None
        tot = int(sys.argv[5]) if len(sys.argv) >= 6 and sys.argv[5].isdigit() else None
        step(project_id, msg, idx, tot)
    elif cmd == "done":
        done(project_id)
    elif cmd == "error" and len(sys.argv) >= 5:
        error(project_id, sys.argv[3], sys.argv[4])
    else:
        print(f"Unknown or invalid command: {cmd}")
        sys.exit(1)
