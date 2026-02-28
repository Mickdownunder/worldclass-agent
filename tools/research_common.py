#!/usr/bin/env python3
"""
Shared helpers for research tools: paths, secrets, project layout.
"""
import os
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LLMResult:
    """Result of an LLM call with token usage."""
    text: str
    input_tokens: int
    output_tokens: int

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
        if k.startswith("OPENAI_") or k in ("BRAVE_API_KEY", "SERPER_API_KEY", "JINA_API_KEY", "GEMINI_API_KEY", "NCBI_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"):
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
    # Gemini / google-genai: retry on rate limit, timeout, server errors (often wrapped or message-based)
    exc_module = type(exc).__module__
    if "genai" in exc_module or "google" in exc_module:
        msg = str(exc).lower()
        if any(x in msg for x in ("429", "503", "500", "502", "rate", "timeout", "resource", "overload")):
            return True
    from urllib.error import HTTPError
    if isinstance(exc, HTTPError) and getattr(exc, 'code', 0) in (429, 500, 502, 503):
        return True
    import socket
    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError)):
        return True
    return False


def _call_openai(model: str, system: str, user: str) -> LLMResult:
    """Call OpenAI API. Returns LLMResult."""
    from openai import OpenAI
    secrets = load_secrets()
    api_key = secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    resp = client.responses.create(model=model, instructions=system or "", input=user)
    text = (resp.output_text or "").strip()
    inp = getattr(resp.usage, "input_tokens", 0) or 0
    out = getattr(resp.usage, "output_tokens", 0) or 0
    return LLMResult(text=text, input_tokens=inp, output_tokens=out)


def _call_gemini(model: str, system: str, user: str) -> LLMResult:
    """Call Google Gemini API. Returns LLMResult."""
    from google import genai
    from google.genai.types import GenerateContentConfig
    secrets = load_secrets()
    api_key = secrets.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set — required for model " + model)
    client = genai.Client(api_key=api_key)
    config = GenerateContentConfig(system_instruction=system or "")
    response = client.models.generate_content(model=model, contents=user, config=config)
    text = (getattr(response, "text", None) or "").strip()
    usage = getattr(response, "usage_metadata", None)
    inp = 0
    out = 0
    if usage is not None:
        inp = getattr(usage, "prompt_token_count", None) or getattr(usage, "input_token_count", None) or 0
        out = getattr(usage, "candidates_token_count", None) or getattr(usage, "output_token_count", None) or 0
    if not isinstance(inp, int):
        inp = 0
    if not isinstance(out, int):
        out = 0
    return LLMResult(text=text, input_tokens=inp, output_tokens=out)


def llm_call(model: str, system: str, user: str, project_id: str = "") -> LLMResult:
    """Route to OpenAI (gpt-*) or Gemini (gemini-*) and optionally track budget. Uses llm_retry."""
    @llm_retry()
    def _invoke():
        if model.startswith("gemini"):
            return _call_gemini(model, system, user)
        return _call_openai(model, system, user)

    result = _invoke()
    if project_id:
        try:
            from tools.research_budget import track_usage
            track_usage(project_id, model, result.input_tokens, result.output_tokens)
        except Exception:
            pass
    return result


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


def get_claims_for_synthesis(proj_path: Path) -> list[dict]:
    """Unified claim list for synthesis: AEM claims/ledger.jsonl or fallback verify/claim_ledger.json. Spec §6.2."""
    claims_dir = proj_path / "claims"
    ledger_jsonl = claims_dir / "ledger.jsonl"
    if ledger_jsonl.exists():
        claims = []
        for line in ledger_jsonl.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            try:
                claims.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if claims:
            return claims
    verify_ledger = proj_path / "verify" / "claim_ledger.json"
    if verify_ledger.exists():
        try:
            data = json.loads(verify_ledger.read_text(encoding="utf-8"))
            return data.get("claims", [])
        except Exception:
            pass
    return []


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


def get_principles_for_research(question: str, domain: str | None = None, limit: int = 5) -> str:
    """Load strategic principles from Memory (Brain context) for use in research LLM prompts."""
    try:
        from lib.memory import Memory
        with Memory() as mem:
            if question and hasattr(mem, "retrieve_with_utility"):
                principles = mem.retrieve_with_utility(question, "principle", k=limit)
            else:
                principles = mem.list_principles(limit=limit, domain=domain or "")
        if not principles:
            return ""
        lines = []
        for p in principles:
            ptype = (p.get("principle_type") or "guiding").upper()
            desc = (p.get("description") or "")[:300]
            if desc:
                lines.append(f"- [{ptype}] {desc}")
        if not lines:
            return ""
        return "\n\nSTRATEGIC PRINCIPLES (follow guiding, avoid cautionary):\n" + "\n".join(lines)
    except Exception:
        return ""
