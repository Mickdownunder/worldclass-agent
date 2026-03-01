"""Tests for research_synthesize_postprocess: CLI and _run with temp project."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_synthesize_postprocess import main, _run


def test_main_no_args_exits_2():
    """Missing project_id => return 2."""
    orig_argv = sys.argv
    try:
        sys.argv = ["research_synthesize_postprocess.py"]
        assert main() == 2
    finally:
        sys.argv = orig_argv


def test_main_nonexistent_project_exits_1(mock_operator_root):
    """Nonexistent project_id => return 1."""
    (mock_operator_root / "research").mkdir(parents=True, exist_ok=True)
    orig_argv = sys.argv
    try:
        sys.argv = ["postprocess", "proj-nonexistent"]
        assert main() == 1
    finally:
        sys.argv = orig_argv


def test_run_no_report_returns_false(mock_operator_root):
    """_run with no report_*.md => returns False."""
    proj = mock_operator_root / "research" / "proj-empty"
    proj.mkdir(parents=True)
    (proj / "reports").mkdir()
    (proj / "verify").mkdir()
    assert _run(proj, None) is False


def test_run_short_body_returns_false(mock_operator_root):
    """_run with report body < 500 chars => does not save, returns False."""
    proj = mock_operator_root / "research" / "proj-short"
    proj.mkdir(parents=True)
    (proj / "reports").mkdir()
    (proj / "verify").mkdir()
    (proj / "findings").mkdir()
    (proj / "sources").mkdir()
    # No claim_ledger: get_claims_for_synthesis returns []
    (proj / "reports" / "report_20250101T120000Z.md").write_text("Short.")
    assert _run(proj, None) is False
    # Should not have overwritten with references-only
    assert (proj / "reports" / "manifest.json").exists() is False


def test_run_success_creates_artifacts(mock_operator_root):
    """_run with valid report and empty claim_ledger => creates manifest, claim_evidence_map."""
    proj = mock_operator_root / "research" / "proj-ok"
    proj.mkdir(parents=True)
    reports_dir = proj / "reports"
    reports_dir.mkdir()
    (proj / "verify").mkdir()
    (proj / "findings").mkdir()
    (proj / "sources").mkdir()
    body = "x" * 600  # long enough
    (reports_dir / "report_20250101T120000Z.md").write_text(body)
    ok = _run(proj, None)
    assert ok is True
    assert (reports_dir / "manifest.json").exists()
    manifest = json.loads((reports_dir / "manifest.json").read_text())
    assert manifest.get("report_count") == 1
    assert (proj / "verify" / "claim_evidence_map_latest.json").exists()
    latest = json.loads((proj / "verify" / "claim_evidence_map_latest.json").read_text())
    assert "report_id" in latest and "claims" in latest
