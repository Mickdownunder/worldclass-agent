# System Audit Report — Operator Project

**Datum:** 2026-02-27  
**Scope:** Vollständiger Code-Scan (keine .md gelesen, nur Quellcode)

---

## 1. Frontend (Next.js / React)

**Status: ISSUES FOUND**

### Critical

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 1 | `ui/src/proxy.ts` | 1-19 | **Dead middleware — API Auth Bypass.** `proxy()` + `config.matcher` exportiert, aber kein `middleware.ts` existiert. Die geplante Session-Prüfung auf allen `/api/`-Routen ist nicht aktiv. | critical |
| 2 | `ui/src/app/api/events/route.ts` | 11 | Kein Auth-Check auf GET — Audit-Log + Jobs öffentlich zugänglich | critical |
| 3 | `ui/src/app/api/memory/route.ts` | 6 | Kein Auth-Check — Memory-Summary öffentlich | critical |
| 4 | `ui/src/app/api/memory/decisions/route.ts` | 6 | Kein Auth-Check — Brain Decisions öffentlich | critical |
| 5 | `ui/src/app/api/memory/entities/route.ts` | 6 | Kein Auth-Check — Knowledge Graph Entities öffentlich | critical |
| 6 | `ui/src/app/api/memory/credibility/route.ts` | 6 | Kein Auth-Check — Source Credibility öffentlich | critical |
| 7 | `ui/src/app/api/memory/outcomes/route.ts` | 6 | Kein Auth-Check — Project Outcomes öffentlich | critical |
| 8 | `ui/src/app/api/memory/principles/route.ts` | 6 | Kein Auth-Check — Learned Principles öffentlich | critical |
| 9 | `ui/src/app/api/agents/route.ts` | 6 | Kein Auth-Check — Agent/Workflow Details öffentlich | critical |
| 10 | `ui/src/app/api/packs/route.ts` | 6 | Kein Auth-Check — Pack Listing öffentlich | critical |
| 11 | `ui/src/app/api/jobs/route.ts` | 9 | Kein Auth-Check — Job Summaries öffentlich | critical |
| 12 | `ui/src/app/api/jobs/[id]/route.ts` | 6 | Kein Auth-Check — Individual Job Detail + Logs öffentlich | critical |
| 13 | `ui/src/app/api/research/calibrated-thresholds/route.ts` | 6 | Kein Auth-Check — Calibrated Thresholds öffentlich | critical |

**Root Cause #2-#13:** `proxy.ts` sollte alle `/api/`-Routen (außer `/api/auth/`) hinter Session-Check gaten. Da es toter Code ist, sind 13 GET-Endpoints unauthentifiziert. POST/DELETE-Endpoints prüfen Auth individuell.

### Warning

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 14 | `ui/src/app/(dashboard)/memory/page.tsx` | 70-71 | `totals?.principles` und `totals?.outcomes` existieren nicht im `MemorySummary.totals`-Type. Zeigt immer "—". | warning |
| 15 | `ui/src/components/ActionButtons.tsx` | 1-82 | Dead File — nie importiert, ersetzt durch `DashboardQuickActions.tsx` | warning |
| 16 | `ui/src/app/(dashboard)/research/[id]/ReportView.tsx` | 1-42 | Dead File — nie importiert, ersetzt durch `tabs/ReportTab.tsx` | warning |
| 17 | `ui/src/app/(dashboard)/memory/BrainTabs.tsx` | 12-19 | Excessive `any` Usage — 6 State-Variablen als `any`, gesamte TypeScript-Safety verloren | warning |

### Info

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 18 | `ui/src/app/api/health/route.ts` | 6 | Kein Auth-Check — wahrscheinlich beabsichtigt für Health Probes, exposed aber Disk Usage, Load, Brain Status | info |
| 19 | `ui/src/app/api/research/[id]/progress/route.ts` | 5 | Kein Auth-Check — Redirect zu Auth-geschütztem Endpoint, niedriges Risiko | info |

**Fix #1 (löst #1-#13):** `ui/src/middleware.ts` erstellen, das `proxy.ts` importiert und re-exportiert.

---

## 2. Backend / CLI

**Status: CLEAN**

