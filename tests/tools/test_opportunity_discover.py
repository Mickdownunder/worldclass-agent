"""Unit tests for tools/opportunity_discover.py."""
import pytest

from tools.opportunity_discover import sha_id, fetch_json, fetch_hn_stories


def test_sha_id_format():
    """sha_id returns opp_ prefix and hex string."""
    out = sha_id("hello")
    assert out.startswith("opp_")
    assert len(out) == len("opp_") + 12
    assert all(c in "0123456789abcdef" for c in out[4:])


def test_sha_id_deterministic():
    """sha_id is deterministic for same input."""
    assert sha_id("x") == sha_id("x")


def test_fetch_json_invalid_url():
    """fetch_json returns None on invalid or unreachable URL."""
    result = fetch_json("http://127.0.0.1:1/")
    assert result is None


def test_fetch_hn_stories_mock_empty(monkeypatch):
    """fetch_hn_stories returns [] when API returns empty."""
    def mock_fetch(url):
        return [] if "stories" in url else None
    monkeypatch.setattr("tools.opportunity_discover.fetch_json", mock_fetch)
    assert fetch_hn_stories("top", limit=5) == []
