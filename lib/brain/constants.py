"""Paths and constants for the cognitive core."""
import os
from pathlib import Path

BASE = Path(os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator")))
CONF = BASE / "conf"
JOBS = BASE / "jobs"
WORKFLOWS = BASE / "workflows"
KNOWLEDGE = BASE / "knowledge"
FACTORY = BASE / "factory"
RESEARCH = BASE / "research"

REFLECT_LLM_TIMEOUT_SEC = 90

GOVERNANCE_LEVELS = {
    0: "report_only",
    1: "suggest",
    2: "act_and_report",
    3: "full_autonomous",
}

_REFLECTION_GENERIC_OUTCOMES = (
    "job completed successfully",
    "execution completed without errors",
    "job status: done",
)
_REFLECTION_GENERIC_LEARNINGS_PREFIXES = ("metrik-basierte bewertung", "key takeaway for future")
_REFLECTION_FAILURE_KEYWORDS = ("fail", "failed", "error", "timeout", "exception", "crash", "rollback")
