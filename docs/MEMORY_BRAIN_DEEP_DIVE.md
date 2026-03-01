# Memory & Brain System — Tiefenanalyse

Vollständige technische Analyse: wie es funktioniert, wo die Probleme liegen, wo SOTA oder novel Verbesserungen möglich sind.

---

## Teil 1: Brain — Kognitive Schleife im Detail

### 1.1 Datenfluss Perceive → Think → Decide → Act → Reflect

- **Perceive** liest ausschließlich aus Dateisystem + einer offenen Memory-Instanz:
  - Jobs: `jobs/*/*/job.json` (letzte 10), Workflows: `workflows/*.sh`, Clients: `factory/clients/*.json`, Goals: `knowledge/goals/*.md`, Priorities: `knowledge/priorities.md`
  - Research: alle `research/proj-*/project.json`, sortiert „nicht done zuerst“, dann `last_phase_at`
  - Playbooks: zuerst `research/playbooks/*.json` (file), dann `memory.all_playbooks()` (gelernt), Domains dedupliziert
  - Memory: `memory.state_summary()` (Episodes, Decisions, Reflections, Playbooks, Principles, Outcomes); `recent_reflections` wird auf Quality ≥ 0.35 gefiltert
  - **research_context**: `brain_context.compile(memory, query=goal)` — goal = erste offene Research-Frage (oder None). Bei `query` gesetzt: **utility-ranked retrieval** (reflections, findings, principles); sonst statisches Retrieval (alle accepted findings, recent reflections, list_principles)
- **Think**: State als JSON (max 12000 Zeichen + Truncation), Strategic Principles **vor** Truncation extrahiert und angehängt (bis 10, mit Tag/Score/Description). Ein LLM-Call liefert Plan (analysis, priorities, plan[], risks, confidence). Bei LLM-Fehler: Fallback-Plan mit confidence 0.1. Jeder Think wird als Decision (phase=think) ins Memory geschrieben.
- **Decide**: Nimmt erste Aktion aus dem Plan; Governance 0/1 → approved=False, 2/3 → approved=True. Decision wird als phase=decide gespeichert.
- **Act**: Bei `plumber:*` → `_act_plumber`; sonst wenn Workflow existiert: `op job new --workflow <id> --request <request>` dann `op run` (timeout 200s). research-cycle: request = Projekt-ID (aus reason extrahiert oder reason). Episode wird in allen Fällen geschrieben (act, act_skipped, act_error, act_no_workflow, act_plumber).
- **Reflect**: Nimmt action_result (job_id, job_dir, status, …). Liest log.txt (tail 2000 Zeichen) + Artifacts-Namen. Ein LLM-Call (Timeout 90s via ThreadPoolExecutor) liefert outcome_summary, went_well, went_wrong, learnings, quality_score, should_retry, playbook_update. Bei Timeout/Fehler: **metrikbasierter Fallback** (DONE→0.75, FAILED→0.25, sonst 0.4). Dann: record_reflection, record_quality, ggf. upsert_playbook(domain=workflow), und bei starkem Learning (len>20, quality≥0.7 → guiding principle, quality≤0.3 → cautionary principle). Phase reflect wird als Decision gespeichert.

**Probleme / Lücken (Brain):**
- State-Truncation bei 12000 Zeichen kann Research-Playbooks und Principles abschneiden; Principles werden explizit vor Truncation angehängt, aber der Rest des State (z. B. viele research_projects) kann relevante Infos verlieren.
- Kein explizites „Welche Memory-Objekte haben diese Decision beeinflusst?“ — nur indirekt über research_context im State.
- Reflect erzeugt Principles nur aus Learnings-Text; es gibt keine Verknüpfung zu konkreten Findings/Episodes (z. B. „dieses Principle stammt von Run X und Finding Y“).
- Governance ist global pro Cycle; keine feinkörnige „diese Aktion nur vorschlagen, jene ausführen“.

---

## Teil 2: Memory — Architektur und Module

### 2.1 Schema (Kern)

