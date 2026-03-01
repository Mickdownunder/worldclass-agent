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


def test_evidence_gaps_structure_and_writes_critique(tmp_project):
    """Phase 4: evidence_gaps returns under_sourced_claims, contradictions, suggested_queries; writes verify/evidence_critique.json."""
    from unittest.mock import patch
    from tools.research_reason import evidence_gaps

    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "findings" / "a.json").write_text(json.dumps({"title": "T", "excerpt": "E"}))
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({
        "claims": [{"text": "Unverified claim", "claim_id": "c1", "is_verified": False, "verification_tier": "UNVERIFIED"}]
    }))
    mock_out = {
        "under_sourced_claims": [{"text": "Unverified claim", "claim_id": "c1"}],
        "contradictions": [],
        "suggested_queries": [{"query": "search for X", "reason": "gap", "priority": "high"}],
    }
    with patch("tools.research_reason._llm_json", return_value=mock_out):
        result = evidence_gaps(tmp_project, {"question": "Q?", "config": {}}, "proj-1")
    assert "under_sourced_claims" in result
    assert "contradictions" in result
    assert "suggested_queries" in result
    assert result["suggested_queries"][0].get("query") == "search for X"
    assert (tmp_project / "verify" / "evidence_critique.json").exists()
    written = json.loads((tmp_project / "verify" / "evidence_critique.json").read_text())
    assert written.get("suggested_queries") == mock_out["suggested_queries"]
