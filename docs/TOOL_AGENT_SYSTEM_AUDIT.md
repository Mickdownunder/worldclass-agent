# Tool- & Agenten-System: Audit (Tool Connector / Experte)

Stand: System vollständig durchdrungen. Bewertung: Sinnhaftigkeit, Wert, Lücken, fehlender „Tool Connector“.

---

## 1. System in einer Nussschale

| Ebene | Was es ist |
|-------|------------|
| **Operator** | Autonomes Job-Orchestrierungs- und Research-System. Einträge: `bin/op`, `bin/brain`, `tools/operator-dispatch`. Daten: `OPERATOR_ROOT` (z.B. `/root/operator`). |
| **Tools** | Alles unter `operator/tools/`: Research-Python-Skripte (`research_*.py`), Shell-Skripte (z.B. `infra-summary.sh`, `run-research-cycle-until-done.sh`), Opportunity/Memory/Dispatch. **Tool-Verträge:** `tools/research_tool_registry.py` definiert pro Research-Tool required_env, min_argv, project_id_arg_index; `ensure_tool_context(tool_name)` in den Tools prüft beim Start (bei `RESEARCH_STRICT_TOOL_CONTEXT=1` hart, sonst nur Warnung). Plumber prüft „missing_contracts“ (referenzierte Tools ohne Eintrag). Factory-Tools: `knowledge/tools/registry.md`. |
| **Agenten** | **Captain** (Brain + Workflows + Jobs), **June** (OpenClaw/Telegram). Dazu: **Research Conductor** (nur Implementierung in `research_conductor.py`, nicht in der UI als „Agent“ gelistet). Workflow-Labels in der UI (Planner, Critic, Tool Use, …) sind **keine** eigenen Agenten, sondern Namen für ausführbare Workflows. |
| **Tool-Connector** | **Existiert nicht.** Die Verdrahtung ist: (1) Workflows → Tools (Bash/Python), (2) Conductor → Tools (Subprocess), (3) Brain → Workflows (op), (4) UI/OpenClaw → Workflows/Tools (op + direkte Aufrufe). |

---

## 2. Wo Tools herkommen und wer sie nutzt

### 2.1 Research-Tools (`tools/research_*.py`)

- **Aufrufer 1: `workflows/research-cycle.sh`**  
  Ruft dutzende Tools explizit per `python3 "$TOOLS/research_*.py" …` auf. Phasen: explore → focus → connect → verify → synthesize. Core-10-Integration über `RESEARCH_ENABLE_*` Flags (plan: `core-10-tool-integration.plan.md`).

- **Aufrufer 2: `tools/research_conductor.py`**  
  Wenn `RESEARCH_USE_CONDUCTOR=1`: Conductor entscheidet (LLM + Fallback) die nächste Aktion (`search_more`, `read_more`, `verify`, `synthesize`) und ruft Tools per **Subprocess** auf (`_run_tool(project_id, "research_*.py", …)`).  
  Genutzte Tools im Conductor: `research_planner.py`, `research_web_search.py`, `research_coverage.py`, `research_parallel_reader.py`, `research_deep_extract.py`, `research_dynamic_outline.py`, `research_supervisor.py`, `research_verify.py` (4 Modi), `research_quality_gate.py`, `research_synthesize.py`, `research_critic.py` (via Import), `research_advance_phase.py`, `research_context_manager.py`, `research_progress.py`.

- **Plumber (Dead-Tool-Erkennung)**  
  `lib/plumber.py` → `diagnose_tool_references()` scannt **nur** Shell-Workflows unter `workflows/*.sh` (und ggf. `workflows/research/phases/*.sh`) nach `$TOOLS/…`, `$OPERATOR_ROOT/tools/…`, `tools/(research_*.py)`. **Nicht** gescannt: `research_conductor.py`. Folge: Tools, die **nur** vom Conductor aufgerufen werden, können als „dead“ gemeldet werden (False Positive). Nach dem Audit wurde der Plumber erweitert, sodass auch `tools/research_conductor.py` als Referenzquelle für `research_*.py` zählt.

### 2.2 Tool-Workflows (`workflows/tool-*.sh`)

