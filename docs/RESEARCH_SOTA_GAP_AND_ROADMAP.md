# Research-System: SOTA-Anspruch vs. Implementierung — Gap-Analyse & Roadmap

**Anspruch:** Das beste, klügste, weltweit führende Research-System — absolutes SOTA, novel.  
**Frage:** Wie stehen Tools und Implementierung da? Was fehlt, was ist stark, was ist der nächste Hebel?

---

## 1. Kurzfassung

| Dimension | Bewertung | Kernaussage |
|-----------|-----------|-------------|
| **Architektur & Design** | **SOTA-fähig** | Pipeline (explore→focus→connect→verify→synthesize), AEM (Settlement, Enforcement, Evidence Index, Claim Lifecycle), Memory v2, Token Governor, Intelligence-per-Token-Design sind **theoretisch und konzeptionell** auf Weltniveau. Die Pläne (Worldclass Plans, Full AEM, INTELLIGENCE_PER_TOKEN) sind mit Forschung und Literatur abgeglichen. |
| **Implementierung** | **Teilweise SOTA, viele Lücken** | Kern-Pipeline läuft; AEM-Bausteine (Settlement, Evidence Index, Contradiction Linking, Falsification Gate) sind implementiert und getestet. **Aber:** Viele im Worldclass-Plan spezifizierten Phasen sind **noch nicht umgesetzt** (Fact-Check-Integration, gewichtete Source Credibility, CoVe durchgängig, Graph in Verify/Synthesize, semantische Findings-Auswahl, Span-Attribution, Factuality-Guard). Token Governor ist **default aus** (RESEARCH_ENABLE_TOKEN_GOVERNOR=0). |
| **Novel** | **Potenzial, noch nicht ausgespielt** | Die **Kombination** aus AEM + Memory v2 + Conductor + Intelligence-per-Token + durchgängiger Claim–Evidence–Lifecycle ist selten. Echte Novelität entsteht, wenn (1) alle Worldclass-Phasen umgesetzt sind, (2) Token Governor und Kalibrierung in der Breite laufen, (3) Connect→Verify→Synthesize **wirklich** durchgängig Daten teilen (Graph, thesis, contradictions). |

**Fazit:** Die **Architektur und die Pläne** sind weltklasse-tauglich. Die **Implementierung** ist auf dem Weg, aber **nicht** „absolut SOTA“ — es fehlen gezielte Vollzüge der bereits spezifizierten Phasen und die Aktivierung/Integration einiger bereits gebauter Bausteine.

---

## 2. Was bereits SOTA-nah oder stark ist

- **Pipeline & Phasen:** Vollständige Deep Dives und Worldclass-Pläne für Explore, Focus, Connect, Verify, Synthesize; klare Datenflüsse und Fail-Codes (RESEARCH_QUALITY_SLO).
- **AEM (Evidence & Settlement):** Enforcement (observe/enforce/strict), Hard Synthesis Contract ([claim_ref]), Outcome/Settlement-Schema, Evidence Index (scope, independence, directness, rigor), Contradiction Linking, Falsification Gate, Claim State Machine. Full AEM Test Plan und Compliance-Report vorhanden.
- **Verify-Grundlagen:** source_reliability, claim_verification, fact_check, claim_ledger, Evidence Gate mit Schwellen, Loop-back (deepening_queries), Recovery; CoVe optional (RESEARCH_ENABLE_COVE_VERIFICATION).
- **Synthesize-Grundlagen:** Claim-Ledger durchgängig, [claim_ref], Epistemic Profile, Claim Evidence Registry, Provenance, Critic + Revision-Runden, References nur aus zitierten Quellen.
- **Memory v2:** Strategy aus Daten, Utility, Principles, Konsolidierung, Explainability (Memory Applied), kalibrierte Schwellen (research_calibrator).
- **Token Governor:** Implementiert (expected_ig_heuristic, recommend_lane, strong nur bei expected_ig_per_token ≥ threshold); Unit-Tests; **aber default aus** und nur an wenigen Stellen im Cycle eingehängt.
- **Conductor:** Dynamische Orchestrierung (search_more, read_more, verify, synthesize), begrenzter State, LLM + Fallback; sinnvoll für adaptive Research.
- **Core-10-Integration:** knowledge_seed, question_graph, relevance_gate, context_manager, dynamic_outline, claim_state_machine, contradiction_linking, falsification_gate, academic, token_governor — über Flags steuerbar; teilweise noch 0 (z. B. token_governor, relevance_gate, dynamic_outline je nach Welle).

---

## 3. Lücken: Wo die Implementierung hinter dem SOTA-Anspruch zurückbleibt

