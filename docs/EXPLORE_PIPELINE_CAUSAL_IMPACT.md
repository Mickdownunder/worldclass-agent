# Pipeline-Änderungen: Wirkungsanalyse (Ursache → Wirkung)

Dieses Dokument beschreibt **für jede geplante Änderung**: was sie bewirkt, wen sie betrifft, welche Invarianten gelten, wie sie mit anderen Änderungen zusammenspielt und welche Risiken entstehen. Ziel: Jede Entscheidung hat eine reale Konsequenz — die muss verstanden sein, damit der Plan und die Implementierung fehlerfrei sind.

**Bezug:** `EXPLORE_PIPELINE_SOTA_ACTION_PLAN.md` (Aufgaben); hier nur Kausalität, Abhängigkeiten und Wechselwirkungen.

---

## 1. Fix 1.4 — Connect: thesis.json Default

### Was sich ändert
- **Ort:** `research/phases/connect.sh`, vor dem ersten Zugriff auf `thesis.json`.
- **Aktion:** Wenn `(p / "thesis.json").exists()` falsch → Datei anlegen mit `{"current": "", "confidence": 0.0, "evidence": []}` (gleicher Inhalt wie in `research-init.sh`).

### Ursache → Wirkung (Kette)
1. **Ursache:** Connect wird aufgerufen (aus research-cycle.sh, Branch `connect`).
2. **Ohne Fix:** `(p / "thesis.json").read_text()` → FileNotFoundError → Python-Block bricht ab → Connect-Phase schlägt fehl, advance_phase(verify) wird nie erreicht.
3. **Mit Fix:** Datei existiert immer beim Lesen → Connect läuft durch → reason/hypothesis/thesis-Update schreibt wieder in thesis.json → advance_phase(verify) wird aufgerufen.

### Wen es betrifft
- **Direkt:** Connect-Phase (kein Absturz bei fehlender Datei).
- **Downstream:** Verify und Synthesize; sie hängen davon ab, dass Connect sauber durchläuft und `phase=verify` gesetzt wird. Synthesize liest thesis.json **optional** (`if (proj_path / "thesis.json").exists()`); durch Connect wird die Datei ohnehin gefüllt, der Default verändert nur den Fall „Projekt ohne Init / wiederhergestellt“.

### Invarianten
- **Vorher:** Es gibt keinen garantierten Pfad, der thesis.json vor Connect anlegt, außer research-init.sh.
- **Nachher:** Connect ist selbst-stabil: fehlt thesis.json, wird sie mit Init-kompatiblem Default angelegt; danach gilt weiterhin: nur Init und Connect schreiben thesis.json.

### Wechselwirkung mit anderen Fixes
- **Unabhängig:** Kein anderer Fix schreibt oder prüft thesis.json in Connect. 1.4 kann zuerst umgesetzt werden und hat keine Abhängigkeit von 1.1, 1.2, 1.3, 1.5.

### Risiko
- **Niedrig:** Gleicher Default wie Init; Connect überschreibt danach mit echten Daten. Einzige Gefahr: falscher Pfad (z.B. `p` anders als Projekt-Root) → dann würde eine falsche Stelle beschrieben; Code nutzt bereits `p = Path(proj_dir)` aus Argument.

---

## 2. Fix 1.2 — Conductor-Gate: Stderr loggen, bei leerer Ausgabe nicht „blind“ advance

### Was sich ändert
- **Ort:** `research-cycle.sh`, Funktion `advance_phase()`.
- **Aktionen:** (a) Stderr des Gate-Aufrufs nach `$CYCLE_LOG` statt `/dev/null`. (b) Wenn `conductor_next` leer (oder nur Whitespace): nächste Phase nicht auf den angefragten Wert setzen, sondern auf die **aktuelle Phase** (aus project.json) — oder **gar nicht** advance_phase aufrufen (siehe unten).

