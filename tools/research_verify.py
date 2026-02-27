#!/usr/bin/env python3
"""
Research verification: source reliability, claim verification, fact-check.
Used in the Verify phase of the research cycle.

Usage:
  research_verify.py <project_id> source_reliability
  research_verify.py <project_id> claim_verification
  research_verify.py <project_id> fact_check
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, ensure_project_layout, llm_call, get_principles_for_research


def _model():
    return os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")


def _verify_model():
    return os.environ.get("RESEARCH_VERIFY_MODEL", "gpt-5.2")


def _load_sources(proj_path: Path, max_items: int = 50) -> list[dict]:
    sources = []
    for f in (proj_path / "sources").glob("*.json"):
        if f.name.endswith("_content.json"):
            continue
        try:
            sources.append(json.loads(f.read_text()))
        except Exception:
            pass
    return sources[:max_items]


def _relevance_score(finding: dict, question: str) -> float:
    """Score how relevant a finding is to the research question using keyword overlap."""
    q_words = set(re.findall(r'\b[a-z]{3,}\b', question.lower()))
    text = ((finding.get("excerpt") or "") + " " + (finding.get("title") or "")).lower()
    f_words = set(re.findall(r'\b[a-z]{3,}\b', text))
    if not q_words or not f_words:
        return 0.0
    overlap = len(q_words & f_words)
    return overlap / len(q_words)


def _load_findings(proj_path: Path, max_items: int = 120, question: str = "") -> list[dict]:
    """Load findings sorted by relevance to the research question."""
    findings = []
    for f in sorted((proj_path / "findings").glob("*.json")):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    if question and findings:
        findings.sort(key=lambda f: _relevance_score(f, question), reverse=True)
    return findings[:max_items]


def _llm_json(system: str, user: str, project_id: str = "", *, model: str | None = None) -> dict | list:
    """Call LLM with retry and optional budget tracking. Uses _model() unless model= is given (e.g. _verify_model())."""
    m = model if model is not None else _model()
    result = llm_call(m, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def source_reliability(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """LLM-based rating of each source: domain trust, recency, author credibility."""
    ensure_project_layout(proj_path)
    sources = _load_sources(proj_path)
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
For each source, return JSON: {"sources": [{"url": "...", "reliability_score": 0.0-1.0, "flags": ["list", "of", "issues or strengths e.g. authoritative_domain"]}]}
Score: 0.3 = low/unreliable, 0.5 = unknown, 0.7+ = decent, 0.9+ = high trust. Consider domain reputation, recency if visible, author if known."""
    if principles_block:
        system += "\n\n" + principles_block
    user = f"SOURCES:\n{payload}\n\nRate each source. Return only valid JSON."
    out = _llm_json(system, user, project_id=project_id)
    if isinstance(out, dict) and "sources" in out:
        return out
    return {"sources": out if isinstance(out, list) else []}


def _load_source_metadata(proj_path: Path, max_items: int = 50) -> list[dict]:
    """Load search result metadata (title + description) as lightweight evidence."""
    summaries = []
    for f in (proj_path / "sources").glob("*.json"):
        if f.name.endswith("_content.json"):
            continue
        try:
            d = json.loads(f.read_text())
            url = (d.get("url") or "").strip()
            title = (d.get("title") or "").strip()
            desc = (d.get("description") or "").strip()
            if url and (title or desc):
                summaries.append({"url": url, "title": title, "snippet": desc[:300]})
        except Exception:
            pass
    return summaries[:max_items]


