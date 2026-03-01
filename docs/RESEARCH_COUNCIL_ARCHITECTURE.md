# The Research Council: Architektur & Deep Dive

Ein Systementwurf, um aus isolierten Follow-up-Läufen ein echtes kollaboratives "Forschungslabor" zu machen, das am Ende tiefgreifendes Wissen synthetisiert und an das "Brain" (Memory) reportet.

## 1. Vision: Das Forschungslabor

Wenn wir aktuell ein Thema untersuchen, erzeugen wir aus den "Next Steps" 3 Follow-up-Projekte. Bisher waren das einfach 3 unabhängige "Mitarbeiter", die danach nach Hause gegangen sind.
Ab jetzt wird ein **Principal Investigator (PI)** Agent eingeführt. Seine Rolle:
1. Er wartet, bis alle Mitarbeiter aus dem Labor (Sandbox-Experimente) und der Bibliothek (Report-Synthese) zurück sind.
2. Er setzt ein **Council Meeting** an.
3. Er holt sich das Vorwissen aus dem **Memory/Brain**.
4. Er verschmilzt Theorie, Code-Experimente und Erkenntnisse zu einem Master-Dossier.
5. Er **reportet die Essenz an das Brain zurück**, damit das System dauerhaft schlauer wird.

---

## 2. Der Ablauf (End-to-End)

### A. Der Trigger (Das Warten auf das Team)
In `run-research-cycle-until-done.sh` (oder am Ende der `research-cycle.sh`):
Wenn ein Projekt den Status `done` erreicht, wird geprüft:
- Hat dieses Projekt ein `parent_project_id`?
- Wenn ja: Gehe zum Parent und prüfe alle seine Follow-ups.
- Sind **alle** Kinder auf `done` (oder terminal `failed`)?
- Wenn ja $\rightarrow$ Setze einen Lock beim Parent und starte den **Council Run** (`research_council.py parent_id`).

### B. Input Gathering (Die Vorbereitung)
Das Skript `research_council.py` wird mit der `parent_id` aufgerufen und sammelt:
1. **Parent-Daten:** Den ursprünglichen Hauptreport (`report.md`) und das Parent-`experiment.json`.
2. **Child-Daten:** Für jedes Follow-up-Projekt:
   - Den finalen Report.
   - Die `experiment.json` (Sandbox Code-Iterationen, Errors, Successes).
   - Die `contradictions.json` (Welche internen Widersprüche wurden in den Teilbereichen gefunden?).
3. **Brain-Input:** Der PI-Agent fragt die `Memory`-DB nach den aktuellen `Principles` in dieser Domain. Er will wissen: *"Welche Grundregeln gelten hier laut Brain, und haben meine Agenten diese gerade bestätigt oder widerlegt?"*

### C. The Council Meeting (Cross-Pollination)
Der PI-Agent (am besten ein sehr fähiges Modell wie `gpt-4.5` oder `gemini-3.1-pro`, weil der Kontext riesig wird) bekommt einen systemischen Prompt:

> *"Du bist der Principal Investigator. Dein Labor hat 4 Untersuchungen zu {Thema} durchgeführt. Einer deiner Agenten hat die Theorie durchleuchtet, die anderen haben Code in der Sandbox getestet. Lese ihre Berichte und Experiment-Logs. Deine Aufgabe: Finde die versteckten Verbindungen. Wenn Agent A an Framework X gescheitert ist und Agent B in einem Paper einen Workaround für X gefunden hat, verknüpfe das. Erstelle das finale Bundle Synthesis Dossier."*

**Schritte des PI-Agenten:**
1. **Konfliktanalyse:** Widersprechen sich die Ergebnisse der Agenten?
2. **Experiment-Review:** Was haben die Code-Sub-Agents in der Sandbox bewiesen, was nicht in der Theorie stand?
3. **Master Dossier Generation:** Ein Bericht (z.B. `MASTER_DOSSIER.md`), der nicht nur zusammenfasst, sondern **neues Wissen** generiert.

