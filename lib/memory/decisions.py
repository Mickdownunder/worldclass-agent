"""Decisions domain: reasoning traces with inputs, reasoning, confidence."""
import json
import time
import sqlite3

from .common import utcnow, hash_id


class Decisions:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record(
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
        did = hash_id(f"decision:{phase}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO decisions (id, ts, phase, inputs, reasoning, decision, confidence, trace_id, job_id, metadata) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (did, utcnow(), phase, json.dumps(inputs), reasoning, decision, confidence, trace_id, job_id, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return did

    def get_trace(self, trace_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM decisions WHERE trace_id=? ORDER BY ts", (trace_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM decisions ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
