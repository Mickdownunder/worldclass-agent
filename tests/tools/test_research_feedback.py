"""Unit tests for tools/research_feedback.py."""
import json
import pytest

from tools.research_feedback import VALID_TYPES


def test_valid_types_defined():
    """VALID_TYPES contains expected feedback types."""
    assert "dig_deeper" in VALID_TYPES
    assert "wrong" in VALID_TYPES
    assert "excellent" in VALID_TYPES
    assert "ignore" in VALID_TYPES
    assert "redirect" in VALID_TYPES
    assert len(VALID_TYPES) >= 5


def test_feedback_appends_jsonl(tmp_project):
    """Appending feedback writes valid JSONL line to feedback.jsonl."""
    from datetime import datetime, timezone
    feedback_file = tmp_project / "feedback.jsonl"
    feedback_file.write_text("")
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "excellent",
        "comment": "Great report",
        "source": "cli",
    }
    with open(feedback_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    lines = feedback_file.read_text().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["type"] == "excellent"
    assert parsed["comment"] == "Great report"
