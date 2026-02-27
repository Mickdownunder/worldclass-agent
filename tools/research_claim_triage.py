#!/usr/bin/env python3
"""
AEM: Claim triage — Top-K by impact; only Top-K enters deep AEM path.
Computes impact_score, decision_relevance, fragility_score, attack_surface_estimate.
Output: triaged list (sorted by impact); callers use top K for attack/settlement.

Usage:
  research_claim_triage.py run <project_id> [--top-k N]
  research_claim_triage.py scores <project_id>   # print scored claims as JSON
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl, load_verify_ledger_claims

DEFAULT_TOP_K = 10


def _load_claims(project_id: str) -> list[dict]:
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    if not claims:
        verify = load_verify_ledger_claims(proj_path)
        claims = [{"claim_id": c.get("claim_id"), "text": c.get("text") or c.get("claim"), "is_verified": c.get("is_verified"), "supporting_source_ids": c.get("supporting_source_ids", [])} for c in verify]
    return claims


def _impact_score(claim: dict, question_graph: dict) -> float:
    """Heuristic: higher if verified, linked to question, longer text (more specific)."""
    score = 0.0
    if claim.get("is_verified"):
        score += 0.4
    if claim.get("state") == "stable":
        score += 0.2
    text_len = len((claim.get("text") or "").strip())
    if text_len > 200:
        score += 0.2
    elif text_len > 50:
        score += 0.1
    linked = sum(1 for q in question_graph.get("questions", []) for cid in q.get("linked_claims", []) if cid == claim.get("claim_id"))
    if linked:
        score += 0.2
    return min(1.0, round(score, 4))


def _decision_relevance(claim: dict, project: dict) -> float:
    """Placeholder: use question relevance from project or 0.5."""
    return 0.5


def _fragility_score(claim: dict) -> float:
    """Higher if few sources, has contradictions, or tentative."""
    fragility = 0.0
    sources = claim.get("supporting_source_ids") or []
    if len(sources) <= 1:
        fragility += 0.3
    if claim.get("contradicts"):
        fragility += 0.3
    if (claim.get("state") or "").lower() in ("tentative", "contested"):
        fragility += 0.2
    return min(1.0, round(fragility, 4))


def _attack_surface_estimate(claim: dict) -> float:
    """Heuristic: more surface if numeric/forecast claim, or long text."""
    text = (claim.get("text") or "").lower()
    surface = 0.2
    if any(w in text for w in ("percent", "%", "number", "rate", "growth", "will", "expect")):
        surface += 0.3
    if len(text) > 150:
        surface += 0.2
    return min(1.0, round(surface, 4))


def triage_claims(project_id: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Score all claims, sort by impact (desc), return list with scores attached.
    Each claim gets impact_score, decision_relevance, fragility_score, attack_surface_estimate.
    """
    proj_path = project_dir(project_id)
    project = load_project(proj_path)
    questions_path = proj_path / "questions" / "questions.json"
    question_graph = {"questions": []}
    if questions_path.exists():
        try:
            question_graph = json.loads(questions_path.read_text())
        except Exception:
            pass
    claims = _load_claims(project_id)
    scored = []
    for c in claims:
        impact = _impact_score(c, question_graph)
        rel = _decision_relevance(c, project)
        frag = _fragility_score(c)
        surface = _attack_surface_estimate(c)
        entry = {**c, "impact_score": impact, "decision_relevance": rel, "fragility_score": frag, "attack_surface_estimate": surface}
        scored.append(entry)
    scored.sort(key=lambda x: (x.get("impact_score", 0), x.get("fragility_score", 0)), reverse=True)
    top = scored[:top_k]
    audit_log(proj_path, "aem_claim_triage", {"total_claims": len(claims), "top_k": len(top)})
    return top


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_claim_triage.py run|scores <project_id> [--top-k N]", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    top_k = DEFAULT_TOP_K
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--top-k" and i + 1 < len(sys.argv):
            try:
                top_k = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "run":
        top = triage_claims(project_id, top_k=top_k)
        print(json.dumps({"ok": True, "triaged_count": len(top), "claim_ids": [c.get("claim_id") for c in top]}))
    elif cmd == "scores":
        top = triage_claims(project_id, top_k=top_k)
        print(json.dumps({"claims": top}, indent=2))
    else:
        print("Unknown command: use run|scores", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
