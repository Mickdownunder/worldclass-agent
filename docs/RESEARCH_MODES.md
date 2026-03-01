# Research-Modi: Standard, Frontier, Discovery

Die Research-Pipeline unterstützt drei Modi (`project.json` → `config.research_mode`). Sie unterscheiden sich in **Evidence Gate**, **Claim-Verifikation**, **Conductor-Prompt**, **Discovery-Analyse**, **Synthese/Critic** und **Critic-Schwelle**.

---

## Übersicht

| Aspekt | Standard | Frontier | Discovery |
|--------|----------|----------|-----------|
| **Ziel** | Marktanalyse, Competitive Intel; Quellen müssen sich gegenseitig stützen | Akademisch, Bleeding-Edge; eine autoritative Quelle kann reichen | Neue Ideen, Hypothesen; Breite und Vielfalt vor Verifikation |
| **Evidence Gate** | Verifizierte Claims + claim_support_rate + ggf. source_reliability | Weniger streng: verified_min ODER (findings≥8, sources≥5, reliability≥0.3) | Kein verified_claim-Check: Pass bei findings≥10 & sources≥8 (oder 6/4), sonst pending/fail |
| **Claim-Verifikation (Verify)** | 2+ zuverlässige Quellen → VERIFIED; 1 autoritative → AUTHORITATIVE, **nicht** als verified | Wie Standard, aber 1 autoritative Quelle → AUTHORITATIVE **zählt als verified** | Eigene Tiers: ESTABLISHED (2+), EMERGING (1+), SPECULATIVE; alle außer SPECULATIVE → is_verified |
| **Conductor (LLM)** | Normaler Prompt | Gleich wie Standard | Zusatz: „Discovery MODE: BREADTH over DEPTH“, verify spät, synthesize bei 8+ Domains, 20+ findings |
| **Conductor Gate (deterministisch)** | Normal (explore→focus 1 Override, focus→connect 2) | Gleich | Discovery: synthesize nur durchlassen wenn findings≥15 und sources≥8 |
| **Nach Verify (wenn Gate pass)** | — | — | **Discovery Analysis** läuft: `research_discovery_analysis.py` → `discovery_analysis.json` (novel_connections, emerging_concepts, research_frontier, key_hypothesis) |
| **Synthesize** | Standard-Report, evidence summary Standard | Standard-Report, evidence summary kürzer (frontier) | Discovery-Brief im Report (novel_connections, emerging_concepts, research_frontier, key_hypothesis) |
| **Critic** | Standard-Dimensionen (coverage, depth, accuracy, novelty, coherence, citation_quality) | **Gleiche Schwelle 0.50** (explizit gesetzt im Workflow) | Eigenes System-Prompt: „research innovation reviewer“, Novelty 3x gewichtet; 0.5 mit hoher Novelty besser als 0.7 ohne neue Insights |
| **UI** | — | — | Eigenes Block „Discovery Insights“ (novel_connections, emerging_concepts, research_frontier, unexplored_opportunities, key_hypothesis) |

---

## 1. Evidence Gate (`research_quality_gate.py`)

- **Standard** (`_decide_gate`):  
  Pass: verified_claim_count ≥ Hard/Soft-Pass und claim_support_rate ausreichend; pending_review in Review-Zone; Fail bei zu wenig verifizierten Claims oder claim_support_rate &lt; 0.3 oder source_reliability zu niedrig.

- **Frontier** (`_decide_gate_frontier`):  
  Pass: verified_claim_count ≥ Hard-Pass **oder** (findings ≥ 8, sources ≥ 5, high_reliability_source_ratio ≥ 0.3 bzw. keine Reliability-Daten). Pending: findings ≥ 5, sources ≥ 3. Sonst fail.

- **Discovery** (`_decide_gate_discovery`):  
  Kein verified_claim-Check. Pass: findings ≥ 10 und sources ≥ 8, oder findings ≥ 6 und sources ≥ 4. Pending: findings ≥ 4. Sonst fail.

---

## 2. Claim-Verifikation (`research_verify.py`)

- **Standard:**  
  2+ zuverlässige Quellen, nicht disputed → VERIFIED, is_verified=True.  
  1 autoritative Quelle, nicht disputed → AUTHORITATIVE, **is_verified=False**.

- **Frontier:**  
  Wie Standard, aber bei 1 autoritativer Quelle: **is_verified=True** (Zeile 387–388: `is_verified = research_mode == "frontier"`).

- **Discovery:**  
  Eigene Tiers: ESTABLISHED (2+ Quellen) → verified; EMERGING (1+ Quelle, nicht disputed) → verified; SPECULATIVE → nicht verified.

