"""Synthesis contract: claim_ref validation, factuality guard. Spec §6.2–6.3."""
import re

# Explicit claim_ref format: [claim_ref: id@ver] or [claim_ref: id1@v1; id2@v2]. Machine-parseable.
CLAIM_REF_PATTERN = re.compile(r"\[claim_ref:\s*([^\]]+)\]", re.IGNORECASE)


def _normalize_ref(ref: str) -> str | None:
    """Normalize to claim_id@version; return None if invalid."""
    ref = (ref or "").strip()
    if not ref or "@" not in ref:
        return None
    parts = ref.split("@", 1)
    cid, ver = parts[0].strip(), parts[1].strip()
    if not cid:
        return None
    try:
        int(ver)
    except ValueError:
        return None
    return f"{cid}@{ver}"


def extract_claim_refs_from_report(report: str) -> list[str]:
    """Extract all claim_ref values from report. Returns list of normalized refs (id@version)."""
    refs: list[str] = []
    for m in CLAIM_REF_PATTERN.finditer(report):
        inner = m.group(1).strip()
        for part in re.split(r"[;,]", inner):
            r = _normalize_ref(part)
            if r:
                refs.append(r)
    return refs


def _build_valid_claim_ref_set(claim_ledger: list[dict]) -> set[str]:
    """Set of valid claim_ref strings (claim_id@version) from ledger."""
    out: set[str] = set()
    for c in claim_ledger:
        cid = (c.get("claim_id") or "").strip()
        if not cid:
            continue
        ver = c.get("claim_version", 1)
        try:
            ver = int(ver)
        except (TypeError, ValueError):
            ver = 1
        out.add(f"{cid}@{ver}")
    return out


def _sentence_contains_valid_claim_ref(sentence: str, valid_refs: set[str]) -> bool:
    """True if sentence contains at least one [claim_ref: X@Y] with X@Y in valid_refs."""
    for m in CLAIM_REF_PATTERN.finditer(sentence):
        inner = m.group(1).strip()
        for part in re.split(r"[;,]", inner):
            r = _normalize_ref(part)
            if r and r in valid_refs:
                return True
    return False


def _factuality_guard(report_body: str, findings: list[dict], claim_ledger: list[dict]) -> dict:
    """Check numeric and quoted spans in report against findings and claim texts. Observe-only (no block)."""
    corpus_parts = []
    for f in findings[:80]:
        excerpt = (f.get("excerpt") or "")[:2000]
        if excerpt:
            corpus_parts.append(excerpt.lower())
    for c in claim_ledger:
        text = (c.get("text") or "")[:500]
        if text:
            corpus_parts.append(text.lower())
    corpus = " ".join(corpus_parts)
    corpus_norm = re.sub(r"\s+", " ", corpus)
    if not corpus_norm.strip():
        return {"unsupported_spans": [], "checked_count": 0, "unsupported_count": 0, "enabled": False}

    candidates = []
    for m in re.finditer(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*%?", report_body):
        candidates.append(m.group(0).strip())
    for m in re.finditer(r"\b(19|20)\d{2}\b", report_body):
        candidates.append(m.group(0))
    for m in re.finditer(r'"[^"]{10,80}"', report_body):
        candidates.append(m.group(0).strip())
    candidates = list(dict.fromkeys(candidates))[:100]
    unsupported = []
    for span in candidates:
        if len(span) < 4:
            continue
        norm_span = re.sub(r"\s+", " ", span.lower().strip())
        if norm_span in corpus_norm or (len(norm_span) > 15 and norm_span[:20] in corpus_norm):
            continue
        if re.search(re.escape(norm_span.replace(",", ".")), corpus_norm):
            continue
        unsupported.append(span[:100])
    return {
        "unsupported_spans": unsupported[:20],
        "checked_count": len(candidates),
        "unsupported_count": len(unsupported),
        "enabled": True,
    }


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _is_claim_like_sentence(sentence: str) -> bool:
    """Heuristic: sentence that looks like a factual claim (length + signals)."""
    s = (sentence or "").strip()
    words = s.split()
    if len(words) < 10:
        return False
    lower = s.lower()
    signals = ("found that", "study shows", "report states", "data indicate", "percent", "%", "research suggests", "evidence shows", "according to")
    if any(sig in lower for sig in signals):
        return True
    if re.search(r'\d+\s*%|\d+\.\d+', s):
        return True
    return False


def _sentence_overlaps_claim(sentence: str, claim_texts_normalized: list[str]) -> bool:
    """True if sentence overlaps substantially with any claim text (substring or word overlap)."""
    norm = _normalize_for_match(sentence)
    if not norm:
        return False
    words = set(re.findall(r"\b[a-z0-9]{2,}\b", norm))
    for ct in claim_texts_normalized:
        if norm in ct or ct in norm:
            return True
        cw = set(re.findall(r"\b[a-z0-9]{2,}\b", ct))
        if cw and words and len(words & cw) / max(len(words), 1) >= 0.25:
            return True
    return False


def validate_synthesis_contract(report: str, claim_ledger: list[dict], mode: str) -> dict:
    """
    Hard claim_ref-enforced contract (Spec §6.2–6.3):
    - Every claim_ref in report must resolve to an existing ledger entry.
    - Every claim-bearing sentence must carry at least one valid [claim_ref: id@version].
    - No new claims (claim-like sentence without valid ref => violation).
    When claim_ledger is empty (non-AEM), ref checks are skipped for backward compatibility.
    Returns dict: unknown_refs, unreferenced_claim_sentences, unreferenced_claim_sentence_count,
      new_claims_in_synthesis (same count), tentative_labels_ok, valid.
    """
    valid_refs = _build_valid_claim_ref_set(claim_ledger)
    refs_in_report = extract_claim_refs_from_report(report)
    unknown_refs = [r for r in refs_in_report if r not in valid_refs]
    unknown_refs_unique = list(dict.fromkeys(unknown_refs))

    unreferenced_sentences: list[str] = []
    if valid_refs:
        sentences = re.split(r"(?<=[.!?])\s+", report)
        for sent in sentences:
            sent = sent.strip()
            if not sent or len(sent) < 20:
                continue
            if not _is_claim_like_sentence(sent):
                continue
            if not _sentence_contains_valid_claim_ref(sent, valid_refs):
                unreferenced_sentences.append(sent[:200])
    unreferenced_count = len(unreferenced_sentences)

    tentative_ok = True
    tentative_claims = [c for c in claim_ledger if (c.get("falsification_status") or "").strip() == "PASS_TENTATIVE"]
    if tentative_claims:
        report_lower = report.lower()
        for c in tentative_claims:
            text_snippet = (c.get("text") or "")[:60]
            if text_snippet and _normalize_for_match(text_snippet) not in _normalize_for_match(report):
                continue
            if "tentative" not in report_lower and "[tentative]" not in report_lower and "pass_tentative" not in report_lower:
                tentative_ok = False
                break

    ref_valid = len(unknown_refs_unique) == 0 and (unreferenced_count == 0 or not valid_refs)
    valid = ref_valid and tentative_ok
    return {
        "unknown_refs": unknown_refs_unique,
        "unreferenced_claim_sentences": unreferenced_sentences,
        "unreferenced_claim_sentence_count": unreferenced_count,
        "new_claims_in_synthesis": unreferenced_count,
        "tentative_labels_ok": tentative_ok,
        "valid": valid,
    }


class SynthesisContractError(Exception):
    """Raised when synthesis violates hard contract and mode is strict."""
    pass
