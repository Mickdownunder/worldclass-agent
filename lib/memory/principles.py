"""Strategic principles (EvolveR-style): guiding and cautionary principles from trajectories."""
import json
import sqlite3

from .common import utcnow, hash_id


class Principles:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(
        self,
        principle_type: str,
        description: str,
        source_project_id: str,
        domain: str | None = None,
        evidence_json: str = "[]",
        metric_score: float = 0.5,
        embedding_json: str | None = None,
    ) -> str:
        pid = hash_id(f"sp:{source_project_id}:{description[:100]}:{utcnow()}")
        self._conn.execute(
            """INSERT INTO strategic_principles
               (id, principle_type, description, domain, source_project_id, evidence_json, metric_score, usage_count, success_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)""",
            (pid, principle_type, description, domain or "", source_project_id, evidence_json, metric_score, utcnow()),
        )
        if embedding_json:
            self._conn.execute("UPDATE strategic_principles SET embedding_json = ? WHERE id = ?", (embedding_json, pid))
        self._conn.commit()
        return pid

    def get(self, principle_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM strategic_principles WHERE id = ?", (principle_id,)).fetchone()
        return dict(row) if row else None

    def search(self, query: str, limit: int = 10, domain: str | None = None, principle_type: str | None = None) -> list[dict]:
        """Keyword search on description. Returns list of principles with id, description, metric_score, etc."""
        terms = query.lower().split()
        conditions = ["LOWER(description) LIKE ?" for _ in terms]
        params = [f"%{t}%" for t in terms]
        if domain:
            conditions.append("(domain = ? OR domain = '')")
            params.append(domain)
        if principle_type:
            conditions.append("principle_type = ?")
            params.append(principle_type)
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM strategic_principles WHERE {' AND '.join(conditions)} ORDER BY metric_score DESC, created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def list_recent(self, limit: int = 50, domain: str | None = None) -> list[dict]:
        if domain:
            rows = self._conn.execute(
                "SELECT * FROM strategic_principles WHERE domain = ? OR domain = '' ORDER BY metric_score DESC, created_at DESC LIMIT ?",
                (domain, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM strategic_principles ORDER BY metric_score DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_usage_success(self, principle_id: str, success: bool) -> None:
        row = self._conn.execute(
            "SELECT usage_count, success_count FROM strategic_principles WHERE id = ?", (principle_id,)
        ).fetchone()
        if not row:
            return
        usage = row["usage_count"] + 1
        success_count = row["success_count"] + (1 if success else 0)
        metric_score = (success_count + 1) / (usage + 2)
        self._conn.execute(
            "UPDATE strategic_principles SET usage_count = ?, success_count = ?, metric_score = ? WHERE id = ?",
            (usage, success_count, metric_score, principle_id),
        )
        self._conn.commit()

    def append_evidence(self, principle_id: str, source_project_id: str, evidence_snippet: str) -> None:
        """Append project evidence to principle (for merge)."""
        row = self._conn.execute(
            "SELECT evidence_json FROM strategic_principles WHERE id = ?", (principle_id,)
        ).fetchone()
        if not row:
            return
        try:
            evidence = json.loads(row["evidence_json"] or "[]")
        except Exception:
            evidence = []
        evidence.append({"project_id": source_project_id, "snippet": (evidence_snippet or "")[:500]})
        self._conn.execute(
            "UPDATE strategic_principles SET evidence_json = ? WHERE id = ?",
            (json.dumps(evidence[-20:]), principle_id),  # keep last 20
        )
        self._conn.commit()
