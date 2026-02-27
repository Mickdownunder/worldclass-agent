"""Tests for planner-side strategy application (Memory v2)."""
from tools import research_planner as planner


def test_apply_strategy_to_plan_resamples_query_types():
    plan = {
        "queries": [
            {"query": "a", "topic_id": "t1", "type": "web", "perspective": "p"},
            {"query": "b", "topic_id": "t1", "type": "web", "perspective": "p"},
            {"query": "c", "topic_id": "t1", "type": "web", "perspective": "p"},
            {"query": "d", "topic_id": "t1", "type": "web", "perspective": "p"},
        ]
    }
    strategy_ctx = {
        "selected_strategy": {
            "policy": {
                "preferred_query_types": {"medical": 0.8, "academic": 0.2, "web": 0.0},
            }
        }
    }
    out = planner._apply_strategy_to_plan(plan, strategy_ctx)
    types = [q["type"] for q in out["queries"]]
    assert "medical" in types
    assert "academic" in types


def test_apply_strategy_to_plan_without_strategy_is_noop():
    plan = {"queries": [{"query": "a", "topic_id": "t1", "type": "web", "perspective": "p"}]}
    out = planner._apply_strategy_to_plan(plan, None)
    assert out["queries"][0]["type"] == "web"
