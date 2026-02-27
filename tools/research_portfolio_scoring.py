#!/usr/bin/env python3
"""
AEM: Anti-gaming portfolio scoring. evidence flooding penalty, redundant claim penalty.
Writes portfolio/portfolio_state.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl

PORTFOLIO_DIR = "portfolio"
PORTFOLIO_FILENAME = "portfolio_state.json"


def run_portfolio_scoring(project_id: str) -> dict:
    """Compute portfolio state: evidence_density, duplicate_penalty, flood_penalty, score."""
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    evidence_density = 0.0
    total_sources = 0
    for c in claims:
        srcs = c.get("supporting_source_ids") or []
        total_sources += len(srcs)
    if claims:
        evidence_density = min(1.0, round(total_sources / (len(claims) * 5), 4))  # cap at 5 sources/claim
    flood_penalty = max(0, evidence_density - 0.8) * 0.2  # penalty if > 80% density
    duplicate_penalty = 0.0  # TODO: semantic duplicate detection
    score = max(0, 1.0 - flood_penalty - duplicate_penalty)
    state = {
        "evidence_density": evidence_density,
        "flood_penalty": round(flood_penalty, 4),
        "duplicate_penalty": round(duplicate_penalty, 4),
        "portfolio_score": round(score, 4),
        "claims_count": len(claims),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (proj_path / PORTFOLIO_DIR).mkdir(parents=True, exist_ok=True)
    (proj_path / PORTFOLIO_DIR / PORTFOLIO_FILENAME).write_text(json.dumps(state, indent=2), encoding="utf-8")
    audit_log(proj_path, "aem_portfolio_scoring_run", {"portfolio_score": score})
    return state


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_portfolio_scoring.py run <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "run":
        state = run_portfolio_scoring(project_id)
        print(json.dumps(state))
    else:
        print("Unknown command: use run", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
