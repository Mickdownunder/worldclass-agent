"""
Tests for trigger_council: Discovery-only policy (trigger only when status=done).
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PROJECT_ID = "proj-discovery-fail"


@pytest.fixture
def research_root(tmp_path):
    (tmp_path / PROJECT_ID).mkdir(parents=True)
    return tmp_path


def test_discovery_parent_not_done_skips_trigger(research_root):
    """Discovery parent with status failed_quality_gate must not trigger council."""
    proj_dir = research_root / PROJECT_ID
    (proj_dir / "project.json").write_text(json.dumps({
        "config": {"research_mode": "discovery"},
        "status": "failed_quality_gate",
        "phase": "failed",
    }, indent=2))
    with patch("tools.trigger_council.RESEARCH", research_root):
        with patch("tools.trigger_council.OPERATOR_ROOT", Path(__file__).resolve().parent.parent.parent):
            with patch.object(sys, "argv", ["trigger_council.py", PROJECT_ID]):
                from tools.trigger_council import main
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 0


def test_get_mode_discovery():
    """get_mode returns 'discovery' for config.research_mode discovery."""
    from tools.trigger_council import get_mode
    assert get_mode({"config": {"research_mode": "discovery"}}) == "discovery"
    assert get_mode({"config": {"research_mode": "standard"}}) == "standard"
