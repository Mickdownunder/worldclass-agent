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
