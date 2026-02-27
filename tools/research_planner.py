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
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import llm_call, research_root


PLANNER_MODEL = os.environ.get("RESEARCH_PLANNER_MODEL", "gemini-2.5-flash")


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
    "pdac", "crc", "nsclc", "sclc", "hcc", "rcc", "aml", "cll", "dlbcl",
    "melanoma", "melanom", "glioblastoma", "glioblastom", "sarcoma", "sarkom",
    "adenocarcinoma", "adenokarzinom", "carcinoma", "karzinom",
    "phase-1", "phase-2", "phase-3", "phase 1", "phase 2", "phase 3",
    "phase-ii", "phase-iii", "clinical trial", "klinische studie",
    "randomized", "randomisiert", "double-blind", "doppelblind",
    "recurrence-free", "disease-free", "progression-free", "overall survival",
    "rfs", "dfs", "pfs", "orr", "objective response",
    "t-zell", "t cell", "t-cell", "cd8", "cd4", "neoantigen", "neoantigen",
    "immunotherapy", "immuntherapie", "checkpoint inhibitor",
    "pd-l1", "pd-1", "atezolizumab", "pembrolizumab", "nivolumab",
    "cevumeran", "autogene", "bnt122", "ro7198457",
    "mrna vaccine", "mrna-impfstoff", "cancer vaccine", "krebsimpfstoff",
    "oncology", "onkologie", "tumor", "tumour", "metastasis", "metastase",
    "adjuvant", "neoadjuvant", "resected", "reseziert",
    "asco", "esmo", "aacr", "sabcs",
})


_NON_CLINICAL_MARKERS = {
    "manufacturing", "skalierung", "scaling", "yield", "purity",
    "cost-reduction", "cost reduction", "formulation", "formulierung",
    "supply chain", "lieferkette", "production", "produktion",
    "factory", "fabrik", "gmp", "fill-finish", "lyophilization",
    "thermostabil", "thermostable", "cold chain", "shelf life",
    "upstream", "downstream", "bioreactor", "fermentation",
}


def _is_medical_topic(text: str) -> bool:
    text_lower = text.lower()
    non_clinical = sum(1 for kw in _NON_CLINICAL_MARKERS if kw in text_lower)
    if non_clinical >= 2:
        return False
    matches = sum(1 for kw in _MEDICAL_KEYWORDS if kw in text_lower)
    return matches >= 3


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
        words = key.split()
        if all(w in _TOPIC_STOPWORDS for w in words):
            continue
        seen.add(key)
        entities.append(cand)
    return entities[:20]


_TOPIC_STOPWORDS = {
    "neueste", "neuesten", "neuste", "neusten", "latest", "newest", "recent",
    "daten", "data", "inklusive", "including", "sowie", "also", "und", "and",
    "the", "die", "der", "das", "eine", "ein", "aus", "von", "mit", "for",
    "über", "nach", "zum", "zur", "beim",
    "welche", "welcher", "welches", "which", "what",
    "fortschritte", "fortschritt", "progress", "advances",
    "gemacht", "macht", "made", "makes",
    "gibt", "gibt's", "there", "have", "has", "been",
    "how", "wie", "warum", "why", "wann", "when",
    "kann", "können", "could", "should", "would",
    "sehr", "mehr", "most", "some", "many", "alle", "all",
    "neue", "neuer", "neues", "new",
}


def _fallback_plan(question: str) -> dict[str, Any]:
    entities = _extract_entities(question)
    is_medical = _is_medical_topic(question)
    words = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", question)
        if w.lower() not in {"what", "which", "when", "where", "with", "from", "about", "into", "than", "that", "this"}
    ]
    top_terms = []
    for w in words:
        wl = w.lower()
        if wl in _TOPIC_STOPWORDS:
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


_PRIORITY_MAP = {"high": 1, "medium": 2, "mid": 2, "low": 3, "critical": 1, "hoch": 1, "mittel": 2, "niedrig": 3}


