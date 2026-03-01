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
    _load_read_stats_combined,
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


# --- Combined read stats (explore + focus) ---


def test_load_read_stats_combined_empty(tmp_project):
    """No read_stats files -> all zeros."""
    out = _load_read_stats_combined(tmp_project)
    assert out["read_attempts"] == 0
    assert out["read_successes"] == 0
    assert out["read_failures"] == 0


def test_load_read_stats_combined_explore_only(tmp_project):
    """Only explore/read_stats.json -> those values."""
    (tmp_project / "explore").mkdir(exist_ok=True)
    (tmp_project / "explore" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 10,
        "read_successes": 8,
        "read_failures": 2,
    }))
    out = _load_read_stats_combined(tmp_project)
    assert out["read_attempts"] == 10
    assert out["read_successes"] == 8
    assert out["read_failures"] == 2


def test_load_read_stats_combined_focus_only(tmp_project):
    """Only focus/read_stats.json -> those values."""
    (tmp_project / "focus").mkdir(exist_ok=True)
    (tmp_project / "focus" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 5,
        "read_successes": 4,
        "read_failures": 1,
    }))
    out = _load_read_stats_combined(tmp_project)
    assert out["read_attempts"] == 5
    assert out["read_successes"] == 4
    assert out["read_failures"] == 1


def test_load_read_stats_combined_both_phases(tmp_project):
    """Explore + focus read_stats -> summed."""
    (tmp_project / "explore").mkdir(exist_ok=True)
    (tmp_project / "explore" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 20,
        "read_successes": 16,
        "read_failures": 4,
    }))
    (tmp_project / "focus").mkdir(exist_ok=True)
    (tmp_project / "focus" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 15,
        "read_successes": 12,
        "read_failures": 3,
    }))
    out = _load_read_stats_combined(tmp_project)
    assert out["read_attempts"] == 35
    assert out["read_successes"] == 28
    assert out["read_failures"] == 7


def test_load_read_stats_combined_malformed_ignored(tmp_project):
    """Malformed or missing keys in one file -> others still summed."""
    (tmp_project / "explore").mkdir(exist_ok=True)
    (tmp_project / "explore" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 6,
        "read_successes": 5,
    }))
    (tmp_project / "focus").mkdir(exist_ok=True)
    (tmp_project / "focus" / "read_stats.json").write_text("not json")
    out = _load_read_stats_combined(tmp_project)
    assert out["read_attempts"] == 6
    assert out["read_successes"] == 5
    assert out["read_failures"] == 0


def test_run_evidence_gate_metrics_use_combined_read_stats(tmp_project, mock_operator_root):
    """run_evidence_gate metrics contain read_attempts/successes/failures from explore + focus."""
    pid = tmp_project.name
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "sources").mkdir(exist_ok=True)
    (tmp_project / "verify").mkdir(exist_ok=True)
    for i in range(10):
        (tmp_project / "findings" / f"f{i}.json").write_text(json.dumps({"url": f"https://x{i}.com", "excerpt": "x"}))
    for i in range(6):
        (tmp_project / "sources" / f"s{i}.json").write_text(json.dumps({"url": f"https://y{i}.com"}))
    (tmp_project / "explore" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 8, "read_successes": 6, "read_failures": 2,
    }))
    (tmp_project / "focus").mkdir(exist_ok=True)
    (tmp_project / "focus" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 7, "read_successes": 5, "read_failures": 2,
    }))
    result = run_evidence_gate(pid)
    assert "metrics" in result
    m = result["metrics"]
    assert m["read_attempts"] == 15
    assert m["read_successes"] == 11
    assert m["read_failures"] == 4


def test_run_evidence_gate_discovery_mode_passes_with_findings_and_sources(tmp_project, mock_operator_root):
    """Discovery mode: pass with enough findings/sources (no verified_claim requirement)."""
    pid = tmp_project.name
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "sources").mkdir(exist_ok=True)
    (tmp_project / "verify").mkdir(exist_ok=True)
    for i in range(12):
        (tmp_project / "findings" / f"f{i}.json").write_text(json.dumps({"url": f"https://x{i}.com", "excerpt": "x"}))
    for i in range(10):
        (tmp_project / "sources" / f"s{i}.json").write_text(json.dumps({"url": f"https://y{i}.com"}))
    (tmp_project / "explore" / "read_stats.json").write_text(json.dumps({
        "read_attempts": 10, "read_successes": 8, "read_failures": 2,
    }))
    project_data = json.loads((tmp_project / "project.json").read_text())
    project_data["config"] = {"research_mode": "discovery"}
    (tmp_project / "project.json").write_text(json.dumps(project_data))
    result = run_evidence_gate(pid)
    assert result.get("pass") is True, f"Discovery mode should pass with 12 findings, 10 sources: {result}"
