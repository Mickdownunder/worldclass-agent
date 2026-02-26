# Testplan: State & Memory (projektübergreifendes Lernen)

**Priorität:** Bugs hier sind unsichtbar und zerstören das Lernverhalten über Wochen.  
**Fokus:** Laplace-Formeln, SQL-Logik, Two-Phase-Retrieval, Calibrator, Brain Context.

Alle Tests: reine Unit-Tests mit SQLite in-memory, kein LLM, Laufzeit Millisekunden.

---

## Priorität 1: Muss-Tests (ein Bug hier ist unsichtbar und zerstörerisch)

### 1. `lib/memory/` — Laplace-Formeln und SQL-Logik

#### 1.1 `tests/lib/test_memory_principles.py` (principles.py)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_update_usage_success_formula_first_use` | usage=0, success_count=0 → nach update_usage_success(pid, True) | metric_score = (0+1)/(0+2) = 0.5 |
| `test_update_usage_success_formula_after_success` | usage=1, success_count=1 → update(pid, True) | metric_score = (2)/(4) = 0.5 |
| `test_update_usage_success_formula_after_failure` | usage=1, success_count=1 → update(pid, False) | metric_score = (1)/(4) = 0.25 |
| `test_update_usage_success_usage_1000` | usage=999, success_count=500 → update(pid, True) | metric_score = 501/1002 ≈ 0.5; keine Overflow/Instabilität |
| `test_update_usage_success_nonexistent_principle` | principle_id nicht in DB | Kein Crash, keine Änderung |
| `test_insert_and_get` | insert() → get() | Zeile mit principle_type, description, usage_count=0, success_count=0 |
| `test_search_returns_matching_by_description` | insert 2 Principles, search(query) | Nur Treffer mit Query in description |
| `test_search_domain_filter` | insert mit domain, search(domain=...) | Nur passende domain oder domain='' |

**Warum kritisch:** Diese Formel steuert, welche Prinzipien aufsteigen/sinken. Off-by-One korrumpiert das System über viele Projekte.

---

#### 1.2 `tests/lib/test_memory_utility.py` (utility.py)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_record_retrieval_insert` | Erster Aufruf (memory_type, memory_id) | Zeile mit retrieval_count=1, helpful_count=0, utility_score=0.5 |
| `test_record_retrieval_increment` | Zweiter Aufruf gleicher (type, id) | retrieval_count=2 (ON CONFLICT DO UPDATE) |
| `test_update_from_outcome_laplace_helpful` | record_retrieval; update_from_outcome(..., outcome_score=0.8) | helpful_count=1, utility_score = (1+1)/(2+2) = 0.5 |
| `test_update_from_outcome_laplace_not_helpful` | retrieval_count=2, helpful_count=0; outcome_score=0.3 | helpful_count=0, utility_score = (0+1)/(2+2) = 0.25 |
| `test_update_from_outcome_multiple_ids` | memory_ids=[id1, id2]; outcome_score=0.8 | Beide Zeilen: helpful_count += 1, Laplace korrekt |
| `test_update_from_outcome_missing_row_skipped` | memory_id nie record_retrieval; update_from_outcome(..., [that_id]) | Kein Crash, Zeile wird nicht angelegt |
| `test_concurrent_updates_single_id` | Optional: zwei update_from_outcome nacheinander | Finale Werte konsistent (helpful_count, utility_score) |

**Warum kritisch:** Utility bestimmt das Ranking in retrieve_with_utility. Falscher Score → falsche Prinzipien im Kontext.

---

#### 1.3 `tests/lib/test_memory_source_credibility.py` (source_credibility.py)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_update_insert_laplace` | update(conn, "domain1", times_used=1, verified_count=1, failed=0) auf leerer Tabelle | learned_credibility = (1+1)/(1+2) = 2/3 |
| `test_update_upsert_aggregates` | update(domain, 2, 1, 0); update(domain, 3, 2, 0) | Zweiter Aufruf: times_used=5, verified_count=3, learned_credibility = (3+1)/(5+2) = 4/7 |
| `test_update_conflict_laplace` | INSERT einmal; ON CONFLICT mit neuen Werten | learned_credibility = (verified + excluded.verified + 1) / (times_used + excluded.times_used + 2) |
| `test_get_returns_none_unknown_domain` | get(conn, "unknown") | None |
| `test_get_returns_row_after_update` | update(domain, 1, 1, 0); get(conn, domain) | dict mit learned_credibility, times_used, verified_count |

**Warum kritisch:** Upsert-Logik falsch → Credibility pro Domain lernt falsch; Verifikation wird systematisch über-/unterschätzt.

---

