# Full AEM Implementation Spec — Bruchfreie Umsetzung

Dieses Dokument verknüpft den **Full AEM Aggressive Implementation Plan** und das **Intelligence-Per-Token System Design** mit der bestehenden Operator-Codebasis und definiert die exakte Umsetzung **ohne Brüche** im laufenden System.

**Quellen:**

- **Plan:** `.cursor/plans/full-aem-aggressive-rollout_9ee51cde.plan.md`
- **Design (nicht übersehen):** `operator/docs/INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md` — Zielfunktion, Architektur (Control/Knowledge/Execution Plane), Question Graph, Claim Lifecycle, Attack Taxonomy, Evidence System, Reopen Protocol, Token-Governor, Metriken, Failure Modes, Minimal Viable Core, Akzeptanzregeln für Features.

---

## 0. Intelligence-Per-Token Design (Referenz)

Das Dokument **INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md** ist verbindliche Referenz für Ziel und Architektur:

- **Zielfunktion:**  
  `IntelligencePerToken = (InformationGain * EvidenceQuality * DecisionUtility) / TotalTokens`  
  Jede Komponente muss diese Funktion verbessern.

- **Design-Prinzipien:** Question-first, Evidence-first, Delta-only compute, Gate-driven expensive reasoning, Claims müssen Falsifikationsdruck überstehen, Memory mit Lifecycle (decay, reopen, retire), Qualität pro Token statt Antwortlänge.

- **Architektur-Ebenen:**
  - **Control Plane:** Orchestrator, Policy Router, Token Governor, Reopen Engine.
  - **Knowledge Plane:** Question Graph, Evidence Store, Claim Ledger, Trajectory Store, Strategy Memory.
  - **Execution Plane:** Explore, Focus, Verify, Synthesis Engine.

- **Claim Lifecycle (State Machine):**  
  `proposed -> evidenced -> attacked -> defended -> stable -> decaying -> contested -> falsified -> retired`  
  (Plan ergänzt: PASS_STABLE / PASS_TENTATIVE / FAIL am Falsification Gate; RETIRE mit reason code.)

- **Attack Taxonomy (Skeptic Scaffolding):** Assumption, Measurement, Mechanism, External-validity, Incentive/confound, Temporal drift, Ontology/definition — mit attack_strength, defense_strength, unresolved_residual.

- **Evidence System:** evidence_id, source_url, source_type, reliability_score, novelty_score, cross_claim_impact, extract_quality, reuse_count; Novelty Gate, Primary-Evidence Bias.

- **Reopen-Trigger:** Strong contradiction, Decay threshold, Domain shock, Ontology change.

- **Token-Efficiency:** Budget-Layer (global, phase, claim-level, reserve), Model-Routing (cheap/mid/strong), Delta-only compute, Hard-Stop-Kriterien.

- **Metriken:** information_gain_per_cycle, uncertainty_reduction_per_question, unsupported_statement_rate, tokens_per_verified_claim, tokens_per_resolved_question, cost_per_information_gain_unit, u. a.

- **Minimal Viable Core (Priorität):** 1) Question Graph, 2) Claim State Machine, 3) Attack Taxonomy, 4) Reopen Protocol, 5) Token Governor.

- **Akzeptanzregel für neue Features:** Nur akzeptieren, wenn Information-Gain-per-Token steigt, unsupported statements sinken und tokens_per_resolved_question nicht steigen.

- **Zusätzliches Modul aus Design (im Spec berücksichtigen):** `research_novelty_gate.py` (Novelty Gate für Evidence).

- **UI aus Design:** Question Board (state + uncertainty), Claim Lifecycle Timeline, Belief Trajectory Panel, Token Efficiency Dashboard, Reopen Event Feed — in Abschnitt 7 (UI/API) abgedeckt.

---

## 1. Ist-Zustand (Relevante Touchpoints)

### 1.1 Phasen und Workflow

