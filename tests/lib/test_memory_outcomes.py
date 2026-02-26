"""Unit tests for lib/memory/outcomes.py — get_successful_outcomes filter."""
import json
import pytest

from lib.memory.outcomes import record_outcome, get_successful_outcomes, count_outcomes


def test_get_successful_outcomes_filters_min_critic(memory_conn):
    """record_outcome(..., critic_score=0.8); record_outcome(..., critic_score=0.5); get_successful_outcomes(min_critic=0.75): only 0.8."""
    record_outcome(memory_conn, "proj-1", critic_score=0.8)
    record_outcome(memory_conn, "proj-2", critic_score=0.5)
    results = get_successful_outcomes(memory_conn, min_critic=0.75)
    assert len(results) == 1
    assert results[0]["project_id"] == "proj-1"


def test_get_successful_outcomes_excludes_rejected(memory_conn):
    """record_outcome(..., user_verdict='rejected', critic_score=0.9): not in get_successful_outcomes(min_critic=0.5)."""
    record_outcome(memory_conn, "proj-rej", user_verdict="rejected", critic_score=0.9)
    results = get_successful_outcomes(memory_conn, min_critic=0.5)
    assert not any(r["project_id"] == "proj-rej" for r in results)


def test_get_successful_outcomes_includes_null_verdict(memory_conn):
    """record_outcome(..., user_verdict=None, critic_score=0.8): in get_successful_outcomes(min_critic=0.75)."""
    record_outcome(memory_conn, "proj-null", user_verdict=None, critic_score=0.8)
    results = get_successful_outcomes(memory_conn, min_critic=0.75)
    assert any(r["project_id"] == "proj-null" for r in results)


def test_get_successful_outcomes_limit(memory_conn):
    """50 outcomes; get_successful_outcomes(limit=10): at most 10 rows."""
    for i in range(50):
        record_outcome(memory_conn, f"proj-{i}", critic_score=0.9)
    results = get_successful_outcomes(memory_conn, min_critic=0.5, limit=10)
    assert len(results) == 10


def test_count_outcomes(memory_conn):
    """3x record_outcome: count_outcomes(conn) == 3."""
    record_outcome(memory_conn, "a", critic_score=0.5)
    record_outcome(memory_conn, "b", critic_score=0.6)
    record_outcome(memory_conn, "c", critic_score=0.7)
    assert count_outcomes(memory_conn) == 3
