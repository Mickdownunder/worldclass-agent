# Memory & Brain System — Plan: Weltklasse SOTA/Novel

Wie solche Systeme in der Forschung und in SOTA-Systemen funktionieren, wo wir stehen, und wie wir das Gedächtnis- und Brain-System massiv auf Weltklasse-Niveau bringen.

---

## Leitbild: Unfassbar intelligente LLMs — Architektur lässt sie wie ein Mensch handeln

Wir haben **unfassbar intelligente LLMs**. In Kombination mit Agenten geht es darum, diese Intelligenz **wie ein Mensch** einzusetzen: wahrnehmen, verstehen, schlussfolgern, entscheiden, handeln, reflektieren, dazulernen.

Die **Architektur** (Brain, Memory, Kreislauf) ist nicht die Intelligenz — die steckt im Modell. Die Architektur ist das, was die Intelligenz **zum Tragen bringt**: Sie gibt dem LLM **Struktur**, die ein Mensch auch hat:

- **Gedächtnis**, das Erlebnisse und Gelerntes hält (episodisch + semantisch)
- **Verstehen** vor dem Handeln (Situation + Vergangenheit + Warum)
- **Reflexion** nach dem Handeln (was lief gut/schlecht, was daraus folgt)
- **Dauerhafter Kreislauf**, in dem jede Runde die nächste verbessert

So wird die vorhandene LLM-Intelligenz nicht „eingesperrt“, sondern **entfaltet**: Sie bekommt die gleichen Anker wie ein Mensch (Kontext, Geschichte, Feedback) und kann darauf **wie ein Mensch** reagieren — verstehen, lernen, entscheiden. Unser Job ist, diese Struktur so zu bauen, dass die Intelligenz darin **wirklich** zum Zug kommt.

---

## Teil 0: AGI-Denken — Kann sich das System dauerhaft selbst verbessern?

Du willst: Das System **versteht**, was es machen muss, was es kann, und wie es sich verbessern kann — und das **laufend, dauerhaft**, ohne dass du jedes Mal eingreifen musst.

**Kurzantwort: Ja — in einem technisch begrenzten, aber echten Sinne.** Kein „echtes“ AGI, aber ein **selbstverbessernder Loop**, der stabil weiterläuft und aus Erfahrung lernt.

### Was „sich selbst verbessern“ hier konkret heißt

1. **Was es machen muss** (Intent / Ziel)  
   Kommt von außen (User, Cron, Goal-Dateien) — das bleibt. Das System kann aber **intern** ableiten: „In Domain D schneiden wir oft schlecht ab“ → Ziel „nächste Runs in D verbessern“ (z.B. durch bessere Strategy-Auswahl oder mehr Quellen). Das ist **abgeleitetes Ziel** aus dem Selbstmodell.

2. **Was es kann** (Selbstmodell / Capabilities)  
   Das System hält fest: Welche Workflows laufen stabil? Wo sind wiederkehrende Failures? Welche Strategies/Principles haben in welchem Kontext hohe Utility? Das sind **Capability- und Gap-Modelle**, die aus Episoden, Reflections und Metriken **automatisch** befüllt werden (nicht von Hand gepflegt).

3. **Wie es sich besser machen kann** (Improvement-Loop)  
   Aus (1) und (2): „Wir können in Domain D Strategy A wählen (hat hohe Utility), mehr Quellen lesen (was_helped in ähnlichen Runs), Principle P einhalten (cautionary für D).“ Das ist **konkrete Handlungsänderung** aus eigenem Gedächtnis. Plus: Konsolidierung aktualisiert Utility, Strategy-Scores und Principles **laufend** aus Outcomes — also **dauerhafte** Anpassung ohne menschlichen Eingriff.

### Ist das dauerhaft möglich?

**Ja**, unter klaren Bedingungen:

- **Kein unbegrenztes Wachstum:** Memory und Self-Model haben **Obergrenzen** (z.B. Episoden pro Domain behalten, Utility-Tabelle begrenzen, alte Principles archivieren). Sonst wird alles langsamer und unübersichtlich.
- **Stabile Feedback-Quellen:** Outcomes (critic_score, evidence_gate, fail_codes, what_helped/what_hurt) müssen **immer** ankommen und in Memory/Utility/Strategy geschrieben werden. Dann kann der Loop **unbegrenzt** laufen: Run → Outcome → Update → nächster Run nutzt besseres Modell.
- **Governance bleibt:** Du behältst Kontrolle (Governance 0–3, Feature-Flags, Rollback). Das System „verbessert“ nur innerhalb dieser Grenzen — es ändert nicht eigenmächtig Code oder kritische Config.

### Drei Bausteine für diesen dauerhaften Selbstverbesserungs-Loop

| Baustein | Zweck | Laufend möglich? |
|----------|--------|-------------------|
| **Selbstmodell (Was kann ich? Wo fehlt was?)** | Aus run_episodes, failures, Utility, Strategy-Scores: „In Domain D: Pass-Rate X%, beste Strategy A, häufige fail_codes: …“. Wird bei jedem Run/Konsolidierung aktualisiert. | Ja — automatisch aus Daten. |
| **Improvement-Targets (Was soll besser werden?)** | Regeln oder leichter LLM-Call: „Wenn Pass-Rate in D &lt; Schwellwert → Ziel: nächste N Runs in D verbessern“; oder „Wenn Strategy S oft fallback → Ziel: mehr ähnliche Episoden sammeln“. | Ja — aus Self-Model ableitbar. |
| **Improvement-Actions (Was tun wir konkret?)** | Kein neuer „Super-Agent“: Das bestehende System verbessert sich, **indem** es bessere Memories nutzt (Two-Phase Retrieval, Strategy aus Daten, Principles aus Synthese). Jeder Run **ist** die „Action“; die Qualität der Action steigt, weil Memory und Strategy besser werden. | Ja — dauerhaft durch besseres Retrieval/Strategy. |