- **Script:** `operator/workflows/research-cycle.sh`
- **Phasenreihenfolge:** `explore` → `focus` → `connect` → `verify` → `synthesize` → `done`
- **Phase `verify`:**
  - Führt aus: `research_verify.py` (source_reliability, claim_verification, fact_check, claim_ledger).
  - Schreibt nach: `$PROJ_DIR/verify/` (source_reliability.json, claim_verification.json, fact_check.json, claim_ledger.json).
  - Danach: **Evidence Gate** via `research_quality_gate.py`; bei Pass → `advance_phase "synthesize"` (Zeile 755).
- **Einschubstelle AEM:** **Nach** Evidence-Gate-Pass, **vor** `advance_phase "synthesize"` (zwischen Zeile 754 und 755).

### 1.2 Bestehende Artefakte (Projekt-Verzeichnis)

| Pfad | Verwendung |
|------|------------|
| `research/proj-*/project.json` | Phase, status, quality_gate, config |
| `research/proj-*/verify/claim_ledger.json` | `{ "claims": [ { "claim_id", "text", "supporting_source_ids", "is_verified", "verification_tier", "verification_reason" } ] }` |
| `research/proj-*/verify/claim_verification.json` | Roh-Claims von LLM (claim, supporting_sources, verified, …) |
| `research/proj-*/verify/source_reliability.json` | sources + reliability_score |
| `research/proj-*/verify/claim_evidence_map_latest.json` | Nach Synthese: claim_id → evidence |
| `research/proj-*/findings/*.json` | Findings (url, title, excerpt, …) |
| `research/proj-*/sources/*.json` | Quellen (url, title, …); `*_content.json` = Volltext |
| `research/proj-*/reports/*.md` | Reports |
| `research/proj-*/audit_log.jsonl` | Events (evidence_gate, claim_ledger_built, …) |

### 1.3 Claim-Ledger-Erzeugung (heute)

- **Modul:** `operator/tools/research_verify.py` → `build_claim_ledger()`
- **Eingabe:** `verify/claim_verification.json` + `verify/source_reliability.json`
- **Ausgabe:** `{ "claims": [ { "claim_id", "text", "supporting_source_ids", "is_verified", "verification_tier", "verification_reason" } ], "total_claims", "verified_count" }`
- **claim_id-Format:** `cl_{i}_{hash(claim[:100]) % 10000}`

### 1.4 Quality Gate (unverändert lassen)

- **Modul:** `operator/tools/research_quality_gate.py`
- Liest: `verify/claim_ledger.json`, `verify/source_reliability.json`, `findings/`, `sources/`, ggf. `explore/read_stats.json`
- **Nicht ersetzen**, nur um AEM erweitern (z. B. zusätzliche Metriken/Fail-Codes dokumentieren).

### 1.5 Synthese

- **Modul:** `operator/tools/research_synthesize.py`
- Liest u. a. `verify/claim_ledger.json` für Claims und Tagging.
- **Kompatibilität:** Synthese muss weiter funktionieren, wenn nur `verify/claim_ledger.json` existiert (kein AEM); bei AEM optional aus erweitertem Ledger lesen.

### 1.6 UI/API

- **Research-Lib:** `operator/ui/src/lib/operator/research.ts` → `getAudit()` liest `verify/claim_evidence_map_latest.json` oder `verify/claim_ledger.json`.
- **API-Routen:** `operator/ui/src/app/api/research/projects/[id]/*` (progress, audit, report, findings, sources, …).

---

## 2. AEM-Artefakte und Pfad-Mapping

Der Plan sieht neue Ordner unter `research/proj-*/` vor. Damit bestehende Pipelines und UI nicht brechen, gelten folgende Konventionen.

### 2.1 Neue Verzeichnisse (nur bei AEM aktiv)

