#!/usr/bin/env python3
"""
Update source_credibility table from a project's verify phase outcomes.
Aggregates per source domain: times_used, verified_count, failed_verification_count.
Usage: research_source_credibility.py <project_id>
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_source_credibility.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1].strip()
    proj_dir = ROOT / "research" / project_id
    if not proj_dir.is_dir():
        print(f"Project dir not found: {proj_dir}", file=sys.stderr)
        sys.exit(1)
    verify_dir = proj_dir / "verify"
    sources_dir = proj_dir / "sources"
    if not sources_dir.is_dir():
        sys.exit(0)
    ledger_path = verify_dir / "claim_ledger.json"
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text())
        except Exception:
            ledger = {}
    else:
        ledger = {}
    claims = ledger.get("claims", [])
    domain_stats: dict[str, dict] = defaultdict(lambda: {"used": 0, "verified": 0, "failed": 0})
    for sf in sources_dir.glob("*.json"):
        if "_content" in sf.name:
            continue
        try:
            src = json.loads(sf.read_text())
        except Exception:
            continue
        url = src.get("url", "")
        domain = urlparse(url).netloc if url else ""
        if not domain:
            continue
        domain_stats[domain]["used"] += 1
        source_id = sf.stem
        claims_from_source = [c for c in claims if source_id in (c.get("supporting_sources") or [])]
        for c in claims_from_source:
            if c.get("is_verified"):
                domain_stats[domain]["verified"] += 1
            else:
                domain_stats[domain]["failed"] += 1
    try:
        from lib.memory import Memory
        mem = Memory()
        for domain, stats in domain_stats.items():
            mem.update_source_credibility(
                domain,
                times_used=stats["used"],
                verified_count=stats["verified"],
                failed_verification_count=stats["failed"],
            )
        mem.close()
    except Exception as e:
        print(f"Source credibility update failed (non-fatal): {e}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
