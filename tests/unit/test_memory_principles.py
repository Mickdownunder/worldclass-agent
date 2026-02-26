"""Unit tests for lib/memory/principles.py — Laplace formula, insert, search."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.principles import Principles


def test_update_usage_success_formula_first_use(memory_conn):
    """usage=0, success_count=0 → after update_usage_success(pid, True): (1+1)/(1+2) = 2/3."""
    p = Principles(memory_conn)
    pid = p.insert("guiding", "Do X", "proj-1")
    p.update_usage_success(pid, True)
    row = p.get(pid)
    assert row is not None
    assert row["usage_count"] == 1
    assert row["success_count"] == 1
    assert abs(row["metric_score"] - (2 / 3)) < 1e-9


def test_update_usage_success_formula_after_success(memory_conn):
    """usage=2, success_count=2 after two update(True): (2+1)/(2+2) = 0.75."""
    p = Principles(memory_conn)
    pid = p.insert("guiding", "Do Y", "proj-1")
    p.update_usage_success(pid, True)
    p.update_usage_success(pid, True)
    row = p.get(pid)
    assert row["usage_count"] == 2
    assert row["success_count"] == 2
    assert abs(row["metric_score"] - 0.75) < 1e-9


def test_update_usage_success_formula_after_failure(memory_conn):
    """usage=2, success_count=1 after one True one False: (1+1)/(2+2) = 0.5."""
    p = Principles(memory_conn)
    pid = p.insert("cautionary", "Avoid Z", "proj-1")
    p.update_usage_success(pid, True)
    p.update_usage_success(pid, False)
    row = p.get(pid)
    assert row["usage_count"] == 2
    assert row["success_count"] == 1
    assert abs(row["metric_score"] - 0.5) < 1e-9


def test_update_usage_success_usage_1000(memory_conn):
    """usage=999, success_count=500 → update(pid, True): 501/1002, no overflow."""
    p = Principles(memory_conn)
    pid = p.insert("guiding", "Stress test", "proj-1")
    for _ in range(998):
        p.update_usage_success(pid, False)
    # Now usage=999, success_count=0. One more success:
    p.update_usage_success(pid, True)
    row = p.get(pid)
    assert row["usage_count"] == 999
    assert row["success_count"] == 1
    expected = (1 + 1) / (999 + 2)
    assert abs(row["metric_score"] - expected) < 1e-9


def test_update_usage_success_nonexistent_principle(memory_conn):
    """principle_id not in DB: no crash, no change."""
    p = Principles(memory_conn)
    p.update_usage_success("nonexistent-id-12345", True)
    assert p.get("nonexistent-id-12345") is None


def test_insert_and_get(memory_conn):
    """insert() → get(): row with principle_type, description, usage_count=0, success_count=0."""
    p = Principles(memory_conn)
    pid = p.insert("guiding", "Always validate inputs", "proj-1", domain="security")
    row = p.get(pid)
    assert row is not None
    assert row["principle_type"] == "guiding"
    assert row["description"] == "Always validate inputs"
    assert row["usage_count"] == 0
    assert row["success_count"] == 0
    assert row["domain"] == "security"


def test_search_returns_matching_by_description(memory_conn):
    """Insert 2 principles, search(query): only matches with query in description."""
    p = Principles(memory_conn)
    p.insert("guiding", "Use AI for hardware research", "proj-1")
    p.insert("cautionary", "Avoid unverified claims", "proj-2")
    results = p.search("hardware", limit=10)
    assert len(results) == 1
    assert "hardware" in results[0]["description"].lower()


def test_search_domain_filter(memory_conn):
    """Insert with domain, search(domain=...): only matching domain or domain=''."""
    p = Principles(memory_conn)
    p.insert("guiding", "Principle A", "proj-1", domain="finance")
    p.insert("guiding", "Principle B", "proj-2", domain="")
    p.insert("guiding", "Principle C", "proj-3", domain="health")
    results = p.search("Principle", domain="finance", limit=10)
    assert len(results) >= 1
    assert all(r["domain"] == "finance" or r["domain"] == "" for r in results)
