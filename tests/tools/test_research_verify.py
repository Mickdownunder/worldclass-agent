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


def test_build_claim_ledger_fact_check_disputed(tmp_project):
    """Phase 1: fact_check disputed fact matching claim (Jaccard >= 0.4) -> dispute -> UNVERIFIED."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_verification.json").write_text(json.dumps({
        "claims": [{
            "claim": "The vaccine efficacy rate was 95 percent in trials",
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
    # Disputed fact with overlapping words (vaccine, efficacy, rate, trials)
    (tmp_project / "verify" / "fact_check.json").write_text(json.dumps({
        "facts": [{
            "statement": "Vaccine efficacy rate in trials was 95 percent",
            "verification_status": "disputed",
            "source": "multiple",
        }]
    }))
    result = build_claim_ledger(tmp_project, {})
    assert len(result["claims"]) == 1
    assert result["claims"][0]["verification_tier"] == "UNVERIFIED"
    assert result["claims"][0]["is_verified"] is False
    assert "disputed" in result["claims"][0].get("verification_reason", "").lower()


def test_build_claim_ledger_cove_overlay_force_unverified(tmp_project):
    """Phase 3: cove_overlay cove_supports False -> force UNVERIFIED."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_verification.json").write_text(json.dumps({
        "claims": [{
            "claim": "Claim that would be verified by sources",
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
    (tmp_project / "verify" / "cove_overlay.json").write_text(json.dumps({
        "claims": [{"claim_text_prefix": "Claim that would be verified by sources", "cove_supports": False}]
    }))
    result = build_claim_ledger(tmp_project, {})
    assert len(result["claims"]) == 1
    assert result["claims"][0]["verification_tier"] == "UNVERIFIED"
    assert result["claims"][0]["is_verified"] is False
    assert "CoVe" in result["claims"][0].get("verification_reason", "")


def test_build_claim_ledger_supporting_evidence_and_credibility(tmp_project):
    """Phase 1/2: ledger has supporting_evidence (snippets) and credibility_weight."""
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "findings" / "f1.json").write_text(json.dumps({
        "url": "https://a.com", "finding_id": "f1", "excerpt": "Relevant excerpt for claim.",
        "title": "Source A",
    }))
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_verification.json").write_text(json.dumps({
        "claims": [{"claim": "Fact X", "supporting_sources": ["https://a.com"]}]
    }))
    (tmp_project / "verify" / "source_reliability.json").write_text(json.dumps({
        "sources": [{"url": "https://a.com", "reliability_score": 0.75}]
    }))
    result = build_claim_ledger(tmp_project, {})
    assert len(result["claims"]) == 1
    c = result["claims"][0]
    assert "supporting_evidence" in c
    assert isinstance(c["supporting_evidence"], list)
    if c["supporting_evidence"]:
        assert "url" in c["supporting_evidence"][0]
        assert "snippet" in c["supporting_evidence"][0]
    assert "credibility_weight" in c
    assert 0 <= c["credibility_weight"] <= 1
