"""Unit tests for tools/opportunity_match_clients.py."""
import json
import pytest
from pathlib import Path

from tools.opportunity_match_clients import topic_fit, load_json, iter_jsonl


def test_topic_fit_overlap():
    """topic_fit returns True when opportunity and client share a topic."""
    assert topic_fit(["AI", "ML"], ["AI", "Cloud"], []) is True
    assert topic_fit(["ML"], ["AI"], []) is False


def test_topic_fit_exclude():
    """topic_fit returns False when opportunity topic is in exclude_topics."""
    assert topic_fit(["spam"], ["AI"], ["spam"]) is False


def test_topic_fit_empty():
    """topic_fit with empty opp_topics returns False."""
    assert topic_fit([], ["AI"], []) is False


def test_load_json(tmp_path):
    """load_json loads valid JSON file."""
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"id": "c1", "topics": ["AI"]}))
    assert load_json(str(f)) == {"id": "c1", "topics": ["AI"]}


def test_iter_jsonl(tmp_path):
    """iter_jsonl yields one dict per non-empty line."""
    f = tmp_path / "opp.jsonl"
    f.write_text('{"id": "1"}\n{"id": "2"}\n\n')
    items = list(iter_jsonl(str(f)))
    assert len(items) == 2
    assert items[0]["id"] == "1"
    assert items[1]["id"] == "2"