### C.1 Sandbox-Validierung der Master-These
Direkt nach dem Schreiben von `MASTER_DOSSIER.md` läuft **`tools/research_council_sandbox.py`**:
- Liest das Dossier, extrahiert **eine** konkrete, testbare These (per LLM).
- Erzeugt daraus ein minimales Python-Skript, das diese These simuliert oder prüft.
- Führt das Skript in der gleichen sicheren Docker-Sandbox aus wie die Follow-up-Experimente.
- Schreibt `council_sandbox_result.json` und **hängt** einen Abschnitt „Sandbox Validation“ an `MASTER_DOSSIER.md` an (PASS/FAIL, Stdout/Stderr).
Damit hat der Master Report nicht nur Theorie, sondern mindestens einen automatischen Sandbox-Check der zentralen These.

**Was PASS bedeutet (und was nicht):** Ein PASS zeigt, dass *in dieser einen Laufkonfiguration* die Selektionslogik (Mutation → nur bessere Utility akzeptiert, innerhalb der Resource-Bounds) funktioniert. Das ist *nicht* ein Beweis für FME im strengen Sinn (keine Langzeit-Stabilität über Generationen, keine Garantie gegen versteckte Seiteneffekte oder lokale Optimierung auf Kosten globaler Stabilität). Um stillem Drift und Selbsttäuschung vorzubeugen, sind Langzeit-Metriken nötig (z. B. Utility-Drift, Rewrite-Count, Stability-Over-Time über viele Iterationen). Siehe ggf. `docs/COUNCIL_SANDBOX_CAVEATS.md`.

### D. Brain Reporting (Das System wird schlauer)
Nachdem das Master-Dossier geschrieben wurde, führt der PI-Agent eine **"Debriefing-Sitzung mit dem Brain"** durch.
Er extrahiert 1-3 **Mega-Principles** aus der gesamten Bündel-Aktion:
- *"Generelle Erkenntnis für zukünftige Forschungen: Sandbox-Experimente mit Framework X schlagen meistens wegen Dependency Y fehl. Verwende stattdessen Z."*
Diese Erkenntnisse werden via `mem.insert_principle` (domain, description, evidence, confidence, principle_type) in die Memory-Datenbank injiziert.

### E. UI & Sichtbarkeit
- Beim Parent-Projekt in der UI entsteht ein neuer Reiter oder eine prominente Box: **"Council Synthesis"**.
- Status-Anzeige: *"Warte auf Abschluss der Laborarbeit (2/3 Follow-ups fertig)..."*
- Nach Abschluss: Das **Master Dossier** wird als Krönung der Recherche präsentiert.
- Im Memory-Tab sieht man das "Debriefing" des PI-Agenten an das System-Brain.

---

## 3. Architektur der Implementierung

1. **`tools/research_council.py`**
   - Das Kernstück. Nutzt `research_common.llm_call`.
   - Greift auf `lib.memory` zu für den Brain-Sync.
   - Schreibt `MASTER_DOSSIER.md` im Parent-Ordner; `tools/research_council_sandbox.py` schreibt `council_sandbox_result.json` und hängt die Sandbox-Validierung an das Dossier an. Status: `project.json` → `council_status`.

2. **Trigger in `workflows/research-cycle.sh`**
   - Am Ende des `synthesize` / `done` Blocks:
   - Führe ein kurzes Python-Check-Skript aus: `check_trigger_council.py <project_id>`.
   - Wenn das Skript "GO" sagt, spawne `research_council.py <parent_id>` asynchron.

3. **Backend-API & UI-Anpassung**
   - `getResearchProject` (in `research.ts`) prüft, ob eine `MASTER_DOSSIER.md` existiert.
   - Die UI (`ResearchProjectPage`) zeigt das Dossier und den Status des "Research Councils" an.

## 4. Warum das Weltklasse ist
- **Es überwindet die "Single-Agent-Isolation"**: KI-Forschungssysteme leiden oft darunter, dass Agenten nicht miteinander reden. Hier erzwingen wir eine Zusammenführung der gesammelten Evidenz.
- **Theorie trifft Praxis**: Da wir die Sandbox-Ergebnisse (`experiment.json`) zwingend mit den Text-Reports kombinieren, kann der PI-Agent Theorie und Praxis abgleichen.
- **Wissensakkumulation**: Durch das explizite Reporting an das "Brain" (Memory) geht das zusammengeführte Meta-Wissen nicht in einem PDF verloren, sondern lenkt künftige, völlig neue Research-Runs in die richtige Richtung.