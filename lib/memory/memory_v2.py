"""Memory v2 storage and learning logic."""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

from .common import hash_id, utcnow


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_json(value, fallback):
    try:
        return json.dumps(value if value is not None else fallback, ensure_ascii=False)
    except Exception:
        return json.dumps(fallback, ensure_ascii=False)


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


class MemoryV2:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record_run_episode(
        self,
        project_id: str,
        question: str,
        domain: str,
        status: str,
        plan_query_mix: dict | None = None,
        source_mix: dict | None = None,
        gate_metrics: dict | None = None,
        critic_score: float | None = None,
        user_verdict: str | None = None,
        fail_codes: list[str] | None = None,
        what_helped: list[str] | None = None,
        what_hurt: list[str] | None = None,
        strategy_profile_id: str | None = None,
    ) -> str:
        episode_id = hash_id(f"episode:{project_id}")
        now = utcnow()
        self._conn.execute(
            """INSERT OR REPLACE INTO run_episodes
               (id, project_id, question, domain, status, plan_query_mix_json, source_mix_json,
                gate_metrics_json, critic_score, user_verdict, fail_codes_json,
                what_helped_json, what_hurt_json, strategy_profile_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                episode_id,
                project_id,
                question or "",
                domain or "general",
                status or "unknown",
                _safe_json(plan_query_mix, {}),
                _safe_json(source_mix, {}),
                _safe_json(gate_metrics, {}),
                critic_score,
                user_verdict or "none",
                _safe_json(fail_codes, []),
                _safe_json(what_helped, []),
                _safe_json(what_hurt, []),
                strategy_profile_id,
                now,
            ),
        )
        self._conn.commit()
        return episode_id

    def upsert_strategy_profile(
        self,
        name: str,
        domain: str,
        policy: dict,
        score: float = 0.5,
        confidence: float = 0.5,
        status: str = "active",
        version: int = 1,
        metadata: dict | None = None,
    ) -> str:
        pid = hash_id(f"strategy:{name}:{domain}:{version}")
        now = utcnow()
        self._conn.execute(
            """INSERT OR REPLACE INTO strategy_profiles
               (id, name, domain, policy_json, score, confidence, usage_count, success_count, fail_count,
                status, version, metadata_json, created_at, updated_at)
               VALUES (
                 ?, ?, ?, ?, ?, ?, COALESCE((SELECT usage_count FROM strategy_profiles WHERE id=?), 0),
                 COALESCE((SELECT success_count FROM strategy_profiles WHERE id=?), 0),
                 COALESCE((SELECT fail_count FROM strategy_profiles WHERE id=?), 0),
                 ?, ?, ?, COALESCE((SELECT created_at FROM strategy_profiles WHERE id=?), ?), ?
               )""",
            (
                pid,
                name,
                domain or "general",
                _safe_json(policy, {}),
                _clamp(float(score), 0.0, 1.0),
                _clamp(float(confidence), 0.0, 1.0),
                pid,
                pid,
                pid,
                status,
                max(1, int(version)),
                _safe_json(metadata, {}),
                pid,
                now,
                now,
            ),
        )
        self._conn.commit()
        return pid

    def list_strategy_profiles(self, domain: str | None = None, limit: int = 20) -> list[dict]:
        if domain:
            rows = self._conn.execute(
                """SELECT * FROM strategy_profiles
                   WHERE status='active' AND (domain=? OR domain='general')
                   ORDER BY score DESC, confidence DESC, updated_at DESC LIMIT ?""",
                (domain, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM strategy_profiles
                   WHERE status='active'
                   ORDER BY score DESC, confidence DESC, updated_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["policy"] = json.loads(d.get("policy_json") or "{}")
            except Exception:
                d["policy"] = {}
            out.append(d)
        return out

    def select_strategy(self, question: str, domain: str | None = None) -> dict | None:
        candidates = self.list_strategy_profiles(domain=domain or None, limit=20)
        if not candidates:
            return None
        q_tokens = _tokenize(question)
        best = None
        best_score = -1.0
        for c in candidates:
            policy_text = json.dumps(c.get("policy", {}), ensure_ascii=False)
            p_tokens = _tokenize(policy_text)
            overlap = len(q_tokens & p_tokens)
            lexical = overlap / max(1, len(q_tokens))
            combined = 0.75 * float(c.get("score") or 0.5) + 0.25 * lexical
            if c.get("domain") == domain:
                combined += 0.05
            if combined > best_score:
                best_score = combined
                best = c
        if not best:
            return None
        confidence = _clamp(best_score, 0.0, 1.0)
        best["selection_confidence"] = confidence
        return best

    def record_strategy_application_event(
        self,
        project_id: str,
        phase: str,
        strategy_profile_id: str | None,
        applied_policy: dict | None = None,
        fallback_used: bool = False,
        outcome_hint: str = "",
        status: str = "ok",
    ) -> str:
        event_id = hash_id(f"strategy-event:{project_id}:{phase}:{utcnow()}:{strategy_profile_id or 'none'}")
        self._conn.execute(
            """INSERT INTO strategy_application_events
               (id, ts, project_id, strategy_profile_id, phase, applied_policy_json, fallback_used, outcome_hint, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                utcnow(),
                project_id,
                strategy_profile_id,
                phase,
                _safe_json(applied_policy, {}),
                1 if fallback_used else 0,
                outcome_hint[:200],
                status[:40],
            ),
        )
        self._conn.commit()
        return event_id

    def record_memory_decision(
        self,
        decision_type: str,
        details: dict,
        project_id: str | None = None,
        phase: str | None = None,
        strategy_profile_id: str | None = None,
        confidence: float = 0.5,
    ) -> str:
        did = hash_id(f"memory-decision:{decision_type}:{project_id or ''}:{phase or ''}:{utcnow()}")
        self._conn.execute(
            """INSERT INTO memory_decision_log
               (id, ts, project_id, phase, decision_type, strategy_profile_id, confidence, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                did,
                utcnow(),
                project_id,
                phase,
                decision_type,
                strategy_profile_id,
                _clamp(confidence, 0.0, 1.0),
                _safe_json(details, {}),
            ),
        )
        self._conn.commit()
        return did

    def record_graph_edge(
        self,
        edge_type: str,
        from_node_type: str,
        from_node_id: str,
        to_node_type: str,
        to_node_id: str,
        project_id: str | None = None,
    ) -> str:
        eid = hash_id(
            f"graph-edge:{edge_type}:{from_node_type}:{from_node_id}:{to_node_type}:{to_node_id}:{project_id or ''}:{utcnow()}"
        )
        self._conn.execute(
            """INSERT INTO memory_graph_edges
               (id, ts, edge_type, from_node_type, from_node_id, to_node_type, to_node_id, project_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                eid,
                utcnow(),
                edge_type[:32],
                from_node_type[:40],
                from_node_id,
                to_node_type[:40],
                to_node_id,
                project_id,
            ),
        )
        self._conn.commit()
        return eid

    def update_source_domain_stats_v2(
        self,
        domain: str,
        topic_domain: str,
        times_seen: int = 1,
        verified_hits: int = 0,
        relevant_hits: int = 0,
        fail_hits: int = 0,
    ) -> None:
        self._conn.execute(
            """INSERT INTO source_domain_stats_v2
               (domain, topic_domain, times_seen, verified_hits, relevant_hits, fail_hits, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(domain, topic_domain) DO UPDATE SET
                 times_seen = times_seen + excluded.times_seen,
                 verified_hits = verified_hits + excluded.verified_hits,
                 relevant_hits = relevant_hits + excluded.relevant_hits,
                 fail_hits = fail_hits + excluded.fail_hits,
                 last_updated = excluded.last_updated""",
            (
                domain,
                topic_domain or "general",
                max(0, int(times_seen)),
                max(0, int(verified_hits)),
                max(0, int(relevant_hits)),
                max(0, int(fail_hits)),
                utcnow(),
            ),
        )
        self._conn.commit()

    def list_source_domain_stats_v2(self, topic_domain: str, limit: int = 30) -> list[dict]:
        rows = self._conn.execute(
            """SELECT *,
                      CAST(verified_hits + 1 AS REAL) / (times_seen + 2) AS verified_rate,
                      CAST(relevant_hits + 1 AS REAL) / (times_seen + 2) AS relevance_rate
               FROM source_domain_stats_v2
               WHERE topic_domain=?
               ORDER BY verified_rate DESC, relevance_rate DESC, times_seen DESC
               LIMIT ?""",
            (topic_domain or "general", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_strategy_from_outcome(
        self,
        strategy_profile_id: str,
        critic_pass: bool,
        evidence_gate_pass: bool,
        user_verdict: str = "none",
        claim_support_rate: float | None = None,
        failed_quality_gate: bool = False,
    ) -> None:
        row = self._conn.execute(
            "SELECT score, confidence, usage_count, success_count, fail_count FROM strategy_profiles WHERE id=?",
            (strategy_profile_id,),
        ).fetchone()
        if not row:
            return
        score = float(row["score"] or 0.5)
        confidence = float(row["confidence"] or 0.5)
        usage_count = int(row["usage_count"] or 0) + 1
        success_count = int(row["success_count"] or 0)
        fail_count = int(row["fail_count"] or 0)
        if critic_pass and evidence_gate_pass and user_verdict == "approved":
            delta = 0.05
            if isinstance(claim_support_rate, (int, float)):
                delta += 0.05 * _clamp(float(claim_support_rate), 0.0, 1.0)
            score = _clamp(score + delta, 0.0, 1.0)
            success_count += 1
        else:
            penalty = 0.08 if failed_quality_gate else 0.05
            if isinstance(claim_support_rate, (int, float)) and float(claim_support_rate) < 0.5:
                penalty += 0.03
            if user_verdict == "rejected":
                penalty += 0.04
            score = _clamp(score - penalty, 0.0, 1.0)
            fail_count += 1
        total = max(1, success_count + fail_count)
        confidence = _clamp(0.25 + 0.75 * (min(50, total) / 50.0), 0.0, 1.0)
        self._conn.execute(
            """UPDATE strategy_profiles
               SET score=?, confidence=?, usage_count=?, success_count=?, fail_count=?, updated_at=?
               WHERE id=?""",
            (score, confidence, usage_count, success_count, fail_count, utcnow(), strategy_profile_id),
        )
        self._conn.commit()

    def summarize_query_type_mix(self, queries: list[dict]) -> dict[str, float]:
        c = Counter()
        total = 0
        for q in queries or []:
            qtype = str((q or {}).get("type") or "web").lower()
            if qtype not in {"web", "academic", "medical"}:
                qtype = "web"
            c[qtype] += 1
            total += 1
        if total <= 0:
            return {}
        return {k: round(v / total, 3) for k, v in c.items()}
