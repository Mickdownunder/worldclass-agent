"""Unit tests for tools/research_quality_gate.py."""
import json
from unittest.mock import patch
import pytest

from tools.research_quality_gate import (
    run_evidence_gate,
    EVIDENCE_GATE_THRESHOLDS,
    HARD_PASS_VERIFIED_MIN,
    SOFT_PASS_VERIFIED_MIN,
    _get_thresholds,
)


def test_thresholds_defined():
    """Evidence gate thresholds exist and are sensible."""
    assert EVIDENCE_GATE_THRESHOLDS["findings_count_min"] >= 1
    assert EVIDENCE_GATE_THRESHOLDS["verified_claim_count_min"] >= 0
    assert 0 <= EVIDENCE_GATE_THRESHOLDS["claim_support_rate_min"] <= 1
    assert HARD_PASS_VERIFIED_MIN >= SOFT_PASS_VERIFIED_MIN


def test_gate_fail_zero_findings(tmp_project, mock_operator_root):
    """Gate fails when findings_count is 0."""
    pid = tmp_project.name
    result = run_evidence_gate(pid)
    assert result.get("pass") is False
    assert "fail_code" in result
    assert result.get("fail_code") in ("failed_insufficient_evidence", "failed_reader_pipeline", None) or "findings" in str(result.get("reasons", [])).lower()


def test_gate_metrics_populated(tmp_project, mock_operator_root):
    """run_evidence_gate() returns metrics dict."""
    pid = tmp_project.name
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "sources").mkdir(exist_ok=True)
    (tmp_project / "verify").mkdir(exist_ok=True)
    for i in range(3):
        (tmp_project / "findings" / f"f{i}.json").write_text(json.dumps({"url": f"https://x{i}.com", "excerpt": "x"}))
    for i in range(3):
        (tmp_project / "sources" / f"s{i}.json").write_text(json.dumps({"url": f"https://y{i}.com"}))
    result = run_evidence_gate(pid)
    assert "metrics" in result
    assert "reasons" in result


def test_get_thresholds_uses_calibrated_when_available():
    """When get_calibrated_thresholds returns a dict, _get_thresholds uses it (calibrated overrides default)."""
    cal = {"findings_count_min": 12, "unique_source_count_min": 6}
    with patch("tools.research_calibrator.get_calibrated_thresholds", return_value=cal):
        t = _get_thresholds()
    assert t["findings_count_min"] == 12
    assert t["unique_source_count_min"] == 6


def test_get_thresholds_uses_default_when_calibrator_none():
    """When get_calibrated_thresholds returns None, _get_thresholds returns EVIDENCE_GATE_THRESHOLDS."""
    with patch("tools.research_calibrator.get_calibrated_thresholds", return_value=None):
        t = _get_thresholds()
    assert t == EVIDENCE_GATE_THRESHOLDS
