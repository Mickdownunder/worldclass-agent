# Full AEM 100% Execution Plan (Agent Handoff)

This is the single execution document for implementing and validating Full AEM to strict completion.

Use this as the operating contract for the implementation agent.

## Mission

Deliver Full AEM as fully functional, end-to-end behavior in Operator, with strict enforcement of contracts and synthesis integrity.

No partial completion. No "core done". No hidden fallbacks that bypass enforcement.

## Source of Truth (must read first)

1. `/root/operator/docs/Full_AEM_Implementation_Spec.md`
2. `/root/.cursor/plans/full-aem-aggressive-rollout_9ee51cde.plan.md`
3. `/root/operator/docs/INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md`

## Hard Completion Definition

Work is complete only if all required items are implemented, wired, and tested:

- Enforcement modes (`observe|enforce|strict`) work end-to-end.
- Hard synthesis contract is enforced with explicit claim references.
- Evidence index is real, populated, and consumed by scoring/governance.
- Contradiction/scope mechanics are active in runtime flow.
- Token governor uses expected IG per token heuristic for lane gating.
- Adversarial regressions pass.

Optional items remain optional only if explicitly marked optional in spec.

---

## Phase 0 — Preflight and Baseline

### Tasks
- Verify repository state and current branch.
- Run current relevant tests to establish baseline.
- Create short baseline report (`docs/FULL_AEM_BASELINE_STATUS.md`).

### Exit Criteria
- Baseline pass/fail matrix created.
- No ambiguity about currently failing and currently passing tests.

---

## Phase 1 — Enforcement Modes (No Bypass)

### Required Implementation
- Ensure `AEM_ENFORCEMENT_MODE` semantics are enforced in workflow:
  - `observe`: fail-open allowed, log violation.
  - `enforce`: block synthesize on AEM failure for stable-dependent path.
  - `strict`: block synthesize on failure OR threshold violations.
- Remove unconditional fallback behavior that bypasses enforce/strict semantics.

### Required Checks
- Workflow must read deterministic settlement output and choose block/advance accordingly.
- `project.json` status and block reason must be set when blocked.

### Exit Criteria
- Integration test proves each mode behavior.
- No code path can silently advance in enforce/strict when blocked.

---

## Phase 2 — Hard Synthesis Contract

### Required Implementation
- Introduce explicit claim reference contract in synthesis output for claim-bearing statements.
- Validate:
  - every claim-bearing statement has explicit `claim_ref`.
  - each `claim_ref` resolves to existing ledger entries.
  - no new claims are introduced in synthesis.
- In `enforce|strict`, violations must fail synthesis deterministically.

### Required Checks
- Keep dual source loading (`claims/ledger.jsonl` -> fallback verify ledger).
- Preserve tentative labeling requirements.

### Exit Criteria
- Contract validator blocks missing/unknown refs and new claims.
- Strict mode fails hard on violations.

---

## Phase 3 — Evidence Index as Live Subsystem

### Required Implementation
- Build and persist `research/proj-*/evidence/evidence_index.jsonl`.
- Ensure required fields are present and used:
  - `source_cluster_id`
  - `independence_score`
  - `primary_source_flag`
  - `evidence_scope`
  - `scope_overlap_score`
  - `directness_score`
  - `method_rigor_score`
  - `conflict_of_interest_flag`
- Wire evidence index into settlement/portfolio decisions.

### Exit Criteria
- Evidence index is generated every AEM settlement run.
- Portfolio/settlement consume the index meaningfully (not dead write).

---

## Phase 4 — Contradiction + Scope Runtime Activation

### Required Implementation
- Activate contradiction linking in operational flow (not helper-only).
- Persist contradiction links on claims with strength scores.
- Enforce `contradiction_review_required` in settlement path.
- Ensure claim/evidence scope overlap contributes to evidence quality logic.

### Exit Criteria
- Contradictions generated in flow affect settlement outcomes.
- Scope mismatch affects support confidence and/or settlement outcome.

---

## Phase 5 — Token Governor Heuristic Compliance

### Required Implementation
- Implement expected IG heuristic:
  - `expected_ig ~= fragility_score * decision_relevance * (1 - evidence_density)`
- Implement expected cost estimate from historical lane/claim usage.
- Gate strong lane only when `expected_ig_per_token` threshold passes.

### Exit Criteria
- Lane decisions are deterministic and testable.
- Strong lane does not activate without threshold pass.

---

## Phase 6 — Adversarial Regression Suite

### Required Tests (must exist and pass)
- Oracle ambiguity
- Claim slicing
- Evidence flooding
- Deadlock loops
- Scope mismatch transfer
- Contradiction linking consistency

### Exit Criteria
- Test file(s) present and integrated in CI target set.
- All adversarial scenarios are green.

---

## Phase 7 — Final Compliance Validation

### Required Artifacts
- `/root/operator/docs/FULL_AEM_COMPLIANCE_REPORT.md` updated with:
  - Requirement -> Implementation -> Test evidence mapping
  - Explicit statement of optional items not implemented
  - Threshold validation status
- `/root/operator/docs/AEM_VALIDATION_REPORT.md` updated with runtime evidence.

### Required Threshold Validation
- `oracle_integrity_rate >= 0.80` for stable settlements.
- `tentative_convergence_rate >= 0.60` within TTL.
- `deadlock_rate <= 0.05`.

### Exit Criteria
- All required thresholds measured and reported from real artifacts.
- No unresolved required item remains.

---

## Test Quality Rules (Anti-Fake)

Tests are rejected if they only assert mocked internals without behavior.

Each critical test must validate at least one of:
- file artifact creation/update
- state transition correctness
- block/advance behavior in workflow
- contract violation detection and hard failure
- threshold gating behavior

Required:
- Negative-path test before happy-path for each guard.
- No blanket skips/xfails for required scenarios.

---

## Execution Discipline

- Implement in small milestones.
- After each milestone:
  1. list changed files
  2. summarize behavior changes
  3. run targeted tests
  4. report pass/fail and residual risk
- If ambiguity exists, choose stricter behavior aligned with spec and document decision.

---

## Definition of Done (Strict)

Done only when all are true:

- All phases above complete.
- Required tests pass.
- Required thresholds validated.
- No required contract left partial.
- No enforcement bypass remains.
- Hard synthesis contract enforced.
- Evidence index + contradiction/scope are operational, not ornamental.

If any required item is missing, output must be "NOT DONE" with exact blockers.
