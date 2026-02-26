"""Shared pytest fixtures: temp project layout, OPERATOR_ROOT, env."""
import os
import json
import pytest
from pathlib import Path


@pytest.fixture
def mock_operator_root(tmp_path):
    """Set OPERATOR_ROOT to a temp directory; restore after test."""
    root = tmp_path / "operator_root"
    root.mkdir()
    (root / "research").mkdir()
    (root / "conf").mkdir()
    orig = os.environ.get("OPERATOR_ROOT")
    os.environ["OPERATOR_ROOT"] = str(root)
    try:
        yield root
    finally:
        if orig is not None:
            os.environ["OPERATOR_ROOT"] = orig
        elif "OPERATOR_ROOT" in os.environ:
            del os.environ["OPERATOR_ROOT"]


@pytest.fixture
def tmp_project(mock_operator_root, tmp_path):
    """A temp research project under mock_operator_root with project.json and dirs."""
    root = mock_operator_root
    research = root / "research"
    pid = "test-proj"
    proj = research / pid
    proj.mkdir(parents=True)
    (proj / "findings").mkdir()
    (proj / "sources").mkdir()
    (proj / "reports").mkdir()
    (proj / "verify").mkdir()
    (proj / "explore").mkdir()
    project_json = {
        "id": pid,
        "question": "Test question?",
        "phase": "explore",
        "status": "running",
    }
    (proj / "project.json").write_text(json.dumps(project_json, indent=2) + "\n")
    return proj


@pytest.fixture
def mock_env(monkeypatch):
    """Minimal env for tests that need RESEARCH_* or API keys (no real keys)."""
    monkeypatch.setenv("RESEARCH_PROJECT_ID", "test-proj", prepend=False)
    # Optional: monkeypatch.setenv("OPENAI_API_KEY", "sk-test") to avoid missing-key errors in code paths that only check presence
