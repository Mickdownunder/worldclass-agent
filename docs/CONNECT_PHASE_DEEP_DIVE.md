# Connect-Phase — Tiefenanalyse

Vollständige technische Analyse: Datenfluss, Schema, wie Widersprüche und Hypothesen entstehen, wo Probleme liegen und wo SOTA oder novel Verbesserungen möglich sind. Quelle der Wahrheit: `operator/workflows/research-cycle.sh` (connect-Branch), `operator/workflows/research/phases/connect.sh`, `operator/tools/research_entity_extract.py`, `operator/tools/research_reason.py`.

---

## Teil 1: Datenfluss der Connect-Phase

### 1.1 Eintritt und Eingänge

- **Eintritt:** Nach Focus: `advance_phase "connect"` (mit Conductor Gate). Phase in `project.json` = `connect`.
- **Eingänge (verfügbar):**
  - **Findings:** `research/<project_id>/findings/*.json` — excerpt, title, url, source (read/deep_extract), read_phase (explore/focus). Max 40 in research_reason, max 50 in research_entity_extract.
  - **Sources:** `research/<project_id>/sources/*.json`, `*_content.json` — werden nicht direkt von Connect gelesen; Findings referenzieren sie.
  - **Projekt-Frage:** `project.json` → `question`, `domain` — genutzt von hypothesis_formation und gap_analysis (letzterer nicht in connect.sh, aber im gleichen Tool research_reason.py).
  - **Coverage/Artefakte:** Aus Explore/Focus (coverage_round*.json, research_plan.json) werden in Connect **nicht** gelesen.

### 1.2 Reihenfolge der Schritte (connect.sh)

| Schritt | Aktion | Tool/Funktion | Ausgabe |
|--------|--------|---------------|---------|
| 0 | OpenAI-Check | Inline Python (research_preflight) | Bei fehlendem `openai`: project status gesetzt, exit 1 |
| 1 | Knowledge Graph bauen | `research_entity_extract.py $PROJECT_ID` | Memory + `connect/entity_graph.json`; stdout JSON stats. Bei Fehler: Phase bricht ab (Phase 5). |
| 2 | Widersprüche finden | `research_reason.py $PROJECT_ID contradiction_detection` | `$PROJ_DIR/contradictions.json` |
| 3 | Hypothesen bilden | `research_reason.py $PROJECT_ID hypothesis_formation` | `$ART/hypotheses.json` (nutzt ggf. contradictions — Phase 3) |
| 4 | Thesis + Alternativen | Inline Python (connect.sh) | `$PROJ_DIR/thesis.json` (current, confidence, evidence, **alternatives**, contradiction_summary) |
| 5 | Connect-Status | Inline Python | `connect/connect_status.json` (entity_extract_ok, contradiction_ok, hypothesis_ok, thesis_updated) |
| 6 | Phasenwechsel | `advance_phase "verify"` | `project.json` phase=verify |

**Hinweis:** hypothesis_formation liest bei vorhandener `contradictions.json` die Widersprüche und kann kontrastive Hypothesen bilden (Connect Phase 3). Verify nutzt thesis, contradictions und Entity-Graph (Phasen 1–2).

### 1.3 Skripte und Funktionen im Detail

- **research_entity_extract.py:**  
  - `_load_findings(proj_path, max_items=50)` → Liste von Finding-Dicts.  
  - Pro Finding: `extract_entities(excerpt[:15000])` → LLM-Call, JSON-Array `[{name, type, properties}]`, type ∈ person|org|tech|concept|event.  
  - Pro Finding: `get_or_create_entity`, `insert_entity_mention` in Memory.  
  - Danach: `extract_relations(entities_list, combined_text[:20000])` → ein LLM-Call; `insert_entity_relation` für jede Relation.  
  - **Connect Phase 2:** Am Ende Export `research/<project_id>/connect/entity_graph.json` (entities, relations) für Verify/Synthesize und UI. Stdout: `{"entities": N, "relations": M, "mentions": K}`.

