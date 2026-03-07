# Refactoring-Plan: workflows/research-phase.sh

**Ziel:** Die ~1955 Zeilen starke Research-Pipeline in klare, wartbare Module aufteilen, **ohne bestehendes Verhalten zu ändern**. Nach dem Refactor muss alles weiterlaufen (gleicher Einstieg, gleiche Jobs, gleiche Tests).

---

## 1. Ausgangslage

| Aspekt | Aktuell |
|--------|--------|
| **Einstieg** | `workflows/research-phase.sh` — aufgerufen via `op job new --workflow research-phase --request <project_id>` |
| **Aufrufer** | `run-scheduled-research.sh`, `run-research-over-days.sh`, `run-research-cycle-until-done.sh` |
| **Inhalt** | Setup, Lock, alle 5 Phasen (explore → synthesize), Conductor, AEM, Experiment, Council, PDF, Progress |
| **Inline Python** | ~176 Aufrufe (`python3 -c`, `python3 -`, `python3 "$TOOLS/..."`) |
| **Bestehende Auslagerung** | `workflows/research/phases/connect.sh` wird bereits per `source` eingebunden |

**Vertrag, der unverändert bleiben muss:**

- Job: `job.json` mit `request` = project_id; Skript läuft im Job-Verzeichnis mit `job.json`, `artifacts/`.
- Projekt: `research/<project_id>/project.json` (phase, status, quality_gate, …), Lock `research/<project_id>/.cycle.lock`, Progress `research_progress.py`.
- Exit: Skript endet mit `echo "done"`; Trap räumt Lock und Progress auf.

---

## 2. Prinzipien

1. **Ein Einstieg bleibt:** `workflows/research-phase.sh` bleibt die einzige Datei, die von `op` als Workflow-Skript ausgeführt wird. Keine Umstellung von `research-phase` auf ein anderes Skript.
2. **Keine Logik-Änderung:** Nur Verschieben und Auslagern; gleiche Reihenfolge, gleiche Env-Variablen, gleiche Aufrufe. Keine neuen Features, keine „Verbesserungen“ der Abläufe.
3. **Shared State per `source`:** Alle Phasen-Skripte werden mit `source` eingebunden, damit sie dieselben Variablen und Funktionen (z. B. `log`, `progress_step`, `advance_phase`) nutzen.
4. **Inline-Python reduzieren:** Längere Python-Blöcke in aufrufbare Python-Tools oder `workflows/research/lib/*.py` auslagern; Aufruf aus Bash bleibt semantisch gleich (gleiche Inputs/Outputs).

---

## 3. Zielstruktur (Übersicht)

```
workflows/
  research-phase.sh              # Dünner Einstieg: Config + Lock + Dispatch + Post-Cycle
  research/
    lib/
      config.sh                   # Pfade, Env, Phase lesen, Memory-Strategy, Guards (Terminal-Status, Cooldown, Budget)
      lock_and_progress.sh        # Lock-Akquisition, progress_*, trap finalize_progress_on_exit
      helpers.sh                  # log, advance_phase, mark_waiting_next_cycle, persist_v2_episode, log_v2_mode_for_cycle
    phases/
      connect.sh                  # (existiert bereits)
      explore.sh                  # komplette Explore-Phase
      focus.sh                    # komplette Focus-Phase
      verify.sh                   # komplette Verify-Phase inkl. Gate, AEM, loop-back
      synthesize.sh               # Synthese, Critic, PDF, Experiment, done-Nachbearbeitung
tools/
  research_phase_*.py             # Neue kleine Skripte für ausgelagerte Inline-Python-Logik (siehe 5.)
```

**research-phase.sh** wird in etwa so aufgebaut:

```bash
#!/usr/bin/env bash
set -euo pipefail
OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
export OPERATOR_ROOT
# 1) Request/Project aus job.json
# 2) source config.sh   → PROJECT_ID, PROJ_DIR, ART, PHASE, alle RESEARCH_* Env, Guards
# 3) source lock_and_progress.sh
# 4) Terminal-Status-Guard, Cooldown, Budget, log_v2_mode_for_cycle
# 5) Conductor (master / shadow)
# 6) case "$PHASE" in explore|focus|connect|verify|synthesize|done|*) → source phases/<phase>.sh
# 7) mark_waiting_next_cycle, Council, Ping June, Brain, echo "done"
```

---

## 4. Schritte (Reihenfolge einhalten)

### Phase A: Vorbereitung (ohne Verhalten zu ändern)

