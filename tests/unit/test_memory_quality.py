"""Unit tests for lib/memory/quality.py — record, trend, avg."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.quality import Quality


def test_quality_record_returns_id(memory_conn):
    """record(job_id, score) returns non-empty id."""
    q = Quality(memory_conn)
    qid = q.record("j1", 0.8)
    assert qid


def test_quality_trend_empty_returns_empty(memory_conn):
    """trend(workflow_id, limit) on empty returns []."""
    assert Quality(memory_conn).trend("wf1", limit=10) == []


def test_quality_trend_returns_scores_for_workflow(memory_conn):
    """record with workflow_id; trend(workflow_id) returns rows."""
    q = Quality(memory_conn)
    q.record("j1", 0.7, workflow_id="wf1")
    q.record("j2", 0.9, workflow_id="wf1")
    rows = q.trend("wf1", limit=10)
    assert len(rows) == 2


def test_quality_avg_empty_returns_zero(memory_conn):
    """avg() on empty table returns 0.0."""
    assert Quality(memory_conn).avg() == 0.0


def test_quality_avg_with_workflow_returns_mean(memory_conn):
    """record two scores; avg(workflow_id) returns mean."""
    q = Quality(memory_conn)
    q.record("j1", 0.6, workflow_id="wf1")
    q.record("j2", 0.8, workflow_id="wf1")
    assert abs(q.avg("wf1") - 0.7) < 1e-9


def test_quality_avg_no_workflow_returns_global_mean(memory_conn):
    """avg(None) returns mean over all scores."""
    q = Quality(memory_conn)
    q.record("j1", 0.5)
    q.record("j2", 0.7)
    assert abs(q.avg() - 0.6) < 1e-9
