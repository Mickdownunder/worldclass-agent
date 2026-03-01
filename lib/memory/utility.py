"""Utility-ranked retrieval (MemRL-inspired): Laplace-smoothed utility scores on memories."""
import sqlite3

from .common import utcnow


class UtilityTracker:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record_retrieval(self, memory_type: str, memory_id: str, context_key: str | None = None) -> None:
        """Called when a memory is retrieved for use in a project."""
        self._conn.execute(
            """INSERT INTO memory_utility (memory_type, memory_id, utility_score, retrieval_count, helpful_count, last_updated)
               VALUES (?, ?, 0.5, 1, 0, ?)
               ON CONFLICT(memory_type, memory_id) DO UPDATE SET
                   retrieval_count = retrieval_count + 1,
                   last_updated = ?""",
            (memory_type, memory_id, utcnow(), utcnow()),
        )
        if context_key:
            ck = str(context_key).strip().lower()[:180]
            self._conn.execute(
                """INSERT INTO memory_utility_context
                   (memory_type, memory_id, context_key, utility_score, retrieval_count, helpful_count, last_updated)
                   VALUES (?, ?, ?, 0.5, 1, 0, ?)
                   ON CONFLICT(memory_type, memory_id, context_key) DO UPDATE SET
                     retrieval_count = retrieval_count + 1,
                     last_updated = ?""",
                (memory_type, memory_id, ck, utcnow(), utcnow()),
            )
        self._conn.commit()

    def get_top_utility(self, memory_type: str | None = None, limit: int = 50) -> list[dict]:
        """Get the most helpful memories ranked by utility score."""
        if memory_type:
            rows = self._conn.execute(
                """SELECT memory_type, memory_id, utility_score, retrieval_count, helpful_count, last_updated
                   FROM memory_utility
                   WHERE memory_type = ?
                   ORDER BY utility_score DESC, retrieval_count DESC LIMIT ?""",
                (memory_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT memory_type, memory_id, utility_score, retrieval_count, helpful_count, last_updated
                   FROM memory_utility
                   ORDER BY utility_score DESC, retrieval_count DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, memory_type: str, memory_id: str, context_key: str | None = None) -> dict | None:
        if context_key:
            ck = str(context_key).strip().lower()[:180]
            row = self._conn.execute(
                """SELECT memory_type, memory_id, utility_score, retrieval_count, helpful_count, last_updated
                   FROM memory_utility_context
                   WHERE memory_type = ? AND memory_id = ? AND context_key = ?""",
                (memory_type, memory_id, ck),
            ).fetchone()
            if row:
                return dict(row)
        row = self._conn.execute(
            "SELECT * FROM memory_utility WHERE memory_type = ? AND memory_id = ?",
            (memory_type, memory_id),
        ).fetchone()
        return dict(row) if row else None

    def update_from_outcome(
        self,
        memory_type: str,
        memory_ids: list[str],
        outcome_score: float,
        context_key: str | None = None,
    ) -> None:
        """Called after project completion. outcome_score = critic_score; helpful if >= 0.7."""
        helpful = outcome_score >= 0.7
        ck = str(context_key).strip().lower()[:180] if context_key else ""
        for mid in memory_ids:
            row = self._conn.execute(
                "SELECT retrieval_count, helpful_count FROM memory_utility WHERE memory_type = ? AND memory_id = ?",
                (memory_type, mid),
            ).fetchone()
            if not row:
                continue
            retrieval_count = row["retrieval_count"]
            helpful_count = row["helpful_count"] + (1 if helpful else 0)
            utility_score = (helpful_count + 1) / (retrieval_count + 2)
            self._conn.execute(
                """UPDATE memory_utility SET helpful_count = ?, utility_score = ?, last_updated = ?
                   WHERE memory_type = ? AND memory_id = ?""",
                (helpful_count, utility_score, utcnow(), memory_type, mid),
            )
            if ck:
                crow = self._conn.execute(
                    """SELECT retrieval_count, helpful_count FROM memory_utility_context
                       WHERE memory_type = ? AND memory_id = ? AND context_key = ?""",
                    (memory_type, mid, ck),
                ).fetchone()
                if crow:
                    cretrieval = crow["retrieval_count"]
                    chelpful = crow["helpful_count"] + (1 if helpful else 0)
                    cscore = (chelpful + 1) / (cretrieval + 2)
                    self._conn.execute(
                        """UPDATE memory_utility_context
                           SET helpful_count = ?, utility_score = ?, last_updated = ?
                           WHERE memory_type = ? AND memory_id = ? AND context_key = ?""",
                        (chelpful, cscore, utcnow(), memory_type, mid, ck),
                    )
        self._conn.commit()
