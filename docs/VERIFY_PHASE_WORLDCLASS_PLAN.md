# Verify-Phase — Plan: Weltklasse SOTA/Novel

Wie Claim Verification, Fact-Checking und Evidence Gates in Forschung und SOTA-Systemen funktionieren, wo wir stehen, und wie wir die Verify-Phase auf Weltklasse-Niveau bringen. Baut auf [VERIFY_PHASE_DEEP_DIVE.md](VERIFY_PHASE_DEEP_DIVE.md) auf.

**100 %-Sicherheit (Definition in diesem Dokument):** „100 % sicher“ heißt hier: Die **Erfolgsbedingungen aus der Forschung** (CoVe, Evidence-based Fact-Checking, Gates mit Kalibrierung, Recovery/Loop-back) sind **vollständig spezifiziert** und in einer **Checkliste (Teil D2)** abbildbar. Wenn der Code **alle neun Checklisten-Punkte** erfüllt, ist die Umsetzung **erfolgssicher** im Sinne der zitierten Literatur — d. h. die Voraussetzungen, unter denen die Forschung Verbesserung und Konvergenz nachweist, sind erfüllt. Das ist **nicht** die Garantie „kein einziger Bug in Produktion“, sondern die Garantie: **Kein fehlender Baustein, keine Abkürzung an den spezifizierten Stellen** — damit die Implementierung theorie- und empiriegestützt zum Erfolg führen kann.

---

## Leitbild: Evidenzbasierte Pass/Fail-Entscheidung und nachvollziehbare Claim–Evidence-Verknüpfung

Die **Verify-Phase** soll sicherstellen, dass nur **evidenzgestützte** Research-Reports in die Synthesize gelangen. Dafür brauchen wir:

- **Klare Gates:** Eine nachvollziehbare, metrikbasierte Pass/Fail-Entscheidung (Evidence Gate) mit optionalem Loop-back (deepening) und Recovery.
- **Claim–Evidence-Verknüpfung:** Jeder zentrale Claim ist explizit mit Quellen und Evidenz-Snippets verknüpft; Verifikationsstatus (VERIFIED / AUTHORITATIVE / UNVERIFIED) ist deterministisch und dokumentiert.
- **Factuality:** Fakten (Zahlen, Daten, Namen) werden geprüft; Status (confirmed / disputed / unverifiable) fließt in Bewertung und Report ein.
- **Source Credibility:** Quellenbewertung (Domain, Autorität, Recency) wird konsequent genutzt — im Ledger, im Gate und optional im Report.
- **Transparenz:** claim_ledger, claim_evidence_map und Gate-Metriken sind die Quelle der Wahrheit für „warum Pass/Fail“ und „welche Claims sind abgesichert“.

So wird die Verify-Phase nicht zum Flaschenhals, sondern zur **Qualitätssicherung**, die Nutzer und nachgelagerte Systeme (Synthesize, Critic, Memory) verlässlich nutzen können.

---

## Teil A: SOTA/Forschung — Claim Verification, Fact-Checking, Evidence Gates

### A.1 Claim Verification und Fact-Checking

| Ansatz | Kernidee | Relevanz für Verify |
|--------|----------|----------------------|
| **Chain-of-Verification (CoVe)** | Draft → Verifikationsfragen planen → unabhängig beantworten → Revision. Reduziert Halluzinationen bei generierten Claims (ACL 2024 Findings). | Claim-Extraktion in Batches um „Verifikationsfragen“ pro Claim erweitern; unabhängige Prüfung gegen Findings/Sources vor Finalisierung des Ledgers. |
| **Evidence-based Fact-Checking (DEFAME, VeraCT, Veracity)** | Multimodale/retrieval-basierte Evidenz-Extraktion, Source Credibility, strukturierte Reports, Attribution. | claim_verification/claim_ledger um strukturierte Evidence-Spans und Source-Credibility-Gewichtung erweitern; fact_check in einheitliches Schema integrieren. |
| **NLI / Entailment** | Natural Language Inference: Prüfung, ob ein Absatz einen Claim stützt oder widerspricht. | Optional: RAG/NLI-Schicht „Claim C ↔ Absatz A“ für präzisere supporting_evidence statt nur URL-Liste. |
| **Attribution in Explanations** | Bewertung, ob Erklärungen korrekt auf Quellen verweisen (ACL/NAACL 2025). | claim_evidence_map und Report-Tags (VERIFIED/AUTHORITATIVE) als Attribution-Basis; Snippets pro Claim für Nachvollziehbarkeit. |

