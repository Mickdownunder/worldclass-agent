"""Source credibility per domain (learned from verification outcomes)."""
import sqlite3

from .common import utcnow


def get(conn: sqlite3.Connection, domain: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM source_credibility WHERE domain = ?", (domain,)
    ).fetchone()
    return dict(row) if row else None


def list_all(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM source_credibility ORDER BY learned_credibility DESC, last_updated DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def update(
    conn: sqlite3.Connection,
    domain: str,
    times_used: int,
    verified_count: int,
    failed_verification_count: int,
) -> None:
    conn.execute(
        """INSERT INTO source_credibility (domain, times_used, verified_count, failed_verification_count, learned_credibility, last_updated)
           VALUES (?, ?, ?, ?, CAST(? + 1 AS REAL) / (? + 2), ?)
           ON CONFLICT(domain) DO UPDATE SET
               times_used = times_used + excluded.times_used,
               verified_count = verified_count + excluded.verified_count,
               failed_verification_count = failed_verification_count + excluded.failed_verification_count,
               learned_credibility = CAST(verified_count + excluded.verified_count + 1 AS REAL) / (times_used + excluded.times_used + 2),
               last_updated = excluded.last_updated""",
        (domain, times_used, verified_count, failed_verification_count, verified_count, times_used, utcnow()),
    )
    conn.commit()
