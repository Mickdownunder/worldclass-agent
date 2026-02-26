"""Playbooks domain: accumulated strategies (ACE pattern)."""
import json
import time
import sqlite3

from .common import utcnow, hash_id


class Playbooks:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert(
        self,
        domain: str,
        strategy: str,
        evidence: list[str] | None = None,
        success_rate: float = 0.0,
    ) -> str:
        existing = self._conn.execute(
            "SELECT * FROM playbooks WHERE domain=? ORDER BY version DESC LIMIT 1", (domain,)
        ).fetchone()

        now = utcnow()
        if existing:
            new_version = existing["version"] + 1
            pid = hash_id(f"playbook:{domain}:{new_version}")
            old_evidence = json.loads(existing["evidence"]) if existing["evidence"] else []
            merged_evidence = list(set(old_evidence + (evidence or [])))[-20:]
            self._conn.execute(
                "INSERT INTO playbooks (id, ts_created, ts_updated, domain, strategy, evidence, success_rate, version) VALUES (?,?,?,?,?,?,?,?)",
                (pid, existing["ts_created"], now, domain, strategy, json.dumps(merged_evidence), success_rate, new_version),
            )
        else:
            pid = hash_id(f"playbook:{domain}:1")
            self._conn.execute(
                "INSERT INTO playbooks (id, ts_created, ts_updated, domain, strategy, evidence, success_rate, version) VALUES (?,?,?,?,?,?,?,?)",
                (pid, now, now, domain, strategy, json.dumps(evidence or []), success_rate, 1),
            )
        self._conn.commit()
        return pid

    def get(self, domain: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM playbooks WHERE domain=? ORDER BY version DESC LIMIT 1", (domain,)
        ).fetchone()
        return dict(row) if row else None

    def all_latest(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM playbooks WHERE id IN (SELECT id FROM playbooks GROUP BY domain HAVING version = MAX(version)) ORDER BY domain"
        ).fetchall()
        return [dict(r) for r in rows]
