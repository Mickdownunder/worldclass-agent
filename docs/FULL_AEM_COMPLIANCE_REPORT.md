# Full AEM Implementation — Compliance Report

This report maps each requirement from **Full_AEM_Implementation_Spec.md** and **full-aem-aggressive-rollout** plan to implementation and test evidence. All required items are implemented and wired; only explicitly optional items remain optional.

---

## 1. AEM_ENFORCEMENT_MODE end-to-end

| Requirement | Implementation | Test evidence |
|-------------|----------------|----------------|
| **observe**: fail-open allowed | `research-cycle.sh`: on AEM failure, do not block; advance to synthesize with fallback | Integration flow runs; no block on error in observe |
| **enforce**: fail-closed for stable-dependent path; tentative with deficit labels allowed | `research-cycle.sh`: if AEM not ok → do not advance; set `status=aem_blocked`, exit 0 | `test_aem_settlement_flow` (settlement run); workflow reads `ok`/`block_synthesize` from `aem_result.json` |
| **strict**: block synthesis if AEM fails or oracle integrity below threshold | `research_aem_settlement.py`: `block_synthesize = (mode=="strict" and (oracle_integrity_rate is None or < 0.80 or deadlock_rate > 0.05 or tentative_convergence_rate < 0.60))`; workflow blocks on `block_synthesize` | `test_oracle_integrity_rate_below_threshold_blocks_strict`, `test_oracle_integrity_rate_at_threshold_allows_strict`, `test_strict_blocks_when_deadlock_rate_above_threshold` |
| No unconditional workflow swallowing (no `\|\| true` that bypasses enforce/strict) | `research-cycle.sh`: AEM run without `|| true`; Python block reads `ok`/`block_synthesize` and blocks advance when enforce/strict and (not ok or block_synthesize) | Code review; workflow uses `aem_result.json` for decision |

**Files:** `operator/workflows/research-cycle.sh`, `operator/tools/research_aem_settlement.py`.

---

## 2. Hard synthesis contract (claim_ref-enforced)

| Requirement | Implementation | Test evidence |
|-------------|----------------|----------------|
| Explicit `claim_ref` format in output | Format: `[claim_ref: claim_id@version]` or `[claim_ref: id1@v1; id2@v2]`. Parser: `extract_claim_refs_from_report()`; validator checks every ref against ledger. | `test_extract_claim_refs_from_report`, `test_build_valid_claim_ref_set` |
| Synthesis cannot introduce new claims | Claim-bearing sentences (heuristic) without a valid `[claim_ref: ...]` in the same sentence → unreferenced; `unknown_refs` = refs not in ledger. | `test_synthesis_contract_blocks_missing_claim_ref_enforce`, `test_synthesis_contract_blocks_new_claim_with_ref_mismatch` |
| Every claim-bearing sentence must carry explicit `claim_ref` | `_sentence_contains_valid_claim_ref(sent, valid_refs)`; `valid_refs = _build_valid_claim_ref_set(claim_ledger)`. | `test_synthesis_contract_passes_with_valid_refs` |
| `claim_ref` not in ledger => violation | `unknown_refs` list; `valid` false when `len(unknown_refs) > 0`. | `test_synthesis_contract_blocks_unknown_claim_ref_enforce` |
| Unreferenced/unknown ref fails synthesis in enforce/strict | `run_synthesis` raises `SynthesisContractError` when (enforce or strict) and not valid; writes `synthesis_contract_status.json`. | `test_enforce_mode_raises_on_violation_in_run_synthesis` |
| Observe mode logs violations, does not block | Contract status written to `synthesis_contract_status.json`; no raise in observe. | `test_synthesis_contract_observe_logs_but_does_not_block` |
| Tentative labels required when PASS_TENTATIVE claims exist | `tentative_labels_ok`: report must contain "tentative"/"[tentative]"/"pass_tentative" when ledger has PASS_TENTATIVE | Verification Summary shows TENTATIVE for PASS_TENTATIVE claims |

**Files:** `operator/tools/research_synthesize.py` (`CLAIM_REF_PATTERN`, `extract_claim_refs_from_report`, `_build_valid_claim_ref_set`, `_sentence_contains_valid_claim_ref`, `validate_synthesis_contract`, `SynthesisContractError`, `_claim_ledger_block`, `_synthesize_section` with claim_ledger). **Tests:** `operator/tests/tools/test_research_synthesize_contract.py`.

---

## 3. Evidence index (real and used)

