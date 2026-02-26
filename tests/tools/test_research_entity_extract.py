"""Unit tests for tools/research_entity_extract.py."""
import pytest

from tools.research_entity_extract import extract_entities, extract_relations


def test_extract_entities_empty_text():
    """extract_entities returns [] for empty or whitespace-only text."""
    assert extract_entities("") == []
    assert extract_entities("   \n  ") == []


def test_extract_relations_empty_entities():
    """extract_relations returns [] when entities is empty."""
    assert extract_relations([], "Some text here.") == []


def test_extract_relations_empty_text():
    """extract_relations returns [] when text is empty."""
    assert extract_relations([{"name": "A", "type": "org"}], "") == []