| Workflow | Inhalt | Bewertung |
|----------|--------|-----------|
| **tool-use.sh** | Ruft **fest** `tools/infra-summary.sh` auf, schreibt Ausgabe nach `artifacts/tool-output.txt`. | **Eng:** Kein generischer „Tool-Use“; ein einziges Tool. Für echten „Tool Use“ müsste Tool-Name/Parameter aus Job-Request kommen. |
| **tool-eval.sh** | Listet `tools/`-Dateien, liest `knowledge/tools/registry.md`, bewertet per LLM (OpenAI) Nutzen/Qualität/Empfehlung, schreibt `eval.json`/`eval.md`. | **Sinnvoll:** Regelmäßige Bewertung des Tool-Bestands. |
| **tool-create.sh** | Legt **immer** dasselbe Skript an: `tools/infra-summary.sh` (uptime, df, free). | **Demo/Placeholder:** Kein parametrisierter Tool-Create; nur ein festes Beispiel. |
| **tool-register.sh** | (Nicht im Detail geprüft; typisch: Eintrag in registry/backlog.) | — |
| **tool-improve.sh**, **tool-backlog-add.sh**, **tool-backlog-improve.sh**, **tool-idea.sh** | Ideen/Backlog/Verbesserung rund um die Factory-Tools. | Konsistent mit Registry/Backlog-Konzept. |

**Fazit Tool-Workflows:** Wertvoll v. a. **tool-eval**; **tool-use** und **tool-create** sind sehr schmal bzw. fest verdrahtet. Für einen echten „Tool-Connector“ wären parametrisierter tool-use (Request = welches Tool, welche Args) und ggf. ein kleines Tool-Register im Code sinnvoll.

### 2.3 Sonstige Tools

- **operator-dispatch** (`tools/operator-dispatch/bin/operator-dispatch`): Bridge (create/run/status/artifacts); liest JSON-Intent, erstellt/startet Jobs via `op`. Kein „Tool“ im Research-Sinne, aber zentral für externe Steuerung.
- **run-research-cycle-until-done.sh** / **run-research-over-days.sh**: UI bzw. OpenClaw starten Research und lassen Cycles bis „done“ bzw. alle X Stunden über N Tage laufen. Korrekt in Doku referenziert (UI_OVERVIEW, RESEARCH_AUTONOMOUS).
- **research_feedback.py**: Direkt von UI (POST /api/research/feedback) und OpenClaw (`/research-feedback`) aufgerufen. Passt.

---

## 3. Agenten: Sinnhaftigkeit und Wert

### 3.1 Captain (Operator)

- **Rolle:** Repräsentiert das Agent-System: Brain, Workflows, Jobs. Läuft autonom (nicht in Telegram).
- **Bewertung:** **Sinnvoll und wertvoll.** Brain sieht nur Workflow-IDs, keine einzelnen Tools; Act = `op job new` + `op run`. Klare Trennung: Brain trifft Entscheidungen, Workflows führen aus (und rufen dabei Tools auf).

### 3.2 June (OpenClaw)

- **Rolle:** Telegram-Agent; startet Research (`/research-start`, `/research-cycle`, `/research-go`), sendet Feedback (`/research-feedback`). Nutzt `op` für Jobs und direkte Tool-Aufrufe (z.B. `research_feedback.py`).
- **Bewertung:** **Sinnvoll und wertvoll.** Einheitliche Schnittstelle für Research und Feedback; Konsistenz mit UI (beide nutzen dieselben Workflows/Tools).

### 3.3 Research Conductor

- **Rolle:** Orchestriert Research bei `RESEARCH_USE_CONDUCTOR=1`: begrenzter State (6 Metriken), 4 Aktionen, LLM + Fallback, max 25 Schritte. Führt Research-Tools per Subprocess aus.
- **Bewertung:** **Sinnvoll und wertvoll.** Entlastet die starre Phasenfolge; dynamische Entscheidung „was als Nächstes“. Nicht in `listAgents()` – bewusst, da kein Nutzer sichtbarer „Agent“, sondern interne Steuerung. **Passt so.**

### 3.4 Workflow-Labels (UI „Agents“-Seite)