def claim_verification(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """Extract key claims from findings and check if >= 2 independent sources support them."""
    ensure_project_layout(proj_path)
    question = project.get("question", "")
    findings = _load_findings(proj_path, question=question)
    source_meta = _load_source_metadata(proj_path)
    if not findings and not source_meta:
        return {"claims": []}
    items = json.dumps(
        [{"url": f.get("url"), "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:800]} for f in findings],
        indent=2, ensure_ascii=False
    )[:24000]
    meta_text = json.dumps(source_meta[:40], indent=2, ensure_ascii=False)[:6000] if source_meta else "[]"
    system = f"""You are a research analyst. The research question is:
"{question}"

From the findings AND source metadata, extract ALL KEY CLAIMS that answer this question.
Extract at least 5-15 claims if the material supports it. Each claim should be a specific, verifiable factual statement.
For each claim, list ALL sources that support it.
Return JSON: {{"claims": [{{"claim": "...", "supporting_sources": ["url1", "url2"], "confidence": 0.0-1.0, "verified": true/false}}]}}
verified = true only if at least 2 distinct source URLs support the claim. Be strict but thorough in matching.
Prefer specific, quantitative claims (e.g. "X achieved Y% response rate in phase Z trial") over vague narrative statements."""
    principles_block = get_principles_for_research(question, domain=project.get("domain"), limit=5)
    if principles_block:
        system += "\n\n" + principles_block
    user = f"QUESTION: {question}\n\nFINDINGS (full content):\n{items}\n\nSOURCE METADATA (search snippets — use as supporting evidence for cross-referencing):\n{meta_text}\n\nExtract claims and verification status. Return only valid JSON."
    out = _llm_json(system, user, project_id=project_id, model=_verify_model())
    if isinstance(out, dict) and "claims" in out:
        return out
    return {"claims": out if isinstance(out, list) else []}


_AUTHORITATIVE_DOMAINS = (
    "arxiv.org", "doi.org", "scholar.google",
    "docs.", "documentation", "github.com", "gitlab.com",
    "openreview.net", "acm.org", "ieee.org", "springer.com",
    "nature.com", "science.org", "sciencedirect.com",
    "pmc.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "pubmed.ncbi",
    "nih.gov", "who.int", "fda.gov", "ema.europa.eu",
    "clinicaltrials.gov", "thelancet.com", "nejm.org", "bmj.com",
    "jamanetwork.com", "cochranelibrary.com",
    "sec.gov", "sec.gov/archives",
    "investors.biontech.de", "biontechse.gcs-web.com",
    "pubs.acs.org", "wiley.com", "cell.com",
    "europa.eu", "gov.uk", "bfarm.de",
)


def _is_authoritative_source(url: str) -> bool:
    """True if URL is from an authoritative primary source."""
    u = (url or "").lower()
    if not u:
        return False
    return any(d in u for d in _AUTHORITATIVE_DOMAINS)


def build_claim_ledger(proj_path: Path, project: dict) -> dict:
    """
    Deterministic claim ledger from claim_verification + source_reliability.
    verification_tier: VERIFIED (>=2 independent reliable), AUTHORITATIVE (1 authoritative source), UNVERIFIED.
    is_verified: True for VERIFIED; also True for AUTHORITATIVE in frontier mode.
    Output: { "claims": [ { "claim_id", "text", "supporting_source_ids", "is_verified", "verification_tier", "verification_reason" } ] }
    """
    ensure_project_layout(proj_path)
    verify_dir = proj_path / "verify"
    claims_in = []
    if (verify_dir / "claim_verification.json").exists():
        try:
            data = json.loads((verify_dir / "claim_verification.json").read_text())
            claims_in = data.get("claims", [])
        except Exception:
            pass
    rel_by_url = {}
    if (verify_dir / "source_reliability.json").exists():
        try:
            rel = json.loads((verify_dir / "source_reliability.json").read_text())
            for s in rel.get("sources", []):
                u = (s.get("url") or "").strip()
                rel_by_url[u] = float(s.get("reliability_score", 0.5))
        except Exception:
            pass
    claims_out = []
    for i, c in enumerate(claims_in):
        try:
            from tools.research_progress import step as progress_step
            # get project_id from somewhere... Wait, build_claim_ledger doesn't take project_id. Let's get it from proj_path.name
            progress_step(proj_path.name, f"Verifying claim {i+1}/{len(claims_in)}", i+1, len(claims_in))
        except Exception:
            pass
        claim_id = f"cl_{i}_{hash(c.get('claim', '')[:100]) % 10000}"
        text = (c.get("claim") or "").strip()
        supporting = c.get("supporting_sources") or []
        if isinstance(supporting, str):
            supporting = [supporting] if supporting else []
        supporting_source_ids = [s for s in supporting if s][:20]
        reliable_sources = [u for u in supporting_source_ids if rel_by_url.get(u, 0.5) >= 0.6]
        distinct_reliable = len(set(reliable_sources))
        dispute = (c.get("disputed") or c.get("verification_status", "") == "disputed" or
                   str(c.get("verification_status", "")).lower() == "disputed")
        authoritative_sources = [u for u in reliable_sources if _is_authoritative_source(u)]
        if distinct_reliable >= 2 and not dispute:
            verification_tier = "VERIFIED"
            is_verified = True
            verification_reason = f"{distinct_reliable} reliable independent sources"
        elif dispute:
            verification_tier = "UNVERIFIED"
            is_verified = False
            verification_reason = "disputed"
        elif distinct_reliable == 1 and authoritative_sources and not dispute:
            verification_tier = "AUTHORITATIVE"
            research_mode = ((project.get("config") or {}).get("research_mode") or "standard").lower()
            is_verified = research_mode == "frontier"
            verification_reason = "single authoritative source (primary)"
        elif distinct_reliable < 2:
            total_distinct = len(set(supporting_source_ids))
            verification_tier = "UNVERIFIED"
            is_verified = False
            if total_distinct >= 2 and distinct_reliable < 2:
                verification_reason = f"{total_distinct} sources but only {distinct_reliable} reliable"
            else:
                verification_reason = f"only {total_distinct} source(s)"
        else:
            verification_tier = "UNVERIFIED"
            is_verified = False
            verification_reason = "not verified"
        claims_out.append({
            "claim_id": claim_id,
            "text": text,
            "supporting_source_ids": supporting_source_ids,
            "is_verified": is_verified,
            "verification_tier": verification_tier,
            "verification_reason": verification_reason,
        })
    from tools.research_common import audit_log
    audit_log(proj_path, "claim_ledger_built", {
        "total_claims": len(claims_out),
        "verified_count": sum(1 for c in claims_out if c.get("is_verified")),
    })
    return {"claims": claims_out}


# Regex to strip all [VERIFIED] and [AUTHORITATIVE] tags (with optional claim_id).
_VERIFIED_TAG_PATTERN = re.compile(r"\s*\[VERIFIED(?::[^\]]+)?\]", re.IGNORECASE)
_AUTHORITATIVE_TAG_PATTERN = re.compile(r"\s*\[AUTHORITATIVE(?::[^\]]+)?\]", re.IGNORECASE)


def apply_verified_tags_to_report(report: str, claims: list[dict]) -> str:
    """
    Deterministic tagging: strip existing tags, then add [VERIFIED:claim_id] for VERIFIED
    and [AUTHORITATIVE:claim_id] for AUTHORITATIVE. Each claim text is tagged at most once.
    """
    if not report:
        return report
    report = _VERIFIED_TAG_PATTERN.sub("", report)
    report = _AUTHORITATIVE_TAG_PATTERN.sub("", report)
    for c in claims:
        tier = c.get("verification_tier") or ("VERIFIED" if c.get("is_verified") else "UNVERIFIED")
        if tier not in ("VERIFIED", "AUTHORITATIVE"):
            continue
        text = (c.get("text") or "").strip()
        if not text or "[VERIFIED" in text or "[AUTHORITATIVE" in text:
            continue
        claim_id = c.get("claim_id", "")
        tag = f" [VERIFIED:{claim_id}]" if tier == "VERIFIED" else f" [AUTHORITATIVE:{claim_id}]"
        if text in report:
            report = report.replace(text, text + tag, 1)
    return report


def fact_check(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """Identify verifiable facts (numbers, dates, names) and mark verification status."""
    ensure_project_layout(proj_path)
    findings = _load_findings(proj_path, question=project.get("question", ""))
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
    out = _llm_json(system, user, project_id=project_id, model=_verify_model())
    if isinstance(out, dict) and "facts" in out:
        return out
    return {"facts": out if isinstance(out, list) else []}


def _record_progress_error(project_id: str, e: BaseException) -> None:
    try:
        from tools.research_progress import error as progress_error
        name = type(e).__name__
        if "Proxy" in name or "403" in str(e):
            code = "proxy_forbidden"
        elif "Connection" in name or "APIConnection" in name:
            code = "openai_connection"
        else:
            code = "verify_error"
        progress_error(project_id, code, str(e)[:500])
    except Exception:
        pass


def main():
    if len(sys.argv) < 3:
        print("Usage: research_verify.py <project_id> <source_reliability|claim_verification|fact_check|claim_ledger>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    mode = sys.argv[2].lower()
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    project = load_project(proj_path)
    try:
        if mode == "source_reliability":
            result = source_reliability(proj_path, project, project_id=project_id)
        elif mode == "claim_verification":
            result = claim_verification(proj_path, project, project_id=project_id)
        elif mode == "fact_check":
            result = fact_check(proj_path, project, project_id=project_id)
        elif mode == "claim_ledger":
            result = build_claim_ledger(proj_path, project)
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        _record_progress_error(project_id, e)
        raise


if __name__ == "__main__":
    main()
