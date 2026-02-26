"""Unit tests for tools/research_advance_phase.py."""
import json
import pytest
from pathlib import Path

from tools.research_advance_phase import advance


def test_advance_explore_to_focus(tmp_project):
    """advance() updates phase from explore to focus."""
    (tmp_project / "project.json").write_text(json.dumps({
        "id": tmp_project.name,
        "phase": "explore",
        "status": "running",
    }, indent=2))
    advance(tmp_project, "focus")
    d = json.loads((tmp_project / "project.json").read_text())
    assert d["phase"] == "focus"
    assert "focus" in d.get("phase_history", [])


def test_advance_to_done_sets_status(tmp_project):
    """advance() to done sets status and completed_at."""
    (tmp_project / "project.json").write_text(json.dumps({
        "id": tmp_project.name,
        "phase": "synthesize",
        "status": "running",
    }, indent=2))
    advance(tmp_project, "done")
    d = json.loads((tmp_project / "project.json").read_text())
    assert d["phase"] == "done"
    assert d["status"] == "done"
    assert "completed_at" in d


def test_advance_records_phase_timings(tmp_project):
    """advance() records phase_timings when phase changes."""
    (tmp_project / "project.json").write_text(json.dumps({
        "id": tmp_project.name,
        "phase": "explore",
        "last_phase_at": "2025-01-01T12:00:00Z",
        "status": "running",
    }, indent=2))
    advance(tmp_project, "focus")
    d = json.loads((tmp_project / "project.json").read_text())
    assert "phase_timings" in d
    assert "explore" in d["phase_timings"]
