#!/usr/bin/env python3
"""
Within-run working memory for research conductor: loss-aware tiered compression.
- Critical: goal-relevant facts, gaps, contradictions — preserved with minimal compression.
- Summary: rest condensed aggressively. Aligns with report: do not merge/discard critical state.

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
# Reserve ~40% for critical (preserved), ~60% for summary (Report: protect critical state)
MAX_CRITICAL_CHARS = 800
MAX_SUMMARY_PART_CHARS = 1200


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


def compress_findings(project_id: str, findings_text: str, project_id_for_budget: str = "") -> tuple[str, str]:
    """Loss-aware tiered compression: critical (preserve) + summary (condensed). Returns (critical, summary)."""
    model = os.environ.get("RESEARCH_CONTEXT_MODEL", "gemini-2.5-flash")
    system = """You are a research context compressor. Output TWO sections. Do NOT merge or discard critical information.

Section 1 — CRITICAL (preserve; minimal compression):
- Facts directly relevant to the research goal.
- Gaps, contradictions, or key uncertainties.
- Source names/URLs that are essential.
Keep verbatim where it matters. Max ~200 tokens. Label: "CRITICAL:"

Section 2 — SUMMARY (condensed):
- Rest of content in a short summary. Max ~300 tokens. Label: "SUMMARY:"

Output format exactly:
CRITICAL:
 bullet points or short lines

SUMMARY:
 short paragraph(s)"""
    user = f"Findings:\n{findings_text[:16000]}\n\nProvide CRITICAL then SUMMARY."
    try:
        result = llm_call(model, system, user, project_id=project_id_for_budget or project_id)
        text = (result.text or "").strip()
        critical, summary = "", text
        if "CRITICAL:" in text and "SUMMARY:" in text:
            a, b = text.split("SUMMARY:", 1)
            critical = a.replace("CRITICAL:", "").strip()[:MAX_CRITICAL_CHARS * 2]
            summary = b.strip()[:MAX_SUMMARY_PART_CHARS * 2]
        elif "CRITICAL:" in text:
            critical = text.replace("CRITICAL:", "").strip()[:MAX_CRITICAL_CHARS * 2]
            summary = ""
        else:
            summary = text[:MAX_SUMMARY_PART_CHARS * 2]
        return critical, summary
    except Exception:
        return "", findings_text[:MAX_SUMMARY_PART_CHARS]


def add_compressed_batch(project_id: str) -> str:
    """Load latest findings, tiered compress (critical + summary), append. Returns full compressed context."""
    proj = project_dir(project_id)
    findings = _load_findings_since(proj, None)
    if not findings:
        return get_compressed_context(project_id) or ""
    text = _findings_to_text(findings)
    critical_part, summary_part = compress_findings(project_id, text)
    context_path = proj / "conductor_context.json"
    data: dict[str, Any] = {"summaries": [], "critical_snippets": [], "updated_at": ""}
    if context_path.exists():
        try:
            data = json.loads(context_path.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(data.get("summaries"), list):
                data["summaries"] = []
            if not isinstance(data.get("critical_snippets"), list):
                data["critical_snippets"] = []
        except Exception:
            data = {"summaries": [], "critical_snippets": [], "updated_at": ""}
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if critical_part:
        data["critical_snippets"].append({"ts": now_iso, "text": critical_part[:MAX_CRITICAL_CHARS]})
    data["critical_snippets"] = data["critical_snippets"][-2:]
    data["summaries"].append({"ts": now_iso, "summary": summary_part[:MAX_SUMMARY_PART_CHARS]})
    data["summaries"] = data["summaries"][-3:]
    data["updated_at"] = now_ts
    critical_block = "\n".join(s.get("text", "") for s in data["critical_snippets"]).strip()
    summary_block = "\n\n".join(s.get("summary", "") for s in data["summaries"]).strip()
    if critical_block:
        data["full_compressed"] = "Critical (preserved):\n" + critical_block[:MAX_CRITICAL_CHARS] + "\n\nSummary:\n" + summary_block[:MAX_SUMMARY_PART_CHARS]
    else:
        data["full_compressed"] = summary_block[:MAX_SUMMARY_CHARS]
    context_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data["full_compressed"][:MAX_SUMMARY_CHARS * 2]


def get_compressed_context(project_id: str) -> str:
    """Return current compressed context for conductor (within-run working memory)."""
    proj = project_dir(project_id)
    context_path = proj / "conductor_context.json"
    if not context_path.exists():
        return ""
    try:
        data = json.loads(context_path.read_text(encoding="utf-8", errors="replace"))
        raw = data.get("full_compressed") or "\n".join(s.get("summary", "") for s in data.get("summaries", []))
        # Allow slightly more when we have tiered content so critical + summary fit
        cap = MAX_SUMMARY_CHARS * 2 if data.get("critical_snippets") else MAX_SUMMARY_CHARS
        return raw[:cap]
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
