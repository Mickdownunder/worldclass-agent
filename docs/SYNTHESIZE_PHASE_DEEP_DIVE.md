# Synthesize-Phase — Tiefenanalyse

Vollständige technische Analyse: Datenfluss, beteiligte Module, Schema, Probleme/Lücken und SOTA/Novel-Möglichkeiten. Quelle der Wahrheit: `operator/workflows/research-cycle.sh` (Branch `synthesize`), `operator/tools/research_synthesize.py`, `operator/tools/research_common.py`.

---

## Teil 1: Datenfluss der Synthesize-Phase im Detail

### 1.1 Eintritt und Vorbedingungen

- **Phase:** `synthesize` (nach bestandenem Evidence Gate in Verify).
- **Shell:** `research-cycle.sh` case `synthesize)` (Zeilen ~1319–1610).
- **Vorbedingung:** Evidence Gate bestanden; Artefakte in `research/<project_id>/verify/` (claim_ledger.json, source_reliability.json, ggf. claim_verification.json, fact_check.json) und `research/<project_id>/findings/`, `sources/` verfügbar.

### 1.2 Inputs und Reihenfolge des Ladens

| Reihenfolge | Input | Quelle | Verwendung |
|-------------|--------|--------|------------|
| 1 | Projekt-Metadaten | `project.json` (question, config, research_mode) | Frage, Playbook-ID, Discovery-Mode |
| 2 | Findings | `findings/*.json` | Alle gelesen, dann nach Relevanz zur Frage sortiert, max `MAX_FINDINGS` (80) |
| 3 | Sources | `sources/*.json` (ohne `*_content.json`) | Referenzliste, Titel, URL; Claim Evidence Registry |
| 4 | Claim Ledger | `get_claims_for_synthesis(proj_path)` → `claims/ledger.jsonl` oder `verify/claim_ledger.json` | Claim-Ledger-Block, Provenance, Epistemic Profile, Section-Prompts |
| 5 | Verify-Artefakte | `verify/source_reliability.json` | `rel_sources` (URL → reliability_score); [LOW RELIABILITY] in Section-Excerpts |
| 6 | Widersprüche | `contradictions.json` | Abschnitt „Contradictions & Open Questions“ |
| 7 | Thesis | `thesis.json` | Executive Decision Synthesis, Scenario Matrix, Conclusions |
| 8 | Playbook | `research/playbooks/<playbook_id>.json` oder `proj/../playbooks/` | `synthesis_instructions` für Outline-Sections |
| 9 | Discovery (optional) | `discovery_analysis.json` → `discovery_brief` | Discovery Map, Key Hypothesis, section prompts (discovery mode) |

### 1.3 Ablauf: beteiligte Skripte und Funktionen

1. **research-cycle.sh (synthesize):**
   - `progress_start "synthesize"`, `progress_step "Generating outline"`.
   - `timeout 900 python3 research_synthesize.py $PROJECT_ID > $ART/report.md`.
   - Post-Processing: `research_synthesize_postprocess.py $PROJECT_ID $ART` — apply_verified_tags, Strippen von LLM-References, Aufbau References aus claim_ledger, claim_evidence_map_*, manifest.json; schreibt `reports/report_<ts>.md` und ggf. zurück nach `$ART/report.md`.
   - Critic: `research_critic.py critique $ART` → `critique.json`; bei Score < Threshold oder „unvollständig“-Weakness: Revision (bis `MAX_REVISE_ROUNDS`), dann erneut Critic.
   - Bei Bestehen: PDF, `research_embed.py`, `research_cross_domain.py`, `advance_phase done`, Brain/Memory-Reflection, Distiller, Utility-Update, `persist_v2_episode "done"`.