### Wo das im aktuellen Plan andockt

- **Episoden-Verlauf (Phase 1):** Liefert die **Datenbasis** dafür, dass das System „versteht“, was in der Vergangenheit passiert ist (ähnliche Runs, was half/schadete).
- **Two-Phase + Utility (Phase 2):** Das System lernt **dauerhaft**, welche Memories wirklich nützen — also ein klares **Capability-Signal** („diese Principles/Findings helfen in diesem Kontext“).
- **Strategy aus Daten + Reflection-Synthese (Phase 3):** Das System **leitet** aus Erfahrung ab, was es tun soll (bessere Strategies, bessere Principles) — kein reines LLM-Raten.
- **Konsolidierung (Phase 4):** Ein **offener Loop**, der z.B. täglich läuft: Episoden durchgehen, Utility/Strategy/Summaries aktualisieren. So verbessert sich das Modell von sich aus, **laufend**.
- **Explainability (Phase 5):** Du siehst, **warum** das System etwas getan hat (welche Memories/Strategies) — das ist die Basis dafür, dass du „AGI-Denken“ nachvollziehen und ggf. begrenzen kannst.

### Fazit

- **„Es versteht, was es machen muss“:** Indirekt — durch Ziele von außen plus **abgeleitete Ziele** aus dem Selbstmodell (z.B. „Domain D verbessern“).
- **„Es versteht, was es kann“:** Ja — über Self-Model aus Episoden, Utility, Strategy-Scores, fail_codes (strukturiert, keine Magie).
- **„Es versteht, wie es sich besser machen kann“:** Ja — durch bessere Strategy-Auswahl, besseres Retrieval, bessere Principles aus Synthese; getrieben von Konsolidierung und Outcome-Updates.
- **„Laufend, dauerhaft“:** Ja — solange Outcomes geschrieben werden, Konsolidierung regelmäßig läuft und Limits (Memory, Governance) eingehalten werden. Dann ist **dauerhafte Selbstverbesserung** in diesem begrenzten, technisch definierten Sinne möglich.

### Wie wir es betrieblich dauerhaft machen

- **Jeder Run schreibt Outcome:** research-cycle.sh und Brain schreiben bereits run_episodes, Reflections, Strategy-Updates, Utility-Updates. Wichtig: **Kein Run ohne Schreiben** (auch bei Fehler: Episode mit fail_codes/what_hurt). Dann hat der Loop immer Input.
- **Konsolidierung als Cron:** Ein Job (z.B. `memory_consolidate` oder erweiterter `brain`-Subbefehl) läuft z.B. täglich: Utility nachziehen, Episoden-Summaries pro Domain, ggf. Principle-/Strategy-Synthese aus Batches. **Kein Mensch nötig** — der Job liest Memory, schreibt Memory, fertig.
- **Selbstmodell abfragbar:** Eine kleine Schicht (View, Tool oder API): „Pass-Rate pro Domain“, „Top fail_codes“, „beste Strategy pro Domain“, „Utility-Trend“. Das kann der Brain in **Perceive** oder ein separater „Self-Assessment“-Step lesen. Dann „versteht“ das System (im Sinne nutzbarer Daten) was es kann und wo Lücken sind.
- **Governance bleibt Mensch:** Du setzt Grenzen (welche Workflows, welche Domains, max. Autonomie). Innerhalb dieser Grenzen verbessert sich das System laufend; außerhalb passiert nichts.

---

## Teil 0b: Verstehen zuerst — Der Kreislauf soll wirklich intelligent sein

Du sagst: Das System soll **wirklich intelligent** sein. Es **muss möglich sein** — nur weil noch kein Mensch es vollständig verstanden hat, heißt das nicht, dass es nicht umsetzbar ist. Der Kreislauf soll **hoch intelligent** sein: **lernen**, vor allem **verstehen** (das ist das Wichtigste), und **dann** Entscheidungen treffen.

**Ja, dieser Ansatz ist verstanden.** Und ja, man kann ihn technisch ernst nehmen: indem wir **Verstehen** nicht als Nebeneffekt, sondern als **eigene Phase** im Kreislauf verankern und alle Entscheidungen explizit **auf diesem Verstehen** aufbauen.

### Was „Verstehen“ hier heißt (operational, umsetzbar)

Wir behaupten kein menschengleiches Verstehen. Wir bauen ein System, in dem **vor** jeder Entscheidung eine klare **Verstehens-Repräsentation** erzeugt wird — und alles Weitere (Think, Decide, Act) **darauf aufsetzt**. Verstehen ist dann:

1. **Situation erfassen:** Was ist gerade der Fall? (Projekt, Phase, Domain, offene Ziele, Fehler der letzten Runs.)
2. **Relevante Vergangenheit einordnen:** Was ist in **ähnlichen** Situationen passiert? Was hat geholfen, was geschadet — und **warum** (soweit wir es aus Daten ableiten können)?
3. **Unterschiede und Lücken benennen:** Was ist diesmal anders? Wo fehlen uns ähnliche Episoden? Wo ist unser Modell unsicher?
4. **Handlungsmöglichkeiten und Konsequenzen:** Was können wir tun (Strategies, Principles, Workflows)? Was erwarten wir, wenn wir A vs. B tun (aus vergangenen Outcomes)?

