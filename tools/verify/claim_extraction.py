"""Claim extraction from findings, dedup, thesis relevance; CoVe overlay."""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tools.research_common import ensure_project_layout, get_principles_for_research
from tools.verify.common import (
    load_findings,
    load_source_metadata,
    load_connect_context,
    llm_json,
    verify_model,
)

CLAIM_EXTRACTION_BATCH_SIZE = 18
COVE_CLAIM_BATCH_LIMIT = 20


def thesis_relevance(claim_text: str, thesis_current: str) -> float:
    if not thesis_current or not claim_text:
        return 0.0
    tw = set(re.findall(r"\b[a-z0-9]{3,}\b", thesis_current.lower()))
    cw = set(re.findall(r"\b[a-z0-9]{3,}\b", claim_text.lower()))
    if not tw or not cw:
        return 0.0
    return len(tw & cw) / len(tw)


def _claim_verification_batch(
    findings_batch: list[dict],
    source_meta: list[dict],
    question: str,
    project_id: str,
    domain: str = "",
) -> list[dict]:
    if not findings_batch:
        return []
    items = json.dumps(
        [{"url": f.get("url"), "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:800]} for f in findings_batch],
        indent=2, ensure_ascii=False
    )
    meta_text = json.dumps(source_meta[:40], indent=2, ensure_ascii=False)[:6000] if source_meta else "[]"
    system = f"""You are a research analyst. The research question is:
"{question}"

From the findings AND source metadata, extract ALL KEY CLAIMS that answer this question.
Extract at least 3-10 claims from this batch if the material supports it. Each claim should be a specific, verifiable factual statement.
For each claim, list ALL sources that support it.
Return JSON: {{"claims": [{{"claim": "...", "supporting_sources": ["url1", "url2"], "confidence": 0.0-1.0, "verified": true/false}}]}}
verified = true only if at least 2 distinct source URLs support the claim. Be strict but thorough in matching.
Prefer specific, quantitative claims (e.g. "X achieved Y% response rate in phase Z trial") over vague narrative statements."""
    principles_block = get_principles_for_research(question, domain=domain, limit=5)
    if principles_block:
        system += "\n\n" + principles_block
    user = f"QUESTION: {question}\n\nFINDINGS (this batch):\n{items}\n\nSOURCE METADATA (search snippets — use as supporting evidence for cross-referencing):\n{meta_text}\n\nExtract claims and verification status. Return only valid JSON."
    out = llm_json(system, user, project_id=project_id, model_fn=verify_model)
    if isinstance(out, dict) and "claims" in out:
        return out["claims"]
    if isinstance(out, list):
        return out
    return []


def normalize_claim_for_dedup(text: str) -> str:
    t = " ".join((text or "").lower().split()).strip()
    t = re.sub(r"[^\w\s\-\.\%]", " ", t)
    return " ".join(t.split())[:250]


def claim_similarity(a: str, b: str) -> float:
    wa = set(re.findall(r"\b[a-z0-9\-\.\%]{2,}\b", a.lower()))
    wb = set(re.findall(r"\b[a-z0-9\-\.\%]{2,}\b", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def merge_dedupe_claims(claims_list: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for c in claims_list:
        text = (c.get("claim") or "").strip()
        if not text:
            continue
        norm = normalize_claim_for_dedup(text)
        if not norm:
            continue
        is_dup = False
        for m in merged:
            existing = normalize_claim_for_dedup(m.get("claim") or "")
            if norm == existing:
                is_dup = True
                break
            if len(norm) >= 30 and len(existing) >= 30 and claim_similarity(norm, existing) >= 0.65:
                is_dup = True
                break
            if norm.startswith(existing[:40]) or existing.startswith(norm[:40]):
                is_dup = True
                break
        if is_dup:
            continue
        merged.append(c)
    return merged


def claim_verification(proj_path: Path, project: dict, project_id: str = "") -> dict:
    ensure_project_layout(proj_path)
    question = project.get("question", "")
    findings = load_findings(proj_path, question=question)
    source_meta = load_source_metadata(proj_path)
    if not findings and not source_meta:
        return {"claims": []}
    batch_size = CLAIM_EXTRACTION_BATCH_SIZE
    domain = (project.get("domain") or "").strip()
    batches = [
        (start, findings[start : start + batch_size])
        for start in range(0, len(findings), batch_size)
    ]
    if not batches:
        return {"claims": []}
    total_batches = len(batches)
    try:
        from tools.research_progress import step as progress_step
    except Exception:
        progress_step = lambda _pid, _msg, _idx=None, _tot=None: None
    results_by_batch: dict[int, list[dict]] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_batch = {
            executor.submit(
                _claim_verification_batch,
                batch,
                source_meta,
                question,
                project_id,
                domain,
            ): batch_num
            for batch_num, (_start, batch) in enumerate(batches, start=1)
        }
        for future in as_completed(future_to_batch):
            batch_num = future_to_batch[future]
            try:
                batch_claims = future.result()
            except Exception:
                batch_claims = []
            results_by_batch[batch_num] = batch_claims
            done += 1
            progress_step(
                project_id or proj_path.name,
                f"Extracting claims batch {done}/{total_batches} ({len(findings)} findings)",
                done,
                total_batches,
            )
    all_claims: list[dict] = []
    for batch_num in sorted(results_by_batch.keys()):
        all_claims.extend(results_by_batch[batch_num])
    merged = merge_dedupe_claims(all_claims)
    thesis_current, contradiction_urls = load_connect_context(proj_path)
    if thesis_current:
        merged.sort(
            key=lambda c: thesis_relevance((c.get("claim") or "").strip(), thesis_current),
            reverse=True,
        )
    entity_names: set[str] = set()
    graph_path = proj_path / "connect" / "entity_graph.json"
    if graph_path.exists():
        try:
            graph = json.loads(graph_path.read_text())
            for e in graph.get("entities", []):
                n = (e.get("name") or "").strip()
                if n:
                    entity_names.add(n.lower())
        except Exception:
            pass
    if entity_names:
        def _entity_score(c: dict) -> int:
            t = (c.get("claim") or "").lower()
            return sum(1 for name in entity_names if len(name) > 2 and name in t)
        merged.sort(
            key=lambda c: (
                thesis_relevance((c.get("claim") or "").strip(), thesis_current),
                _entity_score(c),
            ),
            reverse=True,
        )
    verify_dir = proj_path / "verify"
    verify_dir.mkdir(parents=True, exist_ok=True)
    connect_ctx = {
        "thesis_current": thesis_current,
        "contradiction_source_urls": list(contradiction_urls),
    }
    try:
        (verify_dir / "connect_context.json").write_text(
            json.dumps(connect_ctx, indent=2, ensure_ascii=False)
        )
    except Exception:
        pass
    return {"claims": merged}


def run_claim_verification_cove(proj_path: Path, project: dict, project_id: str = "") -> dict:
    ensure_project_layout(proj_path)
    verify_dir = proj_path / "verify"
    claims_in: list[dict] = []
    if (verify_dir / "claim_verification.json").exists():
        try:
            data = json.loads((verify_dir / "claim_verification.json").read_text())
            claims_in = data.get("claims", [])[:COVE_CLAIM_BATCH_LIMIT]
        except Exception:
            pass
    if not claims_in:
        return {"claims": []}

    findings = load_findings(proj_path, question=project.get("question", ""))
    if not findings:
        return {"claims": [{"claim_text_prefix": (c.get("claim") or "")[:120], "cove_supports": False} for c in claims_in]}

    evidence_parts = []
    for f in findings[:40]:
        url = (f.get("url") or "").strip()
        excerpt = (f.get("excerpt") or "")[:400]
        if url and excerpt:
            evidence_parts.append(f"[{url}]: {excerpt}")
    evidence_text = "\n\n".join(evidence_parts)[:14000]

    pairs: list[tuple[str, str]] = []
    url_to_snippet: dict[str, str] = {}
    for f in findings:
        u = (f.get("url") or "").strip()
        if u:
            url_to_snippet[u] = (f.get("excerpt") or "")[:500]
    for c in claims_in:
        text = (c.get("claim") or "").strip()[:120]
        supporting = c.get("supporting_sources") or []
        if isinstance(supporting, str):
            supporting = [supporting] if supporting else []
        snippets = [url_to_snippet.get(u, "") for u in supporting if u][:3]
        ev = " ".join(s for s in snippets if s).strip() or evidence_text[:800]
        pairs.append((text, ev))

    try:
        system = """You are a verifier. Given ONLY the evidence excerpt for each claim, does the evidence support the claim?
Reply with a JSON object: {"results": [true, false, true, ...]} with exactly one boolean per claim in order.
true = evidence supports the claim; false = evidence does not support or is inconclusive. No other output."""
        user_parts = [f"Claim {i+1}: {t}\nEvidence {i+1}: {e[:600]}" for i, (t, e) in enumerate(pairs)]
        user = "\n\n---\n\n".join(user_parts)[:18000]
        out = llm_json(system, user, project_id=project_id, model_fn=verify_model)
        results = out.get("results", []) if isinstance(out, dict) else []
        while len(results) < len(pairs):
            results.append(False)
        results = results[: len(pairs)]
        overlay_claims = [
            {"claim_text_prefix": pairs[i][0][:120], "cove_supports": bool(results[i])}
            for i in range(len(pairs))
        ]
    except Exception:
        overlay_claims = [{"claim_text_prefix": (c.get("claim") or "")[:120], "cove_supports": False} for c in claims_in]

    verify_dir.mkdir(parents=True, exist_ok=True)
    (verify_dir / "cove_overlay.json").write_text(
        json.dumps({"claims": overlay_claims}, indent=2, ensure_ascii=False)
    )
    return {"claims": overlay_claims}
