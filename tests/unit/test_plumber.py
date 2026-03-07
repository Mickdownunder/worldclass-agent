"""Unit tests for lib/plumber.py — classify_non_repairable (pure function, no I/O)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.plumber import classify_non_repairable


def test_classify_non_repairable_rate_limit():
    """HTTP 429 or rate limit text returns (reason_code, explanation)."""
    result = classify_non_repairable("HTTP Error 429: Too Many Requests")
    assert result is not None
    code, explanation = result
    assert code == "rate_limit"
    assert "rate" in explanation.lower() or "429" in explanation


def test_classify_non_repairable_external_api_5xx():
    """HTTP 5xx returns external_api_error."""
    result = classify_non_repairable("HTTP Error 503 Service Unavailable")
    assert result is not None
    code, _ = result
    assert code == "external_api_error"


def test_classify_non_repairable_disk_full():
    """Disk full / quota text returns disk_full."""
    result = classify_non_repairable("disk full cannot write")
    assert result is not None
    code, _ = result
    assert code == "disk_full"


def test_classify_non_repairable_permission_denied():
    """Permission denied returns permission_denied."""
    result = classify_non_repairable("Permission denied when opening file")
    assert result is not None
    code, _ = result
    assert code == "permission_denied"


def test_classify_repairable_returns_none():
    """Normal Python/script errors (no non-repairable pattern) return None."""
    assert classify_non_repairable("NameError: name 'x' is not defined") is None
    assert classify_non_repairable("SyntaxError: invalid syntax") is None
    assert classify_non_repairable("AssertionError") is None


def test_classify_empty_string_returns_none():
    """Empty or whitespace-only error text returns None."""
    assert classify_non_repairable("") is None