#### 1.4 `tests/lib/test_memory_outcomes.py` (outcomes.py)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_get_successful_outcomes_filters_min_critic` | record_outcome(..., critic_score=0.8); record_outcome(..., critic_score=0.5); get_successful_outcomes(min_critic=0.75) | Nur Eintrag mit 0.8 |
| `test_get_successful_outcomes_excludes_rejected` | record_outcome(..., user_verdict='rejected', critic_score=0.9) | Nicht in get_successful_outcomes(min_critic=0.5) |
| `test_get_successful_outcomes_includes_null_verdict` | record_outcome(..., user_verdict=None, critic_score=0.8) | In get_successful_outcomes(min_critic=0.75) |
| `test_get_successful_outcomes_limit` | 50 Outcomes; get_successful_outcomes(limit=10) | max. 10 Zeilen |
| `test_count_outcomes` | 3x record_outcome | count_outcomes(conn) == 3 |

**Warum kritisch:** Calibrator und Distiller bauen auf get_successful_outcomes. Falscher Filter → falsche Perzentile / falsche Prinzipien-Basis.

---

#### 1.5 `tests/lib/test_memory_schema.py` (schema.py)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_init_schema_creates_all_tables` | init_schema(conn) auf frischer DB | Alle erwarteten Tabellen vorhanden (episodes, decisions, reflections, playbooks, quality_scores, research_findings, memory_admission_events, cross_links, entities, entity_relations, entity_mentions, strategic_principles, memory_utility, project_outcomes, source_credibility) = 15 |
| `test_init_schema_idempotent` | init_schema(conn) zweimal | Kein Fehler, gleiche Struktur |
| `test_migrate_research_findings_quality_adds_columns` | init_schema mit alter research_findings (ohne relevance_score etc.); migrate_research_findings_quality aufgerufen | relevance_score, reliability_score, verification_status, evidence_count, critic_score, importance_score, admission_state vorhanden |
| `test_migrate_on_existing_db_no_crash` | DB mit bereits angelegten Tabellen; init_schema(conn) | Kein Crash, Migration läuft durch |

**Warum kritisch:** Schema-Fehler oder fehlende Migration → Crash bei erstem Zugriff oder stille Datenverluste.

---

### 2. `lib/memory/__init__.py` — retrieve_with_utility()

#### 2.1 `tests/lib/test_memory_facade.py` (Memory.retrieve_with_utility + source_credibility)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_retrieve_with_utility_two_phase_ranking` | Prinzipien einfügen, record_retrieval + update_from_outcome so dass utility_score unterschiedlich; retrieve_with_utility(query, "principle", k=5) | Sortierung nach combined_score = 0.4*relevance + 0.6*utility; Top-k |
| `test_retrieve_with_utility_empty_db` | Leere DB; retrieve_with_utility("anything", "principle", k=10) | [] |
| `test_retrieve_with_utility_unknown_memory_type` | retrieve_with_utility("q", "unknown_type", k=5) | [] |
| `test_retrieve_with_utility_candidate_without_id_skipped` | Kandidat ohne id-Feld (Mock/Search so injizieren) | Kein Crash, Kandidat übersprungen |
| `test_retrieve_with_utility_relevance_fallback` | Kandidat ohne relevance | relevance=0.5 verwendet, combined_score berechnet |
| `test_retrieve_with_utility_no_utility_row_default_0_5` | Kandidat nie record_retrieval | utility_score=0.5, combined_score konsistent |

**Warum kritisch:** Kern von MemRL. Falsches Ranking → Brain bekommt nutzlose Prinzipien, Lernen driftet ab.

---

## Priorität 2: Wichtig (Bug produziert schlechte Reports)

### 3. `tools/research_calibrator.py`

#### 3.1 `tests/tools/test_research_calibrator.py`

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_under_10_projects_returns_none` | < 10 successful outcomes in Memory | get_calibrated_thresholds() is None |
| `test_25th_percentile_10_entries` | 10 Outcomes mit gate_metrics_json (findings_count 1..10) | p25(findings_count) = erwarteter Wert (Definition: z.B. index int(10*0.25) oder int(10*0.25)-1) |
| `test_25th_percentile_11_entries` | 11 Einträge | p25 konsistent |
| `test_25th_percentile_100_entries` | 100 Einträge | p25 = 25. Perzentil der sortierten Liste |
| `test_floor_values_never_undershot` | p25 ergibt Werte unter FLOOR | Ergebnis >= FLOOR pro Key (findings_count_min, unique_source_count_min, …) |
| `test_missing_gate_metrics_keys_filled_with_floor` | Outcomes mit lückenhaftem gate_metrics_json | Alle FLOOR-Keys im Rückgabedict, fehlende aus FLOOR |
| `test_memory_failure_returns_none` | Memory() wirft (z.B. DB fehlt) | get_calibrated_thresholds() returns None |

---

### 4. `tools/research_quality_gate.py` — Calibrator-Integration

#### 4.1 Erweiterung `tests/tools/test_research_quality_gate.py`

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_get_thresholds_uses_calibrated_when_available` | Mock get_calibrated_thresholds() → dict mit z.B. findings_count_min=12 | _get_thresholds() enthält 12 (kalibriert überdeckt Default) |
| `test_get_thresholds_uses_default_when_calibrator_none` | Mock get_calibrated_thresholds() → None | _get_thresholds() == EVIDENCE_GATE_THRESHOLDS |
| `test_calibrated_values_below_floor_use_floor` | Calibrator liefert findings_count_min=2; FLOOR=5 | _get_thresholds()["findings_count_min"] >= 5 (wenn Quality-Gate Floor anwendet; ggf. in Calibrator getestet) |

