"""Semantic/keyword search over episodes and reflections."""
import re
import sqlite3


def search_episodes(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    terms = [t for t in re.findall(r"[a-z0-9]{3,}", (query or "").lower())]
    rows = conn.execute("SELECT * FROM episodes ORDER BY ts DESC LIMIT 500").fetchall()
    out: list[dict] = []
    for row in rows:
        d = dict(row)
        text = (d.get("content") or "").lower()
        if not terms:
            d["similarity_score"] = 0.5
            out.append(d)
            continue
        hit = sum(1 for t in terms if t in text)
        if hit <= 0:
            continue
        tset = set(re.findall(r"[a-z0-9]{3,}", text))
        jacc = len(set(terms) & tset) / max(1, len(set(terms) | tset))
        d["similarity_score"] = round(min(1.0, 0.7 * (hit / max(1, len(terms))) + 0.3 * jacc), 4)
        out.append(d)
    out.sort(key=lambda x: (x.get("similarity_score", 0.0), x.get("ts", "")), reverse=True)
    return out[: max(1, int(limit))]


def search_reflections(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    terms = [t for t in re.findall(r"[a-z0-9]{3,}", (query or "").lower())]
    rows = conn.execute("SELECT * FROM reflections ORDER BY ts DESC LIMIT 500").fetchall()
    out: list[dict] = []
    for row in rows:
        d = dict(row)
        text = " ".join(
            [
                str(d.get("outcome") or ""),
                str(d.get("learnings") or ""),
                str(d.get("went_well") or ""),
                str(d.get("went_wrong") or ""),
            ]
        ).lower()
        if not terms:
            d["similarity_score"] = 0.5
            out.append(d)
            continue
        hit = sum(1 for t in terms if t in text)
        if hit <= 0:
            continue
        tset = set(re.findall(r"[a-z0-9]{3,}", text))
        jacc = len(set(terms) & tset) / max(1, len(set(terms) | tset))
        d["similarity_score"] = round(min(1.0, 0.65 * (hit / max(1, len(terms))) + 0.35 * jacc), 4)
        out.append(d)
    out.sort(key=lambda x: (x.get("similarity_score", 0.0), x.get("quality", 0.0), x.get("ts", "")), reverse=True)
    return out[: max(1, int(limit))]
