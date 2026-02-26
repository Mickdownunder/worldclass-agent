#!/usr/bin/env python3
"""
Threshold Calibrator: adaptive quality gate thresholds from project_outcomes.
After 10+ successful projects, compute 25th percentile of gate metrics and use as thresholds (with floor).
Usage: import get_calibrated_thresholds from tools.research_calibrator; thresholds = get_calibrated_thresholds()
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Safe minimums: never go below these
FLOOR = {
    "findings_count_min": 5,
    "unique_source_count_min": 3,
    "verified_claim_count_min": 1,
    "claim_support_rate_min": 0.3,
    "high_reliability_source_ratio_min": 0.3,
}


def get_calibrated_thresholds():
    """
    Return calibrated thresholds from project_outcomes if >= 10 successful projects;
    else return None (caller uses EVIDENCE_GATE_THRESHOLDS).
    """
    import sys
    sys.path.insert(0, str(ROOT))
    try:
        from lib.memory import Memory
        mem = Memory()
        outcomes = mem.get_successful_outcomes(min_critic=0.75, limit=200)
        mem.close()
    except Exception:
        return None
    if len(outcomes) < 10:
        return None
    findings = []
    sources = []
    verified = []
    rate = []
    high_rel = []
    for o in outcomes:
        m = {}
        try:
            m = json.loads(o.get("gate_metrics_json") or "{}")
        except Exception:
            pass
        if m.get("findings_count") is not None:
            findings.append(m["findings_count"])
        if m.get("unique_source_count") is not None:
            sources.append(m["unique_source_count"])
        if m.get("verified_claim_count") is not None:
            verified.append(m["verified_claim_count"])
        if m.get("claim_support_rate") is not None:
            rate.append(m["claim_support_rate"])
        if m.get("high_reliability_source_ratio") is not None:
            high_rel.append(m["high_reliability_source_ratio"])
    def p25(arr):
        if not arr:
            return None
        arr = sorted(arr)
        i = max(0, int(len(arr) * 0.25) - 1)
        return arr[i]
    out = {}
    v = p25(findings)
    if v is not None:
        out["findings_count_min"] = max(FLOOR["findings_count_min"], int(v))
    v = p25(sources)
    if v is not None:
        out["unique_source_count_min"] = max(FLOOR["unique_source_count_min"], int(v))
    v = p25(verified)
    if v is not None:
        out["verified_claim_count_min"] = max(FLOOR["verified_claim_count_min"], int(v))
    v = p25(rate)
    if v is not None:
        out["claim_support_rate_min"] = max(FLOOR["claim_support_rate_min"], round(v, 2))
    v = p25(high_rel)
    if v is not None:
        out["high_reliability_source_ratio_min"] = max(FLOOR["high_reliability_source_ratio_min"], round(v, 2))
    if not out:
        return None
    # Fill missing keys with floor
    for k, f in FLOOR.items():
        if k not in out:
            out[k] = f
    return out
