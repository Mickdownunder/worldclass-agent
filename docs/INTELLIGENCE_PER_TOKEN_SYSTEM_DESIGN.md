# Intelligence-Per-Token Research System Design

This document captures the complete design direction discussed in chat and turns it into an implementable system blueprint.

Goal: maximize research intelligence with the smallest possible token usage.

Core objective function:

`IntelligencePerToken = (InformationGain * EvidenceQuality * DecisionUtility) / TotalTokens`

Every component below must improve this function.

---

## 1) Product Thesis

This system is not a chat assistant and not a static claim database.
It is a research engine with belief dynamics infrastructure.

Primary target:
- Better information quality (especially for high-stakes domains), not more debate.
- Continuous uncertainty reduction, not long narrative output.
- Reproducible knowledge updates with explicit provenance.

Secondary target:
- Strong epistemic behavior under contradictions and new evidence.
- High throughput with controlled cost.

---

## 2) Design Principles

1. Question-first, not claim-first.
2. Evidence-first, not prose-first.
3. Delta-only computation (no full recompute by default).
4. Gate-driven expensive reasoning.
5. Claims must survive falsification pressure, not only accumulation.
6. Memory is lifecycle-managed (decay, reopen, retire), never append-only.
7. Intelligence is measured by quality-per-token, not answer length.

---

## 3) High-Level Architecture

### A) Control Plane
- Orchestrator: phase transitions and gate evaluation.
- Policy Router: model/tool route per task class.
- Token Governor: hard and soft token budgets.
- Reopen Engine: revalidates stale or shocked beliefs.

### B) Knowledge Plane
- Question Graph: open/resolved questions + uncertainty vectors.
- Evidence Store: normalized source evidence + novelty.
- Claim Ledger: atomic claims + lifecycle state.
- Trajectory Store: belief path and volatility over revisions.
- Strategy Memory: what process choices worked for which problem type.

### C) Execution Plane
- Explore Engine: retrieve, read, extract, score novelty.
- Focus Engine: close high-priority evidence gaps.
- Verify Engine: attacks, counter-evidence, settlement.
- Synthesis Engine: compact decision-grade outputs.

---

## 4) Primary Object Model: Question Graph

Use questions as primary optimization unit.

Suggested schema:

```json
{
  "question_id": "q-...",
  "text": "...",
  "state": "open|narrowed|partially_resolved|resolved|reopened",
  "decision_relevance": 0.0,
  "uncertainty": {
    "measurement": 0.0,
    "mechanism": 0.0,
    "external_validity": 0.0,
    "temporal": 0.0
  },
  "evidence_gap_score": 0.0,
  "linked_claims": ["c-..."],
  "last_updated": "..."
}
```

Why:
- Prevents claim hoarding.
- Forces each cycle to improve an explicit research question state.

---

## 5) Claim Lifecycle (State Machine)

Mandatory state machine:

`proposed -> evidenced -> attacked -> defended -> stable -> decaying -> contested -> falsified -> retired`

Rules:
- No claim can enter `stable` without attack coverage.
- `stable` claims move to `decaying` based on domain half-life.
- `reopen` trigger on contradiction threshold, shock event, or stale threshold.
- `retired` requires explicit reason code.

Minimal claim schema:

```json
{
  "claim_id": "c-...",
  "text": "...",
  "state": "...",
  "confidence_interval": [0.0, 1.0],
  "residual_unknown": "...",
  "attack_coverage": 0.0,
  "source_diversity": 0.0,
  "falsification_status": "none|partial|passed|failed",
  "provenance": ["e-..."],
  "last_validated_revision": 0
}
```

---

## 6) Attack Taxonomy (Skeptic Scaffolding)

Do not run open-ended debates. Run constrained attack classes:

- Assumption attack
- Measurement attack
- Mechanism attack
- External-validity attack
- Incentive/confound attack
- Temporal drift attack
- Ontology/definition attack

Each attack stores:
- `attack_strength`
- `defense_strength`
- `unresolved_residual`

Only unresolved high-strength attacks can block stabilization.

---

## 7) Evidence System (Information Quality Engine)

Evidence is first-class. Each evidence item gets:

```json
{
  "evidence_id": "e-...",
  "source_url": "...",
  "source_type": "primary|secondary|review|news|other",
  "reliability_score": 0.0,
  "novelty_score": 0.0,
  "cross_claim_impact": 0.0,
  "extract_quality": 0.0,
  "reuse_count": 0
}
```

Core gates:
- Novelty Gate: reject near-duplicate evidence unless it materially changes uncertainty.
- Primary-Evidence Bias: prioritize primary sources in ranking and read scheduling.
- Evidence Liquidity: track how easily evidence changes beliefs.

---

## 8) Reopen Protocol (Knowledge Freshness)

