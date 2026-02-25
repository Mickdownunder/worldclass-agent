# V3 Research Quality Guardrails — Implementation Audit & Market Assessment

**Audit Date:** 2026-02-25  
**Scope:** V3 Plan `research_quality_guardrails_v3_f6263b3d.plan.md` vs. target system `/root/operator`  
**Method:** Evidence-based; no assumptions without proof.

---

## 1) Executive Verdict

Die V3-Kernlogik ist **teilweise umgesetzt**: Evidence Gate, Claim-Ledger, Memory-Admission und Brain High-Signal sind implementiert und wirksam. **Kritische Lücken** bleiben: (1) **Halluzinierte [VERIFIED]-Tags werden nicht entfernt** — der Report kann vom LLM eingefügte [VERIFIED]-Markierungen behalten, die nicht im Claim-Ledger stehen. (2) **Red-Team-Fall `hallucinated_verified_tag_blocked` ist nicht als automatisierter Test implementiert** — nur in `redteam_cases.json` beschrieben. (3) **UI-Audit-Tab fehlt** — Claim-to-Evidence-Audit ist nicht in der Research-Detail-Ansicht sichtbar. (4) **research_eval nutzt LLM-`verified` statt Ledger-`is_verified`** — SLO-Metriken können von der deterministischen Verifikation abweichen.  
**Empfehlung: No-Go für produktiven Einsatz**, bis Stripping von nicht-ledger-[VERIFIED], Red-Team-Test für halluzinierte Tags und Audit-UI (oder klare Dokumentation des Verzichts) umgesetzt sind. Danach: **Go mit Monitoring** der SLOs und Quarantäne-Rate.

---

## 2) Findings (nach Schweregrad)

### Critical

#### C1 — Halluzinierte [VERIFIED]-Tags werden nicht aus dem Report entfernt

- **Warum kritisch:** V3 verlangt, dass [VERIFIED] ausschließlich deterministisch aus dem Claim-Ledger kommt. Wenn das Synthese-LLM eigenständig „X [VERIFIED]“ ausgibt und X nicht im Ledger als verifiziert steht, muss der Tag entfernt werden. Andernfalls erscheinen nicht verifizierte Aussagen als verifiziert.
- **Datei/Pfad:** `workflows/research-cycle.sh`, Inline-Python nach Synthesis (ca. Zeilen 328–345).
- **Nachweis:**  
  - Prompt enthält „Do NOT add [VERIFIED] tags yourself“ (Zeile 309), aber es gibt **keinen Code**, der vorhandene ` [VERIFIED]`-Vorkommen im Report prüft und entfernt, wenn der zugehörige Claim nicht im Ledger als `is_verified` steht.  
  - Nur **Hinzufügen** von [VERIFIED] für Ledger-Claims: `report = report.replace(text, text + " [VERIFIED]", 1)` (Zeile 345).  
  - Reproduzierbar: Report-String mit „Fake claim. [VERIFIED]“ und leerem/abweichendem Ledger → Tag bleibt im finalen Report.
- **Fix:** Vor dem Ledger-basierten Hinzufügen: (1) Alle ` [VERIFIED]` im Report entfernen (z. B. `report = re.sub(r'\s*\[VERIFIED\]', '', report)`), dann (2) nur für Claims aus dem Ledger mit `is_verified=True` den Tag wieder setzen (wie heute).

---

#### C2 — Red-Team-Fall `hallucinated_verified_tag_blocked` nicht als Test implementiert

- **Warum kritisch:** V3 verlangt Red-Team-Regressionen als Release-Blocker; `redteam_cases.json` listet `hallucinated_verified_tag_blocked` mit Erwartung `verified_only_from_ledger`. In `tests/research/test_quality_gates.py` existiert **kein** Test, der prüft, dass ein Report mit vom LLM eingefügtem [VERIFIED] bereinigt wird (bzw. dass kein nicht-ledger-[VERIFIED] im Output bleibt).
- **Datei/Pfad:** `tests/research/test_quality_gates.py` (kein Test für `hallucinated_verified_tag_blocked`); `tests/research/redteam_cases.json` (Fall nur beschrieben).
- **Nachweis:**  
  - `grep -n hallucinated tests/research/test_quality_gates.py` → keine Treffer.  
  - `redteam_cases.json` enthält den Fall (id `hallucinated_verified_tag_blocked`).