- **A1** Alle Stellen, die `research-phase.sh` aufrufen oder referenzieren, dokumentieren (bereits erledigt: `op` → `workflows/<workflow>.sh`, run-scheduled-research.sh, run-research-over-days.sh, run-research-cycle-until-done.sh).
- **A2** Bestehende Tests sichern und lokal durchlaufen lassen:
  - `tests/integration/test_research_phase_flow.py` (Phase advance explore → done)
  - Ggf. Bats-Tests unter `tests/` für research-phase/research-cycle
  - Ein manueller Durchlauf mit einem Test-Projekt (z. B. `op job new --workflow research-phase --request <test_project_id>` und Prüfung von phase/status/artifacts).
- **A3** Optional: Snapshot der aktuellen research-phase.sh (z. B. Tag/Branch) für einfachen Rollback.

### Phase B: Gemeinsame Scripts erstellen (source’bar)

- **B1** `workflows/research/lib/config.sh`  
  Inhalt aus Zeilen 1–131 (OPERATOR_ROOT, TOOLS, RESEARCH, ART, PROJECT_ID, REQUEST, PROJ_DIR, CYCLE_LOG, SECRETS, POLICY, alle RESEARCH_* Exporte, IS_FOLLOWUP, WORKERS, Proxy, PHASE, QUESTION, MEMORY_STRATEGY_FILE, Memory-V2-Env aus memory_strategy.json).  
  Am Ende: `log` definieren (oder in helpers.sh).  
  **research-phase.sh:** Nach Setzen von OPERATOR_ROOT und Auslesen von REQUEST/PROJECT_ID/PROJ_DIR: `source "$OPERATOR_ROOT/workflows/research/lib/config.sh"`.

- **B2** `workflows/research/lib/lock_and_progress.sh`  
  Inhalt: Zeilen 136–201 (Terminal-Status-Guard, _acquire_lock, Lock-Recovery, progress_start/step/done, finalize_progress_on_exit, trap).  
  Erwartet: PROJ_DIR, PROJECT_ID, CYCLE_LOG, PHASE, log.  
  **research-phase.sh:** Nach config.sh: `source "$OPERATOR_ROOT/workflows/research/lib/lock_and_progress.sh"`.

- **B3** `workflows/research/lib/helpers.sh`  
  Inhalt: `log` (falls nicht in config), `log_v2_mode_for_cycle`, `advance_phase`, `mark_waiting_next_cycle`, `persist_v2_episode`.  
  Erwartet: PROJ_DIR, PROJECT_ID, ART, TOOLS, OPERATOR_ROOT, CYCLE_LOG, PHASE, log, progress_*.  
  **research-phase.sh:** Nach lock_and_progress.sh: `source "$OPERATOR_ROOT/workflows/research/lib/helpers.sh"`.

Nach B1–B3: research-phase.sh so umbauen, dass es nur noch diese drei Dateien sourced und den bisherigen „Rest“ (Guards Cooldown/Budget, Conductor, case …) unverändert aus der alten research-phase.sh übernimmt. **Test:** Gleiche Tests wie vorher grün; ein Run pro Phase (explore/focus/connect/verify/synthesize) optional.

### Phase C: Phasen in eigene Skripte auslagern

- **C1** `workflows/research/phases/explore.sh`  
  Alles vom `explore)`-Zweig bis einschließlich `advance_phase "focus"` und `;;` (Zeilen 566–951).  
  Am Anfang: `progress_start "explore"`; erwartet: ART, PROJ_DIR, TOOLS, QUESTION, WORKERS, log, progress_*, advance_phase, alle RESEARCH_* Env.  
  **research-phase.sh:** `explore) source "$OPERATOR_ROOT/workflows/research/phases/explore.sh" ;;`

- **C2** `workflows/research/phases/focus.sh`  
  Alles vom `focus)`-Zweig bis einschließlich `source …/connect.sh` und `;;` (Zeilen 952–1114).  
  **research-phase.sh:** `focus) source "$OPERATOR_ROOT/workflows/research/phases/focus.sh" ;;`

- **C3** Connect bleibt wie heute: `connect) progress_start "connect"; source …/connect.sh ;;` bzw. Fokus-Zweig endet mit `progress_start "connect"; source …/connect.sh ;;`.

- **C4** `workflows/research/phases/verify.sh`  
  Kompletter `verify)`-Zweig (Zeilen 1116–1526): Reliability, Claim-Verification, Fact-Check, CoVe, Claim-Ledger, AEM, Evidence-Gate, Loop-Back, GATE_FAIL/BRAIN_REFLECT, persist_v2_episode, GATE_PASS, AEM-Block, Discovery, `advance_phase "synthesize"`.  
  **research-phase.sh:** `verify) source "$OPERATOR_ROOT/workflows/research/phases/verify.sh" ;;`

