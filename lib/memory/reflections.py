"""Reflections domain: post-action evaluations with quality and learnings."""
import json
import time
import sqlite3

from .common import utcnow, hash_id


class Reflections:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record(
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
        rid = hash_id(f"reflection:{job_id}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO reflections (id, ts, job_id, workflow_id, goal, outcome, went_well, went_wrong, learnings, quality, metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rid, utcnow(), job_id, workflow_id, goal, outcome, went_well, went_wrong, learnings, quality, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return rid

    def recent(self, limit: int = 10, min_quality: float | None = None) -> list[dict]:
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

    def for_job(self, job_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM reflections WHERE job_id=? ORDER BY ts DESC LIMIT 1", (job_id,)
        ).fetchone()
        return dict(row) if row else None