- **Fix:** Test hinzufügen: z. B. Funktion die (1) Report-Text mit „arbitrary claim [VERIFIED]“ und (2) Ledger ohne diesen Claim (oder `is_verified=False`) durch die gleiche Nachbearbeitungslogik wie in `research-cycle.sh` laufen lässt und assertiert, dass der finale Text für diesen Claim kein [VERIFIED] enthält. Dazu zuerst C1 (Stripping) im Cycle implementieren.

---

### High

#### H1 — Kein Audit-Tab in der Research-UI

- **Warum relevant:** V3 (Punkt 7) verlangt einen Tab/Abschnitt „Audit“ in der Detailansicht mit verified/disputed/unverified claims und verknüpften Quellen. Das verbessert Nachvollziehbarkeit und Abnahme.
- **Datei/Pfad:** `ui/src/app/(dashboard)/research/[id]/ResearchDetailTabs.tsx`. Tabs: `report`, `findings`, `sources`, `verlauf` — **kein** `audit`.
- **Nachweis:** Zeilen 104–108: `tabs`-Array enthält nur die vier genannten IDs; kein Fetch von `claim_evidence_map` oder `claim_ledger`.
- **Fix:** Tab „Audit“ ergänzen; API-Endpunkt (z. B. `/api/research/projects/[id]/audit`) der `verify/claim_evidence_map_latest.json` bzw. `claim_ledger.json` liefert; UI zeigt verified/disputed/unverified Claims und zugehörige Quellen.

---

#### H2 — research_eval nutzt LLM-`verified` statt Ledger-`is_verified`

- **Warum relevant:** SLO-Dokumentation und Scorecards sollen mit der deterministischen Verifikation übereinstimmen. `research_eval.py` berechnet `claim_support_rate` aus `claim_verification.json` (LLM-Feld `verified`), nicht aus `claim_ledger.json` (`is_verified`).
- **Datei/Pfad:** `tools/research_eval.py`, Zeilen 36–42 (`cv.get("claims", [])`, `c.get("verified")`).
- **Nachweis:** Kein `claim_ledger.json`-Lesen in `_scorecard`; `docs/RESEARCH_QUALITY_SLO.md` verweist auf „claim_support_rate“ als SLO — Quelle sollte Ledger sein.
- **Fix:** In `_scorecard` zuerst `claim_ledger.json` verwenden; falls vorhanden, `claim_support_rate` aus `is_verified` im Ledger berechnen; Fallback auf `claim_verification.json` für ältere Projekte.

---

### Medium

#### M1 — claim_evidence_map_latest / claim_ledger in bestehenden Projekten fehlend

- **Warum relevant:** Ein durchgelaufenes Projekt (`proj-20260225-475f1f9c`) hat in `verify/` weder `claim_ledger.json` noch `claim_evidence_map_latest.json`. Die Pipeline schreibt diese nur in der Verify- bzw. Synthesize-Phase; ältere Läufe oder Läufe ohne vollständigen Verify-Pfad haben sie nicht.
- **Datei/Pfad:** `research/proj-20260225-475f1f9c/verify/` (nur `claim_verification.json`, `critique.json`, `fact_check.json`, `source_reliability.json`).
- **Nachweis:** `ls research/proj-20260225-475f1f9c/verify/` → keine `claim_ledger.json`, keine `claim_evidence_map_*.json`.
- **Fix:** Einmalig: Dokumentieren, dass nur neue Läufe (mit aktuellem research-cycle.sh) Audit-Artefakte haben. Optional: Backfill-Skript für Projekte, die bereits `claim_verification.json` + `source_reliability.json` haben, um `claim_ledger` (und daraus `claim_evidence_map`) zu erzeugen.

---

#### M2 — research_quality_gate akzeptiert sowohl `is_verified` als auch `verified`

