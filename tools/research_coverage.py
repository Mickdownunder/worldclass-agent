#!/usr/bin/env python3
"""
Assess source/finding coverage against research_plan.json.

Usage:
  research_coverage.py <project_id>
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _tokens(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9][a-z0-9\-\+]{2,}", (text or "").lower())
        if w not in {"with", "from", "that", "this", "have", "were", "will", "into", "about", "what", "when", "where", "which"}
    }


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _iter_source_meta(project_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in sorted((project_dir / "sources").glob("*.json")):
        if f.name.endswith("_content.json"):
            continue
        d = _load_json(f, {})
        if not isinstance(d, dict):
            continue
        out.append(d)
    return out


def _iter_findings(project_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in sorted((project_dir / "findings").glob("*.json")):
        d = _load_json(f, {})
        if isinstance(d, dict):
            out.append(d)
    return out


def _is_primary_source(source: dict[str, Any]) -> bool:
    url = str(source.get("url") or "").lower()
    domain = ""
    if "://" in url:
        try:
            domain = url.split("/")[2].replace("www.", "")
        except Exception:
            domain = ""
    primary_domains = {
        "arxiv.org",
        "semanticscholar.org",
        "nature.com",
        "science.org",
        "openai.com",
        "anthropic.com",
        "googleblog.com",
        "docs.python.org",
        "developer.mozilla.org",
        "github.com",
    }
    if domain in primary_domains:
        return True
    source_type = str(source.get("type") or source.get("source_type") or "").lower()
    source_name = str(source.get("source") or "").lower()
    return source_type in {"academic", "paper"} or source_name in {"arxiv", "semantic_scholar", "pubmed"}


def _topic_keywords(topic: dict[str, Any], entities: list[str]) -> set[str]:
    kws = _tokens(f"{topic.get('name', '')} {topic.get('description', '')}")
    lname = str(topic.get("name") or "").lower()
    for e in entities:
        el = e.lower()
        if el and (el in lname or any(part in lname for part in el.split())):
            kws |= _tokens(e)
    return kws


def _match_item(topic_id: str, item: dict[str, Any], keywords: set[str]) -> bool:
    if str(item.get("topic_id") or "") == topic_id:
        return True
    text = f"{item.get('title','')} {item.get('description','')} {item.get('excerpt','')} {item.get('abstract','')}"
    itoks = _tokens(text)
    overlap = len(keywords & itoks)
    return overlap >= 1


def assess_coverage(plan: dict[str, Any], findings: list[dict[str, Any]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    topics = plan.get("topics") if isinstance(plan, dict) else []
    entities = [str(e) for e in (plan.get("entities") or [])] if isinstance(plan, dict) else []
    if not isinstance(topics, list):
        topics = []

    topic_out: list[dict[str, Any]] = []
    for raw in topics:
        if not isinstance(raw, dict):
            continue
        topic = dict(raw)
        tid = str(topic.get("id") or "")
        min_sources = max(1, int(topic.get("min_sources") or 2))
        keywords = _topic_keywords(topic, entities)
        topic_findings = [f for f in findings if _match_item(tid, f, keywords)]
        topic_sources = [s for s in sources if _match_item(tid, s, keywords)]

        cov = {
            "findings_count": len(topic_findings),
            "sources_count": len(topic_sources),
            "has_primary_source": any(_is_primary_source(s) for s in topic_sources),
            "is_covered": len(topic_sources) >= min_sources,
        }
        topic["coverage"] = cov
        topic_out.append(topic)

    covered = sum(1 for t in topic_out if t.get("coverage", {}).get("is_covered"))
    total = len(topic_out)
    coverage_rate = (covered / total) if total else 0.0
    uncovered = [t for t in topic_out if not t.get("coverage", {}).get("is_covered")]
    priority1_uncovered = [t for t in uncovered if int(t.get("priority") or 2) == 1]

    gate_pass = coverage_rate >= 0.7 or (coverage_rate >= 0.5 and len(priority1_uncovered) == 0)
    thin_priority_topics = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "priority": t.get("priority"),
            "sources_count": t.get("coverage", {}).get("sources_count", 0),
        }
        for t in topic_out
        if int(t.get("priority") or 2) == 1 and int(t.get("coverage", {}).get("sources_count", 0)) < 3
    ]

    return {
        "coverage_rate": round(coverage_rate, 4),
        "covered_count": covered,
        "total_topics": total,
        "topics": topic_out,
        "uncovered_topics": uncovered,
        "thin_priority_topics": thin_priority_topics,
        "pass": gate_pass,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_coverage.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    operator_root = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
    project_dir = operator_root / "research" / project_id
    plan_path = project_dir / "research_plan.json"
    if not plan_path.exists():
        print(json.dumps({"pass": False, "error": "research_plan.json not found", "coverage_rate": 0.0}, indent=2))
        return
    plan = _load_json(plan_path, {})
    findings = _iter_findings(project_dir)
    sources = _iter_source_meta(project_dir)
    result = assess_coverage(plan, findings, sources)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