### Ursache → Wirkung (Kette)
1. **Ursache:** Vor jedem Phasenwechsel ruft Bash `research_conductor.py gate …` auf; Ausgabe wird in `conductor_next` gespeichert.
2. **Ohne Fix:** Bei Crash/Timeout/Exception ist die Ausgabe leer; Bash prüft nur `[ -n "$conductor_next" ] && [ "$conductor_next" != "$next_phase" ]` → bei leer ist die Bedingung falsch, also wird `next_phase` nicht überschrieben → **trotzdem** wird `research_advance_phase.py "$PROJ_DIR" "$next_phase"` aufgerufen, also z.B. advance_phase "focus". **Effekt:** Wir advance obwohl der Conductor keine gültige Entscheidung geliefert hat (Fail-Open). Stderr ging nach /dev/null → Fehler unsichtbar.
3. **Mit Fix (Variante A — Plan-Checkliste):** Bei leerem `conductor_next`: `next_phase` = aktuelle Phase aus project.json, dann `advance_phase(next_phase)` wie bisher. **Effekt:** Phase bleibt gleich (z.B. explore → explore), aber **advance_phase(explore)** wird aufgerufen → Python skript schreibt project.json: `phase_history` bekommt einen weiteren Eintrag "explore", `phase` bleibt "explore", `last_phase_at` wird aktualisiert. **Wichtig:** In `research_advance_phase.advance()` wird `loop_count = phase_history.count(new_phase)` erhöht. Nach **4** leeren Gate-Antworten ist `loop_count > 3` → das Skript erzwingt den **nächsten** Phasenschritt (explore → focus). **Konsequenz:** „Nicht advance“ ist nur bis zu 3 Mal sicher; beim 4. Mal advance wir doch (Schutz vor Endlosschleife).
4. **Mit Fix (Variante B — strenger):** Bei leerem `conductor_next`: **keinen** Aufruf von `research_advance_phase.py`; nur loggen und return. **Effekt:** `project.json` bleibt unverändert (phase, phase_history), der Cycle beendet sich; beim **nächsten** Run liest die Bash phase=explore und führt die ganze Explore-Phase erneut aus. Kein Zählen, kein erzwungener Advance nach 4 Mal.

### Wen es betrifft
- **Direkt:** Jeder Phasenwechsel (explore→focus, focus→connect, connect→verify, verify→synthesize, synthesize→done). Nur dort wird das Gate aufgerufen.
- **Indirekt:** Conductor-Logik (gate_check liest project.json, coverage, findings etc.); wenn das Gate fehlschlägt, ist jetzt sichtbar im Log; Entscheidung „nicht advance“ oder „nochmal gleiche Phase“ ist nachvollziehbar.

### Invarianten
- **Nach Fix (A):** Es wird nie mit „leerer“ Conductor-Antwort in die **nächste** Phase gewechselt; höchstens „gleiche Phase“ geschrieben; nach 4× leer erzwingt advance_phase den Schritt weiter (Schleifen-Schutz).
- **Nach Fix (B):** Bei leerer Ausgabe wird project.json nicht verändert; nächster Cycle = Retry derselben Phase ohne Zähler-Effekt.

### Wechselwirkung mit anderen Fixes
- **1.2 und 2.3:** Wenn wir bei Conductor-Override (Conductor sagt „nochmal explore“) `RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1` setzen, verhindern wir, dass genau dieser „nochmal explore“-Fall vom loop_count>3 verschluckt wird. Ohne 2.3 könnte nach 4× „explore“ vom Conductor trotzdem erzwungen focus kommen; mit 2.3 bleibt die Conductor-Entscheidung maßgeblich.

### Risiko
- **Variante A:** Nutzer müssen wissen, dass 4× leeres Gate = automatischer Advance (gewollt als Fail-Safe).
- **Variante B:** Wenn das Gate dauerhaft leer bleibt (z.B. Conductor defekt), bleibt das Projekt in derselben Phase; externer Retry/Cron muss laufen.

---

## 3. Fix 1.1 — read_stats kumulieren (alle Read-Runden)

### Was sich ändert
- **Ort:** `research-cycle.sh`, Explore-Branch: Variablen `read_attempts`, `read_successes`, `read_failures` vor dem ersten parallel_reader initialisieren; nach **jedem** parallel_reader (Round 1, Refinement, Gap, Depth) die letzte Zeile (JSON) parsen und zu diesen Variablen **addieren**. Die bestehende Stelle, die `explore/read_stats.json` schreibt (nach deep_extract), nutzt dann die kumulierten Werte.

