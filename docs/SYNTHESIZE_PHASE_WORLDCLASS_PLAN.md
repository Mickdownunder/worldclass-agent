# Synthesize-Phase — Plan: Weltklasse SOTA/Novel

Wie SOTA-Systeme und Forschung evidenzbasierte Reports erzeugen, wo wir stehen, und wie wir die Synthesize-Phase auf Weltklasse-Niveau bringen. Baut auf [SYNTHESIZE_PHASE_DEEP_DIVE.md](SYNTHESIZE_PHASE_DEEP_DIVE.md) auf.

---

## Leitbild: Evidenzbasierter, nachvollziehbarer, research-firm-grade Report

Die Synthesize-Phase soll einen **professionellen Forschungsbericht** (5K–15K Wörter) liefern, der:

- **Evidenzbasiert** ist: Jede wesentliche Behauptung ist an den Claim-Ledger und an Quellen rückgebunden ([claim_ref: id@version], References, Claim Evidence Registry, Provenance).
- **Nachvollziehbar** ist: Leser und Audit können prüfen, welche Claims verifiziert/tentativ/unverifiziert sind und welche Quellen sie stützen.
- **Strukturiert und konsistent** ist: Klare Sections, Epistemic Language passend zum Verifikationsstatus, keine ungestützten „Fakten“, keine TBD-Matrizen.
- **Qualitätsgeprüft** ist: Critic bewertet Coverage, Tiefe, Genauigkeit, Zitation; Revision-Runden verbessern den Report bis zum Schwellwert oder Max-Runden.

Damit wird die vorhandene Pipeline (Verify → Claim Ledger → Synthesize → Critic) nicht ersetzt, sondern **verstärkt**: bessere Nutzung der Verify-Artefakte, stärkere Factuality/Attribution, konfigurierbare Struktur und messbare Qualität.

---

## Teil A: Wie SOTA-Systeme und Forschung es machen

### A.1 Multi-Document Summarization (MDS) mit Attribution

- **Kernidee:** Aus vielen Dokumenten eine kohärente Zusammenfassung erzeugen, mit **feingranularer Quellen-Zuordnung** (nicht nur „Dokument X“, sondern Span- oder Satz-Level).
- **„Attribute First, then Generate“ (ACL 2024):** Content Selection → Sentence Planning → Sequential Generation mit präziser Attribution; reduziert Verifikationszeit und Halluzination.
- **Was wir daraus nutzen:** Claim-Ledger und [claim_ref] sind ein Schritt; SOTA wäre **Span-Attribution** (welcher Satz welcher Finding/Quote entspricht) und strukturierte „supporting_evidence“ pro Absatz.

### A.2 Claim-driven Writing und Fact-Checking

- **MetaSumPerceiver (2024):** Claim-spezifische Summaries aus Multi-Doc-Evidenz für Fact-Checking; RL-basiertes Entailment-Objective; unterscheidet Truthfulness-Labels.
- **FactCG / HalluTree (2025):** Halluzinationserkennung durch Subclaim-Zerlegung (extractiv vs. inferentiell), Multi-Hop-Verifikation, Kontext-Graphen. Erklärbare Reasoning-Chains für komplexe Claims.
- **Was wir daraus nutzen:** Jede claim-artige Aussage im Report einem Claim oder „no claim“ zuordnen; optional **Post-Generation Factuality-Pass** (Abgleich Report-Sätze vs. Findings/Ledger); TENTATIVE/UNVERIFIED sprachlich strikt behandeln (bereits via Epistemic Reflect).

### A.3 RAG für Reports und Chain-of-Verification

- **RAG für lange Reports:** Retrieval der relevantesten Findings/Sources pro Section (nicht nur Sortierung nach Keyword); Re-Ranking nach Relevanz und Verifikationsstatus.
- **Chain-of-Verification (CoVe):** Nach dem Schreiben explizite Verifikationsschritte („Ist jede Zahl in den Quellen?“); Self-Correction vor Freigabe.
- **Was wir daraus nutzen:** **Semantische Relevanz** für Findings-Auswahl pro Section; optional **Factuality-Guard** als CoVe-ähnlicher Pass (Zahlen/Zitate gegen Ledger/Findings prüfen).

### A.4 Strukturierte Report-Generierung

- **Strukturierte Outputs:** Report als Schema (z. B. JSON: sections[], pro section headline, key_points[], claim_refs[], confidence). Ermöglicht Validierung, bessere Contract-Checks und konsistente Nachbearbeitung.
- **Konfigurierbare Templates:** Playbook- oder Domain-spezifische Section-Typen (Executive Summary, Market Size, Risks, Historical Precedent); LLM füllt Inhalte innerhalb des Schemas.
- **Was wir daraus nutzen:** **Konfigurierbare Report-Struktur** aus Playbook/Config; optional **strukturierte Section-Outputs** (z. B. claim_refs pro Absatz) für bessere Provenance und Contract.

