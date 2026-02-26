"""Quality scores domain."""
import time
import sqlite3

from .common import utcnow, hash_id


class Quality:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record(
        self,
        job_id: str,
        score: float,
        workflow_id: str | None = None,
        dimension: str = "overall",
        notes: str = "",
    ) -> str:
        qid = hash_id(f"quality:{job_id}:{dimension}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO quality_scores (id, ts, job_id, workflow_id, score, dimension, notes) VALUES (?,?,?,?,?,?,?)",
            (qid, utcnow(), job_id, workflow_id, score, dimension, notes),
        )
        self._conn.commit()
        return qid

    def trend(self, workflow_id: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM quality_scores WHERE workflow_id=? ORDER BY ts DESC LIMIT ?",
            (workflow_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def avg(self, workflow_id: str | None = None) -> float:
        if workflow_id:
            row = self._conn.execute(
                "SELECT AVG(score) as avg_score FROM quality_scores WHERE workflow_id=?", (workflow_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT AVG(score) as avg_score FROM quality_scores").fetchone()
        return row["avg_score"] if row and row["avg_score"] is not None else 0.0
