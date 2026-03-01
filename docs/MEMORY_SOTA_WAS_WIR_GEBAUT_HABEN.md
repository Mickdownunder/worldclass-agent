# Was am Memory-System State-of-the-Art (SOTA) ist — Erklärung

Kurz und konkret: **Was die Forschung unter „weltklassem Memory für Agenten“ versteht** und **was wir davon bei unserem Memory umgesetzt haben**.

---

## 1. Episodisches Gedächtnis mit echtem Verlauf (SOTA-Säule 1)

**Was die Forschung will:** Nicht nur „ein Eintrag pro Projekt“, sondern **viele Episoden** mit Zeit, Domain, Outcome, was geholfen/geschadet hat. Dann: „Welche vergangenen Runs ähneln dieser Situation? Was hat in ähnlichen Fällen geholfen?“ — echtes **Reasoning über Ereignisverläufe** (REMem, Generative Agents).

**Was wir gebaut haben:**
- **Mehrere Runs pro Projekt:** `run_episodes` hat keine UNIQUE mehr auf `project_id`; jeder Run schreibt eine **neue Zeile** mit eigener `id`, `run_index` pro Projekt. Mehrere Cycles desselben Projekts = mehrere Episoden.
- **Similarity über viele Episoden:** `_similar_episode_signals` / Strategy-Auswahl nutzt **bis zu 40 vergangene Episoden** (verschiedene Runs, auch gleiches Projekt mehrfach). Ähnlichkeit über Frage/Domain; Auswertung von `what_helped` / `what_hurt` / `fail_codes`.
- **Graph-Verknüpfung:** Bei `record_run_episode` wird eine Kante **Strategy ↔ Episode** in `memory_graph_edges` geschrieben (`used_in`). Episoden sind damit explizite Knoten im Graphen (REMem/HippoRAG-Idee).

**Warum SOTA:** Typische Agenten haben nur „semantisches“ Gedächtnis (Fakten/Embeddings). Wir haben **episodisches Gedächtnis mit Verlauf** und nutzen es für „was half in ähnlichen Fällen?“ — das ist Stand der Forschung (Stanford Generative Agents, REMem).

---

## 2. Two-Phase Retrieval + Utility-Learning (SOTA-Säule 2)

**Was die Forschung will:** Abruf nicht nur nach **Ähnlichkeit** (similar), sondern in **zwei Phasen**: (1) **Recall** = Kandidaten holen (semantisch/keyword), (2) **Selection** = auswählen nach **gelerntem Nutzen** (Utility/Q). Utility wird aus echten Outcomes aktualisiert (MemRL, value-aware retrieval).

**Was wir gebaut haben:**
- **Phase 1 (Recall):** Kandidaten werden geholt mit **Hybrid aus Keyword + optional Semantic** (Principles und Findings: wenn `embedding_json` gesetzt und API-Key da, dann Cosinus-Similarität zur Query; sonst Keyword). 5× k Kandidaten.
- **Phase 2 (Selection):** Re-Rank mit  
  **combined_score = (1 − λ) · similarity + λ · utility**  
  (λ z.B. 0,6, konfigurierbar `RESEARCH_MEMORY_UTILITY_LAMBDA`). Utility kommt aus der Tabelle `memory_utility` (Laplace: helpful_count / retrieval_count).
- **Utility-Update aus Outcome:** Nach jedem Projekt-Ende ruft `research_utility_update.py` (aus research-cycle.sh) **update_utilities_from_outcome** auf: für alle in `prior_knowledge.json` genutzten Principle- und Finding-IDs wird bei critic_score ≥ 0,7 als „helpful“ gezählt, sonst nicht. Utility wird damit **aus echtem Feedback** gelernt.
- **Kontextabhängige Utility:** Es gibt `memory_utility_context` (Utility pro Frage/Kontext); bei Retrieval wird `context_key` aus der aktuellen Frage abgeleitet und genutzt, wenn vorhanden.

**Warum SOTA:** Bloß „die ähnlichsten Memories holen“ führt oft zu irrelevanten oder wenig nützlichen Treffern. **Value-aware Selection** (MemRL) nutzt, ob ein Memory in der Vergangenheit wirklich geholfen hat — genau das machen wir mit Two-Phase + Outcome-Update.

---

## 3. Reflection & Konsolidierung (SOTA-Säule 3)

