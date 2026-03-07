# Monolithen und Dateien mit zu vielen Aufgaben

Kurze Übersicht: wo es sehr große oder verantwortungsreiche Dateien gibt und was sie tun.

---

## Klare Monolithen / zu viele Aufgaben

### 1. `workflows/research-phase.sh` — **Refaktoriert (Dispatcher ~180 Zeilen)**
- **Rolle:** Einstieg für eine Research-Phase (explore → focus → connect → verify → synthesize). Lädt Config, Lock/Progress, Helpers und sourced die jeweilige Phasen-Logik.
- **Struktur:** `workflows/research-phase.sh` (Dispatcher); `workflows/research/lib/config.sh`, `lock_and_progress.sh`, `helpers.sh`; `workflows/research/phases/explore.sh`, `focus.sh`, `connect.sh`, `verify.sh`, `synthesize.sh`. Setup, Lock, Progress, Conductor, Council, PDF, Fortschritt bleiben koordiniert; Phasen-Logik ist pro Phase in eigene Dateien ausgelagert.
- **Stand:** Aufteilung umgesetzt; Verhalten unverändert. Siehe `docs/RESEARCH_PHASE_REFACTOR_PLAN.md`.

### 2. `lib/plumber/` — **Refaktoriert (Paket)**
- **Rolle:** Self-Healing wie zuvor; Einstieg bleibt `from lib.plumber import run_plumber` etc.
- **Struktur:** `lib/plumber/__init__.py` (Re-Export), `constants.py`, `fingerprints.py`, `diagnose.py`, `fix.py`, `llm_fix.py`, `run.py`. Alte `lib/plumber.py` entfernt.
- **Stand:** Aufteilung umgesetzt; Verhalten unverändert. Siehe `docs/PLUMBER_REFACTOR_PLAN.md`.

