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


def test_list_all_empty_returns_empty_list(memory_conn):
    """list_all(conn, limit=50) on empty table returns []."""
    rows = sc.list_all(memory_conn, limit=50)
    assert rows == []


def test_list_all_returns_inserted_domains_ordered(memory_conn):
    """After update(domain1) and update(domain2), list_all returns both rows."""
    sc.update(memory_conn, "domain_a", 1, 1, 0)
    sc.update(memory_conn, "domain_b", 2, 1, 0)
    rows = sc.list_all(memory_conn, limit=10)
    assert len(rows) >= 2
    domains = {r["domain"] for r in rows}
    assert "domain_a" in domains
    assert "domain_b" in domains


def test_list_all_respects_limit(memory_conn):
    """list_all(conn, limit=1) returns at most 1 row."""
    sc.update(memory_conn, "d1", 1, 1, 0)
    sc.update(memory_conn, "d2", 1, 1, 0)
    rows = sc.list_all(memory_conn, limit=1)
    assert len(rows) <= 1
