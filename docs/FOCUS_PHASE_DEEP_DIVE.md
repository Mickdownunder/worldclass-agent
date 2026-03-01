# Focus-Phase: Deep Dive (Experten-Dokument)

Dieses Dokument beschreibt **genau**, wie die Focus-Phase funktioniert, welche Dateien und Tools beteiligt sind, was falsch oder verbesserungswürdig ist und wo SOTA/novel Ansätze möglich sind. Quelle der Wahrheit: Code in `operator/workflows/research-cycle.sh` und `operator/tools/`.

---

## 1. Ablauf: Was passiert in Focus (Schritt für Schritt)

Die Focus-Phase wird in `research-cycle.sh` im `case "focus")` ausgeführt. Reihenfolge:

| Schritt | Aktion | Tool/Skript | Artefakte |
|--------|--------|-------------|-----------|
| 0 | Eintritt | Nach Explore: `advance_phase "focus"` (mit Conductor Gate) | `project.json` phase=focus |
| 1 | Token Governor (wenn Flag) | `research_token_governor.recommend_lane` | `governor_lane.json`, `RESEARCH_GOVERNOR_LANE` |
| 2 | Coverage ermitteln | Inline: round3 → round2 → round1 (Projekt oder Artifacts) | `COV_FILE` |
| 3 | Focus-Queries erzeugen | `research_planner.py --gap-fill $COV_FILE $PROJECT_ID` | `artifacts/focus_queries.json` |
| 4 | Fallback ohne Coverage | Wenn kein COV_FILE: `echo '{"queries":[]}'` | Leere Queries, nur Lesen möglich |
| 5 | Web Search | `research_web_search.py --queries-file focus_queries.json --max-per-query 8` | `artifacts/focus_search.json` |
| 6 | Quellen speichern | Inline Python: URLs aus focus_search → `sources/<sid>.json` | Neue/weitere `sources/*.json` |
| 7 | Ranking | Inline Python: Domain-Rank, Blocklist, topic_boost, unread first | `artifacts/focus_read_order.txt` |
| 8 | Parallel Read | `research_parallel_reader.py $PROJECT_ID focus --input-file focus_read_order.txt --read-limit 15 --workers 8` | `sources/*_content.json`, `findings/*.json` (read_phase=focus) |
| 9 | Deep Extract | `research_deep_extract.py $PROJECT_ID` | Zusätzliche Findings `source=deep_extract` |
| 10 | Context Manager (wenn Flag) | `research_context_manager.py add` | Conductor-Context |
| 11 | advance_phase "connect" | Conductor Gate + `research_advance_phase.py` | phase=connect (oder Override → focus) |

**Conductor Gate:** Vor jedem `advance_phase` wird `research_conductor.py gate $PROJECT_ID <next_phase>` aufgerufen. Für Focus→Connect: erwartete Aktion = `read_more` (PHASE_TO_ACTION["connect"]). Wenn das LLM z.B. `verify` will, Override: nächste Phase = `focus` (ACTION_TO_PHASE["read_more"] = "focus"). Max 2 Overrides für `focus->connect`, dann wird durchgelassen.

---

## 1.1 Verbindung mit Vorgänger- und Nachfolger-Phase

### Explore → Focus

