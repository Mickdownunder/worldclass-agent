"""Unit tests for lib/brain.py pure helpers — _reflection_is_low_signal, _compact_state_for_think."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.brain import (
    _reflection_is_low_signal,
    _compact_state_for_think,
)


def test_reflection_is_low_signal_empty_outcome_returns_true():
    """Empty outcome → True (low signal)."""
    assert _reflection_is_low_signal("", "some learnings", 0.8) is True


def test_reflection_is_low_signal_failure_keyword_returns_false():
    """Outcome containing 'fail' or 'error' → False (never low signal)."""
    assert _reflection_is_low_signal("job failed", "x", 0.5) is False
    assert _reflection_is_low_signal("error during run", "x", 0.3) is False
    assert _reflection_is_low_signal("timeout after 30s", "", 0.2) is False


def test_reflection_is_low_signal_generic_outcome_short_learnings_returns_true():
    """'job completed successfully' + short learnings → True."""
    assert _reflection_is_low_signal("job completed successfully", "ok", 0.7) is True


def test_reflection_is_low_signal_generic_outcome_long_learnings_returns_false():
    """'completed successfully' but long learnings → False."""
    assert _reflection_is_low_signal(
        "job completed successfully",
        "Detailed takeaway that is longer than twenty five characters here",
        0.7,
    ) is False


def test_reflection_is_low_signal_medium_quality_short_learnings_returns_true():
    """Quality in [0.4, 0.85] and learnings < 15 chars → True."""
    assert _reflection_is_low_signal("something happened", "short", 0.6) is True


def test_reflection_is_low_signal_quality_in_range_short_learnings_returns_true():
    """Quality in [0.4, 0.85] and learnings < 15 → True (doc: medium quality but no real takeaway)."""
    assert _reflection_is_low_signal("outcome", "x", 0.5) is True


def test_compact_state_for_think_under_limit_returns_unchanged():
    """State serialized under limit → full payload."""
    state = {"system": {"a": 1}, "governance": {}}
    out = _compact_state_for_think(state, limit=5000)
    assert "system" in out
    assert "a" in out
    assert "(truncated)" not in out


def test_compact_state_for_think_over_limit_truncates():
    """State over limit → truncated with suffix."""
    state = {"system": {"x": "y" * 20000}}
    out = _compact_state_for_think(state, limit=100)
    assert len(out) <= 120
    assert "... (truncated)" in out


def test_compact_state_for_think_priority_keys_included():
    """Priority keys (memory, recent_jobs, research_projects) are in serialized state."""
    state = {
        "system": {},
        "governance": {},
        "memory": {"totals": {"episodes": 1}, "recent_reflections": [{}]},
        "recent_jobs": [{"id": "j1"}],
        "research_projects": [{"id": "p1"}],
    }
    out = _compact_state_for_think(state, limit=5000)
    assert "episodes" in out
    assert "j1" in out
    assert "p1" in out