### A.2 Evidence Gates und Source Credibility

- **Gates:** Klare Schwellen (findings, sources, verified_claim_count, claim_support_rate, high_reliability_ratio) mit research_mode-spezifischer Logik (standard / frontier / discovery) — bereits umgesetzt; SOTA wäre **kalibrierte Schwellen** aus vergangenen Runs (research_calibrator) und **domain-spezifische** Schwellen.
- **Source Credibility:** Domain-Tiers, Autorität, Recency; Gewichtung pro Claim (nicht nur 0.6 Cutoff); Integration in verification_tier (z. B. „single high-credibility source“ vs „multiple low-credibility“).
- **Loop-back und Recovery:** Begrenzte Loop-backs (z. B. max 2) mit gap-getriebenen deepening_queries; Recovery-Reads bei unread sources — bereits vorhanden; SOTA: strukturierte Gaps (priority, reason) und „targeted verification queries“ (nur fehlende Evidenz nachladen).

### A.3 Drei Säulen eines weltklassen Verify-Systems

1. **Strukturierte Claim–Evidence-Verknüpfung**  
   Pro Claim: Evidence-Spans (Snippet/Passage-IDs), Source-IDs, Stärke (supporting / contradicting). Ein einheitliches Schema für claim_verification, claim_ledger und claim_evidence_map; fact_check als „Fakten-Layer“ integriert.

2. **Source-Credibility durchgängig**  
   Von source_reliability über claim_ledger (reliable_sources, authoritative) bis Gate (high_reliability_source_ratio) und optional Report („primary source“, „secondary“). Gewichtete Scores pro Claim wo sinnvoll.

3. **Verifikations-Pipeline mit CoVe-ähnlicher Strenge**  
   Claims extrahieren → Verifikationsfragen formulieren → gegen Findings/Sources prüfen (evtl. NLI/RAG) → Revision/Finalisierung. Reduziert „falsch als verified“ und verbessert claim_support_rate.

---

## Teil B: Ist-Zustand (Brücke zum Code)

- **Pipeline:** source_reliability → claim_verification → fact_check → claim_ledger; Artefakte in `verify/`; Evidence Gate liest verify/ + findings/ + sources/ + read_stats; bei Fail: gap_analysis → deepening_queries → Loop-back zu Focus oder Block.
- **Claim–Evidence:** claim_verification liefert „supporting_sources“ (URLs); claim_ledger baut daraus verification_tier/is_verified; claim_evidence_map wird erst in Synthesize aus claim_ledger + findings gebaut. Keine Evidence-Spans/Snippets in der Verify-Phase selbst.
- **fact_check:** Wird erzeugt, aber nicht in Gate, Ledger oder Report-Tagging genutzt.
- **Source Credibility:** source_reliability fließt in Ledger (reliable ≥ 0.6) und in high_reliability_source_ratio; keine feinkörnige Gewichtung pro Claim.
- **Gaps/Recovery:** gap_analysis nur bei Fail; deepening_queries einfache String-Liste; Recovery einmal pro Verify-Durchlauf.
- **Critic:** Läuft nach Synthesize (Report-Qualität), nicht als „Evidenz-Critique“ vor Synthesize.

Siehe [VERIFY_PHASE_DEEP_DIVE.md](VERIFY_PHASE_DEEP_DIVE.md) für Datenfluss, Schemata und Lücken-Tabelle.

---

## Teil C: Ziele (Weltklasse SOTA/Novel)

