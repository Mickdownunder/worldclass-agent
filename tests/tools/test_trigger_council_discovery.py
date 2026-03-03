"""
Regression tests: Discovery mode council trigger only when parent status=done.
Discovery fail hardening: no Council when parent is failed_quality_gate or other failed*.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

OPERATOR_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_trigger_council(operator_root: Path, project_id: str) -> tuple[int, str]:
    """Run trigger_council.py for project_id; research dir is under operator_root. Returns (exit_code, output)."""
    script = OPERATOR_ROOT / "tools" / "trigger_council.py"
    env = os.environ.copy()
    env["OPERATOR_ROOT"] = str(operator_root)
    r = subprocess.run(
        [sys.executable, str(script), project_id],
        cwd=str(OPERATOR_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return r.returncode, (r.stderr or "") + (r.stdout or "")


def test_discovery_parent_failed_quality_gate_does_not_trigger_council(tmp_path: Path) -> None:
    """Discovery parent with status=failed_quality_gate must not trigger Council (exit 0, no council_status=active)."""
    research = tmp_path / "research"
    research.mkdir()
    proj_dir = research / "proj-discovery-fail"
    proj_dir.mkdir()
    project_json = {
        "id": "proj-discovery-fail",
        "status": "failed_quality_gate",
        "phase": "failed",
        "config": {"research_mode": "discovery"},
        "council_status": None,
    }
    (proj_dir / "project.json").write_text(json.dumps(project_json, indent=2))

    exit_code, out = _run_trigger_council(tmp_path, "proj-discovery-fail")

    assert exit_code == 0, f"trigger_council output: {out}"
    data = json.loads((proj_dir / "project.json").read_text())
    assert data.get("status") == "failed_quality_gate"
    assert data.get("council_status") != "active"


def test_discovery_parent_done_triggers_council(tmp_path: Path) -> None:
    """Discovery parent with status=done may trigger Council (sets council_status=active, spawns process)."""
    research = tmp_path / "research"
    research.mkdir()
    proj_dir = research / "proj-discovery-done"
    proj_dir.mkdir()
    project_json = {
        "id": "proj-discovery-done",
        "status": "done",
        "phase": "done",
        "config": {"research_mode": "discovery"},
    }
    (proj_dir / "project.json").write_text(json.dumps(project_json, indent=2))

    exit_code, _ = _run_trigger_council(tmp_path, "proj-discovery-done")

    assert exit_code == 0
    data = json.loads((proj_dir / "project.json").read_text())
    # Script sets council_status to "active" before spawning council
    assert data.get("council_status") == "active"


def test_standard_parent_failed_quality_gate_still_attempts_trigger(tmp_path: Path) -> None:
    """Standard mode: failed_quality_gate still leads to trigger path (Council can be convened for failed runs)."""
    research = tmp_path / "research"
    research.mkdir()
    proj_dir = research / "proj-standard-fail"
    proj_dir.mkdir()
    project_json = {
        "id": "proj-standard-fail",
        "status": "failed_quality_gate",
        "phase": "failed",
        "config": {"research_mode": "standard"},
    }
    (proj_dir / "project.json").write_text(json.dumps(project_json, indent=2))

    exit_code, _ = _run_trigger_council(tmp_path, "proj-standard-fail")

    # In standard mode we do not exit early for failed; we may set council_status=active
    assert exit_code == 0
    data = json.loads((proj_dir / "project.json").read_text())
    # Council trigger sets council_status to "active"
    assert data.get("council_status") == "active"
