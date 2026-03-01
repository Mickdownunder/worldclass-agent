#!/usr/bin/env python3
"""
Research-specific reasoning: gap_analysis, hypothesis_formation, contradiction_detection, evidence_gaps.
Reads project findings and returns structured JSON (gaps, hypotheses, or contradiction pairs).
Uses RESEARCH_EXTRACT_MODEL (default gpt-4.1-mini) for cost efficiency.

Connect Phase 4: contradiction_detection uses two-step structured mode (RESEARCH_CONTRADICTION_STRUCTURED=1):
  (1) _extract_claims_per_finding → extracted_claims; (2) _compare_claim_pairs → pair_relations.
  contradictions.json gets claim_a_id, claim_b_id, claim_a_text, claim_b_text, relation.
  Set RESEARCH_CONTRADICTION_STRUCTURED=0 for legacy single-call mode.

Connect Phase 6: hypothesis_formation loads connect/entity_graph.json and passes entity graph to LLM.
  thesis.json and claim_ledger get entity_ids (entity names referenced in thesis/claim).

Usage:
  research_reason.py <project_id> gap_analysis
  research_reason.py <project_id> hypothesis_formation
  research_reason.py <project_id> contradiction_detection
  research_reason.py <project_id> evidence_gaps
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, llm_call, get_principles_for_research


def _model():
    return os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")


def _hypothesis_model():
    """Model used only for hypothesis_formation; default gemini-3.1-pro-preview for deeper theses."""
    return os.environ.get("RESEARCH_HYPOTHESIS_MODEL", "gemini-3.1-pro-preview")


def _load_findings(proj_path: Path, max_items: int = 40) -> list[dict]:
    findings = []
    for f in (proj_path / "findings").glob("*.json"):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    return findings[:max_items]


def _llm_json(system: str, user: str, project_id: str = "", *, model: str | None = None) -> dict | list:
    """Call LLM with retry and optional budget tracking. model= overrides default (_model())."""
    import re
    model = model if model is not None else _model()
    result = llm_call(model, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def gap_analysis(proj_path: Path, project: dict, project_id: str = "") -> dict:
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "Analyzing gaps")
    except Exception:
        pass
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    items = json.dumps([{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings], indent=2)[:8000]
    principles_block = get_principles_for_research(question, domain=project.get("domain"), limit=5)
    system = """You are a research analyst. Given the research question and current findings, list GAPS: what is still unknown or under-sourced.
Return JSON: {"gaps": [{"description": "...", "priority": "high|medium|low", "suggested_search": "query"}]}"""
    if principles_block:
        system += "\n\n" + principles_block
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}\n\nList 3-7 gaps. Be specific."
    out = _llm_json(system, user, project_id=project_id)
    return out if isinstance(out, dict) else {"gaps": out}


def _load_entity_graph_for_hypothesis(proj_path: Path) -> str:
    """Phase 6: Load entity graph text for hypothesis prompt (entities + relations)."""
    graph_path = proj_path / "connect" / "entity_graph.json"
    if not graph_path.exists():
        return ""
    try:
        graph = json.loads(graph_path.read_text())
        entities = graph.get("entities", [])[:30]
        relations = graph.get("relations", [])[:20]
        names = [e.get("name") for e in entities if e.get("name")]
        rel_strs = [f"{r.get('from')} --{r.get('relation_type', 'related')}--> {r.get('to')}" for r in relations if r.get("from") and r.get("to")]
        if not names and not rel_strs:
            return ""
        return "Entities: " + ", ".join(names) + "\nRelations: " + "; ".join(rel_strs[:15])
    except Exception:
        return ""


def hypothesis_formation(proj_path: Path, project: dict, project_id: str = "") -> dict:
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "KI: Forming hypotheses")
    except Exception:
        pass
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    items = json.dumps([{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for f in findings], indent=2)[:8000]
    # Connect Phase 3: contradictions
    contradictions_block = ""
    if (proj_path / "contradictions.json").exists():
        try:
            data = json.loads((proj_path / "contradictions.json").read_text())
            contras = data.get("contradictions", [])[:5]
            if contras:
                contradictions_block = "\n\nCONTRADICTIONS (sources disagree on these): " + json.dumps(
                    [{"claim": c.get("claim"), "source_a": c.get("source_a"), "source_b": c.get("source_b"), "summary": c.get("summary")} for c in contras],
                    indent=2, ensure_ascii=False
                )[:2000]
        except Exception:
            pass
    # Phase 6: entity graph as input for graph-based hypotheses
    entity_graph_block = _load_entity_graph_for_hypothesis(proj_path)
    if entity_graph_block:
        entity_graph_block = "\n\nENTITY GRAPH (use these entities and relations in your hypotheses where relevant):\n" + entity_graph_block[:1500]
    system = """You are a research analyst. Form 1-3 testable hypotheses that answer the research question based on current findings.
