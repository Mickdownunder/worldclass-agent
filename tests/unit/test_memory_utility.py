"""Unit tests for lib/memory/utility.py — record_retrieval, update_from_outcome, Laplace."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.utility import UtilityTracker


def test_record_retrieval_insert(memory_conn):
    """First call (memory_type, memory_id): row with retrieval_count=1, helpful_count=0, utility_score=0.5."""
    u = UtilityTracker(memory_conn)
    u.record_retrieval("principle", "pid-1")
    row = u.get("principle", "pid-1")
    assert row is not None
    assert row["retrieval_count"] == 1
    assert row["helpful_count"] == 0
    assert abs(row["utility_score"] - 0.5) < 1e-9


def test_record_retrieval_increment(memory_conn):
    """Second call same (type, id): retrieval_count=2 (ON CONFLICT DO UPDATE)."""
    u = UtilityTracker(memory_conn)
    u.record_retrieval("principle", "pid-1")
    u.record_retrieval("principle", "pid-1")
    row = u.get("principle", "pid-1")
    assert row["retrieval_count"] == 2


def test_update_from_outcome_laplace_helpful(memory_conn):
    """record_retrieval (count=1); update_from_outcome(..., 0.8): helpful_count=1, utility = (1+1)/(1+2)=2/3."""
    u = UtilityTracker(memory_conn)
    u.record_retrieval("principle", "pid-1")
    u.update_from_outcome("principle", ["pid-1"], outcome_score=0.8)
    row = u.get("principle", "pid-1")
    assert row["helpful_count"] == 1
    assert abs(row["utility_score"] - (2 / 3)) < 1e-9


def test_update_from_outcome_laplace_not_helpful(memory_conn):
    """retrieval_count=2, helpful_count=0; outcome_score=0.3: helpful_count=0, utility = (0+1)/(2+2)=0.25."""
    u = UtilityTracker(memory_conn)
    u.record_retrieval("principle", "pid-1")
    u.record_retrieval("principle", "pid-1")
    u.update_from_outcome("principle", ["pid-1"], outcome_score=0.3)
    row = u.get("principle", "pid-1")
    assert row["helpful_count"] == 0
    assert abs(row["utility_score"] - 0.25) < 1e-9


def test_update_from_outcome_multiple_ids(memory_conn):
    """memory_ids=[id1, id2]; outcome_score=0.8: both rows get helpful_count += 1, Laplace (1+1)/(1+2)=2/3."""
    u = UtilityTracker(memory_conn)
    u.record_retrieval("principle", "p1")
    u.record_retrieval("principle", "p2")
    u.update_from_outcome("principle", ["p1", "p2"], outcome_score=0.8)
    r1 = u.get("principle", "p1")
    r2 = u.get("principle", "p2")
    assert r1["helpful_count"] == 1 and r2["helpful_count"] == 1
    assert abs(r1["utility_score"] - (2 / 3)) < 1e-9


def test_update_from_outcome_missing_row_skipped(memory_conn):
    """memory_id never record_retrieval; update_from_outcome(..., [that_id]): no crash, row not created."""
    u = UtilityTracker(memory_conn)
    u.update_from_outcome("principle", ["never-retrieved-id"], outcome_score=0.9)
    assert u.get("principle", "never-retrieved-id") is None


def test_contextual_utility_rows(memory_conn):
    """Context-key retrieval tracks and updates per-context utility independently."""
    u = UtilityTracker(memory_conn)
    u.record_retrieval("principle", "pid-ctx", context_key="medical trial safety")
    row = u.get("principle", "pid-ctx", context_key="medical trial safety")
    assert row is not None
    assert row["retrieval_count"] == 1
    u.update_from_outcome(
        "principle",
        ["pid-ctx"],
        outcome_score=0.9,
        context_key="medical trial safety",
    )
    row2 = u.get("principle", "pid-ctx", context_key="medical trial safety")
    assert row2 is not None
    assert row2["helpful_count"] == 1
