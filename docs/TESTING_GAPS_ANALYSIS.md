# Testing-Gaps-Analyse — Wo Testing massiv ausgebaut werden muss

Stand: 2025-02-27. Analyse des Operator-Projekts (UI + Python Backend/Tools + OpenClaw-Bridge).

**Bereits umgesetzt (nach Analyse):** Session (lib/auth/session.test.ts), Auth-API logout + session, progress (RUNTIME_STATE_*), Cancel-Route (research/projects/[id]/cancel), CancelRunButton, RetryButton. **Weiterer Ausbau:** API agents, packs, actions/retry, memory; Komponenten RuntimeStateBadge, Nav.

### Aktuelle Testabdeckung (UI, Vitest + v8)

| Metrik      | Wert    | Anmerkung |
|------------|---------|-----------|
| **Statements** | 17.91% | 1248/6967 – viele Pages/Routes ungetestet |
| **Branches**   | 53.03% | 192/362  |
| **Functions**  | 36.47% | 62/170   |
| **Lines**      | 17.91% | wie Statements |
| **Tests**      | 98     | 34 Testdateien |

Coverage ausführen: `cd ui && npm run test:coverage`. HTML-Report: `ui/coverage/index.html`.

---

## 1. UI (Next.js) — Kritische Lücken

### 1.1 API-Routes (massiv untertestet)

**Getestet (13 von 35 Routes):**
- `app/api/auth/login` (auth.test.ts)
- `app/api/auth/logout` (auth/__tests__/logout.test.ts)
- `app/api/auth/session` (auth/__tests__/session.test.ts)
- `app/api/events` (events.test.ts)
- `app/api/health` (health.test.ts)
- `app/api/research/projects` (research-projects.test.ts)
- `app/api/research/projects/[id]` (research-project-detail.test.ts)
- `app/api/research/projects/[id]/findings` (research-findings.test.ts)
- `app/api/research/projects/[id]/cancel` (research/projects/__tests__/cancel.test.ts)
- `app/api/agents` (agents/__tests__/route.test.ts)
- `app/api/packs` (packs/__tests__/route.test.ts)
- `app/api/actions/retry` (actions/retry/__tests__/route.test.ts)
- `app/api/memory` (memory/__tests__/route.test.ts)

**Komplett ohne Unit-Tests (22 Routes):**

| Route | Risiko | Begründung |
|-------|--------|------------|
| `api/research/projects/[id]/progress` | Hoch | Laufzeit-State, Stuck/Error-Loop-Erkennung |
| `api/research/[id]/progress` | Hoch | Duplikat/Legacy Progress |
| `api/actions/brain-cycle` | Kritisch | Startet Brain-Cycle, zentrale Aktion |
| `api/memory/outcomes` | Hoch | Daten-API für UI |
| `api/research/projects/[id]/followup` | Hoch | Follow-up-Workflow |
| `api/research/feedback` | Mittel | Feedback-Pipeline |
| `api/research/calibrated-thresholds` | Mittel | Qualitäts-Schwellen |
| `api/research/projects/[id]/audit` | Hoch | Audit-Daten |
| `api/memory/route` | Hoch | Memory-Übersicht |
| `api/memory/decisions` | Hoch | Entscheidungs-API |
| `api/research/projects/[id]/cycle` | Kritisch | Research-Cycle-Start |
| `api/research/projects/[id]/report` | Hoch | Report-Generierung |
| `api/research/projects/[id]/report/pdf` | Mittel | PDF-Export |
| `api/packs/route` | Mittel | Packs-Liste |
| `api/auth/logout` | Mittel | Session-Invalidierung |
| `api/auth/session` | Mittel | Session-Check |
| `api/actions/factory` | Hoch | Factory-Workflows |
| `api/research/projects/[id]/approve` | Hoch | Freigabe-Workflow |
| `api/research/projects/[id]/sources` | Hoch | Quellen-API |
| `api/research/projects/[id]/reports` | Hoch | Reports-Liste |
| `api/actions/run-workflow` | Kritisch | Generischer Workflow-Runner |
| `api/actions/workflows` | Mittel | Workflow-Liste |
| `api/memory/credibility` | Mittel | Source-Credibility |
| `api/memory/entities` | Mittel | Entities-API |
| `api/actions/retry` | Hoch | Retry-Logik |
| `api/research/insights` | Mittel | Insights-API |
| `api/agents/route` | Mittel | Agents-Liste |

