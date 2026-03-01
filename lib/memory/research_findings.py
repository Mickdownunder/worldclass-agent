"""Research findings, admission events, and cross-links."""
import json
import time
import sqlite3

from .common import utcnow, hash_id


class ResearchFindings:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(
        self,
        project_id: str,
        finding_key: str,
        content_preview: str,
        embedding_json: str | None = None,
        url: str | None = None,
        title: str | None = None,
        relevance_score: float | None = None,
        reliability_score: float | None = None,
        verification_status: str | None = None,
        evidence_count: int | None = None,
        critic_score: float | None = None,
        importance_score: float | None = None,
        admission_state: str | None = None,
    ) -> str:
        fid = hash_id(f"rf:{project_id}:{finding_key}:{time.time_ns()}")
        state = (admission_state or "quarantined").lower()
        if state not in ("accepted", "quarantined", "rejected"):
            state = "quarantined"
        self._conn.execute(
            """INSERT INTO research_findings (id, project_id, finding_key, content_preview, embedding_json, ts, url, title,
               relevance_score, reliability_score, verification_status, evidence_count, critic_score, importance_score, admission_state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fid, project_id, finding_key, content_preview[:4000], embedding_json, utcnow(), url, title,
                relevance_score, reliability_score, verification_status, evidence_count, critic_score, importance_score, state,
            ),
        )
        self._conn.commit()
        return fid

    def record_admission_event(
        self,
        project_id: str,
        finding_key: str,
        decision: str,
        reason: str = "",
        scores: dict | None = None,
    ) -> str:
        eid = hash_id(f"ae:{project_id}:{finding_key}:{time.time_ns()}")
        self._conn.execute(
            "INSERT INTO memory_admission_events (id, ts, project_id, finding_key, decision, reason, scores_json) VALUES (?,?,?,?,?,?,?)",
            (eid, utcnow(), project_id, finding_key, decision, reason[:1000], json.dumps(scores or {})),
        )
        self._conn.commit()
        return eid

    def get_with_embeddings(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, project_id, finding_key, content_preview, embedding_json, url, title FROM research_findings WHERE embedding_json IS NOT NULL AND embedding_json != ''"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_accepted(self, project_id: str | None = None, limit: int = 200) -> list[dict]:
        if project_id:
            rows = self._conn.execute(
                """SELECT id, project_id, finding_key, content_preview, url, title, relevance_score, importance_score
                   FROM research_findings WHERE admission_state = 'accepted' AND project_id = ? ORDER BY ts DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT id, project_id, finding_key, content_preview, url, title, relevance_score, importance_score
                   FROM research_findings WHERE admission_state = 'accepted' ORDER BY ts DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def search_by_query(self, query: str, limit: int = 50) -> list[dict]:
        """Return accepted findings whose content_preview or title matches query terms (keyword AND).
         Used for prior-knowledge seeding so discovery and standard runs only get topic-relevant findings."""
        terms = [t for t in query.lower().split() if len(t) >= 2]
        if not terms:
            return []
        conditions = " AND ".join(
            "(LOWER(COALESCE(content_preview,'')) LIKE ? OR LOWER(COALESCE(title,'')) LIKE ?)"
            for _ in terms
        )
        params = [f"%{t}%" for t in terms for _ in (0, 1)]
        params.append(limit)
        rows = self._conn.execute(
            """SELECT id, project_id, finding_key, content_preview, url, title, relevance_score, importance_score
               FROM research_findings WHERE admission_state = 'accepted' AND """
            + conditions
            + " ORDER BY ts DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_cross_link(
        self,
        finding_a_id: str,
        finding_b_id: str,
        project_a: str,
        project_b: str,
        similarity: float,
    ) -> str:
        lid = hash_id(f"cl:{finding_a_id}:{finding_b_id}:{time.time_ns()}")
        self._conn.execute(
            "INSERT OR IGNORE INTO cross_links (id, finding_a_id, finding_b_id, project_a, project_b, similarity, ts) VALUES (?,?,?,?,?,?,?)",
            (lid, finding_a_id, finding_b_id, project_a, project_b, similarity, utcnow()),
        )
        self._conn.commit()
        return lid

    def get_cross_links_unnotified(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM cross_links WHERE notified = 0 ORDER BY similarity DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_cross_links_notified(self, link_ids: list[str]) -> None:
        for lid in link_ids:
            self._conn.execute("UPDATE cross_links SET notified = 1 WHERE id = ?", (lid,))
        self._conn.commit()