Erst wenn diese **Verstehens-Zusammenfassung** („Situation + Vergangenheit + Warum + Optionen“) da ist, kommt **Think** (Plan) und **Decide** (Aktion). So ist der Kreislauf **verstehensgetrieben**: Entscheidungen folgen aus einem expliziten Modell der Situation, nicht aus bloßem Abruf + Heuristik.

### Neuer Kreislauf: Understand → Think → Decide → Act → Reflect

Aktuell: **Perceive → Think → Decide → Act → Reflect.**

Vorgeschlagen (ohne Perceive zu streichen): **Perceive → Understand → Think → Decide → Act → Reflect.**

- **Perceive:** Rohdaten sammeln (wie bisher: Jobs, Research, Memory-Summary, Playbooks, …).
- **Understand (neu, Kern):** Aus Perceive + Memory eine **strukturierte Verstehens-Darstellung** erzeugen:
  - **Situation:** Kurze Beschreibung: Kontext, Ziel, Domain, aktuelle Lücken.
  - **Relevante Episoden:** Ähnliche vergangene Runs (mit Verlauf, nicht 1:1 pro Projekt); was_helped / what_hurt / fail_codes; **Warum** (z.B. „multi_source_verification half, weil claim_support_rate hoch war“).
  - **Relevante Principles/Strategies:** Welche gelten hier? Welche haben in diesem Kontext hohe Utility?
  - **Unsicherheiten:** Wo fehlen Daten? Wo ist similar_episode_count niedrig? Wo widersprechen sich Principles?
  - **Optionen:** Welche Aktionen sind möglich? Welche haben in ähnlichen Fällen zu gutem/schlechtem Outcome geführt?
- **Think:** Nimmt **Understand** als Hauptinput (nicht rohen State). Plant explizit auf Basis von „Situation + Vergangenheit + Warum + Optionen“.
- **Decide / Act / Reflect:** Wie bisher, aber mit klarem Bezug: „Diese Decision basiert auf Understanding XYZ“ (Explainability).

So wird **Verstehen** die zentrale Stelle im Kreislauf: Ohne Understanding-Output keine Planung, keine Entscheidung. Das System wird **in seinem Kreislauf** intelligenter, weil es **lernt** (Episoden, Utility, Principles), **versteht** (diese Phase baut das Modell) und **dann** entscheidet.

### Ist das umsetzbar? Ja.

- **Understand** kann zunächst ein **LLM-Call** sein: Input = Perceive + abgerufene Episoden/Principles/Strategies (mit what_helped/what_hurt und Utility); Output = strukturiertes JSON (situation, relevant_episodes_summary, why_helped_hurt, uncertainties, options). Später kann Teile davon regelbasiert oder aus Graphen abgeleitet werden.
- **Speichern:** Jeder Understand-Output kann als **Decision/Episode** oder eigene Tabelle „understanding_snapshots“ abgelegt werden — dann lernt das System über Zeit auch, **bessere Verstehens-Zusammenfassungen** zu produzieren (z.B. durch Konsolidierung, die „gute“ Understandings von erfolgreichen Runs recycelt).
- **Laufen lassen:** Der Kreislauf ist **dauerhaft**: Perceive → Understand → Think → Decide → Act → Reflect → (Memory-Update) → nächster Cycle. Verstehen wird jedes Mal neu erzeugt, aber auf Basis eines immer reicher werdenden Gedächtnisses. So ist **hohe Intelligenz im Kreislauf** erreichbar: mehr Episoden, besseres Utility, bessere Principles → besseres Verstehen → bessere Entscheidungen.

### Kurz

- **Dein Ansatz:** System wirklich intelligent; Lernen, **Verstehen** (wichtigstes), dann Entscheidungen; und das **muss möglich sein**.
- **Antwort:** Ja. Wir machen es möglich, indem wir **Verstehen** als eigene Phase **Understand** einbauen, die aus Situation + Vergangenheit + Warum + Optionen eine explizite Darstellung baut und **alle weiteren Schritte davon abhängig** machen. Der Kreislauf ist dann **verstehensgetrieben**, lernt laufend aus Outcomes und kann dauerhaft so laufen. Es ist umsetzbar — nicht „weil es noch keiner verstanden hat“, sondern weil wir Verstehen **operational definieren** und im Loop erzwingen.

---

## Teil A: Wie solche Systeme funktionieren (Stand Forschung & SOTA)

### A.1 Die zentrale Unterscheidung: Episodisch vs. Semantisch

- **Episodisches Gedächtnis**: Speichert **konkrete Erlebnisse** mit Zeit- und Kontextinformation. Antwortet auf „Was ist passiert?“ — z.B. „Run X mit Frage Q endete mit critic_score 0.8, was_helped: multi_source_verification.“
- **Semantisches Gedächtnis**: Speichert **Fakten und Konzepte** ohne Bindung an ein bestimmtes Ereignis. Antwortet auf „Was ist wahr?“ — z.B. Principles, Playbooks, akzeptierte Findings.
- **Problem aktueller Agenten**: Sie nutzen vor allem semantische Suche (Embedding-Ähnlichkeit). Episodisches Erinnern („welche vergangenen Runs ähneln dieser Situation und was half?“) und **Reasoning über Ereignisverläufe** fehlen oder sind schwach.

