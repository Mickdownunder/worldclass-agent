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
from tools.research_common import load_secrets, project_dir, load_project, ensure_project_layout, llm_retry


def _model():
    return os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")


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


def _load_findings(proj_path: Path, max_items: int = 50) -> list[dict]:
    findings = []
    for f in (proj_path / "findings").glob("*.json"):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    return findings[:max_items]


def _llm_json(system: str, user: str, project_id: str = "") -> dict | list:
    """Call LLM with retry and optional budget tracking."""
    from openai import OpenAI
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    model = _model()

    @llm_retry()
    def _call():
        return client.responses.create(model=model, instructions=system, input=user)

    resp = _call()

    if project_id:
        try:
            from tools.research_budget import track_usage
            track_usage(project_id, model, resp.usage.input_tokens, resp.usage.output_tokens)
        except Exception:
            pass

    text = (resp.output_text or "").strip()
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
    system = """You are a research analyst evaluating source reliability.
For each source, return JSON: {"sources": [{"url": "...", "reliability_score": 0.0-1.0, "flags": ["list", "of", "issues or strengths e.g. authoritative_domain"]}]}
Score: 0.3 = low/unreliable, 0.5 = unknown, 0.7+ = decent, 0.9+ = high trust. Consider domain reputation, recency if visible, author if known."""
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
    findings = _load_findings(proj_path)
    source_meta = _load_source_metadata(proj_path)
    if not findings and not source_meta:
        return {"claims": []}
    items = json.dumps(
        [{"url": f.get("url"), "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:600]} for f in findings],
        indent=2, ensure_ascii=False
    )[:12000]
    meta_text = json.dumps(source_meta[:30], indent=2, ensure_ascii=False)[:4000] if source_meta else "[]"
    question = project.get("question", "")
    system = """You are a research analyst. From the findings AND source metadata, extract KEY CLAIMS (main factual statements that answer the research question).
For each claim, list ALL sources that support it — both from full findings AND from search metadata snippets. A search snippet counts as a supporting source if it clearly states or implies the same fact.
Return JSON: {"claims": [{"claim": "...", "supporting_sources": ["url1", "url2"], "confidence": 0.0-1.0, "verified": true/false}]}
verified = true only if at least 2 distinct source URLs support the claim. Be strict but thorough in matching."""
    user = f"QUESTION: {question}\n\nFINDINGS (full content):\n{items}\n\nSOURCE METADATA (search snippets — use as supporting evidence for cross-referencing):\n{meta_text}\n\nExtract claims and verification status. Return only valid JSON."
    out = _llm_json(system, user, project_id=project_id)
    if isinstance(out, dict) and "claims" in out:
        return out
    return {"claims": out if isinstance(out, list) else []}


def build_claim_ledger(proj_path: Path, project: dict) -> dict:
    """
    Deterministic claim ledger from claim_verification + source_reliability.
    [VERIFIED] only when: >=2 independent sources, no dispute, sources not low reliability.
    Output: { "claims": [ { "claim_id", "text", "supporting_source_ids", "is_verified", "verification_reason" } ] }
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
        is_verified = bool(distinct_reliable >= 2 and not dispute)
        if is_verified:
            verification_reason = f"{distinct_reliable} reliable independent sources"
        elif dispute:
            verification_reason = "disputed"
        elif distinct_reliable < 2:
            total_distinct = len(set(supporting_source_ids))
            if total_distinct >= 2 and distinct_reliable < 2:
                verification_reason = f"{total_distinct} sources but only {distinct_reliable} reliable"
            else:
                verification_reason = f"only {total_distinct} source(s)"
        else:
            verification_reason = "not verified"
        claims_out.append({
            "claim_id": claim_id,
            "text": text,
            "supporting_source_ids": supporting_source_ids,
            "is_verified": is_verified,
            "verification_reason": verification_reason,
        })
    from tools.research_common import audit_log
    audit_log(proj_path, "claim_ledger_built", {
        "total_claims": len(claims_out),
        "verified_count": sum(1 for c in claims_out if c.get("is_verified")),
    })
    return {"claims": claims_out}


# Regex to strip all [VERIFIED] and [VERIFIED:claim_id] tags (with optional surrounding whitespace).
# Used so only ledger-based is_verified claims get the tag; LLM-hallucinated tags are removed.
_VERIFIED_TAG_PATTERN = re.compile(r"\s*\[VERIFIED(?::[^\]]+)?\]", re.IGNORECASE)


def apply_verified_tags_to_report(report: str, claims: list[dict]) -> str:
    """
    Deterministic [VERIFIED] tagging: strip all existing [VERIFIED], then add only for
    claims with is_verified=True. Each claim text is tagged at most once.
    Same logic as research-cycle.sh synthesis post-step; use this for tests and production.
    """
    if not report:
        return report
    # 1) Remove all existing [VERIFIED] tags (robust to optional spaces)
    report = _VERIFIED_TAG_PATTERN.sub("", report)
    # 2) Add [VERIFIED:claim_id] only for ledger-verified claims; each claim at most once
    for c in claims:
        if not c.get("is_verified"):
            continue
        text = (c.get("text") or "").strip()
        if not text or "[VERIFIED" in text:
            continue
        claim_id = c.get("claim_id", "")
        if text in report:
            report = report.replace(text, text + f" [VERIFIED:{claim_id}]", 1)
    return report


def fact_check(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """Identify verifiable facts (numbers, dates, names) and mark verification status."""
    ensure_project_layout(proj_path)
    findings = _load_findings(proj_path)
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
    out = _llm_json(system, user, project_id=project_id)
    if isinstance(out, dict) and "facts" in out:
        return out
    return {"facts": out if isinstance(out, list) else []}


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


if __name__ == "__main__":
    main()
