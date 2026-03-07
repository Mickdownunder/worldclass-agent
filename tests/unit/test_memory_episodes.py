"""Unit tests for lib/memory/episodes.py — Episodes.record, recent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.episodes import Episodes


def test_episodes_record_returns_id(memory_conn):
    """record(kind, content) returns non-empty id."""
    ep = Episodes(memory_conn)
    eid = ep.record("test", "hello world")
    assert eid
    assert len(eid) >= 8


def test_episodes_recent_empty_returns_empty_list(memory_conn):
    """recent(limit=10) on empty table returns []."""
    ep = Episodes(memory_conn)
    assert ep.recent(limit=10) == []


def test_episodes_recent_returns_recorded(memory_conn):
    """After record(), recent() returns one row with content."""
    ep = Episodes(memory_conn)
    ep.record("test", "content one")
    rows = ep.recent(limit=5)
    assert len(rows) == 1
    assert rows[0]["content"] == "content one"
    assert rows[0]["kind"] == "test"


def test_episodes_recent_with_kind_filters(memory_conn):
    """recent(limit=10, kind='a') returns only kind='a'."""
    ep = Episodes(memory_conn)
    ep.record("a", "x")
    ep.record("b", "y")
    rows = ep.recent(limit=10, kind="a")
    assert len(rows) == 1
    assert rows[0]["kind"] == "a"


def test_episodes_record_with_job_id_and_workflow_id(memory_conn):
    """record with job_id and workflow_id stores them."""
    ep = Episodes(memory_conn)
    ep.record("run", "done", job_id="j1", workflow_id="wf1")
    rows = ep.recent(limit=1)
    assert rows[0]["job_id"] == "j1"
    assert rows[0]["workflow_id"] == "wf1"
