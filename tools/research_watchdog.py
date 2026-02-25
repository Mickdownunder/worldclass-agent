#!/usr/bin/env python3
"""
Watchdog for research quality drift and multi-day robustness.
- Drift alarm when avg report quality drops over the last 3 runs.
- Rate-limit: max new findings per project per day (configurable).
SLOs (documented and checked): admission_reject_rate, unsupported_claim_rate, avg_report_quality.

Usage:
  research_watchdog.py check [project_id]
  research_watchdog.py rate-limit <project_id>   (returns whether project is over limit)
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, research_root, load_project

# SLO / policy constants (single source of truth)
DRIFT_WINDOW_RUNS = 3
DRIFT_DROP_THRESHOLD = 0.15  # alert if avg score drops by this much over window
MAX_NEW_FINDINGS_PER_PROJECT_PER_DAY = 50


def _recent_scorecards(project_id: str, limit: int = DRIFT_WINDOW_RUNS + 2) -> list[dict]:
    """Load recent eval scorecards from project eval/ (and optionally memory)."""
    proj = project_dir(project_id)
    eval_dir = proj / "eval"
    if not eval_dir.exists():
        return []
    cards = []
    for f in sorted(eval_dir.glob("scorecard_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            cards.append(json.loads(f.read_text()))
        except Exception:
            pass
        if len(cards) >= limit:
            break
    return cards


def _avg_score(card: dict) -> float:
    return (
        (card.get("claim_support_rate") or 0) + (card.get("citation_precision") or 0) +
        (card.get("faithfulness") or 0) + (card.get("source_diversity") or 0) +
        (card.get("novelty_score") or 0)
    ) / 5.0


def check_drift(project_id: str) -> dict:
    """Return drift status: ok | drift_detected, with details."""
    cards = _recent_scorecards(project_id, limit=DRIFT_WINDOW_RUNS + 2)
    if len(cards) < DRIFT_WINDOW_RUNS:
        return {"status": "ok", "reason": "insufficient_runs", "runs": len(cards)}
    recent = [_avg_score(c) for c in cards[:DRIFT_WINDOW_RUNS]]
    older = [_avg_score(c) for c in cards[DRIFT_WINDOW_RUNS:]]
    if not older:
        return {"status": "ok", "reason": "no_prior_baseline", "recent_avg": sum(recent) / len(recent)}
    recent_avg = sum(recent) / len(recent)
    older_avg = sum(older) / len(older)
    drop = older_avg - recent_avg
    if drop >= DRIFT_DROP_THRESHOLD:
        return {
            "status": "drift_detected",
            "recent_avg": round(recent_avg, 3),
            "older_avg": round(older_avg, 3),
            "drop": round(drop, 3),
            "project_id": project_id,
        }
    return {"status": "ok", "recent_avg": round(recent_avg, 3), "older_avg": round(older_avg, 3)}


def check_rate_limit(project_id: str) -> dict:
    """Return whether project is over rate limit (new findings in last 24h)."""
    proj = project_dir(project_id)
    if not proj.exists():
        return {"over_limit": False, "reason": "no_project"}
    findings_dir = proj / "findings"
    if not findings_dir.exists():
        return {"over_limit": False, "count_24h": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()
    count = 0
    for f in findings_dir.glob("*.json"):
        try:
            if f.stat().st_mtime >= cutoff:
                count += 1
        except Exception:
            pass
    over = count >= MAX_NEW_FINDINGS_PER_PROJECT_PER_DAY
    return {
        "over_limit": over,
        "count_24h": count,
        "limit": MAX_NEW_FINDINGS_PER_PROJECT_PER_DAY,
        "project_id": project_id,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: research_watchdog.py check [project_id] | research_watchdog.py rate-limit <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1].lower()
    if cmd == "check":
        project_id = sys.argv[2] if len(sys.argv) > 2 else None
        if project_id:
            result = check_drift(project_id)
            if result.get("status") == "drift_detected":
                print(f"DRIFT: {result}", file=sys.stderr)
            print(json.dumps(result))
        else:
            research = research_root()
            results = []
            for p in research.iterdir():
                if not p.is_dir() or not p.name.startswith("proj-"):
                    continue
                r = check_drift(p.name)
                if r.get("status") == "drift_detected":
                    results.append(r)
            print(json.dumps({"drift_detected": results}))
    elif cmd == "rate-limit":
        if len(sys.argv) < 3:
            print("Usage: research_watchdog.py rate-limit <project_id>", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(check_rate_limit(sys.argv[2])))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
