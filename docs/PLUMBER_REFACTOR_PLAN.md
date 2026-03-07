# Refactoring-Plan: lib/plumber.py

**Ziel:** Den ~1932 Zeilen starken Self-Healing-Monolithen in ein Paket `lib/plumber/` mit klaren Modulen aufteilen, **ohne die öffentliche API zu ändern**. Alle bestehenden Aufrufer (`lib.brain`, `bin/brain`, Tests) funktionieren weiter mit `from lib.plumber import ...`.

---

## 1. Ausgangslage

| Aspekt | Aktuell |
|--------|--------|
| **Datei** | `lib/plumber.py` (~1932 Zeilen, 36+ Funktionen/Klassen) |
| **Rolle** | Self-Healing: 7 Diagnose-Kategorien, Fixes (Shell, Dependencies, LLM), Fingerprints, Cooldown, Rollback, Patch-Metriken |
| **Aufrufer** | `lib/brain.py` (`_plumber.run_plumber`), `bin/brain` (`run_plumber`, `rollback_patch`, `list_patches`, `get_fingerprint_stats`, `_load_fingerprints`), `tests/unit/test_plumber.py` (`classify_non_repairable`) |

**Öffentliche API (muss erhalten bleiben):**

- `run_plumber(...)` — Haupteinstieg
- `rollback_patch(patch_path)`, `list_patches()` — Rollback / Auflistung
- `get_fingerprint_stats()`, `_load_fingerprints()` — Fingerprint-Daten
- `classify_non_repairable(error_text)` — Tests

**Sicherheitsmodell (unverändert):** Nur Dateien unter `workflows/` und `tools/`; Governance-Level; Patches unter `plumber/patches/`; Fingerprint-DB und Cooldown.

---

## 2. Prinzipien

1. **Paket statt eine Datei:** `lib/plumber.py` wird zu `lib/plumber/` (Verzeichnis). `lib/plumber/__init__.py` bleibt dünner Einstieg und re-exportiert die öffentliche API, sodass `from lib.plumber import run_plumber` etc. unverändert funktioniert.
2. **Keine Logik-Änderung:** Nur Verschieben; gleiche Funktionen, gleiche Signaturen, gleiche Rückgaben. Keine neuen Features.
3. **Klare Modul-Grenzen:** Jedes Modul hat eine definierte Verantwortung; Abhängigkeiten laufen in eine Richtung (constants → fingerprints → diagnose; constants → fix → llm_fix; run orchestriert).

---

## 3. Zielstruktur

```
lib/
  plumber.py          → entfernt (ersetzt durch Paket)
  plumber/
    __init__.py       # Re-Export der öffentlichen API (~30 Zeilen)
    constants.py      # Pfade, Konstanten, NON_REPAIRABLE_PATTERNS, LLM-Flag
    fingerprints.py   # Fingerprint-DB, Cooldown, classify_non_repairable
    diagnose.py       # Alle diagnose_* + read_job_log, _extract_error, _parse_etime, _get_stdlib_modules
    fix.py            # FixResult, _is_safe_path, _save_patch, fix_shell_syntax, fix_missing_dependency,
                      # fix_repeated_failures, rollback_*, list_patches, _compute_patch_metrics
    llm_fix.py        # llm_code_fix, llm_fix_from_job_failure (inkl. LLM_FIX_* Env)
    run.py            # run_plumber (Orchestrierung aller Kategorien)
```

---

## 4. Modul-Inhalte und Abhängigkeiten

### 4.1 `plumber/constants.py`

