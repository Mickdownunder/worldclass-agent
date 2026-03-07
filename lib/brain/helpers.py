"""Pure helpers: time, trace, secrets, reflection signal, state compaction."""
import hashlib
import json
import time
from datetime import datetime, timezone

from lib.brain.constants import (
    CONF,
    _REFLECTION_FAILURE_KEYWORDS,
    _REFLECTION_GENERIC_LEARNINGS_PREFIXES,
    _REFLECTION_GENERIC_OUTCOMES,
)


def _reflection_is_low_signal(outcome: str, learnings: str, quality: float) -> bool:
    """True if reflection is generic/redundant with no actionable value for planning."""
    out = (outcome or "").strip().lower()
    learn = (learnings or "").strip().lower()
    if not out:
        return True
    if any(k in out for k in _REFLECTION_FAILURE_KEYWORDS):
        return False
    if out in _REFLECTION_GENERIC_OUTCOMES or "completed successfully" in out:
        if len(learn) < 25 or any(learn.startswith(p) for p in _REFLECTION_GENERIC_LEARNINGS_PREFIXES):
            return True
    if len(learn) < 15 and 0.4 <= quality <= 0.85:
        return True
    return False


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trace_id() -> str:
    return hashlib.sha256(f"trace:{time.time_ns()}".encode()).hexdigest()[:12]


def _compact_state_for_think(state: dict, limit: int = 12000) -> str:
    """Prioritize high-signal state slices before truncation."""
    priority = {
        "system": state.get("system", {}),
        "governance": state.get("governance", {}),
        "workflow_health": state.get("workflow_health", {}),
        "workflow_trends": state.get("workflow_trends", {}),
        "research_projects": state.get("research_projects", [])[:12],
        "research_context": state.get("research_context", {}),
        "research_playbooks": state.get("research_playbooks", [])[:12],
        "memory": {
            "totals": ((state.get("memory") or {}).get("totals") or {}),
            "recent_reflections": ((state.get("memory") or {}).get("recent_reflections") or [])[:8],
        },
        "recent_jobs": state.get("recent_jobs", [])[:12],
    }
    payload = json.dumps(priority, indent=2, default=str)
    if len(payload) <= limit:
        return payload
    return payload[:limit] + "\n... (truncated)"


def _load_secrets() -> dict[str, str]:
    secrets = {}
    path = CONF / "secrets.env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()
    return secrets