---

## 3. Conductor (`research_conductor.py`)

- **Standard / Frontier:**  
  Gleicher System-Prompt (nur eine Wortwahl); Aktionen: search_more, read_more, verify, synthesize.

- **Discovery:**  
  Zusatz im System-Prompt: „DISCOVERY MODE: Prioritize BREADTH over DEPTH. Prefer search_more over read_more. Only verify if findings_count >= 30. Synthesize when 8+ domains and 20+ findings.“

- **Conductor Gate (deterministisch):**  
  Bei `research_mode == "discovery"` und proposed_next == "synthesize": nur durchlassen wenn `findings_count >= RESEARCH_DISCOVERY_SYNTHESIZE_MIN_FINDINGS` und `source_count >= RESEARCH_DISCOVERY_SYNTHESIZE_MIN_SOURCES`. Defaults: 15 und 8. Env-Variablen: `RESEARCH_DISCOVERY_SYNTHESIZE_MIN_FINDINGS`, `RESEARCH_DISCOVERY_SYNTHESIZE_MIN_SOURCES`.

---

## 4. Workflow (research-cycle.sh)

- **Discovery:** Nach Evidence-Gate-Pass (verify-Phase), vor advance_phase synthesize:  
  `research_discovery_analysis.py` → schreibt `discovery_analysis.json` (discovery_brief mit novel_connections, emerging_concepts, research_frontier, unexplored_opportunities, key_hypothesis).

- **Frontier:** In der Synthesize-Phase vor dem Critic:  
  `CRITIC_THRESHOLD="0.50"` explizit gesetzt („frontier = explicit low bar“). Standard nutzt ggf. `RESEARCH_MEMORY_CRITIC_THRESHOLD` aus memory_strategy.

---

## 5. Synthese (`research_synthesize.py`)

- **Standard:** Evidence-Zusammenfassung aus Claim-Ledger; keine Discovery-Felder im Report.

- **Frontier:** Kürzere Evidence-Summary-Zeile (`_evidence_summary_line(..., research_mode="frontier")`).

- **Discovery:** Liest `discovery_analysis.json` → `discovery_brief` wird in Sektionen und Conclusions/Next Steps eingebaut (novel_connections, emerging_concepts, research_frontier, unexplored_opportunities, key_hypothesis). Eigenes Strategie-Prompt für Conclusions (`_synthesize_conclusions_next_steps` mit discovery_brief).

---

## 6. Critic (`research_critic.py`)

- **Standard / Frontier:**  
  „Research quality reviewer“; Dimensionen coverage, depth, accuracy, novelty, coherence, citation_quality; Pass bei score ≥ Threshold.

- **Discovery:**  
  „Research innovation reviewer“; Dimensionen mit Gewichtung (novelty 3x, coverage 2x, depth/coherence/accuracy/citation_quality 1x). Explizit: „A discovery report scoring 0.5 with high novelty is better than 0.7 with no novel insights.“

---

## 7. UI & API / Trigger

- **Erstellung:** `POST /api/research/projects` mit `research_mode`: `"standard"` | `"frontier"` | `"discovery"`. Default `"standard"`.
- **Standard/Frontier:** CreateProjectForm auf `/research` (Playbook + Research-Mode-Auswahl).
- **Discovery – eigener Trigger:** Eigener Menüpunkt **„Discovery Research“** in der Nav → Route **`/research/discovery`**. Dort nur ein Formular „Novel / Discovery Research“: eine Frage (Platzhalter z. B. „Wie können wir Krebs heilen? Welche neuen Ansätze gibt es?“), kein Playbook-, kein Research-Mode-Dropdown; `research_mode` ist fest **discovery**. Submit → gleiche API mit `research_mode: "discovery"`; nach Init Redirect auf Projekt-Detail. Discovery wird damit **komplett anders getriggert** als Standard/Frontier und ist für offene, ambitionierte Fragen gedacht.
- **Projekt-Detail:** Bei `config.research_mode === "discovery"` wird der Block „Discovery Insights“ angezeigt (aus `discovery_analysis.json` / `discovery_brief`).

---

## 8. Heuristik (`suggest_research_mode`)

`research_quality_gate.suggest_research_mode(question, domain)` schlägt einen Modus vor:

- **discovery:** Frage enthält z. B. novel, neue ideen, zukunft, future, emerging, discovery, hypothese, trends, paradigm, vision, roadmap.
- **frontier:** Frage enthält z. B. bleeding edge, state of the art, academic, papers, arxiv, conference, study, methodology; oder domain in (academic, science, ai_research, research).
- **standard:** sonst.

