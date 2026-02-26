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
from . import search as search_module

DB_PATH = Path.home() / "operator" / "memory" / "operator.db"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


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
        return {
            "totals": {
                "episodes": total_episodes,
                "decisions": total_decisions,
                "reflections": total_reflections,
                "avg_quality": round(avg_q, 3),
            },
            "recent_episodes": [{"kind": e["kind"], "content": e["content"][:120], "ts": e["ts"]} for e in recent_eps],
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