| Was Explore an Focus übergibt | Wo | Verwendung in Focus |
|-------------------------------|-----|----------------------|
| **Phase** | `project.json` nach `advance_phase "focus"` (inkl. Conductor Gate) | Nächster Cycle startet in `focus)` |
| **Coverage** | `coverage_round3.json` → `round2` → `round1` in **PROJ_DIR** (Explore kopiert nach jeder Runde: `cp "$ART/coverage_roundN.json" "$PROJ_DIR/..."`) | Focus sucht COV_FILE zuerst in PROJ_DIR, dann ART; Gap-Fill liest `uncovered_topics` |
| **research_plan.json** | Bereits in PROJ_DIR (von Init/Explore) | `research_planner.py --gap-fill` liest `topics`, `entities`, `perspectives` |
| **sources/** und **findings/** | PROJ_DIR (Explore hat gesucht, gelesen, Findings geschrieben) | Focus ergänzt neue sources (FOCUS_SAVE), rankt nur **unread** (keine _content.json); neue Findings mit `read_phase=focus` |
| **explore/read_stats.json** | PROJ_DIR | Wird vom Evidence Gate **nach** Verify gemeinsam mit focus/read_stats genutzt (Focus schreibt nicht in explore/) |

**Sonderfall:** Focus läuft in anderem Job als Explore → ART hat keine coverage_round*.json; Focus liest Coverage aus **PROJ_DIR** (von Explore dorthin kopiert). Wenn Explore für dieses Projekt nie lief: kein COV_FILE → leere focus_queries, nur „weiter lesen“ (siehe §8.3).

### Focus → Connect

| Was Focus an Connect übergibt | Wo | Verwendung in Connect |
|-------------------------------|-----|------------------------|
| **Phase** | `project.json` nach `advance_phase "connect"` (inkl. Conductor Gate) | Nächster Cycle startet in `connect)` |
| **findings/** | PROJ_DIR (Explore + Focus: parallel_reader + deep_extract) | Connect: `research_entity_extract.py` (_load_findings), `research_reason.py contradiction_detection` (_load_findings), `research_reason.py hypothesis_formation` (_load_findings) |
| **sources/** | PROJ_DIR (Explore + Focus: FOCUS_SAVE + *_content.json) | Connect liest sie nicht direkt; entity_extract/reason nutzen findings; Verify-Phase nutzt sources später |
| **focus/read_stats.json** | PROJ_DIR | Evidence Gate (Verify) summiert mit explore/read_stats |
| **project.json** | question, config, phase_history | Connect liest project für hypothesis_formation/contradiction_detection |

Connect erwartet **keine** Connect-spezifischen Dateien von Focus; Connect erzeugt selbst `contradictions.json`, `thesis.json`, `connect/connect_status.json`, `ART/hypotheses.json`. Die Verbindung ist damit **lückenlos**: Focus hinterlässt angereicherte findings/ und sources/, Connect arbeitet nur auf findings/ (und schreibt neue Artefakte).

---

## 2. Beteiligte Dateien

### Pro Projekt (`research/<project_id>/`)

| Pfad | Geschrieben von / gelesen in Focus | Inhalt |
|------|------------------------------------|--------|
| `project.json` | advance_phase, Governor | `phase`, `question`, `config`, `phase_history` |
| `research_plan.json` | research_planner (--gap-fill) | `topics`, `entities`, `perspectives` (für Gap-Queries) |
| `coverage_round3.json` / `round2` / `round1` | Explore; Focus liest | `uncovered_topics`, `topics`, `coverage_rate` |
| `sources/<id>.json` | Focus: FOCUS_SAVE + parallel_reader | URL, title, topic_id, confidence |
| `sources/<id>_content.json` | research_parallel_reader | text, title, abstract |
| `findings/<id>.json` | parallel_reader, deep_extract | excerpt, source=read/deep_extract, read_phase=focus |
| `governor_lane.json` | research-cycle.sh (Token Governor) | cheap/mid/strong |
| `conductor_decisions.json` | research_conductor (shadow/gate) | Entscheidungen pro Run |
| `conductor_overrides.json` | research_conductor gate | z.B. `focus->connect: N` |
| `verify/deepening_queries.json` | Verify bei Loop-back; Focus liest und merged | Queries aus gap_analysis (suggested_search); vor gap-fill in focus_queries.json gemerged |

### Temporär im Job (Artifacts)

| Datei | Verwendung |
|-------|------------|
| `focus_queries.json` | Ausgabe: Planner --gap-fill (oder leer); ggf. überschrieben durch Merge (deepening + gap-fill). Eingabe: Web Search, RANK_FOCUS |
| `focus_search.json` | Rohe Suchergebnisse; Eingabe FOCUS_SAVE |
| `focus_read_order.txt` | Sortierte Source-Pfade für parallel_reader |

---

## 3. Tools im Detail (Focus-relevant)

### research_planner.py --gap-fill

- **Eingabe:** Pfad zu Coverage-JSON (round3/2/1), project_id.
- **Logik:** Liest `uncovered_topics` (max 8), `research_plan.json` für `perspectives` und `entities`. Pro ungedecktem Topic:
  - Priorität 1 → 3 Perspektiven, sonst 2.
  - Query = `"{name} {description[:40]} evidence comparison"` (gekürzt 180 Zeichen).
  - Zusätzlich für Entities, die im Topic-Namen vorkommen: `"{entity} {name} benchmark study"` (max 4 Entities).
- **Ausgabe:** `{"queries": [{"query", "topic_id", "type": "academic"|"web", "perspective"}]}` max 40 Queries.
- **Ohne Coverage:** Rückgabe `{"queries": []}`.

### research_parallel_reader.py (mode=focus)

- **Eingabe:** `--input-file` mit einer Source-JSON-Pfad oder URL pro Zeile; `--read-limit` (Focus: min(limit, 15)), `--workers` (default 8).
- **Unterschied zu explore:** `read_limit` für Focus auf max 15 gecappt; `source_label = "read"` (gleich wie explore); Findings bekommen `read_phase: "focus"`.
- **Relevance Gate / Novelty:** Wie in Explore (optional Relevance Gate, Jaccard-Novelty; low-novelty nur Stderr).
- **Ausgabe:** Letzte Zeile stdout JSON: `{"read_attempts", "read_successes", "read_failures"}`.

### research_deep_extract.py

- Läuft nach Focus-Reads (wie nach Explore). Verarbeitet alle `*_content.json` mit Textlänge ≥ 3000 Zeichen; extrahiert 2–5 Fakten pro Quelle; neue Findings mit `source=deep_extract`. Wird von Focus und Explore gemeinsam genutzt.

### research_conductor.py (Gate für focus→connect)

- **focus→connect:** Erwartete Aktion für „Connect“ = `read_more` (PHASE_TO_ACTION["connect"] = "read_more"). Wenn LLM `read_more` sagt → Advance zu connect. Wenn LLM `search_more`/`verify`/`synthesize` sagt → Override zu focus/verify/synthesize; für `read_more` → Phase = focus (nochmal Focus-Runde).
- **Caps:** Max 2 Overrides für focus->connect; bei coverage_score ≥ 0.8 und findings_count ≥ 30 oder budget_spent_pct ≥ 0.8 wird durchgelassen.

### research_advance_phase.py

- Phase-Reihenfolge: `explore → focus → connect → verify → synthesize → done`. Bei gleicher Phase >3× in phase_history: automatisches Bump zur nächsten Phase (Loop-Schutz).

---

## 4. Was falsch oder problematisch ist

### 4.1 Bugs / Lücken

1. **Verify→Focus Loop-back nutzt deepening_queries:** Umgesetzt. Wenn `verify/deepening_queries.json` existiert, merged research-cycle.sh diese Queries mit dem Gap-Fill-Ergebnis (deepening zuerst, Dedupe nach Query-Text) und schreibt das Ergebnis nach `artifacts/focus_queries.json`. Web Search und folgende Schritte nutzen die gemergte Liste.

2. **Focus ohne Coverage:** Wenn Explore in einem anderen Job lief, liegen unter Umständen keine `coverage_round*.json` im Projekt. Dann wird `focus_queries.json = {"queries":[]}` gesetzt. Web Search liefert nichts; Ranking liefert nur bereits vorhandene, noch nicht gelesene Quellen. Das ist dokumentiert (RESEARCH_AUTONOMOUS.md) und bewusst kein Abbruch – aber inhaltlich macht Focus dann nur „weiter lesen was da ist“, kein gezieltes Gap-Fill.

3. **read_stats für Focus:** Umgesetzt. Nach dem Focus-Parallel-Read schreibt research-cycle.sh `focus/read_stats.json` (read_attempts, read_successes, read_failures) analog zu explore/read_stats.json.

### 4.2 Konsistenz / UX

4. **UI ExecutionTree:** Bereits angepasst: Focus wird als „Gap-fill & deep read“ beschrieben (ExecutionTree.tsx).

5. **Conductor focus->connect:** ACTION_TO_PHASE["read_more"] = "focus". Wenn der Conductor also „read_more“ will und wir gerade von Focus nach Connect wollen, bleibt die Phase focus (Override). Das ist gewollt (nochmal lesen). Wenn er „verify“ will, Override-Phase = verify – dann würde der nächste Cycle in **verify** starten, nicht in focus. Korrekt so.

### 4.3 Performance / Grenzen

6. **Gap-Fill-Queries rein template-basiert:** `build_gap_fill_queries` baut Queries ohne LLM aus Topic-Name, description[:40] und festen Perspektiven. Refinement in Explore nutzt dagegen LLM (`build_refinement_plan`). Focus-Queries könnten qualitativ von einer LLM-Gap-to-Query-Stufe profitieren (siehe SOTA/Novel unten).

7. **read_limit 15 in Focus:** Deutlich weniger als Explore (bis 40). Sinnvoll um Focus kurz zu halten; bei vielen Lücken könnten 15 Reads zu wenig sein – aktuell keine adaptive Anpassung.

8. **Eine Focus-Runde pro Cycle:** Pro research-cycle wird genau eine Focus-Runde (ein Gap-Fill + ein Read-Batch) ausgeführt. Mehr Runden entstehen nur durch Conductor-Override (focus→focus).

---

## 5. Was wir nutzen (Zusammenfassung)

- **Coverage-basiertes Gap-Fill:** uncovered_topics aus research_coverage; research_planner --gap-fill; feste Perspektiven/Entities.
- **Gleicher Read-Stack wie Explore:** research_web_search, FOCUS_SAVE, Domain-Rank/Blocklist, research_parallel_reader (mode=focus), research_deep_extract.
- **Conductor Gate:** Hybrid-Entscheidung vor advance_phase (focus→connect mit max 2 Overrides).
- **Token Governor:** Optional gleiche Lane-Logik wie in Explore.
- **Loop-back von Verify:** Bei Evidence-Gate-Fail und high-priority Gaps → advance_phase "focus"; nächste Focus-Runde merged `verify/deepening_queries.json` in focus_queries und nutzt sie für Web Search.

---

## 6. SOTA / Novel: Was wir verbessern oder neu bauen können

### 6.1 Sofort umsetzbar

- **Deepening-Queries in Focus:** Erledigt (Merge deepening + gap_fill, Dedupe, deepening zuerst).
- **Focus read_stats:** Erledigt (`focus/read_stats.json` wird nach Focus-Read geschrieben).
- **UI:** ExecutionTree bereits „Gap-fill & deep read“; UI_OVERVIEW ggf. einen Satz zu Focus ergänzen.

### 6.2 Mittelfristig (SOTA)

- **LLM-gestützte Gap-to-Query für Focus:** Statt nur Template (name + description[:40] + "evidence comparison") ein kurzes LLM-Call pro ungedecktem Topic oder pro Batch: „Given this research question and uncovered topic, output 1–2 precise search queries.“ Reduziert Rauschen und verbessert Trefferqualität (analog zu build_refinement_plan in Explore).
- **Coverage-Freshness:** Focus verwendet Coverage aus Explore (round3/2/1). Wenn in einer Conductor-Focus-Runde schon neue Findings dazugekommen sind, könnte vor dem nächsten Focus-Run Coverage neu berechnet werden, damit Gap-Fill auf aktuellem Stand basiert (heute: gleiche Coverage-Datei wie beim ersten Focus-Eintritt).
- **Adaptives read_limit in Focus:** Abhängig von Anzahl der Gap-Queries oder Anzahl neuer Sources (z.B. wenn viele neue URLs aus focus_search, read_limit auf 20–25 anheben).

### 6.3 Novel / Forschung

- **Gap-Priorisierung mit Unsicherheit:** Statt nur uncovered_topics linear abzuarbeiten: LLM oder kleines Modell schätzt „impact“ oder „uncertainty reduction“ pro Gap; Focus liest zuerst Quellen für die Gaps mit höchstem erwarteten Nutzen.
- **Diversitätssteuerung in Focus:** Bei vielen Queries gezielt Domains/Perspektiven diversifizieren (z.B. pro Domain Cap 2 in Focus), um Echo-Kammern zu vermeiden.
- **Focus-spezifisches Relevance-Gate:** Leicht andere Relevanzfrage („How much does this source fill a known gap?“) statt nur „relevant to question“, mit Gap-Kontext aus coverage/uncovered_topics.

---

## 7. Referenzen

- Explore-Phase (Vorgänger): `docs/EXPLORE_PHASE_DEEP_DIVE.md`
- Conductor & Overrides: `tools/research_conductor.py`, `docs/EXPLORE_PHASE_DEEP_DIVE.md` §3
- Coverage-Struktur: `tools/research_coverage.py` (assess_coverage → uncovered_topics)
- Loop-back Verify→Focus: `workflows/research-cycle.sh` (Evidence Gate fail + LOOPCHECK + advance_phase "focus")
- Phase-Reihenfolge: `tools/research_advance_phase.py` (order), `docs/UI_OVERVIEW.md`

---

## 8. Alle erdenklichen Situationen (Was passiert wo, wann, warum, worauf hat was Einfluss)

Dieser Abschnitt geht systematisch jede erdenkliche Situation durch: **Wo** werden Daten geschrieben/gelesen, **wann** tritt welcher Pfad ein, **warum**, und **worauf** hat jede Sache Einfluss.

### 8.1 Orte: PROJ_DIR vs. ART

| Ort | Bedeutung | Wer schreibt | Wer liest (in Focus) |
|-----|------------|--------------|----------------------|
| **PROJ_DIR** = `research/<project_id>/` | Projektzustand, persistent über Jobs hinweg | Explore (coverage, sources, findings, explore/read_stats), Verify (verify/*, deepening_queries.json), Focus (sources, findings, focus/read_stats), advance_phase (project.json) | Focus: project.json, research_plan.json, coverage_round*.json, verify/deepening_queries.json, sources/, focus/ (read_stats schreiben) |
| **ART** = `$PWD/artifacts` | Job-lokale Artefakte; bei neuem Job leer bzw. nur was dieser Job erzeugt | Dieser research-cycle (focus_queries.json, focus_search.json, focus_read_order.txt) | Focus: focus_queries.json (nach Gap-Fill und Merge), focus_search.json, focus_read_order.txt |

- **Folge:** Wenn Focus in einem **anderen Job** als Explore läuft: `ART` hat keine coverage_round*.json aus Explore. Daher sucht Focus zuerst in **PROJ_DIR** (round3→2→1), dann in ART. Explore kopiert nach jeder Coverage-Runde nach PROJ_DIR (`cp … "$PROJ_DIR/coverage_roundN.json"`), also ist Coverage in PROJ_DIR vorhanden, sofern Explore jemals für dieses Projekt gelaufen ist.
- **Folge:** Wenn Explore für dieses Projekt **noch nie** gelaufen ist (z. B. manuell phase=focus gesetzt): Kein COV_FILE → focus_queries = [] (siehe 8.3).

### 8.2 Wann kommt Focus dran?

| Situation | Auslöser | Nächster Schritt nach Focus |
|-----------|----------|----------------------------|
| Normal nach Explore | Explore beendet mit `advance_phase "focus"` (inkl. Conductor Gate) | Focus läuft → am Ende `advance_phase "connect"` |
| Loop-back von Verify | Evidence Gate fail + high-priority Gaps + `phase_history.count("focus") < 2` → `advance_phase "focus"` | Focus läuft; dabei wird `verify/deepening_queries.json` (von Verify geschrieben) mit Gap-Fill gemerged |
| Conductor-Override (Focus→Connect) | Beim `advance_phase "connect"` gibt Conductor z. B. `read_more` zurück → next_phase = focus (ACTION_TO_PHASE["read_more"]) | Nächster Cycle startet wieder in Focus („nochmal lesen“); max 2 solche Overrides, dann wird durchgelassen |
| Loop-Schutz in advance_phase | `phase_history.count(new_phase) > 3` | Automatisches Bump zur nächsten Phase (kein dritter Focus-Loop nur durch Conductor) |

### 8.3 Focus ohne Coverage (kein COV_FILE)

| Schritt | Was passiert |
|--------|----------------|
| COV_FILE | Keine Datei in PROJ_DIR/ART → `focus_queries.json` = `{"queries":[]}` |
| Merge deepening | Falls `verify/deepening_queries.json` existiert: Nur diese Queries landen in focus_queries.json (Gap-Fill war leer). **Ohne** deepening bleibt focus_queries = [] |
| Web Search | Liefert keine neuen Treffer (leere Query-Liste) |
| FOCUS_SAVE | Fügt keine neuen sources hinzu |
| RANK_FOCUS | Sortiert nur **bereits vorhandene** sources, die noch keine `*_content.json` haben (unread first) |
| Parallel Read | Liest bis zu 15 dieser unread sources (oder weniger, wenn weniger da sind) |
| focus/read_stats.json | Wird trotzdem geschrieben (attempts/successes/failures; können 0/0/0 sein wenn keine Kandidaten) |

**Einfluss:** Evidence Gate nutzt `_load_read_stats_combined`: Explore- und Focus-Read-Statistik werden summiert (read_attempts, read_successes, read_failures) für adaptive findings_count_min und Reader-Pipeline-Fail-Erkennung.

### 8.4 deepening_queries.json: Wer schreibt, Format, wer liest

| Aspekt | Detail |
|--------|--------|
| **Wer schreibt** | Verify-Phase, im Block „Evidence gate failed“: LOOPCHECK schreibt `proj_dir/verify/deepening_queries.json` nur wenn high_gaps und loopback_count < 2 und `queries` (aus suggested_search) nicht leer. |
| **Format** | Verify schreibt `{"queries": [str, str, ...]}` (reine Strings von `g.get("suggested_search")`). Das Merge-Skript in Focus akzeptiert **sowohl** Strings **als auch** Dicts (`{"query": "...", "topic_id", "type", "perspective"}`), damit beide Formate funktionieren. |
| **Wer liest** | Nur Focus: wenn Datei existiert, Merge (deepening zuerst, dann Gap-Fill, Dedupe nach Query-Text lower 200 Zeichen) → Überschreibt `artifacts/focus_queries.json`. |
| **Wann wird es genutzt?** | Genau in der **nächsten** Focus-Runde nach dem Verify-Loop-back. Einmal gemerged, werden die Queries mit Web Search ausgeführt; die Datei wird vom Merge-Skript nicht gelöscht (könnte bei erneutem Focus ohne Loop-back nochmal mit drin sein – dann Dedupe verhindert Doppelungen). |

### 8.5 Abhängigkeiten und Einflüsse (Überblick)

| Ding | Hat Einfluss auf |
|------|-------------------|
| **project.json phase** | Welcher case im research-cycle läuft (focus vs. connect vs. …). |
| **project.json status** | Terminal-Status (failed/cancelled/abandoned) → Cycle wird übersprungen. |
| **phase_history** | Loop-back-Zähler (focus count < 2 für Verify→Focus); advance_phase Loop-Schutz (>3 gleiche Phase → Bump). |
| **coverage_round*.json** (PROJ_DIR/ART) | Ob Gap-Fill Queries liefert; ob Focus inhaltlich „Gap-Fill + Lesen“ oder nur „weiter lesen“ macht. |
| **verify/deepening_queries.json** | Ob zusätzliche gezielte Queries (aus Verify gap_analysis) in focus_queries landen. |
| **research_plan.json** | Wird von `--gap-fill` gelesen (topics, perspectives, entities). |
| **sources/** (ohne _content) | RANK_FOCUS: Nur unread (keine _content.json) werden sortiert und in focus_read_order.txt geschrieben. |
| **Conductor Gate** | Nächste Phase nach Focus (connect vs. erneut focus/verify/synthesize); max 2 Overrides focus→connect. |
| **RESEARCH_ENABLE_TOKEN_GOVERNOR** | Ob Governor-Lane gesetzt wird (governor_lane.json, RESEARCH_GOVERNOR_LANE). |
| **explore/read_stats.json** | Evidence Gate (findings_count_min adaptiv, Metriken). |
| **focus/read_stats.json** | Wird mit explore/read_stats in `_load_read_stats_combined` summiert; Evidence Gate nutzt die kombinierte Statistik. |

### 8.6 Edge Cases kurz

- **deepening_queries.json existiert, aber queries = []:** Merge läuft, Ergebnis = nur Gap-Fill (oder leer).
- **deepening_queries.json malformed:** try/except im Merge → queries aus dieser Datei ignoriert, Gap-Fill bleibt.
- **focus_queries.json leer nach Merge:** Web Search liefert nichts; Rest wie 8.3.
- **parallel_reader liefert kein JSON / Stderr-only:** FOCUS_STATS leer → focus_read_attempts/successes/failures = 0; focus_read_failures per Fallback attempts−successes; read_stats.json wird trotzdem geschrieben.
- **Conductor gibt leer oder Fehler:** advance_phase nutzt dann die angeforderte Phase (connect); kein Override.
