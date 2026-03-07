"""Source reliability and fact_check (evidence-side verification)."""
import json
from pathlib import Path

from tools.research_common import ensure_project_layout, get_principles_for_research
from tools.verify.common import (
    load_sources,
    load_findings,
    load_connect_context,
    llm_json,
    verify_model,
)


def source_reliability(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """LLM-based rating of each source: domain trust, recency, author credibility."""
    ensure_project_layout(proj_path)
    sources = load_sources(proj_path)
    if not sources:
        return {"sources": []}
    items = []
    for s in sources:
        url = s.get("url", "")
        title = s.get("title", "")
        items.append({"url": url, "title": title or "(no title)"})
    payload = json.dumps(items, indent=2, ensure_ascii=False)[:12000]
    question = project.get("question", "")
    principles_block = get_principles_for_research(question, domain=project.get("domain"), limit=5)
    system = """You are a research analyst evaluating source reliability.
For each source, return JSON: {"sources": [{"url": "...", "reliability_score": 0.0-1.0, "flags": ["list", "of", "issues or strengths e.g. authoritative_domain"], "domain_tier": "high|medium|low|unknown" (optional), "recency_score": 0.0-1.0 (optional)}]}
Score: 0.3 = low/unreliable, 0.5 = unknown, 0.7+ = decent, 0.9+ = high trust. Consider domain reputation, recency if visible, author if known."""
    if principles_block:
        system += "\n\n" + principles_block
    user = f"SOURCES:\n{payload}\n\nRate each source. Return only valid JSON."
    out = llm_json(system, user, project_id=project_id, model_fn=verify_model)
    if isinstance(out, dict) and "sources" in out:
        sources_out = out["sources"]
    else:
        sources_out = out if isinstance(out, list) else []
    _, contradiction_urls = load_connect_context(proj_path)
    if contradiction_urls:
        for s in sources_out:
            url = (s.get("url") or "").strip()
            title = (s.get("title") or "").strip()
            in_contra = any(
                url == u or u in url or title == u or (len(u) > 20 and u in url)
                for u in contradiction_urls
            )
            if in_contra:
                s["in_contradiction"] = True
                flags = s.get("flags") or []
                if "in_contradiction" not in flags:
                    s["flags"] = flags + ["in_contradiction"]
    return {"sources": sources_out}


def fact_check(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """Identify verifiable facts (numbers, dates, names) and mark verification status."""
    ensure_project_layout(proj_path)
    findings = load_findings(proj_path, question=project.get("question", ""))
    if not findings:
        return {"facts": []}
    items = json.dumps(
        [{"url": f.get("url"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings],
        indent=2, ensure_ascii=False
    )[:12000]
    system = """You are a fact-checker. From the findings, list VERIFIABLE FACTS (specific numbers, dates, names, events).
For each fact, state verification status based on how many sources mention it consistently.
Return JSON: {"facts": [{"statement": "...", "verification_status": "confirmed|disputed|unverifiable", "source": "url or summary"}]}
confirmed = multiple sources agree; disputed = sources disagree; unverifiable = only one source or unclear."""
    user = f"FINDINGS:\n{items}\n\nList 3-10 key facts with status. Return only valid JSON."
    out = llm_json(system, user, project_id=project_id, model_fn=verify_model)
    if isinstance(out, dict) and "facts" in out:
        return out
    return {"facts": out if isinstance(out, list) else []}
