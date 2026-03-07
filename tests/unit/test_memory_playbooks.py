"""Unit tests for lib/memory/playbooks.py — upsert, get, all_latest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.playbooks import Playbooks


def test_playbooks_upsert_new_domain_returns_id(memory_conn):
    """upsert(domain, strategy) for new domain returns id."""
    p = Playbooks(memory_conn)
    pid = p.upsert("domain1", "strategy text")
    assert pid


def test_playbooks_get_returns_none_unknown_domain(memory_conn):
    """get('unknown') returns None."""
    assert Playbooks(memory_conn).get("unknown") is None


def test_playbooks_get_returns_latest_version(memory_conn):
    """After upsert, get(domain) returns row with strategy."""
    p = Playbooks(memory_conn)
    p.upsert("d1", "first strategy")
    row = p.get("d1")
    assert row is not None
    assert row["strategy"] == "first strategy"


def test_playbooks_upsert_existing_increments_version(memory_conn):
    """Second upsert same domain creates new version."""
    p = Playbooks(memory_conn)
    p.upsert("d1", "v1")
    p.upsert("d1", "v2", evidence=["e1"])
    row = p.get("d1")
    assert row["strategy"] == "v2"
    assert row["version"] == 2


def test_playbooks_all_latest_returns_one_per_domain(memory_conn):
    """all_latest() returns one row per domain (latest version)."""
    p = Playbooks(memory_conn)
    p.upsert("a", "s1")
    p.upsert("b", "s2")
    rows = p.all_latest()
    assert len(rows) == 2
    domains = {r["domain"] for r in rows}
    assert domains == {"a", "b"}
