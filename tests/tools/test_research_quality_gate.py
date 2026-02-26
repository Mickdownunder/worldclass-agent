"""Unit tests for tools/research_quality_gate.py."""
import json
import pytest

from tools.research_quality_gate import (
    run_evidence_gate,
    EVIDENCE_GATE_THRESHOLDS,
    HARD_PASS_VERIFIED_MIN,
    SOFT_PASS_VERIFIED_MIN,
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
