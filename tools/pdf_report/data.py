"""
Load report markdown, verify data, and extract sections. Build enriched claims and context for PDF.
"""
import json
import re
from pathlib import Path

from tools.pdf_report.tokens import esc
from tools.pdf_report import claims


def load_latest_report_md(proj_dir: Path):
    """Return (md_text, timestamp_str) or None if no report found."""
    reports_dir = proj_dir / "reports"
    if not reports_dir.exists():
        return None
    md_files = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.name, reverse=True)
    if not md_files:
        return None
    path = md_files[0]
    ts = path.stem.replace("report_", "").replace("_revised", "").strip()
    md = path.read_text(encoding="utf-8", errors="replace")
    md = re.sub(r"\n---\s*\n\s*## References\s*\n.*", "", md, flags=re.DOTALL | re.IGNORECASE)
    md = re.sub(r"\n#+\s*References\s*\n.*", "", md, flags=re.DOTALL | re.IGNORECASE)
    return md.rstrip(), ts


def derive_title(md: str, question: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return (question[:120] if question and len(question) > 10 else "Research Report")


def md_to_html(md: str) -> str:
    import markdown
    html = markdown.markdown(md, extensions=["extra", "nl2br", "smarty"])
    def add_h2_id(m):
        title = m.group(1)
        slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-").lower()[:50]
        return f'<h2 id="{slug}">{title}</h2>'
    html = re.sub(r"<h2>(.+?)</h2>", add_h2_id, html)
    html = re.sub(r"\[VERIFIED(?::[^\]]+)?\]", '<span class="verified-tag">VERIFIED</span>', html)
    def wrap_verified(m):
        if "verified-tag" in m.group(1):
            return f'<div class="verified-claim"><p>{m.group(1)}</p></div>'
        return m.group(0)
    html = re.sub(r"<p>(.*?)</p>", wrap_verified, html, flags=re.DOTALL)
    return html


def format_duration(proj_data: dict) -> str:
    pt = proj_data.get("phase_timings") or {}
    if not pt:
        created = proj_data.get("created_at") or ""
        if created:
            try:
                from datetime import datetime, timezone
                start = datetime.fromisoformat(created.replace("Z", "+00:00"))
                d = (datetime.now(timezone.utc) - start).total_seconds()
                return f"{int(d)}s" if d < 60 else (f"{d/60:.1f}m" if d < 3600 else f"{d/3600:.1f}h")
            except Exception:
                pass
        return "—"
    total_s = sum(t.get("duration_s") or 0 for t in pt.values())
    return f"{int(total_s)}s" if total_s < 60 else (f"{total_s/60:.1f}m" if total_s < 3600 else f"{total_s/3600:.1f}h")


def extract_section(md, pattern):
    m = re.search(pattern, md, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extract_exec_summary(md):
    return extract_section(md, r"##\s*\d*\.?\s*Executive\s+Summary\s*\n+(.*?)(?=\n---|\n##)")


def extract_conclusion(md):
    for pat in [
        r"##\s*\d*\.?\s*(?:Conclusion|Thesis|Fazit|Zusammenfassung).*?\n+(.*?)(?=\n---|\n##|\Z)",
        r"##\s*\d*\.?\s*(?:Key\s+Findings).*?\n+(.*?)(?=\n---|\n##)",
        r"##\s*\d*\.?\s*(?:Executive\s+Summary).*?\n+(.*?)(?=\n---|\n##)",
    ]:
        result = extract_section(md, pat)
        if result and len(result) > 50:
            return result
    return ""


def extract_bullet_items(md, section_pattern):
    block = extract_section(md, section_pattern)
    if not block:
        return []
    items = []
    for item in re.findall(r"-\s*\*\*(.+?)\*\*[:\s]*\n?\s*(.*?)(?=\n-\s*\*\*|\Z)", block, re.DOTALL):
        items.append((item[0].strip(), item[1].strip()))
    if not items:
        for line in block.split("\n"):
            line = line.strip().lstrip("- ")
            if line:
                items.append((line, ""))
    return items


def extract_gaps(md):
    return extract_bullet_items(md, r"##\s*\d*\.?\s*(?:Contradictions|Gaps|Contradictions\s*/\s*Gaps).*?\n+(.*?)(?=\n---|\n##)")


def extract_next_steps(md):
    return extract_bullet_items(md, r"##\s*\d*\.?\s*(?:Suggested\s+Next\s+Steps|Next\s+Steps|Retrieval|Recommendations).*?\n+(.*?)(?=\n---|\n##|\Z)")


def extract_key_findings(md):
    return extract_bullet_items(md, r"##\s*\d*\.?\s*(?:Key\s+Findings).*?\n+(.*?)(?=\n---|\n##)")


def load_verify_data(proj_dir: Path):
    """Load claim_evidence, claim_verification, fact_check, source_reliability, critique from verify/."""
    claim_evidence = []
    for p in [proj_dir / "verify" / "claim_evidence_map_latest.json", proj_dir / "verify" / "claim_ledger.json"]:
        if p.exists():
            try:
                claim_evidence = json.loads(p.read_text()).get("claims", [])
                break
            except Exception:
                pass

    claim_verification = []
    cv_path = proj_dir / "verify" / "claim_verification.json"
    if cv_path.exists():
        try:
            claim_verification = json.loads(cv_path.read_text()).get("claims", [])
        except Exception:
            pass

    source_reliability = []
    sr_path = proj_dir / "verify" / "source_reliability.json"
    if sr_path.exists():
        try:
            source_reliability = json.loads(sr_path.read_text()).get("sources", [])
        except Exception:
            pass

    critique = {}
    cr_path = proj_dir / "verify" / "critique.json"
    if cr_path.exists():
        try:
            critique = json.loads(cr_path.read_text())
        except Exception:
            pass

    src_rel_map = {}
    for s in source_reliability:
        url = (s.get("url") or "").strip()
        if url:
            src_rel_map[url] = s.get("reliability_score", 0.5)

    return {
        "claim_evidence": claim_evidence,
        "claim_verification": claim_verification,
        "source_reliability": source_reliability,
        "critique": critique,
        "src_rel_map": src_rel_map,
    }


def build_enriched_claims(report_md: str, claim_evidence, claim_verification, src_rel_map):
    """Build enriched_claims and epi_counts from verify data and report markdown."""
    from tools.pdf_report.tokens import STATE_STABLE, STATE_TENTATIVE, STATE_CONTESTED

    cv_map = {}
    for cv in claim_verification:
        key = cv.get("claim", "")[:80]
        cv_map[key] = cv

    gaps_raw = extract_gaps(report_md)
    gap_texts = " ".join(t + " " + d for t, d in gaps_raw).lower()

    enriched_claims = []
    for ce in claim_evidence:
        text = ce.get("text", "") or ce.get("claim", "")
        cv = cv_map.get(text[:80], {})
        confidence = cv.get("confidence", 0.5)
        sources = ce.get("supporting_source_ids", []) or cv.get("supporting_sources", [])
        verified = ce.get("is_verified", False) or cv.get("verified", False)

        state = claims.derive_claim_state(
            {"verified": verified, "confidence": confidence, "supporting_sources": sources},
            ce, src_rel_map
        )

        counter = "—"
        for gt, gd in gaps_raw:
            if any(w in gt.lower() for w in text.lower().split()[:4] if len(w) > 4):
                counter = gd[:100] if gd else gt
                break

        if confidence >= 0.9 and len(sources) >= 3:
            failure = "Stable unless primary sources retracted"
        elif confidence >= 0.7:
            failure = "Weakens if single supporting source contradicted"
        else:
            failure = "Fails with any credible counter-evidence"

        enriched_claims.append({
            "text": text,
            "state": state,
            "confidence": confidence,
            "verified": verified,
            "sources": sources,
            "counter": counter,
            "failure_boundary": failure,
        })

    epi_counts = {
        "stable": sum(1 for c in enriched_claims if c["state"] == STATE_STABLE),
        "tentative": sum(1 for c in enriched_claims if c["state"] == STATE_TENTATIVE),
        "contested": sum(1 for c in enriched_claims if c["state"] == STATE_CONTESTED),
        "unresolved": len(gaps_raw),
    }
    return enriched_claims, epi_counts