- **Warum relevant:** Gate liest Claims aus Ledger (wenn vorhanden), Ledger hat `is_verified`. Zusätzlich wird in Zeile 84 `c.get("is_verified") or c.get("verified")` verwendet — Fallback auf LLM-`verified` wenn Ledger-Struktur anders ist. Konsistenz und klare Priorität (Ledger vor LLM) sind wünschenswert.
- **Datei/Pfad:** `tools/research_quality_gate.py`, Zeile 84.
- **Nachweis:** `verified_count = sum(1 for c in claims_data if c.get("is_verified") or c.get("verified"))` — bei vorhandenem Ledger kommt nur `is_verified` vor; bei reinem claim_verification nur `verified`. Kein Bug, aber zweideutig für Wartung.
- **Fix:** Kommentar ergänzen: „Ledger provides is_verified; claim_verification provides verified. Both supported for backward compat.“ Optional: explizit zuerst Ledger verwenden, dann claim_verification.

---

### Low

#### L1 — Kein zentraler CI-Blocker für Red-Team-Tests

- **Warum relevant:** V3 verlangt, dass CI/Autonomous Run failed, wenn ein Red-Team-Fall „durchgeht“ (gefährliches Verhalten nicht blockiert). Die Tests in `test_quality_gates.py` laufen manuell; ob sie in CI als Blockierer laufen, ist aus dem Repo nicht ersichtlich.
- **Datei/Pfad:** Keine `.github/workflows` oder vergleichbare CI-Datei im geprüften Baum, die `tests/research/test_quality_gates.py` als must-pass ausweist.
- **Fix:** CI-Job definieren, der `python3 tests/research/test_quality_gates.py` ausführt und bei Exit != 0 den Build failed.

---

## 3) V3 Compliance Table

| Requirement | Status | Evidence (Datei + Testnachweis) | Risk | Action |
|-------------|--------|----------------------------------|------|--------|
| 1) Evidence Gate vor done | **Implemented** | `research-cycle.sh` (201–264): Gate vor synthesize, bei Fail `status=failed_*`, kein advance zu synthesize. `research_quality_gate.py`: Schwellen (8/5/2/0.6/0.5). Test: `test_no_findings_should_not_done` (0 findings → gate fail). | Niedrig | — |
| 2) Deterministische [VERIFIED] | **Partial** | `research_verify.py` `build_claim_ledger`: is_verified nur bei ≥2 Quellen, kein dispute, keine low reliability. Synthesis fügt nur Ledger-verified hinzu. **ABER:** Kein Stripping von LLM-[VERIFIED] (C1). | Hoch | C1 beheben; Red-Team-Test (C2). |
| 3) Memory Admission Enforcement | **Implemented** | `research_memory_policy.py` decide() → accepted/quarantined/rejected. `research_embed.py`: nur accepted werden embedded; admission_state und record_admission_event. `memory.py`: get_research_findings_accepted filtert auf admission_state='accepted'. | Niedrig | — |
| 4) Brain nur High-Signal | **Implemented** | `brain_context.py` compile(): get_research_findings_accepted(); Reflections mit quality >= 0.6. `brain.py` perceive(): state["memory"]["recent_reflections"] gefiltert auf quality >= 0.6; state["research_context"] = brain_context.compile(memory). | Niedrig | — |
| 5) Fail-Codes + SLOs | **Implemented** | Fail-Codes in `research-cycle.sh` und `research_quality_gate.py` (failed_insufficient_evidence, failed_verification_inconclusive, failed_quality_gate, failed_source_diversity). SLO-Doku: `docs/RESEARCH_QUALITY_SLO.md`. research_eval liefert Scorecard; Metrik-Quelle für claim_support_rate ist noch LLM (H2). | Mittel | H2: Ledger für claim_support_rate nutzen. |
| 6) Red-Team Regression Pack | **Partial** | `redteam_cases.json` mit 5 Fällen. `test_quality_gates.py`: 4 Tests (no_findings, single_source, conflicting_dispute, memory_quarantine, thresholds). **Fehlt:** automatisierter Test für `hallucinated_verified_tag_blocked` (C2). | Hoch | C2 beheben. |
| 7) Claim-to-Evidence Audit | **Partial** | Artefakt: `claim_evidence_map_{ts}.json` und `claim_evidence_map_latest.json` in Synthese (research-cycle.sh 348–358). **Fehlt:** UI-Audit-Tab (H1). | Mittel | H1: Audit-Tab + API. |

---

