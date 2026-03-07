"""Unit tests for lib/memory/research_findings.py — insert, get_accepted, record_admission_event, search, cross_links."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.research_findings import ResearchFindings


def test_research_findings_insert_returns_id(memory_conn):
    """insert(project_id, finding_key, content_preview) returns id."""
    rf = ResearchFindings(memory_conn)
    fid = rf.insert("p1", "key1", "preview text")
    assert fid


def test_research_findings_insert_defaults_admission_state_quarantined(memory_conn):
    """insert without admission_state uses 'quarantined'."""
    rf = ResearchFindings(memory_conn)
    rf.insert("p1", "k1", "x", admission_state=None)
    rows = rf.get_accepted(project_id="p1", limit=10)
    assert len(rows) == 0


def test_research_findings_get_accepted_filters_by_state(memory_conn):
    """insert with admission_state='accepted'; get_accepted returns it."""
    rf = ResearchFindings(memory_conn)
    rf.insert("p1", "k1", "preview", admission_state="accepted")
    rows = rf.get_accepted(project_id="p1", limit=10)
    assert len(rows) == 1
    assert rows[0]["finding_key"] == "k1"


def test_research_findings_get_accepted_all_projects_when_project_id_none(memory_conn):
    """get_accepted(project_id=None) returns accepted from any project."""
    rf = ResearchFindings(memory_conn)
    rf.insert("pa", "ka", "a", admission_state="accepted")
    rf.insert("pb", "kb", "b", admission_state="accepted")
    rows = rf.get_accepted(project_id=None, limit=10)
    assert len(rows) >= 2


def test_research_findings_record_admission_event_returns_id(memory_conn):
    """record_admission_event(project_id, finding_key, decision) returns id."""
    rf = ResearchFindings(memory_conn)
    eid = rf.record_admission_event("p1", "k1", "accepted", reason="good")
    assert eid


def test_research_findings_get_with_embeddings_empty(memory_conn):
    """get_with_embeddings() with no rows with embedding returns []."""
    rf = ResearchFindings(memory_conn)
    rf.insert("p1", "k1", "x")  # no embedding_json
    assert rf.get_with_embeddings() == []


def test_research_findings_search_by_query_returns_matching(memory_conn):
    """search_by_query('preview') returns finding with that text."""
    rf = ResearchFindings(memory_conn)
    rf.insert("p1", "k1", "preview content here", admission_state="accepted")
    rows = rf.search_by_query("preview", limit=10)
    assert len(rows) >= 1
    assert "preview" in (rows[0].get("content_preview") or "").lower()


def test_research_findings_insert_cross_link_returns_id(memory_conn):
    """insert_cross_link(a_id, b_id, pa, pb, sim) returns id."""
    rf = ResearchFindings(memory_conn)
    a = rf.insert("pa", "ka", "a", admission_state="accepted")
    b = rf.insert("pb", "kb", "b", admission_state="accepted")
    lid = rf.insert_cross_link(a, b, "pa", "pb", 0.9)
    assert lid


def test_research_findings_get_cross_links_unnotified_returns_unnotified(memory_conn):
    """get_cross_links_unnotified returns links with notified=0."""
    rf = ResearchFindings(memory_conn)
    a = rf.insert("p1", "k1", "x", admission_state="accepted")
    b = rf.insert("p2", "k2", "y", admission_state="accepted")
    rf.insert_cross_link(a, b, "p1", "p2", 0.8)
    rows = rf.get_cross_links_unnotified(limit=10)
    assert len(rows) >= 1


def test_research_findings_mark_cross_links_notified(memory_conn):
    """mark_cross_links_notified(ids) then get_cross_links_unnotified excludes them."""
    rf = ResearchFindings(memory_conn)
    a = rf.insert("p1", "k1", "x", admission_state="accepted")
    b = rf.insert("p2", "k2", "y", admission_state="accepted")
    lid = rf.insert_cross_link(a, b, "p1", "p2", 0.8)
    rf.mark_cross_links_notified([lid])
    rows = rf.get_cross_links_unnotified(limit=10)
    ids = [r["id"] for r in rows]
    assert lid not in ids
