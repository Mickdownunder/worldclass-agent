# Refactoring-Plan: lib/brain.py

**Ziel:** Die ~1145 Zeilen und eine große Brain-Klasse in ein Paket `lib/brain/` mit klaren Modulen aufteilen, **ohne die öffentliche API zu ändern**. Alle Aufrufer (bin/brain, planner.sh, Tests) funktionieren weiter mit `from lib.brain import Brain` und `Brain().run_cycle()` etc.

---

## 1. Ausgangslage

| Aspekt | Aktuell |
|--------|--------|
| **Datei** | `lib/brain.py` (~1145 Zeilen, 1 Klasse Brain, ~20 Methoden + 5 Modul-Funktionen) |
| **Rolle** | Cognitive Core: Perceive → Understand → Think → Decide → Act → Reflect; Plumber-Integration; run_cycle, reflect_on_job. |
| **Aufrufer** | `bin/brain` (Brain, perceive, think, run_cycle, reflect_on_job), `workflows/planner.sh` (brain think --goal), `tests/unit/test_brain_helpers.py` (_reflection_is_low_signal, _compact_state_for_think) |

**Öffentliche API (muss erhalten bleiben):**

- `Brain` — Klasse mit `__init__(governance_level=2)`, Context Manager (`with Brain() as brain`)
- `brain.perceive()` → dict (state)
- `brain.understand(state, goal)` → dict
- `brain.think(state, goal, understanding=None)` → dict (plan)
- `brain.decide(plan, retrieved_memory_ids=None)` → dict (decision)
- `brain.act(decision)` → dict (action_result)
- `brain.reflect(action_result, goal, retrieved_principle_ids=None)` → dict
- `brain.run_cycle(goal)` → dict
- `brain.reflect_on_job(job_dir, goal)` → dict
- `brain.close()` / `__enter__` / `__exit__`
- Modul-Level (Tests): `_reflection_is_low_signal`, `_compact_state_for_think`

**Abhängigkeiten (unverändert):** `lib.memory.Memory`, `lib.brain_context`, `lib.plumber` (als _plumber), Pfade (OPERATOR_ROOT, BASE, JOBS, WORKFLOWS, …), CONF/secrets, subprocess für op job/run.

---

## 2. Prinzipien

1. **Paket statt eine Datei:** `lib/brain.py` wird zu `lib/brain/` (Verzeichnis). `lib/brain/__init__.py` re-exportiert `Brain` und die Test-Helfer, sodass `from lib.brain import Brain`, `from lib.brain import _reflection_is_low_signal` unverändert funktionieren.
2. **Keine Logik-Änderung:** Nur Verschieben; gleiche Signaturen, gleiche Rückgaben. Keine neuen Features.
3. **Brain-Klasse bleibt Einstieg:** Die Klasse lebt in einem Modul (z. B. `run.py`) und ruft reine Phasen-Funktionen in anderen Modulen auf; sie hält weiterhin `self.memory`, `self.governance_level`, LLM/Secrets und orchestriert.

---

## 3. Zielstruktur

```
lib/
  brain.py          → entfernt (ersetzt durch Paket)
  brain/
    __init__.py     # Re-Export: Brain, _reflection_is_low_signal, _compact_state_for_think
    constants.py    # BASE, CONF, JOBS, WORKFLOWS, KNOWLEDGE, FACTORY, RESEARCH,
                    # GOVERNANCE_LEVELS, REFLECT_LLM_TIMEOUT_SEC, _REFLECTION_* Konstanten
    helpers.py      # _utcnow, _trace_id, _load_secrets, _reflection_is_low_signal, _compact_state_for_think
    perceive.py     # perceive_phase(memory, governance_level) → state
    understand.py   # understand_phase(state, goal, memory) → understanding
    think.py        # think_phase(state, goal, understanding, memory, llm_json_fn) → plan
    decide.py       # decide_phase(plan, governance_level, memory) → decision
    act.py          # act_phase(decision, memory, run_plumber_fn, llm_json_fn) → action_result
                    # + _act_plumber_phase(...)
    reflect.py      # reflect_phase(action_result, goal, memory, retrieved_principle_ids, llm_json_fn) → reflection
    run.py          # Brain-Klasse (__init__, llm, _llm_reason, _llm_json; Methoden rufen *_phase auf),
                    # run_cycle, reflect_on_job, close, __enter__, __exit__
```

---

## 4. Modul-Inhalte und Abhängigkeiten

### 4.1 `brain/constants.py`

- **Inhalt:** `BASE`, `CONF`, `JOBS`, `WORKFLOWS`, `KNOWLEDGE`, `FACTORY`, `RESEARCH` (Path aus OPERATOR_ROOT/home); `GOVERNANCE_LEVELS`, `REFLECT_LLM_TIMEOUT_SEC`; `_REFLECTION_GENERIC_OUTCOMES`, `_REFLECTION_GENERIC_LEARNINGS_PREFIXES`, `_REFLECTION_FAILURE_KEYWORDS`.
- **Abhängigkeiten:** `os`, `pathlib.Path`.
- **Zeilenreferenz (aktuell):** 31–59.

