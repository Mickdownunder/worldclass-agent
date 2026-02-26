"""Unit tests for tools/research_watchdog.py."""
import json
import pytest

from tools.research_watchdog import check_drift, check_rate_limit


def test_check_drift_insufficient_runs(tmp_project):
    """check_drift() returns ok when insufficient scorecard runs."""
    r = check_drift(tmp_project.name)
    assert r["status"] == "ok"
    assert r.get("reason") == "insufficient_runs" or "runs" in r


def test_check_rate_limit_no_project(mock_operator_root):
    """check_rate_limit() returns over_limit=False when project missing."""
    r = check_rate_limit("nonexistent-proj")
    assert r.get("over_limit") is False
    assert r.get("reason") == "no_project"


def test_check_rate_limit_under_limit(tmp_project):
    """check_rate_limit() returns over_limit=False when under limit."""
    r = check_rate_limit(tmp_project.name)
    assert "over_limit" in r
    assert r.get("over_limit") is False or "new_findings" in str(r).lower()
