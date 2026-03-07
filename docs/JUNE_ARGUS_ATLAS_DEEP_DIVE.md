# June, Argus, Atlas: Deep Dive und Verbindung

Technisches Deep-Dive: Wer June, Argus und Atlas sind, wie sie funktionieren und wie sie mit Operator, OpenClaw und der UI verbunden sind.

---

## 1. Überblick: Drei Agenten, eine Kette

| Agent | Rolle | Wo er läuft | Wer startet ihn |
|-------|--------|-------------|------------------|
| **June** | General / Autonomous operations assistant | OpenClaw (Server), Workspace `/root/agent/workspace` | Mensch (Telegram/DM), UI (indirekt über Brain/Research) |
| **Argus** | Senior Research Engineer (Sub-Agent) | Scripts in `/root/agent/argus/workspace`; optional als OpenClaw-Subagent | June (via june-delegate-argus oder june-command-run → MissionExecutor) |
| **Atlas** | Sandbox Validation Engineer (Sub-Agent) | Scripts in `/root/agent/atlas/workspace`; optional als OpenClaw-Subagent | Argus (via argus-delegate-atlas) |

**Kette:** Master (Mensch) → June → Argus → Atlas. June entscheidet und delegiert; Argus führt Research-/Test-Pläne aus; Atlas führt Validierungscode in einer Sandbox aus und liefert Beweis/Gegenbeweis.

---

## 2. OpenClaw: Plattform für June (und Subagenten)

- **OpenClaw** ist die Chat-/Agent-Plattform (Telegram, ggf. weitere Kanäle). Konfiguration: `~/.openclaw/openclaw.json`.
- **Agenten-Liste:** `agents.list` enthält:
  - **main** (id: `main`): Standard-Agent in direkten Chats. Workspace = `/root/agent/workspace` (= June). Sandbox `mode: off`; darf Subagent **argus** spawnen (`subagents.allowAgents: ["argus"]`).
  - **argus**: Eigenes Workspace `/root/agent/argus/workspace`, Modell z. B. gpt-5.3-codex, Identity „Argus“, Theme „precise, skeptical, evidence-first“. Darf Subagent **atlas** spawnen.
  - **atlas**: Workspace `/root/agent/atlas/workspace`, Identity „Atlas“, Theme „strict, methodical, failure-intolerant“. Keine Subagenten.
- **Zwei Nutzungsarten von Argus/Atlas:**
  1. **Skript-Delegation (Standard für Missionen):** June führt per Exec `june-delegate-argus` aus → Bash ruft `argus-research-run` auf → der ruft `argus-delegate-atlas` auf → Bash ruft `atlas-sandbox-run`. Kein eigener LLM-Turn von Argus/Atlas; nur deterministische Skripte.
  2. **OpenClaw-Subagent (konversationell):** June kann Argus als Subagent starten (wenn die UI/OpenClaw-Funktion genutzt wird); dann hat Argus eigene Session/LLM und kann seinerseits Atlas spawnen. Seltener Pfad für die typische „Mission run“-Ausführung.

---

## 3. June im Detail

### 3.1 Identität und Kontext

