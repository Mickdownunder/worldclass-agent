#!/usr/bin/env python3
"""Operator-side client for June-owned research control-plane handoffs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator")))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_plane_contract import VALID_RESEARCH_MODES, validate_project_id
from tools.research_control_event import emit_event

JUNE_HANDOFF_BIN = Path(os.environ.get("JUNE_CONTROL_PLANE_HANDOFF_BIN", "/root/agent/workspace/bin/june-control-plane-handoff"))


def _run_june_handoff(args: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        ["python3", str(JUNE_HANDOFF_BIN), *args],
        cwd=str(ROOT),
        env={**os.environ, "OPERATOR_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    stdout = (completed.stdout or "").strip()
    payload: dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid june handoff response: {exc}") from exc
    if completed.returncode != 0:
        detail = payload.get("error") if isinstance(payload.get("error"), str) else (completed.stderr or stdout or "june handoff failed").strip()
        raise RuntimeError(detail)
    return payload


def submit_research_start(
    question: str,
    *,
    source_command: str,
    research_mode: str = "standard",
    run_until_done: bool = True,
    parent_project_id: str = "",
    hypothesis_to_test: str = "",
    timeout: int = 180,
) -> dict[str, Any]:
    clean_question = question.strip()
    if not clean_question:
        raise RuntimeError("question is required")
    if len(clean_question) > 4000:
        raise RuntimeError("question too long")
    if not source_command.strip():
        raise RuntimeError("source_command is required")
    mode = research_mode if research_mode in VALID_RESEARCH_MODES else "standard"
    clean_parent_project_id = parent_project_id.strip()
    if clean_parent_project_id:
        validate_project_id(clean_parent_project_id)
    clean_hypothesis = hypothesis_to_test.strip()
    request_event_id = uuid.uuid4().hex[:16]
    args = [
        "research-start",
        "--question",
        clean_question,
        "--research-mode",
        mode,
        "--run-until-done",
        "1" if run_until_done else "0",
        "--source-command",
        source_command,
        "--request-event-id",
        request_event_id,
    ]
    if clean_parent_project_id:
        args.extend(["--parent-project-id", clean_parent_project_id])
    if clean_hypothesis:
        args.extend(["--hypothesis-to-test", clean_hypothesis])

    payload = _run_june_handoff(args, timeout=timeout)
    project_id = validate_project_id(str(payload.get("projectId") or ""))
    emit_event(
        project_id,
        "research_start_requested",
        {
            "source": source_command,
            "authority_scope": "canonical_intake",
            "control_plane_owner": "june",
            "question": clean_question,
            "research_mode": mode,
            "run_until_done": run_until_done,
            "init_job_id": "delegated_to_june",
            "source_command": source_command,
            **({"parent_project_id": clean_parent_project_id} if clean_parent_project_id else {}),
            **({"hypothesis_to_test": clean_hypothesis} if clean_hypothesis else {}),
        },
        event_id=request_event_id,
    )
    if run_until_done:
        emit_event(
            project_id,
            "research_continue_dispatched",
            {
                "source": source_command,
                "authority_scope": "canonical_intake",
                "dispatch_mode": "background",
                "request_event_id": request_event_id,
                "runner": "june-control-plane-handoff",
                "source_command": source_command,
            },
        )
    return payload


def submit_research_continue(
    project_id: str,
    *,
    source_command: str,
    max_cycles: int | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    validated_project_id = validate_project_id(project_id)
    if not source_command.strip():
        raise RuntimeError("source_command is required")
    request_event_id = uuid.uuid4().hex[:16]
    requested_action = "continue_one_cycle" if max_cycles == 1 else "continue_until_terminal"
    emit_event(
        validated_project_id,
        "research_continue_requested",
        {
            "source": source_command,
            "authority_scope": "canonical_intake",
            "control_plane_owner": "june",
            "requested_action": requested_action,
            "source_command": source_command,
            **({"max_cycles": max_cycles} if isinstance(max_cycles, int) and max_cycles > 0 else {}),
        },
        event_id=request_event_id,
    )
    args = [
        "research-continue",
        "--project-id",
        validated_project_id,
        "--source-command",
        source_command,
        "--request-event-id",
        request_event_id,
    ]
    if isinstance(max_cycles, int) and max_cycles > 0:
        args.extend(["--max-cycles", str(max_cycles)])
    payload = _run_june_handoff(args, timeout=timeout)
    emit_event(
        validated_project_id,
        "research_continue_dispatched",
        {
            "source": source_command,
            "authority_scope": "canonical_intake",
            "dispatch_mode": "background",
            "request_event_id": request_event_id,
            "runner": "june-control-plane-handoff",
            "source_command": source_command,
            **({"max_cycles": max_cycles} if isinstance(max_cycles, int) and max_cycles > 0 else {}),
        },
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Operator-side client for June research control-plane handoffs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("research-start")
    start_parser.add_argument("--question", required=True)
    start_parser.add_argument("--source-command", required=True)
    start_parser.add_argument("--research-mode", default="standard")
    start_parser.add_argument("--run-until-done", choices=["0", "1"], default="1")
    start_parser.add_argument("--parent-project-id", default="")
    start_parser.add_argument("--hypothesis-to-test", default="")

    continue_parser = subparsers.add_parser("research-continue")
    continue_parser.add_argument("--project-id", required=True)
    continue_parser.add_argument("--source-command", required=True)
    continue_parser.add_argument("--max-cycles", type=int, default=0)

    try:
        args = parser.parse_args()
        if args.command == "research-start":
            payload = submit_research_start(
                args.question,
                source_command=args.source_command,
                research_mode=args.research_mode,
                run_until_done=args.run_until_done == "1",
                parent_project_id=args.parent_project_id,
                hypothesis_to_test=args.hypothesis_to_test,
            )
        else:
            payload = submit_research_continue(
                args.project_id,
                source_command=args.source_command,
                max_cycles=args.max_cycles if args.max_cycles > 0 else None,
            )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1

    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