| Plan-Pfad | Tatsächlicher Pfad | Hinweis |
|-----------|--------------------|---------|
| `research/proj-*/questions/questions.json` | `research/proj-*/questions/questions.json` | Frage-Graph; optional, kann aus project.json + findings abgeleitet werden |
| `research/proj-*/claims/ledger.jsonl` | `research/proj-*/claims/ledger.jsonl` | Ein Claim pro Zeile (JSONL); erweiterte Felder |
| `research/proj-*/attacks/attacks.jsonl` | `research/proj-*/attacks/attacks.jsonl` | Attack-Log |
| `research/proj-*/trajectories/belief_paths.jsonl` | `research/proj-*/trajectories/belief_paths.jsonl` | Belief-Trajektorien |
| `research/proj-*/evidence/evidence_index.jsonl` | `research/proj-*/evidence/evidence_index.jsonl` | Evidence-Index mit Unabhängigkeit/Scope |
| `research/proj-*/market/settlements.jsonl` | `research/proj-*/market/settlements.jsonl` | Settlements |
| `research/proj-*/portfolio/portfolio_state.json` | `research/proj-*/portfolio/portfolio_state.json` | Portfolio-State |
| `research/proj-*/policy/episode_metrics.jsonl` | `research/proj-*/policy/episode_metrics.jsonl` | IG/Token-Telemetrie |
| `research/proj-*/contracts/claim_outcome_schema.json` | `research/proj-*/contracts/claim_outcome_schema.json` | Claim-Outcome-Schema (Projekt oder global) |

### 2.2 Rückwärtskompatibilität: Ledger

- **Weiter schreiben:** `verify/claim_ledger.json` wie bisher (von `research_verify.py`).
- **AEM:** Liest `verify/claim_ledger.json` (und ggf. `verify/claim_verification.json`), schreibt erweiterte Einträge nach `claims/ledger.jsonl`.
- **Synthesize:**  
  - **Fall 1 (ohne AEM):** wie heute nur `verify/claim_ledger.json`.  
  - **Fall 2 (mit AEM):** wenn `claims/ledger.jsonl` existiert und nicht leer ist → Claims für Report/Tags daraus lesen; sonst Fallback `verify/claim_ledger.json`.
- **UI/Audit:** Audit-Daten weiter aus `verify/claim_evidence_map_latest.json` oder `verify/claim_ledger.json` liefern; optional zusätzliche API für AEM (Trajectory, Unresolved Attacks, Token-Efficiency) später.

---

## 3. Verträge (Data Contracts) — Erweiterungen

### 3.1 claim_outcome_schema (neu: contracts/claim_outcome_schema.json)

Laut Plan v1:

- `resolution_authority`: `internal_auditor | external_source | benchmark_suite | panel`
- `audit_trace_required`: boolean
- `allowed_evidence_types`: list
- `oracle_failure_modes`: list

Projekt-spezifisch unter `research/proj-*/contracts/` oder global unter `operator/contracts/claim_outcome_schema.json` (von Tools geladen).

**Verbindliche v1-Pflichtfelder pro Claim (deterministisch):**

- `claim_ref`: `claim_id@claim_version`
- `outcome_type`: `binary|numeric|interval|categorical|ranking|explanatory`
- `resolution_method`: `event|dataset|audit_panel|benchmark|manual`
- `resolution_authority`: `internal_auditor|external_source|benchmark_suite|panel`
- `resolution_horizon`: ISO-8601 Datum oder `unknown`
- `settlement_confidence`: float `[0.0, 1.0]`
- `audit_trace_required`: boolean
- `allowed_evidence_types`: string[]
- `oracle_failure_modes`: string[]

**Validierungsregeln (muss in `research_claim_outcome_schema.py` enforced werden):**

1. `resolution_authority=panel` oder `resolution_method=manual` **erfordert** `audit_trace_required=true`.
2. `settlement_confidence < 0.5` darf **nie** zu `PASS_STABLE` führen.
3. Wenn verwendete Evidenz nicht in `allowed_evidence_types` liegt, muss Settlement auf `PASS_TENTATIVE` oder `FAIL`.
4. Fehlendes oder ungültiges Outcome-Schema für einen Claim blockiert dessen Settlement (Claim bleibt `contested`/`tentative`).

### 3.2 ledger.jsonl (claims/ledger.jsonl)

Pro Zeile ein JSON-Objekt. Zusätzlich zu bestehenden Feldern (claim_id, text, supporting_source_ids, is_verified, verification_tier, verification_reason):

