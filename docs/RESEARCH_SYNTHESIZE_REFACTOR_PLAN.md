# Refactoring-Plan: tools/research_synthesize.py

**Ziel:** Die ~1474 Zeilen und 48+ Funktionen umfassende Synthese-Pipeline in ein Paket mit klaren Modulen aufteilen, **ohne die öffentliche API zu ändern**. Alle Aufrufer (CLI, Conductor, Workflow, Tests) funktionieren weiter mit `tools/research_synthesize.py` als Einstieg und `from tools.research_synthesize import ...`.

---

## 1. Ausgangslage

| Aspekt | Aktuell |
|--------|--------|
| **Datei** | `tools/research_synthesize.py` (~1474 Zeilen, 48+ Funktionen, 1 Klasse) |
| **Rolle** | Komplette Synthese-Pipeline: Outline, Sections, Claim-Registry, Provenance, Gap-Detection, Epistemic Reflect, Executive Summary, Research Situation Map, Tipping Conditions, Scenario Matrix, Conclusions/Next Steps, Factuality Guard, Contract-Validation, Checkpoints |
| **Aufrufer** | `workflows/research/phases/synthesize.sh` (python3 research_synthesize.py), `tools/research_conductor.py` (run_tool("research_synthesize.py", ...)), `tests/tools/test_research_synthesize_*.py`, `tests/integration/test_aem_adversarial.py` (validate_synthesis_contract, SynthesisContractError) |

**Öffentliche API (muss erhalten bleiben):**

- `run_synthesis(project_id: str) -> str` — Haupteinstieg
- `main()` — CLI
- `validate_synthesis_contract(report, claim_ledger, mode) -> dict`
- `SynthesisContractError` — Exception
- `normalize_to_strings(value) -> list[str]` — Tests/Normalisierung
- `extract_claim_refs_from_report(report) -> list[str]` — Tests/Contract
- `_build_provenance_appendix`, `_build_claim_source_registry` — von test_research_synthesize_normalize.py genutzt

**Einstieg als Skript:** `python3 tools/research_synthesize.py <project_id>` muss unverändert funktionieren (Workflow, Conductor).

---

## 2. Prinzipien

1. **Einstiegsdatei bleibt:** `tools/research_synthesize.py` bleibt als schlanke Datei (~30–50 Zeilen) erhalten: Pfad-Setup, Re-Export der öffentlichen API aus dem neuen Paket, `if __name__ == "__main__": main()`. So bleiben alle Aufrufe (Skriptname, `run_tool("research_synthesize.py", ...)`) gültig.
2. **Paket unter anderem Namen:** Da `import tools.research_synthesize` die Datei laden würde, kommt die Logik in ein Paket mit anderem Namen, z. B. **`tools/synthesis/`**. `research_synthesize.py` importiert aus `tools.synthesis` und re-exportiert.
3. **Keine Logik-Änderung:** Nur Verschieben; gleiche Signaturen, gleiche Rückgaben. Keine neuen Features.
4. **Klare Modul-Grenzen:** Jedes Modul hat eine definierte Verantwortung; Abhängigkeiten laufen in eine Richtung (constants → data → outline/ledger → sections → run; contract eigenständig mit Zugriff auf ledger-Helfer).

---

## 3. Zielstruktur