- **Inhalt:** `BASE`, `WORKFLOWS`, `TOOLS`, `JOBS`, `LIB`, `BIN`, `UI_SRC`, `PLUMBER_DIR`, `PATCHES_DIR`, `VENV`, `ALLOWED_FIX_ROOTS`, `MAX_LOG_LINES`, `MAX_PATCH_SIZE`, `CRITICAL`/`WARNING`/`INFO`, `FINGERPRINT_DB`, `COOLDOWN_HOURS`, `MAX_FIX_ATTEMPTS_PER_FINGERPRINT`, `NON_REPAIRABLE_PATTERNS`, `LLM_FIX_ENABLED`, `LLM_FIX_MAX_DIFF_LINES`, `LLM_FIX_MAX_ATTEMPTS_PER_FILE`, `LLM_FIX_MODEL`.
- **Abhängigkeiten:** keine (nur `os`, `re`, `Path`).
- **Hinweis:** `BASE` aus `Path.home() / "operator"` wie bisher; Aufrufer setzen ggf. `OPERATOR_ROOT` — in `run.py` oder `constants` kann bei Bedarf `os.environ.get("OPERATOR_ROOT")` berücksichtigt werden, falls schon heute genutzt (im aktuellen Code ist es nur `Path.home() / "operator"`).

### 4.2 `plumber/fingerprints.py`

- **Inhalt:** `_utcnow`, `_error_fingerprint`, `_load_fingerprints`, `_save_fingerprints`, `record_fingerprint`, `is_on_cooldown`, `classify_non_repairable`, `mark_non_repairable`, `get_fingerprint_stats`.
- **Abhängigkeiten:** `constants` (FINGERPRINT_DB, PLUMBER_DIR, COOLDOWN_*, MAX_FIX_ATTEMPTS, NON_REPAIRABLE_PATTERNS).
- **Export:** Öffentlich sichtbar bleiben: `classify_non_repairable`, `get_fingerprint_stats`, `_load_fingerprints` (für bin/brain); Rest intern.

### 4.3 `plumber/diagnose.py`

- **Inhalt:** `diagnose_shell_syntax`, `diagnose_repeated_failures`, `read_job_log`, `_extract_error_from_logs`, `diagnose_python_tools`, `diagnose_dependencies`, `_get_stdlib_modules`, `diagnose_tool_references`, `diagnose_tool_contracts`, `diagnose_processes`, `_parse_etime`, `diagnose_venv`.
- **Abhängigkeiten:** `constants` (alle Pfade, MAX_LOG_LINES).
- **Hinweis:** `_get_stdlib_modules` wird auch von `fix_missing_dependency` genutzt → in `diagnose` belassen und von `fix` importieren.

### 4.4 `plumber/fix.py`

- **Inhalt:** `FixResult`, `_is_safe_path`, `_save_patch`, `fix_shell_syntax`, `_fix_block_balance`, `_fix_unterminated`, `fix_missing_dependency`, `fix_repeated_failures`, `rollback_if_still_failing`, `_compute_patch_metrics`, `rollback_patch`, `list_patches`.
- **Abhängigkeiten:** `constants`, `fingerprints` (record_fingerprint, is_on_cooldown, classify_non_repairable, mark_non_repairable), `diagnose` (diagnose_shell_syntax, read_job_log, _extract_error_from_logs, _get_stdlib_modules), `llm_fix` (llm_fix_from_job_failure — nur in fix_repeated_failures als letzter Schritt).
- **Zirkularität vermeiden:** `fix_repeated_failures` ruft `llm_fix_from_job_failure` auf. Option A: `llm_fix` importiert `fix` nur für `FixResult`/`_save_patch`/`_is_safe_path`; `fix` importiert `llm_fix` für `llm_fix_from_job_failure` → zulässig (fix → llm_fix, llm_fix → fix nur Typen/Helpers). Option B: Aufruf von `llm_fix_from_job_failure` in `run.py` belassen und `fix_repeated_failures` bekommt einen optionalen `llm_fix_callback` — dann braucht `fix` kein `llm_fix`. Empfehlung: Option A (direkter Import), da die Abhängigkeit von fix → llm_fix nur eine Funktion ist und llm_fix seinerseits fix nur für FixResult und Patch-Helfer nutzt.

### 4.5 `plumber/llm_fix.py`

- **Inhalt:** `LLM_FIX_ENABLED`, `LLM_FIX_MAX_DIFF_LINES`, `LLM_FIX_MAX_ATTEMPTS_PER_FILE`, `LLM_FIX_MODEL`, `_llm_fix_attempted`, `llm_code_fix`, `llm_fix_from_job_failure`.
- **Abhängigkeiten:** `constants`, `fix` (FixResult, _save_patch, _is_safe_path), `diagnose` (diagnose_shell_syntax, read_job_log, _extract_error_from_logs für Kontext).
- **Hinweis:** `llm_fix_from_job_failure` ruft `llm_code_fix` auf; beide bleiben in einem Modul.

