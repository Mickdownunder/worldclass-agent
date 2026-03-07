"""Perspective-rotate queries from thin topics (JSON or CSV)."""
from pathlib import Path
from typing import Any

from tools.planner.plan import load_project_plan
from tools.planner.helpers import slug


def parse_thin_topics(raw: str) -> list[dict[str, Any]]:
    import json
    p = Path(raw)
    if p.exists():
        data = json.loads(p.read_text())
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            t = data.get("thin_topics")
            if isinstance(t, list):
                return [x for x in t if isinstance(x, dict)]
    topics: list[dict[str, Any]] = []
    for idx, s in enumerate([x.strip() for x in raw.split(",") if x.strip()], start=1):
        topics.append({"id": f"thin-{idx}", "name": s, "priority": 1})
    return topics


def build_perspective_rotate_queries(thin_topics_arg: str, project_id: str) -> dict[str, Any]:
    topics = parse_thin_topics(thin_topics_arg)[:10]
    plan = load_project_plan(project_id)
    perspectives = plan.get("perspectives") or ["AI researcher", "framework developer", "enterprise user"]
    rotate = ["academic", "practitioner", "comparison"]
    out_queries: list[dict[str, Any]] = []
    for t in topics:
        tid = str(t.get("id") or slug(str(t.get("name") or "topic"), "topic"))
        tname = str(t.get("name") or "topic")
        for i, ang in enumerate(rotate):
            perspective = perspectives[i % len(perspectives)]
            if ang == "academic":
                q = f"{tname} arxiv paper empirical results"
                qtype = "academic"
            elif ang == "practitioner":
                q = f"{tname} production lessons case study"
                qtype = "web"
            else:
                q = f"{tname} vs alternatives comparison benchmark"
                qtype = "web"
            out_queries.append(
                {
                    "query": " ".join(q.split())[:180],
                    "topic_id": tid,
                    "type": qtype,
                    "perspective": perspective,
                }
            )
    return {"queries": out_queries[:40]}