- **Rolle:** `listWorkflows()` liest `workflows/*.sh` und mappt IDs auf Namen/Beschreibung via `WORKFLOW_LABELS` in `ui/src/lib/operator/agents.ts`. Fehlt ein Eintrag, wird aus der ID ein lesbarer Name generiert (z.B. „Research Cycle“).
- **Lücke:** **research-cycle** und **research-init** hatten **keine** expliziten Labels; sie erschienen mit generierten Namen. Empfohlen: Einträge in `WORKFLOW_LABELS` für research-init, research-cycle (und ggf. weitere Research-Workflows) ergänzen – dann sind Bezeichnungen und Doku konsistent.

---

## 4. Fehlender „Tool Connector“: Braucht man einen?

**Aktuell:** Es gibt **keinen** dedizierten Baustein namens „Tool Connector“. Die Verdrahtung ist dezentral:

1. **Workflows (Bash)** → rufen Tools explizit auf (`$TOOLS/…`).
2. **Conductor (Python)** → ruft Tools per `_run_tool(…, "research_*.py", …)` auf.
3. **Brain** → kennt nur Workflows; ruft keine Tools direkt auf.
4. **UI / OpenClaw** → starten Workflows (op) oder einzelne Tools (z.B. research_feedback).

**Bewertung:**

- **Für den aktuellen Betrieb:** Ein expliziter „Tool Connector“ ist **nicht zwingend**. Die Aufgaben (Welches Tool? Mit welchen Args? Von wem?) sind klar verteilt: Workflows und Conductor wissen, welche Tools sie brauchen; Brain bleibt auf Workflow-Ebene.
- **Wenn du den Begriff „Tool Connector“ einführen willst**, wären sinnvolle Optionen:
  - **Option A (dokumentell):** Ein Doc (z.B. dieses hier + Abschnitt in `UI_OVERVIEW.md`), das die Verdrahtung „Tools ↔ Workflows/Conductor/Agents“ beschreibt und als Referenz dient.
  - **Option B (klein, code):** Ein Modul oder Skript, das (1) alle `research_*.py` auflistet, (2) Referenzen in `research-cycle.sh` und `research_conductor.py` (und ggf. anderen Workflows) erkennt und (3) eine einfache „Tool-Referenz-Matrix“ ausgibt (wer ruft welches Tool auf). Das könnte der Plumber nutzen (bereits teilweise umgesetzt: Conductor als Referenzquelle).
  - **Option C (vollwertig):** Ein Registry mit Tool-Signaturen (Name, Eingaben, Ausgaben), von dem Workflows/Conductor/UI lesen. Deutlich mehr Aufwand; lohnt sich, wenn viele neue Tools hinzukommen oder mehrere Agenten dieselben Tools einheitlich aufrufen sollen.

**Empfehlung:** Option A + B umsetzen (Doku + Plumber/Conductor-Referenzen); Option C nur bei Bedarf (z.B. wenn Tool-Idee/Create/Use generisch werden).

---

## 4b. Tool-Absicherung (Registry + Strict Mode)

- **`tools/research_tool_registry.py`:** Enthält `TOOL_CONTRACTS` (pro Skript: required_env, min_argv, project_id_arg_index, project_id_pattern). `validate_invocation(tool_name, env, argv)` liefert (ok, errors). `ensure_tool_context(tool_name)` ruft das am Start eines Tools auf; bei **RESEARCH_STRICT_TOOL_CONTEXT=1** beendet sich das Tool mit Fehlermeldung, wenn env/argv nicht passen, sonst nur Stderr-Warnung.
- **Eingebaut in:** research_verify.py, research_synthesize.py, research_conductor.py, research_quality_gate.py (zu Beginn von main()).
- **Plumber:** Kategorie `tool_contracts` – meldet Research-Tools, die in Workflows referenziert werden, aber **keinen** Eintrag in TOOL_CONTRACTS haben („missing_contracts“). So werden neue Tools im Pipeline-Betrieb sichtbar, wenn sie noch nicht abgesichert sind.
- **Aktivierung:** In `research-cycle.sh` (oder conf) `RESEARCH_STRICT_TOOL_CONTEXT=1` setzen, um Vertragsverletzungen sofort zu blockieren. Default 0 = nur Warnung.
- **Manuell prüfen:** `python3 tools/research_tool_registry.py validate research_verify.py proj-xxx source_reliability` (mit OPERATOR_ROOT gesetzt).

