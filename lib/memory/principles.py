"""Strategic principles (EvolveR-style): guiding and cautionary principles from trajectories."""
import json
import re
import sqlite3

from .common import utcnow, hash_id, cosine_similarity


class Principles:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(
        self,
        principle_type: str,
        description: str,
        source_project_id: str,
        domain: str | None = None,
        evidence_json: str = "[]",
        metric_score: float = 0.5,
        embedding_json: str | None = None,
    ) -> str:
        pid = hash_id(f"sp:{source_project_id}:{description[:100]}:{utcnow()}")
        self._conn.execute(
            """INSERT INTO strategic_principles
               (id, principle_type, description, domain, source_project_id, evidence_json, metric_score, usage_count, success_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)""",
            (pid, principle_type, description, domain or "", source_project_id, evidence_json, metric_score, utcnow()),
        )
        if embedding_json:
            self._conn.execute("UPDATE strategic_principles SET embedding_json = ? WHERE id = ?", (embedding_json, pid))
        self._conn.commit()
        return pid

    def get(self, principle_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM strategic_principles WHERE id = ?", (principle_id,)).fetchone()
        return dict(row) if row else None

    def search(
        self,
        query: str,
        limit: int = 10,
        domain: str | None = None,
        principle_type: str | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[dict]:
        """Hybrid lexical + optional semantic (embedding_json) search on principle descriptions."""
        terms = [t for t in re.findall(r"[a-z0-9]{3,}", (query or "").lower())]
        if not terms and not query_embedding:
            return []
        where = []
        params: list = []
        if domain:
            where.append("(domain = ? OR domain = '')")
            params.append(domain)
        if principle_type:
            where.append("principle_type = ?")
            params.append(principle_type)
        sql = "SELECT * FROM strategic_principles"
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self._conn.execute(sql).fetchall()
        by_id: dict[str, dict] = {}
        for r in rows:
            d = dict(r)
            desc = (d.get("description") or "").lower()
            lex_score = 0.0
            if terms:
                hit = sum(1 for t in terms if t in desc)
                if hit <= 0 and not query_embedding:
                    continue
                if hit > 0:
                    token_set = set(re.findall(r"[a-z0-9]{3,}", desc))
                    jacc = len(set(terms) & token_set) / max(1, len(set(terms) | token_set))
                    contains_phrase = 1.0 if " ".join(terms[:3]) in desc else 0.0
                    lex_score = round(min(1.0, 0.6 * (hit / max(1, len(terms))) + 0.3 * jacc + 0.1 * contains_phrase), 4)
            else:
                lex_score = 0.5
            emb_score = 0.0
            if query_embedding:
                ej = d.get("embedding_json")
                if ej:
                    try:
                        vec = json.loads(ej) if isinstance(ej, str) else ej
                        if isinstance(vec, list) and len(vec) == len(query_embedding):
                            emb_score = cosine_similarity(query_embedding, vec)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass
            if lex_score <= 0 and emb_score <= 0:
                continue
            d["similarity_score"] = round(max(lex_score, emb_score, 0.7 * emb_score + 0.3 * lex_score if (lex_score and emb_score) else (lex_score or emb_score)), 4)
            by_id[d["id"]] = d
        out = sorted(by_id.values(), key=lambda x: (x.get("similarity_score", 0.0), x.get("metric_score", 0.0), x.get("created_at", "")), reverse=True)
        return out[: max(1, int(limit))]

    def list_recent(self, limit: int = 50, domain: str | None = None) -> list[dict]:
        if domain:
            rows = self._conn.execute(
                "SELECT * FROM strategic_principles WHERE domain = ? OR domain = '' ORDER BY metric_score DESC, created_at DESC LIMIT ?",
                (domain, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM strategic_principles ORDER BY metric_score DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_usage_success(self, principle_id: str, success: bool) -> None:
        row = self._conn.execute(
            "SELECT usage_count, success_count FROM strategic_principles WHERE id = ?", (principle_id,)
        ).fetchone()
        if not row:
            return
        usage = row["usage_count"] + 1
        success_count = row["success_count"] + (1 if success else 0)
        metric_score = (success_count + 1) / (usage + 2)
        self._conn.execute(
            "UPDATE strategic_principles SET usage_count = ?, success_count = ?, metric_score = ? WHERE id = ?",
            (usage, success_count, metric_score, principle_id),
        )
        self._conn.commit()

    def append_evidence(self, principle_id: str, source_project_id: str, evidence_snippet: str) -> None:
        """Append project evidence to principle (for merge)."""
        row = self._conn.execute(
            "SELECT evidence_json FROM strategic_principles WHERE id = ?", (principle_id,)
        ).fetchone()
        if not row:
            return
        try:
            evidence = json.loads(row["evidence_json"] or "[]")
        except Exception:
            evidence = []
        evidence.append({"project_id": source_project_id, "snippet": (evidence_snippet or "")[:500]})
        self._conn.execute(
            "UPDATE strategic_principles SET evidence_json = ? WHERE id = ?",
            (json.dumps(evidence[-20:]), principle_id),  # keep last 20
        )
        self._conn.commit()