2. **research_synthesize.py — Kernablauf:**
   - `run_synthesis(project_id)`:
     - Lädt project, question, research_mode, discovery_brief; findings (`_load_findings`), sources (`_load_sources`), claim_ledger (`get_claims_for_synthesis`), contradictions, rel_sources, thesis.
     - `_build_ref_map(findings, claim_ledger)` → ref_map (url→ref_num), ref_list (url, title).
     - **Checkpoint:** Falls `synthesize_checkpoint.json` existiert und konsistent → Sections ab Index `len(bodies)` fortsetzen; sonst neu: Clustering, Outline, Section-Schleife.
     - **Clustering:** `_cluster_findings(findings, question, project_id)` — LLM-Call: 3–7 thematische Cluster (JSON `clusters`); Fallback: je 5 Findings pro Cluster.
     - **Outline:** `_outline_sections(question, clusters, playbook_instructions, project_id)` — LLM: Section-Titel pro Cluster; Playbook-Instructions einbezogen.
     - **Pro Section:** `_synthesize_section(...)` mit findings für Cluster, ref_map, claim_ledger, previous_sections_summary, used_claim_refs, epistemic_profile; danach `_epistemic_reflect` (Sprache an Tier anpassen). Optional WARP-Deepening (RESEARCH_WARP_DEEPEN=1): Gap-Detection, Web-Search, Re-Synthese erste Section.
     - Checkpoint nach jeder Section gespeichert.
     - Danach: Dedup Sections (`_deduplicate_sections`), dann Methodology, Contradictions, Verification Summary, Research Situation Map, Tipping Conditions, Scenario Matrix, Conclusions & Next Steps.
     - Executive Summary (`_synthesize_exec_summary`) nach KEY NUMBERS eingefügt; Executive Decision Synthesis vor Methodology eingefügt.
     - Claim Evidence Registry + Provenance + Appendix B + References (aus ref_list) angehängt.
     - **Synthesis Contract:** `validate_synthesis_contract(report_body, claim_ledger, mode)`; bei enforce/strict und Invalid → `SynthesisContractError`.
   - Ausgabe: vollständiger Report-Markdown (stdout → `$ART/report.md`).

3. **An das LLM übergebene Daten (Auszug):**
   - **Clustering:** JSON der Findings (i, title, excerpt[:500]), max ~12k Zeichen; System: 3–7 Cluster, JSON mit `clusters`.
   - **Outline:** Frage, Cluster-Summaries („Cluster 1: N findings“), optional Playbook-Instructions; JSON `sections` (Titel pro Cluster).
   - **Section-Prompt pro Sektion:** Frage, Section-Titel, Reference Mapping (ref_num, url, title), Findings (excerpts bis `EXCERPT_CHARS` 2000, mit [LOW RELIABILITY] wenn reliability < 0.3), Full Source Content (bis `SOURCE_CONTENT_CHARS` 6000 pro Quelle, max 5 Quellen), CLAIM LEDGER (claim_ref, Tier, Text), Epistemic Profile, previous_sections_summary, used_claim_refs; Discovery-Brief wenn discovery mode.
   - **Epistemic Reflect:** Liste verwendeter claim_refs mit Tier; Abschnittstext; Ausgabe: sprachlich angepasster Text.
   - Weitere LLM-Calls: Research Situation Map, Tipping Conditions, Scenario Matrix, Executive Summary, Decision Matrix, Conclusions/Next Steps, Key Numbers.

---

## Teil 2: Schema/Struktur der beteiligten Daten

### 2.1 Findings (`findings/*.json`)

- Typische Felder: `finding_id`, `url`, `title`, `excerpt`, `source` (read/deep_extract), ggf. `read_phase`, `search_query`.
- Synthesize liest alle, sortiert nach `_relevance_score` (Keyword-Overlap mit question), begrenzt auf `MAX_FINDINGS` (80).

### 2.2 Source-Metadaten (`sources/<id>.json`)

- `url`, `title`, `description`, `published_date`/`date`; keine `*_content.json` in der Liste.
- Source-Content: `sources/<key>_content.json` mit `text` oder `abstract`; pro URL max `SOURCE_CONTENT_CHARS` (6000) Zeichen.

### 2.3 Claim Ledger (für Synthese)

- **Quelle:** `get_claims_for_synthesis(proj_path)` — bevorzugt `claims/ledger.jsonl` (AEM), sonst `verify/claim_ledger.json` → `claims`.
- **Eintrag (vereinfacht):** `claim_id`, `text`, `supporting_source_ids` (URLs), `source_finding_ids`, `is_verified`, `verification_tier` (VERIFIED | AUTHORITATIVE | TENTATIVE | UNVERIFIED | ESTABLISHED | EMERGING | SPECULATIVE), `verification_reason`, `claim_version`, ggf. `falsification_status` (PASS_TENTATIVE).
- **Verwendung:** Claim-Ledger-Block in Section-Prompt (`[claim_ref: id@version] [TIER] text`), Provenance (Claim ID → source_finding_ids), Evidence Registry (Claim → Source → URL → Date → Tier), Epistemic Profile (Tier-Zählung), Contract-Validierung (jeder claim-artige Satz muss [claim_ref: id@version] haben, wenn Ledger nicht leer).

### 2.4 Report-Struktur (Markdown)