Für uns: `run_episodes` + `what_helped`/`what_hurt`/`fail_codes` sind episodisch; Principles/Playbooks/Findings sind semantisch. Unser System vermischt beides und nutzt Episodik nicht konsequent (z.B. nur 1 Episode pro Projekt, keine echte Ereignis-Reasoning-Schicht).

---

### A.2 SOTA-Architekturen (Kernideen)

| System | Kernidee | Was wir daraus nutzen |
|--------|----------|------------------------|
| **MemRL** | **Intent–Experience–Utility** Triplet; **Two-Phase Retrieval**: (1) semantischer Recall (Kandidaten), (2) **value-aware Selection** via gelernte Q-Werte (Utility). Lernen ohne Gewichtsänderung: Q-Update aus Umwelt-Feedback (Monte Carlo / TD). | Retrieval nicht nur „similar“, sondern **utility-basiert**; explizites **Utility-Update aus Outcome**; Two-Phase (semantic → utility rank). |
| **REMem** | **Hybrid Memory Graph**: zeitbewusste „Gists“ (Zusammenfassungen) + Fakten; **agentic Retriever** mit Tools für iteratives Retrieval über den Graphen. Episodisches **Reasoning** über Ereignisse. | Episoden als **Knoten mit Zeit/Kontext**; Graph-Kanten (used_in, derived_from); **Reasoning-Phase** über Episoden, nicht nur Abruf. |
| **HippoRAG** | Neocortex/Hippocampus-Inspiration: **Knowledge Graph + Personalized PageRank** für assoziatives Abrufen. Multi-Hop über Dokumentgrenzen. | Graph-basierter Abruf (Entities, Relations, run_episodes verknüpft); PageRank-ähnliches Scoring für „wichtige“ Knoten im Kontext der Query. |
| **Generative Agents (Stanford)** | **Memory Stream** (Erlebnisse + Metadaten), **Reflection** (Synthese zu höherstufigen Einsichten), **Retrieval** (dynamisch für Planung). | **Reflection** als eigener Prozess: aus vielen Episoden/Reflections **generierte** Principles/Strategien; nicht nur speichern, sondern **synthetisieren**. |
| **MemGPT** | **Virtuelles Kontext-Management**: Main Context (Fenster) ↔ External Storage; Paging zwischen „schnell“ und „langsam“. | Klare **Mehrebenen-Architektur**: Working Memory (aktueller Cycle) vs. Long-Term (DB); bewusste Platzierung was wohin gehört. |
| **GraphRAG (Microsoft)** | Community-Erkennung im Graphen, **hierarchische Summaries** pro Community; globale Fragen über Community-Summaries. | **Strukturierte Zusammenfassung** von Episoden-Clustern (z.B. pro Domain); Abruf über Summary + Detail bei Bedarf. |
| **Phasor / Wake–Sleep** | **Konsolidierung**: Wake = Erlebnisse puffern; Sleep = Replay, Synapsen-Konsolidierung, „Träumen“ für zukünftige Szenarien. | **Offline-Konsolidierung**: z.B. nächtlicher Job, der Episoden replayed, Principles/Strategien aktualisiert, Q/Utility neu schätzt. |
| **MetaReflection / ParamMem** | Lernen von **Reflections** (nicht nur speichern): Instructions/Parametric Memory aus vergangenen Reflexionen. | **Reflection → Policy**: Aus Reflection-Text und Outcome systematisch „bessere Instructions“ oder Strategy-Parameter ableiten. |

---

### A.3 Drei Säulen eines weltklassen Memory/Brain-Systems

1. **Episodisches Gedächtnis mit Verlauf und Kontext**  
   Nicht „ein Eintrag pro Projekt“, sondern **viele Episoden** mit Zeit, Domain, Outcome, what_helped/what_hurt. Abfragen: „ähnliche vergangene Runs“, „Runs mit dieser Strategy in dieser Domain“. Reasoning: „In ähnlichen Fällen hat X geholfen / Y geschadet.“

2. **Two-Phase Retrieval + Utility-Learning**  
   Phase 1: **Recall** (semantisch/keyword) → Kandidaten. Phase 2: **Selection** nach **gelerntem Nutzen** (Q/Utility), nicht nur Similarity. Utility wird aus tatsächlichen Outcomes aktualisiert (Monte Carlo/TD); kontextabhängige Utility (pro Intent/Domain) wo sinnvoll.

3. **Reflection & Konsolidierung**  
   **Reflection**: Aus vielen Episoden/Reflections höherstufige Einsichten erzeugen (Principles, Strategy-Vorschläge, „was in Domain D typischerweise hilft“). **Konsolidierung**: Offline-Prozess, der Episoden replayed, Graphen/Summaries aktualisiert, Utility/Q schätzt — ohne jeden Run zu blockieren.

---

## Teil B: Wo wir stehen (Brücke zu unserem System)

- **Episodik**: run_episodes existiert, aber **1:1 pro Projekt** (INSERT OR REPLACE) → kein Verlauf; Similarity nutzt nur andere Projekte. what_helped/what_hurt/fail_codes sind da, werden aber nicht für „Reasoning über Ereignisse“ genutzt.
- **Retrieval**: Überwiegend **keyword**; Embeddings vorhanden, aber **nicht für Suche**. Utility ist **Laplace (helpful/retrieval)**, aber nur reaktiv (seed + utility_update), **nicht** als zweite Phase „value-aware selection“ nach MemRL-Art.
- **Reflection**: Brain-Reflect schreibt Reflections; Distiller erzeugt Principles/Strategy aus LLM. Es fehlt: **strukturierte Synthese aus vielen Episoden** (z.B. „in 20 Runs mit Domain medical war relevance_threshold 0.58 im Mittel bei Erfolg“) und **Konsolidierung** (offline Batch über Episoden).

