# Memory v2 Masterplan

Ziel: Kein "mehr Kontext", sondern besseres Verhalten durch lernende, ausfuehrbare und auditierbare Memory-Logik, passend zum bestehenden System (`operator.db`, `research-cycle.sh`, `research_*` tools, Quality Gate).

## Leitprinzipien

- Behavior over Prompt: Memory steuert Pipeline-Parameter, nicht nur Prompt-Text.
- Small Context, High Impact: Wenige, hochrelevante Memory-Objekte pro Phase.
- Evidence-first Learning: Lernen nur aus verifizierten Outcomes + Critic + User-Verdict.
- Full Auditability: Jede Memory-Entscheidung muss nachvollziehbar sein.
- Safe by Default: Neue Memory-Logik darf bestehende Runs nie blockieren (Feature Flags + Fallback).

## Zielarchitektur

### 1) Episodic Run Memory (ERMs)

Jeder abgeschlossene Run wird als Episode gespeichert:

- Frage, Domain, Plan-Muster (Query-Type-Mix)
- Quellenmix, Gate-Metriken, Critic-Score, User-Verdict, Fail-Codes
- "Was hat geholfen / geschadet" in strukturierter Form

Nutzen: Neue Fragen koennen auf ganze Erfolgsrezepte frueherer, aehnlicher Runs zugreifen.

### 2) Executable Strategy Memory (ESM)

Neue Memory-Klasse mit ausfuehrbaren Strategy-Profilen (JSON-Policies), z. B.:

- `preferred_query_types` (medical/academic/web Gewichte)
- `domain_rank_overrides`
- `relevance_threshold`
- `critic_threshold`
- `revise_rounds`
- `required_source_mix`

Nutzen: Learning beeinflusst direkt Verhalten in Planner, Explore, Focus und Critic-Gate.

### 3) Provenance Source Memory

Domain/Quelle bekommt Track Record:

- Verifiziert-Rate, Relevanz-Rate, Fail-Rate in aehnlichen Themen
- Einfluss auf Ranking und Coverage

Nutzen: System lernt nicht nur was stimmt, sondern auch wo gute Evidenz herkommt.

### 4) Leichtgewichtiger Graph-Layer auf SQLite

Kein separates Graph-Produkt. In SQLite:

- Knoten: `run_episode`, `strategy_profile`, `principle`, `source_domain`
- Kanten: `derived_from`, `used_in`, `improved`, `failed_on`

Nutzen: Relationale Lernpfade ohne Infrastrukturbruch.

## Implementierungsphasen

## Phase A - Foundation (Schema + Write-Path)

Dauer: 2-3 Tage

### Neue Tabellen

- `run_episodes`
- `strategy_profiles`
- `strategy_application_events`
- `source_domain_stats_v2`
- `memory_decision_log`

### Write-Path Integration

- In `research-cycle.sh` bei `done`/`failed`: Episode persistieren
- In `research_experience_distiller.py`: Prinzipien + Strategy-Proposal generieren
- In `research_utility_update.py`: Utility-Updates auf Strategy-Elemente erweitern

Abnahme:

- Jeder Run erzeugt 1 Episode + Decision Logs
- Keine Regression in bestehender Pipeline

## Phase B - Read-Path Strategy Injection

Dauer: 3-4 Tage

### Integrationspunkte

- `research_planner.py`: passende Strategy vor Query-Erzeugung laden
- Ranking in `research-cycle.sh`: Domain/Type-Gewichte aus Strategy anwenden
- Critic-Block: Threshold/Revisionsrunden strategy-basiert mit Guards

### Safety

- Feature Flag: `RESEARCH_MEMORY_V2_ENABLED=1`
- Fallback bei Fehlern: alter statischer Pfad

Abnahme:

- Sichtbar veraenderte Plan-/Ranking-Entscheidungen bei aehnlichen Themen
- Keine neuen Hard-Fails durch Memory

## Phase C - Closed-Loop Learning

Dauer: 3 Tage

### Update-Regeln

- Strategy-Score steigt bei `critic_pass + user_approved + evidence_gate_pass`
- Strategy-Score sinkt bei `failed_quality_gate`, schwacher Claim-Support-Rate oder User-Reject
- Domain-spezifische Varianten (medical, finance, devtools)

### Konfliktloesung

- Mehrere passende Strategien: weighted ensemble + confidence
- Bei niedriger confidence: conservative default

Abnahme:

- Nach 5-10 aehnlichen Runs steigt Pass-Rate messbar
- Strategy-Auswahl wird stabiler

## Phase D - Explainability + UI

Dauer: 2 Tage

### UI-Erweiterung auf Research-Detail

"Memory Applied" Panel:

- welche Strategy gewaehlt wurde
- welche Regeln aktiv waren
- welche Domains bevorzugt wurden
- erwarteter Nutzen

Post-run:

- was bestaetigt/widerlegt wurde

Abnahme:

- Team kann Memory-Entscheidungen ohne DB-Forensik nachvollziehen

## KPIs

- Critic Pass Rate (ohne manuelle Eingriffe)
- Average Revision Rounds bis Pass
- Verified Claim Rate
- Noise Ratio in Findings
- Cost per successful report
- Loop/Terminal Fail Frequency

Zielwerte (2 Wochen):

- +20-30% Critic-Pass
- -25% unnoetige Revisionen
- -15% Cost pro erfolgreichem Run

## Risiken und Gegenmassnahmen

- Overfitting auf alte Themen: Domain + Similarity Guards + conservative fallback
- Zu aggressive Strategy-Steuerung: harte Min/Max-Bounds (z. B. Threshold 0.50-0.65)
- Komplexitaet: `memory_decision_log` + Explainability-UI verpflichtend
- Schlechte Lerndaten: nur validierte Runs fuer Strategy-Updates

## Warum das zum aktuellen System passt

- Nutzt existierende Stacks: `operator.db`, Distiller, Utility, Quality Gate
- Kein Plattformwechsel, keine neue Infra
- Loest aktuelle Kernprobleme:
  - Critic-Haenger
  - irrelevante Quellen
  - gelernt, aber nicht angewandt

## Nächster konkreter Schritt

Tech-Design-Dokument erstellen mit:

- exakten DB-Schemata (DDL)
- Strategy-JSON-Schema
- Integrationspunkten pro Datei (`research_planner.py`, `research-cycle.sh`, `research_experience_distiller.py`, `research_common.py`)
- Rollout-/Migration-Plan via Feature Flags