- **Claim–Evidence strukturiert:** Einheitliches Schema mit Evidence-Spans/Snippets pro Claim; claim_evidence_map-äquivalent bereits nach Verify verfügbar (oder nahtlos aus Ledger + Findings ableitbar); RAG/NLI-Option für präzisere Stützung.
- **Fact-Check integriert:** fact_check-Fakten mit claim_ledger/Claims abgleichen; einheitlicher Status (confirmed/disputed/unverifiable); Nutzung im Gate oder Report-Tagging (z. B. nur confirmed als VERIFIED).
- **Source-Credibility gewichtet:** Pro-Quelle-Score (Domain, Autorität, Recency) durchgängig; gewichteter Claim-Score oder Tiers („primary“, „secondary“, „low-confidence“); Gate optional mit credibility-weighted verified count.
- **CoVe-ähnliche Verifikation:** Nach Claim-Extraktion: Verifikationsfragen pro Claim → unabhängige Prüfung gegen Material → Revision des Ledgers; weniger falsch-positive „verified“.
- **Evidenz-Critique vor Synthesize (optional):** Kurzer Schritt „fehlende Evidenz für Kernthesen / Widersprüche“ → Ausgabe als deepening_queries oder Warnung; Loop-back oder Nutzer-Hinweis.
- **Transparenz und Metriken:** Pass-Rate, claim_support_rate, Revision-Runden, Anteil VERIFIED/AUTHORITATIVE/UNVERIFIED; Docs und UI synchron mit Code.

---

## Teil D: Phasierter Plan (konkret umsetzbar)

### Phase 1: Fact-Check integrieren und Claim–Evidence-Schema vereinheitlichen

**Ziel:** fact_check in die Bewertung einbinden; ein einheitliches Claim–Evidence-Schema für Ledger und claim_evidence_map (Snippets pro Claim).

- **Code/Schema:**  
  - fact_check-Fakten mit claim_ledger-Claims abgleichen (Text-Similarity oder LLM-Match); Claims, die einem „confirmed“ Fact entsprechen, können Tier-Bonus erhalten; „disputed“ Facts führen zu disputed-Flag im Ledger.  
  - claim_ledger/claim_evidence_map: pro Claim `supporting_evidence: [{ "url", "snippet", "source_id" }]` aus Findings befüllen; Build-Schritt in Verify (nach claim_ledger) oder in Synthesize beibehalten, aber Schema vereinheitlichen und in Verify lesbar machen.
- **Abnahme:** fact_check wird in Dokumentation und optional in Gate/Ledger genutzt; claim_evidence_map-Schema hat Snippets, Verify-Artefakte sind konsistent.
- **Risiko:** Niedrig.

---

### Phase 2: Source-Credibility gewichtet und durchgängig

**Ziel:** Credibility-Score pro Quelle (nicht nur 0.6 Cutoff); gewichteter Beitrag zum verification_tier oder neues Feld „credibility_weight“ pro Claim.

- **Code/Schema:**  
  - source_reliability um optionale Felder erweitern (domain_tier, recency_score); in build_claim_ledger: gewichteter Score pro Claim (z. B. Durchschnitt reliability der supporting_sources) oder Tiers (alle high / mixed / low).  
  - Gate: optional high_reliability_source_ratio durch „credibility-weighted verified claims“ ergänzen oder Schwellen kalibrierbar halten.
- **Abnahme:** Ledger und Gate nutzen durchgängig Source-Credibility; Dokumentation und RESEARCH_QUALITY_SLO angepasst.
- **Risiko:** Niedrig.

---

### Phase 3: CoVe-ähnliche Verifikation (Verifikationsfragen + Revision)

**Ziel:** Nach Claim-Extraktion: für jeden (oder Top-K) Claim Verifikationsfragen generieren; unabhängig gegen Findings/Sources beantworten; Ledger-Revision (verified nur bei bestätigter Evidenz).

