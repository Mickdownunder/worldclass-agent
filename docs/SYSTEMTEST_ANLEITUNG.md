# So testest du das ganze System sauber durch

Reihenfolge: zuerst automatische Checks, dann ein echter Research-Durchlauf, dann UI prüfen.

---

## Schritt 1: Automatischer System-Check (Terminal)

Auf dem Server (oder in deiner Umgebung):

```bash
cd /root/operator
./scripts/run-system-check.sh
```

**Erwartung:** Alle Zeilen zeigen `[OK]` (Health, Jobs, Research-Ordner, Memory-DB, Sandbox/Docker).

Wenn etwas `[FAIL]` ist: die genannte Komponente prüfen (z.B. Docker starten, `op healthcheck` manuell ausführen).

---

## Schritt 2: UI läuft und Login

1. UI starten (falls nicht schon am Laufen):
   ```bash
   cd /root/operator/ui && npm run start
   ```
2. Im Browser: **http://DEINE-SERVER-IP:3000** (z.B. http://168.119.238.211:3000).
3. Mit deinem Passwort einloggen.
4. Du solltest das **Command Center** sehen (Health, Research, Jobs, Brain & Memory).

**Erfolg:** Login klappt, Dashboard lädt.

---

## Schritt 3: E2E-Tests der UI (optional, aber empfohlen)

Damit werden Login und Research-Liste/Erstellen/Detail/Löschen automatisch getestet.

**Voraussetzung:** UI läuft (z.B. auf Port 3000). Passwort für die Tests muss zum gesetzten `UI_PASSWORD_HASH` passen.

```bash
cd /root/operator/ui

# Passwort "e2etest" → Hash setzen (nur für diesen Testlauf)
export UI_PASSWORD_HASH=37a97310cedfe6ae001033c2b9832f6c9722b3337d3aba2ee3bb4b71756a9d72
export E2E_PASSWORD=e2etest
export PLAYWRIGHT_BASE_URL=http://localhost:3000

npx playwright test
```

**Erwartung:** Alle Tests grün (Login, Research-Liste, Projekt anlegen, Detail, Löschen). Wenn die UI unter einer anderen URL läuft: `PLAYWRIGHT_BASE_URL=http://168.119.238.211:3000` setzen.

---

## Schritt 4: Ein Research komplett durchlaufen lassen

Das ist der wichtigste „echte“ Test: Ein Projekt von Start bis Report.

1. Im Browser: **Research** → **Neues Research-Projekt** (oder „Forschung starten“).
2. Eine konkrete Frage eingeben, z.B.: **„Was sind die Top-3-Trends bei KI-Agenten 2025?“**
3. **Forschung starten** klicken.
4. Ca. 1–2 Minuten warten (Init). Die Liste zeigt das neue Projekt.
5. **Nicht** „Nächste Phase“ klicken – im Hintergrund läuft der komplette Zyklus (explore → focus → connect → verify → synthesize → ggf. Experiment → done).
6. Nach einigen Minuten (je nach Frage und Quellen: ca. 5–15 Min) die Seite ggf. neu laden. Phase sollte sich ändern und am Ende **done** sein.
7. Projekt öffnen → Tab **Report**. Es sollte ein Report mit Executive Summary, Findings, Quellen und „Suggested Next Steps“ stehen.
8. Optional: Tab **Findings** – es sollten Findings gelistet sein. **Budget** in der Kopfzeile – Kosten sollten > 0 sein (LLM/API getrackt).

**Erfolg:** Projekt wird angelegt, Phasen laufen von selbst durch, Report erscheint, Budget sichtbar.  
**Wenn es hängt:** Unter **Jobs** nachsehen, ob ein Job FAILED ist; in `research/proj-…/log.txt` oder `jobs/…/log.txt` nach Fehlern schauen.

---

## Schritt 5: Memory & Brain prüfen

1. Im Browser: **Brain & Memory** (oder **Memory** in der Nav).
2. **Totals:** Episodes > 0, Decisions/Reflections sollten nach Research/Brain-Aktivität Einträge haben.
3. Tabs **Runs**, **Strategies**, **Utility**, **Graph** – sollten (nach ein paar Läufen) Daten anzeigen oder „noch keine“.
4. **Activity:** Letzte Konsolidierung und ggf. Auto-Prompt-Optimierung sichtbar.

**Erfolg:** Nach Research-Runs und ggf. Brain-Cycles siehst du Episodes, Run-Timeline, ggf. Strategies und Graph.

---

## Schritt 6: Sandbox/Experiment (optional)

Wenn ein Research bis **done** durchgelaufen ist und die Experiment-Phase aktiv war (`RESEARCH_ENABLE_EXPERIMENT_LOOP=1`):

1. Dasselbe Projekt öffnen.
2. Es sollte ein Block **„Autonomous Experiment“** und im Execution Tree ein Schritt **„Experiment“** (Sandbox / Sub-agents) sichtbar sein.
3. Dort: Iterations, ggf. Sub-agents spawned – bestätigt, dass die Sandbox (Docker) genutzt wurde.

**Erfolg:** Experiment-Block sichtbar, keine Fehler in `research/proj-…/log.txt` bezüglich Sandbox.

---

## Kurz-Checkliste

| # | Was | Wie |
|---|-----|-----|
| 1 | System-Check | `./scripts/run-system-check.sh` → alles [OK] |
| 2 | UI + Login | Browser → URL:3000 → einloggen → Command Center sichtbar |
| 3 | E2E-Tests | `cd ui && E2E_PASSWORD=e2etest UI_PASSWORD_HASH=… npx playwright test` |
| 4 | Research durch | Eine Frage starten, warten bis done, Report prüfen |
| 5 | Memory/Brain | Brain & Memory → Totals, Runs, Activity prüfen |
| 6 | Experiment (opt.) | Projekt mit Experiment-Block prüfen |

Wenn 1–5 durch sind und Ergebnisse passen: **Das System ist sauber durchgetestet.**