### 3. `lib/memory/__init__.py` + `lib/memory/summary.py` + `lib/memory/embedding.py` + `lib/memory/retrieval.py` — **Teilrefaktoriert**
- **Rolle:** Unverändert: Fassade für das gesamte Memory-System (Episodes, Decisions, Reflections, Playbooks, Quality, Research Findings, Entities, Principles, Utility, Outcomes, Source Credibility, v2, state_summary).
- **Stand:** `state_summary` in `lib/memory/summary.py` (`build_state_summary(memory)`); `_embed_query` in `lib/memory/embedding.py` (`embed_query`); `retrieve_with_utility`-Logik in `lib/memory/retrieval.py` (`retrieve_with_utility_impl`). `Memory.retrieve_with_utility` ruft nur noch `retrieve_with_utility_impl(self, ...)`. API unverändert (`Memory`, `DB_PATH`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`).

### 4. `tools/research_synthesize.py` + `tools/synthesis/` — **Refaktoriert (Paket)**
- **Rolle:** Unverändert: Komplette Synthese-Pipeline (Outline, Sections, Claim-Registry, Provenance, Gap, Epistemic Reflect, Executive Summary, RSM, Tipping, Scenario, Conclusions, Factuality Guard, Contract, Checkpoints).
- **Struktur:** `tools/research_synthesize.py` (~45 Zeilen Einstieg + Re-Export); Paket `tools/synthesis/`: `constants.py`, `data.py`, `ledger.py`, `outline.py`, `checkpoint.py`, `sections.py`, `blocks.py`, `contract.py`, `run.py`, `__init__.py`.
- **Stand:** Aufteilung umgesetzt; API unverändert (`run_synthesis`, `validate_synthesis_contract`, `normalize_to_strings` etc.). Siehe `docs/RESEARCH_SYNTHESIZE_REFACTOR_PLAN.md`.

### 5. `lib/brain/` — **Refaktoriert (Paket)**
- **Rolle:** Unverändert: Cognitive Core (Perceive → Understand → Think → Decide → Act → Reflect), run_cycle, reflect_on_job, Plumber-Integration.
- **Struktur:** Paket `lib/brain/`: `constants.py`, `helpers.py`, `perceive.py`, `understand.py`, `think.py`, `decide.py`, `act.py`, `reflect.py`, `run.py` (Brain-Klasse), `__init__.py` (Re-Export). Alte `lib/brain.py` entfernt.
- **Stand:** Aufteilung umgesetzt; API unverändert (`from lib.brain import Brain`, `_reflection_is_low_signal`, `_compact_state_for_think`). Siehe `docs/BRAIN_REFACTOR_PLAN.md`.

### 6. `tools/pdf_report/` — **Refaktoriert (Paket)**
- **Rolle:** Unverändert: Intelligence Artifact PDF aus Research-Daten (Cover, Outcome Layer, Claim State Map, Belief Trajectory, Evidence, Disagreement, Insight, Action, Auditor Mode, References).
- **Struktur:** Einstieg `tools/research_pdf_report.py` (~30 Zeilen); Paket `tools/pdf_report/`: `tokens.py` (Design-Tokens, `esc`), `styles.py` (CSS), `data.py` (load report/verify, extract sections, enriched claims), `claims.py` (lifecycle state, confidence), `sections.py` (alle Section-Builder), `render.py` (HTML bauen, WeasyPrint), `__init__.py` (main).
- **Stand:** Aufteilung umgesetzt; API unverändert (`python3 research_pdf_report.py <project_id>`).

### 7. `tools/planner/` — **Refaktoriert (Paket)**
- **Rolle:** Unverändert: LLM-Plan, Gap-Fill, Refinement, Perspective-Rotate; Memory-v2-Strategie-Overlay.
- **Struktur:** Einstieg `tools/research_planner.py` (~45 Zeilen); Paket `tools/planner/`: `constants.py`, `helpers.py`, `fallback.py`, `sanitize.py`, `memory.py` (Strategy Load/Apply/Persist), `prior.py`, `plan.py` (build_plan, load_project_plan), `gap_fill.py`, `perspective.py`, `__init__.py` (main).
- **Stand:** Aufteilung umgesetzt; API unverändert (`research_planner.py <question> [project_id]`, `--gap-fill`, `--refinement-queries`, `--perspective-rotate`, `--fallback-only`; `build_plan`, `build_gap_fill_queries`, `build_refinement_plan`, `build_perspective_rotate_queries`).

### 8. `tools/verify/` — **Refaktoriert (Paket)**
- **Rolle:** Unverändert: Source Reliability, Claim Verification, Fact-Check, Claim Ledger, CoVe-Overlay; Tagging im Report.
- **Struktur:** Einstieg `tools/research_verify.py` (~45 Zeilen); Paket `tools/verify/`: `common.py` (load_sources, load_findings, load_connect_context, llm_json, …), `evidence.py` (source_reliability, fact_check), `claim_extraction.py` (claim_verification, run_claim_verification_cove), `ledger.py` (build_claim_ledger, apply_verified_tags_to_report), `__init__.py` (main).
- **Stand:** Aufteilung umgesetzt; API unverändert (`research_verify.py <project_id> source_reliability|claim_verification|fact_check|claim_ledger|claim_verification_cove`; `build_claim_ledger`, `apply_verified_tags_to_report`).

---

## Große Dateien (noch vertretbar, aber prüfen)

| Datei | Zeilen | Hinweis |
|-------|--------|--------|
| `bin/op` | ~608 | Ein CLI mit vielen Subcommands (job new/status/get/run/retry, healthcheck). Verantwortungen klar getrennt (Job-Lifecycle, Lock, Run, Health). Kann so bleiben oder in `lib/op_*.py` ausgelagert werden. |
| `lib/memory/memory_v2.py` | ~972 | Memory v2 (Strategien, Profile, Graph). Groß, aber thematisch geschlossen. |
| `tools/research_synthesize.py` | ~45 | Einstieg; Logik in `tools/synthesis/`. |
| `tools/research_pdf_report.py` | ~30 | Einstieg; Logik in `tools/pdf_report/` (tokens, styles, data, claims, sections, render). |
| `tools/research_planner.py` | ~45 | Einstieg; Logik in `tools/planner/` (constants, helpers, fallback, sanitize, memory, prior, plan, gap_fill, perspective). |
| `tools/research_verify.py` | ~45 | Einstieg; Logik in `tools/verify/` (common, evidence, claim_extraction, ledger). |
| `tools/research_conductor.py` | ~750 | Conductor-Logik. Noch überschaubar. |
| `workflows/research-phase.sh` | ~180 | Dispatcher; Logik in `workflows/research/lib/` und `workflows/research/phases/`. |

---

## UI: große Komponenten

| Datei | Zeilen | Hinweis |
|-------|--------|--------|
| `ui/src/lib/operator/research.ts` | ~983 | Viele Research-API- und State-Funktionen. Könnte in `research/api.ts`, `research/state.ts`, `research/project.ts` o.ä. geteilt werden. |
| `ui/src/components/command-center/CommandCenterClient.tsx` | ~966 | Command Center: Health, Projekte, Events, Quick-Actions. Könnte in Subkomponenten (HealthBlock, ProjectList, EventFeed, QuickActions) und Hooks ausgelagert werden. |
| `ui/src/app/(dashboard)/research/[id]/page.tsx` | ~791 | Projekt-Detail: Layout, Tabs, State. Tabs sind vermutlich eigene Komponenten; Seite könnte schlanker werden. |
| `ui/src/app/(dashboard)/memory/tabs/PlumberTab.tsx` | ~578 | Ein Tab mit viel Logik. Logik in Hooks/Utils auslagern. |

---

## Zusammenfassung

- **Stärkste Monolithen:** `lib/memory/__init__.py` (state_summary in summary.py ausgelagert). (`workflows/research-phase.sh`, `lib/plumber.py`, `tools/research_synthesize.py`, `lib/brain.py` wurden in lib/phases/, lib/plumber/, tools/synthesis/, lib/brain/ aufgeteilt.)
- **Zu viele Aufgaben** = eine Datei/Klasse/Skript, die gleichzeitig: Config, mehrere Phasen/Pipelines, Diagnose + Fix, oder eine sehr große Fassade mit 50+ Methoden bündelt.
- **Empfohlene Richtung:** Phasen/Schritte in eigene Module/Skripte ziehen, Fassaden dünn halten, große „Runner“ in klar benannte Submodule aufteilen (ohne Big Bang Refactor).
