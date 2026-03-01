# Agent-Prompt: Verify-Phase auf Weltklasse (SOTA/Novel)

**Zweck:** Ein Agent soll für die **Verify-Phase** der Research-Pipeline dasselbe leisten wie für das Memory/Brain-System: vollständige Tiefenanalyse, SOTA/Novel-Recherche, konkreter Weltklasse-Plan und optional vollständige Umsetzung. Die Forschung für diese Phase soll explizit stattfinden.

---

## Deine Rolle und der Qualitätsanspruch

Du arbeitest als **Senior Production Engineer** an einem Research-Operator-System. Der Nutzer hat **hohe Ansprüche**: Das Ergebnis soll **produktionsreif**, **korrekt** und **von Anfang bis Ende durchdacht** sein – kein Platzhalter-Code, keine halben Sachen. Wenn du dir bei einer Anforderung unsicher bist, formuliere eine präzise Annahme und arbeite sie ab; dokumentiere sie.

- **Korrektheit, Wartbarkeit und Verlässlichkeit** gehen vor schnelle Hacks.
- **Dokumentation und Code** müssen übereinstimmen (vgl. `.cursor/rules/docs-sync-with-code.mdc`). Betroffene Docs bei Änderungen anpassen.
- **Keine Aktion ohne Verständnis:** Zuerst die Phase und den Code verstehen, dann planen, dann umsetzen.

---

## Kontext: Was bereits für Memory/Brain gemacht wurde (Vorbild)

Für das **Memory- und Brain-System** wurden folgende Artefakte erstellt; sie dienen dir als **Strukturvorbild** für die Verify-Phase:

1. **Tiefenanalyse (Deep Dive)** – `operator/docs/MEMORY_BRAIN_DEEP_DIVE.md`: Datenfluss, Schema, Probleme/Lücken, SOTA/Novel-Möglichkeiten.
2. **Weltklasse-Plan** – `operator/docs/MEMORY_BRAIN_WORLDCLASS_PLAN.md`: Leitbild, SOTA-Überblick, Ist-Zustand, Ziele, phasierter Plan, optional Erfolgsbedingungen, Metriken.
3. **Umsetzung** – Alle Phasen implementiert; Docs und UI mitgezogen.

**Deine Aufgabe:** Dasselbe für die **Verify-Phase** – gleiche Tiefe, gleiche Struktur, gleicher Anspruch.

---

## Fokus: Die Verify-Phase

Die **Verify-Phase** prüft Evidenz und Qualität vor dem Report; nur bei bestandenem **Evidence Gate** wird in Synthesize weitergemacht:

- **Eingang:** Nach Connect. Verfügbar: Findings, Sources, thesis.json, contradictions.json, hypotheses.json, ggf. Connect-Artefakte.
- **Kern:**  
  - **Source Reliability** (`research_verify.py source_reliability`) → `source_reliability.json`  
  - **Claim Verification** (`research_verify.py claim_verification`) → `claim_verification.json`  
  - **Fact Check** (`research_verify.py fact_check`) → `fact_check.json`  
  - **Claim Ledger** (`research_verify.py claim_ledger`) → `claim_ledger.json`  
  - **Quality Gate** (Critic, Evidence Gate): Bewertung, Pass/Fail, ggf. **Loop-back** (deepening_queries → zurück zu Focus).  
  - **Gap Analysis** (`research_reason.py gap_analysis`) → `gaps_verify.json`, `verify/deepening_queries.json`.
- **Ausgang:** Artefakte in `research/proj-…/verify/` (source_reliability, claim_verification, fact_check, claim_ledger, critique.json, claim_evidence_map_latest.json); bei Pass → `advance_phase "synthesize"`, bei Fail → Loop-back oder Block.

**Wichtige Dateien und Stellen (Quelle der Wahrheit):**

- **Shell:** `operator/workflows/research-cycle.sh` – Branch `verify)`, Aufrufe von `research_verify.py` (Subcommands), Kopieren nach `$PROJ_DIR/verify/`, Evidence-Gate-Logik, AEM/block_synthesize, advance_phase synthesize.
- **Kern-Tool:** `operator/tools/research_verify.py` – source_reliability, claim_verification, fact_check, claim_ledger; ggf. apply_verified_tags_to_report.
- **Weitere:** `operator/tools/research_critic.py` (Critic, Revise), `operator/tools/research_reason.py` (gap_analysis), Quality-Gate-/Evidence-Gate-Code in research-cycle.sh (Python-Blöcke).
- **Docs:** `operator/docs/EXPLORE_PHASE_DEEP_DIVE.md`, `operator/docs/FOCUS_PHASE_DEEP_DIVE.md`, `operator/docs/RESEARCH_QUALITY_SLO.md` (Fail-Codes, Schwellen), `operator/docs/UI_OVERVIEW.md` – bei Änderungen synchron halten.

---

## Konkrete Aufgaben (in dieser Reihenfolge)

### 1. Tiefenanalyse (Deep Dive) erstellen

