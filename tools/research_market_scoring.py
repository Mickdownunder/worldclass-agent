#!/usr/bin/env python3
"""
AEM: Settlement by claim outcome type. Writes market/settlements.jsonl.
Each line: claim_ref (claim_id@version), decision (PASS_STABLE|PASS_TENTATIVE|FAIL),
settlement_confidence, oracle_integrity_pass, contradiction_review_required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl

MARKET_DIR = "market"
SETTLEMENTS_FILENAME = "settlements.jsonl"
ORACLE_INTEGRITY_RATE_THRESHOLD = 0.80  # v1 default


def _claim_ref(c: dict) -> str:
    return f"{c.get('claim_id', '')}@{c.get('claim_version', 1)}"


def run_market_scoring(project_id: str) -> list[dict]:
    """Read ledger (falsification_status), write settlements.jsonl. Returns settlements written."""
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    (proj_path / MARKET_DIR).mkdir(parents=True, exist_ok=True)
    path = proj_path / MARKET_DIR / SETTLEMENTS_FILENAME
    existing = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                try:
                    existing.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    seen_refs = {s.get("claim_ref") for s in existing}
    new_settlements = []
    for c in claims:
        ref = _claim_ref(c)
        if ref in seen_refs:
            continue
        decision = (c.get("falsification_status") or "FAIL").strip()
        if decision not in ("PASS_STABLE", "PASS_TENTATIVE", "FAIL"):
            decision = "FAIL"
        contradiction_review_required = bool(c.get("contradicts"))
        # Enforce: no PASS_STABLE when contradiction_review_required (spec: require review before stable)
        if contradiction_review_required and decision == "PASS_STABLE":
            decision = "PASS_TENTATIVE"
        settlement_confidence = float(c.get("settlement_confidence", 0.5))
        oracle_integrity_pass = settlement_confidence >= 0.5 and (decision != "PASS_STABLE" or settlement_confidence >= ORACLE_INTEGRITY_RATE_THRESHOLD)
        rec = {
            "claim_ref": ref,
            "decision": decision,
            "settlement_confidence": round(settlement_confidence, 4),
            "oracle_integrity_pass": oracle_integrity_pass,
            "contradiction_review_required": contradiction_review_required,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        new_settlements.append(rec)
        existing.append(rec)
    lines = [json.dumps(s, ensure_ascii=False) for s in existing]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    audit_log(proj_path, "aem_market_scoring_run", {"settlements_added": len(new_settlements)})
    return new_settlements


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_market_scoring.py run <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "run":
        out = run_market_scoring(project_id)
        print(json.dumps({"ok": True, "settlements_count": len(out)}))
    else:
        print("Unknown command: use run", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
