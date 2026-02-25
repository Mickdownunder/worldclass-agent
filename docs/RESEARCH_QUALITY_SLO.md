# Research Quality SLOs (Worldclass Quality V2 + Guardrails V3)

Runtime checks and targets for research quality and stability.

## Standard fail codes (V3)

| Code | Meaning |
|------|--------|
| `failed_insufficient_evidence` | Evidence gate failed (findings/sources/verified claims below threshold) |
| `failed_verification_inconclusive` | claim_support_rate or verified_claim_count too low |
| `failed_quality_gate` | Report critic score < 0.6 |
| `failed_source_diversity` | high_reliability_source_ratio below threshold |

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

## Thresholds (single source)

- Policy: `tools/research_memory_policy.py` → `THRESHOLDS`
- Evidence gate: `tools/research_quality_gate.py` → `EVIDENCE_GATE_THRESHOLDS`
- Watchdog: `tools/research_watchdog.py` → `DRIFT_*`, `MAX_NEW_FINDINGS_*`

## V3 SLO targets (start values)

- `unsupported_claim_rate` ≤ 0.15
- `citation_precision` ≥ 0.85
- `pass_rate_evidence_gate` ≥ 0.8 (on valid topics)
- `memory_reject_or_quarantine_rate` ≥ 0.2 (gate not too lax)
