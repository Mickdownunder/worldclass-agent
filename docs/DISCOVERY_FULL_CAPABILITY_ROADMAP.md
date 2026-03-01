# Discovery: Was müssen wir machen, damit das System voll in der Lage ist?

Damit das System **voll in der Lage** ist, intelligente, novel Entdeckungen zu machen (z. B. „Krebs heilen“), sind folgende Schritte nötig. Priorität nach Impact.

---

## 1. Discovery-aware Planner (Explore) — **Priorität 1**

**Problem:** Der Planner kennt kein `research_mode`. Die erste Suchwelle ist für Discovery nicht optimiert.

**Maßnahme:**
- In `research_planner.build_plan(question, project_id)` Projekt laden und `config.research_mode` auslesen.
- Wenn `research_mode == "discovery"`: eigenes System-/User-Prompt:
  - Ziel: **Breite, Vielfalt, Lücken, Hypothesen** (nicht „eine Antwort verifizieren“).
  - Mehr Queries (z. B. 20–40), mehr Perspektiven (z. B. 5–8).
  - Explizit: „Include adjacent fields“, „competing hypotheses“, „emerging approaches“, „where is evidence missing?“.
  - Types: mehr academic/medical wo sinnvoll (Papers, Trials), um echte Forschungslücken zu treffen.

**Ergebnis:** Explore startet mit einem Plan, der von Anfang an auf Novelty und Breite ausgerichtet ist.

**Status:** ✅ Umgesetzt (Planner liest research_mode, Discovery-Prompt aktiv).

---

## 2. Entity-Graph für Discovery Analysis ab Tag 1 — **Priorität 2**

**Problem:** Transitive Muster und Cross-Domain in `research_discovery_analysis` brauchen Entity-Relations im Memory. Beim ersten Lauf oder ohne Connect-Output sind die Signale schwach.

**Maßnahme:**
- Sicherstellen, dass Connect (entity_extract) **immer** vor Discovery Analysis läuft und Entity-Relations in Memory schreibt (bereits der Fall).
- Optional: Discovery Analysis so erweitern, dass sie **zusätzlich** den lokalen Connect-Output nutzt (z. B. `connect/entity_graph.json`), wenn Memory noch leer ist – z. B. transitive Muster aus entity_graph.json ableiten, nicht nur aus DB.
- Cross-Domain: `research_cross_domain.py` oder Insights-Job so einbinden, dass nach mehreren Projekten cross_links gepflegt werden; dann liefert _cross_domain_insights mehr.

**Ergebnis:** Novel connections und emerging entities sind auch beim ersten Discovery-Projekt stärker nutzbar.

**Status:** ✅ Umgesetzt. `research_discovery_analysis.py`: `_local_entity_graph_signals(proj_path)` liest `connect/entity_graph.json`, liefert entities/relations/local_patterns; werden in run_discovery_analysis geladen und an _synthesize_discovery_brief übergeben; bei leerem Memory werden local_patterns als GRAPH PATTERNS genutzt, LOCAL ENTITY GRAPH im Prompt übergeben.

---

## 3. Token Governor für Discovery aktivieren — **Priorität 3**

**Problem:** Token Governor ist default aus; Discovery nutzt teure Modelle ohne Lane-Steuerung.

**Maßnahme:**
- In `research-cycle.sh` Token Governor auch in **Verify** und **Synthesize** setzen (nicht nur Explore/Focus), wenn `RESEARCH_ENABLE_TOKEN_GOVERNOR=1`.
- Discovery-Modus: Lane „mid“ oder „strong“ für Discovery Analysis und Synthesize erlauben (Novelty braucht ggf. besseres Modell), aber Governor entscheidet nach expected_ig.

**Ergebnis:** Kosten unter Kontrolle; Intelligence-per-Token auch in Discovery genutzt.

**Status:** ✅ Bereits umgesetzt. research-cycle.sh setzt Governor vor Verify (Zeile ~930) und vor Synthesize/Critic (~1343, ~1365), Default `RESEARCH_ENABLE_TOKEN_GOVERNOR:-1` = an. Verify/Synthesize/Critic nutzen `model_for_lane()` (research_common.py).