- **research_reason.py contradiction_detection:**  
  - `_load_findings(proj_path, max_items=40)`; Findings als JSON (url, title, excerpt[:400]) bis 10000 Zeichen.  
  - Ein LLM-Call: System-Prompt „Identify CONTRADICTIONS: pairs of findings that disagree…“, User = FINDINGS + „List 0-5 contradictions.“  
  - Ausgabe: `{"contradictions": [{"claim", "source_a", "source_b", "summary"}]}` → nach `$PROJ_DIR/contradictions.json` geschrieben (Shell redirect).

- **research_reason.py hypothesis_formation:**  
  - Gleiche Findings; question aus project. **Connect Phase 3:** Liest bei vorhandener `contradictions.json` Widersprüche und übergibt sie dem Prompt („Consider these contradictions; form hypotheses, possibly contrasting positions A vs B.“).  
  - Ein LLM-Call (RESEARCH_HYPOTHESIS_MODEL). Ausgabe: `{"hypotheses": [{"statement", "confidence", "evidence_summary"}]}` → `$ART/hypotheses.json`.

- **thesis.json-Update (connect.sh):**  
  - Liest `$ART/hypotheses.json`; erste Hypothese → `current`, `confidence`, `evidence`.  
  - **Phase 3:** `alternatives`: Liste `[{statement, confidence}]` aus weiteren Hypothesen (hyps[1:5]); optional `contradiction_summary` aus erster Widerspruch-Summary.  
  - Wenn `thesis.json` nicht existiert: wird mit Default angelegt.  
  - Danach: `connect/connect_status.json` geschrieben (Phase 5).

---

## Teil 2: Schema und Struktur

### 2.1 contradictions.json

- **Ort:** `research/<project_id>/contradictions.json`.  
- **Struktur (Phase 4 strukturiert):** `{"extracted_claims": [...], "contradictions": [{"claim", "source_a", "source_b", "summary", "claim_a_id", "claim_b_id", "claim_a_text", "claim_b_text", "relation": "contradiction"}], "pair_relations": [...]}`. Legacy: nur `{"contradictions": [{"claim", "source_a", "source_b", "summary"}]}`.  
- **Semantik:** claim = Zusammenfassung der Uneinigkeit; claim_a_id/claim_b_id verknüpfen mit extracted_claims; relation = contradiction|entailment.  
- **Gelesen von:** research_synthesize.py, research_discovery_analysis.py, research_verify.py (connect_context, in_contradiction).

### 2.2 hypotheses.json

- **Ort:** `$ART/hypotheses.json` (Job-Artefakt, nicht unter research/proj-…).  
- **Struktur:** `{"hypotheses": [{"statement": str, "confidence": 0.0–1.0, "evidence_summary": str}]}`.  
- **Semantik:** Testbare Hypothesen zur Forschungsfrage; nur die erste fließt in thesis.json.  
- **Gelesen von:** Nur der Inline-Block in connect.sh; Verify/Synthesize lesen die Hypothesen **nicht** direkt, sondern nur die abgeleitete thesis.json.

### 2.3 thesis.json

- **Ort:** `research/<project_id>/thesis.json`.  
- **Struktur:** `{"current": str, "confidence": float, "evidence": list[str], "alternatives": [...], "contradiction_summary": str?, "entity_ids": list[str]?}`.  
- **Geschrieben von:** research-init.sh (Initial-Default), connect.sh (nach hypothesis_formation; Phase 3+6: alternatives, contradiction_summary, entity_ids).  
- **Gelesen von:** research_synthesize.py (Executive Decision Synthesis, Scenario Matrix, Conclusions).

### 2.4 Entity-/Graph-Output (Memory)

- **Tabellen (lib/memory/schema.py, entities.py):**  
  - **entities:** id, name, type (person|org|tech|concept|event), properties_json, first_seen_project, created_at.  
  - **entity_relations:** id, entity_a_id, entity_b_id, relation_type, source_project, evidence, created_at.  
  - **entity_mentions:** id, entity_id, project_id, finding_key, context_snippet.  
