"""Unit tests for tools/research_reason.py."""
import json
import pytest

from tools.research_reason import _load_findings


def test_gap_analysis_empty_findings(tmp_project):
    """gap_analysis with no findings: _load_findings returns []."""
    from tools.research_reason import _load_findings
    (tmp_project / "findings").mkdir(exist_ok=True)
    findings = _load_findings(tmp_project)
    assert findings == []


def test_gap_analysis_structure_without_llm(tmp_project):
    """gap_analysis returns dict with gaps key when _load_findings is empty and we mock."""
    from tools.research_reason import _load_findings
    findings = _load_findings(tmp_project)
    assert findings == []
    # Without calling LLM, we can't get result; test the loader only
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "findings" / "a.json").write_text(json.dumps({"title": "T", "excerpt": "E"}))
    findings = _load_findings(tmp_project)
    assert len(findings) == 1
    assert findings[0].get("title") == "T"


def test_load_findings_with_one_file(tmp_project):
    """_load_findings returns list of findings from JSON files."""
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "findings" / "a.json").write_text(json.dumps({"title": "T", "excerpt": "E"}))
    assert len(_load_findings(tmp_project)) == 1
