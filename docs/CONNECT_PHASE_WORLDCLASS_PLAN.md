# Connect-Phase — Plan: Weltklasse SOTA/Novel

Wie Contradiction Detection, Hypothesis Generation und Knowledge-Graph-Nutzung in der Forschung und in SOTA-Systemen funktionieren, wo wir stehen, und wie wir die Connect-Phase auf Weltklasse-Niveau bringen.

---

## Leitbild: Widersprüche sichtbar, Entitäten nutzbar, klare Hypothesen für Verify und Synthesize

Die **Connect-Phase** soll die Ergebnisse von Explore und Focus **verbinden**: Sie macht Widersprüche zwischen Quellen explizit, extrahiert Entitäten und Beziehungen in einen nutzbaren Graph, und formuliert testbare Hypothesen sowie eine klare Thesis. So bereitet Connect **Verify** (Priorisierung welcher Claims/Thesen zu prüfen sind) und **Synthesize** (narrative Struktur, Position A vs B, Evidenz-Basis) vor.

Ziel ist nicht nur „irgendwelche“ Widersprüche und Hypothesen zu erzeugen, sondern:

- **Widersprüche**, die in Verify gezielt geprüft und in Synthesize als „Contradictions & Open Questions“ sichtbar werden.
- **Entitäten und Beziehungen**, die in Verify (Claim-Entity-Zuordnung) und Synthesize (Struktur, Narrative) genutzt werden.
- **Hypothesen und Thesis**, die Verify steuern (welche Claims stützen/widerlegen die Thesis?) und Synthesize als roten Faden liefern.

Die Architektur soll diese Artefakte **wirklich durch die Pipeline durchreichen** und in nachgelagerten Phasen genutzt werden — nicht nur erzeugen und ablegen.

---

## Teil A: SOTA und Forschung (Kernideen)

### A.1 Contradiction Detection

| Ansatz | Kernidee | Relevanz für Connect |
|--------|----------|------------------------|
| **Claim-first** | Zuerst Claims pro Dokument/Finding extrahieren, dann Paarvergleich (entailment/contradiction/neutral). | Weniger Halluzination; Nachvollziehbarkeit (Claim → Quelle). |
| **Multi-Document Reasoning** | Stance/Entailment über mehrere Dokumente; source-level disagreement. | Passt zu „source_a vs source_b“; kann zu strukturierten Disagreement-Reports erweitert werden. |
| **Contradiction-to-Consensus** | Evidence für Original- und Negated-Claim; Quellen-Disagreement analysieren. | Verbesserte Transparenz; Widersprüche als „wo Experten uneins sind“. |
| **RAFTS / Contrastive Arguments** | Supporting und refuting Arguments aus Evidence erzeugen; kleinere LLMs mit strukturierter Synthese. | Kontrastive Hypothesen (Position A vs B) statt nur einer Thesis. |

Aktuell: Ein Monolith-LLM-Call über alle Findings; keine Claim-Extraktion, keine zweistufige Verifikation.

### A.2 Hypothesis Generation

| Ansatz | Kernidee | Relevanz für Connect |
|--------|----------|------------------------|
| **Evidence-Graph-basiert** | Claims und Conclusions als Knoten; Kanten = unterstützt/widerspricht. Hypothesen als Pfade oder Cluster. | Nutzung des Entity/Relation-Graphen und von Widersprüchen. |
| **Multi-Hypothesis** | Mehrere konkurrierende Hypothesen mit Gewichten; explizite Unsicherheit. | thesis.json als Set (current + alternatives + uncertainty). |
| **Claim–Conclusion-Strukturen** | Strukturierte Ableitung von Conclusion aus Claims; NLI/Entailment. | Hypothesen mit expliziten evidence_summary → Claim-Mapping für Verify. |

Aktuell: Ein LLM-Call (stärkeres Modell für Hypothesen); keine Nutzung von Graph oder Widersprüchen; nur erste Hypothese wird Thesis.

### A.3 Knowledge Graph für Research

| Ansatz | Kernidee | Relevanz für Connect |
|--------|----------|------------------------|
| **GraphRAG / Community Summaries** | Communities im Graphen; hierarchische Summaries; Abruf über Summary + Detail. | Entity-Graph pro Projekt; optional Community-Cluster für Synthesize-Abschnitte. |
| **Entity-Centric Verify** | Claims nach Entitäten gruppieren; Verifikation entlang „welche Claims betreffen Entity X?“ | Verify priorisiert Claims, die Thesis-Entitäten betreffen; bessere Fokussierung. |
| **Narrative entlang Graph** | Synthese-Struktur folgt Entitäten und Relationen (Wer, Was, Beziehung). | Synthesize nutzt get_entities/get_entity_relations für Struktur und Evidenz-Anker. |