**Was die Forschung will:** Aus vielen Episoden/Reflections **höherstufige Einsichten** erzeugen (Principles, bessere Strategien), nicht nur speichern. Dazu ein **offline Konsolidierungs-Prozess** (Wake–Sleep, GraphRAG): Episoden in Ruhe durchgehen, Utility/Summaries/Principles aktualisieren, ohne jeden Run zu blockieren (Generative Agents, Phasor).

**Was wir gebaut haben:**
- **Reflection-Synthese aus Episoden:** `memory_consolidate.py` (aufrufbar via **`brain memory-consolidate`**) macht:  
  - **Empirische Strategy-Profile** aus run_episodes (z.B. mittlere relevance_threshold, revise_rounds pro Domain bei Erfolg).  
  - **Synthese von Principles** aus vielen Episoden („was half / was schadete“ aggregiert, kontrastive guiding/cautionary Principles).  
  Das ist datengetrieben, nicht nur LLM-Distiller.
- **Offline-Job:** Konsolidierung läuft als eigener Befehl/Cron (z.B. nachts), nicht während eines Research-Runs. Zwei Zeitskalen: schnelle Updates pro Run (Utility, Episode) vs. langsame Konsolidierung (Strategy, Principles) — das entspricht der Theorie (Memento-II, Stabilität durch zwei Zeitskalen).

**Warum SOTA:** „Reflection“ als eigener Prozess und **Konsolidierung** als offline Batch sind zentrale Ideen von Generative Agents, GraphRAG, Wake–Sleep. Wir haben beides: Synthese aus Episoden + Cron-Job.

---

## 4. Verstehen vor Handeln (Pre-Act)

**Was die Forschung will:** Nicht sofort handeln, sondern **zuerst die Situation verstehen** (Plan/Reasoning vor Action). Pre-Act-Studien zeigen: +70 % Action Recall, +69,5 % Action Accuracy, +28 % Goal Completion gegenüber ReAct ohne globalen Plan. Entscheidend: **strukturierte Verstehens-Darstellung** aus echten Daten (kein Halluzinieren), darauf baut dann Think/Decide/Act auf.

**Was wir gebaut haben:**
- **Eigene Phase „Understand“** im Brain-Loop: **Perceive → Understand → Think → Decide → Act → Reflect.**  
  Understand bekommt nur Perceive + **abgerufene Memories** (grounded). Ausgabe: strukturiertes JSON (situation, relevant_episodes_summary, why_helped_hurt, uncertainties, options). Kein Raten — nur aus tatsächlich abgerufenen Daten.
- **Think/Decide/Act** bekommen **nur** dieses Understanding (+ State-Zusammenfassung). Es gibt **keinen Bypass**: Keine Aktion ohne vorherigen Understand-Output (im `run_cycle` fest verdrahtet).
- Bei **Unsicherheit** (z.B. keine ähnlichen Episoden) wird das im Understanding in „uncertainties“ ausgewiesen; Fallback-Strategy wird genutzt (select_strategy liefert dann None/Default).

**Warum SOTA:** Das ist genau die Pre-Act-Idee: Plan/Reasoning vor Action, Grounding durch explizites Verstehen, keine Premature Action. Unser Loop erzwingt das architektonisch.

---

## 5. Explainability (Nachvollziehbarkeit)

**Was die Forschung will:** Für jede Entscheidung sichtbar: **Welche Memory-Objekte** (Principles, Findings, Episoden) haben diese Decision beeinflusst? So kann man prüfen und ggf. begrenzen (Agent-Failure-Modes: Over-Helpfulness, Context Pollution).

**Was wir gebaut haben:**
- **retrieved_memory_ids** werden in jeder relevanten Phase gespeichert: in **Understand** (aus research_context/memory_trace), in **Think** (aus Understanding durchgereicht), in **Decide** (aus Understanding an decide() übergeben). Alle werden als `metadata.retrieved_memory_ids` in der Tabelle `decisions` abgelegt (principle_ids, finding_ids, ggf. episode_ids).
- **UI:** Im Brain-Tab (Cognitive Traces) wird bei jeder Decision angezeigt: **„Basierend auf: P:&lt;id&gt; F:&lt;id&gt; E:&lt;id&gt;“** (Principles, Findings, Episodes). So siehst du, auf welche Memories die Entscheidung gestützt wurde.

**Warum SOTA:** Traceability von Decision → Memory ist Voraussetzung für Vertrauen und Debugging; viele Agent-Systeme liefern das nicht. Wir haben es durchgängig (Understand → Think → Decide) und in der UI sichtbar.

