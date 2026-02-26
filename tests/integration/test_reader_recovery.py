"""
E2E: Reader crash recovery — reader outputs valid JSON and exits 0 on fetch error.
Pipeline can handle reader failure without aborting.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
READER = ROOT / "tools" / "research_web_reader.py"


def test_reader_outputs_json_on_fetch_error():
    """Reader exits 0 and outputs JSON with error_code/message when fetch fails."""
    if not READER.exists():
        pytest.skip("research_web_reader.py not found")
    r = subprocess.run(
        [sys.executable, str(READER), "http://127.0.0.1:1/"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, "Reader must not exit non-zero on fetch error"
    out = json.loads(r.stdout)
    assert "url" in out
    assert out.get("error") or out.get("error_code") or out.get("message")