Aktuell: Graph wird in Connect erzeugt und in Memory geschrieben; **kein** Standard-Schritt in Verify oder Synthesize liest ihn.

### A.4 Claim–Counterclaim-Strukturen

- **Strukturierte Repräsentation:** claim, supporting_sources, refuting_sources, summary; Verknüpfung zu findings/claims für Verify.  
- **Synthesize:** „Position A vs Position B“-Abschnitte mit klarer Zuordnung zu Quellen; bereits in SYNTHESIZE_PHASE_DEEP_DIVE erwähnt, aber Connect liefert dafür nur flache contradictions (claim, source_a, source_b, summary).

---

## Teil B: Ist-Zustand (Brücke zum Code)

- **Contradiction Detection:** Ein LLM-Call in research_reason.py; Ausgabe contradictions.json. Keine Claim-Extraktion; keine Nutzung in hypothesis_formation; Verify liest contradictions nicht.
- **Hypothesis Formation:** Ein LLM-Call (stärkeres Modell); Ausgabe hypotheses.json; nur erste Hypothese → thesis.json. Keine Kopplung an Widersprüche oder Graph.
- **Entity/Graph:** research_entity_extract.py schreibt in Memory (entities, entity_relations, entity_mentions). Kein Export als Projekt-Artefakt; Verify/Synthesize nutzen den Graph nicht.
- **thesis.json:** Wird in Synthesize gelesen; Verify nutzt thesis nicht für Claim-Priorisierung oder Fokus.
- **Reihenfolge:** Entity Extract → Contradiction Detection → Hypothesis Formation → thesis-Update → advance_phase verify. Keine Datenflüsse zwischen diesen Schritten außer „erste Hypothese → thesis“.

---

## Teil C: Ziele (Weltklasse SOTA/Novel)

- **Widersprüche nutzbar:** Contradictions in Verify einbeziehen (Quellen der Widersprüche priorisieren, Stance prüfen); in Synthesize klar „Position A vs B“ mit Quellenbezug.
- **Graph durchgängig:** Entity-Graph in Verify (Claim-Entity-Zuordnung, Priorisierung) und Synthesize (Struktur, Narrative) nutzen; optional Export connect/entity_graph.json für UI und Reproduzierbarkeit.
- **Hypothesen und Thesis verbunden:** Widersprüche als Input für hypothesis_formation (kontrastive oder vorsichtige Formulierung); thesis.json mit current + alternatives + optional uncertainty; Verify priorisiert Claims, die Thesis stützen/widerlegen.
- **Strukturierte Contradiction Detection:** Zwei Stufen (Claim-Extraktion, dann Paarvergleich) oder klare Claim–Counterclaim-Struktur für bessere Nachvollziehbarkeit und weniger Halluzination.
- **Robustheit:** Connect-Fehler (z. B. entity_extract) nicht still verschlucken; Fehlerstatus in project oder Artefakt, advance_phase nur bei konsistentem Zustand.

---

## Teil D: Phasierter Plan (konkret umsetzbar)

### Phase 1: Verify und Synthesize nutzen Connect-Output (Sofortnutzen)

**Ziel:** thesis.json und contradictions.json werden in Verify und (weiterhin) in Synthesize genutzt.

- **Code:**  
  - research_verify.py: Bei claim_verification (und ggf. source_reliability) project thesis.json und contradictions.json einlesen. Thesis-relevante Claims priorisieren (z. B. Keywords/Entities aus thesis.current); Quellen, die in contradictions vorkommen, in source_reliability oder Metadaten markieren.  
  - Synthesize nutzt bereits contradictions und thesis; prüfen, ob hypotheses.json direkt nützlich ist (z. B. „Alternative Hypothesen“-Abschnitt) und optional einbinden.
- **Schema:** Keine Schema-Änderung; nur Nutzung bestehender Dateien.
- **Abnahme:** Verify-Priorisierung oder -Metadaten zeigen Nutzung von thesis/contradictions; Synthesize-Report referenziert Widersprüche und Thesis konsistent.
- **Risiko:** Niedrig.

---

### Phase 2: Entity-Graph in Verify und Synthesize (Graph durchgängig)

**Ziel:** Nachgelagerte Phasen lesen den in Connect erzeugten Graph.

- **Code:**  
  - research_verify.py: get_entities(project_id=…), get_entity_relations(project_id=…) aus Memory; Claims (oder Finding-Auszüge) nach erwähnten Entitäten gruppieren oder priorisieren (z. B. Claims, die Thesis-Entitäten erwähnen, zuerst).  
  - research_synthesize.py: Vor oder während Clustering/Outline get_entities/get_entity_relations aufrufen; optional Abschnitte oder Narrative entlang zentraler Entitäten/Relationen strukturieren.  
  - Optional: connect.sh oder research_entity_extract.py schreibt `research/<project_id>/connect/entity_graph.json` (Entities + Relations für Projekt) für UI und Reproduzierbarkeit.