### Ursache → Wirkung (Kette)
1. **Ursache:** Mehrere Aufrufe von `research_parallel_reader.py` liefern je eine Zeile JSON mit read_attempts, read_successes, read_failures (oder ähnlich). Bisher wird nur die erste genutzt; die anderen gehen mit `| tail -1 > /dev/null` verloren.
2. **Ohne Fix:** `explore/read_stats.json` enthält nur Round-1-Statistik. **Downstream:** `research_quality_gate._load_explore_stats()` liest diese Datei; `_effective_findings_min()` nutzt `read_attempts` und `read_successes` für die adaptive Untergrenze (bei Erfolgsrate < 0.5 wird die Mindestanzahl Findings gesenkt). Unterzählte Reads → Erfolgsrate kann **zu hoch** erscheinen (nur Round 1, oft gut) → Schwellen können **zu streng** sein; oder umgekehrt bei vielen Fehlern in R2/R3 wird das nicht reflektiert.
3. **Mit Fix:** read_stats = Summe über alle Runden. Evidence Gate und adaptive findings_count_min basieren auf der **tatsächlichen** Lese-Statistik. Mehr Reads mit vielen Fehlern → niedrigere Erfolgsrate → _effective_findings_min kann sinken (z.B. max(3, base*rate*1.5)); weniger „unfair“ Fail bei schlechter Konnektivität.

### Wen es betrifft
- **Direkt:** Explore-Phase (Bash-Variablen, eine JSON-Datei).
- **Downstream:** **Nur** `research_quality_gate.py` (`_load_explore_stats` → `_effective_findings_min` → Evidence-Gate-Entscheidung). Kein anderes Tool liest explore/read_stats.json im kritischen Pfad.

### Invarianten
- **Vorher:** read_stats repräsentiert nur Round 1.
- **Nachher:** read_stats repräsentiert die Summe aller Explore-Reads (Round 1 + Refinement + Gap + Depth). Format und Pfad unverändert; Quality Gate erwartet weiterhin read_attempts, read_successes, read_failures.

### Wechselwirkung mit anderen Fixes
- **Unabhängig** von 1.2, 1.4, 1.5. **2.1 (Coverage im run_cycle):** run_cycle ruft parallel_reader und deep_extract auf, schreibt aber **nicht** in explore/read_stats.json (Bash-Explore-Branch macht das). Daher ändert 1.1 nichts am Conductor-run_cycle; 2.1 ist separat (Coverage-Datei, nicht read_stats).

### Risiko
- **Mittel:** Wenn das Parsen einer Zeile fehlschlägt (anderes Format, mehrere Zeilen), müssen wir robust parsen (z.B. nur letzte Zeile, try/except im Python-One-Liner). Sonst können Variablen leer bleiben oder falsch → write von read_stats mit falschen Werten.

---

## 4. Fix 1.3 — Tool-Fehler im run_cycle: Logging + Abbruch nach N Fehlern

### Was sich ändert
- **Ort:** `research_conductor.py`: `_run_tool` schreibt bei returncode != 0 in eine Log-Datei (z.B. conductor_tool_errors.log) oder in events; `run_cycle` zählt `consecutive_failures`, setzt bei Erfolg auf 0 zurück; bei `consecutive_failures >= N` (z.B. 3): Break, optional project.json status setzen, return False.

### Ursache → Wirkung (Kette)
1. **Ursache:** run_cycle ruft nacheinander Tools auf (_run_tool). Bei Fehler wurde bisher nur `continue` gemacht, kein Log, kein Abbruch.
2. **Ohne Fix:** Ein dauerhaft fehlschlagendes Tool (z.B. API down) führt zu vielen nutzlosen Schritten, bis MAX_STEPS; keine sichtbare Fehlerursache im Projekt.
3. **Mit Fix:** Nach N aufeinanderfolgenden Fehlern bricht run_cycle ab; Fehler sind im Projekt-Log/Events; optional status=failed_conductor_tool_errors. Bash-Pipeline übernimmt beim nächsten Run (research-cycle.sh sieht Conductor „failed or incomplete“, läuft mit Fallback weiter).

