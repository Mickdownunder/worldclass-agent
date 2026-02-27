# Das Brain-System — Erklärung

Das **Brain** ist die **kognitive Zentrale** des Operators: Es nimmt den Systemzustand wahr, plant mit einem LLM die nächste Aktion, führt sie aus (über Jobs) und reflektiert danach. Außerdem kann es **nachträglich** über bereits gelaufene Jobs nachdenken (Reflection). Alles wird im **Memory** (Episodes, Decisions, Reflections, Playbooks) gespeichert.

---

## 1. Die Idee: Strukturierter kognitiver Loop (SCL)

Der Brain folgt einem festen Ablauf:

```
Perceive → Think → Decide → Act → Reflect → Remember
```

| Phase      | Was passiert |
|-----------|----------------|
| **Perceive** | Sammelt den aktuellen Zustand: System-Health (Disk, Load), letzte Jobs, Research-Projekte (Phase, Status), Clients, Workflows, Ziele, Prioritäten, **Memory** (Episodes, Reflections, Playbooks) und ggf. **strategische Prinzipien** aus vergangenen Projekten. |
| **Think**    | Schickt diesen Zustand + ein **Goal** an ein **LLM**. Das LLM liefert einen Plan (JSON): Analyse, Prioritäten, konkrete Aktionen (z. B. `research-cycle` mit Projekt-ID), Risiken, Confidence. Es nutzt Research-Playbooks und strategische Prinzipien, wenn vorhanden. |
| **Decide**   | Wählt die **erste geplante Aktion** aus und prüft sie gegen den **Governance-Level** (0–3). Bei Level 2 (Standard) wird die Aktion genehmigt und ausgeführt. |
| **Act**      | Führt die Aktion aus: Ruft `op job new --workflow <id> --request <text>` und dann `op run` auf. Typische Aktion: `research-cycle` mit Projekt-ID, um eine Research-Phase voranzutreiben. |
| **Reflect**  | Bewertet das Ergebnis (Job-Status, Log, Artifacts) per LLM: Was lief gut, was schief, Learnings, Quality-Score, Playbook-Update. Das wird ins Memory geschrieben. |
| **Remember** | Episodes und Reflections landen in der **Memory**-Datenbank; Playbooks und Prinzipien werden für zukünftige **Think**-Phasen genutzt. |

Ein **einziger** solcher Durchlauf heißt **ein Cycle** („Brain Cycle“).

---

## 2. Zwei Arten, wie der Brain läuft

### A) **Brain Cycle** (`brain cycle [--goal "..."]`)

- **Ein vollständiger SCL-Durchlauf:** Perceive → Think → Decide → Act → Reflect.
- **Wird gestartet von:**
  - **UI:** Button „Brain Cycle“ im Command Center → `POST /api/actions/brain-cycle` → startet einen Prozess `brain cycle --goal "Decide and execute the most impactful next action"`.
  - **Cron / Autopilot:** z. B. `autopilot-infra.sh` oder Daily-Run ruft `brain cycle --goal "Autonomous maintenance cycle: ..."` auf.
- **Dauer:** Normalerweise einige Minuten (mehrere LLM-Calls + ein Job). Wenn der Prozess **länger als 10 Minuten** läuft, wertet die Health-Prüfung das als **hängend (stuck)**.

### B) **Brain Reflect** (`brain reflect <job_dir> [--goal "..."]`)

- **Nur Reflection:** Es wird **kein** Perceive/Think/Decide/Act gemacht. Der Brain liest den **abgeschlossenen Job** (job.json, Log, Artifacts), baut ein „action result“ daraus und ruft intern **nur** `reflect(...)` auf – also ein **einzelner LLM-Call**, der Learnings und Quality-Score erzeugt und ins Memory schreibt.
- **Wird gestartet von:**
  - **`op run` (bin/op):** Nach **jedem** beendeten Job (DONE oder FAILED) startet `op` **asynchron** einen Prozess:
    - `brain reflect <job_dir> --goal "<request>"`
    - z. B. `--goal "proj-20260227-2ff679b0"` bei einem research-cycle-Job.
  - Dadurch gibt es **viele** Reflect-Prozesse, sobald viele Jobs durchgelaufen sind (z. B. 20 research-cycle-Jobs → 20 Reflect-Prozesse, die parallel starten).
- **Dauer:** Sollte nur **wenige Minuten** dauern (ein LLM-Call). Wenn ein Reflect **länger als 5 Minuten** läuft, gilt er als **stuck** (typisch: LLM-Timeout oder API blockiert).