- **Code:**  
  - Neuer Schritt in research_verify.py (z. B. `claim_verification_cove` oder erweiterte claim_verification): Pro Batch nach Extraktion → LLM „Verifikationsfragen“ zu jedem Claim → zweiter LLM-Call mit nur Findings/Sources (ohne ursprünglichen Claim-Text) → Antworten mit Claim abgleichen → verified/supporting_sources aktualisieren.  
  - Optional: NLI/RAG-Modul für „Absatz stützt Claim“ statt nur LLM.
- **Abnahme:** claim_support_rate und verified_claim_count messbar konservativer (weniger falsch-positive verified); Tests mit festen Fixtures.
- **Risiko:** Mittel (Laufzeit, Kosten); Feature-Flag oder Batch-Limit (nur Top-N Claims).

---

### Phase 4: Evidenz-Critique vor Synthesize (optional) und Gaps strukturiert

**Ziel:** Optionaler Schritt nach Evidence Gate Pass (oder immer nach claim_ledger): „Fehlende Evidenz für Kernthesen / Widersprüche“; Ausgabe als strukturierte deepening_queries (reason, priority) oder Warnung. Gaps-Schema erweitern.

- **Code:**  
  - Optionaler Aufruf (z. B. research_verify.py evidence_critique oder research_reason.py evidence_gaps): Input claim_ledger + findings + question; Output: under_sourced_claims[], contradictions[], suggested_queries[].  
  - deepening_queries.json um reason/priority pro Query erweitern; Focus merged wie bisher, kann reason für Logging/UI nutzen.
- **Abnahme:** Bei aktiviertem Schritt: Ausgabe in verify/; deepening_queries hat strukturierte Einträge; Doku aktualisiert.
- **Risiko:** Niedrig.

---

### Phase 5: Kalibrierung und Metriken (Betrieb)

**Ziel:** Schwellen aus vergangenen Runs (research_calibrator); Metriken (Pass-Rate, claim_support_rate, Revision-Runden) in RESEARCH_QUALITY_SLO und ggf. run_episodes/UI.

- **Code:** research_calibrator bereits erwähnt in research_quality_gate.py; sicherstellen, dass Evidence-Gate-Metriken und Pass/Fail in Kalibrierung einfließen. Metriken in RESEARCH_QUALITY_SLO und VERIFY-PHASE-Docs dokumentieren.
- **Abnahme:** Schwellen dokumentiert; Pass-Rate und claim_support_rate als SLO-Ziele geführt.
- **Risiko:** Niedrig.

---

## Teil D2: 100 % Umsetzung — Erfolgsbedingungen und Garantien (forschungssicher)

Wenn die Umsetzung nicht garantierbar ist, war die Forschung unvollständig. Die Literatur liefert **konkrete Bedingungen**, unter denen Verify-Systeme **empirisch weniger Halluzinationen** und **bessere Verifikationsqualität** liefern. Wenn wir diese Bedingungen **vollständig umsetzen**, ist die Umsetzung zu 100 % spezifiziert und erfolgssicher.

### Was die Forschung garantiert (und was wir daraus ableiten)

**1. Chain-of-Verification (CoVe) — Dhuliawala et al., ACL 2024 Findings**  
- Vier Schritte: (i) Draft (Claims/Response), (ii) **Verifikationsfragen planen** zu jedem Claim, (iii) **Fragen unabhängig beantworten** (ohne Draft-Context, um Bias zu vermeiden), (iv) **Finale Antwort/Ledger** aus den Verifikationsantworten ableiten.  
- Empirisch: **CoVe verringert Halluzinationen** bei Listenfragen, MultiSpanQA und Longform-Generierung.  
- Entscheidend: Unabhängige Beantwortung (Schritt iii) verhindert, dass das Modell den eigenen Draft „bestätigt“; nur Evidenz aus dem Material zählt.

