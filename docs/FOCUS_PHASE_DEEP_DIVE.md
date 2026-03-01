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
| `verify/deepening_queries.json` | Verify bei Loop-back zu Focus | **Wird in Focus derzeit nicht gelesen** (siehe Abschnitt 4) |

### Temporär im Job (Artifacts)

| Datei | Verwendung |
|-------|------------|
| `focus_queries.json` | Ausgabe Planner --gap-fill; Eingabe Web Search |
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

1. **Verify→Focus Loop-back nutzt deepening_queries nicht:** Wenn das Evidence Gate in Verify failt und `research_reason.py gap_analysis` high-priority Gaps mit `suggested_search` liefert, schreibt der Cycle `verify/deepening_queries.json` und ruft `advance_phase "focus"` auf. Die **nächste** Focus-Runde liest aber ausschließlich aus Coverage (`--gap-fill $COV_FILE`) und ignoriert `verify/deepening_queries.json`. Die vom Verify-Gap-Analysis erzeugten Suchanfragen werden nie ausgeführt. **Empfehlung:** In Focus: wenn `verify/deepening_queries.json` existiert und nicht leer, diese Queries zusätzlich oder vorrangig für Web Search nutzen (oder erste Focus-Runde nach Verify-Loop mit deepening_queries füllen).

2. **Focus ohne Coverage:** Wenn Explore in einem anderen Job lief, liegen unter Umständen keine `coverage_round*.json` im Projekt. Dann wird `focus_queries.json = {"queries":[]}` gesetzt. Web Search liefert nichts; Ranking liefert nur bereits vorhandene, noch nicht gelesene Quellen. Das ist dokumentiert (RESEARCH_AUTONOMOUS.md) und bewusst kein Abbruch – aber inhaltlich macht Focus dann nur „weiter lesen was da ist“, kein gezieltes Gap-Fill.

3. **read_stats für Focus nicht persistiert:** Explore schreibt `explore/read_stats.json` aus Round-1-Read. Focus schreibt FOCUS_STATS nur ins Log und in Shell-Variablen; es gibt kein `focus/read_stats.json`. Für ein einheitliches Evidence-Gate oder Metriken wäre kumulierte oder phasenspezifische Read-Statistik nützlich.

### 4.2 Konsistenz / UX

4. **UI ExecutionTree:** Focus wird als „Relevance filtering“ beschrieben. Inhaltlich ist Focus „targeted deep-dive from coverage gaps“ (Gap-Fill + Lesen). Die Beschreibung sollte auf „Gap-fill & deep read“ o.ä. angepasst werden (siehe Regel docs-sync-with-code).

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
- **Loop-back von Verify:** Bei Evidence-Gate-Fail und high-priority Gaps → advance_phase "focus" (deepening_queries werden derzeit nicht genutzt).

---

## 6. SOTA / Novel: Was wir verbessern oder neu bauen können

### 6.1 Sofort umsetzbar

- **Deepening-Queries in Focus nutzen:** Wenn `verify/deepening_queries.json` existiert (z.B. nach Loop-back von Verify), in Focus diese Queries mit in die Web Search geben (z.B. focus_queries = gap_fill_queries + deepening_queries, oder erste Priorität deepening).
- **Focus read_stats persistieren:** `focus/read_stats.json` mit read_attempts/successes/failures schreiben (analog explore/read_stats.json) für Metriken und Evidence Gate.
- **UI:** ExecutionTree-Beschreibung für Focus auf „Gap-fill & deep read“ (oder vergleichbar) ändern; UI_OVERVIEW ggf. einen Satz zu Focus ergänzen.

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