- **episodes**: Ereignis-Log (kind, content, job_id, workflow_id, metadata, optional embedding). Indizes: kind, job_id, ts.
- **decisions**: Reasoning-Traces (phase, inputs, reasoning, decision, confidence, trace_id, job_id). Index: trace_id.
- **reflections**: Job-Reflexionen (outcome, quality, went_well, went_wrong, learnings, optional embedding). Indizes: job_id, quality.
- **playbooks**: Domain → strategy, evidence, success_rate, version. Kein expliziter Index auf domain (Tabellenscan).
- **quality_scores**: job_id, workflow_id, score, dimension, notes.
- **research_findings**: project_id, finding_key, content_preview, embedding_json, url, title, relevance/reliability/verification/evidence_count/critic/importance, **admission_state** (accepted|quarantined|rejected).
- **memory_admission_events**: project_id, finding_key, decision, reason, scores_json.
- **strategic_principles**: principle_type, description, domain, source_project_id, evidence_json, metric_score, usage_count, success_count, **embedding_json** (optional, wird in search nicht genutzt).
- **memory_utility**: (memory_type, memory_id) → utility_score, retrieval_count, helpful_count. Laplace-artig: utility = (helpful_count+1)/(retrieval_count+2) nach update_from_outcome.
- **run_episodes** (v2): project_id (UNIQUE), question, domain, status, plan_query_mix_json, source_mix_json, gate_metrics_json, critic_score, user_verdict, fail_codes_json, what_helped_json, what_hurt_json, strategy_profile_id, memory_mode, strategy_confidence, verified_claim_count, claim_support_rate.
- **strategy_profiles**: name, domain, policy_json, score, confidence, usage_count, success_count, fail_count, status, version, metadata_json.
- **strategy_application_events**, **memory_decision_log**, **memory_graph_edges**, **source_domain_stats_v2**, **read_urls** (question_hash, url).

**Probleme (Schema):**
- run_episodes.id = hash(project_id) → **INSERT OR REPLACE**: nur ein Episode pro Projekt; jeder neue Run überschreibt den vorherigen. Kein Verlauf mehrerer Runs pro Projekt in run_episodes (nur der letzte bleibt). Das schränkt „similar past runs“ auf den letzten Run pro Projekt ein.
- playbooks: Kein Index auf domain → Abfragen nach Domain durchscannen die Tabelle.
- strategic_principles: embedding_json wird nirgends für Suche verwendet (siehe unten).

---

## Teil 3: Retrieval und Suche — Was wirklich passiert

### 3.1 Episodes / Reflections (search.py)

- **search_episodes**: SQL LIKE mit AND über alle Suchbegriffe auf `content`; ORDER BY ts DESC. Rein **keyword**, keine Embeddings.
- **search_reflections**: LIKE mit OR über outcome, learnings, went_well, went_wrong (pro Term 4× Parameter); keyword-only.

### 3.2 Research Findings (research_findings.py)

- **get_accepted**: admission_state = 'accepted', nach ts DESC.
- **search_by_query**: Accepted findings, **alle** Suchbegriffe müssen in content_preview **oder** title vorkommen (AND über Terme), ORDER BY ts DESC. Keine semantische Suche, kein embedding_json-Einsatz hier.

### 3.3 Principles (principles.py)

- **search**: Keyword LIKE auf description (AND über Terme), optional domain, principle_type; ORDER BY metric_score DESC, created_at DESC. **embedding_json wird nicht verwendet** — trotz Schema und Docstring „EvolveR-style“ ist die Suche rein lexikalisch.

### 3.4 Utility-ranked retrieval (__init__.py + utility.py)

- **retrieve_with_utility(query, memory_type, k)**:
  1. Kandidaten: principles.search(query, limit=k*5) / search_reflections(conn, query, k*5) / research_findings.search_by_query(query, k*5) — alles **keyword**.
  2. Pro Kandidat: utility_score aus memory_utility (default 0.5), relevance aus relevance_score/relevance (default 0.5).
  3. combined_score = 0.4 * relevance + 0.6 * utility_score; sortieren; Top-k.
- **record_retrieval**: Wird von `research_knowledge_seed.py` aufgerufen, wenn Principles/Findings für ein Projekt geladen werden (retrieval_count wird erhöht).
- **update_from_outcome**: Nach Projektende (research_utility_update.py) mit critic_score; helpful = outcome_score >= 0.7; utility_score = (helpful_count+1)/(retrieval_count+2).

**Probleme (Retrieval):**
- Nirgends echte **semantische Suche** (Embeddings): research_findings.embedding_json, strategic_principles.embedding_json und episodes/reflections.embedding sind entweder ungenutzt oder nur für andere Zwecke (z. B. Cross-Links). Die Docstrings erwähnen „semantic retrieval“ — aktuell ist alles keyword-basiert.
- Utility ist rein **reaktiv**: Nur wenn knowledge_seed läuft, wird record_retrieval getriggert; nur wenn utility_update läuft, wird utility_score aktualisiert. Fehlt einer der Schritte, bleibt utility bei 0.5.
- combined_score 0.4/0.6 ist fest; keine Lerngewichte, keine A/B-Metriken.

---

## Teil 4: Memory v2 — Strategy Selection und Learning

