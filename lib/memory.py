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

import json
import sqlite3
import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / "operator" / "memory" / "operator.db"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class Memory:
    def __init__(self, db_path: Path | str | None = None):
        self._path = Path(db_path) if db_path else DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          TEXT PRIMARY KEY,
                ts          TEXT NOT NULL,
                kind        TEXT NOT NULL,
                job_id      TEXT,
                workflow_id TEXT,
                content     TEXT NOT NULL,
                metadata    TEXT DEFAULT '{}',
                embedding   BLOB
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id          TEXT PRIMARY KEY,
                ts          TEXT NOT NULL,
                phase       TEXT NOT NULL,
                inputs      TEXT NOT NULL,
                reasoning   TEXT NOT NULL,
                decision    TEXT NOT NULL,
                confidence  REAL NOT NULL DEFAULT 0.5,
                trace_id    TEXT,
                job_id      TEXT,
                metadata    TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS reflections (
                id          TEXT PRIMARY KEY,
                ts          TEXT NOT NULL,
                job_id      TEXT NOT NULL,
                workflow_id TEXT,
                goal        TEXT,
                outcome     TEXT NOT NULL,
                went_well   TEXT,
                went_wrong  TEXT,
                learnings   TEXT,
                quality     REAL NOT NULL DEFAULT 0.5,
                metadata    TEXT DEFAULT '{}',
                embedding   BLOB
            );

            CREATE TABLE IF NOT EXISTS playbooks (
                id          TEXT PRIMARY KEY,
                ts_created  TEXT NOT NULL,
                ts_updated  TEXT NOT NULL,
                domain      TEXT NOT NULL,
                strategy    TEXT NOT NULL,
                evidence    TEXT DEFAULT '[]',
                success_rate REAL DEFAULT 0.0,
                version     INTEGER DEFAULT 1,
                metadata    TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS quality_scores (
                id          TEXT PRIMARY KEY,
                ts          TEXT NOT NULL,
                job_id      TEXT NOT NULL,
                workflow_id TEXT,
                score       REAL NOT NULL,
                dimension   TEXT DEFAULT 'overall',
                notes       TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_episodes_kind ON episodes(kind);
            CREATE INDEX IF NOT EXISTS idx_episodes_job ON episodes(job_id);
            CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_reflections_job ON reflections(job_id);
            CREATE INDEX IF NOT EXISTS idx_reflections_quality ON reflections(quality DESC);
            CREATE INDEX IF NOT EXISTS idx_decisions_trace ON decisions(trace_id);
            CREATE INDEX IF NOT EXISTS idx_quality_workflow ON quality_scores(workflow_id);

            CREATE TABLE IF NOT EXISTS research_findings (
                id              TEXT PRIMARY KEY,
                project_id      TEXT NOT NULL,
                finding_key     TEXT NOT NULL,
                content_preview  TEXT NOT NULL,
                embedding_json  TEXT,
                ts              TEXT NOT NULL,
                url             TEXT,
                title           TEXT
            );
            CREATE TABLE IF NOT EXISTS cross_links (
                id              TEXT PRIMARY KEY,
                finding_a_id    TEXT NOT NULL,
                finding_b_id    TEXT NOT NULL,
                project_a       TEXT NOT NULL,
                project_b       TEXT NOT NULL,
                similarity      REAL NOT NULL,
                ts              TEXT NOT NULL,
                notified        INTEGER DEFAULT 0,
                UNIQUE(finding_a_id, finding_b_id)
            );
            CREATE INDEX IF NOT EXISTS idx_research_findings_project ON research_findings(project_id);
            CREATE INDEX IF NOT EXISTS idx_cross_links_projects ON cross_links(project_a, project_b);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------

    def record_episode(
        self,
        kind: str,
        content: str,
        job_id: str | None = None,
        workflow_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        eid = _hash(f"{kind}:{content}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO episodes (id, ts, kind, job_id, workflow_id, content, metadata) VALUES (?,?,?,?,?,?,?)",
            (eid, _utcnow(), kind, job_id, workflow_id, content, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return eid

    def recent_episodes(self, limit: int = 20, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM episodes WHERE kind=? ORDER BY ts DESC LIMIT ?", (kind, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM episodes ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Decisions (Reasoning Traces)
    # ------------------------------------------------------------------

    def record_decision(
        self,
        phase: str,
        inputs: dict,
        reasoning: str,
        decision: str,
        confidence: float = 0.5,
        trace_id: str | None = None,
        job_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        did = _hash(f"decision:{phase}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO decisions (id, ts, phase, inputs, reasoning, decision, confidence, trace_id, job_id, metadata) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (did, _utcnow(), phase, json.dumps(inputs), reasoning, decision, confidence, trace_id, job_id, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return did

    def get_trace(self, trace_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM decisions WHERE trace_id=? ORDER BY ts", (trace_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_decisions(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM decisions ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Reflections
    # ------------------------------------------------------------------

    def record_reflection(
        self,
        job_id: str,
        outcome: str,
        quality: float,
        workflow_id: str | None = None,
        goal: str | None = None,
        went_well: str | None = None,
        went_wrong: str | None = None,
        learnings: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        rid = _hash(f"reflection:{job_id}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO reflections (id, ts, job_id, workflow_id, goal, outcome, went_well, went_wrong, learnings, quality, metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rid, _utcnow(), job_id, workflow_id, goal, outcome, went_well, went_wrong, learnings, quality, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return rid

    def recent_reflections(self, limit: int = 10, min_quality: float | None = None) -> list[dict]:
        if min_quality is not None:
            rows = self._conn.execute(
                "SELECT * FROM reflections WHERE quality >= ? ORDER BY ts DESC LIMIT ?",
                (min_quality, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM reflections ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def reflection_for_job(self, job_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM reflections WHERE job_id=? ORDER BY ts DESC LIMIT 1", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Playbooks (evolving strategies — ACE pattern)
    # ------------------------------------------------------------------

    def upsert_playbook(
        self,
        domain: str,
        strategy: str,
        evidence: list[str] | None = None,
        success_rate: float = 0.0,
    ) -> str:
        existing = self._conn.execute(
            "SELECT * FROM playbooks WHERE domain=? ORDER BY version DESC LIMIT 1", (domain,)
        ).fetchone()

        now = _utcnow()
        if existing:
            new_version = existing["version"] + 1
            pid = _hash(f"playbook:{domain}:{new_version}")
            old_evidence = json.loads(existing["evidence"]) if existing["evidence"] else []
            merged_evidence = list(set(old_evidence + (evidence or [])))[-20:]
            self._conn.execute(
                "INSERT INTO playbooks (id, ts_created, ts_updated, domain, strategy, evidence, success_rate, version) VALUES (?,?,?,?,?,?,?,?)",
                (pid, existing["ts_created"], now, domain, strategy, json.dumps(merged_evidence), success_rate, new_version),
            )
        else:
            pid = _hash(f"playbook:{domain}:1")
            self._conn.execute(
                "INSERT INTO playbooks (id, ts_created, ts_updated, domain, strategy, evidence, success_rate, version) VALUES (?,?,?,?,?,?,?,?)",
                (pid, now, now, domain, strategy, json.dumps(evidence or []), success_rate, 1),
            )
        self._conn.commit()
        return pid

    def get_playbook(self, domain: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM playbooks WHERE domain=? ORDER BY version DESC LIMIT 1", (domain,)
        ).fetchone()
        return dict(row) if row else None

    def all_playbooks(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM playbooks WHERE id IN (SELECT id FROM playbooks GROUP BY domain HAVING version = MAX(version)) ORDER BY domain"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Quality Tracking
    # ------------------------------------------------------------------

    def record_quality(
        self,
        job_id: str,
        score: float,
        workflow_id: str | None = None,
        dimension: str = "overall",
        notes: str = "",
    ) -> str:
        qid = _hash(f"quality:{job_id}:{dimension}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO quality_scores (id, ts, job_id, workflow_id, score, dimension, notes) VALUES (?,?,?,?,?,?,?)",
            (qid, _utcnow(), job_id, workflow_id, score, dimension, notes),
        )
        self._conn.commit()
        return qid

    def quality_trend(self, workflow_id: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM quality_scores WHERE workflow_id=? ORDER BY ts DESC LIMIT ?",
            (workflow_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def avg_quality(self, workflow_id: str | None = None) -> float:
        if workflow_id:
            row = self._conn.execute(
                "SELECT AVG(score) as avg_score FROM quality_scores WHERE workflow_id=?", (workflow_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT AVG(score) as avg_score FROM quality_scores").fetchone()
        return row["avg_score"] if row and row["avg_score"] is not None else 0.0

    # ------------------------------------------------------------------
    # Research: findings with embeddings, cross-domain links
    # ------------------------------------------------------------------

    def insert_research_finding(
        self,
        project_id: str,
        finding_key: str,
        content_preview: str,
        embedding_json: str | None = None,
        url: str | None = None,
        title: str | None = None,
    ) -> str:
        fid = _hash(f"rf:{project_id}:{finding_key}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO research_findings (id, project_id, finding_key, content_preview, embedding_json, ts, url, title) VALUES (?,?,?,?,?,?,?,?)",
            (fid, project_id, finding_key, content_preview[:4000], embedding_json, _utcnow(), url, title),
        )
        self._conn.commit()
        return fid

    def get_research_findings_with_embeddings(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, project_id, finding_key, content_preview, embedding_json, url, title FROM research_findings WHERE embedding_json IS NOT NULL AND embedding_json != ''"
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_cross_link(
        self,
        finding_a_id: str,
        finding_b_id: str,
        project_a: str,
        project_b: str,
        similarity: float,
    ) -> str:
        lid = _hash(f"cl:{finding_a_id}:{finding_b_id}:{time.time_ns()}")
        self._conn.execute(
            "INSERT OR IGNORE INTO cross_links (id, finding_a_id, finding_b_id, project_a, project_b, similarity, ts) VALUES (?,?,?,?,?,?,?)",
            (lid, finding_a_id, finding_b_id, project_a, project_b, similarity, _utcnow()),
        )
        self._conn.commit()
        return lid

    def get_cross_links_unnotified(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM cross_links WHERE notified = 0 ORDER BY similarity DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_cross_links_notified(self, link_ids: list[str]) -> None:
        for lid in link_ids:
            self._conn.execute("UPDATE cross_links SET notified = 1 WHERE id = ?", (lid,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Semantic Search (keyword fallback when no embeddings)
    # ------------------------------------------------------------------

    def search_episodes(self, query: str, limit: int = 10) -> list[dict]:
        terms = query.lower().split()
        conditions = " AND ".join(["LOWER(content) LIKE ?" for _ in terms])
        params = [f"%{t}%" for t in terms]
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM episodes WHERE {conditions} ORDER BY ts DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def search_reflections(self, query: str, limit: int = 10) -> list[dict]:
        terms = query.lower().split()
        conditions = " OR ".join([
            f"LOWER(outcome) LIKE ? OR LOWER(learnings) LIKE ? OR LOWER(went_well) LIKE ? OR LOWER(went_wrong) LIKE ?"
            for _ in terms
        ])
        params = []
        for t in terms:
            params.extend([f"%{t}%"] * 4)
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM reflections WHERE ({conditions}) ORDER BY ts DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # State Summary (used by the cognitive core to build perception)
    # ------------------------------------------------------------------

    def state_summary(self) -> dict:
        """Compact summary of current memory state for the cognitive core."""
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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