### 3.1 Verify (vgl. VERIFY_PHASE_WORLDCLASS_PLAN)

| Lücke | SOTA-Ziel | Aktuell | Priorität |
|------|-----------|---------|-----------|
| **Fact-Check in Gate/Ledger** | fact_check-Fakten mit Claims abgleichen; confirmed/disputed in Ledger; Nutzung im Gate. | fact_check wird erzeugt, **nicht** in Gate oder Ledger-Bewertung genutzt. | Hoch |
| **Evidence-Spans/Snippets** | Pro Claim strukturierte supporting_evidence (url, snippet, source_id). | Ledger hat supporting_sources (URLs); **keine** Snippets in Verify; claim_evidence_map erst in Synthesize. | Hoch |
| **Source Credibility gewichtet** | Pro-Quelle-Score; gewichteter Claim-Score oder Tiers (primary/secondary/low). | source_reliability fließt ein (z. B. 0.6 Cutoff); **keine** feinkörnige Gewichtung pro Claim. | Mittel |
| **CoVe durchgängig** | Verifikationsfragen pro Claim → unabhängige Prüfung → Revision. | CoVe optional (Flag), nicht Standard; nicht in allen Modi genutzt. | Mittel |
| **Evidenz-Critique vor Synthesize** | Kurzer Schritt „fehlende Evidenz für Kernthesen“ → deepening_queries/Warnung. | gap_analysis bei Fail; **kein** strukturierter „Evidence-Critique“-Schritt vor Synthesize. | Niedrig |

### 3.2 Connect (vgl. CONNECT_PHASE_WORLDCLASS_PLAN)

| Lücke | SOTA-Ziel | Aktuell | Priorität |
|------|-----------|---------|-----------|
| **Verify/Synthesize nutzen Connect** | thesis.json + contradictions.json für Claim-Priorisierung in Verify; Graph in Verify/Synthesize. | thesis/contradictions in Verify **teilweise** (thesis_relevance, Connect-Context); **kein** durchgängiger Entity-Graph in Verify/Synthesize. | Hoch |
| **Entity-Graph durchgängig** | Graph als Projekt-Artefakt; Verify (Claim-Entity-Zuordnung), Synthesize (Struktur/Narrative) lesen ihn. | Graph in Connect erzeugt, in Memory geschrieben; **nicht** als Standard in Verify/Synthesize genutzt. | Hoch |
| **Contradiction → Hypothesis** | Widersprüche als Input für hypothesis_formation; thesis mit alternatives + uncertainty. | Ein LLM-Call pro Schritt; **keine** Kopplung Contradictions → Hypothesis; nur erste Hypothese → thesis. | Mittel |
| **Claim-first Contradiction** | Zuerst Claims extrahieren, dann Paarvergleich (entailment/contradiction). | Ein Monolith-LLM über Findings; **keine** zweistufige Claim-Extraktion + Vergleich. | Mittel |

### 3.3 Synthesize (vgl. SYNTHESIZE_PHASE_WORLDCLASS_PLAN)

| Lücke | SOTA-Ziel | Aktuell | Priorität |
|------|-----------|---------|-----------|
| **Semantische Findings-Auswahl** | Hybrid/semantische Relevanz für Findings pro Section (nicht nur Keyword). | RESEARCH_SYNTHESIS_SEMANTIC=1 optional; **keyword** dominiert sonst. | Mittel |
| **Span-Attribution** | Satz-/Span-Level: welcher Satz welcher Finding/Quote entspricht. | Claim→Source; **kein** Satz→Span. | Mittel |
| **Factuality-Guard** | Post-Generation: Zahlen/Zitate vs. Ledger/Findings prüfen (CoVe-ähnlich). | **Nicht** implementiert. | Mittel |
| **Strukturierte Report-Struktur** | Konfigurierbares Schema (Sections aus Playbook/Config); maschinell auswertbar. | Struktur über Playbook-Instructions; **kein** festes konfigurierbares Section-Schema. | Niedrig |
| **Critic-Weaknesses in Revise** | Weaknesses strukturiert pro Section in Revise zurückgespielt. | Revise nutzt Critic-Output; **nicht** fein pro Section. | Niedrig |

### 3.4 Token Governor & Kosten-Intelligenz

