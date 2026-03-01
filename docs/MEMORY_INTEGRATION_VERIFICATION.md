# Memory-System: Verbindungs-Check (Integration Verification)

**Frage:** Ist jeder Teil mit jedem anderen verbunden und korrekt eingesetzt? (SOTA/Novel, alles greift ineinander.)

**Kurzantwort:** **Ja.** Der Memory-Graph wird geschrieben **und** gelesen: `get_episode_ids_for_strategy` liest die Kanten; `_strategy_episodes_for_causal` (und damit Causal-Signal in der Strategy-Auswahl) nutzt den Graph zuerst, Fallback auf `strategy_profile_id` wenn keine Kanten da sind.

---

## 1. Research-Pipeline ↔ Memory

| Verbindung | Wo | Status |
|------------|-----|--------|
| **Prior Knowledge (Read)** | `research_knowledge_seed.py` ruft `retrieve_with_utility(question, "principle", k=5)` und `retrieve_with_utility(question, "finding", k=10)`; schreibt `prior_knowledge.json` inkl. `principle_ids`, `finding_ids`. | ✅ Verbunden |
| **record_retrieval** | In `retrieve_with_utility` werden für jede **ausgewählte** Memory (Top-k) `record_retrieval(memory_type, id, context_key)` aufgerufen. Knowledge_seed nutzt retrieve_with_utility → Retrievals werden gezählt. | ✅ Verbunden |
| **Utility-Update nach Run** | `research_utility_update.py` (aus research-cycle.sh nach Projekt-Ende): liest `prior_knowledge.json` (principle_ids, finding_ids), `project.json` (critic_score), ruft `update_utilities_from_outcome("principle", principle_ids, critic_score)` und `update_utilities_from_outcome("finding", finding_ids, critic_score)`. | ✅ Verbunden |
| **Strategy-Auswahl** | `research_planner.py` ruft `mem.select_strategy(question, domain=domain)` auf; schreibt `memory_strategy.json` inkl. `strategy_profile_id`. | ✅ Verbunden |
| **Strategy-Update aus Outcome** | `research_utility_update.py` ruft `mem.update_strategy_from_outcome(strategy_profile_id, ...)` (Pass/Fail, evidence_gate, claim_support_rate). | ✅ Verbunden |
| **Run-Episode schreiben** | research-cycle.sh (Python-Block): ruft `mem.record_run_episode(..., strategy_profile_id=..., what_helped=..., what_hurt=..., ...)`. Episode enthält die genutzte Strategy und Outcomes. | ✅ Verbunden |
| **read_urls** | research-cycle.sh: `mem.record_read_urls(question, read_urls_list)` nach Reads; `skip_urls = mem.get_read_urls_for_question(question)` zum Filtern. | ✅ Verbunden |

→ **Research nutzt Memory vollständig:** Abruf (Two-Phase + Utility), Zählung (record_retrieval), Lernen (update_utilities_from_outcome, update_strategy_from_outcome), Episoden (record_run_episode), read_urls (Dedup ähnlicher Fragen).

---

## 2. Brain ↔ Memory

| Verbindung | Wo | Status |
|------------|-----|--------|
| **Perceive / Context** | `brain.perceive()` baut `state["research_context"] = brain_context.compile(self.memory, query=goal)`. Bei `query` gesetzt: `compile` ruft `retrieve_with_utility` für reflection, finding, principle; baut `memory_trace` mit `principle_ids`, `finding_ids`, `reflection_ids`. | ✅ Verbunden |
| **Understand** | `brain.understand(state, goal)` liest `research_context["memory_trace"]` und übernimmt `retrieved_memory_ids` (principle_ids, finding_ids); speichert sie in `record_decision(phase="understand", metadata={"retrieved_memory_ids": ...})`. | ✅ Verbunden |
| **Think** | `brain.think(state, goal, understanding=understanding)` bekommt Understanding; übergibt `retrieved_memory_ids` an `record_decision(phase="think", metadata=...)`. | ✅ Verbunden |
| **Decide** | `brain.decide(plan, retrieved_memory_ids=understanding.get("retrieved_memory_ids"))` speichert sie in `record_decision(phase="decide", metadata=...)`. | ✅ Verbunden |
| **Episodes** | `record_episode("cycle_start", ...)` und `record_episode("cycle_complete", ...)` mit cycle_result. | ✅ Verbunden |

→ **Brain nutzt Memory durchgängig:** Utility-Retrieval im Context, Explainability (retrieved_memory_ids) in understand/think/decide, Episodes für Trace.

---

## 3. Konsolidierung ↔ Memory

