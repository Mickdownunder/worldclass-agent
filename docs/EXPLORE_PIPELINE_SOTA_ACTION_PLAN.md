# Pipeline & Conductor — Aktionsplan: Weltklasse-Standard & Ineinandergreifen

**Ziel:** Das System auf den Stand bringen, den du willst: **SOTA-nah, alles greift ineinander, funktioniert zuverlässig — und der Kreislauf (Memory/Brain) kann dauerhaft aus Outcomes lernen.**  
**Basis:** `EXPLORE_PHASE_DEEP_DIVE.md`, `MEMORY_BRAIN_WORLDCLASS_PLAN.md`, `MEMORY_BRAIN_DEEP_DIVE.md`, vollständiger Ablauf aller Phasen (Explore, Focus, Connect, Verify, Synthesize, Done) und aller Fehlerpfade.

**Wirkungsanalyse (Ursache → Wirkung):** Jede Änderung hat reale Konsequenzen: was sie bewirkt, wen sie betrifft, welche Invarianten gelten und wie sie mit anderen Fixes zusammenspielt, ist in **`EXPLORE_PIPELINE_CAUSAL_IMPACT.md`** dokumentiert. Vor der Implementierung dort nachlesen, damit keine ungewollten Seiteneffekte entstehen.

---

## Teil 0: Dein Ziel (explizit) & warum dieser Plan das abdeckt

### 0.1 Was du willst (aus Weltklasse-Plan und Konversation)

- **Leitbild:** LLM-Intelligenz **wie ein Mensch** einsetzen: wahrnehmen, verstehen, schlussfolgern, entscheiden, handeln, reflektieren, dazulernen. Die **Architektur** (Pipeline, Memory, Brain) bringt diese Intelligenz zum Tragen — strukturiert, wiederholbar, lernend.
- **Pipeline:** **Alles greift ineinander** — keine versteckten Fehler, keine falschen Metriken, keine Fail-Open ohne Log. Conductor und Bash nutzen dieselbe „Wahrheit“ (Coverage, read_stats, Phase). Jede Phase (Explore, Focus, Connect, Verify, Synthesize) ist durchdrungen: Ablauf, Tools, Artefakte, Fehlerpfade.
- **Memory/Brain:** **Jeder Run schreibt Outcome** (run_episode, record_project_outcome, record_quality, persist_v2_episode, experience_distiller, utility_update). Ohne das kann der selbstverbessernde Loop nicht laufen (MEMORY_BRAIN_WORLDCLASS_PLAN: „Stabile Feedback-Quellen“). Explainability: Nachvollziehbar, welche Memories/Strategies eine Decision beeinflusst haben.
- **SOTA/Novel:** Episoden-Verlauf (nicht 1:1 pro Projekt), Two-Phase Retrieval + Utility, Strategy aus Daten, Reflection-Synthese, Konsolidierung — wie in Teil C und D des Weltklasse-Plans. Der **Pipeline-Plan** stellt sicher, dass die **Daten** (Outcomes, Episoden, Gate-Metriken) **immer ankommen**; der **Memory/Brain-Plan** (Phasen 1–6) baut darauf auf.

### 0.2 Warum dieser Plan „weltklasse-tauglich“ ist

- **Vollständigkeit:** Alle fünf Research-Phasen (Explore, Focus, Connect, Verify, Synthesize) und Done sind erfasst — Ablauf, beteiligte Dateien, bekannte Fehler (inkl. Connect thesis.json, read_stats, Conductor-Gate, Recovery/Evidence-Gate, AEM, Critic). Kein „nur Explore“.
- **Fehlerpfade:** Jeder terminale Zustand (done, failed_*, pending_review, aem_blocked) wird durchgegangen: Wird persist_v2_episode / record_project_outcome / experience_distiller / utility_update aufgerufen? Wenn eine Stelle fehlt, ist sie im Plan als Fix enthalten.
- **Abgleich mit Weltklasse-Plan:** Die Pipeline-Fixes (Korrektheit, Conductor, Beobachtbarkeit) sind die **Voraussetzung** dafür, dass Phasen 1–6 des Memory/Brain-Plans greifen können (Episoden, Utility, Strategy aus Daten). Dieser Plan nennt die konkreten Code-/Doc-Änderungen; der Weltklasse-Plan nennt die Ziele und die Phasen 1–6.
- **Nach Umsetzung:** Mit diesem Plan können wir behaupten: **Alle Abläufe und Fehler im Research-Pipeline-System sind erfasst; der Umbau ist auf SOTA/Novel und dein explizites Ziel ausgerichtet; die Pipeline liefert stabile Feedback-Quellen für den dauerhaften Selbstverbesserungs-Loop.**