| Lücke | SOTA-Ziel | Aktuell | Priorität |
|------|-----------|---------|-----------|
| **Governor in kritischem Pfad** | Alle teuren LLM-Schritte (Verify, Synthesize, Critic) respektieren Lane (cheap/mid/strong). | RESEARCH_ENABLE_TOKEN_GOVERNOR=**0**; nur an zwei Stellen in research-cycle.sh (Explore/Focus) eingehängt; **nicht** in Verify/Synthesize/Critic. | Hoch |
| **Budget-Layer** | Global, Phase, Claim-Level Budgets (vgl. INTELLIGENCE_PER_TOKEN). | Design vorhanden; **nicht** flächendeckend umgesetzt. | Mittel |

### 3.5 AEM & Tests

| Lücke | SOTA-Ziel | Aktuell | Priorität |
|------|-----------|---------|-----------|
| **Full AEM durchgängig getestet** | Alle Testmatrix-Punkte (Contracts, Enforcement, Evidence Index, Token Governor) grün; CI. | FULL_AEM_TEST_PLAN vorhanden; **nicht** alle Punkte automatisiert/grün; Adversarial/Regressionen teils offen. | Hoch |
| **Kalibrierung in Produktion** | Kalibrierte Schwellen aus vergangenen Runs (research_calibrator) aktiv. | Calibrator existiert; Nutzung **nicht** überall** (z. B. Gate-Schwellen kalibriert wo eingebaut). | Mittel |

---

## 4. Priorisierte Roadmap: Von „stark auf dem Papier“ zu „SOTA in Produktion“

### Stufe 1 — Sofortnutzen (0–2 Wochen) — **umgesetzt**

1. **Token Governor aktivieren und ausweiten** ✅  
   - `RESEARCH_ENABLE_TOKEN_GOVERNOR=1` als Default in `research-cycle.sh`.  
   - Lane vor **Verify**, vor **Synthesize** und vor **Critic** gesetzt; `governor_lane.json` im Projektverzeichnis für UI.  
   - **Lane → Modell:** `model_for_lane(context)` in `research_common.py`; Verify-, Synthesize- und Critic-Tools wählen das Modell nach Lane (cheap/mid/strong). Env-Overrides: `RESEARCH_VERIFY_MODEL_CHEAP`/`_MID`, `RESEARCH_SYNTHESIS_MODEL_CHEAP`/`_MID`, `RESEARCH_CRITIQUE_MODEL_CHEAP`/`_MID`; Defaults: cheap = gpt-4.1-mini, mid = gemini-2.5-flash, strong = jew. RESEARCH_*_MODEL.  
   - **Effekt:** Höhere Intelligence-per-Token; Lane steuert tatsächlich die Modellwahl.

2. **Connect-Output in Verify nutzen (Phase 1 Worldclass Connect)** ✅ (bereits vorhanden, beibehalten)  
   - thesis.json und contradictions.json in research_verify.py eingelesen; thesis-relevante Claims priorisiert; connect_context.json geschrieben; Quellen aus contradictions in Ledger (in_contradiction).  
   - **Effekt:** Verify evidenzgeführt durch Connect; UI zeigt Thesis und Contradictions im Research-Intelligence-Panel.

3. **Fact-Check in Ledger/Gate (Phase 1 Worldclass Verify)** ✅  
   - fact_check mit claim_ledger abgeglichen: disputed → disputed-Flag; **confirmed** → Tier-Bonus (AUTHORITATIVE mit 1 Quelle wenn fact_check confirmed).  
   - **Effekt:** Weniger „falsch als verified“; UI zeigt Fact-Check-Summary (confirmed/disputed/unverifiable) und Claim-Ledger-Summary im Research-Intelligence-Panel.

### Stufe 2 — Durchgängigkeit (2–6 Wochen)

4. **Entity-Graph in Verify und Synthesize (Phase 2 Worldclass Connect)**  
   - Graph als Projekt-Artefakt exportieren (z. B. connect/entity_graph.json).  
   - Verify: Claim-Entity-Zuordnung, Priorisierung nach Thesis-Entitäten.  
   - Synthesize: Struktur/Narrative entlang Entitäten/Relationen (get_entities, get_entity_relations).  
   - **Effekt:** Connect wird zur echten Schaltstelle; Novelität durch durchgängigen Graph.

5. **Evidence-Spans/Snippets in Verify (Phase 1 Worldclass Verify)**  
   - claim_ledger/claim_evidence_map: pro Claim `supporting_evidence: [{ url, snippet, source_id }]` aus Findings befüllen; Schema vereinheitlichen.  
   - **Effekt:** Nachvollziehbarkeit und bessere Basis für Synthesize/Attribution.

6. **Source Credibility gewichtet (Phase 2 Worldclass Verify)**  
   - source_reliability um domain_tier/recency_score erweitern; in build_claim_ledger credibility_weight oder Tiers pro Claim.  
   - **Effekt:** Differenzierte Bewertung statt nur 0.6-Cutoff.

