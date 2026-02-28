#!/usr/bin/env python3
"""
Dynamic outline: evolving research plan that updates with each evidence batch (WebWeaver pattern).
Merge new findings into outline, identify gaps, replan. Used by conductor after each read batch.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, llm_call


def _load_plan(proj: Path) -> dict:
    p = proj / "research_plan.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _load_compressed_context(proj: Path) -> str:
    ctx = proj / "conductor_context.json"
    if not ctx.exists():
        return ""
    try:
        d = json.loads(ctx.read_text(encoding="utf-8", errors="replace"))
        return d.get("full_compressed", "") or ""
    except Exception:
        return ""


def merge_evidence_into_outline(project_id: str) -> dict:
    """
    Merge new evidence (compressed context) into research plan; identify gaps.
    Returns updated outline/plan snippet and list of gap descriptions.
    """
    proj = project_dir(project_id)
    project = load_project(proj)
    question = (project.get("question") or "")[:1000]
    plan = _load_plan(proj)
    compressed = _load_compressed_context(proj)
    topics = plan.get("topics") or []
    topics_text = json.dumps([{"id": t.get("id"), "name": t.get("name")} for t in topics[:20]], ensure_ascii=False)

    model = os.environ.get("RESEARCH_CONDUCTOR_MODEL", "gemini-2.5-flash")
    system = """You are a research planner. Given the current plan and new evidence summary:
1. Merge evidence into the outline (which topics are now supported).
2. Identify gaps (topics with little or no evidence).
Reply with JSON only: {"updated_outline": "short text", "gaps": ["gap1", "gap2"], "suggested_queries": ["query1"]}"""
    user = f"Question: {question}\n\nCurrent topics: {topics_text}\n\nNew evidence summary:\n{compressed[:3000]}\n\nReturn JSON with updated_outline, gaps, suggested_queries."
    try:
        result = llm_call(model, system, user, project_id=project_id)
        text = (result.text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1].replace("json", "", 1).strip()
        out = json.loads(text)
        if not isinstance(out, dict):
            return {"updated_outline": "", "gaps": [], "suggested_queries": []}
        # Persist for conductor
        outline_path = proj / "conductor_outline.json"
        outline_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        return out
    except Exception:
        return {"updated_outline": "", "gaps": [], "suggested_queries": []}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_dynamic_outline.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    out = merge_evidence_into_outline(project_id)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