*Hinweis:* Floor wird im Calibrator angewendet (max(FLOOR, p25)); Quality-Gate ruft nur Calibrator auf. Test „kalibriert unter Floor“ kann in test_research_calibrator abgedeckt werden.

---

### 5. `lib/brain_context.py` — Query-basierter Pfad

#### 5.1 `tests/lib/test_brain_context.py`

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_compile_without_query_static_path_no_strategic_principles` | memory ohne retrieve_with_utility oder query=None | Rückgabe hat KEIN Key "strategic_principles" |
| `test_compile_with_query_uses_utility_path` | memory mit retrieve_with_utility; compile(memory, query="AI hardware") | Key "strategic_principles" vorhanden, Liste (evtl. leer) |
| `test_compile_with_query_findings_by_project` | query gesetzt, retrieve_with_utility liefert findings | accepted_findings_by_project gruppiert nach project_id, max_findings_per_project eingehalten |
| `test_compile_memory_without_retrieve_with_utility_fallback` | Fake memory nur mit get_research_findings_accepted, recent_reflections (kein retrieve_with_utility) | Kein Crash, statischer Pfad, kein strategic_principles |
| `test_compile_totals_populated` | query gesetzt, nicht leere Ergebnisse | totals.accepted_projects, totals.principles_count etc. gesetzt |

**Warum kritisch:** Falscher Pfad (query vs. statisch) oder fehlender Fallback → Planner bekommt falschen oder leeren Kontext.

---

## Priorität 3: Gut zu haben

### 6. `tools/research_experience_distiller.py` (nach Dedup-Fix)

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_guiding_vs_cautionary_from_critic_score` | principles_data mit critic_score; Einordnung guiding vs. cautionary | guiding bei hohem, cautionary bei niedrigem critic_score (Definition aus Code) |
| `test_json_parse_error_graceful` | LLM/Input liefert ungültiges JSON | Kein Crash, graceful exit oder leere Liste |
| `test_empty_principles_data_no_insert` | principles_data = [] | Kein Insert in Memory |

*Hinweis:* LLM-Aufrufe mocken; nur Logik (Guiding/Cautionary, JSON-Parse, leere Daten) testen.

---

### 7. `tools/research_knowledge_seed.py`

| Test | Beschreibung | Assertions |
|------|--------------|------------|
| `test_project_without_findings_in_db_writes_empty_prior_knowledge` | Projekt ohne Findings in Memory; prior_knowledge.json geschrieben | prior_knowledge.json mit principles=[], findings=[], principle_ids=[], finding_ids=[] |
| `test_no_crash_when_memory_unavailable` | Memory() wirft | exit 0 (non-fatal), stderr oder leere Ausgabe |

---

## Übersicht: 5 Testdateien mit höchstem Nutzen

| Datei | Inhalt (Kurz) |
|-------|----------------|
| `tests/lib/test_memory_principles.py` | Laplace update_usage_success, insert, search, domain filter |
| `tests/lib/test_memory_utility.py` | record_retrieval, update_from_outcome, Laplace, Concurrency optional |
| `tests/lib/test_memory_facade.py` | retrieve_with_utility Two-Phase, leere DB, unbekannter type, Kandidat ohne id |
| `tests/tools/test_research_calibrator.py` | < 10 → None, p25 bei 10/11/100, Floor, fehlende Keys |
| `tests/lib/test_brain_context.py` | query vs. no-query, strategic_principles vorhanden/fehlend, Fallback ohne retrieve_with_utility |

Zusätzlich empfohlen (Priorität 1 vollständig):

- `tests/lib/test_memory_source_credibility.py` — update Laplace + Upsert
- `tests/lib/test_memory_outcomes.py` — get_successful_outcomes Filter
- `tests/lib/test_memory_schema.py` — init_schema 15 Tabellen, Migration idempotent

---

## Implementierungshinweise

- **DB:** `sqlite3.connect(":memory:")` oder `tempfile.NamedTemporaryFile(suffix=".db")`, `conn.row_factory = sqlite3.Row`.
- **Memory-Klasse:** `Memory(db_path=path)` für echte Datei oder In-Memory; für __init__ Schema prüfen mit eigenem conn.
- **Calibrator/Brain:** `unittest.mock.patch` oder `pytest` fixtures für Memory / get_calibrated_thresholds.
- **Kein LLM:** Alle Tests ohne echte API-Calls; Distiller/Knowledge-Seed nur soweit ohne LLM testbar (JSON, leere Daten, Crash-Sicherheit).

Nach Umsetzung: `pytest tests/lib/ tests/tools/test_research_calibrator.py tests/tools/test_research_quality_gate.py -v` aus Repo-Root (mit gesetztem PYTHONPATH oder `python -m pytest`).
