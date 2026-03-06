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

    def recent_for_planning(
        self,
        limit: int = 10,
        min_quality: float = 0.5,
        exclude_low_signal: bool = True,
        dedupe_outcome_prefix: int = 80,
    ) -> list[dict]:
        """Recent reflections suitable for planning: quality filter, drop low-signal, dedupe by (workflow, outcome prefix)."""
        rows = self._conn.execute(
            "SELECT * FROM reflections WHERE quality >= ? ORDER BY quality DESC, ts DESC LIMIT ?",
            (min_quality, limit * 6),  # fetch more for dedupe
        ).fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            if exclude_low_signal:
                try:
                    meta = json.loads(d.get("metadata") or "{}")
                    if meta.get("low_signal") is True:
                        continue
                except (TypeError, ValueError):
                    pass
            out.append(d)
        # Dedupe: one per (workflow_id, outcome_prefix), keep highest quality
        key_to_best: dict[tuple, dict] = {}
        for d in out:
            wf = ((d.get("workflow_id") or "").strip().lower()) or "unknown"
            outcome = ((d.get("outcome") or "").strip().lower())[:dedupe_outcome_prefix]
            key = (wf, outcome)
            if key not in key_to_best or (d.get("quality") or 0) > (key_to_best[key].get("quality") or 0):
                key_to_best[key] = d
        deduped = sorted(key_to_best.values(), key=lambda x: (-(x.get("quality") or 0), x.get("ts") or ""))
        return deduped[:limit]

    def for_job(self, job_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM reflections WHERE job_id=? ORDER BY ts DESC LIMIT 1", (job_id,)
        ).fetchone()
        return dict(row) if row else None
