# Research Quality SLOs (Worldclass Quality V2 + Guardrails V3)

Runtime checks and targets for research quality and stability. **SOTA-Anspruch vs. Implementierung (Gaps, Roadmap):** siehe [RESEARCH_SOTA_GAP_AND_ROADMAP.md](RESEARCH_SOTA_GAP_AND_ROADMAP.md).

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
| `failed_conductor_tool_errors` | Conductor run_cycle: 3+ consecutive tool failures; run aborted, episode persisted |
| `aem_blocked` | AEM enforce/strict: settlement failed or oracle_integrity below threshold; synthesize blocked |
| `aem_deadlock` | AEM settlement: cycles > N without state transition (deadlock rate above threshold) |

Projects with these statuses do not reach `done`; they remain in a failed state until criteria are met or the project is reset.

## SLOs

| SLO | Target | Check |
|-----|--------|--------|
| **admission_reject_rate** | Not too low (gate must be meaningful) | Policy in `research_memory_policy.py`; events in `memory_admission_events` |
| **unsupported_claim_rate** | Low (most claims verified) | `research_eval.py` → `claim_support_rate` |
| **avg_report_quality** | ≥ 0.6 (critic score) | `quality_gate.critic_score` in project.json; `research_eval` scorecard. Critic 6-D: coverage, depth, accuracy, novelty, coherence, citation_quality in `research_critic.py` (dimensions + remediation_action). Synthesize-Phase: `docs/SYNTHESIZE_PHASE_DEEP_DIVE.md`, Weltklasse-Plan `docs/SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md`. |
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
- Evidence gate: `tools/research_quality_gate.py` → `EVIDENCE_GATE_THRESHOLDS`; kalibrierte Schwellen (≥10 erfolgreiche Outcomes): `tools/research_calibrator.py` → `get_calibrated_thresholds()`, FLOOR wird nie unterschritten.
- Watchdog: `tools/research_watchdog.py` → `DRIFT_*`, `MAX_NEW_FINDINGS_*`
- AEM (v1): `oracle_integrity_rate >= 0.80` for PASS_STABLE; `tentative_convergence_rate >= 0.60` within TTL; `deadlock_rate <= 0.05`. Enforced in `tools/research_aem_settlement.py` (strict mode: block_synthesize when any threshold violated). Scripts: `tools/research_claim_outcome_schema.py`, `tools/research_episode_metrics.py`, `tools/research_aem_settlement.py`, `tools/research_market_scoring.py`, `tools/research_falsification_gate.py`.
- Memory v2 strategy guards (if enabled): `relevance_threshold` and `critic_threshold` are bounded to `0.50..0.65`; `revise_rounds` bounded to `1..4` (`workflows/research-cycle.sh`).

## Research pipeline optimizations

- **Claim extraction:** Findings are batched (15–20 per LLM call) in `research_verify.py`; claims are merged and deduplicated. **Connect→Verify:** Claim order is thesis- and entity-prioritized; source_reliability marks `in_contradiction`; claim_ledger includes `supporting_evidence` (url, snippet, source_id), `credibility_weight`, and `in_contradiction`; fact_check disputed facts (Jaccard ≥ 0.4) set claim dispute flag (Phase 1). **CoVe** (RESEARCH_ENABLE_COVE_VERIFICATION=1): `claim_verification_cove` schreibt `cove_overlay.json`; build_claim_ledger wendet es an (cove_supports false → UNVERIFIED, fail-safe). **Evidence gaps:** `research_reason.py evidence_gaps` schreibt optional `verify/evidence_critique.json`. **deepening_queries:** Strukturiert mit query, reason, priority.
- **Parallel search:** Web search runs with 5–8 workers (`research_web_search.py` batch mode).
- **Parallel reads:** URL reading uses `research_parallel_reader.py` (8 workers in explore; see `docs/EXPLORE_PHASE_DEEP_DIVE.md`) instead of sequential bash loops. Findings get `finding_id`, `search_query`, `read_phase`, and `novelty_score` (Jaccard vs. recent findings); low-novelty findings are logged. Saturation: `tools/research_saturation_check.py` runs after explore round 1; when ≥7 of last 10 findings have novelty &lt; 0.2 it exits 1 and `research-cycle.sh` **skips** refinement, gap-fill, and depth reads for that cycle.
- **Adaptive search:** After round 1 reads, gap-fill and depth search results are read before "Extracting findings"; Planner Round 2 (`--refinement-queries`) adds precision queries from coverage.
- **Hypothesis model:** `RESEARCH_HYPOTHESIS_MODEL` (default `gemini-3.1-pro-preview`) is used only for `hypothesis_formation` in `research_reason.py`. **Connect Phase 4:** `RESEARCH_CONTRADICTION_STRUCTURED=1` (default) uses two-step contradiction detection (claim extraction per finding, then pair comparison); set to `0` for legacy single-call. **Phase 6:** hypothesis_formation reads `connect/entity_graph.json`; thesis and claim_ledger include `entity_ids` (entity names referenced).
- **Synthesize options:** `RESEARCH_SYNTHESIS_SEMANTIC=1` enables hybrid semantic+keyword relevance for findings; `RESEARCH_SYNTHESIS_SEMANTIC_WEIGHT` (default 0.5), `RESEARCH_EMBEDDING_MODEL` (default `text-embedding-3-small`), `RESEARCH_SYNTHESIS_STRUCTURED_SECTIONS=1` for JSON section output. Post-processing (tags, references, claim_evidence_map, manifest) is unified in `tools/research_synthesize_postprocess.py` (shell + Conductor).
- **Source dedup (Memory v2):** Read URLs are stored per question; future runs skip already-read URLs (see `read_urls` table, `lib.memory`).

## Memory v2 canary rollout gates

- Enable canary with `RESEARCH_MEMORY_V2_ENABLED=1` for a small subset first.
- Gate 1 (stability): no increase in hard fails (`failed_quality_gate`, `failed_insufficient_evidence`) over last 20 canary runs.
- Gate 2 (quality): critic-pass and claim-support-rate must be >= control baseline for 20 canary runs.
- Gate 3 (cost): average revision rounds and spend per successful run must not regress by >10%.

Automatic fallback criteria:

- Strategy mode becomes fallback when no strategy is found, confidence is too low, or strategy loading fails.
- Fallback reasons tracked in decision logs: `no_strategy`, `low_confidence`, `db_error`, `import_error`, `exception`.
- Even with v2 enabled, static bounded defaults remain active when fallback is selected.

## V3 SLO targets (start values)

- `unsupported_claim_rate` ≤ 0.15
- `citation_precision` ≥ 0.85
- `pass_rate_evidence_gate` ≥ 0.8 (on valid topics)
- `memory_reject_or_quarantine_rate` ≥ 0.2 (gate not too lax)
