# Research-Phasen Deep-Dive — Umsetzung & Risiken

Prüfung jeder Phase: Was ist umgesetzt, was kann brechen, was fehlt. Quelle: Code in `workflows/research-cycle.sh`, `workflows/research/phases/connect.sh`, `tools/research_*.py`.

---

## Vor der Phase (pro Run)

| Check | Status | Anmerkung |
|-------|--------|-----------|
| PHASE aus project.json | OK | Zeile 55: `PHASE=$(python3 -c "import json; ... phase ...")` |
| REQUEST / PROJECT_ID | OK | job.json request oder $*; Abbruch wenn kein Verzeichnis RESEARCH/$PROJECT_ID |
| secrets.env, policy.env | OK | Zeile 30–32: sourced wenn vorhanden |
| Memory v2 (memory_strategy.json) | OK | Zeile 62–117: relevance_threshold, critic_threshold, revise_rounds, domain_overrides mit Bounds 0.50–0.65, 1–4 |
| Conductor shadow | OK | Zeile 436–438: wenn RESEARCH_USE_CONDUCTOR≠1 wird conductor shadow geloggt |
| Conductor als Master | OK | Zeile 422–434: wenn RESEARCH_USE_CONDUCTOR=1, research_conductor run_cycle; bei Erfolg exit, sonst Fallback Bash |

Risiko: Wenn `research_conductor.py` fehlt oder crasht, bleibt Fallback; wenn gate leer zurückgibt, bleibt Phase unverändert (Zeile 264–266).

---

## Phase: EXPLORE

### Ablauf (wie umgesetzt)

