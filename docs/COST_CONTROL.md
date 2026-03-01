# 100 % Kostenkontrolle im Operator

Das Research-System ist so gebaut, dass **alle API- und LLM-Kosten** einem Projekt oder einem System-Job zugeordnet und begrenzt werden können. Kein Token und keine externe API-Nutzung soll unkontrolliert anfallen.

---

## Garantien

1. **Jeder Research-Projekt-Run** hat ein **Budget-Limit** (Standard z. B. in `project.json` → `config.budget_limit`). Vor kritischen Phasen wird `research_budget.check(project_id)` aufgerufen; bei Überschreitung kann die Pipeline stoppen oder begrenzt weiterlaufen (je nach Konfiguration).
2. **Alle LLM-Aufrufe** im Research-Pfad laufen über `research_common.llm_call(model, system, user, project_id=...)`. Nur wenn `project_id` gesetzt ist, wird getrackt; in der Praxis ist in allen Research-Tools eine Projekt-ID gesetzt.
3. **Token-Kosten** werden mit `research_budget.track_usage(project_id, model, input_tokens, output_tokens)` in `project.json` unter `current_spend` und `spend_breakdown` (pro Modell) persistiert.
4. **Externe APIs** (Suche, Reader, etc.) werden über `track_api_call(project_id, api_name, count)` gebucht.
5. **Sub-Agent-Kosten** werden nach Abschluss des Sub-Agent-Jobs auf das **Parent-Projekt** umgelegt (Roll-up in `research_experiment.spawn_subagent`). Das Budget eines Haupt-Projekts enthält damit auch die Kosten aller von ihm gespawnten Sub-Agenten.
6. **System-Jobs** (z. B. nächtliche Konsolidierung, Auto-Prompt-Optimierung) buchen auf ein festes System-Projekt (z. B. `proj-sys-consolidate`), damit die Kosten sichtbar und nicht „unsichtbar“ sind.

---

## Wo du die Kosten siehst

| Ort | Inhalt |
|-----|--------|
| **Research-Projekt-Detail (UI)** | **Budget:** `current_spend` / `budget_limit`; Tooltip mit `spend_breakdown` (pro Modell/API). Enthält auch Sub-Agent-Roll-up. |
| **Projekt-Datei** | `research/proj-…/project.json` → `current_spend`, `spend_breakdown` |
| **System-Konsolidierung** | Kosten der Auto-Prompt-Optimierung in `research/proj-sys-consolidate/` (falls angelegt) |
| **CLI** | `python3 tools/research_budget.py check <project_id>` → ok, current_spend, budget_limit |

---

## Abdeckung (was getrackt wird)

- **LLM (OpenAI/Gemini):** Planner, Conductor, Verify, Synthesize, Critic, Entity/Deep Extract, Relevance Gate, Discovery Analysis, Experiment-Loop, Context Manager, Dynamic Outline, Experience Distiller, etc. – alle über `llm_call(..., project_id=...)`.
- **Embeddings:** Synthesize (semantische Sortierung) und Embed (Findings in Memory) buchen auf das jeweilige Projekt (`embedding` / `text-embedding-3-small` in `spend_breakdown`).
- **APIs:** Brave/Serper, Jina Reader etc. über `track_api_call`.
- **Sub-Agenten:** Vollständiger Roll-up von `current_spend` und `spend_breakdown` ins Parent-Projekt.
- **Konsolidierung / Auto-Prompt:** Alle LLM-Calls mit `project_id=proj-sys-consolidate`.

Damit hast du **100 % Kontrolle** über Research-Kosten: alles ist einem Projekt oder einem System-Projekt zugeordnet, sichtbar in der UI und in den Projektdateien, und durch Budget-Checks begrenzbar.

**Außerhalb des Research-Budgets (nicht pro Projekt getrackt):** Brain-Reflection-LLM-Aufrufe (nach Job-Ende) und Memory-Embeddings für die semantische Suche im Brain laufen ohne Projekt-Kontext; sie zählen nicht zum Research-Budget. Optional können sie später einem System-Projekt (z. B. `proj-sys-brain`) zugeordnet werden, um auch diese Kosten sichtbar zu machen.