Alle CLI-Dateien (`bin/op`, `bin/brain`, `bin/daily-run`) sind korrekt strukturiert. Shebang-Zeilen, Imports, Command-Dispatch, venv-Bootstrapping — alles verifiziert. Keine toten Pfade, fehlenden Dependencies oder undefinierten Variablen.

---

## 3. Workflows

**Status: ISSUES FOUND**

### Critical

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 1 | `workflows/autopilot-infra.sh` | 29 | **Broken Heredoc.** `"$(date -u +%Y-%m-%dT%H:%M:%SZ")"` — das `"` vor `)` bricht die Command Substitution. `signals.json` wird leer geschrieben. | critical |

### Warning

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 2 | `workflows/research-cycle.sh` | 495 | `GATE_PASS` Fallback geht zu stdout statt Variable. `GATE_PASS=$(...) || echo "0"` — bei Fehler bleibt Variable leer. | warning |
| 3 | `workflows/research-cycle.sh` | 604 | Gleicher `GATE_PASS` Fallback-Bug (zweites Vorkommen) | warning |
| 4 | `workflows/prioritize.sh` | 7 | Hartes `cp` ohne Existenz-Check, crasht unter `set -e` | warning |
| 5 | `workflows/tool-backlog-add.sh` | 6 | `grep -q` auf möglicherweise nicht existenter Datei | warning |
| 6 | `workflows/tool-use.sh` | 7 | Hardcoded Tool-Call ohne Existenz-Check | warning |

### Info

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 7 | `workflows/goal-progress.sh` | 4-7 | Kein `mkdir -p` für Parent-Verzeichnis | info |
| 8 | `workflows/opportunity-ingest.sh` | 50 | `datetime.utcnow()` deprecated seit Python 3.12 | info |
| 9 | `workflows/opportunity-dispatch.sh` | 88 | Gleiche `utcnow()` Deprecation | info |
| 10 | `workflows/queue-run.sh` | 61 | Gleiche `utcnow()` Deprecation | info |
| 11 | `workflows/factory-cycle.sh` | 115-116 | Undeclared `jq` Dependency | info |

---

## 4. Python Tools

**Status: ISSUES FOUND**

AEM-Pipeline JSON-Feld-Contracts sind über alle 14 Module konsistent. Alle Import-Chains resolven korrekt.

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 1 | `tools/research_episode_metrics.py` | 199 | Race Condition bei `append_episode_metrics` — liest+schreibt ganze Datei ohne File-Lock | warning |
| 2 | `tools/research_attack_taxonomy.py` | 89 | Nur 2 von 7 Attack-Klassen werden generiert (default `max_per_claim=2`). 5 Klassen sind Dead Code. | warning |
| 3 | `tools/research_claim_state_machine.py` | 162-174 | Transition `evidenced → stable` umgeht Attack-Coverage. Widerspricht Docstring-Regel. | warning |
| 4 | `tools/research_synthesize.py` | 376 | `_is_claim_like_sentence` triggert bei jeder Sentence ≥18 Wörter — False Positives bei enforce/strict Mode | warning |
| 5 | `tools/research_evidence_index.py` | 79 | Kein Check ob `findings/` Directory existiert | info |
| 6 | `tools/research_market_scoring.py` | 55 | `oracle_integrity_pass` akzeptiert low-confidence tentative Claims (p=0.5) | info |
| 7 | `tools/research_portfolio_scoring.py` | 33 | `duplicate_penalty` immer 0.0 — TODO comment, Anti-Gaming unvollständig | info |

---

## 5. Tests

**Status: ISSUES FOUND**

### Test Coverage

| Modul | Test? | Anmerkung |
|-------|-------|-----------|
| `research_claim_state_machine.py` | ✅ | 10 Tests |
| `research_claim_outcome_schema.py` | ✅ | 8 Tests |
| `research_episode_metrics.py` | ✅ | 6 Tests |
| `research_token_governor.py` | ✅ | 6 Tests |
| `research_question_graph.py` | ✅ | 3 Tests |
| `research_aem_settlement.py` | ✅ | Integration |
| `research_synthesize.py` | ✅ | Contract Tests |
| `research_falsification_gate.py` | 🔶 | Nur Integration |
| `research_market_scoring.py` | 🔶 | Nur Integration |
| `research_portfolio_scoring.py` | 🔶 | Nur Integration |
| `research_evidence_index.py` | 🔶 | Nur Integration |
| `research_reopen_protocol.py` | ❌ | Kein Test |
| `research_contradiction_linking.py` | ❌ | Kein Test |
| `research_claim_triage.py` | ❌ | Kein Test |
| `research_attack_taxonomy.py` | ❌ | Kein Test |
| `research_utility_update.py` | ❌ | Kein Test |
| `research_cross_domain.py` | ❌ | Kein Test |
| `research_pdf_report.py` | ❌ | Kein Test |
| `research_critic.py` | ❌ | Kein Test |
| `research_auto_followup.py` | ❌ | Kein Test |
| +10 weitere Module | ❌ | Kein Test |