- **Name:** June. **Rolle:** Autonomous operations assistant. **Vibe:** Calm and direct.
- **Workspace:** `/root/agent/workspace`. Wichtige Dateien: `AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `USER.md`, `SESSION_STARTUP.md`, `MEMORY.md`, `knowledge/operator_system.md`, `knowledge/june_control_spec_v1.md`, `knowledge/june_command_map_v1.md`.
- **Zugriff:** June läuft auf dem **gleichen Server** wie Operator und OpenClaw Gateway. Ihr Exec-Tool hat dort vollen Zugriff (Dateien, Befehle, `/root/operator`, Research, Jobs). Kein separater „Freischalt“-Bereich nötig.

### 3.2 Steuerung (Control Spec, Command Map)

- **june_control_spec_v1.md:** Definiert Intents (`run_tests_sequential`, `continue_until_done`, `report_after_duration`, `status_now`, `stop_now`, `pause_queue`, `resume_queue`), Prioritätenleiter, Sequential Test Protocol, Reporting Policy (silent by default), Delegation Contract (Argus liefert Evidence + Empfehlung), Decision Gates (wann Master fragen), erlaubte Execution Surface.
- **june_command_map_v1.md:** June darf **nur** fest gemappte Befehle ausführen (oc-healthcheck, oc-job-status, oc-research-init, oc-research-cycle, oc-brain-memory, oc-brain-think, june-command-run, june-frontier-eval; Legacy: june-seq-run, june-delegate-argus). Kein beliebiges Shell für autonome Aktionen.

### 3.3 Wie June mit Operator/Research redet

- **Telegram-Commands (OpenClaw-Plugin „Operator Bridge“):** Das Plugin registriert Slash-Commands, die June (bzw. den Nutzer) mit dem Operator verbinden:
  - `/research-start`, `/research-cycle`, `/research-go`, `/research-status`, `/research-feedback` → Handler in `operator/openclaw-bridge/commands/research.ts` (op job new/run, run-research-cycle-until-done.sh, run-research-over-days.sh, research_feedback.py).
  - `/think`, `/cycle`, `/memory` → Handler in `commands/brain.ts` (brain think, brain cycle, brain memory).
- **Direkte Nutzung:** Der Mensch kann in Telegram z. B. `/research-go "Frage"` tippen → Plugin führt Init + over-days aus und antwortet. Oder der Mensch schreibt June an; June interpretiert die Nachricht, mappt auf einen Intent und führt **über ihr Exec** einen der erlaubten Befehle aus (z. B. `oc-research-cycle proj-xxx` oder `june-command-run <objective> --request-text <text> --execute`).

### 3.4 Mission Control: june-command-run

- **Einstieg:** `/root/agent/workspace/bin/june-command-run [objective] --request-text <text> [--execute]` bzw. mit `--mission-id` für Steuerung (show, pause, retry, resume, replan).
- **Ablauf:** `MissionCompiler` erstellt aus Objective + Request-Text eine Mission (Mission, TaskGraph). Bei `--execute` übernimmt `MissionController` + `MissionExecutor`. Der Executor führt je nach Plan und execution_mode entweder eine **strukturierte Audit**-Pipeline (Architect, Skeptic, etc.) oder den **Delegations-Pfad** aus.
- **Delegations-Pfad:** `MissionExecutor._run_delegate(plan, request_text)` ruft subprocess auf: `["/root/agent/workspace/bin/june-delegate-argus", plan, request_text?]`. Die Ausgabe von june-delegate-argus enthält Zeilen wie `OVERALL=`, `RECOMMENDATION=`, `ATLAS_OVERALL=`, `ATLAS_RECOMMENDATION=`, `RUN_DIR=`, `SUMMARY_FILE=`. `parse_envelope(raw_output)` parst daraus ein `ResultEnvelope`. Danach: decide_next_action, Epistemic/Campaign/Portfolio-Updates, Arbiter, Event-Log.
- **Frontier-Gate:** Vor Promotion-Empfehlungen soll June `june-frontier-eval` ausführen und z. B. GATE_CHAIN, GATE_ATLAS, GATE_EVIDENCE auf PASS verlangen.

---

## 4. Argus im Detail

### 4.1 Identität und Rolle

- **Name:** Argus. **Rolle:** Senior Research Engineer (sub-agent). **Vibe:** precise, skeptical, evidence-first.
- **Workspace:** `/root/agent/argus/workspace`. Lektüre: `knowledge/argus_control_spec_v1.md`, `knowledge/argus_command_map_v1.md`.

### 4.2 Erlaubte Ausführung

- **Primär:** `argus-research-run <status|research|full|mini> [request text]`.
- **Intern genutzt:** oc-healthcheck, oc-job-status, oc-research-init, oc-research-cycle (laut Command Map).
- **Delegation an Atlas:** `argus-delegate-atlas <status|research|full|mini> [request text]`.

### 4.3 argus-research-run

- Legt Run-Verzeichnis unter `/root/agent/argus/workspace/logs/seq/<timestamp>-<plan>/` an.
- Je nach Plan: **status** (Health + Jobs), **research** (Health + Research Init + Research Cycle), **full** (Status + Research), **mini** (Health + Mini-Policy-Trio). Kann für bestimmte Request-Texte einen „probe“-Modus nutzen (weniger Schritte).
- Ruft für Sandbox-Validierung **argus-delegate-atlas** auf (mit Timeout, Heartbeat-Logging). Erwartet von Atlas Zeilen `OVERALL=`, `RECOMMENDATION=`, `RUN_DIR=`, `SUMMARY_FILE=`.
- Schreibt Summary, setzt OVERALL/RECOMMENDATION/ATLAS_OVERALL/ATLAS_RECOMMENDATION und gibt sie an den Aufrufer (june-delegate-argus) zurück.
- Loggt Delegation in `operator/logs/agent-activity.jsonl` (from=argus, to=atlas).

### 4.4 argus-delegate-atlas

- Bash-Skript: ruft `atlas-sandbox-run <plan> [request text]` mit Timeout auf (status 180s, mini/research/full 0 = kein harter Timeout), Heartbeat auf stderr.
- Parst Atlas-Ausgabe, gibt Vertragszeilen weiter, schreibt Eintrag in agent-activity.jsonl.

---

## 5. Atlas im Detail

### 5.1 Identität und Rolle

- **Name:** Atlas. **Rolle:** Sandbox Validation Engineer. **Vibe:** strict, methodical, failure-intolerant.
- **Mission:** **Ausführen und Beweisen** – der Code, der die These testet, wird von Atlas (in einer Sandbox) ausgeführt; Atlas liefert Evidenz (Beweis/Gegenbeweis) und Empfehlung.

### 5.2 Erlaubte Ausführung

- **atlas-sandbox-run** `<status|research|full|mini>` `[request text]`: Policy-Check, Health (optional), Job-Status, ggf. research_init + research_cycle, oder mini_audit.
- **atlas-run-sandbox** `<path_to_script.py>` `[timeout_seconds]`: Führt thesis-validierenden Python-Code in der **Research-Sandbox** (Docker: operator-research-sandbox, kein Netz, numpy/scipy, Timeout). Logs: `logs/sandbox/<timestamp>-run/`.

### 5.3 atlas-sandbox-run

- Run-Dir: `/root/agent/atlas/workspace/logs/seq/<timestamp>-<plan>/`.
- GATE_MODE: strict (default) oder warn (z. B. bei skip_health, gate=warn im Request).
- Schritte je Plan: z. B. sandbox_policy, sandbox_list, healthcheck, job_status, research_init, research_cycle, mini_audit. Schreibt summary.txt, setzt OVERALL, RECOMMENDATION, RUN_DIR, SUMMARY_FILE.
- Kein direkter Aufruf von Atlas durch June; immer über Argus.

---

## 6. Verbindung: Datenfluss Ende-zu-Ende

### 6.1 Mensch startet Research (Telegram)

1. User: `/research-go "Frage"` oder schreibt June „Starte Research zu X“.
2. Bei Slash: OpenClaw-Plugin führt research.ts Handler aus → research-init (op job new + run), dann run-research-over-days.sh im Hintergrund. Antwort an User.
3. Bei Freitext: June interpretiert, mappt Intent, führt z. B. oc-research-init + oc-research-cycle oder june-command-run aus (je nach Command Map / Control Spec).

### 6.2 June startet deterministische Mission (june-command-run --execute)

1. June (oder Cron/UI) ruft auf: `june-command-run <objective> --request-text <text> --execute`.
2. MissionCompiler erstellt Mission + TaskGraph.
3. MissionExecutor führt aus: `_run_delegate(plan, request)` → subprocess `june-delegate-argus <plan> [request]`.
4. june-delegate-argus (Bash): Timeout + Heartbeat, ruft `argus-research-run <plan> [request]` auf.
5. argus-research-run: Führt Schritte aus, ruft für Validierung `argus-delegate-atlas <plan> [request]` auf.
6. argus-delegate-atlas: Ruft `atlas-sandbox-run <plan> [request]` auf.
7. atlas-sandbox-run: Führt Schritte aus (healthcheck, job_status, research_init, research_cycle, mini_audit …), schreibt Summary, gibt OVERALL/RECOMMENDATION zurück.
8. Rückwärts: Atlas → Argus → june-delegate-argus → MissionExecutor. Executor parst Envelope, decide_next_action, speichert Mission-State, Event-Log, ggf. Arbiter/Campaign/Portfolio.
9. June nutzt Ergebnis (OVERALL, RECOMMENDATION, ATLAS_OVERALL, ATLAS_RECOMMENDATION) für nächste Aktion (stop, more_runs, new_test, candidate_for_promotion) und ggf. june-frontier-eval vor Promotion.

### 6.3 Operator ↔ June/Argus/Atlas

- **Operator** stellt bereit: `bin/op`, research-init, research-phase, run-research-cycle-until-done, Brain, Tools (research_*.py). Kein direkter „Aufruf“ von June; June ruft Operator (op, oc-*-Wrapper) auf.
- **oc-*-Wrapper:** June Command Map verweist auf z. B. `/root/operator/bin/oc-healthcheck`, `oc-research-init`, `oc-research-cycle`. Diese Wrapper (falls vorhanden) kapseln op/Brain; ansonsten nutzt June direkt op (über Exec). OpenClaw-Plugin ruft für Slash-Commands direkt op/run-research-*-Scripts auf (research.ts).
- **Agent-Activity-Log:** `operator/logs/agent-activity.jsonl` wird von june-delegate-argus (June→Argus) und argus-delegate-atlas (Argus→Atlas) beschrieben. UI/Agent-Activity-API kann daraus lesen (Delegationen, overall, recommendation).

### 6.4 UI (Operator Dashboard)

- **Agents-Seite:** `listAgents()` in `ui/src/lib/operator/agents.ts` liefert Captain (Operator/Brain), June (OpenClaw), Argus (delegationFrom: june), Atlas (delegationFrom: argus). Keine Live-Sessions; beschreibt die Rollen und die Kette.
- **Activity/Agent-Activity:** Kann agent-activity.jsonl oder zugehörige API nutzen, um letzte Delegationen und Runs anzuzeigen.

---

## 7. Wichtige Dateien (Referenz)

| Bereich | Dateien |
|--------|---------|
| OpenClaw Config | `~/.openclaw/openclaw.json` (agents.list: main, argus, atlas) |
| Operator Bridge (Telegram) | `operator/openclaw-bridge/commands/research.ts`, `brain.ts`, `index.ts`, `runner.ts` |
| June | `agent/workspace/AGENTS.md`, `IDENTITY.md`, `knowledge/june_control_spec_v1.md`, `knowledge/june_command_map_v1.md`, `SESSION_STARTUP.md` |
| June Mission | `agent/workspace/bin/june-command-run`, `bin/june-delegate-argus`, `runtime/step_executor.py` (_run_delegate), `runtime/result_envelope.py` |
| Argus | `agent/argus/workspace/AGENTS.md`, `IDENTITY.md`, `knowledge/argus_control_spec_v1.md`, `knowledge/argus_command_map_v1.md`, `bin/argus-research-run`, `bin/argus-delegate-atlas` |
| Atlas | `agent/atlas/workspace/AGENTS.md`, `IDENTITY.md`, `knowledge/atlas_control_spec_v1.md`, `knowledge/atlas_command_map_v1.md`, `bin/atlas-sandbox-run`, `bin/atlas-run-sandbox` |
| UI Agents | `operator/ui/src/lib/operator/agents.ts` (listAgents), Agents-Seite |
| Logs | `operator/logs/agent-activity.jsonl`, Mission/Attempt-Logs unter `agent/workspace/logs/missions/`, Argus/Atlas seq-Logs |

---

## 8. Kurz: Wer macht was?

- **June:** Interpretiert Absicht, hält sich an Command Map/Control Spec, startet Research (via Telegram-Commands oder Exec), startet Missionen (june-command-run), delegiert Ausführung an Argus (june-delegate-argus), wertet Envelope und ATLAS_OVERALL/RECOMMENDATION aus, entscheidet nächste Aktion, fragt Master bei Gates.
- **Argus:** Führt deterministische Pläne (status, research, full, mini) aus, ruft Operator (oc-healthcheck, oc-research-init, oc-research-cycle) und Atlas (argus-delegate-atlas) auf, liefert Evidence-Pfade und Empfehlung, keine Promotion ohne June/Master.
- **Atlas:** Führt Sandbox-Checks und Validierungsläufe aus (atlas-sandbox-run), optional thesis-validierenden Code (atlas-run-sandbox), liefert OVERALL/RECOMMENDATION; sein Ergebnis ist das Gate-Signal (GATE_ATLAS) vor Promotion-Empfehlungen.

Diese Doku mit Code/Config abgleichen bei Änderungen an Agenten, Command Maps oder Bridge (siehe docs-sync-with-code Regel).