| Verbindung | Wo | Status |
|------------|-----|--------|
| **Empirische Strategy** | `tools/memory_consolidate.py` ruft `mem.upsert_empirical_strategy(domain, min_samples)` pro Domain. Schreibt in Tabelle `strategy_profiles` (Name z.B. "empirical-{domain}"). | ✅ Verbunden |
| **Principle-Synthese** | `memory_consolidate.py` ruft `mem.synthesize_principles_from_episodes(domain, min_count)`. Schreibt in `strategic_principles`. | ✅ Verbunden |
| **Nutzung im Run** | `select_strategy` (in research_planner) liest aus `strategy_profiles` inkl. der von upsert_empirical_strategy erzeugten Profile; Similarity nutzt `_similar_episode_signals` (run_episodes). Neue empirische Profiles und Principles fließen so in die nächsten Runs. | ✅ Verbunden |
| **CLI** | `brain memory-consolidate` ruft `tools/memory_consolidate.py` auf (Cron-fähig). | ✅ Verbunden |

→ **Konsolidierung schreibt ins gleiche Schema (strategy_profiles, strategic_principles); Select und Similarity lesen daraus.** Kein getrennter „Konsolidierungs-Speicher“ – alles ein System.

---

## 4. Graph-Kanten (in Nutzung)

| Verbindung | Wo | Status |
|------------|-----|--------|
| **Schreiben** | `record_run_episode` ruft bei `strategy_profile_id` gesetzt `record_graph_edge("used_in", "strategy_profile", strategy_profile_id, "run_episode", episode_id, project_id)`. | ✅ Verbunden |
| **Lesen** | `get_episode_ids_for_strategy(strategy_profile_id, domain?, limit)` liest aus `memory_graph_edges` (used_in strategy→episode), optional mit Domain-Filter über Join mit `run_episodes`. | ✅ Verbunden |
| **Nutzung** | `_strategy_episodes_for_causal` nutzt zuerst `get_episode_ids_for_strategy` (Graph); wenn Kanten da sind, werden Episoden darüber geladen. Fallback: `run_episodes WHERE strategy_profile_id=?` wenn der Graph noch leer ist. Causal-Signal und Strategy-Auswahl laufen damit über den Graph. | ✅ Verbunden |

→ **Graph wird genutzt:** Strategy → Episoden-Verknüpfung kommt aus dem Graph; Causal-Score und what_helped/what_hurt nutzen diese Episoden.

---

## 5. Übersicht: Datenfluss (alles ineinandergreifend)

```
Research Run:
  knowledge_seed     → retrieve_with_utility → prior_knowledge.json (ids)
                    → record_retrieval (in retrieve_with_utility für Top-k)
  research_planner   → select_strategy (run_episodes + strategy_profiles) → memory_strategy.json
  research-cycle     → record_run_episode (strategy_profile_id, what_helped, …) → run_episodes + graph edge
  research-cycle     → record_read_urls / get_read_urls_for_question
  research_utility_update → update_utilities_from_outcome(principle_ids, finding_ids, critic_score)
                         → update_strategy_from_outcome(strategy_profile_id, …)

Brain Cycle:
  perceive           → brain_context.compile(memory, query=goal) → retrieve_with_utility → state["research_context"] + memory_trace
  understand         → memory_trace → retrieved_memory_ids → record_decision(understand)
  think / decide     → retrieved_memory_ids → record_decision(think/decide, metadata)
  record_episode     → cycle_start, cycle_complete

Offline:
  memory_consolidate → upsert_empirical_strategy, synthesize_principles_from_episodes
                     → strategy_profiles, strategic_principles (werden von select_strategy / list_principles genutzt)
```

---

## Fazit

- **Ja:** Die Teile sind **miteinander verbunden und korrekt eingesetzt**. Research schreibt und liest Memory; Brain nutzt Utility-Retrieval und Explainability; Konsolidierung speist dieselben Tabellen, aus denen Select und Retrieval lesen. SOTA-Bausteine (Two-Phase, Utility aus Outcome, Understand vor Act, Episoden, read_urls) sind im Datenfluss aktiv.
- Der **Memory-Graph** wird in der Strategy-Logik genutzt: Episoden für Causal-Signal kommen bevorzugt aus dem Graph (`get_episode_ids_for_strategy`), Fallback auf `strategy_profile_id`-Spalte.

**Boundaries of knowledge:** Das System ist SOTA + eine Novel-Erweiterung (read_urls semantisch); die Grenzen des Wissens sind in dem Sinne „gebogen“, dass wir episodisches Gedächtnis, value-aware Retrieval und Verstehen-vor-Handeln architektonisch umsetzen. Ob es „unfassbar intelligent“ wirkt, hängt von Daten, Runs und Konsolidierung ab – die **Verdrahtung** dafür ist vorhanden und konsistent.
