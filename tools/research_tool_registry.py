#!/usr/bin/env python3
"""
Tool registry and invocation contract for research tools.
Ensures tools are invoked with required env and argv so they run correctly.

Use:
  - ensure_tool_context("research_verify.py") at start of main() — exits with clear error if
    RESEARCH_STRICT_TOOL_CONTEXT=1 and env/argv don't match the contract.
  - validate_invocation(tool_name, env, argv) for programmatic checks (e.g. Plumber).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Contract per tool: required env vars, min number of args (after script name), project_id position (1-based in argv)
# argv[0] = script path, argv[1] = first arg. So project_id at index 1 => project_id_arg_index=1.
TOOL_CONTRACTS: dict[str, dict] = {
    "research_verify.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 3,  # script + project_id + subcommand
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Verify: source_reliability | claim_verification | fact_check | claim_ledger",
    },
    "research_synthesize.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Synthesize report for project_id",
    },
    "research_conductor.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 3,  # script + mode + project_id
        "project_id_arg_index": 2,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Conductor: shadow | run | run_cycle | gate + project_id",
    },
    "research_planner.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": 2,  # question, project_id
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Planner: question + project_id",
    },
    "research_quality_gate.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Evidence gate for project_id",
    },
    "research_parallel_reader.py": {
        "required_env": ["OPERATOR_ROOT", "RESEARCH_PROJECT_ID"],
        "min_argv": 4,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Parallel read: project_id phase [--input-file ...]",
    },
    "research_web_search.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 1,
        "project_id_arg_index": None,
        "description": "Web search: --queries-file ... [--max-per-query N]",
    },
    "research_deep_extract.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Deep extract for project_id",
    },
    "research_coverage.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Coverage for project_id",
    },
    "research_critic.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 4,  # project_id critique|revise artifacts_dir
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Critic: project_id critique|revise artifacts_dir",
    },
    "research_advance_phase.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": None,
        "description": "Advance phase: proj_dir next_phase",
    },
    "research_progress.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 3,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Progress: project_id start|step|done ...",
    },
    "research_budget.py": {
        "required_env": ["OPERATOR_ROOT"],
        "min_argv": 2,
        "project_id_arg_index": 1,
        "project_id_pattern": re.compile(r"^proj-[a-zA-Z0-9_-]+$"),
        "description": "Budget check for project_id",
    },
}


def validate_invocation(
    tool_name: str,
    env: dict[str, str] | None = None,
    argv: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """
    Validate that env and argv satisfy the tool's contract.
    Returns (ok, list of error messages).
    """
    errors: list[str] = []
    env = env if env is not None else dict(os.environ)
    argv = argv if argv is not None else list(sys.argv)

    contract = TOOL_CONTRACTS.get(tool_name)
    if not contract:
        return True, []  # unknown tool: no contract, skip validation

    for key in contract.get("required_env", []):
        if not (env.get(key) or "").strip():
            errors.append(f"Missing required env: {key}")

    min_argv = contract.get("min_argv", 0)
    if len(argv) < min_argv:
        errors.append(
            f"Too few arguments: got {len(argv)}, need at least {min_argv} (incl. script). "
            f"Usage: {contract.get('description', 'see docstring')}"
        )

    idx = contract.get("project_id_arg_index")
    pattern = contract.get("project_id_pattern")
    if idx is not None and pattern is not None and len(argv) > idx:
        val = (argv[idx] or "").strip()
        if not pattern.match(val):
            errors.append(
                f"argv[{idx}] must be a project_id (proj-...), got: {val[:50]!r}"
            )

    return (len(errors) == 0, errors)


def ensure_tool_context(tool_name: str) -> None:
    """
    Call at the start of a tool's main(). If RESEARCH_STRICT_TOOL_CONTEXT=1 and
    the current env/argv do not satisfy the tool's contract, print errors and exit(1).
    Otherwise, if validation fails, log a warning but continue (so existing callers
    don't break until strict mode is enabled).
    """
    ok, errors = validate_invocation(tool_name)
    if ok:
        return
    strict = (os.environ.get("RESEARCH_STRICT_TOOL_CONTEXT") or "").strip() == "1"
    msg = f"[{tool_name}] Contract violation: " + "; ".join(errors)
    if strict:
        print(msg, file=sys.stderr)
        sys.exit(1)
    # Non-strict: warn but continue (allow gradual rollout)
    print(f"Warning: {msg}", file=sys.stderr)


def list_registered_tools() -> list[str]:
    """Return sorted list of tool script names that have a contract."""
    return sorted(TOOL_CONTRACTS.keys())


def main() -> None:
    """CLI: validate a tool invocation. Usage: research_tool_registry.py validate <tool_name> [arg1 [arg2 ...]]"""
    if len(sys.argv) < 3 or sys.argv[1].lower() != "validate":
        print("Usage: research_tool_registry.py validate <tool_name> [arg1 [arg2 ...]]", file=sys.stderr)
        print("  Example: research_tool_registry.py validate research_verify.py proj-123 source_reliability", file=sys.stderr)
        sys.exit(2)
    tool_name = sys.argv[2]
    argv = [tool_name] + (sys.argv[3:] if len(sys.argv) > 3 else [])
    ok, errors = validate_invocation(tool_name, env=dict(os.environ), argv=argv)
    if ok:
        print("OK: contract satisfied")
        sys.exit(0)
    for e in errors:
        print(e, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