### Stufe 3 — SOTA-Absicherung (6–12 Wochen)

7. **CoVe als Standard-Option**  
   - CoVe-ähnlicher Pfad (Verifikationsfragen → unabhängige Prüfung → Revision) als Standard für claim_verification wo sinnvoll; Flag behalten für Rollback.  
   - **Effekt:** Weniger Halluzination bei Claims; Alignment mit Literatur.

8. **Synthesize: Semantische Relevanz + optional Factuality-Guard**  
   - Semantische (oder Hybrid-) Relevanz für Findings-Auswahl pro Section flächendeckend nutzbar (nicht nur optional).  
   - Optional: Post-Generation-Pass (Zahlen/Zitate vs. Ledger/Findings).  
   - **Effekt:** Bessere Report-Qualität und Factuality.

9. **Full AEM Test- und CI-Matrix**  
   - Alle FULL_AEM_TEST_PLAN-Punkte in automatisierte Tests überführen; CI (z. B. quality-gates) erweitern; Adversarial/Regressionen abdecken.  
   - **Effekt:** Kein Regress; AEM bleibt „100 %-sicher“ im Sinne der Spec.

### Stufe 4 — Novel & Differenzierung (ongoing)

10. **Contradiction → Hypothesis + Claim-first Contradiction**  
    - Widersprüche als Input für hypothesis_formation; thesis mit alternatives + uncertainty.  
    - Zwei Stufen: Claim-Extraktion, dann Paarvergleich.  
    - **Effekt:** Stärkere Connect-Phase; klarere „Position A vs B“.

11. **Span-Attribution & konfigurierbare Report-Struktur**  
    - Satz-/Span-Level Attribution wo sinnvoll; konfigurierbares Section-Schema aus Playbook/Config.  
    - **Effekt:** Maximale Nachvollziehbarkeit und Automatisierbarkeit.

12. **Kalibrierung und Self-Model**  
    - Kalibrierte Schwellen überall dort nutzen, wo Gate/Quality entscheidet; Self-Model (Pass-Rate pro Domain, beste Strategy, fail_codes) für Brain und Explainability.  
    - **Effekt:** System lernt und passt Schwellen an; echte „Intelligence per Token“.

---

## 5. Metriken: Wann ist „absolut SOTA“ erreicht?

- **Pipeline:** Alle Worldclass-Plan-Phasen (Verify Phase 1+2, Connect Phase 1+2, Synthesize Phase 1) **umgesetzt** und in Doku/Code abgebildet.
- **AEM:** Full AEM Test-Matrix grün; Enforcement-Modi und Synthesis Contract in Produktion getestet; keine stillen Bypässe.
- **Token Governor:** Default an; in Verify, Synthesize, Critic genutzt; Metrik „IntelligencePerToken“ oder Proxy (z. B. quality_score / token_budget) getrackt.
- **Connect→Verify→Synthesize:** thesis, contradictions, Entity-Graph in Verify und Synthesize **nachweisbar** genutzt (Artefakte, Logs, Doku).
- **Qualität:** claim_support_rate, critic_score, evidence_gate pass_rate, unsupported_claim_rate innerhalb der SLO-Ziele (RESEARCH_QUALITY_SLO); keine Regression über 20 Runs.
- **Novel:** Mindestens eine klare Differenzierung beschreibbar (z. B. „AEM + durchgängiger Claim–Evidence–Graph + Intelligence-per-Token in einer Pipeline“) mit Referenz zu Design-Docs und Tests.

---

## 6. Referenzen

- **Pläne:** VERIFY_PHASE_WORLDCLASS_PLAN.md, CONNECT_PHASE_WORLDCLASS_PLAN.md, SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md, MEMORY_BRAIN_WORLDCLASS_PLAN.md  
- **AEM:** Full_AEM_Implementation_Spec.md, FULL_AEM_TEST_PLAN.md, FULL_AEM_COMPLIANCE_REPORT.md, INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md  
- **Qualität:** RESEARCH_QUALITY_SLO.md, research_calibrator.py, research_quality_gate.py  
- **Tools:** TOOL_AGENT_SYSTEM_AUDIT.md, core-10-tool-integration.plan.md  

Damit ist der Anspruch „beste, klügste, SOTA, novel“ **architektonisch und planerisch** eingelöst; die **Implementierung** braucht die gezielte Abarbeitung der oben priorisierten Lücken und die Aktivierung der bereits vorhandenen Bausteine (Token Governor, Connect→Verify, Fact-Check, Graph).