**→ Umsetzungspflicht:**  
- Nach Claim-Extraktion: **Verifikationsfragen** pro Claim generieren (Phase 3).  
- **Unabhängige Prüfung:** Zweiter LLM-Call (oder NLI/RAG) mit **nur** Findings/Sources-Text, **ohne** ursprünglichen Claim-Text im gleichen Kontext; Antworten dann mit Claim abgleichen.  
- Ledger-Revision: `verified` / `supporting_sources` nur setzen, wenn die unabhängige Prüfung den Claim stützt.  
- Fallback: Wenn CoVe-Schritt fehlschlägt (Timeout, leerer Output), **kein Upgrade** des Claims auf verified — bestehender Ledger-Status bleibt oder wird auf UNVERIFIED gesetzt (fail-safe).

**2. Evidence-based Fact-Checking (Evidenz vs. Relevanz)**  
- Literatur (+VeriRel, RAVE, Ev2R): Die Unterscheidung **relevant vs. evidential** ist zentral — „relevant“ reicht nicht; Dokumente müssen den Claim **tatsächlich stützen**.  
- Verification Feedback (Erfolg der Verifikation) in Bewertung einbeziehen verbessert Downstream-Performance.  
- Strukturierte Signale (Source Credibility, Retrieval-Score) verbessern Precision/Recall bei Claim-Erkennung und Verifikation.

**→ Umsetzungspflicht:**  
- **fact_check** und **claim_ledger** nutzen dieselbe Evidenzbasis (Findings/Sources); fact_check-Status (confirmed/disputed/unverifiable) wird mit Claims abgeglichen und fließt in Ledger oder Gate ein (Phase 1).  
- **Source Credibility** durchgängig: nicht nur 0.6-Cutoff, sondern gewichteter Score pro Claim; Gate und Ledger lesen source_reliability (Phase 2).  
- **Supporting Evidence:** Pro Claim mindestens supporting_source_ids; optional supporting_evidence (Snippets) aus Findings, damit „evidential“ prüfbar ist (Phase 1).

**3. Evidence Gates mit Schwellen und Kalibrierung**  
- Gate-Entscheidung nur auf **beobachtbaren Metriken** (findings_count, unique_source_count, verified_claim_count, claim_support_rate, high_reliability_source_ratio, read_stats).  
- Kalibrierung aus vergangenen erfolgreichen Runs (z. B. p25 der Metriken als Schwellen mit Floor) verbessert Pass-Rate ohne Qualitätsverlust (research_calibrator).

**→ Umsetzungspflicht:**  
- Gate liest **ausschließlich** aus Projektdateien (verify/, findings/, sources/, read_stats); keine versteckten Inputs (bereits so in research_quality_gate.py).  
- Schwellen: EVIDENCE_GATE_THRESHOLDS + get_calibrated_thresholds() bei ≥10 erfolgreichen Outcomes; FLOOR in research_calibrator wird nie unterschritten.  
- research_mode (standard / frontier / discovery) mit dokumentierter Logik (_decide_gate, _decide_gate_frontier, _decide_gate_discovery); keine Ad-hoc-Änderung ohne Doku-Update.

**4. Recovery und Loop-back (begrenzt)**  
- Systeme, die bei Fehlern **Recovery** auslösen und Ergebnis in den nächsten Schritt einspeisen, sind robuster.  
- Loop-back muss **begrenzt** sein (max 2 Focus), sonst Endlosschleife; deepening_queries müssen von Focus **deterministisch** gelesen und gemerged werden.

**→ Umsetzungspflicht:**  
- Recovery: genau **ein** Versuch pro Verify-Durchlauf (.recovery_attempted); danach nur noch Gap-Analysis/Loop-back oder Fail.  
- Loop-back: nur wenn phase_history.count("focus") < 2 und high-priority Gaps und suggested_search nicht leer; deepening_queries.json Format dokumentiert; Focus merged in FOCUS_PHASE_DEEP_DIVE und research-cycle.sh beschrieben.  
- AEM/block_synthesize: nach Gate Pass; dokumentiert in RESEARCH_QUALITY_SLO und VERIFY_PHASE_DEEP_DIVE.

