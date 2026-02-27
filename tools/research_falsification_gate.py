#!/usr/bin/env python3
"""
AEM: Falsification gate v2 — PASS_STABLE | PASS_TENTATIVE | FAIL with deadlock-safe exits.
Reads attacks and ledger; for each triaged claim decides gate outcome. No claim can stay in gate
forever: max_cycles without state change => force FAIL or PASS_TENTATIVE with failure_boundary.

Usage:
  research_falsification_gate.py run <project_id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl, save_ledger_jsonl
from tools.research_claim_outcome_schema import load_schema_for_project, can_settle_stable

GATE_OUTCOMES = {"PASS_STABLE", "PASS_TENTATIVE", "FAIL"}
DEADLOCK_MAX_CYCLES = 5  # After this many AEM cycles without transition, force exit


def _load_attacks(proj_path: Path) -> list[dict]:
    path = proj_path / "attacks" / "attacks.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _attacks_for_claim_ref(attacks: list[dict], claim_ref: str) -> list[dict]:
    return [a for a in attacks if a.get("claim_ref") == claim_ref]


def _claim_ref(claim: dict) -> str:
    return f"{claim.get('claim_id', '')}@{claim.get('claim_version', 1)}"


def _decide_gate_outcome(
    claim: dict,
    attacks: list[dict],
    schema: dict,
    tentative_cycles_used: int,
) -> tuple[str, dict]:
    """
    Returns (outcome, failure_boundary). outcome in PASS_STABLE | PASS_TENTATIVE | FAIL.
    Deadlock-safe: if tentative_cycles_used >= DEADLOCK_MAX_CYCLES => FAIL or PASS_TENTATIVE with boundary.
    """
    ref = _claim_ref(claim)
    claim_attacks = _attacks_for_claim_ref(attacks, ref)
    selected = [a for a in claim_attacks if a.get("selected_for_gate")]
    outcome = "FAIL"
    failure_boundary = claim.get("failure_boundary") or {"reason": "", "evidence_refs": [], "threshold_exceeded": False}

    # Deadlock exit
    if tentative_cycles_used >= DEADLOCK_MAX_CYCLES:
        failure_boundary["reason"] = "deadlock_exit_max_cycles"
        failure_boundary["threshold_exceeded"] = True
        return "FAIL", failure_boundary

    # No attacks selected => can pass if verified
    if not selected:
        if claim.get("is_verified") or (claim.get("state") or "").lower() == "stable":
            outcome = "PASS_STABLE"
        else:
            outcome = "PASS_TENTATIVE"
            failure_boundary["reason"] = "no_attack_coverage"
        return outcome, failure_boundary

    # Unresolved high-strength attacks block STABLE
    unresolved = [a for a in selected if (a.get("unresolved_residual") or 0) > 0.3]
    if unresolved:
        outcome = "PASS_TENTATIVE"
        failure_boundary["reason"] = "unresolved_attacks"
        failure_boundary["evidence_refs"] = [a.get("attack_class") for a in unresolved[:5]]
        failure_boundary["threshold_exceeded"] = True
        return outcome, failure_boundary

    # Check schema: can we settle stable?
    outcome_dict = {
        "outcome_type": claim.get("outcome_type") or "binary",
        "resolution_authority": claim.get("resolution_authority") or "internal_auditor",
        "resolution_method": claim.get("resolution_method") or "event",
        "settlement_confidence": float(claim.get("settlement_confidence", 0.7)),
        "audit_trace_required": claim.get("audit_trace_required", False),
    }
    can_stable, reason = can_settle_stable(schema, outcome_dict, claim.get("evidence_types_used"))
    if can_stable:
        outcome = "PASS_STABLE"
    else:
        outcome = "PASS_TENTATIVE"
        failure_boundary["reason"] = reason or "schema_blocks_stable"
    return outcome, failure_boundary


def run_falsification_gate(project_id: str) -> dict:
    """
    For each claim in ledger (or triaged subset), compute gate outcome; update ledger with
    falsification_status, failure_boundary, tentative_cycles_used. Returns summary.
    """
    proj_path = project_dir(project_id)
    schema = load_schema_for_project(project_id)
    claims = load_ledger_jsonl(proj_path)
    attacks = _load_attacks(proj_path)
    stats = {"PASS_STABLE": 0, "PASS_TENTATIVE": 0, "FAIL": 0}
    updated = []
    for c in claims:
        ref = _claim_ref(c)
        tentative_cycles = c.get("tentative_cycles_used", 0)
        outcome, failure_boundary = _decide_gate_outcome(c, attacks, schema, tentative_cycles)
        stats[outcome] = stats.get(outcome, 0) + 1
        c["falsification_status"] = outcome
        c["failure_boundary"] = failure_boundary
        if outcome == "PASS_TENTATIVE":
            c["tentative_cycles_used"] = tentative_cycles + 1
            ttl = c.get("tentative_ttl", 3)
            c["tentative_ttl"] = max(0, ttl - 1)
            if c["tentative_ttl"] == 0 and outcome != "FAIL":
                outcome = "FAIL"
                failure_boundary["reason"] = "tentative_ttl_expired"
                failure_boundary["threshold_exceeded"] = True
                c["falsification_status"] = outcome
                stats["PASS_TENTATIVE"] = stats.get("PASS_TENTATIVE", 0) - 1
                stats["FAIL"] = stats.get("FAIL", 0) + 1
        c["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated.append(c)
    if updated:
        save_ledger_jsonl(proj_path, updated)
    audit_log(proj_path, "aem_falsification_gate_run", stats)
    return {"outcomes": stats, "claims_updated": len(updated)}


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_falsification_gate.py run <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "run":
        result = run_falsification_gate(project_id)
        print(json.dumps(result))
    else:
        print("Unknown command: use run", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