**Wichtig:** Research-cycle.sh schreibt am Ende **selbst** Metriken ins Memory (record_episode, record_quality, record_project_outcome). Das ist **zusätzlich** zum Brain: Der Brain-Reflect-Prozess liefert eine **sprachliche** Reflection (Learnings, Playbook-Vorschläge); die Workflow-Skripte liefern strukturierte Zahlen und Outcomes.

---

## 3. Governance-Level (wie viel darf der Brain tun?)

| Level | Name              | Bedeutung |
|-------|-------------------|-----------|
| 0     | report_only       | Aktion nur loggen, **nicht** ausführen. |
| 1     | suggest           | Aktion vorschlagen, **keine** Ausführung (menschliche Freigabe). |
| 2     | act_and_report    | **Standard:** Aktion ausführen und berichten. |
| 3     | full_autonomous   | Volle Autonomie. |

Beim **Brain Cycle** aus der UI oder aus Autopilot wird in der Regel Level 2 verwendet.

---

## 4. Memory — was der Brain speichert und nutzt

- **Episodes:** Kurze Ereignis-Log-Einträge (z. B. „cycle_start“, „job_complete“, „research_complete“, „perceive“, „cycle_complete“).
- **Decisions:** Jeder Schritt im Cycle (perceive, think, decide) wird als Decision mit Phase, Reasoning, Confidence und trace_id gespeichert → in der UI unter „Brain Cognitive Traces“ sichtbar.
- **Reflections:** Die vom Brain (LLM) erzeugten Reflexionen zu Jobs: Outcome, Learnings, Quality-Score, Playbook-Update.
- **Playbooks:** Strategien pro Domaine/Workflow; werden in **Think** mit in den Kontext gegeben.
- **Strategic Principles:** Aus vergangenen Projekten gelernte „guiding“ / „cautionary“ Prinzipien; fließen in **Think** ein.

Die UI **Brain & Memory** zeigt Episodes, Decisions, Reflections, Playbooks und Qualitäts-Trends.

---

## 5. Warum so viele Reflect-Prozesse / warum „hängend“?

- **Viele Reflect-Prozesse:** Jeder **abgeschlossene** Job (research-cycle, factory, autopilot, …) triggert **einen** asynchronen `brain reflect`. Bei vielen Jobs entstehen viele parallele Reflect-Prozesse.
- **Stuck:** Jeder Reflect macht **einen** LLM-Call. Wenn die API langsam ist, Timeouts groß sind oder Retries endlos laufen, können Reflect-Prozesse **stundenlang** laufen. Die Health-Prüfung meldet dann: **Reflect stuck** (läuft > 5 min). Dasselbe kann bei einem **Cycle** passieren (mehrere LLM-Calls + Job) → **Cycle stuck** (> 10 min).

Die UI zeigt im Command Center und auf Brain & Memory, ob Brain-Prozesse laufen und ob sie als **hängend** gelten; bei Stuck wird z. B. `pkill -f 'bin/brain'` als Hinweis angezeigt.

**Abhilfe (im System umgesetzt):**
- **Reflect-Timeout:** Der LLM-Aufruf in `reflect()` ist auf **90 Sekunden** begrenzt (gesamter Aufruf inkl. Retries). Danach: Fallback-Reflection (metrikbasiert), Prozess beendet sich.
- **Reflect nach Job abschaltbar:** `BRAIN_REFLECT_AFTER_JOB=0` (oder `false`/`no`/`off`) → `op` startet nach Job-Ende **keinen** Reflect-Prozess.
- **Begrenzung paralleler Reflects:** `BRAIN_REFLECT_MAX_CONCURRENT=3` (Default). Wenn bereits 3 oder mehr `brain reflect`-Prozesse laufen, startet `op` keinen weiteren, bis wieder Platz ist.

---

## 6. Kurz-Übersicht

| Begriff            | Bedeutung |
|--------------------|-----------|
| **Brain**          | Kognitive Zentrale: Perceive → Think → Decide → Act → Reflect, mit LLM und Memory. |
| **Cycle**          | Ein vollständiger SCL-Durchlauf; wird von UI/Cron/Autopilot gestartet. |
| **Reflect (Standalone)** | Nur Reflection über einen **bereits gelaufenen** Job; wird von `op` nach jedem Job asynchron gestartet. |
| **Memory**         | Persistente Speicherung von Episodes, Decisions, Reflections, Playbooks, Principles. |
| **Governance**     | Level 0–3: wie viel der Brain ausführen darf (nur Report bis voll autonom). |
| **Stuck**          | Cycle > 10 min oder Reflect > 5 min → Health meldet „Brain hängend“. |

Wenn du willst, können wir als Nächstes z. B. nur die Reflect-Logik oder nur den Ablauf „von UI-Klick bis Job“ Schritt für Schritt durchgehen.
