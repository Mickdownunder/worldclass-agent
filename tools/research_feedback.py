#!/usr/bin/env python3
"""
Append feedback for a research project. Used by Telegram and UI.
Stores in research/<project_id>/feedback.jsonl. Optionally records in Memory.

Usage:
  research_feedback.py <project_id> <dig_deeper|wrong|excellent|ignore> [comment]
  research_feedback.py <project_id> redirect "<new question>"
  Or single arg (for Telegram): research_feedback.py "<project_id> <type> [comment]>"
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, save_project

VALID_TYPES = {"dig_deeper", "wrong", "excellent", "ignore", "redirect"}


def main():
    if len(sys.argv) < 2:
        print("Usage: research_feedback.py <project_id> <type> [comment]", file=sys.stderr)
        sys.exit(2)
    if len(sys.argv) == 2:
        parts = sys.argv[1].strip().split(None, 2)
        project_id = parts[0] if len(parts) >= 1 else ""
        fb_type = (parts[1] or "").lower() if len(parts) >= 2 else ""
        comment = (parts[2] or "").strip() if len(parts) >= 3 else ""
    else:
        project_id = sys.argv[1]
        fb_type = sys.argv[2].lower()
        comment = " ".join(sys.argv[3:]).strip() if len(sys.argv) > 3 else ""

    if fb_type not in VALID_TYPES:
        print(f"Invalid type. Use one of: {VALID_TYPES}", file=sys.stderr)
        sys.exit(2)

    proj_path = project_dir(project_id)
    if not proj_path.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"ts": ts, "type": fb_type, "comment": comment, "source": "cli"}

    feedback_file = proj_path / "feedback.jsonl"
    with open(feedback_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if fb_type == "redirect" and comment:
        project = load_project(proj_path)
        q_file = proj_path / "questions.json"
        if q_file.exists():
            q_data = json.loads(q_file.read_text())
            q_data.setdefault("open", []).append(comment)
            q_file.write_text(json.dumps(q_data, indent=2))
        project["phase"] = "focus"
        save_project(proj_path, project)

    print(json.dumps({"ok": True, "project_id": project_id, "type": fb_type}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
