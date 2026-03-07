# Analyse: Synthesize-Hänger proj-20260307-c1d43501

**Datum:** 2026-03-07  
**Projekt:** proj-20260307-c1d43501  
**Endergebnis:** status=`failed_stuck_phase`, phase=`synthesize`

## Ablauf (aus Log + progress.json)

1. **Verify → Conductor override zu Synthesize (17:15:09)**  
   Evidence-Gate war durchgefallen, Pipeline wollte zurück zu Focus. Conductor hat stattdessen auf Synthesize gesetzt → `advance_phase "synthesize"`, dann Run-Ende (Finalized progress on exit).  
   → Dieser Run hat **nur** die Phase auf synthesize gestellt und ist beendet; der **Synthesize-Block wurde in diesem Lauf nicht ausgeführt**.

2. **Nächster Run (17:15:13)**  
   Phase: SYNTHESIZE — report. Um 17:16:55 „Finalized progress on exit“. Unklar, ob hier Report fertig und `advance_phase "done"` erreicht wurde oder ob vorher abgebrochen.

3. **Run ab 17:37:36**  
   Synthesize läuft: Outline, Sections 1–5, Situation Map, Tipping Conditions, Scenario Matrix, Executive Synthesis, „Saving report & applying citations“, dann **„Running quality critic“** (research_critic.py, timeout 600s).  
   - Report wurde geschrieben: `reports/report_20260307T174224Z.md` (62KB).  
   - `progress.json`: step „Running quality critic“, step_started_at 17:42:24, **alive: false**, pid 4020456.  
   → Der Prozess ist **während des Quality-Critic-Schritts** beendet (Absturz/OOM/kill). Der EXIT-Trap wurde bei SIGKILL **nicht** ausgeführt.

4. **Lock-Verhalten**  
   - `.cycle.lock` wurde von dem abgestürzten Run gehalten. Nach Prozess-Ende gibt der Kernel die flock frei, aber die Trap entfernt die Lock-Datei nicht (bei SIGKILL keine Trap).  
   - Weitere Runs (17:42:36): „Another research-cycle is already running — skipping.“  
   - run-research-cycle-until-done zählt „same phase“ mehrfach → nach MAX_SAME_PHASE Markierung als **failed_stuck_phase**.

## Ursachen (kurz)

1. **Lifecycle:** Ein Run setzt nur `phase=synthesize` und beendet sich; der eigentliche Synthesize-Block läuft erst im nächsten Run. Das ist konsistent mit „ein Run = eine Phase“, führt aber zu dem Eindruck „hängt in synthesize“, wenn der nächste Run dann erst startet.
2. **Absturz im Critic:** Der Run, der den Report geschrieben hat, stirbt im Schritt „Running quality critic“ (pid 4020456, alive: false). Kein Traceback im Projekt-Log – naheliegend: OOM oder externer Kill (z. B. SIGKILL). EXIT-Trap läuft bei SIGKILL nicht → **Lock-Datei bleibt liegen** (stale lock).
3. **Stale Lock:** Danach versuchte Runs sehen die Lock-Datei; wenn sie zur gleichen Zeit starten, kann einer noch den Lock gehalten haben. Wenn der Halter-Prozess tot ist, bleibt die Datei trotzdem; ohne „Stale-Lock-Recovery“ geben wir weiter „already running — skipping“ aus und erhöhen same_phase_count.

## Maßnahmen (umgesetzt / empfohlen)

- **Stale-Lock-Recovery (research-phase.sh):** Wenn `flock -n` fehlschlägt, prüfen wir `progress.json`: falls die darin gespeicherte PID nicht mehr in `/proc` existiert, betrachten wir die Lock als verwaist, entfernen die Lock-Datei und versuchen den Lock einmal neu. So können nach Absturz/Kill neue Runs wieder durchstarten.
- **Optional:** Beim Start eines Runs die Lock-Datei nur dann als „stale“ löschen, wenn die zugehörige PID (z. B. aus progress.json) nicht mehr lebt; dann erneuter Lock-Versuch (bereits im Skript vorgesehen).
- **Monitoring:** Bei „Running quality critic“ + lange Laufzeit oder wiederholtem Absturz: research_critic.py (Timeout, Speicher, externe APIs) prüfen; ggf. Timeout oder Ressourcen anpassen.