### Wen es betrifft
- **Direkt:** Conductor run_cycle (nur wenn RESEARCH_USE_CONDUCTOR=1). Bash-Pipeline ist unverändert.
- **Indirekt:** Operator/Betreiber sehen Fehler im Log; ggf. UI wenn events.jsonl genutzt wird.

### Invarianten
- **Nachher:** Kein endloses Durchlaufen von run_cycle bei dauerhaft fehlendem Tool; es gibt eine obere Schranke (N aufeinanderfolgende Fehler) und Nachweisbarkeit.

### Wechselwirkung mit anderen Fixes
- **2.1, 3.1:** Unabhängig; 1.3 betrifft nur Fehlerbehandlung und Abbruch in run_cycle.

### Risiko
- **Niedrig:** N (z.B. 3) muss sinnvoll gewählt werden; zu klein = vorschneller Abbruch bei temporären Fehlern; zu groß = lange Laufzeit ohne Nutzen.

---

## 5. Fix 2.1 — Coverage im run_cycle

### Was sich ändert
- **Ort:** `research_conductor.run_cycle`: Nach `search_more` und nach `read_more` (und ggf. nach weiteren Aktionen, die sources/findings ändern) `research_coverage.py` aufrufen und Ergebnis persistieren (coverage_round*.json oder eine Conductor-spezifische Datei), damit `read_state` beim nächsten Schritt aktuelle Coverage sieht.

### Ursache → Wirkung (Kette)
1. **Ursache:** decide_action und read_state nutzen u.a. coverage_rate, priority1_uncovered. Im Bash-Explore werden coverage_round*.json von research_coverage.py geschrieben; im run_cycle gibt es nach search_more/read_more **keinen** Aufruf von research_coverage.py.
2. **Ohne Fix:** Conductor entscheidet mit **veralteter** Coverage (oder 0); kann zu „search_more“/„read_more“ in Schleifen führen, obwohl nach dem letzten Read die Coverage schon gut wäre.
3. **Mit Fix:** Nach jedem search_more/read_more ist die Coverage-Datei aktuell; read_state liefert die richtigen Werte; decide_action kann sinnvoll „synthesize“ oder „verify“ wählen.

### Wen es betrifft
- **Direkt:** run_cycle (read_state, decide_action); research_coverage.py (wird aufgerufen).
- **Indirekt:** Conductor-Entscheidungen und damit Phasenverlauf, wenn Conductor Master ist.

### Invarianten
- **Nachher:** Nach jeder Änderung von sources/findings im run_cycle ist Coverage einmal neu berechnet und für read_state verfügbar (gleiche „Wahrheit“ wie in der Bash-Explore-Phase).

### Wechselwirkung mit anderen Fixes
- **1.1:** run_cycle schreibt nicht in explore/read_stats.json; 2.1 betrifft nur Coverage. Keine Überschneidung.
- **2.2, 2.3:** Unabhängig.

### Risiko
- **Niedrig:** research_coverage.py muss mit der gleichen Projekt-Struktur (sources, findings, research_plan) umgehen können wie in der Bash-Phase; das ist bereits der Fall.

---

## 6. Fix 2.2 — steps_taken dokumentieren

### Was sich ändert
- **Ort:** Code + Doku: Regel, wo und wie steps_taken (Conductor) definiert und persistiert wird (z.B. conductor_state.json, write_conductor_step_count), und dass Bash-Pipeline steps_taken nicht nutzt.

### Ursache → Wirkung
- **Wirkung:** Klarheit für Wartung und Debugging; keine Verhaltensänderung der Pipeline, nur Dokumentation und ggf. einheitliche Benennung.

### Wechselwirkung
- Keine Abhängigkeit von anderen Fixes; kann jederzeit ergänzt werden.

---

## 7. Fix 2.3 — advance_phase: loop_count bei Conductor-Override überspringen

### Was sich ändert
- **Ort:** `research_advance_phase.advance()`: Wenn Umgebungsvariable `RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1`, den Block `if loop_count > 3: … next_phase = order[idx+1]` nicht ausführen. In research-cycle.sh: Wenn der Conductor-Override genutzt wurde (next_phase wurde vom Gate geändert), vor dem Aufruf von research_advance_phase.py `export RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1` setzen.

