# Operator-System: Tiefenverständnis

Technisches Deep-Dive für alle, die das System erweitern, debuggen oder integrieren wollen. Ergänzt `OPERATOR_SYSTEM_OVERVIEW.md` (Phasen, Steuerung) um Ablauf, State, Locking, Conductor, Gates und Datenfluss.

---

## 1. Architektur-Überblick

- **Operator Root** (`OPERATOR_ROOT`, typ. `/root/operator`): Alle Skripte, Tools, Research-Daten, Jobs, Config.
- **Jobs** (`operator/jobs/YYYY-MM-DD/<job_id>/`): Pro Workflow-Lauf ein Verzeichnis mit `job.json`, `artifacts/`, `log.txt`. Erstellt durch `op job new --workflow <id> --request <text>`.
- **Research-Projekte** (`operator/research/<project_id>/`): Ein Projekt pro Forschungsfrage. State in `project.json`; Artefakte in `findings/`, `sources/`, `verify/`, `reports/` usw.
- **Workflows** (`operator/workflows/*.sh`): Bash-Skripte. Eintritt: `op run <job_dir>` → ausgeführt mit `cwd=job_dir`, `OPERATOR_ROOT` gesetzt. `research-phase.sh` ist der Kern einer Research-Phase; `research-cycle.sh` ist nur ein Wrapper um `run-research-cycle-until-done.sh`.

Kernfluss Research:

1. **Init:** `research-init.sh` erstellt `research/<project_id>/`, schreibt `project.json` (phase=explore, status=active), optional Knowledge-Seed.
2. **Cycle-Runner:** `run-research-cycle-until-done.sh` loop: liest `project.json` (phase, status) → startet **einen** Job `research-phase` mit Request=project_id → `op run` (blockierend) → wiederholt bis status/phase terminal oder MAX_RUNS/Stuck.
3. **Pro Phasen-Lauf:** `research-phase.sh` wird im Job-Kontext ausgeführt (Request=project_id aus job.json). Liest Phase aus `project.json`, führt die entsprechende Phasen-Logik aus, ruft `advance_phase` auf, am Ende `mark_waiting_next_cycle` und ggf. Council/June/Brain.

---

## 2. Job-Modell (`bin/op`)

- **`op job new --workflow <id> --request <text>`:** Legt `jobs/<today>/<uuid>/` an, schreibt `job.json` (workflow_id, request, status=CREATED, timeout_s). Für `research-cycle` ist timeout_s = None. Gibt Job-Pfad aus (stdout).
- **`op run <job_dir|job_id>`:** Holt Job-Lock (Datei-Lock), setzt status=RUNNING, führt `workflows/<workflow_id>.sh` mit `cwd=job_dir` aus. Bei Timeout (falls gesetzt) → subprocess.TimeoutExpired → Job FAILED. Exit-Code des Skripts → job.json exit_code, duration_s, status=FAILED|DONE.
- **research-cycle:** Wird von UI/June/Brain oft **ohne** `op job new` für research-cycle gestartet: direkt `run-research-cycle-until-done.sh <project_id>` im Hintergrund. Dieses Skript erzeugt **pro Phase** einen neuen Job: `op job new --workflow research-phase --request <project_id>` und führt `op run <job_dir>` aus. Es gibt also viele research-phase-Jobs, keinen einzelnen „research-cycle“-Job (außer man startet explizit einen research-cycle-Job).

---

## 3. Research State

### 3.1 project.json

- **id, question, status, phase, created_at, completed_at**
- **config:** max_sources, max_findings, **research_mode** (standard|frontier|discovery)
- **phase_history:** Liste der durchlaufenen Phasen (für loop_count, Conductor)
- **phase_timings:** { phase: { started_at, completed_at, duration_s } }
- **quality_gate:** evidence_gate (status, decision, fail_code, metrics), last_evidence_gate_at
- **council_status:** active | done | waiting (für Council V2)
- **parent_project_id:** bei Follow-up-Projekten
- **waiting_reason:** gesetzt von `mark_waiting_next_cycle`

Status-Werte: active, waiting_next_cycle, done, pending_review, failed_*, cancelled, abandoned, aem_blocked, paused_rate_limited, FAILED_BUDGET_EXCEEDED.

### 3.2 progress.json (Live-Lauf)

- **pid, alive, heartbeat, phase, step, step_started_at, step_index, step_total**
- **steps_completed:** [{ ts, step, duration_s }]
- **active_steps:** laufende Teilschritte
- **started_at**

