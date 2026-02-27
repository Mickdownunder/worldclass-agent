#!/usr/bin/env python3
"""
AEM: Token governor — model routing (cheap/mid/strong), expected_ig_per_token gate.
Strong lane only if expected_ig_per_token exceeds threshold. Budget layers: global, phase, claim-level.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project
from tools.research_episode_metrics import get_last_episode_metrics
from tools.research_claim_triage import triage_claims

EXPECTED_IG_PER_TOKEN_THRESHOLD_STRONG = 0.001  # v1: strong model only if expected_ig_per_token > this
LANES = ["cheap", "mid", "strong"]
# Expected token usage by lane (v1 default) for expected_ig_per_token denominator
DEFAULT_EXPECTED_TOKENS = {"cheap": 2000, "mid": 5000, "strong": 8000}


def get_enforcement_mode() -> str:
    return (os.environ.get("AEM_ENFORCEMENT_MODE") or "observe").strip().lower()


def expected_ig_heuristic(project_id: str) -> float:
    """
    expected_ig ~= fragility_score * decision_relevance * (1 - evidence_density).
    Uses top triaged claim and portfolio evidence_density.
    """
    try:
        triaged = triage_claims(project_id, top_k=5)
        if not triaged:
            return 0.0
        # Use max impact for "expected" (best case for next step)
        fragility = sum(c.get("fragility_score", 0) for c in triaged) / len(triaged)
        relevance = sum(c.get("decision_relevance", 0.5) for c in triaged) / len(triaged)
        evidence_density = 0.5
        try:
            p = project_dir(project_id) / "portfolio" / "portfolio_state.json"
            if p.exists():
                state = json.loads(p.read_text())
                evidence_density = float(state.get("evidence_density", 0.5))
        except Exception:
            pass
        return round(fragility * relevance * (1.0 - evidence_density), 6)
    except Exception:
        return 0.0


def expected_tokens_heuristic(project_id: str, lane: str) -> float:
    """Expected token count for lane from episode_metrics or default (for expected_ig_per_token)."""
    last = get_last_episode_metrics(project_id)
    if last and last.get("tokens_spent") is not None:
        return max(1, int(last["tokens_spent"]))
    return float(DEFAULT_EXPECTED_TOKENS.get(lane, DEFAULT_EXPECTED_TOKENS["strong"]))


def recommend_lane(project_id: str, task_class: str = "default") -> str:
    """
    Recommend cheap|mid|strong. Strong only if expected_ig_per_token > threshold (spec heuristic).
    expected_ig_per_token = expected_ig / expected_cost; strong when ratio >= EXPECTED_IG_PER_TOKEN_THRESHOLD_STRONG.
    """
    proj_path = project_dir(project_id)
    if task_class in ("extraction", "dedupe", "scoring", "classification"):
        return "cheap"
    expected_ig = expected_ig_heuristic(project_id)
    tokens_strong = expected_tokens_heuristic(project_id, "strong")
    expected_ig_per_token = expected_ig / max(tokens_strong, 1.0)
    if task_class in ("synthesis", "falsification_high"):
        if expected_ig_per_token >= EXPECTED_IG_PER_TOKEN_THRESHOLD_STRONG:
            return "strong"
        return "mid"
    # Fallback: last episode ig_per_token
    last_metrics = get_last_episode_metrics(project_id)
    if last_metrics and last_metrics.get("ig_per_token") is not None:
        if float(last_metrics["ig_per_token"]) >= EXPECTED_IG_PER_TOKEN_THRESHOLD_STRONG:
            return "strong"
    return "mid"


def within_budget(project_id: str, phase: str) -> bool:
    """Check project budget (delegate to research_budget if present)."""
    try:
        from tools.research_budget import check_budget
        r = check_budget(project_id)
        return bool(r.get("ok"))
    except Exception:
        return True


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_token_governor.py recommend <project_id> [task_class]", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    task_class = sys.argv[3].strip() if len(sys.argv) > 3 else "default"
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "recommend":
        lane = recommend_lane(project_id, task_class)
        print(json.dumps({"lane": lane, "task_class": task_class}))
    else:
        print("Unknown command: use recommend", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