- `claim_version`, `supersedes`
- `tentative_ttl`, `tentative_cycles_used`
- `retire_reason`: `UNRESOLVABLE_NOW | ILL_POSED | OUT_OF_SCOPE | NORMATIVE_NON_SETTLEABLE | SUPERSEDED`
- `reopen_allowed`, `reopen_conditions`
- `claim_scope`: `{ population, geography, timeframe, domain }`
- `contradicts`: `[ { claim_ref, contradiction_strength } ]`
- strukturierte `failure_boundary`

**Migration:** Ein erster AEM-Lauf kann `verify/claim_ledger.json` → `claims/ledger.jsonl` konvertieren (ein Eintrag pro Claim, gleiche IDs), mit Defaults für neue Felder.

### 3.3 attacks.jsonl, settlements.jsonl, episode_metrics.jsonl, evidence_index.jsonl

Feld-Spezifikationen siehe Plan (Abschnitt „Contract upgrades required in v1“). Bei Implementierung der jeweiligen Module exakt umsetzen.

**Zusätzliche Pflichtfelder für deterministische Auswertung:**

- `settlements.jsonl`:
  - `decision`: `PASS_STABLE|PASS_TENTATIVE|FAIL`
  - `oracle_integrity_pass`: boolean
  - `contradiction_review_required`: boolean
  - `claim_ref`: `claim_id@version`
- `episode_metrics.jsonl`:
  - `ig_mode`: `entropy|proxy`
  - `false_collapse_rate`
  - `evidence_delta`
- `attacks.jsonl`:
  - `attack_class`
  - `attack_weight`
  - `selected_for_gate`: boolean
- `evidence_index.jsonl`:
  - `evidence_scope` + `scope_overlap_score`

---

## 4. Workflow-Änderung: research-cycle.sh

### 4.1 Einfügen des AEM-Blocks (nach Evidence-Gate-Pass, vor advance_phase synthesize)

**Datei:** `operator/workflows/research-cycle.sh`  
**Position:** Nach dem Block, der mit `# Update source credibility from verify outcomes` endet (Zeile 752–754), **vor** `advance_phase "synthesize"` (Zeile 755).

**Exakter Einfügepunkt:** zwischen Zeile 754 und 755 (nach `python3 "$TOOLS/research_source_credibility.py" ...` und vor `advance_phase "synthesize"`).

**Einzufügender Block:**

```bash
    # AEM Settlement (optional; when tools present): upgrade ledger, run settlement, write AEM artifacts
    if [ -f "$TOOLS/research_claim_outcome_schema.py" ] && [ -f "$TOOLS/research_episode_metrics.py" ]; then
      progress_step "AEM settlement"
      python3 "$TOOLS/research_aem_settlement.py" "$PROJECT_ID" 2>> "$PWD/log.txt" || true
    fi
    # Evidence gate passed — advance to synthesize
    advance_phase "synthesize"
```

- `research_aem_settlement.py` wird als **ein** Einstiegspunkt eingeführt: er orchestriert intern Schema, Ledger-Upgrade, Triage, Falsification Gate, Settlement, Portfolio, Episode-Metrics, Reopen, Token-Governor (in Rollout-Reihenfolge).
- Fehler in AEM werden **policy-gesteuert** behandelt (nicht pauschal fail-open):
  - `AEM_ENFORCEMENT_MODE=observe` (Default v1 bootstrap): fail-open erlaubt, Fehler nur loggen, Synthese mit Fallback-Ledger.
  - `AEM_ENFORCEMENT_MODE=enforce`: fail-closed für `PASS_STABLE`-abhängige Claims; nur `PASS_TENTATIVE`-Claims dürfen mit Defizit-Markierung in Synthese.
  - `AEM_ENFORCEMENT_MODE=strict`: blockiert Synthese, wenn AEM-Settlement nicht ausführbar oder `oracle_integrity_rate` unter Schwelle fällt.
  - Modus muss in `project.json.config` oder Env explizit gesetzt werden; keine impliziten Defaults im Produktionsbetrieb.

