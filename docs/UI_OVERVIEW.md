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

**Formular „Neues Research-Projekt“:**

- **Frage:** Was willst du erforschen? (Pflicht)
- **Playbook:** Allgemein, Marktanalyse, Literatur-Review, Patent-Landscape, Due Diligence (wird mitgeschickt; Backend nutzt aktuell nur die Frage für `research-init`).
- **Aktion:** „Forschung starten“ → `POST /api/research/projects` mit `{ question, playbook_id }`.

**Was passiert technisch:**

1. UI sendet `POST /api/research/projects` mit Frage (und Playbook).
2. Backend ruft `runWorkflow("research-init", question)` auf.
3. `runWorkflow` erstellt einen Job: `op job new --workflow research-init --request "<question>"`, dann startet `op run <job_dir>` **im Hintergrund** (detached). Die UI wartet nicht auf das Ende des Jobs.
4. Antwort: „Research-Projekt wird erstellt (Job läuft).“ + `jobId`.
5. Beim nächsten Laden der Seite erscheint das neue Projekt in der Liste (sobald `research/proj-…/project.json` existiert).

**So verstehst du es:** Ein Klick auf „Forschung starten“ = **ein research-init-Job wird gestartet**. Die UI startet nur den Job; sie pollt nicht auf Fertigstellung. Du siehst das neue Projekt, sobald der Init-Job das Projektverzeichnis angelegt hat und die Liste wieder geladen wird (z.B. durch Refresh oder Navigation).

---

### Research-Projekt-Detail (`/research/[id]`)

- **Kopf:** Link „← Research“, Projekt-ID als Titel.
- **Infobox:** Frage, Status-Badge, Phase, Anzahl Findings/Reports/Feedback, **Fortschrittsbalken** (explore → focus → connect → verify → synthesize).
- **Button „Nächste Phase starten“:** Nur sichtbar, wenn Status ≠ done. Startet **einen** research-cycle-Job für dieses Projekt.

**„Nächste Phase starten“:**

1. UI sendet `POST /api/research/projects/[id]/cycle`.
2. Backend prüft: Projekt vorhanden, nicht „done“. Ruft `runWorkflow("research-cycle", projectId)` auf.
3. Wie oben: `op job new --workflow research-cycle --request "<projectId>"`, dann `op run` im Hintergrund.
4. Antwort: „Nächste Phase wird gestartet (Job läuft).“
5. Nach Refresh siehst du ggf. neue Phase, mehr Findings, neuen Report.

**Tabs: Report | Findings | Sources | Verlauf**

- **Report:** Neuester Report als Markdown (aus `research/proj-…/reports/*.md`). Download als .md möglich.
- **Findings:** Liste aus `GET /api/research/projects/[id]/findings` (findings/*.json). Pro Finding: Feedback-Buttons (Excellent, Irrelevant, Falsch, Tiefer graben) → `POST /api/research/feedback`.
- **Sources:** Liste aus `GET /api/research/projects/[id]/sources` (sources).
- **Verlauf:** Liste aller Reports (Dateinamen + Inhalt) aus `GET /api/research/projects/[id]/reports`.

**So verstehst du es:** Die Detailseite ist die **Steuerung und Anzeige** eines einzelnen Forschungsprojekts. Du siehst Phase und Fortschritt, startest manuell den nächsten Cycle, liest den Report und gibst Feedback. Die UI liest alles aus dem Dateisystem des Operators (`research/proj-…/`); die API-Routen sind dünne Wrapper darüber.

---

## 3. Datenfluss: UI ↔ Operator

| Was du in der UI tust | API / Backend | Operator |
|------------------------|---------------|----------|
| Login | Session-Cookie | — |
| Command Center laden | — | Liest Health, listet `research/proj-*/project.json` |
| „Forschung starten“ | POST /api/research/projects | runWorkflow("research-init", question) → op job new + op run |
| „Nächste Phase starten“ | POST /api/research/projects/[id]/cycle | runWorkflow("research-cycle", id) → op job new + op run |
| Projekt-Detail | GET project, report, findings, sources, reports | Liest research/proj-…/project.json, findings/, reports/, etc. |
| Feedback zu Finding | POST /api/research/feedback | research_feedback.py (Frage/Redirect/Type) |

**Wichtig:** Die UI **startet** Jobs (research-init, research-cycle), sie **wartet nicht** auf deren Ende. Jobs laufen auf dem Server; Fortschritt siehst du durch erneutes Laden oder Refresh.

---

## 4. Rest der Nav (kurz)

- **Insights** (`/research/insights`): Cross-Domain-Insights (Findings über Projekte hinweg, Similarity).
- **Agents** (`/agents`): Konfigurierte Agents/Clients.
- **Jobs** (`/jobs`): Job-Liste, Detail, Retry.
- **Packs** (`/packs`): Packs-Liste und -Detail.
- **Brain & Memory** (`/memory`): Episoden, Reflexionen, Playbooks.
- **Clients** (`/clients`): Client-Konfiguration.

Alles liest bzw. triggert gegen den gleichen Operator (Dateisystem + `op`).

---

## 5. So behältst du den Überblick

1. **Command Center = Zentrale:** Health, aktive Research-Projekte, Quick-Actions. Von hier aus startest du Research oder gehst in die Details.
2. **Research = Projekte + Phasen:** Ein Projekt = eine Frage, ein Ordner `research/proj-…/`, State in `project.json`. „Forschung starten“ = Init-Job; „Nächste Phase starten“ = ein Cycle-Job. Phasen laufen nacheinander (explore → … → synthesize → done).
3. **UI startet Jobs, wartet nicht:** Nach Klick auf „Forschung starten“ oder „Nächste Phase starten“ läuft der Job auf dem Server. Fortschritt = Seite neu laden oder später nochmal ins Projekt gehen.
4. **Report & Feedback:** Im Projekt-Detail liest du den Report, siehst Findings/Sources/Verlauf und gibst Feedback; das Backend schreibt in das Projektverzeichnis und ggf. in die Research-Logik (redirect, Fragen).

Damit ist das System über die UI **sauber durchgängig**: Login → Command Center → Research starten/öffnen → Phasen manuell vorantreiben oder laufen lassen → Report lesen, Feedback geben. Alles über die gleiche Operator-Instanz und dasselbe Dateisystem.
