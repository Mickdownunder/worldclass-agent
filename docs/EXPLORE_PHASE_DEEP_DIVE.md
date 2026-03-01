# Explore-Phase: Deep Dive (Experten-Dokument)

Dieses Dokument beschreibt **genau**, wie die Explore-Phase funktioniert, **alle** beteiligten Dateien (was sie tun, was sie dem System bringen), ihre **Zusammenhänge** und den Datenfluss, was falsch oder verbesserungswürdig ist und wo SOTA/novel Ansätze möglich sind. Quelle der Wahrheit: Code in `operator/workflows/research-cycle.sh` und `operator/tools/`.

**Was dieses Dokument bringt:**

- **Ablauf:** Schrittfolge Explore mit Tool- und Artefakt-Namen.
- **Alle Dateien:** Jede beteiligte Datei (Skript, Artefakt, Config) mit Rolle, Ein-/Ausgabe und **Nutzen für das System**.
- **Zusammenhänge:** Wer liest was von wem; Datenfluss und Abhängigkeiten.
- **Gemeinsame Infrastruktur:** research_common, Progress, Budget, Memory — was alle Tools nutzen.
- **Probleme & SOTA:** Bekannte Bugs, Lücken, Verbesserungsideen.
- **Conductor & Tool-Use:** Bewertung der Umsetzung.

**Inhaltsübersicht:** 1 Ablauf · 2 Alle Dateien (Rolle, I/O, Nutzen) · 3 Zusammenhänge & Datenfluss · 4 Gemeinsame Infrastruktur · 5 Tools im Detail · 6 Was falsch ist · 7 Was wir nutzen · 8 SOTA/Novel · 9 Referenzen · 10 Conductor & Tool-Use.

---

## 1. Ablauf: Was passiert in Explore (Schritt für Schritt)

Die Explore-Phase wird in `research-cycle.sh` im `case "explore")` ausgeführt. Reihenfolge:

| Schritt | Aktion | Tool/Skript | Artefakte |
|--------|--------|-------------|-----------|
| 0 | Conductor-Shadow (optional) | `research_conductor.py shadow` | `conductor_decisions.json`, `conductor_shadow.log` |
| 1 | Token Governor (wenn Flag) | `research_token_governor.recommend_lane` | `governor_lane.json`, `RESEARCH_GOVERNOR_LANE` |
| 2 | Knowledge Seed (wenn Flag) | `research_knowledge_seed.py` | `prior_knowledge.json` |
| 3 | Question Graph (wenn Flag) | `research_question_graph.py build` | `questions/questions.json` |
| 4 | Research Plan | `research_planner.py $QUESTION $PROJECT_ID` | `artifacts/research_plan.json` → `research_plan.json` |
| 5 | Web Search Round 1 | `research_web_search.py --queries-file research_plan.json --max-per-query 5` | `web_search_round1.json` |
| 6 | Academic (wenn Flag) | `research_academic.py semantic_scholar` | `academic_round1.json` → in `sources/*.json` gemerged |
| 7 | Filter & Save | Inline Python: Plan + Search → Topic-Overlap, Topic-IDs | Neue `sources/*.json` |
| 8 | Smart Rank | Inline Python: Domain-Rank, Blocklist, pro-Domain-Cap (3), Priorität | `read_order_round1.txt` (Pfade zu Source-JSONs) |
| 9 | Memory Filter | `lib.memory.Memory.get_read_urls_for_question(question)` | `read_order_round1.txt` (bereinigt: schon gelesene URLs entfernt) |
| 10 | Parallel Read Round 1 | `research_parallel_reader.py $PROJECT_ID explore --input-file read_order_round1.txt --read-limit $READ_LIMIT --workers 8` | `sources/*_content.json`, `findings/*.json`, stdout JSON Stats |
| 11 | Saturation Check | `research_saturation_check.py $PROJ_DIR` | Exit 0/1; bei 1 werden Rounds 2–3 übersprungen |
| 12 | Coverage Round 1 | `research_coverage.py $PROJECT_ID` | `coverage_round1.json` |
| 13a | Wenn Coverage nicht pass: Refinement | Planner `--refinement-queries`, Web Search, Save, Parallel Read (explore, limit 10) | `refinement_queries.json`, `refinement_urls_to_read.txt` |
| 13b | Gap Fill Round 2 | Planner `--gap-fill`, Web Search, Save, Parallel Read (explore, limit 10) | `gap_queries.json`, `gap_urls_to_read.txt`, `coverage_round2.json` |
| 13c | Wenn thin_priority_topics: Depth Round 3 | Planner `--perspective-rotate`, Web Search, Save, Parallel Read (explore, limit 8) | `depth_queries.json`, `depth_urls_to_read.txt`, `coverage_round3.json` |
| 14 | Deep Extract | `research_deep_extract.py $PROJECT_ID` | Zusätzliche Findings mit `source=deep_extract` |
| 15 | Read Stats persist | Inline Python | `explore/read_stats.json` (read_attempts, read_successes, read_failures) |
| 16 | Relevance Gate Batch (wenn Flag) | `research_relevance_gate.py batch $PROJECT_ID` | `explore/relevance_gate_results.json` |
| 17 | Context Manager (wenn Flag) | `research_context_manager.py add` | Conductor-Context-Kompression |
| 18 | Dynamic Outline (wenn Flag) | `research_dynamic_outline.py` | Outline + Evidenz |
| 19 | advance_phase "focus" | `research_advance_phase.py` + Conductor Gate | `project.json` phase=focus (oder Override zurück auf explore) |

**READ_LIMIT** wird aus Plan-Complexity abgeleitet: `complex`→40, `moderate`→25, sonst 15.

**Coverage-Pass** (`research_coverage.py`): `pass = (coverage_rate >= 0.7) or (coverage_rate >= 0.5 and priority1_uncovered == 0)`. Bei Pass nach Round 1 werden Rounds 2 und 3 übersprungen.

---

## 2. Alle Dateien: Rolle, Ein-/Ausgabe, was sie dem System bringen

Jede Datei, die in der Explore-Phase eine Rolle spielt — ob Skript, Artefakt oder Konfiguration — wird hier mit **Input**, **Output** und **Nutzen für das System** beschrieben.

### 2.1 Orchestrierung & Infrastruktur

