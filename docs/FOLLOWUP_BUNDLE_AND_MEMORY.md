# Follow-up-Bündel und Memory/Brain

## Verknüpfung: Die 3 Runs wissen, dass sie zusammengehören

- **Beim Erzeugen:** Jedes Follow-up-Projekt bekommt in `project.json` das Feld **`parent_project_id`** (das Projekt, von dem aus „Aus Next Steps neue Projekte erstellen“ geklickt wurde).
- **In der UI:** Auf der Projekt-Detailseite siehst du:
  - **Bei Follow-up-Projekten:** „Follow-up von proj-…“ mit Link zum Parent.
  - **Beim Parent:** „Follow-up-Projekte: proj-…, proj-…, proj-…“ mit Links zu den Kindern.
- **Memory/Brain:** Jeder Run wird wie gewohnt als **run_episode** mit seiner `project_id` gespeichert. Die Verknüpfung „gehört zu Parent“ steckt in `project.json` und in der UI; die Episode selbst hat weiterhin nur `project_id`. Eine spätere Erweiterung könnte `parent_project_id` auch in run_episodes oder in der Konsolidierung nutzen (z. B. Bündel-Strategien).

## Wissensfluss nach dem Run

- **Pro Run:** Am Ende eines Research-Cycles schreibt die Pipeline eine **run_episode** (Frage, Phase, Status, Critic-Score, what_helped/what_hurt, Strategy, etc.). Findings können per **research_embed** in die Memory-DB (research_findings, Embeddings) fließen.
- **Konsolidierung:** Das Nacht-Job bzw. manuell gestartete **memory_consolidate.py** wertet **alle** run_episodes aus (nach Domain), baut/aktualisiert **strategy_profiles** und synthetisiert **principles**. Die 3 Follow-up-Runs fließen also mit allen anderen Runs in dieselbe Wissensbasis – nach Domain, nicht nach „Bündel“. Das Wissen wird gebündelt, indem es in Strategies und Principles landet; die Bündel-Zugehörigkeit (Parent/Children) ist in der UI sichtbar und in `project.json` gespeichert.
- **Nächste Research-Starts:** Beim nächsten „Forschung starten“ oder weiteren Follow-ups nutzt **research_knowledge_seed** die gleichen Strategies/Principles und prior knowledge – inklusive der Ergebnisse aus den 3 Follow-up-Runs, sofern sie in die gleiche Domain fallen.

## Welche „Intelligenz“ nutzen Follow-ups, um am Thema weiterzuforschen?

Aktuell:

1. **Fragen aus dem Hauptreport**  
   Die Follow-up-Fragen kommen aus „5) Suggested Next Steps“. Dadurch sind sie **inhaltlich am gleichen Thema** – das ist die wichtigste Steuerung.

2. **Memory/Brain (prior knowledge)**  
   Beim Anlegen des Projekts läuft **research_knowledge_seed.py**: Es holt aus dem Memory **Principles** und **Findings** per **semantischer Ähnlichkeit zur Follow-up-Frage** (und Utility). Wenn der Hauptrun (oder andere Runs in der Domain) schon Principles/Findings ins Memory geschrieben haben, bekommt das Follow-up dieses Vorwissen. So bleibt es thematisch dran – **indirekt** über die Frage und das, was Memory zu dieser Frage zurückgibt.

3. **Domain**  
   Beim Anlegen eines Follow-ups wird die **Domain vom Parent übernommen** (wenn der Parent eine andere als `general` hat). So nutzen Follow-ups dieselbe Domain für Strategies/Principles und bleiben stärker im gleichen Themenbereich.

4. **Was heute nicht passiert**  
   Es wird **nicht** explizit übergeben: Parent-Report, Parent-Findings oder Parent-Playbook. Es gibt also kein klares „Hier ist der Hauptreport, forsche daran weiter“ – nur die Frage (aus Next Steps) und das, was Memory zur Frage liefert.

**Kurz:** Die „Intelligenz“, die Follow-ups am Thema hält, ist (a) die **Herkunft der Fragen** (Next Steps), (b) das **Memory-Retrieval** (Principles/Findings zur Follow-up-Frage) und (c) die **Domain-Vererbung** vom Parent (gleiche Domain → gleiche Strategies/Principles).