1. progress_start "explore"
2. Optional: Token Governor (RESEARCH_ENABLE_TOKEN_GOVERNOR=1) → governor_lane.json
3. Optional: knowledge_seed (RESEARCH_ENABLE_KNOWLEDGE_SEED=1), question_graph (RESEARCH_ENABLE_QUESTION_GRAPH=1)
4. research_planner "$QUESTION" "$PROJECT_ID" → ART/research_plan.json (timeout 300); Fallback minimal plan wenn leer
5. research_plan.json → PROJ_DIR
6. READ_LIMIT aus complexity (complex=40, moderate=25, else=15)
7. research_web_search --queries-file research_plan.json --max-per-query 5 → web_search_round1.json
8. Optional: research_academic semantic_scholar (RESEARCH_ENABLE_ACADEMIC=1) → academic_round1.json, Merge in sources
9. Filter+Save: Plan + web_search → sources/*.json (topic/entity-Filter)
10. SMART_RANK: Domain-Rank, Blocklist, per_domain cap 3, topic/entity boost → read_order_round1.txt
11. FILTER_READ_URLS: get_read_urls_for_question (lib.memory) entfernt bereits gelesene URLs aus read_order
12. research_parallel_reader explore --input-file read_order_round1.txt --read-limit $READ_LIMIT --workers 8
13. research_saturation_check → SATURATION_DETECTED
14. research_coverage → coverage_round1.json, COVERAGE_PASS
15. Wenn nicht pass: refinement-queries → refinement_search → parallel_reader (refinement_urls_to_read), dann gap-fill (gap_queries → gap_search_round2 → parallel_reader), dann optional Round 3 (thin_topics → depth_queries → depth_search_round3 → parallel_reader); nach R2/R3 jeweils coverage_round2/3
16. research_deep_extract (timeout 600)
17. explore/read_stats.json geschrieben (read_attempts, read_successes, read_failures)
18. Optional: relevance_gate (RESEARCH_ENABLE_RELEVANCE_GATE=1), context_manager (RESEARCH_ENABLE_CONTEXT_MANAGER=1), dynamic_outline (RESEARCH_ENABLE_DYNAMIC_OUTLINE=1)
19. advance_phase "focus"

### Abhängigkeiten / Risiken

| Punkt | Risiko | Einschätzung |
|-------|--------|--------------|
| lib.memory get_read_urls_for_question | Import/DB-Fehler → FILTER_READ_URLS scheitert | try/except, skip_urls=set(); läuft weiter |
| research_planner timeout 300 | Bei Timeout/Fehler: zuerst research_planner --fallback-only (15–30 Queries aus Frage), nur bei dessen Fehler leerer Plan | Vollständige Fallback-Umsetzung (kein 0-Queries-Minimal mehr) |
| research_web_search / research_academic | 429/Timeout → leere oder Teil-Ergebnisse | Kein Retry im Script; Runden 2/3 füllen ggf. nach |
| research_parallel_reader | Stderr in CYCLE_LOG; letzte Zeile JSON stats | tail -1 für Stats; bei Crash keine Stats → read_attempts/successes 0 |
| research_deep_extract timeout 600 | Wie zuvor: Timeout-Kill ohne flush | Bereits gefixt: progress pid + flush in synthesize; deep_extract schreibt progress.step → pid aktuell |
| research_coverage | Liest findings/sources; Ausgabe JSON mit pass | Wenn Dateien fehlen, Tool kann fehlschlagen → Prüfung in quality_gate |
| advance_phase "focus" | Conductor gate kann auf "explore" zurücksetzen → weitere Explore-Runde | Gewollt |

Funktioniert: Ja, wenn Planner und Web Search mindestens teilweise liefern. Grenzfälle: Nur academic ohne Web Search (queries leer), oder alle Reads 429 → coverage pass trotzdem möglich (wenige Quellen).

---

## Phase: FOCUS

### Ablauf

1. progress_start "focus"
2. Optional: Token Governor
3. Coverage-Datei: round3 → round2 → round1 (PROJ_DIR dann ART)
4. Wenn kein COV_FILE: focus_queries.json = {"queries":[]}; sonst research_planner --gap-fill $COV_FILE $PROJECT_ID → focus_queries.json
5. Wenn verify/deepening_queries.json existiert: Merge (deepening zuerst, Dedup nach query text) in focus_queries.json
6. research_web_search --queries-file focus_queries.json --max-per-query 8 → focus_search.json
7. FOCUS_SAVE: focus_search URLs → sources/*.json
8. RANK_FOCUS: Domain-Rank, Blocklist, topic_boost, nur unread (ohne _content) → focus_read_order.txt
9. research_parallel_reader focus --input-file focus_read_order.txt --read-limit 15 --workers 8
10. focus/read_stats.json geschrieben
11. research_deep_extract (timeout 600)
12. Optional: context_manager add
13. progress_done, advance_phase "connect"

### Abhängigkeiten / Risiken

| Punkt | Risiko | Einschätzung |
|-------|--------|--------------|
| Kein Coverage (Explore in anderem Job) | focus_queries leer → Web Search liefert nichts; Ranking nur bereits vorhandene unread sources | Dokumentiert; Focus liest dann nur bestehende Quellen |
| deepening_queries Merge | verify/deepening_queries.json wird gelesen und mit gap-fill zusammengeführt | Korrekt umgesetzt (FOCUS_MERGE Block) |
| focus read_limit 15 | Parallel reader cap 15; bei vielen neuen URLs nur 15 Reads | Bewusst so; ausreichend für „targeted deep-dive“ |

Funktioniert: Ja. deepening_queries wird nun genutzt. Ohne Coverage bleibt Focus sinnvoll (weiter lesen, was da ist).

---

## Phase: CONNECT (connect.sh)

### Ablauf

1. connect/connect_status.json initial (entity_extract_ok etc. false)
2. Wenn kein OpenAI-Import: apply_connect_openai_fail_to_project → status failed_dependency_missing_openai, exit 1
3. research_entity_extract (timeout 600) → log.txt (>> "$PWD/log.txt"); kein || true → Phase schlägt bei Fehler fehl
4. research_reason contradiction_detection → contradictions.json
5. research_reason hypothesis_formation → ART/hypotheses.json
6. Wenn hypotheses.json: thesis.json aktualisieren (current, confidence, alternatives, contradiction_summary, entity_ids aus connect/entity_graph.json)
7. connect_status.json auf true gesetzt (entity_extract_ok, contradiction_ok, hypothesis_ok, thesis_updated)
8. advance_phase "verify"

### Abhängigkeiten / Risiken

| Punkt | Risiko | Einschätzung |
|-------|--------|--------------|
| research_entity_extract | Kein || true → jeder Fehler/Timeout bricht Connect | Gewollt („entity_extract failure fails the phase“) |
| log.txt | connect.sh schreibt in $PWD/log.txt (Job-Verzeichnis), nicht in PROJ_DIR/log.txt | Abweichung zu restlichem Cycle (CYCLE_LOG = PROJ_DIR/log.txt); bei getrenntem Job trotzdem auffindbar |
| research_reason | contradiction_detection / hypothesis_formation mit timeout 300 | Bei Timeout/Fehler || true → Connect läuft weiter, thesis ggf. leer/alt |

Funktioniert: Ja, sofern OpenAI verfügbar und entity_extract durchläuft. Bei fehlendem OpenAI wird Projekt sauber auf failed_dependency gesetzt.

---

## Phase: VERIFY

### Ablauf

1. progress_start "verify"
2. source_reliability (timeout 300, Retry nach 30s bei Fehler) → ART + PROJ_DIR/verify/
3. claim_verification (timeout 300, Retry) → ART + PROJ_DIR/verify/
4. fact_check (timeout 300, Retry) → ART + PROJ_DIR/verify/
5. Optional: research_verify claim_verification_cove (RESEARCH_ENABLE_COVE_VERIFICATION=1)
6. claim_ledger (timeout 300) → ART + PROJ_DIR/verify/
7. Optional: claim_state_machine, contradiction_linking, falsification_gate (Welle 3 Flags)
8. Counter-evidence: Top-3 verified claims → Suchanfragen, research_web_search (einzelne Query + --max 3), neue sources, parallel_reader counter, research_reason contradiction_detection
9. research_quality_gate (timeout 300) → GATE_RESULT, GATE_PASS
10. Wenn GATE_PASS≠1: Recovery (wenn unread sources, .recovery_attempted fehlt): Rank unread, parallel_reader recovery, erneut claim_verification + claim_ledger + quality_gate
11. Wenn weiterhin fail: pending_review (wenn decision pending_review) oder gap_analysis → LOOP_BACK (deepening_queries.json, advance_phase "focus") oder GATE_FAIL (status/phase/fail_code, abort_report, Brain reflect, distiller, utility_update, persist_v2_episode)
12. Wenn GATE_PASS=1: evidence_gate in project.json passed, low-reliability in sources markieren, research_source_credibility, optional AEM settlement, optional discovery_analysis (discovery mode), advance_phase "synthesize"

### Abhängigkeiten / Risiken

| Punkt | Risiko | Einschätzung |
|-------|--------|--------------|
| research_web_search im Counter-Block | Aufruf mit einem String q; research_web_search unterstützt "query" [--max N] | OK (Zeile 996: query, "--max", "3") |
| parallel_reader recovery | Mode "recovery" existiert (read_limit min(limit,10)) | OK |
| research_quality_gate | Liest explore/read_stats.json, verify/claim_ledger, verify/source_reliability; calibrator wenn ≥10 Outcomes | focus/read_stats wird nicht geladen; Gate nutzt _load_explore_stats nur (explore/read_stats). Focus-Reads zählen in Gate-Metriken über claim_ledger/sources, nicht über focus/read_stats. | Prüfung: quality_gate nutzt findings_count, unique_source_count, verified_claim_count aus claim_ledger/source_reliability → OK |
| AEM settlement | research_aem_settlement.py, research_claim_outcome_schema, research_episode_metrics müssen existieren | Wenn nicht vorhanden, Block wird übersprungen (if -f ...). Wenn enforce/strict und aem_result nicht ok → advance_phase nicht, AEM_BLOCK gesetzt | OK |

Funktioniert: Ja. Recovery und Loop-back zu Focus mit deepening_queries sind verbunden. Evidence Gate ist zentrale Entscheidung vor Synthesize.

---

## Phase: SYNTHESIZE

### Ablauf

1. progress_start "synthesize"
2. timeout 1800 research_synthesize.py → ART/report.md (stderr → CYCLE_LOG); print(report, flush=True) bereits eingebaut
3. research_synthesize_postprocess.py $PROJECT_ID $ART → report.md + proj/reports/report_*.md, claim_evidence_map, manifest; body_ok &lt; 500 Zeichen → kein Schreiben, return False
4. research_critic critique "$ART" → critique.json (timeout 600, bei leer Retry nach 15s)
5. SCORE aus critique.json; CRITIC_THRESHOLD aus Memory oder Default 0.50 (frontier 0.50); MAX_REVISE_ROUNDS (Memory oder 2)
6. FORCE_ONE_REVISION wenn weaknesses "unvollständig"/"bricht ab"/"fehlt"
7. Schleife: wenn SCORE &lt; CRITIC_THRESHOLD oder FORCE_ONE_REVISION → research_critic revise "$ART" → revised_report.md, kopieren nach report.md und reports/report_*_revisedN.md, erneut critique → neues SCORE
8. Wenn nach Schleife score &lt; threshold: quality_gate_status failed, fail_code failed_quality_gate, status/phase/completed_at gesetzt, abort_report, Brain reflect, distiller, utility_update, persist_v2_episode
9. Sonst: quality_gate in project.json (critic_score, quality_gate_status), persist_v2_episode "done", advance_phase "done"

### Abhängigkeiten / Risiken

| Punkt | Risiko | Einschätzung |
|-------|--------|--------------|
| research_synthesize timeout 1800 | 30 Min; bei sehr langem Report theoretisch noch Kill | flush=True verhindert Datenverlust bei Kill; 30 Min reicht für die meisten Reports |
| research_synthesize_postprocess | Liest ART/report.md; body_ok &lt; 500 → kein Schreiben, WARN, return 1 | Verhindert „nur References“-Report. Aufruf in research-cycle.sh mit „or true“ → Rückgabewert ignoriert. Bei body nicht ok: reports/ bleibt leer, Critic läuft trotzdem auf ART/report.md (ggf. leer) → score 0 → Revision → 429-Risiko. | **Empfehlung:** Bei postprocess exit 1 Critic überspringen, status=failed_quality_gate, fail_code=failed_synthesis_empty_report setzen. |
| research_critic | Nutzt llm_call (5 Retries, Backoff). 429: bei „insufficient_quota“ kein Retry (schneller Fehler); bei Rate-Limit (RPM) Retries. Nach Ausschöpfen → score 0, Revision schlägt fehl | Wenn Quota nie erreicht: 429 oft Rate-Limit (RPM) → Retries helfen; research_common._is_retryable unterscheidet Quota (nicht retry) vs Rate-Limit (retry) |

Funktioniert: Ja, wenn Synthese genug Body liefert und Critic/Revision API zur Verfügung stehen. Leerer Report wird nicht mehr als final gespeichert; Timeout und Flush sind abgesichert.

---

## advance_phase, Conductor-Gate, Evidence Gate, Critic (Querschnitt)

### advance_phase (alle Phasen)

- Conductor gate: `research_conductor gate "$PROJECT_ID" "$next_phase"` wenn RESEARCH_CONDUCTOR_GATE=1 und RESEARCH_USE_CONDUCTOR≠1.
- Wenn conductor_next leer → Phase nicht wechseln (bleibt aktuell).
- Wenn conductor_next ≠ next_phase → Override (z. B. focus → explore), RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1.
- research_advance_phase.py "$PROJ_DIR" "$next_phase": phase_history append, phase_timings, loop_count &gt; 3 → nächste Phase (außer bei SKIP_LOOP_LIMIT), bei "done" status=done, completed_at. Terminal-Status (failed*, cancelled, abandoned) werden nicht überschrieben.

Risiko: Conductor gate liefert leer bei Tool-Fehler → Phase bleibt stehen. Kein endlos-Loop: loop_count &gt; 3 erzwingt nächste Phase (wenn nicht SKIP_LOOP_LIMIT).

### Evidence Gate (Verify → Synthesize)

- Tool: research_quality_gate.py (tools/research_quality_gate.py). Liest explore/read_stats.json, verify/claim_ledger, verify/source_reliability; EVIDENCE_GATE_THRESHOLDS (findings_count_min 8, unique_source_count_min 5, verified_claim_count_min 2, claim_support_rate_min 0.5, high_reliability_source_ratio_min 0.5). Adaptive: HARD_PASS_VERIFIED_MIN=5, SOFT_PASS_VERIFIED_MIN=3, REVIEW_ZONE_RATE=0.4, HARD_FAIL_RATE=0.3. Calibrator überschreibt bei ≥10 Outcomes.
- Ergebnis: GATE_PASS=1 → advance_phase "synthesize"; sonst Recovery oder pending_review oder Loop-back (deepening_queries) oder GATE_FAIL (status/abort_report/Brain/distiller/utility_update).

### Critic (Synthesize)

- research_critic.py critique "$ART" → critique.json (score, weaknesses). research_critic revise "$ART" → revised_report.md. RESEARCH_CRITIQUE_MODEL (z. B. gpt-5.2). Threshold aus RESEARCH_MEMORY_CRITIC_THRESHOLD oder 0.50; frontier mode fest 0.50. MAX_REVISE_ROUNDS aus Memory oder 2. FORCE_ONE_REVISION bei Weaknesses „unvollständig“/„bricht ab“/„fehlt“. Nach Schleife: score &lt; threshold → failed_quality_gate, abort_report, Brain, distiller, utility_update, persist_v2_episode; sonst quality_gate in project.json, advance_phase "done".

---

## Tools – Vorhandenheit

Alle genannten Tools vorhanden: research_planner, research_parallel_reader, research_deep_extract, research_web_search, research_coverage, research_saturation_check, research_entity_extract, research_reason, research_verify, research_quality_gate, research_synthesize, research_critic, research_advance_phase, research_knowledge_seed, research_question_graph, research_academic, research_experience_distiller, research_utility_update, research_abort_report, research_preflight. research_synthesize_postprocess vorhanden und mit body_ok-Guard.

---

## Kurz-Bewertung pro Phase

| Phase | Umgesetzt | Wird funktionieren | Offene Punkte |
|-------|-----------|---------------------|---------------|
| Explore | Ja | Ja | 429 bei Search/Academic → weniger Quellen; kein Retry |
| Focus | Ja | Ja | deepening_queries eingebaut; ohne Coverage nur „weiter lesen“ |
| Connect | Ja | Ja | entity_extract hart; Log in Job-PWD |
| Verify | Ja | Ja | Recovery und Gate-Logik konsistent |
| Synthesize | Ja | Ja | Postprocess verhindert leeren Report; Critic 429 weiterhin möglich |

Gesamt: Pipeline ist konsistent umgesetzt und wird unter normalen Bedingungen (API erreichbar, Quota) durchlaufen. Bekannte Grenzfälle: OpenAI-Quota (Critic/Revision), Timeout bei sehr langen Reports (bereits entschärft), fehlende Coverage bei getrennten Jobs (Focus degradiert sauber).

---

## 429 vs. Quota (Klärung)

- **429** kann bedeuten: (1) **Rate Limit** (Requests pro Minute) oder (2) **Quota** (Token-/Dollar-Limit).
- **research_common.llm_call**: 5 Retries mit exponentiellem Backoff. `_is_retryable()`: bei Meldung „insufficient_quota“ / „quota exceeded“ wird **nicht** erneut versucht (schneller Fehler, klare Logs). Bei reinem Rate-Limit (RPM) werden Retries durchgeführt.
- Wenn ihr **Quota nie erreicht** habt, ist 429 oft **Rate-Limit** (zu viele Anfragen in kurzer Zeit) → Retries sind sinnvoll. Prüft in CYCLE_LOG/Stderr, ob die API-Meldung „rate_limit“ oder „insufficient_quota“ enthält.