Wird beim Erstellen eines Projekts nicht automatisch gesetzt; die UI übergibt den vom Nutzer gewählten Modus.

---

## 9. Ist das System SOTA genau für Discovery (z. B. „Krebs heilen“)?

**Kurz:** **Architektur und viele Bausteine ja; Vollzug noch nicht vollständig.**

| Aspekt | Status | Anmerkung |
|--------|--------|-----------|
| **Trigger & UX** | ✅ | Eigenes Menü, eigene Seite, Form nur für offene Fragen (z. B. „Krebs heilen“). |
| **Evidence Gate** | ✅ | Discovery-spezifisch: Breite (Findings/Sources), kein verified_claim-Zwang. |
| **Conductor** | ✅ | BREADTH over DEPTH, search_more vor read_more, synthesize bei 8+ Domains, 20+ Findings. |
| **Claim-Verifikation** | ✅ | ESTABLISHED/EMERGING/SPECULATIVE; EMERGING zählt als verified. |
| **Discovery Analysis** | ✅ | Transitive Muster, Entity-Frequenz, Cross-Domain (Memory), Widersprüche → Frontier, LLM discovery_brief. |
| **Synthesize/Critic** | ✅ | discovery_brief im Report; Critic Novelty 3×, „0.5 mit Novelty besser als 0.7 ohne“. |
| **Explore (Planner)** | ✅ | Planner liest `config.research_mode`; bei **discovery** eigener Prompt: 20–40 Queries, Breite, Lücken, konkurrierende Hypothesen, benachbarte Felder (siehe DISCOVERY_FULL_CAPABILITY_ROADMAP.md). |
| **Memory/Graph** | ✅ | `discovery_analysis` nutzt Entity-Relations und cross_links aus Memory. **Neu:** Beim Projektstart (`research_knowledge_seed`) werden im Discovery-Modus automatisch **Lateral Principles** (die nützlichsten Prinzipien aus komplett anderen Domains) injiziert, um analoges Denken beim Planner zu triggern. |
| **Gesamt-SOTA** | Siehe RESEARCH_SOTA_GAP_AND_ROADMAP | Token Governor default aus, Entity-Graph nicht durchgängig in Verify/Synthesize, weitere Lücken dort beschrieben. |

**Konkrete Schritte „voll in der Lage“:** Siehe **`docs/DISCOVERY_FULL_CAPABILITY_ROADMAP.md`** (Checkliste inkl. Discovery-Planner ✅, Entity-Graph, Token Governor, Brief bei leerem Graph, Conductor-Schwellen, Kalibrierung).

**Fazit:** Für Discovery ist das System **sehr gut aufgestellt** (eigener Ablauf, Gate, Conductor, Discovery Analysis, Novelty-Critic, Lateral Inspiration aus dem Memory) und für ambitionierte Fragen wie „Krebs heilen“ **nutzbar und optimiert**.

---

## 10. Captain-Verdict: Ist das System „equipped“ für intelligente, novel Entdeckungen?

**Ja – es ist für maximale Discovery-Kompatibilität ausgerüstet.**

| Fähigkeit | Vorhanden? | Wo |
|-----------|------------|-----|
| **Breite vor Tiefe** | ✅ | Conductor Discovery: search_more vor read_more; Gate nach Breite (Findings/Sources). |
| **Lücken erkennen** | ✅ | Coverage-Gaps → gap_opportunities; refinement/gap-fill in Explore/Focus. |
| **Hypothesen bilden** | ✅ | Connect: hypothesis_formation; Discovery Brief: key_hypothesis; Synthesize: Conclusions mit [EMERGING]. |
| **Novel Connections** | ✅ | discovery_analysis: transitive A→B→C; Entity-Frequenz; cross_domain_insights; Widersprüche. |
| **Cross-Domain/Lateral**| ✅ | `research_knowledge_seed.py` injiziert im Discovery-Modus Top-Utility-Prinzipien (Lateral Inspiration), der Planner nutzt diese aktiv für out-of-the-box Queries. |
| **Report & Bewertung** | ✅ | discovery_brief im Report; Critic Novelty 3×. |

**Einschränkungen (Rest):**
1. **Memory-Dichte:** Transitive Muster und Cross-Domain brauchen ein initial gefülltes Memory (Entity-Relations und cross_links). Beim allerersten Discovery-Projekt ist dieses Signal naturgemäß schwächer.

**Kurz:** Das System **ist maximal ausgestattet**, um intelligente, novel Entdeckungen zu **machen** und das Memory-System voll auszureizen (inkl. analogem Querdenken und Graph-Analysen).