### Spezifische Issues

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 1 | `tests/tools/test_research_synthesize_contract.py` | 133-146 | Fake Test — wirft Exception manuell statt Code zu testen | warning |
| 2 | `tests/tools/test_research_synthesize_contract.py` | 149-158 | Gleicher Fake-Test, zweites Vorkommen | warning |
| 3 | `tests/tools/test_research_experience_distiller.py` | 10-33 | Tests testen Inline-Logik, nicht das Modul. Import von `main` unused. | warning |
| 4 | `requirements-test.txt` | 1 | Fehlt: `beautifulsoup4`, `jsonschema` für vollständige Test-Suite | warning |
| 5 | `tests/tools/test_research_feedback.py` | 18-34 | Testet manuelles File-Write, nicht das Modul | info |
| 6 | `tests/research/test_quality_gates.py` | 112-128 | Erfordert Live-DB, unvollständiger Skip-Handler | info |
| 7 | `tests/research/test_audit_consistency.py` | 48-68 | Permanent übersprungen (Fixture-Dir fehlt) | info |
| 8 | `tests/tools/` | — | Fehlende `__init__.py` in Unterverzeichnissen | info |

---

## 6. Konfiguration

**Status: ISSUES FOUND**

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 1 | `conf/secrets.env` | 1-6 | **Plaintext API Keys.** Zwar in `.gitignore`, aber kein Encryption at Rest. | critical |
| 2 | `ui/.env.local` | 3 | **Weak Session Secret.** `UI_SESSION_SECRET=operator-ui-session-secret-change-in-production` — Default-String, Sessions fälschbar. | critical |
| 3 | `conf/secrets.env` | — | `BRAVE_API_KEY` im Code referenziert aber nie definiert. `search_brave()` ist toter Code. | warning |
| 4 | `conf/policy.env` | — | `AEM_ENFORCEMENT_MODE` nirgends definiert. Immer default `"observe"`. Enforce/Strict-Modus unerreichbar ohne externe Injektion. | warning |
| 5 | `openclaw-bridge/runner.ts` | 9 | Hardcoded `OPERATOR_ROOT`, ignoriert env-Variable | warning |
| 6 | `package.json` (root) | 5-7 | Kein `build`-Script im Root-Package — `npm run build` schlägt fehl | info |
| 7 | `ui/.env.local.example` | 11-12 | `UI_TELEGRAM_NOTIFY` nicht in `.env.local`, Telegram-Benachrichtigungen stillschweigend deaktiviert | info |

---

## 7. Daten-Contracts

**Status: ISSUES FOUND**

### Cross-Module Artifact Matrix

| Artefakt | Writer | Reader | Status |
|----------|--------|--------|--------|
| `project.json` | `research-init.sh`, `research-cycle.sh`, `research_common.py`, `research_preflight.py`, `research_advance_phase.py` | ~20 Module | ✅ OK |
| `claims/ledger.jsonl` | `research_claim_state_machine.py` | 7 Module | ⚠️ Issues |
| `market/settlements.jsonl` | `research_market_scoring.py` | `research_aem_settlement.py` | ✅ OK |
| `attacks/attacks.jsonl` | `research_attack_taxonomy.py` | `research_falsification_gate.py` | ✅ OK |
| `evidence/evidence_index.jsonl` | `research_evidence_index.py` | `research_portfolio_scoring.py` | ✅ OK |
| `policy/episode_metrics.jsonl` | `research_episode_metrics.py` | `research_token_governor.py` | ✅ OK |
| `questions/questions.json` | `research-init.sh`, `research_question_graph.py` | `research_claim_triage.py`, `research_feedback.py` | ⚠️ Issues |