Reopen triggers:
- Strong new contradiction.
- Decay threshold exceeded.
- Domain shock event.
- Ontology change.

Reopen action:
- Set affected claims to `contested`.
- Spawn targeted evidence acquisition only for impacted question regions.
- Re-settle impacted claim portfolio.

Never recompute globally unless explicitly requested.

---

## 9) Token-Efficiency Architecture

### A) Budget Layers
- Global project token budget
- Phase budgets (`explore`, `focus`, `verify`, `synthesize`)
- Claim-level budget for high-impact claims
- Reserve budget for reopen/shock events

### B) Model Routing
- Cheap model: extraction, dedupe, scoring, classification
- Mid model: planning, gap-filling, route decisions
- Strong model: high-impact falsification and final synthesis only

### C) Delta-Only Compute
- Evaluate only new evidence and changed claims.
- Hash artifacts and skip unchanged branches.
- Incremental verify, incremental synthesis.

### D) Hard Stop Criteria
- Marginal information gain below threshold.
- No meaningful uncertainty reduction over consecutive steps.
- Attack coverage sufficient and residual unknown non-critical.

---

## 10) Metrics That Actually Matter

### Quality
- information_gain_per_cycle
- uncertainty_reduction_per_question
- unsupported_statement_rate
- contradiction_resolution_quality
- decision_utility_score
- reproducibility_score

### Epistemic robustness
- calibration_error (ECE/Brier)
- overconfidence_rate
- stale_claim_ratio
- reopen_precision
- belief_volatility

### Efficiency
- tokens_per_verified_claim
- tokens_per_resolved_question
- cost_per_information_gain_unit

If a feature does not improve these, remove it.

---

## 11) Failure Modes and Guardrails

### Settlement-Oracle problem
Risk: non-binary or long-horizon claims cannot settle cleanly.
Mitigation:
- Claim typing (`forecast`, `structural`, `explanatory`, `normative`)
- Partial settlement and trajectory scoring

### Incentive gaming
Risk: trivial claims, hedging, consensus shadowing.
Mitigation:
- Portfolio scoring
- Complexity penalty
- Novelty bonus
- Adversarial coverage requirement

### False precision
Risk: pseudo-confidence from single point estimates.
Mitigation:
- Confidence interval
- Multi-axis uncertainty vector
- Mandatory residual unknown

### Skeptic asymmetry
Risk: builder-heavy drift.
Mitigation:
- Default auto-skeptic generation
- Skeptic reward weighting

### Decay misconfiguration
Risk: either stale beliefs or endless revalidation.
Mitigation:
- Domain-adaptive half-life
- Evidence-velocity adaptive decay

### Policy lock-in
Risk: exploit local strategy and suppress novelty.
Mitigation:
- Forced exploration quota
- Stochastic route mixing
- Novelty regularization

### Additional critical risks
- Ontology drift
- Evidence poisoning
- Benchmark lock-in
- Regime shift blindness

---

## 12) Integration Into Current Operator System

Proposed new files/modules:

- `tools/research_question_graph.py`
- `tools/research_claim_state_machine.py`
- `tools/research_attack_taxonomy.py`
- `tools/research_novelty_gate.py`
- `tools/research_reopen_protocol.py`
- `tools/research_token_governor.py`

Proposed project artifacts:

- `research/proj-*/questions/questions.json`
- `research/proj-*/claims/ledger.jsonl`
- `research/proj-*/attacks/attacks.jsonl`
- `research/proj-*/trajectories/belief_paths.jsonl`
- `research/proj-*/evidence/evidence_index.jsonl`
- `research/proj-*/policy/episode_metrics.jsonl`

Workflow insertion points:
- Explore: novelty + question-gap mapping
- Focus: unresolved high-priority question closure
- Verify: attack coverage + falsification settlement
- Synthesize: stable claims only + explicit residual unknown + next actions

UI additions:
- Question board (state + uncertainty)
- Claim lifecycle timeline
- Belief trajectory panel
- Token efficiency dashboard
- Reopen event feed

---

## 13) Minimal Viable Core (Prioritized)

If only a small set is implemented first:

1. Question Graph
2. Claim State Machine
3. Attack Taxonomy
4. Reopen Protocol
5. Token Governor

This gives most of the epistemic and cost gains without overbuilding.

---

## 14) Acceptance Rules for New Features

A new feature is accepted only if it improves all relevant targets:

- Improves `information_gain_per_token`
- Reduces unsupported statements
- Does not worsen `tokens_per_resolved_question`

Otherwise reject.

---

## 15) Practical Operating Rule

Default behavior per cycle:
- Acquire only evidence likely to reduce uncertainty on decision-relevant questions.
- Settle only impacted claim deltas.
- Synthesize only when epistemic gates pass.
- Stop when marginal gain is low.

This enforces intelligence growth without token inflation.
