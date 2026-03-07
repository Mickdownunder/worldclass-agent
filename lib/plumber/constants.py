# Plumber constants: paths, limits, severity, non-repairable patterns, trusted packages, LLM flags.
from __future__ import annotations

import os
import re
from pathlib import Path

BASE = Path(os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator")))
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

CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

FINGERPRINT_DB = PLUMBER_DIR / "fingerprints.json"
COOLDOWN_HOURS = 6
MAX_FIX_ATTEMPTS_PER_FINGERPRINT = 3

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

TRUSTED_PACKAGES = {
    "jsonschema", "tenacity", "openai", "requests", "beautifulsoup4",
    "bs4", "lxml", "weasyprint", "markdown", "pyyaml", "httpx",
    "google-genai", "pillow", "chardet", "cssselect", "cssselect2",
    "fonttools", "brotli", "pytest", "python-dateutil",
}

LLM_FIX_ENABLED = os.environ.get("PLUMBER_LLM_FIX", "0") in ("1", "true", "yes")
LLM_FIX_MAX_DIFF_LINES = 50
LLM_FIX_MAX_ATTEMPTS_PER_FILE = 1
LLM_FIX_MODEL = os.environ.get("PLUMBER_LLM_MODEL", "codex-5.3")
