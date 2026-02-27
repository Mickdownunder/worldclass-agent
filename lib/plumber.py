"""
Plumber — Self-Healing Subsystem for the Operator Brain.

Full system doctor with 7 diagnostic categories:
  1. Shell-script syntax errors (bash -n + targeted patching)
  2. Repeated job failures (log analysis → root-cause → fix)
  3. Python compile + import checks for all tools
  4. Dependency consistency (installed packages vs actual imports)
  5. Dead tool detection (tools not referenced by any workflow)
  6. Workflow tool-reference integrity (scripts referencing missing tools)
  7. Process health (stuck brain cycles/reflects, zombie processes)

Learning & resilience features:
  - Error fingerprinting: persistent hashes per error pattern → tracks
    occurrences, fix attempts, success rates, per-category breakdowns.
  - Fix cooldown: after MAX_FIX_ATTEMPTS_PER_FINGERPRINT failed fixes for the
    same fingerprint, waits COOLDOWN_HOURS before retrying (prevents thrashing).
  - Non-repairable classification: external API outages, OOM, disk full,
    permission denied, TLS errors, etc. are detected and excluded from fixes.
  - Patch-impact metrics: tracks LOC changed, files affected, revert count,
    success rate per category for maintenance quality visibility.

Safety model:
  - Only touches files under workflows/ and tools/ (never lib/, ui/, conf/)
  - Every fix is stored as a patch in plumber/patches/ for audit + rollback
  - Governance level gates execution:
      Level ≤1  → diagnose only, no writes
      Level  2  → diagnose + dry-run (patch created but not applied)
      Level  3  → diagnose + apply fix + verify
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path.home() / "operator"
WORKFLOWS = BASE / "workflows"
TOOLS = BASE / "tools"
JOBS = BASE / "jobs"
LIB = BASE / "lib"
BIN = BASE / "bin"
UI_SRC = BASE / "ui" / "src"
PLUMBER_DIR = BASE / "plumber"
PATCHES_DIR = PLUMBER_DIR / "patches"
VENV = BASE / ".venv"

ALLOWED_FIX_ROOTS = [WORKFLOWS, TOOLS]

MAX_LOG_LINES = 200
MAX_PATCH_SIZE = 5000

# Severity levels for diagnostics
CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

# Fingerprint DB + Cooldown
FINGERPRINT_DB = PLUMBER_DIR / "fingerprints.json"
COOLDOWN_HOURS = 6
MAX_FIX_ATTEMPTS_PER_FINGERPRINT = 3

# Non-repairable patterns — Plumber should never try to fix these
NON_REPAIRABLE_PATTERNS = [
    (re.compile(r"HTTP\s*(Error\s*)?429", re.I), "rate_limit",
     "External API rate limit — wait or increase quota"),
    (re.compile(r"HTTP\s*(Error\s*)?5\d\d", re.I), "external_api_error",
     "External API server error — not a code issue"),
    (re.compile(r"disk.*(full|space|quota)", re.I), "disk_full",
     "Disk full — free space or expand volume"),
    (re.compile(r"permission denied", re.I), "permission_denied",
     "Permission denied — fix file/directory permissions"),
    (re.compile(r"connection (refused|reset|timed out)", re.I), "connection_error",
     "Network connection failure — check connectivity"),
    (re.compile(r"ENOSPC|No space left", re.I), "disk_full",
     "No space left on device"),
    (re.compile(r"out of memory|OOM|MemoryError", re.I), "oom",
     "Out of memory — increase limits or reduce load"),
    (re.compile(r"certificate.*(expired|invalid|verify)", re.I), "tls_error",
     "TLS/certificate error — renew or trust certificate"),
    (re.compile(r"SIGKILL|killed", re.I), "process_killed",
     "Process killed by OS (likely OOM or timeout)"),
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Fingerprint system — persistent error tracking + cooldown + learning
# ---------------------------------------------------------------------------


def _error_fingerprint(workflow: str, error_text: str) -> str:
    """Generate a stable hash for an error pattern."""
    import hashlib
    # Normalize: strip timestamps, PIDs, paths that change per run
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "TS", error_text)
    normalized = re.sub(r"/root/operator/jobs/\S+", "JOB_DIR", normalized)
    normalized = re.sub(r"pid[=: ]*\d+", "PID", normalized)
    normalized = re.sub(r"\b\d{6,}\b", "ID", normalized)
    key = f"{workflow}::{normalized[:500]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _load_fingerprints() -> dict:
    """Load the persistent fingerprint database."""
    if FINGERPRINT_DB.exists():
        try:
            return json.loads(FINGERPRINT_DB.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_fingerprints(db: dict) -> None:
    """Save the fingerprint database."""
    PLUMBER_DIR.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_DB.write_text(json.dumps(db, indent=2, default=str))


def record_fingerprint(
    workflow: str, error_text: str, fix_attempted: bool,
    fix_succeeded: bool, action: str, category: str = "",
) -> str:
    """Record an error occurrence and fix attempt in the fingerprint DB.

    Returns the fingerprint hash.
    """
    fp = _error_fingerprint(workflow, error_text)
    db = _load_fingerprints()
    entry = db.get(fp, {
        "fingerprint": fp,
        "workflow": workflow,
        "error_snippet": error_text[:300],
        "category": category,
        "first_seen": _utcnow(),
        "occurrences": 0,
        "fix_attempts": 0,
        "fix_successes": 0,
        "last_seen": "",
        "last_action": "",
        "non_repairable": False,
        "cooldown_until": "",
    })
    entry["occurrences"] += 1
    entry["last_seen"] = _utcnow()
    entry["last_action"] = action
    if fix_attempted:
        entry["fix_attempts"] += 1
    if fix_succeeded:
        entry["fix_successes"] += 1
    db[fp] = entry
    _save_fingerprints(db)
    return fp


def is_on_cooldown(workflow: str, error_text: str) -> tuple[bool, dict | None]:
    """Check if an error fingerprint is on cooldown (too many recent fix attempts)."""
    fp = _error_fingerprint(workflow, error_text)
    db = _load_fingerprints()
    entry = db.get(fp)
    if not entry:
        return False, None

    # Already classified as non-repairable
    if entry.get("non_repairable"):
        return True, entry

    # Check cooldown
    cooldown_until = entry.get("cooldown_until", "")
    if cooldown_until and cooldown_until > _utcnow():
        return True, entry

    # Too many failed fix attempts
    attempts = entry.get("fix_attempts", 0)
    successes = entry.get("fix_successes", 0)
    if attempts >= MAX_FIX_ATTEMPTS_PER_FINGERPRINT and successes == 0:
        # Set cooldown
        from datetime import timedelta
        cooldown_end = datetime.now(timezone.utc) + timedelta(hours=COOLDOWN_HOURS)
        entry["cooldown_until"] = cooldown_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        db[fp] = entry
        _save_fingerprints(db)
        return True, entry

    return False, entry


def classify_non_repairable(error_text: str) -> tuple[str, str] | None:
    """Check if an error matches a known non-repairable pattern.

    Returns (reason_code, explanation) or None.
    """
    for pattern, code, explanation in NON_REPAIRABLE_PATTERNS:
        if pattern.search(error_text):
            return code, explanation
    return None


def mark_non_repairable(workflow: str, error_text: str, reason_code: str,
                        category: str = "repeated_failures") -> None:
    """Permanently mark a fingerprint as non-repairable."""
    fp = _error_fingerprint(workflow, error_text)
    db = _load_fingerprints()
    entry = db.get(fp, {
        "fingerprint": fp, "workflow": workflow,
        "error_snippet": error_text[:300], "first_seen": _utcnow(),
        "occurrences": 1, "fix_attempts": 0, "fix_successes": 0,
        "last_seen": _utcnow(), "last_action": "non_repairable",
        "non_repairable": False, "cooldown_until": "", "category": category,
    })
    entry["non_repairable"] = True
    entry["non_repairable_reason"] = reason_code
    entry["last_action"] = f"classified_non_repairable:{reason_code}"
    db[fp] = entry
    _save_fingerprints(db)


def get_fingerprint_stats() -> dict:
    """Get aggregate stats from the fingerprint DB for UI/metrics."""
    db = _load_fingerprints()
    total = len(db)
    non_repairable = sum(1 for e in db.values() if e.get("non_repairable"))
    on_cooldown = sum(1 for e in db.values()
                      if e.get("cooldown_until", "") > _utcnow())
    total_occurrences = sum(e.get("occurrences", 0) for e in db.values())
    total_attempts = sum(e.get("fix_attempts", 0) for e in db.values())
    total_successes = sum(e.get("fix_successes", 0) for e in db.values())
    success_rate = (total_successes / total_attempts * 100) if total_attempts > 0 else 0

    # Per-category stats
    by_category: dict[str, dict] = {}
    for e in db.values():
        cat = e.get("category") or "unknown"
        c = by_category.setdefault(cat, {"occurrences": 0, "attempts": 0, "successes": 0})
        c["occurrences"] += e.get("occurrences", 0)
        c["attempts"] += e.get("fix_attempts", 0)
        c["successes"] += e.get("fix_successes", 0)

    # Top recurring errors
    top_errors = sorted(db.values(), key=lambda e: e.get("occurrences", 0), reverse=True)[:5]

    return {
        "total_fingerprints": total,
        "non_repairable": non_repairable,
        "on_cooldown": on_cooldown,
        "total_occurrences": total_occurrences,
        "fix_attempts": total_attempts,
        "fix_successes": total_successes,
        "fix_success_rate_pct": round(success_rate, 1),
        "by_category": by_category,
        "top_recurring": [
            {"fingerprint": e["fingerprint"], "workflow": e.get("workflow", "?"),
             "occurrences": e.get("occurrences", 0), "snippet": e.get("error_snippet", "")[:100],
             "non_repairable": e.get("non_repairable", False)}
            for e in top_errors
        ],
    }


def _is_safe_path(path: Path) -> bool:
    """Only allow fixes to files under the safe roots."""
    rp = path.resolve()
    return any(rp.is_relative_to(root.resolve()) for root in ALLOWED_FIX_ROOTS)


def _save_patch(filename: str, original: str, fixed: str, meta: dict) -> Path:
    """Save a unified diff as a patch file for audit trail."""
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    patch_content = "".join(diff)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    patch_path = PATCHES_DIR / f"{ts}_{Path(filename).stem}.patch"
    patch_path.write_text(
        f"# Plumber patch — {_utcnow()}\n"
        f"# Reason: {meta.get('reason', 'unknown')}\n"
        f"# Diagnosis: {meta.get('diagnosis', '')[:200]}\n\n"
        + patch_content
    )
    meta_path = patch_path.with_suffix(".json")
    meta["patch_file"] = str(patch_path)
    meta["created_at"] = _utcnow()
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return patch_path


# ---------------------------------------------------------------------------
# Diagnosis routines
# ---------------------------------------------------------------------------


def diagnose_shell_syntax(script_path: Path) -> dict:
    """Run bash -n on a shell script and return errors."""
    result = subprocess.run(
        ["bash", "-n", str(script_path)],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return {"ok": True, "script": str(script_path)}
    errors = (result.stderr or "").strip()
    m = re.search(r"line (\d+):", errors)
    line_no = int(m.group(1)) if m else None
    return {
        "ok": False,
        "script": str(script_path),
        "errors": errors,
        "line": line_no,
    }


def diagnose_repeated_failures(limit: int = 15) -> list[dict]:
    """Scan recent jobs and find workflows with repeated failures."""
    failures: dict[str, list[dict]] = {}
    if not JOBS.exists():
        return []
    job_files = sorted(JOBS.glob("*/*/job.json"), reverse=True)[:limit * 3]
    for f in job_files:
        try:
            j = json.loads(f.read_text())
            if j.get("status") != "FAILED":
                continue
            wf = j.get("workflow_id", "unknown")
            failures.setdefault(wf, []).append({
                "job_id": j.get("id"),
                "error": (j.get("error") or "")[:200],
                "duration_s": j.get("duration_s"),
                "job_dir": str(f.parent),
            })
        except (json.JSONDecodeError, OSError):
            continue

    result = []
    for wf, fails in failures.items():
        if len(fails) >= 2:
            result.append({
                "workflow": wf,
                "fail_count": len(fails),
                "failures": fails[:5],
            })
    result.sort(key=lambda x: x["fail_count"], reverse=True)
    return result


def read_job_log(job_dir: str, tail: int = MAX_LOG_LINES) -> str:
    """Read the last N lines of a job's log."""
    log_path = Path(job_dir) / "log.txt"
    if not log_path.exists():
        return ""
    lines = log_path.read_text().splitlines()
    return "\n".join(lines[-tail:])


