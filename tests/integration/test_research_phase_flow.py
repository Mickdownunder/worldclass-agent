"""
E2E: Phase flow — advance_phase explore -> focus -> connect -> verify -> synthesize -> done.
No real LLM; only file/phase transitions.
"""
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_advance_phase import advance

ORDER = ["explore", "focus", "connect", "verify", "synthesize", "done"]


def test_phase_flow_explore_to_done(tmp_project):
    """advance through all phases ends at done with status=done."""
    (tmp_project / "project.json").write_text(
        json.dumps(
            {
                "id": tmp_project.name,
                "question": "E2E?",
                "phase": "explore",
                "status": "running",
            },
            indent=2,
        )
    )
    for next_phase in ORDER[1:]:  # focus, connect, verify, synthesize, done
        advance(tmp_project, next_phase)
    data = json.loads((tmp_project / "project.json").read_text())
    assert data["phase"] == "done"
    assert data["status"] == "done"
    assert "completed_at" in data
    assert "phase_history" in data
    assert "done" in data["phase_history"]


def test_phase_timings_recorded(tmp_project):
    """advance records phase_timings when phase changes."""
    (tmp_project / "project.json").write_text(
        json.dumps(
            {
                "id": tmp_project.name,
                "phase": "explore",
                "last_phase_at": "2026-01-01T12:00:00Z",
                "status": "running",
            },
            indent=2,
        )
    )
    advance(tmp_project, "focus")
    data = json.loads((tmp_project / "project.json").read_text())
    assert data["phase"] == "focus"
    assert "phase_timings" in data
    assert "explore" in data["phase_timings"]