---

## Woher kommen die Follow-up-Themen? Bleibt es im Thema?

- **Quelle:** Die Follow-up-Fragen werden aus dem Abschnitt **„5) Suggested Next Steps“** des **Hauptreports** erzeugt. Ein LLM liest diese Sektion (oder den Report-Ausschnitt) und gibt 2–3 **konkrete, recherchierbare Forschungsfragen** aus (JSON).
- **Thematik:** Die Fragen stammen aus demselben Report – sie sind also **im gleichen übergeordneten Thema** (z. B. Multi-Agent-Systeme, Selbstreplikation). Sie sind aber **eigenständige Teilfragen** (Vertiefung, Nebenäste, Lücken), kein 1:1-Abgleich. Das System „gleicht“ inhaltlich nicht automatisch ab; es **vertieft und erweitert** das Thema an den Stellen, die der Hauptreport als Next Steps vorgeschlagen hat.
- **Domain:** Follow-ups erben keine explizite Domain vom Parent; die Domain wird pro Projekt aus der Frage/Playbook ermittelt. Für Memory/Konsolidierung zählt die Domain – ähnliche Themen landen oft in derselben Domain und fließen gemeinsam in Strategies/Principles.

## Ein Hauptreport vs. mehrere Reports – was ist besser?

**Aktuell:** Es gibt **4 getrennte Reports** (1 Hauptrun + 3 Follow-ups). Jeder Run schreibt seinen eigenen Report; es gibt **keinen automatischen „Hauptreport“**, der alle vier zusammenführt oder abgleicht.

**Vorteile mehrerer Reports (Status quo):**
- **Tiefe pro Frage:** Jeder Report geht voll auf eine spezifische Frage ein; keine Vermischung.
- **Nachvollziehbarkeit:** Du siehst genau, welcher Run welche Antwort geliefert hat (Claim Evidence, Quellen).
- **Memory/Brain:** Alle 4 Runs fließen in run_episodes und Konsolidierung; das System lernt aus allen.

**Vorteile eines zusätzlichen „Hauptreports“ (Bündel-Synthese):**
- **Eine Story:** Ein Dokument, das Hauptreport + 3 Follow-ups zusammenfasst, Widersprüche oder Lücken benennt und Handlungsempfehlungen bündelt.
- **Abgleich:** Ein optionaler Schritt könnte explizit „abgleichen“ (Konsistenz, Priorisierung, nächste Schritte aus allen 4).

**Empfehlung für „echt gute Infos“:**
- **So lassen und nutzen:** Die 4 Reports einzeln lesen; über die UI (Follow-up von / Follow-up-Projekte) siehst du die Verknüpfung. Für tiefe, saubere Infos pro Teilfrage ist das ideal.
- **Optional später:** Ein Feature **„Bündel-Synthese“** (z. B. Button „Master-Report aus Haupt + Follow-ups erzeugen“ wenn alle 4 done sind): Ein Job liest die 4 Reports, erzeugt einen **Master-Report** (Zusammenfassung, Abgleich, eine narrative Story). Dann hast du beides: die 4 Detail-Reports und einen übergeordneten Hauptreport.

## Kurz

- **Bündel:** Parent und die 3 Follow-up-Projekte sind über `parent_project_id` und die UI („Follow-up von“ / „Follow-up-Projekte“) verknüpft.
- **Thema:** Follow-ups bleiben im Thema (aus Next Steps des Hauptreports), sind aber eigene Teilfragen; kein automatisches inhaltliches Abgleichen, sondern Vertiefung.
- **Wissen:** Alle Runs (Parent + Follow-ups) landen in Memory (run_episodes, ggf. findings); Konsolidierung bündelt das Wissen domänenweise in Strategies und Principles. Ein gemeinsamer „Bündel-Report“ (Master-Report) wird aktuell nicht automatisch erzeugt – das wäre eine optionale Erweiterung (z. B. „Master-Report aus Bündel erzeugen“).