Gesetzt von `research_progress.py` (start/step/done). Beim Start einer Phase: `progress_start "explore"` usw.; während der Phase: `progress_step "message"`. Beim Verlassen von research-phase.sh (EXIT-Trap): wenn progress gestartet aber nicht finalized → `progress_done phase "Idle"`. `alive=false` am Ende des Laufs.

### 3.3 Projekt-Lock (`.cycle.lock`)

- **Nur ein research-phase-Lauf pro Projekt gleichzeitig.** In `lock_and_progress.sh`: `flock -n 9` auf `$PROJ_DIR/.cycle.lock`. Bei Nicht-Verfügbarkeit: Prüfung auf Recovery (alter pid nicht mehr in /proc oder progress.alive=false) → Lock löschen und erneut versuchen; sonst exit 2. Exit 2 wird von run-research-cycle-until-done als „skipped, other cycle running“ behandelt (run-Zähler zurück, kein Stuck).

---

## 4. research-phase.sh: Ablauf im Detail

Reihenfolge (gekürzt):

1. **config.sh** — Pfade, PROJECT_ID, PROJ_DIR, PHASE aus project.json, QUESTION, Memory-Strategy (memory_strategy.json), Env (RESEARCH_*).
2. **lock_and_progress.sh** — Terminal-Status-Guard (failed/cancelled/abandoned → exit 0). Projekt-Lock (.cycle.lock). Trap: beim EXIT progress finalisieren und Lock freigeben.
3. **helpers.sh** — advance_phase, mark_waiting_next_cycle, persist_v2_episode, log_v2_mode_for_cycle.
4. **SET_ACTIVE** — Wenn phase != done und Status nicht terminal: status=active, waiting_reason entfernen (damit UI nicht „Waiting for next cycle“ während des Laufs zeigt).
5. **Pause-on-Rate-Limit** — Bei status=paused_rate_limited: 30-Min-Cooldown prüfen; danach status=in_progress.
6. **Budget** — research_budget.py check; bei Überschreitung status=FAILED_BUDGET_EXCEEDED, exit 0.
7. **Memory v2** — log_v2_mode_for_cycle (Observability).
8. **Conductor (optional)** — Wenn RESEARCH_USE_CONDUCTOR=1: `research_conductor.py run_cycle`; bei Erfolg „done“ und exit 0. Bei Fehler (z. B. failed_conductor_tool_errors) persist_v2_episode, exit 0.
9. **Shadow Conductor** — Wenn Conductor nicht Master: shadow-Aufruf nur zum Loggen.
10. **case PHASE** — explore|focus|connect|verify|synthesize|done: jeweiliges Skript aus `workflows/research/phases/*.sh` sourcen. Connect/Verify/Synthesize rufen intern `progress_start`/`progress_step` und am Ende `advance_phase "next_phase"` auf (explore/focus ebenfalls).
11. **mark_waiting_next_cycle** — Wenn nicht terminal: status=waiting_next_cycle, waiting_reason setzen.
12. **Council** — trigger_council.py (Discovery nur bei status=done; Standard auch bei done/failed/aem_blocked).
13. **Control-Plane Completion Event** — `research-phase.sh` schreibt ein strukturiertes `research_cycle_completed`-Event in Projekt- und Global-Event-Logs. Keine ad-hoc `last_research_complete.json`-Steuerdatei mehr.
14. **Brain Consumption** — der Brain kann den letzten Control-Plane-Event im Perceive-State sehen, wird aber nicht mehr direkt von `research-phase.sh` als globaler Folge-Orchestrator gestartet.

---

## 5. run-research-cycle-until-done.sh: Loop-Logik

- Liest zu Beginn jeder Iteration phase und status aus project.json.
- **Terminal:** done → exit 0; pending_review → exit 0; failed*/cancelled/abandoned/aem_blocked → exit 1.
- **Stuck-Erkennung:** Wenn phase == last_phase, same_phase_count erhöhen. Bei same_phase_count >= MAX_SAME_PHASE (3): status=failed_stuck_phase setzen, progress.json alive=false, exit 1.
- **Job starten:** `op job new --workflow research-phase --request "$PROJECT_ID"` → job_dir; `op run "$job_dir"` (blockierend). Exit 2 (Lock gehalten) → run und same_phase_count zurücksetzen, sleep 2, continue.
- MAX_RUNS=10; nach 10 Läufen ohne Terminal → exit 1.

---

## 6. advance_phase und Conductor-Gate

