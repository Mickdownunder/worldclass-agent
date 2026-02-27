#!/usr/bin/env python3
"""
AEM: Contradiction linking in operational flow. After ledger is ready, run contradiction detection
(source-level), map source_a/source_b to claim_refs via supporting_source_ids, and call add_contradiction.
Ensures contradiction_review_required is enforceable in settlement (market scoring blocks PASS_STABLE).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl, add_contradiction
from tools.research_reason import contradiction_detection


def _claim_ref(c: dict) -> str:
    return f"{c.get('claim_id', '')}@{c.get('claim_version', 1)}"


def _source_to_claim_refs(claims: list[dict]) -> dict[str, list[str]]:
    """Map source url (or title used as key) -> list of claim_ref that cite it (supporting_source_ids)."""
    out: dict[str, list[str]] = {}
    for c in claims:
        ref = _claim_ref(c)
        for sid in c.get("supporting_source_ids") or []:
            key = (sid if isinstance(sid, str) else str(sid)).strip()
            if not key:
                continue
            if key not in out:
                out[key] = []
            if ref not in out[key]:
                out[key].append(ref)
    return out


def _normalize_source_key(url_or_title: str) -> str:
    return (url_or_title or "").strip().lower()[:200]


def run_contradiction_linking(project_id: str) -> dict:
    """
    Run reason.contradiction_detection, map (source_a, source_b) to claim pairs, add_contradiction for each.
    Returns { "ok": True, "links_added": N, "contradictions_processed": M }.
    """
    proj_path = project_dir(project_id)
    project = load_project(proj_path)
    claims = load_ledger_jsonl(proj_path)
    if not claims:
        return {"ok": True, "links_added": 0, "contradictions_processed": 0}
    source_to_refs = _source_to_claim_refs(claims)
    # Also build by normalized url/title for matching reason output (source_a, source_b)
    by_norm: dict[str, list[str]] = {}
    for k, refs in source_to_refs.items():
        n = _normalize_source_key(k)
        if n not in by_norm:
            by_norm[n] = []
        for r in refs:
            if r not in by_norm[n]:
                by_norm[n].append(r)
    try:
        result = contradiction_detection(proj_path, project, project_id=project_id)
    except Exception as e:
        audit_log(proj_path, "aem_contradiction_linking_error", {"error": str(e)})
        return {"ok": False, "links_added": 0, "contradictions_processed": 0, "error": str(e)}
    contradictions = result.get("contradictions") or []
    links_added = 0
    for cont in contradictions:
        sa = _normalize_source_key(cont.get("source_a") or cont.get("source_a_url") or "")
        sb = _normalize_source_key(cont.get("source_b") or cont.get("source_b_url") or "")
        refs_a = by_norm.get(sa) or source_to_refs.get(sa) or []
        refs_b = by_norm.get(sb) or source_to_refs.get(sb) or []
        # Match by url substring if exact norm not found
        if not refs_a and sa:
            for k, refs in by_norm.items():
                if sa in k or k in sa:
                    refs_a = refs
                    break
        if not refs_b and sb:
            for k, refs in by_norm.items():
                if sb in k or k in sb:
                    refs_b = refs
                    break
        strength = 0.7  # default
        for ra in refs_a:
            for rb in refs_b:
                if ra == rb:
                    continue
                try:
                    add_contradiction(project_id, ra, rb, contradiction_strength=strength)
                    links_added += 1
                except Exception:
                    pass
    audit_log(proj_path, "aem_contradiction_linking", {"links_added": links_added, "contradictions_processed": len(contradictions)})
    return {"ok": True, "links_added": links_added, "contradictions_processed": len(contradictions)}


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_contradiction_linking.py run <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    if cmd != "run":
        print("Unknown command: use run", file=sys.stderr)
        sys.exit(2)
    out = run_contradiction_linking(project_id)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
