"""Unit tests for tools/research_budget.py."""
import json
import pytest

from tools.research_budget import (
    get_budget_limit,
    track_usage,
    track_api_call,
    check_budget,
    DEFAULT_BUDGET_LIMIT,
    API_COSTS,
)


def test_get_budget_limit_default(tmp_project):
    """get_budget_limit() returns DEFAULT when no config."""
    from tools.research_common import load_project
    proj = load_project(tmp_project)
    assert get_budget_limit(proj) == DEFAULT_BUDGET_LIMIT


def test_get_budget_limit_custom(tmp_project):
    """get_budget_limit() reads config.budget_limit."""
    from tools.research_common import load_project, save_project
    save_project(tmp_project, {"id": "p", "config": {"budget_limit": 10.0}})
    proj = load_project(tmp_project)
    assert get_budget_limit(proj) == 10.0


def test_track_usage_increments(tmp_project, mock_operator_root):
    """track_usage() adds token cost to current_spend."""
    from tools.research_common import load_project
    pid = tmp_project.name
    track_usage(pid, "gpt-4o-mini", 100, 50)
    proj = load_project(tmp_project)
    assert proj.get("current_spend", 0) > 0


def test_track_api_call_jina(tmp_project):
    """track_api_call() adds API cost to current_spend."""
    from tools.research_common import load_project
    pid = tmp_project.name
    track_api_call(pid, "jina_reader", count=1)
    proj = load_project(tmp_project)
    assert proj.get("current_spend", 0) >= API_COSTS.get("jina_reader", 0)


def test_check_budget_ok(tmp_project):
    """check_budget() returns ok=True when under limit."""
    r = check_budget(tmp_project.name)
    assert r["ok"] is True
    assert r["current_spend"] >= 0
    assert r["budget_limit"] == DEFAULT_BUDGET_LIMIT


def test_check_budget_over_limit(tmp_project):
    """check_budget() returns ok=False when over limit."""
    from tools.research_common import save_project
    save_project(tmp_project, {"id": tmp_project.name, "current_spend": 100.0, "config": {"budget_limit": 1.0}})
    r = check_budget(tmp_project.name)
    assert r["ok"] is False
    assert r["current_spend"] == 100.0
    assert r["budget_limit"] == 1.0