- **C5** `workflows/research/phases/synthesize.sh`  
  Kompletter `synthesize)`-Zweig (Zeilen 1528–1908): Outline, report, Discovery-Fallback, Critic, Revision-Loop, Quality-Gate (passed/failed), PDF, Experiment, embed, cross_domain, advance_phase "done", progress_done, Telegram, auto_followup, BRAIN_REFLECT, persist_v2_episode.  
  **research-phase.sh:** `synthesize) source "$OPERATOR_ROOT/workflows/research/phases/synthesize.sh" ;;`

- **C6** `done)` und `*)` bleiben in research-phase.sh (nur log / advance_phase "explore").

Nach C1–C6: research-phase.sh enthält nur noch Sourcing von config, lock_and_progress, helpers und den passenden phases/*.sh. **Test:** Wieder alle Integrationstests + ein vollständiger Lauf explore → done (oder bis zu einer bestimmten Phase).

### Phase D: Inline-Python auslagern (optional, schrittweise)

Jeder Block bleibt semantisch gleich; nur der Aufruf wechselt von `python3 -c "..."` / `python3 - <<'HEREDOC'` zu `python3 "$TOOLS/research_phase_<name>.py" ...` oder `python3 "$OPERATOR_ROOT/workflows/research/lib/<name>.py" ...`.

- **D1** Memory / V2:  
  - `log_v2_mode_for_cycle` → bereits in helpers.sh; der Python-Teil kann in `tools/research_phase_memory_v2_mode.py` (ProjDir, OpRoot, ProjectId, Phase) ausgelagert werden; helpers.sh ruft das Tool auf.  
  - `persist_v2_episode` → Python in `tools/research_phase_persist_episode.py` (ProjDir, OpRoot, ProjectId, run_status); helpers.sh ruft es auf.

- **D2** Conductor / advance_phase:  
  - Der Guard (coverage_pass, findings_count, source_count) in advance_phase als kleines Python-Skript (z. B. `tools/research_phase_conductor_guard.py`); advance_phase in helpers.sh ruft es auf.

- **D3** Evidence-Gate / Verify:  
  - PENDING_REVIEW, GATE_FAIL, GATE_PASS, loop-back (LOOPCHECK), BRAIN_REFLECT etc. als kleine CLI-Tools (z. B. `research_phase_project_status.py --pending-review`, `--gate-fail`, `--gate-pass`, `--loop-back`, `--brain-reflect`) mit gleichen Inputs (ProjDir, ggf. ART, Gate-Result).

- **D4** Synthesize:  
  - Discovery-Fallback, QG_DISCOVERY_SOFT, QF_FAIL, QG, MANIFEST_UPDATE, EXPERIMENT_GATE_*, OUTCOME_RECORD, BRAIN_REFLECT als einzelne kleine Skripte oder Subcommands, von synthesize.sh aufgerufen.

- **D5** Sonstige:  
  - Alle übrigen `python3 - "$PROJ_DIR" ... <<'...'` und längeren `python3 -c "..."` in tools oder workflows/research/lib auslagern; Bash behält nur kurze Aufrufe wie `VAR=$(python3 tool.py ...)`.

Nach D: research-phase.sh und alle phases/*.sh enthalten kaum noch mehrzeiliges Inline-Python; Verhalten weiter unverändert. **Test:** Erneut test_research_phase_flow.py + manueller Lauf.

### Phase E: Abschluss und Doku

- **E1** `docs/UI_OVERVIEW.md`, `RESEARCH_QUALITY_SLO.md`, `RESEARCH_AUTONOMOUS.md`, `SYSTEM_CHECK.md` prüfen: Verweise auf „research-phase.sh“ oder „research cycle“ ggf. um „research-phase.sh + workflows/research/lib + phases“ ergänzen, keine inhaltlichen Änderungen an Abläufen.
- **E2** `docs/MONOLITH_AND_LARGE_FILES.md` aktualisieren: research-phase.sh als „Dispatcher ~150 Zeilen“, neue Struktur (lib/config.sh, lock_and_progress.sh, helpers.sh, phases/*.sh) eintragen.
- **E3** Kurze Kommentare in research-phase.sh: Welche Scripts werden wo gesourct; wo wird welche Phase ausgeführt.

---

## 5. Abhängigkeiten und Variablen (für phases/*.sh)

Jedes Phasen-Skript muss diese **gesetzt** vorfinden (kommen aus config.sh / lock_and_progress.sh / helpers.sh):

- `OPERATOR_ROOT`, `TOOLS`, `RESEARCH`, `ART`, `PROJ_DIR`, `PROJECT_ID`, `QUESTION`, `PHASE`, `CYCLE_LOG`
- `WORKERS`, `IS_FOLLOWUP`
- Alle `RESEARCH_*` Umgebungsvariablen (z. B. RESEARCH_ENABLE_*, RESEARCH_MEMORY_*, RESEARCH_CRITIC_THRESHOLD, …)
- Funktionen: `log`, `progress_start`, `progress_step`, `progress_done`, `advance_phase`, `persist_v2_episode` (für verify/synthesize)

Phasen-Skripte dürfen **keine** eigenen trap/EXIT-Handler setzen, die den zentralen finalize_progress_on_exit stören.

---

## 6. Verifikation („100 % sicher, dass danach alles geht“)

| Check | Aktion |
|-------|--------|
| Unit/Integration | `pytest tests/integration/test_research_phase_flow.py -v` |
| Bats (falls vorhanden) | Alle Research-/Phase-relevanten Bats-Tests ausführen |
| Einstieg unverändert | `op job new --workflow research-phase --request <project_id>` startet weiterhin `workflows/research-phase.sh` |
| Lock/Progress | Nach Abbruch/Kill: Lock wird freigegeben, progress wird finalisiert (bestehende Stale-Lock-Logik bleibt) |
| Phasenfolge | explore → focus → connect → verify → synthesize → done; project.json phase/status wie vorher |
| Artifacts | Gleiche Dateien in `research/<id>/` und ggf. Job-`artifacts/` wie vor dem Refactor |
| Council / June / Brain | Nach done/failed: Council-Trigger, last_research_complete.json, brain cycle wie bisher |

Empfehlung: Nach **Phase B** und nach **Phase C** jeweils die gleichen Checks laufen lassen; nach **Phase D** nur dann, wenn D tatsächlich umgesetzt wird.

**Verifizierung 2026-03-07:** Refactor umgesetzt. `pytest tests/integration/test_research_phase_flow.py` (2/2 passed), `research-phase.sh` mit ungültigem Projekt (exit 2), mit Testprojekt explore („staying in explore“), `op job new --workflow research-phase --request <id>` + `op run` (DONE, exit_code=0).

---

## 7. Rollback

- Falls nach einem Schritt etwas bricht: Aus dem Snapshot (A3) die ursprüngliche `workflows/research-phase.sh` wiederherstellen und die neuen Dateien (lib/*.sh, phases/explore.sh, focus.sh, verify.sh, synthesize.sh) vorübergehend nicht aufrufen.
- Wenn nur eine Phase fehlschlägt: Den entsprechenden case-Zweig in research-phase.sh wieder inline setzen (Inhalt aus dem ausgegliederten phases/*.sh kopieren) und das Phasen-Skript ignorieren.

---

## 8. Kurzfassung

- **Ein** Einstieg: `workflows/research-phase.sh` (Dispatcher).
- **Drei** gemeinsame Scripts: `config.sh`, `lock_and_progress.sh`, `helpers.sh`.
- **Fünf** Phasen-Skripte: `explore.sh`, `focus.sh`, `connect.sh` (bereits da), `verify.sh`, `synthesize.sh`.
- **Optional:** Inline-Python in kleine Python-Tools auslagern.
- **Nichts** am Job-Contract, an phase/status oder an Aufrufern ändern; Verifikation nach B und C durch Tests und einen vollständigen Lauf.

Damit ist der Refactor planbar, schrittweise und rückrollbar, ohne bestehende Abläufe zu brechen.

---

## 9. Zeilen-Referenz (research-phase.sh, Stand ~1956 Zeilen)

| Block | Zeilen (ca.) | Ziel |
|-------|--------------|------|
| Kopf + Request/Project + Env | 1–131 | config.sh |
| log, Terminal-Status, Lock, Progress, trap | 133–201 | lock_and_progress.sh |
| log_v2_mode_for_cycle | 202–257 | helpers.sh |
| Cooldown (pause-on-rate-limit) | 259–284 | in research-phase.sh nach config/lock/helpers |
| Budget Circuit Breaker | 286–306 | in research-phase.sh |
| log_v2_mode_for_cycle Aufruf | 307–308 | research-phase.sh |
| advance_phase | 309–372 | helpers.sh |
| mark_waiting_next_cycle | 374–400 | helpers.sh |
| persist_v2_episode | 402–544 | helpers.sh |
| Conductor master / shadow | 546–564 | research-phase.sh |
| case explore | 566–951 | phases/explore.sh |
| case focus | 952–1114 | phases/focus.sh |
| case connect | 1116–1118 | research-phase.sh (source connect.sh) |
| case verify | 1119–1526 | phases/verify.sh |
| case synthesize | 1528–1908 | phases/synthesize.sh |
| case done / * | 1909–1915 | research-phase.sh |
| mark_waiting_next_cycle, Council, Ping June, Brain | 1917–1956 | research-phase.sh |