- **Aufruf:** Aus den Phasen-Skripten mit z. B. `advance_phase "focus"` oder `advance_phase "synthesize"`.
- **research_advance_phase.py:** Schreibt project.json: phase_history.append(next_phase), phase_timings für vorherige Phase, phase=next_phase, last_phase_at. Bei phase=done zusätzlich status=done, completed_at. **Loop-Bremse:** Wenn phase_history.count(new_phase) > 3 und RESEARCH_ADVANCE_SKIP_LOOP_LIMIT != 1, wird stattdessen die nächste Phase in der Reihenfolge gesetzt (explore→focus→connect→…).
- **Conductor-Gate (helpers.sh):** Wenn RESEARCH_CONDUCTOR_GATE=1 und RESEARCH_USE_CONDUCTOR!=1: vor dem Advance ruft advance_phase `research_conductor.py gate "$PROJECT_ID" "$next_phase"` auf. Conductor liefert entweder next_phase (durchlassen) oder eine andere Phase (z. B. explore für eine weitere Runde). **Discovery-Guard:** Bei focus→explore-Override prüft ein Python-Block: Discovery-Modus und findings_count>=6 und source_count>=4 → Override blockieren (0 ausgeben). Sonst Override erlauben (z. B. bei dünner Coverage). Bei Override: progress_step „Conductor: weitere …-Runde“, RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1 exportieren, damit die Loop-Bremse in research_advance_phase nicht greift.

Conductor gate_check (research_conductor.py): Liest State (findings_count, source_count, coverage_score, verified_claims, budget_spent_pct, steps_taken). Discovery: explore→focus erlaubt bei findings>=6, sources>=4; synthesize nur bei findings>=15, sources>=8 (Env). Bei budget_spent_pct>=0.8 oder max Overrides pro Transition → immer durchlassen. Sonst LLM decide_action (search_more, read_more, verify, synthesize); wenn Aktion != erwartete Aktion für next_phase → Override (andere Phase zurückgeben), _save_override.

---

## 7. Conductor run_cycle (RESEARCH_USE_CONDUCTOR=1)

- Conductor ist dann der Master: research-phase.sh ruft nur noch `research_conductor.py run_cycle` auf; Bash-Phasen (case) werden nicht ausgeführt.
- run_cycle: Loop bis MAX_STEPS oder phase=done/failed. State lesen, action = decide_action(…). Aktionen:
  - **synthesize:** research_synthesize.py, Report schreiben, postprocess, critic, advance_phase done, return True.
  - **verify:** research_verify (source_reliability, claim_verification, fact_check, claim_ledger), research_quality_gate; bei Pass advance_phase synthesize.
  - **read_more:** Unread sources → research_parallel_reader, research_deep_extract, coverage, ggf. dynamic_outline, supervisor.
  - **search_more:** research_planner, research_web_search, Quellen speichern, research_parallel_reader, research_deep_extract, coverage.
- Nach MAX_CONSECUTIVE_TOOL_FAILURES Fehlern: status=failed_conductor_tool_errors, return False.

---

## 8. Evidence Gate (Verify-Phase)

- **Ort:** verify.sh nach claim_ledger, optional CoVe/Claim-State-Machine/Contradiction/Falsification. `research_quality_gate.py "$PROJECT_ID"` → JSON { pass, decision, fail_code, metrics, reasons }.
- **Modi (research_quality_gate.py + research_mode):**
  - **Standard:** Pass bei ausreichend verified_claim_count + claim_support_rate; pending_review in Review-Zone; Fail bei zu wenig Evidence.
  - **Frontier:** Eine autoritative Quelle kann für verified zählen; Pass auch bei findings/sources/reliability-Schwelle.
  - **Discovery:** Kein verified_claim-Zwang; Pass bei findings/sources (z. B. 6/4 oder 10/8); pending bei geringerer Schwelle.
- **Bei Gate Fail (decision=fail):** pending_review möglich → status=pending_review, quality_gate.evidence_gate schreiben, exit 0. Sonst: gap_analysis, LOOP_BACK-Check (high-priority Gaps, phase_history focus-count < 2): Wenn ja → deepening_queries.json schreiben, advance_phase focus, exit 0. Sonst: status=fail_code, phase=failed, quality_gate schreiben, completed_at, abort_report, Brain-Reflection, experience_distiller, utility_update, persist_v2_episode.
- **Bei Pass:** quality_gate.evidence_gate status=passed, Discovery Analysis (nur discovery), advance_phase synthesize.

---

## 9. Council (trigger_council.py)