| Datei | Liest | Schreibt | Was es dem System bringt |
|-------|-------|----------|---------------------------|
| **research-cycle.sh** | `project.json` (phase, question), `job.json` (request), Env/Policy/Secrets | Log in `$CYCLE_LOG`, Artifacts in `$ART`, Aufrufe aller Tools, `project.json` via advance_phase | **Zentrale Steuerung:** Ein Einstieg pro Cycle; entscheidet anhand `phase` den Branch (explore/focus/…), ruft Tools in fester Reihenfolge auf, setzt Progress-Steps, führt Conductor-Gate vor advance_phase aus. Ohne diese Datei gibt es keine Phasen-Pipeline. |
| **research_advance_phase.py** | `project.json` | `project.json` (phase, phase_history, phase_timings, ggf. status/done) | **Einheitlicher Phasenwechsel:** Eine Stelle, die Phase und Verlauf schreibt; verhindert Überschreiben bei Terminal-Status; berechnet phase_timings; loop_count > 3 erzwingt nächste Phase (Endlosschleifen-Schutz). |
| **research_progress.py** | — | `progress.json`, `events.jsonl` | **Laufzeit-Feedback für UI:** phase, step, heartbeat; UI kann RUNNING/IDLE/STUCK erkennen; Events für Audit/Timeline. Ohne Progress wirkt die Pipeline „hängend“. |
| **research_common.py** | Env (OPERATOR_ROOT), `conf/secrets.env`, `project.json` | — | **Gemeinsame Basis:** project_dir(), load_project(), llm_call(), load_secrets(); alle Research-Tools bauen darauf. Ein Ort für Pfade und LLM-Aufrufe. |
| **research_budget.py** | `project.json` (config), ggf. Spend-Tracking | check: stdout JSON (ok, current_spend, budget_limit) | **Kostenbremse:** Vor jedem Cycle wird Budget geprüft; bei Überschreitung wird Projekt auf FAILED_BUDGET_EXCEEDED gesetzt und Cycle abgebrochen. Schützt vor Runaway-Spend. |

### 2.2 Vor dem Lesen (Planung, Suche, Ranking)

