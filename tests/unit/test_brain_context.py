"""Unit tests for lib/brain_context.py — query vs no-query path, strategic_principles."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from unittest.mock import MagicMock
import pytest
from lib.brain_context import compile


def test_compile_without_query_static_path_no_strategic_principles():
    """memory without retrieve_with_utility or query=None: result has NO key 'strategic_principles'."""
    memory = MagicMock()
    memory.get_research_findings_accepted.return_value = []
    memory.recent_reflections.return_value = []
    result = compile(memory, query=None)
    assert "strategic_principles" not in result
    assert "accepted_findings_by_project" in result
    assert "totals" in result


def test_compile_with_query_uses_utility_path():
    """memory with retrieve_with_utility; compile(memory, query='AI hardware'): key 'strategic_principles' present."""
    memory = MagicMock()
    memory.retrieve_with_utility = MagicMock(return_value=[])
    memory.retrieve_with_utility.side_effect = lambda q, t, k: (
        [] if t == "reflection" else ([] if t == "finding" else [])
    )
    result = compile(memory, query="AI hardware")
    assert "strategic_principles" in result
    assert result["strategic_principles"] == []
    assert "totals" in result
    assert "principles_count" in result["totals"]


def test_compile_with_query_findings_by_project():
    """query set, retrieve_with_utility returns findings: accepted_findings_by_project grouped by project_id."""
    memory = MagicMock()
    def retrieve(q, memory_type, k):
        if memory_type == "finding":
            return [
                {"id": "f1", "project_id": "p1", "finding_key": "k1", "content_preview": "x", "url": None},
                {"id": "f2", "project_id": "p1", "finding_key": "k2", "content_preview": "y", "url": None},
            ]
        return []
    memory.retrieve_with_utility = retrieve
    result = compile(memory, query="x", max_findings_per_project=5, max_projects=10)
    assert "p1" in result["accepted_findings_by_project"]
    assert len(result["accepted_findings_by_project"]["p1"]) == 2
    assert result["totals"]["accepted_findings"] == 2


def test_compile_memory_without_retrieve_with_utility_fallback():
    """Fake memory only get_research_findings_accepted, recent_reflections (no retrieve_with_utility): no crash, static path."""
    class StaticMemory:
        def get_research_findings_accepted(self, project_id=None, limit=200):
            return []
        def recent_reflections(self, limit=20, min_quality=None):
            return []
    memory = StaticMemory()
    result = compile(memory, query="something")
    assert "strategic_principles" not in result
    assert "accepted_findings_by_project" in result


def test_compile_totals_populated():
    """query set, non-empty results: totals.accepted_projects, principles_count set."""
    memory = MagicMock()
    memory.retrieve_with_utility = lambda q, t, k: (
        [{"id": "r1", "job_id": "j1", "quality": 0.8, "learnings": "x"}] if t == "reflection" else
        [{"id": "p1", "description": "d", "principle_type": "guiding", "metric_score": 0.7}] if t == "principle" else
        []
    )
    result = compile(memory, query="x")
    assert result["totals"]["principles_count"] == 1
    assert result["totals"]["reflections_above_threshold"] == 1
