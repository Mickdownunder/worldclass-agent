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
- `brain.cycle.stuck` und `brain.reflect.stuck` beide `false` (sonst unhealthy)
- `recent_failures`: leer oder wenige Einträge

**Brain:** `op healthcheck` listet laufende `brain cycle`- und `brain reflect`-Prozesse. **Stuck** = Cycle >10 Min oder Reflect >5 Min (typisch: LLM blockiert). UI: Command Center + Brain & Memory zeigen „Hängend“ und Hinweis `pkill -f 'bin/brain'`. Reflect hat jetzt 90s-Timeout; optional: `BRAIN_REFLECT_AFTER_JOB=0` (Reflect nach Job deaktivieren), `BRAIN_REFLECT_MAX_CONCURRENT=3` (max. parallele Reflects).

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

**Conductor (Shadow):** Pro Cycle wird `tools/research_conductor.py shadow <project_id> <phase>` aufgerufen. Log: `research/proj-*/conductor_shadow.log`, Entscheidungen: `research/proj-*/conductor_decisions.json`. Bei `RESEARCH_USE_CONDUCTOR=1` übernimmt der Conductor die Steuerung (`run_cycle`). In diesem Modus schreibt run_cycle nach search_more/read_more Coverage nach `coverage_conductor.json`, setzt Fortschritt per `research_progress` (UI zeigt z. B. „Conductor: reading more sources“) und bricht nach mehreren aufeinanderfolgenden Tool-Fehlern ab (Status `failed_conductor_tool_errors`, Log `conductor_tool_errors.log`). **steps_taken:** Wenn `conductor_state.json` existiert, wird die Schrittanzahl dort gelesen; sonst aus `phase_history`.

**PDF-Reports:** Die Pipeline erzeugt nach dem Report eine PDF (WeasyPrint). Wenn WeasyPrint fehlt, steht im Job-Log „PDF generation failed (install weasyprint? …)“ und es wird keine PDF geschrieben. Dann: `pip install weasyprint` (oder `pip install -r requirements-research.txt`). Anschließend im Report-Tab **„Generate PDF“** klicken, um die PDF nachträglich zu erzeugen.

**AEM (Full AEM):** Nach Verify (Evidence Gate bestanden) läuft optional das AEM-Settlement (`research_aem_settlement.py`). Artefakte liegen unter `research/proj-*/claims/`, `attacks/`, `questions/`, `market/`, `portfolio/`, `policy/`. Fehler im AEM-Block blockieren Synthese nur bei `AEM_ENFORCEMENT_MODE=strict`.

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

# 5. (Optional) Memory v2 aktiv?
python3 -c "
import json
from pathlib import Path
p = Path('/root/operator/research')
latest = sorted([x for x in p.glob('proj-*') if (x / 'memory_strategy.json').exists()], key=lambda x: x.stat().st_mtime, reverse=True)
print('memory_strategy_found:', bool(latest))
if latest:
    d = json.loads((latest[0] / 'memory_strategy.json').read_text())
    print('strategy:', (d.get('selected_strategy') or {}).get('name'))
"
# Erwartung bei aktivem Flag: memory_strategy_found: True und ein Strategy-Name

# 6. Memory v2 mode/fallback Logging vorhanden?
python3 -c "
from lib.memory import Memory
with Memory() as m:
  rows = m.list_memory_decisions(limit=20)
v2 = [r for r in rows if r.get('decision_type') == 'v2_mode']
print('v2_mode_entries:', len(v2))
if v2:
  d = v2[0].get('details') or {}
  print('last_mode:', d.get('mode'), 'fallback_reason:', d.get('fallback_reason'))
"
# Erwartung: mindestens ein v2_mode-Eintrag nach einem research-cycle-Run; mode ist v2_applied|v2_fallback|v2_disabled

# 7. (Optional) Memory-Konsolidierung läuft?
python3 tools/memory_consolidate.py --min-samples 3 --min-principle-count 3
# oder: brain memory-consolidate --min-samples 3 --min-principle-count 3
python3 -c "
import json
from pathlib import Path
p = Path('/root/operator/memory/consolidation_last.json')
print('consolidation_file:', p.exists())
if p.exists():
  d = json.loads(p.read_text())
  print('domains_processed:', len(d.get('domains') or []))
"
# Erwartung: consolidation_file: True; domains_processed >= 0
```

Wenn alle vier durchlaufen ohne Fehler und mit sinnvollen Werten: **Funktion (a) gegeben.** Qualität (b) beurteilst du an Hand der obigen Tabellen (Reports, Findings, Avg quality, Learnings, Playbooks).

---

## Kurz

- **A) Funktion:** Health grün, ein Research-Durchlauf ohne Klicken bis Report, Brain & Memory mit Episodes/Reflections/Playbooks, optional Telegram bei done.
- **B) Schrott:** Viele FAILED-Jobs, keine Reports/Findings, Phase hängt, Avg quality dauerhaft niedrig, Reflections ohne sinnvolle Learnings.

Wenn du willst, können wir ein kleines Script `tools/run-system-check.sh` bauen, das die vier Terminal-Checks ausführt und „OK“ / „FAIL“ pro Schritt ausgibt.