---

## 6. Jeder Run schreibt, Utility wird aus Outcome gelernt

**Was die Forschung will:** **Read = Policy Improvement, Write = Policy Evaluation** (Memento-II / SRDP). Jeder Run muss etwas in Memory schreiben (Episode, ggf. Utility-Update); nur so kann der nächste Run „besser“ werden. Utility muss aus **Outcome** (critic_score, Pass/Fail) kommen, nicht nur aus Heuristik.

**Was wir gebaut haben:**
- **Jeder Run schreibt:** research-cycle.sh und Brain schreiben run_episodes, Reflections; bei Nutzung von Prior Knowledge wird record_retrieval aufgerufen; nach Projekt-Ende research_utility_update mit principle_ids/finding_ids aus prior_knowledge.json und critic_score → update_utilities_from_outcome. Kein „stiller“ Run ohne Memory-Write.
- **Utility = Laplace aus helpful/retrieval:** Jedes Mal, wenn ein Principle/Finding in einen Kontext geholt wird, wird record_retrieval gezählt; nach Outcome wird helpful_count erhöht (wenn critic_score ≥ 0,7). utility_score = (helpful_count+1)/(retrieval_count+2). Das ist **gelernt aus Feedback**, nicht fest verdrahtet.

**Warum SOTA:** Das ist die Kernbedingung für Konvergenz in der Theorie (SRDP): Read/Write und zwei Zeitskalen. Wir erfüllen „jeder Run schreibt“ und „Utility aus Outcome“.

---

## Kurz-Tabelle: SOTA-Idee → Was wir umgesetzt haben

| SOTA-Idee (Forschung) | Was wir konkret gebaut haben |
|------------------------|------------------------------|
| **Episodisches Gedächtnis mit Verlauf** | run_episodes: mehrere Zeilen pro Projekt (run_index), Similarity über ~40 Episoden, Graph-Kante Episode↔Strategy |
| **Two-Phase Retrieval** | Phase 1: Recall (keyword + optional semantic/embedding); Phase 2: Re-Rank mit (1−λ)·similarity + λ·utility |
| **Utility aus Outcome** | record_retrieval bei Abruf; update_utilities_from_outcome nach Projekt-Ende (research_utility_update.py); memory_utility + memory_utility_context |
| **Reflection & Synthese** | memory_consolidate: empirische Strategy-Profile, Principle-Synthese aus Episoden; brain memory-consolidate |
| **Offline-Konsolidierung** | Cron-fähiger Job (brain memory-consolidate), zwei Zeitskalen (Run vs. Konsolidierung) |
| **Graph (Kanten)** | memory_graph_edges, record_graph_edge bei record_run_episode (used_in strategy→episode) |
| **Understand vor Act (Pre-Act)** | Phase Understand im Brain; strukturierte Ausgabe aus Perceive+Memories; Think/Decide/Act nur auf Understanding; kein Act ohne Understand |
| **Explainability** | retrieved_memory_ids in decisions (understand, think, decide); UI „Basierend auf: P:/F:/E:“ |
| **Semantische Suche wo möglich** | principles.search / research_findings.search_by_query mit optionalem query_embedding; _embed_query(); Hybrid Cosine + Keyword |

---

## Was wir *nicht* gebaut haben (und trotzdem SOTA sind)

- **Intent–Experience–Utility (Q-Learning-artig):** Noch kein explizites Q(intent, experience). Wir haben Utility pro Memory-ID (und pro context_key), also value-aware Selection, aber nicht das volle MemRL-Q-Schema.
- **Multi-Hop über den Graph:** Abruf nutzt den Graph für Kanten (used_in), aber noch keine PageRank- oder Community-Summaries wie bei HippoRAG/GraphRAG.
- **Novel-Erweiterungen:** read_urls semantisch (ähnliche Fragen) haben wir; Causal Strategy Selection und explizites Intent–Experience–Q nicht.

**Fazit:** Unser Memory-System erfüllt die **drei SOTA-Säulen** (Episodik mit Verlauf, Two-Phase + Utility, Reflection & Konsolidierung), plus **Pre-Act** (Understand vor Act), **Explainability**, **Graph-Kanten** und **Utility aus Outcome**. Das ist nach aktuellem Forschungsstand **State-of-the-Art** für ein Agent-Memory-System; die Novel-Erweiterungen (z.B. read_urls ähnliche Fragen) gehen darüber hinaus.
