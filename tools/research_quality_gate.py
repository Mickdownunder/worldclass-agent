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

# Evidence Gate thresholds (single source of truth, configurable via this dict)
EVIDENCE_GATE_THRESHOLDS = {
    "findings_count_min": 8,
    "unique_source_count_min": 5,
    "verified_claim_count_min": 2,
    "claim_support_rate_min": 0.6,
    "high_reliability_source_ratio_min": 0.5,
}


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
    reasons = []

    # Read stats from explore (for root-cause: reader vs evidence gap)
    explore_stats = {}
    if (proj / "explore" / "read_stats.json").exists():
        try:
            explore_stats = json.loads((proj / "explore" / "read_stats.json").read_text())
            metrics["read_attempts"] = explore_stats.get("read_attempts", 0)
            metrics["read_successes"] = explore_stats.get("read_successes", 0)
            metrics["read_failures"] = explore_stats.get("read_failures", 0)
        except Exception:
            pass

    # Adaptive findings threshold: lower floor if read failure rate is high
    effective_findings_min = EVIDENCE_GATE_THRESHOLDS["findings_count_min"]
    read_attempts = metrics.get("read_attempts", 0)
    read_successes = metrics.get("read_successes", 0)
    if read_attempts > 0:
        success_rate = read_successes / read_attempts
        if success_rate < 0.5:
            effective_findings_min = max(3, int(EVIDENCE_GATE_THRESHOLDS["findings_count_min"] * success_rate * 1.5))

    # findings_count
    if findings_dir.exists():
        metrics["findings_count"] = len(list(findings_dir.glob("*.json")))
    if metrics["findings_count"] < effective_findings_min:
        reasons.append(f"findings_count {metrics['findings_count']} < {effective_findings_min}")

    # unique_source_count (by URL domain or URL)
    urls = set()
    if sources_dir.exists():
        for f in sources_dir.glob("*.json"):
            if f.name.endswith("_content.json"):
                continue
            try:
                d = json.loads(f.read_text())
                u = (d.get("url") or "").strip()
                if u:
                    urls.add(u)
            except Exception:
                pass
    metrics["unique_source_count"] = len(urls)
    if metrics["unique_source_count"] < EVIDENCE_GATE_THRESHOLDS["unique_source_count_min"]:
        reasons.append(f"unique_source_count {metrics['unique_source_count']} < {EVIDENCE_GATE_THRESHOLDS['unique_source_count_min']}")
    # Root-cause: zero findings with sources present and 0 read_successes => reader pipeline failure
    if (
        metrics["findings_count"] == 0
        and metrics["unique_source_count"] >= 1
        and metrics.get("read_successes", -1) == 0
        and metrics.get("read_attempts", 0) > 0
    ):
        reasons.append("zero_extractable_sources")
        reasons.append("read_failures_high")

    # verified_claim_count, claim_support_rate from claim_verification / claim_ledger
    claims_data = []
    if (verify_dir / "claim_verification.json").exists():
        try:
            claims_data = json.loads((verify_dir / "claim_verification.json").read_text()).get("claims", [])
        except Exception:
            pass
    if (verify_dir / "claim_ledger.json").exists():
        try:
            ledger = json.loads((verify_dir / "claim_ledger.json").read_text())
            claims_data = ledger.get("claims", claims_data)
        except Exception:
            pass
    # Ledger provides is_verified; claim_verification provides verified. Both supported for backward compat; Ledger preferred.
    verified_count = sum(1 for c in claims_data if c.get("is_verified") or c.get("verified"))
    metrics["verified_claim_count"] = verified_count
    if claims_data:
        metrics["claim_support_rate"] = round(verified_count / len(claims_data), 3)
    if metrics["verified_claim_count"] < EVIDENCE_GATE_THRESHOLDS["verified_claim_count_min"]:
        reasons.append(f"verified_claim_count {metrics['verified_claim_count']} < {EVIDENCE_GATE_THRESHOLDS['verified_claim_count_min']}")
    if claims_data and metrics["claim_support_rate"] < EVIDENCE_GATE_THRESHOLDS["claim_support_rate_min"]:
        reasons.append(f"claim_support_rate {metrics['claim_support_rate']} < {EVIDENCE_GATE_THRESHOLDS['claim_support_rate_min']}")

    # high_reliability_source_ratio from source_reliability
    high_rel_count = 0
    total_sources = 0
    if (verify_dir / "source_reliability.json").exists():
        try:
            rel = json.loads((verify_dir / "source_reliability.json").read_text())
            for s in rel.get("sources", []):
                total_sources += 1
                if (s.get("reliability_score") or 0) >= 0.6:
                    high_rel_count += 1
            if total_sources > 0:
                metrics["high_reliability_source_ratio"] = round(high_rel_count / total_sources, 3)
        except Exception:
            pass
    if total_sources > 0 and metrics["high_reliability_source_ratio"] < EVIDENCE_GATE_THRESHOLDS["high_reliability_source_ratio_min"]:
        reasons.append(f"high_reliability_source_ratio {metrics['high_reliability_source_ratio']} < {EVIDENCE_GATE_THRESHOLDS['high_reliability_source_ratio_min']}")

    # Determine pass and fail_code
    pass_gate = len(reasons) == 0
    if pass_gate:
        audit_log(proj, "evidence_gate", {
            "decision": "pass",
            "fail_code": None,
            "metrics": metrics,
            "reasons": reasons,
        })
        return {"pass": True, "fail_code": None, "metrics": metrics, "reasons": []}
    # Technical reader/dependency failure (0 extractable content despite sources)
    if (
        metrics["findings_count"] == 0
        and metrics["unique_source_count"] >= 1
        and metrics.get("read_successes", -1) == 0
        and metrics.get("read_attempts", 0) > 0
    ):
        fail_code = "failed_reader_pipeline"
    elif metrics["findings_count"] < effective_findings_min or metrics["unique_source_count"] < EVIDENCE_GATE_THRESHOLDS["unique_source_count_min"]:
        fail_code = "failed_insufficient_evidence"
    elif metrics["verified_claim_count"] < EVIDENCE_GATE_THRESHOLDS["verified_claim_count_min"] or metrics["claim_support_rate"] < EVIDENCE_GATE_THRESHOLDS["claim_support_rate_min"]:
        fail_code = "failed_verification_inconclusive"
    elif metrics["high_reliability_source_ratio"] < EVIDENCE_GATE_THRESHOLDS["high_reliability_source_ratio_min"]:
        fail_code = "failed_source_diversity"
    else:
        fail_code = "failed_insufficient_evidence"
    audit_log(proj, "evidence_gate", {
        "decision": "fail",
        "fail_code": fail_code,
        "metrics": metrics,
        "reasons": reasons,
    })
    return {"pass": False, "fail_code": fail_code, "metrics": metrics, "reasons": reasons}


def main():
    if len(sys.argv) < 2:
        print("Usage: research_quality_gate.py <project_id>", file=sys.stderr)
        sys.exit(2)
    result = run_evidence_gate(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
