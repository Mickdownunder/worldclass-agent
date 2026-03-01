# The Research Council (Bündel-Forschung)

Ein Konzept für echte, kollaborative Multi-Agenten-Forschung.

## Das Problem heute
Wir haben einen Haupt-Run. Dieser liefert einen Report und generiert 3 „Follow-ups“ (Next Steps). 
Diese 3 Follow-ups starten als isolierte Projekte. Sie forschen tief, schreiben Code, machen Experimente in der Sandbox.
**Aber:** Am Ende liegen 4 getrennte Reports auf dem Tisch. Die Agenten reden nicht miteinander. Niemand fügt die Puzzleteile („Agent 1 hat herausgefunden, dass X nicht klappt“, „Agent 2 hat in einem Paper die Lösung für X gefunden“) zusammen.

## Die Lösung: Der „Research Council“ (Die Besprechung)

Wir bauen das System so um, dass ein **Forschungs-Bündel** (Parent + Follow-ups) wie ein echtes Forscherteam arbeitet.

### Phase 1: Delegation (Die Aufgabenverteilung)
1. **Parent-Projekt** ist fertig. Der Report zeigt Wissenslücken.
2. Der „Lead Researcher“ (das System) definiert 3 Follow-up-Missionen.
3. 3 **Child-Projekte** werden gestartet. Jedes bekommt ein klares Ziel (z.B. „Du suchst nach Papern zu X“, „Du schreibst Code-Prototypen in der Sandbox für Y“).

### Phase 2: Deep Dive & Experiments (Die Feldarbeit)
1. Die 3 Projekte laufen völlig autark und parallel.
2. Sie lesen, evaluieren, spawnen Code-Agenten, crashen in der Docker-Sandbox, reparieren den Code.
3. Jedes Projekt schließt ab und speichert seine **Findings**, **Experiment-Logs** und seinen **Report**.

### Phase 3: The Council Meeting (Die Synthese)
Das ist das neue, fehlende Element. Sobald alle 3 Follow-ups den Status `done` haben, triggert das System automatisch den **Research Council**.

1. **Input:** Das System lädt den Hauptreport, die 3 Follow-up-Reports und vor allem die `experiment.json` (Code-Ergebnisse) aller Agenten.
2. **Die Debatte (LLM-Processing):** Ein „PI Agent“ (Principal Investigator) analysiert die Schnittmengen:
   - *„Agent A hat in der Sandbox bewiesen, dass Framework Z zu langsam ist.“*
   - *„Agent B hat ein Paper gefunden, das einen Workaround für genau dieses Framework Z beschreibt.“*
   - Der PI-Agent **verknüpft** diese Entdeckungen. Er merkt, dass B die Lösung für das Problem von A hat.
3. **Der Master-Report:** Der Council erzeugt ein finales Dokument: **Das „Bundle Synthesis Dossier“**.
   - Keine bloße Zusammenfassung, sondern eine **neue Erkenntnisebene**.
   - Es zeigt Widersprüche auf, die zwischen den Agenten entstanden sind, und löst sie auf.
   - Es generiert die endgültige „State of the Art“-Antwort auf die allererste Ursprungsfrage.

## Wie setzen wir das technisch um?

1. **Trigger:** Ein Job, der regelmäßig prüft: *„Gibt es ein Parent-Projekt, bei dem alle Kinder `done` sind?“*
2. **Council-Skript:** Ein neues Script `research_council.py`.
   - Liest alle `reports/*.md` und `experiment.json` der Kinder.
   - Führt einen LLM-Prompt aus: *„Du bist der Lead Researcher. Deine 3 Teams haben folgende Daten gebracht... Verbinde die Entdeckungen, löse Konflikte, schreibe den Master-Report.“*
3. **Speicherort:** Der Master-Report wird direkt im Verzeichnis des **Parent-Projekts** (z.B. als `MASTER_REPORT.md`) abgelegt und in der UI als das **ultimative Ergebnis** des gesamten Bündels präsentiert.
