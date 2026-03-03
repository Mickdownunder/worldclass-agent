# Research Council V2: Vom "Zusammenfasser" zum "Forschungsleiter" (The Scientific Method)

## 1. Die Vision: Autonome Forschungs-Schleifen

Aktuell ist der Workflow starr: `Parent -> User klickt -> 3 Follow-ups -> Council -> Ende`.
Das Problem: Der Council (Principal Investigator / PI) kommt nur am Ende als "Zusammenfasser" zusammen.

**Zukunft (V2): Vollautomatische Rekursion.**
Der User startet nur noch den initialen Parent Run. Ab dann übernimmt der Council das Steuer:
1. Parent schreibt Bericht.
2. Council liest Bericht und entscheidet **eigenständig**, wie viele und welche Follow-ups es braucht.
3. Council **schickt die Follow-ups los** (ohne User-Klick).
4. Follow-ups kommen zurück (mit Reports und Sandbox-Ergebnissen).
5. Council tritt wieder zusammen, wertet aus und entscheidet: **Ist das Problem gelöst?**
   - Wenn NEIN: Spawnt die nächste Generation Follow-ups.
   - Wenn JA: Schreibt das finale Master Dossier und beendet den Prozess.

Der Ablauf wiederholt sich autonom, bis das Problem geknackt ist (oder ein Token-Sicherheitslimit greift).

---

## 2. Der neue Workflow

### Phase 1: Parent Research
- Läuft wie bisher (Init, Synthesize).
- Endet mit dem Parent-Report.

### Phase 2 (NEU): Council "Planning & Dispatch"
- **Trigger:** Sobald der Parent (oder eine Follow-up-Generation) fertig ist, startet automatisch der Council (`research_council.py` im Planning-Modus).
- **Input:** Alle bisherigen Reports, Sandbox-Logs und das "Brain".
- **Entscheidung:** Der PI wertet aus: "Problem gelöst?"
  - Wenn JA $\rightarrow$ Master Dossier schreiben, Sandbox-Check machen, ins Brain speichern (Ende).
  - Wenn NEIN $\rightarrow$ Der PI entwirft 1-N neue "Research Missions" (inkl. Hypothesen für die Sandbox).
- **Autonome Ausführung:** Das Skript ruft *sofort* `op job new` für jede dieser Missions auf und feuert die nächste Generation an Follow-ups in den Hintergrund (ohne Wartezeit auf den User). Die UI zeigt: *"Council hat Generation X gestartet..."*

### Phase 3: Hypothesis-Driven Follow-ups
- Die gespawnten Agenten laufen los. Ihr Prompt ist geschärft: *"Deine Mission vom PI: Teste Hypothese X in der Sandbox."*
- Sie generieren Code, crashen, lernen, erzeugen `experiment.json` und Report.
- **Trigger:** Wenn der *letzte* Agent dieser Generation `done` ist, springt der Prozess wieder zu **Phase 2 (Council)**.

---

## 3. Technische Umsetzung (Roadmap für morgen)

**Schritt 1: Council als State Machine (`tools/research_council.py`)**
- Das Skript muss den Zustand lesen: Ist das eine "Zwischenauswertung" oder das "Finale"? 
- Wenn das LLM sagt `STATUS: NEEDS_MORE_DATA`, parsen wir die vom LLM generierten Sub-Themen.

**Schritt 2: Autonomer Spawn (Der "Dispatch")**
- Direkt im Python-Skript des Councils rufen wir über `subprocess` für jedes neue Thema den Research-Cycle auf (mit `parent_project_id` auf den Root-Parent).

**Schritt 3: UI-Update (Generationen-Sicht)**
- Die Projekt-Seite (Parent) muss die "Generationen" von Follow-ups anzeigen. Anstatt eines statischen "Team losschicken"-Buttons sieht der User einen Live-Feed: *Generation 1 läuft $\rightarrow$ Council tagt $\rightarrow$ Generation 2 läuft $\rightarrow$ Council tagt $\rightarrow$ Master Dossier.*

**Schritt 4: Endlos-Schleifen-Schutz**
- Eine harte Obergrenze in der Konfiguration (z.B. `MAX_GENERATIONS=3` oder `MAX_SPEND=$10`), damit das System sich nicht bei unlösbaren Problemen totläuft.

## Warum das revolutionär ist
Wir zwingen das LLM aus der "Text-Zusammenfassungs-Falle" heraus und simulieren eine echte Hierarchie:
**Kreativer Planer (PI) $\rightarrow$ Präziser Ausführer (Follow-up/Sandbox) $\rightarrow$ Kritischer Gutachter (PI).**
Genau so funktioniert echte Wissenschaft.
