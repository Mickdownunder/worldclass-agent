# System prüfen: Funktioniert es? Ist es Schrott?

Kurze Checkliste, um **a) Funktion** und **b) Qualität** zu prüfen.

---

## A) Funktioniert das System?

### 1. Health-Check (Kern)

**Wo:** Dashboard → Command Center (erste Zeile) oder Terminal.

**Terminal:**
```bash
cd /root/operator
./bin/op healthcheck
```

**Erwartung:**
- `"healthy": true`
- `disk_ok: true` (Disk < 90 %)
- `load_ok: true`
- `recent_failures`: leer oder wenige Einträge

**Wenn `healthy: false` oder viele `recent_failures`:** Disk/Load prüfen, fehlgeschlagene Jobs unter **Jobs** ansehen, Logs (`jobs/*/*/log.txt`) prüfen.

---

### 2. Research: Ein Durchlauf

**Check:** Ein Research-Projekt starten und **ohne manuelles „Nächste Phase“** bis zum Report durchlaufen lassen.

**Schritte:**
1. Dashboard → Research → „Forschung starten“ mit einer konkreten Frage (z. B. „Marktgröße Vertical SaaS EU 2025“).
2. Ca. 1–2 Min warten (Init).
3. Nicht klicken – im Hintergrund läuft `run-research-cycle-until-done.sh`.
4. Nach einigen Minuten: Projekt in der Liste prüfen → Phase sollte sich ändern (explore → focus → … → done).
5. Wenn Phase **done**: Report-Tab öffnen → Report sollte da sein (Executive Summary, Key Findings, Suggested Next Steps).

**Erfolg:** Projekt wird angelegt, Phasen laufen automatisch, Report erscheint.  
**Schrott:** Init schlägt fehl, Phase bleibt hängen, kein Report, viele Fehler in `jobs/*/log.txt`.

---

### 3. Brain & Memory: Daten fließen

**Check:** Es werden Episodes/Decisions/Reflections geschrieben und in der UI angezeigt.

**Schritte:**
1. Dashboard → Brain & Memory.
2. **Totals:** Episodes > 0, mind. ein paar Decisions/Reflections (wenn schon Brain-Cycles oder Jobs gelaufen sind).
3. **Recent Episodes:** Einträge mit `job_complete`, `research-cycle`, `research-init` o. ä.
4. **Recent Reflections:** Wenn Brain schon Jobs ausgeführt hat, sollten Einträge mit Q (Quality) und Learnings stehen.
5. **Playbooks:** Mind. ein Eintrag (z. B. nach ein paar Brain-Cycles).

**Erfolg:** Zahlen steigen nach Aktivität, Episodes/Reflections/Playbooks sichtbar.  
**Schrott:** Episodes bleiben 0 obwohl Jobs laufen (Memory/DB kaputt?), Reflections immer leer (Reflect läuft nicht oder schlägt fehl).

---

### 4. Telegram (optional)

**Check:** Benachrichtigung bei Research „done“ und ggf. UI-Trigger.

**Schritte:**
1. Research-Projekt starten (Dashboard oder `/research-go`).
2. Warten bis Phase **done**.
3. Telegram: Nachricht „Research abgeschlossen: proj-…“ mit Frage und Report-Pfad.

**Erfolg:** Nachricht kommt.  
**Schrott:** Keine Nachricht trotz done (OpenClaw/send-telegram.sh, Token, Ziel-Chat prüfen).

---

## B) Ist es Schrott? (Qualität)

### 1. Health & Jobs

| Was prüfen | Wo | Schrott-Signal |
|------------|-----|-----------------|
| Fehlgeschlagene Jobs | Dashboard → Jobs oder `op job status` | Viele FAILED, gleicher Fehler wiederholt |
| Recent Failures | Command Center / `op healthcheck` | Liste wird länger, gleiche Workflow-IDs |
| Disk | Health | `disk_ok: false`, > 90 % belegt |
| Load | Health | `load_ok: false`, System dauerhaft überlastet |

---

### 2. Research-Qualität

| Was prüfen | Wo | Schrott-Signal |
|------------|-----|-----------------|
| Report-Inhalt | Research → Projekt → Report | Leer, nur Platzhalter, keine Quellen, keine „Suggested Next Steps“ |
| Findings | Research → Projekt → Findings | Immer 0 oder generisch/unsinnig |
| Phase hängt | Research → Projekt | Phase bleibt z. B. auf „explore“ oder „focus“, kein Fortschritt über viele Runs |

**Pragmatischer Test:** Eine klare Frage stellen (z. B. „Top 3 Anbieter für X in Deutschland“). Report sollte konkrete Aussagen, Quellen/Findings und nächste Schritte enthalten.

---

### 3. Brain & Memory – Qualität

| Was prüfen | Wo | Schrott-Signal |
|------------|-----|-----------------|
| Avg quality | Brain & Memory → Totals | Dauerhaft < 0.4, fällt über Zeit |
| Reflections | Recent Reflections | Immer „LLM failed“, „Execution failed“, keine sinnvollen Learnings |
| Playbooks | Playbooks | Keine oder nur „fix connectivity“, keine domänenspezifischen Strategien |

**Erfolg:** Quality nach vielen Runs im Bereich 0.5–1.0, Learnings lesbar und nachvollziehbar, Playbooks mit konkreten Strategien.

---

### 4. Ein schneller Gesamt-Check (Terminal)

```bash
cd /root/operator

# 1. Health
./bin/op healthcheck
# Erwartung: "healthy": true

# 2. Jobs – letzte 5
./bin/op job status --limit 5
# Erwartung: DONE oder RUNNING, nicht nur FAILED

# 3. Research – Projekte
ls -la research/
# Erwartung: proj-* Ordner, project.json pro Projekt

# 4. Memory – DB erreichbar
python3 -c "
from lib.memory import Memory
m = Memory()
s = m.state_summary()
print('Episodes:', s['totals']['episodes'], 'Avg quality:', s['totals'].get('avg_quality'))
m.close()
"
# Erwartung: Zahlen ausgegeben, kein Traceback
```

Wenn alle vier durchlaufen ohne Fehler und mit sinnvollen Werten: **Funktion (a) gegeben.** Qualität (b) beurteilst du an Hand der obigen Tabellen (Reports, Findings, Avg quality, Learnings, Playbooks).

---

## Kurz

- **A) Funktion:** Health grün, ein Research-Durchlauf ohne Klicken bis Report, Brain & Memory mit Episodes/Reflections/Playbooks, optional Telegram bei done.
- **B) Schrott:** Viele FAILED-Jobs, keine Reports/Findings, Phase hängt, Avg quality dauerhaft niedrig, Reflections ohne sinnvolle Learnings.

Wenn du willst, können wir ein kleines Script `tools/run-system-check.sh` bauen, das die vier Terminal-Checks ausführt und „OK“ / „FAIL“ pro Schritt ausgibt.
