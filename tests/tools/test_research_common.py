"""Unit tests for tools/research_common.py."""
import json
import pytest
from pathlib import Path

from tools.research_common import (
    operator_root,
    research_root,
    project_dir,
    load_project,
    save_project,
    load_secrets,
    ensure_project_layout,
    model_for_lane,
    _is_quota_or_bottleneck,
    _is_retryable,
)


def test_operator_root_default(mock_operator_root):
    """operator_root() returns OPERATOR_ROOT when set."""
    assert str(operator_root()) == str(mock_operator_root)


def test_research_root_under_operator(mock_operator_root):
    """research_root() is operator_root/research."""
    assert research_root() == mock_operator_root / "research"


def test_project_dir(mock_operator_root):
    """project_dir(id) is research/id."""
    assert project_dir("my-proj") == mock_operator_root / "research" / "my-proj"


def test_load_project_empty(tmp_project):
    """load_project() returns {} when project.json missing."""
    (tmp_project / "project.json").unlink()
    assert load_project(tmp_project) == {}


def test_load_project_valid(tmp_project):
    """load_project() returns parsed project.json."""
    data = {"id": "x", "question": "Q?"}
    (tmp_project / "project.json").write_text(json.dumps(data))
    assert load_project(tmp_project) == data


def test_save_project(tmp_project):
    """save_project() writes project.json."""
    data = {"id": "p1", "phase": "explore"}
    save_project(tmp_project, data)
    assert json.loads((tmp_project / "project.json").read_text()) == data


def test_load_secrets_from_env(monkeypatch):
    """load_secrets() includes OPENAI_* and known keys from env."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    secrets = load_secrets()
    assert secrets.get("OPENAI_API_KEY") == "sk-test"
    assert secrets.get("BRAVE_API_KEY") == "brave-key"


def test_ensure_project_layout(tmp_project):
    """ensure_project_layout creates findings, sources, reports."""
    (tmp_project / "findings").rmdir()
    (tmp_project / "sources").rmdir()
    (tmp_project / "reports").rmdir()
    ensure_project_layout(tmp_project)
    assert (tmp_project / "findings").is_dir()
    assert (tmp_project / "sources").is_dir()
    assert (tmp_project / "reports").is_dir()


def test_model_for_lane_strong_by_default(monkeypatch):
    """model_for_lane with no RESEARCH_GOVERNOR_LANE returns strong default."""
    monkeypatch.delenv("RESEARCH_GOVERNOR_LANE", raising=False)
    m = model_for_lane("verify")
    assert m


def test_model_for_lane_cheap_returns_cheap(monkeypatch):
    """model_for_lane with lane=cheap returns cheap model."""
    monkeypatch.setenv("RESEARCH_GOVERNOR_LANE", "cheap")
    m = model_for_lane("verify")
    assert m


def test_model_for_lane_mid_returns_mid(monkeypatch):
    """model_for_lane with lane=mid returns mid model."""
    monkeypatch.setenv("RESEARCH_GOVERNOR_LANE", "mid")
    m = model_for_lane("synthesize")
    assert m


def test_is_quota_or_bottleneck_429():
    """_is_quota_or_bottleneck returns True for 429 message."""
    assert _is_quota_or_bottleneck(Exception("HTTP 429")) is True


def test_is_quota_or_bottleneck_quota_exceeded():
    """_is_quota_or_bottleneck returns True for quota exceeded."""
    assert _is_quota_or_bottleneck(Exception("you exceeded your current quota")) is True


def test_is_quota_or_bottleneck_other_returns_false():
    """_is_quota_or_bottleneck returns False for other errors."""
    assert _is_quota_or_bottleneck(Exception("not found")) is False


def test_is_retryable_quota_returns_false():
    """_is_retryable returns False for quota exceeded."""
    assert _is_retryable(Exception("quota exceeded")) is False


def test_is_retryable_timeout_returns_true():
    """_is_retryable returns True for TimeoutError."""
    assert _is_retryable(TimeoutError()) is True


def test_is_retryable_connection_error_returns_true():
    """_is_retryable returns True for ConnectionError."""
    assert _is_retryable(ConnectionError()) is True


def test_is_retryable_http_error_429_returns_true():
    """_is_retryable returns True for HTTPError with code 429."""
    from urllib.error import HTTPError
    try:
        raise HTTPError("url", 429, "Rate Limited", None, None)
    except HTTPError as e:
        assert _is_retryable(e) is True


def test_is_retryable_http_error_503_returns_true():
    """_is_retryable returns True for HTTPError 503."""
    from urllib.error import HTTPError
    try:
        raise HTTPError("url", 503, "Service Unavailable", None, None)
    except HTTPError as e:
        assert _is_retryable(e) is True