- Titel, Report-Datum, Projekt, Frage.
- Evidence Summary (eine Zeile).
- KEY NUMBERS (LLM-extrahiert).
- Optional: Discovery Map (Novel Connections, Emerging Concepts, Research Frontier, Key Hypothesis).
- Executive Summary (nach KEY NUMBERS eingefügt).
- Deep-Analysis Sections (## Titel + Body; 500–1500 Wörter pro Section).
- Executive Decision Synthesis (vor Methodology).
- Methodology (Findings-/Source-Zahlen, Modell, Timestamp).
- Contradictions & Open Questions.
- Verification Summary (Tabelle: Claim, Status, Sources).
- Research Situation Map, Tipping Conditions, Scenario Matrix.
- Conclusions & Thesis, Recommended Next Steps.
- Claim Evidence Registry (Tabelle), Provenance (Claim ID → Finding IDs), Appendix B (Methodology Details), References (nur aus claim_ledger zitiert).

### 2.5 Post-Processing (research-cycle.sh)

- References: nur URLs aus `supporting_source_ids` der Claims; Titel aus findings/sources.
- `claim_evidence_map_<ts>.json`: report_id, claims mit claim_id, text, is_verified, verification_reason, supporting_source_ids, supporting_evidence (url, snippet).
- `verify/claim_evidence_map_latest.json` — Kopie für UI/Audit.

**UI:** `GET /api/research/projects/[id]/report` nutzt `getLatestReportMarkdown`: liest `reports/*.md`, sortiert nach Dateiname (nicht mtime). Für konsistent „neuesten“ Report kann `reports/manifest.json` (is_final / letzter Eintrag) genutzt werden.

---

## Teil 3: Retrieval/Selektion für die Synthese

### 3.1 Findings: Filter und Sortierung

- **Geladen:** Alle `findings/*.json`; keine Filterung nach admission_state oder read_phase (alle Findings des Projekts).
- **Sortierung:** `_relevance_score(finding, question)` = Keyword-Overlap (Wörter ≥3 Zeichen): `|q_words ∩ f_words| / |q_words|`.
- **Limit:** `MAX_FINDINGS = 80` (erste 80 nach Sortierung).

**Einschränkung:** Rein lexikalische Relevanz; keine semantische Suche, keine Nutzung von Verify-Status (verified/unverified) für die Sortierung.

### 3.2 Source-Content laden und kürzen

- `_load_source_content(proj_path, url, max_chars=SOURCE_CONTENT_CHARS)` mit `SOURCE_CONTENT_CHARS = 6000`.
- Pro Section werden bis zu 5 Quellen mit vollem Content geladen (URLs aus section_findings); Excerpts pro Finding bis `EXCERPT_CHARS = 2000`.

### 3.3 Section-Umfang

- `SECTION_WORDS_MIN, SECTION_WORDS_MAX = 500, 1500` (in Prompts erwähnt); keine harte Nachprüfung im Code.

### 3.4 Limits (Zusammenfassung)

| Konstante | Wert | Ort |
|-----------|------|-----|
| MAX_FINDINGS | 80 | research_synthesize.py |
| EXCERPT_CHARS | 2000 | research_synthesize.py |
| SOURCE_CONTENT_CHARS | 6000 | research_synthesize.py |
| SECTION_WORDS_MIN/MAX | 500, 1500 | research_synthesize.py (Prompt) |
| Claim Ledger in Section | 40 Einträge | _claim_ledger_block |
| Findings pro Section | 15 (excerpts), 5 URLs full content | _synthesize_section |
| Clustering-Input | ~12k Zeichen | _cluster_findings |

---

## Teil 4: Probleme-/Lücken-Tabelle

| Bereich | Problem | Schwere |
|----------|---------|--------|
| Relevanz | Findings-Sortierung nur Keyword-Overlap; keine semantische/embedding-basierte Relevanz zur Frage | hoch |
| Verify-Nutzung | Claim Ledger wird genutzt; critique.json und detaillierte Verify-Metriken fließen nicht in Section-Auswahl oder Gewichtung ein | mittel |
| Claim–Evidence | Provenance (Claim ID → finding IDs) ist vorhanden; feingranulare Span-Attribution (welcher Satz welcher Quelle) fehlt | mittel |
| Factuality | Epistemic Reflect und Tier-Sprache vorhanden; kein expliziter Factuality-Check (z. B. Claim-vs-Report-Abgleich) nach Generierung | mittel |
| Report-Struktur | Outline und Sections fest an Clustering gebunden; konfigurierbare Report-Templates (z. B. Playbook-spezifische Sections) nur über playbook_instructions im Outline | mittel |
| Limits | MAX_FINDINGS 80 und 15/5 pro Section können bei großen Projekten zu Verlust relevanter Findings führen; keine adaptive Anpassung | niedrig |
| References | Nur aus claim_ledger zitiert; Findings ohne Claim-Verknüpfung erscheinen nicht in References (gewollt, aber einschränkend für „alle genutzten Quellen“) | niedrig |
| Checkpoint | Checkpoint nur für Section-Bodies; bei Abbruch gehen spätere Teile (Situation Map, Tipping, etc.) verloren und müssen neu erzeugt werden | niedrig |
| Contract | Synthesis Contract (claim_ref pro claim-artiger Satz) nur bei nicht leerem Ledger; bei leerem Ledger keine Prüfung auf ungestützte Behauptungen | mittel |
| Critic/Revise | Revision-Runden verbessern Report; Weaknesses werden nicht strukturiert in Section-Prompts zurückgespielt (nur indirekt über Revise-Prompt) | niedrig |

---

## Teil 5: SOTA- und Novel-Verbesserungsmöglichkeiten

### 5.1 State of the Art (Einordnung)

- **Multi-Document Summarization mit Attribution:** Systeme wie „Attribute First, then Generate“ liefern feingranulare Attributierung (Span-Level) statt nur Dokument-Zitate; MetaSumPerceiver und Fact-Checking-orientierte Ansätze trennen claim-spezifische Evidenz und Truthfulness-Labels.
- **Claim-driven Writing:** Unser Claim-Ledger und [claim_ref: id@version] sind ein Schritt in diese Richtung; SOTA würde jede Behauptung im Report einem Claim oder einer expliziten „no claim“-Kategorie zuordnen und Span-zu-Source abbilden.
- **Factuality/Attribution:** HalluTree/FactCG-ähnliche Ideen: Subclaims klassifizieren (extractiv vs. inferentiell), Multi-Hop-Verifikation, Kontext-Graphen für Evidenz. Ein Post-Generation-Factuality-Pass könnte Sätze gegen Claim-Ledger und Findings prüfen.
- **Strukturierte Outputs:** Report-Schema (z. B. JSON mit Sections, Claims pro Absatz, Confidence) würde maschinelle Validierung und bessere Nachverfolgbarkeit ermöglichen.
- **Chain-of-Verification:** Eigenständige Verifikationsschritte nach dem Schreiben („Ist jede Zahl/Quote in den Findings?“) vor Freigabe.

### 5.2 Konkrete Verbesserungen (priorisiert)

1. **Semantische Relevanz für Findings:** Embedding-basierte oder hybrid (Keyword + Semantic) Sortierung der Findings zur Frage; Begrenzung auf Top-K nach kombinierter Relevanz statt nur Keyword + festes MAX_FINDINGS.
2. **Claim–Evidence feingranular:** Pro Satz oder Absatz optional „supporting_finding_ids“ oder Span-Attribution aus dem LLM (strukturierter Output); in claim_evidence_map und Provenance persistieren.
3. **Factuality-Guard:** Nach Section- oder Report-Generierung: Automatischer Abgleich von Zahlen, Daten, Zitaten gegen Findings/Claim-Ledger; Flagging oder automatische Korrektur/Qualifier.
4. **Konfigurierbare Report-Struktur:** Playbook oder Projekt-Config definiert feste Section-Typen (z. B. „Executive Summary“, „Market Size“, „Risiken“, „Historischer Präzedenz“); Outline-LLM füllt nur Titel innerhalb dieses Schemas.
5. **Verify-Artefakte voll nutzen:** critique.json (vorherige Runs), evidence_gate metrics, claim_support_rate in Epistemic Profile oder Section-Guidance einbeziehen; Weaknesses aus Critic in Revise-Runde strukturiert („fehlende Tiefe in Section X“) zurückführen.
6. **Strukturierte Report-Generierung:** Optional JSON-Schema für Sections (headline, key_points[], claim_refs[], confidence); daraus Markdown rendern; ermöglicht bessere Validierung und Contract-Checks.

### 5.3 Novel-Ideen

- **Contrastive Sections:** Bei Widersprüchen (contradictions.json) explizit „Position A vs. Position B“-Abschnitte mit klarer Zuordnung zu Quellen/Claims.
- **Uncertainty-bewusste Executive Summary:** Automatische Kürzung/Konditionierung der Executive Summary, wenn Epistemic Profile „TENTATIVE+UNVERIFIED > 60%“ (bereits als Text-Anweisung vorhanden; könnte als strukturierte Regel + kürzere Max-Words umgesetzt werden).

---

Dieses Dokument bei Änderungen an Synthesize-Phase, research_synthesize.py, research_common.get_claims_for_synthesis, research-cycle.sh (synthesize), Verify→Synthesize-Schnittstelle und an UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK mitführen.

**Weiterführend:** [SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md](SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md) — SOTA-Überblick, Ist-Zustand, Ziele und phasierter Weltklasse-Plan.