### 4.1 select_strategy(question, domain) — Ablauf

1. **Kandidaten**: list_strategy_profiles(domain, limit=20); dann **Fail-Code-Filter**: _strategy_fail_code_blocked(id, domain) — für Domains wie biomedical/clinical/medical werden Strategien ausgeschlossen, die in run_episodes mit z. B. safety_filter_block in fail_codes_json vorkommen.
2. **Signale**:
   - **Similar episodes**: _similar_episode_signals(question, domain) — bis zu 40 run_episodes (nach domain gefiltert), Jaccard-Overlap (q_tokens & other_tokens) / |union|; Overlap ≥ 0.12 zählt als „similar“. similar_count + recency (exponentiell mit age_days/30, dann normalisiert). **Einschränkung**: run_episodes hat nur einen Eintrag pro project_id (INSERT OR REPLACE), d. h. „40 Episodes“ sind 40 verschiedene Projekte, nicht 40 Runs desselben Themas.
3. **Scoring pro Kandidat**:
   - lexical = |q_tokens ∩ policy_tokens| / |q_tokens| (Policy als JSON-String getokenized).
   - causal_score, what_hurt_penalty = _causal_signal(strategy_id, domain, question, domain) aus Episodes die diese Strategy in dieser Domain hatten: what_hurt/what_helped/critic_score; Hurt-Overlap mit Frage → penalty -0.2.
   - combined = 0.40*score + 0.20*lexical + 0.20*causal + 0.10*similar_norm + 0.10*recency; +0.05 wenn strategy.domain == domain.
4. **Gates**:
   - _strategy_domain_mismatch: Domain-Keywords (clinical, manufacturing, biomedical) — wenn Strategy-Domain spezifisch ist und Frage-Domain nicht dazu passt → return None.
   - **similar_episode_count == 0** → return None („strategy_skipped_no_similar_episodes“), um Cross-Topic-Leakage zu vermeiden.

**Woher kommen Strategy Profiles?**
- **research_experience_distiller.py**: Nach Projektende (success/fail). LLM liefert strategy_proposal mit policy (relevance_threshold, critic_threshold, revise_rounds, preferred_query_types, domain_rank_overrides, required_source_mix); Bounds 0.50–0.65, 1–4. upsert_strategy_profile(name, domain, policy, score=0.58/0.45, confidence=0.45). Es gibt **kein** direktes Lesen aus run_episodes für „welche Parameter haben funktioniert“ — die Policy kommt aus dem LLM-Output des Distillers.
- **research_utility_update.py**: update_strategy_from_outcome(strategy_profile_id, critic_pass, evidence_gate_pass, user_verdict, claim_support_rate, failed_quality_gate). Score wird um +0.05 (plus claim_support Bonus) oder -0.05/–0.08 (plus Zuschläge bei low claim_support/rejected) angepasst; confidence = 0.25 + 0.75 * min(50, total)/50.

**Probleme (Memory v2):**
- **run_episodes 1:1 pro Projekt**: Ähnlichkeit basiert auf „andere Projekte mit ähnlicher Frage“, nicht auf „mehrere Runs desselben Projekts“. Sobald ein Projekt ein zweites Mal durchläuft, wird der erste Episode überschrieben — similar_count kann nicht von mehreren Runs pro Projekt profitieren.
- **Similarity nur Jaccard auf Token**: Keine Embeddings; Themenverschiebung (z. B. „Klima“ vs „Energiepolitik“) wird nur über Wortüberlappung erfasst.
- **Strategy-Erstellung**: Distiller erfindet Policy per LLM; es gibt keine automatische **Ableitung** von Policy aus run_episodes (z. B. „in erfolgreichen Runs war relevance_threshold im Mittel 0.58“). Das ist eine verpasste Chance für datengetriebenes Tuning.
- **read_urls**: Dedup pro Frage (question_hash); gleiche Frage in anderer Formulierung nutzt anderen Hash → keine Dedup über Paraphrase.

---

## Teil 5: Research-Integration — Wo Memory geschrieben und gelesen wird

### 5.1 research_planner.py

- **Vor dem Plan**: _load_strategy_context(question, project_id) → Memory.select_strategy; Ergebnis (mode, selected_strategy, confidence_drivers, similar_episode_count) wird in _persist_strategy_context → `research/proj-*/memory_strategy.json` geschrieben.
- **Nach Plan-Erstellung**: _apply_strategy_to_plan(plan, strategy_ctx) — wenn v2_applied, werden Queries mit _resample_query_types an preferred_query_types der Policy angepasst (nur Query-Typ-Mix, keine Änderung an Inhalten).
- **Decision-Log**: record_memory_decision bei v2_disabled, no_strategy, low_confidence, v2_applied, db_error, exception.