---

## Teil B: Wo wir heute stehen (Brücke zum Code)

- **Stärken:** Multi-Pass-Synthese (Clustering → Outline → Section-by-Section); Claim-Ledger durchgängig genutzt ([claim_ref], Epistemic Profile, Verification Summary, Claim Evidence Registry, Provenance); Epistemic Reflect passt Sprache an Tier an; Synthesis Contract (claim_ref pro claim-artiger Satz bei nicht leerem Ledger); Critic + Revision-Runden; References nur aus zitierten Quellen; Discovery-Mode und Frontier-Mode unterstützt.
- **Lücken (vgl. Deep Dive):** Findings-Auswahl nur **keyword**-basiert; keine semantische Relevanz. Verify-Artefakte (critique-Vorgänger, evidence_gate-Metriken) fließen nicht in Section-Guidance ein. Keine **Span-Attribution** (nur Claim→Source, nicht Satz→Span). Kein **Factuality-Guard** nach Generierung. Report-Struktur nur über Playbook-Instructions im Outline, nicht als festes konfigurierbares Schema. Weaknesses aus Critic werden in Revise nicht strukturiert pro Section zurückgespielt.

---

## Teil C: Ziele (Weltklasse SOTA/Novel)

1. **Claim–Evidence voll ausreizen:** Claim-Ledger und Verify-Artefakte konsistent nutzen; optional Span- oder Absatz-Level-Attribution; jede Behauptung tracebar.
2. **Factuality und Attribution:** Post-Generation-Check (Zahlen, Zitate vs. Findings/Ledger); sprachliche Konsistenz mit TENTATIVE/UNVERIFIED (bereits angelegt, verfeinern).
3. **Bessere Eingangsselektion:** Semantische (oder Hybrid-) Relevanz für Findings zur Frage; Relevanz/Verifikationsstatus in Section-Input gewichten.
4. **Konfigurierbare Report-Struktur:** Playbook/Config definiert Section-Typen oder feste Gliederung; Outline und Sections folgen diesem Schema.
5. **Critic- und Verify-Rückkopplung:** Weaknesses und Gate-Metriken strukturiert in Revise und ggf. in Epistemic Profile/Section-Guidance nutzen.
6. **Strukturierte Outputs (optional):** Sections mit maschinell auswertbarem claim_refs-/evidence-Schema für bessere Validierung und Contract.

---

## Teil D: Phasierter Plan (konkret umsetzbar)

### Phase 1: Claim-Ledger und Provenance konsistent nutzen (Grundlage)

**Ziel:** Sicherstellen, dass alle Verify-Artefakte, die Synthesize erreichen, einheitlich gelesen und genutzt werden; keine doppelten Pfade; Provenance und Claim Evidence Registry immer vollständig.

- **Code/Schema:**  
  - `get_claims_for_synthesis` bleibt Quelle der Wahrheit (AEM ledger.jsonl vor verify/claim_ledger.json).  
  - Sicherstellen, dass `source_finding_ids` und `supporting_source_ids` in allen Consumern (Registry, Provenance, claim_evidence_map) genutzt werden.  
  - Optional: Einheitliches Lesen von `verify/source_reliability.json` und Kennzeichnung [LOW RELIABILITY] in allen Section-Excerpts (bereits vorhanden; prüfen ob lückenlos).
- **Abnahme:** Report enthält für jeden Claim in der Registry mindestens eine Source; Provenance listet für jeden Claim die zugehörigen Finding-IDs; keine Referenz auf fehlende Ledger-Einträge.
- **Risiko:** Niedrig.

---

### Phase 2: Semantische Relevanz und bessere Findings-Nutzung

**Ziel:** Findings für Clustering und Section-Input nicht nur nach Keyword-Relevanz sortieren; optional semantische (Embedding-) oder Hybrid-Relevanz; Verify-Status in Gewichtung einbeziehen.

- **Code/Config:**  
  - In `research_synthesize.py`: Optionale Relevanz-Sortierung mit Embedding (wenn RESEARCH_SYNTHESIS_SEMANTIC=1 und Embedding-Infra vorhanden): Frage embedden, Findings nach Cosine-Similarity oder Hybrid-Score (Keyword + Semantic) sortieren.  
  - Fallback: Weiterhin `_relevance_score` (Keyword).  
  - Optional: Bei nicht leerem Claim-Ledger Findings, die in `supporting_source_ids` vorkommen, in Section-Input priorisieren (höheres Gewicht oder zuerst anbieten).