def _extract_error_from_logs(logs: list[str]) -> str:
    """Extract the most common/recent error pattern from job logs."""
    error_lines = []
    for log in logs:
        for line in log.splitlines():
            ll = line.lower()
            if any(kw in ll for kw in ["error", "traceback", "syntax error", "filenotfound", "modulenotfound", "exception"]):
                error_lines.append(line.strip())
    if not error_lines:
        return "unknown"
    c = Counter(error_lines)
    return c.most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Diagnostic: Python compile + import checks
# ---------------------------------------------------------------------------


def diagnose_python_tools() -> list[dict]:
    """Compile-check and import-check every Python tool."""
    issues = []
    if not TOOLS.exists():
        return issues
    python = str(VENV / "bin" / "python3") if (VENV / "bin" / "python3").exists() else "python3"

    for py_file in sorted(TOOLS.glob("*.py")):
        # Phase 1: py_compile (syntax check)
        try:
            r = subprocess.run(
                [python, "-m", "py_compile", str(py_file)],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                issues.append({
                    "file": str(py_file),
                    "check": "compile",
                    "severity": CRITICAL,
                    "error": (r.stderr or "").strip()[:300],
                })
                continue
        except Exception as e:
            issues.append({
                "file": str(py_file),
                "check": "compile",
                "severity": WARNING,
                "error": f"compile check failed: {e}",
            })
            continue

        # Phase 2: import check (catches missing dependencies at import time)
        module_name = py_file.stem
        try:
            r = subprocess.run(
                [python, "-c", f"import importlib; importlib.import_module('tools.{module_name}')"],
                capture_output=True, text=True, timeout=15,
                cwd=str(BASE),
                env={**os.environ, "PYTHONPATH": str(BASE)},
            )
            if r.returncode != 0:
                stderr = (r.stderr or "").strip()
                # Ignore harmless "no main" or usage errors — only flag real import failures
                if "ModuleNotFoundError" in stderr or "ImportError" in stderr or "SyntaxError" in stderr:
                    issues.append({
                        "file": str(py_file),
                        "check": "import",
                        "severity": CRITICAL if "ModuleNotFoundError" in stderr else WARNING,
                        "error": stderr[:300],
                    })
        except subprocess.TimeoutExpired:
            issues.append({
                "file": str(py_file),
                "check": "import",
                "severity": WARNING,
                "error": "import timed out (>15s) — possible side effect at import time",
            })
        except Exception:
            pass

    return issues


# ---------------------------------------------------------------------------
# Diagnostic: Dependency consistency
# ---------------------------------------------------------------------------


def diagnose_dependencies() -> list[dict]:
    """Check that imports used in tools match installed packages."""
    issues = []
    if not TOOLS.exists():
        return issues

    # Collect all top-level imports from tools/*.py
    imported_modules: set[str] = set()
    stdlib_modules = set(_get_stdlib_modules())

    for py_file in TOOLS.glob("*.py"):
        try:
            content = py_file.read_text()
        except OSError:
            continue
        for line in content.splitlines():
            line = line.strip()
            m = re.match(r'^(?:import|from)\s+([\w]+)', line)
            if m:
                mod = m.group(1)
                # Skip relative/local imports
                if mod not in ("tools", "lib", "__future__") and mod not in stdlib_modules:
                    imported_modules.add(mod)

    # Also check lib/*.py
    if LIB.exists():
        for py_file in LIB.glob("*.py"):
            try:
                content = py_file.read_text()
            except OSError:
                continue
            for line in content.splitlines():
                line = line.strip()
                m = re.match(r'^(?:import|from)\s+([\w]+)', line)
                if m:
                    mod = m.group(1)
                    if mod not in ("tools", "lib", "__future__") and mod not in stdlib_modules:
                        imported_modules.add(mod)

    # Check which are installed
    python = str(VENV / "bin" / "python3") if (VENV / "bin" / "python3").exists() else "python3"
    installed: set[str] = set()
    try:
        r = subprocess.run(
            [python, "-m", "pip", "freeze", "--local"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.splitlines():
            pkg = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower().replace("-", "_")
            if pkg:
                installed.add(pkg)
    except Exception:
        pass

    # Common PyPI name → import name mappings
    pkg_to_import = {
        "beautifulsoup4": "bs4", "pillow": "PIL", "google_genai": "google",
        "python_dateutil": "dateutil", "pyyaml": "yaml", "scikit_learn": "sklearn",
        "lxml_html_clean": "lxml_html_clean",
    }
    import_to_pkg = {v: k for k, v in pkg_to_import.items()}

    for mod in sorted(imported_modules):
        mod_lower = mod.lower().replace("-", "_")
        # Check direct match or via mapping
        found = (
            mod_lower in installed
            or mod_lower in {v.lower() for v in pkg_to_import.values()}
            or import_to_pkg.get(mod, "").lower() in installed
        )
        if not found:
            # Try actual import as final check
            try:
                r = subprocess.run(
                    [python, "-c", f"import {mod}"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode != 0 and "ModuleNotFoundError" in (r.stderr or ""):
                    # Resolve the pip package name
                    pip_name = import_to_pkg.get(mod, mod)
                    issues.append({
                        "module": mod,
                        "pip_name": pip_name,
                        "check": "dependency",
                        "severity": CRITICAL,
                        "error": f"Module '{mod}' imported in code but not installed",
                        "suggested_fix": f"pip install {pip_name}",
                    })
            except Exception:
                pass

    return issues


# Packages we trust enough to auto-install (prevents supply-chain attacks)
TRUSTED_PACKAGES = {
    "jsonschema", "tenacity", "openai", "requests", "beautifulsoup4",
    "bs4", "lxml", "weasyprint", "markdown", "pyyaml", "httpx",
    "google-genai", "pillow", "chardet", "cssselect", "cssselect2",
    "fonttools", "brotli", "pytest", "python-dateutil",
}


def fix_missing_dependency(module: str, pip_name: str, governance_level: int = 2) -> FixResult:
    """Install a missing Python package into the venv."""
    pip_lower = pip_name.lower().replace("-", "_")

    if pip_lower not in {p.lower().replace("-", "_") for p in TRUSTED_PACKAGES}:
        return FixResult(
            False,
            f"Module '{module}' (pip: {pip_name}) not in trusted package list",
            "blocked — untrusted package",
            details={"module": module, "pip_name": pip_name,
                     "hint": f"Add '{pip_name}' to TRUSTED_PACKAGES in plumber.py to allow auto-install"},
        )

    if governance_level < 3:
        return FixResult(
            False,
            f"Would install '{pip_name}' (governance {governance_level} < 3)",
            "dry_run — needs governance 3",
            details={"module": module, "pip_name": pip_name},
        )

    python = str(VENV / "bin" / "python3") if (VENV / "bin" / "python3").exists() else "python3"
    pip_cmd = [python, "-m", "pip", "install", pip_name]
    try:
        r = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            # Verify import works now
            verify = subprocess.run(
                [python, "-c", f"import {module}"],
                capture_output=True, text=True, timeout=10,
            )
            if verify.returncode == 0:
                return FixResult(
                    True,
                    f"Installed '{pip_name}' — import {module} OK",
                    "applied",
                    details={"module": module, "pip_name": pip_name, "verified": True},
                )
            else:
                return FixResult(
                    False,
                    f"Installed '{pip_name}' but import {module} still fails: {verify.stderr[:200]}",
                    "fix_failed_verification",
                    details={"module": module, "pip_name": pip_name},
                )
        else:
            return FixResult(
                False,
                f"pip install {pip_name} failed: {r.stderr[:200]}",
                "install_failed",
                details={"module": module, "pip_name": pip_name},
            )
    except Exception as e:
        return FixResult(
            False,
            f"pip install {pip_name} error: {e}",
            "install_error",
            details={"module": module, "pip_name": pip_name},
        )


def _get_stdlib_modules() -> list[str]:
    """Return a list of Python standard library module names."""
    return [
        "abc", "argparse", "ast", "asyncio", "base64", "bisect", "builtins",
        "calendar", "cgi", "cmd", "codecs", "collections", "colorsys",
        "concurrent", "configparser", "contextlib", "copy", "csv", "ctypes",
        "dataclasses", "datetime", "decimal", "difflib", "dis", "email",
        "enum", "errno", "faulthandler", "fileinput", "fnmatch", "fractions",
        "ftplib", "functools", "gc", "getpass", "gettext", "glob", "gzip",
        "hashlib", "heapq", "hmac", "html", "http", "imaplib", "importlib",
        "inspect", "io", "ipaddress", "itertools", "json", "keyword",
        "linecache", "locale", "logging", "lzma", "mailbox", "math",
        "mimetypes", "mmap", "multiprocessing", "numbers", "operator", "os",
        "pathlib", "pdb", "pickle", "platform", "plistlib", "poplib",
        "posixpath", "pprint", "profile", "pstats", "py_compile", "pydoc",
        "queue", "quopri", "random", "re", "readline", "reprlib", "resource",
        "runpy", "sched", "secrets", "select", "shelve", "shlex", "shutil",
        "signal", "site", "smtplib", "socket", "socketserver", "sqlite3",
        "ssl", "stat", "statistics", "string", "struct", "subprocess",
        "sys", "sysconfig", "syslog", "tarfile", "tempfile", "textwrap",
        "threading", "time", "timeit", "token", "tokenize", "tomllib",
        "trace", "traceback", "tracemalloc", "tty", "turtle", "types",
        "typing", "unicodedata", "unittest", "urllib", "uuid", "venv",
        "warnings", "wave", "weakref", "webbrowser", "xml", "xmlrpc",
        "zipfile", "zipimport", "zlib", "_thread",
    ]


# ---------------------------------------------------------------------------
# Diagnostic: Dead tools + missing tool references
# ---------------------------------------------------------------------------


def diagnose_tool_references() -> dict:
    """Check workflow scripts for tool references and find dead/missing tools."""
    referenced: set[str] = set()
    existing: set[str] = set()
    missing_refs: list[dict] = []
    dead_tools: list[str] = []

    # Collect all existing tools
    if TOOLS.exists():
        for f in TOOLS.glob("*.py"):
            existing.add(f.name)

    # Scan workflow scripts for tool references
    patterns = [
        re.compile(r'\$TOOLS/([\w_]+\.py)'),
        re.compile(r'\$OPERATOR_ROOT/tools/([\w_]+\.py)'),
        re.compile(r'tools/(research_[\w_]+\.py)'),
    ]

    workflow_dirs = [WORKFLOWS]
    # Also check subdirectories like workflows/research/phases/
    if (WORKFLOWS / "research" / "phases").exists():
        workflow_dirs.append(WORKFLOWS / "research" / "phases")

    for wf_dir in workflow_dirs:
        if not wf_dir.exists():
            continue
        for script in wf_dir.glob("*.sh"):
            try:
                content = script.read_text()
            except OSError:
                continue
            for pattern in patterns:
                for m in pattern.finditer(content):
                    tool_name = m.group(1)
                    referenced.add(tool_name)
                    if tool_name not in existing:
                        missing_refs.append({
                            "tool": tool_name,
                            "script": str(script),
                            "severity": CRITICAL,
                        })

    # Dead tools: exist but never referenced
    for tool in sorted(existing):
        if tool not in referenced and tool.startswith("research_"):
            dead_tools.append(tool)

    return {
        "referenced_count": len(referenced),
        "existing_count": len(existing),
        "missing_refs": missing_refs,
        "dead_tools": dead_tools,
    }


# ---------------------------------------------------------------------------
# Diagnostic: Process health
# ---------------------------------------------------------------------------


def diagnose_processes() -> dict:
    """Check for stuck brain processes and zombie workers."""
    result = {
        "brain_cycles": [],
        "brain_reflects": [],
        "stuck": False,
        "zombie_count": 0,
    }
    try:
        r = subprocess.run(
            ["ps", "-eo", "pid,etime,args"],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            if "bin/brain" not in line:
                continue
            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue
            pid, etime, cmd = parts
            secs = _parse_etime(etime)
            proc_type = "cycle" if "cycle" in cmd else "reflect" if "reflect" in cmd else "other"
            entry = {"pid": int(pid), "elapsed_s": secs, "type": proc_type, "cmd": cmd[:100]}

            if proc_type == "cycle":
                result["brain_cycles"].append(entry)
                if secs > 600:
                    result["stuck"] = True
                    entry["stuck"] = True
            elif proc_type == "reflect":
                result["brain_reflects"].append(entry)
                if secs > 300:
                    result["stuck"] = True
                    entry["stuck"] = True
    except Exception:
        pass

    # Check for zombie processes
    try:
        r = subprocess.run(
            ["ps", "-eo", "stat"],
            capture_output=True, text=True, timeout=5,
        )
        result["zombie_count"] = sum(1 for line in r.stdout.splitlines() if line.strip().startswith("Z"))
    except Exception:
        pass

    return result


def _parse_etime(etime_str: str) -> int:
    """Parse ps etime format (dd-hh:mm:ss or hh:mm:ss or mm:ss) to seconds."""
    etime_str = etime_str.strip()
    days = 0
    if "-" in etime_str:
        day_part, etime_str = etime_str.split("-", 1)
        days = int(day_part)
    parts = etime_str.split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 3:
        return days * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return days * 86400 + parts[0] * 60 + parts[1]
    return days * 86400


# ---------------------------------------------------------------------------
# Diagnostic: Venv consistency
# ---------------------------------------------------------------------------


def diagnose_venv() -> list[dict]:
    """Check venv health: does it exist, does it have key packages."""
    issues = []
    venv_python = VENV / "bin" / "python3"

    if not venv_python.exists():
        issues.append({
            "check": "venv",
            "severity": CRITICAL,
            "error": "No Python venv found at operator/.venv — tools requiring openai/tenacity will fail",
        })
        return issues

    # Check key packages
    essential = ["openai", "tenacity", "requests", "beautifulsoup4"]
    try:
        r = subprocess.run(
            [str(venv_python), "-m", "pip", "freeze", "--local"],
            capture_output=True, text=True, timeout=10,
        )
        installed = set()
        for line in r.stdout.splitlines():
            pkg = line.split("==")[0].split(">=")[0].strip().lower().replace("-", "_")
            if pkg:
                installed.add(pkg)

        for pkg in essential:
            pkg_norm = pkg.lower().replace("-", "_")
            if pkg_norm not in installed:
                issues.append({
                    "check": "venv_package",
                    "severity": WARNING if pkg_norm != "openai" else CRITICAL,
                    "error": f"Essential package '{pkg}' not installed in venv",
                    "suggested_fix": f"{venv_python} -m pip install {pkg}",
                })
    except Exception as e:
        issues.append({
            "check": "venv",
            "severity": WARNING,
            "error": f"Could not check venv packages: {e}",
        })

    # Check which bin/ scripts properly activate venv
    scripts_needing_venv = ["brain"]
    for script_name in scripts_needing_venv:
        script_path = BIN / script_name
        if not script_path.exists():
            continue
        try:
            content = script_path.read_text()
            if ".venv" not in content and "venv" not in content:
                issues.append({
                    "check": "venv_activation",
                    "severity": WARNING,
                    "error": f"bin/{script_name} does not activate venv — may miss dependencies",
                })
        except OSError:
            pass

    return issues


# ---------------------------------------------------------------------------
# Fix routines
# ---------------------------------------------------------------------------


class FixResult:
    def __init__(self, fixed: bool, diagnosis: str, action: str,
                 patch_path: str | None = None, details: dict | None = None):
        self.fixed = fixed
        self.diagnosis = diagnosis
        self.action = action
        self.patch_path = patch_path
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "fixed": self.fixed,
            "diagnosis": self.diagnosis,
            "action": self.action,
            "patch_path": self.patch_path,
            **self.details,
        }


def fix_shell_syntax(script_path: Path, governance_level: int = 2) -> FixResult:
    """Attempt to fix a shell script syntax error."""
    diag = diagnose_shell_syntax(script_path)
    if diag["ok"]:
        return FixResult(False, "No syntax error found", "none")

    if not _is_safe_path(script_path):
        return FixResult(False, diag["errors"], "blocked — file outside safe zone")

    original = script_path.read_text()
    lines = original.splitlines(keepends=True)
    err_line = diag.get("line")
    errors_text = diag.get("errors", "")
    fixed_content = None
    fix_description = ""

    # --- Fix strategy: missing fi/done/esac ---
    if any(kw in errors_text for kw in ["unexpected token", "unexpected end of file", "syntax error"]):
        fix_content_result = _fix_block_balance(lines, err_line, errors_text)
        if fix_content_result:
            fixed_content, fix_description = fix_content_result

    # --- Fix strategy: unmatched quotes ---
    if fixed_content is None and ("unexpected EOF" in errors_text or "unexpected end of file" in errors_text or "unterminated" in errors_text.lower()):
        fix_content_result = _fix_unterminated(lines, err_line, errors_text)
        if fix_content_result:
            fixed_content, fix_description = fix_content_result

    if fixed_content is None:
        # Deterministic fix failed — LLM fix available as fallback (if enabled)
        if LLM_FIX_ENABLED:
            return FixResult(
                False,
                f"Syntax error at line {err_line}: {errors_text} (LLM fix available if llm_fn provided)",
                "diagnose_only — no auto-fix pattern, try llm_code_fix()",
                details={"errors": errors_text, "line": err_line, "llm_fixable": True},
            )
        return FixResult(
            False,
            f"Syntax error at line {err_line}: {errors_text}",
            "diagnose_only — no auto-fix pattern matched",
            details={"errors": errors_text, "line": err_line},
        )

    # Verify the fix
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as tmp:
        tmp.write(fixed_content)
        tmp_path = tmp.name
    try:
        verify = subprocess.run(["bash", "-n", tmp_path], capture_output=True, text=True, timeout=10)
        if verify.returncode != 0:
            return FixResult(
                False,
                f"Fix attempted but verification failed: {verify.stderr.strip()}",
                "fix_failed_verification",
                details={"original_error": errors_text, "fix_attempted": fix_description},
            )
    finally:
        os.unlink(tmp_path)

    # Save patch
    patch_path = _save_patch(
        script_path.name, original, fixed_content,
        {"reason": "shell_syntax_fix", "diagnosis": errors_text,
         "fix": fix_description, "file": str(script_path)},
    )

    if governance_level >= 3:
        script_path.write_text(fixed_content)
        return FixResult(
            True, f"Fixed: {fix_description}",
            "applied",
            patch_path=str(patch_path),
            details={"line": err_line, "verified": True},
        )
    else:
        return FixResult(
            False, f"Fix ready (dry-run): {fix_description}",
            "dry_run — patch saved, governance < 3",
            patch_path=str(patch_path),
            details={"line": err_line, "verified": True, "governance": governance_level},
        )


def _fix_block_balance(lines: list[str], err_line: int | None, errors_text: str):
    """Fix unbalanced if/fi, while/done, case/esac blocks."""
    content = "".join(lines)

    # Count shell-level blocks (skip heredocs)
    in_heredoc = False
    heredoc_end = ""
    if_count = 0
    fi_count = 0
    case_count = 0
    esac_count = 0
    while_for_count = 0
    done_count = 0

    for line in lines:
        stripped = line.strip()
        if in_heredoc:
            if stripped == heredoc_end:
                in_heredoc = False
            continue
        # Detect heredoc start
        hd = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if hd:
            heredoc_end = hd.group(1)
            in_heredoc = True

        # Count keywords (only at shell level, ignore Python/comments)
        shell_part = stripped.split("#")[0].strip() if "#" in stripped else stripped
        if re.match(r'^if\s', shell_part) or re.match(r'^if\s', stripped):
            if_count += 1
        if shell_part in ("fi", "fi;") or re.match(r'^fi\b', shell_part):
            fi_count += 1
        if re.match(r'^case\s', shell_part):
            case_count += 1
        if shell_part in ("esac", "esac;") or re.match(r'^esac\b', shell_part):
            esac_count += 1
        if re.match(r'^(while|for)\s', shell_part):
            while_for_count += 1
        if shell_part in ("done", "done;") or re.match(r'^done\b', shell_part):
            done_count += 1

    # Determine insertion point: before the error line, or at EOF if no specific line
    def _insert_idx():
        if err_line and err_line <= len(lines):
            return err_line - 1
        return len(lines)

    if if_count > fi_count:
        missing = if_count - fi_count
        idx = _insert_idx()
        indent = "    "
        if idx < len(lines):
            m = re.match(r'^(\s*)', lines[idx])
            if m:
                indent = m.group(1)
        for _ in range(missing):
            lines.insert(idx, f"{indent}fi\n")
        fixed = "".join(lines)
        return fixed, f"Inserted {missing} missing 'fi' at line {idx + 1}"

    if case_count > esac_count:
        missing = case_count - esac_count
        idx = _insert_idx()
        indent = "    "
        for _ in range(missing):
            lines.insert(idx, f"{indent}esac\n")
        fixed = "".join(lines)
        return fixed, f"Inserted {missing} missing 'esac' at line {idx + 1}"

    if while_for_count > done_count:
        missing = while_for_count - done_count
        idx = _insert_idx()
        indent = "    "
        for _ in range(missing):
            lines.insert(idx, f"{indent}done\n")
        fixed = "".join(lines)
        return fixed, f"Inserted {missing} missing 'done' at line {idx + 1}"

    return None


def _fix_unterminated(lines: list[str], err_line: int | None, errors_text: str):
    """Fix unterminated strings or heredocs."""
    # Simple case: unterminated quote on a specific line
    if err_line and err_line <= len(lines):
        line = lines[err_line - 1]
        single_q = line.count("'") % 2
        double_q = line.count('"') % 2
        if single_q:
            lines[err_line - 1] = line.rstrip("\n") + "'\n"
            return "".join(lines), f"Added closing single quote at line {err_line}"
        if double_q:
            lines[err_line - 1] = line.rstrip("\n") + '"\n'
            return "".join(lines), f"Added closing double quote at line {err_line}"
    return None


# ---------------------------------------------------------------------------
# Fix: repeated job failures (LLM-assisted root cause analysis)
# ---------------------------------------------------------------------------


def fix_repeated_failures(
    workflow: str,
    failures: list[dict],
    governance_level: int = 2,
    llm_fn=None,
) -> FixResult:
    """Analyze repeated failures and attempt a fix.

    Integrates fingerprint tracking, cooldown gating, and non-repairable
    classification before attempting any fix.
    """
    logs = []
    for f in failures[:3]:
        log = read_job_log(f.get("job_dir", ""), tail=60)
        if log:
            logs.append(log)

    if not logs:
        record_fingerprint(workflow, "no logs available", fix_attempted=False,
                           fix_succeeded=False, action="no_logs",
                           category="repeated_failures")
        return FixResult(False, "No logs available for analysis", "no_logs")

    error_summary = _extract_error_from_logs(logs)

    # ---- Non-repairable classification (before any fix attempt) ----
    nr = classify_non_repairable(error_summary)
    if nr:
        reason_code, explanation = nr
        mark_non_repairable(workflow, error_summary, reason_code)
        record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action=f"non_repairable:{reason_code}",
                           category="repeated_failures")
        return FixResult(
            False,
            f"Non-repairable: {explanation}",
            f"non_repairable:{reason_code}",
            details={"reason": reason_code, "explanation": explanation,
                     "error_summary": error_summary[:300]},
        )

    # ---- Cooldown check (prevent fix thrashing) ----
    on_cd, cd_entry = is_on_cooldown(workflow, error_summary)
    if on_cd and cd_entry:
        record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="cooldown_skip",
                           category="repeated_failures")
        reason = "non-repairable" if cd_entry.get("non_repairable") else "cooldown active"
        return FixResult(
            False,
            f"Skipped fix — {reason} (fingerprint {cd_entry.get('fingerprint', '?')}, "
            f"{cd_entry.get('fix_attempts', 0)} prior attempts)",
            f"cooldown_skip",
            details={"fingerprint": cd_entry.get("fingerprint"),
                     "prior_attempts": cd_entry.get("fix_attempts", 0),
                     "cooldown_until": cd_entry.get("cooldown_until", "")},
        )

    # ---- Deterministic fix attempts ----

    # Check if the workflow script has a syntax error
    script = WORKFLOWS / f"{workflow}.sh"
    if script.exists():
        syntax_diag = diagnose_shell_syntax(script)
        if not syntax_diag["ok"]:
            result = fix_shell_syntax(script, governance_level)
            record_fingerprint(workflow, error_summary, fix_attempted=result.applied,
                               fix_succeeded=result.applied, action=result.action,
                               category="shell_syntax")
            return result

    # Pattern: FileNotFoundError in Python
    fnf_match = re.search(r"FileNotFoundError.*No such file.*: '([^']+)'", error_summary)
    if fnf_match:
        missing_path = fnf_match.group(1)
        record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="diagnose_only",
                           category="missing_file")
        return FixResult(
            False,
            f"Jobs fail because file is missing: {missing_path}",
            "diagnose_only — missing file detected",
            details={"missing_file": missing_path, "error_pattern": "FileNotFoundError"},
        )

    # Pattern: ModuleNotFoundError
    mod_match = re.search(r"ModuleNotFoundError.*No module named '([^']+)'", error_summary)
    if mod_match:
        module = mod_match.group(1)
        record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="diagnose_only",
                           category="missing_module")
        return FixResult(
            False,
            f"Jobs fail due to missing Python module: {module}",
            "diagnose_only — missing module",
            details={"missing_module": module, "error_pattern": "ModuleNotFoundError",
                     "suggested_fix": f"pip install {module}"},
        )

    # Pattern: timeout
    if "timeout" in error_summary.lower():
        record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="diagnose_only",
                           category="timeout")
        return FixResult(
            False,
            f"Jobs fail due to timeout: {error_summary[:200]}",
            "diagnose_only — timeout",
            details={"error_pattern": "timeout"},
        )

    # LLM analysis for complex cases
    if llm_fn:
        try:
            analysis = llm_fn(
                system="You are a DevOps expert. Analyze these job failure logs and identify the root cause. Return JSON: {\"root_cause\": \"...\", \"fix_suggestion\": \"...\", \"file_to_fix\": \"path or null\", \"confidence\": 0.0-1.0}",
                user=f"Workflow: {workflow}\nError: {error_summary}\n\nRecent logs:\n" + "\n---\n".join(logs[:2])[:4000],
            )
            record_fingerprint(workflow, error_summary, fix_attempted=False,
                               fix_succeeded=False, action="llm_analysis",
                               category="llm_diagnosis")
            return FixResult(
                False,
                f"LLM analysis: {analysis.get('root_cause', 'unknown')}",
                "diagnose_only — LLM analysis",
                details={
                    "llm_root_cause": analysis.get("root_cause"),
                    "llm_fix_suggestion": analysis.get("fix_suggestion"),
                    "llm_file": analysis.get("file_to_fix"),
                    "llm_confidence": analysis.get("confidence"),
                },
            )
        except Exception:
            pass

    # Last resort: try LLM code fix (only if enabled)
    if LLM_FIX_ENABLED and llm_fn:
        llm_result = llm_fix_from_job_failure(workflow, failures, governance_level, llm_fn)
        if llm_result is not None:
            fp_action = "llm_fix_applied" if llm_result.applied else "llm_fix_failed"
            record_fingerprint(workflow, error_summary, fix_attempted=True,
                               fix_succeeded=llm_result.applied, action=fp_action,
                               category="llm_fix")
            return llm_result

    record_fingerprint(workflow, error_summary, fix_attempted=False,
                       fix_succeeded=False, action="no_fix_pattern",
                       category="unknown")
    return FixResult(
        False,
        f"Repeated failures ({len(failures)}x) in {workflow}: {error_summary[:200]}",
        "diagnose_only — no matching fix pattern",
        details={"error_summary": error_summary},
    )


