"""Unit tests for tools/research_abort_report.py."""
import json
import pytest

from tools.research_abort_report import generate_abort_report


def test_generate_abort_report_no_project(mock_operator_root):
    """generate_abort_report() returns empty string when project does not exist."""
    out = generate_abort_report("nonexistent-id-xyz")
    assert out == ""


def test_generate_abort_report_creates_content(tmp_project):
    """generate_abort_report() returns non-empty markdown for existing project."""
    from tools.research_common import save_project
    save_project(tmp_project, {
        "id": tmp_project.name,
        "question": "Test?",
        "status": "failed_reader_pipeline",
        "phase": "explore",
    })
    out = generate_abort_report(tmp_project.name)
    assert isinstance(out, str)
    assert "Test?" in out or "Abort" in out or "report" in out.lower() or "failed" in out.lower()


def test_generate_abort_report_contains_question(tmp_project):
    """generate_abort_report() return contains question and status info."""
    from tools.research_common import save_project
    save_project(tmp_project, {"id": tmp_project.name, "question": "Q?", "status": "failed", "phase": "explore"})
    out = generate_abort_report(tmp_project.name)
    assert "Q?" in out
    assert "failed" in out or "phase" in out.lower()