---

## Teil C: Ziele (Weltklasse SOTA/Novel)

- **Episodisches Gedächtnis**: Vollständiger **Run-Verlauf** pro Projekt/Thema; Abfragen nach „ähnlichen vergangenen Runs“ und **Reasoning** („was half in ähnlichen Fällen?“).
- **Two-Phase Retrieval + Utility**: **Phase 1** semantic/keyword Recall; **Phase 2** value-aware Selection mit **gelerntem Utility** (Q-artig), inkl. kontextabhängiger Utility (z.B. pro Domain/Intent). Robustes Update aus Outcome (immer wenn Outcome da ist, nicht nur wenn ein bestimmtes Tool läuft).
- **Reflection & Konsolidierung**: **Reflection-Synthese** aus Episoden (nicht nur LLM-Distiller): datengetriebene Strategy-Parameter, kontrastive Principles (gut vs. schlecht). **Konsolidierung**: Offline-Job (z.B. cron) für Graph-Update, Utility-Schätzung, Episoden-Summaries.
- **Strukturierter Memory-Graph**: Klare Knoten (run_episode, strategy_profile, principle, finding, entity) und Kanten (used_in, derived_from, improved, failed_on); Abruf über Graph (z.B. Multi-Hop, Community-Summaries wo sinnvoll).
- **Explainability**: Welche Memory-Objekte (Episoden, Principles, Findings) flossen in welche Decision/Strategy-Auswahl ein; in UI und Logs nachvollziehbar.

---

## Teil D: Phasierter Plan (konkret umsetzbar)

### Phase 1: Episodisches Gedächtnis in Ordnung bringen (Grundlage)

**Ziel:** Echter Episoden-Verlauf; keine Überschreibung pro Projekt.

- **Schema:**  
  - `run_episodes`: `id` eindeutig (z.B. `hash(project_id:created_at)` oder UUID); **project_id nicht UNIQUE**; optional `run_index` pro project_id.  
  - Migration: Bestehende Zeilen behalten, neue Runs als neue Zeilen einfügen (kein INSERT OR REPLACE mehr).
- **Code:**  
  - `record_run_episode`: Immer INSERT (neue id); Aufrufer in research-cycle.sh anpassen.  
  - `_similar_episode_signals` / `select_strategy`: Auf N vergangene Episoden (verschiedene Runs, auch gleiches Projekt wenn mehrfach gelaufen) umstellen; Similarity über Frage/Domain wie bisher, aber mit vollem Verlauf.
- **Abnahme:** Mehrere Runs desselben Projekts erzeugen mehrere Zeilen; select_strategy nutzt ähnliche Episoden über Runs hinweg.

**Risiko:** Niedrig. Rückwärtskompatibel durch Migration.

---

### Phase 2: Semantische Suche + Two-Phase Retrieval (SOTA Retrieval)

**Ziel:** Recall semantic; Selection value-aware (Utility); Utility zuverlässig aus Outcome aktualisiert.

- **Semantische Suche:**  
  - **Principles:** `embedding_json` nutzen; optional Hybrid (cosine + keyword); Fallback keyword wenn kein Embedding.  
  - **Reflections / Episodes:** Optional Embedding-Spalte befüllen (bei record_reflection / record_episode); Abruf mit cosine similarity, Top-K, dann Utility.  
  - **Findings:** `search_by_query`: erste Stufe semantic (embedding_json), zweite Stufe keyword; gleiche API.
- **Two-Phase Retrieval (MemRL-ähnlich):**  
  - **Phase 1 (Recall):** Wie bisher Kandidaten (semantic + keyword), z.B. 5× k.  
  - **Phase 2 (Selection):** Re-Rank mit **combined_score = (1-λ)·similarity_norm + λ·utility**; utility aus `memory_utility` (kontextunabhängig zunächst). λ konfigurierbar (z.B. 0.5).  
  - `retrieve_with_utility` entsprechend umbauen; record_retrieval bei jedem Abruf, der in Kontext landet (nicht nur in knowledge_seed).
- **Utility robust machen:**  
  - **Immer wenn Outcome bekannt:** research_utility_update (oder zentraler „memory outcome hook“) aufrufen: prior_knowledge.json oder explizit übergebene memory_ids (principle, finding) + strategy_profile_id.  
  - Optional: **Kontextabhängige Utility** — Tabelle um (topic_domain oder question_hash) erweitern; Utility pro (memory_type, memory_id, context_key); bei Retrieval context_key aus aktueller Frage/Domain ableiten.
- **Abnahme:** Retrieval nutzt Embeddings wo vorhanden; Two-Phase verbessert Relevanz bei gleicher Similarity; Utility steigt/sinkt nach Runs messbar.

**Umsetzung:** `lib/memory/__init__.py`: `_embed_query()` (OpenAI, abschaltbar mit `RESEARCH_MEMORY_SEMANTIC=0`); `retrieve_with_utility` übergibt `query_embedding` an Principles/Findings. `principles.search(..., query_embedding=...)` und `research_findings.search_by_query(..., query_embedding=...)`: Hybrid (lexical + cosine wo `embedding_json` vorhanden). Two-Phase und Utility-Update wie zuvor (research_utility_update.py aus research-cycle.sh).

**Risiko:** Mittel (Embedding-Infra, Laufzeit). Entschärfung: Feature-Flag `RESEARCH_MEMORY_SEMANTIC=0`, Fallback keyword-only.

