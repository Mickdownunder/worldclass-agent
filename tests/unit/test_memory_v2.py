"""Unit tests for Memory v2 tables and strategy learning."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.memory import Memory


def test_memory_v2_record_episode_and_select_strategy(tmp_path):
    db_path = tmp_path / "memory" / "operator.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    mem = Memory(db_path=str(db_path))
    sid = mem.upsert_strategy_profile(
        name="medical-high-precision",
        domain="medical",
        policy={
            "preferred_query_types": {"medical": 0.7, "academic": 0.3},
            "relevance_threshold": 0.6,
            "critic_threshold": 0.58,
            "revise_rounds": 2,
        },
        score=0.62,
        confidence=0.5,
    )
    eid = mem.record_run_episode(
        project_id="proj-a",
        question="Best clinical trial evidence for mRNA vaccine safety",
        domain="medical",
        status="done",
        strategy_profile_id=sid,
        plan_query_mix={"medical": 0.8},
    )
    mem.record_graph_edge(
        edge_type="used_in",
        from_node_type="strategy_profile",
        from_node_id=sid,
        to_node_type="run_episode",
        to_node_id=eid,
        project_id="proj-a",
    )
    selected = mem.select_strategy("clinical trial mRNA safety evidence", domain="medical")
    mem.close()

    assert selected is not None
    assert selected["id"] == sid
    assert selected["selection_confidence"] >= 0.4


def test_memory_v2_strategy_score_updates(tmp_path):
    db_path = tmp_path / "memory" / "operator.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    mem = Memory(db_path=str(db_path))
    sid = mem.upsert_strategy_profile(
        name="general-balanced",
        domain="general",
        policy={"critic_threshold": 0.55},
        score=0.5,
        confidence=0.3,
    )
    before = [s for s in mem.list_strategy_profiles(domain="general", limit=10) if s["id"] == sid][0]["score"]
    mem.update_strategy_from_outcome(
        strategy_profile_id=sid,
        critic_pass=True,
        evidence_gate_pass=True,
        user_verdict="approved",
        claim_support_rate=0.9,
    )
    after_success = [s for s in mem.list_strategy_profiles(domain="general", limit=10) if s["id"] == sid][0]["score"]
    mem.update_strategy_from_outcome(
        strategy_profile_id=sid,
        critic_pass=False,
        evidence_gate_pass=False,
        user_verdict="rejected",
        claim_support_rate=0.2,
        failed_quality_gate=True,
    )
    after_fail = [s for s in mem.list_strategy_profiles(domain="general", limit=10) if s["id"] == sid][0]["score"]
    mem.close()

    assert after_success > before
    assert after_fail < after_success


def test_memory_v2_select_strategy_includes_confidence_drivers(tmp_path):
    db_path = tmp_path / "memory" / "operator.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    mem = Memory(db_path=str(db_path))
    sid = mem.upsert_strategy_profile(
        name="finance-precision",
        domain="finance",
        policy={"preferred_query_types": {"academic": 0.7, "web": 0.3}},
        score=0.66,
        confidence=0.4,
    )
    mem.record_run_episode(
        project_id="proj-f1",
        question="equity valuation multiples in private markets",
        domain="finance",
        status="done",
        strategy_profile_id=sid,
    )
    selected = mem.select_strategy("private market equity valuation multiples", domain="finance")
    mem.close()

    assert selected is not None
    assert selected["id"] == sid
    assert selected.get("similar_episode_count", 0) >= 1
    drivers = selected.get("confidence_drivers") or {}
    assert "strategy_score" in drivers
    assert "query_overlap" in drivers


def test_memory_v2_keeps_multiple_run_episodes_per_project(tmp_path):
    db_path = tmp_path / "memory" / "operator.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    mem = Memory(db_path=str(db_path))
    e1 = mem.record_run_episode(
        project_id="proj-repeat",
        question="Q1",
        domain="general",
        status="done",
    )
    e2 = mem.record_run_episode(
        project_id="proj-repeat",
        question="Q1 follow-up",
        domain="general",
        status="done",
    )
    rows = mem._conn.execute(
        "SELECT id, run_index FROM run_episodes WHERE project_id='proj-repeat' ORDER BY run_index ASC"
    ).fetchall()
    mem.close()
    assert e1 != e2
    assert len(rows) == 2
    assert [int(r["run_index"]) for r in rows] == [1, 2]


def test_memory_v2_read_urls_signature_handles_reordered_question(tmp_path):
    db_path = tmp_path / "memory" / "operator.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    mem = Memory(db_path=str(db_path))
    mem.record_read_urls("How to improve battery life in EV fleets", ["https://example.com/a"])
    urls = mem.get_read_urls_for_question("Improve EV fleet battery life how")
    mem.close()
    assert "https://example.com/a" in urls
