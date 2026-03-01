# Verify-Phase — Tiefenanalyse

Vollständige technische Analyse: Datenfluss, Schemata, Gate-Logik, Lücken und SOTA/Novel-Möglichkeiten. Quelle der Wahrheit: `research-cycle.sh` (verify-Branch), `research_verify.py`, `research_quality_gate.py`, `research_critic.py`, `research_reason.py` (gap_analysis).

---

## Teil 1: Datenfluss der Verify-Phase

### 1.1 Eingang

- **Nach Connect.** Verfügbar: `findings/`, `sources/`, `project.json` (question, domain, config, phase_history), ggf. Connect-Artefakte. Keine `thesis.json`/`contradictions.json`/`hypotheses.json` als direkte Inputs der Verify-Subcommands; diese liegen ggf. im Projekt, werden von Verify nicht zwingend gelesen.

### 1.2 Reihenfolge der Subcommands und Persistierung

| Schritt | Tool/Subcommand | Input | Output (Artefakt) | Persistiert nach |
|--------|-----------------|-------|-------------------|------------------|
| 1 | `research_verify.py … source_reliability` | project.json, sources/*.json | source_reliability.json | `$ART/` → `$PROJ_DIR/verify/` (wenn non-empty) |
| 2 | `research_verify.py … claim_verification` | project.json, findings/*.json, sources (metadata) | claim_verification.json | `$ART/` → `$PROJ_DIR/verify/` |
| 3 | `research_verify.py … fact_check` | project.json, findings | fact_check.json | `$ART/` → `$PROJ_DIR/verify/` |
| 4 | (optional) `research_verify.py … claim_verification_cove` | verify/claim_verification.json, findings | cove_overlay.json | `$PROJ_DIR/verify/` (nur bei RESEARCH_ENABLE_COVE_VERIFICATION=1) |
| 5 | `research_verify.py … claim_ledger` | verify/claim_verification.json, verify/source_reliability.json, verify/fact_check.json, verify/cove_overlay.json (optional), project.json | claim_ledger.json | `$ART/` → `$PROJ_DIR/verify/` |

Danach (optional, Feature-Flags):

- **Claim State Machine** (`RESEARCH_ENABLE_CLAIM_STATE_MACHINE=1`): `research_claim_state_machine.py upgrade`
- **Contradiction Linking** (`RESEARCH_ENABLE_CONTRADICTION_LINKING=1`): `research_contradiction_linking.py run`
- **Falsification Gate** (`RESEARCH_ENABLE_FALSIFICATION_GATE=1`): `research_falsification_gate.py run`
- **Counter-Evidence:** Inline-Python in research-cycle.sh: Suchanfragen für Top-3 verified claims (disputed/criticism), schreibt `counter_search_*.json`, merged neue Quellen in `sources/`, liest bis zu 9 URLs mit `research_parallel_reader.py counter`, dann `research_reason.py contradiction_detection` → `contradictions.json`.

### 1.3 Evidence Gate und Einfluss der Artefakte

- **Evidence Gate:** `research_quality_gate.py <project_id>`. Liest ausschließlich aus Projektdateien:
  - **Findings/Sources:** `findings/*.json`, `sources/*.json` (Anzahlen)
  - **Read-Statistik:** `explore/read_stats.json`, `focus/read_stats.json` (read_attempts, read_successes, read_failures)
  - **Verify-Artefakte:** `verify/source_reliability.json`, `verify/claim_ledger.json` (bzw. claim_verification.json als Fallback für claims)
- **Metriken:** findings_count, unique_source_count, verified_claim_count, claim_support_rate, high_reliability_source_ratio, read_attempts/successes/failures. Entscheidung: pass | pending_review | fail; bei fail → fail_code (z. B. failed_verification_inconclusive, failed_insufficient_evidence).
- **Critic** läuft **nicht** in der Verify-Phase, sondern in der **Synthesize-Phase** nach Report-Erstellung (`research_critic.py … critique`). Die Verify-Phase endet mit dem Evidence Gate; bei Pass fließt nur die Gate-Entscheidung und die Metriken in project.json.

### 1.4 Gap Analysis und Loop-back

- Bei **Gate Fail** (decision == "fail", nicht pending_review):  
  `research_reason.py … gap_analysis` → Ausgabe nach `$ART/gaps_verify.json` (nicht nach `$PROJ_DIR/verify/`).
- **Loop-Check (LOOPCHECK):** Liest `gaps_verify.json` (gaps[].priority, suggested_search, description). Wenn **high-priority Gaps** vorhanden und `phase_history.count("focus") < 2` und es suggested_search-Queries gibt → schreibt `$PROJ_DIR/verify/deepening_queries.json` (Format: `{"queries": [{"query": "...", "reason": "...", "priority": "high|medium|low"}]}`) und setzt LOOP_BACK=1.
- Bei LOOP_BACK=1: `advance_phase "focus"` und Exit 0. Beim nächsten Lauf landet die Focus-Phase; sie merged `verify/deepening_queries.json` mit Gap-Fill in `focus_queries.json` und führt Web Search + Reads aus, danach erneut Connect → Verify → Gate.

### 1.5 Recovery (ohne Loop-back)

- Wenn Gate Fail und **nicht** pending_review und **nicht** Loop-back: Zuerst **Recovery-Versuch**, falls noch unread sources existieren und `verify/.recovery_attempted` nicht existiert. Dann: unread sources ranken, bis zu 10 mit `research_parallel_reader.py recovery` lesen, danach **claim_verification** und **claim_ledger** erneut ausführen, Gate erneut prüfen. Nur ein Recovery-Durchlauf pro Verify-Durchlauf (.recovery_attempted wird gesetzt).

### 1.6 Ausgang bei Pass

- Gate Pass: `evidence_gate_result.json` in $ART; project.json wird mit quality_gate.evidence_gate (status=passed, metrics) aktualisiert; Quellen mit reliability_score < 0.3 werden in sources/*.json mit `low_reliability` markiert; `research_source_credibility.py` läuft; optional AEM Settlement (block_synthesize kann Advance blockieren); dann `advance_phase "synthesize"`.
- **claim_evidence_map** wird **nicht** in der Verify-Phase erzeugt, sondern in der **Synthesize-Phase** nach Report-Generierung (aus claim_ledger + findings/sources); Ergebnis: `reports/claim_evidence_map_{ts}.json` und `verify/claim_evidence_map_latest.json`.
- **critique.json** entsteht in Synthesize (Critic-Block), wird danach nach `$PROJ_DIR/verify/critique.json` kopiert.

---

## Teil 2: Schema und Struktur der Artefakte

### 2.1 source_reliability.json

- **Struktur:** `{"sources": [{"url": "...", "reliability_score": 0.0–1.0, "flags": ["…"], "domain_tier": "high|medium|low|unknown" (optional), "recency_score": 0.0–1.0 (optional)}]}`  
- Erzeugt von: `research_verify.py source_reliability` (LLM pro Quelle: domain trust, recency, author credibility).  
- Genutzt von: `research_quality_gate.py` (high_reliability_source_ratio: Anteil mit score ≥ 0.6), `build_claim_ledger` (reliability pro URL für VERIFIED/UNVERIFIED, **credibility_weight** pro Claim = Durchschnitt der supporting_sources).

### 2.2 claim_verification.json

- **Struktur:** `{"claims": [{"claim": "...", "supporting_sources": ["url1", "url2"], "confidence": 0.0–1.0, "verified": true|false, …}]}`  
- Erzeugt: Batched (bis 18 Findings pro LLM-Call), parallel (4 Workers), danach Merge und Dedup (normalisierter Text, Jaccard-Ähnlichkeit ≥ 0.65).  
- Genutzt von: `build_claim_ledger` (Eingabe für claim_id, text, supporting_sources, is_verified/Tier).

### 2.3 fact_check.json

- **Struktur:** `{"facts": [{"statement": "...", "verification_status": "confirmed|disputed|unverifiable", "source": "…"}]}`  
- Erzeugt: Ein LLM-Call über Findings (3–10 Fakten).  
- **Aktuell nicht** in die Evidence-Gate-Entscheidung oder claim_ledger integriert; eigenständiges Artefakt für Transparenz/UI.

### 2.4 claim_ledger.json

- **Struktur:** `{"claims": [{"claim_id", "text", "supporting_source_ids", "source_finding_ids", "supporting_evidence": [{"url", "snippet", "source_id"}], "credibility_weight", "is_verified", "verification_tier", "verification_reason", "claim_support_rate", "in_contradiction"}]}`  
- **verification_tier:** VERIFIED (≥2 zuverlässige unabhängige Quellen), AUTHORITATIVE (1 autoritative Quelle), UNVERIFIED; in research_mode discovery: ESTABLISHED / EMERGING / SPECULATIVE. **CoVe:** Bei vorhandenem `cove_overlay.json` mit `cove_supports: false` wird der Claim auf UNVERIFIED gesetzt (fail-safe).  
- **Fact-Check:** Disputed Facts (fact_check.json) mit Jaccard-Ähnlichkeit ≥ 0.4 zum Claim setzen dispute → UNVERIFIED.  
- **credibility_weight:** Durchschnitt der reliability_score der supporting_sources (Phase 2).  
- Genutzt von: Evidence Gate (verified_claim_count, claim_support_rate), Synthesize (apply_verified_tags_to_report, claim_evidence_map), Report-Referenzen.

### 2.5 claim_evidence_map (verify/claim_evidence_map_latest.json)

- Erzeugt **in Synthesize**, nicht in Verify.  
- **Struktur:** `{"report_id": "report_{ts}.md", "ts": "...", "claims": [{"claim_id", "text", "is_verified", "verification_reason", "supporting_source_ids", "supporting_evidence": [{"url", "snippet"}]}]}`.  
- Dient UI und Nachvollziehbarkeit: welche Claims im Report, mit welcher Evidenz und Verifikation.

### 2.6 critique.json

- Erzeugt in **Synthesize** (Critic), dann nach `verify/critique.json` kopiert.  
- **Struktur:** score (0–1), weaknesses, suggestions, pass (bool), dimensions (coverage, depth, accuracy, novelty, coherence, citation_quality je mit score und remediation_action).  
- Nicht Teil der **Evidence Gate**-Entscheidung; Quality Gate (Report-Qualität) wird nach Synthesize mit Critic bewertet (failed_quality_gate bei score < Schwellwert).

### 2.7 Evidence-Gate-Metriken (quality_gate.evidence_gate in project.json)

- findings_count, unique_source_count, verified_claim_count, claim_support_rate, high_reliability_source_ratio, read_attempts, read_successes, read_failures.  
- Schwellen: `research_quality_gate.py` → EVIDENCE_GATE_THRESHOLDS (findings_count_min 8, unique_source_count_min 5, verified_claim_count_min 2, claim_support_rate_min 0.5, high_reliability_source_ratio_min 0.5); adaptive Floor für findings bei niedriger read success rate; research_mode (standard / frontier / discovery) ändert Entscheidungslogik (_decide_gate / _decide_gate_frontier / _decide_gate_discovery).

### 2.8 gaps_verify.json, deepening_queries.json, evidence_critique.json, cove_overlay.json

- **gaps_verify.json:** Nur in $ART. Format: `{"gaps": [{"description", "priority": "high|medium|low", "suggested_search"}]}`.  
- **deepening_queries.json:** Unter `$PROJ_DIR/verify/`. Format: `{"queries": [{"query": "...", "reason": "...", "priority": "high|medium|low"}]}` (Phase 4). Wird bei Gate Fail + high Gaps + loopback_count < 2 geschrieben; Focus merged mit gap-fill (unterstützt String- oder Objekt-Liste).  
- **evidence_critique.json:** Optional, von `research_reason.py evidence_gaps` geschrieben. Format: `{"under_sourced_claims", "contradictions", "suggested_queries": [{"query", "reason", "priority"}]}`.  
- **cove_overlay.json:** Von `research_verify.py claim_verification_cove` (RESEARCH_ENABLE_COVE_VERIFICATION=1). Format: `{"claims": [{"claim_text_prefix", "cove_supports": bool}]}`. build_claim_ledger: cove_supports false → UNVERIFIED.

---

## Teil 3: Gate-Logik — Wann Pass / Fail / Loop-back / Block

### 3.1 Evidence Gate (research_quality_gate.py)

- **Vorprüfungen:**  
  - Reader-Pipeline-Failure (sources ≥ 1, read_attempts > 0, read_successes == 0, findings_count == 0) → sofort fail, fail_code failed_reader_pipeline.  
  - findings_count < effective_findings_min oder unique_source_count < 5 → fail, failed_insufficient_evidence.
- **research_mode standard:**  
  - HARD_PASS: verified_claim_count ≥ 5 → pass.  
  - SOFT_PASS: verified_claim_count ≥ 3 und claim_support_rate ≥ 0.5 → pass.  
  - REVIEW: verified ≥ 3 und rate ≥ 0.4 → pending_review.  
  - Fail: rate < 0.3 oder verified < 3 → fail_code failed_verification_inconclusive / failed_source_diversity / failed_insufficient_evidence.
- **frontier:** Höhere Toleranz (findings/sources/reliability); authority gewichtet.  
- **discovery:** Kein verified_claim_count-Check; Pass über findings/sources-Anzahl.

### 3.2 pending_review

- Bei decision == "pending_review": Projektstatus wird auf "pending_review" gesetzt, quality_gate.evidence_gate gespeichert, Cycle beendet (exit 0). Kein Loop-back, kein Advance.

### 3.3 Loop-back (deepening_queries)

- Nur bei decision == "fail".  
- gap_analysis → gaps_verify.json.  
- Loop-Check: high-priority Gaps vorhanden, phase_history.count("focus") < 2, suggested_search nicht leer → deepening_queries.json schreiben, advance_phase "focus", exit 0.  
- Maximal 2 Loop-backs (focus höchstens zweimal erneut durchlaufen).

### 3.4 Recovery

- Bei Fail, keine pending_review: Wenn unread sources und kein .recovery_attempted → Recovery-Reads (bis 10), Re-Run claim_verification + claim_ledger, erneuter Gate-Check. Danach entweder Pass oder erneut Fail → dann gap_analysis/Loop-back oder endgültiger Fail.

### 3.5 AEM / block_synthesize

- **Nach** Evidence Gate Pass: Optional AEM Settlement (`research_aem_settlement.py`). Bei AEM_ENFORCEMENT_MODE enforce/strict und (ok false oder block_synthesize true) wird **nicht** advance_phase "synthesize" ausgeführt; Projektstatus aem_blocked, Exit 0.  
- block_synthesize kommt aus AEM (z. B. oracle_integrity_rate unter Schwellwert, deadlock).

### 3.6 advance_phase "synthesize"

- Nur wenn Gate Pass und (AEM nicht aktiv oder AEM_ADVANCE=1). Danach Phase synthesize (Report, claim_evidence_map, Critic, ggf. Revise, advance_phase "done").

---

## Teil 4: Probleme und Lücken (Tabelle)

| Bereich | Problem / Lücke | Schwere |
|--------|------------------|--------|
| Claim–Evidence-Verknüpfung | Claim-Extraktion und Support sind LLM-basiert; „supporting_sources“ sind URL-Strings, keine strukturierten Snippets/Spans pro Claim in Verify; claim_evidence_map wird erst in Synthesize aus claim_ledger + findings gebaut. | hoch |
| Fact-Check-Nutzung | fact_check.json wird erzeugt, aber weder in Evidence Gate noch in claim_ledger noch in Report-Tagging genutzt; Fakten und Claims sind getrennte Welten. | hoch |
| Source-Credibility-Nutzung | source_reliability fließt in claim_ledger (reliable_sources ≥ 0.6) und in high_reliability_source_ratio; keine explizite Gewichtung von Autor/Domain pro Claim (z. B. „diese Claim-Stütze ist peer-reviewed“). | mittel |
| Gap Analysis | gap_analysis läuft nur bei Gate Fail; Gaps werden nicht in Pass-Pfad genutzt (z. B. „welche Claims sind noch unterversorgt“). deepening_queries Format ist nur String-Liste, keine Priorität/Reason pro Query. | mittel |
| Kritik/Revise | Critic läuft nach Synthesize; bei Verify gibt es keine „Pre-Synthesize-Critique“ der Evidenzlage (z. B. Widersprüche, fehlende Quellen für Kernthesen). | mittel |
| Counter-Evidence | Counter-Suche und Widerspruchserkennung laufen, aber Ergebnis (contradictions.json) fließt nicht deterministisch in claim_ledger oder Gate ein (disputed wird in claim_ledger aus claim_verification/disputed/verification_status gelesen, nicht aus contradictions). | mittel |
| Recovery | Nur ein Recovery-Durchlauf (.recovery_attempted); keine mehrfache Iteration „read more → verify → gate“. | niedrig |
| Metriken | claim_support_rate = verified / total claims; „total“ kommt aus claim_verification/claim_ledger, nicht aus einer expliziten „alle geprüften Claims“-Liste (all_checked_sources in Ledger nur pro Claim, nicht global). | niedrig |
| Schemas | claim_verification „verified“ vs claim_ledger „is_verified“/„verification_tier“; zwei Repräsentationen, Ledger ist autoritativ, aber Verlust von Confidence/Details aus claim_verification. | niedrig |

---

## Teil 5: SOTA- und Novel-Verbesserungen (Möglichkeiten)

- **Chain-of-Verification (CoVe):** Claims generieren → separate Verifikationsfragen → gezielte Prüfung und Re-Generierung; Reduktion von Halluzinationen bei Claims.  
- **Strukturierte Claim–Evidence-Schemas:** Pro Claim: Evidence-Spans (Satz/Absatz-IDs), Source-ID, Stärke (supporting / contradicting / neutral); RAG oder NLI-Modell für „claim C wird von Absatz A gestützt“.  
- **Fact-Check-Integration:** fact_check-Fakten mit claim_ledger abgleichen; einheitliches „statement + status + sources“; Gate oder Report-Tagging nutzen (z. B. nur confirmed facts als VERIFIED markieren).  
- **Source-Credibility gewichtet:** Pro Quelle: Domain-Tier, Autorität, Recency; gewichteter Score pro Claim (nicht nur 0.6 Cutoff); Gate-Schwellen oder Ledger-Tiers davon abhängig.  
- **Pre-Synthesize Evidenz-Critique:** Optionaler Schritt nach claim_ledger: LLM oder regelbasiert „fehlende Evidenz für Kernthesen“, „Widersprüche“, „under-sourced claims“ → Ausgabe als deepening_queries oder Warnung vor Synthesize.  
- **RAG-basierte Evidenzprüfung:** Retrieval aus gespeicherten Findings/Snippets zu vorgegebenen Claims; NLI oder LLM „entailment/contradiction“; Anreicherung von claim_verification oder claim_ledger.  
- **Attribution und Zitate:** Jeder Claim im Report mit expliziten source_finding_ids und Snippets (claim_evidence_map erweitern); Export für Zitations-Checks und Plagiatsprävention.  
- **Loop-back und Gaps:** Gaps nicht nur bei Fail, sondern optional bei Pass als „Improvement-Queries“ für nächsten Run oder als Metadaten für Nutzer; strukturiertes deepening_queries (priority, reason, suggested_search).  

**Weiterführend:** [VERIFY_PHASE_WORLDCLASS_PLAN.md](VERIFY_PHASE_WORLDCLASS_PLAN.md) — Leitbild, SOTA-Überblick, phasierter Plan und **100 %-Umsetzung** (Teil D2: Erfolgsbedingungen, Garantien aus der Forschung, Checkliste, Implementierungsspezifikation mit Fallbacks und testbarer Abnahme).

---

Dieses Dokument sollte bei Änderungen an Verify-Phase, Evidence Gate, claim_ledger, gap_analysis und zugehörigen Docs (UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK) mitgeführt werden.