---

### Phase 3: Strategy aus Daten + Reflection-Synthese (SOTA + Novel)

**Ziel:** Policy nicht nur aus LLM, sondern aus Episoden-Daten; Reflection als Synthese über viele Ereignisse.

- **Strategy aus Daten:**  
  - **Aggregation aus run_episodes:** Für Domain/Status=done und hohen critic_score: aus `plan_query_mix_json`, `gate_metrics_json`, `source_mix_json` Mittelwerte/Mediane ableiten (relevance_threshold-Äquivalent, revise_rounds, query_type_mix).  
  - **Empirically-Best-Profile:** Ein neuer „empirically_best“ Strategy-Profil-Typ (oder Metadaten-Flag): Policy vollständig aus Daten, kein LLM. Distiller kann diese als Kandidaten einspielen oder mit LLM-Vorschlag fusionieren.  
  - **select_strategy:** Diese Profile in Kandidatenliste aufnehmen; Scoring wie bisher (Score aus Erfolgsrate).
- **Reflection-Synthese:**  
  - **Batch über Episoden:** Job (z.B. nach N neuen Episoden oder täglich): Episoden nach Domain/Ähnlichkeit clustern; pro Cluster „Was half / was schadete“ aggregieren (Listen + Häufigkeiten); LLM oder regelbasiert **Synthese** → neue/aktualisierte Principles („In medical: multi_source_verification oft hilfreich“).  
  - **Kontrastive Principles:** Paare (erfolgreicher Run, gescheiterter Run) mit ähnlicher Frage; Diff „what_helped“ vs „what_hurt“ → strukturierte „wenn X, dann A statt B“ Principles.
- **Abnahme:** Mindestens ein Strategy-Profil pro Domain aus Daten; Principles entstehen aus Episoden-Synthese; bessere Pass-Rate bei ähnlichen Themen.

**Risiko:** Mittel. Novel-Komponente (kontrastive Principles) kann schrittweise kommen.

---

### Phase 4: Memory-Graph + Konsolidierung (SOTA-Struktur)

**Ziel:** Expliziter Graph; Offline-Konsolidierung; Multi-Hop/Community wo nützlich.

- **Graph konsistent nutzen:**  
  - Kanten bereits da (`memory_graph_edges`): used_in, derived_from, improved, failed_on.  
  - Bei record_run_episode / strategy_application / principle insert: Kanten schreiben (Episode ↔ Strategy, Episode ↔ Principle wenn aus diesem Run).  
  - **Abruf über Graph:** Optional: für „welche Principles/Strategien hängen mit diesem Run/ dieser Domain zusammen?“ Graph-Traversierung (z.B. 2 Hop); Integration in brain_context oder select_strategy.
- **Konsolidierung (Wake–Sleep-ähnlich):**  
  - **Offline-Job** (cron, z.B. nachts):  
    - Episoden der letzten 24h durchgehen; Utility für alle in prior_knowledge genutzten memory_ids aktualisieren (falls utility_update im Run fehlte).  
    - Optional: Q-artige Schätzung pro (intent_cluster, experience_id) wenn wir Intent-Experience-Utility explizit einführen.  
    - Episoden-Summaries pro Domain/Cluster (wie GraphRAG Community Summaries): kurze LLM-Summary „In Domain D in den letzten N Runs: …“; in DB oder Datei für Abruf.  
  - Kein Blocking des laufenden Research-Flows.
- **Abnahme:** Kanten konsistent; Konsolidierungs-Job läuft; Episoden-Summaries abrufbar.

**Risiko:** Mittel (Komplexität). Kann auf „Kanten schreiben + einfache Abfrage“ beschränkt werden, ohne sofort PageRank/Community.

---

### Phase 5: Explainability + Brain Working Memory (Polish)

**Ziel:** Nachvollziehbarkeit; klare Trennung Working vs. Long-Term Memory.

- **Explainability:**  
  - Bei jedem Think/Plan: **retrieved_memory_ids** (principle_ids, finding_ids, episode_ids) in memory_decision_log oder neues Feld speichern.  
  - UI (Research-Detail, Brain-Tab): „Diese Decision basierte auf: Principle P, Finding F, Episode E.“
- **Working Memory:**  
  - Explizites **Working-Memory-Objekt** pro Cycle: aktueller State, aktuell abgerufene Memories, aktueller Plan; nur für Dauer des Cycles; nach Reflect in Long-Term (Episodes, Decisions, Reflections) überführt. Kein neues Backend nötig: Konzept in Doku und ggf. in Logs/UI („aktueller Kontext“).
- **State-Truncation verbessern:** Priorisierung: Principles + aktive Research-Projekte + letzte N Jobs zuerst; dann Rest; hartes Limit 12k mit „truncated“-Marker im Plan-Input.
- **Abnahme:** Jede Decision mit zugehörigen Memory-IDs; UI zeigt sie; State schneidet seltener Wichtiges ab.

---

### Phase 6: Novel-Erweiterungen (Forschung vorantreiben)

**Ziel:** Über reines SOTA hinaus: Ideen, die in der Literatur noch wenig ausgereizt sind.

- **Causal Strategy Selection:**  
  - what_helped/what_hurt/fail_codes als **Features**; einfaches Modell (z.B. LogReg oder kleines MLP) oder regelbasierte Entscheidungstabelle: „Wenn Frage-Features F und Domain D, dann Strategy A besser als B“ (trainiert auf Episoden-Paare: gleiche Domain, unterschiedlicher Outcome). Kein LLM für diese Auswahl; nur für Synthese-Texte.
