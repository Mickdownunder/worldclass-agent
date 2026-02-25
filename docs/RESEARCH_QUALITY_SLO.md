# Research Quality SLOs (Worldclass Quality V2)

Runtime checks and targets for research quality and stability.

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
- Watchdog: `tools/research_watchdog.py` → `DRIFT_*`, `MAX_NEW_FINDINGS_*`
