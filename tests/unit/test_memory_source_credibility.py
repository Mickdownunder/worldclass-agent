"""Unit tests for lib/memory/source_credibility.py — Laplace, upsert."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory import source_credibility as sc


def test_update_insert_laplace(memory_conn):
    """update(conn, 'domain1', times_used=1, verified_count=1, failed=0) on empty table: learned_credibility = (1+1)/(1+2) = 2/3."""
    sc.update(memory_conn, "domain1", times_used=1, verified_count=1, failed_verification_count=0)
    row = sc.get(memory_conn, "domain1")
    assert row is not None
    assert abs(row["learned_credibility"] - (2 / 3)) < 1e-9
    assert row["times_used"] == 1
    assert row["verified_count"] == 1


def test_update_upsert_aggregates(memory_conn):
    """update(domain, 2, 1, 0); update(domain, 3, 2, 0): second call: times_used=5, verified_count=3, learned_credibility = (3+1)/(5+2) = 4/7."""
    sc.update(memory_conn, "domain2", times_used=2, verified_count=1, failed_verification_count=0)
    sc.update(memory_conn, "domain2", times_used=3, verified_count=2, failed_verification_count=0)
    row = sc.get(memory_conn, "domain2")
    assert row["times_used"] == 5
    assert row["verified_count"] == 3
    assert abs(row["learned_credibility"] - (4 / 7)) < 1e-9


def test_get_returns_none_unknown_domain(memory_conn):
    """get(conn, 'unknown'): None."""
    assert sc.get(memory_conn, "unknown") is None


def test_get_returns_row_after_update(memory_conn):
    """update(domain, 1, 1, 0); get(conn, domain): dict with learned_credibility, times_used, verified_count."""
    sc.update(memory_conn, "domain3", 1, 1, 0)
    row = sc.get(memory_conn, "domain3")
    assert "learned_credibility" in row
    assert "times_used" in row
    assert "verified_count" in row
    assert row["times_used"] == 1
    assert row["verified_count"] == 1
