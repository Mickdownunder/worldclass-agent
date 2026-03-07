"""Unit tests for lib/memory/outcomes.py — record_outcome, count_outcomes, list_outcomes, get_successful_outcomes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.outcomes import (
    record_outcome,
    count_outcomes,
    list_outcomes,
    get_successful_outcomes,
)


def test_record_outcome_inserts_row(memory_conn):
    """record_outcome creates one row in project_outcomes."""
    record_outcome(
        memory_conn,
        project_id="proj-1",
        domain="health",
        critic_score=0.8,
        user_verdict="accepted",
    )
    assert count_outcomes(memory_conn) == 1


def test_record_outcome_replace_same_project_id(memory_conn):
    """record_outcome with same project_id replaces (INSERT OR REPLACE)."""
    record_outcome(memory_conn, project_id="p1", critic_score=0.5)
    record_outcome(memory_conn, project_id="p1", critic_score=0.9, domain="ai")
    assert count_outcomes(memory_conn) == 1
    rows = list_outcomes(memory_conn, limit=10)
    assert len(rows) == 1
    assert rows[0]["critic_score"] == 0.9
    assert rows[0]["domain"] == "ai"


def test_count_outcomes_empty_is_zero(memory_conn):
    """count_outcomes on empty DB returns 0."""
    assert count_outcomes(memory_conn) == 0


def test_count_outcomes_after_two_records(memory_conn):
    """count_outcomes returns 2 after two distinct project_ids."""
    record_outcome(memory_conn, project_id="p1")
    record_outcome(memory_conn, project_id="p2")
    assert count_outcomes(memory_conn) == 2


def test_list_outcomes_returns_ordered_by_completed_at_desc(memory_conn):
    """list_outcomes returns rows ordered by completed_at DESC; both records present."""
    record_outcome(memory_conn, project_id="first")
    record_outcome(memory_conn, project_id="second")
    rows = list_outcomes(memory_conn, limit=10)
    assert len(rows) == 2
    pids = {r["project_id"] for r in rows}
    assert pids == {"first", "second"}
    # completed_at DESC: later insert has later timestamp (when distinct)
    assert rows[0]["completed_at"] >= rows[1]["completed_at"]


def test_list_outcomes_respects_limit(memory_conn):
    """list_outcomes(limit=1) returns at most 1 row."""
    record_outcome(memory_conn, project_id="p1")
    record_outcome(memory_conn, project_id="p2")
    rows = list_outcomes(memory_conn, limit=1)
    assert len(rows) == 1


def test_get_successful_outcomes_filters_by_min_critic(memory_conn):
    """get_successful_outcomes(min_critic=0.75) excludes rows with critic_score < 0.75."""
    record_outcome(memory_conn, project_id="low", critic_score=0.5)
    record_outcome(memory_conn, project_id="high", critic_score=0.9)
    result = get_successful_outcomes(memory_conn, min_critic=0.75, limit=10)
    assert len(result) == 1
    assert result[0]["project_id"] == "high"


def test_get_successful_outcomes_excludes_rejected_verdict(memory_conn):
    """get_successful_outcomes excludes user_verdict='rejected' even if critic high."""
    record_outcome(memory_conn, project_id="rej", critic_score=0.9, user_verdict="rejected")
    record_outcome(memory_conn, project_id="ok", critic_score=0.9, user_verdict="accepted")
    result = get_successful_outcomes(memory_conn, min_critic=0.75, limit=10)
    pids = [r["project_id"] for r in result]
    assert "rej" not in pids
    assert "ok" in pids


def test_record_outcome_optional_fields_default(memory_conn):
    """record_outcome with minimal args: domain/verdict/gate_metrics etc default safely."""
    record_outcome(memory_conn, project_id="minimal")
    rows = list_outcomes(memory_conn, limit=1)
    assert len(rows) == 1
    assert rows[0]["domain"] == ""
    assert rows[0]["user_verdict"] == "none"


def test_record_outcome_with_none_critic_score_stores_null(memory_conn):
    """record_outcome(project_id, critic_score=None): row has critic_score NULL, get_successful skips it."""
    record_outcome(memory_conn, project_id="no_critic", critic_score=None)
    rows = get_successful_outcomes(memory_conn, min_critic=0.75, limit=10)
    pids = [r["project_id"] for r in rows]
    assert "no_critic" not in pids
    all_rows = list_outcomes(memory_conn, limit=1)
    assert all_rows[0]["critic_score"] is None


def test_record_outcome_with_findings_count_and_source_count(memory_conn):
    """record_outcome with findings_count/source_count: stored and readable."""
    record_outcome(
        memory_conn,
        project_id="with_counts",
        findings_count=10,
        source_count=5,
    )
    rows = list_outcomes(memory_conn, limit=1)
    assert rows[0]["findings_count"] == 10
    assert rows[0]["source_count"] == 5