| Requirement | Implementation | Test evidence |
|-------------|----------------|----------------|
| Create and maintain `research/proj-*/evidence/evidence_index.jsonl` | `research_evidence_index.py`: `build_evidence_index(project_id)` from findings + sources + verify/source_reliability | `test_evidence_index_independence_lowered_for_same_cluster`, `test_evidence_scope_overlap_computed_from_ledger` |
| Required fields: `source_cluster_id`, `independence_score`, `primary_source_flag`, `evidence_scope`, `scope_overlap_score`, `directness_score`, `method_rigor_score`, `conflict_of_interest_flag` | All fields set in each evidence row; `scope_overlap_score` and `independence_score` computed from ledger (claim scope overlap, cluster count) | Evidence index tests; schema in module docstring |
| Evidence index step in settlement flow | `research_aem_settlement.py`: step "evidence_index" after ledger upgrade; calls `build_evidence_index(project_id)` | `test_aem_settlement_run` (steps include evidence_index) |

**Files:** `operator/tools/research_evidence_index.py`, `operator/tools/research_aem_settlement.py`.

---

## 4. Contradiction/scope logic active

| Requirement | Implementation | Test evidence |
|-------------|----------------|----------------|
| Contradiction linking in operational flow | `research_contradiction_linking.py`: `run_contradiction_linking(project_id)` after triage; calls `contradiction_detection` (reason), maps source_a/source_b to claim_refs, `add_contradiction(project_id, ra, rb, strength)` | Settlement steps include "contradiction_linking"; `test_contradiction_review_required_blocks_pass_stable` |
| Claim/evidence scope overlap computed and persisted | `research_evidence_index.py`: load ledger, build url→claim_scope, `_scope_overlap(claim_scope, evidence_scope)`; persist `scope_overlap_score` per evidence | `test_evidence_scope_overlap_computed_from_ledger` |
| `contradiction_review_required` enforced in settlement path | `research_market_scoring.py`: `contradiction_review_required = bool(c.get("contradicts"))`; if True and decision==PASS_STABLE → decision = PASS_TENTATIVE | `test_contradiction_review_required_blocks_pass_stable` |

**Files:** `operator/tools/research_contradiction_linking.py`, `operator/tools/research_evidence_index.py`, `operator/tools/research_market_scoring.py`, `operator/tools/research_aem_settlement.py`.

---

## 5. Token governor expected_ig heuristic

| Requirement | Implementation | Test evidence |
|-------------|----------------|----------------|
| `expected_ig ~= fragility_score * decision_relevance * (1 - evidence_density)` | `research_token_governor.py`: `expected_ig_heuristic(project_id)` uses triage top-K, portfolio `evidence_density` from `portfolio_state.json` | Token governor unit behavior (triage + portfolio read) |
| `expected_cost` from historical lane+claim type usage | `expected_tokens_heuristic(project_id, lane)`: from `get_last_episode_metrics` tokens_spent or `DEFAULT_EXPECTED_TOKENS` | Governor uses episode_metrics or defaults |
| Strong lane only when ratio threshold passes | `recommend_lane`: `expected_ig_per_token = expected_ig / max(tokens_strong, 1)`; strong when `expected_ig_per_token >= EXPECTED_IG_PER_TOKEN_THRESHOLD_STRONG` (0.001) | `research_token_governor.py` logic |

**Files:** `operator/tools/research_token_governor.py`.

---

## 6. Adversarial regression suite

| Scenario | Test | Location |
|----------|------|----------|
| Oracle ambiguity | `test_oracle_integrity_rate_below_threshold_blocks_strict`, `test_oracle_integrity_rate_at_threshold_allows_strict` | `tests/integration/test_aem_adversarial.py` |
| Claim slicing | `test_synthesis_contract_blocks_new_claims_in_enforce` | Same |
| Evidence flooding | `test_evidence_index_independence_lowered_for_same_cluster` | Same |
| Deadlock loops | `test_deadlock_exit_after_max_cycles`, `test_strict_blocks_when_deadlock_rate_above_threshold` | Same |
| Scope mismatch transfer | `test_evidence_scope_overlap_computed_from_ledger` | Same |
| Contradiction linking consistency | `test_contradiction_review_required_blocks_pass_stable` | Same |

**File:** `operator/tests/integration/test_aem_adversarial.py`.

---

## 7. Required contracts (validated, not just stored)