### 4.2 Reopen-Pfade (später)

Plan: „reopen path branches“. Optionen:

- **A:** Neue Phase `reopen` zwischen verify und synthesize; bei Reopen-Trigger → `advance_phase "focus"` oder `advance_phase "connect"` statt synthesize.
- **B:** Reopen nur als Flag/Marker in project.json; nächster research-cycle prüft Flag und springt in passende Phase.

Erst nach Rollout der Kern-AEM-Module konkret festlegen; in Phase 1 kein Reopen-Branch nötig.

---

## 5. Neue Module (tools/) — Reihenfolge und Abhängigkeiten

Alle unter `operator/tools/`. Implementierung in dieser Reihenfolge (Rollout Sequence des Plans).

| Nr | Modul | Zweck | Abhängigkeiten |
|----|-------|--------|------------------|
| 1 | `research_claim_outcome_schema.py` | Schema + authority/auditability; schreibt `contracts/claim_outcome_schema.json` | — |
| 2 | `research_episode_metrics.py` | IG/Token-Telemetrie; schreibt `policy/episode_metrics.jsonl` | project.json, claims/ledger (wenn da) |
| 3 | `research_question_graph.py` | Frage-Graph; schreibt `questions/questions.json` | project.json, findings, verify |
| 4 | `research_claim_state_machine.py` | Lifecycle-State-Machine, Guards, Versioning | claim_outcome_schema, verify/claim_ledger |
| 5 | `research_claim_triage.py` | Top-K Impact; nur Top-K in tiefen AEM-Pfad | claims/ledger oder verify/claim_ledger |
| 6 | `research_attack_taxonomy.py` | Gewichtete Attack-Taxonomie (vgl. INTELLIGENCE_PER_TOKEN: attack classes, strength/defense/residual); schreibt `attacks/attacks.jsonl` | triaged claims |
| 7 | `research_falsification_gate.py` | PASS_STABLE / PASS_TENTATIVE / FAIL; deadlock-sichere Exits | attacks, ledger |
| 8 | `research_reopen_protocol.py` | Reopen-Trigger (Widerspruch, Decay, Shock, Ontology-Drift) — vgl. INTELLIGENCE_PER_TOKEN §8 | trajectory, ledger |
| 9 | `research_token_governor.py` | Modell-Routing (cheap/mid/strong), expected_ig_per_token, Budget-Layer — vgl. INTELLIGENCE_PER_TOKEN §9 | episode_metrics, triage |
| 10 | `research_market_scoring.py` | Settlement nach outcome type | ledger, claim_outcome_schema |
| 11 | `research_portfolio_scoring.py` | Anti-Gaming, evidence flooding penalty, duplicate penalty | ledger, evidence_index, market |
| 12 | `research_novelty_gate.py` | **Aus INTELLIGENCE_PER_TOKEN §7:** Novelty Gate (near-duplicate evidence ablehnen), Primary-Evidence Bias | findings, evidence_index |
| 13 | `research_aem_settlement.py` | **Orchestrator:** ruft 1–12 in sinnvoller Reihenfolge auf, schreibt alle AEM-Artefakte | alle obigen (optional, fallback wenn fehlend) |

### 5.1 Integration in research_quality_gate.py

- **Nicht ersetzen.** Optional: in `run_evidence_gate()` nach bestehender Logik AEM-Metriken auslesen (z. B. aus `policy/episode_metrics.jsonl`) und in `metrics` oder separatem Block zurückgeben; Fail-Codes wie `failed_insufficient_evidence` etc. unverändert.
- Neuer Fail-Code nur wenn gewünscht, z. B. `aem_deadlock` (Rate über Schwellwert) → in RESEARCH_QUALITY_SLO.md aufnehmen.

---

## 6. Synthese-Anpassung (research_synthesize.py)

### 6.1 Claim-Quelle (Dual Source)

