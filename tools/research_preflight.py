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


def main():
    result = run_preflight()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
