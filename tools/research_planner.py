#!/usr/bin/env python3
"""
Create an LLM-driven research plan and adaptive follow-up query batches.

Modes:
- default: plan from QUESTION (+ optional PROJECT_ID)
- --gap-fill <coverage_json> <PROJECT_ID>
- --perspective-rotate <thin_topics_json_or_csv> <PROJECT_ID>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import llm_call, research_root


PLANNER_MODEL = "gpt-4.1-mini"


def _json_only(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].replace("json", "", 1).strip()
    return json.loads(t)


def _slug(s: str, fallback: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out or fallback


_MEDICAL_KEYWORDS = frozenset({
    "medical", "medicine", "clinical", "disease", "therapy", "treatment",
    "drug", "pharmaceutical", "vaccine", "cancer", "tumor", "oncology",
    "surgery", "diagnosis", "patient", "health", "hospital", "symptom",
    "chronic", "acute", "infection", "virus", "bacteria", "antibiotic",
    "cardiac", "cardiovascular", "diabetes", "insulin", "mrna", "rna",
    "dna", "gene", "genetic", "genomic", "protein", "biomarker",
    "trial", "placebo", "efficacy", "mortality", "morbidity",
    "epidemiology", "pandemic", "pathology", "radiology", "neurology",
    "psychiatry", "immunology", "allergy", "inflammation", "transplant",
    "stem cell", "biopsy", "chemotherapy", "radiation", "prognosis",
    "fda", "ema", "who", "nih", "cdc", "pubmed", "lancet", "nejm",
    "alzheimer", "parkinson", "dementia", "stroke", "hypertension",
    "obesity", "cholesterol", "lung", "liver", "kidney", "brain",
    "mental health", "depression", "anxiety", "adhd", "autism",
    "pediatric", "geriatric", "pregnancy", "prenatal", "neonatal",
    "impfstoff", "krebs", "therapie", "krankheit", "medizin",
    "gesundheit", "arzt", "klinisch", "studie", "behandlung",
})


def _is_medical_topic(text: str) -> bool:
    text_lower = text.lower()
    matches = sum(1 for kw in _MEDICAL_KEYWORDS if kw in text_lower)
    return matches >= 2


def _extract_entities(question: str) -> list[str]:
    seen: set[str] = set()
    entities: list[str] = []
    pattern = r"\b([A-Z][A-Za-z0-9\-\+]{2,}(?:\s+[A-Z][A-Za-z0-9\-\+]{2,}){0,3})\b"
    for m in re.finditer(pattern, question):
        cand = m.group(1).strip()
        if len(cand) < 3:
            continue
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        entities.append(cand)
    return entities[:20]


def _fallback_plan(question: str) -> dict[str, Any]:
    entities = _extract_entities(question)
    words = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", question)
        if w.lower() not in {"what", "which", "when", "where", "with", "from", "about", "into", "than", "that", "this"}
    ]
    top_terms = []
    for w in words:
        wl = w.lower()
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

    perspectives = ["AI researcher", "framework developer", "enterprise user"]
    queries: list[dict[str, Any]] = []
    for i, e in enumerate(entities):
        topic_id = topics[i % len(topics)]["id"]
        queries.append(
            {
                "query": f"{e} architecture benchmark paper",
                "topic_id": topic_id,
                "type": "academic",
                "perspective": "AI researcher",
            }
        )
    for i, t in enumerate(topics):
        for p in perspectives[:2]:
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


def _sanitize_plan(plan: dict[str, Any], question: str) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return _fallback_plan(question)
    topics = plan.get("topics")
    queries = plan.get("queries")
    if not isinstance(topics, list) or not isinstance(queries, list):
        return _fallback_plan(question)

    clean_topics: list[dict[str, Any]] = []
    for i, t in enumerate(topics, start=1):
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or f"t{i}")
        clean_topics.append(
            {
                "id": tid,
                "name": str(t.get("name") or f"Topic {i}")[:120],
                "priority": int(t.get("priority") or 2),
                "description": str(t.get("description") or "")[:400],
                "source_types": [str(x) for x in (t.get("source_types") or ["docs"])][:4],
                "min_sources": max(1, min(5, int(t.get("min_sources") or 2))),
            }
        )
    if not clean_topics:
        return _fallback_plan(question)
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
        return _fallback_plan(question)

    entities = [str(e) for e in (plan.get("entities") or []) if str(e).strip()]
    if not entities:
        entities = _extract_entities(question)
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

    # Auto-detect medical topics and inject PubMed queries
    all_text = f"{question} " + " ".join(t["name"] + " " + t.get("description", "") for t in clean_topics)
    if _is_medical_topic(all_text):
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
        # Upgrade existing academic queries to medical for medical topics
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


def build_plan(question: str, project_id: str) -> dict[str, Any]:
    system = "You are a senior research strategist planning a comprehensive investigation."
    user = f"""
