# Research Council V2: Vom "Zusammenfasser" zum "Forschungsleiter" (The Scientific Method)

## 1. Die Vision: Echte Arbeitsteilung
Aktuell ist der Council (Principal Investigator / PI) nur am Ende aktiv: Er liest die Ergebnisse der Follow-ups und fasst sie zusammen. 
**Das Problem:** Die Follow-ups basieren auf den generischen "Next Steps" des Parent-Reports. Es fehlt das zielgerichtete *Experiment-Design*.

**Zukunft (V2):** Der Council tritt **zweimal** zusammen. 
1. **Planning Session:** Nach dem Parent-Report analysiert der PI die Ergebnisse, verwirft langweilige Pfade und entwirft 1-3 **knallharte, testbare Hypothesen** für die Sandbox.
2. **Synthesis Session:** Nach den Follow-ups führt der PI die Ergebnisse zusammen (wie heute).
3. **Rekursion:** Der PI entscheidet am Ende: *"Ist das Problem gelöst, oder brauchen wir eine Generation 2 (Gen-2) an Follow-ups?"*

---

## 2. Der neue Workflow

### Phase 1: Parent Research
- Läuft wie bisher (Init, Synthesize).
- Endet mit dem Parent-Report.

### Phase 2 (NEU): Council Planning Session
- **Trigger:** Sobald der Parent fertig ist, startet automatisch `tools/research_council_planning.py`.
- **Input:** Parent-Report + "Brain" (Vorwissen).
- **Task:** Der PI-Agent spielt "Experiment Designer". Er definiert genau, was das Labor testen soll.
- **Output:** `council_plan.json` mit 1-3 konkreten "Research Missions" (inkl. Hypothese, die in der Sandbox getestet werden muss).
- **UI:** Anstatt der generischen "Next Steps" zeigt die Projektseite jetzt den "PI Experiment Plan". Ein Klick auf "Team losschicken" spawnt die Follow-ups mit diesen exakten Hypothesen.

### Phase 3: Hypothesis-Driven Follow-ups
- Die Follow-ups laufen los, aber ihr Prompt wird geschärft: *"Deine Mission (vom PI): Teste Hypothese X in der Sandbox."*
- Sie generieren den Code, erzeugen `experiment.json` und ihren Report.

### Phase 4: Council Synthesis & Rekursion
- **Trigger:** Wenn alle Kinder fertig sind, läuft `research_council.py` (wie heute).
- **Zusatz (NEU):** Der PI bewertet, ob das Gesamtziel erreicht wurde.
- **Entscheidung:**
  - `SOLVED`: Schreibt Master-Dossier, macht Sandbox-Check, speichert ins Brain (Status Quo).
  - `NEEDS_MORE_RESEARCH`: Schreibt ein Zwischen-Dossier und generiert sofort eine **neue** `council_plan.json` für Gen-2. Die UI zeigt: *"Runde 1 fertig. PI fordert Runde 2 an."*

---

## 3. Technische Umsetzung (Roadmap für morgen)

**Schritt 1: Das Planning-Skript (`tools/research_council_planning.py`)**
- Baut einen Prompt, der aus dem Parent-Report einen harten Forschungsplan macht.
- Speichert `council_plan.json` im Parent-Ordner.

**Schritt 2: UI-Update für den PI-Plan**
- Die Projekt-Seite (Parent) liest `council_plan.json`.
- Die Follow-up-Erstellung (UI/API) nutzt diese Daten anstatt der "Next Steps" aus dem Markdown.

**Schritt 3: Schärfung des Follow-up-Prompts**
- Wenn ein Projekt aus einem `council_plan` erstellt wird, wird das Feld `hypothesis_to_test` mitgegeben, damit die Experiment-Phase exakt weiß, was der Boss sehen will.

**Schritt 4: Rekursions-Logik (Optional / Stufe 2b)**
- `research_council.py` um das Output-Feld `status: "solved" | "needs_gen2"` erweitern.

## Warum das revolutionär ist
Wir zwingen das LLM aus der "Text-Zusammenfassungs-Falle" heraus und simulieren eine echte Hierarchie:
**Kreativer Planer (PI) $\rightarrow$ Präziser Ausführer (Follow-up/Sandbox) $\rightarrow$ Kritischer Gutachter (PI).**
Genau so funktioniert echte Wissenschaft.