**Empfehlung:** Pro Route mindestens: (1) 401 bei fehlender Auth, (2) 200/4xx bei gültigen/ungültigen Requests, (3) Mock der Backend-Calls. Priorität: `brain-cycle`, `run-workflow`, `cycle`, `cancel`, `progress`.

---

### 1.2 Komponenten (stark untertestet)

**Getestet (10 von 23 echten Komponenten):**
- ConfirmDialog, CreateProjectForm, DeleteProjectButton, ExecutionTree, StartCycleButton, StatusBadge, CancelRunButton, RetryButton, RuntimeStateBadge, Nav

**Ohne Tests (13 Komponenten):**

| Komponente | Risiko | Begründung |
|------------|--------|------------|
| `ActivityFeed.tsx` | Mittel | Event-Anzeige, Fehlerbehandlung |
| `ProjectRowProgress.tsx` | Hoch | Progress-Anzeige, Stuck/Error-States |
| `LiveRefresh.tsx` | Mittel | Polling/SSE, Cleanup |
| `MarkdownView.tsx` | Niedrig | Rendering (einfach) |
| `ActionButtons.tsx` | Hoch | Aktionen (Start/Cancel/Retry) |
| `LoadingSpinner.tsx` | Niedrig | UI-only |
| `ThemeToggle.tsx` | Niedrig | UI-only |
| `DashboardQuickActions.tsx` | Mittel | Links zu Research/Agents |
| `EmptyState.tsx` | Niedrig | Platzhalter |
| `ReviewPanel.tsx` | Hoch | Review-Logik, Claims |
| `CreateFollowupButton.tsx` | Hoch | Follow-up-Erstellung |
| `VerifiedClaimSlideover.tsx` | Hoch | Claim-Details, Verifizierung |
| `EventFeed.tsx` | Mittel | Event-Liste, SSE/Polling |

**Empfehlung:** Zuerst: `CancelRunButton`, `RetryButton`, `ActionButtons`, `ProjectRowProgress`, `RuntimeStateBadge`, `ReviewPanel`, `CreateFollowupButton`, `VerifiedClaimSlideover`. Dann `Nav`, `LiveRefresh`, `EventFeed`, `ActivityFeed`.

---

### 1.3 Lib (operator + auth)

**Getestet:**  
`config`, `jobs`, `health`, `research`, `agents`, `actions`, `memory`, `packs` (jeweils `lib/operator/*`), `auth/config`.

**Bereits getestet (nach Umsetzung):** `lib/auth/session.ts` (session.test.ts), `lib/operator/progress.ts` (progress.test.ts für RUNTIME_STATE_LABELS/HINT).

**Ohne Tests:** `lib/operator/index.ts` (nur Re-Exports).

---

### 1.4 E2E (Playwright)

**Vorhanden:**  
`e2e/auth.spec.ts` (Login, Redirect, falsches Passwort), `e2e/research.spec.ts` (Liste, Create, Detail, Delete, Cancel).

**Fehlend / ausbaufähig:**
- E2E für **Memory** (Seite, Tabs, ggf. Brain).
- E2E für **Agents**.
- E2E für **Packs** (Liste, Client/Date).
- E2E für **Research Insights**.
- E2E für **Start Cycle** und **Cancel Run** (Happy Path + Abbruch).
- E2E für **Follow-up** erstellen.
- E2E für **Report/PDF** (mindestens Button klicken, keine 500).
- E2E für **Logout** und erneuten Zugriff auf geschützte Seite.

**Empfehlung:** Nächste Schritte: Memory-Seite, „Forschung starten“ + Cancel, Logout. Dann Packs, Agents, Insights.

---

## 2. Python Backend (operator/) — Kritische Lücken

### 2.1 Tools — ohne oder mit minimalen Tests