# ---------------------------------------------------------------------------
# LLM-powered code fix (DISABLED by default — set PLUMBER_LLM_FIX=1 to enable)
# ---------------------------------------------------------------------------

LLM_FIX_ENABLED = os.environ.get("PLUMBER_LLM_FIX", "0") in ("1", "true", "yes")
LLM_FIX_MAX_DIFF_LINES = 50
LLM_FIX_MAX_ATTEMPTS_PER_FILE = 1
LLM_FIX_MODEL = os.environ.get("PLUMBER_LLM_MODEL", "codex-5.3")

# Track files already attempted in this session to prevent recursive fixes
_llm_fix_attempted: set[str] = set()


def llm_code_fix(
    file_path: Path,
    error_context: str,
    governance_level: int = 2,
    llm_fn=None,
) -> FixResult:
    """Use LLM to analyze a code error and generate a targeted fix.

    Safety guards:
      - Only files under ALLOWED_FIX_ROOTS
      - Max LLM_FIX_MAX_DIFF_LINES changed lines per patch
      - No recursive fixes (max 1 attempt per file per session)
      - Verification after fix (bash -n for .sh, py_compile for .py)
      - Patch saved for audit + rollback
      - Only at governance >= 3
    """
    file_str = str(file_path)

    if not LLM_FIX_ENABLED:
        return FixResult(
            False,
            f"LLM fix disabled (set PLUMBER_LLM_FIX=1 to enable)",
            "disabled",
            details={"file": file_str, "hint": "export PLUMBER_LLM_FIX=1"},
        )

    if not llm_fn:
        return FixResult(
            False, "No LLM function available", "no_llm",
            details={"file": file_str},
        )

    if not _is_safe_path(file_path):
        return FixResult(
            False, f"File outside safe zone: {file_str}", "blocked",
            details={"file": file_str},
        )

    if file_str in _llm_fix_attempted:
        return FixResult(
            False, f"Already attempted LLM fix on {file_path.name} this session",
            "skip_recursive",
            details={"file": file_str},
        )
    _llm_fix_attempted.add(file_str)

    if not file_path.exists():
        return FixResult(False, f"File not found: {file_str}", "file_missing")

    original = file_path.read_text()
    lines = original.splitlines()

    # Limit context sent to LLM (first/last 200 lines if file is huge)
    if len(lines) > 400:
        context_lines = lines[:200] + ["", "# ... (truncated) ...", ""] + lines[-200:]
    else:
        context_lines = lines
    code_context = "\n".join(context_lines)

    # Build the prompt
    file_type = file_path.suffix
    system_prompt = f"""You are an expert code repair agent. You fix bugs in production code.

RULES:
1. Output ONLY valid JSON with this structure:
   {{"fixed_code": "the complete fixed file content", "explanation": "what you changed and why", "confidence": 0.0-1.0}}
2. Make the SMALLEST possible change that fixes the error. Do NOT rewrite or refactor.
3. Keep all existing functionality intact.
4. The fix must be syntactically valid ({'.sh = bash' if file_type == '.sh' else '.py = Python 3'}).
5. Maximum {LLM_FIX_MAX_DIFF_LINES} lines changed. If the fix requires more, set confidence to 0.0.
6. If you are NOT confident about the fix (< 0.6), set confidence accordingly — the system will skip low-confidence patches."""

    user_prompt = f"""FILE: {file_path.name}
TYPE: {file_type}
ERROR:
{error_context[:2000]}

CURRENT CODE:
```
{code_context[:8000]}
```

Analyze the error, find the root cause, and provide the minimal fix."""

    # Call LLM
    try:
        result = llm_fn(system=system_prompt, user=user_prompt)
    except Exception as e:
        return FixResult(
            False, f"LLM call failed: {e}", "llm_error",
            details={"file": file_str},
        )

    if not isinstance(result, dict) or "fixed_code" not in result:
        return FixResult(
            False, "LLM returned invalid response (no fixed_code)", "llm_bad_response",
            details={"file": file_str},
        )

    fixed_code = result["fixed_code"]
    explanation = result.get("explanation", "")
    confidence = float(result.get("confidence", 0.0))

    # Safety: reject low confidence
    if confidence < 0.6:
        return FixResult(
            False,
            f"LLM fix rejected: confidence {confidence:.2f} < 0.6 — {explanation[:200]}",
            "low_confidence",
            details={"file": file_str, "confidence": confidence, "explanation": explanation[:300]},
        )

    # Safety: check diff size
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed_code.splitlines(keepends=True)
    diff = list(difflib.unified_diff(original_lines, fixed_lines, n=0))
    changed_lines = sum(1 for line in diff if line.startswith("+") or line.startswith("-"))
    # Subtract the --- and +++ header lines
    changed_lines = max(0, changed_lines - 2)

    if changed_lines > LLM_FIX_MAX_DIFF_LINES:
        return FixResult(
            False,
            f"LLM fix too large: {changed_lines} lines changed (max {LLM_FIX_MAX_DIFF_LINES})",
            "diff_too_large",
            details={"file": file_str, "changed_lines": changed_lines, "explanation": explanation[:300]},
        )

    if changed_lines == 0:
        return FixResult(
            False, "LLM returned identical code (no changes)", "no_changes",
            details={"file": file_str},
        )

    # Verify the fix
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=file_type, delete=False) as tmp:
        tmp.write(fixed_code)
        tmp_path = tmp.name
    try:
        if file_type == ".sh":
            verify = subprocess.run(["bash", "-n", tmp_path], capture_output=True, text=True, timeout=10)
        elif file_type == ".py":
            python = str(VENV / "bin" / "python3") if (VENV / "bin" / "python3").exists() else "python3"
            verify = subprocess.run([python, "-m", "py_compile", tmp_path], capture_output=True, text=True, timeout=10)
        else:
            # Unknown file type — skip verification
            verify = subprocess.CompletedProcess(args=[], returncode=0)

        if verify.returncode != 0:
            return FixResult(
                False,
                f"LLM fix failed verification: {verify.stderr.strip()[:200]}",
                "fix_failed_verification",
                details={"file": file_str, "explanation": explanation[:300],
                         "verify_error": verify.stderr.strip()[:200]},
            )
    finally:
        os.unlink(tmp_path)

    # Save patch
    patch_path = _save_patch(
        file_path.name, original, fixed_code,
        {
            "reason": "llm_code_fix",
            "model": LLM_FIX_MODEL,
            "diagnosis": error_context[:300],
            "explanation": explanation[:500],
            "confidence": confidence,
            "changed_lines": changed_lines,
            "file": file_str,
        },
    )

    # Apply at governance 3
    if governance_level >= 3:
        file_path.write_text(fixed_code)
        return FixResult(
            True,
            f"LLM fix applied ({changed_lines} lines, confidence {confidence:.2f}): {explanation[:200]}",
            "applied",
            patch_path=str(patch_path),
            details={
                "file": file_str, "changed_lines": changed_lines,
                "confidence": confidence, "model": LLM_FIX_MODEL,
                "explanation": explanation[:500], "verified": True,
            },
        )
    else:
        return FixResult(
            False,
            f"LLM fix ready (dry-run, {changed_lines} lines, confidence {confidence:.2f}): {explanation[:200]}",
            "dry_run",
            patch_path=str(patch_path),
            details={
                "file": file_str, "changed_lines": changed_lines,
                "confidence": confidence, "model": LLM_FIX_MODEL,
                "explanation": explanation[:500], "verified": True, "governance": governance_level,
            },
        )


