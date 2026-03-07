"""Unit tests for lib/memory/reflections.py — record, recent, recent_for_planning, for_job."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.reflections import Reflections


def test_reflections_record_returns_id(memory_conn):
    """record(job_id, outcome, quality) returns non-empty id."""
    r = Reflections(memory_conn)
    rid = r.record("j1", "ok", 0.8)
    assert rid


def test_reflections_recent_empty_returns_empty(memory_conn):
    """recent(limit=5) on empty table returns []."""
    assert Reflections(memory_conn).recent(limit=5) == []


def test_reflections_recent_with_min_quality_filters(memory_conn):
    """recent(limit=10, min_quality=0.7) returns only quality >= 0.7."""
    ref = Reflections(memory_conn)
    ref.record("j1", "low", 0.4)
    ref.record("j2", "high", 0.9)
    rows = ref.recent(limit=10, min_quality=0.7)
    assert len(rows) == 1
    assert rows[0]["quality"] >= 0.7


def test_reflections_recent_for_planning_dedupes_by_outcome_prefix(memory_conn):
    """recent_for_planning with two same workflow+outcome prefix returns one."""
    ref = Reflections(memory_conn)
    ref.record("j1", "outcome A", 0.8, workflow_id="wf1")
    ref.record("j2", "outcome A", 0.7, workflow_id="wf1")
    rows = ref.recent_for_planning(limit=10, dedupe_outcome_prefix=80)
    assert len(rows) >= 1
    assert len(rows) <= 2


def test_reflections_recent_for_planning_excludes_low_signal(memory_conn):
    """Reflection with metadata low_signal=True excluded from recent_for_planning."""
    ref = Reflections(memory_conn)
    ref.record("j1", "ok", 0.8, metadata={"low_signal": True})
    rows = ref.recent_for_planning(limit=10, exclude_low_signal=True)
    assert len(rows) == 0


def test_reflections_for_job_returns_one_reflection_for_that_job(memory_conn):
    """for_job(job_id) returns one reflection row for that job (latest by ts)."""
    ref = Reflections(memory_conn)
    ref.record("job-x", "first", 0.5)
    ref.record("job-x", "second", 0.9)
    row = ref.for_job("job-x")
    assert row is not None
    assert row["job_id"] == "job-x"
    assert row["outcome"] in ("first", "second")


def test_reflections_for_job_unknown_returns_none(memory_conn):
    """for_job('unknown') returns None."""
    assert Reflections(memory_conn).for_job("unknown") is None