**49 Tools gesamt. Davon mit Tests:** ~24 (u. a. research_common, research_verify, research_budget, research_quality_gate, research_advance_phase, research_abort_report, research_feedback, research_reason, research_web_reader, research_web_search, research_entity_extract, research_memory_policy, research_calibrator, research_knowledge_seed, research_experience_distiller, research_watchdog, research_pdf_reader, research_claim_state_machine, research_question_graph, research_episode_metrics, research_claim_outcome_schema, opportunity_match_clients, opportunity_discover, schema_validate).

**Ohne dedizierte Tool-Tests (massiv ausbaufähig):**

| Tool | Risiko | Begründung |
|------|--------|------------|
| `research_planner.py` | Kritisch | Planungslogik, Phasen |
| `research_progress.py` | Kritisch | Fortschritt, Steps, Heartbeat |
| `research_preflight.py` | Kritisch | Preflight-Checks (teilw. in research/test_quality_gates) |
| `research_synthesize.py` | Kritisch | Synthese-Pipeline |
| `research_eval.py` | Hoch | Bewertungslogik |
| `research_pdf_report.py` | Hoch | Report-Generierung |
| `research_deep_read.py` | Hoch | Deep-Read-Pipeline |
| `research_deep_extract.py` | Hoch | Extraktion |
| `research_critic.py` | Hoch | Bewertung |
| `research_coverage.py` | Hoch | Coverage-Logik |
| `research_cross_domain.py` | Hoch | Cross-Domain |
| `research_auto_followup.py` | Hoch | Follow-up-Auslösung |
| `research_claim_triage.py` | Hoch | Claim-Triage |
| `research_embed.py` | Mittel | Embedding |
| `research_academic.py` | Mittel | Academic-Suche |
| `research_aem_settlement.py` | Hoch | AEM-Settlement (nur Integration test_aem_settlement_flow) |
| `research_attack_taxonomy.py` | Mittel | Taxonomie |
| `research_falsification_gate.py` | Hoch | Falsifikations-Gate |
| `research_market_scoring.py` | Mittel | Scoring |
| `research_portfolio_scoring.py` | Mittel | Portfolio |
| `research_reopen_protocol.py` | Mittel | Reopen |
| `research_source_credibility.py` | Hoch | Credibility (lib hat Tests) |
| `research_token_governor.py` | Mittel | Token-Governance |
| `research_utility_update.py` | Mittel | Utility-Update |
| `research_watch.py` | Mittel | Watch-Logik |
| `opportunity_llm.py` | Hoch | LLM-Calls für Opportunities |
| `opportunity_pack_build.py` | Hoch | Pack-Build-Pipeline |

**Empfehlung:** Höchste Priorität: `research_planner`, `research_progress`, `research_preflight`, `research_synthesize`, `research_eval`, `research_pdf_report`. Dann `research_deep_read`, `research_critic`, `research_claim_triage`, `research_auto_followup`, `research_aem_settlement` (mehr Unit-Tests zusätzlich zu Integration).

---

### 2.2 Lib — ungetestete Module

**Getestet:**  
`lib/brain_context.py`, `lib/memory/utility.py`, `lib/memory/schema.py`, `lib/memory/source_credibility.py`, `lib/memory/principles.py`, `lib/memory/outcomes.py`, `lib/memory` (facade in test_memory_facade).

**Ohne Unit-Tests:**
- `lib/brain.py` — **Kritisch.** Kern des Cognitive Loop (perceive, think, decide, act, reflect). Nur `brain_context` wird getestet; Brain selbst nicht (LLM/Subprocess-Mocks nötig).
- `lib/memory/common.py` — gemeinsame Hilfen.
- `lib/memory/decisions.py` — Entscheidungs-API.
- `lib/memory/entities.py` — Entities.
- `lib/memory/episodes.py` — Episoden.
- `lib/memory/playbooks.py` — Playbooks.
- `lib/memory/quality.py` — Qualitätslogik.
- `lib/memory/reflections.py` — Reflexionen.
- `lib/memory/research_findings.py` — Research-Findings.
- `lib/memory/search.py` — Suche.

