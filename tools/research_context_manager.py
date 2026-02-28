#!/usr/bin/env python3
"""
Within-run working memory for research conductor: semantic compression.
After each read batch, summarize new findings into compressed context (~500 tokens).
Pass compressed context to next decision; no raw findings in conductor state.

Usage:
  research_context_manager.py add <project_id>   # compress latest findings and append
  research_context_manager.py get <project_id>   # print current compressed context (for conductor)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, llm_call

TARGET_TOKENS = 500
APPROX_CHARS_PER_TOKEN = 4
MAX_SUMMARY_CHARS = TARGET_TOKENS * APPROX_CHARS_PER_TOKEN  # ~2000 chars


def _load_findings_since(proj: Path, since_ts: str | None) -> list[dict]:
    """Load findings from project; if since_ts given, only those modified after (from audit or file mtime)."""
    findings_dir = proj / "findings"
    if not findings_dir.exists():
        return []
    out = []
    for f in sorted(findings_dir.glob("*.json")):
        if "_content" in f.name:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(d, dict):
                out.append(d)
        except Exception:
            pass
    return out


def _findings_to_text(findings: list[dict], max_chars: int = 12000) -> str:
    """Serialize findings to text for LLM summarization."""
    parts = []
    for i, f in enumerate(findings[:80]):
        title = (f.get("title") or "")[:200]
        excerpt = (f.get("excerpt") or f.get("text") or "")[:600]
        url = (f.get("url") or "")[:120]
        parts.append(f"[{i+1}] {title}\nURL: {url}\n{excerpt}")
        if sum(len(p) for p in parts) >= max_chars:
            break
    return "\n\n".join(parts)[:max_chars]


def compress_findings(project_id: str, findings_text: str, project_id_for_budget: str = "") -> str:
    """Summarize findings into ~500-token compressed context. Returns summary string."""
    model = os.environ.get("RESEARCH_CONTEXT_MODEL", "gemini-2.5-flash")
    system = """You are a research context compressor. Summarize the following findings into a single concise summary.
Keep only: key facts, main sources, gaps or contradictions noted. No raw quotes. Target ~500 tokens (about 2000 characters).
Output only the summary text, no JSON."""
    user = f"Findings:\n{findings_text[:16000]}\n\nProvide a concise summary (~500 tokens)."
    try:
        result = llm_call(model, system, user, project_id=project_id_for_budget or project_id)
        text = (result.text or "").strip()
        return text[:MAX_SUMMARY_CHARS * 2]  # allow a bit over
    except Exception:
        return findings_text[:MAX_SUMMARY_CHARS]  # fallback: truncate


def add_compressed_batch(project_id: str) -> str:
    """Load latest findings, compress, append to conductor_context.json. Returns new compressed snippet."""
    proj = project_dir(project_id)
    findings = _load_findings_since(proj, None)
    if not findings:
        return get_compressed_context(project_id) or ""
    text = _findings_to_text(findings)
    summary = compress_findings(project_id, text)
    # Append to stored context (keep last N summaries to stay within ~500 tokens total for next decision)
    context_path = proj / "conductor_context.json"
    data: dict[str, Any] = {"summaries": [], "updated_at": ""}
    if context_path.exists():
        try:
            data = json.loads(context_path.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(data.get("summaries"), list):
                data["summaries"] = []
        except Exception:
            data = {"summaries": [], "updated_at": ""}
    from datetime import datetime, timezone
    data["summaries"].append({"ts": datetime.now(timezone.utc).isoformat(), "summary": summary})
    # Keep only last 3 summaries to avoid unbounded growth
    data["summaries"] = data["summaries"][-3:]
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["full_compressed"] = "\n\n".join(s.get("summary", "") for s in data["summaries"])
    context_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data["full_compressed"][:MAX_SUMMARY_CHARS]


def get_compressed_context(project_id: str) -> str:
    """Return current compressed context for conductor (within-run working memory)."""
    proj = project_dir(project_id)
    context_path = proj / "conductor_context.json"
    if not context_path.exists():
        return ""
    try:
        data = json.loads(context_path.read_text(encoding="utf-8", errors="replace"))
        raw = data.get("full_compressed") or "\n".join(s.get("summary", "") for s in data.get("summaries", []))
        return raw[:MAX_SUMMARY_CHARS]
    except Exception:
        return ""


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_context_manager.py <add|get> <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1].lower()
    project_id = sys.argv[2]
    proj = project_dir(project_id)
    if not proj.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "add":
        out = add_compressed_batch(project_id)
        print(out[:4000])
    elif cmd == "get":
        out = get_compressed_context(project_id)
        print(out)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
