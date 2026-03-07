"""
Research verification: source reliability, claim verification, fact_check, claim_ledger, CoVe.
Entry point: main(). Call via tools/research_verify.py which sets sys.path.
"""
import json
import sys
from pathlib import Path

from tools.research_common import project_dir, load_project
from tools.verify.evidence import source_reliability, fact_check
from tools.verify.claim_extraction import claim_verification, run_claim_verification_cove
from tools.verify.ledger import build_claim_ledger, apply_verified_tags_to_report


def _record_progress_error(project_id: str, e: BaseException) -> None:
    try:
        from tools.research_progress import error as progress_error
        name = type(e).__name__
        msg = str(e)
        if "Proxy" in name or "403" in msg:
            code = "proxy_forbidden"
        elif "Connection" in name or "APIConnection" in name:
            code = "openai_connection"
        elif "name resolution" in msg or "Errno -3" in msg or "NameResolutionError" in name:
            code = "openai_connection"
        else:
            code = "verify_error"
        progress_error(project_id, code, msg[:500])
    except Exception:
        pass


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_verify.py <project_id> <source_reliability|claim_verification|fact_check|claim_ledger>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    mode = sys.argv[2].lower()
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    try:
        from tools.research_tool_registry import ensure_tool_context
        ensure_tool_context("research_verify.py")
    except ImportError:
        pass
    project = load_project(proj_path)
    try:
        if mode == "source_reliability":
            result = source_reliability(proj_path, project, project_id=project_id)
        elif mode == "claim_verification":
            result = claim_verification(proj_path, project, project_id=project_id)
        elif mode == "fact_check":
            result = fact_check(proj_path, project, project_id=project_id)
        elif mode == "claim_ledger":
            result = build_claim_ledger(proj_path, project)
        elif mode == "claim_verification_cove":
            result = run_claim_verification_cove(proj_path, project, project_id=project_id)
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        _record_progress_error(project_id, e)
        raise