- **Schema:** Keine Änderung an Findings-Schema; optional neues Feld `relevance_to_question` aus Synthesize-Schritt (nur für Logging/Observability).
- **Abnahme:** Bei aktivierter semantischer Relevanz: bessere Abdeckung der Frage in Top-80-Findings (subjektiv oder per Stichprobe); keine Regression bei Keyword-Only.
- **Risiko:** Mittel (Embedding-Infra, Laufzeit). Entschärfung: Feature-Flag, Fallback Keyword.

---

### Phase 3: Factuality-Guard und bessere Epistemic-Konsistenz

**Ziel:** Nach Section- oder Report-Generierung automatisch prüfen, ob Zahlen, Daten, Zitate in den Findings/Ledger vorkommen; Verstöße flaggen oder qualifizieren. Epistemic Reflect und TENTATIVE-Labels durchgängig.

- **Code:**  
  - **Factuality-Guard (optional):** Ein Pass über Report-Absätze: Extraktion von Zahlen, Daten, wörtlichen Zitaten; Abgleich gegen Findings-Excerpts und Claim-Texte; Ausgabe: Liste „unsupported_span“ oder automatische Qualifier („laut Quellen“, „unverifiziert“). Kann zunächst nur loggen oder in synthesis_contract_status.json aufnehmen.  
  - **TENTATIVE/UNVERIFIED:** Bereits in validate_synthesis_contract (tentative_labels_ok); sicherstellen, dass Epistemic Reflect und Prompts in allen Modi (standard/frontier/discovery) einheitlich sind.
- **Abnahme:** Bei aktiviertem Guard: Keine harten „Fakten“-Behauptungen ohne Treffer in Findings/Ledger (oder explizit als „unverified“ markiert). Tentative Claims im Report mit passender Sprache.
- **Risiko:** Mittel (False Positives bei Guard). Entschärfung: Guard zunächst im observe-Modus (nur Metriken, kein Block).

---

### Phase 4: Konfigurierbare Report-Struktur und Critic-Rückkopplung

**Ziel:** Report-Struktur aus Playbook oder Projekt-Config (feste Section-Typen); Weaknesses aus Critic strukturiert in Revise-Runde einbeziehen.

- **Code/Config:**  
  - **Struktur:** Playbook oder `project.json` config z. B. `report_sections: ["Executive Summary", "Market Size", "Risiken", "Historischer Präzedenz", "Conclusions"]`. Outline-LLM liefert nur Titel innerhalb dieser Liste oder ergänzt fehlende; Section-Schleife folgt dieser Reihenfolge (Clustering-Ergebnis auf Section-Typen mappen).  
  - **Critic-Rückkopplung:** In `research_critic.py` Revise-Modus: Weaknesses als strukturierte Liste (z. B. „Section 3: fehlende Tiefe“); Revise-Prompt erhält diese Liste und fordert gezielte Verbesserungen in den genannten Sections.
- **Abnahme:** Mit gesetzter report_sections erscheinen die gewünschten Blöcke in der Reihenfolge; Revise adressiert mindestens eine genannte Weakness gezielt.
- **Risiko:** Niedrig bis mittel (Playbook-Schema erweitern, Backward-Kompatibilität).

---

### Phase 5 (optional): Strukturierte Section-Outputs und Span-Attribution

**Ziel:** Pro Section optional strukturierter Output (z. B. JSON mit headline, key_points[], claim_refs[], confidence); daraus Markdown rendern. Optional Span-Attribution (Satz → finding_id/quote) für bessere Provenance.

