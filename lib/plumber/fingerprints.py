# Plumber fingerprint system: error tracking, cooldown, non-repairable classification.
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import constants


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error_fingerprint(workflow: str, error_text: str) -> str:
    import hashlib
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "TS", error_text)
    normalized = re.sub(r"/root/operator/jobs/\S+", "JOB_DIR", normalized)
    normalized = re.sub(r"pid[=: ]*\d+", "PID", normalized)
    normalized = re.sub(r"\b\d{6,}\b", "ID", normalized)
    key = f"{workflow}::{normalized[:500]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _load_fingerprints() -> dict:
    if constants.FINGERPRINT_DB.exists():
        try:
            return json.loads(constants.FINGERPRINT_DB.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_fingerprints(db: dict) -> None:
    constants.PLUMBER_DIR.mkdir(parents=True, exist_ok=True)
    constants.FINGERPRINT_DB.write_text(json.dumps(db, indent=2, default=str))


def record_fingerprint(
    workflow: str, error_text: str, fix_attempted: bool,
    fix_succeeded: bool, action: str, category: str = "",
) -> str:
    fp = _error_fingerprint(workflow, error_text)
    db = _load_fingerprints()
    entry = db.get(fp, {
        "fingerprint": fp,
        "workflow": workflow,
        "error_snippet": error_text[:300],
        "category": category,
        "first_seen": _utcnow(),
        "occurrences": 0,
        "fix_attempts": 0,
        "fix_successes": 0,
        "last_seen": "",
        "last_action": "",
        "non_repairable": False,
        "cooldown_until": "",
    })
    entry["occurrences"] += 1
    entry["last_seen"] = _utcnow()
    entry["last_action"] = action
    if fix_attempted:
        entry["fix_attempts"] += 1
    if fix_succeeded:
        entry["fix_successes"] += 1
    db[fp] = entry
    _save_fingerprints(db)
    return fp


def is_on_cooldown(workflow: str, error_text: str) -> tuple[bool, dict | None]:
    fp = _error_fingerprint(workflow, error_text)
    db = _load_fingerprints()
    entry = db.get(fp)
    if not entry:
        return False, None
    if entry.get("non_repairable"):
        return True, entry
    cooldown_until = entry.get("cooldown_until", "")
    if cooldown_until and cooldown_until > _utcnow():
        return True, entry
    attempts = entry.get("fix_attempts", 0)
    successes = entry.get("fix_successes", 0)
    if attempts >= constants.MAX_FIX_ATTEMPTS_PER_FINGERPRINT and successes == 0:
        cooldown_end = datetime.now(timezone.utc) + timedelta(hours=constants.COOLDOWN_HOURS)
        entry["cooldown_until"] = cooldown_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        db[fp] = entry
        _save_fingerprints(db)
        return True, entry
    return False, entry


def classify_non_repairable(error_text: str) -> tuple[str, str] | None:
    for pattern, code, explanation in constants.NON_REPAIRABLE_PATTERNS:
        if pattern.search(error_text):
            return code, explanation
    return None


def mark_non_repairable(workflow: str, error_text: str, reason_code: str,
                        category: str = "repeated_failures") -> None:
    fp = _error_fingerprint(workflow, error_text)
    db = _load_fingerprints()
    entry = db.get(fp, {
        "fingerprint": fp, "workflow": workflow,
        "error_snippet": error_text[:300], "first_seen": _utcnow(),
        "occurrences": 1, "fix_attempts": 0, "fix_successes": 0,
        "last_seen": _utcnow(), "last_action": "non_repairable",
        "non_repairable": False, "cooldown_until": "", "category": category,
    })
    entry["non_repairable"] = True
    entry["non_repairable_reason"] = reason_code
    entry["last_action"] = f"classified_non_repairable:{reason_code}"
    db[fp] = entry
    _save_fingerprints(db)


def get_fingerprint_stats() -> dict:
    db = _load_fingerprints()
    total = len(db)
    non_repairable = sum(1 for e in db.values() if e.get("non_repairable"))
    on_cooldown = sum(1 for e in db.values()
                      if e.get("cooldown_until", "") > _utcnow())
    total_occurrences = sum(e.get("occurrences", 0) for e in db.values())
    total_attempts = sum(e.get("fix_attempts", 0) for e in db.values())
    total_successes = sum(e.get("fix_successes", 0) for e in db.values())
    success_rate = (total_successes / total_attempts * 100) if total_attempts > 0 else 0
    by_category: dict[str, dict] = {}
    for e in db.values():
        cat = e.get("category") or "unknown"
        c = by_category.setdefault(cat, {"occurrences": 0, "attempts": 0, "successes": 0})
        c["occurrences"] += e.get("occurrences", 0)
        c["attempts"] += e.get("fix_attempts", 0)
        c["successes"] += e.get("fix_successes", 0)
    top_errors = sorted(db.values(), key=lambda e: e.get("occurrences", 0), reverse=True)[:5]
    return {
        "total_fingerprints": total,
        "non_repairable": non_repairable,
        "on_cooldown": on_cooldown,
        "total_occurrences": total_occurrences,
        "fix_attempts": total_attempts,
        "fix_successes": total_successes,
        "fix_success_rate_pct": round(success_rate, 1),
        "by_category": by_category,
        "top_recurring": [
            {"fingerprint": e["fingerprint"], "workflow": e.get("workflow", "?"),
             "occurrences": e.get("occurrences", 0), "snippet": e.get("error_snippet", "")[:100],
             "non_repairable": e.get("non_repairable", False)}
            for e in top_errors
        ],
    }