- Wird am Ende von research-phase.sh aufgerufen (nach mark_waiting_next_cycle).
- **Discovery:** Nur wenn status=done (nie bei failed_quality_gate o. ä.).
- **Standard:** Bei done, done-Phase, failed*, aem_blocked.
- **Parent:** Wenn Projekt kein parent_project_id hat und Status/Phase terminal → council_status prüfen; wenn bereits active/done/waiting → exit 0. Sonst council_status=active setzen, research_council.py im Hintergrund starten.
- **Child:** Wenn alle Geschwister terminal → Parent prüfen, dann Council auslösen (einmal pro Parent-Completion).

---

## 10. Init und Einstiege

- **research-init.sh:** Request = Frage oder JSON { question, research_mode, hypothesis_to_test }. Erstellt project_id (proj-YYYYMMDD-hex), project.json (phase=explore, status=active), questions.json, thesis.json. research_knowledge_seed optional. Schreibt project_id nach artifacts/project_id.txt.
- **UI „Forschung starten“ (run_until_done=true):** runResearchInitAndCycleUntilDone → op job new research-init, op run (Timeout 120s), project_id aus artifacts lesen, spawnResearchCycleUntilDone(projectId).
- **UI „Research fortsetzen“:** POST cycle → runWorkflow("research-cycle", id) = spawnResearchCycleUntilDone(id).
- **June /research-cycle:** run-research-cycle-until-done.sh im Hintergrund (detached), kein Timeout.
- **Brain:** Darf nur research-cycle (project_id), kein research-init. Startet op run für research-cycle-Job im Hintergrund (kein Timeout). Council-Wartezeit: Bei council_status active/waiting und council_children_running > 0 kein research-cycle für Parent vorschlagen.

---

## 11. UI/API Datenfluss

- **Projektliste/Detail:** API liest research/<id>/project.json (und ggf. phase_timings, quality_gate, reports). getResearchProject(id) → ResearchProjectDetail.
- **Progress (Live):** GET /api/research/projects/[id]/progress liest progress.json (alive, phase, step, heartbeat). UI zeigt RUNNING/IDLE/STUCK; „Waiting for next cycle“ nur wenn status=waiting_next_cycle und nicht durch aktiven Lauf überschrieben (nach Fix: status wird zu Beginn jeder Phase auf active gesetzt).
- **Cycle starten:** POST .../cycle → runWorkflow("research-cycle", id) → spawnResearchCycleUntilDone(id). Projekt-Lock in API: 409 wenn bereits ein Cycle läuft (prüft Lock oder progress.alive).

---

## 12. Wichtige Dateien und Referenzen

| Bereich | Dateien |
|--------|--------|
| Phase-Orchestrierung | workflows/research-phase.sh, workflows/research/lib/config.sh, lock_and_progress.sh, helpers.sh |
| Cycle-Loop | tools/run-research-cycle-until-done.sh, workflows/research-cycle.sh |
| Phasen | workflows/research/phases/explore.sh, focus.sh, connect.sh, verify.sh, synthesize.sh |
| Advance & Gate | tools/research_advance_phase.py, tools/research_conductor.py (gate_check, run_cycle), tools/research_quality_gate.py |
| Progress | tools/research_progress.py, progress.json, events.jsonl |
| Council | tools/trigger_council.py, tools/research_council.py |
| Init | workflows/research-init.sh |
| Jobs | bin/op, jobs/<date>/<id>/job.json |
| UI | ui/src/lib/operator/actions.ts (runWorkflow, spawnResearchCycleUntilDone, runResearchInitAndCycleUntilDone), api/research/projects/route.ts, [id]/cycle/route.ts |

---

## 13. Fehler- und Stuck-Szenarien

- **failed_stuck_phase:** run-research-cycle-until-done erkennt gleiche phase über MAX_SAME_PHASE Runs → setzt status, exit 1.
- **failed_conductor_tool_errors:** Conductor run_cycle nach MAX_CONSECUTIVE_TOOL_FAILURES.
- **Evidence-Gate-Fail:** failed_insufficient_evidence (oder anderer fail_code), ggf. Loop-back zu focus mit deepening_queries (max 2×).
- **Lock vergeben:** Neuer research-phase-Lauf bekommt Lock nicht → exit 2; run-research-cycle-until-done zählt nicht als Stuck, versucht später erneut.
- **Stale Lock:** Lock vorhanden, aber pid tot oder progress.alive=false → Lock gelöscht, neuer Lauf übernimmt.

Diese Doku mit Code abgleichen bei Änderungen an Ablauf, Gates oder State (siehe docs-sync-with-code Regel).
