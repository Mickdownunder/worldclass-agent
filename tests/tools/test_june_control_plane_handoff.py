import json
import os
import stat
import subprocess
from pathlib import Path

SCRIPT = "/root/agent/workspace/bin/june-control-plane-handoff"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _prepare_runtime(agent_root: Path) -> Path:
    runtime_dir = agent_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "__init__.py").write_text("", encoding="utf-8")
    (runtime_dir / "event_log.py").write_text(
        "from pathlib import Path\nimport json\nfrom datetime import datetime, timezone\n"
        "def append_event(log_path, event_type, **payload):\n"
        "    path = Path(log_path)\n"
        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    event = {'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'event_type': event_type, **payload}\n"
        "    with path.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(event, ensure_ascii=True) + '\\n')\n"
        "    return event\n",
        encoding="utf-8",
    )
    return agent_root / "logs" / "runtime-events.jsonl"


def _append_cycle_event(operator_root: Path, project_id: str, *, event_id: str, completed_phase: str, resulting_phase: str, resulting_status: str) -> None:
    payload = {
        "ts": "2026-03-08T00:00:00Z",
        "event": "research_cycle_completed",
        "event_id": event_id,
        "event_scope": "control_plane",
        "project_id": project_id,
        "source": "research-phase.sh",
        "authority_scope": "operator_local",
        "completed_phase": completed_phase,
        "resulting_phase": resulting_phase,
        "resulting_status": resulting_status,
        "research_mode": "discovery",
        "council_triggered": False,
        "handoff_required": True,
        "handoff_target": "june",
    }
    project_events = operator_root / "research" / project_id / "events.jsonl"
    project_events.parent.mkdir(parents=True, exist_ok=True)
    with project_events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    global_events = operator_root / "logs" / "control-plane-events.jsonl"
    global_events.parent.mkdir(parents=True, exist_ok=True)
    with global_events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def test_june_handoff_start_initializes_project_and_runs_continue_loop(tmp_path):
    agent_root = tmp_path / "agent"
    operator_root = tmp_path / "operator"
    bin_dir = operator_root / "bin"
    research_dir = operator_root / "research" / "proj-123"
    bin_dir.mkdir(parents=True)
    research_dir.mkdir(parents=True)
    event_log = _prepare_runtime(agent_root)
    init_log = tmp_path / "init.log"
    cycle_log = tmp_path / "cycle.log"
    cycle_count = tmp_path / "cycle-count.txt"

    _write_executable(
        bin_dir / "oc-research-init",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$1\" > {init_log}\n"
        f"mkdir -p {research_dir}\n"
        f"cat > {research_dir / 'project.json'} <<'JSON'\n{{\"id\": \"proj-123\", \"phase\": \"explore\", \"status\": \"running\", \"question\": \"Question?\", \"config\": {{\"research_mode\": \"discovery\"}}}}\nJSON\n"
        "echo 'PROJECT_ID=proj-123'\n",
    )
    _write_executable(
        bin_dir / "oc-research-cycle",
        f"#!/usr/bin/env python3\n"
        f"import json\n"
        f"from pathlib import Path\n"
        f"log_path = Path({json.dumps(str(cycle_log))})\n"
        f"count_path = Path({json.dumps(str(cycle_count))})\n"
        f"project_path = Path({json.dumps(str(research_dir / 'project.json'))})\n"
        f"operator_root = Path({json.dumps(str(operator_root))})\n"
        f"count = int(count_path.read_text() if count_path.exists() else '0') + 1\n"
        f"count_path.write_text(str(count))\n"
        f"log_path.write_text((log_path.read_text() if log_path.exists() else '') + 'proj-123\\n')\n"
        f"data = json.loads(project_path.read_text())\n"
        f"if count == 1:\n"
        f"    data['phase'] = 'focus'\n"
        f"    data['status'] = 'waiting_next_cycle'\n"
        f"    project_path.write_text(json.dumps(data))\n"
        f"    payload = {{'ts':'2026-03-08T00:00:00Z','event':'research_cycle_completed','event_id':'evt-cycle-1','event_scope':'control_plane','project_id':'proj-123','source':'research-phase.sh','authority_scope':'operator_local','completed_phase':'explore','resulting_phase':'focus','resulting_status':'waiting_next_cycle','research_mode':'discovery','council_triggered':False,'handoff_required':True,'handoff_target':'june'}}\n"
        f"else:\n"
        f"    data['phase'] = 'done'\n"
        f"    data['status'] = 'done'\n"
        f"    project_path.write_text(json.dumps(data))\n"
        f"    payload = {{'ts':'2026-03-08T00:00:01Z','event':'research_cycle_completed','event_id':'evt-cycle-2','event_scope':'control_plane','project_id':'proj-123','source':'research-phase.sh','authority_scope':'operator_local','completed_phase':'focus','resulting_phase':'done','resulting_status':'done','research_mode':'discovery','council_triggered':False,'handoff_required':True,'handoff_target':'june'}}\n"
        f"for target in [operator_root / 'research' / 'proj-123' / 'events.jsonl', operator_root / 'logs' / 'control-plane-events.jsonl']:\n"
        f"    target.parent.mkdir(parents=True, exist_ok=True)\n"
        f"    with target.open('a', encoding='utf-8') as handle:\n"
        f"        handle.write(json.dumps(payload) + '\\n')\n",
    )

    env = {
        **os.environ,
        "AGENT_WORKSPACE": str(agent_root),
        "OPERATOR_ROOT": str(operator_root),
        "JUNE_RUNTIME_EVENT_LOG": str(event_log),
        "JUNE_OC_RESEARCH_INIT": str(bin_dir / "oc-research-init"),
        "JUNE_OC_RESEARCH_CYCLE": str(bin_dir / "oc-research-cycle"),
        "JUNE_HANDOFF_DETACH": "0",
        "JUNE_CONTINUE_MAX_CYCLES": "4",
    }
    completed = subprocess.run(
        [
            "python3",
            SCRIPT,
            "ui-research-start",
            "--question",
            "Question?",
            "--research-mode",
            "discovery",
            "--run-until-done",
            "1",
            "--request-event-id",
            "evt-1",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload == {
        "ok": True,
        "command": "ui-research-start",
        "projectId": "proj-123",
        "runUntilDone": True,
    }
    assert json.loads(init_log.read_text()) == {
        "question": "Question?",
        "research_mode": "discovery",
        "control_plane_owner": "june",
        "source_command": "ui-research-start",
    }
    assert cycle_log.read_text().strip().splitlines() == ["proj-123", "proj-123"]
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [event["event_type"] for event in events] == [
        "control_plane_handoff_received",
        "control_plane_handoff_project_initialized",
        "control_plane_continue_loop_started",
        "control_plane_continue_cycle_started",
        "control_plane_continue_cycle_finished",
        "control_plane_continue_decision",
        "control_plane_continue_cycle_started",
        "control_plane_continue_cycle_finished",
        "control_plane_continue_decision",
        "control_plane_continue_loop_finished",
        "control_plane_handoff_dispatched",
    ]
    assert events[-2]["final_decision"] == "stop_success"


def test_june_handoff_continue_runs_loop_until_project_done(tmp_path):
    agent_root = tmp_path / "agent"
    operator_root = tmp_path / "operator"
    bin_dir = operator_root / "bin"
    project_dir = operator_root / "research" / "proj-456"
    bin_dir.mkdir(parents=True)
    project_dir.mkdir(parents=True)
    event_log = _prepare_runtime(agent_root)
    cycle_log = tmp_path / "cycle.log"
    cycle_count = tmp_path / "cycle-count.txt"
    (project_dir / "project.json").write_text(
        json.dumps({"id": "proj-456", "phase": "explore", "status": "running", "config": {"research_mode": "standard"}}),
        encoding="utf-8",
    )

    _write_executable(bin_dir / "oc-research-init", "#!/usr/bin/env bash\necho 'PROJECT_ID=proj-unused'\n")
    _write_executable(
        bin_dir / "oc-research-cycle",
        f"#!/usr/bin/env python3\n"
        f"import json\n"
        f"from pathlib import Path\n"
        f"log_path = Path({json.dumps(str(cycle_log))})\n"
        f"count_path = Path({json.dumps(str(cycle_count))})\n"
        f"project_path = Path({json.dumps(str(project_dir / 'project.json'))})\n"
        f"operator_root = Path({json.dumps(str(operator_root))})\n"
        f"count = int(count_path.read_text() if count_path.exists() else '0') + 1\n"
        f"count_path.write_text(str(count))\n"
        f"log_path.write_text((log_path.read_text() if log_path.exists() else '') + 'proj-456\\n')\n"
        f"data = json.loads(project_path.read_text())\n"
        f"data['phase'] = 'done'\n"
        f"data['status'] = 'done'\n"
        f"project_path.write_text(json.dumps(data))\n"
        f"payload = {{'ts':'2026-03-08T00:00:02Z','event':'research_cycle_completed','event_id':'evt-cycle-3','event_scope':'control_plane','project_id':'proj-456','source':'research-phase.sh','authority_scope':'operator_local','completed_phase':'explore','resulting_phase':'done','resulting_status':'done','research_mode':'standard','council_triggered':False,'handoff_required':True,'handoff_target':'june'}}\n"
        f"for target in [operator_root / 'research' / 'proj-456' / 'events.jsonl', operator_root / 'logs' / 'control-plane-events.jsonl']:\n"
        f"    target.parent.mkdir(parents=True, exist_ok=True)\n"
        f"    with target.open('a', encoding='utf-8') as handle:\n"
        f"        handle.write(json.dumps(payload) + '\\n')\n",
    )

    env = {
        **os.environ,
        "AGENT_WORKSPACE": str(agent_root),
        "OPERATOR_ROOT": str(operator_root),
        "JUNE_RUNTIME_EVENT_LOG": str(event_log),
        "JUNE_OC_RESEARCH_INIT": str(bin_dir / "oc-research-init"),
        "JUNE_OC_RESEARCH_CYCLE": str(bin_dir / "oc-research-cycle"),
        "JUNE_HANDOFF_DETACH": "0",
        "JUNE_CONTINUE_MAX_CYCLES": "3",
    }
    completed = subprocess.run(
        [
            "python3",
            SCRIPT,
            "ui-research-continue",
            "--project-id",
            "proj-456",
            "--request-event-id",
            "evt-2",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload == {
        "ok": True,
        "command": "ui-research-continue",
        "projectId": "proj-456",
    }
    assert cycle_log.read_text().strip() == "proj-456"
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [event["event_type"] for event in events] == [
        "control_plane_handoff_received",
        "control_plane_continue_loop_started",
        "control_plane_continue_cycle_started",
        "control_plane_continue_cycle_finished",
        "control_plane_continue_decision",
        "control_plane_continue_loop_finished",
        "control_plane_handoff_dispatched",
    ]
    assert events[-2]["final_decision"] == "stop_success"


def test_june_handoff_generic_start_preserves_parent_and_hypothesis(tmp_path):
    agent_root = tmp_path / "agent"
    operator_root = tmp_path / "operator"
    bin_dir = operator_root / "bin"
    research_dir = operator_root / "research" / "proj-789"
    bin_dir.mkdir(parents=True)
    research_dir.mkdir(parents=True)
    event_log = _prepare_runtime(agent_root)
    init_log = tmp_path / "init.log"

    _write_executable(
        bin_dir / "oc-research-init",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$1\" > {init_log}\n"
        f"mkdir -p {research_dir}\n"
        f"cat > {research_dir / 'project.json'} <<'JSON'\n{{\"id\": \"proj-789\", \"phase\": \"explore\", \"status\": \"running\", \"question\": \"Question?\", \"config\": {{\"research_mode\": \"discovery\"}}, \"parent_project_id\": \"proj-parent\", \"hypothesis_to_test\": \"Hypothesis\"}}\nJSON\n"
        "echo 'PROJECT_ID=proj-789'\n",
    )
    _write_executable(bin_dir / "oc-research-cycle", "#!/usr/bin/env bash\nexit 0\n")

    env = {
        **os.environ,
        "AGENT_WORKSPACE": str(agent_root),
        "OPERATOR_ROOT": str(operator_root),
        "JUNE_RUNTIME_EVENT_LOG": str(event_log),
        "JUNE_OC_RESEARCH_INIT": str(bin_dir / "oc-research-init"),
        "JUNE_OC_RESEARCH_CYCLE": str(bin_dir / "oc-research-cycle"),
        "JUNE_HANDOFF_DETACH": "0",
    }
    completed = subprocess.run(
        [
            "python3",
            SCRIPT,
            "research-start",
            "--question",
            "Question?",
            "--research-mode",
            "discovery",
            "--run-until-done",
            "0",
            "--request-event-id",
            "evt-3",
            "--source-command",
            "research_council",
            "--mission-id",
            "mis-123",
            "--parent-project-id",
            "proj-parent",
            "--hypothesis-to-test",
            "Hypothesis",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload == {
        "ok": True,
        "command": "research-start",
        "projectId": "proj-789",
        "runUntilDone": False,
    }
    assert json.loads(init_log.read_text()) == {
        "question": "Question?",
        "research_mode": "discovery",
        "control_plane_owner": "june",
        "source_command": "research_council",
        "mission_id": "mis-123",
        "parent_project_id": "proj-parent",
        "hypothesis_to_test": "Hypothesis",
    }
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [event["event_type"] for event in events] == [
        "control_plane_handoff_received",
        "control_plane_handoff_project_initialized",
    ]
    assert events[0]["source_command"] == "research_council"
    assert events[1]["mission_id"] == "mis-123"
    operator_events = [
        json.loads(line)
        for line in (operator_root / "research" / "proj-789" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert operator_events[-1]["event"] == "research_project_initialized"
    assert operator_events[-1]["mission_id"] == "mis-123"
    assert operator_events[-1]["source_command"] == "research_council"


def test_june_handoff_generic_continue_respects_max_cycles(tmp_path):
    agent_root = tmp_path / "agent"
    operator_root = tmp_path / "operator"
    bin_dir = operator_root / "bin"
    project_dir = operator_root / "research" / "proj-999"
    bin_dir.mkdir(parents=True)
    project_dir.mkdir(parents=True)
    event_log = _prepare_runtime(agent_root)
    cycle_log = tmp_path / "cycle.log"
    (project_dir / "project.json").write_text(
        json.dumps({"id": "proj-999", "phase": "focus", "status": "waiting_next_cycle", "config": {"research_mode": "standard"}}),
        encoding="utf-8",
    )

    _write_executable(bin_dir / "oc-research-init", "#!/usr/bin/env bash\necho 'PROJECT_ID=proj-unused'\n")
    _write_executable(
        bin_dir / "oc-research-cycle",
        f"#!/usr/bin/env python3\n"
        f"import json\n"
        f"from pathlib import Path\n"
        f"log_path = Path({json.dumps(str(cycle_log))})\n"
        f"project_path = Path({json.dumps(str(project_dir / 'project.json'))})\n"
        f"operator_root = Path({json.dumps(str(operator_root))})\n"
        f"log_path.write_text((log_path.read_text() if log_path.exists() else '') + 'proj-999\\n')\n"
        f"data = json.loads(project_path.read_text())\n"
        f"data['phase'] = 'verify'\n"
        f"data['status'] = 'waiting_next_cycle'\n"
        f"project_path.write_text(json.dumps(data))\n"
        f"payload = {{'ts':'2026-03-08T00:00:03Z','event':'research_cycle_completed','event_id':'evt-cycle-4','event_scope':'control_plane','project_id':'proj-999','source':'research-phase.sh','authority_scope':'operator_local','completed_phase':'focus','resulting_phase':'verify','resulting_status':'waiting_next_cycle','research_mode':'standard','council_triggered':False,'handoff_required':True,'handoff_target':'june'}}\n"
        f"for target in [operator_root / 'research' / 'proj-999' / 'events.jsonl', operator_root / 'logs' / 'control-plane-events.jsonl']:\n"
        f"    target.parent.mkdir(parents=True, exist_ok=True)\n"
        f"    with target.open('a', encoding='utf-8') as handle:\n"
        f"        handle.write(json.dumps(payload) + '\\n')\n",
    )

    env = {
        **os.environ,
        "AGENT_WORKSPACE": str(agent_root),
        "OPERATOR_ROOT": str(operator_root),
        "JUNE_RUNTIME_EVENT_LOG": str(event_log),
        "JUNE_OC_RESEARCH_INIT": str(bin_dir / "oc-research-init"),
        "JUNE_OC_RESEARCH_CYCLE": str(bin_dir / "oc-research-cycle"),
        "JUNE_HANDOFF_DETACH": "0",
    }
    completed = subprocess.run(
        [
            "python3",
            SCRIPT,
            "research-continue",
            "--project-id",
            "proj-999",
            "--request-event-id",
            "evt-4",
            "--source-command",
            "run-research-over-days",
            "--max-cycles",
            "1",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload == {
        "ok": True,
        "command": "research-continue",
        "projectId": "proj-999",
    }
    assert cycle_log.read_text().strip() == "proj-999"
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert events[0]["source_command"] == "run-research-over-days"
    assert events[-2]["final_decision"] == "stop_max_cycles"
