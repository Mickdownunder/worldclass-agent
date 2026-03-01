# Agent-Prompt: Connect-Phase auf Weltklasse (SOTA/Novel)

**Zweck:** Ein Agent soll für die **Connect-Phase** der Research-Pipeline dasselbe leisten wie für das Memory/Brain-System: vollständige Tiefenanalyse, SOTA/Novel-Recherche, konkreter Weltklasse-Plan und optional vollständige Umsetzung. Die Forschung für diese Phase soll explizit stattfinden.

---

## Deine Rolle und der Qualitätsanspruch

Du arbeitest als **Senior Production Engineer** an einem Research-Operator-System. Der Nutzer hat **hohe Ansprüche**: Das Ergebnis soll **produktionsreif**, **korrekt** und **von Anfang bis Ende durchdacht** sein – kein Platzhalter-Code, keine halben Sachen. Wenn du dir bei einer Anforderung unsicher bist, formuliere eine präzise Annahme und arbeite sie ab; dokumentiere sie.

- **Korrektheit, Wartbarkeit und Verlässlichkeit** gehen vor schnelle Hacks.
- **Dokumentation und Code** müssen übereinstimmen (vgl. `.cursor/rules/docs-sync-with-code.mdc`). Betroffene Docs bei Änderungen anpassen.
- **Keine Aktion ohne Verständnis:** Zuerst die Phase und den Code verstehen, dann planen, dann umsetzen.

---

## Kontext: Was bereits für Memory/Brain gemacht wurde (Vorbild)

Für das **Memory- und Brain-System** wurden folgende Artefakte erstellt; sie dienen dir als **Strukturvorbild** für die Connect-Phase:

1. **Tiefenanalyse (Deep Dive)** – `operator/docs/MEMORY_BRAIN_DEEP_DIVE.md`: Datenfluss, Schema, Probleme/Lücken, SOTA/Novel-Möglichkeiten.
2. **Weltklasse-Plan** – `operator/docs/MEMORY_BRAIN_WORLDCLASS_PLAN.md`: Leitbild, SOTA-Überblick, Ist-Zustand, Ziele, phasierter Plan, optional Erfolgsbedingungen, Metriken.
3. **Umsetzung** – Alle Phasen implementiert; Docs und UI mitgezogen.

**Deine Aufgabe:** Dasselbe für die **Connect-Phase** – gleiche Tiefe, gleiche Struktur, gleicher Anspruch.

---

## Fokus: Die Connect-Phase

Die **Connect-Phase** verbindet Explore/Focus-Ergebnisse zu Widersprüchen, Entitäten und Hypothesen und bereitet die Verify-Phase vor:

- **Eingang:** Nach Focus (advance_phase "connect"). Verfügbar: Findings, Sources, Projekt-Frage, ggf. Coverage/Artefakte aus Explore/Focus.
- **Kern:**  
  - **Knowledge Graph / Entity Extraction** (`research_entity_extract.py`) – Entitäten und Beziehungen aus Findings/Sources.  
  - **Contradiction Detection** (`research_reason.py contradiction_detection`) → `contradictions.json`.  
  - **Hypothesis Formation** (`research_reason.py hypothesis_formation`) → `ART/hypotheses.json`.  
  - **Thesis** – Erste Hypothese wird in `thesis.json` (current, confidence, evidence) geschrieben.
- **Ausgang:** `research/proj-…/contradictions.json`, `thesis.json`; Artefakte in `$ART` (hypotheses.json); danach `advance_phase "verify"`.

**Wichtige Dateien und Stellen (Quelle der Wahrheit):**

- **Shell:** `operator/workflows/research-cycle.sh` – Branch `connect)` ruft `source "$OPERATOR_ROOT/workflows/research/phases/connect.sh"`.
- **Phase-Skript:** `operator/workflows/research/phases/connect.sh` – Aufrufe von research_entity_extract.py, research_reason.py (contradiction_detection, hypothesis_formation), Schreiben von thesis.json, advance_phase verify.
- **Tools:** `operator/tools/research_entity_extract.py`, `operator/tools/research_reason.py` (contradiction_detection, hypothesis_formation).
- **Docs:** `operator/docs/EXPLORE_PHASE_DEEP_DIVE.md`, `operator/docs/FOCUS_PHASE_DEEP_DIVE.md`, `operator/docs/UI_OVERVIEW.md` – bei Änderungen synchron halten.

---

## Konkrete Aufgaben (in dieser Reihenfolge)

### 1. Tiefenanalyse (Deep Dive) erstellen

