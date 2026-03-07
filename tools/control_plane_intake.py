#!/usr/bin/env python3
"""Canonical control-plane intake for user-facing research actions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator")))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_plane_contract import build_intake_response, validate_project_id, VALID_RESEARCH_MODES
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


def submit_ui_research_continue(project_id: str) -> dict[str, Any]:
    try:
        validated_project_id = validate_project_id(project_id)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    request_event = emit_event(
        validated_project_id,
        "research_continue_requested",
        {
            "source": "ui",
            "authority_scope": "external_ingress",
            "control_plane_owner": "june",
            "requested_action": "continue_until_terminal",
        },
    )
    _run_june_handoff(
        [
            "ui-research-continue",
            "--project-id",
            validated_project_id,
            "--request-event-id",
            request_event["event_id"],
        ],
        timeout=30,
    )
    emit_event(
        validated_project_id,
        "research_continue_dispatched",
        {
            "source": "control_plane_intake.py",
            "authority_scope": "canonical_intake",
            "dispatch_mode": "background",
            "request_event_id": request_event["event_id"],
            "runner": "june-control-plane-handoff",
        },
    )
    return build_intake_response(
        command="ui-research-continue",
        ok=True,
        job_id=validated_project_id,
        project_id=validated_project_id,
        request_event_id=request_event["event_id"],
    )


def submit_ui_research_start(question: str, research_mode: str, run_until_done: bool) -> dict[str, Any]:
    clean_question = question.strip()
    if not clean_question:
        raise RuntimeError("question is required")
    if len(clean_question) > 4000:
        raise RuntimeError("question too long")
    mode = research_mode if research_mode in VALID_RESEARCH_MODES else "standard"

    june_payload = _run_june_handoff(
        [
            "ui-research-start",
            "--question",
            clean_question,
            "--research-mode",
            mode,
            "--run-until-done",
            "1" if run_until_done else "0",
        ],
        timeout=180,
    )
    project_id = validate_project_id(str(june_payload.get("projectId") or ""))
    request_event = emit_event(
        project_id,
        "research_start_requested",
        {
            "source": "ui",
            "authority_scope": "external_ingress",
            "control_plane_owner": "june",
            "question": clean_question,
            "research_mode": mode,
            "run_until_done": run_until_done,
            "init_job_id": "delegated_to_june",
        },
    )

    if run_until_done:
        emit_event(
            project_id,
            "research_continue_dispatched",
            {
                "source": "control_plane_intake.py",
                "authority_scope": "canonical_intake",
                "dispatch_mode": "background",
                "request_event_id": request_event["event_id"],
                "runner": "june-control-plane-handoff",
            },
        )

    return build_intake_response(
        command="ui-research-start",
        ok=True,
        job_id=project_id,
        project_id=project_id,
        request_event_id=request_event["event_id"],
        run_until_done=run_until_done,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical control-plane intake for UI research actions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("ui-research-start")
    start_parser.add_argument("--question", required=True)
    start_parser.add_argument("--research-mode", default="standard")
    start_parser.add_argument("--run-until-done", choices=["0", "1"], default="1")

    continue_parser = subparsers.add_parser("ui-research-continue")
    continue_parser.add_argument("--project-id", required=True)

    args = parser.parse_args()
    try:
        if args.command == "ui-research-start":
            payload = submit_ui_research_start(
                question=args.question,
                research_mode=args.research_mode,
                run_until_done=args.run_until_done == "1",
            )
        else:
            payload = submit_ui_research_continue(args.project_id)
    except Exception as exc:
        print(json.dumps(build_intake_response(command=args.command, ok=False, error=str(exc)), ensure_ascii=True))
        return 1

    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