**5. Attribution und Nachvollziehbarkeit**  
- claim_evidence_map (report_id, claims mit supporting_evidence/Snippets) und Report-Tags [VERIFIED:claim_id] / [AUTHORITATIVE:claim_id] ermöglichen Nachvollzug und Zitation.  
- Synthesize liest Claims **nur** aus get_claims_for_synthesis (AEM ledger oder verify/claim_ledger.json); keine neu erfundenen Claims im Report.

**→ Umsetzungspflicht:**  
- get_claims_for_synthesis(proj_path): zuerst claims/ledger.jsonl, sonst verify/claim_ledger.json; nie leere Liste „erfinden“.  
- apply_verified_tags_to_report(report, claims) nutzt nur die übergebene Claim-Liste; Tags nur für verification_tier VERIFIED/AUTHORITATIVE.  
- claim_evidence_map wird aus claim_ledger + findings/sources gebaut (Synthesize); Schema mit supporting_evidence (url, snippet) ist verbindlich.

### Checkliste: Wenn diese Punkte erfüllt sind, ist die Umsetzung „100 %“ (theorie- und empiriegestützt)

| Nr. | Bedingung | Wo im Plan / im Code |
|-----|-----------|------------------------|
| 1 | Evidence Gate liest nur Findings, Sources, verify/claim_ledger (bzw. claim_verification Fallback), source_reliability, read_stats; keine versteckten Inputs. | research_quality_gate.py; VERIFY_PHASE_DEEP_DIVE. |
| 2 | Jeder Claim im Ledger hat supporting_source_ids; optional supporting_evidence (Snippets) aus Findings; claim_evidence_map-Schema einheitlich. | Phase 1; research-cycle.sh Synthesize-Block; research_verify.build_claim_ledger. |
| 3 | fact_check wird genutzt: Abgleich mit Claims, Status (confirmed/disputed) fließt in Ledger oder Gate ein; nicht nur erzeugt und ignoriert. | Phase 1: build_claim_ledger oder _metrics_* in quality_gate. |
| 4 | Source Credibility durchgängig: source_reliability in Ledger (reliable_sources, ggf. gewichteter Score), Gate (high_reliability_source_ratio), optional Report. | Phase 2; research_verify.build_claim_ledger; research_quality_gate._metrics_reliability. |
| 5 | CoVe-ähnlicher Schritt: Verifikationsfragen pro Claim → unabhängige Prüfung (nur Findings/Sources) → Ledger-Revision; bei Fehler/Timeout Fallback: kein Upgrade auf verified. | Phase 3; research_verify.py (claim_verification_cove oder erweiterte claim_verification); Feature-Flag/Batch-Limit erlaubt. |
| 6 | Recovery genau einmal pro Verify (.recovery_attempted); Loop-back max 2× Focus; deepening_queries Format und Merge in Focus dokumentiert. | research-cycle.sh; FOCUS_PHASE_DEEP_DIVE; VERIFY_PHASE_DEEP_DIVE. |
| 7 | Synthesize nutzt nur get_claims_for_synthesis; apply_verified_tags_to_report nur mit dieser Liste; claim_evidence_map aus Ledger + Findings gebaut. | research_common.get_claims_for_synthesis; research_synthesize; research-cycle.sh. |
| 8 | Schwellen: EVIDENCE_GATE_THRESHOLDS + get_calibrated_thresholds (≥10 Outcomes), FLOOR eingehalten; research_mode-Logik dokumentiert. | research_quality_gate.py; research_calibrator.py; RESEARCH_QUALITY_SLO. |
| 9 | AEM/block_synthesize und pending_review in Docs; Code = Quelle der Wahrheit. | RESEARCH_QUALITY_SLO; UI_OVERVIEW; VERIFY_PHASE_DEEP_DIVE. |

Wenn **alle neun Punkte** in der Implementierung erfüllt sind, erfüllt die Verify-Phase die **Erfolgsbedingungen** aus CoVe (unabhängige Verifikation, weniger Halluzinationen), Evidence-based Fact-Checking (Evidenz vs. Relevanz, Source Credibility), Gates mit Kalibrierung und Recovery/Loop-back. Dann ist die Umsetzung **vollständig spezifiziert** und **erfolgssicher** im Sinne der aktuellen Forschung — also **100 % umsetzbar und zum Erfolg führend**, sofern der Code diese Checkliste erfüllt.