- **Priorität 1:** Wenn `research/proj-*/claims/ledger.jsonl` existiert und mindestens eine Zeile hat: Claims daraus lesen (eine JSON-Zeile pro Claim; mind. claim_id, text, is_verified, verification_tier, supporting_source_ids).
- **Priorität 2:** Sonst wie bisher `verify/claim_ledger.json` → `get("claims", [])`.

### 6.2 Kompatibilitäts-Helfer (für research_synthesize.py und ggf. research_common.py)

Voraussetzung: `import json`, `from pathlib import Path`.

```python
def get_claims_for_synthesis(proj_path: Path) -> list[dict]:
    """Einheitliche Claim-Liste für Synthese: AEM ledger.jsonl oder Fallback verify/claim_ledger.json."""
    claims_dir = proj_path / "claims"
    ledger_jsonl = claims_dir / "ledger.jsonl"
    if ledger_jsonl.exists():
        claims = []
        for line in ledger_jsonl.read_text().strip().splitlines():
            if not line.strip():
                continue
            try:
                claims.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if claims:
            return claims
    verify_ledger = proj_path / "verify" / "claim_ledger.json"
    if verify_ledger.exists():
        try:
            data = json.loads(verify_ledger.read_text())
            return data.get("claims", [])
        except Exception:
            pass
    return []
```

- **research_synthesize.py:** Am Anfang (nach load_project) `claims = get_claims_for_synthesis(proj_path)` aufrufen und diese Liste für Sektionen und für `apply_verified_tags_to_report(report, claims)` verwenden. Bestehende Lade-Logik für `verify/claim_ledger.json` durch diesen Aufruf ersetzen.
- **Tagging:** `apply_verified_tags_to_report(report, claims)` unverändert; Liste aus `get_claims_for_synthesis`.
- **Synthesis-Contract (hart, verbindlich):**
  - Synthese darf **keine neuen Claims erzeugen**.
  - Jeder claim-bezogene Satz muss einen `claim_ref` besitzen, der in Ledger existiert.
  - Für jeden referenzierten Claim müssen mindestens folgende Felder verfügbar sein:
    - `state`
    - `failure_boundary`
    - `best_counter_evidence_ref` (oder explizit `null`)
    - Freshness/Decay-Status
    - `p_true` nur falls für Claim-Typ definiert
  - Wenn ein Claim ohne gültigen `claim_ref` auftaucht, muss der Synthese-Lauf mit Fehlerstatus abbrechen (kein stilles Durchrutschen).

### 6.3 Synthesis Gate vor Report-Freigabe

Vor finaler Report-Ausgabe müssen folgende Checks bestehen:

1. `unreferenced_claim_sentence_count == 0`
2. `new_claims_in_synthesis == 0`
3. Für `PASS_TENTATIVE`-Claims ist Tentative-Label im Output vorhanden.
4. Wenn `AEM_ENFORCEMENT_MODE=strict`, dann `oracle_integrity_rate >= threshold`.

---

## 7. UI/API-Erweiterungen (späterer Schritt)

Vgl. **INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md §12** (UI additions):

- **research.ts:** Keine Pflichtänderung für Phase 1. Optional: Hilfsfunktion `getAEMArtifacts(projectId)` für trajectory, attacks, episode_metrics (für Panels).
- **Neue API-Routen (optional):**  
  `GET /api/research/projects/[id]/trajectory`  
  `GET /api/research/projects/[id]/attacks`  
  `GET /api/research/projects/[id]/episode-metrics`  
  `GET /api/research/projects/[id]/questions` (Question Graph state + uncertainty)
- **UI-Panels aus Design-Doc (nach Stabilisierung der AEM-Module):**
  - **Question Board:** Fragen-State + Uncertainty (open/narrowed/partially_resolved/resolved/reopened)
  - **Claim Lifecycle Timeline:** Zustandsverlauf pro Claim (proposed → … → stable/retired)
  - **Belief Trajectory Panel:** belief_paths.jsonl / Trajectory Store
  - **Token Efficiency Dashboard:** tokens_per_verified_claim, tokens_per_resolved_question, cost_per_information_gain_unit (episode_metrics)
  - **Reopen Event Feed:** Reopen-Ereignisse (Widerspruch, Decay, Shock, Ontology)

