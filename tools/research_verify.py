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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import load_secrets, project_dir, load_project, ensure_project_layout


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


def _llm_json(system: str, user: str) -> dict | list:
    from openai import OpenAI
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    resp = client.responses.create(model=_model(), instructions=system, input=user)
    text = (resp.output_text or "").strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def source_reliability(proj_path: Path, project: dict) -> dict:
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
    out = _llm_json(system, user)
    if isinstance(out, dict) and "sources" in out:
        return out
    return {"sources": out if isinstance(out, list) else []}


def claim_verification(proj_path: Path, project: dict) -> dict:
    """Extract key claims from findings and check if >= 2 independent sources support them."""
    ensure_project_layout(proj_path)
    findings = _load_findings(proj_path)
    if not findings:
        return {"claims": []}
    items = json.dumps(
        [{"url": f.get("url"), "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:600]} for f in findings],
        indent=2, ensure_ascii=False
    )[:14000]
    question = project.get("question", "")
    system = """You are a research analyst. From the findings, extract KEY CLAIMS (main factual statements that answer the research question).
For each claim, assess how many independent sources support it.
Return JSON: {"claims": [{"claim": "...", "supporting_sources": ["url1", "url2"], "confidence": 0.0-1.0, "verified": true/false}]}
verified = true only if at least 2 distinct sources support the claim. Be strict."""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}\n\nExtract claims and verification status. Return only valid JSON."
    out = _llm_json(system, user)
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
        # Deterministic is_verified: >=2 distinct sources, none low reliability, no dispute
        low_rel = any((rel_by_url.get(u, 0.5) < 0.6) for u in supporting_source_ids)
        dispute = (c.get("disputed") or c.get("verification_status", "") == "disputed" or
                   str(c.get("verification_status", "")).lower() == "disputed")
        distinct_count = len(set(supporting_source_ids))
        is_verified = bool(distinct_count >= 2 and not low_rel and not dispute)
        if is_verified:
            verification_reason = f"{distinct_count} independent sources, reliability OK"
        elif dispute:
            verification_reason = "disputed"
        elif low_rel:
            verification_reason = "supporting source(s) low reliability"
        elif distinct_count < 2:
            verification_reason = f"only {distinct_count} source(s)"
        else:
            verification_reason = "not verified"
        claims_out.append({
            "claim_id": claim_id,
            "text": text,
            "supporting_source_ids": supporting_source_ids,
            "is_verified": is_verified,
            "verification_reason": verification_reason,
        })
    return {"claims": claims_out}


def fact_check(proj_path: Path, project: dict) -> dict:
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
    out = _llm_json(system, user)
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
        result = source_reliability(proj_path, project)
    elif mode == "claim_verification":
        result = claim_verification(proj_path, project)
    elif mode == "fact_check":
        result = fact_check(proj_path, project)
    elif mode == "claim_ledger":
        result = build_claim_ledger(proj_path, project)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
