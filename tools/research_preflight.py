#!/usr/bin/env python3
"""
Preflight check for research runs: required Python modules (e.g. bs4 for web reader).
Fails fast with clear fail_code and reason; no silent continue when reader stack is broken.

Usage:
  research_preflight.py
  Output: JSON { "ok": bool, "fail_code": str|null, "missing": [...], "message": str }
  Exit: 0 if ok, 1 if required missing.
"""
import json
import sys
from pathlib import Path

# Required for web reader (research_web_reader.py)
REQUIRED_MODULES = ["bs4"]
# Optional; if missing, reader falls back to bs4-only
OPTIONAL_MODULES = ["readability", "pypdf"]


def check_import(module: str) -> tuple[bool, str | None]:
    """Return (success, error_message)."""
    try:
        if module == "bs4":
            __import__("bs4")
        elif module == "readability":
            __import__("readability")
        elif module == "pypdf":
            __import__("pypdf")
        else:
            __import__(module)
        return True, None
    except ImportError as e:
        return False, str(e)


def run_preflight() -> dict:
    missing_required = []
    missing_optional = []
    for mod in REQUIRED_MODULES:
        ok, err = check_import(mod)
        if not ok:
            missing_required.append(mod)
    for mod in OPTIONAL_MODULES:
        ok, _ = check_import(mod)
        if not ok:
            missing_optional.append(mod)

    if missing_required:
        fail_code = "failed_dependency_missing_bs4" if "bs4" in missing_required else "failed_dependency_missing_modules"
        message = f"Required module(s) missing: {', '.join(missing_required)}. Install e.g. pip install beautifulsoup4"
        return {
            "ok": False,
            "fail_code": fail_code,
            "missing": missing_required,
            "missing_optional": missing_optional,
            "message": message,
        }
    return {
        "ok": True,
        "fail_code": None,
        "missing": [],
        "missing_optional": missing_optional,
        "message": "Preflight OK",
    }


def apply_preflight_fail_to_project(proj_dir: Path, art_dir: Path) -> None:
    """
    Read preflight stdout/stderr from art dir, parse or build informative failure,
    and write status + quality_gate.reasons to project.json.
    Matches research-cycle.sh PREFLIGHT_FAIL block; used for consistent fail handling and tests.
    """
    from datetime import datetime, timezone

    proj_dir = Path(proj_dir)
    art_dir = Path(art_dir)
    stdout_path = art_dir / "preflight_stdout.txt"
    stderr_path = art_dir / "preflight_stderr.txt"
    preflight_str = stdout_path.read_text().strip() if stdout_path.exists() else ""
    stderr_content = stderr_path.read_text().strip()[:500] if stderr_path.exists() else ""
    parse_msg = None
    try:
        preflight = json.loads(preflight_str) if preflight_str else {}
    except Exception as parse_err:
        preflight = {}
        stderr_suffix = f" stderr: {stderr_content}" if stderr_content else ""
        parse_msg = (
            f"Preflight parse failed: {str(parse_err)[:200]}; raw (first 200 chars): {repr(preflight_str[:200])}{stderr_suffix}"
        )
    if not preflight or preflight.get("fail_code") is None:
        preflight = {
            "fail_code": "failed_dependency_preflight_error",
            "message": parse_msg or "Preflight parse failed",
        }
    reasons = [preflight.get("message", "Dependency preflight failed")]
    if stderr_content and stderr_content not in str(reasons):
        reasons.append("preflight_stderr: " + stderr_content[:300])
    d = json.loads((proj_dir / "project.json").read_text())
    d["status"] = preflight.get("fail_code") or "failed_dependency_preflight_error"
    d.setdefault("quality_gate", {})["evidence_gate"] = {
        "status": "failed",
        "fail_code": preflight.get("fail_code"),
        "reasons": reasons,
        "metrics": {},
    }
    d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (proj_dir / "project.json").write_text(json.dumps(d, indent=2))


def main():
    try:
        result = run_preflight()
        out = json.dumps(result, indent=2)
        print(out, flush=True)
        sys.exit(0 if result["ok"] else 1)
    except Exception as e:
        err_payload = {
            "ok": False,
            "fail_code": "failed_dependency_preflight_error",
            "missing": [],
            "message": f"Preflight error: {str(e)[:500]}",
        }
        print(json.dumps(err_payload), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
