# Operator-System: Phasen, Ablauf, Steuerung

Übersicht über das Operator-System: **alle Phasen**, wie sie funktionieren und **wer sie steuern kann**. Quelle: Code + `UI_OVERVIEW.md`, `RESEARCH_QUALITY_SLO.md`, `RESEARCH_AUTONOMOUS.md`, `RESEARCH_MODES.md`, `TOOL_AGENT_SYSTEM_AUDIT.md`, `BRAIN_SYSTEM.md`, `SYSTEM_CHECK.md`.

---

## 1. Kernkonzept

- **Operator** = Job-Orchestrierung + Research-Pipeline + Brain + Memory. Daten: `OPERATOR_ROOT` (z. B. `/root/operator`).
- **Research** = ein Projekt pro Frage; State in `research/proj-*/project.json` (phase, status, config).
- **Phasen** laufen nacheinander: **explore → focus → connect → verify → synthesize → done** (oder failed/pending_review).
- Ein **research-cycle**-Lauf führt **eine** Phase aus (oder mehrere in einem Run bei same-run advance, z. B. focus→connect), dann wartet das Projekt auf den nächsten Cycle-Run.

---

## 2. Phasen im Detail

### 2.1 Phasenfolge und Verantwortung

| Phase      | Kurzbeschreibung | Haupt-Tools / Skripte | advance_phase → |
|-----------|------------------|------------------------|------------------|
| **explore** | Breite Suche: Plan, Web Search, Parallel Read, Coverage, ggf. Refinement/Gap/Depth, Read Stats | `research_planner.py`, `research_web_search.py`, `research_parallel_reader.py`, `research_coverage.py`, `research_saturation_check.py` | focus (oder Conductor-Override → explore) |
| **focus**  | Lücken füllen: Gap-Fill aus Coverage (+ ggf. verify/deepening_queries), Web Search, Parallel Read, Read Stats | `research_planner.py --gap-fill`, `research_web_search.py`, `research_parallel_reader.py` | connect |
| **connect** | Entity-Graph, Thesis, Widersprüche, Hypothese; Vorbereitung für Verify | `workflows/research/phases/connect.sh` → diverse Connect-Tools | verify |
| **verify** | Source Reliability, Claim Verification, Fact Check, Claim Ledger; **Evidence Gate**; ggf. Loop-back zu focus | `research_verify.py` (source_reliability, claim_verification, fact_check, claim_ledger), `research_quality_gate.py` | synthesize oder focus (bei Gate-Fail + Gaps) |
| **synthesize** | Report erzeugen, Postprocess, Critic, ggf. Experiment-Loop (Sandbox), Council-Trigger | `research_synthesize.py`, `research_synthesize_postprocess.py`, `research_critic.py`, `trigger_council.py` | done (oder failed_quality_gate / failed_experiment_gate / aem_blocked) |
| **done**   | Terminal: Report fertig, Council ggf. getriggert | — | — |

- **Conductor (optional):** Bei `RESEARCH_USE_CONDUCTOR=1` kann der Conductor vor `advance_phase` die nächste Phase überschreiben (z. B. focus → explore). Bash-Pipeline bleibt Master; Conductor-Gate in `research-phase.sh` → `research_conductor.py gate`.
- **Guards:** Kein advance zu focus/connect, wenn Explore/Focus keine verwertbare Evidenz produziert haben (No-Evidence-Guards). Verify → Focus Loop-back nur bei Evidence-Gate-Fail + high-priority Gaps (max 2×).

### 2.2 Wo die Phasenlogik liegt

- **Orchestrierung:** `workflows/research-phase.sh` (nicht `research-cycle.sh` – das ist nur ein Wrapper). Liest `project.json` → `PHASE`, führt `case "$PHASE" in explore|focus|connect|verify|synthesize|done)` aus, ruft Tools auf, ruft `advance_phase "next_phase"` auf.
- **Phasenwechsel:** `tools/research_advance_phase.py` schreibt `project.json` (phase, phase_history, phase_timings).
- **Cycle-until-done:** `tools/run-research-cycle-until-done.sh` loop: liest phase/status, startet **einen** Job `research-phase` mit Request=project_id, wartet auf Ende; wiederholt bis status ∈ {done, pending_review, failed*, cancelled, …} oder MAX_RUNS / stuck.