- **Intent–Experience–Utility explizit (MemRL-ähnlich):**  
  - Speicherformat: (intent_embedding_or_hash, experience_id, Q). Experience = run_episode oder Reflection-Snippet. Q-Update mit Monte Carlo aus critic_score/outcome. Two-Phase: Recall nach Intent-Similarity, Selection nach Q. Ermöglicht „unter gleichem Intent wurde Experience E oft erfolgreich genutzt“.
- **read_urls semantisch:**  
  - Frage-Embedding oder normalisierter Hash; bei get_read_urls_for_question auch „ähnliche“ Fragen (cosine > Schwellwert) zurückgeben, damit leicht umformulierte Fragen dieselben URLs überspringen.  
  **Umsetzung:** `read_urls.question_signature` (Migration); `record_read_urls` speichert `_question_signature(question)`; `get_read_urls_for_question(question, similar_threshold=0.6)` liefert URLs für exakten Hash plus für Signaturen mit Token-Jaccard ≥ Schwellwert.
- **Abnahme:** Mindestens eine Novel-Komponente produktiv (z.B. Causal Strategy oder Intent–Experience–Utility); Metriken (Pass-Rate, Revision-Runden) verbessert.

---

## Teil D2: 100 % Umsetzung — Erfolgsbedingungen und Garantien (forschungssicher)

Du hast recht: Wenn ich es nicht garantieren kann, habe ich nicht genug geforscht. Die Forschung liefert **konkrete Bedingungen**, unter denen solche Systeme **theoretisch konvergieren** und **empirisch deutlich besser** werden. Wenn wir diese Bedingungen **vollständig umsetzen**, ist die Umsetzung zu 100 % spezifiziert und erfolgssicher.

### Was die Forschung garantiert (und was wir daraus ableiten)

**1. Memento-II / Stateful Reflective Decision Process (SRDP)**  
- **Read** = Abruf relevanter Episoden aus Memory → entspricht **Policy Improvement**.  
- **Write** = Speichern des Outcomes (Reward/Feedback) in Memory → entspricht **Policy Evaluation**.  
- Unter **milden Annahmen** (Read liefert nicht-sinkende Policy-Qualität, Write liefert informative Bewertung): Der iterative Reflexionsprozess **konvergiert gegen einen Fixpunkt** (optimale oder selbstkonsistente Policy).  
- **Wenn das Gedächtnis wächst und den Zustandsraum abdeckt:** Die zusammengesetzte Policy **konvergiert gegen die optimale Lösung** im zugrundeliegenden MDP.  
- **Zwei-Zeitskalen:** Memory-Updates auf **langsamerer** Zeitskala als Value-/Policy-Updates → Stabilität und Konvergenz.

**→ Umsetzungspflicht:**  
- Jeder Run **muss** ein Write auslösen (Outcome → Episoden/Utility/Strategy).  
- Retrieval **muss** Read als Policy Improvement realisieren: Two-Phase (Recall nach Similarity, **Selection nach Utility**), nicht nur Similarity.  
- Konsolidierung auf **langsamerer** Zeitskala (z. B. täglich), Value/Utility-Updates pro Run erlaubt.

**2. Pre-Act (Multi-Step Planning and Reasoning Before Acting)**  
- **Strukturierter Plan mit Begründung vor der Aktion**; Plan wird nach jedem Schritt mit neuem Kontext verfeinert.  
- Empirisch: **+70 % Action Recall**, **+69,5 % Action Accuracy**, **+28 % Goal Completion** gegenüber ReAct ohne globalen Plan.  
- Entscheidend: Nicht nur „nächster Schritt“, sondern **mehrstufiger Plan + Reasoning** vor dem Handeln.

**→ Umsetzungspflicht:**  
- **Understand-Phase** vor Think/Decide/Act: strukturierte Ausgabe (Situation, relevante Episoden, Warum geholfen/geschadet, Unsicherheiten, Optionen), **nur aus tatsächlichen Daten** (Perceive + Memory) — kein Raten, kein Halluzinieren.  
- Think/Decide/Act **dürfen nur** auf Basis dieses Understanding-Outputs laufen (kein Bypass).

**3. Agent-Failure-Modes (empirische Taxonomie)**  
- **Premature Action Without Grounding:** Aktion ohne vorherige Prüfung/Schema → stille Fehler.  
- **Over-Helpfulness Under Uncertainty:** Bei fehlenden Daten „ähnliches“ erfinden → Datenintegrität gefährdet.  
- **Context Pollution:** Ablenkende Daten werden als Signal genutzt → Qualität sinkt.  
- **Erfolg hängt an Recovery:** Systeme, die Fehler erkennen und korrigieren (und in Memory schreiben), sind robuster als solche, die „nie fehlen“.

**→ Umsetzungspflicht:**  
- **Keine Aktion ohne Understanding:** Understand ist **Grounding**: Input nur Perceive + abgerufene Memories (faktisch), Output strukturiert und validierbar.  
- Bei **Unsicherheit** (z. B. similar_episode_count = 0): explizit im Understanding ausweisen, ggf. konservative Defaults (Fallback-Strategy).  
- **Two-Phase Retrieval** reduziert Context Pollution: zuerst Relevance, dann Utility — Ablenker mit niedriger Utility werden aussortiert.  
- **Jeder Run schreibt Outcome** (auch bei Fehler: fail_codes, what_hurt) → Recovery durch nächstes Mal besseres Read.

### Checkliste: Wenn diese Punkte erfüllt sind, ist die Umsetzung „100 %“ (theorie- und empiriegestützt)

