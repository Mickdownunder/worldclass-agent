#!/usr/bin/env python3
"""
AEM: Orchestrator. Runs schema, ledger upgrade, question graph, state machine, triage, attacks,
falsification gate, market scoring, portfolio, episode metrics, reopen (optional), token governor.
Respects AEM_ENFORCEMENT_MODE: observe (fail-open), enforce (fail-closed for PASS_STABLE deps), strict (block synthesize if AEM fails).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log

ENFORCEMENT_MODES = ("observe", "enforce", "strict")
ORACLE_INTEGRITY_RATE_THRESHOLD = 0.80  # v1: strict blocks synthesize if below
TENTATIVE_CONVERGENCE_RATE_THRESHOLD = 0.60  # v1: strict blocks if below
DEADLOCK_RATE_THRESHOLD = 0.05  # v1: strict blocks if above


def _compute_oracle_integrity_rate(proj_path: Path) -> float | None:
    """From market/settlements.jsonl: fraction of PASS_STABLE settlements with oracle_integrity_pass true. None if no settlements."""
    path = proj_path / "market" / "settlements.jsonl"
    if not path.exists():
        return None
    stable_total = 0
    stable_pass = 0
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            s = json.loads(line)
            if s.get("decision") == "PASS_STABLE":
                stable_total += 1
                if s.get("oracle_integrity_pass"):
                    stable_pass += 1
        except json.JSONDecodeError:
            continue
    if stable_total == 0:
        return 1.0  # No stable claims => no failure
    return round(stable_pass / stable_total, 4)


def _compute_deadlock_rate(proj_path: Path) -> float:
    """Fraction of claims in ledger with failure_boundary.reason == deadlock_exit_max_cycles."""
    from tools.research_claim_state_machine import load_ledger_jsonl
    claims = load_ledger_jsonl(proj_path)
    if not claims:
        return 0.0
    dead = sum(1 for c in claims if (c.get("failure_boundary") or {}).get("reason") == "deadlock_exit_max_cycles")
    return round(dead / len(claims), 4)


def _compute_tentative_convergence_rate(proj_path: Path) -> float:
    """From settlements: stable / (stable + tentative); 1.0 if no tentative (all stable or fail)."""
    path = proj_path / "market" / "settlements.jsonl"
    if not path.exists():
        return 1.0
    stable, tentative = 0, 0
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            s = json.loads(line)
            d = s.get("decision") or ""
            if d == "PASS_STABLE":
                stable += 1
            elif d == "PASS_TENTATIVE":
                tentative += 1
        except json.JSONDecodeError:
            continue
    total = stable + tentative
    if total == 0:
        return 1.0
    return round(stable / total, 4)


def get_enforcement_mode() -> str:
    mode = (os.environ.get("AEM_ENFORCEMENT_MODE") or "observe").strip().lower()
    return mode if mode in ENFORCEMENT_MODES else "observe"


def run_settlement(project_id: str) -> dict:
    """
    Run AEM pipeline in order. On exception: if observe -> log and return {ok: false}; if enforce/strict -> re-raise.
    """
    mode = get_enforcement_mode()
    proj_path = project_dir(project_id)
    results: dict = {"ok": True, "steps": [], "error": None}
    try:
        # 1. Contracts
        from tools.research_claim_outcome_schema import ensure_project_schema
        ensure_project_schema(project_id)
        results["steps"].append("claim_outcome_schema")

        # 2. Ledger upgrade (verify -> claims/ledger.jsonl)
        from tools.research_claim_state_machine import upgrade_verify_ledger_to_claims
        upgraded = upgrade_verify_ledger_to_claims(project_id)
        results["steps"].append("ledger_upgrade")

        # 3. Question graph
        from tools.research_question_graph import build_question_graph, write_question_graph
        write_question_graph(project_id, build_question_graph(project_id))
        results["steps"].append("question_graph")

        # 4. Evidence index (for portfolio + scope/contradiction)
        from tools.research_evidence_index import build_evidence_index
        build_evidence_index(project_id)
        results["steps"].append("evidence_index")

        # 5. Triage
        from tools.research_claim_triage import triage_claims
        triage_claims(project_id)
        results["steps"].append("triage")

        # 5b. Contradiction linking (operational flow: detect and persist to ledger)
        from tools.research_contradiction_linking import run_contradiction_linking
        run_contradiction_linking(project_id)
        results["steps"].append("contradiction_linking")

        # 6. Attack taxonomy
        from tools.research_attack_taxonomy import run_attack_taxonomy
        run_attack_taxonomy(project_id)
        results["steps"].append("attack_taxonomy")

        # 7. Falsification gate
        from tools.research_falsification_gate import run_falsification_gate
        run_falsification_gate(project_id)
        results["steps"].append("falsification_gate")

        # 8. Market scoring
        from tools.research_market_scoring import run_market_scoring
        run_market_scoring(project_id)
        results["steps"].append("market_scoring")

        # 9. Portfolio scoring
        from tools.research_portfolio_scoring import run_portfolio_scoring
        run_portfolio_scoring(project_id)
        results["steps"].append("portfolio_scoring")

        # 10. Episode metrics (append one record)
        from tools.research_episode_metrics import append_episode_metrics
        project = load_project(proj_path)
        tokens_spent = 0  # Caller can pass via env or project.json
        append_episode_metrics(project_id, tokens_spent=tokens_spent)
        results["steps"].append("episode_metrics")

        # 11. Reopen check (optional; do not apply by default to avoid loop)
        # from tools.research_reopen_protocol import check_reopen_triggers
        # triggers = check_reopen_triggers(project_id)
        # if triggers and mode != "observe": apply_reopen(project_id, triggers)

        # Compute oracle_integrity_rate and block_synthesize for workflow (strict: block if below thresholds)
        results["oracle_integrity_rate"] = _compute_oracle_integrity_rate(proj_path)
        results["deadlock_rate"] = _compute_deadlock_rate(proj_path)
        results["tentative_convergence_rate"] = _compute_tentative_convergence_rate(proj_path)
        results["block_synthesize"] = (
            mode == "strict"
            and (
                results["oracle_integrity_rate"] is None
                or results["oracle_integrity_rate"] < ORACLE_INTEGRITY_RATE_THRESHOLD
                or results["deadlock_rate"] > DEADLOCK_RATE_THRESHOLD
                or results["tentative_convergence_rate"] < TENTATIVE_CONVERGENCE_RATE_THRESHOLD
            )
        )
        audit_log(proj_path, "aem_settlement_complete", {"steps": len(results["steps"]), "mode": mode, "oracle_integrity_rate": results.get("oracle_integrity_rate")})
    except Exception as e:
        results["ok"] = False
        results["error"] = str(e)
        results["oracle_integrity_rate"] = None
        results["block_synthesize"] = mode == "strict"  # strict: block when AEM fails
        try:
            audit_log(proj_path, "aem_settlement_error", {"error": str(e), "mode": mode})
        except Exception:
            pass
        if mode in ("enforce", "strict"):
            raise
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_aem_settlement.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    result = run_settlement(project_id)
    print(json.dumps(result))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
