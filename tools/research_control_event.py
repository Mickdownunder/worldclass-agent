#!/usr/bin/env python3
"""Structured control-plane events for research lifecycle handoffs."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.control_plane_contract import build_control_plane_event


CONTROL_PLANE_LOG_NAME = "control-plane-events.jsonl"


def _operator_root() -> Path:
    return Path(os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator")))


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_events_file(project_id: str) -> Path:
    return _operator_root() / "research" / project_id / "events.jsonl"


def _global_events_file() -> Path:
    return _operator_root() / "logs" / CONTROL_PLANE_LOG_NAME


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "a", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _job_context() -> dict[str, str]:
    job_file = Path.cwd() / "job.json"
    if not job_file.exists():
        return {}
    try:
        payload = json.loads(job_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        "job_id": str(payload.get("id") or ""),
        "workflow_id": str(payload.get("workflow_id") or ""),
        "job_request": str(payload.get("request") or ""),
    }


def emit_event(project_id: str, event_type: str, payload: dict[str, Any], *, event_id: str | None = None) -> dict[str, Any]:
    record = build_control_plane_event(
        project_id=project_id,
        event_type=event_type,
        payload=payload,
        ts=_utcnow(),
        event_id=event_id or uuid.uuid4().hex[:16],
        job_context=_job_context(),
    )
    _append_jsonl(_project_events_file(project_id), record)
    _append_jsonl(_global_events_file(), record)
    return record


def emit_research_cycle_completed(
    *,
    project_id: str,
    completed_phase: str,
    resulting_phase: str,
    resulting_status: str,
    research_mode: str,
    council_triggered: bool,
) -> dict[str, Any]:
    return emit_event(
        project_id,
        "research_cycle_completed",
        {
            "source": "research-phase.sh",
            "authority_scope": "operator_local",
            "completed_phase": completed_phase,
            "resulting_phase": resulting_phase,
            "resulting_status": resulting_status,
            "research_mode": research_mode,
            "council_triggered": council_triggered,
            "handoff_required": True,
            "handoff_target": "june",
        },
    )


def emit_research_project_initialized(
    *,
    project_id: str,
    request_event_id: str,
    question: str,
    research_mode: str,
    source: str = "june-control-plane-handoff",
    source_command: str = "",
    mission_id: str = "",
    parent_project_id: str = "",
    hypothesis_to_test: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": source,
        "authority_scope": "canonical_intake",
        "control_plane_owner": "june",
        "request_event_id": request_event_id,
        "question": question,
        "research_mode": research_mode,
    }
    if source_command:
        payload["source_command"] = source_command
    if mission_id:
        payload["mission_id"] = mission_id
    if parent_project_id:
        payload["parent_project_id"] = parent_project_id
    if hypothesis_to_test:
        payload["hypothesis_to_test"] = hypothesis_to_test
    return emit_event(project_id, "research_project_initialized", payload)


def _load_last_control_plane_event_from_path(path: Path, *, event_types: tuple[str, ...] | None = None) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event_scope") != "control_plane":
            continue
        if event_types and payload.get("event") not in event_types:
            continue
        return payload
    return None


def load_last_control_plane_event(*, event_types: tuple[str, ...] | None = None) -> dict[str, Any] | None:
    return _load_last_control_plane_event_from_path(_global_events_file(), event_types=event_types)


def load_last_project_control_plane_event(project_id: str, event_types: tuple[str, ...] | None = None) -> dict[str, Any] | None:
    return _load_last_control_plane_event_from_path(_project_events_file(project_id), event_types=event_types)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit structured control-plane events for research lifecycle handoffs.")
    parser.add_argument("command", choices=["research-cycle-completed"])
    parser.add_argument("project_id")
    parser.add_argument("--completed-phase", required=True)
    parser.add_argument("--resulting-phase", required=True)
    parser.add_argument("--resulting-status", required=True)
    parser.add_argument("--research-mode", required=True)
    parser.add_argument("--council-triggered", choices=["0", "1"], default="0")
    args = parser.parse_args()

    event = emit_research_cycle_completed(
        project_id=args.project_id,
        completed_phase=args.completed_phase,
        resulting_phase=args.resulting_phase,
        resulting_status=args.resulting_status,
        research_mode=args.research_mode,
        council_triggered=args.council_triggered == "1",
    )
    print(json.dumps(event, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
