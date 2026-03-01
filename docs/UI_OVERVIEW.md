# Wie das System über die UI funktioniert — und wie du es verstehst

Die UI ist das **Dashboard** für den Operator. Du loggst dich ein, siehst Status und Research-Projekte, startest Workflows und liest Reports. Alles läuft gegen den Operator auf dem Server (`OPERATOR_ROOT`, z.B. `/root/operator`).

---

## 1. Einstieg: Login und Command Center

- **Login:** Ein Nutzer, Passwort (Hash in `UI_PASSWORD_HASH`). Session über Cookie.
- **Nach dem Login:** Du landest im **Command Center** (`/`).

**Command Center zeigt:**

- **System-Health:** Status OK/Eingeschränkt, Disk, Load, fehlgeschlagene Jobs.
- **Aktive Research-Projekte:** Liste mit Phase, Findings-Anzahl, Fortschrittsbalken (explore → … → synthesize). Klick → Projekt-Detail.
- **Letzte Aktionen:** Event-Feed (was zuletzt passiert ist).
- **Quick-Actions:** Factory, Brain Cycle etc. (mit Bestätigung).
- **Links:** Neues Research-Projekt, Jobs, Packs, Brain & Memory.

**So verstehst du es:** Das Command Center ist die **Startseite**. Von hier aus siehst du, ob das System gesund ist und ob Research-Projekte laufen. Alles Weitere (Research starten, Projekt öffnen, Jobs) geht von hier oder über die Nav.

---

## 2. Research: Projekte starten und steuern

### Research-Übersicht (`/research`)

- **Liste aller Research-Projekte:** Tabelle mit Projekt-ID, Frage, Status/Phase, Anzahl Findings, Anzahl Reports, Link „Öffnen“.
- **Neues Projekt:** Formular **„Neues Research-Projekt“** (auf dieser Seite oder über den Button „Neues Research-Projekt“ im Command Center).

**Formular „Neues Research-Projekt“ (Standard/Frontier):**

- **Frage:** Was willst du erforschen? (Pflicht)
- **Playbook:** Allgemein, Marktanalyse, Literatur-Review, Patent-Landscape, Due Diligence (wird mitgeschickt).
- **Research-Modus:** standard | frontier | discovery (beeinflusst Evidence Gate, Claim-Verifikation, Conductor, Synthese, Critic; siehe `docs/RESEARCH_MODES.md`).
- **Aktion:** „Forschung starten“ → `POST /api/research/projects` mit `{ question, playbook_id, research_mode }`.

**Discovery Research – eigener Menüpunkt und eigene Seite (`/research/discovery`):**

- **Nav:** Punkt **„Discovery Research“** führt zu `/research/discovery`.
- **Eigenes Formular:** Nur eine Frage (offen, ambitioniert), Platzhalter z. B. „Wie können wir Krebs heilen? Welche neuen Ansätze gibt es?“; kein Playbook-, kein Research-Mode-Dropdown. `research_mode` ist fest **discovery**. Aktion „Discovery starten“ → gleiche API mit `research_mode: "discovery"`. Discovery wird damit **komplett anders getriggert**; alle Phasen (Explore, Focus, Connect, Verify, Synthesize) laufen im Discovery-Modus anders (Evidence Gate, Conductor, Discovery Analysis, Novelty-Critic). Siehe `docs/RESEARCH_MODES.md`.

**Was passiert technisch (Standard = „bis Report fertig“):**

1. UI sendet `POST /api/research/projects` mit Frage, Playbook, `research_mode` (standard | frontier | discovery). Default: `run_until_done === true`. Unterschiede der Modi: `docs/RESEARCH_MODES.md`.
2. Backend ruft **`runResearchInitAndCycleUntilDone(question, researchMode)`** auf: erstellt Job `research-init`, wartet auf Abschluss, liest `project_id` aus Artifacts, startet dann **`run-research-cycle-until-done.sh`** im Hintergrund (alle Phasen bis done).
3. Antwort: „Projekt angelegt. Alle Phasen laufen automatisch – Report erscheint, wenn fertig.“ + `jobId`, `projectId`.
4. Beim nächsten Laden erscheint das Projekt in der Liste; Phasen laufen ohne weiteres Klicken bis Report fertig.

**Ohne „bis fertig“** (nur Init): Request mit `run_until_done: false` → Backend nutzt nur `runWorkflow("research-init", …)`; dann musst du „Nächste Phase starten“ manuell nutzen.

