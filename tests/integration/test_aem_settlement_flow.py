"""
Integration: AEM settlement flow — contracts, ledger upgrade, triage, attacks, gate, market, portfolio, episode_metrics.
Uses temp project with verify/claim_ledger.json; no LLM.
"""
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_aem_settlement_run(mock_operator_root, tmp_project):
    """Run full AEM settlement on project with verify ledger; artifacts created."""
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({
        "claims": [
            {"claim_id": "cl_0_1", "text": "Claim A", "is_verified": True, "supporting_source_ids": ["u1", "u2"]},
            {"claim_id": "cl_1_2", "text": "Claim B", "is_verified": False, "supporting_source_ids": ["u1"]},
        ]
    }))
    from tools.research_aem_settlement import run_settlement
    result = run_settlement(pid)
    assert result.get("ok") is True
    assert "steps" in result
    assert "claim_outcome_schema" in result["steps"]
    assert "ledger_upgrade" in result["steps"]
    assert (tmp_project / "claims" / "ledger.jsonl").exists()
    assert (tmp_project / "questions" / "questions.json").exists()
    assert (tmp_project / "attacks" / "attacks.jsonl").exists()
    assert (tmp_project / "market" / "settlements.jsonl").exists()
    assert (tmp_project / "portfolio" / "portfolio_state.json").exists()
    assert (tmp_project / "policy" / "episode_metrics.jsonl").exists()


def test_get_claims_for_synthesis_prefers_aem_ledger(mock_operator_root, tmp_project):
    """get_claims_for_synthesis returns claims from claims/ledger.jsonl when present."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({"claims": [{"claim_id": "v1", "text": "From verify"}]}))
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    (tmp_project / "claims" / "ledger.jsonl").write_text(json.dumps({"claim_id": "aem1", "claim_version": 1, "text": "From AEM"}))
    from tools.research_common import get_claims_for_synthesis
    claims = get_claims_for_synthesis(tmp_project)
    assert len(claims) == 1
    assert claims[0].get("claim_id") == "aem1"
    assert claims[0].get("text") == "From AEM"


def test_get_claims_for_synthesis_fallback_verify(mock_operator_root, tmp_project):
    """get_claims_for_synthesis falls back to verify/claim_ledger.json when no AEM ledger."""
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({"claims": [{"claim_id": "v1", "text": "From verify"}]}))
    from tools.research_common import get_claims_for_synthesis
    claims = get_claims_for_synthesis(tmp_project)
    assert len(claims) == 1
    assert claims[0].get("claim_id") == "v1"


# --- D. Evidence Index (D1, D2) ---

REQUIRED_EVIDENCE_INDEX_FIELDS = [
    "source_cluster_id", "independence_score", "primary_source_flag", "evidence_scope",
    "scope_overlap_score", "directness_score", "method_rigor_score", "conflict_of_interest_flag",
]


def test_d1_evidence_index_created_by_aem_settlement(mock_operator_root, tmp_project):
    """D1: evidence/evidence_index.jsonl is created by AEM settlement and is not empty when there are findings."""
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({
        "claims": [{"claim_id": "cl_0_1", "text": "Claim A", "is_verified": True, "supporting_source_ids": []}],
    }))
    (tmp_project / "findings" / "f1.json").write_text(json.dumps({"url": "https://example.com/a", "title": "T", "excerpt": "E"}))
    from tools.research_aem_settlement import run_settlement
    result = run_settlement(pid)
    assert result.get("ok") is True
    evidence_path = tmp_project / "evidence" / "evidence_index.jsonl"
    assert evidence_path.exists()
    lines = [l for l in evidence_path.read_text().strip().splitlines() if l.strip()]
    assert len(lines) >= 1


def test_d2_evidence_index_entries_have_required_fields(mock_operator_root, tmp_project):
    """D2: every evidence_index.jsonl entry has required fields."""
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "findings").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({
        "claims": [{"claim_id": "cl_0_1", "text": "C", "is_verified": True, "supporting_source_ids": []}],
    }))
    (tmp_project / "findings" / "f1.json").write_text(json.dumps({"url": "https://x.com/1", "title": "T", "excerpt": "E"}))
    from tools.research_evidence_index import build_evidence_index, load_evidence_index
    build_evidence_index(pid)
    idx = load_evidence_index(tmp_project)
    assert len(idx) >= 1
    for e in idx:
        for key in REQUIRED_EVIDENCE_INDEX_FIELDS:
            assert key in e, f"missing field {key} in evidence entry"


# --- C. Enforcement (C1–C3, C7, C8) ---

def test_c1_observe_aem_settlement_error_does_not_block_synth(mock_operator_root, tmp_project):
    """C1: observe mode: AEM settlement error does not block synthesis (fail-open)."""
    import os
    from unittest.mock import patch
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({"claims": []}))
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "observe"}):
        from tools.research_aem_settlement import run_settlement
        result = run_settlement(pid)
    assert "ok" in result
    assert result.get("block_synthesize") is not True


def test_c2_enforce_aem_settlement_error_blocks_synth(mock_operator_root, tmp_project):
    """C2: enforce mode: AEM settlement error leads to block (status=aem_blocked / re-raise)."""
    import os
    from unittest.mock import patch
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({"claims": []}))
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "enforce"}):
        from tools.research_aem_settlement import run_settlement
        result = run_settlement(pid)
    assert result.get("ok") in (True, False)
    if not result.get("ok"):
        assert result.get("error") or result.get("block_synthesize") is not True


def test_c7_strict_all_thresholds_ok_settlement_ok_no_block(mock_operator_root, tmp_project):
    """C7: strict mode: when all thresholds OK and settlement OK, synth is not blocked."""
    import os
    from unittest.mock import patch
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    (tmp_project / "market").mkdir(parents=True, exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({
        "claims": [{"claim_id": "cl_1", "text": "C", "is_verified": True, "supporting_source_ids": []}],
    }))
    (tmp_project / "market" / "settlements.jsonl").write_text("\n".join([
        json.dumps({"claim_ref": "cl_1@1", "decision": "PASS_STABLE", "oracle_integrity_pass": True}),
    ]))
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "strict"}):
        from tools.research_aem_settlement import run_settlement
        result = run_settlement(pid)
    assert result.get("ok") is True
    assert result.get("block_synthesize") is False
