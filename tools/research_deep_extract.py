#!/usr/bin/env python3
"""
Extract 2-5 key facts per high-quality source (content > 3000 chars) for deeper reports.
Adds findings with source="deep_extract". Run after explore and focus read loops.

Usage:
  research_deep_extract.py <project_id>
"""
import json
import os
import re
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, llm_call

MIN_CONTENT_LEN = 3000
EXTRACT_MODEL = "gpt-4.1-mini"


def _llm_json(system: str, user: str, project_id: str = "") -> list:
    result = llm_call(EXTRACT_MODEL, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
    try:
        out = json.loads(text)
        if isinstance(out, dict) and "facts" in out:
            return out["facts"]
        if isinstance(out, list):
            return out[:5]
    except Exception:
        pass
    return []


def run(project_id: str) -> int:
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    sources_dir = proj_path / "sources"
    findings_dir = proj_path / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for f in sources_dir.glob("*.json"):
        if "_content" not in f.name:
            continue
        try:
            d = json.loads(f.read_text())
            text = (d.get("text") or d.get("abstract") or "").strip()
        except Exception:
            continue
        if len(text) < MIN_CONTENT_LEN:
            continue
        base_id = f.stem.replace("_content", "")
        url = ""
        title = ""
        meta = sources_dir / f"{base_id}.json"
        if meta.exists():
            try:
                m = json.loads(meta.read_text())
                url = (m.get("url") or "").strip()
                title = (m.get("title") or "").strip()
            except Exception:
                pass
        system = """Extract 2-5 key facts or claims from the text. Return JSON: {"facts": ["fact one", "fact two", ...]}.
Each fact should be a single sentence or short paragraph. Be specific (numbers, dates, names)."""
        user = f"TEXT:\n{text[:8000]}\n\nReturn only valid JSON with key 'facts'."
        facts = _llm_json(system, user, project_id=project_id)
        for i, fact in enumerate(facts):
            if not isinstance(fact, str) or len(fact.strip()) < 10:
                continue
            fid = hashlib.sha256((url + fact[:200] + str(i)).encode()).hexdigest()[:12]
            out_path = findings_dir / f"{fid}.json"
            if out_path.exists():
                continue
            out_path.write_text(json.dumps({
                "url": url,
                "title": title,
                "excerpt": fact.strip()[:4000],
                "source": "deep_extract",
                "confidence": 0.55,
            }, indent=2))
            added += 1
    return added


def main():
    if len(sys.argv) < 2:
        print("Usage: research_deep_extract.py <project_id>", file=sys.stderr)
        sys.exit(2)
    try:
        n = run(sys.argv[1])
        print(n)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
