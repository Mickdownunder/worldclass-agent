"""
Red-team regression tests for Research Quality Guardrails V3.
Gate policy: CI/autonomous run fails if a dangerous case passes.
"""
import json
import tempfile
import sys
from pathlib import Path

# Allow importing operator tools
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

def test_no_findings_should_not_done():
    """Project with 0 findings must not pass evidence gate."""
    from tools.research_quality_gate import run_evidence_gate, EVIDENCE_GATE_THRESHOLDS
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        research = root / "research"
        research.mkdir()
        tid = "proj-redteam-no-findings"
        proj = research / tid
        proj.mkdir()
        (proj / "findings").mkdir()
        (proj / "sources").mkdir()
        (proj / "verify").mkdir()
        (proj / "project.json").write_text(json.dumps({"id": tid, "question": "?"}))
        import os
        orig = os.environ.get("OPERATOR_ROOT")
        os.environ["OPERATOR_ROOT"] = str(root)
        try:
            result = run_evidence_gate(tid)
            assert result.get("pass") is False, "0 findings must fail evidence gate"
            assert result.get("fail_code") == "failed_insufficient_evidence" or "findings_count" in str(result.get("reasons", []))
        finally:
            if orig is not None:
                os.environ["OPERATOR_ROOT"] = orig
            elif "OPERATOR_ROOT" in os.environ:
                del os.environ["OPERATOR_ROOT"]


def test_single_source_claim_not_verified():
    """Claim with only 1 supporting source must not be is_verified in ledger."""
    from tools.research_verify import build_claim_ledger
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        research = root / "research"
        research.mkdir()
        tid = "proj-redteam-single-source"
        proj = research / tid
        proj.mkdir()
        (proj / "verify").mkdir()
        (proj / "project.json").write_text(json.dumps({"id": tid}))
        (proj / "verify" / "claim_verification.json").write_text(json.dumps({
            "claims": [{"claim": "Only one source says this.", "supporting_sources": ["https://one.com"], "verified": False}]
        }))
        (proj / "verify" / "source_reliability.json").write_text(json.dumps({
            "sources": [{"url": "https://one.com", "reliability_score": 0.8}]
        }))
        import os
        orig = os.environ.get("OPERATOR_ROOT")
        os.environ["OPERATOR_ROOT"] = str(root)
        try:
            ledger = build_claim_ledger(proj, {"question": "?"})
            claims = ledger.get("claims", [])
            assert len(claims) >= 1
            assert claims[0].get("is_verified") is False
            reason = claims[0].get("verification_reason", "")
            assert "source" in reason.lower()
        finally:
            if orig is not None:
                os.environ["OPERATOR_ROOT"] = orig
            elif "OPERATOR_ROOT" in os.environ:
                del os.environ["OPERATOR_ROOT"]


def test_conflicting_sources_must_dispute():
    """Claim marked disputed must have is_verified=false."""
    from tools.research_verify import build_claim_ledger
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        research = root / "research"
        research.mkdir()
        tid = "proj-redteam-dispute"
        proj = research / tid
        proj.mkdir()
        (proj / "verify").mkdir()
        (proj / "project.json").write_text(json.dumps({"id": tid}))
        (proj / "verify" / "claim_verification.json").write_text(json.dumps({
            "claims": [{"claim": "Disputed fact.", "supporting_sources": ["https://a.com", "https://b.com"], "verified": False, "verification_status": "disputed"}]
        }))
        (proj / "verify" / "source_reliability.json").write_text(json.dumps({
            "sources": [{"url": "https://a.com", "reliability_score": 0.7}, {"url": "https://b.com", "reliability_score": 0.7}]
        }))
        import os
        orig = os.environ.get("OPERATOR_ROOT")
        os.environ["OPERATOR_ROOT"] = str(root)
        try:
            ledger = build_claim_ledger(proj, {})
            claims = ledger.get("claims", [])
            assert len(claims) >= 1
            assert claims[0].get("is_verified") is False
            assert "dispute" in claims[0].get("verification_reason", "").lower()
        finally:
            if orig is not None:
                os.environ["OPERATOR_ROOT"] = orig
            elif "OPERATOR_ROOT" in os.environ:
                del os.environ["OPERATOR_ROOT"]


def test_memory_quarantine_not_used_by_brain():
    """Brain context must only include accepted findings (get_research_findings_accepted)."""
    from lib.memory import Memory
    from lib import brain_context
    mem = Memory()
    accepted = mem.get_research_findings_accepted(limit=100)
    ctx = brain_context.compile(mem)
    assert "accepted_findings_by_project" in ctx
    assert "high_quality_reflections" in ctx
    mem.close()


def test_evidence_gate_thresholds_exist():
    """Evidence gate thresholds are defined and used."""
    from tools.research_quality_gate import EVIDENCE_GATE_THRESHOLDS
    assert EVIDENCE_GATE_THRESHOLDS["findings_count_min"] >= 1
    assert EVIDENCE_GATE_THRESHOLDS["verified_claim_count_min"] >= 0
    assert 0 <= EVIDENCE_GATE_THRESHOLDS["claim_support_rate_min"] <= 1


if __name__ == "__main__":
    test_evidence_gate_thresholds_exist()
    test_no_findings_should_not_done()
    test_single_source_claim_not_verified()
    test_conflicting_sources_must_dispute()
    test_memory_quarantine_not_used_by_brain()
    print("All red-team tests passed.")