### Ursache → Wirkung (Kette)
1. **Ursache:** Conductor Gate kann „nochmal explore“ zurückgeben (Override). Dann ruft Bash advance_phase("explore") auf. In advance() wird phase_history um "explore" ergänzt; loop_count = count("explore") steigt. Ab loop_count > 3 erzwingt advance() den Sprung zur nächsten Phase (explore → focus), **unabhängig** davon, ob der Conductor bewusst „nochmal explore“ wollte.
2. **Ohne Fix:** Conductor-Entscheidung „nochmal explore“ wird nach 4 Mal durch die Schleifen-Logik überschrieben → Advance zu focus.
3. **Mit Fix:** Wenn der Aufruf von advance_phase aus einem Conductor-Override kommt, wird die loop_count-Logik übersprungen → Phase bleibt „explore“ (oder was der Conductor zurückgab), auch beim 4. Mal.

### Wen es betrifft
- **Direkt:** Nur die Stelle, an der Bash nach Conductor-Gate advance_phase aufruft; und research_advance_phase.py (eine zusätzliche Bedingung).
- **Indirekt:** Conductor als „Herr“ über den Phasenwechsel, wenn Override aktiv ist; Endlosschleifen-Schutz bleibt für den Fall, dass **kein** Override gesetzt ist (normale advance ohne Gate-Änderung).

### Invarianten
- **Nachher:** Conductor-Override führt nicht mehr zum erzwungenen Phasensprung durch loop_count>3; der Override wird respektiert. Ohne Override (normale advance "focus") bleibt loop_count>3 aktiv.

### Wechselwirkung mit anderen Fixes
- **1.2:** Siehe oben (1.2 Variante A: 4× leeres Gate → Advance; 2.3 betrifft nur den Fall „Override gesetzt“, nicht „leeres Gate“).

### Risiko
- **Niedrig:** Man muss sicherstellen, dass RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1 **nur** beim Conductor-Override gesetzt wird, nicht bei jedem advance_phase (sonst würde der Endlosschleifen-Schutz immer ausgeschaltet).

---

## 8. Fix 3.1 — Progress im run_cycle

### Was sich ändert
- **Ort:** `research_conductor.run_cycle`: Nach sinnvollen Schritten (z.B. nach jedem Tool oder nach jedem action-Block) research_progress (progress_step / events) aufrufen, damit die UI „RUNNING“ und den aktuellen Schritt anzeigt.

### Ursache → Wirkung
- **Ohne Fix:** Bei RESEARCH_USE_CONDUCTOR=1 sieht die UI keinen Fortschritt während run_cycle (Progress wird nur in der Bash-Pipeline gesetzt).
- **Mit Fix:** progress.json / events.jsonl werden auch im run_cycle aktualisiert → UX konsistent.

### Wen es betrifft
- **Direkt:** UI (Progress-Anzeige); run_cycle.
- **Invarianten:** Keine Änderung an fachlicher Logik; nur Beobachtbarkeit.

---

## 9. Fix 1.5 — AEM-Block: persist_v2_episode aufrufen

### Was sich ändert
- **Ort:** `research-cycle.sh`: Direkt nach dem AEM_BLOCK-Python-Block (der project.json auf status=aem_blocked setzt), **vor** `exit 0`, Aufruf `persist_v2_episode "aem_blocked"`.

### Ursache → Wirkung (Kette)
1. **Ursache:** AEM in enforce/strict blockiert den Übergang zu Synthesize; project.json wird auf status=aem_blocked gesetzt, dann exit 0. Bisher wird **kein** persist_v2_episode aufgerufen.
2. **Ohne Fix:** Memory/Brain sieht für diesen Run **kein** abgeschlossenes Episode-Outcome; der selbstverbessernde Loop hat eine Lücke („Run ist weder done noch failed noch pending_review“).
3. **Mit Fix:** persist_v2_episode("aem_blocked") liest project.json (bereits status=aem_blocked); der Inline-Code in persist_v2_episode behandelt status "aem_blocked" wie einen terminalen Status (fail_codes, record_run_episode mit user_verdict="none" o.ä.), schreibt Episode und record_read_urls. Danach exit 0. **Effekt:** Jeder Run endet mit einem klaren Outcome in Memory; AEM-Block ist kein „schwarzes Loch“ mehr.

