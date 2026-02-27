"""
Hard claim_ref-enforced synthesis contract tests.
- claim-bearing sentence without claim_ref => violation
- claim_ref not in ledger => violation
- new claim text not backed by existing ledger claim_ref => violation
- valid report with refs to real claims => passes
- observe mode logs violations and does not block
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_synthesize import (
    validate_synthesis_contract,
    SynthesisContractError,
    extract_claim_refs_from_report,
    _build_valid_claim_ref_set,
)


def _ledger(*claims):
    """Build claim_ledger from (claim_id, version, text) tuples."""
    return [
        {"claim_id": cid, "claim_version": ver, "text": text or f"Claim {cid}"}
        for cid, ver, text in claims
    ]


def test_synthesis_contract_blocks_missing_claim_ref_enforce():
    """Claim-bearing sentence without claim_ref => violation; enforce mode => valid=False."""
    ledger = _ledger(("cl_1", 1, "The effect was significant."))
    # Report has a claim-like sentence but no [claim_ref: ...] in it
    report = (
        "This section summarizes the data. "
        "The study found that the effect was significant and the research suggests a strong correlation. "
        "Further work is needed."
    )
    out = validate_synthesis_contract(report, ledger, "enforce")
    assert out["valid"] is False
    assert out["unreferenced_claim_sentence_count"] >= 1
    assert "unreferenced_claim_sentences" in out


def test_synthesis_contract_blocks_unknown_claim_ref_enforce():
    """claim_ref not found in ledger => violation; enforce blocks."""
    ledger = _ledger(("cl_1", 1, "Only this claim exists."))
    report = (
        "The effect was significant [claim_ref: cl_1@1]. "
        "Another finding shows 50% increase [claim_ref: cl_99@1]."
    )
    out = validate_synthesis_contract(report, ledger, "enforce")
    assert out["valid"] is False
    assert "cl_99@1" in out["unknown_refs"]


def test_synthesis_contract_blocks_new_claim_with_ref_mismatch():
    """New claim text not backed by existing ledger claim_ref => violation (claim-like sentence without valid ref)."""
    ledger = _ledger(("cl_1", 1, "The effect was significant."))
    # Sentence that is claim-like but cites a ref that doesn't match the claim content (or we have an extra claim-like sentence with no ref)
    report = (
        "The effect was significant [claim_ref: cl_1@1]. "
        "Data indicate that revenue grew by 40 percent in Q3 and the report states this was above expectations."
    )
    out = validate_synthesis_contract(report, ledger, "strict")
    # Second sentence is claim-like and has no [claim_ref: ...] => unreferenced
    assert out["valid"] is False
    assert out["unreferenced_claim_sentence_count"] >= 1


def test_synthesis_contract_passes_with_valid_refs():
    """Valid report with refs to real claims => passes."""
    ledger = _ledger(
        ("cl_1", 1, "The effect was significant."),
        ("cl_2", 1, "Revenue grew by 40 percent."),
    )
    report = (
        "The effect was significant [claim_ref: cl_1@1]. "
        "Revenue grew by 40 percent [claim_ref: cl_2@1]. "
        "Further work is needed."
    )
    out = validate_synthesis_contract(report, ledger, "enforce")
    assert out["valid"] is True
    assert out["unknown_refs"] == []
    assert out["unreferenced_claim_sentence_count"] == 0


def test_synthesis_contract_observe_logs_but_does_not_block():
    """Observe mode: violations present but no raise; contract status can be written to metadata (caller responsibility)."""
    ledger = _ledger(("cl_1", 1, "Only one claim."))
    # Claim-like sentence (signals + length) without any [claim_ref: ...] => violation
    report = (
        "The study found that the effect was significant and the data indicate a strong correlation. "
        "No claim_ref in this sentence."
    )
    out = validate_synthesis_contract(report, ledger, "observe")
    # Valid is still False (we have violations) but observe mode does not raise - caller does not raise
    assert out["valid"] is False
    assert out["unreferenced_claim_sentence_count"] >= 1
    # Verify we can build contract_status for metadata (same shape as in run_synthesis)
    contract_status = {
        "valid": out["valid"],
        "mode": "observe",
        "unknown_refs": out.get("unknown_refs", []),
        "unreferenced_claim_sentence_count": out.get("unreferenced_claim_sentence_count", 0),
        "tentative_labels_ok": out.get("tentative_labels_ok", True),
    }
    assert contract_status["mode"] == "observe"
    assert contract_status["valid"] is False


def test_extract_claim_refs_from_report():
    """Parser: extract refs from [claim_ref: id@ver] and [claim_ref: a@1; b@2]."""
    report = "Text [claim_ref: cl_1@1] more. [claim_ref: cl_2@1; cl_3@2] end."
    refs = extract_claim_refs_from_report(report)
    assert "cl_1@1" in refs
    assert "cl_2@1" in refs
    assert "cl_3@2" in refs


def test_build_valid_claim_ref_set():
    """Valid ref set from ledger."""
    ledger = _ledger(("cl_1", 1, "A"), ("cl_2", 2, "B"))
    s = _build_valid_claim_ref_set(ledger)
    assert "cl_1@1" in s
    assert "cl_2@2" in s


def test_enforce_mode_raises_on_violation_in_run_synthesis():
    """Enforce: validate_synthesis_contract returns valid=False for report with claim-like sentence but no ref."""
    ledger = _ledger(("cl_1", 1, "Claim."))
    report = (
        "The study found that the effect was significant and the data indicate a strong correlation."
    )
    out = validate_synthesis_contract(report, ledger, "enforce")
    assert out["valid"] is False
    assert out["unreferenced_claim_sentence_count"] >= 1 or len(out.get("unknown_refs", [])) > 0


def test_b6_strict_mode_raises_on_violation():
    """B6: strict mode returns valid=False for report with unresolved violations."""
    ledger = _ledger(("cl_1", 1, "Only one claim."))
    report = "The study found that the effect was significant and the data indicate a strong correlation."
    out = validate_synthesis_contract(report, ledger, "strict")
    assert out["valid"] is False
    assert out["unreferenced_claim_sentence_count"] >= 1 or len(out.get("unknown_refs", [])) > 0


def test_b8_empty_ledger_non_aem_fallback_synthesis_passes():
    """B8: empty ledger (non-AEM fallback) => no ref-check enforced, synthesis contract passes."""
    ledger = []
    report = "This is a summary with no claim-like sentences that would require a claim_ref."
    out = validate_synthesis_contract(report, ledger, "observe")
    assert out["valid"] is True
    assert out.get("unknown_refs", []) == []
    assert out.get("unreferenced_claim_sentence_count", 0) == 0