def llm_fix_from_job_failure(
    workflow: str,
    failures: list[dict],
    governance_level: int = 2,
    llm_fn=None,
) -> FixResult | None:
    """Attempt an LLM code fix based on repeated job failures.

    Returns None if LLM fix is not applicable, FixResult otherwise.
    """
    if not LLM_FIX_ENABLED or not llm_fn:
        return None

    # Gather error context from logs
    logs = []
    for f in failures[:3]:
        log = read_job_log(f.get("job_dir", ""), tail=80)
        if log:
            logs.append(log)
    if not logs:
        return None

    error_summary = _extract_error_from_logs(logs)

    # Try to identify the failing file from the traceback
    file_to_fix = None
    for log in logs:
        for line in log.splitlines():
            m = re.search(r'File "(/root/operator/(tools|workflows)/[^"]+)"', line)
            if m:
                candidate = Path(m.group(1))
                if candidate.exists() and _is_safe_path(candidate):
                    file_to_fix = candidate
                    break
        if file_to_fix:
            break

    # Fallback: try the workflow script itself
    if not file_to_fix:
        script = WORKFLOWS / f"{workflow}.sh"
        if script.exists():
            file_to_fix = script

    if not file_to_fix:
        return None

    error_context = f"Workflow: {workflow}\nRepeated failures: {len(failures)}x\n\nError:\n{error_summary}\n\nRecent log:\n{logs[0][:3000]}"

    return llm_code_fix(file_to_fix, error_context, governance_level, llm_fn)