### 4.2 `brain/helpers.py`

- **Inhalt:** `_utcnow()`, `_trace_id()`, `_load_secrets()` (liest CONF/secrets.env), `_reflection_is_low_signal(outcome, learnings, quality)`, `_compact_state_for_think(state, limit)`.
- **Abhängigkeiten:** `constants` (CONF, _REFLECTION_*), `hashlib`, `time`, `json`, `datetime`.
- **Zeilenreferenz:** 62–111.

### 4.3 `brain/perceive.py`

- **Inhalt:** `perceive_phase(memory, governance_level) -> dict`. Baut das komplette State-Dict (system, recent_jobs, workflows, clients, goals, priorities, research_projects, research_playbooks, memory.state_summary, research_context via brain_context.compile, plumber_last_scan, workflow_health, workflow_trends, governance). Nutzt JOBS, WORKFLOWS, KNOWLEDGE, RESEARCH, BASE, FACTORY aus constants; ruft `memory.state_summary()`, `memory.all_playbooks()`, `memory.quality_trend()`, `brain_context.compile(memory, query=...)`.
- **Abhängigkeiten:** `constants`, `helpers` (_utcnow), `lib.memory`, `lib.brain_context`, `json`, `os`, `pathlib`.
- **Zeilenreferenz:** 164–410.

### 4.4 `brain/understand.py`

- **Inhalt:** `understand_phase(state, goal, memory) -> dict`. Baut situation, relevant_episodes_summary, why_helped_hurt, uncertainties, options, retrieved_memory_ids; ruft `memory.record_decision(phase="understand", ...)`.
- **Abhängigkeiten:** `constants` (für _trace_id aus helpers), `helpers` (_trace_id), `memory`, `json`.
- **Zeilenreferenz:** 412–498.

### 4.5 `brain/think.py`

- **Inhalt:** `think_phase(state, goal, understanding, memory, llm_json_fn) -> dict`. Baut ctx_for_think, System-/User-Prompt, ruft llm_json_fn, schreibt record_decision(phase="think"), gibt plan mit _trace_id zurück.
- **Abhängigkeiten:** `constants`, `helpers` (_trace_id), `memory`, `json`. LLM wird von außen als llm_json_fn übergeben (kein direkter OpenAI-Import).
- **Zeilenreferenz:** 505–632.

### 4.6 `brain/decide.py`

- **Inhalt:** `decide_phase(plan, governance_level, memory, trace_id) -> dict`. Filtert research-init, wählt Top-Action, setzt approved je nach governance_level, ruft memory.record_decision(phase="decide").
- **Abhängigkeiten:** `constants` (GOVERNANCE_LEVELS), `memory`.
- **Zeilenreferenz:** 634–693.

### 4.7 `brain/act.py`

- **Inhalt:** `act_phase(decision, memory, base_paths, run_plumber_fn, llm_json_fn) -> dict`; plus `_act_plumber_phase(action, decision, trace_id, memory, run_plumber_fn, llm_json_fn) -> dict`. Führt workflow via subprocess (op job new / op run) oder ruft run_plumber_fn; research-init wird abgelehnt; record_episode für act/act_plumber/act_skipped.
- **Abhängigkeiten:** `constants` (BASE, WORKFLOWS, JOBS), `memory`, `subprocess`, `pathlib`, `os`. run_plumber_fn und llm_json_fn von außen (um lib.plumber und LLM gekapselt zu halten).
- **Zeilenreferenz:** 695–898.

### 4.8 `brain/reflect.py`

- **Inhalt:** `reflect_phase(action_result, goal, memory, retrieved_principle_ids, llm_json_fn) -> dict`. LLM-Reflection mit Timeout (ThreadPoolExecutor), Fallback bei Fehler/Timeout; record_reflection, record_quality, upsert_playbook, insert_principle, record_decision(phase="reflect"), update_utilities_from_outcome.
- **Abhängigkeiten:** `constants` (REFLECT_LLM_TIMEOUT_SEC), `helpers` (_reflection_is_low_signal, _trace_id), `memory`, `json`, `concurrent.futures`. LLM via llm_json_fn.
- **Zeilenreferenz:** 903–1072.

### 4.9 `brain/run.py`

- **Inhalt:**
  - **Brain-Klasse:** `__init__(governance_level)`, Property `llm` (lazy OpenAI-Client), `_llm_reason`, `_llm_json`; Methoden `perceive()` → ruft perceive_phase(self.memory, self.governance_level); `understand(state, goal)` → understand_phase(...); `think(state, goal, understanding)` → think_phase(..., self._llm_json); `decide(plan, retrieved_memory_ids)` → decide_phase(...); `act(decision)` → act_phase(..., run_plumber_fn=_plumber.run_plumber, llm_json_fn=self._llm_json); `reflect(...)` → reflect_phase(..., self._llm_json); `run_cycle(goal)`; `reflect_on_job(job_dir, goal)`; `close()`, `__enter__`, `__exit__`.
