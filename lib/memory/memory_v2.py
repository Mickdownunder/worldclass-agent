"""Memory v2 storage and learning logic."""
from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone

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


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "about", "what", "when", "where", "which",
    "wie", "und", "der", "die", "das", "den", "dem", "ein", "eine", "einer", "eines", "mit", "auf", "ist",
    "sind", "von", "zu", "in", "an", "im", "am", "als",
}


def _question_signature(question: str) -> str:
    """
    Normalize questions for read-URL dedup across paraphrases:
    lowercase, tokenized, stopword-filtered, sorted unique terms.
    """
    raw = [t for t in re.findall(r"[a-z0-9]{3,}", (question or "").lower()) if t not in _STOPWORDS]
    tokens: list[str] = []
    for t in raw:
        s = t
        # Very lightweight stemming for paraphrase robustness (plural/tense variants).
        for suf in ("ing", "ed", "es", "s"):
            if len(s) >= 5 and s.endswith(suf):
                s = s[: -len(suf)]
                break
        tokens.append(s)
    if not tokens:
        return (question or "").strip().lower()
    return " ".join(sorted(set(tokens)))


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
        memory_mode: str | None = None,
        strategy_confidence: float | None = None,
        verified_claim_count: int | None = None,
        claim_support_rate: float | None = None,
    ) -> str:
        now = utcnow()
        episode_id = hash_id(f"episode:{project_id}:{now}:{question[:64]}")
        run_row = self._conn.execute(
            "SELECT COALESCE(MAX(run_index), 0) AS m FROM run_episodes WHERE project_id=?",
            (project_id,),
        ).fetchone()
        run_index = int(run_row["m"] or 0) + 1
        mode_val = (memory_mode or "fallback").strip().lower()
        if mode_val not in ("applied", "fallback"):
            mode_val = "fallback"
        self._conn.execute(
            """INSERT INTO run_episodes
               (id, project_id, question, domain, status, plan_query_mix_json, source_mix_json,
                gate_metrics_json, critic_score, user_verdict, fail_codes_json,
                what_helped_json, what_hurt_json, strategy_profile_id, created_at,
                run_index, memory_mode, strategy_confidence, verified_claim_count, claim_support_rate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                run_index,
                mode_val,
                strategy_confidence,
                verified_claim_count,
                claim_support_rate,
            ),
        )
        if strategy_profile_id:
            # Keep episode<->strategy graph linkage consistent even if caller forgets.
            self.record_graph_edge(
                edge_type="used_in",
                from_node_type="strategy_profile",
                from_node_id=strategy_profile_id,
                to_node_type="run_episode",
                to_node_id=episode_id,
                project_id=project_id,
            )
        self._conn.commit()
        return episode_id

    def get_memory_value_score(self) -> dict:
        """Memory Value: avg(critic_score) applied - avg(critic_score) fallback. Answers: does memory help?"""
        try:
            applied = self._conn.execute(
                """SELECT AVG(critic_score) AS avg_score, COUNT(*) AS cnt
                   FROM run_episodes WHERE memory_mode = 'applied' AND critic_score IS NOT NULL"""
            ).fetchone()
            fallback = self._conn.execute(
                """SELECT AVG(critic_score) AS avg_score, COUNT(*) AS cnt
                   FROM run_episodes WHERE memory_mode = 'fallback' AND critic_score IS NOT NULL"""
            ).fetchone()
            applied_avg = float(applied["avg_score"]) if applied and applied["avg_score"] is not None else None
            fallback_avg = float(fallback["avg_score"]) if fallback and fallback["avg_score"] is not None else None
            applied_cnt = int(applied["cnt"] or 0) if applied else 0
            fallback_cnt = int(fallback["cnt"] or 0) if fallback else 0
            if applied_avg is not None and fallback_avg is not None:
                memory_value = round(applied_avg - fallback_avg, 3)
            elif applied_avg is not None:
                memory_value = round(applied_avg, 3)
            elif fallback_avg is not None:
                memory_value = round(-fallback_avg, 3)
            else:
                memory_value = None
            return {
                "memory_value": memory_value,
                "applied_avg": round(applied_avg, 3) if applied_avg is not None else None,
                "fallback_avg": round(fallback_avg, 3) if fallback_avg is not None else None,
                "applied_count": applied_cnt,
                "fallback_count": fallback_cnt,
            }
        except Exception:
            return {"memory_value": None, "applied_avg": None, "fallback_avg": None, "applied_count": 0, "fallback_count": 0}

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
        # Fail-code filter: hard-exclude strategies that had blocking fail_codes in this domain (Priority 3)
        candidates = [c for c in candidates if not self._strategy_fail_code_blocked(c.get("id") or "", domain)]
        if not candidates:
            return None
        q_tokens = _tokenize(question)
        similar_count, similar_recency = self._similar_episode_signals(question, domain)
        similar_norm = min(1.0, similar_count / 10.0)
        recency_domain = similar_recency
        if domain and any(c.get("domain") == domain for c in candidates):
            recency_domain = _clamp(recency_domain + 0.1, 0.0, 1.0)
        best = None
        best_score = -1.0
        for c in candidates:
            policy_text = json.dumps(c.get("policy", {}), ensure_ascii=False)
            p_tokens = _tokenize(policy_text)
            overlap = len(q_tokens & p_tokens)
            lexical = overlap / max(1, len(q_tokens))
            causal_score, what_hurt_penalty = self._causal_signal(
                c.get("id") or "", c.get("domain") or "", question, domain
            )
            # Weights: 40% historical, 20% lexical, 20% causal, 10% similar episodes, 10% recency+domain (Priority 3)
            combined = (
                0.40 * float(c.get("score") or 0.5)
                + 0.20 * lexical
                + 0.20 * causal_score
                + 0.10 * similar_norm
                + 0.10 * recency_domain
            )
            if c.get("domain") == domain:
                combined += 0.05
            if what_hurt_penalty:
                combined -= 0.2
            if combined > best_score:
                best_score = combined
                best = c
                best["confidence_drivers"] = {
                    "strategy_score": round(float(c.get("score") or 0.5), 3),
                    "query_overlap": round(lexical, 3),
                    "causal_score": round(causal_score, 3),
                    "what_hurt_penalty": what_hurt_penalty,
                    "similar_episode_count": similar_count,
                    "similar_recency_weight": round(similar_recency, 3),
                }
        if not best:
            return None
        # Domain mismatch: if strategy's domain overrides don't fit question domain, fall back to defaults (Priority 3)
        if self._strategy_domain_mismatch(best, domain):
            self.record_memory_decision(
                "strategy_domain_mismatch",
                {"strategy_id": best.get("id"), "strategy_domain": best.get("domain"), "question_domain": domain or ""},
                confidence=_clamp(best_score, 0.0, 1.0),
            )
            return None
        confidence = _clamp(best_score, 0.0, 1.0)
        best["selection_confidence"] = confidence
        best["similar_episode_count"] = int((best.get("confidence_drivers") or {}).get("similar_episode_count", 0))
        # Similar-episode gate: do not apply a strategy when there are no similar past runs (avoids cross-topic leakage)
        if (best.get("similar_episode_count") or 0) == 0:
            self.record_memory_decision(
                "strategy_skipped_no_similar_episodes",
                {"strategy_id": best.get("id"), "strategy_name": best.get("name")},
                confidence=confidence,
            )
            return None
        return best

    def _similar_episode_signals(self, question: str, domain: str | None) -> tuple[int, float]:
        try:
            if domain:
                rows = self._conn.execute(
                    """SELECT question, created_at FROM run_episodes
                       WHERE domain=? ORDER BY created_at DESC LIMIT 40""",
                    (domain,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT question, created_at FROM run_episodes ORDER BY created_at DESC LIMIT 40"
                ).fetchall()
        except Exception:
            return 0, 0.0
        q_tokens = _tokenize(question)
        if not q_tokens:
            return 0, 0.0
        similar_count = 0
        weighted = 0.0
        for r in rows:
            other = _tokenize(r["question"] or "")
            if not other:
                continue
            overlap = len(q_tokens & other) / max(1, len(q_tokens | other))
            if overlap < 0.12:
                continue
            similar_count += 1
            ts = str(r["created_at"] or "")
            age_days = 30.0
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
            except Exception:
                pass
            weighted += math.exp(-age_days / 30.0)
        if similar_count <= 0:
            return 0, 0.0
        return similar_count, _clamp(weighted / similar_count, 0.0, 1.0)

    # Domain -> fail_codes that trigger hard-exclude when strategy was used in that domain (Priority 3)
    _DOMAIN_BLOCKING_FAIL_CODES: dict[str, list[str]] = {
        "biomedical": ["safety_filter_block"],
        "clinical": ["safety_filter_block"],
        "medical": ["safety_filter_block"],
    }

    def _strategy_episodes_for_causal(
        self, strategy_profile_id: str, domain: str | None, limit: int = 30
    ) -> list[dict]:
        """Episodes that used this strategy in same/similar domain (via graph used_in, fallback strategy_profile_id)."""
        try:
            # Prefer graph: episodes linked by memory_graph_edges (used_in strategy -> episode)
            episode_ids = self.get_episode_ids_for_strategy(strategy_profile_id, domain=domain, limit=limit)
            if episode_ids:
                placeholders = ",".join("?" * len(episode_ids))
                if domain:
                    rows = self._conn.execute(
                        f"""SELECT question, domain, what_helped_json, what_hurt_json, fail_codes_json, critic_score
                           FROM run_episodes WHERE id IN ({placeholders}) AND domain=?
                           ORDER BY created_at DESC LIMIT ?""",
                        (*episode_ids, domain, limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        f"""SELECT question, domain, what_helped_json, what_hurt_json, fail_codes_json, critic_score
                           FROM run_episodes WHERE id IN ({placeholders})
                           ORDER BY created_at DESC LIMIT ?""",
                        (*episode_ids, limit),
                    ).fetchall()
            else:
                # Fallback when no graph edges yet (e.g. older DBs)
                if domain:
                    rows = self._conn.execute(
                        """SELECT question, domain, what_helped_json, what_hurt_json, fail_codes_json, critic_score
                           FROM run_episodes WHERE strategy_profile_id=? AND domain=?
                           ORDER BY created_at DESC LIMIT ?""",
                        (strategy_profile_id, domain, limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        """SELECT question, domain, what_helped_json, what_hurt_json, fail_codes_json, critic_score
                           FROM run_episodes WHERE strategy_profile_id=?
                           ORDER BY created_at DESC LIMIT ?""",
                        (strategy_profile_id, limit),
                    ).fetchall()
            out = []
            for r in rows:
                try:
                    what_helped = json.loads(r["what_helped_json"] or "[]")
                    what_hurt = json.loads(r["what_hurt_json"] or "[]")
                    fail_codes = json.loads(r["fail_codes_json"] or "[]")
                except Exception:
                    what_helped, what_hurt, fail_codes = [], [], []
                out.append({
                    "question": r["question"] or "",
                    "domain": r["domain"] or "",
                    "what_helped": what_helped if isinstance(what_helped, list) else [],
                    "what_hurt": what_hurt if isinstance(what_hurt, list) else [],
                    "fail_codes": fail_codes if isinstance(fail_codes, list) else [],
                    "critic_score": float(r["critic_score"]) if r["critic_score"] is not None else None,
                })
            return out
        except Exception:
            return []

    def _strategy_fail_code_blocked(self, strategy_profile_id: str, domain: str | None) -> bool:
        """True if this strategy should be hard-excluded for this domain (e.g. safety_filter_block on biomedical)."""
        if not domain:
            return False
        domain_lower = (domain or "").lower()
        blocking = []
        for d, codes in self._DOMAIN_BLOCKING_FAIL_CODES.items():
            if d in domain_lower or domain_lower in d:
                blocking.extend(codes)
        if not blocking:
            return False
        try:
            rows = self._conn.execute(
                """SELECT fail_codes_json FROM run_episodes
                   WHERE strategy_profile_id=? AND domain=?""",
                (strategy_profile_id, domain),
            ).fetchall()
            for r in rows:
                try:
                    codes = json.loads(r["fail_codes_json"] or "[]")
                    if isinstance(codes, list) and any(c in blocking for c in (str(x) for x in codes)):
                        return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def _causal_signal(
        self, strategy_profile_id: str, strategy_domain: str, question: str, domain: str | None
    ) -> tuple[float, bool]:
        """
        Returns (causal_score 0..1, what_hurt_penalty_applied).
        causal_score: higher if past episodes with this strategy had what_helped / good outcomes; lower if what_hurt matches.
        what_hurt_penalty_applied: True if we apply -0.2 elsewhere (similar episode had what_hurt matching question).
        """
        episodes = self._strategy_episodes_for_causal(strategy_profile_id, domain or strategy_domain, limit=20)
        if not episodes:
            return 0.5, False  # neutral
        q_tokens = _tokenize(question)
        hurt_penalty = False
        help_count = 0
        hurt_count = 0
        good_outcome_count = 0
        for ep in episodes:
            what_hurt = [str(x).lower() for x in ep.get("what_hurt") or []]
            what_helped = [str(x).lower() for x in ep.get("what_helped") or []]
            hurt_tokens = _tokenize(" ".join(what_hurt))
            help_tokens = _tokenize(" ".join(what_helped))
            if q_tokens and hurt_tokens and len(q_tokens & hurt_tokens) >= 1:
                hurt_penalty = True
                hurt_count += 1
            if what_helped and (not q_tokens or len(q_tokens & help_tokens) >= 1 or len(help_tokens) <= 2):
                help_count += 1
            if isinstance(ep.get("critic_score"), (int, float)) and float(ep["critic_score"]) >= 0.5:
                good_outcome_count += 1
        n = len(episodes)
        causal = 0.5
        if n > 0:
            causal = 0.3 + 0.4 * (good_outcome_count / n) + 0.2 * min(1.0, help_count / 3) - 0.2 * min(1.0, hurt_count)
        causal = _clamp(causal, 0.0, 1.0)
        return causal, hurt_penalty

    def _strategy_domain_mismatch(self, strategy: dict, question_domain: str | None) -> bool:
        """True if strategy's domain overrides don't fit question domain (e.g. clinical strategy for manufacturing)."""
        if not question_domain:
            return False
        strategy_domain = (strategy.get("domain") or "").strip().lower()
        if not strategy_domain or strategy_domain == "general":
            return False
        qd = (question_domain or "").lower()
        # Mismatch if strategy is domain-specific and question domain is different
        domain_keywords = {
            "clinical": ["clinical", "medical", "biomedical", "health", "trial"],
            "manufacturing": ["manufacturing", "industrial", "supply", "production"],
            "biomedical": ["bio", "medical", "clinical", "health"],
            "general": [],
        }
        for key, keywords in domain_keywords.items():
            if key == "general":
                continue
            if strategy_domain == key or strategy_domain in key:
                if not any(kw in qd for kw in keywords):
                    return True
        return False

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

    def list_memory_decisions(self, project_id: str | None = None, limit: int = 50) -> list[dict]:
        if project_id:
            rows = self._conn.execute(
                """SELECT * FROM memory_decision_log
                   WHERE project_id=?
                   ORDER BY ts DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memory_decision_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d["details"] = json.loads(d.get("details_json") or "{}")
            except Exception:
                d["details"] = {}
            out.append(d)
        return out

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

    def get_episode_ids_for_strategy(
        self, strategy_profile_id: str, domain: str | None = None, limit: int = 50
    ) -> list[str]:
        """Episodes linked to this strategy via graph (used_in). If domain given, only episodes in that domain."""
        try:
            if domain:
                rows = self._conn.execute(
                    """SELECT e.to_node_id FROM memory_graph_edges e
                       INNER JOIN run_episodes r ON r.id = e.to_node_id
                       WHERE e.from_node_type = 'strategy_profile' AND e.from_node_id = ?
                         AND e.to_node_type = 'run_episode' AND r.domain = ?
                       ORDER BY e.ts DESC LIMIT ?""",
                    (strategy_profile_id, domain, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """SELECT to_node_id FROM memory_graph_edges
                       WHERE from_node_type = 'strategy_profile' AND from_node_id = ?
                         AND to_node_type = 'run_episode'
                       ORDER BY ts DESC LIMIT ?""",
                    (strategy_profile_id, limit),
                ).fetchall()
            return [str(r[0]) for r in rows if r and r[0]]
        except Exception:
            return []

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

    def build_empirical_policy(self, domain: str, min_samples: int = 3) -> dict | None:
        """
        Build a data-derived strategy policy from successful episodes in a domain.
        This is intentionally conservative and bounded for production safety.
        """
        rows = self._conn.execute(
            """SELECT plan_query_mix_json, source_mix_json, critic_score, claim_support_rate
               FROM run_episodes
               WHERE domain=? AND status='done' AND critic_score IS NOT NULL
               ORDER BY created_at DESC LIMIT 200""",
            (domain or "general",),
        ).fetchall()
        if len(rows) < max(1, int(min_samples)):
            return None

        qmix_sum: Counter[str] = Counter()
        smix_sum: Counter[str] = Counter()
        critics: list[float] = []
        supports: list[float] = []
        used = 0
        for r in rows:
            try:
                qmix = json.loads(r["plan_query_mix_json"] or "{}")
                smix = json.loads(r["source_mix_json"] or "{}")
            except Exception:
                qmix, smix = {}, {}
            if not isinstance(qmix, dict):
                qmix = {}
            if not isinstance(smix, dict):
                smix = {}
            used += 1
            for k, v in qmix.items():
                try:
                    qmix_sum[str(k).lower()] += float(v)
                except Exception:
                    continue
            for k, v in smix.items():
                try:
                    smix_sum[str(k).lower()] += float(v)
                except Exception:
                    continue
            if isinstance(r["critic_score"], (int, float)):
                critics.append(float(r["critic_score"]))
            if isinstance(r["claim_support_rate"], (int, float)):
                supports.append(float(r["claim_support_rate"]))
        if used < max(1, int(min_samples)):
            return None

        def _normalize_counter(cn: Counter[str], top_n: int = 6) -> dict[str, float]:
            if not cn:
                return {}
            items = cn.most_common(top_n)
            total = sum(v for _, v in items) or 1.0
            return {k: round(v / total, 3) for k, v in items}

        preferred_query_types = _normalize_counter(qmix_sum, top_n=3)
        required_source_mix = _normalize_counter(smix_sum, top_n=4)
        critic_avg = sum(critics) / len(critics) if critics else 0.55
        support_avg = sum(supports) / len(supports) if supports else 0.55
        policy = {
            "preferred_query_types": preferred_query_types or {"web": 0.6, "academic": 0.4},
            "required_source_mix": required_source_mix,
            "critic_threshold": round(_clamp(critic_avg * 0.95, 0.50, 0.65), 3),
            "relevance_threshold": round(_clamp(0.50 + 0.15 * support_avg, 0.50, 0.65), 3),
            "revise_rounds": int(_clamp(2 + (1 if support_avg < 0.55 else 0), 1, 4)),
            "source": "empirical",
            "samples": used,
        }
        return policy

    def upsert_empirical_strategy(self, domain: str, min_samples: int = 3) -> str | None:
        policy = self.build_empirical_policy(domain=domain, min_samples=min_samples)
        if not policy:
            return None
        score = _clamp(0.55 + 0.2 * float(policy.get("critic_threshold", 0.55)), 0.0, 1.0)
        confidence = _clamp(min(1.0, float(policy.get("samples", 0)) / 20.0), 0.25, 0.9)
        return self.upsert_strategy_profile(
            name=f"empirical-{(domain or 'general').strip().lower()}",
            domain=domain or "general",
            policy=policy,
            score=score,
            confidence=confidence,
            metadata={"profile_type": "empirical", "samples": policy.get("samples", 0)},
        )

    def synthesize_principles_from_episodes(self, domain: str, min_count: int = 3) -> list[str]:
        """
        Generate conservative guiding/cautionary principles from frequent what_helped/what_hurt signals.
        Returns inserted principle ids.
        """
        rows = self._conn.execute(
            """SELECT project_id, what_helped_json, what_hurt_json
               FROM run_episodes WHERE domain=? ORDER BY created_at DESC LIMIT 200""",
            (domain or "general",),
        ).fetchall()
        helped_counter: Counter[str] = Counter()
        hurt_counter: Counter[str] = Counter()
        recent_project = None
        for r in rows:
            recent_project = recent_project or (r["project_id"] or "unknown")
            try:
                helped = json.loads(r["what_helped_json"] or "[]")
                hurt = json.loads(r["what_hurt_json"] or "[]")
            except Exception:
                continue
            if isinstance(helped, list):
                for item in helped:
                    s = str(item).strip().lower()
                    if len(s) >= 8:
                        helped_counter[s] += 1
            if isinstance(hurt, list):
                for item in hurt:
                    s = str(item).strip().lower()
                    if len(s) >= 8:
                        hurt_counter[s] += 1

        inserted: list[str] = []
        if not recent_project:
            return inserted

        def _maybe_insert(ptype: str, text: str, cnt: int) -> None:
            if cnt < min_count:
                return
            desc = (
                f"[{domain or 'general'}] Frequent signal ({cnt} runs): {text}. "
                f"Treat this as {'recommended practice' if ptype == 'guiding' else 'risk pattern'}."
            )[:500]
            existing = self._conn.execute(
                "SELECT id FROM strategic_principles WHERE domain=? AND description=? LIMIT 1",
                (domain or "", desc),
            ).fetchone()
            if existing:
                return
            pid = hash_id(f"sp:{recent_project}:{ptype}:{desc}:{utcnow()}")
            self._conn.execute(
                """INSERT INTO strategic_principles
                   (id, principle_type, description, domain, source_project_id, evidence_json, metric_score, usage_count, success_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)""",
                (
                    pid,
                    ptype,
                    desc,
                    domain or "",
                    recent_project,
                    _safe_json([{"source": "episode_synthesis", "count": cnt, "signal": text}], []),
                    _clamp(0.45 + 0.05 * min(cnt, 8), 0.45, 0.85),
                    utcnow(),
                ),
            )
            inserted.append(pid)

        for txt, cnt in helped_counter.most_common(5):
            _maybe_insert("guiding", txt, cnt)
        for txt, cnt in hurt_counter.most_common(5):
            _maybe_insert("cautionary", txt, cnt)
        if inserted:
            self._conn.commit()
        return inserted

    def _question_hash(self, question: str) -> str:
        """Stable hash for semantic-ish dedup: normalized token signature across paraphrases."""
        return hash_id("read_urls:" + _question_signature(question))

    def record_read_urls(self, question: str, urls: list[str]) -> None:
        """Store read URLs for this question so future runs can skip them (with signature for similar-question dedup)."""
        if not urls:
            return
        qh = self._question_hash(question)
        sig = _question_signature(question)
        now = utcnow()
        for url in urls:
            u = (url or "").strip()
            if not u or "://" not in u:
                continue
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO read_urls (question_hash, url, created_at, question_signature) VALUES (?, ?, ?, ?)",
                    (qh, u[:2048], now, sig[:2000] if sig else ""),
                )
            except Exception:
                try:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO read_urls (question_hash, url, created_at) VALUES (?, ?, ?)",
                        (qh, u[:2048], now),
                    )
                except Exception:
                    pass
        self._conn.commit()

    def get_read_urls_for_question(self, question: str, similar_threshold: float = 0.6) -> set[str]:
        """Return URLs already read for this question (exact hash) or for similar questions (signature token overlap)."""
        qh = self._question_hash(question)
        sig = _question_signature(question)
        tokens = set((sig or "").split())
        out: set[str] = set()
        try:
            rows = self._conn.execute(
                "SELECT url FROM read_urls WHERE question_hash = ?",
                (qh,),
            ).fetchall()
            for r in rows:
                if r["url"]:
                    out.add(str(r["url"] or "").strip())
        except Exception:
            pass
        try:
            cur = self._conn.execute(
                "SELECT DISTINCT question_signature FROM read_urls WHERE question_signature IS NOT NULL AND question_signature != '' LIMIT 5000"
            )
            similar_sigs: list[str] = []
            for row in cur.fetchall():
                s = (row["question_signature"] or "").strip()
                if not s or s == sig:
                    continue
                row_tokens = set(s.split())
                inter = len(tokens & row_tokens)
                union = len(tokens | row_tokens)
                if union > 0 and inter / union >= similar_threshold:
                    similar_sigs.append(s)
            if similar_sigs:
                placeholders = ",".join("?" * len(similar_sigs))
                rows2 = self._conn.execute(
                    f"SELECT url FROM read_urls WHERE question_signature IN ({placeholders})",
                    similar_sigs,
                ).fetchall()
                for r in rows2:
                    if r["url"]:
                        out.add(str(r["url"] or "").strip())
        except Exception:
            pass
        return out
