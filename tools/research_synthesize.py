#!/usr/bin/env python3
"""
Multi-pass section-by-section synthesis for research-firm-grade reports (5K–15K words).
Replaces single-call synthesis: topic clustering, full source content, playbook-driven structure.

Usage:
  research_synthesize.py <project_id>
  Writes full markdown to stdout. Pipeline captures to ART/report.md and runs post-processing.

Implementation lives in tools.synthesis package; this module is the entry point and API facade.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.synthesis import (
    run_synthesis,
    main,
    validate_synthesis_contract,
    SynthesisContractError,
    normalize_to_strings,
    extract_claim_refs_from_report,
    _build_provenance_appendix,
    _build_claim_source_registry,
    _build_valid_claim_ref_set,
)

if __name__ == "__main__":
    main()
