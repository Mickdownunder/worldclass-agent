"""State summary aggregation for the Memory facade. No direct DB access beyond what Memory exposes."""
import json as _json


def build_state_summary(memory) -> dict:
    """Build the aggregated state summary dict used by Memory.state_summary()."""
    total_episodes = memory._conn.execute("SELECT COUNT(*) as c FROM episodes").fetchone()["c"]
    total_decisions = memory._conn.execute("SELECT COUNT(*) as c FROM decisions").fetchone()["c"]
    total_reflections = memory._conn.execute("SELECT COUNT(*) as c FROM reflections").fetchone()["c"]
    avg_q = memory.avg_quality()
    recent_eps = memory.recent_episodes(limit=5)
    recent_refs = memory.recent_reflections(limit=3)
    playbooks = memory.all_playbooks()
    recent_failures = memory._conn.execute(
        "SELECT * FROM reflections WHERE quality < 0.4 ORDER BY ts DESC LIMIT 3"
    ).fetchall()
    total_principles = memory._conn.execute("SELECT COUNT(*) as c FROM strategic_principles").fetchone()["c"]
    total_outcomes = memory.count_project_outcomes()
    try:
        total_run_episodes = memory._conn.execute("SELECT COUNT(*) as c FROM run_episodes").fetchone()["c"]
    except Exception:
        total_run_episodes = 0
    memory_value = memory._v2.get_memory_value_score()
    try:
        recent_run_rows = memory._conn.execute(
            """SELECT id, project_id, question, domain, status, critic_score,
                      what_helped_json, what_hurt_json, strategy_profile_id, run_index, created_at, memory_mode
               FROM run_episodes ORDER BY created_at DESC LIMIT 20"""
        ).fetchall()
    except Exception:
        recent_run_rows = []

    def _run_episode_row(r) -> dict:
        q = (r["question"] or "")[:100]
        helped_raw = r["what_helped_json"] or "[]"
        hurt_raw = r["what_hurt_json"] or "[]"
        try:
            helped = _json.loads(helped_raw) if isinstance(helped_raw, str) else helped_raw
            hurt = _json.loads(hurt_raw) if isinstance(hurt_raw, str) else hurt_raw
        except Exception:
            helped, hurt = [], []
        helped_preview = ", ".join(str(x)[:40] for x in (helped[:2] if isinstance(helped, list) else [])) or "—"
        hurt_preview = ", ".join(str(x)[:40] for x in (hurt[:2] if isinstance(hurt, list) else [])) or "—"
        return {
            "id": r["id"],
            "project_id": r["project_id"],
            "question": q,
            "domain": r["domain"] or "—",
            "status": r["status"],
            "critic_score": round(r["critic_score"], 3) if r["critic_score"] is not None else None,
            "what_helped": helped_preview,
            "what_hurt": hurt_preview,
            "strategy_profile_id": r["strategy_profile_id"],
            "run_index": r["run_index"],
            "created_at": r["created_at"],
            "memory_mode": r["memory_mode"],
        }

    recent_run_episodes = [_run_episode_row(dict(r)) for r in recent_run_rows]
    consolidation = None
    try:
        cpath = memory._path.parent / "consolidation_last.json"
        if cpath.exists():
            consolidation = _json.loads(cpath.read_text())
    except Exception:
        pass

    return {
        "totals": {
            "episodes": total_episodes,
            "decisions": total_decisions,
            "reflections": total_reflections,
            "avg_quality": round(avg_q, 3),
            "principles": total_principles,
            "outcomes": total_outcomes,
            "run_episodes": total_run_episodes,
            "memory_value": memory_value,
        },
        "recent_episodes": [{"kind": e["kind"], "content": e["content"][:120], "ts": e["ts"]} for e in recent_eps],
        "recent_run_episodes": recent_run_episodes,
        "consolidation": consolidation,
        "recent_reflections": [
            {"job_id": r["job_id"], "quality": r["quality"], "learnings": (r["learnings"] or "")[:150], "ts": r["ts"]}
            for r in recent_refs
        ],
        "recent_failures": [
            {"job_id": dict(r)["job_id"], "went_wrong": (dict(r)["went_wrong"] or "")[:150], "ts": dict(r)["ts"]}
            for r in recent_failures
        ],
        "playbooks": [{"domain": p["domain"], "strategy": p["strategy"][:150], "success_rate": p["success_rate"]} for p in playbooks],
    }
