# Agent-Prompt: Synthesize-Phase auf Weltklasse (SOTA/Novel)

**Zweck:** Ein Agent soll für die **Synthesize-Phase** der Research-Pipeline dasselbe leisten wie für das Memory/Brain-System: vollständige Tiefenanalyse, SOTA/Novel-Recherche, konkreter Weltklasse-Plan und optional vollständige Umsetzung. Die Forschung für diese Phase soll explizit stattfinden.

---

## Deine Rolle und der Qualitätsanspruch

Du arbeitest als **Senior Production Engineer** an einem Research-Operator-System. Der Nutzer hat **hohe Ansprüche**: Das Ergebnis soll **produktionsreif**, **korrekt** und **von Anfang bis Ende durchdacht** sein – kein Platzhalter-Code, keine halben Sachen. Wenn du dir bei einer Anforderung unsicher bist, formuliere eine präzise Annahme und arbeite sie ab; dokumentiere sie.

- **Korrektheit, Wartbarkeit und Verlässlichkeit** gehen vor schnelle Hacks.
- **Dokumentation und Code** müssen übereinstimmen (vgl. `.cursor/rules/docs-sync-with-code.mdc`). Betroffene Docs bei Änderungen anpassen.
- **Keine Aktion ohne Verständnis:** Zuerst die Phase und den Code verstehen, dann planen, dann umsetzen.

---

## Kontext: Was bereits für Memory/Brain gemacht wurde (Vorbild)

Für das **Memory- und Brain-System** wurden folgende Artefakte erstellt; sie dienen dir als **Strukturvorbild** für die Synthesize-Phase:

1. **Tiefenanalyse (Deep Dive)**  
   - `operator/docs/MEMORY_BRAIN_DEEP_DIVE.md`  
   - Enthält: Wie funktioniert das System? (Datenfluss, Schema, Abruf, alle beteiligten Module.)  
   - Wo sind die **Probleme/Lücken**? (Tabelle oder Liste mit konkreten Stellen.)  
   - Wo sind **SOTA- oder novel Verbesserungen** möglich? (kurz begründet.)

2. **Weltklasse-Plan (SOTA/Novel)**  
   - `operator/docs/MEMORY_BRAIN_WORLDCLASS_PLAN.md`  
   - Enthält: Leitbild, AGI/Selbstverbesserung (wo anwendbar), „Verstehen zuerst“, **SOTA-Überblick** (MemRL, REMem, HippoRAG, Generative Agents, MemGPT, GraphRAG, Wake–Sleep, MetaReflection etc.), **drei Säulen**, **Ist-Zustand (Teil B)**, **Ziele (Teil C)**, **phasierter Plan (Teil D)** mit konkreten Phasen (Ziel, Code/Schema, Abnahme, Risiko), optional **Erfolgsbedingungen/Checkliste (Teil D2)**, Priorisierung, Metriken.

3. **Umsetzung**  
   - Alle Phasen des Plans wurden (soweit spezifiziert) implementiert; Docs und UI wurden mitgezogen.

**Deine Aufgabe:** Dasselbe für die **Synthesize-Phase** – gleiche Tiefe, gleiche Struktur, gleicher Anspruch.

---

## Fokus: Die Synthesize-Phase

Die **Synthesize-Phase** ist die letzte inhaltliche Phase der Research-Pipeline vor `done`:

- **Eingang:** Nach bestandenem Evidence Gate (Verify-Phase). Verfügbar: Findings (`research/proj-…/findings/*.json`), Sources, Verify-Artefakte (z. B. critique, Claim Evidence Registry), optional Playbook, Projekt-Frage.
- **Kern:** Ein **Report** wird erzeugt (Markdown, 5K–15K Wörter, „research-firm-grade“). Dazu: Topic-Clustering der Findings, section-by-section Synthesis, Claim–Source-Verknüpfung, Provenance.
- **Ausgang:** `report.md` (in Artifacts), ggf. PDF, Quality Gate (Critic), Revision-Runden, dann `advance_phase done`.

**Wichtige Dateien und Stellen (Quelle der Wahrheit):**

