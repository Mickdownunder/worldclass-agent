"""Unit tests for tools/research_progress.py finalize behavior."""
import json

from tools import research_progress as rp


def test_done_preserves_non_terminal_phase_when_provided(tmp_project):
    """done(..., final_phase='explore') should set alive=false without forcing phase=done."""
    project_id = tmp_project.name
    rp.start(project_id, "explore")
    rp.step(project_id, "Reading sources")
    rp.done(project_id, final_phase="explore", final_step="Idle")
    progress = json.loads((tmp_project / "progress.json").read_text())
    assert progress["alive"] is False
    assert progress["phase"] == "explore"
    assert progress["step"] == "Idle"
    assert progress.get("active_steps") == []


def test_done_marks_terminal_done_when_phase_is_explicit(tmp_project):
    """done(..., final_phase='done') uses terminal Done marker."""
    project_id = tmp_project.name
    rp.start(project_id, "synthesize")
    rp.done(project_id, final_phase="done")
    progress = json.loads((tmp_project / "progress.json").read_text())
    assert progress["alive"] is False
    assert progress["phase"] == "done"
    assert progress["step"] == "Done"
