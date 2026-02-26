#!/usr/bin/env python3
"""
Shared helpers for research tools: paths, secrets, project layout.
"""
import os
import json
from pathlib import Path

def operator_root() -> Path:
    return Path(os.environ.get("OPERATOR_ROOT", Path.home() / "operator"))

def research_root() -> Path:
    return operator_root() / "research"

def project_dir(project_id: str) -> Path:
    return research_root() / project_id

def load_secrets() -> dict:
    secrets = {}
    conf = operator_root() / "conf" / "secrets.env"
    if conf.exists():
        for line in conf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k.startswith("OPENAI_") or k in ("BRAVE_API_KEY", "SERPER_API_KEY", "JINA_API_KEY"):
            secrets[k] = v
    return secrets

def ensure_project_layout(proj_path: Path) -> None:
    (proj_path / "findings").mkdir(parents=True, exist_ok=True)
    (proj_path / "sources").mkdir(parents=True, exist_ok=True)
    (proj_path / "reports").mkdir(parents=True, exist_ok=True)

def load_project(proj_path: Path) -> dict:
    pj = proj_path / "project.json"
    if not pj.exists():
        return {}
    return json.loads(pj.read_text())

def save_project(proj_path: Path, data: dict) -> None:
    (proj_path / "project.json").write_text(json.dumps(data, indent=2) + "\n")


def _is_retryable(exc):
    """Return True for transient errors that should be retried (rate-limit, timeout, server errors)."""
    try:
        from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
        if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)):
            return True
    except ImportError:
        pass
    from urllib.error import HTTPError
    if isinstance(exc, HTTPError) and getattr(exc, 'code', 0) in (429, 500, 502, 503):
        return True
    import socket
    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError)):
        return True
    return False


def llm_retry():
    """Decorator factory for LLM calls: 5 attempts, exponential backoff 2-60s."""
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        reraise=True,
    )


def api_retry():
    """Decorator factory for external API calls: 3 attempts, exponential backoff 1-15s."""
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        reraise=True,
    )


def audit_log(proj_path: Path, event: str, detail: dict | None = None) -> None:
    """Append a structured audit entry to the project's audit_log.jsonl."""
    from datetime import datetime, timezone
    log_file = proj_path / "audit_log.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
    }
    if detail:
        entry["detail"] = detail
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