- **API:** get_or_create_entity, insert_entity_relation, insert_entity_mention, get_entities, get_entity_relations.  
- **Projekt-Artefakt:** Connect Phase 2: `research/<project_id>/connect/entity_graph.json` (entities, relations) wird von research_entity_extract.py geschrieben. Verify und Synthesize lesen diese Datei (Priorisierung, entity_context, entity_ids). Phase 6: hypothesis_formation liest entity_graph und nutzt ihn im Prompt.

---

## Teil 3: Erzeugung von Widersprüchen und Hypothesen

### 3.1 Methode: durchweg LLM

- **Contradiction Detection (Phase 4):** Zwei Stufen bei RESEARCH_CONTRADICTION_STRUCTURED=1 (default): (1) _extract_claims_per_finding pro Finding → extracted_claims; (2) _compare_claim_pairs → pair_relations (contradiction|entailment|neutral). contradictions.json enthält claim_a_id, claim_b_id, claim_a_text, claim_b_text, source_a, source_b, relation, summary. Fallback: ein LLM-Call (Legacy) bei RESEARCH_CONTRADICTION_STRUCTURED=0.  
- **Hypothesis Formation (Phase 6):** Ein LLM-Call (RESEARCH_HYPOTHESIS_MODEL). Input: Frage + Findings + Widersprüche (Phase 3) + **Entity-Graph** aus connect/entity_graph.json („Given this entity graph, form hypotheses that reference or explain those entities and relations“).  
- **Entity/Relation Extraction:** Pro Finding ein LLM-Call für Entities, ein gemeinsamer für Relations; Typen und Relationen durch Prompt vorgegeben.

### 3.2 Limits und Fallbacks

- **Token-/Längenlimits:** Findings excerpt in entity_extract 15000 Zeichen pro Text, 8000 pro Finding für Entities; Relations auf 12000 Zeichen kombiniert; contradiction_detection 400 Zeichen pro excerpt, 10000 gesamt; hypothesis_formation 500 pro excerpt, 8000 gesamt.  
- **Fehlerbehandlung:** research_entity_extract: `|| true` im connect.sh → Fehler bremsen nicht die Pipeline; Forschung läuft weiter. contradiction_detection/hypothesis_formation: Ausgabe wird in Dateien umgeleitet; bei LLM-Exception liefert _llm_json `{}` bzw. `[]` → leere Listen.  
- **thesis.json:** Wenn hypotheses.json fehlt oder leer: thesis bleibt `current=""`, `confidence=0.0`, `evidence=[]`.  
- **OpenAI fehlt:** Connect bricht mit exit 1 ab, project status wird gesetzt (failed_dependency_missing_openai).

### 3.3 Keine Rückkopplung zwischen Teilschritten

- Contradiction Detection und Hypothesis Formation laufen **parallel** (nacheinander, aber ohne Datenfluss). Widersprüche werden nicht als Input für „vorsichtige“ oder kontrastive Hypothesen genutzt.  
- Der Knowledge Graph (Entities/Relations) wird in Connect **nicht** für Contradiction oder Hypothesis genutzt; er liegt nur in Memory.

---

## Teil 4: Probleme und Lücken

| Bereich | Problem | Schwere | Stand (Umsetzung) |
|--------|---------|--------|-------------------|
| Verify | thesis/contradictions in Verify nutzen | ~~hoch~~ | **Erledigt:** source_reliability markiert in_contradiction; claim_verification priorisiert thesis-relevant + Entity; build_claim_ledger setzt in_contradiction; connect_context.json. |
| Synthesize | hypotheses/alternatives nutzen | ~~mittel~~ | **Erledigt:** thesis.alternatives und contradiction_summary in Conclusions-Prompt. |
| Graph-Nutzung | Entity-Graph Export und Nutzung | ~~hoch~~ | **Erledigt:** connect/entity_graph.json; Verify priorisiert claims nach Entities; Synthesize nutzt entity_context im Outline. |
| Contradiction ↔ Hypothesis | Kopplung | ~~mittel~~ | **Erledigt:** hypothesis_formation liest contradictions, Prompt erweitert. |
| thesis.json | Nur erste Hypothese | ~~mittel~~ | **Erledigt:** alternatives, contradiction_summary in thesis.json. |
| Robustheit | entity_extract Fehler verschluckt | ~~mittel~~ | **Erledigt:** Kein \|\| true mehr; connect_status.json; Phase bricht bei entity_extract-Fehler ab. |
| Limits | Feste Zeichenlimits | niedrig | Unverändert. |
| Prinzipien/Domain | get_principles in Connect-Reasoning | niedrig | Unverändert. |

