"""Integration/smoke tests for bin/op CLI (Phase B: Shell/CLI layer without Bats)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


def test_op_healthcheck_returns_valid_json_with_mock_root(tmp_path):
    """op healthcheck runs with OPERATOR_ROOT and prints JSON with expected keys (disk_ok, healthy, …)."""
    # bin/op uses BASE = Path.home()/operator; use a fake home so BASE = tmp_path/operator
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    operator_root = fake_home / "operator"
    operator_root.mkdir()
    (operator_root / "jobs").mkdir()
    (operator_root / "workflows").mkdir()
    (operator_root / "conf").mkdir()
    (operator_root / "lib").mkdir()
    env = {**os.environ, "HOME": str(fake_home), "OPERATOR_ROOT": str(operator_root)}
    result = subprocess.run(
        [sys.executable, str(ROOT / "bin" / "op"), "healthcheck"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=15,
    )
    out = result.stdout or result.stderr or ""
    assert result.returncode in (0, 1)
    data = json.loads(out)
    assert "disk_ok" in data or "healthy" in data
    assert "workflows_available" in data or "jobs_total" in data or "memory" in data


def test_op_main_requires_subcommand():
    """op without args exits non-zero and prints usage."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "bin" / "op")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=5,
    )
    assert result.returncode != 0
    assert "Usage" in (result.stderr or result.stdout or "")
