"""
Research planner: LLM-driven plan, gap-fill, refinement, perspective-rotate.
Entry point: main(). Call via tools/research_planner.py which sets sys.path.
"""
import json
import sys
from pathlib import Path

from tools.planner.plan import build_plan, load_project_plan
from tools.planner.gap_fill import build_gap_fill_queries, build_refinement_plan
from tools.planner.perspective import build_perspective_rotate_queries
from tools.planner.fallback import fallback_plan
from tools.planner import memory as planner_memory


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: research_planner.py <question> [project_id] | --fallback-only <question> [project_id] | --gap-fill <coverage_json> <project_id> | ...",
            file=sys.stderr,
        )
        sys.exit(2)

    if sys.argv[1] == "--fallback-only":
        if len(sys.argv) < 3:
            print("Usage: research_planner.py --fallback-only <question> [project_id]", file=sys.stderr)
            sys.exit(2)
        question = sys.argv[2]
        project_id = sys.argv[3] if len(sys.argv) > 3 else ""
        plan = fallback_plan(question)
        try:
            strategy_ctx = planner_memory.load_strategy_context(question, project_id)
            plan = planner_memory.apply_strategy_to_plan(plan, strategy_ctx)
            planner_memory.persist_strategy_context(project_id, strategy_ctx)
        except Exception:
            pass
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return

    if sys.argv[1] == "--gap-fill":
        if len(sys.argv) < 4:
            sys.exit(2)
        result = build_gap_fill_queries(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if sys.argv[1] == "--refinement-queries":
        if len(sys.argv) < 4:
            sys.exit(2)
        result = build_refinement_plan(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if sys.argv[1] == "--perspective-rotate":
        if len(sys.argv) < 4:
            sys.exit(2)
        result = build_perspective_rotate_queries(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    question = sys.argv[1]
    project_id = sys.argv[2] if len(sys.argv) > 2 else ""
    result = build_plan(question, project_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