### 2.3 Research-Modi (project.json → config.research_mode)

- **standard:** Marktanalyse, Competitive Intel; Evidence Gate streng (verified claims, claim_support_rate).
- **frontier:** Akademisch; eine autoritative Quelle kann für VERIFIED reichen; Critic-Schwelle 0.50.
- **discovery:** Breite vor Tiefe; Evidence Gate ohne verified_claim-Zwang (findings/sources); Discovery Analysis vor Synthese; Critic **advisory** bei bestandenem Evidence Gate; Council nur bei status=done; Fallback-Report bei Synthese-Fehler; strikter Experiment-Gate (nur Sandbox-Crash/Timeout = failed_experiment_gate).

Details: `docs/RESEARCH_MODES.md`.

---

## 3. Wer kann was steuern?

### 3.1 Neues Projekt anlegen (research-init)

| Steuerung      | Wie | Hinweis |
|----------------|-----|--------|
| **UI**         | Research → „Neues Research-Projekt“ oder Discovery → „Discovery starten“ → `POST /api/research/projects` mit question, playbook_id, research_mode. Default: `run_until_done: true` → Init + `run-research-cycle-until-done.sh` im Hintergrund. | Standard: ein Klick = Init + alle Phasen bis done. |
| **Telegram (June)** | `/research-start "Frage"` oder `/research-go "Frage"` (go = Init + over-days). | June ruft `op job new --workflow research-init --request "…"` und ggf. `run-research-over-days.sh`. |
| **Brain (Captain)** | **Darf kein research-init starten.** Nur bestehende Projekte via `research-cycle` vorantreiben. | `lib/brain.py`: research-init aus erlaubten Aktionen gefiltert. |
| **Orchestrator** | `tools/run-research-orchestrator.sh` (Cron): LLM entscheidet aus done Reports + Sandbox → 0–3 neue Fragen → pro Frage `op job new research-init` + `run-research-cycle-until-done.sh` im Hintergrund. | June-Level-Autonomie. |
| **Auto-Follow-up** | Bei `RESEARCH_AUTO_FOLLOWUP=1`: wenn Projekt **done**, extrahiert „Suggested Next Steps“ aus Report → neue Projekte per research-init. | Pro Report bis zu RESEARCH_MAX_FOLLOWUPS (z. B. 3). |
| **Council**      | `trigger_council.py` (nach done, nur bei Discovery wenn status=done): erstellt Follow-up-Projekte aus Report → research-init + run-research-cycle-until-done. | Siehe `workflows/research-phase.sh` (nach done), `tools/trigger_council.py`. |
| **Experiment/Sub-Agent** | `research_experiment.py` kann research-init + research-cycle für Sub-Fragen starten. | Sub-Agent erstellt eigenes Projekt. |

### 3.2 Research fortsetzen (research-cycle / research-phase)

| Steuerung      | Wie | Hinweis |
|----------------|-----|--------|
| **UI**         | Projekt-Detail → „Research fortsetzen“ → `POST /api/research/projects/[id]/cycle` → `runWorkflow("research-cycle", id)`. Ein Cycle = **ein** Job research-cycle, der intern `run-research-cycle-until-done.sh` ausführt (mehrere research-phase-Runs bis terminal). | Projekt-Level-Lock: 409 wenn bereits ein Cycle für dieses Projekt läuft. |
| **Telegram**   | `/research-cycle <project_id>` startet **alle Phasen im Hintergrund** (`run-research-cycle-until-done.sh` detached, kein Timeout). `/research-go "Frage"` startet Init + `run-research-over-days.sh` (alle 6h ein Cycle, bis 14 Tage oder done). | Früher: 5‑Min-Timeout → Lauf endete nach ~1 Phase; jetzt Hintergrund wie UI. |
| **Brain**      | Darf **research-cycle** mit project_id ausführen (bestehende Projekte vorantreiben). Sieht offene Projekte in Perceive; schlägt Aktion research-cycle mit project_id vor. Council-Wartezeit: wenn project council_status active/waiting und council_children_running > 0 → kein research-cycle für dieses Parent vorschlagen. | `lib/brain.py`: research-init blockiert, research-cycle erlaubt. |
| **Cron (Scheduler)** | `tools/run-scheduled-research.sh` (z. B. alle 6h): für jedes Projekt mit phase ≠ done einen research-cycle-Job starten, nacheinander. | Autonom viele Projekte. |
| **run-research-cycle-until-done.sh** | Wird von UI (run_until_done), Telegram (/research-go), Orchestrator, Council, Experiment gestartet. Führt in einer Schleife `op job new --workflow research-phase --request project_id` + `op run` aus. | Ein Einstieg = viele research-phase-Runs bis done/failed. |
| **Conductor**  | Bei `RESEARCH_USE_CONDUCTOR=1`: Conductor **ist** der Master; ruft Tools per Subprocess auf, entscheidet nächste Aktion (search_more, read_more, verify, synthesize). Bash-Pipeline dann vereinfacht/ Fallback. | `tools/research_conductor.py` run_cycle. |