| Contract | Implementation | Validation |
|---------|-----------------|------------|
| claim_outcome_schema | `research_claim_outcome_schema.py`; `can_settle_stable(schema, outcome_dict, evidence_types)` | Falsification gate and market scoring use schema for PASS_STABLE |
| ledger.jsonl | `research_claim_state_machine.py`: versioning, retire semantics, reopen controls, scope, contradicts, failure_boundary, tentative fields | State machine guards; `add_contradiction`, `set_claim_scope` |
| attacks.jsonl | `research_attack_taxonomy.py`; fields attack_class, weight, selected_for_gate; falsification gate reads them | Gate uses selected attacks and unresolved residual |
| settlements.jsonl | `research_market_scoring.py`: claim_ref@version, decision, settlement_confidence, oracle_integrity_pass, contradiction_review_required | Market scoring writes; settlement and workflow read for block_synthesize |
| episode_metrics.jsonl | `research_episode_metrics.py`: entropy/proxy IG, ig_per_token, false_collapse_rate, evidence_delta, oracle_integrity_rate, etc. | Append in settlement; token governor reads last |
| evidence_index.jsonl | `research_evidence_index.py`: independence + scope + quality fields; scope_overlap from ledger | Build in settlement; portfolio/scope logic consume |

---

## 8. Required thresholds (v1 defaults)

| Threshold | Value | Enforcement | Test |
|-----------|--------|-------------|------|
| oracle_integrity_rate | ≥ 0.80 for PASS_STABLE | `research_aem_settlement.py`: strict blocks when rate < 0.80; `research_market_scoring.py`: oracle_integrity_pass per settlement | `test_oracle_integrity_rate_*` |
| tentative_convergence_rate | ≥ 0.60 within TTL | `research_aem_settlement.py`: `_compute_tentative_convergence_rate`; strict blocks when < 0.60 | In settlement result; block_synthesize logic |
| deadlock_rate | ≤ 0.05 | `research_aem_settlement.py`: `_compute_deadlock_rate`; strict blocks when > 0.05; `research_falsification_gate.py`: DEADLOCK_MAX_CYCLES exit | `test_deadlock_exit_after_max_cycles`, `test_strict_blocks_when_deadlock_rate_above_threshold` |

**Files:** `operator/tools/research_aem_settlement.py` (ORACLE_INTEGRITY_RATE_THRESHOLD, TENTATIVE_CONVERGENCE_RATE_THRESHOLD, DEADLOCK_RATE_THRESHOLD), `operator/tools/research_falsification_gate.py` (DEADLOCK_MAX_CYCLES).

---

## 9. Backward compatibility and quality gate

| Requirement | Implementation |
|-------------|----------------|
| Backward compatibility for non-AEM path | Synthesis uses `get_claims_for_synthesis`: AEM ledger first, fallback verify/claim_ledger.json |
| quality_gate logic composed, not replaced | AEM is separate step; quality_gate unchanged (RESEARCH_QUALITY_SLO.md, research_quality_gate.py) |
| Delta-only processing where specified | Evidence index and settlement operate on current project state; ledger append/update |
| No silent fallback that hides policy violations in enforce/strict | Workflow blocks advance and sets aem_blocked; synthesis raises SynthesisContractError |
| No placeholder TODO behavior for required items | All listed items implemented with real logic |

---

## 10. Docs updated

| Doc | Updates |
|-----|--------|
| RESEARCH_QUALITY_SLO.md | AEM thresholds (oracle_integrity_rate, tentative_convergence_rate, deadlock_rate); script paths; aem_deadlock fail code |
| Full_AEM_Implementation_Spec.md | (Reference; no change in this pass) |
| SYSTEM_CHECK.md / UI_OVERVIEW.md | Per workspace rule: keep in sync with code (Nav, API, workflows); AEM block and status aem_blocked |

---

## Summary

- **Gap 1 (AEM_ENFORCEMENT_MODE):** Enforced in workflow and settlement; block_synthesize and aem_blocked set as specified.
- **Gap 2 (Hard synthesis contract):** Validator and SynthesisContractError; unreferenced/tentative checks; enforce/strict block.
- **Gap 3 (Evidence index):** evidence_index.jsonl with all required fields; built in settlement; scope_overlap and independence from ledger.
- **Gap 4 (Contradiction/scope):** Contradiction linking step in flow; scope_overlap in evidence index; contradiction_review_required → no PASS_STABLE.
- **Gap 5 (Token governor):** expected_ig heuristic, expected_tokens, strong-lane gating by expected_ig_per_token.
- **Gap 6 (Adversarial tests):** Six scenarios covered in test_aem_adversarial.py.
- **Thresholds:** oracle_integrity_rate, tentative_convergence_rate, deadlock_rate enforced in strict mode and tested where applicable.
- **Compliance report:** This document maps spec/plan requirements to code and tests.

All required plan/spec items for Full AEM (as specified) are implemented, wired, and covered by tests or explicit code paths. Only explicitly optional items (e.g. full reopen branch, novelty_gate rollout) remain optional.