---

## Teil 5: SOTA- und Novel-Verbesserungen

### 5.1 Einordnung

- **Contradiction Detection (SOTA):** Strukturierte Claim-Extraktion (z. B. NER + Claim-Segmente), dann Paarvergleich (semantische Ähnlichkeit + Negation/Contrast); Nutzung von Stance-Detection und Fact-Checking-Pipelines. Aktuell: ein Monolith-LLM-Call ohne Vorstrukturierung.  
- **Hypothesis Generation (SOTA):** Abgeleitet aus Evidence-Graphen, Claim-Conclusion-Strukturen, oder Multi-Document Reasoning; mehrere konkurrierende Hypothesen mit Gewichten. Aktuell: ein LLM-Call, keine Nutzung von Graph oder Widersprüchen.  
- **Knowledge Graph für Research (SOTA):** Graph für Query-Expansion, für Verify („welche Claims betreffen Entity X?“), für Synthesize (narrative Struktur um Entitäten). Aktuell: Graph wird erzeugt, aber downstream nicht genutzt.

### 5.2 Konkrete Verbesserungen (priorisiert)

1. **Verify nutzt Connect-Output:** thesis und contradictions (und optional Top-Hypothesen) in research_verify.py einlesen; Claim-Verifikation priorisiert Claims, die die Thesis stützen/widerlegen; Source-Reliability kann Widerspruchs-Quellen markieren.  
2. **Graph in Verify/Synthesize:** get_entities/get_entity_relations(project_id) aufrufen; Verify: Claims nach Entitäten gruppieren; Synthesize: Abschnitte oder Narrative entlang des Graphen (Entitäten und Beziehungen).  
3. **Contradiction → Hypothesis:** Widersprüche als Input für hypothesis_formation („berücksichtige diese Widersprüche; formuliere ggf. kontrastive Hypothesen“); oder separater Schritt „contradiction-aware hypotheses“.  
4. **Thesis als Set:** thesis.json um alternative Hypothesen und Unsicherheits-Indikatoren erweitern; Synthesize kann dann „Position A vs B“ explizit machen.  
5. **Strukturierte Contradiction Detection:** Zwei Stufen: (1) Claims pro Finding extrahieren, (2) Paarvergleich (semantisch/regelbasiert oder LLM) statt einem großen LLM-Call; bessere Nachvollziehbarkeit und weniger Halluzination.  
6. **Export des Graphen:** Connect schreibt optional `research/<project_id>/connect/entity_graph.json` (oder ähnlich) für UI und nachgelagerte Phasen; einheitliche Quelle für „was Connect produziert hat“.

Details und phasierter Plan: [CONNECT_PHASE_WORLDCLASS_PLAN.md](CONNECT_PHASE_WORLDCLASS_PLAN.md).

---

## Kurz-Checkliste (Probleme)

| Bereich | Problem | Schwere |
|--------|---------|--------|
| Verify | Keine Nutzung von thesis/contradictions/hypotheses | hoch |
| Graph | Erzeugt, aber nicht in Verify/Synthesize genutzt; kein Projekt-Export | hoch |
| Contradiction ↔ Hypothesis | Keine Kopplung | mittel |
| thesis | Nur erste Hypothese; keine Alternativen | mittel |
| Robustheit | entity_extract Fehler mit \|\| true verschluckt | mittel |
| Limits/Prinzipien | Feste Limits; keine Principles in Connect-Reasoning | niedrig |

---

Dieses Dokument sollte bei Änderungen an Connect-Phase, research_reason.py, research_entity_extract.py, connect.sh und an UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK mitgeführt werden.

**Weiterführend:** [CONNECT_PHASE_WORLDCLASS_PLAN.md](CONNECT_PHASE_WORLDCLASS_PLAN.md) — SOTA-Überblick und phasierter Plan für eine weltklasse Connect-Phase.