## 4) Test Results (Pass/Fail Matrix)

| Test | Input | Erwartung | Ist-Ergebnis | Pass/Fail | Root Cause bei Fail |
|------|--------|-----------|----------------|-----------|----------------------|
| 0 findings → done | Projekt mit 0 Findings | Nicht done; evidence_gate fail | Gate fail, status=failed_insufficient_evidence, Phase bleibt verify | **Pass** | — |
| Single-source claim → VERIFIED | 1 Quelle, claim_verification | is_verified=False im Ledger | build_claim_ledger: is_verified=False, reason enthält "source" | **Pass** | — |
| Conflicting/disputed → VERIFIED | disputed + 2 Quellen | is_verified=False | Ledger: is_verified=False, reason "disputed" | **Pass** | — |
| Quarantined memory → Brain | Nur accepted in Kontext | brain_context nur get_research_findings_accepted | compile() nutzt get_research_findings_accepted; keine quarantined/rejected | **Pass** | — |
| Halluziniertes [VERIFIED] | Report mit "X [VERIFIED]", X nicht im Ledger | Tag entfernt oder nicht im Output | Tag bleibt im Report (kein Stripping-Code) | **Fail** | C1: Stripping nicht implementiert |
| Red-Team hallucinated_verified_tag_blocked | Wie oben, als automatisierter Test | Test existiert und grün | Kein Test in test_quality_gates.py | **Fail** | C2: Test nicht implementiert |

**Zusammenfassung:** 4/6 Pass, 2/6 Fail (beide um halluzinierte [VERIFIED]-Tags).

---

## 5) Qualitätsmetriken & Produktionsreife

### Metriken (aus vorhandenen Artefakten)

- **claim_support_rate:** Aus `eval/scorecard_latest.json` eines Projekts: 0 (claim_verification war leer oder nicht genutzt). Sollte künftig aus Ledger kommen (H2).
- **citation_precision:** 0.567 (Anteil Quellen mit reliability ≥ 0.6).
- **evidence_gate_pass_rate:** Nicht aggregiert gemessen; Einzelnachweis: 0 findings → fail.
- **quarantine_rate / memory_reject_or_quarantine_rate:** Nicht in Scorecard; würde aus `memory_admission_events` berechnet werden (SLO-Doku verweist darauf).
- **source_diversity:** 1.0 (normiert auf 10 Domains) in der geprüften Scorecard.

### Production Readiness

- **Bewertung:** **Nein** für unüberwachte Produktion.
- **Begründung:** (1) Halluzinierte [VERIFIED]-Tags können im Report bleiben (Integritätsrisiko). (2) Red-Team-Fall für genau dieses Verhalten ist nicht getestet. (3) Audit für Nutzer nicht sichtbar (UI).
- **Blocker-Liste:**
  1. Stripping von [VERIFIED], die nicht aus dem Claim-Ledger stammen (C1).
  2. Red-Team-Test für `hallucinated_verified_tag_blocked` (C2).
  3. Entweder Audit-Tab/API (H1) oder explizite Dokumentation, dass Audit nur über Dateien erfolgt.

---

## 6) Marktvergleich & Quellen

### Referenzen (nachvollziehbar, mit URL)

| Quelle | URL | Relevanz |
|--------|-----|----------|
| EviBound: Evidence-Bound Autonomous Research | https://arxiv.org/abs/2511.05524 | Dual Gates (Approval + Verification), 0% Hallucination bei Verifikation; machine-checkable evidence. |
| DeepTRACE: Auditing Research AI | https://arxiv.org/abs/2509.04499 | Claim/Citation-Evidence-Matrizen, statement-level Audit. |
| ResearchRubrics (Deep Research Agents) | https://arxiv.org/abs/2511.07685 | Bewertung von factual grounding, reasoning, clarity. |
| Eval-Driven Memory (EDM) | https://www.preprints.org/manuscript/202601.0195 | Memory-Governance, selektive Konsolidierung nach Metriken. |
| RAG/Agentic Evaluation (8-Step Framework) | https://raga.ai/research/... | Multi-step, component interdependencies, agentic evaluation. |

### Competitive / Capability Matrix