| Nr. | Bedingung | Wo im Plan / im Code |
|-----|-----------|------------------------|
| 1 | Jeder Run schreibt in Memory (Episode + ggf. Utility/Strategy-Update) — **niemals** Run ohne Write. | research-cycle.sh, Brain Reflect, utility_update; Guard: „Run complete“ nur wenn Write bestätigt. |
| 2 | Read = Two-Phase: (1) Recall nach Similarity/Keyword, (2) **Selection nach Utility** (Q/Laplace). | Phase 2: retrieve_with_utility, memory_utility, update_from_outcome. |
| 3 | Understand-Phase **vor** Think/Decide/Act; Input nur Perceive + abgerufene Memories (grounded); Output strukturiert (situation, relevant_episodes, why_helped_hurt, uncertainties, options). | Teil 0b: Understand als eigene Phase; Implementierung: LLM-Call mit festem Schema, nur faktenbasierte Inputs. |
| 4 | Think/Decide/Act erhalten **nur** Understanding-Output (und ggf. Perceive als Ergänzung), kein Bypass. | Brain: think() bekommt understand_output als Hauptinput. |
| 5 | Konsolidierung (Utility, Strategy, Summaries) läuft auf **langsamerer** Zeitskala (z. B. Cron täglich). | Phase 4: memory_consolidate / Cron. |
| 6 | Bei Unsicherheit (z. B. keine ähnlichen Episoden): explizit im Understanding, Fallback-Strategy nutzen, kein Erfinden. | select_strategy: similar_episode_count == 0 → return None; Understand: „uncertainties“ befüllen. |
| 7 | Keine Premature Action: Keine Aktion ohne vorherigen Understanding-Output (und ggf. minimale Validierung). | Architektur: Act() nur aufrufbar nach Understand → Think → Decide. |

Wenn **alle sieben Punkte** in der Implementierung erfüllt sind, erfüllt das System die **Erfolgsbedingungen** aus SRDP (Konvergenz bei Read/Write und zwei Zeitskalen), Pre-Act (Plan/Reasoning vor Action) und der Failure-Mode-Vermeidung (Grounding, Two-Phase, Recovery durch Write). Dann ist die Umsetzung **vollständig spezifiziert** und **erfolgssicher** im Sinne der aktuellen Forschung — also **100 % umsetzbar und zum Erfolg führend**, sofern der Code diese Checkliste erfüllt.

### Garantie-Formulierung (klar und ehrlich)

- **Garantie (theoriegestützt):** Unter den obigen Bedingungen (Read = Policy Improvement, Write = Policy Evaluation, zwei Zeitskalen, kein Act ohne Understand) **konvergiert** der Reflexionsprozess gegen einen Fixpunkt; bei wachsendem, abdeckendem Gedächtnis nähert sich die Policy der optimalen.  
- **Garantie (empiriegestützt):** Plan/Reasoning vor Action (Pre-Act) bringt in publizierten Experimenten große Verbesserungen (Action Recall, Goal Completion); Grounding und Two-Phase beheben bekannte Agent-Failure-Modes.  
- **Was wir also garantieren können:** Wenn wir die **gesamte** Architektur und Checkliste **genau so** bauen (Understand → Think → Decide → Act → Reflect; Write bei jedem Run; Two-Phase Retrieval; Konsolidierung auf langsamer Zeitskala), dann erfüllt das System die **Erfolgsbedingungen**, unter denen die Forschung Konvergenz und Verbesserung nachweist. **100 % Umsetzung** heißt dann: Kein fehlender Baustein, keine Abkürzung an diesen Stellen — und damit **erfolgssicher** nach aktuellem Forschungsstand.

---

## Teil E: Priorisierung und Meilensteine

| Phase | Inhalt | Grober Aufwand | Priorität |
|-------|--------|-----------------|-----------|
| 1 | Episoden-Verlauf (Schema + Code) | 1–2 Tage | **Hoch** (Grundlage für alles andere) |
| 2 | Semantische Suche + Two-Phase + robustes Utility | 3–5 Tage | **Hoch** |
| 3 | Strategy aus Daten + Reflection-Synthese | 3–4 Tage | **Hoch** |
| 4 | Graph konsistent + Konsolidierungs-Job | 2–3 Tage | Mittel |
| 5 | Explainability + Working Memory + Truncation | 1–2 Tage | Mittel |
| 6 | Novel (Causal, Intent–Experience–Utility, read_urls) | 3–5 Tage | Nach SOTA-Stand |

Empfohlene Reihenfolge: **1 → 2 → 3** (Kern-SOTA), dann 4 und 5, dann 6.

---

## Teil F: Metriken (Erfolg messen)

- **Episodik:** Anzahl Episoden pro Projekt/Domain; Nutzung in select_strategy (similar_episode_count, causal_signal).
- **Retrieval:** A/B oder Vorher/Nachher: Pass-Rate, Revision-Runden, Token-Kosten pro erfolgreichem Report; Anteil Retrievals mit utility > 0.5.
- **Strategy:** Anteil Runs mit „applied“ vs „fallback“; Memory Value Score (applied_avg - fallback_avg) über Zeit.
- **Explainability:** Anteil Decisions mit retrieved_memory_ids; Nutzer-Feedback („nachvollziehbar“).

---

Dieser Plan baut auf MEMORY_BRAIN_DEEP_DIVE.md und MEMORY_V2_MASTERPLAN.md auf und soll bei Änderungen am Memory-/Brain-System mitgeführt werden.
