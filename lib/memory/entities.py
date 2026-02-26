"""Entities domain: knowledge graph (entities, relations, mentions)."""
import json
import time
import sqlite3

from .common import utcnow, hash_id


class Entities:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_or_create(
        self,
        name: str,
        entity_type: str,
        properties: dict | None = None,
        first_seen_project: str | None = None,
    ) -> str:
        name_n = (name or "").strip()
        if not name_n:
            raise ValueError("Entity name required")
        row = self._conn.execute(
            "SELECT id FROM entities WHERE name = ? AND type = ?", (name_n, entity_type)
        ).fetchone()
        if row:
            return row["id"]
        eid = hash_id(f"ent:{name_n}:{entity_type}:{time.time_ns()}")
        now = utcnow()
        self._conn.execute(
            "INSERT INTO entities (id, name, type, properties_json, first_seen_project, created_at) VALUES (?,?,?,?,?,?)",
            (eid, name_n, entity_type, json.dumps(properties or {}), first_seen_project or "", now),
        )
        self._conn.commit()
        return eid

    def insert_relation(
        self,
        entity_a_id: str,
        entity_b_id: str,
        relation_type: str,
        source_project: str,
        evidence: str = "",
    ) -> str:
        rid = hash_id(f"er:{entity_a_id}:{entity_b_id}:{relation_type}:{time.time_ns()}")
        self._conn.execute(
            "INSERT OR IGNORE INTO entity_relations (id, entity_a_id, entity_b_id, relation_type, source_project, evidence, created_at) VALUES (?,?,?,?,?,?,?)",
            (rid, entity_a_id, entity_b_id, relation_type, source_project, evidence[:2000], utcnow()),
        )
        self._conn.commit()
        return rid

    def insert_mention(
        self,
        entity_id: str,
        project_id: str,
        finding_key: str | None = None,
        context_snippet: str = "",
    ) -> str:
        mid = hash_id(f"em:{entity_id}:{project_id}:{finding_key or ''}:{time.time_ns()}")
        self._conn.execute(
            "INSERT OR IGNORE INTO entity_mentions (id, entity_id, project_id, finding_key, context_snippet) VALUES (?,?,?,?,?)",
            (mid, entity_id, project_id, finding_key or "", context_snippet[:1000]),
        )
        self._conn.commit()
        return mid

    def get(
        self,
        entity_type: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if project_id:
            rows = self._conn.execute(
                """SELECT e.* FROM entities e
                   JOIN entity_mentions m ON m.entity_id = e.id
                   WHERE m.project_id = ? AND (? = '' OR e.type = ?)
                   GROUP BY e.id ORDER BY e.created_at DESC LIMIT ?""",
                (project_id, entity_type or "", entity_type or "", limit),
            ).fetchall()
        elif entity_type:
            rows = self._conn.execute(
                "SELECT * FROM entities WHERE type = ? ORDER BY created_at DESC LIMIT ?",
                (entity_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM entities ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_relations(self, project_id: str | None = None, limit: int = 50) -> list[dict]:
        if project_id:
            rows = self._conn.execute(
                """SELECT r.*, a.name as name_a, b.name as name_b
                   FROM entity_relations r
                   JOIN entities a ON a.id = r.entity_a_id
                   JOIN entities b ON b.id = r.entity_b_id
                   WHERE r.source_project = ? ORDER BY r.created_at DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT r.*, a.name as name_a, b.name as name_b
                   FROM entity_relations r
                   JOIN entities a ON a.id = r.entity_a_id
                   JOIN entities b ON b.id = r.entity_b_id
                   ORDER BY r.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