- **Datei:** `operator/docs/CONNECT_PHASE_DEEP_DIVE.md` (neu).
- **Inhalt (analog MEMORY_BRAIN_DEEP_DIVE):**
  - **Teil 1:** Datenfluss der Connect-Phase: Welche Inputs (Findings, Sources, Frage)? Reihenfolge: Entity Extract → Contradiction Detection → Hypothesis Formation → thesis.json. Welche Skripte/Funktionen, welche Ausgaben wo?
  - **Teil 2:** Schema/Struktur: contradictions.json, hypotheses.json, thesis.json; ggf. Entity/Graph-Output von research_entity_extract.py.
  - **Teil 3:** Wie werden Widersprüche und Hypothesen erzeugt? (LLM, regelbasiert, Hybrid?) Welche Limits und Fallbacks?
  - **Teil 4:** **Probleme-/Lücken-Tabelle:** Was fehlt? Was ist fragil? Was ist nicht SOTA (z. B. nur oberflächliche Widerspruchserkennung, schwache Nutzung des Knowledge Graph in Verify/Synthesize)?
  - **Teil 5:** Wo sind **SOTA- oder novel Verbesserungen** möglich? (z. B. bessere Contradiction Detection, Graph-basierte Hypothesen, Nutzung von Connect-Output in Verify/Synthesize.) Verweis auf Weltklasse-Plan.

### 2. SOTA/Novel-Recherche und Weltklasse-Plan

- **Datei:** `operator/docs/CONNECT_PHASE_WORLDCLASS_PLAN.md` (neu).
- **Inhalt (analog MEMORY_BRAIN_WORLDCLASS_PLAN):**
  - **Leitbild:** Was soll die Connect-Phase leisten? (Widersprüche sichtbar machen, Entitäten und Beziehungen nutzbar machen, klare Hypothesen/Thesis für Verify und Synthesize.)
  - **Teil A:** SOTA/Forschung: Contradiction Detection, Hypothesis Generation, Knowledge Graph für Research, Multi-Document Reasoning, Claim–Counterclaim-Strukturen.
  - **Teil B:** Ist-Zustand (Brücke zum Code).
  - **Teil C:** Ziele (Weltklasse SOTA/Novel).
  - **Teil D:** Phasierter Plan (Ziel, Code/Schema, Abnahme, Risiko) pro Phase.
  - Optional **Teil D2:** Erfolgsbedingungen/Checkliste.
  - Priorisierung und Metriken (z. B. Nutzung von contradictions/thesis in Verify/Synthesize, Qualität der Hypothesen).

### 3. Dokumentation synchron halten

- Bei Code- oder Ablauf-Änderungen: UI_OVERVIEW, RESEARCH_QUALITY_SLO, SYSTEM_CHECK, RESEARCH_AUTONOMOUS sowie CONNECT_PHASE_DEEP_DIVE und CONNECT_PHASE_WORLDCLASS_PLAN anpassen. Code = Quelle der Wahrheit.

### 4. Optional: Vollständige Umsetzung

- Alle Phasen des Weltklasse-Plans implementieren, Tests und Docs-Sync; gleicher Standard wie bei Memory/Brain.

---

## Kurz-Checkliste

- [ ] `CONNECT_PHASE_DEEP_DIVE.md` erstellt: Datenfluss, Entity Extract, Contradiction/Hypothesis, thesis.json, Probleme, SOTA/Novel-Möglichkeiten.
- [ ] `CONNECT_PHASE_WORLDCLASS_PLAN.md` erstellt: SOTA-Überblick, Ist-Zustand, Ziele, phasierter Plan, ggf. Erfolgsbedingungen, Metriken.
- [ ] Alle Aussagen mit **Code** (research-cycle.sh connect-Branch, phases/connect.sh, research_entity_extract.py, research_reason.py) abgeglichen.
- [ ] Docs-Sync bei Änderungen.
- [ ] Optional: Plan vollständig umgesetzt.

---

## Copy-Paste-Prompt (für einen anderen Agenten)

```
Führe für die Connect-Phase der Research-Pipeline dieselbe Arbeit durch wie für das Memory/Brain-System: vollständige Tiefenanalyse, SOTA/Novel-Recherche und ein konkreter Weltklasse-Plan, damit die Forschung für diese Phase stattfindet.

Vorgehen:
1. Lies und befolge die Anweisungen in operator/docs/PROMPT_CONNECT_PHASE_WORLDCLASS.md vollständig.
2. Erstelle operator/docs/CONNECT_PHASE_DEEP_DIVE.md (Datenfluss, research_entity_extract.py, research_reason.py contradiction_detection/hypothesis_formation, thesis.json, contradictions.json, Probleme/Lücken, SOTA/Novel-Möglichkeiten). Quelle der Wahrheit: operator/workflows/research-cycle.sh (connect-Branch), operator/workflows/research/phases/connect.sh, operator/tools/research_entity_extract.py, operator/tools/research_reason.py.
3. Erstelle operator/docs/CONNECT_PHASE_WORLDCLASS_PLAN.md (Leitbild, SOTA-Überblick zu Contradiction Detection / Hypothesis Generation / Knowledge Graph, Ist-Zustand, Ziele, phasierter Plan mit Abnahme, optional Erfolgsbedingungen, Priorisierung, Metriken). Orientiere dich an operator/docs/MEMORY_BRAIN_WORLDCLASS_PLAN.md.
4. Halte die Dokumentation mit dem Code synchron (docs-sync-with-code). Bei Implementierung: alle Phasen des Plans umsetzen, Tests und Docs aktualisieren.

Qualitätsanspruch: Produktionsreif, korrekt, von Anfang bis Ende durchdacht – gleicher Standard wie beim Memory/Brain-System.
```
