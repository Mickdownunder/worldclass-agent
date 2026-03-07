"""Claim ledger from verification outputs; apply verified/authoritative tags to report."""
import json
import re
from pathlib import Path

from tools.research_common import ensure_project_layout, audit_log

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


def is_authoritative_source(url: str) -> bool:
    u = (url or "").lower()
    if not u:
        return False
    return any(d in u for d in _AUTHORITATIVE_DOMAINS)


def _claim_fact_similarity(claim_text: str, fact_statement: str) -> float:
    wa = set(re.findall(r"\b[a-z0-9\-\.\%]{2,}\b", (claim_text or "").lower()))
    wb = set(re.findall(r"\b[a-z0-9\-\.\%]{2,}\b", (fact_statement or "").lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def build_claim_ledger(proj_path: Path, project: dict) -> dict:
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
    default_reliability = 0.65 if not rel_by_url else 0.5
    sources_dir = proj_path / "sources"
    total_project_sources = (
        len([f for f in sources_dir.glob("*.json") if not f.name.endswith("_content.json")])
        if sources_dir.exists() else 1
    )
    findings_dir = proj_path / "findings"
    url_to_finding_ids: dict[str, list[str]] = {}
    url_to_snippet: dict[str, str] = {}
    if findings_dir.exists():
        for p in findings_dir.glob("*.json"):
            try:
                d = json.loads(p.read_text())
                u = (d.get("url") or "").strip()
                fid = (d.get("finding_id") or "").strip()
                excerpt = (d.get("excerpt") or "").strip()[:500]
                if u and fid:
                    url_to_finding_ids.setdefault(u, []).append(fid)
                if u and excerpt:
                    url_to_snippet[u] = excerpt
            except Exception:
                pass
    fact_check_facts: list[dict] = []
    if (verify_dir / "fact_check.json").exists():
        try:
            fc = json.loads((verify_dir / "fact_check.json").read_text())
            fact_check_facts = fc.get("facts", [])
        except Exception:
            pass

    def _claim_matches_disputed_fact(claim_text: str) -> bool:
        for f in fact_check_facts:
            if (f.get("verification_status") or "").strip().lower() != "disputed":
                continue
            st = (f.get("statement") or "").strip()
            if st and _claim_fact_similarity(claim_text, st) >= 0.4:
                return True
        return False

    def _claim_matches_confirmed_fact(claim_text: str) -> bool:
        for f in fact_check_facts:
            if (f.get("verification_status") or "").strip().lower() not in ("confirmed", "supported"):
                continue
            st = (f.get("statement") or "").strip()
            if st and _claim_fact_similarity(claim_text, st) >= 0.4:
                return True
        return False

    entity_names_list: list[str] = []
    graph_path_ledger = proj_path / "connect" / "entity_graph.json"
    if graph_path_ledger.exists():
        try:
            g = json.loads(graph_path_ledger.read_text())
            entity_names_list = [(e.get("name") or "").strip() for e in g.get("entities", []) if (e.get("name") or "").strip()]
        except Exception:
            pass
    contradiction_source_urls: set[str] = set()
    if (verify_dir / "connect_context.json").exists():
        try:
            ctx = json.loads((verify_dir / "connect_context.json").read_text())
            contradiction_source_urls = set(ctx.get("contradiction_source_urls") or [])
        except Exception:
            pass
    if not contradiction_source_urls and (proj_path / "contradictions.json").exists():
        try:
            data = json.loads((proj_path / "contradictions.json").read_text())
            for c in data.get("contradictions", []):
                for key in ("source_a", "source_b"):
                    v = (c.get(key) or "").strip()
                    if v:
                        contradiction_source_urls.add(v)
        except Exception:
            pass

    cove_overlay: dict[str, bool] = {}
    if (verify_dir / "cove_overlay.json").exists():
        try:
            cove_data = json.loads((verify_dir / "cove_overlay.json").read_text())
            for item in cove_data.get("claims", []):
                prefix = (item.get("claim_text_prefix") or "").strip()[:120]
                if prefix and item.get("cove_supports") is False:
                    cove_overlay[prefix] = False
        except Exception:
            pass

    existing_ledger_path = verify_dir / "claim_ledger.json"
    prev_verified: dict[str, dict] = {}
    if existing_ledger_path.exists():
        try:
            prev = json.loads(existing_ledger_path.read_text())
            for pc in prev.get("claims", []):
                if pc.get("is_verified"):
                    key = (pc.get("text") or pc.get("claim") or "")[:100]
                    if key:
                        prev_verified[key] = pc
        except Exception:
            pass
    claims_out = []
    for i, c in enumerate(claims_in):
        try:
            from tools.research_progress import step as progress_step
            progress_step(proj_path.name, f"Verifying claim {i+1}/{len(claims_in)}", i+1, len(claims_in))
        except Exception:
            pass
        claim_id = f"cl_{i}_{hash(c.get('claim', '')[:100]) % 10000}"
        text = (c.get("claim") or "").strip()
        supporting = c.get("supporting_sources") or []
        if isinstance(supporting, str):
            supporting = [supporting] if supporting else []
        supporting_source_ids = [s for s in supporting if s][:20]
        reliable_sources = [u for u in supporting_source_ids if rel_by_url.get(u, default_reliability) >= 0.6]
        distinct_reliable = len(set(reliable_sources))
        dispute = (c.get("disputed") or c.get("verification_status", "") == "disputed" or
                   str(c.get("verification_status", "")).lower() == "disputed")
        if not dispute and text and _claim_matches_disputed_fact(text):
            dispute = True
        authoritative_sources = [u for u in reliable_sources if is_authoritative_source(u)]
        research_mode = ((project.get("config") or {}).get("research_mode") or "standard").strip().lower()

        if research_mode == "discovery":
            if distinct_reliable >= 2 and not dispute:
                verification_tier = "ESTABLISHED"
                is_verified = True
                verification_reason = f"{distinct_reliable} independent sources confirm"
            elif len(set(supporting_source_ids)) >= 1 and not dispute:
                verification_tier = "EMERGING"
                is_verified = True
                verification_reason = "single or limited sourcing, emerging concept"
            else:
                verification_tier = "SPECULATIVE"
                is_verified = False
                verification_reason = "speculative / opinion-based"
        elif distinct_reliable >= 2 and not dispute:
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
        elif distinct_reliable == 1 and not dispute and _claim_matches_confirmed_fact(text):
            verification_tier = "AUTHORITATIVE"
            research_mode = ((project.get("config") or {}).get("research_mode") or "standard").lower()
            is_verified = research_mode == "frontier"
            verification_reason = "single source + fact_check confirmed"
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
        key = text[:100]
        for prefix in (text[:80], text[:100], text[:120]):
            if prefix in cove_overlay and cove_overlay[prefix] is False:
                verification_tier = "UNVERIFIED"
                is_verified = False
                verification_reason = "CoVe independent verification did not support"
                break
        if not is_verified and key in prev_verified:
            is_verified = True
            verification_tier = prev_verified[key].get("verification_tier", "VERIFIED")
            verification_reason = prev_verified[key].get("verification_reason", verification_reason)
            supporting_source_ids = prev_verified[key].get("supporting_source_ids", supporting_source_ids)
        total_checked = len(c.get("all_checked_sources", [])) or total_project_sources
        claim_support_rate = round(len(supporting_source_ids) / max(1, total_checked), 3)
        source_finding_ids = []
        for u in supporting_source_ids:
            source_finding_ids.extend(url_to_finding_ids.get(u, []))
        source_finding_ids = list(dict.fromkeys(source_finding_ids))[:50]
        in_contradiction = bool(
            contradiction_source_urls
            and any(
                u in contradiction_source_urls or any(cu in u for cu in contradiction_source_urls)
                for u in supporting_source_ids
            )
        )
        supporting_evidence = [
            {
                "url": u,
                "snippet": (url_to_snippet.get(u) or "")[:300],
                "source_id": (url_to_finding_ids.get(u) or [""])[0],
            }
            for u in supporting_source_ids[:15]
        ]
        rels = [rel_by_url.get(u, default_reliability) for u in supporting_source_ids]
        credibility_weight = round(sum(rels) / len(rels), 3) if rels else 0.5
        claim_entity_ids = []
        if entity_names_list and text:
            text_lower = text.lower()
            for name in entity_names_list:
                if len(name) > 2 and name.lower() in text_lower:
                    claim_entity_ids.append(name)
        claim_entity_ids = list(dict.fromkeys(claim_entity_ids))[:15]
        claims_out.append({
            "claim_id": claim_id,
            "text": text,
            "supporting_source_ids": supporting_source_ids,
            "source_finding_ids": source_finding_ids,
            "supporting_evidence": supporting_evidence,
            "entity_ids": claim_entity_ids,
            "credibility_weight": credibility_weight,
            "is_verified": is_verified,
            "verification_tier": verification_tier,
            "verification_reason": verification_reason,
            "claim_support_rate": claim_support_rate,
            "in_contradiction": in_contradiction,
        })
    audit_log(proj_path, "claim_ledger_built", {
        "total_claims": len(claims_out),
        "verified_count": sum(1 for c in claims_out if c.get("is_verified")),
    })
    return {"claims": claims_out}


_VERIFIED_TAG_PATTERN = re.compile(r"\s*\[VERIFIED(?::[^\]]+)?\]", re.IGNORECASE)
_AUTHORITATIVE_TAG_PATTERN = re.compile(r"\s*\[AUTHORITATIVE(?::[^\]]+)?\]", re.IGNORECASE)


def apply_verified_tags_to_report(report: str, claims: list[dict]) -> str:
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
