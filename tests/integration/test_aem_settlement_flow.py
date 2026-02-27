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