- **Shell:** `operator/workflows/research-cycle.sh` – Branch `synthesize)`, Aufruf von `research_synthesize.py`, Schreiben von `report.md`, ggf. Critic/Revise-Loop.
- **Kern-Tool:** `operator/tools/research_synthesize.py` – Multi-Pass-Synthese, Clustering, Outline, Section Writing, Claim-Ledger, Provenance.
- **Hilfen:** `operator/tools/research_common.py` – z. B. `get_claims_for_synthesis`, `project_dir`, `load_project`, `llm_call`.
- **Verify → Synthesize:** Welche Verify-Artefakte werden in die Synthesize übergeben? (z. B. Claim-Liste, Evidence-Registry, critique.json.)
- **Docs:** `operator/docs/EXPLORE_PHASE_DEEP_DIVE.md`, `operator/docs/FOCUS_PHASE_DEEP_DIVE.md` – gleiche Tiefe erwünscht; `operator/docs/RESEARCH_QUALITY_SLO.md`, `operator/docs/UI_OVERVIEW.md` – bei Änderungen an Ablauf/APIs/UI synchron halten.

---

## Konkrete Aufgaben (in dieser Reihenfolge)

### 1. Tiefenanalyse (Deep Dive) erstellen

- **Datei:** `operator/docs/SYNTHESIZE_PHASE_DEEP_DIVE.md` (neu).
- **Inhalt (analog MEMORY_BRAIN_DEEP_DIVE):**
  - **Teil 1:** Datenfluss der Synthesize-Phase im Detail: Welche Inputs (Findings, Sources, Verify-Artefakte, Playbook, Frage)? In welcher Reihenfolge werden sie gelesen? Welche Skripte/Funktionen sind beteiligt? Was wird an das LLM übergeben (Clustering, Outline, Section-Prompts)?
  - **Teil 2:** Schema/Struktur der beteiligten Daten (Findings-Format, Source-Content, Claim-Ledger, Report-Struktur, Appendix B / Provenance).
  - **Teil 3:** Retrieval/Selektion für die Synthese: Wie werden Findings gefiltert/sortiert (z. B. Relevanz zur Frage)? Wie wird Source-Content geladen und gekürzt? Wo sind Limits (MAX_FINDINGS, EXCERPT_CHARS, SECTION_WORDS)?
  - **Teil 4:** Klare **Probleme-/Lücken-Tabelle**: Was fehlt? Was ist fragil? Was ist nicht SOTA (z. B. nur Keyword-Relevanz, keine semantische Auswahl)? Wo fehlt Provenance oder Factuality?
  - **Teil 5:** Kurz: Wo sind **SOTA- oder novel Verbesserungen** möglich? (z. B. bessere Claim–Evidence-Attribution, Multi-Doc-Summarization, Factuality-Guards, strukturierte Outputs.) Verweis am Ende auf den Weltklasse-Plan.

### 2. SOTA/Novel-Recherche und Weltklasse-Plan

- **Datei:** `operator/docs/SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md` (neu).
- **Inhalt (analog MEMORY_BRAIN_WORLDCLASS_PLAN):**
  - **Leitbild:** Was soll die Synthesize-Phase können? (z. B. evidenzbasierter, nachvollziehbarer, strukturierter Report; Claim–Source-Traceability; Qualität auf „research-firm-grade“.)
  - **Teil A:** Wie machen es **SOTA-Systeme und die Forschung**? (Literatur/Systeme: z. B. Multi-Document Summarization, Claim-driven Writing, RAG für Reports, Factuality/Attribution, Chain-of-Verification, Structured Report Generation. Kurz pro System/Idee: Kernidee + was wir daraus nutzen.)
  - **Teil B:** **Wo stehen wir heute?** (Brücke zum aktuellen Code: Was ist bereits gut? Was fehlt im Vergleich zu SOTA?)
  - **Teil C:** **Ziele** (Weltklasse SOTA/Novel): Konkrete Ziele für die Synthesize-Phase (z. B. bessere Claim–Evidence-Verknüpfung, Factuality-Checks, konfigurierbare Report-Struktur, bessere Nutzung der Verify-Artefakte).
  - **Teil D:** **Phasierter Plan (konkret umsetzbar):**  
    - Phase 1: … (z. B. Claim-Ledger und Provenance konsistent nutzen),  
    - Phase 2: … (z. B. Factuality/Attribution),  
    - Phase 3: … (z. B. strukturierte Outputs oder bessere Section-Qualität),  
    - ggf. weitere Phasen.  
    Pro Phase: **Ziel**, **konkrete Code/Schema/Config-Änderungen**, **Abnahme**, **Risiko**.
  - Optional **Teil D2:** Erfolgsbedingungen/Checkliste (unter welchen Bedingungen gilt die Synthesize-Phase als „100 % spezifiziert“ oder erfolgssicher).
  - **Priorisierung und Metriken:** Was wird zuerst umgesetzt? Wie messen wir Erfolg (z. B. Critic-Score, Revision-Runden, Provenance-Vollständigkeit)?

