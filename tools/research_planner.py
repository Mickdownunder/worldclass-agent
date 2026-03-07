#!/usr/bin/env python3
"""
Create an LLM-driven research plan and adaptive follow-up query batches.

Modes:
- default: plan from QUESTION (+ optional PROJECT_ID)
- --gap-fill <coverage_json> <PROJECT_ID>
- --perspective-rotate <thin_topics_json_or_csv> <PROJECT_ID>

Implementation lives in tools.planner package; this module is the entry point and API facade.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.research_common import research_root  # re-export for tests that patch planner.research_root
from tools.planner import main
from tools.planner.plan import build_plan, load_project_plan
from tools.planner.gap_fill import build_gap_fill_queries, build_refinement_plan
from tools.planner.perspective import build_perspective_rotate_queries
from tools.planner import memory as _planner_memory

# Re-export for CLI and programmatic use
_apply_strategy_to_plan = _planner_memory.apply_strategy_to_plan
_load_strategy_context = _planner_memory.load_strategy_context
_persist_strategy_context = _planner_memory.persist_strategy_context

if __name__ == "__main__":
    main()
    sys.exit(0)