Return JSON: {"hypotheses": [{"statement": "...", "confidence": 0.0-1.0, "evidence_summary": "..."}]}
If contradictions are provided, consider contrasting positions (e.g. Position A vs B) or state uncertainty.
If an entity graph is provided, form hypotheses that reference or explain those entities and relations where relevant."""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}{contradictions_block}{entity_graph_block}\n\nForm hypotheses. Return only valid JSON."
    out = _llm_json(system, user, project_id=project_id, model=_hypothesis_model())
    return out if isinstance(out, dict) else {"hypotheses": out}


def _extract_claims_per_finding(
    findings: list[dict], project_id: str, max_claims_per_finding: int = 4
) -> list[dict]:
    """Phase 4 step 1: Extract verifiable claims per finding. Returns list of {claim_id, text, source_url, source_title, finding_id}."""
    extracted: list[dict] = []
    for idx, f in enumerate(findings[:25]):
        excerpt = (f.get("excerpt") or "")[:2000]
        url = (f.get("url") or "").strip()
        title = (f.get("title") or "").strip()
        finding_id = f.get("finding_id") or f"f_{idx}"
        if not excerpt:
            continue
        system = """You are a research analyst. From the following finding excerpt, extract 1-4 KEY CLAIMS: specific, verifiable factual statements (numbers, dates, causal claims).
Return JSON: {"claims": ["claim text 1", "claim text 2", ...]}.
Each claim must be a single sentence. No generic statements. Return only valid JSON."""
        user = f"FINDING EXCERPT:\n{excerpt}\n\nExtract 1-{max_claims_per_finding} key claims. Return only valid JSON."
        try:
            out = _llm_json(system, user, project_id=project_id)
            claims = out.get("claims", out if isinstance(out, list) else [])
            if not isinstance(claims, list):
                claims = []
            for cidx, ctext in enumerate(claims[:max_claims_per_finding]):
                if isinstance(ctext, dict):
                    ctext = ctext.get("claim") or ctext.get("text") or ""
                text = (str(ctext) or "").strip()
                if not text or len(text) < 15:
                    continue
                claim_id = f"ce_{idx}_{cidx}_{hash(text[:80]) % 10000}"
                extracted.append({
                    "claim_id": claim_id,
                    "text": text,
                    "source_url": url,
                    "source_title": title,
                    "finding_id": finding_id,
                })
        except Exception:
            continue
    return extracted


def _compare_claim_pairs(
    claims: list[dict], project_id: str, max_pairs: int = 20
) -> list[dict]:
    """Phase 4 step 2: Compare claim pairs; return those with relation contradiction|entailment|neutral."""
    if len(claims) < 2:
        return []
    pairs: list[tuple[dict, dict]] = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if claims[i].get("source_url") == claims[j].get("source_url"):
                continue
            pairs.append((claims[i], claims[j]))
            if len(pairs) >= max_pairs:
                break
        if len(pairs) >= max_pairs:
            break
    if not pairs:
        return []
    pair_list = [
        {"claim_a": {"claim_id": a["claim_id"], "text": (a.get("text") or "")[:400], "source": a.get("source_url") or a.get("source_title")},
         "claim_b": {"claim_id": b["claim_id"], "text": (b.get("text") or "")[:400], "source": b.get("source_url") or b.get("source_title")}}
        for a, b in pairs[:15]
    ]
    items = json.dumps(pair_list, indent=2, ensure_ascii=False)[:12000]
    system = """You are a research analyst. For each PAIR below (claim_a and claim_b from different sources), set:
