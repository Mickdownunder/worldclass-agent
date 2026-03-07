# Neue Runde & Autonom

## Neue Runde starten

**Komplett neues Thema**

- **UI:** Research → „Was willst du erforschen?“ → Frage → „Forschung starten“.
- **Telegram:** `/research-go "Deine Frage"` (startet Projekt + läuft autonom über Tage).

**Follow-up (z. B. aus „Suggested Next Steps“)**

- **Neues Projekt** mit konkreter Frage, z. B.  
  `/research-go "Pilotprojekte Feststoffbatterien: Lebensdauer und Sicherheit"`  
  oder in der UI: Frage = „Skalierungsstrategien und Produktionskosten Feststoffbatterien“.
- **Oder Redirect** am bestehenden Projekt:  
  `/research-feedback <proj-id> redirect "Pilotprojekte und Lebensdauer"`  
  → dasselbe Projekt läuft mit neuer Frage weiter (Phase zurück auf focus).

---

## Autonom: Ein Projekt

**Bereits umgesetzt.**  
Ein Befehl startet alles, danach läuft es ohne weiteres Zutun:

- **Telegram:** `/research-go "Frage"`  
  → Projekt wird angelegt, dann läuft `run-research-over-days.sh`: **alle 6h ein Cycle**, bis Phase **done** oder **14 Tage**.
- **Telegram:** `/research-cycle <project_id>`  
  → Startet **alle Phasen bis done/failed im Hintergrund** (kein Timeout mehr). Status: `/research-status <project_id>`.
- Du musst nicht „Nächste Phase starten“ klicken; Status prüfen mit `/research-status <project_id>`.

---

## Autonom: Mehrere Projekte (Scheduler)

Wenn du **mehrere** Research-Projekte hast (z. B. mehrere „Suggested Next Steps“ als eigene Projekte) und alle **ohne manuelles Klicken** vorantreiben willst:

1. **Projekte anlegen** (UI oder Telegram), z. B.:
   - Projekt A: „Pilotprojekte Feststoffbatterien: Lebensdauer“
   - Projekt B: „Skalierung und Produktionskosten Feststoffbatterien“
   - Projekt C: „Regulatorik Batterietechnologien“
2. **Scheduler** führt für **jedes** Projekt mit Phase ≠ done **einen** research-cycle aus – z. B. alle 6 Stunden.

**Conductor (Next Level Architecture):**

- **Shadow Mode (Standard):** Bei jedem research-cycle wird der **Research Conductor** parallel ausgeführt. Er liest den aktuellen State (6 Metriken), entscheidet per LLM die nächste Aktion (`search_more`, `read_more`, `verify`, `synthesize`) und schreibt die Entscheidung in `research/proj-*/conductor_decisions.json`. Die Bash-Pipeline bleibt Master; der Conductor loggt nur.
- **Conductor als Master (Phase C):** `RESEARCH_USE_CONDUCTOR=1` — dann steuert der Conductor den Ablauf (max 25 Schritte, 4 Aktionen, Context Manager + Supervisor). Bash-Pipeline ist Fallback mit `RESEARCH_USE_CONDUCTOR=0`. Bei Conductor-Override (Gate sagt „nochmal Phase X“) setzt research-cycle.sh `RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1`, damit advance_phase die Conductor-Entscheidung nicht nach 4 Runden überschreibt. **Hinweis:** Im Conductor-Modus wird die volle Bash-Explore-Pipeline (3 Runden, Coverage, Refinement/Gap/Depth) nicht ausgeführt; es ist ein vereinfachter Aktionen-Loop. Details und Bewertung: `docs/EXPLORE_PHASE_DEEP_DIVE.md` Abschnitt 8.
- **Explore-Loop-Guard (Hybrid-Gate):** Im Hybrid-Modus blockt `research-cycle.sh` standardmäßig ein Override `focus -> explore`, sobald Coverage bereits bestanden ist und genügend Evidenz vorliegt (Guard gegen Endlosschleifen). Ausnahme nur mit `RESEARCH_CONDUCTOR_ALLOW_EXPLORE_OVERRIDE_ON_COVERAGE_PASS=1`.
- **No-Evidence Guard (Explore -> Focus):** Wenn Explore keine verwertbare Evidenz produziert (`findings=0` und keine gelesenen `*_content.json`), bleibt das Projekt in `phase=explore` (statt auf `focus` zu springen). Das verhindert leere Focus-Runs bei temporären DNS/Search-Ausfällen.
- **No-Evidence Guard (Focus -> Connect):** Wenn Focus ebenfalls keine verwertbare Evidenz produziert (`findings=0` und keine gelesenen `*_content.json`), bleibt das Projekt in `phase=focus` (statt auf `connect` zu springen).

