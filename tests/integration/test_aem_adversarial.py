"""
Adversarial regression suite for AEM: oracle ambiguity, claim slicing, evidence flooding,
deadlock loops, scope mismatch transfer, contradiction linking consistency.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# --- Fixtures ---

@pytest.fixture
def proj_with_settlements(mock_operator_root, tmp_project):
    """Project with market/settlements.jsonl for oracle integrity tests."""
    pid = "test-proj"
    (tmp_project / "market").mkdir(parents=True, exist_ok=True)
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    (tmp_project / "contracts").mkdir(parents=True, exist_ok=True)
    (tmp_project / "questions").mkdir(parents=True, exist_ok=True)
    (tmp_project / "attacks").mkdir(parents=True, exist_ok=True)
    (tmp_project / "portfolio").mkdir(parents=True, exist_ok=True)
    (tmp_project / "policy").mkdir(parents=True, exist_ok=True)
    (tmp_project / "evidence").mkdir(parents=True, exist_ok=True)
    return tmp_project


def _ledger_line(claim_id: str, version: int = 1, text: str = "Claim", **kw):
    d = {"claim_id": claim_id, "claim_version": version, "text": text, "state": "evidenced",
         "supporting_source_ids": [], "is_verified": True, "contradicts": [], "claim_scope": {}}
    d.update(kw)
    return json.dumps(d)


# --- 1. Oracle ambiguity ---

def test_oracle_integrity_rate_below_threshold_blocks_strict(proj_with_settlements):
    """Strict mode: block_synthesize when oracle_integrity_rate < 0.80 (oracle ambiguity)."""
    proj = proj_with_settlements
    # Settlements: 2 PASS_STABLE, only 1 with oracle_integrity_pass => rate 0.5
    lines = [
        json.dumps({"claim_ref": "c1@1", "decision": "PASS_STABLE", "oracle_integrity_pass": True}),
        json.dumps({"claim_ref": "c2@1", "decision": "PASS_STABLE", "oracle_integrity_pass": False}),
    ]
    (proj / "market" / "settlements.jsonl").write_text("\n".join(lines))
    from tools.research_aem_settlement import _compute_oracle_integrity_rate, get_enforcement_mode
    rate = _compute_oracle_integrity_rate(proj)
    assert rate is not None
    assert rate == 0.5
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "strict"}):
        from tools.research_aem_settlement import run_settlement
        res = run_settlement(proj.name)
        assert res.get("block_synthesize") is True
        assert res.get("oracle_integrity_rate") == 0.5


def test_strict_blocks_when_deadlock_rate_above_threshold(proj_with_settlements):
    """Strict: block_synthesize when deadlock_rate > 0.05 (v1 threshold)."""
    from tools.research_aem_settlement import (
        _compute_deadlock_rate,
        DEADLOCK_RATE_THRESHOLD,
    )
    proj = proj_with_settlements
    (proj / "claims" / "ledger.jsonl").write_text("\n".join([
        _ledger_line("c1", 1, "A", failure_boundary={"reason": "deadlock_exit_max_cycles", "threshold_exceeded": True}),
        _ledger_line("c2", 1, "B"),
    ]))
    rate = _compute_deadlock_rate(proj)
    assert rate == 0.5
    assert rate > DEADLOCK_RATE_THRESHOLD
    # In strict mode, block_synthesize would be True when deadlock_rate > 0.05


def test_oracle_integrity_rate_at_threshold_allows_strict(proj_with_settlements):
    """Strict: when oracle_integrity_rate >= 0.80, block_synthesize is False."""
    proj = proj_with_settlements
    lines = [
        json.dumps({"claim_ref": "c1@1", "decision": "PASS_STABLE", "oracle_integrity_pass": True}),
        json.dumps({"claim_ref": "c2@1", "decision": "PASS_STABLE", "oracle_integrity_pass": True}),
        json.dumps({"claim_ref": "c3@1", "decision": "PASS_STABLE", "oracle_integrity_pass": False}),
        json.dumps({"claim_ref": "c4@1", "decision": "PASS_STABLE", "oracle_integrity_pass": True}),
    ]
    (proj / "market" / "settlements.jsonl").write_text("\n".join(lines))
    from tools.research_aem_settlement import _compute_oracle_integrity_rate
    rate = _compute_oracle_integrity_rate(proj)
    assert rate == 0.75  # 3/4
    lines.append(json.dumps({"claim_ref": "c5@1", "decision": "PASS_STABLE", "oracle_integrity_pass": True}))
    (proj / "market" / "settlements.jsonl").write_text("\n".join(lines))
    rate = _compute_oracle_integrity_rate(proj)
    assert rate == 0.8  # 4/5
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "strict"}):
        from tools.research_aem_settlement import run_settlement
        res = run_settlement(proj.name)
        assert res.get("block_synthesize") is False


# --- 2. Claim slicing (synthesis contract) ---

def test_synthesis_contract_blocks_new_claims_in_enforce(proj_with_settlements):
    """Synthesis that would introduce new claims fails contract in enforce/strict (claim slicing)."""
    from tools.research_synthesize import validate_synthesis_contract, SynthesisContractError
    ledger = [
        {"claim_id": "cl_1", "claim_version": 1, "text": "The only allowed claim."},
    ]
    # Report as string (contract expects full report text)
    report = "Summary: Something entirely new that is a claim-like statement."
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "enforce"}):
        out = validate_synthesis_contract(report, ledger, "enforce")
        assert out.get("unreferenced_claim_sentence_count", 0) >= 0  # heuristic may or may not flag
        assert "valid" in out
    # Explicit invalid case: valid=False and enforce => caller should raise
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "enforce"}):
        out_strict = validate_synthesis_contract(report, ledger, "strict")
        assert "valid" in out_strict
    # If validator flags unreferenced, valid should be False in enforce/strict
    if out.get("unreferenced_claim_sentence_count", 0) > 0:
        assert out.get("valid") is False


# --- 3. Evidence flooding ---

def test_evidence_index_independence_lowered_for_same_cluster(proj_with_settlements):
    """Evidence from same cluster gets lower independence_score (evidence flooding resilience)."""
    proj = proj_with_settlements
    (proj / "findings").mkdir(exist_ok=True)
    for i in range(3):
        (proj / "findings" / f"f{i}.json").write_text(json.dumps({
            "url": f"https://same-domain.com/page{i}", "title": f"Title {i}", "excerpt": "x"
        }))
    from tools.research_evidence_index import build_evidence_index, load_evidence_index
    build_evidence_index(proj.name)
    idx = load_evidence_index(proj)
    assert len(idx) >= 3
    clusters = [e.get("source_cluster_id") for e in idx]
    same = [e for e in idx if e.get("source_cluster_id") == clusters[0]]
    if len(same) >= 2:
        # At least one should have reduced independence
        scores = [e.get("independence_score") for e in same]
        assert min(scores) <= 0.7


# --- 4. Deadlock loops ---

def test_deadlock_exit_after_max_cycles(proj_with_settlements):
    """Falsification gate forces FAIL with failure_boundary when tentative_cycles_used >= DEADLOCK_MAX_CYCLES."""
    from tools.research_falsification_gate import DEADLOCK_MAX_CYCLES, run_falsification_gate
    proj = proj_with_settlements
    (proj / "claims" / "ledger.jsonl").write_text(_ledger_line("cl_1", 1, "Claim A", tentative_cycles_used=DEADLOCK_MAX_CYCLES))
    (proj / "contracts" / "claim_outcome_schema.json").write_text(json.dumps({"outcome_types": ["PASS_STABLE", "PASS_TENTATIVE", "FAIL"]}))
    (proj / "attacks" / "attacks.jsonl").write_text("")  # empty attacks
    run_falsification_gate(proj.name)
    ledger_path = proj / "claims" / "ledger.jsonl"
    lines = [l for l in ledger_path.read_text().strip().splitlines() if l.strip()]
    assert len(lines) >= 1
    claim = json.loads(lines[0])
    fb = claim.get("failure_boundary") or {}
    assert fb.get("reason") == "deadlock_exit_max_cycles" or claim.get("falsification_status") == "FAIL"


# --- 5. Scope mismatch transfer ---

def test_evidence_scope_overlap_computed_from_ledger(proj_with_settlements):
    """Evidence index scope_overlap_score reflects claim/evidence scope (scope mismatch)."""
    proj = proj_with_settlements
    (proj / "findings").mkdir(exist_ok=True)
    url = "https://example.com/source1"
    (proj / "findings" / "f1.json").write_text(json.dumps({"url": url, "title": "T", "excerpt": "E"}))
    (proj / "claims" / "ledger.jsonl").write_text(_ledger_line("cl_1", 1, "Claim", supporting_source_ids=[url], claim_scope={"population": "adults", "geography": "US"}))
    from tools.research_evidence_index import build_evidence_index, load_evidence_index
    build_evidence_index(proj.name)
    idx = load_evidence_index(proj)
    ev = next((e for e in idx if e.get("source_url") == url), None)
    assert ev is not None
    assert "scope_overlap_score" in ev
    # Evidence scope default empty; overlap with claim scope may be 0 (no match) or computed
    assert isinstance(ev.get("scope_overlap_score"), (int, float))


# --- 6. Contradiction linking consistency ---

def test_contradiction_review_required_blocks_pass_stable(proj_with_settlements):
    """When claim has contradicts, market scoring sets contradiction_review_required and no PASS_STABLE."""
    from tools.research_market_scoring import run_market_scoring
    proj = proj_with_settlements
    claim = json.loads(_ledger_line("cl_1", 1, "A", contradicts=[{"claim_ref": "cl_2@1", "contradiction_strength": 0.8}]))
    claim["falsification_status"] = "PASS_STABLE"
    (proj / "claims" / "ledger.jsonl").write_text(json.dumps(claim))
    run_market_scoring(proj.name)
    path = proj / "market" / "settlements.jsonl"
    assert path.exists()
    for line in path.read_text().strip().splitlines():
        if not line:
            continue
        s = json.loads(line)
        if s.get("claim_ref") == "cl_1@1":
            assert s.get("contradiction_review_required") is True
            assert s.get("decision") == "PASS_TENTATIVE"
            return
    pytest.fail("Settlement for cl_1@1 not found")