- relation: "contradiction" (disagree on same fact), "entailment" (one supports the other), or "neutral"
- summary: one sentence describing the relation.
Return JSON: {"pairs": [{"claim_a_id": "<claim_a.claim_id from input>", "claim_b_id": "<claim_b.claim_id from input>", "relation": "contradiction|entailment|neutral", "summary": "..."}]}
Include only pairs where relation is contradiction or entailment. Max 8. Return only valid JSON."""
    user = f"CLAIM PAIRS (each has claim_a and claim_b):\n{items}\n\nReturn pairs with relation and summary. Return only valid JSON."
    try:
        out = _llm_json(system, user, project_id=project_id)
        pair_results = out.get("pairs", out if isinstance(out, list) else [])
        if not isinstance(pair_results, list):
            return []
        id_to_claim = {c["claim_id"]: c for c in claims}
        result = []
        for p in pair_results[:10]:
            a_id = p.get("claim_a_id") or p.get("claim_a")
            b_id = p.get("claim_b_id") or p.get("claim_b")
            rel = (p.get("relation") or "neutral").strip().lower()
            if rel not in ("contradiction", "entailment", "neutral"):
                rel = "neutral"
            a_claim = id_to_claim.get(a_id, {})
            b_claim = id_to_claim.get(b_id, {})
            result.append({
                "claim_a_id": a_id,
                "claim_b_id": b_id,
                "claim_a_text": a_claim.get("text", ""),
                "claim_b_text": b_claim.get("text", ""),
                "source_a": a_claim.get("source_url") or a_claim.get("source_title", ""),
                "source_b": b_claim.get("source_url") or b_claim.get("source_title", ""),
                "relation": rel,
                "summary": (p.get("summary") or "").strip()[:300],
            })
        return result
    except Exception:
        return []


def contradiction_detection(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """Phase 4: Two-step structured contradiction detection (claim extraction, then pair comparison). Fallback: single-call legacy."""
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "KI: Detecting contradictions")
    except Exception:
        pass
    findings = _load_findings(proj_path)
    pid = project_id or proj_path.name
    use_structured = os.environ.get("RESEARCH_CONTRADICTION_STRUCTURED", "1") == "1" and len(findings) >= 2
    if use_structured:
        try:
            from tools.research_progress import step as progress_step
            progress_step(pid, "KI: Extracting claims from findings")
        except Exception:
            pass
        extracted_claims = _extract_claims_per_finding(findings, pid)
        try:
            from tools.research_progress import step as progress_step
            progress_step(pid, "KI: Comparing claim pairs")
        except Exception:
            pass
        pairs = _compare_claim_pairs(extracted_claims, pid)
        contradictions_only = [p for p in pairs if p.get("relation") == "contradiction"]
        out_contradictions = []
        for p in contradictions_only:
            out_contradictions.append({
                "claim": p.get("summary") or f"{p.get('claim_a_text', '')[:80]} vs {p.get('claim_b_text', '')[:80]}",
                "source_a": p.get("source_a", ""),
                "source_b": p.get("source_b", ""),
                "summary": p.get("summary", ""),
                "claim_a_id": p.get("claim_a_id"),
                "claim_b_id": p.get("claim_b_id"),
                "claim_a_text": p.get("claim_a_text", ""),
                "claim_b_text": p.get("claim_b_text", ""),
                "relation": p.get("relation", "contradiction"),
            })
        return {
            "extracted_claims": extracted_claims[:50],
            "contradictions": out_contradictions,
            "pair_relations": [{"claim_a_id": x.get("claim_a_id"), "claim_b_id": x.get("claim_b_id"), "relation": x.get("relation")} for x in pairs],
        }
    items = json.dumps([{"url": f.get("url"), "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:400]} for f in findings], indent=2)[:10000]
    system = """You are a research analyst. Identify CONTRADICTIONS: pairs of findings that disagree on the same fact or claim.
