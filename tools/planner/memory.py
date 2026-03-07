"""Memory v2 strategy: load/apply/persist strategy context for planner."""
import json
import os
import sqlite3
from typing import Any

from tools import research_common as _research_common


def _research_root():
    return _research_common.research_root()


def memory_v2_enabled() -> bool:
    return os.environ.get("RESEARCH_MEMORY_V2_ENABLED", "1").strip() == "1"


def min_strategy_confidence() -> float:
    try:
        value = float(os.environ.get("RESEARCH_MEMORY_V2_MIN_CONFIDENCE", "0.45"))
    except Exception:
        value = 0.45
    return max(0.25, min(0.8, value))


def domain_for_project(project_id: str) -> str:
    if not project_id:
        return "general"
    p = _research_root() / project_id / "project.json"
    if not p.exists():
        return "general"
    try:
        d = json.loads(p.read_text())
        return str(d.get("domain") or "general")
    except Exception:
        return "general"


def resample_query_types(queries: list[dict[str, Any]], preferred: dict[str, float]) -> list[dict[str, Any]]:
    if not queries:
        return queries
    weights = {
        "web": max(0.0, float(preferred.get("web", 0.0))),
        "academic": max(0.0, float(preferred.get("academic", 0.0))),
        "medical": max(0.0, float(preferred.get("medical", 0.0))),
    }
    if sum(weights.values()) <= 0.0:
        return queries
    ordered = [(k, v) for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True) if v > 0.0]
    target_types = [t for t, _ in ordered]
    if not target_types:
        return queries
    q_out = []
    bucket = []
    for idx, q in enumerate(queries):
        qq = dict(q)
        bucket.append(qq)
        if len(bucket) >= max(1, len(target_types)):
            for j, b in enumerate(bucket):
                b["type"] = target_types[(idx + j) % len(target_types)]
                q_out.append(b)
            bucket = []
    q_out.extend(bucket)
    return q_out


def load_strategy_context(question: str, project_id: str) -> dict[str, Any] | None:
    if not project_id:
        return None
    if not memory_v2_enabled():
        try:
            from lib.memory import Memory
            with Memory() as mem:
                mem.record_memory_decision(
                    decision_type="strategy_mode_detail",
                    details={"mode": "v2_disabled", "fallback_reason": "flag_off"},
                    project_id=project_id,
                    phase="planner",
                    confidence=1.0,
                )
        except Exception:
            pass
        return {
            "mode": "v2_disabled",
            "fallback_reason": "flag_off",
            "expected_benefit": "v2 is disabled; static defaults are used",
        }
    min_conf = min_strategy_confidence()
    try:
        from lib.memory import Memory
    except ImportError:
        return {
            "mode": "v2_fallback",
            "fallback_reason": "import_error",
            "expected_benefit": "memory module unavailable; safe defaults active",
        }
    try:
        domain = domain_for_project(project_id)
        with Memory() as mem:
            strategy = mem.select_strategy(question, domain=domain)
            if not strategy:
                mem.record_memory_decision(
                    decision_type="strategy_mode_detail",
                    details={"mode": "v2_fallback", "fallback_reason": "no_strategy", "domain": domain},
                    project_id=project_id,
                    phase="planner",
                    confidence=0.2,
                )
                return {
                    "mode": "v2_fallback",
                    "fallback_reason": "no_strategy",
                    "expected_benefit": "no matching strategy; safe defaults active",
                }
            policy = strategy.get("policy") or {}
            selection_confidence = float(strategy.get("selection_confidence", 0.5) or 0.5)
            if selection_confidence < min_conf:
                mem.record_memory_decision(
                    decision_type="strategy_mode_detail",
                    details={
                        "mode": "v2_fallback",
                        "fallback_reason": "low_confidence",
                        "selection_confidence": selection_confidence,
                        "min_confidence": min_conf,
                        "domain": domain,
                    },
                    project_id=project_id,
                    phase="planner",
                    strategy_profile_id=strategy.get("id"),
                    confidence=selection_confidence,
                )
                return {
                    "mode": "v2_fallback",
                    "fallback_reason": "low_confidence",
                    "confidence": selection_confidence,
                    "min_confidence": min_conf,
                    "selected_strategy": {
                        "id": strategy.get("id"),
                        "name": strategy.get("name"),
                        "domain": strategy.get("domain"),
                    },
                    "confidence_drivers": strategy.get("confidence_drivers") or {},
                    "similar_episode_count": strategy.get("similar_episode_count", 0),
                    "expected_benefit": "confidence too low; safe defaults active",
                }
            mem.record_strategy_application_event(
                project_id=project_id,
                phase="planner",
                strategy_profile_id=strategy.get("id"),
                applied_policy=policy,
                fallback_used=False,
                outcome_hint="pre-plan",
            )
            mem.record_memory_decision(
                decision_type="strategy_mode_detail",
                details={
                    "mode": "v2_applied",
                    "fallback_reason": None,
                    "strategy_profile_id": strategy.get("id"),
                    "strategy_name": strategy.get("name"),
                    "domain": domain,
                    "selection_confidence": selection_confidence,
                    "confidence_drivers": strategy.get("confidence_drivers") or {},
                    "similar_episode_count": strategy.get("similar_episode_count", 0),
                },
                project_id=project_id,
                phase="planner",
                strategy_profile_id=strategy.get("id"),
                confidence=selection_confidence,
            )
            return {
                "mode": "v2_applied",
                "fallback_reason": None,
                "selected_strategy": {
                    "id": strategy.get("id"),
                    "name": strategy.get("name"),
                    "domain": strategy.get("domain"),
                    "score": strategy.get("score"),
                    "confidence": selection_confidence,
                    "policy": policy,
                },
                "confidence_drivers": strategy.get("confidence_drivers") or {},
                "similar_episode_count": strategy.get("similar_episode_count", 0),
                "min_confidence": min_conf,
                "expected_benefit": "higher critic pass and lower revision loops on similar topics",
            }
    except sqlite3.Error:
        return {
            "mode": "v2_fallback",
            "fallback_reason": "db_error",
            "expected_benefit": "strategy DB unavailable; safe defaults active",
        }
    except Exception:
        return {
            "mode": "v2_fallback",
            "fallback_reason": "exception",
            "expected_benefit": "unexpected strategy error; safe defaults active",
        }


def apply_strategy_to_plan(plan: dict[str, Any], strategy_ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not strategy_ctx or strategy_ctx.get("mode") != "v2_applied":
        return plan
    selected = strategy_ctx.get("selected_strategy") or {}
    policy = selected.get("policy") or {}
    preferred = policy.get("preferred_query_types")
    if isinstance(preferred, dict):
        plan["queries"] = resample_query_types(plan.get("queries") or [], preferred)
    return plan


def persist_strategy_context(project_id: str, strategy_ctx: dict[str, Any] | None) -> None:
    if not project_id:
        return
    p = _research_root() / project_id / "memory_strategy.json"
    if strategy_ctx is None:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
        return
    try:
        p.write_text(json.dumps(strategy_ctx, indent=2, ensure_ascii=False))
    except Exception:
        pass
