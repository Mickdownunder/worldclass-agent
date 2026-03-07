"""Claim/source ledger helpers: normalize, ref map, registry, provenance. No LLM."""
import json
from pathlib import Path


def _flatten_to_strings(value) -> list[str]:
    """Recursively flatten mixed list/scalar values into clean strings."""
    out: list[str] = []

    def _walk(v):
        if v is None:
            return
        if isinstance(v, (list, tuple, set)):
            for item in v:
                _walk(item)
            return
        if isinstance(v, dict):
            try:
                out.append(json.dumps(v, ensure_ascii=False)[:200])
            except Exception:
                out.append(str(v)[:200])
            return
        s = str(v).strip()
        if s:
            out.append(s)

    _walk(value)
    return out


def normalize_to_strings(value: object) -> list[str]:
    """Normalize nested claim/source fields to list[str] for safe join/iteration. Never raises."""
    if value is None:
        return []
    return _flatten_to_strings(value)


def _build_claim_source_registry(
    claim_ledger: list[dict],
    sources: list[dict],
    ref_list_with_titles: list[tuple[str, str]],
) -> str:
    """Build Claim Evidence Registry table: claim (short) | source | URL | date | tier. No LLM."""
    url_to_title = dict(ref_list_with_titles)
    url_to_date = {}
    for s in sources:
        u = (s.get("url") or "").strip()
        if u:
            url_to_date[u] = (s.get("published_date") or s.get("date") or "").strip()[:20]
    lines = ["| # | Claim (short) | Source | URL | Date | Tier |", "| --- | --- | --- | --- | --- | --- |"]
    for i, c in enumerate(claim_ledger[:50], 1):
        text = (c.get("text") or "")[:60].replace("|", " ").replace("\n", " ")
        urls = normalize_to_strings(c.get("supporting_source_ids"))
        first_url = (urls[0] or "").strip() if urls else ""
        title = (url_to_title.get(first_url) or "").strip()[:50].replace("|", " ")
        url_short = (first_url[:55] + "...") if len(first_url) > 55 else first_url
        date = url_to_date.get(first_url, "")
        tier = (c.get("verification_tier") or "").strip() or "UNVERIFIED"
        lines.append(f"| {i} | {text} | {title} | {url_short} | {date} | {tier} |")
    return "\n".join(lines)


def _build_provenance_appendix(claim_ledger: list[dict]) -> str:
    """Tier 2a: Claim → source finding IDs for traceability. No LLM."""
    lines = ["| Claim ID | Source finding IDs |", "| --- | --- |"]
    for c in claim_ledger[:50]:
        cid = (c.get("claim_id") or "").strip()
        fids_str = normalize_to_strings(c.get("source_finding_ids"))
        lines.append(f"| {cid} | {', '.join(fids_str[:15])}{' …' if len(fids_str) > 15 else ''} |")
    return "\n".join(lines)


def _ensure_source_finding_ids(claim_ledger: list[dict], proj_path: Path) -> list[dict]:
    """Ensure every claim has source_finding_ids when it has supporting_source_ids (AEM ledger may omit them)."""
    findings_dir = proj_path / "findings"
    url_to_finding_ids: dict[str, list[str]] = {}
    if findings_dir.exists():
        for p in findings_dir.glob("*.json"):
            try:
                d = json.loads(p.read_text())
                u = (d.get("url") or "").strip()
                fid = (d.get("finding_id") or "").strip()
                if u and fid:
                    url_to_finding_ids.setdefault(u, []).append(fid)
            except Exception:
                pass
    out = []
    for c in claim_ledger:
        c = dict(c)
        if not c.get("source_finding_ids") and c.get("supporting_source_ids"):
            fids = []
            for u in normalize_to_strings(c.get("supporting_source_ids")):
                if u:
                    fids.extend(url_to_finding_ids.get(u, []))
            c["source_finding_ids"] = list(dict.fromkeys(fids))[:50]
        out.append(c)
    return out


def _build_ref_map(findings: list[dict], claim_ledger: list[dict]) -> tuple[dict[str, int], list[tuple[str, str]]]:
    """Build url -> ref number (1-based) and ordered list (url, title) for References."""
    cited = set()
    for c in claim_ledger:
        for u in normalize_to_strings(c.get("supporting_source_ids")):
            if u:
                cited.add(u)
    for f in findings:
        u = (f.get("url") or "").strip()
        if u:
            cited.add(u)
    ref_list = sorted(cited)
    ref_map = {u: i + 1 for i, u in enumerate(ref_list)}
    titles = {}
    for f in findings:
        u = (f.get("url") or "").strip()
        if u and f.get("title"):
            titles[u] = f["title"]
    ref_list_with_titles = [(u, titles.get(u, "")) for u in ref_list]
    return ref_map, ref_list_with_titles


def _claim_ledger_block(claim_ledger: list[dict]) -> str:
    """Build CLAIM LEDGER text for section prompt: one line per claim_ref with short text and epistemic status."""
    lines = []
    for c in claim_ledger[:40]:
        cid = (c.get("claim_id") or "").strip()
        if not cid:
            continue
        ver = c.get("claim_version", 1)
        try:
            ver = int(ver)
        except (TypeError, ValueError):
            ver = 1
        tier = (c.get("verification_tier") or "UNVERIFIED").strip().upper()
        if c.get("is_verified") and tier not in ("VERIFIED", "AUTHORITATIVE"):
            tier = "VERIFIED"
        text = (c.get("text") or "")[:120].replace("\n", " ")
        lines.append(f"[claim_ref: {cid}@{ver}] [{tier}] {text}")
    return "\n".join(lines) if lines else ""