### Spezifische Feld-Issues

| # | Problem | Schweregrad |
|---|---------|-------------|
| 1 | `research_market_scoring.py` liest `falsification_status` aus Ledger — wird nie von `research_claim_state_machine.py` geschrieben. Fragile implizite Ordering-Abhängigkeit. | warning |
| 2 | `settlement_confidence` ist Phantom-Feld — wird von keinem Modul geschrieben, überall default 0.5/0.7 | warning |
| 3 | **`questions.json` Schema-Split:** Init schreibt `{open: [], answered: []}`, AEM schreibt `{questions: [...], version: "v1"}`. `research_feedback.py` nutzt `"open"` Key — funktioniert nicht nach `build_question_graph`. Feedback geht verloren. | warning |
| 4 | `research_episode_metrics.py` liest `outcome_type`, `claim_type`, `p_true`, `confidence`, `claim_support_rate` — nie geschrieben. IG-Metrik ist effektiv Dead Data. | warning |
| 5 | `research_falsification_gate.py` liest `outcome_type`, `resolution_authority`, `resolution_method` — nie gesetzt. Schema-Validierung ist No-Op. | warning |
| 6 | `tentative_ttl` wird geschrieben (default 3) aber nie dekrementiert oder gelesen — Dead Data | info |

---

## 8. Memory / Brain

**Status: ISSUES FOUND**

| # | Datei | Zeile | Problem | Schweregrad |
|---|-------|-------|---------|-------------|
| 1 | `lib/brain.py` | 36-42 | **Hardcoded `Path.home() / "operator"`** ignoriert `OPERATOR_ROOT` env-Variable. Bricht bei Deployment außerhalb `~/operator`. | warning |
| 2 | `lib/memory/__init__.py` | 30 | **`DB_PATH` hardcoded auf `~/operator/memory/operator.db`** — gleiche Ursache wie #1 | warning |
| 3 | `lib/memory/playbooks.py` | 49-52 | SQL `GROUP BY domain HAVING version = MAX(version)` ist non-deterministisch bei gleicher Version | warning |
| 4 | `lib/memory/schema.py` | 85-93 | `research_findings` Columns werden per Migration hinzugefügt — keine Error-Handling falls Migration fehlschlägt | warning |
| 5 | `lib/brain_context.py` | 31 | `retrieve_with_utility` für Reflections nutzt `relevance=0.5` Fallback — Utility Re-Ranking ist verzerrt | warning |
| 6 | `lib/memory/search.py` | 6-8 | Leerer Query matched alles (Full-Table-Scan) | info |
| 7 | `lib/brain.py` | 92 | `sys.path.insert` bei jedem Aufruf statt einmalig bei Import | info |
| 8 | `lib/memory/schema.py` | 206-208 | `UPDATE ... SET admission_state = 'quarantined'` bei jeder DB-Connection (idempotent aber overhead) | info |

---

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| **Critical Issues** | 16 |
| **Warnings** | 33 |
| **Info** | 20 |
| **Bereiche CLEAN** | 1/8 (Backend/CLI) |

### Top-5 Prioritäten

1. **🔴 Middleware aktivieren** (`ui/src/middleware.ts` erstellen) — Fixt 13 unauthentifizierte API-Endpoints auf einen Schlag.

2. **🔴 Session Secret rotieren** — `UI_SESSION_SECRET` in `.env.local` durch einen echten Random-Key ersetzen. Sessions sind aktuell fälschbar.

3. **🔴 `autopilot-infra.sh` Heredoc fixen** — Broken Command Substitution erzeugt leere `signals.json`, Downstream-Workflows bekommen Garbage-Input.

4. **🟡 `questions.json` Schema vereinheitlichen** — Init-Schema (`open/answered`) und AEM-Schema (`questions/version`) divergieren. `research_feedback.py` verliert Redirects nach erster AEM-Runde.

5. **🟡 Phantom-Felder in Ledger-Pipeline dokumentieren/implementieren** — 6+ Felder werden gelesen aber nie geschrieben (`falsification_status`, `settlement_confidence`, `outcome_type`, `p_true`, etc.). Entweder im State-Machine-Writer implementieren oder Reader-Defaults explizit dokumentieren.