- **Schema:** Optional neues Artefakt connect/entity_graph.json; Memory-Schema unverändert.
- **Abnahme:** Verify-Log oder -Artefakt zeigt Entity-Nutzung; Synthesize-Report nutzt Entitäten/Relationen sichtbar (z. B. in Abschnittsstruktur oder Referenzen).
- **Risiko:** Niedrig bis mittel (Abhängigkeit von Memory in Verify/Synthesize-Umgebung).

---

### Phase 3: Contradiction-aware Hypothesis und thesis als Set (SOTA Hypothesis)

**Ziel:** Widersprüche fließen in Hypothesenbildung; thesis.json enthält Alternativen und optional Unsicherheit.

- **Code:**  
  - research_reason.py hypothesis_formation: Optional contradictions (aus proj_path/contradictions.json) als zusätzlichen User-Input übergeben; Prompt erweitern („Consider these contradictions; form 1–3 hypotheses, possibly contrasting positions A vs B.“).  
  - connect.sh: Statt nur erste Hypothese in thesis zu schreiben, thesis-Struktur erweitern, z. B. `current`, `alternatives` (Liste weiterer statements mit confidence), `evidence`, optional `uncertainty` oder `contradiction_summary`.  
  - research_synthesize.py: Bei alternatives vorhanden „Alternative Hypothesen“ oder „Position A vs B“ nutzen; bereits vorhandene Contradictions-Sektion beibehalten.
- **Schema:** thesis.json erweitert um `alternatives`: `[{statement, confidence}]`, optional `uncertainty`, `contradiction_summary`.
- **Abnahme:** Nach Connect mit Widersprüchen enthält thesis alternatives oder vorsichtigere Formulierung; Synthesize zeigt Alternativen wo sinnvoll.
- **Risiko:** Mittel (Rückwärtskompatibilität thesis.json; bestehende Leser müssen alternatives optional handhaben).

---

### Phase 4: Strukturierte Contradiction Detection (SOTA Contradiction)

**Ziel:** Zwei Stufen: Claim-Extraktion pro Finding, dann Paarvergleich; bessere Nachvollziehbarkeit.

- **Code:**  
  - research_reason.py: Neuer Modus oder erweiterter Ablauf: (1) Claim-Extraktion pro Finding (LLM oder regelbasiert) → Liste claims mit finding_id/source; (2) Paarvergleich (LLM oder NLI-Modell): welche Claim-Paare sind contradiction/entailment/neutral.  
  - contradictions.json-Struktur erweitern: z. B. claim_a_id, claim_b_id, claim_a_text, claim_b_text, source_a, source_b, relation (contradiction|entailment|neutral), summary.  
  - Optional: Verknüpfung zu claim_ledger/Verify (claim_id), damit Verify gezielt diese Claims prüft.
- **Schema:** contradictions.json erweitert; optional claim_id-Felder für Verify-Anbindung.
- **Abnahme:** Widersprüche haben explizite Claim-Texte und Quellen; Verify kann sie gezielt adressieren.
- **Risiko:** Mittel (mehr LLM-Calls oder NLI-Infra; Laufzeit).

---

### Phase 5: Robustheit und Observability (Betriebssicherheit)

**Ziel:** Connect-Fehler sichtbar; kein stilles Verschlucken.

- **Code:**  
  - connect.sh: research_entity_extract ohne `|| true` oder bei Fehler Exit-Code in Artefakt schreiben und advance_phase nur bei Erfolg (oder explizitem „degraded“-Modus).  
  - Optional: project.json oder connect/connect_status.json mit Feldern wie entity_extract_ok, contradiction_ok, hypothesis_ok, thesis_updated.  
  - Logging/Progress: Klare Steps („Building knowledge graph“, „Finding cross-references“, „Forming hypotheses“, „Updating thesis“) beibehalten; bei Fehler Schritt markieren.
- **Abnahme:** Bei entity_extract-Fehler bricht Connect nachvollziehbar ab oder setzt Status; Pipeline kann reagieren (Retry, Skip, Alert).
- **Risiko:** Niedrig.

---

### Phase 6: Novel — Graph-basierte Hypothesen und Claim–Entity-Verknüpfung

**Ziel:** Hypothesen oder Thesis explizit aus Graph ableiten (z. B. „zentrale Entitäten und ihre Relationen“); Claims in Verify mit Entity-IDs verknüpfen.

