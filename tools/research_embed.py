#!/usr/bin/env python3
"""
Index research findings into Memory with OpenAI embeddings (text-embedding-3-small).
Call after new findings are added. Reads from research/<project_id>/findings/*.json.

Usage:
  research_embed.py [project_id]
  If project_id omitted, indexes all projects under research/.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import research_root, load_secrets
from lib.memory import Memory

EMBEDDING_MODEL = "text-embedding-3-small"


def get_embedding(text: str, client) -> list[float]:
    if not text or not text.strip():
        return []
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text[:8000])
    return resp.data[0].embedding


def main():
    from openai import OpenAI
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    memory = Memory()

    research = research_root()
    if not research.exists():
        print("No research root", file=sys.stderr)
        return 0

    project_ids = [p.name for p in research.iterdir() if p.is_dir() and p.name.startswith("proj-")]
    if len(sys.argv) >= 2:
        project_ids = [sys.argv[1]]

    indexed = 0
    for project_id in project_ids:
        findings_dir = research / project_id / "findings"
        if not findings_dir.exists():
            continue
        for f in findings_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            content = (data.get("excerpt") or data.get("title") or data.get("url") or "")[:4000]
            if not content:
                continue
            finding_key = f.stem
            # Check if already in memory with same key (avoid re-embedding)
            existing = memory._conn.execute(
                "SELECT id FROM research_findings WHERE project_id=? AND finding_key=?", (project_id, finding_key)
            ).fetchone()
            if existing:
                continue
            try:
                emb = get_embedding(content, client)
                emb_json = json.dumps(emb) if emb else None
            except Exception as e:
                print(f"Embedding failed {finding_key}: {e}", file=sys.stderr)
                emb_json = None
            memory.insert_research_finding(
                project_id=project_id,
                finding_key=finding_key,
                content_preview=content[:500],
                embedding_json=emb_json,
                url=data.get("url"),
                title=data.get("title"),
            )
            indexed += 1
    print(f"Indexed {indexed} findings", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