### 4.6 `plumber/run.py`

- **Inhalt:** nur `run_plumber(intent, target, governance_level, llm_fn)`.
- **Abhängigkeiten:** `constants`, `fingerprints` (record_fingerprint, get_fingerprint_stats, _utcnow), `diagnose` (alle diagnose_*), `fix` (fix_shell_syntax, fix_repeated_failures, fix_missing_dependency, rollback_if_still_failing, _is_safe_path, list_patches, _compute_patch_metrics, FixResult), `llm_fix` (kein direkter Aufruf in run_plumber; LLM wird über fix_repeated_failures genutzt).

### 4.7 `lib/plumber/__init__.py`

- **Inhalt:** Re-Export der öffentlichen API, sodass `from lib.plumber import run_plumber, rollback_patch, list_patches, get_fingerprint_stats, classify_non_repairable` und ggf. `_load_fingerprints` weiter funktionieren.
- **Beispiel:**

```python
from lib.plumber.run import run_plumber
from lib.plumber.fix import rollback_patch, list_patches
from lib.plumber.fingerprints import (
    get_fingerprint_stats,
    _load_fingerprints,
    classify_non_repairable,
)

__all__ = [
    "run_plumber",
    "rollback_patch",
    "list_patches",
    "get_fingerprint_stats",
    "_load_fingerprints",
    "classify_non_repairable",
]
```

---

## 5. Schritte (Reihenfolge einhalten)

### Phase A: Vorbereitung

- **A1** Alle Imports von `lib.plumber` und `lib import plumber` dokumentieren (bereits erfasst: brain, bin/brain, tests).
- **A2** Bestehende Tests ausführen: `pytest tests/unit/test_plumber.py -v` (und ggf. Integrationstests, die Plumber ansprechen). Snapshot/Branch für Rollback.

### Phase B: Paket anlegen, keine Löschung von plumber.py

- **B1** Verzeichnis `lib/plumber/` anlegen.
- **B2** `lib/plumber/constants.py` erstellen: gesamten Konstanten-/Pfad-Block aus `plumber.py` (Zeilen 34–92 inkl. NON_REPAIRABLE_PATTERNS) übernehmen; `BASE` ggf. aus `os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator"))` ableiten, falls gewünscht (aktuell im Original nur `Path.home() / "operator"`).
- **B3** `lib/plumber/fingerprints.py` erstellen: `_utcnow`, Fingerprint-Funktionen (bis einschließlich `get_fingerprint_stats`). Imports aus `constants` nutzen. Kein Import von diagnose/fix/run.
- **B4** `lib/plumber/diagnose.py` erstellen: alle `diagnose_*`, `read_job_log`, `_extract_error_from_logs`, `_get_stdlib_modules`, `_parse_etime`. Imports aus `constants`.
- **B5** `lib/plumber/llm_fix.py` erstellen: LLM-Flag/Konstanten und `llm_code_fix`, `llm_fix_from_job_failure`. Importiert `constants`, `fix` (FixResult, _save_patch, _is_safe_path), `diagnose` (was für Kontext nötig ist). Da `fix` seinerseits `llm_fix` importiert, auf Zirkularität achten: in `fix.py` den Import von `llm_fix` nur innerhalb von `fix_repeated_failures` (lazy import) setzen, z. B. `from lib.plumber import llm_fix` erst beim Aufruf des LLM-Last-Resort-Blocks, dann ist die Kette: run → fix → (bei Bedarf) llm_fix → fix (nur FixResult/Patch) → ok.
- **B6** `lib/plumber/fix.py` erstellen: FixResult, _is_safe_path, _save_patch, alle fix_* und rollback/list_patches/_compute_patch_metrics. Importiert `constants`, `fingerprints`, `diagnose`. Für `llm_fix_from_job_failure`: lazy import am Anfang von `fix_repeated_failures` (z. B. `from lib.plumber.llm_fix import llm_fix_from_job_failure`), damit beim Laden von `fix` das Modul `llm_fix` noch nicht `fix` braucht (llm_fix wird erst bei Aufruf von fix_repeated_failures mit LLM gebraucht).
- **B7** `lib/plumber/run.py` erstellen: nur `run_plumber` aus der aktuellen Datei übernehmen; darin alle Imports aus `constants`, `fingerprints`, `diagnose`, `fix` (und ggf. nur dort `llm_fix` wenn nötig — aktuell ruft nur `fix_repeated_failures` llm_fix auf, nicht run_plumber direkt).
- **B8** `lib/plumber/__init__.py` erstellen: Re-Exports wie in 4.7.