def _parse_priority(val: Any) -> int:
    if isinstance(val, int):
        return max(1, min(3, val))
    s = str(val).strip().lower()
    if s in _PRIORITY_MAP:
        return _PRIORITY_MAP[s]
    try:
        return max(1, min(3, int(s)))
    except (ValueError, TypeError):
        return 2


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
                "priority": _parse_priority(t.get("priority")),
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


def _memory_v2_enabled() -> bool:
    # Default ON; set RESEARCH_MEMORY_V2_ENABLED=0 to force-disable.
    return os.environ.get("RESEARCH_MEMORY_V2_ENABLED", "1").strip() == "1"


def _min_strategy_confidence() -> float:
    try:
        value = float(os.environ.get("RESEARCH_MEMORY_V2_MIN_CONFIDENCE", "0.45"))
    except Exception:
        value = 0.45
    return max(0.25, min(0.8, value))


def _domain_for_project(project_id: str) -> str:
    if not project_id:
        return "general"
    p = research_root() / project_id / "project.json"
    if not p.exists():
        return "general"
    try:
        d = json.loads(p.read_text())
        return str(d.get("domain") or "general")
    except Exception:
        return "general"


def _resample_query_types(queries: list[dict[str, Any]], preferred: dict[str, float]) -> list[dict[str, Any]]:
    if not queries:
        return queries
    weights = {
        "web": max(0.0, float(preferred.get("web", 0.0))),
        "academic": max(0.0, float(preferred.get("academic", 0.0))),
        "medical": max(0.0, float(preferred.get("medical", 0.0))),
    }
    if sum(weights.values()) <= 0.0:
        return queries
    ordered = [(k, v) for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True) if v > 0.0]
    target_types = [t for t, _ in ordered]
    if not target_types:
        return queries
    q_out = []
    bucket = []
    for idx, q in enumerate(queries):
        qq = dict(q)
        bucket.append(qq)
        if len(bucket) >= max(1, len(target_types)):
            for j, b in enumerate(bucket):
                b["type"] = target_types[(idx + j) % len(target_types)]
                q_out.append(b)
            bucket = []
    q_out.extend(bucket)
    return q_out


