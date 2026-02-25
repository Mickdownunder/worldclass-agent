#!/usr/bin/env python3
"""
Central policy for research finding admission into Memory (Quality Contract).
Only findings that pass the gate are stored as 'accepted' and eligible for embedding/Brain context.
Thresholds live here only; backward compat: existing rows default to quarantined.

Usage:
  from tools.research_memory_policy import decide, THRESHOLDS
  decision = decide({"reliability_score": 0.7, "importance_score": 0.6, "verification_status": "confirmed"})
"""
from __future__ import annotations

# Central thresholds (single source of truth)
THRESHOLDS = {
    "reliability_min": 0.6,
    "importance_min": 0.5,
    "verification_reject": "unverified",  # status that blocks acceptance
}


def decide(finding: dict) -> str:
    """
    Deterministic admission: accepted | quarantined | rejected.
    finding may contain: reliability_score, importance_score, verification_status, evidence_count, critic_score, relevance_score.
    """
    rel = finding.get("reliability_score")
    imp = finding.get("importance_score")
    ver = (finding.get("verification_status") or "").strip().lower()

    # Reject: explicitly unverified
    if ver == THRESHOLDS["verification_reject"]:
        return "rejected"

    # Treat None as fail for acceptance (backward compat: no scores => quarantined)
    rel_ok = rel is not None and rel >= THRESHOLDS["reliability_min"]
    imp_ok = imp is not None and imp >= THRESHOLDS["importance_min"]
    ver_ok = ver not in ("", "unverified")

    if rel_ok and imp_ok and ver_ok:
        return "accepted"
    if rel is not None and rel < 0.3:
        return "rejected"
    return "quarantined"


def reason(finding: dict, decision: str) -> str:
    """Short human-readable reason for the decision (for admission_events)."""
    if decision == "accepted":
        return "passed reliability, importance, verification"
    if decision == "rejected":
        ver = (finding.get("verification_status") or "").lower()
        if ver == "unverified":
            return "verification_status=unverified"
        rel = finding.get("reliability_score")
        if rel is not None and rel < 0.3:
            return "reliability below reject threshold"
        return "failed minimum thresholds"
    return "below acceptance thresholds (quarantined)"
