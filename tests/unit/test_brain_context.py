"""Unit tests for lib/brain_context.py — query vs no-query path, strategic_principles, _filter_low_signal_reflections."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from unittest.mock import MagicMock
import pytest
from lib.brain_context import compile, _filter_low_signal_reflections, MIN_REFLECTION_QUALITY


def test_compile_without_query_static_path_includes_strategic_principles():
    """memory without retrieve_with_utility or query=None: result has strategic_principles (may be empty)."""
    memory = MagicMock()
    memory.get_research_findings_accepted.return_value = []
    memory.recent_reflections_for_planning.return_value = []
    memory.list_principles.return_value = []
    result = compile(memory, query=None)
    assert "strategic_principles" in result
    assert "accepted_findings_by_project" in result
    assert "totals" in result


def test_compile_with_query_uses_utility_path():
    """memory with retrieve_with_utility; compile(memory, query='AI hardware'): key 'strategic_principles' present."""
    memory = MagicMock()
    memory.retrieve_with_utility = lambda q, t, k, context_key=None: (
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
    def retrieve(q, memory_type, k, context_key=None):
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
    """Fake memory only get_research_findings_accepted, recent_reflections_for_planning, list_principles (no retrieve_with_utility): no crash, static path."""
    class StaticMemory:
        def get_research_findings_accepted(self, project_id=None, limit=200):
            return []
        def recent_reflections_for_planning(self, limit=10, min_quality=0.5, exclude_low_signal=True, dedupe_outcome_prefix=80):
            return []
        def list_principles(self, limit=50, domain=None):
            return []
    memory = StaticMemory()
    result = compile(memory, query="something")
    assert "strategic_principles" in result
    assert "accepted_findings_by_project" in result


def test_compile_totals_populated():
    """query set, non-empty results: totals.accepted_projects, principles_count set."""
    def retrieve(q, memory_type, k, context_key=None):
        if memory_type == "reflection":
            return [{"id": "r1", "job_id": "j1", "quality": 0.8, "learnings": "x"}]
        if memory_type == "principle":
            return [{"id": "p1", "description": "d", "principle_type": "guiding", "metric_score": 0.7}]
        return []
    memory = MagicMock()
    memory.retrieve_with_utility = retrieve
    result = compile(memory, query="x")
    assert result["totals"]["principles_count"] == 1
    assert result["totals"]["reflections_above_threshold"] == 1


# --- _filter_low_signal_reflections ---


def test_filter_low_signal_drops_below_min_quality():
    """Reflections with quality < min_quality are excluded."""
    reflections = [
        {"id": "r1", "quality": 0.8, "metadata": "{}"},
        {"id": "r2", "quality": 0.3, "metadata": "{}"},
    ]
    out = _filter_low_signal_reflections(reflections, min_quality=MIN_REFLECTION_QUALITY)
    assert len(out) == 1
    assert out[0]["id"] == "r1"


def test_filter_low_signal_drops_low_signal_metadata():
    """Reflections with metadata.low_signal=True are excluded."""
    reflections = [
        {"id": "r1", "quality": 0.8, "metadata": "{}"},
        {"id": "r2", "quality": 0.8, "metadata": '{"low_signal": true}'},
    ]
    out = _filter_low_signal_reflections(reflections, min_quality=0.5)
    assert len(out) == 1
    assert out[0]["id"] == "r1"


def test_filter_low_signal_keeps_high_quality_no_metadata():
    """High quality, no metadata: kept."""
    reflections = [{"id": "r1", "quality": 0.7}]
    out = _filter_low_signal_reflections(reflections, min_quality=0.5)
    assert len(out) == 1


def test_filter_low_signal_none_quality_treated_as_zero():
    """quality=None treated as 0 and excluded when min_quality > 0."""
    reflections = [{"id": "r1", "quality": None}]
    out = _filter_low_signal_reflections(reflections, min_quality=0.5)
    assert len(out) == 0


def test_filter_low_signal_invalid_metadata_skipped():
    """metadata that is not valid JSON: treated as non-dict, no low_signal check; reflection kept if quality OK."""
    reflections = [
        {"id": "r1", "quality": 0.7, "metadata": "not valid json {"},
    ]
    out = _filter_low_signal_reflections(reflections, min_quality=0.5)
    assert len(out) == 1
    assert out[0]["id"] == "r1"