def rollback_if_still_failing(patch_meta_path: Path) -> dict | None:
    """Auto-rollback: if a patched file's workflow still fails after fix, undo it.

    Called by the plumber on subsequent runs to detect bad fixes.
    Returns rollback result or None if no rollback needed.
    """
    if not patch_meta_path.exists():
        return None
    try:
        meta = json.loads(patch_meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Only auto-rollback LLM fixes (deterministic fixes are trusted)
    if meta.get("reason") != "llm_code_fix":
        return None

    created = meta.get("created_at", "")
    if not created:
        return None

    # Check if the workflow that was fixed has failed AFTER the fix was applied
    file_fixed = meta.get("file", "")
    # Extract workflow name from file path
    wf_name = None
    if "/workflows/" in file_fixed:
        wf_name = Path(file_fixed).stem

    if not wf_name:
        return None

    # Look for failures after the patch timestamp
    post_fix_failures = 0
    if JOBS.exists():
        for job_file in sorted(JOBS.glob("*/*/job.json"), reverse=True)[:20]:
            try:
                j = json.loads(job_file.read_text())
                if j.get("workflow_id") != wf_name:
                    continue
                if j.get("status") != "FAILED":
                    continue
                job_ts = j.get("created_at", "")
                if job_ts > created:
                    post_fix_failures += 1
            except (json.JSONDecodeError, OSError):
                continue

    if post_fix_failures >= 2:
        # Workflow still failing after fix — rollback
        patch_file = meta.get("patch_file", "")
        if patch_file:
            result = rollback_patch(patch_file)
            result["reason"] = f"Auto-rollback: {wf_name} still failing ({post_fix_failures}x) after LLM fix"
            return result

    return None


# ---------------------------------------------------------------------------
# Patch-impact metrics
# ---------------------------------------------------------------------------


def _compute_patch_metrics(patches: list[dict]) -> dict:
    """Aggregate patch metrics for maintenance quality visibility."""
    total = len(patches)
    if total == 0:
        return {
            "total_patches": 0, "files_affected": 0, "total_loc_changed": 0,
            "reverts": 0, "success_rate_pct": 0, "by_category": {},
        }

    files_affected = set()
    total_loc = 0
    reverts = 0
    successes = 0
    by_cat: dict[str, dict] = {}

    for p in patches:
        f = p.get("file", "")
        if f:
            files_affected.add(f)
        loc = p.get("loc_changed", 0)
        total_loc += loc
        cat = p.get("category", p.get("type", "unknown"))
        c = by_cat.setdefault(cat, {"count": 0, "loc": 0, "reverts": 0, "successes": 0})
        c["count"] += 1
        c["loc"] += loc
        if p.get("reverted"):
            reverts += 1
            c["reverts"] += 1
        elif p.get("verified", True):
            successes += 1
            c["successes"] += 1

    return {
        "total_patches": total,
        "files_affected": len(files_affected),
        "total_loc_changed": total_loc,
        "reverts": reverts,
        "success_rate_pct": round(successes / total * 100, 1) if total > 0 else 0,
        "by_category": by_cat,
    }


# ---------------------------------------------------------------------------
# Master entry point: the Plumber dispatch
# ---------------------------------------------------------------------------


def run_plumber(
    intent: str = "diagnose-and-fix",
    target: str | None = None,
    governance_level: int = 2,
    llm_fn=None,
) -> dict:
    """
    Main entry point for the Plumber self-healing system.

    Runs 7 diagnostic categories and attempts fixes where possible.

    Args:
        intent: What to do — "diagnose-and-fix", "diagnose-only", "rollback"
        target: Optional specific target (workflow name, job_id, file path)
        governance_level: Controls what the plumber is allowed to do
        llm_fn: Optional LLM function for advanced analysis

    Returns:
        Dict with diagnosis, actions taken, and patches created.
    """
    PLUMBER_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    issues_found = 0
    issues_fixed = 0
    categories: dict[str, dict] = {}

    # ── Pre-check: auto-rollback bad LLM patches ─────────────────────
    if LLM_FIX_ENABLED and PATCHES_DIR.exists():
        for meta_file in PATCHES_DIR.glob("*.json"):
            rb = rollback_if_still_failing(meta_file)
            if rb and rb.get("ok"):
                results.append({
                    "type": "auto_rollback",
                    "severity": WARNING,
                    "fixed": True,
                    "diagnosis": rb.get("reason", "Auto-rollback of bad LLM fix"),
                    "action": "rolled_back",
                    "target": rb.get("rolled_back", ""),
                })
                issues_found += 1
                issues_fixed += 1

    # ── Category 1: Shell syntax ──────────────────────────────────────
    cat_shell = {"status": "clean", "issues": []}
    if WORKFLOWS.exists():
        for script in sorted(WORKFLOWS.glob("*.sh")):
            diag = diagnose_shell_syntax(script)
            if not diag["ok"]:
                issues_found += 1
                fix = fix_shell_syntax(script, governance_level)
                entry = {"type": "shell_syntax", "target": str(script), **fix.to_dict()}
                results.append(entry)
                cat_shell["issues"].append(entry)
                cat_shell["status"] = "issues_found"
                record_fingerprint(
                    script.stem, diag.get("error", "shell syntax error"),
                    fix_attempted=fix.applied, fix_succeeded=fix.applied,
                    action=fix.action, category="shell_syntax",
                )
                if fix.fixed:
                    issues_fixed += 1
    categories["shell_syntax"] = cat_shell

    # ── Category 2: Repeated job failures ─────────────────────────────
    cat_failures = {"status": "clean", "issues": []}
    repeated = diagnose_repeated_failures()
    for r in repeated:
        wf = r["workflow"]
        if target and target != wf:
            continue
        issues_found += 1
        fix = fix_repeated_failures(wf, r["failures"], governance_level, llm_fn)
        entry = {"type": "repeated_failures", "target": wf, "fail_count": r["fail_count"], **fix.to_dict()}
        results.append(entry)
        cat_failures["issues"].append(entry)
        cat_failures["status"] = "issues_found"
        if fix.fixed:
            issues_fixed += 1
    categories["repeated_failures"] = cat_failures

    # ── Category 3: Python tool compile + import checks ───────────────
    cat_python = {"status": "clean", "issues": []}
    py_issues = diagnose_python_tools()
    for issue in py_issues:
        issues_found += 1
        entry = {"type": "python_tool", **issue}
        results.append(entry)
        cat_python["issues"].append(entry)
        cat_python["status"] = "issues_found"
        record_fingerprint(
            issue.get("tool", "unknown"), issue.get("error", "python tool error"),
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="python_tools",
        )
    categories["python_tools"] = cat_python

    # ── Category 4: Dependency consistency ────────────────────────────
    cat_deps = {"status": "clean", "issues": []}
    dep_issues = diagnose_dependencies()
    for issue in dep_issues:
        issues_found += 1
        mod = issue.get("module", "")
        pip_name = issue.get("pip_name", mod)
        fix = fix_missing_dependency(mod, pip_name, governance_level)
        entry = {"type": "dependency", **issue, **fix.to_dict()}
        results.append(entry)
        cat_deps["issues"].append(entry)
        cat_deps["status"] = "issues_found"
        record_fingerprint(
            mod, f"missing dependency: {mod}",
            fix_attempted=fix.applied, fix_succeeded=fix.applied,
            action=fix.action, category="dependencies",
        )
        if fix.fixed:
            issues_fixed += 1
            cat_deps["status"] = "fixed"
    categories["dependencies"] = cat_deps

    # ── Category 5: Tool reference integrity ──────────────────────────
    cat_refs = {"status": "clean", "issues": [], "dead_tools": []}
    ref_info = diagnose_tool_references()
    for miss in ref_info.get("missing_refs", []):
        issues_found += 1
        diag_msg = f"Workflow references {miss['tool']} but file does not exist"
        entry = {"type": "missing_tool_ref", "target": miss["tool"], "script": miss["script"], "severity": CRITICAL,
                 "fixed": False, "diagnosis": diag_msg, "action": "diagnose_only"}
        results.append(entry)
        cat_refs["issues"].append(entry)
        cat_refs["status"] = "issues_found"
        record_fingerprint(
            miss.get("script", "unknown"), diag_msg,
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="tool_references",
        )
    cat_refs["dead_tools"] = ref_info.get("dead_tools", [])
    cat_refs["referenced_count"] = ref_info.get("referenced_count", 0)
    if ref_info.get("dead_tools"):
        cat_refs["status"] = "info"
    categories["tool_references"] = cat_refs

    # ── Category 6: Process health ────────────────────────────────────
    cat_proc = {"status": "clean", "issues": []}
    proc_info = diagnose_processes()
    if proc_info.get("stuck"):
        issues_found += 1
        stuck_procs = [p for group in [proc_info["brain_cycles"], proc_info["brain_reflects"]]
                       for p in group if p.get("stuck")]
        diag_msg = f"{len(stuck_procs)} stuck brain process(es)"
        entry = {
            "type": "stuck_process",
            "severity": CRITICAL,
            "fixed": False,
            "diagnosis": diag_msg,
            "action": "diagnose_only — use 'pkill -f bin/brain' or UI kill button",
            "processes": stuck_procs,
        }
        results.append(entry)
        cat_proc["issues"].append(entry)
        cat_proc["status"] = "issues_found"
        record_fingerprint(
            "brain", diag_msg,
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="processes",
        )
    if proc_info.get("zombie_count", 0) > 0:
        diag_msg = f"{proc_info['zombie_count']} zombie process(es) on system"
        entry = {
            "type": "zombie_processes",
            "severity": WARNING,
            "fixed": False,
            "diagnosis": diag_msg,
            "action": "diagnose_only",
        }
        results.append(entry)
        cat_proc["issues"].append(entry)
        if cat_proc["status"] == "clean":
            cat_proc["status"] = "issues_found"
        record_fingerprint(
            "system", diag_msg,
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="processes",
        )
    cat_proc["cycle_count"] = len(proc_info.get("brain_cycles", []))
    cat_proc["reflect_count"] = len(proc_info.get("brain_reflects", []))
    categories["processes"] = cat_proc

    # ── Category 7: Venv health ───────────────────────────────────────
    cat_venv = {"status": "clean", "issues": []}
    venv_issues = diagnose_venv()
    for issue in venv_issues:
        issues_found += 1
        entry = {"type": "venv", **issue}
        results.append(entry)
        cat_venv["issues"].append(entry)
        cat_venv["status"] = "issues_found"
        record_fingerprint(
            "venv", issue.get("error", issue.get("check", "venv issue")),
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="venv",
        )
    categories["venv"] = cat_venv

    # ── Targeted fix ──────────────────────────────────────────────────
    if target and Path(target).exists() and Path(target).suffix == ".sh":
        target_path = Path(target)
        if _is_safe_path(target_path):
            diag = diagnose_shell_syntax(target_path)
            if not diag["ok"]:
                issues_found += 1
                fix = fix_shell_syntax(target_path, governance_level)
                results.append({"type": "targeted_fix", "target": str(target_path), **fix.to_dict()})
                if fix.fixed:
                    issues_fixed += 1

    # ── Summary ───────────────────────────────────────────────────────
    clean_count = sum(1 for c in categories.values() if c["status"] == "clean")
    critical_count = sum(1 for r in results if r.get("severity") == CRITICAL)
    warning_count = sum(1 for r in results if r.get("severity") == WARNING)

    # ── Fingerprint stats (learning data) ─────────────────────────────
    fp_stats = get_fingerprint_stats()

    # ── Patch-impact metrics ──────────────────────────────────────────
    patches = list_patches()
    patch_metrics = _compute_patch_metrics(patches)

    report = {
        "timestamp": _utcnow(),
        "intent": intent,
        "governance_level": governance_level,
        "issues_found": issues_found,
        "issues_fixed": issues_fixed,
        "categories": categories,
        "summary": {
            "clean": clean_count,
            "total_categories": len(categories),
            "critical": critical_count,
            "warnings": warning_count,
        },
        "results": results,
        "fingerprints": fp_stats,
        "patch_metrics": patch_metrics,
    }
    report_path = PLUMBER_DIR / "last_run.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))

    return report


def rollback_patch(patch_path: str) -> dict:
    """Rollback a previously applied patch."""
    pp = Path(patch_path)
    if not pp.exists():
        return {"ok": False, "error": "Patch file not found"}

    meta_path = pp.with_suffix(".json")
    if not meta_path.exists():
        return {"ok": False, "error": "Patch meta not found"}

    meta = json.loads(meta_path.read_text())
    target_file = Path(meta.get("file", ""))
    if not target_file.exists():
        return {"ok": False, "error": f"Target file not found: {target_file}"}

    # Use patch -R to reverse
    try:
        result = subprocess.run(
            ["patch", "-R", str(target_file), str(pp)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"ok": True, "rolled_back": str(target_file)}
        return {"ok": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_patches() -> list[dict]:
    """List all plumber patches for audit."""
    patches = []
    if not PATCHES_DIR.exists():
        return patches
    for meta_file in sorted(PATCHES_DIR.glob("*.json"), reverse=True):
        try:
            patches.append(json.loads(meta_file.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return patches
