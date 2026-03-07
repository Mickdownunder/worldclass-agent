"""Unit tests for Memory.retrieve_with_utility — two-phase ranking, edge cases."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from unittest.mock import patch
import pytest
from lib.memory import Memory


@pytest.fixture
def memory_db_path(tmp_path):
    """Path to a temp DB file for Memory (Memory requires a file path)."""
    db = tmp_path / "memory" / "operator.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    return db


def test_retrieve_with_utility_two_phase_ranking(memory_db_path):
    """Insert principles, set different utility via record_retrieval + update_from_outcome; retrieve sorts by 0.4*relevance + 0.6*utility."""
    mem = Memory(db_path=str(memory_db_path))
    pid1 = mem.insert_principle("guiding", "Principle high utility", "proj-1")
    pid2 = mem.insert_principle("guiding", "Principle low utility", "proj-1")
    mem.record_retrieval("principle", pid1)
    mem.record_retrieval("principle", pid1)
    mem.record_retrieval("principle", pid2)
    mem.update_utilities_from_outcome("principle", [pid1], outcome_score=0.9)
    mem.update_utilities_from_outcome("principle", [pid2], outcome_score=0.2)
    results = mem.retrieve_with_utility("Principle", "principle", k=5)
    mem.close()
    assert len(results) >= 2
    assert results[0]["combined_score"] >= results[1]["combined_score"]
    ids = [r["id"] for r in results]
    assert ids.index(pid1) < ids.index(pid2)


def test_retrieve_with_utility_empty_db(memory_db_path):
    """Empty DB; retrieve_with_utility('anything', 'principle', k=10): []."""
    mem = Memory(db_path=str(memory_db_path))
    results = mem.retrieve_with_utility("anything", "principle", k=10)
    mem.close()
    assert results == []


def test_retrieve_with_utility_unknown_memory_type(memory_db_path):
    """retrieve_with_utility('q', 'unknown_type', k=5): []."""
    mem = Memory(db_path=str(memory_db_path))
    results = mem.retrieve_with_utility("q", "unknown_type", k=5)
    mem.close()
    assert results == []


def test_retrieve_with_utility_no_utility_row_default_0_5(memory_db_path):
    """Candidate never record_retrieval: utility_score=0.5, combined_score consistent."""
    mem = Memory(db_path=str(memory_db_path))
    mem.insert_principle("guiding", "New principle", "proj-1")
    results = mem.retrieve_with_utility("New", "principle", k=5)
    mem.close()
    assert len(results) == 1
    assert abs(results[0]["utility_score"] - 0.5) < 1e-9
    assert "similarity_score" in results[0]
    assert "combined_score" in results[0]
    assert 0.0 <= float(results[0]["combined_score"]) <= 1.0


def test_retrieve_with_utility_candidate_without_id_skipped(memory_db_path):
    """Candidate without id: no crash; candidate stays in list but is not ranked (no combined_score or score 0)."""
    mem = Memory(db_path=str(memory_db_path))
    with patch.object(mem._principles, "search", return_value=[{"description": "no id field"}]):
        results = mem.retrieve_with_utility("x", "principle", k=5)
    mem.close()
    # Implementation skips adding utility/combined for missing id; candidate may still appear with default score 0
    assert len(results) <= 1
    if results:
        assert results[0].get("description") == "no id field"


def test_retrieve_with_utility_principles_domain_first_with_fallback(memory_db_path, monkeypatch):
    """Flag on: same-domain principles are prioritized; unknown domain falls back to global results."""
    monkeypatch.setenv("RESEARCH_MEMORY_PRINCIPLE_DOMAIN_FILTER", "1")
    mem = Memory(db_path=str(memory_db_path))
    pid_m = mem.insert_principle(
        "guiding",
        "Use evidence layering and source triangulation in manufacturing investigations",
        "proj-1",
        domain="manufacturing",
    )
    mem.insert_principle(
        "guiding",
        "Use evidence layering and source triangulation in biomedical investigations",
        "proj-1",
        domain="biomedical",
    )
    prioritized = mem.retrieve_with_utility(
        "evidence triangulation investigations",
        "principle",
        k=5,
        domain="manufacturing",
    )
    fallback = mem.retrieve_with_utility(
        "evidence triangulation investigations",
        "principle",
        k=5,
        domain="unknown-domain",
    )
    mem.close()
    assert prioritized
    assert prioritized[0]["id"] == pid_m
    assert fallback


def test_list_memory_decisions_v2(memory_db_path):
    """Memory facade exposes memory v2 decision log rows with parsed details."""
    mem = Memory(db_path=str(memory_db_path))
    mem.record_memory_decision(
        decision_type="v2_mode",
        details={"mode": "v2_disabled", "fallback_reason": "flag_off"},
        project_id="proj-1",
        phase="planner",
        confidence=1.0,
    )
    rows = mem.list_memory_decisions(project_id="proj-1", limit=5)
    mem.close()
    assert rows
    assert rows[0]["decision_type"] == "v2_mode"
    assert rows[0]["details"]["mode"] == "v2_disabled"


def test_record_episode_and_recent_episodes(memory_db_path):
    """record_episode then recent_episodes returns the recorded row."""
    mem = Memory(db_path=str(memory_db_path))
    eid = mem.record_episode("test", "content here", job_id="j1")
    rows = mem.recent_episodes(limit=5)
    mem.close()
    assert eid
    assert len(rows) == 1
    assert rows[0]["content"] == "content here"
    assert rows[0]["kind"] == "test"


def test_record_decision_and_get_trace(memory_db_path):
    """record_decision with trace_id then get_trace returns the decision."""
    mem = Memory(db_path=str(memory_db_path))
    tid = "trace-abc"
    did = mem.record_decision("think", {"x": 1}, "reasoning", "do X", trace_id=tid)
    trace = mem.get_trace(tid)
    mem.close()
    assert did
    assert len(trace) == 1
    assert trace[0]["decision"] == "do X"


def test_record_reflection_and_recent_reflections(memory_db_path):
    """record_reflection then recent_reflections returns the row."""
    mem = Memory(db_path=str(memory_db_path))
    rid = mem.record_reflection("j1", "outcome", 0.8, learnings="learned")
    rows = mem.recent_reflections(limit=5)
    mem.close()
    assert rid
    assert len(rows) == 1
    assert rows[0]["outcome"] == "outcome"
    assert rows[0]["quality"] == 0.8


def test_upsert_playbook_and_get_playbook(memory_db_path):
    """upsert_playbook then get_playbook returns the strategy."""
    mem = Memory(db_path=str(memory_db_path))
    mem.upsert_playbook("domain1", "strategy text", evidence=["e1"])
    row = mem.get_playbook("domain1")
    mem.close()
    assert row is not None
    assert row["strategy"] == "strategy text"


def test_record_quality_and_trend_and_avg(memory_db_path):
    """record_quality then quality_trend and avg_quality return the score."""
    mem = Memory(db_path=str(memory_db_path))
    mem.record_quality("j1", 0.85, workflow_id="wf1")
    trend = mem.quality_trend("wf1", limit=5)
    avg = mem.avg_quality("wf1")
    mem.close()
    assert len(trend) == 1
    assert trend[0]["score"] == 0.85
    assert abs(avg - 0.85) < 1e-9


def test_state_summary_returns_dict(memory_db_path):
    """state_summary returns dict with totals and recent_* keys."""
    mem = Memory(db_path=str(memory_db_path))
    mem.record_episode("test", "x")
    summary = mem.state_summary()
    mem.close()
    assert "totals" in summary
    assert "recent_episodes" in summary
    assert summary["totals"]["episodes"] >= 1


def test_search_episodes_and_search_reflections(memory_db_path):
    """search_episodes and search_reflections return matching rows."""
    mem = Memory(db_path=str(memory_db_path))
    mem.record_episode("test", "docker and kubernetes")
    mem.record_reflection("j1", "deployment succeeded", 0.8, learnings="kubernetes best practices")
    ep = mem.search_episodes("docker", limit=5)
    ref = mem.search_reflections("kubernetes", limit=5)
    mem.close()
    assert len(ep) >= 1
    assert len(ref) >= 1
    assert "similarity_score" in ep[0]
    assert "similarity_score" in ref[0]


def test_insert_research_finding_and_get_accepted(memory_db_path):
    """insert_research_finding with admission_state=accepted then get_research_findings_accepted returns it."""
    mem = Memory(db_path=str(memory_db_path))
    fid = mem.insert_research_finding("p1", "key1", "preview", admission_state="accepted")
    rows = mem.get_research_findings_accepted(project_id="p1", limit=10)
    mem.close()
    assert fid
    assert len(rows) >= 1
    assert rows[0]["finding_key"] == "key1"


def test_record_project_outcome_and_count_and_list(memory_db_path):
    """record_project_outcome then count_project_outcomes and list_project_outcomes."""
    mem = Memory(db_path=str(memory_db_path))
    mem.record_project_outcome("proj-1", domain="health", critic_score=0.9)
    n = mem.count_project_outcomes()
    rows = mem.list_project_outcomes(limit=10)
    mem.close()
    assert n >= 1
    assert len(rows) >= 1
    assert rows[0]["project_id"] == "proj-1"
    assert rows[0]["critic_score"] == 0.9


def test_get_source_credibility_and_update(memory_db_path):
    """update_source_credibility then get_source_credibility returns the row."""
    mem = Memory(db_path=str(memory_db_path))
    mem.update_source_credibility("domain1", times_used=2, verified_count=1, failed_verification_count=0)
    row = mem.get_source_credibility("domain1")
    mem.close()
    assert row is not None
    assert row["times_used"] >= 2
    assert "learned_credibility" in row


def test_recent_reflections_for_planning(memory_db_path):
    """record_reflection then recent_reflections_for_planning returns high-quality ones."""
    mem = Memory(db_path=str(memory_db_path))
    mem.record_reflection("j1", "outcome", 0.9, learnings="takeaway")
    rows = mem.recent_reflections_for_planning(limit=5, min_quality=0.5)
    mem.close()
    assert len(rows) >= 1
    assert rows[0]["quality"] >= 0.5