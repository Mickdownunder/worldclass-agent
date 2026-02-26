"""Unit tests for tools/research_calibrator.py — threshold computation, floor, < 10 projects."""
import json
from unittest.mock import patch, MagicMock
import pytest

from tools.research_calibrator import get_calibrated_thresholds, FLOOR


def test_under_10_projects_returns_none():
    """Fewer than 10 successful outcomes: get_calibrated_thresholds() returns None."""
    mock_mem = MagicMock()
    mock_mem.get_successful_outcomes.return_value = [
        {"gate_metrics_json": json.dumps({"findings_count": 8})} for _ in range(9)
    ]
    with patch("lib.memory.Memory", return_value=mock_mem):
        result = get_calibrated_thresholds()
    assert result is None


def test_25th_percentile_10_entries():
    """10 outcomes with findings_count 1..10: p25 gives 2nd element (index 1), floor 5 applies."""
    mock_mem = MagicMock()
    mock_mem.get_successful_outcomes.return_value = [
        {"gate_metrics_json": json.dumps({"findings_count": i, "unique_source_count": 5, "verified_claim_count": 2, "claim_support_rate": 0.5, "high_reliability_source_ratio": 0.5})}
        for i in range(1, 11)
    ]
    with patch("lib.memory.Memory", return_value=mock_mem):
        result = get_calibrated_thresholds()
    assert result is not None
    # p25 of [1..10]: sorted, index int(10*0.25)-1 = 1, value 2. Floor 5 -> 5
    assert result["findings_count_min"] >= FLOOR["findings_count_min"]


def test_25th_percentile_100_entries():
    """100 entries: p25 is 25th percentile of sorted list."""
    mock_mem = MagicMock()
    base = [{"gate_metrics_json": json.dumps({
        "findings_count": i, "unique_source_count": 10, "verified_claim_count": 5,
        "claim_support_rate": 0.6, "high_reliability_source_ratio": 0.5
    })} for i in range(1, 101)]
    mock_mem.get_successful_outcomes.return_value = base
    with patch("lib.memory.Memory", return_value=mock_mem):
        result = get_calibrated_thresholds()
    assert result is not None
    # p25 index = max(0, int(100*0.25)-1) = 24, value 25
    assert result["findings_count_min"] == max(FLOOR["findings_count_min"], 25)


def test_floor_values_never_undershot():
    """p25 below FLOOR: result >= FLOOR for each key."""
    mock_mem = MagicMock()
    mock_mem.get_successful_outcomes.return_value = [
        {"gate_metrics_json": json.dumps({
            "findings_count": 1, "unique_source_count": 1, "verified_claim_count": 0,
            "claim_support_rate": 0.1, "high_reliability_source_ratio": 0.1
        })} for _ in range(10)
    ]
    with patch("lib.memory.Memory", return_value=mock_mem):
        result = get_calibrated_thresholds()
    assert result is not None
    for k, floor_val in FLOOR.items():
        assert k in result
        assert result[k] >= floor_val


def test_memory_failure_returns_none():
    """Memory() raises: get_calibrated_thresholds() returns None."""
    with patch("lib.memory.Memory", side_effect=RuntimeError("DB unavailable")):
        result = get_calibrated_thresholds()
    assert result is None
