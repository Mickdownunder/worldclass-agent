"""Utility-ranked retrieval (MemRL-inspired): Laplace-smoothed utility scores on memories."""
import sqlite3

from .common import utcnow


class UtilityTracker:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record_retrieval(self, memory_type: str, memory_id: str) -> None:
        """Called when a memory is retrieved for use in a project."""
        self._conn.execute(
            """INSERT INTO memory_utility (memory_type, memory_id, utility_score, retrieval_count, helpful_count, last_updated)
               VALUES (?, ?, 0.5, 1, 0, ?)
               ON CONFLICT(memory_type, memory_id) DO UPDATE SET
                   retrieval_count = retrieval_count + 1,
                   last_updated = ?""",
            (memory_type, memory_id, utcnow(), utcnow()),
        )
        self._conn.commit()

    def get(self, memory_type: str, memory_id: str) -> dict | None:
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
    ) -> None:
        """Called after project completion. outcome_score = critic_score; helpful if >= 0.7."""
        helpful = outcome_score >= 0.7
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
        self._conn.commit()