### Garantie-Formulierung (klar und ehrlich)

- **Garantie (empiriegestützt):** CoVe (ACL 2024 Findings) zeigt, dass **Draft → Verifikationsfragen → unabhängige Beantwortung → Revision** Halluzinationen signifikant reduziert. Wenn wir diesen Ablauf in der Verify-Phase abbilden (Phase 3) und bei Fehlern fail-safe (kein Upgrade auf verified) handeln, **reduzieren wir falsch-positive Verified-Claims**.  
- **Garantie (empiriegestützt):** Evidence-based Fact-Checking-Systeme zeigen, dass **Evidenz vs. Relevanz** und **Source Credibility** die Verifikationsqualität verbessern. Wenn fact_check in Ledger/Gate integriert ist (Phase 1) und Source Credibility durchgängig genutzt wird (Phase 2), **verbessern wir Precision/Recall der Pass/Fail-Entscheidung**.  
- **Garantie (theoriegestützt):** Gates, die nur auf beobachtbaren Metriken und kalibrierten Schwellen basieren, sind **deterministisch nachvollziehbar**; Recovery und begrenztes Loop-back erhalten **Konvergenz** (kein Endlosschleife).  
- **Was wir also garantieren können:** Wenn wir die **gesamte** Checkliste (alle 9 Punkte) **genau so** umsetzen — CoVe-ähnliche unabhängige Verifikation, fact_check integriert, Source Credibility durchgängig, Gate nur auf Metriken, Recovery/Loop-back begrenzt, Synthesize nur get_claims_for_synthesis — dann erfüllt die Verify-Phase die **Erfolgsbedingungen**, unter denen die Forschung Verbesserung nachweist. **100 % Umsetzung** heißt: Kein fehlender Baustein an diesen Stellen, keine Abkürzung (z. B. fact_check ignorieren oder Gate mit versteckten Inputs) — und damit **erfolgssicher** nach aktuellem Forschungsstand.

### SOTA- und Novel-Einordnung (präzise)

- **SOTA (Literatur-Referenz):** CoVe (Dhuliawala et al. 2024); Evidence-based Fact-Checking mit Evidenz/Relevanz und Source Credibility (+VeriRel, RAVE, DEFAME/Veracity-ähnliche Ideen); kalibrierte Schwellen aus Outcomes (research_calibrator).  
- **Novel (Kombination in dieser Pipeline):** Die **Verknüpfung** von Evidence Gate + begrenztem Loop-back (deepening_queries) + claim_ledger + AEM-Option + Synthesize-get_claims_for_synthesis in einer einzigen Research-Pipeline ist in dieser Form dokumentiert und umgesetzt; CoVe-ähnlicher Schritt **nach** batched claim_verification und **vor** build_claim_ledger ist eine konkrete Implementierungsentscheidung, die die Literatur nicht vorschreibt, aber die CoVe-Idee auf Claim-Ledger anwendet.  
- **Nicht behauptet:** Dass jedes Detail (z. B. 0.6-Cutoff, HARD_PASS_VERIFIED_MIN=5) aus einer einzelnen Paper stammt; diese Werte sind **kalibrierbar** und über FLOOR/get_calibrated_thresholds abgesichert.

---

## Implementierungsspezifikation (deterministische Fallbacks, testbare Abnahme)

Damit „voll funktionsfähig“ **testbar** ist, gelten pro Phase folgende **Abnahme- und Fallback-Regeln**:

