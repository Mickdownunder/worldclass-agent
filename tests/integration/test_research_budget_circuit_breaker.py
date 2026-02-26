"""
E2E: Budget circuit breaker — project stops when spend >= budget_limit.
research-cycle.sh checks research_budget.py check and sets FAILED_BUDGET_EXCEEDED.
"""
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_budget import check_budget, get_budget_limit


def test_budget_check_ok_false_when_over_limit(tmp_project, mock_operator_root):
    """When current_spend >= budget_limit, check_budget returns ok=False."""
    from tools.research_common import save_project
    pid = tmp_project.name
    save_project(
        tmp_project,
        {
            "id": pid,
            "question": "Q?",
            "current_spend": 10.0,
            "config": {"budget_limit": 3.0},
        },
    )
    result = check_budget(pid)
    assert result["ok"] is False
    assert result["current_spend"] == 10.0
    assert result["budget_limit"] == 3.0


def test_budget_check_ok_true_when_under_limit(tmp_project):
    """When current_spend < budget_limit, check_budget returns ok=True."""
    from tools.research_common import save_project
    pid = tmp_project.name
    save_project(
        tmp_project,
        {"id": pid, "question": "Q?", "current_spend": 0.5, "config": {"budget_limit": 3.0}},
    )
    result = check_budget(pid)
    assert result["ok"] is True
    assert result["current_spend"] == 0.5
    assert result["budget_limit"] == 3.0