**Skript:** `tools/run-scheduled-research.sh`

- Durchläuft alle `research/proj-*/` mit gültigem `project.json`.
- Wenn Phase = done → überspringen.
- Sonst: einen research-cycle-Job starten und warten bis fertig, dann nächste Projekt.

**Cron einrichten (Beispiel: alle 6 Stunden):**

```bash
# Crontab bearbeiten
crontab -e

# Zeile einfügen (anpassen: User, Pfad, Log)
0 */6 * * * /root/operator/tools/run-scheduled-research.sh >> /root/operator/logs/scheduled-research.log 2>&1
```

**Log prüfen:**

```bash
tail -f /root/operator/logs/scheduled-research.log
```

Dann reicht es, neue Projekte zu erstellen (UI oder `/research-go`); der Cron sorgt dafür, dass alle nicht-done-Projekte automatisch weiterlaufen.

---

## Auto-Follow-up aus „Suggested Next Steps"

Wenn ein Research-Projekt **done** ist, kann das System automatisch **neue Projekte** aus dem Report-Abschnitt „5) Suggested Next Steps" anlegen.

**Aktivierung (opt-in):**

- `RESEARCH_AUTO_FOLLOWUP=1` — beim Erreichen von Phase „done" wird `tools/research_auto_followup.py` aufgerufen.
- `RESEARCH_MAX_FOLLOWUPS=3` — maximal so viele neue Projekte pro Report (Standard: 3).

**Ablauf:**