---

## 8. Sicherheit und Kosten (Plan + INTELLIGENCE_PER_TOKEN)

- Pro-Phase Token-Caps und Fail-Safe: in `research-cycle.sh` und ggf. `research_budget.py` bereits vorhanden; AEM-Module sollen keine zusätzlichen unbounded LLM-Calls ohne Budget-Check.
- Delta-Recompute: nur geänderte Claims/Evidence/Questions verarbeiten (in Modul-Logik umsetzen).
- Keine langen Zwischen-Synthesen; strukturierte JSON/JSONL-Ausgaben.
- Evidence Gate bleibt finale Guardrail; AEM ergänzt epistemische Guardrails (falsification_gate, lifecycle, reopen).
- `attack_budget_exhausted` als explizites Defizit tracken/surfacing (z. B. in episode_metrics oder project.json).
- Tentative-Convergence: TTL/Budget in ledger-Einträgen; bei Erschöpfung FAIL oder RETIRE mit failure_boundary; Synthesize kann tentative Claims kennzeichnen.

### 8.1 Verbindliche IG/token-Berechnung (v1)

Um Goodharting zu vermeiden, ist IG/token für v1 wie folgt fixiert:

- Für `forecast|binary|categorical`:
  - `prior_entropy = -sum(p_i * log2(p_i))` über `belief_vector` im Question-Cluster
  - `posterior_entropy` analog nach Evidence-/Settlement-Update
  - `ig = prior_entropy - posterior_entropy`
  - `ig_mode = "entropy"`
- Für `structural|explanatory`:
  - `ig_proxy = disagreement_width_reduction + residual_reduction`
  - `ig = ig_proxy`
  - `ig_mode = "proxy"`
- `ig_per_token = ig / max(tokens_spent, 1)`
- `false_collapse_rate` muss mitgeführt werden:
  - Entropie-/Proxy-Reduktion ohne ausreichendes `evidence_delta` zählt als potenzieller Collapse.

Diese Formel darf nicht pro Modul frei interpretiert werden; sie ist zentral in `research_episode_metrics.py` zu implementieren.

**Failure Modes aus INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md §11** bei Implementierung berücksichtigen: Settlement-Oracle (Claim-Typing, Partial Settlement), Incentive Gaming (Portfolio Scoring, Novelty Bonus), False Precision (Confidence-Intervalle, Residual Unknown), Skeptic Asymmetry (Auto-Skeptic, Reward-Weighting), Decay Misconfiguration (domain-adaptive half-life), Policy Lock-in (Exploration-Quota, Novelty-Regularization), Ontology Drift, Evidence Poisoning, Benchmark Lock-in, Regime-Shift-Blindness.

---

## 9. Tests (Plan Testing Plan)

- Unit-Tests pro neuem Modul (State-Transitions, Scoring, Reopen, Governor-Routing) unter `operator/tests/` (z. B. `tests/research/test_aem_*.py`).
- Integration: Ein voller verify-Durchlauf mit AEM-Einschub und optional Reopen (wenn implementiert).
- Adversarial/Regression: Settlement-Orakel-Ambiguität, Gaming, Stale-Belief-Reopen, Overconfidence, Deadlock, Claim-Slicing, Evidence-Flooding, Widerspruch-Linking, Scope-Mismatch (siehe Plan).
- Token-Budget-Regression: Cost-Drift erkennen (z. B. in episode_metrics.jsonl auswerten).

---

## 10. Dokumentations-Sync (Workspace Rules)

Nach Umsetzung prüfen und anpassen:

