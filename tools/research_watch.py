#!/usr/bin/env python3
"""
Watch mode: check for updates on done research projects (re-run search, compare sources).
Usage:
  research_watch.py check <project_id>   -> JSON { new_sources, changed_sources, needs_update }
  research_watch.py briefing <project_id> [changes_json]  -> Markdown update briefing
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, ensure_project_layout


def _load_sources(proj_path: Path) -> list[dict]:
    sources = []
    for f in (proj_path / "sources").glob("*.json"):
        if f.name.endswith("_content.json"):
            continue
        try:
            sources.append(json.loads(f.read_text()))
        except Exception:
            pass
    return sources


def check_for_updates(project_id: str) -> dict:
    """Re-run search with project question, compare URLs to stored sources."""
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        return {"error": f"Project not found: {project_id}", "needs_update": False}
    project = load_project(proj_path)
    question = project.get("question", "")
    if not question:
        return {"new_sources": [], "changed_sources": [], "needs_update": False}
    existing_urls = {s.get("url", "").strip() for s in _load_sources(proj_path) if s.get("url")}
    # Run web search (same as cycle)
    tools = Path(__file__).resolve().parent
    import subprocess
    r = subprocess.run(
        [sys.executable, str(tools / "research_web_search.py"), question, "--max", "15"],
        capture_output=True, text=True, timeout=30, cwd=str(proj_path),
    )
    new_sources = []
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            for item in (data if isinstance(data, list) else []):
                url = (item.get("url") or "").strip()
                if url and url not in existing_urls:
                    new_sources.append(item)
        except Exception:
            pass
    return {
        "new_sources": new_sources,
        "changed_sources": [],  # Could add diff of content; skip for now
        "needs_update": len(new_sources) > 0,
    }


def generate_update_briefing(project_id: str, changes: dict) -> str:
    """Produce short markdown briefing from new/changed sources."""
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        return "# Update\n\nProject not found."
    project = load_project(proj_path)
    question = project.get("question", "")
    new_sources = changes.get("new_sources", [])[:10]
    if not new_sources:
        return f"# Update: {project_id}\n\nNo new sources since last check.\n"
    lines = [f"# Update: {project_id}", f"**Question:** {question}", "", "## New sources", ""]
    for s in new_sources:
        title = s.get("title", "") or "(no title)"
        url = s.get("url", "")
        lines.append(f"- [{title}]({url})")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: research_watch.py check <project_id> | research_watch.py briefing <project_id> [changes.json]", file=sys.stderr)
        sys.exit(2)
    mode = sys.argv[1].lower()
    project_id = sys.argv[2]
    if mode == "check":
        result = check_for_updates(project_id)
        # Update last_checked and optionally update_count in project.json
        proj_path = project_dir(project_id)
        if proj_path.exists():
            project = load_project(proj_path)
            watch = project.get("watch") or {}
            watch["last_checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if result.get("needs_update"):
                watch["update_count"] = watch.get("update_count", 0) + 1
            project["watch"] = watch
            (proj_path / "project.json").write_text(json.dumps(project, indent=2))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif mode == "briefing":
        changes = {}
        if len(sys.argv) > 3:
            try:
                changes = json.loads(Path(sys.argv[3]).read_text())
            except Exception:
                pass
        else:
            # Run check to get current changes
            changes = check_for_updates(project_id)
        out = generate_update_briefing(project_id, changes)
        print(out)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