---

## 5. Lücken und konkrete Verbesserungen

| Lücke | Priorität | Maßnahme (erledigt/offen) |
|-------|-----------|----------------------------|
| Plumber meldet Conductor-only-Tools als „dead“ | Mittel | **Erledigt:** `diagnose_tool_references()` in `lib/plumber.py` scannt zusätzlich `tools/research_conductor.py` nach Aufrufen von `research_*.py` und zählt diese als referenziert. |
| research-cycle / research-init ohne klare UI-Labels | Niedrig | **Empfohlen:** In `agents.ts` `WORKFLOW_LABELS` um `research-init`, `research-cycle` ergänzen (siehe Änderung im Repo). |
| tool-use.sh nur ein festes Tool (infra-summary) | Niedrig | Optional: Job-Request = Tool-Name + Args; workflow wählt Skript dynamisch. Sonst umbenennen/Label: „Infra Summary“ statt „Tool Use“. |
| tool-create.sh immer gleiches Demo-Skript | Niedrig | Optional: Parametrisierung (Name, Typ, Body) aus Request oder Backlog; sonst als „Demo“ in Doku kennzeichnen. |
| Keine zentrale Liste „alle Tools + Aufrufer“ | Niedrig | Durch Plumber-Erweiterung und dieses Doc abgedeckt; bei Bedarf kleines Skript „tool-matrix“ (wer ruft was) wie in Option B. |

---

## 6. Referenzen (Code & Doku)

- **Agenten/Workflows:** `operator/ui/src/lib/operator/agents.ts` (`listAgents`, `listWorkflows`, `WORKFLOW_LABELS`).
- **Brain Act:** `operator/lib/brain.py` (Workflows aus `state["workflows"]`, Act = `op job new` + `op run`; research-cycle mit request = project_id).
- **Conductor:** `operator/tools/research_conductor.py` (`_run_tool`, `run_cycle`, Aktionen search_more/read_more/verify/synthesize).
- **Research-Cycle:** `operator/workflows/research-cycle.sh` (alle `$TOOLS/research_*.py`-Aufrufe, Conductor gate/run_cycle/shadow, Core-10-Flags).
- **OpenClaw Research:** `operator/openclaw-bridge/commands/research.ts` (research-start, research-cycle, research-go, research-feedback).
- **UI Actions:** `operator/ui/src/lib/operator/actions.ts` (`ALLOWED_WORKFLOWS`, `runWorkflow`, `runResearchInitAndCycleUntilDone`).
- **Plumber Tool-Referenzen:** `operator/lib/plumber.py` (`diagnose_tool_references()`).
- **Doku:** `operator/docs/UI_OVERVIEW.md`, `RESEARCH_QUALITY_SLO.md`, `RESEARCH_AUTONOMOUS.md`, `SYSTEM_CHECK.md`; Plan: `.cursor/plans/core-10-tool-integration.plan.md`; Registry: `operator/knowledge/tools/registry.md`.

---

## 7. Kurzfassung

- **System:** Verständlich und konsistent. Tools leben unter `tools/`, werden von Workflows und dem Research Conductor aufgerufen; Brain arbeitet nur mit Workflows; UI und June triggern Workflows und wenige Tools direkt.
- **Agenten:** Captain, June und der Conductor sind sinnvoll und wertvoll; Workflow-Labels sind keine eigenen Agenten, aber für die UI wichtig (research-init/research-cycle sollten explizite Labels haben).
- **Tool-Connector:** Existiert nicht als Baustein; Verdrahtung ist dezentral. Für Klarheit reichen Doku + Plumber-Anreicherung (Conductor als Referenz); ein optionales Tool-Matrix-Skript oder später ein kleines Registry ist möglich.
- **Umsetzung:** Plumber um Conductor-Scan erweitert; WORKFLOW_LABELS um research-init/research-cycle ergänzt; dieses Audit-Dokument angelegt und in die Docs-Sync-Regel einbezogen.
