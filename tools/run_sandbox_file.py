#!/usr/bin/env python3
"""
Run a Python file in the research sandbox (Docker: no network, numpy/scipy, timeout).
Used by ATLAS to execute thesis-validation code safely.

Usage: run_sandbox_file.py <path_to_script.py> [timeout_seconds]
Output: JSON to stdout with keys: exit_code, timeout, stdout, stderr, success.
"""

import json
import sys
from pathlib import Path

# Allow import when run from operator bin with PYTHONPATH set
try:
    from tools.research_sandbox import run_in_sandbox
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.research_sandbox import run_in_sandbox


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: run_sandbox_file.py <path_to_script.py> [timeout_seconds]"}), file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    if not path.is_file():
        out = {"error": f"file not found: {path}", "exit_code": 1, "success": False}
        print(json.dumps(out))
        sys.exit(1)
    code = path.read_text(encoding="utf-8", errors="replace")
    result = run_in_sandbox(code, timeout_seconds=timeout)
    out = {
        "exit_code": result.exit_code,
        "timeout": result.timeout,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.exit_code == 0 and not result.timeout,
    }
    print(json.dumps(out))
    sys.exit(0 if out["success"] else 1)


if __name__ == "__main__":
    main()