**So verstehst du es:** Standard = **ein Klick startet Init + alle Cycles bis done**. Die UI startet den Init-Job, wartet auf Projekt-ID, dann läuft `run-research-cycle-until-done.sh` detached. Du siehst Fortschritt durch Refresh/Navigation.

---

### Research-Projekt-Detail (`/research/[id]`)

- **Kopf:** Link „← Research“, Projekt-ID als Titel.
- **Infobox:** Frage, Status-Badge, **Research-Modus-Badge** (Standard / Frontier / Discovery), Phase, Anzahl Findings/Reports/Feedback, **Fortschrittsbalken** (explore → focus → connect → verify → synthesize). Mögliche Status u. a.: done, failed (Evidence Gate / Critic), **failed_conductor_tool_errors** (Conductor run_cycle nach mehreren Tool-Fehlern abgebrochen), **aem_blocked** (AEM enforce/strict blockiert Synthese).
- **Evidence Gate (nach Verify):** Im Projekt-Detail wird bei vorhandenem Gate die Metrik **„Read Success (Explore + Focus)“** angezeigt; der Wert ist die **kumulierte** Read-Statistik aus `explore/read_stats.json` und `focus/read_stats.json` (wie vom Evidence Gate berechnet).
- **Research Intelligence (neu):** Auf der Projekt-Detailseite wird ein Panel **„Research Intelligence“** angezeigt, sobald Daten vorliegen: **Token Governor** (Lane: cheap/mid/strong für Verify/Synthesize/Critic), **Thesis** (Connect-Phase), **Contradictions** (Anzahl + Vorschau), **Fact-Check** (confirmed/disputed/unverifiable), **Claim Ledger** (verified/authoritative/unverified/in_contradiction). Quelle: `project.json`, `thesis.json`, `contradictions.json`, `governor_lane.json`, `verify/fact_check.json`, `verify/claim_ledger.json` (über `getResearchProject`).
- **Button „Nächste Phase starten“:** Nur sichtbar, wenn Status ≠ done. Startet **einen** research-cycle-Job für dieses Projekt.

**„Nächste Phase starten“:**

1. UI sendet `POST /api/research/projects/[id]/cycle`.
2. Backend prüft: Projekt vorhanden, nicht „done“. Prüft **Projekt-Level-Lock** (progress.json `alive` oder bereits laufender Cycle): wenn ein Cycle für dieses Projekt läuft → **409 Conflict** mit Meldung „Ein Cycle läuft bereits für dieses Projekt.“
3. Sonst: `runWorkflow("research-cycle", projectId)` → `op job new` + `op run`. In `research-cycle.sh` hält ein **flock** auf `research/proj-…/.cycle.lock` den zweiten gleichzeitigen Cycle für dasselbe Projekt ab (sofortiger Exit 0).
4. Antwort: „Nächste Phase wird gestartet (Job läuft).“
5. Nach Refresh siehst du ggf. neue Phase, mehr Findings, neuen Report.

**Tabs: Report | Critique | Findings | Sources | History | Audit**

