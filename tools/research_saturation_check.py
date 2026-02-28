#!/usr/bin/env python3
"""
Tier 2b: Evidence saturation check. Load last 10 findings by mtime;
if >= 7 have novelty_score < 0.2, log to stderr. No pipeline control change.

Usage: research_saturation_check.py <project_dir>
"""
import json
import sys
from pathlib import Path

def main() -> int:
    """Exit 0 = no saturation, 1 = saturation detected (caller may skip further reads)."""
    if len(sys.argv) < 2:
        return 0
    proj_dir = Path(sys.argv[1])
    findings_dir = proj_dir / "findings"
    if not findings_dir.exists():
        return 0
    paths = sorted(findings_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
    if len(paths) < 10:
        return 0
    low_novelty = 0
    for p in paths:
        try:
            d = json.loads(p.read_text())
            ns = d.get("novelty_score")
            if ns is not None and float(ns) < 0.2:
                low_novelty += 1
        except Exception:
            pass
    if low_novelty >= 7:
        print(
            f"Evidence saturation detected ({low_novelty}/10 recent findings low novelty). Skipping further refinement/gap/depth reads this round.",
            file=sys.stderr,
        )
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
