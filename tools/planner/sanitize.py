"""Sanitize and validate LLM plan output; inject medical queries when appropriate."""
from typing import Any

from tools.planner.helpers import extract_entities, is_medical_topic, parse_priority
from tools.planner.fallback import fallback_plan


def sanitize_plan(plan: dict[str, Any], question: str) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return fallback_plan(question)
    topics = plan.get("topics")
    queries = plan.get("queries")
    if not isinstance(topics, list) or not isinstance(queries, list):
        return fallback_plan(question)

    clean_topics: list[dict[str, Any]] = []
    for i, t in enumerate(topics, start=1):
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or f"t{i}")
        clean_topics.append(
            {
                "id": tid,
                "name": str(t.get("name") or f"Topic {i}")[:120],
                "priority": parse_priority(t.get("priority")),
                "description": str(t.get("description") or "")[:400],
                "source_types": [str(x) for x in (t.get("source_types") or ["docs"])][:4],
                "min_sources": max(1, min(5, int(t.get("min_sources") or 2))),
            }
        )
    if not clean_topics:
        return fallback_plan(question)
    topic_ids = {t["id"] for t in clean_topics}

    clean_queries: list[dict[str, Any]] = []
    for q in queries:
        if not isinstance(q, dict):
            continue
        qq = str(q.get("query") or "").strip()
        if not qq:
            continue
        qtopic = str(q.get("topic_id") or clean_topics[0]["id"])
        if qtopic not in topic_ids:
            qtopic = clean_topics[0]["id"]
        qtype = str(q.get("type") or "web").lower()
        if qtype not in {"web", "academic", "medical"}:
            qtype = "web"
        perspective = str(q.get("perspective") or "analyst")
        clean_queries.append(
            {
                "query": " ".join(qq.split())[:180],
                "topic_id": qtopic,
                "type": qtype,
                "perspective": perspective[:80],
            }
        )
    if not clean_queries:
        return fallback_plan(question)

    entities = [str(e) for e in (plan.get("entities") or []) if str(e).strip()]
    if not entities:
        entities = extract_entities(question)
    perspectives = [str(p) for p in (plan.get("perspectives") or []) if str(p).strip()]
    if not perspectives:
        perspectives = ["AI researcher", "framework developer", "enterprise user"]
    complexity = str(plan.get("complexity") or "moderate").lower()
    if complexity not in {"simple", "moderate", "complex"}:
        complexity = "moderate"
    estimated = int(plan.get("estimated_sources_needed") or (len(clean_topics) * 4))
    estimated = max(10, min(250, estimated))

    while len(clean_queries) < 15:
        base_topic = clean_topics[len(clean_queries) % len(clean_topics)]
        clean_queries.append(
            {
                "query": f"{base_topic['name']} benchmark comparison case study",
                "topic_id": base_topic["id"],
                "type": "web",
                "perspective": "enterprise user",
            }
        )

    all_text = f"{question} " + " ".join(t["name"] + " " + t.get("description", "") for t in clean_topics)
    if is_medical_topic(all_text):
        medical_queries: list[dict[str, Any]] = []
        for t in clean_topics[:5]:
            medical_queries.append({
                "query": f"{t['name']} clinical trial systematic review",
                "topic_id": t["id"],
                "type": "medical",
                "perspective": "clinical researcher",
            })
        for e in entities[:5]:
            medical_queries.append({
                "query": f"{e} randomized controlled trial meta-analysis",
                "topic_id": clean_topics[0]["id"],
                "type": "medical",
                "perspective": "medical specialist",
            })
        for q in clean_queries:
            if q["type"] == "academic":
                q["type"] = "medical"
        clean_queries.extend(medical_queries)
        if "clinical researcher" not in perspectives:
            perspectives.append("clinical researcher")
        if "medical specialist" not in perspectives:
            perspectives.append("medical specialist")

    return {
        "topics": clean_topics,
        "entities": entities[:40],
        "perspectives": perspectives[:8],
        "queries": clean_queries[:50],
        "complexity": complexity,
        "estimated_sources_needed": estimated,
    }