| Capability | Unser Status | Marktstandard (Referenz) | Gap | Priorisierte Empfehlung |
|------------|--------------|---------------------------|-----|--------------------------|
| Evidence Gate vor „done“ | Gate vor synthesize, Fail-Codes | EviBound: Verification Gate mit machine-checkable evidence | Gate vorhanden; keine Abfrage von Run-IDs/Artifacts wie bei EviBound | Optional: Artifact-Check (z. B. claim_ledger vorhanden) im Gate |
| Deterministische Verifikation | Ledger mit ≥2 Quellen, kein dispute | EviBound: Claims nur bei verifizierten Artifacts | Ledger gut; **Stripping** von nicht-ledger-[VERIFIED] fehlt | C1 umsetzen |
| Memory Admission | accepted/quarantined/rejected, nur accepted embedded | EDM: metric-guided consolidation; EviBound: evidence-bound | Policy klar; Quarantäne-Rate als SLO messen | memory_reject_or_quarantine_rate in Eval/Scorecard aufnehmen |
| Claim-to-Evidence Audit | claim_evidence_map.json, kein UI | DeepTRACE: citation/factual-support matrices, statement-level | Audit-Daten vorhanden; Nutzersicht fehlt | H1: Audit-Tab oder klare Doku |
| Red-Team Regression | 4/5 Fälle getestet, 1 Fall nur spezifiziert | EviBound: governance stress tests; ABC für Benchmarks | Vollständige Abdeckung der redteam_cases.json in Tests | C2: Test für hallucinated_verified_tag_blocked |
| SLO-Metriken | Fail-Codes, Scorecard, SLO-Doku | EDM: Trust Index, Planning Efficiency; ResearchRubrics: rubrics | claim_support_rate aus Ledger (H2); Quarantäne-Rate messbar machen | H2 + Quarantäne in research_eval |

---

## 7) Top 10 priorisierte Maßnahmen (Impact × Aufwand)

| # | Maßnahme | Impact | Aufwand | Priorität |
|---|----------|--------|--------|-----------|
| 1 | [VERIFIED] strippen: alle aus Report entfernen, dann nur Ledger-verified wieder setzen (C1) | Hoch | Niedrig | Sofort |
| 2 | Red-Team-Test `hallucinated_verified_tag_blocked` in test_quality_gates.py (C2) | Hoch | Niedrig | Sofort |
| 3 | Audit-Tab in Research-Detail-UI + API für claim_evidence_map/claim_ledger (H1) | Mittel | Mittel | Kurzfristig |
| 4 | research_eval: claim_support_rate aus claim_ledger.json (is_verified) (H2) | Mittel | Niedrig | Kurzfristig |
| 5 | CI-Job: tests/research/test_quality_gates.py als Blockierer (L1) | Mittel | Niedrig | Kurzfristig |
| 6 | Quarantäne-Rate (memory_reject_or_quarantine_rate) in research_eval/Scorecard | Mittel | Mittel | Mittelfristig |
| 7 | Backfill claim_ledger/claim_evidence_map für bestehende Projekte mit verify-Daten (M1) | Niedrig | Mittel | Optional |
| 8 | Kommentar/Klarstellung in research_quality_gate (is_verified vs verified) (M2) | Niedrig | Niedrig | Optional |
| 9 | Evidence-Gate optional: Prüfung auf Existenz von claim_ledger.json | Niedrig | Niedrig | Optional |
| 10 | Mehrtägige Stabilität: Drift-Test über mehrere Cycles (simuliert oder reell) | Mittel | Hoch | Nach Go |

---

## 8) Go/No-Go Empfehlung

- **No-Go für produktiven Einsatz**, bis:
  - C1 behoben ist (Stripping von nicht-ledger-[VERIFIED]),
  - C2 behoben ist (Red-Team-Test für halluzinierte Tags),
  - und entweder H1 (Audit-UI) umgesetzt oder der Verzicht auf Audit-UI dokumentiert ist.

- **Danach: Go mit Monitoring:** SLOs (claim_support_rate aus Ledger, citation_precision, pass_rate_evidence_gate, memory_reject_or_quarantine_rate) beobachten; Schwellen nach 1–2 Wochen Produktionsdaten feinjustieren (nur über zentrale Policy).

---

*Ende des Audits.*