```
tools/
  research_synthesize.py     # Schlanker Einstieg: path, Re-Export, main()
  synthesis/
    __init__.py               # Re-Export run_synthesis, main, validate_synthesis_contract,
                              # SynthesisContractError, normalize_to_strings, extract_claim_refs_from_report,
                              # _build_provenance_appendix, _build_claim_source_registry (für Tests)
    constants.py              # MAX_FINDINGS, EXCERPT_CHARS, SOURCE_CONTENT_CHARS, SECTION_WORDS_*,
                              # SYNTHESIZE_CHECKPOINT, _model()
    data.py                   # Laden & Sortierung: _load_findings, _load_sources, _load_source_content,
                              # _relevance_score, _embed_texts, _semantic_relevance_sort
    outline.py                # _cluster_findings, _outline_sections
    ledger.py                 # _flatten_to_strings, normalize_to_strings, _build_claim_source_registry,
                              # _build_provenance_appendix, _ensure_source_finding_ids, _build_ref_map,
                              # _claim_ledger_block
    sections.py               # _extract_section_key_points, _extract_used_claim_refs,
                              # _epistemic_profile_from_ledger, _epistemic_reflect, _synthesize_section,
                              # _detect_gaps
    blocks.py                 # Alle „Block“-Synthesen + Text-Utils: _synthesize_research_situation_map,
                              # _synthesize_decision_matrix, _synthesize_tipping_conditions,
                              # _synthesize_scenario_matrix, _synthesize_exec_summary,
                              # _synthesize_conclusions_next_steps, _evidence_summary_line, _key_numbers,
                              # _normalize_sentence, _sentence_overlap, _deduplicate_sections
    contract.py               # _normalize_ref, extract_claim_refs_from_report, _build_valid_claim_ref_set,
                              # _sentence_contains_valid_claim_ref, _factuality_guard, _normalize_for_match,
                              # _is_claim_like_sentence, _sentence_overlaps_claim, validate_synthesis_contract,
                              # SynthesisContractError
    checkpoint.py             # _load_checkpoint, _save_checkpoint, _clear_checkpoint
    run.py                    # run_synthesis (Orchestrierung; ruft data, outline, ledger, sections, blocks,
                              # contract, checkpoint auf)
```

---

## 4. Modul-Inhalte und Abhängigkeiten

### 4.1 `synthesis/constants.py`

- **Inhalt:** `MAX_FINDINGS`, `EXCERPT_CHARS`, `SOURCE_CONTENT_CHARS`, `SECTION_WORDS_MIN`, `SECTION_WORDS_MAX`, `SYNTHESIZE_CHECKPOINT`, `_model()` (ruft `model_for_lane("synthesize")` aus research_common).
- **Abhängigkeiten:** `tools.research_common.model_for_lane`.
- **Zeilenreferenz (aktuell):** ca. 20–28, 853.

### 4.2 `synthesis/data.py`

- **Inhalt:** `_load_findings`, `_load_sources`, `_load_source_content`, `_relevance_score`, `_embed_texts`, `_semantic_relevance_sort`.
- **Abhängigkeiten:** `constants` (MAX_FINDINGS, SOURCE_CONTENT_CHARS, _model), `tools.research_common` (llm_call, load_secrets), `pathlib`, `json`, `os`, `re`.
- **Zeilenreferenz:** ca. 30–131, 145–184.

### 4.3 `synthesis/outline.py`

- **Inhalt:** `_cluster_findings`, `_outline_sections`.
- **Abhängigkeiten:** `constants` (_model), `tools.research_common.llm_call`, `data` nur indirekt über run (run lädt findings und übergibt); outline bekommt findings/question/project_id von run. Kein direkter data-Import nötig, wenn run die Aufrufe macht.
- **Zeilenreferenz:** ca. 159–218.

### 4.4 `synthesis/ledger.py`

- **Inhalt:** `_flatten_to_strings`, `normalize_to_strings`, `_build_claim_source_registry`, `_build_provenance_appendix`, `_ensure_source_finding_ids`, `_build_ref_map`, `_claim_ledger_block`.
- **Abhängigkeiten:** `constants` (keine speziellen), `pathlib`, `json`. Kein LLM.
- **Zeilenreferenz:** ca. 220–375.

### 4.5 `synthesis/sections.py`

- **Inhalt:** `_extract_section_key_points`, `_extract_used_claim_refs`, `_epistemic_profile_from_ledger`, `_epistemic_reflect`, `_synthesize_section`, `_detect_gaps`.
- **Abhängigkeiten:** `constants` (_model, EXCERPT_CHARS, SOURCE_CONTENT_CHARS), `tools.research_common` (llm_call, get_optimized_system_prompt), `ledger` (_claim_ledger_block, normalize_to_strings), `data` (_load_source_content). Optional: data nur für _load_source_content — entweder in sections importieren oder _load_source_content nach data.py und von sections importieren.
- **Zeilenreferenz:** ca. 336–606.

### 4.6 `synthesis/blocks.py`

- **Inhalt:** `_synthesize_research_situation_map`, `_synthesize_decision_matrix`, `_synthesize_tipping_conditions`, `_synthesize_scenario_matrix`, `_synthesize_exec_summary`, `_synthesize_conclusions_next_steps`, `_evidence_summary_line`, `_key_numbers`, `_normalize_sentence`, `_sentence_overlap`, `_deduplicate_sections`.
- **Abhängigkeiten:** `constants` (_model), `tools.research_common` (llm_call), `ledger` (normalize_to_strings).
- **Zeilenreferenz:** ca. 608–828, 725–740, 763–827.

