"""Load prior knowledge, questions, and research_mode from project dir."""
import json
from pathlib import Path

from tools.research_common import research_root


def load_prior_knowledge_and_questions(project_id: str) -> tuple[str, str, str]:
    """Load optional prior_knowledge.json, questions.json, and get research_mode from project.json.
    Returns (prior_snippet, questions_snippet, research_mode)."""
    prior_snippet = ""
    questions_snippet = ""
    research_mode = "standard"
    if not project_id:
        return prior_snippet, questions_snippet, research_mode
    root = research_root() / project_id

    try:
        p_path = root / "project.json"
        if p_path.exists():
            data = json.loads(p_path.read_text(encoding="utf-8", errors="replace"))
            research_mode = data.get("config", {}).get("research_mode", "standard")
    except Exception:
        pass

    try:
        pk_path = root / "prior_knowledge.json"
        if pk_path.exists():
            data = json.loads(pk_path.read_text(encoding="utf-8", errors="replace"))
            principles = data.get("principles") or []
            findings = data.get("findings") or []
            parts = []
            if principles:
                parts.append("Principles: " + "; ".join((p.get("description") or "")[:200] for p in principles[:5]))
            lateral = data.get("lateral_principles") or []
            if lateral:
                parts.append("Cross-Domain Inspiration (Lateral Thinking): " + "; ".join((p.get("description") or "")[:200] for p in lateral))
            if findings:
                parts.append("Prior findings: " + "; ".join((f.get("preview") or "")[:150] for f in findings[:8]))
            if parts:
                prior_snippet = "\nPrior knowledge (use to align queries): " + " ".join(parts)[:1200]
    except Exception:
        pass
    try:
        q_path = root / "questions" / "questions.json"
        if q_path.exists():
            data = json.loads(q_path.read_text(encoding="utf-8", errors="replace"))
            questions = data.get("questions") or []
            if questions:
                q_lines = [f"- {(q.get('text') or '')[:120]} (uncertainty: {q.get('uncertainty') or {}})" for q in questions[:10]]
                questions_snippet = "\nSub-questions / uncertainty (consider in plan):\n" + "\n".join(q_lines)[:800]
    except Exception:
        pass
    return prior_snippet, questions_snippet, research_mode


def research_mode_for_project(project_id: str) -> str:
    """Read config.research_mode from project.json; return 'standard' if missing."""
    if not project_id:
        return "standard"
    p = research_root() / project_id / "project.json"
    if not p.exists():
        return "standard"
    try:
        data = json.loads(p.read_text())
        mode = (data.get("config") or {}).get("research_mode") or "standard"
        return str(mode).strip().lower()
    except Exception:
        return "standard"