- **Phase 1 (Fact-Check + Schema):**  
  - fact_check-Fakten mit Claims abgleichen: Text-Similarity (z. B. Jaccard auf Token) ≥ 0.4 oder optional LLM-Match; bei Match: confirmed → Claim behält/bekommt Tier; disputed → disputed-Flag im Ledger. **Fallback:** Kein fact_check.json oder leer → Ledger unverändert (keine Herabstufung).  
  - supporting_evidence: Aus findings/*.json pro supporting_source_id excerpt[:500] oder title+description; **Fallback:** Fehlende Snippet → url + leerer snippet.  
  - **Abnahme-Test:** Fixture mit claim_ledger + fact_check; erwarteter Ledger-Output (disputed gesetzt wo fact disputed); claim_evidence_map enthält supporting_evidence mit Snippets.

- **Phase 2 (Source Credibility):**  
  - Gewichteter Score pro Claim = Durchschnitt reliability_score der supporting_sources (default 0.5 pro unbekannter URL). **Fallback:** source_reliability.json fehlt → alle URLs 0.5; Ledger-Logik unverändert (distinct_reliable wie heute).  
  - **Abnahme-Test:** Gate und Ledger mit/ohne source_reliability; Schwellen und Tiers wie dokumentiert.

- **Phase 3 (CoVe):**  
  - Verifikationsfragen: 1–3 Fragen pro Claim (LLM); unabhängiger Call: nur Findings/Sources-Text, Fragenliste; Antworten mit Claim abgleichen (LLM oder Keyword-Overlap). **Fallback:** Timeout/Fehler/leer → Claim bleibt UNVERIFIED oder wird auf UNVERIFIED gesetzt (nie Upgrade auf VERIFIED). Batch-Limit (z. B. Top-20 Claims) und Feature-Flag RESEARCH_ENABLE_COVE_VERIFICATION=1.  
  - **Abnahme-Test:** Fixture: 2 Claims, einer stützbar aus Findings, einer nicht; erwarteter Ledger: nur erster verified nach CoVe.

- **Phase 4 (Evidenz-Critique + Gaps):**  
  - evidence_critique/evidence_gaps: Output unter verify/; deepening_queries erweitert um {"queries": [{"query": "...", "reason": "...", "priority": "high|medium|low"}]}. **Fallback:** Schritt schlägt fehl → deepening_queries unverändert (nur bei Gate Fail wie bisher).  
  - **Abnahme:** deepening_queries mit reason/priority wird von Focus gelesen; reason optional für Logging.

- **Phase 5 (Kalibrierung):**  
  - get_calibrated_thresholds() wie heute; EVIDENCE_GATE_THRESHOLDS und FLOOR in research_calibrator dokumentiert. **Abnahme:** Tests in test_research_quality_gate.py und test_research_calibrator.py grün.

---

## Teil E: Priorisierung und Metriken

| Phase | Inhalt | Aufwand | Priorität |
|-------|--------|---------|-----------|
| 1 | Fact-Check integrieren, Claim–Evidence-Schema (Snippets) | 1–2 Tage | Hoch |
| 2 | Source-Credibility gewichtet, durchgängig | 1 Tag | Hoch |
| 3 | CoVe-ähnliche Verifikation (Verifikationsfragen + Revision) | 2–3 Tage | Mittel |
| 4 | Evidenz-Critique optional, Gaps strukturiert | 1 Tag | Mittel |
| 5 | Kalibrierung, Metriken, Docs | 0.5–1 Tag | Hoch (Betrieb) |

**Metriken (Erfolg messen):**

- **Pass-Rate Evidence Gate:** Anteil Runs, die Evidence Gate passieren (pro Domain/Modus).
- **claim_support_rate:** Mittelwert über Projekte; Ziel ≥ 0.5 (vgl. RESEARCH_QUALITY_SLO).
- **verified_claim_count:** Verteilung; Ziel mind. 2 (Standard), 5 für HARD_PASS.
- **Revision-Runden (Synthesize):** Sinkt, wenn Verify qualitativ besser vorfiltert.
- **Anteil VERIFIED vs UNVERIFIED im Ledger:** Mehr VERIFIED bei gleicher Pass-Rate = bessere Nutzung der Evidenz.

---

Dieser Plan baut auf VERIFY_PHASE_DEEP_DIVE.md auf und soll bei Änderungen an der Verify-Phase, am Evidence Gate und an zugehörigen Docs (UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK) mitgeführt werden.