**Empfehlung:** Zuerst `lib/brain.py` (mit gemocktem LLM und Memory): mindestens einen vollen Cycle, Fehlerpfade, Governance-Level. Dann `lib/memory/decisions`, `research_findings`, `quality`, `reflections`, `search`, `entities`, `episodes`, `playbooks`, `common`.

---

### 2.3 Integrationstests

**Vorhanden:**  
`test_research_phase_flow`, `test_research_budget_circuit_breaker`, `test_reader_recovery`, `test_aem_settlement_flow`.

**Ausbaufähig:**
- Integration: Research-Pipeline Ende-zu-Ende (init → explore → focus → report → done).
- Integration: Brain-Cycle (mit Mock-LLM) einmal durchlaufen.
- Integration: Memory + Brain (retrieve, decide, store).
- Integration: Packs-Build (opportunity_discover → pack_build) mit Testdaten.

---

### 2.4 Shell-Tests (BATS)

**Vorhanden:**  
`test_op_cli.bats`, `test_research_init.bats`, `test_research_cycle_phases.bats`, `test_budget_circuit_breaker.bats`.

**Ausbaufähig:**
- `op healthcheck` (Exit-Codes, Ausgabe).
- `op job status` / Job-Liste.
- `op research …` Subcommands (list, start, cancel) mit OPERATOR_ROOT.
- Timeouts und Fehlerbehandlung (nicht nur Happy Path).

---

## 3. OpenClaw-Bridge (TypeScript) — komplett ohne Tests

**Dateien:**  
`runner.ts`, `index.ts`, `commands/health.ts`, `commands/jobs.ts`, `commands/queue.ts`, `commands/brain.ts`, `commands/clients.ts`, `commands/research.ts`.

**Status:** Kein Vitest/Jest, keine Testdateien. Die Bridge ruft Operator-Backend/CLI auf und ist für Cursor/IDE-Integration zentral.

**Empfehlung:**
- Test-Setup (Vitest) im Repo (z. B. unter `operator/openclaw-bridge` oder zentral unter `operator/ui` mit Projekt-Referenz).
- Unit-Tests für Command-Parser und Response-Handling (z. B. `research`, `jobs`, `health`, `brain`) mit gemockten Child-Process/HTTP.
- Mindestens ein Integrationstest: Aufruf von `op` mit Mock-Backend.

---

## 4. Root-Skripte / CI

- **operator/package.json:** `test` führt nur `npm run test --prefix ui` aus. Python-Tests laufen nicht mit `npm test` im Root.
- **Python-Tests** werden in CI über `./scripts/run_quality_gate_tests.sh` (pytest) und Shell über BATS ausgeführt — in Ordnung.
- **Empfehlung:** Im Root optional `test:py` oder `test:all` hinzufügen, das sowohl UI- als auch Python-Tests (und ggf. BATS) ausführt, damit lokal „alles“ mit einem Befehl lauffähig ist.

---

## 5. Priorisierte To-dos (kurz)

1. **API-Routes (UI):** Tests für `brain-cycle`, `run-workflow`, `cycle`, `cancel`, `progress` (und Auth 401 überall).
2. **Python:** Unit-Tests für `lib/brain.py`; dann `research_planner`, `research_progress`, `research_synthesize`, `research_preflight`.
3. **Python Tools:** Tests für alle „kritisch/hoch“ gelisteten Tools (siehe Tabelle oben).
4. **Python lib/memory:** Tests für `decisions`, `research_findings`, `quality`, `reflections`, `search`.
5. **UI-Komponenten:** CancelRunButton, RetryButton, ActionButtons, ProjectRowProgress, RuntimeStateBadge, ReviewPanel.
6. **E2E:** Memory-Seite, Start/Cancel Cycle, Logout.
7. **OpenClaw-Bridge:** Test-Setup + Unit-Tests für Commands.
8. **Root:** `test:all` / `test:py` für einheitliches lokales Testen.

---

*Dieses Dokument soll mit dem Code synchron gehalten werden (vgl. docs-sync-with-code).*