def _load_strategy_context(question: str, project_id: str) -> dict[str, Any] | None:
    if not project_id:
        return None
    if not _memory_v2_enabled():
        try:
            from lib.memory import Memory
            with Memory() as mem:
                mem.record_memory_decision(
                    decision_type="strategy_mode_detail",
                    details={"mode": "v2_disabled", "fallback_reason": "flag_off"},
                    project_id=project_id,
                    phase="planner",
                    confidence=1.0,
                )
        except Exception:
            pass
        return {
            "mode": "v2_disabled",
            "fallback_reason": "flag_off",
            "expected_benefit": "v2 is disabled; static defaults are used",
        }
    min_conf = _min_strategy_confidence()
    try:
        from lib.memory import Memory
    except ImportError:
        return {
            "mode": "v2_fallback",
            "fallback_reason": "import_error",
            "expected_benefit": "memory module unavailable; safe defaults active",
        }
    try:
        domain = _domain_for_project(project_id)
        with Memory() as mem:
            strategy = mem.select_strategy(question, domain=domain)
            if not strategy:
                mem.record_memory_decision(
                    decision_type="strategy_mode_detail",
                    details={"mode": "v2_fallback", "fallback_reason": "no_strategy", "domain": domain},
                    project_id=project_id,
                    phase="planner",
                    confidence=0.2,
                )
                return {
                    "mode": "v2_fallback",
                    "fallback_reason": "no_strategy",
                    "expected_benefit": "no matching strategy; safe defaults active",
                }
            policy = strategy.get("policy") or {}
            selection_confidence = float(strategy.get("selection_confidence", 0.5) or 0.5)
            if selection_confidence < min_conf:
                mem.record_memory_decision(
                    decision_type="strategy_mode_detail",
                    details={
                        "mode": "v2_fallback",
                        "fallback_reason": "low_confidence",
                        "selection_confidence": selection_confidence,
                        "min_confidence": min_conf,
                        "domain": domain,
                    },
                    project_id=project_id,
                    phase="planner",
                    strategy_profile_id=strategy.get("id"),
                    confidence=selection_confidence,
                )
                return {
                    "mode": "v2_fallback",
                    "fallback_reason": "low_confidence",
                    "confidence": selection_confidence,
                    "min_confidence": min_conf,
                    "selected_strategy": {
                        "id": strategy.get("id"),
                        "name": strategy.get("name"),
                        "domain": strategy.get("domain"),
                    },
                    "confidence_drivers": strategy.get("confidence_drivers") or {},
                    "similar_episode_count": strategy.get("similar_episode_count", 0),
                    "expected_benefit": "confidence too low; safe defaults active",
                }
            mem.record_strategy_application_event(
                project_id=project_id,
                phase="planner",
                strategy_profile_id=strategy.get("id"),
                applied_policy=policy,
                fallback_used=False,
                outcome_hint="pre-plan",
            )
            mem.record_memory_decision(
                decision_type="strategy_mode_detail",
                details={
                    "mode": "v2_applied",
                    "fallback_reason": None,
                    "strategy_profile_id": strategy.get("id"),
                    "strategy_name": strategy.get("name"),
                    "domain": domain,
                    "selection_confidence": selection_confidence,
                    "confidence_drivers": strategy.get("confidence_drivers") or {},
                    "similar_episode_count": strategy.get("similar_episode_count", 0),
                },
                project_id=project_id,
                phase="planner",
                strategy_profile_id=strategy.get("id"),
                confidence=selection_confidence,
            )
            return {
                "mode": "v2_applied",
                "fallback_reason": None,
                "selected_strategy": {
                    "id": strategy.get("id"),
                    "name": strategy.get("name"),
                    "domain": strategy.get("domain"),
                    "score": strategy.get("score"),
                    "confidence": selection_confidence,
                    "policy": policy,
                },
                "confidence_drivers": strategy.get("confidence_drivers") or {},
                "similar_episode_count": strategy.get("similar_episode_count", 0),
                "min_confidence": min_conf,
                "expected_benefit": "higher critic pass and lower revision loops on similar topics",
            }
    except sqlite3.Error:
        return {
            "mode": "v2_fallback",
            "fallback_reason": "db_error",
            "expected_benefit": "strategy DB unavailable; safe defaults active",
        }
    except Exception:
        return {
            "mode": "v2_fallback",
            "fallback_reason": "exception",
            "expected_benefit": "unexpected strategy error; safe defaults active",
        }


def _apply_strategy_to_plan(plan: dict[str, Any], strategy_ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not strategy_ctx or strategy_ctx.get("mode") != "v2_applied":
        return plan
    selected = strategy_ctx.get("selected_strategy") or {}
    policy = selected.get("policy") or {}
    preferred = policy.get("preferred_query_types")
    if isinstance(preferred, dict):
        plan["queries"] = _resample_query_types(plan.get("queries") or [], preferred)
    return plan


def _persist_strategy_context(project_id: str, strategy_ctx: dict[str, Any] | None) -> None:
    if not project_id:
        return
    p = research_root() / project_id / "memory_strategy.json"
    if strategy_ctx is None:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
        return
    try:
        p.write_text(json.dumps(strategy_ctx, indent=2, ensure_ascii=False))
    except Exception:
        pass


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
        base = _sanitize_plan(_json_only(resp.text), question)
        print(f"PLANNER: LLM plan generated ({len(base.get('queries', []))} queries, {len(base.get('topics', []))} topics)", file=sys.stderr)
    except Exception as exc:
        print(f"PLANNER: LLM call failed ({type(exc).__name__}: {exc}), using fallback", file=sys.stderr)
        base = _fallback_plan(question)
    strategy_ctx = _load_strategy_context(question, project_id)
    plan = _apply_strategy_to_plan(base, strategy_ctx)
    _persist_strategy_context(project_id, strategy_ctx)
    return plan


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
        prio = _parse_priority(t.get("priority"))
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
