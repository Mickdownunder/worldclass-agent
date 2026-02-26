"""Unit tests for tools/research_web_search.py."""
import json
import sys
from io import StringIO

import pytest


def test_search_brave_no_key_returns_empty(monkeypatch):
    """search_brave() returns [] when no API key."""
    monkeypatch.setattr("tools.research_web_search.load_secrets", lambda: {})
    from tools.research_web_search import search_brave
    result = search_brave("test query")
    assert result == []


def test_search_serper_no_key_returns_empty(monkeypatch):
    """search_serper() returns [] when no API key."""
    monkeypatch.setattr("tools.research_web_search.load_secrets", lambda: {})
    from tools.research_web_search import search_serper
    result = search_serper("test")
    assert result == []


def test_main_outputs_json_array_when_no_keys(monkeypatch):
    """main() with no API keys prints JSON array (empty) to stdout."""
    monkeypatch.setattr("tools.research_web_search.load_secrets", lambda: {})
    monkeypatch.setattr("sys.argv", ["research_web_search.py", "query"])
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    from tools.research_web_search import main
    main()
    data = json.loads(out.getvalue())
    assert isinstance(data, list)
    assert data == []
