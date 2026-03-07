"""Unit tests for lib/memory/decisions.py — record, get_trace, recent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.decisions import Decisions


def test_decisions_record_returns_id(memory_conn):
    """record(phase, inputs, reasoning, decision) returns non-empty id."""
    d = Decisions(memory_conn)
    did = d.record("think", {"x": 1}, "reasoning", "do X")
    assert did


def test_decisions_recent_empty_returns_empty(memory_conn):
    """recent(limit=5) on empty table returns []."""
    assert Decisions(memory_conn).recent(limit=5) == []


def test_decisions_get_trace_returns_all_with_trace_id(memory_conn):
    """record with trace_id; get_trace(trace_id) returns those decisions."""
    dec = Decisions(memory_conn)
    tid = "trace-1"
    dec.record("phase1", {}, "r1", "d1", trace_id=tid)
    dec.record("phase2", {}, "r2", "d2", trace_id=tid)
    rows = dec.get_trace(tid)
    assert len(rows) == 2


def test_decisions_get_trace_unknown_returns_empty(memory_conn):
    """get_trace('unknown') returns []."""
    assert Decisions(memory_conn).get_trace("unknown") == []
