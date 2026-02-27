# Research Quality SLOs (Worldclass Quality V2 + Guardrails V3)

Runtime checks and targets for research quality and stability.

## Standard fail codes (V3)

| Code | Meaning |
|------|--------|
| `failed_insufficient_evidence` | Evidence gate failed (findings/sources/verified claims below threshold) |
| `failed_verification_inconclusive` | claim_support_rate or verified_claim_count too low |
| `failed_quality_gate` | Report critic score < 0.6 |
| `failed_source_diversity` | high_reliability_source_ratio below threshold |
| `failed_dependency_missing_bs4` | Preflight: required module bs4 not installed (reader stack broken) |
| `failed_reader_no_extractable_content` | Explore: sources present but 0 read_successes (reader failed for all URLs) |
| `failed_reader_pipeline` | Evidence gate: 0 findings with sources and read_successes=0 (technical extraction failure) |
| `aem_deadlock` | AEM settlement: cycles > N without state transition (deadlock rate above threshold) |

Projects with these statuses do not reach `done`; they remain in a failed state until criteria are met or the project is reset.

## SLOs

| SLO | Target | Check |
|-----|--------|--------|
| **admission_reject_rate** | Not too low (gate must be meaningful) | Policy in `research_memory_policy.py`; events in `memory_admission_events` |
| **unsupported_claim_rate** | Low (most claims verified) | `research_eval.py` → `claim_support_rate` |
| **avg_report_quality** | ≥ 0.6 (critic score) | `quality_gate.critic_score` in project.json; `research_eval` scorecard |
| **time_to_verified_report** | Tracked per project | Phase history + last_phase_at |

## Runtime enforcement

- **Admission gate:** Only findings passing `research_memory_policy.decide()` are stored as `accepted` and embedded (`research_embed.py`).
- **Drift:** `research_watchdog.py check` alerts when avg scorecard drops by ≥ 0.15 over last 3 runs.
- **Rate limit:** Max `MAX_NEW_FINDINGS_PER_PROJECT_PER_DAY` (50) new findings per project per 24h; enforced in `research-cycle.sh` explore phase.

## Red-Team CI / Blocker (V3)

- **Script:** `./scripts/run_quality_gate_tests.sh` — runs `tests/research/test_quality_gates.py`. Exit code = test exit code; **fail (≠ 0) = build/run must not succeed**.
- **CI:** `.github/workflows/quality-gates.yml` runs this script on push/PR to main; job fails if tests fail.

## Thresholds (single source)

- Policy: `tools/research_memory_policy.py` → `THRESHOLDS`
- Evidence gate: `tools/research_quality_gate.py` → `EVIDENCE_GATE_THRESHOLDS`
- Watchdog: `tools/research_watchdog.py` → `DRIFT_*`, `MAX_NEW_FINDINGS_*`
- AEM (v1): `oracle_integrity_rate >= 0.80` for PASS_STABLE; `tentative_convergence_rate >= 0.60` within TTL; `deadlock_rate <= 0.05`. Enforced in `tools/research_aem_settlement.py` (strict mode: block_synthesize when any threshold violated). Scripts: `tools/research_claim_outcome_schema.py`, `tools/research_episode_metrics.py`, `tools/research_aem_settlement.py`, `tools/research_market_scoring.py`, `tools/research_falsification_gate.py`.
- Memory v2 strategy guards (if enabled): `relevance_threshold` and `critic_threshold` are bounded to `0.50..0.65`; `revise_rounds` bounded to `1..4` (`workflows/research-cycle.sh`).

## V3 SLO targets (start values)

- `unsupported_claim_rate` ≤ 0.15
- `citation_precision` ≥ 0.85
- `pass_rate_evidence_gate` ≥ 0.8 (on valid topics)
- `memory_reject_or_quarantine_rate` ≥ 0.2 (gate not too lax)