- **Code:**  
  - Section-Prompt erweitern: „Return JSON: { \"body_md\": \"...\", \"claim_refs_used\": [\"cl_1@1\", ...], \"key_points\": [...] }“; Parser rendert body_md; claim_refs_used in Provenance/Contract nutzen.  
  - Optional: „supporting_evidence“ pro Absatz (finding_id + optional span) aus LLM oder nachträglich per Abgleich.
- **Abnahme:** Report bleibt lesbar (Markdown); Zusatzdaten für Audit und Contract verfügbar.
- **Risiko:** Mittel (LLM-Compliance mit Schema, Parsing-Robustheit).

---

## Teil D2: Erfolgsbedingungen (optional)

Unter welchen Bedingungen gilt die Synthesize-Phase als „spezifiziert“ und qualitätssicher:

| Nr. | Bedingung | Wo im Plan / Code |
|-----|-----------|-------------------|
| 1 | Claim-Ledger ist einzige Quelle für Claims in Report; jeder claim-artige Satz trägt [claim_ref: id@version] wenn Ledger nicht leer. | Phase 1; validate_synthesis_contract, Prompts |
| 2 | References und Claim Evidence Registry enthalten nur Quellen aus Ledger (supporting_source_ids). | research-cycle.sh Post-Processing, Phase 1 |
| 3 | Epistemic Profile und Epistemic Reflect sind in allen Modi aktiv; TENTATIVE/UNVERIFIED führen zu vorsichtiger Sprache. | research_synthesize.py, Phase 3 |
| 4 | Critic-Score und Revision-Runden sind konfigurierbar (Threshold, Max-Runden); Mindestens eine Revision bei kritischen Weaknesses (unvollständig, bricht ab). | research-cycle.sh, RESEARCH_MEMORY_CRITIC_THRESHOLD, RESEARCH_MEMORY_REVISE_ROUNDS |
| 5 | Optional: Factuality-Guard oder CoVe-Pass liefert Metriken (unsupported_count); bei enforce-Modus kann Synthese blockiert werden. | Phase 3 |
| 6 | Report-Struktur konfigurierbar (Playbook/Config); Outline und Sections respektieren sie. | Phase 4 |

---

## Teil E: Priorisierung und Metriken

### Priorisierung

| Phase | Inhalt | Aufwand | Priorität |
|-------|--------|---------|-----------|
| 1 | Claim-Ledger & Provenance konsistent | 0,5–1 Tag | **Hoch** (Grundlage) |
| 2 | Semantische Relevanz, bessere Findings-Nutzung | 2–3 Tage | **Hoch** |
| 3 | Factuality-Guard, Epistemic-Konsistenz | 2–3 Tage | **Hoch** |
| 4 | Konfigurierbare Struktur, Critic-Rückkopplung | 1–2 Tage | Mittel |
| 5 | Strukturierte Outputs, Span-Attribution | 2–4 Tage | Nach SOTA-Stand |

Empfohlene Reihenfolge: **1 → 2 → 3** (Kern-SOTA), dann 4, dann 5.

### Metriken (Erfolg messen)

- **Provenance-Vollständigkeit:** Anteil Claims im Ledger mit mindestens einem Eintrag in Provenance und in Claim Evidence Registry; Ziel 100 %.
- **Contract-Validität:** Anteil Reports mit `synthesis_contract_status.valid === true`; bei enforce/strict Ziel 100 %.
- **Critic-Score:** Durchschnitt critic_score nach letzter Revision; Ziel ≥ 0,6 (vgl. RESEARCH_QUALITY_SLO).
- **Revision-Runden:** Durchschnittliche Anzahl Revisionen bis Pass; Reduktion bei besserer Erstqualität (bessere Findings-Nutzung, Epistemic Reflect) als Erfolg.
- **Factuality (wenn Guard aktiv):** Anzahl gemeldeter unsupported_spans pro Report; Trend über Zeit; optional Block-Rate bei enforce.

---

---

## Teil F: Vollständiger Umsetzungsplan — alle Zusammenhänge

Damit bei der Umsetzung **jede Funktion, jede Route, jedes Artefakt** berücksichtigt wird, sind hier alle Abhängigkeiten und Berührungspunkte aufgelistet.

### F.1 Shell-Ablauf (research-cycle.sh, case `synthesize`)

| Schritt | Aktion | Abhängigkeiten |
|--------|--------|----------------|
| 1 | `progress_start "synthesize"`, `progress_step "Generating outline"` | `tools/research_progress.py` (step), `project_id` |
| 2 | `timeout 1800 python3 research_synthesize.py $PROJECT_ID > $ART/report.md` | `OPERATOR_ROOT`, `ART=$PWD/artifacts`, `PROJ_DIR`, `findings/`, `sources/`, `verify/`, `project.json`, `claims/ledger.jsonl` oder `verify/claim_ledger.json`, `thesis.json`, `contradictions.json`, `discovery_analysis.json`, Playbooks, `RESEARCH_SYNTHESIS_MODEL` |
| 3 | Inline-Python: Post-Processing | `get_claims_for_synthesis(proj_dir)`, `apply_verified_tags_to_report(report, claim_ledger)` aus `research_verify.py`, `findings/*.json`, `sources/*.json` für ref_map; Schreiben: `report.md`, `reports/report_<ts>.md`, `reports/claim_evidence_map_<ts>.json`, `verify/claim_evidence_map_latest.json`, `reports/manifest.json` |
| 4 | Critic: `research_critic.py $PROJECT_ID critique $ART` | Liest Report aus `reports/` (neueste report_*.md) oder `$ART/report.md`; schreibt `$ART/critique.json`; kopiert nach `verify/critique.json` |
| 5 | CRITIC_THRESHOLD, MAX_REVISE_ROUNDS | `RESEARCH_CRITIC_THRESHOLD`, `RESEARCH_MEMORY_CRITIC_THRESHOLD` (aus memory_strategy.json), `RESEARCH_MEMORY_REVISE_ROUNDS`; frontier → CRITIC_THRESHOLD=0.50 |
| 6 | FORCE_ONE_REVISION | Keywords in `critique.json` weaknesses: „unvollständig“, „bricht ab“, „fehlt“ |
| 7 | Revise-Loop | `research_critic.py revise $ART` → liest `verify/critique.json` oder `$ART/critique.json`, `_load_report(proj_path, art_path)`; stdout → `revised_report.md`; dann `report.md` überschreiben, `reports/report_<ts>_revised<N>.md` speichern; erneut critique |
| 8 | Bei Fail: QF_FAIL, research_abort_report, OUTCOME_RECORD, distiller, utility_update, persist_v2_episode | `project.json` status/phase/quality_gate; `research_abort_report.py` (verify/claim_ledger.json, source_reliability, findings, project); Memory.record_project_outcome |
| 9 | Bei Pass: QG (quality_gate in project.json), MANIFEST_UPDATE (quality_score in manifest), PDF, embed, cross_domain, advance_phase done, Brain-Reflect, distiller, utility_update, persist_v2_episode | `research_pdf_report.py`, `research_embed.py`, `research_cross_domain.py`, `research_advance_phase.py` |

### F.2 research_synthesize.py — alle Funktionen und Lesepfade

| Funktion / Konstante | Zweck | Liest / Schreibt |
|----------------------|--------|-------------------|
| `_model()` | RESEARCH_SYNTHESIS_MODEL | env |
| `_relevance_score(finding, question)` | Keyword-Relevanz | — |
| `_load_findings(proj_path, max_items, question)` | Findings laden, sortieren, kappen | `findings/*.json` |
| `_load_sources(proj_path)` | Source-Metadaten | `sources/*.json` (ohne *_content) |
| `_load_source_content(proj_path, url, max_chars)` | Volltext einer Quelle | `sources/<key>_content.json` |
| `_cluster_findings(...)` | LLM-Clustering 3–7 Cluster | llm_call, project_id (Budget) |
| `_outline_sections(...)` | LLM Section-Titel | playbook_instructions, llm_call |
| `_build_claim_source_registry(...)` | Tabelle Claim→Source→URL→Date→Tier | claim_ledger, sources, ref_list |
| `_build_provenance_appendix(claim_ledger)` | Claim ID → source_finding_ids | claim_ledger |
| `_build_ref_map(findings, claim_ledger)` | url→ref_num, ref_list (url, title) | findings, claim_ledger |
| `_detect_gaps(...)` | WARP Gap-Detection (optional) | llm_call |
| `_claim_ledger_block(claim_ledger)` | Textblock für Section-Prompt | claim_ledger |
| `_extract_section_key_points(body)` | Anti-Repetition | — |
| `_extract_used_claim_refs(text)` | claim_refs aus Text | — |
| `_epistemic_profile_from_ledger(claim_ledger)` | Tier-Zählung | claim_ledger |
| `_epistemic_reflect(body, claim_ledger, project_id)` | LLM Sprachanpassung | llm_call (gemini-2.5-flash) |
| `_synthesize_section(...)` | Eine Section schreiben | ref_map, findings, claim_ledger, rel_sources, proj_path (source content), llm_call |
| `_synthesize_research_situation_map(...)` | LLM Situation Map | claim_ledger, findings, llm_call |
| `_synthesize_decision_matrix(...)` | LLM Decision Synthesis | claim_ledger, thesis, tipping, llm_call |
| `_synthesize_tipping_conditions(...)` | LLM Tipping Table | claim_ledger, llm_call |
| `_synthesize_scenario_matrix(...)` | LLM Scenario Matrix | claim_ledger, thesis, tipping, llm_call |
| `_synthesize_exec_summary(...)` | LLM Executive Brief | full_report_body, question, epistemic_profile, llm_call |
| `_synthesize_conclusions_next_steps(...)` | LLM Conclusions + Next Steps | thesis, contradictions, discovery_brief, llm_call |
| `_evidence_summary_line(claim_ledger, research_mode)` | Eine Zeile Evidence Summary | claim_ledger |
| `_key_numbers(findings, claim_ledger, project_id)` | LLM Key Numbers | findings, claim_ledger, llm_call |
| `_deduplicate_sections(parts)` | Satz-Dedup über Sections | — |
| `extract_claim_refs_from_report(report)` | Alle claim_ref aus Report | — |
| `_build_valid_claim_ref_set(claim_ledger)` | Gültige id@version | claim_ledger |
| `validate_synthesis_contract(report, claim_ledger, mode)` | unknown_refs, unreferenced, tentative_labels_ok | claim_ledger, AEM_ENFORCEMENT_MODE |
| `_load_checkpoint` / `_save_checkpoint` / `_clear_checkpoint` | Section-Resume | `synthesize_checkpoint.json` |
| `run_synthesis(project_id)` | Hauptablauf | project_dir, load_project, get_claims_for_synthesis, verify/source_reliability.json, verify_dir, thesis.json, contradictions.json, discovery_analysis.json, playbooks; schreibt synthesis_contract_status.json |
| **research_synthesize_postprocess.py** | | |
| `_run(proj_dir, art_dir)` | Apply tags, Strip Refs, References aus claim_ledger, claim_evidence_map, manifest | get_claims_for_synthesis, apply_verified_tags_to_report; liest report aus art_dir/report.md oder neueste reports/report_*.md; schreibt reports/report_<ts>.md, claim_evidence_map_<ts>.json, verify/claim_evidence_map_latest.json, reports/manifest.json |

**Eingaben von run_synthesis (vollständig):**  
`project.json` (question, config.research_mode, config.playbook_id), `findings/*.json`, `sources/*.json`, `sources/*_content.json`, `get_claims_for_synthesis(proj_path)` → `claims/ledger.jsonl` oder `verify/claim_ledger.json`, `verify/source_reliability.json`, `verify/` (implizit für claim_ledger-Pfad), `thesis.json`, `contradictions.json`, `discovery_analysis.json`, Playbook `synthesis_instructions`, `OPERATOR_ROOT` (Playbook-Pfad), `RESEARCH_SYNTHESIS_MODEL`, `AEM_ENFORCEMENT_MODE`, `RESEARCH_WARP_DEEPEN` (optional WARP-Deepening).

### F.3 research_common.py — Synthesize-relevante Funktionen

| Funktion | Verwendung in Synthesize |
|----------|---------------------------|
| `project_dir(project_id)` | Proj-Pfad |
| `load_project(proj_path)` | question, config |
| `llm_call(model, system, user, project_id)` | Alle LLM-Calls in research_synthesize |
| `get_claims_for_synthesis(proj_path)` | Einzige Quelle Claim-Liste: zuerst `claims/ledger.jsonl`, sonst `verify/claim_ledger.json` → `data.claims` |

### F.4 research_verify.py — Synthesize-relevante Teile

| Funktion / Aufruf | Verwendung |
|-------------------|------------|
| `apply_verified_tags_to_report(report, claims)` | research_synthesize_postprocess.py (und früher research-cycle.sh Inline-Python): [VERIFIED]/[AUTHORITATIVE] Tags setzen/entfernen |
| `build_claim_ledger(proj_path, project)` | Wird in Verify gebaut; Ausgabe verify/claim_ledger.json; von get_claims_for_synthesis gelesen (wenn kein AEM ledger) |

### F.5 research_critic.py — Vollständig

| Funktion / Entry | Liest | Schreibt / Ausgabe |
|------------------|--------|---------------------|
| `_model()` | RESEARCH_CRITIQUE_MODEL | — |
| `_threshold()` | RESEARCH_CRITIC_THRESHOLD (default 0.50) | — |
| `_load_report(proj_path, art_path)` | `reports/report_*.md` (neueste nach mtime) oder `art_path/report.md` | — |
| `critique_report(proj_path, project, art_path, project_id)` | report, project.question, config.research_mode | JSON score, weaknesses, suggestions, pass, dimensions; audit_log(proj_path, "critic_evaluation", …) |
| `revise_report(proj_path, critique, art_path, project_id)` | _load_report, critique (weaknesses, suggestions) | Revidierter Markdown (stdout) |
| CLI `critique` | project_id, art_path (optional) | JSON stdout → $ART/critique.json |
| CLI `revise` | project_id, art_path; critique aus verify/critique.json oder $ART/critique.json | Markdown stdout → revised_report.md |

### F.6 research_pdf_report.py — Synthesize-Bezug

| Schritt | Liest | Anmerkung |
|--------|--------|-----------|
| `_load_latest_report_md(proj_dir)` | Neueste `reports/report_*.md` (nach mtime) | |
| project.json | proj_data | |
| claim_evidence | `verify/claim_evidence_map_latest.json` oder `verify/claim_ledger.json` → claims | |
| claim_verification | verify/claim_verification.json | |
| fact_check | verify/fact_check.json | |
| source_reliability | verify/source_reliability.json | |
| _build_references_html | findings, sources, claim_ledger (supporting_source_ids) | |

### F.7 research_abort_report.py — Bei Synthesize-Fail (Quality Gate)

| Liest | Schreibt |
|--------|----------|
| project.json, verify/evidence_gate, verify/source_reliability.json, verify/claim_ledger.json, sources/*.json, findings/*.json | reports/abort_report.md, audit_log |

### F.8 Conductor (research_conductor.py) — Synthesize-Pfad

| Wenn phase == synthesize | Aktion |
|---------------------------|--------|
| run_cycle | run_tool("research_synthesize.py", project_id) → stdout in proj/reports/report_<ts>.md; **run_tool("research_synthesize_postprocess.py", project_id)** (apply_verified_tags, References, claim_evidence_map, manifest); dann critique_report(proj, project, None, project_id) → verify/critique.json. |

**Umgesetzt:** Conductor ruft nach dem Schreiben des Reports dasselbe Post-Processing wie die Bash-Pipeline auf (`research_synthesize_postprocess.py`), sodass claim_evidence_map und manifest.json auch im Conductor-Pfad erzeugt werden.

### F.9 API-Routen und UI (alle Berührungspunkte)

| Route / Funktion | Liest | Rückgabe |
|------------------|--------|----------|
| GET /api/research/projects/[id]/report | getLatestReportMarkdown(id) | reports/manifest.json → is_final bzw. letzter Eintrag; Fallback: readdir + sort reverse; 404 wenn leer |
| GET /api/research/projects/[id]/report/pdf | PDF-Generierung oder Redirect | reports/*.pdf |
| GET /api/research/projects/[id]/critique | getCritique(id) | verify/critique.json (score, weaknesses, suggestions, strengths, pass) |
| GET /api/research/projects/[id]/reports | getAllReports(id) | Alle reports/*.md (filename + content) |
| GET /api/research/projects/[id]/audit | getAudit(id) | verify/claim_evidence_map_latest.json oder verify/claim_ledger.json → claims (claim_id, text, is_verified, verification_tier, supporting_evidence) |

**UI (umgesetzt):** getLatestReportMarkdown liest zuerst `reports/manifest.json` und wählt den Eintrag mit `is_final: true` bzw. den letzten Eintrag; Fallback bleibt readdir + sort reverse.

### F.10 Umgebungsvariablen (vollständig)

| Variable | Default / Quelle | Verwendung |
|----------|------------------|------------|
| OPERATOR_ROOT | /root/operator | Pfade, Python sys.path |
| RESEARCH_SYNTHESIS_MODEL | gemini-3.1-pro-preview | research_synthesize alle LLM-Calls (außer _epistemic_reflect: gemini-2.5-flash) |
| RESEARCH_CRITIQUE_MODEL | gpt-5.2 | research_critic |
| RESEARCH_CRITIC_THRESHOLD | 0.50 | research_critic._threshold(); Überschreibung durch RESEARCH_MEMORY_CRITIC_THRESHOLD aus memory_strategy.json (0.50–0.55) |
| RESEARCH_MEMORY_CRITIC_THRESHOLD | aus memory_strategy.json (policy.critic_threshold) | research-cycle.sh CRITIC_THRESHOLD |
| RESEARCH_MEMORY_REVISE_ROUNDS | 2 (1–4 aus memory_strategy) | Max Revision-Runden |
| AEM_ENFORCEMENT_MODE | observe | research_synthesize validate_synthesis_contract (observe/enforce/strict); research-cycle.sh AEM-Block vor synthesize |
| RESEARCH_WARP_DEEPEN | 0 | research_synthesize: Gap-Detection + Web-Search + Re-Synthese erste Section |
| RESEARCH_SYNTHESIS_SEMANTIC | 0 | research_synthesize: 1 = semantische Relevanz für Findings-Sortierung (Hybrid mit Keyword) |
| RESEARCH_SYNTHESIS_SEMANTIC_WEIGHT | 0.5 | Alpha für Hybrid-Score (semantisch vs. Keyword) |
| RESEARCH_EMBEDDING_MODEL | text-embedding-3-small | research_synthesize _embed_texts (OpenAI) |
| RESEARCH_SYNTHESIS_STRUCTURED_SECTIONS | 0 | 1 = Section-Output als JSON (body_md, claim_refs_used, key_points) |
| OPENAI_API_KEY, GEMINI_API_KEY | secrets.env / env | llm_call |

### F.11 Artefakte: Wer schreibt was (Synthesize-Branch)

| Artefakt | Geschrieben von | Gelesen von |
|----------|------------------|-------------|
| artifacts/report.md | research_synthesize stdout (Shell redirect); dann research_synthesize_postprocess.py schreibt zurück | Post-Processing (Lesen bei artifacts_dir), research_critic (_load_report wenn art_path) |
| artifacts/revised_report.md | research_critic revise stdout | Shell kopiert → report.md, reports/report_<ts>_revised<N>.md |
| artifacts/critique.json | research_critic critique stdout | Shell, MANIFEST_UPDATE, getCritique (nach cp nach verify/) |
| research/<id>/reports/report_<ts>.md | research_synthesize_postprocess.py (Shell: aus $ART; Conductor: aus zuvor geschriebenem Report) | research_critic _load_report, getLatestReportMarkdown, getAllReports, research_pdf_report |
| research/<id>/reports/report_<ts>_revised<N>.md | Shell nach Revise | _load_report (neueste mtime), getAllReports |
| research/<id>/reports/claim_evidence_map_<ts>.json | research_synthesize_postprocess.py | — |
| research/<id>/verify/claim_evidence_map_latest.json | research_synthesize_postprocess.py | getAudit, research_pdf_report |
| research/<id>/reports/manifest.json | research_synthesize_postprocess.py, MANIFEST_UPDATE | getLatestReportMarkdown (is_final / letzter Eintrag) |
| research/<id>/verify/critique.json | Shell cp von $ART/critique.json; QG-Block | getCritique, research_critic revise (Fallback) |
| research/<id>/synthesis_contract_status.json | research_synthesize run_synthesis | — (Logging/Observability) |
| research/<id>/synthesize_checkpoint.json | research_synthesize _save_checkpoint | research_synthesize _load_checkpoint (wird am Ende _clear_checkpoint gelöscht) |
| research/<id>/project.json (quality_gate, status, phase) | QF_FAIL, QG, GATE_PASS, advance_phase | Alle |

### F.12 Tests, die Synthesize/Report/Critique berühren

| Test | Relevanz |
|------|----------|
| tests/tools/test_research_synthesize_contract.py | validate_synthesis_contract, extract_claim_refs_from_report |
| tests/integration/test_aem_settlement_flow.py | get_claims_for_synthesis, block_synthesize |
| tests/integration/test_aem_adversarial.py | block_synthesize, validate_synthesis_contract, SynthesisContractError |
| tests/tools/test_research_advance_phase.py | phase synthesize |
| tests/integration/test_research_phase_flow.py | Phase-Reihenfolge … → synthesize → done |
| tests/research/test_quality_gates.py | apply_verified_tags_to_report, build_claim_ledger |
| tests/research/test_audit_consistency.py | claim_ledger, claim_evidence_map_latest |

Bei Änderungen an Contract, Claim-Ledger-Pfaden, Post-Processing oder Critic/Revise diese Tests anpassen bzw. erweitern.

### F.13 Abhängigkeiten Connect/Verify → Synthesize

- **Connect:** Erzeugt `thesis.json`, `contradictions.json`; beide werden in run_synthesis gelesen.
- **Verify:** Erzeugt `verify/source_reliability.json`, `verify/claim_verification.json`, `verify/claim_ledger.json`, ggf. `verify/fact_check.json`; AEM-Pfad: `claims/ledger.jsonl` (research_claim_state_machine upgrade). get_claims_for_synthesis liest AEM zuerst, dann verify/claim_ledger.json.
- **Evidence Gate:** Muss bestanden sein, damit phase auf synthesize geht; gate_metrics und claim_support_rate stehen in project.json quality_gate.evidence_gate; werden in run_synthesis nicht direkt gelesen, aber in persist_v2_episode und utility_update genutzt.

---

Dieser Plan soll bei Änderungen an der Synthesize-Phase, research_synthesize.py, research-cycle.sh (synthesize), Verify→Synthesize-Schnittstelle und an RESEARCH_QUALITY_SLO, UI_OVERVIEW, RESEARCH_AUTONOMOUS, SYSTEM_CHECK mitgeführt werden.

**Quelle der Wahrheit für Implementierung:** Code in `operator/workflows/research-cycle.sh` (synthesize), `operator/tools/research_synthesize.py`, `operator/tools/research_common.py` (get_claims_for_synthesis), `operator/tools/research_verify.py` (apply_verified_tags_to_report, build_claim_ledger), `operator/tools/research_critic.py`, `operator/tools/research_pdf_report.py`, `operator/tools/research_abort_report.py`, `operator/ui/src/lib/operator/research.ts` (getLatestReportMarkdown, getCritique, getAllReports, getAudit).
