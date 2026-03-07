# Plumber diagnostics: shell, repeated failures, Python tools, dependencies, tool refs, processes, venv.
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import constants


def diagnose_shell_syntax(script_path: Path) -> dict:
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
    failures: dict[str, list[dict]] = {}
    if not constants.JOBS.exists():
        return []
    job_files = sorted(constants.JOBS.glob("*/*/job.json"), reverse=True)[:limit * 3]
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


def read_job_log(job_dir: str, tail: int = constants.MAX_LOG_LINES) -> str:
    log_path = Path(job_dir) / "log.txt"
    if not log_path.exists():
        return ""
    lines = log_path.read_text().splitlines()
    return "\n".join(lines[-tail:])


def _extract_error_from_logs(logs: list[str]) -> str:
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


def _get_stdlib_modules() -> list[str]:
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


def diagnose_python_tools() -> list[dict]:
    issues = []
    if not constants.TOOLS.exists():
        return issues
    python = str(constants.VENV / "bin" / "python3") if (constants.VENV / "bin" / "python3").exists() else "python3"
    for py_file in sorted(constants.TOOLS.glob("*.py")):
        try:
            r = subprocess.run(
                [python, "-m", "py_compile", str(py_file)],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                issues.append({
                    "file": str(py_file),
                    "check": "compile",
                    "severity": constants.CRITICAL,
                    "error": (r.stderr or "").strip()[:300],
                })
                continue
        except Exception as e:
            issues.append({
                "file": str(py_file),
                "check": "compile",
                "severity": constants.WARNING,
                "error": f"compile check failed: {e}",
            })
            continue
        module_name = py_file.stem
        try:
            r = subprocess.run(
                [python, "-c", f"import importlib; importlib.import_module('tools.{module_name}')"],
                capture_output=True, text=True, timeout=15,
                cwd=str(constants.BASE),
                env={**os.environ, "PYTHONPATH": str(constants.BASE)},
            )
            if r.returncode != 0:
                stderr = (r.stderr or "").strip()
                if "ModuleNotFoundError" in stderr or "ImportError" in stderr or "SyntaxError" in stderr:
                    issues.append({
                        "file": str(py_file),
                        "check": "import",
                        "severity": constants.CRITICAL if "ModuleNotFoundError" in stderr else constants.WARNING,
                        "error": stderr[:300],
                    })
        except subprocess.TimeoutExpired:
            issues.append({
                "file": str(py_file),
                "check": "import",
                "severity": constants.WARNING,
                "error": "import timed out (>15s) — possible side effect at import time",
            })
        except Exception:
            pass
    return issues


def diagnose_dependencies() -> list[dict]:
    issues = []
    if not constants.TOOLS.exists():
        return issues
    imported_modules: set[str] = set()
    stdlib_modules = set(_get_stdlib_modules())
    for py_file in constants.TOOLS.glob("*.py"):
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
    if constants.LIB.exists():
        for py_file in constants.LIB.glob("*.py"):
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
    python = str(constants.VENV / "bin" / "python3") if (constants.VENV / "bin" / "python3").exists() else "python3"
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
    pkg_to_import = {
        "beautifulsoup4": "bs4", "pillow": "PIL", "google_genai": "google",
        "python_dateutil": "dateutil", "pyyaml": "yaml", "scikit_learn": "sklearn",
        "lxml_html_clean": "lxml_html_clean",
    }
    import_to_pkg = {v: k for k, v in pkg_to_import.items()}
    for mod in sorted(imported_modules):
        mod_lower = mod.lower().replace("-", "_")
        found = (
            mod_lower in installed
            or mod_lower in {v.lower() for v in pkg_to_import.values()}
            or import_to_pkg.get(mod, "").lower() in installed
        )
        if not found:
            try:
                r = subprocess.run(
                    [python, "-c", f"import {mod}"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode != 0 and "ModuleNotFoundError" in (r.stderr or ""):
                    pip_name = import_to_pkg.get(mod, mod)
                    issues.append({
                        "module": mod,
                        "pip_name": pip_name,
                        "check": "dependency",
                        "severity": constants.CRITICAL,
                        "error": f"Module '{mod}' imported in code but not installed",
                        "suggested_fix": f"pip install {pip_name}",
                    })
            except Exception:
                pass
    return issues


def diagnose_tool_references() -> dict:
    referenced: set[str] = set()
    existing: set[str] = set()
    missing_refs: list[dict] = []
    dead_tools: list[str] = []
    if constants.TOOLS.exists():
        for f in constants.TOOLS.glob("*.py"):
            existing.add(f.name)
    patterns = [
        re.compile(r'\$TOOLS/([\w_]+\.py)'),
        re.compile(r'\$OPERATOR_ROOT/tools/([\w_]+\.py)'),
        re.compile(r'tools/(research_[\w_]+\.py)'),
    ]
    workflow_dirs = [constants.WORKFLOWS]
    if (constants.WORKFLOWS / "research" / "phases").exists():
        workflow_dirs.append(constants.WORKFLOWS / "research" / "phases")
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
                            "severity": constants.CRITICAL,
                        })
    conductor_py = constants.TOOLS / "research_conductor.py"
    if conductor_py.exists():
        try:
            content = conductor_py.read_text()
            for m in re.finditer(r'["\'](research_[\w_]+\.py)["\']', content):
                referenced.add(m.group(1))
        except OSError:
            pass
    for tool in sorted(existing):
        if tool not in referenced and tool.startswith("research_"):
            dead_tools.append(tool)
    return {
        "referenced_count": len(referenced),
        "existing_count": len(existing),
        "missing_refs": missing_refs,
        "dead_tools": dead_tools,
        "referenced_tools": sorted(referenced),
    }


def diagnose_tool_contracts() -> dict:
    ref_info = diagnose_tool_references()
    referenced = set(ref_info.get("referenced_tools", []))
    research_tools = [t for t in referenced if t.startswith("research_") and t.endswith(".py")]
    missing_contracts: list[str] = []
    registered_count = 0
    try:
        sys.path.insert(0, str(constants.BASE))
        from tools.research_tool_registry import TOOL_CONTRACTS
        registered_count = len(TOOL_CONTRACTS)
        for name in research_tools:
            if name not in TOOL_CONTRACTS:
                missing_contracts.append(name)
    except ImportError:
        pass
    return {
        "referenced_research_tools": len(research_tools),
        "registered_contracts": registered_count,
        "missing_contracts": missing_contracts,
    }


def _parse_etime(etime_str: str) -> int:
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


def diagnose_processes() -> dict:
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
    try:
        r = subprocess.run(
            ["ps", "-eo", "stat"],
            capture_output=True, text=True, timeout=5,
        )
        result["zombie_count"] = sum(1 for line in r.stdout.splitlines() if line.strip().startswith("Z"))
    except Exception:
        pass
    return result


def diagnose_venv() -> list[dict]:
    issues = []
    venv_python = constants.VENV / "bin" / "python3"
    if not venv_python.exists():
        issues.append({
            "check": "venv",
            "severity": constants.CRITICAL,
            "error": "No Python venv found at operator/.venv — tools requiring openai/tenacity will fail",
        })
        return issues
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
                    "severity": constants.WARNING if pkg_norm != "openai" else constants.CRITICAL,
                    "error": f"Essential package '{pkg}' not installed in venv",
                    "suggested_fix": f"{venv_python} -m pip install {pkg}",
                })
    except Exception as e:
        issues.append({
            "check": "venv",
            "severity": constants.WARNING,
            "error": f"Could not check venv packages: {e}",
        })
    scripts_needing_venv = ["brain"]
    for script_name in scripts_needing_venv:
        script_path = constants.BIN / script_name
        if not script_path.exists():
            continue
        try:
            content = script_path.read_text()
            if ".venv" not in content and "venv" not in content:
                issues.append({
                    "check": "venv_activation",
                    "severity": constants.WARNING,
                    "error": f"bin/{script_name} does not activate venv — may miss dependencies",
                })
        except OSError:
            pass
    return issues
