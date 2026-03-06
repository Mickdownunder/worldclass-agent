#!/usr/bin/env python3
"""Cancel all research projects matching prefix (set status=cancelled)."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
research = root / "research"
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

prefix = sys.argv[1] if len(sys.argv) > 1 else "proj-20260306"
cancelled = 0
for d in sorted(research.iterdir()):
    if not d.is_dir() or not d.name.startswith(prefix):
        continue
    p = d / "project.json"
    if not p.exists():
        continue
    try:
        data = json.loads(p.read_text())
        data["status"] = "cancelled"
        data["cancelled_at"] = now
        data["completed_at"] = now
        p.write_text(json.dumps(data, indent=2))
        print("Cancelled", d.name)
        cancelled += 1
    except Exception as e:
        print("Error", d.name, e, file=sys.stderr)
print("Done.", cancelled, "project(s) cancelled.")
