# Full AEM Implementation — Validation Report

**Date:** 2026-02-27  
**Spec:** `operator/docs/Full_AEM_Implementation_Spec.md`  
**Plan:** `.cursor/plans/full-aem-aggressive-rollout_9ee51cde.plan.md`

## Delivered

### 1. Contracts (Milestone 1)
- **research_claim_outcome_schema.py:** Schema load/ensure, `validate_authority_auditability`, `can_settle_stable`, `validate_outcome_shape`. Global default: `operator/contracts/claim_outcome_schema.json`.
- **research_episode_metrics.py:** `policy/episode_metrics.jsonl` with prior_entropy, posterior_entropy, ig, ig_per_token, ig_mode, oracle_integrity_rate, tentative_decay_rate, resolution_rate, stable_claim_rate, false_collapse_rate, evidence_delta.

### 2. Question Graph + Claim State Machine (Milestones 2–3)
- **research_question_graph.py:** `questions/questions.json` with question_id, text, state, uncertainty, evidence_gap_score, linked_claims.
- **research_claim_state_machine.py:** Ledger upgrade verify→claims/ledger.jsonl; states and guards; claim_version, supersedes, retire_reason, reopen_allowed/reopen_conditions, claim_scope, contradicts, failure_boundary, tentative_ttl/cycles; `add_contradiction`, `set_claim_scope`.

### 3. Triage + Attack Taxonomy (Milestone 4)
- **research_claim_triage.py:** impact_score, decision_relevance, fragility_score, attack_surface_estimate; Top-K triage.
- **research_attack_taxonomy.py:** `attacks/attacks.jsonl` with attack_class, attack_weight, falsification_test, minimal_repro_steps, selected_for_gate, attack_strength, defense_strength, unresolved_residual.

### 4. Falsification Gate + Settlement + Portfolio (Milestones 5–6)
- **research_falsification_gate.py:** PASS_STABLE | PASS_TENTATIVE | FAIL; deadlock exit after DEADLOCK_MAX_CYCLES.
- **research_market_scoring.py:** `market/settlements.jsonl` with claim_ref, decision, settlement_confidence, oracle_integrity_pass, contradiction_review_required.
- **research_portfolio_scoring.py:** `portfolio/portfolio_state.json` (flood/duplicate penalty, portfolio_score).

### 5. Reopen + Token Governor (Milestones 7–8)
- **research_reopen_protocol.py:** check_reopen_triggers, apply_reopen (contradiction_delta, decay_threshold).
- **research_token_governor.py:** recommend_lane (cheap/mid/strong) by expected_ig_per_token.

### 6. Workflow + Synthesis (Milestones 9–10)
- **research_aem_settlement.py:** Orchestrator; AEM_ENFORCEMENT_MODE=observe|enforce|strict.
- **research-cycle.sh:** AEM block after evidence gate pass, before advance_phase synthesize; dual-source claim load in synthesize inline script.
- **research_common.get_claims_for_synthesis:** AEM ledger then verify fallback.
- **research_synthesize.py:** Uses get_claims_for_synthesis (no new claims; claim_ref from ledger only).

### 7. Tests + Docs
- Unit: test_research_claim_outcome_schema, test_research_episode_metrics, test_research_question_graph, test_research_claim_state_machine; quality_gate and verify unchanged.
- Integration: test_aem_settlement_flow (full settlement + get_claims_for_synthesis AEM/fallback).
- RESEARCH_QUALITY_SLO.md: aem_deadlock fail code; AEM thresholds and script paths.
- SYSTEM_CHECK.md: AEM artifacts and AEM_ENFORCEMENT_MODE note.

## Acceptance Criteria (Plan) — Status

| Criterion | Status |
|----------|--------|
| No regression in quality_gate pass/fail | Met (quality_gate untouched; tests pass) |
| Old non-AEM path functional | Met (synthesis uses verify ledger when no claims/ledger.jsonl) |
| Synthesis never invents new claims | Met (synthesis reads only from get_claims_for_synthesis) |
| Contracts mandatory | Met (schema + episode_metrics first; validation rules enforced) |
| Delta-only where specified | Ledger append/update; episode_metrics append |
| Deadlock-safe falsification gate | Met (DEADLOCK_MAX_CYCLES force exit) |
| v1 thresholds (oracle_integrity_rate ≥ 0.80, tentative_convergence ≥ 0.60, deadlock_rate ≤ 0.05) | Documented in RESEARCH_QUALITY_SLO; enforced in market_scoring and falsification_gate |

## Not Done in This Pass

- **API/UI surfacing:** Trajectory, attacks, episode-metrics endpoints and UI panels (spec: “only after core works”).
- **Novelty gate:** research_novelty_gate.py (optional per spec).
- **Hard synthesis contract enforcement:** Unreferenced-claim-sentence check and strict fail in synthesis (foundation in place; strict gate can be added in synthesize).
- **Adversarial regression tests:** Settlement oracle ambiguity, gaming, deadlock loops (listed in spec; can be added next).

## Risk / Metric Impact

- **Risk:** Low. AEM is optional (script presence check); observe mode fail-open; synthesis fallback preserves current behavior.
- **Metric:** IG/token and episode_metrics written; no change to existing evidence gate or critic flow until AEM is enforced.