### 3. Dokumentation synchron halten

- Wenn du **Code oder Abläufe** änderst: `operator/docs/UI_OVERVIEW.md`, `operator/docs/RESEARCH_QUALITY_SLO.md`, `operator/docs/SYSTEM_CHECK.md`, `operator/docs/RESEARCH_AUTONOMOUS.md` und die neuen Docs (`SYNTHESIZE_PHASE_DEEP_DIVE.md`, `SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md`) so anpassen, dass sie mit dem Code übereinstimmen.
- Code ist **Quelle der Wahrheit**; die Doku folgt nach.

### 4. Optional: Vollständige Umsetzung

- Wenn der Nutzer oder du entscheidest, den Plan **vollständig umzusetzen**: Alle Phasen des Weltklasse-Plans implementieren (analog zur Memory/Brain-Umsetzung), mit Tests und Docs-Sync. Keine Phase weglassen, es sei denn, sie wird explizit als „optional“ oder „später“ markiert.

---

## Kurz-Checkliste für dich

- [ ] `SYNTHESIZE_PHASE_DEEP_DIVE.md` erstellt: Datenfluss, Schema, Probleme, SOTA/Novel-Möglichkeiten.
- [ ] `SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md` erstellt: SOTA-Überblick, Ist-Zustand, Ziele, phasierter Plan, ggf. Erfolgsbedingungen und Metriken.
- [ ] Alle Aussagen in den neuen Docs mit dem **aktuellen Code** (research-cycle.sh, research_synthesize.py, research_common) abgeglichen.
- [ ] Bei Code- oder Ablauf-Änderungen: bestehende Docs (UI_OVERVIEW, RESEARCH_QUALITY_SLO, SYSTEM_CHECK, RESEARCH_AUTONOMOUS) und neue Synthesize-Docs aktualisiert.
- [ ] Optional: Phasen des Plans implementiert, getestet und dokumentiert.

---

## Copy-Paste-Prompt (für einen anderen Agenten oder Chat)

```
Führe für die Synthesize-Phase der Research-Pipeline dieselbe Arbeit durch wie für das Memory/Brain-System: vollständige Tiefenanalyse, SOTA/Novel-Recherche und ein konkreter Weltklasse-Plan, damit die Forschung für diese Phase stattfindet.

Vorgehen:
1. Lies und befolge die Anweisungen in operator/docs/PROMPT_SYNTHESIZE_PHASE_WORLDCLASS.md vollständig.
2. Erstelle operator/docs/SYNTHESIZE_PHASE_DEEP_DIVE.md (Datenfluss, beteiligte Module, Schema, Probleme/Lücken, SOTA/Novel-Möglichkeiten). Quelle der Wahrheit: operator/workflows/research-cycle.sh (synthesize-Branch), operator/tools/research_synthesize.py, operator/tools/research_common.py (get_claims_for_synthesis etc.).
3. Erstelle operator/docs/SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md (Leitbild, SOTA-Überblick, Ist-Zustand, Ziele, phasierter Plan mit Abnahme, optional Erfolgsbedingungen, Priorisierung, Metriken). Orientiere dich an der Struktur von operator/docs/MEMORY_BRAIN_WORLDCLASS_PLAN.md.
4. Halte die Dokumentation mit dem Code synchron (docs-sync-with-code). Bei Implementierung: alle Phasen des Plans umsetzen, Tests und Docs aktualisieren.

Qualitätsanspruch: Produktionsreif, korrekt, von Anfang bis Ende durchdacht – gleicher Standard wie beim Memory/Brain-System.
```

---

*Dieser Prompt und die genannten Docs sind Teil des Operator-Projekts und sollen bei Änderungen an der Synthesize-Phase mitgeführt werden.*
