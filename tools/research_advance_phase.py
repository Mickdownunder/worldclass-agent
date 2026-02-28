#!/usr/bin/env python3
"""Update project.json to the next research phase. Called from research-cycle.sh.
Usage: research_advance_phase.py <proj_dir> <next_phase>
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def advance(proj_dir: Path, new_phase: str) -> None:
    p = proj_dir / "project.json"
    d = json.loads(p.read_text())

    # Never advance a project with a terminal status
    status = d.get("status", "")
    if status.startswith("failed") or status in ("cancelled", "abandoned"):
        return

    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    prev_phase = d.get("phase", "unknown")
    prev_at = d.get("last_phase_at", "")
    if prev_at and prev_phase != new_phase:
        try:
            started = datetime.fromisoformat(prev_at.replace("Z", "+00:00"))
            duration_s = round((now - started).total_seconds(), 1)
            d.setdefault("phase_timings", {})[prev_phase] = {
                "started_at": prev_at,
                "completed_at": now_str,
                "duration_s": duration_s,
            }
        except Exception:
            pass

    d.setdefault("phase_history", []).append(new_phase)
    loop_count = d["phase_history"].count(new_phase)
    if loop_count > 3:
        order = ["explore", "focus", "connect", "verify", "synthesize", "done"]
        try:
            idx = order.index(new_phase)
            if idx < len(order) - 1:
                new_phase = order[idx + 1]
                d["phase_history"][-1] = new_phase
        except ValueError:
            pass

    d["phase"] = new_phase
    d["last_phase_at"] = now_str
    if new_phase == "done":
        d["status"] = "done"
        d["completed_at"] = now_str

    p.write_text(json.dumps(d, indent=2))


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: research_advance_phase.py <proj_dir> <next_phase>", file=sys.stderr)
        sys.exit(2)
    proj_dir = Path(sys.argv[1])
    next_phase = sys.argv[2]
    if not (proj_dir / "project.json").exists():
        print(f"Not found: {proj_dir / 'project.json'}", file=sys.stderr)
        sys.exit(1)
    advance(proj_dir, next_phase)


if __name__ == "__main__":
    main()
