"""Unit tests for lib/memory/schema.py — init_schema, migrations."""
import pytest

from lib.memory.schema import init_schema, migrate_research_findings_quality

EXPECTED_TABLES = [
    "episodes", "decisions", "reflections", "playbooks", "quality_scores",
    "research_findings", "memory_admission_events", "cross_links",
    "entities", "entity_relations", "entity_mentions",
    "strategic_principles", "memory_utility", "project_outcomes", "source_credibility",
]


def test_init_schema_creates_all_tables(memory_conn):
    """init_schema(conn) on fresh DB: all 15 tables present."""
    for name in EXPECTED_TABLES:
        row = memory_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        assert row is not None, f"Table {name} missing"


def test_init_schema_idempotent(memory_conn):
    """init_schema(conn) twice: no error, same structure."""
    init_schema(memory_conn)
    for name in EXPECTED_TABLES:
        row = memory_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        assert row is not None


def test_migrate_research_findings_quality_adds_columns(memory_conn):
    """After init_schema, research_findings has quality columns from migration."""
    cur = memory_conn.execute("PRAGMA table_info(research_findings)")
    cols = {row[1] for row in cur.fetchall()}
    for name in ["relevance_score", "reliability_score", "verification_status", "evidence_count", "critic_score", "importance_score", "admission_state"]:
        assert name in cols, f"Column {name} missing"


def test_migrate_on_existing_db_no_crash(memory_conn):
    """DB with tables already; init_schema(conn) again: no crash, migration runs."""
    init_schema(memory_conn)
    init_schema(memory_conn)
