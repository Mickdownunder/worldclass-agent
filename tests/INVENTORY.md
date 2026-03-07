# Inventar testbarer Einheiten (Phase A)

Alle testbaren Einheiten des Operator-/Research-/Agent-Stacks. Basis-Check: Module importierbar und smoke-getestet vor Testschreibung.

## Python-Module

### lib/
| Modul | Getestet in | Tests |
|-------|-------------|-------|
| lib.memory (Schema, Episodes, Decisions, …) | tests/unit/test_memory_*.py | schema, common, search, outcomes, utility, v2, principles, source_credibility, facade |
| lib.brain_context | tests/unit/test_brain_context.py | compile, _filter_low_signal_reflections |
| lib.plumber | tests/unit/test_plumber.py | classify_non_repairable (pure) |

### tools/
| Bereich | Getestet in |
|---------|-------------|
| research_verify, research_quality_gate, research_advance_phase | tests/tools/test_research_verify.py, test_research_quality_gate.py, test_research_advance_phase.py |
| research_budget, research_sandbox, research_synthesize* | tests/tools/test_research_budget.py, test_research_sandbox.py, test_research_synthesize_*.py |
| research_claim_*, research_token_governor, research_web_reader | tests/tools/test_research_claim_*.py, test_research_token_governor.py, test_research_web_reader.py |
| research_common, research_planner_memory_v2, research_episode_metrics | tests/tools/test_research_common.py, test_research_planner_memory_v2.py, test_research_episode_metrics.py |
| research_entity_extract, research_memory_policy, research_feedback | tests/tools/test_research_entity_extract.py, test_research_memory_policy.py, test_research_feedback.py |
| research_abort_report, research_experiment_gate, research_knowledge_seed | tests/tools/test_research_abort_report.py, test_research_knowledge_seed.py, test_research_experiment_gate.py |
| research_calibrator, research_watchdog, research_pdf_reader, research_web_search | tests/tools/test_research_calibrator.py, test_research_watchdog.py, test_research_pdf_reader.py, test_research_web_search.py |
| trigger_council, schema_validate | tests/tools/test_trigger_council*.py, test_schema_validate.py |

## Workflows / Shell

| Einheit | Getestet in |
|---------|-------------|
| bin/op (CLI) | tests/shell/test_op_cli.bats, **tests/integration/test_op_cli_smoke.py** (ohne Bats) |
| research-init | tests/shell/test_research_init.bats |
| research-cycle / advance_phase | tests/shell/test_research_cycle_phases.bats |
| budget circuit breaker | tests/shell/test_budget_circuit_breaker.bats |

Workflows (research-phase.sh, research-cycle.sh, …): über Bats und tests/integration/test_research_phase_flow.py abgedeckt.

## UI / API

| Einheit | Getestet in |
|---------|-------------|
| Next.js API-Routen (health, research, memory, auth, …) | ui/src/app/api/__tests__/ (Jest) — im UI-Repo |

Operator-repo tests/ enthält keine Browser- oder Next.js-Server-Tests; API-Logik wird in ui/ getestet.

## Integration

| Bereich | Getestet in |
|---------|-------------|
| Research-Phasenfluss, Budget-Circuit-Breaker | tests/integration/test_research_phase_flow.py, test_research_budget_circuit_breaker.py |
| AEM-Settlement, Reader-Recovery | tests/integration/test_aem_settlement_flow.py, test_aem_adversarial.py, test_reader_recovery.py |

## Research / Quality-Gates

| Bereich | Getestet in |
|---------|-------------|
| Quality-Gates, Preflight, Connect/Reader | tests/research/test_quality_gates.py |
| Audit-Consistency | tests/research/test_audit_consistency.py |

## Coverage (≥ 60 %)

Coverage-Ziel **60 %** für lib + tools. Ausgenommen in `.coveragerc`: lib/brain.py, lib/plumber.py; tools (LLM-/Script-Entry-Points): research_conductor, research_orchestrator, research_pdf_report, research_experience_distiller, research_synthesize, research_planner, research_verify, research_reason, research_experiment, research_entity_extract sowie weitere reine Entry-Points (relevance_gate, reopen_protocol, …). Vollständige Liste in `.coveragerc` unter `omit`.

## Fixtures (validiert)

- **conftest.py:** mock_operator_root (temp OPERATOR_ROOT, research/, conf/), tmp_project (project.json + findings/sources/reports/verify/explore), mock_env (RESEARCH_PROJECT_ID), memory_conn (in-memory SQLite mit init_schema).
- **tmp_project:** project.json mit id, question, phase, status — valide Keys für load_project.
- **memory_conn:** init_schema erzeugt alle Tabellen (episodes, decisions, reflections, project_outcomes, …); idempotent.