---

## 4. Discovery-Brief auch bei schwachem Graph nutzbar machen — **Priorität 4**

**Problem:** Wenn transitive_patterns und cross_links leer sind, kommt der Brief fast nur aus contradictions + gaps. Das ist gut, aber wir können Lücken noch stärker machen.

**Maßnahme:**
- In `research_discovery_analysis`: Wenn `patterns` und `cross_links` leer sind, im LLM-Prompt explizit sagen: „No graph/cross-domain data yet; emphasize contradictions and coverage gaps as discovery opportunities.“
- Optional: Findings-Überblick (z. B. Top-10 Domains, seltene Begriffe) als zusätzliches Signal an den Brief-LLM übergeben.

**Ergebnis:** Key hypothesis und research_frontier sind auch ohne gefülltes Memory aussagekräftig.

**Status:** ✅ Umgesetzt. In _synthesize_discovery_brief: wenn graph_empty (keine patterns, keine cross_links), wird NOTE im User-Prompt ergänzt („emphasize contradictions and coverage gaps … Still produce novel_connections and key_hypothesis“); local_entity_graph wird immer mitgegeben, wenn vorhanden.

---

## 5. Conductor-Gate Discovery-Schwellen dokumentieren und ggf. anpassen — **Priorität 5**

**Problem:** Conductor Gate für Discovery (findings ≥ 15, sources ≥ 8) ist fest im Code. Für sehr ambitionierte Fragen könnte man früher synthesizen (z. B. 12/6) oder später (20/10).

**Maßnahme:**
- Schwellen in `research_conductor.py` als Konstanten mit Kommentar dokumentieren.
- Optional: Über Env (z. B. `RESEARCH_DISCOVERY_SYNTHESIZE_MIN_FINDINGS`) konfigurierbar machen.

**Ergebnis:** Transparenz und ggf. Tuning ohne Code-Änderung.

**Status:** ✅ Umgesetzt. research_conductor.py: `RESEARCH_DISCOVERY_SYNTHESIZE_MIN_FINDINGS` (Default 15), `RESEARCH_DISCOVERY_SYNTHESIZE_MIN_SOURCES` (Default 8); Kommentar „Discovery: only allow synthesize when enough breadth (configurable)“.

---

## 6. Kalibrierung & Memory für Discovery — **Priorität 6**

**Problem:** research_calibrator und Memory-Strategien sind nicht discovery-spezifisch.

**Maßnahme:**
- Bei `suggest_research_mode` bereits „discovery“-Keywords (siehe RESEARCH_MODES.md). Optional: Nach Abschluss von Discovery-Projekten Kalibrierung um „discovery_pass_rate“ oder „discovery_novelty_avg“ erweitern.
- Memory v2: Domain-Overrides und Strategy können auch für domain=„discovery“ oder research_mode=discovery genutzt werden, wenn gewünscht.

**Ergebnis:** System lernt aus Discovery-Läufen; Schwellen/Strategien verbesserbar.

---

## Kurz-Checkliste („voll in der Lage“)

| # | Maßnahme | Status |
|---|----------|--------|
| 1 | Discovery-aware Planner (Explore) | ✅ Umgesetzt |
| 2 | Entity-Graph / lokaler Connect-Output für Discovery Analysis | ✅ Umgesetzt |
| 3 | Token Governor in Verify/Synthesize (und für Discovery) | ✅ Bereits umgesetzt |
| 4 | Discovery-Brief bei leerem Graph robuster | ✅ Umgesetzt |
| 5 | Conductor Discovery-Schwellen dokumentiert/konfigurierbar | ✅ Umgesetzt |
| 6 | Kalibrierung/Memory für Discovery | Offen (optional) |

Mit 1–5 umgesetzt ist das System **voll in der Lage** für novel Entdeckungen. 6 erhöht Langfrist-Qualität (Lernen aus Discovery-Läufen).