- **Datei:** `operator/docs/VERIFY_PHASE_DEEP_DIVE.md` (neu).
- **Inhalt (analog MEMORY_BRAIN_DEEP_DIVE):**
  - **Teil 1:** Datenfluss der Verify-Phase: Reihenfolge der Subcommands (source_reliability → claim_verification → fact_check → claim_ledger), Inputs/Outputs pro Schritt, wo werden Artefakte persistiert? Wie fließen sie in Evidence Gate und Critic ein?
  - **Teil 2:** Schema/Struktur: claim_verification.json, claim_ledger.json, claim_evidence_map, critique.json, quality_gate, Evidence-Gate-Metriken (claim_support_rate etc.).
  - **Teil 3:** Gate-Logik: Wann Pass/Fail? Loop-back (deepening_queries) und Recovery; AEM/block_synthesize.
  - **Teil 4:** **Probleme-/Lücken-Tabelle:** Was fehlt? Was ist fragil? Was ist nicht SOTA (z. B. Claim-Evidence-Verknüpfung, Factuality-Checks, Source-Credibility-Nutzung)?
  - **Teil 5:** Wo sind **SOTA- oder novel Verbesserungen** möglich? (z. B. Chain-of-Verification, RAG-basierte Evidenzprüfung, strukturierte Claim–Evidence-Schemas.) Verweis auf Weltklasse-Plan.

### 2. SOTA/Novel-Recherche und Weltklasse-Plan

- **Datei:** `operator/docs/VERIFY_PHASE_WORLDCLASS_PLAN.md` (neu).
- **Inhalt (analog MEMORY_BRAIN_WORLDCLASS_PLAN):**
  - **Leitbild:** Was soll die Verify-Phase leisten? (evidenzbasierte Pass/Fail-Entscheidung, nachvollziehbare Claim–Evidence-Verknüpfung, Factuality, klare Gates.)
  - **Teil A:** SOTA/Forschung: Claim Verification, Fact-Checking-Systeme, Evidence Gates, Chain-of-Verification, Attribution, Source Credibility.
  - **Teil B:** Ist-Zustand (Brücke zum Code).
  - **Teil C:** Ziele (Weltklasse SOTA/Novel).
  - **Teil D:** Phasierter Plan (Ziel, Code/Schema, Abnahme, Risiko) pro Phase.
  - Optional **Teil D2:** Erfolgsbedingungen/Checkliste.
  - Priorisierung und Metriken (z. B. Pass-Rate, claim_support_rate, Revision-Runden).

### 3. Dokumentation synchron halten

- Bei Code- oder Ablauf-Änderungen: UI_OVERVIEW, RESEARCH_QUALITY_SLO, SYSTEM_CHECK, RESEARCH_AUTONOMOUS sowie VERIFY_PHASE_DEEP_DIVE und VERIFY_PHASE_WORLDCLASS_PLAN anpassen. Code = Quelle der Wahrheit.

### 4. Optional: Vollständige Umsetzung

- Alle Phasen des Weltklasse-Plans implementieren, Tests und Docs-Sync; gleicher Standard wie bei Memory/Brain.

---

## Kurz-Checkliste

- [ ] `VERIFY_PHASE_DEEP_DIVE.md` erstellt: Datenfluss, Schema, Gates, Probleme, SOTA/Novel-Möglichkeiten.
- [ ] `VERIFY_PHASE_WORLDCLASS_PLAN.md` erstellt: SOTA-Überblick, Ist-Zustand, Ziele, phasierter Plan, ggf. Erfolgsbedingungen, Metriken.
- [ ] Alle Aussagen mit **Code** (research-cycle.sh verify-Branch, research_verify.py, research_critic.py, research_reason.py) abgeglichen.
- [ ] Docs-Sync bei Änderungen.
- [ ] Optional: Plan vollständig umgesetzt.

---

## Copy-Paste-Prompt (für einen anderen Agenten)

```
Führe für die Verify-Phase der Research-Pipeline dieselbe Arbeit durch wie für das Memory/Brain-System: vollständige Tiefenanalyse, SOTA/Novel-Recherche und ein konkreter Weltklasse-Plan, damit die Forschung für diese Phase stattfindet.

Vorgehen:
1. Lies und befolge die Anweisungen in operator/docs/PROMPT_VERIFY_PHASE_WORLDCLASS.md vollständig.
2. Erstelle operator/docs/VERIFY_PHASE_DEEP_DIVE.md (Datenfluss, Subcommands source_reliability/claim_verification/fact_check/claim_ledger, Evidence Gate, Critic, Gap-Analysis, Loop-back, Probleme/Lücken, SOTA/Novel-Möglichkeiten). Quelle der Wahrheit: operator/workflows/research-cycle.sh (verify-Branch), operator/tools/research_verify.py, operator/tools/research_critic.py, operator/tools/research_reason.py (gap_analysis).
3. Erstelle operator/docs/VERIFY_PHASE_WORLDCLASS_PLAN.md (Leitbild, SOTA-Überblick zu Claim Verification / Fact-Checking / Evidence Gates, Ist-Zustand, Ziele, phasierter Plan mit Abnahme, optional Erfolgsbedingungen, Priorisierung, Metriken). Orientiere dich an operator/docs/MEMORY_BRAIN_WORLDCLASS_PLAN.md.
4. Halte die Dokumentation mit dem Code synchron (docs-sync-with-code). Bei Implementierung: alle Phasen des Plans umsetzen, Tests und Docs aktualisieren.

Qualitätsanspruch: Produktionsreif, korrekt, von Anfang bis Ende durchdacht – gleicher Standard wie beim Memory/Brain-System.
```