### 5.2 research-cycle.sh

- **Anfang**: Liest memory_strategy.json; setzt RESEARCH_MEMORY_RELEVANCE_THRESHOLD, RESEARCH_MEMORY_CRITIC_THRESHOLD, RESEARCH_MEMORY_REVISE_ROUNDS, RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON aus policy (mit harten Bounds 0.50–0.65, 1–4).
- **Nach Run (terminal)**: Python-Block liest project.json, quality_gate, plan_mix, source_mix; record_run_episode mit strategy_profile_id, memory_mode, strategy_confidence aus memory_strategy.json; record_memory_decision; record_graph_edge (strategy_profile → run_episode); record_read_urls(question, urls aus sources).
- **Explore**: Vor parallel_reader wird read_order_round1.txt gegen get_read_urls_for_question gefiltert (URLs entfernt, die schon für diese Frage gelesen wurden).

### 5.3 research_memory_policy.py (Admission Gate)

- **decide(finding)**: accepted wenn reliability≥0.6, importance≥0.5, verification≠unverified; rejected wenn verification=unverified oder reliability<0.3; sonst quarantined. Nur accepted Findings fließen in get_research_findings_accepted und in Brain-Context/Knowledge-Seed.

### 5.4 research_experience_distiller.py

- Principles: LLM extrahiert Principles; Dedup per _dedup_principles; für jeden: search_principles → _llm_equivalent_to_existing → update_principle_usage_success/append_evidence oder insert_principle.
- Strategy: Aus strategy_proposal (LLM) wird policy mit Bounds gebaut; upsert_strategy_profile; record_memory_decision(strategy_proposed).

### 5.5 research_utility_update.py

- Liest prior_knowledge.json (principle_ids, finding_ids); critic_score aus project.json; strategy_profile_id aus memory_strategy.json. update_utilities_from_outcome(principle/finding, ids, critic_score); update_strategy_from_outcome(strategy_profile_id, …); source_domain_stats_v2 pro Quelle (verified/relevant/fail).

### 5.6 research_knowledge_seed.py

- retrieve_with_utility(question, principle, 5) und (question, finding, 10); record_retrieval für jede id; schreibt prior_knowledge.json (principles, findings, principle_ids, finding_ids). Wird vermutlich vor Explore aufgerufen (abhängig von Workflow).

**Probleme (Integration):**
- prior_knowledge / knowledge_seed / utility_update müssen in der richtigen Reihenfolge laufen; wenn knowledge_seed nicht läuft, gibt es keine record_retrieval → utility bleibt 0.5 für alle.
- Strategy wird nur aus memory_strategy.json gelesen, wenn die Datei beim Cycle-Start existiert; wird der Planner zweimal aufgerufen und überschreibt mit fallback, verliert der laufende Cycle die zuvor gewählte Strategy nicht (er hat schon die Env gesetzt), aber der nächste Cycle sieht Fallback.

---

## Teil 6: Brain Context Compiler (brain_context.py)

- **Mit query** (erste offene Research-Frage): retrieve_with_utility für reflection (k=10), finding (k=20), principle (k=5). Findings nach project_id gebucketed, max 5 pro Projekt, max 10 Projekte. Principles nach causal bevorzugt, dann metric_score.
- **Ohne query**: get_research_findings_accepted (statisch), recent_reflections (Quality ≥ 0.35), list_principles(10). Keine Utility-Berechnung.
- **Konstanten**: MAX_FINDINGS_PER_PROJECT=5, MAX_PROJECTS=10, MAX_REFLECTIONS=10, MIN_REFLECTION_QUALITY=0.35.

**Problem**: Wenn kein Research-Projekt offen ist, ist goal leer → query=None → statisches Retrieval. Utility wird dann für Think nicht genutzt.

---

## Teil 7: Wo wir SOTA oder novel ansetzen können

### 7.1 State of the Art (Einordnung)