### Wen es betrifft
- **Direkt:** Memory/Brain (record_run_episode, record_memory_decision, record_read_urls); Episoden-Historie.
- **Invarianten:** persist_v2_episode akzeptiert bereits run_status als String und nutzt project.status; "aem_blocked" ist im Code bereits als terminaler Status berücksichtigt (fail_codes).

### Wechselwirkung mit anderen Fixes
- **Unabhängig:** Kein anderer Fix ändert den AEM-Pfad oder persist_v2_episode-Signatur.

### Risiko
- **Niedrig:** Muss vor exit 0 stehen, sonst wird es nie ausgeführt.

---

## 10. Abhängigkeitsgraph (Reihenfolge)

- **1.4** (thesis.json) → keine Abhängigkeit; kann zuerst.
- **1.2** (Conductor-Gate) → keine Code-Abhängigkeit; sinnvoll früh, damit alle weiteren advance_phase-Läufe schon „sicher“ sind.
- **1.1** (read_stats) → unabhängig.
- **1.3** (run_cycle Tool-Fehler) → unabhängig.
- **2.1** (Coverage run_cycle) → unabhängig.
- **2.2** (steps_taken Doku) → unabhängig.
- **2.3** (advance_phase skip loop_limit) → wirkt zusammen mit 1.2 (Conductor-Override); sollte nach 1.2.
- **3.1** (Progress run_cycle) → unabhängig.
- **2.4** (Doku Conductor) → jederzeit.
- **1.5** (AEM persist_v2_episode) → unabhängig.
- **4.1** (read_urls optional) → eigenes Ticket.

Empfohlene Reihenfolge bleibt: **1.4 → 1.2 → 1.1 → 1.3 → 2.1 → 2.2 → 2.3 → 3.1 → 2.4 → 1.5 → 4.1.**

---

## 11. Kurz: Was jede Änderung bewirkt und worauf sie Einfluss hat

| Fix | Bewirkt (direkt) | Beeinflusst (downstream) | Verändert (Invarianten/Verträge) |
|-----|------------------|---------------------------|-----------------------------------|
| 1.4 | Connect stürzt nicht ab | Verify/Synthesize erhalten sauberen Phasenwechsel | thesis.json immer vorhanden beim Connect-Start |
| 1.2 | Conductor-Fehler sichtbar; bei leerem Gate kein blindes Advance | Phasenwechsel; ggf. 4× leer → erzwungen Advance (Variante A) | Gate-Ausgabe = einzige Quelle für Override; leer = nicht advance (oder Retry) |
| 1.1 | read_stats = Summe aller Explore-Reads | Evidence Gate, adaptive findings_count_min | explore/read_stats.json = kumulierte Metrik |
| 1.3 | Tool-Fehler geloggt; Abbruch nach N Fehlern in run_cycle | Conductor run_cycle, ggf. Fallback zur Bash | run_cycle bricht deterministisch ab bei Dauerfehler |
| 2.1 | Coverage nach search_more/read_more aktualisiert | read_state, decide_action im run_cycle | Conductor entscheidet mit aktueller Coverage |
| 2.2 | Doku steps_taken | Wartung/Debug | Keine Verhaltensänderung |
| 2.3 | Conductor-Override ignoriert loop_count>3 | advance_phase bei Override | Conductor-Entscheidung hat Vorrang vor Schleifen-Schutz |
| 3.1 | Progress/Events während run_cycle | UI | Keine fachliche Änderung |
| 1.5 | AEM-Block schreibt Episode | Memory/Brain, Episoden | Jeder Run hat ein Outcome |
| 2.4 | Doku Conductor-Modus | Betreiber | Keine Verhaltensänderung |
| 4.1 | read_urls optional (Focus) | Memory, Fokus-Leseliste | Optionales Verhalten |

---

Damit ist für jede Änderung klar: **was sie bewirkt, worauf sie einfluss hat, was sie verändert und wie sie mit den anderen zusammenspielt.** Das ist die Grundlage für einen Plan, der die reale Wirkung (wie Mathe/Physik) abbildet und fehlerfreie Implementierung ermöglicht.
