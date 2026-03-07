"""Fallback plan when LLM is unavailable or returns invalid JSON."""
import re
from typing import Any

from tools.planner.helpers import extract_entities, is_medical_topic
from tools.planner.constants import TOPIC_STOPWORDS


def fallback_plan(question: str) -> dict[str, Any]:
    entities = extract_entities(question)
    is_medical = is_medical_topic(question)
    words = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", question)
        if w.lower() not in {"what", "which", "when", "where", "with", "from", "about", "into", "than", "that", "this"}
    ]
    top_terms = []
    for w in words:
        wl = w.lower()
        if wl in TOPIC_STOPWORDS:
            continue
        if wl not in top_terms:
            top_terms.append(wl)
    top_terms = top_terms[:8]

    topics: list[dict[str, Any]] = []
    for idx, term in enumerate(top_terms[:6], start=1):
        topics.append(
            {
                "id": f"t{idx}",
                "name": term.replace("-", " ").title(),
                "priority": 1 if idx <= 2 else (2 if idx <= 4 else 3),
                "description": f"Evidence and sources around {term}.",
                "source_types": ["docs", "paper"] if idx <= 3 else ["docs"],
                "min_sources": 2 if idx <= 3 else 1,
            }
        )
    if not topics:
        topics = [
            {
                "id": "t1",
                "name": "Core topic",
                "priority": 1,
                "description": "Core aspects required to answer the question.",
                "source_types": ["docs", "paper"],
                "min_sources": 2,
            }
        ]

    if not entities:
        entities = [question[:60]]

    if is_medical:
        perspectives = ["clinical researcher", "medical specialist", "systematic reviewer"]
    else:
        perspectives = ["AI researcher", "framework developer", "enterprise user"]

    queries: list[dict[str, Any]] = []
    for i, e in enumerate(entities):
        topic_id = topics[i % len(topics)]["id"]
        if is_medical:
            qtype = "medical" if i % 3 != 2 else "web"
            queries.append(
                {
                    "query": f"{e} clinical trial systematic review" if qtype == "medical" else f"{e} latest results evidence",
                    "topic_id": topic_id,
                    "type": qtype,
                    "perspective": "clinical researcher",
                }
            )
        else:
            queries.append(
                {
                    "query": f"{e} architecture benchmark paper",
                    "topic_id": topic_id,
                    "type": "academic",
                    "perspective": "AI researcher",
                }
            )
    for i, t in enumerate(topics):
        for j, p in enumerate(perspectives[:2]):
            if is_medical:
                qtype = "medical" if (i + j) % 3 != 2 else "web"
                queries.append(
                    {
                        "query": f"{t['name']} clinical data outcomes evidence" if qtype == "medical" else f"{t['name']} latest research findings",
                        "topic_id": t["id"],
                        "type": qtype,
                        "perspective": p,
                    }
                )
            else:
                queries.append(
                    {
                        "query": f"{t['name']} best practices comparison",
                        "topic_id": t["id"],
                        "type": "web" if i % 2 else "academic",
                        "perspective": p,
                    }
                )
    while len(queries) < 15:
        t = topics[len(queries) % len(topics)]
        if is_medical:
            qtype = "medical" if len(queries) % 3 != 2 else "web"
            queries.append(
                {
                    "query": f"{t['name']} randomized controlled trial meta-analysis" if qtype == "medical" else f"{t['name']} latest news update",
                    "topic_id": t["id"],
                    "type": qtype,
                    "perspective": "systematic reviewer",
                }
            )
        else:
            queries.append(
                {
                    "query": f"{t['name']} implementation pitfalls benchmarks",
                    "topic_id": t["id"],
                    "type": "web",
                    "perspective": "framework developer",
                }
            )

    return {
        "topics": topics,
        "entities": entities,
        "perspectives": perspectives,
        "queries": queries[:30],
        "complexity": "moderate" if len(topics) > 3 else "simple",
        "estimated_sources_needed": max(20, len(topics) * 4),
    }
