#!/usr/bin/env python3
"""
Research verification: source reliability, claim verification, fact-check.
Used in the Verify phase of the research cycle.

Usage:
  research_verify.py <project_id> source_reliability
  research_verify.py <project_id> claim_verification
  research_verify.py <project_id> fact_check
  research_verify.py <project_id> claim_ledger
  research_verify.py <project_id> claim_verification_cove  # CoVe (RESEARCH_ENABLE_COVE_VERIFICATION=1)

Implementation lives in tools.verify package; this module is the entry point and API facade.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.verify import main
from tools.verify.evidence import source_reliability, fact_check
from tools.verify.claim_extraction import claim_verification, run_claim_verification_cove
from tools.verify.ledger import build_claim_ledger, apply_verified_tags_to_report

if __name__ == "__main__":
    main()