1. Report wird gelesen (Abschnitt „Suggested Next Steps" oder ganzer Report).
2. LLM extrahiert 2–3 konkrete Forschungsfragen.
3. Für jede Frage: `op job new --workflow research-init --request "Frage"` + Job im Hintergrund gestartet.
4. Neue Projekte werden vom Scheduler (Cron) oder von `/research-cycle` weitergetrieben.

**Beispiel (in `conf/secrets.env` oder vor dem Lauf):**

```bash
export RESEARCH_AUTO_FOLLOWUP=1
export RESEARCH_MAX_FOLLOWUPS=3
```

---

## Research Orchestrator (June-Level Autonomie)

Über dem Auto-Follow-up (pro Report) sitzt der **Orchestrator**: Er sieht **alle** done Reports + Sandbox-Ergebnisse + laufende Projekte und entscheidet zentral, welche neuen Research-Fragen und welche Sandbox-Runden gestartet werden. Das entspricht „June im Hintergrund“ – ohne dass du in Telegram befehlen musst.

**Skript:** `tools/research_orchestrator.py` (Aufruf: `tools/run-research-orchestrator.sh`)

- Liest alle `research/proj-*/` mit Phase done (Report-Auszug + optional `experiment.json`) und alle laufenden Projekte.
- Ruft ein LLM mit diesem Kontext auf; Ausgabe: `research_questions` (0–3 neue Fragen) und `sandbox_project_ids` (0–2 done-Projekte für zusätzliche Sandbox-Experimente).
- Startet pro Frage: `op job new research-init`, dann `run-research-cycle-until-done.sh` im Hintergrund.
- Startet pro Sandbox-ID: `research_experiment.py <project_id>` im Hintergrund.

**Umgebungsvariablen (optional):**

- `RESEARCH_ORCHESTRATOR_MAX_RESEARCH=3` — max. neue Research-Fragen pro Lauf (Standard 3).
- `RESEARCH_ORCHESTRATOR_MAX_SANDBOX=2` — max. Sandbox-Runden pro Lauf (Standard 2).
- `RESEARCH_ORCHESTRATOR_MODEL` / `RESEARCH_ORCHESTRATOR_FALLBACK_MODEL` — LLM (Standard: gpt-4.1-mini, Fallback gemini-2.5-flash).

**Cron (z. B. alle 2 Stunden):**

```bash
0 */2 * * * /root/operator/tools/run-research-orchestrator.sh >> /root/operator/logs/orchestrator.log 2>&1
```

**Dry-Run (nur anzeigen, nichts starten):**

```bash
/root/operator/tools/run-research-orchestrator.sh --dry-run
```

---

## June (Brain) und Research

**Ping bei Run-Ende:** Wenn ein research-cycle fertig ist, wird June automatisch benachrichtigt:

- `research-phase.sh` emittiert nach Run-Ende ein strukturiertes `research_cycle_completed`-Event in die Control-Plane-Logs. Der Brain kann dieses Event wahrnehmen, wird aber nicht mehr direkt von der Phase als zweiter globaler Orchestrator gestartet.
- June kann so den Report lesen und den nächsten Schritt wählen (weiteres research-cycle vorschlagen oder warten).

**Council-Wartezeit:** Wenn der **Research Council** weitere Läufe gestartet hat (Follow-up-Projekte), sieht June das im State:

- Jedes Projekt hat `council_status` (z. B. `active`, `waiting`, `done`) und bei Eltern `council_children_running` (Anzahl noch laufender Kinder).
- Wenn `council_status` in [active, waiting] und `council_children_running` > 0, schlägt June **kein** research-cycle für dieses Parent-Projekt vor – der Council meldet sich erst wieder, wenn alle Kinder fertig sind (kann Tage dauern).

---

## Proxy / Umgebung

Wenn in der Umgebung **HTTP_PROXY/HTTPS_PROXY** gesetzt ist (z. B. Cursor/IDE), können OpenAI-Calls mit **403 Forbidden** fehlschlagen. Das Workflow-Skript **research-cycle.sh** setzt daher zu Beginn **NO_PROXY** für `api.openai.com` und `generativelanguage.googleapis.com`, sodass LLM-Traffic nicht über den Proxy läuft. Bei weiterhin 403: Proxy-Anbieter prüfen oder NO_PROXY vor dem Start setzen.

## Pipeline Intelligence (Tier 2)

- **Provenance:** Findings speichern `finding_id`, `search_query`, `read_phase`; Claims im Ledger haben `source_finding_ids`. Deep-Extract-Findings haben optional `parent_finding_id` (Verweis auf das Ursprungs-Finding derselben URL). Optional: `RESEARCH_SEARCH_QUERY` setzen, um den Suchkontext für gespeicherte Findings zu übergeben (wird in `research_parallel_reader.py` ausgewertet).
- **Novelty & Saturation:** Jedes Finding erhält ein `novelty_score` (Jaccard vs. letzte 50 Findings). Nach der Explore-Runde 1 ruft `research-cycle.sh` `tools/research_saturation_check.py` auf. Bei **Saturation** (≥7 von 10 letzten Findings mit `novelty_score < 0.2`) werden **Refinement-, Gap- und Depth-Lese-Runden in dieser Explore-Phase übersprungen** (weniger redundante Reads, Exit-Code 1 vom Check).

## Memory v2 (optional, empfohlen)

Feature-Flag und Verhalten:

- `RESEARCH_MEMORY_V2_ENABLED=1` aktiviert Strategy-Memory-Injection im Planner/Cycle.
- `RESEARCH_MEMORY_PRINCIPLE_DOMAIN_FILTER=1` aktiviert bei Principle-Retrieval eine **Domain-First** Auswahl (nur für Principles), mit globalem Fallback wenn zu wenig Treffer gefunden werden. Default `0` (aus).
- Planner schreibt `research/proj-*/memory_strategy.json` (gewählte Strategy + Regeln).
- Cycle nutzt daraus konservative Guards:
  - `relevance_threshold` (hart begrenzt auf `0.50..0.65`)
  - `critic_threshold` (hart begrenzt auf `0.50..0.65`)
  - `revise_rounds` (begrenzt auf `1..4`)
  - `domain_rank_overrides` für Source-Ranking
- Fallback: ohne Flag oder bei Fehlern läuft der bestehende statische Pfad weiter (kein Hard-Fail).

### Memory-Konsolidierung (empfohlen, offline)

- Skript: `tools/memory_consolidate.py` — oder über Brain-CLI: **`brain memory-consolidate`** (ruft dasselbe Skript auf).
- Zweck: erzeugt/aktualisiert datenbasierte Strategy-Profile pro Domain (`empirical-*`) und synthetisiert wiederkehrende guiding/cautionary Principles aus `run_episodes`.
- Ausgabe: `memory/consolidation_last.json` + Decision-Log `memory_consolidation_run`.

Beispiel:

```bash
cd /root/operator
python3 tools/memory_consolidate.py --min-samples 3 --min-principle-count 3
# oder (venv/OPERATOR_ROOT wird von brain gesetzt):
brain memory-consolidate --min-samples 3 --min-principle-count 3
```

Optional per Cron (z. B. nachts):

```bash
30 2 * * * cd /root/operator && /usr/bin/python3 tools/memory_consolidate.py >> /root/operator/logs/memory-consolidate.log 2>&1
# alternativ mit Brain-CLI (venv):
30 2 * * * cd /root/operator && ./bin/brain memory-consolidate >> /root/operator/logs/memory-consolidate.log 2>&1
```

## Bekannte Laufzeit-Themen

- **HTTP 429 (Rate Limit):** Semantic Scholar und arXiv können in der Explore-Phase 429 zurückgeben. Das Skript loggt WARN und fährt fort; ggf. weniger parallele Jobs oder Backoff.
- **Job-Timeout (z. B. 300s):** Synthesize-Phase kann bei langen Reports den Job-Timeout treffen. Timeout beim Start des Jobs erhöhen (z. B. `op run … --timeout 900`) oder Report-Umfang begrenzen.
- **Focus ohne Coverage:** Wenn Explore in einem anderen Job lief und keine Coverage-Datei im Projekt liegt, nutzt Focus leere Queries und macht nur Lese-Schritte; kein Abbruch mehr.
- **Verify→Focus Loop-back:** Bei Evidence-Gate-Fail mit high-priority Gaps wird `advance_phase "focus"` aufgerufen; `verify/deepening_queries.json` wird geschrieben und in der nächsten Focus-Runde mit Gap-Fill gemerged und für Web Search genutzt. Siehe `docs/FOCUS_PHASE_DEEP_DIVE.md`.

---

## Discovery mode (Fail-Härtung)

- **Council:** Wird nur ausgelöst, wenn das Parent-Projekt **done** ist (nicht bei `failed_quality_gate` o. ä.). Siehe `tools/trigger_council.py` und `workflows/research-cycle.sh` (TRIGGER_COUNCIL nur bei `status=done` für Discovery).
- **Synthesize:** Bei Fehler oder leerem Report wird ein **Fallback-Report** aus `discovery_analysis.json`, Claim-Ledger und Verify-Metriken erzeugt; der Lauf endet trotzdem mit Report.
- **Critic:** Bei Discovery und bestandenem Evidence Gate ist der Critic **advisory** (niedriger Score → `quality_gate_status=advisory_low_score`, Projekt wird trotzdem als `done` abgeschlossen).
- **Experiment (strict gate):** Nach Synthesize läuft der Sandbox-Experiment-Loop. In Discovery: Wenn `RESEARCH_STRICT_EXPERIMENT_GATE=1` (z. B. bei manuellem Einzelzyklus), wird nur bei Sandbox-Crash/Timeout `failed_experiment_gate` gesetzt; läuft der Code durch → `done`. **`run-research-cycle-until-done.sh` setzt standardmäßig `RESEARCH_STRICT_EXPERIMENT_GATE=0`**, damit autonome Discovery-Läufe bei Sandbox-Crash/Timeout nicht auf `failed_experiment_gate` enden, sondern mit Report auf `done` gehen. Mit `RESEARCH_STRICT_EXPERIMENT_GATE=1` (export vor Aufruf) bleibt striktes Gate auch im Cycle-Runner aktiv.

---

## Kurz

| Ziel | Vorgehen |
|------|----------|
| **Eine neue Runde (ein Thema)** | Neues Projekt: UI oder `/research-go "Frage"` → läuft mit over-days autonom. |
| **Follow-up aus Report** | Neues Projekt mit konkreter Frage aus „Suggested Next Steps“ oder Redirect am alten Projekt. |
| **Autonom ein Projekt** | `/research-go "Frage"` (over-days alle 6h, 14 Tage). |
| **Autonom viele Projekte** | Projekte anlegen, Cron für `run-scheduled-research.sh` (z. B. alle 6h). |

### Hinweis zu Phasen-Runs

- Ein `research-cycle`-Job arbeitet normalerweise **eine Phase pro Run** ab und setzt danach den Projektstatus auf `waiting_next_cycle` (nicht mehr still `active` ohne Prozess).
- Das ist **kein Hänger**: Es bedeutet „Phase vorbereitet, wartet auf den nächsten Cycle-Run“.
| **Orchestrator (June-Level)** | Cron für `run-research-orchestrator.sh` (z. B. alle 2h): entscheidet aus allen done Reports + Sandbox, startet neue Research + Sandbox-Runden. |