QUESTION: {question}

Create a research plan. Return JSON with keys:
1) topics: [{{id,name,priority,description,source_types,min_sources}}]
2) entities: [specific systems/papers/people]
3) perspectives: [3-6 perspectives]
4) queries: [{{query,topic_id,type,perspective}}]
   - 15-30 queries
   - English
   - max 10 words each
   - every entity gets at least one dedicated query
   - each topic gets queries from multiple perspectives
   - type: "web" | "academic" | "medical"
   - Use "medical" for health/biomedical/clinical queries (searches PubMed)
   - Use "academic" for scientific/technical papers (Semantic Scholar + ArXiv)
   - Use "web" for general information
5) complexity: simple|moderate|complex
6) estimated_sources_needed: integer

Return ONLY JSON.
""".strip()
    try:
        resp = llm_call(PLANNER_MODEL, system, user, project_id=project_id)
        return _sanitize_plan(_json_only(resp.text), question)
    except Exception:
        return _fallback_plan(question)


def _load_project_plan(project_id: str) -> dict[str, Any]:
    plan_path = research_root() / project_id / "research_plan.json"
    if not plan_path.exists():
        return {"topics": [], "entities": [], "perspectives": []}
    try:
        return json.loads(plan_path.read_text())
    except Exception:
        return {"topics": [], "entities": [], "perspectives": []}


def build_gap_fill_queries(coverage_path: str, project_id: str) -> dict[str, Any]:
    if project_id:
        try:
            from tools.research_progress import step as progress_step
            progress_step(project_id, "Planning focus queries")
        except Exception:
            pass
    p = Path(coverage_path)
    if not p.exists():
        return {"queries": []}
    cov = json.loads(p.read_text())
    uncovered = cov.get("uncovered_topics", [])
    plan = _load_project_plan(project_id)
    perspectives = plan.get("perspectives") or ["AI researcher", "framework developer", "enterprise user"]
    entities = [str(e) for e in (plan.get("entities") or [])]
    out_queries: list[dict[str, Any]] = []
    for i, t in enumerate(uncovered[:8]):
        tid = str(t.get("id") or f"gap-{i+1}")
        name = str(t.get("name") or "topic").strip()
        desc = str(t.get("description") or "").strip()
        prio = int(t.get("priority") or 2)
        pset = perspectives[:3] if prio == 1 else perspectives[:2]
        for p in pset:
            q = f"{name} {desc[:40]} evidence comparison".strip()
            out_queries.append(
                {
                    "query": " ".join(q.split())[:180],
                    "topic_id": tid,
                    "type": "academic" if prio == 1 else "web",
                    "perspective": p,
                }
            )
        for e in entities[:4]:
            if e.lower() in f"{name} {desc}".lower():
                out_queries.append(
                    {
                        "query": f"{e} {name} benchmark study",
                        "topic_id": tid,
                        "type": "academic",
                        "perspective": "AI researcher",
                    }
                )
    return {"queries": out_queries[:40]}


def _parse_thin_topics(raw: str) -> list[dict[str, Any]]:
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
    topics = _parse_thin_topics(thin_topics_arg)[:10]
    plan = _load_project_plan(project_id)
    perspectives = plan.get("perspectives") or ["AI researcher", "framework developer", "enterprise user"]
    rotate = ["academic", "practitioner", "comparison"]
    out_queries: list[dict[str, Any]] = []
    for t in topics:
        tid = str(t.get("id") or _slug(str(t.get("name") or "topic"), "topic"))
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


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: research_planner.py <question> [project_id] | --gap-fill <coverage_json> <project_id> | --perspective-rotate <thin_topics_json_or_csv> <project_id>",
            file=sys.stderr,
        )
        sys.exit(2)

    if sys.argv[1] == "--gap-fill":
        if len(sys.argv) < 4:
            sys.exit(2)
        result = build_gap_fill_queries(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if sys.argv[1] == "--perspective-rotate":
        if len(sys.argv) < 4:
            sys.exit(2)
        result = build_perspective_rotate_queries(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    question = sys.argv[1]
    project_id = sys.argv[2] if len(sys.argv) > 2 else ""
    result = build_plan(question, project_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
