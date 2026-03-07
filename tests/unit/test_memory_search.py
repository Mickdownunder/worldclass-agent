"""Unit tests for lib/memory/search.py — search_episodes, search_reflections."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.schema import init_schema
from lib.memory.common import utcnow
from lib.memory.search import search_episodes, search_reflections


def _add_episode(conn, eid: str, content: str, ts: str | None = None):
    conn.execute(
        "INSERT INTO episodes (id, ts, kind, content, metadata) VALUES (?, ?, ?, ?, ?)",
        (eid, ts or utcnow(), "test", content, "{}"),
    )
    conn.commit()


def _add_reflection(conn, rid: str, outcome: str, learnings: str = "", quality: float = 0.5, went_well: str = "", went_wrong: str = "", ts: str | None = None):
    conn.execute(
        """INSERT INTO reflections (id, ts, job_id, outcome, learnings, quality, went_well, went_wrong, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rid, ts or utcnow(), "job-" + rid, outcome, learnings, quality, went_well, went_wrong, "{}"),
    )
    conn.commit()


def test_search_episodes_empty_db_returns_empty_list(memory_conn):
    """search_episodes on empty DB returns []."""
    result = search_episodes(memory_conn, "foo", limit=10)
    assert result == []


def test_search_episodes_no_match_returns_empty(memory_conn):
    """One episode with content that does not match query returns []."""
    _add_episode(memory_conn, "e1", "only bananas and apples")
    result = search_episodes(memory_conn, "docker kubernetes", limit=10)
    assert result == []


def test_search_episodes_match_returns_results_with_similarity(memory_conn):
    """Episodes matching query terms return with similarity_score."""
    _add_episode(memory_conn, "e1", "docker containers and kubernetes cluster")
    _add_episode(memory_conn, "e2", "something unrelated")
    result = search_episodes(memory_conn, "docker kubernetes", limit=10)
    assert len(result) >= 1
    assert any("docker" in (r.get("content") or "").lower() for r in result)
    for r in result:
        assert "similarity_score" in r
        assert isinstance(r["similarity_score"], (int, float))


def test_search_episodes_respects_limit(memory_conn):
    """search_episodes(limit=2) returns at most 2 rows."""
    for i in range(5):
        _add_episode(memory_conn, f"e{i}", "docker and kubernetes")
    result = search_episodes(memory_conn, "docker", limit=2)
    assert len(result) <= 2


def test_search_episodes_empty_query_returns_all_with_score(memory_conn):
    """Empty query: all episodes returned with similarity_score 0.5 (keyword fallback)."""
    _add_episode(memory_conn, "e1", "hello world")
    result = search_episodes(memory_conn, "", limit=10)
    assert len(result) == 1
    assert result[0].get("similarity_score") == 0.5


def test_search_reflections_empty_db_returns_empty_list(memory_conn):
    """search_reflections on empty DB returns []."""
    result = search_reflections(memory_conn, "foo", limit=10)
    assert result == []


def test_search_reflections_match_learnings_and_outcome(memory_conn):
    """Reflections with matching outcome/learnings returned with similarity_score."""
    _add_reflection(memory_conn, "r1", outcome="deployment succeeded", learnings="docker best practices")
    result = search_reflections(memory_conn, "docker deployment", limit=10)
    assert len(result) >= 1
    for r in result:
        assert "similarity_score" in r


def test_search_reflections_respects_limit(memory_conn):
    """search_reflections(limit=1) returns at most 1 row."""
    _add_reflection(memory_conn, "r1", "docker", "docker")
    _add_reflection(memory_conn, "r2", "docker", "docker")
    result = search_reflections(memory_conn, "docker", limit=1)
    assert len(result) <= 1


def test_search_reflections_empty_query_returns_all_with_score(memory_conn):
    """Empty query: reflections returned with similarity_score 0.5."""
    _add_reflection(memory_conn, "r1", "ok", "learned")
    result = search_reflections(memory_conn, "", limit=10)
    assert len(result) == 1
    assert result[0].get("similarity_score") == 0.5