### 3.3 Projekt abbrechen (cancel)

| Steuerung | Wie |
|-----------|-----|
| **UI**    | Projekt-Detail → Abbrechen → `POST /api/research/projects/[id]/cancel` → `cancelResearchProject(id)` (Prozesse beenden, status=cancelled, laufende Jobs FAILED markieren). |
| **Skript** | `cancel_projects.py` (Prefix-basiert, setzt status=cancelled). |

### 3.4 Einzelne Aktionen ohne Phase (Feedback, PDF, etc.)

- **Feedback zu Finding:** UI oder Telegram → `POST /api/research/feedback` bzw. `/research-feedback <proj-id> <type> [comment]` → `research_feedback.py`.
- **PDF nachträglich:** UI Report-Tab → „Generate PDF“ → `research_pdf_report.py`.

---

## 4. Datenfluss: Wer ruft was auf

- **UI / API:** `runWorkflow(workflowId, request)` → `op job new --workflow <id> --request <request>` + bei research-cycle: `op run` (blockierend für einen Cycle), bei „Forschung starten“ mit run_until_done: `runResearchInitAndCycleUntilDone` → research-init warten → `run-research-cycle-until-done.sh` im Hintergrund.
- **OpenClaw (June):** `runOp(["job", "new", "--workflow", "research-init"|"research-cycle", "--request", ...])`, `runOp(["run", jobDir])`; bei /research-go: Init + `run-research-over-days.sh`.
- **Brain:** Act = `op job new --workflow <id> --request <text>` + `op run`; nur Workflows, u. a. research-cycle mit project_id; kein research-init.
- **Orchestrator / Council / Auto-Follow-up:** Subprocess-Aufrufe auf `op` und/oder `run-research-cycle-until-done.sh`.
- **research-phase.sh:** Wird nur als Job-Workflow „research-phase“ gestartet (Request = project_id). Von `run-research-cycle-until-done.sh` in Schleife aufgerufen.

---

## 5. Wo stoppt es nach einer Phase (by design) vs. wo läuft es durch

**Läuft bis done/failed (kein Stopp nach einer Phase):**

| Einstieg | Verhalten |
|----------|-----------|
| UI „Forschung starten“ (run_until_done: true) | Init, dann `run-research-cycle-until-done.sh` im Hintergrund → alle Phasen bis done. |
| UI „Research fortsetzen“ | Startet `run-research-cycle-until-done.sh` im Hintergrund → alle Phasen bis done. |
| Telegram `/research-cycle <id>` | Startet `run-research-cycle-until-done.sh` im Hintergrund → alle Phasen bis done. |
| Brain (research-cycle) | Startet `op run` für research-cycle-Job im Hintergrund (kein Timeout) → alle Phasen bis done. |
| Council / Orchestrator / Auto-Follow-up | Starten `run-research-cycle-until-done.sh` (bzw. op run research-cycle) im Hintergrund. |

**Stoppt nach einer Phase und wartet auf nächsten Trigger (by design):**

| Einstieg | Verhalten |
|----------|-----------|
| UI „Forschung starten“ mit **run_until_done: false** | Nur research-init; Projekt wartet auf manuellen Klick „Research fortsetzen“ oder `/research-cycle`. |
| Telegram `/research-start` | Nur Init; Hinweis „Nächster Schritt: /research-cycle …“. |
| Cron **run-scheduled-research.sh** | Pro Cron-Lauf **eine** Phase pro Projekt, dann 6h Pause bis nächster Cron. (Timeout pro Phase: 30 Min.) |
| **run-research-over-days.sh** (z. B. `/research-go`) | Pro Durchlauf **eine** Phase, dann Sleep 6h, dann nächste Phase. (Timeout pro Phase: 30 Min.) |