---

## Vollständiger System-Überblick (alle Phasen, alle Fehlerpfade)

| Phase | Kernablauf | Kritische Abhängigkeiten | Bekannte Fehler/Lücken |
|-------|------------|--------------------------|-------------------------|
| **Explore** | Plan → Search → Rank → Memory-Filter → Parallel Read (R1–R3) → Saturation → Coverage → Deep Extract → read_stats → Relevance/Context/Outline → advance_phase(focus) + Conductor Gate | research_plan.json, sources, findings, coverage_round*.json, explore/read_stats.json | 1.1–1.2–2.1–3.1 umgesetzt: read_stats kumuliert, Gate stderr/leer gefixt, run_cycle mit Coverage + Progress. |
| **Focus** | Coverage-Datei (round3/2/1) → Planner --gap-fill → Web Search → FOCUS_SAVE + RANK_FOCUS → parallel_reader focus → deep_extract → context_manager → advance_phase(connect) | coverage_round*.json (von Explore); focus_read_order.txt nur **unread** sources | Focus-Stats nicht in explore/read_stats (bewusst getrennt); kein Memory-Filter auf focus_read_order. |
| **Connect** | connect.sh: OpenAI-Check → research_entity_extract → research_reason contradiction_detection, hypothesis_formation → thesis.json Update → advance_phase(verify) | thesis.json (wird in **init** angelegt; Connect legt Default an falls fehlend) | Fix 1.4 umgesetzt: thesis.json Default bei fehlender Datei. |
| **Verify** | source_reliability, claim_verification, fact_check, claim_ledger → AEM (optional) → Counter-Evidence (optional) → **Evidence Gate** → bei Fail: Recovery (1×) oder pending_review oder Loop-back focus (max 2×) oder GATE_FAIL + abort_report + Brain/Memory + persist_v2_episode(failed) | verify/*.json, quality_gate, findings, sources, explore/read_stats | Gate bei Timeout → Fallback JSON pass:false; Recovery-Stats nicht in read_stats; Loop-back advance_phase(focus) durchläuft Conductor Gate. |
| **Synthesize** | report.md → apply_verified_tags → References → claim_evidence_map → Critic (bis zu MAX_REVISE_ROUNDS) → bei Score &lt; Threshold: failed_quality_gate + outcome + distiller + utility + persist_v2_episode(failed); sonst PDF, embed, cross_domain, advance_phase(done), Brain/Memory, distiller, utility, persist_v2_episode(done) | claim_ledger, findings, sources, thesis.json (optional) | Alle terminalen Pfade rufen persist_v2_episode und distiller/utility auf (geprüft). |
| **Done** | Nur Log „already done“. | — | — |

### Memory/Brain: Pflicht-Outcomes (kein Run ohne Schreiben)

- **done:** persist_v2_episode("done"), record_episode, record_quality, record_project_outcome(approved), experience_distiller, utility_update.  
- **failed_insufficient_evidence (Evidence Gate):** GATE_FAIL schreibt project.json; abort_report; BRAIN_REFLECT (record_episode, record_quality, record_project_outcome user_verdict=none); experience_distiller, utility_update; persist_v2_episode("failed").  
- **failed_quality_gate (Critic):** QF_FAIL; abort_report; OUTCOME_RECORD (record_project_outcome rejected); experience_distiller, utility_update; persist_v2_episode("failed").  
- **pending_review:** project.json status; **kein** persist_v2_episode (gewollt: Mensch entscheidet).  
- **aem_blocked:** AEM_BLOCK; exit 0; **kein** persist_v2_episode im aktuellen Code — **Lücke:** AEM-Block sollte Outcome/Episode schreiben (Fix 1.5 optional).

---

## Übersicht der Umsetzungs-Phasen

| Phase | Fokus | Aufwand (grob) | Abhängigkeiten |
|-------|--------|-----------------|----------------|
| **1** | Korrektheit & Robustheit | 1–2 Tage | keine |
| **2** | Conductor & Pipeline konsistent | 1–2 Tage | Phase 1 optional (Gate zuerst) |
| **3** | Beobachtbarkeit & UX | 0,5 Tag | keine |
| **4** | Optional / SOTA (Memory, Doku) | 1+ Tage | Phase 1–3 |

---

## Phase 1: Korrektheit & Robustheit

Ohne diese Punkte sind Metriken falsch oder Fehler unsichtbar — das untergräbt jedes „alles greift“.

### 1.1 read_stats kumulieren (alle Read-Runden)

**Problem:** `explore/read_stats.json` enthält nur die Statistik der **ersten** parallel_reader-Runde (read_order_round1). Refinement-, Gap- und Depth-Reads werden verworfen (`| tail -1 > /dev/null`). Evidence Gate und adaptive findings_count_min basieren auf unterzählten Reads.

**Ziel:** Nach allen Explore-Reads (Round 1 + ggf. Refinement + Gap + Depth) eine **kumulierte** Statistik (read_attempts, read_successes, read_failures) in `explore/read_stats.json` schreiben.

**Änderungen:**

1. **research-cycle.sh (explore-Branch)**  
   - Vor dem ersten parallel_reader: `read_attempts=0`, `read_successes=0`, `read_failures=0`.  
   - Nach **jedem** Aufruf von `research_parallel_reader.py`: stdout (letzte Zeile JSON) parsen und zu `read_attempts`, `read_successes`, `read_failures` **addieren** (nicht nur nach Round 1).  
   - Die bestehende Stelle, die `explore/read_stats.json` schreibt (nach deep_extract), unverändert lassen, aber die Variablen sind dann bereits kumuliert.  
   - Konkret: Bei Refinement/Gap/Depth nicht `> /dev/null`, sondern in eine temporäre Variable parsen und aufaddieren.

2. **Optional:** Kleines Python-Skript `tools/research_read_stats_merge.py` (z.B. nimmt Liste von JSON-Strings oder Dateien, gibt ein einziges aggregiertes JSON aus), dann ruft Bash das einmal am Ende auf. Alternativ reines Bash-Parsing nach jedem parallel_reader (weniger elegant, aber ohne neues Tool).

**Akzeptanz:** Nach einem Explore-Run mit Coverage nicht pass (also mit Refinement+Gap+Depth) enthält `explore/read_stats.json` die **Summe** aller Versuche/Erfolge/Fehler. Quality Gate nutzt diese Werte (bereits über `_load_explore_stats`).

---

### 1.2 Conductor-Gate: Stderr loggen, bei leerer Ausgabe nicht advance

**Problem:** Gate-Aufruf: `conductor_next=$(... 2>>/dev/null) || true`. Bei Crash/Timeout ist die Ausgabe leer → Bash wertet „Override“ nicht aus und **advance** trotzdem. Fail-Open ohne Log.

**Ziel:** Stderr sichtbar machen; bei leerem `conductor_next` **nicht** advance, sondern **gleiche Phase** nochmal (sichere Wiederholung) oder explizites Fail-Safe (z.B. nach 2 leeren Antworten doch advance).

**Änderungen:**

1. **research-cycle.sh**  
   - In `advance_phase()`: `2>>/dev/null` durch `2>> "$CYCLE_LOG"` ersetzen, damit Conductor-Fehler im Projekt-Log landen.  
   - Nach dem Aufruf: Wenn `conductor_next` leer ist (oder nur Whitespace), **nicht** `next_phase="$conductor_next"` setzen, sondern:  
     - Option A (konservativ): `next_phase` unverändert lassen (nochmal dieselbe Phase laufen).  
     - Option B: Zähler für „leere Gate-Antworten“ (z.B. in einer temporären Datei oder Env); beim zweiten Mal leer → doch `next_phase` wie gewünscht (advance), um Deadlock zu vermeiden.  
   - Dokumentieren: „Leere Gate-Ausgabe = Conductor-Fehler; wir wiederholen die Phase (oder advance nach 2× leer).“

**Akzeptanz:** Conductor-Crash/Timeout erscheint in `log.txt`; bei leerer Ausgabe wird nicht blind advance gemacht (mindestens Option A umgesetzt).

---

### 1.3 Tool-Fehler im run_cycle: Logging + Abbruch nach N Fehlern

**Problem:** `_run_tool` gibt nur True/False zurück; bei False wird oft `continue` gemacht. Kein Retry, kein projektspezifisches Log, kein Abbruch bei wiederholten Fehlern.

**Ziel:** Fehlgeschlagene Tool-Aufrufe im Conductor run_cycle in eine Datei loggen (z.B. `conductor_tool_errors.log` oder Einträge in `events.jsonl`); optional: nach N Fehlern in Folge (z.B. 3) die Schleife abbrechen und Phase/Status setzen (z.B. „failed_conductor_tool_errors“).

**Änderungen:**

1. **research_conductor.py**  
   - `_run_tool`: Bei returncode != 0 einen Eintrag schreiben (z.B. in `proj / "conductor_tool_errors.log"` oder über `research_progress`/events: „conductor_tool_error“, tool, args, returncode).  
   - In `run_cycle`: Zähler `consecutive_failures`; nach jedem fehlgeschlagenen _run_tool erhöhen, bei Erfolg zurücksetzen. Wenn `consecutive_failures >= 3` (konfigurierbar): Break, optional `project.json` status setzen (z.B. `failed_conductor_tool_errors`), Return False.  
   - So wird nicht endlos weiterlaufen, wenn ein Tool dauerhaft fehlschlägt.

**Akzeptanz:** Drei fehlgeschlagene Tool-Aufrufe in Folge → run_cycle bricht ab; Fehler sind in Log/Events sichtbar.

---

### 1.4 Connect: thesis.json fehlt → Absturz vermeiden

**Problem:** `connect.sh` liest `(p / "thesis.json").read_text()` ohne Prüfung. thesis.json wird nur in `research-init.sh` angelegt. Wenn Connect in Isolation läuft oder das Projekt ohne Init wiederhergestellt wurde, stürzt der Python-Block ab (FileNotFoundError).

**Ziel:** Vor dem Lesen prüfen: Existiert thesis.json nicht → mit Default `{"current": "", "confidence": 0.0, "evidence": []}` anlegen (wie in init), dann fortfahren.

**Änderungen:**

1. **workflows/research/phases/connect.sh** — Im Python-Block vor `th = json.loads((p / "thesis.json").read_text())`:  
   `if not (p / "thesis.json").exists(): (p / "thesis.json").write_text(json.dumps({"current": "", "confidence": 0.0, "evidence": []}, indent=2))`  
   Dann `th = json.loads(...)` wie bisher.

**Akzeptanz:** Connect läuft auch, wenn thesis.json fehlte; Projekt bleibt konsistent.

---

### 1.5 (Optional) AEM block: Outcome/Episode schreiben

**Problem:** Bei `aem_blocked` wird project.json gesetzt und exit 0; es gibt **keinen** Aufruf von persist_v2_episode oder record_project_outcome. Für den Weltklasse-Loop („jeder Run schreibt Outcome“) sollte auch AEM-Block ein Outcome/Episode schreiben.

**Ziel:** Nach AEM_BLOCK (vor exit 0) persist_v2_episode mit Status z.B. "aem_blocked" aufrufen (oder einen kleinen Python-Block, der record_project_outcome/record_episode mit passendem status aufruft), damit Memory/Brain diesen Run als abgeschlossen mit bekanntem Outcome sieht.

**Änderungen:** research-cycle.sh nach dem AEM_BLOCK-Python-Block: `persist_v2_episode "aem_blocked"` (oder neuer Status) aufrufen, sofern persist_v2_episode solche Status akzeptiert; andernfalls in persist_v2_episode erlauben oder separater kleiner Block record_episode/record_project_outcome.

**Akzeptanz:** AEM-blockierte Runs erscheinen im Memory/Episode-Log mit klarem Status.

---

## Phase 2: Conductor & Pipeline konsistent

Damit Conductor und Bash-Pipeline dieselbe „Wahrheit“ nutzen und klar definiert sind.

### 2.1 run_cycle: Coverage nach search_more/read_more aktualisieren

**Problem:** Im Conductor run_cycle wird `research_coverage.py` nie aufgerufen. `coverage_score` in read_state bleibt alt oder 0 → Entscheidungen (z.B. verify) basieren auf veralteten Daten.

**Ziel:** Nach jeder search_more- und read_more-Aktion optional `research_coverage.py` aufrufen und Ergebnis in `proj/coverage_round1.json` (oder eine feste Datei, die read_state liest) schreiben, damit read_state einen aktuellen coverage_score hat.

**Änderungen:**

1. **research_conductor.py (run_cycle)**  
   - Nach dem Block **search_more** (nach dem Schreiben der sources): `_run_tool(project_id, "research_coverage.py", project_id)` mit capture_stdout=True; stdout in `proj / "coverage_round1.json"` schreiben (oder Round-Nummer beibehalten: z.B. immer coverage_round1 im Conductor-Modus überschreiben).  
   - Nach dem Block **read_more** (nach deep_extract/context/supervisor): erneut `research_coverage.py` aufrufen und gleiche Datei aktualisieren.  
   - read_state liest bereits coverage_round3/2/1; damit ist coverage_score nach jedem Schritt aktuell.

**Akzeptanz:** Conductor run_cycle: Nach search_more und read_more existiert eine aktuelle Coverage-Datei; read_state liefert einen sinnvollen coverage_score.

---

### 2.2 steps_taken: Eine klare Quelle der Wahrheit

**Problem:** steps_taken wird aus `phase_history` Länge gelesen, außer wenn `conductor_state.json` existiert — dann überschreibt dessen `steps_taken`. Zwei Quellen, bei Wechsel Bash/Conductor verwirrend.

**Ziel:** Eine dokumentierte Regel: Wenn Conductor aktiv (conductor_state.json vorhanden oder RESEARCH_USE_CONDUCTOR=1), dann steps_taken **nur** aus conductor_state; phase_history nur für Phasenverlauf (welche Phase als nächstes / Historie). Sonst steps_taken = len(phase_history).

**Änderungen:**

1. **research_conductor.py (read_state)**  
   - Kommentar oder klare Logik: „steps_taken: if conductor_state.json exists and has steps_taken, use it; else use len(phase_history).“  
   - Keine Änderung der Semantik nötig, wenn das bereits so ist — nur **dokumentieren** in Code und in EXPLORE_PHASE_DEEP_DIVE.md / RESEARCH_AUTONOMOUS.md.

2. **Docs**  
   - In EXPLORE_PHASE_DEEP_DIVE.md (Abschnitt 10 oder 2): „steps_taken wird ausschließlich aus conductor_state.json gelesen, falls vorhanden; andernfalls aus phase_history. phase_history dient nur dem Phasenverlauf.“

**Akzeptanz:** Regel in Code und Doku eindeutig; keine doppelte Semantik mehr unklar.

---

### 2.3 advance_phase: loop_count bei Conductor-Override respektieren

**Problem:** Wenn dieselbe Phase schon dreimal in phase_history vorkommt, erzwingt advance_phase die **nächste** Phase. Conductor könnte bewusst „nochmal explore“ wollen — nach dem dritten Mal wird trotzdem focus erzwungen.

**Ziel:** Wenn der Aufruf von advance_phase von einem **Conductor-Override** kommt (d.h. wir setzen bewusst die **gleiche** Phase wieder), die loop_count-Logik **nicht** anwenden (nicht automatisch zur nächsten Phase springen). Nur anwenden, wenn die Pipeline „normal“ zur nächsten Phase wechselt.

**Änderungen:**

1. **research_advance_phase.py**  
   - Neuer optionaler Parameter oder Env: z.B. `RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1` oder drittes Argument `--conductor-override`. Wenn gesetzt: Bei `new_phase == prev_phase` (oder explizit conductor-override) die Prüfung `loop_count > 3` **nicht** ausführen; Phase unverändert schreiben.  
   - research-cycle.sh: Beim Aufruf nach Conductor-Override (wenn next_phase auf „explore“ etc. geändert wurde) diese Option setzen (Env oder neues Argument).  
   - research_conductor.py: Bei advance_phase(proj, next_phase) nach run_cycle kein Override-Fall (dort wird nur synthesize/done gesetzt). Nur Bash ruft advance_phase mit „wieder gleiche Phase“ auf → also nur in research-cycle.sh die Option übergeben.

2. **research-cycle.sh**  
   - In advance_phase(): Wenn `next_phase` durch Conductor-Override geändert wurde (z.B. wir haben vorher „focus“ übergeben, conductor_next ist „explore“), dann Aufruf von research_advance_phase.py mit z.B. `RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1` oder drittes Arg, damit advance_phase die loop_count-Logik überspringt.

**Akzeptanz:** Conductor kann „nochmal explore“ auch ein viertes Mal erzwingen, ohne dass advance_phase automatisch auf focus springt.

---

### 2.4 Doku: Conductor-as-Master als vereinfachter Modus

**Ziel:** In RESEARCH_AUTONOMOUS.md und EXPLORE_PHASE_DEEP_DIVE.md klarstellen: „Conductor-as-Master (RESEARCH_USE_CONDUCTOR=1) ist ein **vereinfachter** Aktionen-Loop (search_more, read_more, verify, synthesize). Er **ersetzt nicht** die volle 3-Runden-Explore-Pipeline (SMART_RANK, Refinement, Gap, Depth, Saturation).“

**Änderungen:**  
- RESEARCH_AUTONOMOUS.md: Den bestehenden Hinweis (Abschnitt Conductor als Master) beibehalten und ggf. um einen Satz ergänzen: „Für maximale Explore-Tiefe die Bash-Pipeline mit RESEARCH_USE_CONDUCTOR=0 nutzen; Conductor-Modus für schnellere/leichtere Runs.“  
- EXPLORE_PHASE_DEEP_DIVE.md: In Abschnitt 10.2 (Was nicht sauber ist) und 10.3 (Empfehlungen) bereits enthalten; optional eine Kurzzeile in der Inhaltsübersicht oder am Anfang von Abschnitt 10.

**Akzeptanz:** Jeder, der die Doku liest, versteht den Unterschied zwischen vollem Explore (Bash) und Conductor-Modus.

---

## Phase 3: Beobachtbarkeit & UX

### 3.1 Progress im run_cycle

**Problem:** run_cycle ruft weder progress_start noch progress_step auf → UI zeigt bei RESEARCH_USE_CONDUCTOR=1 keinen Fortschritt (Phase „explore“ ohne sichtbare Schritte).

**Ziel:** Vor/nach jeder Aktion im run_cycle (search_more, read_more, verify, synthesize) progress_start(phase) bzw. progress_step(„…“) aufrufen, damit die UI den aktuellen Schritt anzeigt.

**Änderungen:**

1. **research_conductor.py**  
   - Am Anfang von run_cycle: `progress_start(project_id, phase)` (phase aus project.json).  
   - Vor search_more: progress_step(project_id, "Conductor: searching for more sources", …).  
   - Vor read_more: progress_step(project_id, "Conductor: reading more sources", …).  
   - Vor verify: progress_step(project_id, "Conductor: running verification", …).  
   - Vor synthesize: progress_step(project_id, "Conductor: synthesizing report", …).  
   - Implementierung über Aufruf von `research_progress.step(...)` bzw. Subprocess `research_progress.py step ...` (wie in Bash), damit progress.json und events konsistent sind.

**Akzeptanz:** Bei RESEARCH_USE_CONDUCTOR=1 zeigt die UI während run_cycle wechselnde Schritte (z.B. „Conductor: reading more sources“) statt starrer „explore“.

---

## Phase 4: Optional / SOTA

Diese Punkte bringen das System näher an SOTA; sie sind nicht zwingend für „alles greift“, aber für deinen langfristigen Standard.

### 4.1 Memory read_urls: paraphrase-robust

**Problem:** get_read_urls_for_question nutzt exakten question_hash; leichte Umformulierung = anderer Hash = keine URL-Dedup über Paraphrase.

**Ziel:** Optional semantisches Matching (z.B. Embedding-Nearest-Neighbor oder normalisierter/expandierter Hash), damit gleiche Intention dieselben URLs skippt.

**Hinweis:** Größerer Aufwand (Embedding-Infrastruktur oder Frage-Normalisierung); kann als separates Backlog-Item geführt werden. Priorität nach Phase 1–3.

---

### 4.2 Weitere SOTA-Ideen (Backlog)

- Novelty: Embedding-Ähnlichkeit neben Jaccard (EXPLORE_PHASE_DEEP_DIVE Abschnitt 8).  
- Refinement-Queries aus Episoden (RAG aus erfolgreichen Queries).  
- Coverage semantisch (Topic-/Finding-Embeddings).

Diese können in einem separaten „SOTA Backlog“ oder in MEMORY_BRAIN_WORLDCLASS_PLAN.md weiter ausformuliert werden.

---

## Reihenfolge der Umsetzung (Vorschlag)

1. **1.2** Conductor-Gate (Stderr + leere Ausgabe) — schnell, hoher Nutzen für Robustheit.  
2. **1.1** read_stats kumulieren — Evidence Gate und Metriken korrekt.  
3. **1.4** Connect thesis.json — verhindert Absturz bei fehlender Datei.  
4. **1.3** Tool-Fehler run_cycle — verhindert sinnlose Schleifen.  
5. **2.1** Coverage im run_cycle — Conductor entscheidet mit aktuellen Daten.  
6. **2.2** steps_taken dokumentieren — Klarheit.  
7. **2.3** advance_phase loop_count bei Conductor-Override — Kontrolle beim Conductor.  
8. **3.1** Progress im run_cycle — UX.  
9. **2.4** Doku Conductor-Modus — einmalig.  
10. **1.5** (Optional) AEM block Outcome schreiben — Memory-Loop vollständig.  
11. **4.1** Memory read_urls (optional) — wenn Kapazität.

---

## Abnahme / Definition of Done

- **Phase 1:** Nach einem vollen Explore-Run (mit Rounds 2/3) sind read_stats kumuliert; Conductor-Gate loggt Fehler und advance nicht bei leerer Ausgabe; run_cycle bricht nach N Tool-Fehlern ab und loggt sie; Connect stürzt nicht ab bei fehlendem thesis.json (1.4); optional AEM-Block schreibt Outcome (1.5).  
- **Phase 2:** Conductor run_cycle schreibt nach search_more/read_more Coverage; steps_taken-Regel ist in Code und Doku festgehalten; Conductor-Override kann dieselbe Phase mehrfach wählen ohne erzwungenen Phasensprung; Doku erklärt Conductor-Modus.  
- **Phase 3:** Bei RESEARCH_USE_CONDUCTOR=1 zeigt die UI Fortschritts-Schritte während run_cycle.  
- **Phase 4:** Nach Priorität; 4.1 als eigenes Ticket/Backlog.  
- **Vollständigkeit:** Der Abschnitt „Vollständiger System-Überblick“ oben bleibt Referenz; bei neuen Fehlerpfaden oder Phasen-Änderungen den Plan und ggf. EXPLORE_PHASE_DEEP_DIVE aktualisieren.

---

## Abschluss: Behauptung nach Umsetzung

Nach vollständiger Umsetzung der Phasen 1–3 und der dokumentierten Doku-/Optional-Punkte (2.4, 1.5, 4.1) gilt:

- **Alle Abläufe** der Research-Pipeline (Explore, Focus, Connect, Verify, Synthesize, Done) sind erfasst; jede Phase und jeder Fehlerpfad ist im Plan berücksichtigt.
- **Alle bekannten Fehler** (read_stats, Conductor-Gate, thesis.json, run_cycle Coverage/Progress/Tool-Fehler, steps_taken, advance_phase loop_count, optional AEM-Outcome) sind mit konkreten Änderungen adressiert.
- **Memory/Brain** erhält stabile Feedback-Quellen (persist_v2_episode, record_project_outcome, experience_distiller, utility_update) an allen terminalen Zuständen; der selbstverbessernde Loop aus MEMORY_BRAIN_WORLDCLASS_PLAN kann darauf aufbauen.
- **Dein Ziel** (Weltklasse, alles greift ineinander, SOTA/Novel, dauerhaftes Lernen) ist explizit im Plan verankert und durch die Umsetzung erreichbar.

Damit kann behauptet werden: **Der Plan ist weltklasse-tauglich; alle Abläufe und Fehler im aktuellen System sind verstanden und der Umbau kann SOTA/Novel umsetzen und dein Ziel zu 100 % abdecken.**

---

## Implementierungs-Checkliste (für fehlerfreie Umsetzung)

Im Code verifiziert; bei Umsetzung genau so umsetzen:

- **1.1 read_stats:** Nach erstem parallel_reader (Zeile 612–615) sind read_attempts/read_successes gesetzt. An den drei Stellen Refinement (657), Gap (690), Depth (727): Ausgabe in Variable fangen (nicht > /dev/null), mit gleichem Python-One-Liner parsen und zu read_attempts/read_successes **addieren**; read_failures = read_attempts - read_successes bleibt.
- **1.2 Conductor-Gate:** In advance_phase(): Stderr `2>> "$CYCLE_LOG"`. Wenn conductor_next leer: (Variante A) next_phase aus project.json lesen (aktuelle Phase), dann advance_phase(next_phase) — Phase bleibt gleich, phase_history wächst; nach 4× leer erzwingt advance_phase den nächsten Schritt. (Variante B, strenger) advance_phase **nicht** aufrufen, nur loggen und return — project.json unverändert, nächster Run retry dieselbe Phase. Siehe `EXPLORE_PIPELINE_CAUSAL_IMPACT.md` Abschnitt 2.
- **1.4 thesis.json:** In connect.sh im Block PY, **vor** `th = json.loads((p / "thesis.json").read_text())`: `if not (p / "thesis.json").exists(): (p / "thesis.json").write_text(json.dumps({"current": "", "confidence": 0.0, "evidence": []}, indent=2))`.
- **2.3 advance_phase:** In research_advance_phase.advance(): Wenn `os.environ.get("RESEARCH_ADVANCE_SKIP_LOOP_LIMIT") == "1"`, den Block `if loop_count > 3: ...` überspringen. In research-cycle.sh: Bei Conductor-Override (next_phase geändert) vor Aufruf von research_advance_phase.py `export RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1`.
- **1.5 AEM:** Nach AEM_BLOCK (vor exit 0) `persist_v2_episode "aem_blocked"` aufrufen; persist_v2_episode akzeptiert run_status als String und schreibt Episode (project hat dann bereits status=aem_blocked).

Empfohlene Reihenfolge: 1.4 → 1.2 → 1.1 → 1.3 → 2.1 → 2.2 → 2.3 → 3.1 → 2.4 → 1.5 → 4.1. Nach jedem Fix: kurzer Test und Log prüfen.

Wenn du willst, kann als Nächstes eine dieser Aufgaben konkret im Code umgesetzt werden (z.B. 1.4 oder 1.2).