- **Report:** Neuester Report als Markdown: UI liest `reports/manifest.json` und wählt den Eintrag mit `is_final: true` bzw. letzten Eintrag; Fallback: neueste `reports/report_*.md` nach Dateiname. Enthält u. a. Claim Evidence Registry, Provenance, Appendix B, References. Download als .md möglich. Wenn ein Report existiert, aber keine PDF: Button **„Generate PDF“** (erzeugt PDF nachträglich per `research_pdf_report.py`, z. B. wenn WeasyPrint im Job fehlte). Wenn PDF vorhanden: **„Download PDF“**. Unter der Quality-Score-Zeile: aufklappbare **Critic Weaknesses** (erste 2) mit Link „View full critique“ → wechselt zum Critique-Tab.
- **Critique:** Bewertung des Critics aus `research/proj-…/verify/critique.json` (Score, Weaknesses, Suggestions, ggf. Strengths). Lazy-Load über `GET /api/research/projects/[id]/critique`; 404 wenn noch keine Kritik.
- **Findings:** Liste aus `GET /api/research/projects/[id]/findings` (findings/*.json). Pro Finding: Feedback-Buttons (Excellent, Irrelevant, Falsch, Tiefer graben) → `POST /api/research/feedback`.
- **Sources:** Liste aus `GET /api/research/projects/[id]/sources` (sources).
- **History:** Liste aller Reports (Dateinamen + Inhalt) aus `GET /api/research/projects/[id]/reports`.
- **Audit:** Verifizierte Claims und Beweislage aus `GET /api/research/projects/[id]/audit` (für Qualitätsprüfung).

**Memory Applied Panel (Research-Detail):**

- Wenn `RESEARCH_MEMORY_V2_ENABLED=1` aktiv ist und eine Strategy gewählt wurde, zeigt die Detailseite zusätzlich ein Panel **„Memory Applied“**.
- Sichtbar: gewählte Strategy, Confidence, aktive Regeln (`relevance_threshold`, `critic_threshold`, `revise_rounds`), Query-Type-Mix und Domain-Overrides.
- Zusätzlich sichtbar: **Mode Badge** (`v2_applied | v2_fallback | v2_disabled`), Fallback-Grund und Confidence-Drivers (warum diese Strategy gewählt wurde).
- Quelle: `research/proj-*/memory_strategy.json` (wird beim Planning geschrieben).

**Live Activity & Runtime-Status („Läuft es oder hängt es?“):**

- Die UI pollt `GET /api/research/projects/[id]/progress`. Der Endpoint liefert einen **berechneten Laufzeit-Status** (nicht nur „Running/Idle“):
  - **RUNNING:** Heartbeat frisch (< 30s), Step wird ausgeführt.
  - **IDLE:** Kein laufender Prozess, wartet auf Trigger.
  - **STUCK:** Kein Fortschritt seit 5 Min (gleicher Step), Prozess hängt. Bei aktiven Parallel-Workern (`active_steps`) zählt das jüngste Worker-`started_at` als Fortschritt, um False Positives zu vermeiden.
  - **ERROR_LOOP:** Gleicher Fehlercode mehrfach in 5 Min (z. B. Proxy/OpenAI-Fehler).
  - **FAILED / DONE:** Projekt-Status fehlgeschlagen bzw. abgeschlossen.
- Zusätzlich: **Phase**, **aktueller Step**, **letzte Aktivität**, **letzter Fehler** (Code + Meldung), **Ereignis-Timeline** (events.jsonl). So erkennst du zuverlässig, ob gearbeitet wird, ein Fehler-Loop läuft oder du (z. B. mit „Nächste Phase starten“ oder Abbrechen) reagieren solltest.
- **Bei Conductor-Modus** (`RESEARCH_USE_CONDUCTOR=1`): Der aktuelle Step kann u. a. „Conductor: synthesizing report“, „Conductor: running verification“, „Conductor: reading more sources“, „Conductor: searching for more sources“ anzeigen (geschrieben von run_cycle über research_progress).
- **Conductor-Override (Hybrid-Gate):** Wenn der Conductor z. B. focus → explore zurückschickt, wird nach `advance_phase` sofort `progress_start(next_phase)` ausgeführt, damit `progress.json` (Phase + Heartbeat) zur neuen Phase passt. Die UI bleibt damit konsistent und „klebt“ nicht mehr auf der alten Phase/Step.

**So verstehst du es:** Die Detailseite ist die **Steuerung und Anzeige** eines einzelnen Forschungsprojekts. Du siehst Phase und Fortschritt, startest manuell den nächsten Cycle, liest den Report und gibst Feedback. Die UI liest alles aus dem Dateisystem des Operators (`research/proj-…/`); die API-Routen sind dünne Wrapper darüber.

---

## 3. Datenfluss: UI ↔ Operator

| Was du in der UI tust | API / Backend | Operator |
|------------------------|---------------|----------|
| Login | Session-Cookie | — |
| Command Center laden | — | Liest Health, listet `research/proj-*/project.json` |
| „Forschung starten“ | POST /api/research/projects | Default: runResearchInitAndCycleUntilDone → init + run-research-cycle-until-done.sh; optional run_until_done: false → nur research-init |
| „Nächste Phase starten“ | POST /api/research/projects/[id]/cycle | runWorkflow("research-cycle", id) → op job new + op run |
| Projekt-Detail | GET project, report, findings, sources, reports | Liest research/proj-…/project.json, findings/, reports/, etc. |
| Explainability (Memory Applied) | GET project detail | Liest `research/proj-…/memory_strategy.json` und rendert Strategy/Regeln |
| Live-Fortschritt / Status | GET /api/research/projects/[id]/progress | Liest progress.json + events.jsonl, berechnet state (RUNNING/IDLE/STUCK/ERROR_LOOP/FAILED/DONE) |
| Brain-Status (läuft/hängt) | GET /api/health (op healthcheck) | `brain.cycle` / `brain.reflect`: Anzahl, max_elapsed_sec; **stuck** wenn Cycle >10 min oder Reflect >5 min. Zeile im Command Center + Infobox auf Brain & Memory. System gilt als unhealthy wenn stuck. |
| Feedback zu Finding | POST /api/research/feedback | research_feedback.py (Frage/Redirect/Type) |

**Wichtig:** Beim normalen „Forschung starten“ wartet die UI auf Abschluss von research-init (für project_id), dann läuft der Cycle-until-done im Hintergrund. Einzelne „Nächste Phase starten“-Jobs laufen ebenfalls detached. Fortschritt siehst du durch erneutes Laden oder Refresh.

---

## 4. Rest der Nav (kurz)

- **Memory & Graph** (`/memory`): Memory-Value-Karte, Stats (Ereignisse, Run-Episoden, Decisions, Reflections, Ø Qualität, Principles, Outcomes), Tabs: Activity (inkl. Konsolidierungs-Status), Runs (Run-Verlauf v2: was half/schadete, Strategy, Critic), Strategies (Profile & Policies), Principles, Sources, Brain (mit klickbarer Explainability), Utility (Top Memories), Graph (Strategy-Verknüpfungen), Plumber, Knowledge.
- **Audit Logs** (`/jobs`): Job-Liste, Detail, Retry.
- **Agents** (`/agents`): Übersicht **wer läuft und was eingesetzt wird**: Zwei Agent-Karten (Captain = Operator/Brain/Workflows, June = OpenClaw/Telegram) mit Kurzbeschreibung und „Einsatz/Nutzt“-Liste; Workflows nach Kategorie (Research, Brain & Qualität, Factory & Opportunity, Tools, Infrastruktur, Produkt, Sonstige) mit Tabellen und Badge **„Von UI startbar“** für Workflows aus `ALLOWED_WORKFLOWS`. Kurzreferenz zu Research, Brain, Tool-Workflows. Details: `docs/TOOL_AGENT_SYSTEM_AUDIT.md`.
- **Insights** (`/research/insights`): Cross-Domain-Insights (Findings über Projekte hinweg).

(Packs und Clients sind in der UI nicht mehr angeboten; Backend/Factory nutzt weiterhin `factory/packs` und `factory/clients`.)

Alles liest bzw. triggert gegen den gleichen Operator (Dateisystem + `op`).

---

## 5. So behältst du den Überblick

1. **Command Center = Zentrale:** Health, aktive Research-Projekte, Quick-Actions. Von hier aus startest du Research oder gehst in die Details.
2. **Research = Projekte + Phasen:** Ein Projekt = eine Frage, ein Ordner `research/proj-…/`, State in `project.json`. „Forschung starten“ = Init-Job; „Nächste Phase starten“ = ein Cycle-Job. Phasen laufen nacheinander (explore → focus → connect → verify → synthesize → done). Details: Explore `docs/EXPLORE_PHASE_DEEP_DIVE.md`, Focus `docs/FOCUS_PHASE_DEEP_DIVE.md`, Connect `docs/CONNECT_PHASE_DEEP_DIVE.md` (Plan: `docs/CONNECT_PHASE_WORLDCLASS_PLAN.md`), Synthesize `docs/SYNTHESIZE_PHASE_DEEP_DIVE.md` (Plan: `docs/SYNTHESIZE_PHASE_WORLDCLASS_PLAN.md`). **Focus** nutzt Gap-Fill aus Coverage (und bei Verify-Loop-back `verify/deepening_queries.json`), schreibt `focus/read_stats.json` und geht danach in Connect; das Evidence Gate berücksichtigt Explore- und Focus-Read-Statistik gemeinsam.
3. **UI startet Jobs, wartet nicht:** Nach Klick auf „Forschung starten“ oder „Nächste Phase starten“ läuft der Job auf dem Server. Fortschritt = Seite neu laden oder später nochmal ins Projekt gehen.
4. **Report & Feedback:** Im Projekt-Detail liest du den Report, siehst Findings/Sources/Verlauf und gibst Feedback; das Backend schreibt in das Projektverzeichnis und ggf. in die Research-Logik (redirect, Fragen).

Damit ist das System über die UI **sauber durchgängig**: Login → Command Center → Research starten/öffnen → Phasen manuell vorantreiben oder laufen lassen → Report lesen, Feedback geben. Alles über die gleiche Operator-Instanz und dasselbe Dateisystem.
