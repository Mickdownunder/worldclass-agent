"""Episodes domain: raw events (job started, finished, etc.)."""
import json
import time
import sqlite3

from .common import utcnow, hash_id


class Episodes:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record(
        self,
        kind: str,
        content: str,
        job_id: str | None = None,
        workflow_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        eid = hash_id(f"{kind}:{content}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO episodes (id, ts, kind, job_id, workflow_id, content, metadata) VALUES (?,?,?,?,?,?,?)",
            (eid, utcnow(), kind, job_id, workflow_id, content, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return eid

    def recent(self, limit: int = 20, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM episodes WHERE kind=? ORDER BY ts DESC LIMIT ?", (kind, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM episodes ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
