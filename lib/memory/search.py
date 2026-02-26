"""Semantic/keyword search over episodes and reflections."""
import sqlite3


def search_episodes(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    terms = query.lower().split()
    conditions = " AND ".join(["LOWER(content) LIKE ?" for _ in terms])
    params = [f"%{t}%" for t in terms]
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM episodes WHERE {conditions} ORDER BY ts DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def search_reflections(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    terms = query.lower().split()
    conditions = " OR ".join([
        "LOWER(outcome) LIKE ? OR LOWER(learnings) LIKE ? OR LOWER(went_well) LIKE ? OR LOWER(went_wrong) LIKE ?"
        for _ in terms
    ])
    params = []
    for t in terms:
        params.extend([f"%{t}%"] * 4)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM reflections WHERE ({conditions}) ORDER BY ts DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
