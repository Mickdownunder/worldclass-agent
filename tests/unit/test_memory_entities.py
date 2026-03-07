"""Unit tests for lib/memory/entities.py — get_or_create, insert_relation, insert_mention, get, get_relations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.entities import Entities


def test_entities_get_or_create_creates_new(memory_conn):
    """get_or_create(name, type) for new entity returns id."""
    e = Entities(memory_conn)
    eid = e.get_or_create("Alice", "person")
    assert eid


def test_entities_get_or_create_same_returns_same_id(memory_conn):
    """get_or_create same name+type twice returns same id."""
    e = Entities(memory_conn)
    id1 = e.get_or_create("Bob", "person")
    id2 = e.get_or_create("Bob", "person")
    assert id1 == id2


def test_entities_get_or_create_empty_name_raises(memory_conn):
    """get_or_create('', type) raises ValueError."""
    with pytest.raises(ValueError, match="name required"):
        Entities(memory_conn).get_or_create("", "person")


def test_entities_insert_relation_returns_id(memory_conn):
    """insert_relation(a_id, b_id, type, project) returns id."""
    e = Entities(memory_conn)
    a = e.get_or_create("A", "concept")
    b = e.get_or_create("B", "concept")
    rid = e.insert_relation(a, b, "related_to", "proj1")
    assert rid


def test_entities_insert_mention_returns_id(memory_conn):
    """insert_mention(entity_id, project_id) returns id."""
    e = Entities(memory_conn)
    eid = e.get_or_create("X", "org")
    mid = e.insert_mention(eid, "proj1", finding_key="f1")
    assert mid


def test_entities_get_by_type_returns_created(memory_conn):
    """get(entity_type='person') returns entities of that type."""
    ent = Entities(memory_conn)
    ent.get_or_create("P1", "person")
    ent.get_or_create("C1", "concept")
    rows = ent.get(entity_type="person", limit=10)
    assert len(rows) >= 1
    assert all(r["type"] == "person" for r in rows)


def test_entities_get_relations_empty_returns_empty(memory_conn):
    """get_relations() on empty returns []."""
    assert Entities(memory_conn).get_relations(limit=10) == []