- **INTELLIGENCE_PER_TOKEN_SYSTEM_DESIGN.md:** Verbindliche Referenz für Zielfunktion, Architektur, Lifecycle, Attack-Taxonomie, Evidence, Reopen, Token-Efficiency, Metriken, Failure Modes, Minimal Viable Core. Bei Änderungen an diesen Konzepten oder neuen Modulen (z. B. novelty_gate) prüfen, ob das Design-Doc ergänzt werden muss.
- **UI_OVERVIEW.md:** Falls neue Phase oder Tabs (Question Board, Claim Timeline, Trajectory, Token Efficiency, Reopen Feed) → Nav-Labels, Tabs, Datenfluss-Tabelle, API-Endpunkte.
- **RESEARCH_QUALITY_SLO.md:** Neue Fail-Codes (z. B. `aem_deadlock`), Schwellen (deadlock_rate, oracle_integrity_rate, tentative_convergence_rate), Pfade zu AEM-Skripten/Modulen, CI-Skripte.
- **RESEARCH_AUTONOMOUS.md:** Skript-Pfade, Env-Variablen (z. B. AEM_ENABLED), Cron/Scheduler (keine Änderung nötig, solange research-cycle.sh nur einen Block gewinnt).
- **SYSTEM_CHECK.md:** `op healthcheck`, `op job status` unverändert; ggf. Hinweis „AEM-Artefakte unter research/proj-*/claims|attacks|policy/“.

---

## 11. Rollout-Checkliste (Kurz)

**Minimal Viable Core (INTELLIGENCE_PER_TOKEN §13)** als erste Priorität: Question Graph, Claim State Machine, Attack Taxonomy, Reopen Protocol, Token Governor.

1. Contracts landen: `claim_outcome_schema` + `episode_metrics` (Struktur + Schreibpfade).
2. Question-Graph + Claim-State-Machine + Versioning (Ledger-Format ledger.jsonl); Lifecycle-Zustände wie Design-Doc §5.
3. Minimale Widerspruch-/Scope-Contracts (contradicts, claim_scope).
4. Triage + Attack-Taxonomie (inkl. attack classes aus Design §6).
5. Falsification Gate v2 (PASS_STABLE | PASS_TENTATIVE | FAIL).
6. Settlement nach outcome type + Portfolio-Scoring.
7. Belief-Trajectory + Reopen-Protokoll (Trigger wie Design §8).
8. Token-Governor mit expected_ig_per_token (Budget-Layer, Model-Routing wie Design §9).
9. Optional: Novelty Gate (research_novelty_gate.py) für Evidence.
10. research-cycle.sh: AEM-Block einfügen; research_aem_settlement.py als Einstieg.
11. Synthesize: Duale Quelle (claims/ledger.jsonl vs. verify/claim_ledger.json).
12. UI/API/Observability (Question Board, Claim Timeline, Trajectory, Token Dashboard, Reopen Feed) + finale Integration- und Adversarial-Tests.
13. Docs (UI_OVERVIEW, RESEARCH_QUALITY_SLO, RESEARCH_AUTONOMOUS, SYSTEM_CHECK, INTELLIGENCE_PER_TOKEN als Referenz) abgleichen.

---

## 12. Akzeptanzkriterien (Plan)

- Unsupported-Statement-Rate vs. Baseline sinkt.
- Höhere Unsicherheitsreduktion pro Frage.
- Stabile oder bessere Report-Qualität bei geringeren Tokens pro gelöster Frage.
- Reopen-Events korrekt getriggert und ohne Phasen-Deadlocks.
- Keine Regression in quality_gate Pass/Fail.
- Deadlock-Rate in AEM unter Schwellwert (z. B. ≤ 0.05).
- Adversarial-Coverage für High-Impact-Claims über Minimum.
- Trivial-Claim-Inflation nicht erhöht.
- Strong-Lane-Token mit positivem expected_ig_per_token vs. Mid-Lane.
- Oracle-Integrität über Schwellwert, gültige Audit-Traces.
- PASS_TENTATIVE innerhalb TTL zu STABLE oder sauber FAIL/RETIRE.

**Verbindliche v1-Startschwellen:**

- `oracle_integrity_rate >= 0.80` für STABLE-Settlements
- `tentative_convergence_rate >= 0.60` innerhalb TTL
- `deadlock_rate <= 0.05` (AEM cycles > N ohne Zustandsänderung)

Mit dieser Spec kann der Plan schrittweise und ohne Brüche im laufenden System umgesetzt werden.