Return JSON: {"contradictions": [{"claim": "what they disagree on", "source_a": "url or title", "source_b": "url or title", "summary": "brief"}]}"""
    user = "FINDINGS:\n" + items + '\n\nList 0-5 contradictions. If none, return {"contradictions": []}.'
    out = _llm_json(system, user, project_id=project_id)
    return out if isinstance(out, dict) else {"contradictions": out}


def evidence_gaps(proj_path: Path, project: dict, project_id: str = "") -> dict:
    """
    Phase 4: Evidence critique — under-sourced claims, contradictions, suggested queries.
    Reads claim_ledger + findings; writes verify/evidence_critique.json when verify dir exists.
    """
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id or proj_path.name, "Evidence gaps analysis")
    except Exception:
        pass
    findings = _load_findings(proj_path)
    question = project.get("question", "")
    claim_ledger: list[dict] = []
    verify_dir = proj_path / "verify"
    if (verify_dir / "claim_ledger.json").exists():
        try:
            data = json.loads((verify_dir / "claim_ledger.json").read_text())
            claim_ledger = data.get("claims", [])
        except Exception:
            pass
    under_sourced = [c for c in claim_ledger if not c.get("is_verified") and (c.get("verification_tier") or "").strip() == "UNVERIFIED"]
    under_sourced_claims = [{"text": (c.get("text") or "")[:200], "claim_id": c.get("claim_id")} for c in under_sourced[:15]]
    items = json.dumps(
        [{"title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:400]} for f in findings],
        indent=2,
        ensure_ascii=False,
    )[:8000]
    claims_text = json.dumps(
        [{"text": (c.get("text") or "")[:150], "tier": c.get("verification_tier")} for c in claim_ledger[:25]],
        ensure_ascii=False,
    )[:4000]
    system = """You are a research analyst. Given the research question, current claim ledger (with verification tier), and findings, identify:
1) under_sourced_claims: claims that are UNVERIFIED and need more evidence (list of claim text snippets).
2) contradictions: brief description of any contradictions between sources or claims (list of strings).
3) suggested_queries: 1-5 search queries to find evidence for under-sourced claims or to resolve gaps. Each: {"query": "...", "reason": "brief", "priority": "high|medium|low"}.
Return JSON: {"under_sourced_claims": [...], "contradictions": [...], "suggested_queries": [{"query": "...", "reason": "...", "priority": "high|medium|low"}]}."""
    user = f"QUESTION: {question}\n\nCLAIM LEDGER (tier):\n{claims_text}\n\nFINDINGS (excerpts):\n{items}\n\nReturn the JSON."
    out = _llm_json(system, user, project_id=project_id)
    if not isinstance(out, dict):
        out = {"under_sourced_claims": under_sourced_claims, "contradictions": [], "suggested_queries": []}
    out.setdefault("under_sourced_claims", under_sourced_claims)
    out.setdefault("contradictions", [])
    out.setdefault("suggested_queries", [])
    if verify_dir.exists():
        try:
            (verify_dir / "evidence_critique.json").write_text(
                json.dumps(out, indent=2, ensure_ascii=False)
            )
        except Exception:
            pass
    return out


def main():
    if len(sys.argv) < 3:
        print("Usage: research_reason.py <project_id> <gap_analysis|hypothesis_formation|contradiction_detection|evidence_gaps>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    mode = sys.argv[2].lower()
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    project = load_project(proj_path)
    if mode == "gap_analysis":
        result = gap_analysis(proj_path, project, project_id=project_id)
    elif mode == "evidence_gaps":
        result = evidence_gaps(proj_path, project, project_id=project_id)
    elif mode == "hypothesis_formation":
        result = hypothesis_formation(proj_path, project, project_id=project_id)
    elif mode == "contradiction_detection":
        result = contradiction_detection(proj_path, project, project_id=project_id)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
