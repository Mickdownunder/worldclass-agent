"""
Claim lifecycle derivation: epistemic state and confidence labels.
"""
from tools.pdf_report.tokens import (
    STATE_STABLE,
    STATE_TENTATIVE,
    STATE_CONTESTED,
    STATE_DECAYING,
)


def derive_claim_state(claim_v, claim_e, source_rel_map):
    """Derive epistemic lifecycle state from verification + evidence data."""
    verified = claim_v.get("verified", False) or claim_e.get("is_verified", False)
    confidence = claim_v.get("confidence", 0.5)
    sources = claim_v.get("supporting_sources", []) or claim_e.get("supporting_source_ids", [])
    n_sources = len(sources)

    avg_rel = 0.0
    if sources and source_rel_map:
        rels = [source_rel_map.get(s, 0.5) for s in sources]
        avg_rel = sum(rels) / len(rels) if rels else 0.5

    if not verified:
        return STATE_CONTESTED
    if verified and n_sources >= 3 and confidence >= 0.9 and avg_rel >= 0.7:
        return STATE_STABLE
    if verified and avg_rel < 0.5:
        return STATE_DECAYING
    return STATE_TENTATIVE


def confidence_label(c):
    """Return (label_str, css_class) for confidence value."""
    if c >= 0.9:
        return "high", "b-high"
    if c >= 0.7:
        return "medium", "b-med"
    return "low", "b-low"