### 4.7 `synthesis/contract.py`

- **Inhalt:** `_normalize_ref`, `extract_claim_refs_from_report`, `_build_valid_claim_ref_set`, `_sentence_contains_valid_claim_ref`, `_factuality_guard`, `_normalize_for_match`, `_is_claim_like_sentence`, `_sentence_overlaps_claim`, `validate_synthesis_contract`, `SynthesisContractError`.
- **Abhängigkeiten:** `ledger` (normalize_to_strings), `constants` (_model für _factuality_guard falls LLM genutzt — aktuell _factuality_guard nutzt kein _model direkt; prüfen). Sonst nur `re`, `json`.
- **Zeilenreferenz:** ca. 859–1048.

### 4.8 `synthesis/checkpoint.py`

- **Inhalt:** `_load_checkpoint`, `_save_checkpoint`, `_clear_checkpoint`.
- **Abhängigkeiten:** `constants` (SYNTHESIZE_CHECKPOINT), `pathlib`, `json`.
- **Zeilenreferenz:** ca. 1054–1076.

### 4.9 `synthesis/run.py`

- **Inhalt:** `run_synthesis(project_id: str) -> str`. Lädt Projekt, findings, sources, claim_ledger; ruft data, outline, ledger, sections, blocks, contract, checkpoint in der bestehenden Reihenfolge auf; baut report_body; schreibt synthesis_contract_status.json; wirft SynthesisContractError bei Verletzung in enforce/strict.
- **Abhängigkeiten:** alle anderen synthesis-Module + `tools.research_common` (project_dir, load_project, get_claims_for_synthesis), `tools.research_progress` (step, optional).
- **Zeilenreferenz:** 1079–1452.

### 4.10 `synthesis/__init__.py`

- Re-Export: `run_synthesis`, `main`, `validate_synthesis_contract`, `SynthesisContractError`, `normalize_to_strings`, `extract_claim_refs_from_report`, `_build_provenance_appendix`, `_build_claim_source_registry` (und ggf. `_build_valid_claim_ref_set` falls Tests das brauchen). `main()` implementiert in run.py oder hier; aktuell main() in Zeile 1454–1474: path, ensure_tool_context, argv-Check, run_synthesis, print. `main` kann in run.py leben und hier re-exportiert werden.

### 4.11 `tools/research_synthesize.py` (Einstiegsdatei)

- **Inhalt:** `sys.path.insert`, optional `ensure_tool_context("research_synthesize.py")`, dann:
  - `from tools.synthesis import run_synthesis, main, validate_synthesis_contract, SynthesisContractError, normalize_to_strings, extract_claim_refs_from_report, _build_provenance_appendix, _build_claim_source_registry`
  - `if __name__ == "__main__": main()`
- So bleiben `from tools.research_synthesize import run_synthesis` und alle anderen Imports unverändert.

---

## 5. Abhängigkeitsrichtung (keine Zyklen)

```
constants
   ↓
data, ledger, checkpoint
   ↓
outline (braucht _model, llm_call; keine data)
sections (braucht ledger, data._load_source_content, constants)
blocks   (braucht ledger, constants)
contract (braucht ledger)
   ↓
run (orchestriert data, outline, ledger, sections, blocks, contract, checkpoint)
```

- `sections` kann `data` importieren für `_load_source_content` (oder `_load_source_content` wird in run aufgerufen und Ergebnis an sections übergeben — aktuell wird _load_source_content nur in _synthesize_section verwendet, also sections → data ist ok).
- `run` importiert alle und ruft die Funktionen in der richtigen Reihenfolge auf.

---

## 6. Implementierungsschritte