| Datei | Liest | Schreibt | Was es dem System bringt |
|-------|-------|----------|---------------------------|
| **research_knowledge_seed.py** | `project.json` (question), Memory (retrieve_with_utility) | `prior_knowledge.json` (principles, findings, ids) | **Prior-Wissen:** Bringt relevante Principles und Findings aus vergangenen Projekten in den Kontext; Planner und spätere Schritte können darauf aufbauen. Erhöht Konsistenz und Vermeidung von Wiederholungen. |
| **research_question_graph.py** | `project.json` (question), ggf. verify/claim_ledger | `questions/questions.json` (question_id, text, state, uncertainty, linked_claims) | **Strukturierte Fragen:** Macht die Forschungsfrage und Teilfragen/Uncertainty für Planner und AEM nutzbar; Grundlage für decision_relevance und spätere Analyse. |
| **research_planner.py** | question, project_id; optional `prior_knowledge.json`, `questions/questions.json`, `memory_strategy.json`; bei Moden: coverage_round*.json, thin_topics | stdout → `research_plan.json` (queries, topics, entities, complexity); Memory v2: `memory_strategy.json` | **Strategie & Queries:** Erzeugt den Suchplan (was und wie gesucht wird), Topics mit Priorität, Complexity für READ_LIMIT. Refinement/Gap/Depth-Moden füllen Lücken aus Coverage. Ohne Planner keine zielgerichtete Suche. |
| **research_web_search.py** | `--queries-file` (research_plan.json o. Ä.), Env (API-Keys) | stdout: JSON-Array von Treffern (url, title, description, …) | **Web-Treffer:** Liefert die URL-Kandidaten für alle Runden (Round 1, Refinement, Gap, Depth). Ohne Search keine Quellen. |
| **research_academic.py** | Frage/Query, Env (API-Keys) | stdout: JSON-Array (title, url, abstract, source=semantic_scholar/arxiv/…) | **Akademische Quellen:** Ergänzt Web-Ergebnisse um Papers/Abstracts; erhöht Qualität und Diversität der Quellen. |
| **research_web_reader.py** | URL (CLI), Env (JINA etc.) | stdout: JSON (url, title, text, error, error_code) | **Seiteninhalt:** Holt den eigentlichen Text einer URL; wird von parallel_reader pro URL aufgerufen. Ohne Reader nur Metadaten, keine Findings. |
| **FILTER_AND_SAVE (inline)** | research_plan.json, web_search_round1.json | Neue `sources/<id>.json` (nur Treffer mit Topic-Overlap/Entity) | **Qualitätsfilter:** Reduziert Rauschen; nur Treffer, die zum Plan passen, landen in sources. |
| **SMART_RANK (inline)** | research_plan.json, sources/*.json, Env (DOMAIN_RANK, OVERRIDES) | `read_order_round1.txt` (Pfade sortiert nach Score) | **Lese-Reihenfolge:** Priorisiert nach Domain, Topic-Priorität, Entity; begrenzt pro Domain (z. B. 3); Blocklist. Bringt die „besten“ Kandidaten zuerst. |
| **FILTER_READ_URLS (inline)** | read_order_round1.txt, Memory.get_read_urls_for_question | read_order_round1.txt (bereinigt) | **Kein doppeltes Lesen:** Entfernt URLs, die für dieselbe Frage schon gelesen wurden (Memory v2). Spart Zeit und API. |

### 2.3 Lesen, Coverage, Saturation, Extraktion

| Datei | Liest | Schreibt | Was es dem System bringt |
|-------|-------|----------|---------------------------|
| **research_parallel_reader.py** | `--input-file` (URLs/Pfade), project.json (question), findings (für Novelty), optional relevance_gate | `sources/<id>_content.json`, `findings/<id>.json`; stdout: read_attempts/successes/failures | **Paralleles Lesen + Findings:** Führt viele URLs effizient aus; speichert Inhalt und erzeugt Findings mit novelty_score, relevance_score; optional pro-URL-Relevanzfilter. Kern der Evidenz-Sammlung. |
| **research_saturation_check.py** | findings/*.json (mtime, novelty_score) | Exit-Code 0/1 | **Stopp bei Redundanz:** Verhindert sinnlose weitere Reads, wenn die letzten Findings kaum neu sind. Spart Kosten und Zeit. |
| **research_coverage.py** | research_plan.json, findings/, sources/ (ohne _content) | stdout → coverage_round*.json (coverage_rate, topics, uncovered, thin_priority_topics, pass) | **Thematische Abdeckung:** Entscheidet, ob noch Runden 2/3 nötig sind und welche Topics „dünn“ sind. Treibt Refinement/Gap/Depth an. |
| **research_deep_extract.py** | sources/*_content.json (≥3000 Zeichen), findings (relevance) | findings/*.json (source=deep_extract) | **Tiefere Fakten:** Extrahiert 2–5 konkrete Fakten pro langer Quelle; verbessert Report-Tiefe ohne jede Zeile im Report zu zitieren. |
| **explore/read_stats.json** (inline geschrieben) | Shell-Variablen (read_attempts, read_successes, read_failures) | `explore/read_stats.json` | **Metriken für Evidence Gate:** quality_gate und adaptive Schwellen nutzen Read-Statistik; aktuell nur Round 1 (Bug). |

### 2.4 Nach dem Lesen (Gate, Kontext, Conductor)

| Datei | Liest | Schreibt | Was es dem System bringt |
|-------|-------|----------|---------------------------|
| **research_relevance_gate.py** | question, findings (title, excerpt); batch: alle Findings | Einzel: stdout JSON (relevant, score, reason); batch: `explore/relevance_gate_results.json` | **Relevanz-Bewertung:** Markiert irrelevante Findings; Batch ändert keine Findings, nur Bewertung für Analyse/Debug. Reduziert Rauschen in späteren Phasen, wenn genutzt. |
| **research_quality_gate.py** | findings/, sources/, verify/, **explore/read_stats.json** | stdout: pass, metrics, reasons | **Evidence Gate:** Entscheidet, ob genug Evidenz für Verify/Synthesize da ist; nutzt read_stats für adaptive findings_count_min. Schützt vor Report mit zu wenig Beleg. |
| **research_context_manager.py** | findings/ | `conductor_context.json` (compressed batches) | **Kontext für Conductor:** Komprimiert Findings auf ~500 Tokens; Conductor entscheidet ohne alle Findings zu laden. Ermöglicht bounded state. |
| **research_dynamic_outline.py** | research_plan.json, conductor_context.json | merge_evidence_into_outline: updated_outline, gaps, suggested_queries | **Lücken nach Evidenz:** Aktualisiert Plan mit neuem Stand; identifiziert Gaps; optional für nächste Conductor-Runde. |
| **research_conductor.py** | project.json, findings_count, sources, coverage_*.json, budget, conductor_state, conductor_overrides, conductor_decisions; optional context_manager | conductor_decisions.json, conductor_overrides.json, conductor_state.json; gate: stdout (next_phase) | **Entscheidung „weiter oder nochmal“:** LLM wählt Aktion (search_more, read_more, verify, synthesize); Gate vergleicht mit erwarteter Aktion und kann Phase wiederholen. Verhindert zu frühes Abbrechen oder zu langes Schleifen (Caps). |
| **research_token_governor.py** | project_id (episode_metrics, triage, portfolio) | recommend_lane → stdout (cheap/mid/strong) | **Modell-Routing:** Empfiehlt Lane für Token-Kosten vs. Qualität; Tools können RESEARCH_GOVERNOR_LANE lesen. Optional für Explore. |

### 2.5 Projekt-Artefakte (persistent)

| Pfad | Geschrieben von | Gelesen von | Was es dem System bringt |
|------|-----------------|-------------|---------------------------|
| **project.json** | init, advance_phase, Gate-Fail-Blocke, quality_gate Updates | Fast alle Tools (phase, question, config, quality_gate) | **Projekt-Status:** Einheitliche Quelle für Phase, Frage, Status, Config; Phase treibt research-cycle.sh Branch. |
| **research_plan.json** | research_planner (Copy aus artifacts) | coverage, planner (Moden), web_search, dynamic_outline, focus | **Such- und Themenplan:** Treibt alle Such- und Coverage-Entscheidungen. |
| **sources/<id>.json** | Filter_And_Save, Academic-Merge, Refinement/Gap/Depth-Save | coverage, parallel_reader (Pfad→URL), SMART_RANK | **Quellen-Metadaten:** URL, title, topic_id, confidence; ohne _content nur Kandidat. |
| **sources/<id>_content.json** | research_parallel_reader (research_web_reader) | deep_extract, coverage nicht | **Volltext:** Ermöglicht Extraktion und Findings. |
| **findings/*.json** | parallel_reader, deep_extract | coverage, relevance_gate batch, context_manager, dynamic_outline, conductor (indirekt über count), synthesize, verify | **Evidenz-Basis:** Kern aller nachgelagerten Phasen (Focus, Connect, Verify, Synthesize). |
| **explore/read_stats.json** | research-cycle.sh (inline) | research_quality_gate._load_explore_stats | **Read-Metriken:** Für Evidence Gate und adaptive Schwellen (aktuell nur Round 1). |
| **explore/relevance_gate_results.json** | research_relevance_gate batch | Optional Analyse/UI | **Relevanz-Audit:** Welche Findings als relevant bewertet. |
| **coverage_round1/2/3.json** | research_coverage | research-cycle.sh (COVERAGE_PASS, THIN_TOPICS), conductor read_state | **Abdeckungsstand:** Steuert Runden 2/3 und Conductor-Entscheidung. |
| **prior_knowledge.json** | research_knowledge_seed | research_planner | **Prior-Kontext:** Bessere Pläne durch Vergangenheitswissen. |
| **questions/questions.json** | research_question_graph | research_planner | **Fragen-Struktur:** Für Planner und AEM. |
| **memory_strategy.json** | research_planner (Memory v2) | research-cycle.sh (Env-Schwellen), UI „Memory Applied“ | **Strategie pro Run:** Welche Schwellen und Policy aktiv sind. |
| **governor_lane.json** | research-cycle.sh (Token Governor) | Tools, die RESEARCH_GOVERNOR_LANE lesen | **Lane-Empfehlung:** Kosten/Qualität-Routing. |
| **conductor_decisions.json** | research_conductor shadow/gate | Conductor read_state (steps_taken, deltas) | **Entscheidungslog:** Nachvollziehbarkeit und Deltas. |
| **conductor_overrides.json** | research_conductor gate | Conductor gate_check (Caps) | **Override-Zähler:** Begrenzt Wiederholungen. |
| **conductor_state.json** | research_conductor | read_state (steps_taken) | **Aktueller Conductor-Stand.** |
| **progress.json** | research_progress | API/UI (Fortschritt, STUCK-Erkennung) | **Laufzeit-Anzeige.** |
| **events.jsonl** | research_progress | API/UI (Timeline) | **Ereignis-Verlauf.** |

### 2.6 Temporäre Artifacts (Job, $ART)

| Datei | Erzeugt von | Verbraucht von | Nutzen |
|-------|-------------|----------------|--------|
| research_plan.json (in ART) | research_planner | Copy nach PROJ_DIR, web_search, QUERY_COUNT, COMPLEXITY | Erstes Schreibziel; dann Projekt-Kopie. |
| web_search_round1.json, refinement_search.json, gap_search_round2.json, depth_search_round3.json | research_web_search | FILTER_AND_SAVE / SAVE_REFINEMENT / SAVE_GAP / SAVE_DEPTH | Rohe Suchergebnisse pro Runde. |
| academic_round1.json | research_academic | MERGE_ACADEMIC | Akademische Treffer → sources. |
| read_order_round1.txt, refinement_urls_to_read.txt, gap_urls_to_read.txt, depth_urls_to_read.txt | SMART_RANK / Inline-URL-Extraktion | research_parallel_reader | Eingabeliste für Reads. |
| coverage_round1/2/3.json (in ART) | research_coverage | research-cycle.sh (Bedingungen), Copy nach PROJ_DIR | Entscheidung Runden 2/3, dann persistent. |

### 2.7 Memory (lib.memory) — außerhalb Projektordner

| Funktion / Tabelle | Schreiben | Lesen | Was es dem System bringt |
|--------------------|-----------|-------|---------------------------|
| **get_read_urls_for_question(question)** | — | FILTER_READ_URLS (research-cycle.sh) | **URL-Dedup:** Verhindert doppeltes Lesen derselben URL für dieselbe Frage (Hash-basiert). |
| **record_read_urls(question, urls)** | persist_v2_episode (am Run-Ende) | — | **Persistenz der gelesenen URLs** für zukünftige Runs. |
| **read_urls (DB)** | record_read_urls | get_read_urls_for_question | Speicherung question_hash → URLs. |

---

## 3. Zusammenhänge und Datenfluss

### 3.1 Abhängigkeitskette (Wer liefert für wen)

```
project.json (phase, question)
    → research-cycle.sh (Branch explore)
    → research_knowledge_seed → prior_knowledge.json
    → research_question_graph → questions/questions.json
    → research_planner (liest prior_knowledge, questions, memory_strategy)
        → research_plan.json
    → research_web_search (liest research_plan) → web_search_round1.json
    → FILTER_AND_SAVE → sources/*.json
    → SMART_RANK → read_order_round1.txt
    → Memory.get_read_urls_for_question → read_order_round1.txt (bereinigt)
    → research_parallel_reader (liest read_order, question) → sources/*_content.json, findings/*
    → research_saturation_check (liest findings) → Exit 0/1
    → research_coverage (liest plan, findings, sources) → coverage_round1.json
    → [wenn nicht pass] research_planner --refinement / --gap-fill / --perspective-rotate
        → weitere Searches + parallel_reader → coverage_round2/3
    → research_deep_extract (liest sources/*_content, findings) → weitere findings
    → explore/read_stats.json (inline)
    → research_relevance_gate batch (liest findings) → explore/relevance_gate_results.json
    → research_context_manager (liest findings) → conductor_context.json
    → research_dynamic_outline (liest plan, conductor_context) → gaps/suggested_queries
    → advance_phase "focus" → research_conductor gate (liest state, coverage, budget) → next_phase
    → research_advance_phase → project.json (phase, phase_history)
```

### 3.2 Querbezüge (gleiche Daten, mehrere Consumer)

- **research_plan.json:** Planner (Refinement/Gap/Depth), coverage (Topic-IDs/Keywords), web_search, dynamic_outline, focus (gap-fill). **Zentrale Referenz** für „was wird gesucht und abgedeckt“.
- **findings/:** coverage (Match zu Topics), relevance_gate (Bewertung), context_manager (Komprimierung), dynamic_outline (Evidenz), quality_gate (Anzahl), conductor (findings_count). **Gemeinsame Evidenz-Basis**.
- **coverage_round*.json:** Bash (COVERAGE_PASS, THIN_TOPICS), conductor read_state (coverage_score). **Gemeinsame Metrik** für „reicht die Abdeckung“.
- **project.json:** phase (Steuerung), question (alle LLM-Tools), config (research_mode, budget), quality_gate (Ergebnis Verify). **Single Source of Truth** für Projekt-Status.

### 3.3 Kritische Pfade

- **Ohne research_plan.json** gibt es keine zielgerichteten Queries und kein Topic-Matching für Coverage; Fallback: leeres Plan-Objekt.
- **Ohne findings** bleiben coverage, quality_gate, context_manager, synthesize ohne Input; Pipeline kann nicht sinnvoll zu Verify/Synthesize gehen.
- **Ohne research_advance_phase** bleibt phase unverändert; der nächste Cycle läuft dieselbe Phase erneut (gewollt bei Conductor-Override, sonst Bug).
- **Ohne progress.json** kann die UI nicht zwischen RUNNING und STUCK unterscheiden.

---

## 4. Gemeinsame Infrastruktur (von vielen Tools genutzt)

| Komponente | Bereitgestellt durch | Nutzer (Beispiele) | Nutzen |
|------------|----------------------|--------------------|--------|
| **Projektpfad / Projekt laden** | research_common.project_dir, load_project | fast alle research_*.py | Einheitliche Pfade und project.json-Zugriff. |
| **LLM-Aufrufe** | research_common.llm_call | planner, relevance_gate, deep_extract, context_manager, conductor, dynamic_outline | Ein Modell, Retry-Logik, Token-Tracking (Budget). |
| **Secrets / API-Keys** | research_common.load_secrets, Env | web_search, academic, web_reader (Jina etc.) | Keine Hardcodes; gleiche Konfiguration. |
| **Progress / Events** | research_progress.start, step, done; events.jsonl | research-cycle.sh (progress_start, progress_step), parallel_reader (step_start/step_finish) | UI-Fortschritt und Stuck-Erkennung. |
| **Budget** | research_budget.check, get_budget_limit | research-cycle.sh (Circuit Breaker), conductor read_state (budget_spent_pct) | Kostenkontrolle vor und während Cycle. |
| **Memory v2** | lib.memory (Memory, read_urls, strategy, run_episodes) | knowledge_seed, FILTER_READ_URLS, record_read_urls, planner (strategy), persist_v2_episode | Prior-Wissen, URL-Dedup, Strategie-Auswahl, Episoden-Log. |

---

## 5. Tools im Detail (Explore-relevant, Kurzreferenz)

(Vollständige Rollen und Ein-/Ausgaben siehe Abschnitt 2.)

### research_planner.py

- **Default-Mode:** Liest optional `prior_knowledge.json` und `questions/questions.json` über `_load_prior_knowledge_and_questions(project_id)` und fügt sie als Kontext in den User-Prompt ein. Erzeugt `queries`, `topics`, `entities`, `complexity`.
- **--refinement-queries:** `build_refinement_plan(coverage_path, project_id)` — nutzt coverage_round1 + Findings-Summary, LLM erzeugt 5–10 Präzisions-Queries für Lücken.
- **--gap-fill:** `build_gap_fill_queries(coverage_path, project_id)` — aus uncovered_topics + perspectives/entities.
- **--perspective-rotate:** `build_perspective_queries(thin_topics_path, project_id)` — für thin_priority_topics (Priorität 1, <3 Quellen).

### research_parallel_reader.py

- **Mode:** `explore | focus | counter | recovery`. Explore: read_limit bis 40, source_label `"read"`, confidence-Formel mit rel_score.
- **Eingabe:** `--input-file` mit einer URL oder einem Pfad zu einer Source-JSON pro Zeile. Bei Pfad: URL aus JSON geladen.
- **Pro URL:** Subprocess `research_web_reader.py <url>`, dann `_save_result`: optional Relevance Gate (wenn `RESEARCH_ENABLE_RELEVANCE_GATE=1`), Relevance-Threshold aus `RESEARCH_MEMORY_RELEVANCE_THRESHOLD` (default 0.50), Novelty (Jaccard vs. letzte 50 Findings). Bei nicht relevant oder zu niedrigem Score wird nicht gespeichert; bei novelty < 0.15 nur Stderr-Log.
- **Ausgabe:** JSON-Last-Zeile stdout: `{"read_attempts", "read_successes", "read_failures"}`. Findings mit `read_phase: mode`, `novelty_score`, `relevance_score`.

### research_coverage.py

- Liest `research_plan.json`, `findings/`, `sources/` (ohne _content). Match pro Topic über topic_id oder Keyword-Overlap. Pro Topic: min_sources (default 2), is_covered = (sources_count >= min_sources). `pass` = coverage_rate >= 0.7 oder (coverage_rate >= 0.5 und keine ungedeckten Priorität-1-Topics). `thin_priority_topics` = Priorität 1 mit < 3 Quellen (für Round 3).

### research_saturation_check.py

- Liest die letzten 10 Findings (nach mtime). Wenn ≥ 7 mit `novelty_score < 0.2`: Exit 1 (Saturation), sonst Exit 0. research-cycle.sh setzt dann `SATURATION_DETECTED=1` und überspringt Refinement/Gap/Depth-Reads.

### research_deep_extract.py

- Quelle: nur `*_content.json` mit Textlänge ≥ 3000 Zeichen. Pro Quelle: LLM extrahiert 2–5 Fakten; neue Findings mit `source=deep_extract`, confidence 0.55. Bei Fehler: Exit 0 (Pipeline bricht nicht ab). 6 Worker.

### research_relevance_gate.py

- **Einzelcheck:** `check_relevance(question, title, text)` → LLM Score 0–10, relevant = (score >= 7). Fail-open bei LLM-Fehler.
- **Batch:** `run_batch(project_id)` — alle Findings, schreibt `explore/relevance_gate_results.json`. Ändert keine Findings; nur Bewertung.

### research_quality_gate.py

- `_load_explore_stats(proj)` liest `explore/read_stats.json` (read_attempts, read_successes, read_failures). Wird in der Evidence-Gate-Metrik und für adaptive findings_count_min genutzt (niedrigere Mindestanzahl bei schlechter Read-Erfolgsrate).

### research_conductor.py

- **Gate:** Am Ende von Explore ruft research-cycle.sh `advance_phase "focus"` auf; vor dem Schreiben wird `research_conductor.py gate $PROJECT_ID focus` aufgerufen. Conductor vergleicht gewünschte Aktion („focus“ → erwartete Aktion „read_more“) mit LLM-Entscheidung (search_more, read_more, verify, synthesize). Wenn LLM z.B. „search_more“ will → Override: nächste Phase = „explore“ (bleibt in Explore). Max 1 Override für „explore->focus“, sonst max 2; bei budget_spent_pct >= 0.8 oder coverage_score >= 0.8 und findings_count >= 30 wird immer durchgelassen.
- **State:** findings_count, source_count, coverage_score, verified_claims, budget_spent_pct, steps_taken, findings_delta, sources_delta. Keine rohen Findings im State.

### Memory (lib.memory)

- **get_read_urls_for_question(question):** Hash der Frage (lower, strip) → Set von URLs, die für diese Frage schon gelesen wurden. Wird in research-cycle.sh im Block FILTER_READ_URLS verwendet: Zeilen in read_order_round1.txt, deren Source-URL in skip_urls ist, werden entfernt.
- **record_read_urls(question, urls):** Wird am Ende eines Runs (terminal) mit allen gelesenen Source-URLs aufgerufen (in research-cycle.sh im Block MEMORY_V2_EPISODE). Dedup pro question_hash; Paraphrase der Frage = anderer Hash → keine cross-question Dedup.

---

## 6. Was falsch oder problematisch ist

### 6.1 Logik / Bugs

1. **read_stats nur aus Round 1:** `read_attempts`, `read_successes` werden in research-cycle.sh aus dem **ersten** Aufruf von `research_parallel_reader.py` (read_order_round1.txt) ausgelesen. Die folgenden Aufrufe (refinement, gap, depth) liefern ebenfalls JSON, werden aber mit `| tail -1 > /dev/null` verworfen. Damit enthält `explore/read_stats.json` **nur** die Round-1-Statistik, nicht die kumulierten Reads aller Runden. **Folge:** Evidence Gate und adaptive findings_count_min basieren auf unterzählten Reads.

2. **Saturation-Exit und Refinement-Bedingung:** Wenn `COVERAGE_PASS != True` ist, wird zuerst Refinement (Round 2 Precision) und dann Gap Fill ausgeführt. Die Bedingung für Refinement-Read ist `[ "$REFINEMENT_COUNT" -gt 0 ] && [ "$SATURATION_DETECTED" != "1" ]`. Gap/Depth-Reads werden ebenfalls nur bei `SATURATION_DETECTED != 1` ausgeführt. Korrekt; aber Saturation wird **nach** Round-1-Read und **vor** Coverage berechnet. Wenn Round 1 schon stark redundant war, werden Rounds 2–3 zu Recht übersprungen.

3. **Memory read_urls Filter:** `get_read_urls_for_question` nutzt exakten question_hash. Leichte Formulierungsänderungen der gleichen Frage führen zu anderem Hash → keine Dedup. Dokumentiert in MEMORY_BRAIN_DEEP_DIVE.md.

4. **Relevance Gate in parallel_reader:** Wenn `RESEARCH_ENABLE_RELEVANCE_GATE=1`, wird **pro URL** im Worker `check_relevance` (LLM) aufgerufen. Das kann viele parallele LLM-Calls und Rate-Limits/Instabilität erzeugen; deshalb default 0. Batch-Modus läuft **nach** allen Reads und ändert keine Findings, nur Ergebnisse in `explore/relevance_gate_results.json`.

5. **deep_extract überspringt „nicht relevant“ Findings:** Es prüft pro Quelle, ob bereits ein Finding mit gleicher URL und `relevance_score < 7` existiert; wenn ja, wird die Quelle übersprungen. Das ist konsistent mit „nur relevante vertiefen“, aber deep_extract läuft nach allen Reads — zu diesem Zeitpunkt haben Findings aus parallel_reader bereits relevance_score (wenn Gate aktiv) oder default.

### 6.2 Konsistenz / UX

6. **UI „Phase abgeschlossen“ in Explore:** In ActivityFeed wird „Phase abgeschlossen“ nur angezeigt, wenn `step === "Done"` oder (Reading-Source-final und **displayPhase !== "explore"**). In Explore kann „Reading source N/N“ mehrfach kommen (Conductor-Runden); daher wird in Explore bewusst **kein** „Phase abgeschlossen“ angezeigt, bis tatsächlich advance_phase auf focus gegangen ist. Korrekt so.

7. **Progress bei Conductor-Override:** Wenn der Conductor von focus zurück auf explore override’t, wird `progress_step "Conductor: weitere explore-Runde"` gesetzt; der nächste sichtbare Schritt kommt erst beim Wiedereintritt in den explore-Case. Plan ui-stuck_bei_conductor-runde: sofortiger Step verhindert „hängend“-Wahrnehmung.

8. **prior_knowledge Nutzung:** knowledge_seed schreibt `prior_knowledge.json`; der Planner lädt sie in `_load_prior_knowledge_and_questions` und fügt sie als Kontext ein. Wenn knowledge_seed nicht läuft (Flag 0 oder Fehler), ist prior_knowledge.json leer/fehlt — Planner hat dann keinen Prior-Kontext. Kein Bug, aber Abhängigkeit.

### 6.3 Performance / Stabilität

9. **parallel_reader workers=8:** Bei vielen URLs und aktivem Relevance Gate (pro-URL-LLM) können viele gleichzeitige Aufrufe entstehen. research_deep_extract begrenzt auf 6 Worker „to reduce memory/API pressure and stabilize explore phase“.

10. **READ_LIMIT 40 bei complex:** Bei 40 URLs und 8 Workers entstehen 40 Reads; bei langsamen Quellen oder Timeouts kann die Phase lange dauern. Timeout pro URL in parallel_reader: 90s (research_web_reader.py).

---

## 7. Was wir nutzen (Zusammenfassung)

- **Planning:** research_planner (Plan, Refinement, Gap-Fill, Perspective-Rotate), optional prior_knowledge + question_graph.
- **Search:** research_web_search, research_academic (Semantic Scholar).
- **Ranking:** Inline SMART_RANK (Domain-Rank, Blocklist, pro-Domain-Cap, Topic-Priorität, Entity-Boost).
- **Dedup/Filter:** Memory get_read_urls_for_question; optional pro-URL relevance_gate + novelty (Jaccard) in parallel_reader.
- **Read:** research_parallel_reader (explore mode), research_web_reader pro URL.
- **Coverage:** research_coverage (topic-basiert, min_sources, pass/thin_priority_topics).
- **Saturation:** research_saturation_check (novelty der letzten 10 Findings).
- **Extraction:** research_deep_extract (2–5 Fakten pro lange Quelle).
- **Post-Read:** relevance_gate batch, context_manager, dynamic_outline (alle optional).
- **Orchestration:** research-cycle.sh (explore-Branch), research_conductor gate, research_advance_phase.

---

## 8. SOTA / Novel: Wo wir ansetzen können

### 8.1 State of the Art (Einordnung)

- **Planning:** LLM-basierte Queries + Topic/Entity-Extraktion; Refinement/Gap aus Coverage. SOTA wäre: retrieval-augmented planning (z.B. ähnliche erfolgreiche Queries aus Episoden), kontrollierte Diversität (z.B. MMR über Query-Embeddings), explizite Perspektiven-/Contrarian-Queries.
- **Ranking:** Heuristiken (Domain, Topic, Entity). SOTA: LTR (Learning to Rank) aus Feedback, oder zweistufiges Retrieval (z.B. Embedding-Pool + Reranker).
- **Relevance:** Einzelner LLM-Score 0–10, Schwellwert 7. SOTA: Cross-Encoder-Reranker, oder kleine spezialisierte Relevanz-Modelle; Batch-Nachbewertung ohne Pipeline-Änderung ist konservativ.
- **Novelty:** Jaccard auf Wort-Sets (3+ Zeichen) vs. letzte 50 Findings. SOTA: Embedding-basierte Ähnlichkeit (z.B. cosine), oder dedizierte „already stated“-Klassifikation.
- **Coverage:** Topic-basiert, min_sources, Keyword-Match. SOTA: semantische Topic-Coverage (Embeddings pro Topic vs. Finding-Embeddings), oder konzeptuelle Lückenerkennung (LLM/Graph).
- **Saturation:** Einfacher Schwellwert (7/10 low novelty). SOTA: Trend über Runden (z.B. novelty-Verteilung über Zeit), oder Stopp wenn marginaler Informationsgewinn unter Schwellwert.
- **Conductor:** Bounded State, 4 Aktionen, LLM + Fallback. SOTA: Reinforcement Learning / Bandits über Phasenübergänge mit Belohnung (z.B. Report-Qualität, Kritik-Score); oder explizites „explore vs. exploit“ (search_more vs. verify).

### 8.2 Konkrete Verbesserungen (priorisiert)

1. **read_stats kumulieren:** In research-cycle.sh die JSON-Outputs aller parallel_reader-Aufrufe (Round 1, Refinement, Gap, Depth) sammeln und am Ende attempts/successes/failures summieren; `explore/read_stats.json` mit diesen kumulierten Werten schreiben. So sind Evidence Gate und adaptive Schwellen korrekt.

2. **Memory read_urls:** Paraphrase-robustes Matching (z.B. semantischer Hash oder Embedding-Nearest-Neighbor für Frage) damit leichte Umformulierungen dieselben URLs skippen.

3. **Novelty:** Optionale Embedding-Ähnlichkeit neben Jaccard (z.B. wenn findings bereits Embeddings haben oder on-the-fly berechnet); Schwellwert konfigurierbar.

4. **Exploration vs. Exploitation:** Conductor-Prompt oder Policy explizit „explore early“ (mehr search_more/read_more) vs. „exploit“ (verify/synthesize) abhängig von findings_count und coverage; oder einfache Bandit-Regel für „noch eine Runde vs. weiter“.

5. **Coverage semantisch:** Optional Topic- und Finding-Embeddings; Coverage-Rate als Überlappung semantischer Räume statt nur Keyword-Match. Aufwand höher, aber genauer für thematische Lücken.

6. **Refinement-Queries aus Episoden:** Planner könnte ähnliche erfolgreiche Queries aus früheren Projekten (Memory/run_episodes) als Beispiele abrufen (RAG), um bessere Präzisions-Queries zu erzeugen.

---

## 9. Referenzen (Code-Stellen)

- Explore-Branch: `operator/workflows/research-cycle.sh` ab Zeile ~437 (`case "explore")`).
- Parallel Reader: `operator/tools/research_parallel_reader.py` (main, _save_result, _run_worker).
- Coverage: `operator/tools/research_coverage.py` (assess_coverage, main).
- Conductor Gate: `operator/tools/research_conductor.py` (gate_check, PHASE_TO_ACTION, ACTION_TO_PHASE).
- Memory read_urls: `operator/lib/memory/memory_v2.py` (record_read_urls, get_read_urls_for_question), Aufruf in research-cycle.sh FILTER_READ_URLS.
- Planner Modes: `operator/tools/research_planner.py` (build_refinement_plan, build_gap_fill_queries, _load_prior_knowledge_and_questions).
- Quality Gate Explore-Stats: `operator/tools/research_quality_gate.py` (_load_explore_stats).

---

## 10. Conductor & Tool-Use: Sauber umgesetzt? (Bewertung)

### 10.1 Was sauber ist

- **Einheitliche Tool-Aufrufe (Bash):** Alle Tools werden mit `python3 "$TOOLS/<script>.py" ...` aufgerufen; stderr konsistent nach `$CYCLE_LOG` oder `2>/dev/null` (Progress). Kein wilder Mix aus Subprocess und Inline-Python für dieselbe Aufgabe.
- **Conductor als Berater (Gate):** Wenn `RESEARCH_USE_CONDUCTOR=0`, ist die Bash-Pipeline Master. Vor jedem `advance_phase(next)` wird `research_conductor.py gate $PROJECT_ID $next_phase` aufgerufen. Der Conductor gibt entweder `next_phase` (weiter) oder eine andere Phase (z. B. `explore`) zurück; dann wird `research_advance_phase.py` mit dieser Phase aufgerufen. Klare Trennung: Conductor entscheidet nur „weiter oder nochmal Phase X“, Bash führt aus.
- **Bounded State:** Conductor sieht nur 6 Metriken (findings_count, source_count, coverage_score, verified_claims, budget_spent_pct, steps_taken) plus Deltas. Keine rohen Findings im State — gut für Stabilität und Reproduzierbarkeit.
- **Override-Caps:** Max 1 Override für `explore->focus`, sonst max 2 pro Transition; bei budget ≥ 80 % oder coverage ≥ 0,8 und findings ≥ 30 wird immer durchgelassen. Verhindert Endlosschleifen.
- **advance_phase.py:** Eine zentrale Stelle für Phasenwechsel; schreibt `phase`, `phase_history`, `phase_timings`, bei `done` auch `status` und `completed_at`. Terminal-Status wird nicht überschrieben.
- **Conductor run_cycle nutzt dieselben Tools:** `_run_tool()` ruft die gleichen Python-Skripte (planner, web_search, parallel_reader, deep_extract, verify, quality_gate, synthesize) per Subprocess auf; Umgebung `OPERATOR_ROOT`, `RESEARCH_PROJECT_ID` gesetzt.

### 10.2 Was nicht sauber bzw. durchdacht ist

1. **Conductor-Gate: Stderr verworfen, leere Ausgabe = Advance**  
   Im Bash wird der Gate-Aufruf so gemacht:  
   `conductor_next=$(python3 "$TOOLS/research_conductor.py" gate "$PROJECT_ID" "$next_phase" 2>>/dev/null) || true`  
   - Bei Python-Crash oder Exception gibt der Conductor ggf. nichts aus → `conductor_next` ist leer. Dann gilt `if [ -n "$conductor_next" ] && [ "$conductor_next" != "$next_phase" ]` als falsch → **wir advance immer** (kein Override). Das ist Fail-Open: Conductor-Fehler führt zum Phasenwechsel statt zur sicheren Wiederholung. Stderr landet nirgends (außer in /dev/null), Fehler sind schwer debuggbar.

2. **Conductor run_cycle vs. Bash-Pipeline nicht äquivalent**  
   Wenn `RESEARCH_USE_CONDUCTOR=1`, übernimmt `research_conductor.py run_cycle` die Steuerung und die Bash-Pipeline (explore/focus/connect/verify) wird **nie** ausgeführt. Im run_cycle:
   - **search_more:** Nur Planner (wenn kein Plan) + Web Search; Ergebnis wird als `sources/*.json` gespeichert. Es gibt **kein** SMART_RANK, keinen Memory-Filter auf read_order, kein Academic, keine Coverage-Runden, keine Saturation, keine Refinement/Gap/Depth-Reads. Die „Explore“-Logik der Bash (3-Runden-Planung, Coverage, Lücken füllen) existiert im Conductor-Modus nicht.
   - **read_more:** Unread Sources → parallel_reader(explore) + deep_extract + context_manager + dynamic_outline + supervisor. Kein Coverage-Update danach.
   - **verify:** Vier Verify-Tools + quality_gate; bei Pass → advance_phase(synthesize). Es gibt **keinen** separaten „connect“-Schritt (Counter-Evidence, etc.).
   - **Phase-Label:** Conductor ruft `advance_phase()` nur für `synthesize` und `done`. Die Phase im Projekt springt also von `explore` direkt zu `synthesize`/`done`. `focus` und `connect` kommen in `phase_history` nie vor, wenn nur run_cycle läuft. UI/Analytics erwarten aber oft die klassische Kette explore → focus → connect → verify → synthesize.

3. **Coverage wird im Conductor run_cycle nie berechnet**  
   `read_state()` liest `coverage_score` aus `coverage_round3/2/1.json`. Im run_cycle wird nirgends `research_coverage.py` aufgerufen. Nach search_more/read_more stehen neue sources/findings, aber die Coverage-Dateien bleiben alt. Der Conductor entscheidet also mit **veraltetem** coverage_score (oder 0), bis irgendwann einmal die Bash-Pipeline gelaufen ist. Das untergräbt die Qualität der Entscheidung (z. B. „verify“ wenn coverage eigentlich noch niedrig ist).

4. **Kein Progress im Conductor-Modus**  
   run_cycle ruft weder `progress_start` noch `progress_step` auf. Die UI (ActivityFeed, progress.json) zeigt dann keinen Fortschritt, obwohl der Conductor arbeitet. Nutzer sieht „Phase explore“ ohne sichtbare Schritte.

5. **Doppelte Semantik von steps_taken**  
   `steps_taken` wird aus `phase_history` Länge gelesen, aber wenn `conductor_state.json` existiert, überschreibt dessen `steps_taken` das. Bei Conductor als Master wächst nur `conductor_state.steps_taken`, `phase_history` hat nur [synthesize, done]. Zwei Quellen der Wahrheit können bei Wechsel zwischen Bash und Conductor oder bei Auswertung verwirren.

6. **research_advance_phase: loop_count > 3 erzwingt Sprung**  
   Wenn dieselbe Phase schon dreimal in `phase_history` vorkommt, wird automatisch die **nächste** Phase gesetzt (z. B. viertes „explore“ → „focus“). Das verhindert Endlosschleifen, kollidiert aber mit dem Conductor-Override: Conductor könnte bewusst „nochmal explore“ wollen; nach dem dritten Mal erzwingt advance_phase trotzdem focus. Die Logik ist nicht zwischen „Conductor-Override“ und „Bash-Normalablauf“ dokumentiert.

7. **Tool-Fehler im run_cycle still schlucken**  
   `_run_tool` gibt nur True/False zurück; bei False wird oft einfach `continue` gemacht. Es gibt kein Retry, kein explizites Logging in eine projektspezifische Log-Datei aus dem Conductor heraus, und keine Abbruchstrategie (z. B. „nach 3 Fehlern in Folge aufgeben“). Ein dauerhaft fehlerhaftes Tool kann zu vielen nutzlosen Schleifendurchläufen führen.

### 10.3 Empfehlungen (priorisiert)

1. **Conductor-Gate:** Stderr des Gate-Aufrufs in `$CYCLE_LOG` leiten (z. B. `2>> "$CYCLE_LOG"`) und bei leerem `conductor_next` (z. B. Timeout/Crash) **nicht** advance, sondern `next_phase` beibehalten (nochmal gleiche Phase) oder explizit Fail-Safe (z. B. nach 2 leeren Antworten advance).
2. **run_cycle angleichen oder klar dokumentieren:** Entweder (a) nach search_more/read_more optional `research_coverage.py` aufrufen und Coverage-Dateien schreiben, oder (b) in der Doku (RESEARCH_AUTONOMOUS.md, EXPLORE_PHASE_DEEP_DIVE.md) klar stellen: „Conductor-as-Master ist ein vereinfachter Aktionen-Loop, kein Ersatz für die volle 3-Runden-Explore-Pipeline.“
3. **Progress im run_cycle:** Vor/nach Aktionen `research_progress.py` start/step aufrufen (oder zentrales Progress-Modul aus Python), damit die UI auch bei RESEARCH_USE_CONDUCTOR=1 Fortschritt anzeigt.
4. **steps_taken:** Eine klare Regel dokumentieren oder im Code: z. B. „Wenn conductor_state.json existiert, steps_taken nur dort lesen; phase_history nur für Phasenverlauf, nicht für Schrittanzahl.“
5. **advance_phase loop_count:** Optional einen Parameter oder Env (z. B. RESEARCH_FORCE_PHASE_ADVANCE_AFTER_LOOPS=3), oder bei Conductor-Override die loop_count-Logik überspringen, damit der Conductor die volle Kontrolle behält.

---

*Letzte Aktualisierung: Stand Code/Repo; bei Änderungen an Routen, Phasen oder Flags die übrigen Docs (UI_OVERVIEW.md, RESEARCH_QUALITY_SLO.md, RESEARCH_AUTONOMOUS.md, SYSTEM_CHECK.md) anpassen.*
