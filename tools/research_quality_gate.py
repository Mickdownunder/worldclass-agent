#!/usr/bin/env python3
"""
Evidence Gate: hard check before synthesize. No report if gate fails.
Central policy; result stored in project.json (quality_gate.status, fail_code, metrics).

Standard fail codes: failed_insufficient_evidence | failed_verification_inconclusive | failed_quality_gate | failed_source_diversity | failed_reader_pipeline | failed_dependency_missing_bs4 | failed_reader_no_extractable_content

Usage:
  research_quality_gate.py <project_id>
  Output: JSON { "pass": bool, "fail_code": str|null, "metrics": {...}, "reasons": [...] }
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log

# Evidence Gate thresholds (single source of truth; overridden by calibrator when >= 10 outcomes)
EVIDENCE_GATE_THRESHOLDS = {
    "findings_count_min": 8,
    "unique_source_count_min": 5,
    "verified_claim_count_min": 2,
    "claim_support_rate_min": 0.5,
    "high_reliability_source_ratio_min": 0.5,
}


def _get_thresholds():
    """Return calibrated thresholds if >= 10 successful projects, else defaults."""
    try:
        from tools.research_calibrator import get_calibrated_thresholds
        cal = get_calibrated_thresholds()
        if cal:
            return {**EVIDENCE_GATE_THRESHOLDS, **cal}
    except Exception:
        pass
    return EVIDENCE_GATE_THRESHOLDS

# Adaptive gate: primary metric = absolute verified claim count
HARD_PASS_VERIFIED_MIN = 5   # >= 5 verified = always pass
SOFT_PASS_VERIFIED_MIN = 3   # >= 3 verified + rate >= 0.5 = pass
REVIEW_ZONE_RATE = 0.4       # rate >= 0.4 but verified < 5 = pending_review
HARD_FAIL_RATE = 0.3         # rate < 0.3 = hard fail


def _load_explore_stats(proj: Path) -> dict:
    """Load read_attempts, read_successes, read_failures from explore/read_stats.json."""
    out = {"read_attempts": 0, "read_successes": 0, "read_failures": 0}
    path = proj / "explore" / "read_stats.json"
    if not path.exists():
        return out
    try:
        data = json.loads(path.read_text())
        out["read_attempts"] = data.get("read_attempts", 0)
        out["read_successes"] = data.get("read_successes", 0)
        out["read_failures"] = data.get("read_failures", 0)
    except Exception:
        pass
    return out


def _effective_findings_min(metrics: dict) -> int:
    """Adaptive floor: lower if read success rate is low."""
    t = _get_thresholds()
    base = t["findings_count_min"]
    attempts = metrics.get("read_attempts", 0)
    successes = metrics.get("read_successes", 0)
    if attempts <= 0:
        return base
    rate = successes / attempts
    if rate < 0.5:
        return max(3, int(base * rate * 1.5))
    return base


def _metrics_findings(findings_dir: Path) -> int:
    """Count JSON files in findings dir (exclude _content)."""
    if not findings_dir.exists():
        return 0
    return len([f for f in findings_dir.glob("*.json") if "_content" not in f.name])


def _metrics_sources(sources_dir: Path) -> tuple[int, set]:
    """Count unique source URLs; return (count, url_set)."""
    urls = set()
    if not sources_dir.exists():
        return 0, urls
    for f in sources_dir.glob("*.json"):
        if f.name.endswith("_content.json"):
            continue
        try:
            u = (json.loads(f.read_text()).get("url") or "").strip()
            if u:
                urls.add(u)
        except Exception:
            pass
    return len(urls), urls


def _metrics_claims(verify_dir: Path) -> tuple[list, int, float]:
    """Load claims from claim_ledger/claim_verification; return (claims, verified_count, claim_support_rate)."""
    claims_data = []
    for name in ("claim_ledger.json", "claim_verification.json"):
        path = verify_dir / name
        if path.exists():
            try:
                data = json.loads(path.read_text())
                claims_data = data.get("claims", claims_data)
            except Exception:
                pass
    verified = sum(1 for c in claims_data if c.get("is_verified") or c.get("verified"))
    rate = round(verified / len(claims_data), 3) if claims_data else 0.0
    return claims_data, verified, rate


def _metrics_reliability(verify_dir: Path) -> tuple[float, bool]:
    """High-reliability source ratio from source_reliability.json. Returns (ratio, has_data)."""
    path = verify_dir / "source_reliability.json"
    if not path.exists() or path.stat().st_size == 0:
        return 0.0, False
    try:
        rel = json.loads(path.read_text())
        total = high = 0
        for s in rel.get("sources", []):
            total += 1
            if (s.get("reliability_score") or 0) >= 0.6:
                high += 1
        return (round(high / total, 3) if total > 0 else 0.0, total > 0)
    except Exception:
        return 0.0, False


def _is_reader_pipeline_failure(metrics: dict) -> bool:
    """True if we have sources but zero read success (reader failed)."""
    return (
        metrics.get("findings_count", 0) == 0
        and metrics.get("unique_source_count", 0) >= 1
        and metrics.get("read_successes", -1) == 0
        and metrics.get("read_attempts", 0) > 0
    )


def _collect_reasons(metrics: dict, effective_findings_min: int, has_reliability_data: bool = False) -> list[str]:
    """Build list of failure reasons from metrics vs thresholds."""
    reasons = []
    t = _get_thresholds()
    if metrics["findings_count"] < effective_findings_min:
        reasons.append(f"findings_count {metrics['findings_count']} < {effective_findings_min}")
    if metrics["unique_source_count"] < t["unique_source_count_min"]:
        reasons.append(f"unique_source_count {metrics['unique_source_count']} < {t['unique_source_count_min']}")
    if _is_reader_pipeline_failure(metrics):
        reasons.append("zero_extractable_sources")
        reasons.append("read_failures_high")
    if metrics["verified_claim_count"] < t["verified_claim_count_min"]:
        reasons.append(f"verified_claim_count {metrics['verified_claim_count']} < {t['verified_claim_count_min']}")
    if metrics.get("claim_support_rate", 0) < t["claim_support_rate_min"] and metrics.get("verified_claim_count", 0) > 0:
        reasons.append(f"claim_support_rate {metrics['claim_support_rate']} < {t['claim_support_rate_min']}")
    if has_reliability_data and metrics.get("high_reliability_source_ratio", 0) < t["high_reliability_source_ratio_min"]:
        reasons.append(f"high_reliability_source_ratio {metrics['high_reliability_source_ratio']} < {t['high_reliability_source_ratio_min']}")
    return reasons


def suggest_research_mode(question: str, domain: str = "") -> str:
    """Heuristic: 'discovery' | 'frontier' | 'standard' from question/domain."""
    q = (question or "").lower()
    d = (domain or "").lower()
    discovery_keywords = (
        "novel", "neue ideen", "zukunft", "future", "emerging", "discovery",
        "hypothese", "was waere wenn", "potential", "exploratory", "trends",
        "next generation", "paradigm", "vision", "roadmap",
    )
    frontier_keywords = (
        "bleeding edge", "state of the art", "stand der technik", "frontier",
        "neueste forschung", "academic", "papers", "architekturen", "arxiv",
        "conference", "study", "mechanism", "methodology", "hypothesis",
    )
    if any(k in q for k in discovery_keywords):
        return "discovery"
    if any(k in q for k in frontier_keywords):
        return "frontier"
    if d in ("academic", "science", "ai_research", "research"):
        return "frontier"
    return "standard"


def suggest_frontier_mode(question: str, domain: str = "") -> bool:
    """Deprecated: use suggest_research_mode() instead. True if frontier or discovery."""
    return suggest_research_mode(question, domain) in ("frontier", "discovery")


def _decide_gate(metrics: dict) -> tuple[str, str | None]:
    """Return (decision, fail_code). decision in pass | pending_review | fail."""
    vc = metrics["verified_claim_count"]
    rate = metrics["claim_support_rate"]
    if vc >= HARD_PASS_VERIFIED_MIN:
        return "pass", None
    if vc >= SOFT_PASS_VERIFIED_MIN and rate >= 0.5:
        return "pass", None
    if vc >= SOFT_PASS_VERIFIED_MIN and rate >= REVIEW_ZONE_RATE:
        return "pending_review", None
    t = _get_thresholds()
    if rate < HARD_FAIL_RATE or vc < SOFT_PASS_VERIFIED_MIN:
        if vc < t["verified_claim_count_min"] or rate < t["claim_support_rate_min"]:
            return "fail", "failed_verification_inconclusive"
        if metrics.get("high_reliability_source_ratio", 0) < t["high_reliability_source_ratio_min"]:
            return "fail", "failed_source_diversity"
        return "fail", "failed_insufficient_evidence"
    return "fail", "failed_insufficient_evidence"


def _decide_gate_frontier(metrics: dict, has_reliability_data: bool = True) -> tuple[str, str | None]:
    """Frontier research: source authority > cross-verification. Strong verified-claim count overrides missing reliability."""
    findings = metrics.get("findings_count", 0)
    sources = metrics.get("unique_source_count", 0)
    reliability = metrics.get("high_reliability_source_ratio", 0)
    verified = metrics.get("verified_claim_count", 0)

    if verified >= HARD_PASS_VERIFIED_MIN:
        return "pass", None
    reliability_ok = reliability >= 0.3 if has_reliability_data else True
    if findings >= 8 and sources >= 5 and reliability_ok:
        return "pass", None
    if findings >= 5 and sources >= 3:
        return "pending_review", None
    return "fail", "failed_insufficient_evidence"


def _decide_gate_discovery(metrics: dict) -> tuple[str, str | None]:
    """Discovery mode: idea diversity > verification. Pass with enough findings + sources (no verified_claim_count check)."""
    findings = metrics.get("findings_count", 0)
    sources = metrics.get("unique_source_count", 0)
    if findings >= 10 and sources >= 8:
        return "pass", None
    if findings >= 6 and sources >= 4:
        return "pass", None
    if findings >= 4:
        return "pending_review", None
    return "fail", "failed_insufficient_evidence"


def run_evidence_gate(project_id: str) -> dict:
    """Compute metrics and pass/fail. Does not modify project."""
    proj = project_dir(project_id)
    if not proj.exists():
        return {"pass": False, "fail_code": "failed_insufficient_evidence", "metrics": {}, "reasons": ["project not found"]}
    project = load_project(proj)
    verify_dir = proj / "verify"
    sources_dir = proj / "sources"
    findings_dir = proj / "findings"

    metrics = {
        "findings_count": 0,
        "unique_source_count": 0,
        "verified_claim_count": 0,
        "claim_support_rate": 0.0,
        "high_reliability_source_ratio": 0.0,
        "read_attempts": 0,
        "read_successes": 0,
        "read_failures": 0,
    }
    explore = _load_explore_stats(proj)
    metrics.update(explore)

    effective_findings_min = _effective_findings_min(metrics)
    metrics["findings_count"] = _metrics_findings(findings_dir)
    source_count, _ = _metrics_sources(sources_dir)
    metrics["unique_source_count"] = source_count

    claims_data, verified_count, claim_rate = _metrics_claims(verify_dir)
    metrics["verified_claim_count"] = verified_count
    metrics["claim_support_rate"] = claim_rate
    rel_ratio, has_reliability_data = _metrics_reliability(verify_dir)
    metrics["high_reliability_source_ratio"] = rel_ratio

    reasons = _collect_reasons(metrics, effective_findings_min, has_reliability_data)

    # Technical reader failure first
    if _is_reader_pipeline_failure(metrics):
        audit_log(proj, "evidence_gate", {"decision": "fail", "fail_code": "failed_reader_pipeline", "metrics": metrics, "reasons": reasons})
        return {"pass": False, "fail_code": "failed_reader_pipeline", "decision": "fail", "metrics": metrics, "reasons": reasons}

    # Insufficient findings/sources
    if metrics["findings_count"] < effective_findings_min or metrics["unique_source_count"] < EVIDENCE_GATE_THRESHOLDS["unique_source_count_min"]:
        audit_log(proj, "evidence_gate", {"decision": "fail", "fail_code": "failed_insufficient_evidence", "metrics": metrics, "reasons": reasons})
        return {"pass": False, "fail_code": "failed_insufficient_evidence", "decision": "fail", "metrics": metrics, "reasons": reasons}

    research_mode = "standard"
    config = project.get("config") or {}
    if isinstance(config, dict):
        research_mode = (config.get("research_mode") or "standard").strip().lower()
    if research_mode not in ("frontier", "discovery"):
        research_mode = "standard"

    if research_mode == "discovery":
        decision, fail_code = _decide_gate_discovery(metrics)
    elif research_mode == "frontier":
        decision, fail_code = _decide_gate_frontier(metrics, has_reliability_data)
    else:
        decision, fail_code = _decide_gate(metrics)
    if decision == "pass":
        audit_log(proj, "evidence_gate", {"decision": "pass", "fail_code": None, "metrics": metrics, "reasons": []})
        return {"pass": True, "fail_code": None, "decision": "pass", "metrics": metrics, "reasons": []}
    if decision == "pending_review":
        audit_log(proj, "evidence_gate", {"decision": "pending_review", "fail_code": None, "metrics": metrics, "reasons": reasons})
        return {"pass": False, "fail_code": None, "decision": "pending_review", "metrics": metrics, "reasons": reasons}
    if not fail_code:
        fail_code = "failed_insufficient_evidence"
    audit_log(proj, "evidence_gate", {"decision": "fail", "fail_code": fail_code, "metrics": metrics, "reasons": reasons})
    return {"pass": False, "fail_code": fail_code, "decision": "fail", "metrics": metrics, "reasons": reasons}


def main():
    if len(sys.argv) < 2:
        print("Usage: research_quality_gate.py <project_id>", file=sys.stderr)
        sys.exit(2)
    result = run_evidence_gate(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