1. **Verzeichnis anlegen:** `tools/synthesis/` erstellen.
2. **constants.py:** Konstanten + `_model()` aus research_synthesize.py extrahieren.
3. **data.py:** Daten-Lade- und Sortierfunktionen; Import von constants und research_common.
4. **ledger.py:** Alle Ledger-/Ref-Helfer; keine LLM-Abhängigkeit.
5. **outline.py:** _cluster_findings, _outline_sections; Import constants, research_common.
6. **checkpoint.py:** Checkpoint-Laden/Speichern/Löschen; Import constants.
7. **sections.py:** Section-Synthese + Epistemic/Gaps; Import constants, data (_load_source_content), ledger, research_common.
8. **blocks.py:** Alle Block-Synthesen + _deduplicate_sections, _normalize_sentence, _sentence_overlap; Import constants, ledger, research_common.
9. **contract.py:** Factuality + Contract-Validierung + SynthesisContractError; Import ledger.
10. **run.py:** `run_synthesis` und `main` aus der Monolith-Datei übernehmen; alle Aufrufe auf die neuen Module umstellen.
11. **synthesis/__init__.py:** Re-Export der öffentlichen API (run_synthesis, main, validate_synthesis_contract, SynthesisContractError, normalize_to_strings, extract_claim_refs_from_report, _build_provenance_appendix, _build_claim_source_registry).
12. **research_synthesize.py ersetzen:** Inhalt durch schlanken Einstieg ersetzen (path, Re-Import aus tools.synthesis, `if __name__ == "__main__": main()`).
13. **Tests ausführen:**  
    - `pytest tests/tools/test_research_synthesize_normalize.py tests/tools/test_research_synthesize_contract.py -v`  
    - `pytest tests/integration/test_aem_adversarial.py -v` (validate_synthesis_contract, SynthesisContractError)  
    - Optional: End-to-End mit echtem Projekt (synthesize-Phase einmal laufen lassen).
14. **Alte Datei sichern:** `tools/research_synthesize.py.bak` vor dem Ersetzen anlegen.
15. **Doku aktualisieren:** `docs/MONOLITH_AND_LARGE_FILES.md` — Eintrag zu research_synthesize auf „Refaktoriert (Paket tools/synthesis)“ setzen, Struktur und Link auf diesen Plan.

---

## 7. Verifikation

| Check | Aktion |
|-------|--------|
| CLI | `python3 tools/research_synthesize.py <project_id>` liefert Report auf stdout (oder Fehler mit Exitcode 2 bei fehlendem Arg). |
| Import | `from tools.research_synthesize import run_synthesis, validate_synthesis_contract, SynthesisContractError, normalize_to_strings, extract_claim_refs_from_report` funktioniert. |
| Tests Normalize | `pytest tests/tools/test_research_synthesize_normalize.py -v` — alle grün. |
| Tests Contract | `pytest tests/tools/test_research_synthesize_contract.py -v` — alle grün. |
| AEM Integration | `pytest tests/integration/test_aem_adversarial.py -v` — alle grün. |
| Conductor | `run_tool("research_synthesize.py", project_id, ...)` (in research_conductor.py) läuft ohne Änderung. |
| Workflow | `synthesize.sh` ruft weiter `python3 "$TOOLS/research_synthesize.py" "$PROJECT_ID"` auf. |

---

## 8. Kurzreferenz: Funktion → Modul

| Funktion / Klasse | Modul |
|-------------------|--------|
| _model | constants |
| _relevance_score, _embed_texts, _semantic_relevance_sort | data |
| _load_findings, _load_sources, _load_source_content | data |
| _cluster_findings, _outline_sections | outline |
| _flatten_to_strings, normalize_to_strings | ledger |
| _build_claim_source_registry, _build_provenance_appendix | ledger |
| _ensure_source_finding_ids, _build_ref_map, _claim_ledger_block | ledger |
| _extract_section_key_points, _extract_used_claim_refs | sections |
| _epistemic_profile_from_ledger, _epistemic_reflect | sections |
| _synthesize_section, _detect_gaps | sections |
| _synthesize_research_situation_map, _synthesize_decision_matrix, _synthesize_tipping_conditions, _synthesize_scenario_matrix | blocks |
| _synthesize_exec_summary, _synthesize_conclusions_next_steps | blocks |
| _evidence_summary_line, _key_numbers | blocks |
| _normalize_sentence, _sentence_overlap, _deduplicate_sections | blocks |
| _normalize_ref, extract_claim_refs_from_report, _build_valid_claim_ref_set | contract |
| _sentence_contains_valid_claim_ref, _factuality_guard, _normalize_for_match, _is_claim_like_sentence, _sentence_overlaps_claim | contract |
| validate_synthesis_contract, SynthesisContractError | contract |
| _load_checkpoint, _save_checkpoint, _clear_checkpoint | checkpoint |
| run_synthesis, main | run |