- **Code:**  
  - research_reason.py oder neues Modul: Aus get_entities/get_entity_relations(project_id) „Kern-Entitäten“ und „Kern-Relationen“ extrahieren; LLM-Hypothesenbildung erhält diesen Graph als Input („Given this entity graph, form hypotheses that explain or use these relations.“).  
  - research_verify.py: Bei Claim-Verifikation optional entity_ids speichern (welche Entitäten der Claim betrifft); für Aggregation „Verifikation pro Entität“ oder „Evidenz pro Relation“.  
- **Schema:** Optional claim_ledger oder Verify-Artefakt um entity_ids pro Claim; thesis um entity_ids (welche Entitäten die Thesis betrifft).
- **Abnahme:** Mindestens eine Hypothese/Thesis referenziert explizit Entitäten aus dem Graph; Verify-Artefakt enthält Entity-Bezug wo sinnvoll.
- **Risiko:** Mittel (Novel; schrittweise einführen).

---

## Teil D2: Erfolgsbedingungen (optional)

| Nr. | Bedingung | Wo im Plan | Umgesetzt |
|-----|-----------|------------|-----------|
| 1 | Verify nutzt thesis und contradictions für Priorisierung oder Metadaten | Phase 1 | Ja: connect_context, Priorisierung, in_contradiction in source_reliability + claim_ledger |
| 2 | Synthesize nutzt weiterhin contradictions und thesis; optional hypotheses/alternatives | Phase 1, 3 | Ja: thesis + alternatives + contradiction_summary in Conclusions |
| 3 | Entity-Graph wird in Verify und/oder Synthesize gelesen (Memory oder Export) | Phase 2 | Ja: connect/entity_graph.json; Verify Priorisierung, Synthesize entity_context im Outline |
| 4 | thesis.json enthält mindestens current + evidence; optional alternatives | Phase 3 | Ja: current, evidence, alternatives, contradiction_summary |
| 5 | Contradictions haben nachvollziehbare Claim-/Quellen-Struktur | Phase 4 | Ja: Zwei Stufen (Claim-Extraktion pro Finding, Paarvergleich); claim_a_id, claim_b_id, claim_a_text, claim_b_text, relation; RESEARCH_CONTRADICTION_STRUCTURED=1 (default) |
| 6 | Connect-Fehler führen nicht zu stillem „leeren“ Graph; Status oder Abbruch | Phase 5 | Ja: entity_extract ohne \|\| true; connect_status zu Start (entity_extract_ok=false) und vor advance |
| 7 | Graph-basierte Hypothesen; entity_ids in thesis/claim_ledger | Phase 6 | Ja: hypothesis_formation liest entity_graph.json; thesis.entity_ids; claim_ledger.entity_ids pro Claim |

---

## Teil E: Priorisierung und Metriken

### Priorität (Reihenfolge)

| Phase | Inhalt | Aufwand | Priorität |
|-------|--------|---------|-----------|
| 1 | Verify/Synthesize nutzen Connect-Output | 1–2 Tage | **Hoch** |
| 2 | Entity-Graph in Verify/Synthesize | 1–2 Tage | **Hoch** |
| 3 | Contradiction-aware Hypothesis, thesis als Set | 1–2 Tage | **Hoch** |
| 4 | Strukturierte Contradiction Detection | 2–3 Tage | Mittel |
| 5 | Robustheit und Observability | 0,5–1 Tag | Mittel |
| 6 | Novel: Graph-basierte Hypothesen, Claim–Entity | 2–3 Tage | Nach SOTA |

Empfohlene Reihenfolge: **1 → 2 → 3** (sofortiger Nutzen + Graph + bessere Thesis), dann 5 (Robustheit), dann 4 und 6.

### Metriken (Erfolg messen)

- **Nutzung Connect in Verify:** Anteil Verify-Runs, die thesis/contradictions einlesen; Anteil Claims, die als „thesis-relevant“ oder „contradiction-related“ markiert sind.
- **Nutzung Graph:** Verify/Synthesize rufen get_entities/get_entity_relations auf; optional: Anzahl Abschnitte oder Claims, die Entitäten referenzieren.
- **Qualität Hypothesen/Thesis:** Manuell oder über Critic: Sind alternatives und Widersprüche in Synthesize-Report sichtbar und kohärent?
- **Robustheit:** Keine stillen Fehler in entity_extract; Connect-Status in project oder Artefakt bei Fehler gesetzt.

---

Dieser Plan baut auf [CONNECT_PHASE_DEEP_DIVE.md](CONNECT_PHASE_DEEP_DIVE.md) auf und soll bei Änderungen an der Connect-Phase, research_reason.py, research_entity_extract.py und an UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK mitgeführt werden.