**Frühere Bugs (behoben):** June `/research-cycle` und Brain research-cycle hatten ein festes Timeout (5 Min / 3 Min) und haben den Lauf nach ~1 Phase abgebrochen. Beide starten den Cycle jetzt im Hintergrund ohne Timeout.

---

## 6. Terminal-Status und Fail-Codes

- **done:** Report fertig, Critic bestanden (oder Discovery advisory), ggf. Council getriggert.
- **pending_review:** Manueller Review-Gate.
- **failed_***: z. B. failed_insufficient_evidence, failed_quality_gate, failed_conductor_tool_errors, failed_experiment_gate, failed_stuck_phase.
- **aem_blocked:** AEM enforce/strict blockiert Synthese.
- **cancelled / abandoned:** Manuell oder Skript.

Siehe `docs/RESEARCH_QUALITY_SLO.md` (Standard fail codes, Discovery-Fail-Härtung).

---

## 7. Kurzreferenz: Steuerung nach Ziel

| Ziel | Wer | Aktion |
|------|-----|--------|
| Neues Projekt + alle Phasen bis done | UI, Telegram (/research-go), Orchestrator, Council, Auto-Follow-up | research-init + run-research-cycle-until-done (oder over-days). |
| Nur Projekt anlegen, Phasen manuell | UI (run_until_done: false), Telegram (/research-start) | research-init; danach UI „Research fortsetzen“ oder /research-cycle. |
| Einzelnes Projekt einen Cycle vorantreiben | UI „Research fortsetzen“, Telegram /research-cycle, Brain, Scheduler | research-cycle (führt bis terminalen Zustand in einer Job-Kette). |
| Alle nicht-done-Projekte periodisch vorantreiben | Cron | run-scheduled-research.sh. |
| Neue Fragen aus allen done Reports + Sandbox | Cron | run-research-orchestrator.sh. |
| Projekt abbrechen | UI (Cancel), Skript | cancel API / cancel_projects.py. |
| Brain darf neue Research starten? | Nein | Nur research-cycle für bestehende Projekte. |

---

## 8. Referenzen (Code & Doku)

- **Tiefenverständnis (Ablauf, State, Lock, Conductor, Gates, Datenfluss):** `docs/OPERATOR_SYSTEM_DEEP_DIVE.md`
- **June, Argus, Atlas (Rollen, Delegation, OpenClaw, Verbindung mit Operator):** `docs/JUNE_ARGUS_ATLAS_DEEP_DIVE.md`
- Phasen-Orchestrierung: `workflows/research-phase.sh`, `tools/run-research-cycle-until-done.sh`, `workflows/research-cycle.sh`.
- Init: `workflows/research-init.sh`; API: `ui/src/app/api/research/projects/route.ts`, `ui/src/lib/operator/actions.ts`.
- Cycle/Cancel: `ui/src/app/api/research/projects/[id]/cycle/route.ts`, `cancel/route.ts`, `lib/operator/research.ts` (cancelResearchProject).
- Brain: `lib/brain.py` (research-init blockiert, research-cycle erlaubt, Council-Wartezeit).
- Conductor: `tools/research_conductor.py` (gate, run_cycle, shadow).
- Orchestrator / Council / Auto-Follow-up: `tools/run-research-orchestrator.sh`, `tools/trigger_council.py`, `tools/research_auto_followup.py`, `tools/research_council.py`.
- Telegram: `openclaw-bridge/commands/research.ts`.
- Doku: `UI_OVERVIEW.md`, `RESEARCH_QUALITY_SLO.md`, `RESEARCH_AUTONOMOUS.md`, `RESEARCH_MODES.md`, `TOOL_AGENT_SYSTEM_AUDIT.md`, `BRAIN_SYSTEM.md`, `SYSTEM_CHECK.md`; Phasen-Deep-Dives: `EXPLORE_PHASE_DEEP_DIVE.md`, `FOCUS_PHASE_DEEP_DIVE.md`, `CONNECT_PHASE_DEEP_DIVE.md`, `VERIFY_PHASE_DEEP_DIVE.md`, `SYNTHESIZE_PHASE_DEEP_DIVE.md`.
