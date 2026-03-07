import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path("/root/operator")
SCRIPT = ROOT / "tools" / "run-research-single-cycle.sh"
OC_SCRIPT = ROOT / "bin" / "oc-research-cycle"
WORKFLOW_SCRIPT = ROOT / "workflows" / "research-cycle.sh"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_operator_root(tmp_path: Path, *, phase: str = "explore", status: str = "running") -> tuple[Path, Path]:
    operator_root = tmp_path / "operator"
    project_dir = operator_root / "research" / "proj-123"
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text(
        json.dumps({"id": "proj-123", "phase": phase, "status": status}, indent=2),
        encoding="utf-8",
    )
    return operator_root, project_dir


def test_run_research_single_cycle_dispatches_one_research_phase_job(tmp_path):
    operator_root, _ = _make_operator_root(tmp_path)
    log_file = tmp_path / "op-calls.jsonl"
    fake_job_dir = tmp_path / "job-123"
    fake_job_dir.mkdir()
    _write_executable(
        operator_root / "bin" / "op",
        f"#!/usr/bin/env bash\nprintf '%s\n' \"$*\" >> {log_file}\n"
        f"if [ \"$1\" = \"job\" ] && [ \"$2\" = \"new\" ]; then echo '{fake_job_dir}'; exit 0; fi\n"
        "if [ \"$1\" = \"run\" ]; then exit 0; fi\n"
        "exit 99\n",
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT), "proj-123"],
        env={**os.environ, "OPERATOR_ROOT": str(operator_root)},
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    calls = log_file.read_text(encoding="utf-8").splitlines()
    assert calls == [
        "job new --workflow research-phase --request proj-123",
        f"run {fake_job_dir}",
    ]
    assert "JOB_DIR=" in completed.stdout
    assert "RUN_EXIT=0" in completed.stdout


def test_run_research_single_cycle_uses_synthesize_timeout(tmp_path):
    operator_root, _ = _make_operator_root(tmp_path, phase="synthesize")
    log_file = tmp_path / "op-calls.jsonl"
    fake_job_dir = tmp_path / "job-456"
    fake_job_dir.mkdir()
    _write_executable(
        operator_root / "bin" / "op",
        f"#!/usr/bin/env bash\nprintf '%s\n' \"$*\" >> {log_file}\n"
        f"if [ \"$1\" = \"job\" ] && [ \"$2\" = \"new\" ]; then echo '{fake_job_dir}'; exit 0; fi\n"
        "if [ \"$1\" = \"run\" ]; then exit 0; fi\n"
        "exit 99\n",
    )

    subprocess.run(
        ["bash", str(SCRIPT), "proj-123"],
        env={**os.environ, "OPERATOR_ROOT": str(operator_root)},
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    calls = log_file.read_text(encoding="utf-8").splitlines()
    assert calls[0] == "job new --workflow research-phase --request proj-123 --timeout 5400"


def test_oc_research_cycle_delegates_to_single_cycle_runner(tmp_path):
    operator_root, _ = _make_operator_root(tmp_path)
    delegated_log = tmp_path / "delegated.txt"
    _write_executable(
        operator_root / "tools" / "run-research-single-cycle.sh",
        f"#!/usr/bin/env bash\nprintf '%s\n' \"$1\" >> {delegated_log}\n",
    )

    subprocess.run(
        ["bash", str(OC_SCRIPT), "proj-123"],
        env={**os.environ, "OPERATOR_ROOT": str(operator_root)},
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert delegated_log.read_text(encoding="utf-8").strip() == "proj-123"


def test_research_cycle_workflow_reads_job_request_and_delegates(tmp_path):
    operator_root, _ = _make_operator_root(tmp_path)
    delegated_log = tmp_path / "delegated.txt"
    _write_executable(
        operator_root / "tools" / "run-research-single-cycle.sh",
        f"#!/usr/bin/env bash\nprintf '%s\n' \"$1\" >> {delegated_log}\n",
    )
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "job.json").write_text(json.dumps({"request": "proj-123 extra ignored"}), encoding="utf-8")

    subprocess.run(
        ["bash", str(WORKFLOW_SCRIPT)],
        env={**os.environ, "OPERATOR_ROOT": str(operator_root)},
        cwd=str(job_dir),
        capture_output=True,
        text=True,
        check=True,
    )

    assert delegated_log.read_text(encoding="utf-8").strip() == "proj-123"
