#!/usr/bin/env python3
"""
Update memory utilities from project outcome: mark which retrieved principles/findings
were helpful (critic_score >= 0.7). Reads prior_knowledge.json and project.json.
Usage: research_utility_update.py <project_id>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(0)
    project_id = sys.argv[1].strip()
    proj_dir = ROOT / "research" / project_id
    if not proj_dir.is_dir():
        sys.exit(0)
    prior_path = proj_dir / "prior_knowledge.json"
    if not prior_path.exists():
        sys.exit(0)
    try:
        prior = json.loads(prior_path.read_text())
        principle_ids = prior.get("principle_ids") or []
        finding_ids = [str(x) for x in prior.get("finding_ids") or []]
    except Exception:
        sys.exit(0)
    project_json = proj_dir / "project.json"
    critic_score = 0.5
    if project_json.exists():
        try:
            d = json.loads(project_json.read_text())
            c = d.get("quality_gate", {}).get("critic_score")
            if c is not None:
                critic_score = float(c)
        except Exception:
            pass
    if not principle_ids and not finding_ids:
        sys.exit(0)
    try:
        from lib.memory import Memory
        mem = Memory()
        if principle_ids:
            mem.update_utilities_from_outcome("principle", principle_ids, critic_score)
        if finding_ids:
            mem.update_utilities_from_outcome("finding", finding_ids, critic_score)
        mem.close()
    except Exception as e:
        print(f"[utility_update] failed (non-fatal): {e}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