- **Abhängigkeiten:** alle anderen brain-Module + `lib.memory`, `lib.brain_context`, `lib.plumber` (als _plumber).
- **Zeilenreferenz:** 126–145 (init/llm), 1074–1145 (run_cycle, reflect_on_job, close, enter, exit).

### 4.10 `brain/__init__.py`

- **Re-Export:** `Brain` (aus run), `_reflection_is_low_signal`, `_compact_state_for_think` (aus helpers), optional `_trace_id`, `_utcnow` falls irgendwo genutzt.
- **Öffentlich dokumentiert für Tests:** `_reflection_is_low_signal`, `_compact_state_for_think`.

---

## 5. Abhängigkeitsrichtung (keine Zyklen)

```
constants
   ↓
helpers
   ↓
perceive, understand, think, decide, act, reflect   (parallel; keiner importiert den anderen)
   ↓
run (Brain class orchestriert alle; importiert perceive_phase, understand_phase, …)
```

- `run.py` importiert alle *_phase-Funktionen und _plumber; ruft sie mit self.memory, self.governance_level, self._llm_json etc. auf.
- Kein Modul importiert `run` außer `__init__.py`.

---

## 6. Implementierungsschritte

1. **Verzeichnis anlegen:** `lib/brain/` erstellen.
2. **constants.py:** BASE, CONF, JOBS, WORKFLOWS, KNOWLEDGE, FACTORY, RESEARCH, GOVERNANCE_LEVELS, REFLECT_LLM_TIMEOUT_SEC, _REFLECTION_* aus brain.py extrahieren.
3. **helpers.py:** _utcnow, _trace_id, _load_secrets, _reflection_is_low_signal, _compact_state_for_think; Import constants/conf.
4. **perceive.py:** perceive_phase(memory, governance_level) aus perceive()-Body; Import constants, helpers, brain_context, memory.
5. **understand.py:** understand_phase(state, goal, memory) aus understand()-Body.
6. **think.py:** think_phase(state, goal, understanding, memory, llm_json_fn) aus think()-Body.
7. **decide.py:** decide_phase(plan, governance_level, memory) aus decide()-Body (trace_id aus plan oder helpers._trace_id).
8. **act.py:** act_phase und _act_plumber_phase; run_plumber_fn und llm_json_fn als Parameter (kein direkter _plumber-Import in act.py, wird in run.py übergeben).
9. **reflect.py:** reflect_phase(action_result, goal, memory, retrieved_principle_ids, llm_json_fn).
10. **run.py:** Brain-Klasse mit __init__, llm, _llm_reason, _llm_json; perceive/understand/think/decide/act/reflect als Wrapper um *_phase; run_cycle, reflect_on_job, close, __enter__, __exit__. Import _plumber nur in run.py.
11. **__init__.py:** Re-Export Brain, _reflection_is_low_signal, _compact_state_for_think.
12. **Alte Datei ersetzen:** `lib/brain.py` löschen (oder durch Redirect ersetzen: nur `from lib.brain.run import Brain` etc. – dann bleibt eine Datei brain.py die aus dem Paket lädt). **Wichtig:** In Python hat das Paket `lib/brain/` Vorrang vor einer Datei `lib/brain.py`. Also: `lib/brain.py` entfernen, Aufrufer nutzen weiter `from lib.brain import Brain` (lädt lib/brain/__init__.py).
13. **Backup:** `lib/brain.py.bak` vor dem Löschen anlegen.
14. **Tests:** `pytest tests/unit/test_brain_helpers.py -v`; `bin/brain perceive` (oder think --goal "test"); optional ein run_cycle mit governance 0.
15. **Doku:** `docs/MONOLITH_AND_LARGE_FILES.md` — Eintrag brain auf „Refaktoriert (Paket)“ setzen, Link auf diesen Plan.

---

## 7. Verifikation

| Check | Aktion |
|-------|--------|
| Import | `from lib.brain import Brain, _reflection_is_low_signal, _compact_state_for_think` funktioniert. |
| Tests | `pytest tests/unit/test_brain_helpers.py -v` — alle grün. |
| CLI perceive | `bin/brain perceive` liefert JSON-State. |
| CLI think | `bin/brain think --goal "Analyze system"` liefert JSON-Plan. |
| CLI cycle | `bin/brain cycle --governance 0` (report-only) einmal durchlaufen. |
| Planner | `workflows/planner.sh` ruft weiter `$BRAIN think --goal "..."` auf (bin/brain). |

---

## 8. Kurzreferenz: Funktion/Methode → Modul

| Symbol | Modul |
|--------|--------|
| BASE, CONF, JOBS, … GOVERNANCE_LEVELS, REFLECT_LLM_TIMEOUT_SEC, _REFLECTION_* | constants |
| _utcnow, _trace_id, _load_secrets, _reflection_is_low_signal, _compact_state_for_think | helpers |
| perceive_phase | perceive |
| understand_phase | understand |
| think_phase | think |
| decide_phase | decide |
| act_phase, _act_plumber_phase | act |
| reflect_phase | reflect |
| Brain, run_cycle, reflect_on_job | run |
| Re-Export für Aufrufer/Tests | __init__.py |
