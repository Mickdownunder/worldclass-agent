"""Project outcomes for calibration and distiller input."""
import json
import sqlite3

from .common import utcnow


def record_outcome(
    conn: sqlite3.Connection,
    project_id: str,
    domain: str | None = None,
    critic_score: float | None = None,
    user_verdict: str | None = None,
    gate_metrics_json: str | None = None,
    strategy_used: str | None = None,
    principles_used_json: str | None = None,
    findings_count: int | None = None,
    source_count: int | None = None,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO project_outcomes
           (project_id, domain, critic_score, user_verdict, gate_metrics_json, strategy_used, principles_used_json, findings_count, source_count, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            domain or "",
            critic_score,
            user_verdict or "none",
            gate_metrics_json or "{}",
            strategy_used or "",
            principles_used_json or "[]",
            findings_count,
            source_count,
            utcnow(),
        ),
    )
    conn.commit()


def get_successful_outcomes(conn: sqlite3.Connection, min_critic: float = 0.75, limit: int = 100) -> list[dict]:
    """Projects with critic_score >= min_critic and user_verdict != 'rejected'."""
    rows = conn.execute(
        """SELECT * FROM project_outcomes
           WHERE critic_score >= ? AND (user_verdict IS NULL OR user_verdict != 'rejected')
           ORDER BY completed_at DESC LIMIT ?""",
        (min_critic, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def count_outcomes(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) as c FROM project_outcomes").fetchone()
    return row["c"] if row else 0