- **Episodic Memory / Run-Memory**: Ihr run_episodes + strategy_profiles + memory_decision_log sind nah an „episodic control“ und „learning from outcomes“. SOTA wäre: mehrere Episoden pro Projekt/Run, temporale Abfolge, Option-Critic-ähnliche Updates.
- **Retrieval**: Aktuell rein keyword. SOTA: Dense Retrieval (Embeddings für principles, reflections, findings); Hybrid (keyword + semantic); RAG mit Re-Ranking (z. B. Cross-Encoder oder utility wie jetzt, aber mit semantic first stage).
- **Strategy Learning**: Policy kommt aus LLM (Distiller), nicht aus Daten. SOTA: Bandits/RL über diskrete Parameter (relevance_threshold, revise_rounds); Meta-Learning über Episoden; automatische Ableitung von policy aus erfolgreichen run_episodes (z. B. mittlere Schwellenwerte, Query-Type-Mix aus gate_metrics).
- **Utility**: Laplace-Smoothing (helpful_count/retrieval_count) ist einfach. SOTA: Kontextuelle Utility (nicht nur global pro memory_id, sondern „utility für dieses Projekt/Thema“); Thompson Sampling für Exploration.
- **Principles**: EvolveR-Style (guiding/cautionary) ist gut; Merge per LLM equivalent. SOTA: Embedding-basierte Dedup und Retrieval; Prinzipien mit strukturierten Bedingungen („when domain=medical, avoid …“).

### 7.2 Konkrete Verbesserungen (priorisiert)

1. **run_episodes als Verlauf**:  
   - Neues Schema: episode_id eindeutig (z. B. hash(project_id:run_timestamp)); project_id nicht UNIQUE.  
   - Similarity und causal_signal auf N vergangene Runs pro Thema/Domain; select_strategy kann „similar_episode_count“ aus echten ähnlichen Runs berechnen.

2. **Semantische Suche aktivieren**:  
   - principles.search und search_reflections/search_episodes um optionale Embedding-Suche erweitern (z. B. cosine similarity auf embedding_json / embedding); Fallback keyword.  
   - research_findings.search_by_query: erste Stufe semantic (wenn embedding_json vorhanden), zweite Stufe keyword; oder Hybrid-Score.

3. **Strategy aus Daten ableiten**:  
   - Aus run_episodes (domain, status=done, critic_score hoch) plan_query_mix_json, gate_metrics_json aggregieren → „empirically_best“ policy (Schwellen, Mix). Distiller kann diese als Vorschlag nutzen oder als zusätzlichen Kandidaten in select_strategy.

4. **read_urls mit Normalisierung**:  
   - Frage normalisieren (z. B. lowercase, Stoppwörter, Lemmatisierung) oder zusätzlich Embedding-basierten Cluster-Key für „semantisch gleiche Frage“ → weniger doppelt gelesene URLs bei leichten Formulierungsänderungen.

5. **Utility kontextabhängig**:  
   - memory_utility um (topic_domain oder question_hash) erweitern: „utility von principle P für Themen wie Q“. Retrieval dann: zuerst semantic/keyword Kandidaten, dann utility für aktuelles question/topic; combined_score mit kontextuellem utility.

6. **Explainability und Observability**:  
   - memory_decision_log bereits gut; erweitern um „retrieved_memory_ids“ pro Think/Plan (welche Principles/Findings flossen ein). UI: „Diese Decision basierte auf Principle X, Finding Y“.

7. **Novel**:  
   - **Causal Strategy Selection**: what_helped/what_hurt und fail_codes nicht nur als Penalty, sondern als strukturierte Features für ein kleines Modell (z. B. „bei diesen Frage-Features war Strategy A besser als B“) — leichte Form von Meta-Learning.  
   - **Contrastive Principles**: Prinzipien nicht nur „guiding/cautionary“, sondern „wenn Situation S, dann A vs B“ (kontrastiv), aus Paaren von Runs (einer gut, einer schlecht) ableiten.

---

## Teil 8: Kurz-Checkliste (Probleme)

| Bereich | Problem | Schwere |
|--------|---------|--------|
| run_episodes | 1 Episode pro Projekt (INSERT OR REPLACE) | hoch |
| Search | Keine echte semantische Suche; embedding_json ungenutzt | hoch |
| Utility | Nur reaktiv (seed + utility_update); 0.4/0.6 fest | mittel |
| Strategy | Policy nur aus LLM, nicht aus Episoden-Daten | mittel |
| read_urls | Nur exakter question_hash, keine Paraphrase | niedrig |
| Brain state | Truncation 12k kann Kontext verlieren | niedrig |
| Principles | causal in list_recent/search nicht durchgängig priorisiert (nur in compile) | niedrig |
| playbooks | Kein Index auf domain | niedrig |

---

Dieses Dokument sollte bei Änderungen an Brain, Memory, Research-Integration und Docs (UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK) mitgeführt werden.

**Weiterführend:** [MEMORY_BRAIN_WORLDCLASS_PLAN.md](MEMORY_BRAIN_WORLDCLASS_PLAN.md) — Wie SOTA/Novel-Systeme funktionieren und konkreter Phasenplan für ein weltklasse Memory- und Brain-System.
