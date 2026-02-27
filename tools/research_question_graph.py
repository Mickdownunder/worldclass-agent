#!/usr/bin/env python3
"""
AEM: Question Graph — questions as primary optimization unit.
Writes research/proj-*/questions/questions.json.

Schema (INTELLIGENCE_PER_TOKEN §4 + spec):
  question_id, text, state (open|narrowed|partially_resolved|resolved|reopened),
  decision_relevance, uncertainty { measurement, mechanism, external_validity, temporal },
  evidence_gap_score, linked_claims, last_updated

Usage:
  research_question_graph.py build <project_id>
  research_question_graph.py get <project_id>   # print questions.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log

QUESTIONS_DIR = "questions"
QUESTIONS_FILENAME = "questions.json"
QUESTION_STATES = {"open", "narrowed", "partially_resolved", "resolved", "reopened"}


def _question_id_from_text(text: str) -> str:
    import hashlib
    h = hashlib.sha256((text or "").strip().encode()).hexdigest()[:12]
    return f"q-{h}"


def build_question_graph(project_id: str) -> dict:
    """
    Build question graph from project.json (main question) and optional sub-questions from findings.
    Returns dict with "questions" list; each question has required schema fields.
    """
    proj_path = project_dir(project_id)
    project = load_project(proj_path)
    question_text = (project.get("question") or "").strip()
    if not question_text:
        return {"questions": [], "version": "v1"}

    # Single primary question from project (v1: one question per project)
    q_id = _question_id_from_text(question_text)
    uncertainty = {
        "measurement": 0.5,
        "mechanism": 0.5,
        "external_validity": 0.5,
        "temporal": 0.5,
    }
    linked_claims: list[str] = []
    # Link claims from claims/ledger.jsonl or verify/claim_ledger.json if present
    ledger = proj_path / "claims" / "ledger.jsonl"
    if ledger.exists():
        for line in ledger.read_text().strip().splitlines():
            if not line.strip():
                continue
            try:
                c = json.loads(line)
                cid = c.get("claim_id")
                if cid:
                    linked_claims.append(cid)
            except json.JSONDecodeError:
                continue
    else:
        verify_ledger = proj_path / "verify" / "claim_ledger.json"
        if verify_ledger.exists():
            try:
                data = json.loads(verify_ledger.read_text())
                for c in data.get("claims", []):
                    if c.get("claim_id"):
                        linked_claims.append(c["claim_id"])
            except Exception:
                pass

    evidence_gap_score = 0.5
    findings_dir = proj_path / "findings"
    if findings_dir.exists():
        count = len(list(findings_dir.glob("*.json")))
        if count >= 10:
            evidence_gap_score = 0.2
        elif count >= 5:
            evidence_gap_score = 0.4

    state = "open"
    if linked_claims:
        state = "partially_resolved"
    if evidence_gap_score <= 0.2 and linked_claims:
        state = "narrowed"

    question = {
        "question_id": q_id,
        "text": question_text[:2000],
        "state": state,
        "decision_relevance": 0.8,
        "uncertainty": uncertainty,
        "evidence_gap_score": round(evidence_gap_score, 4),
        "linked_claims": linked_claims[:500],
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = {"questions": [question], "version": "v1"}

    # Migrate legacy init-schema (open/answered) to AEM schema for backward compatibility
    q_path = proj_path / QUESTIONS_DIR / QUESTIONS_FILENAME
    if q_path.exists():
        try:
            existing = json.loads(q_path.read_text(encoding="utf-8"))
            if "open" in existing and "questions" not in existing:
                for q_text in existing.get("open", []):
                    if isinstance(q_text, str) and q_text.strip():
                        sub_q = {
                            "question_id": _question_id_from_text(q_text),
                            "text": q_text.strip()[:2000],
                            "state": "open",
                            "decision_relevance": 0.6,
                            "uncertainty": {"measurement": 0.5, "mechanism": 0.5, "external_validity": 0.5, "temporal": 0.5},
                            "evidence_gap_score": 0.5,
                            "linked_claims": [],
                            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                        out["questions"].append(sub_q)
            # Preserve open/answered keys for backward compat with feedback.py
            if "open" in existing:
                out["open"] = existing["open"]
            if "answered" in existing:
                out["answered"] = existing["answered"]
        except (json.JSONDecodeError, OSError):
            pass

    return out


def ensure_questions_dir(proj_path: Path) -> Path:
    d = proj_path / QUESTIONS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_question_graph(project_id: str, graph: dict | None = None) -> Path:
    if graph is None:
        graph = build_question_graph(project_id)
    proj_path = project_dir(project_id)
    ensure_questions_dir(proj_path)
    path = proj_path / QUESTIONS_DIR / QUESTIONS_FILENAME
    path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    audit_log(proj_path, "aem_question_graph_written", {"questions_count": len(graph.get("questions", []))})
    return path


def get_question_graph(project_id: str) -> dict:
    path = project_dir(project_id) / QUESTIONS_DIR / QUESTIONS_FILENAME
    if not path.exists():
        return {"questions": [], "version": "v1"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"questions": [], "version": "v1"}


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_question_graph.py build|get <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "build":
        graph = build_question_graph(project_id)
        write_question_graph(project_id, graph)
        print(json.dumps({"ok": True, "questions_count": len(graph.get("questions", []))}))
    elif cmd == "get":
        print(json.dumps(get_question_graph(project_id), indent=2))
    else:
        print("Unknown command: use build|get", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
