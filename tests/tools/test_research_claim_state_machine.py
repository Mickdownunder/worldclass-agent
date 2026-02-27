"""Unit tests for tools/research_claim_state_machine.py (AEM)."""
import json
import pytest
from pathlib import Path
from tools.research_claim_state_machine import (
    load_verify_ledger_claims,
    load_ledger_jsonl,
    save_ledger_jsonl,
    upgrade_claim_to_ledger_entry,
    can_transition,
    upgrade_verify_ledger_to_claims,
    apply_transition,
    add_contradiction,
    set_claim_scope,
    VALID_STATES,
    RETIRE_REASONS,
)


def test_upgrade_claim_to_ledger_entry():
    c = {"claim_id": "cl_0_123", "text": "Foo", "is_verified": True, "supporting_source_ids": ["u1"]}
    out = upgrade_claim_to_ledger_entry(c, version=1)
    assert out["claim_id"] == "cl_0_123"
    assert out["claim_version"] == 1
    assert out["state"] in VALID_STATES
    assert "claim_scope" in out
    assert "contradicts" in out
    assert "failure_boundary" in out
    assert "retire_reason" in out
    assert "reopen_allowed" in out
    assert "reopen_conditions" in out
    assert "tentative_ttl" in out
    assert "tentative_cycles_used" in out


def test_can_transition_retired_requires_reason():
    ok, reason = can_transition("contested", "retired", {"retire_reason": "ILL_POSED", "reopen_conditions": []})
    assert ok is True
    ok2, reason2 = can_transition("contested", "retired", {"retire_reason": "UNKNOWN"})
    assert ok2 is False
    assert "retire_reason" in reason2


def test_can_transition_allowed():
    ok, _ = can_transition("proposed", "evidenced", {})
    assert ok is True
    ok2, _ = can_transition("evidenced", "stable", {})
    assert ok2 is True


def test_can_transition_disallowed():
    ok, _ = can_transition("stable", "proposed", {})
    assert ok is False
    ok2, _ = can_transition("retired", "stable", {})
    assert ok2 is False


def test_upgrade_verify_ledger_to_claims(mock_operator_root, tmp_project):
    pid = tmp_project.name
    (tmp_project / "verify").mkdir(exist_ok=True)
    (tmp_project / "verify" / "claim_ledger.json").write_text(json.dumps({
        "claims": [
            {"claim_id": "cl_0_1", "text": "A", "is_verified": False},
            {"claim_id": "cl_1_2", "text": "B", "is_verified": True},
        ]
    }))
    claims = upgrade_verify_ledger_to_claims(pid)
    assert len(claims) == 2
    assert (tmp_project / "claims" / "ledger.jsonl").exists()
    lines = (tmp_project / "claims" / "ledger.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["claim_id"] == "cl_0_1"
    assert first["claim_version"] == 1
    assert first["state"] in VALID_STATES


def test_apply_transition(mock_operator_root, tmp_project):
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    claim = {
        "claim_id": "cl_0_1", "claim_version": 1, "text": "A", "state": "evidenced",
        "contradicts": [], "claim_scope": {}, "reopen_conditions": [], "retire_reason": None,
    }
    save_ledger_jsonl(tmp_project, [claim])
    updated = apply_transition(pid, "cl_0_1@1", "stable")
    assert updated is not None
    assert updated["state"] == "stable"
    loaded = load_ledger_jsonl(tmp_project)
    assert loaded[0]["state"] == "stable"


def test_add_contradiction(mock_operator_root, tmp_project):
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    save_ledger_jsonl(tmp_project, [{"claim_id": "c1", "claim_version": 1, "contradicts": [], "text": "x"}])
    out = add_contradiction(pid, "c1@1", "c2@1", 0.8)
    assert out is not None
    assert len(out["contradicts"]) == 1
    assert out["contradicts"][0]["claim_ref"] == "c2@1"
    assert out["contradicts"][0]["contradiction_strength"] == 0.8


def test_set_claim_scope(mock_operator_root, tmp_project):
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    save_ledger_jsonl(tmp_project, [{"claim_id": "c1", "claim_version": 1, "claim_scope": {}, "text": "x"}])
    out = set_claim_scope(pid, "c1@1", {"population": "EU", "timeframe": "2025"})
    assert out is not None
    assert out["claim_scope"].get("population") == "EU"
    assert out["claim_scope"].get("timeframe") == "2025"
