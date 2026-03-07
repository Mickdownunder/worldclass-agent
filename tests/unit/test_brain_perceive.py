import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.brain.perceive import perceive_phase


class _DummyMemory:
    def all_playbooks(self):
        return []

    def state_summary(self):
        return {"recent_reflections": []}

    def record_episode(self, *_args, **_kwargs):
        return None

    def get_research_findings_accepted(self, project_id=None, limit=0):
        return []

    def recent_reflections_for_planning(self, limit=0, min_quality=0.0, exclude_low_signal=True, dedupe_outcome_prefix=80):
        return []

    def list_principles(self, limit=10):
        return []


def test_perceive_phase_surfaces_last_control_plane_event(mock_operator_root):
    log_file = mock_operator_root / "logs" / "control-plane-events.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        json.dumps({"event": "research_cycle_completed", "project_id": "proj-1", "status": "done", "event_scope": "control_plane"}) + "\n"
    )

    state = perceive_phase(_DummyMemory(), governance_level=2)

    assert state["last_control_plane_event"]["event"] == "research_cycle_completed"
    assert state["last_control_plane_event"]["project_id"] == "proj-1"


def test_perceive_phase_ignores_missing_control_plane_log(mock_operator_root):
    state = perceive_phase(_DummyMemory(), governance_level=2)

    assert "last_control_plane_event" not in state
    assert state["governance"]["level"] == 2
    assert "research_projects" in state
