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
    assert abs(results[0]["combined_score"] - (0.4 * 0.5 + 0.6 * 0.5)) < 1e-9


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