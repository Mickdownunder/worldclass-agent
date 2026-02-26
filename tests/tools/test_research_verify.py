"""Unit tests for tools/research_verify.py."""
import json
import pytest

from tools.research_verify import build_claim_ledger, apply_verified_tags_to_report


def test_build_claim_ledger_zero_claims(tmp_project):
    """build_claim_ledger() with no claim_verification returns empty claims."""
    result = build_claim_ledger(tmp_project, {"id": tmp_project.name})
    assert result["claims"] == []


def test_build_claim_ledger_missing_files(tmp_project):
    """build_claim_ledger() with missing verify dir still returns structure."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    result = build_claim_ledger(tmp_project, {"id": tmp_project.name})
    assert "claims" in result
    assert result["claims"] == []


def test_build_claim_ledger_two_sources_verified(tmp_project):
    """build_claim_ledger() marks verified when >=2 reliable sources."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_verification.json").write_text(json.dumps({
        "claims": [{
            "claim": "Fact X",
            "supporting_sources": ["https://a.com", "https://b.com"],
            "verified": True,
        }]
    }))
    (tmp_project / "verify" / "source_reliability.json").write_text(json.dumps({
        "sources": [
            {"url": "https://a.com", "reliability_score": 0.8},
            {"url": "https://b.com", "reliability_score": 0.7},
        ]
    }))
    result = build_claim_ledger(tmp_project, {})
    assert len(result["claims"]) == 1
    assert result["claims"][0]["is_verified"] is True
    assert "reliable" in result["claims"][0].get("verification_reason", "").lower() or "source" in result["claims"][0].get("verification_reason", "").lower()


def test_build_claim_ledger_one_source_not_verified(tmp_project):
    """build_claim_ledger() marks not verified with only one source."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_verification.json").write_text(json.dumps({
        "claims": [{"claim": "Only one source.", "supporting_sources": ["https://one.com"]}]
    }))
    (tmp_project / "verify" / "source_reliability.json").write_text(json.dumps({
        "sources": [{"url": "https://one.com", "reliability_score": 0.9}]
    }))
    result = build_claim_ledger(tmp_project, {})
    assert len(result["claims"]) == 1
    assert result["claims"][0]["is_verified"] is False


def test_apply_verified_tags_strips_all_when_empty_ledger():
    """apply_verified_tags_to_report() strips [VERIFIED] when ledger empty."""
    report = "Claim A [VERIFIED]. Claim B [VERIFIED:xyz]."
    out = apply_verified_tags_to_report(report, [])
    assert "[VERIFIED]" not in out
    assert "Claim A" in out and "Claim B" in out


def test_apply_verified_tags_adds_only_for_verified():
    """apply_verified_tags_to_report() adds tag only for is_verified=True."""
    report = "Real claim here. Other text."
    claims = [
        {"claim_id": "c1", "text": "Real claim", "is_verified": True},
        {"claim_id": "c2", "text": "Other text", "is_verified": False},
    ]
    out = apply_verified_tags_to_report(report, claims)
    assert "Real claim" in out
    assert "[VERIFIED" in out
    # "Other text" should not get [VERIFIED]
    assert out.count("[VERIFIED") == 1
