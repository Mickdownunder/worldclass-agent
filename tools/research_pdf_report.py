#!/usr/bin/env python3
"""
Generate an AEM-native Intelligence Artifact PDF from research data.

Not a research report — a structured map of knowledge, uncertainty, and action.
Structure:
  Cover  → Outcome Layer → Claim State Map → Belief Trajectory
  → Evidence Landscape → Disagreement Layer → Insight Layer
  → Action Layer → Full Report (Auditor Mode) → References

Usage:  python3 research_pdf_report.py <project_id>

Implementation lives in tools.pdf_report package; this module is the entry point.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.pdf_report import main

if __name__ == "__main__":
    sys.exit(main())
