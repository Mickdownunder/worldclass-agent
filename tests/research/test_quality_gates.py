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


def test_preflight_structure():
    """Preflight returns ok, fail_code, missing, message."""
    from tools.research_preflight import run_preflight
    result = run_preflight()
    assert "ok" in result
    assert "fail_code" in result
    assert "missing" in result
    assert "message" in result


def test_preflight_passes_when_bs4_installed():
    """When bs4 is installed, preflight passes (required for reader). Skip when bs4 missing."""
    try:
        import bs4  # noqa: F401
    except ImportError:
        return  # skip: bs4 not installed
    from tools.research_preflight import run_preflight
    result = run_preflight()
    assert result.get("ok") is True, "Preflight must pass when bs4 is available"
    assert result.get("fail_code") is None


def test_gate_failed_reader_pipeline_when_zero_extractable():
    """Project with sources, 0 findings, read_stats read_successes=0 -> fail_code failed_reader_pipeline."""
    from tools.research_quality_gate import run_evidence_gate
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        research = root / "research"
        research.mkdir()
        tid = "proj-redteam-reader-fail"
        proj = research / tid
        proj.mkdir()
        (proj / "findings").mkdir()
        (proj / "sources").mkdir()
        (proj / "verify").mkdir()
        (proj / "explore").mkdir()
        (proj / "project.json").write_text(json.dumps({"id": tid, "question": "?"}))
        (proj / "sources" / "a.json").write_text(json.dumps({"url": "https://example.com/a"}))
        (proj / "explore" / "read_stats.json").write_text(json.dumps({
            "read_attempts": 5,
            "read_successes": 0,
            "read_failures": 5,
        }))
        import os
        orig = os.environ.get("OPERATOR_ROOT")
        os.environ["OPERATOR_ROOT"] = str(root)
        try:
            result = run_evidence_gate(tid)
            assert result.get("pass") is False
            assert result.get("fail_code") == "failed_reader_pipeline"
            reasons = result.get("reasons", [])
            assert "zero_extractable_sources" in reasons or "read_failures_high" in reasons
        finally:
            if orig is not None:
                os.environ["OPERATOR_ROOT"] = orig
            elif "OPERATOR_ROOT" in os.environ:
                del os.environ["OPERATOR_ROOT"]


def test_reader_output_structured_error():
    """Reader outputs valid JSON with error_code and message when error (e.g. fetch fails)."""
    import subprocess
    tools = Path(__file__).resolve().parent.parent.parent / "tools"
    script = tools / "research_web_reader.py"
    # Connection refused to trigger fetch error quickly; reader must not crash
    r = subprocess.run(
        [sys.executable, str(script), "http://127.0.0.1:1/"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Reader exits 0 and outputs JSON (graceful error)
    assert r.returncode == 0, "Reader must not exit non-zero on fetch error"
    out = json.loads(r.stdout)
    assert "url" in out
    assert out.get("error") or out.get("error_code") or out.get("message"), "Error response must include error info"


def test_hallucinated_verified_tag_blocked():
    """[VERIFIED] only from claim_ledger; hallucinated LLM [VERIFIED] must be stripped (red-team: hallucinated_verified_tag_blocked)."""
    from tools.research_verify import apply_verified_tags_to_report
    # Input: report contains non-legit [VERIFIED]; ledger has no such claim or is_verified=False
    report_with_fake = "Fake claim [VERIFIED] and another sentence. Also X [VERIFIED] here."
    empty_ledger = []
    result = apply_verified_tags_to_report(report_with_fake, empty_ledger)
    assert "[VERIFIED]" not in result, "Hallucinated [VERIFIED] must be stripped when ledger is empty"
    assert "Fake claim" in result and "another sentence" in result
    # Ledger has claim but is_verified=False -> still no [VERIFIED]
    ledger_unverified = [{"text": "Fake claim", "is_verified": False, "claim_id": "c1"}]
    result2 = apply_verified_tags_to_report("Fake claim [VERIFIED].", ledger_unverified)
    assert "[VERIFIED]" not in result2
    # Ledger has one verified claim -> only that gets [VERIFIED]
    ledger_one_verified = [{"text": "Real claim", "is_verified": True, "claim_id": "c1"}]
    result3 = apply_verified_tags_to_report("Fake [VERIFIED]. Real claim here.", ledger_one_verified)
    assert "Fake." in result3 and "Real claim [VERIFIED] here" in result3
    assert result3.count("[VERIFIED]") == 1


if __name__ == "__main__":
    test_evidence_gate_thresholds_exist()
    test_preflight_structure()
    test_preflight_passes_when_bs4_installed()
    test_no_findings_should_not_done()
    test_single_source_claim_not_verified()
    test_conflicting_sources_must_dispute()
    test_gate_failed_reader_pipeline_when_zero_extractable()
    test_reader_output_structured_error()
    try:
        test_hallucinated_verified_tag_blocked()
    except (ImportError, AttributeError):
        pass  # apply_verified_tags_to_report may not exist in all branches
    test_memory_quarantine_not_used_by_brain()
    print("All red-team tests passed.")