**Noch nicht:** `lib/plumber.py` (die große Datei) bleibt vorerst unverändert; es wird nur das neue Paket daneben gebaut. Optional: temporär in `lib/plumber.py` nur `from lib.plumber import *` und `__all__` re-exportieren und testen, ob alle Aufrufer weiterlaufen.

### Phase C: Umstellung auf Paket, alte Datei entfernen

- **C1** `lib/plumber.py` (Monolith) durch einen dünnen Stub ersetzen: Inhalt nur noch Re-Export aus dem Paket, z. B. `from lib.plumber import *` und `__all__` wie in `__init__.py`. Damit bleibt `import lib.plumber` und `from lib.plumber import run_plumber` etc. erhalten (Python lädt zuerst `lib/plumber/` als Paket, wenn ein Verzeichnis `lib/plumber` existiert; **wichtig:** in Python hat ein Verzeichnis `lib/plumber/` Vorrang vor einer Datei `lib/plumber.py`). Also: **Datei `lib/plumber.py` löschen**, nur das Paket `lib/plumber/` behalten. Dann sind alle Imports bereits auf das Paket umgestellt.
- **C2** Tests erneut ausführen; einmal manuell `bin/brain plumber` (oder Äquivalent) und ggf. Brain-Logik, die `run_plumber` aufruft.

### Phase D: Doku und Aufräumen

- **D1** `docs/MONOLITH_AND_LARGE_FILES.md`: Eintrag zu `lib/plumber.py` auf „Refaktoriert (Paket lib/plumber/)“ setzen.
- **D2** In `lib/plumber/README.md` oder im Modul-Docstring kurz die Module und ihre Rolle beschreiben (optional).

---

## 6. Abhängigkeitsgraph (kurz)

```
constants
  ├── fingerprints
  ├── diagnose
  ├── fix  (→ fingerprints, diagnose; lazy → llm_fix)
  └── llm_fix (→ fix für FixResult/_save_patch/_is_safe_path, diagnose für Kontext)
run (→ constants, fingerprints, diagnose, fix)
```

Lazy-Import in `fix.py` für `llm_fix_from_job_failure`, damit beim Start keine zirkuläre Abhängigkeit fix ↔ llm_fix entsteht.

---

## 7. Verifikation

| Check | Aktion |
|-------|--------|
| Unit-Tests | `pytest tests/unit/test_plumber.py -v` |
| Brain-Import | `python3 -c "from lib import plumber; print(plumber.run_plumber)"` |
| bin/brain | `python3 bin/brain plumber --help` bzw. `--list-patches` / `--fingerprints` |
| Brain run_plumber | Einmal Brain-Lauf oder manuell `run_plumber(intent="diagnose-only")` aufrufen |

---

## 8. Rollback

- Falls nötig: Paket `lib/plumber/` umbenennen/entfernen und ursprüngliche `lib/plumber.py` aus Git/Backup wiederherstellen.

---

## 9. Kurzfassung

- **Ein** Paket `lib/plumber/` mit **6 Modulen** + `__init__.py`.
- **Öffentliche API** unverändert: `run_plumber`, `rollback_patch`, `list_patches`, `get_fingerprint_stats`, `_load_fingerprints`, `classify_non_repairable`.
- **Alte** `lib/plumber.py` wird **gelöscht** (Python nutzt dann das Paket `lib/plumber/`).
- Lazy-Import von `llm_fix` in `fix.py` vermeidet Zirkularität.
- Verhalten und Sicherheitsmodell bleiben gleich.
