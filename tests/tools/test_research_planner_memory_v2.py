"""Tests for planner-side strategy application (Memory v2)."""
import json

from tools import research_planner as planner
from lib.memory import Memory


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
        "mode": "v2_applied",
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


def test_load_strategy_context_logs_fallback_no_strategy(monkeypatch, tmp_path):
    root = tmp_path / "operator"
    proj = root / "research" / "proj-x"
    proj.mkdir(parents=True)
    (proj / "project.json").write_text(json.dumps({"id": "proj-x", "domain": "general"}))
    monkeypatch.setenv("OPERATOR_ROOT", str(root))
    monkeypatch.setenv("RESEARCH_MEMORY_V2_ENABLED", "1")
    from lib import memory as memory_module
    monkeypatch.setattr(memory_module, "DB_PATH", root / "memory" / "operator.db")

    ctx = planner._load_strategy_context("question without strategy", "proj-x")
    with Memory(db_path=str(root / "memory" / "operator.db")) as mem:
        decisions = mem.list_memory_decisions(project_id="proj-x", limit=10)

    assert ctx is not None
    assert ctx.get("mode") == "v2_fallback"
    assert ctx.get("fallback_reason") == "no_strategy"
    assert any(
        d.get("decision_type") == "strategy_mode_detail"
        and (d.get("details") or {}).get("fallback_reason") == "no_strategy"
        for d in decisions
    )


def test_persist_strategy_context_contains_mode_fields(tmp_path):
    root = tmp_path / "operator"
    proj = root / "research" / "proj-y"
    proj.mkdir(parents=True)
    data = {
        "mode": "v2_fallback",
        "fallback_reason": "low_confidence",
        "confidence_drivers": {"strategy_score": 0.4},
        "similar_episode_count": 1,
    }
    old_root = planner.research_root
    planner.research_root = lambda: root / "research"
    try:
        planner._persist_strategy_context("proj-y", data)
        saved = json.loads((proj / "memory_strategy.json").read_text())
    finally:
        planner.research_root = old_root
    assert saved["mode"] == "v2_fallback"
    assert saved["fallback_reason"] == "low_confidence"
    assert saved["similar_episode_count"] == 1
