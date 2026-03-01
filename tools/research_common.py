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


def model_for_lane(context: str) -> str:
    """
    Return LLM model for the current RESEARCH_GOVERNOR_LANE (cheap | mid | strong).
    context: "verify" | "synthesize" | "critic".
    When lane is unset, returns the default (strong) model for that context so behavior is unchanged.
    """
    lane = (os.environ.get("RESEARCH_GOVERNOR_LANE") or "").strip().lower()
    defaults = {
        "verify": {
            "strong": os.environ.get("RESEARCH_VERIFY_MODEL", "gemini-3.1-pro-preview"),
            "mid": os.environ.get("RESEARCH_VERIFY_MODEL_MID", "gemini-2.5-flash"),
            "cheap": os.environ.get("RESEARCH_VERIFY_MODEL_CHEAP", "gpt-4.1-mini"),
        },
        "synthesize": {
            "strong": os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gemini-3.1-pro-preview"),
            "mid": os.environ.get("RESEARCH_SYNTHESIS_MODEL_MID", "gemini-2.5-flash"),
            "cheap": os.environ.get("RESEARCH_SYNTHESIS_MODEL_CHEAP", "gpt-4.1-mini"),
        },
        "critic": {
            "strong": os.environ.get("RESEARCH_CRITIQUE_MODEL", "gpt-5.2"),
            "mid": os.environ.get("RESEARCH_CRITIQUE_MODEL_MID", "gemini-2.5-flash"),
            "cheap": os.environ.get("RESEARCH_CRITIQUE_MODEL_CHEAP", "gpt-4.1-mini"),
        },
    }
    maps = defaults.get(context, defaults["verify"])
    if lane == "cheap":
        return maps["cheap"]
    if lane == "mid":
        return maps["mid"]
    return maps["strong"]


def _is_quota_or_bottleneck(exc) -> bool:
    """True if error is quota/429 so we may try another provider (when RESEARCH_LLM_FALLBACK_ON_QUOTA=1)."""
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    if "429" in msg or "insufficient_quota" in msg or "quota exceeded" in msg or "you exceeded your current quota" in msg:
        return True
    return False


def _is_retryable(exc):
    """Return True for transient errors that should be retried (rate-limit, timeout, server errors).
    Returns False for quota exceeded (retrying won't help; fail fast so logs show clear reason)."""
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    if "insufficient_quota" in msg or "quota exceeded" in msg or "you exceeded your current quota" in msg:
        return False
    try:
        from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
        if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)):
            return True
    except ImportError:
        pass
    # Gemini / google-genai: retry on rate limit, timeout, server errors (often wrapped or message-based)
    exc_module = type(exc).__module__
    if "genai" in exc_module or "google" in exc_module:
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


def _fallback_model_for_quota(primary_model: str) -> str | None:
    """Return an alternative model on another provider when primary hits quota. None if no fallback available."""
    secrets = load_secrets()
    has_openai = bool(secrets.get("OPENAI_API_KEY"))
    has_gemini = bool(secrets.get("GEMINI_API_KEY"))
    if primary_model.startswith("gemini"):
        if has_openai:
            return os.environ.get("RESEARCH_LLM_FALLBACK_OPENAI", "gpt-4.1-mini")
        return None
    if primary_model.startswith("gpt-") or "openai" in primary_model.lower():
        if has_gemini:
            return os.environ.get("RESEARCH_LLM_FALLBACK_GEMINI", "gemini-2.5-flash")
        return None
    return None


def _llm_invoke(model: str, system: str, user: str) -> LLMResult:
    """Single provider call: Gemini or OpenAI by model prefix."""
    if model.startswith("gemini"):
        return _call_gemini(model, system, user)
    return _call_openai(model, system, user)


def llm_call(model: str, system: str, user: str, project_id: str = "") -> LLMResult:
    """Route to OpenAI (gpt-*) or Gemini (gemini-*) and optionally track budget. Uses llm_retry.
    When RESEARCH_LLM_FALLBACK_ON_QUOTA=1 and the primary provider returns quota/429, tries once with
    the other provider (fallback model) so the system continues without manual intervention."""
    import sys

    @llm_retry()
    def _invoke_primary():
        return _llm_invoke(model, system, user)

    used_model = model
    try:
        result = _invoke_primary()
    except Exception as e:
        fallback_enabled = os.environ.get("RESEARCH_LLM_FALLBACK_ON_QUOTA", "").strip() in ("1", "true", "yes")
        if not fallback_enabled or not _is_quota_or_bottleneck(e):
            raise
        fallback = _fallback_model_for_quota(model)
        if not fallback:
            raise
        print(
            f"research_common: provider fallback (quota/429) {model} -> {fallback}",
            file=sys.stderr,
        )
        try:
            result = _llm_invoke(fallback, system, user)
            used_model = fallback
        except Exception:
            raise e  # reraise original so caller sees quota, not fallback error

    if project_id:
        try:
            from tools.research_budget import track_usage
            track_usage(project_id, used_model, result.input_tokens, result.output_tokens)
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
                principles = mem.retrieve_with_utility(question, "principle", k=limit, context_key=question)
            else:
                principles = mem.list_principles(limit=limit, domain=domain or "")
        if not principles:
            return ""
        lines = []
        for p in principles:
            ptype = (p.get("principle_type") or "guiding").upper()
            if ptype == "SYSTEM_PROMPT":
                continue # System prompts are handled separately now
            desc = (p.get("description") or "")[:300]
            if desc:
                lines.append(f"- [{ptype}] {desc}")
        if not lines:
            return ""
        return "\n\nSTRATEGIC PRINCIPLES (follow guiding, avoid cautionary):\n" + "\n".join(lines)
    except Exception:
        return ""

def get_optimized_system_prompt(domain: str, default_prompt: str) -> str:
    """
    Returns the active optimized system prompt for the domain if one exists in the versioned ledger.
    Otherwise, returns the default_prompt.
    """
    try:
        versions_file = operator_root() / "memory" / "prompt_versions.json"
        if not versions_file.exists():
            return default_prompt
            
        versions = json.loads(versions_file.read_text())
        active = [v for v in versions if v.get("domain") == domain and v.get("status") == "active"]
        
        if active:
            # Sort by created_at descending just in case there are multiple active (shouldn't happen)
            active.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            optimized = active[0].get("prompt_text", "").strip()
            if optimized:
                return optimized + "\n\n" + default_prompt
    except Exception:
        pass
    return default_prompt
