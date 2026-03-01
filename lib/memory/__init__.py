"""
Structured Memory System for the Operator.

Implements a multi-tier memory architecture:
  - Episodes:  Raw events (job started, job finished, error occurred)
  - Decisions: Reasoning traces with inputs, reasoning, confidence
  - Reflections: Post-action evaluations with quality scores and learnings
  - Playbooks: Accumulated strategies that evolve through experience (ACE pattern)

Storage: SQLite with optional OpenAI embeddings for semantic retrieval.
Falls back to keyword search when embeddings unavailable.
"""

from pathlib import Path

from .schema import init_schema
from .episodes import Episodes
from .decisions import Decisions
from .reflections import Reflections
from .playbooks import Playbooks
from .quality import Quality
from .research_findings import ResearchFindings
from .entities import Entities
from .principles import Principles
from .utility import UtilityTracker
from . import search as search_module
from . import outcomes as outcomes_module
from . import source_credibility as source_credibility_module
from .memory_v2 import MemoryV2

import json as _json
import os as _os
DB_PATH = Path(_os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator"))) / "memory" / "operator.db"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _embed_query(text: str) -> list[float] | None:
    """Return query embedding vector or None if disabled/failed. Used for hybrid semantic retrieval."""
    if not (text or "").strip() or _os.environ.get("RESEARCH_MEMORY_SEMANTIC", "1") == "0":
        return None
    try:
        api_key = _os.environ.get("OPENAI_API_KEY")
        if not api_key:
            conf = Path(_os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator"))) / "conf" / "secrets.env"
            if conf.exists():
                for line in conf.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY=") and "=" in line:
                        api_key = line.split("=", 1)[1].strip().strip('"\'')
                        break
        if not api_key:
            return None
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.embeddings.create(input=(text or "")[:8000], model=EMBEDDING_MODEL)
        if r.data and len(r.data) > 0:
            return list(r.data[0].embedding)
    except Exception:
        pass
    return None


class Memory:
    def __init__(self, db_path: Path | str | None = None):
        self._path = Path(db_path) if db_path else DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        init_schema(self._conn)

        self._episodes = Episodes(self._conn)
        self._decisions = Decisions(self._conn)
        self._reflections = Reflections(self._conn)
        self._playbooks = Playbooks(self._conn)
        self._quality = Quality(self._conn)
        self._research = ResearchFindings(self._conn)
        self._entities = Entities(self._conn)
        self._principles = Principles(self._conn)
        self._utility = UtilityTracker(self._conn)
        self._v2 = MemoryV2(self._conn)

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------
    def record_episode(self, kind: str, content: str, job_id: str | None = None, workflow_id: str | None = None, metadata: dict | None = None) -> str:
        return self._episodes.record(kind, content, job_id, workflow_id, metadata)

    def recent_episodes(self, limit: int = 20, kind: str | None = None) -> list[dict]:
        return self._episodes.recent(limit, kind)

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------
    def record_decision(self, phase: str, inputs: dict, reasoning: str, decision: str, confidence: float = 0.5, trace_id: str | None = None, job_id: str | None = None, metadata: dict | None = None) -> str:
        return self._decisions.record(phase, inputs, reasoning, decision, confidence, trace_id, job_id, metadata)

    def get_trace(self, trace_id: str) -> list[dict]:
        return self._decisions.get_trace(trace_id)

    def recent_decisions(self, limit: int = 10) -> list[dict]:
        return self._decisions.recent(limit)

    # ------------------------------------------------------------------
    # Reflections
    # ------------------------------------------------------------------
    def record_reflection(self, job_id: str, outcome: str, quality: float, workflow_id: str | None = None, goal: str | None = None, went_well: str | None = None, went_wrong: str | None = None, learnings: str | None = None, metadata: dict | None = None) -> str:
        return self._reflections.record(job_id, outcome, quality, workflow_id, goal, went_well, went_wrong, learnings, metadata)

    def recent_reflections(self, limit: int = 10, min_quality: float | None = None) -> list[dict]:
        return self._reflections.recent(limit, min_quality)

    def reflection_for_job(self, job_id: str) -> dict | None:
        return self._reflections.for_job(job_id)

    # ------------------------------------------------------------------
    # Playbooks
    # ------------------------------------------------------------------
    def upsert_playbook(self, domain: str, strategy: str, evidence: list[str] | None = None, success_rate: float = 0.0) -> str:
        return self._playbooks.upsert(domain, strategy, evidence, success_rate)

    def get_playbook(self, domain: str) -> dict | None:
        return self._playbooks.get(domain)

    def all_playbooks(self) -> list[dict]:
        return self._playbooks.all_latest()

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------
    def record_quality(self, job_id: str, score: float, workflow_id: str | None = None, dimension: str = "overall", notes: str = "") -> str:
        return self._quality.record(job_id, score, workflow_id, dimension, notes)

    def quality_trend(self, workflow_id: str, limit: int = 20) -> list[dict]:
        return self._quality.trend(workflow_id, limit)

    def avg_quality(self, workflow_id: str | None = None) -> float:
        return self._quality.avg(workflow_id)

    # ------------------------------------------------------------------
    # Research findings
    # ------------------------------------------------------------------
    def insert_research_finding(self, project_id: str, finding_key: str, content_preview: str, embedding_json: str | None = None, url: str | None = None, title: str | None = None, relevance_score: float | None = None, reliability_score: float | None = None, verification_status: str | None = None, evidence_count: int | None = None, critic_score: float | None = None, importance_score: float | None = None, admission_state: str | None = None) -> str:
        return self._research.insert(project_id, finding_key, content_preview, embedding_json, url, title, relevance_score, reliability_score, verification_status, evidence_count, critic_score, importance_score, admission_state)

    def record_admission_event(self, project_id: str, finding_key: str, decision: str, reason: str = "", scores: dict | None = None) -> str:
        return self._research.record_admission_event(project_id, finding_key, decision, reason, scores)

    def get_research_findings_with_embeddings(self) -> list[dict]:
        return self._research.get_with_embeddings()

    def get_research_findings_accepted(self, project_id: str | None = None, limit: int = 200) -> list[dict]:
        return self._research.get_accepted(project_id, limit)

    def insert_cross_link(self, finding_a_id: str, finding_b_id: str, project_a: str, project_b: str, similarity: float) -> str:
        return self._research.insert_cross_link(finding_a_id, finding_b_id, project_a, project_b, similarity)

    def get_cross_links_unnotified(self, limit: int = 50) -> list[dict]:
        return self._research.get_cross_links_unnotified(limit)

    def mark_cross_links_notified(self, link_ids: list[str]) -> None:
        return self._research.mark_cross_links_notified(link_ids)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------
    def get_or_create_entity(self, name: str, entity_type: str, properties: dict | None = None, first_seen_project: str | None = None) -> str:
        return self._entities.get_or_create(name, entity_type, properties, first_seen_project)

    def insert_entity_relation(self, entity_a_id: str, entity_b_id: str, relation_type: str, source_project: str, evidence: str = "") -> str:
        return self._entities.insert_relation(entity_a_id, entity_b_id, relation_type, source_project, evidence)

    def insert_entity_mention(self, entity_id: str, project_id: str, finding_key: str | None = None, context_snippet: str = "") -> str:
        return self._entities.insert_mention(entity_id, project_id, finding_key, context_snippet)

    def get_entities(self, entity_type: str | None = None, project_id: str | None = None, limit: int = 100) -> list[dict]:
        return self._entities.get(entity_type, project_id, limit)

    def get_entity_relations(self, project_id: str | None = None, limit: int = 50) -> list[dict]:
        return self._entities.get_relations(project_id, limit)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search_episodes(self, query: str, limit: int = 10) -> list[dict]:
        return search_module.search_episodes(self._conn, query, limit)

    def search_reflections(self, query: str, limit: int = 10) -> list[dict]:
        return search_module.search_reflections(self._conn, query, limit)

    # ------------------------------------------------------------------
    # Strategic principles (EvolveR-style)
    # ------------------------------------------------------------------
    def search_principles(self, query: str, limit: int = 10, domain: str | None = None, principle_type: str | None = None) -> list[dict]:
        return self._principles.search(query, limit, domain, principle_type)

    def list_principles(self, limit: int = 50, domain: str | None = None) -> list[dict]:
        return self._principles.list_recent(limit, domain)

    def get_principle(self, principle_id: str) -> dict | None:
        return self._principles.get(principle_id)

    def insert_principle(
        self,
        principle_type: str,
        description: str,
        source_project_id: str,
        domain: str | None = None,
        evidence_json: str = "[]",
        metric_score: float = 0.5,
        embedding_json: str | None = None,
    ) -> str:
        return self._principles.insert(
            principle_type, description, source_project_id, domain, evidence_json, metric_score, embedding_json
        )

    def update_principle_usage_success(self, principle_id: str, success: bool) -> None:
        self._principles.update_usage_success(principle_id, success)

    def append_principle_evidence(self, principle_id: str, source_project_id: str, evidence_snippet: str) -> None:
        self._principles.append_evidence(principle_id, source_project_id, evidence_snippet)

    # ------------------------------------------------------------------
    # Utility-ranked retrieval (MemRL-inspired)
    # ------------------------------------------------------------------
    def record_retrieval(self, memory_type: str, memory_id: str, context_key: str | None = None) -> None:
        self._utility.record_retrieval(memory_type, memory_id, context_key=context_key)

    def retrieve_with_utility(self, query: str, memory_type: str, k: int = 10, context_key: str | None = None) -> list[dict]:
        """Phase 1: semantic/keyword candidates. Phase 2: utility re-rank.
        Findings are filtered by query (keyword match) so discovery and standard runs
        only get topic-relevant prior knowledge. When RESEARCH_MEMORY_SEMANTIC=1 and
        OPENAI_API_KEY is set, principles/findings with embedding_json use cosine similarity."""
        ctx = (context_key or query or "").strip().lower()[:180]
        try:
            lam = float(_os.environ.get("RESEARCH_MEMORY_UTILITY_LAMBDA", "0.6"))
        except Exception:
            lam = 0.6
        lam = max(0.1, min(0.9, lam))
        query_embedding = _embed_query(query or "")
        if memory_type == "principle":
            candidates = self._principles.search(query, limit=k * 5, query_embedding=query_embedding)
        elif memory_type == "reflection":
            candidates = search_module.search_reflections(self._conn, query, limit=k * 5)
        elif memory_type == "finding":
            candidates = self._research.search_by_query(query, limit=k * 5, query_embedding=query_embedding)
        else:
            return []

        for c in candidates:
            mid = c.get("id")
            if not mid:
                continue
            util_row = self._utility.get(memory_type, mid, context_key=ctx or None)
            util_score = util_row["utility_score"] if util_row else 0.5
            c["utility_score"] = util_score
            similarity = c.get("similarity_score", c.get("relevance_score", c.get("relevance", 0.5)))
            if not isinstance(similarity, (int, float)):
                similarity = 0.5
            c["similarity_score"] = float(similarity)
            c["combined_score"] = round((1.0 - lam) * float(similarity) + lam * float(util_score), 6)

        candidates.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
        selected = candidates[:k]
        # Record retrieval for every memory actually selected into context.
        for c in selected:
            mid = c.get("id")
            if mid:
                self._utility.record_retrieval(memory_type, str(mid), context_key=ctx or None)
        return selected

    def update_utilities_from_outcome(
        self,
        memory_type: str,
        memory_ids: list[str],
        outcome_score: float,
        context_key: str | None = None,
    ) -> None:
        self._utility.update_from_outcome(memory_type, memory_ids, outcome_score, context_key=context_key)

    # ------------------------------------------------------------------
    # Project outcomes
    # ------------------------------------------------------------------
    def record_project_outcome(
        self,
        project_id: str,
        domain: str | None = None,
        critic_score: float | None = None,
        user_verdict: str | None = None,
        gate_metrics_json: str | None = None,
        strategy_used: str | None = None,
        principles_used_json: str | None = None,
        findings_count: int | None = None,
        source_count: int | None = None,
    ) -> None:
        outcomes_module.record_outcome(
            self._conn,
            project_id,
            domain,
            critic_score,
            user_verdict,
            gate_metrics_json,
            strategy_used,
            principles_used_json,
            findings_count,
            source_count,
        )

    def get_successful_outcomes(self, min_critic: float = 0.75, limit: int = 100) -> list[dict]:
        return outcomes_module.get_successful_outcomes(self._conn, min_critic, limit)

    def list_project_outcomes(self, limit: int = 100) -> list[dict]:
        return outcomes_module.list_outcomes(self._conn, limit)

    def count_project_outcomes(self) -> int:
        return outcomes_module.count_outcomes(self._conn)

    # ------------------------------------------------------------------
    # Source credibility (per-domain, from verification outcomes)
    # ------------------------------------------------------------------
    def get_source_credibility(self, domain: str) -> dict | None:
        return source_credibility_module.get(self._conn, domain)

    def list_source_credibility(self, limit: int = 50) -> list[dict]:
        return source_credibility_module.list_all(self._conn, limit)

    def update_source_credibility(
        self,
        domain: str,
        times_used: int,
        verified_count: int,
        failed_verification_count: int,
    ) -> None:
        source_credibility_module.update(self._conn, domain, times_used, verified_count, failed_verification_count)

    # ------------------------------------------------------------------
    # Memory v2
    # ------------------------------------------------------------------
    def record_run_episode(
        self,
        project_id: str,
        question: str,
        domain: str,
        status: str,
        plan_query_mix: dict | None = None,
        source_mix: dict | None = None,
        gate_metrics: dict | None = None,
        critic_score: float | None = None,
        user_verdict: str | None = None,
        fail_codes: list[str] | None = None,
        what_helped: list[str] | None = None,
        what_hurt: list[str] | None = None,
        strategy_profile_id: str | None = None,
        memory_mode: str | None = None,
        strategy_confidence: float | None = None,
        verified_claim_count: int | None = None,
        claim_support_rate: float | None = None,
    ) -> str:
        return self._v2.record_run_episode(
            project_id=project_id,
            question=question,
            domain=domain,
            status=status,
            plan_query_mix=plan_query_mix,
            source_mix=source_mix,
            gate_metrics=gate_metrics,
            critic_score=critic_score,
            user_verdict=user_verdict,
            fail_codes=fail_codes,
            what_helped=what_helped,
            what_hurt=what_hurt,
            strategy_profile_id=strategy_profile_id,
            memory_mode=memory_mode,
            strategy_confidence=strategy_confidence,
            verified_claim_count=verified_claim_count,
            claim_support_rate=claim_support_rate,
        )

    def get_memory_value_score(self) -> dict:
        """Memory Value: avg(critic) applied - avg(critic) fallback. Does memory help?"""
        return self._v2.get_memory_value_score()

    def upsert_strategy_profile(
        self,
        name: str,
        domain: str,
        policy: dict,
        score: float = 0.5,
        confidence: float = 0.5,
        status: str = "active",
        version: int = 1,
        metadata: dict | None = None,
    ) -> str:
        return self._v2.upsert_strategy_profile(
            name=name,
            domain=domain,
            policy=policy,
            score=score,
            confidence=confidence,
            status=status,
            version=version,
            metadata=metadata,
        )

    def list_strategy_profiles(self, domain: str | None = None, limit: int = 20) -> list[dict]:
        return self._v2.list_strategy_profiles(domain=domain, limit=limit)

    def select_strategy(self, question: str, domain: str | None = None) -> dict | None:
        return self._v2.select_strategy(question=question, domain=domain)

    def record_strategy_application_event(
        self,
        project_id: str,
        phase: str,
        strategy_profile_id: str | None,
        applied_policy: dict | None = None,
        fallback_used: bool = False,
        outcome_hint: str = "",
        status: str = "ok",
    ) -> str:
        return self._v2.record_strategy_application_event(
            project_id=project_id,
            phase=phase,
            strategy_profile_id=strategy_profile_id,
            applied_policy=applied_policy,
            fallback_used=fallback_used,
            outcome_hint=outcome_hint,
            status=status,
        )

    def record_memory_decision(
        self,
        decision_type: str,
        details: dict,
        project_id: str | None = None,
        phase: str | None = None,
        strategy_profile_id: str | None = None,
        confidence: float = 0.5,
    ) -> str:
        return self._v2.record_memory_decision(
            decision_type=decision_type,
            details=details,
            project_id=project_id,
            phase=phase,
            strategy_profile_id=strategy_profile_id,
            confidence=confidence,
        )

    def record_graph_edge(
        self,
        edge_type: str,
        from_node_type: str,
        from_node_id: str,
        to_node_type: str,
        to_node_id: str,
        project_id: str | None = None,
    ) -> str:
        return self._v2.record_graph_edge(
            edge_type=edge_type,
            from_node_type=from_node_type,
            from_node_id=from_node_id,
            to_node_type=to_node_type,
            to_node_id=to_node_id,
            project_id=project_id,
        )

    def get_episode_ids_for_strategy(
        self, strategy_profile_id: str, domain: str | None = None, limit: int = 50
    ) -> list[str]:
        """Episodes linked to this strategy via graph (used_in). Used in strategy selection and causal signal."""
        return self._v2.get_episode_ids_for_strategy(
            strategy_profile_id=strategy_profile_id, domain=domain, limit=limit
        )

    def update_source_domain_stats_v2(
        self,
        domain: str,
        topic_domain: str,
        times_seen: int = 1,
        verified_hits: int = 0,
        relevant_hits: int = 0,
        fail_hits: int = 0,
    ) -> None:
        self._v2.update_source_domain_stats_v2(
            domain=domain,
            topic_domain=topic_domain,
            times_seen=times_seen,
            verified_hits=verified_hits,
            relevant_hits=relevant_hits,
            fail_hits=fail_hits,
        )

    def list_source_domain_stats_v2(self, topic_domain: str, limit: int = 30) -> list[dict]:
        return self._v2.list_source_domain_stats_v2(topic_domain=topic_domain, limit=limit)

    def update_strategy_from_outcome(
        self,
        strategy_profile_id: str,
        critic_pass: bool,
        evidence_gate_pass: bool,
        user_verdict: str = "none",
        claim_support_rate: float | None = None,
        failed_quality_gate: bool = False,
    ) -> None:
        self._v2.update_strategy_from_outcome(
            strategy_profile_id=strategy_profile_id,
            critic_pass=critic_pass,
            evidence_gate_pass=evidence_gate_pass,
            user_verdict=user_verdict,
            claim_support_rate=claim_support_rate,
            failed_quality_gate=failed_quality_gate,
        )

    def upsert_empirical_strategy(self, domain: str, min_samples: int = 3) -> str | None:
        return self._v2.upsert_empirical_strategy(domain=domain, min_samples=min_samples)

    def synthesize_principles_from_episodes(self, domain: str, min_count: int = 3) -> list[str]:
        return self._v2.synthesize_principles_from_episodes(domain=domain, min_count=min_count)

    def summarize_query_type_mix(self, queries: list[dict]) -> dict[str, float]:
        return self._v2.summarize_query_type_mix(queries=queries)

    def record_read_urls(self, question: str, urls: list[str]) -> None:
        """Store read URLs for this question so future runs can skip them (source dedup)."""
        self._v2.record_read_urls(question=question, urls=urls)

    def get_read_urls_for_question(self, question: str) -> set[str]:
        """Return set of URLs already read for this question (for skip/dedup)."""
        return self._v2.get_read_urls_for_question(question=question)

    def list_memory_decisions(self, project_id: str | None = None, limit: int = 50) -> list[dict]:
        return self._v2.list_memory_decisions(project_id=project_id, limit=limit)

    def list_strategy_profiles(self, domain: str | None = None, limit: int = 20) -> list[dict]:
        return self._v2.list_strategy_profiles(domain=domain, limit=limit)

    def get_top_utility(self, memory_type: str | None = None, limit: int = 50) -> list[dict]:
        return self._utility.get_top_utility(memory_type=memory_type, limit=limit)

    def get_graph_edges(self, from_node_type: str | None = None, to_node_type: str | None = None, limit: int = 100) -> list[dict]:
        sql = "SELECT from_node_type, from_node_id, to_node_type, to_node_id, project_id, ts FROM memory_graph_edges WHERE 1=1"
        params = []
        if from_node_type:
            sql += " AND from_node_type = ?"
            params.append(from_node_type)
        if to_node_type:
            sql += " AND to_node_type = ?"
            params.append(to_node_type)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = [dict(r) for r in self._conn.execute(sql, tuple(params)).fetchall()]
        strategy_ids = list({r["from_node_id"] for r in rows if r.get("from_node_type") == "strategy_profile"})
        name_by_id = {}
        if strategy_ids:
            placeholders = ",".join("?" * len(strategy_ids))
            for row in self._conn.execute(
                f"SELECT id, name, domain FROM strategy_profiles WHERE id IN ({placeholders})",
                strategy_ids,
            ).fetchall():
                name_by_id[row["id"]] = {"name": row["name"], "domain": row["domain"]}
        for r in rows:
            if r.get("from_node_type") == "strategy_profile":
                info = name_by_id.get(r["from_node_id"]) or {}
                r["strategy_name"] = info.get("name")
                r["strategy_domain"] = info.get("domain")
        return rows

    # ------------------------------------------------------------------
    # State summary
    # ------------------------------------------------------------------
    def state_summary(self) -> dict:
        total_episodes = self._conn.execute("SELECT COUNT(*) as c FROM episodes").fetchone()["c"]
        total_decisions = self._conn.execute("SELECT COUNT(*) as c FROM decisions").fetchone()["c"]
        total_reflections = self._conn.execute("SELECT COUNT(*) as c FROM reflections").fetchone()["c"]
        avg_q = self.avg_quality()
        recent_eps = self.recent_episodes(limit=5)
        recent_refs = self.recent_reflections(limit=3)
        playbooks = self.all_playbooks()
        recent_failures = self._conn.execute(
            "SELECT * FROM reflections WHERE quality < 0.4 ORDER BY ts DESC LIMIT 3"
        ).fetchall()
        total_principles = self._conn.execute("SELECT COUNT(*) as c FROM strategic_principles").fetchone()["c"]
        total_outcomes = self.count_project_outcomes()
        try:
            total_run_episodes = self._conn.execute("SELECT COUNT(*) as c FROM run_episodes").fetchone()["c"]
        except Exception:
            total_run_episodes = 0
        memory_value = self._v2.get_memory_value_score()
        try:
            recent_run_rows = self._conn.execute(
                """SELECT id, project_id, question, domain, status, critic_score,
                          what_helped_json, what_hurt_json, strategy_profile_id, run_index, created_at, memory_mode
                   FROM run_episodes ORDER BY created_at DESC LIMIT 20"""
            ).fetchall()
        except Exception:
            recent_run_rows = []
        def _run_episode_row(r) -> dict:
            q = (r["question"] or "")[:100]
            helped_raw = r["what_helped_json"] or "[]"
            hurt_raw = r["what_hurt_json"] or "[]"
            try:
                helped = _json.loads(helped_raw) if isinstance(helped_raw, str) else helped_raw
                hurt = _json.loads(hurt_raw) if isinstance(hurt_raw, str) else hurt_raw
            except Exception:
                helped, hurt = [], []
            helped_preview = ", ".join(str(x)[:40] for x in (helped[:2] if isinstance(helped, list) else [])) or "—"
            hurt_preview = ", ".join(str(x)[:40] for x in (hurt[:2] if isinstance(hurt, list) else [])) or "—"
            return {
                "id": r["id"],
                "project_id": r["project_id"],
                "question": q,
                "domain": r["domain"] or "—",
                "status": r["status"],
                "critic_score": round(r["critic_score"], 3) if r["critic_score"] is not None else None,
                "what_helped": helped_preview,
                "what_hurt": hurt_preview,
                "strategy_profile_id": r["strategy_profile_id"],
                "run_index": r["run_index"],
                "created_at": r["created_at"],
                "memory_mode": r["memory_mode"],
            }
        recent_run_episodes = [_run_episode_row(dict(r)) for r in recent_run_rows]
        consolidation = None
        try:
            cpath = self._path.parent / "consolidation_last.json"
            if cpath.exists():
                consolidation = _json.loads(cpath.read_text())
        except Exception:
            pass

        return {
            "totals": {
                "episodes": total_episodes,
                "decisions": total_decisions,
                "reflections": total_reflections,
                "avg_quality": round(avg_q, 3),
                "principles": total_principles,
                "outcomes": total_outcomes,
                "run_episodes": total_run_episodes,
                "memory_value": memory_value,
            },
            "recent_episodes": [{"kind": e["kind"], "content": e["content"][:120], "ts": e["ts"]} for e in recent_eps],
            "recent_run_episodes": recent_run_episodes,
            "consolidation": consolidation,
            "recent_reflections": [
                {"job_id": r["job_id"], "quality": r["quality"], "learnings": (r["learnings"] or "")[:150], "ts": r["ts"]}
                for r in recent_refs
            ],
            "recent_failures": [
                {"job_id": dict(r)["job_id"], "went_wrong": (dict(r)["went_wrong"] or "")[:150], "ts": dict(r)["ts"]}
                for r in recent_failures
            ],
            "playbooks": [{"domain": p["domain"], "strategy": p["strategy"][:150], "success_rate": p["success_rate"]} for p in playbooks],
        }

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
