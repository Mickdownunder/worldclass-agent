#!/usr/bin/env python3
"""
AEM: Evidence index — research/proj-*/evidence/evidence_index.jsonl.
Required fields: source_cluster_id, independence_score, primary_source_flag, evidence_scope,
scope_overlap_score, directness_score, method_rigor_score, conflict_of_interest_flag.
Built from findings + sources + verify (source_reliability); used by portfolio scoring and scope/contradiction logic.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl

EVIDENCE_DIR = "evidence"
EVIDENCE_INDEX_FILENAME = "evidence_index.jsonl"
SCOPE_KEYS = ("population", "geography", "timeframe", "domain")


def _default_evidence_scope() -> dict:
    return {"population": "", "geography": "", "timeframe": "", "domain": ""}


def _source_cluster_id(url: str, domain_hint: str = "") -> str:
    """Cluster by domain for independence; same domain => same cluster."""
    try:
        domain = url.split("/")[2].replace("www.", "") if "://" in url else url[:20]
    except Exception:
        domain = domain_hint or "unknown"
    h = hashlib.sha256(domain.encode()).hexdigest()[:10]
    return f"sc-{h}"


def _scope_overlap(claim_scope: dict, evidence_scope: dict) -> float:
    """Fraction of scope keys where both non-empty and values overlap (match or substring). 0 if no keys filled."""
    claim_scope = claim_scope or {}
    evidence_scope = evidence_scope or {}
    total, match = 0, 0
    for k in SCOPE_KEYS:
        cv = (claim_scope.get(k) or "").strip()
        ev = (evidence_scope.get(k) or "").strip()
        if not cv and not ev:
            continue
        total += 1
        if cv and ev and (cv.lower() == ev.lower() or cv.lower() in ev.lower() or ev.lower() in cv.lower()):
            match += 1
        elif not cv or not ev:
            match += 0  # one side empty => no overlap for that key
    return round(match / total, 4) if total else 0.0


def build_evidence_index(project_id: str) -> list[dict]:
    """
    Build evidence_index.jsonl from findings, sources, verify/source_reliability.
    One line per evidence item (per finding or per source with content). Required fields present.
    """
    proj_path = project_dir(project_id)
    project = load_project(proj_path)
    domain = (project.get("domain") or "").strip() or "general"
    rel_by_url: dict[str, float] = {}
    verify_rel = proj_path / "verify" / "source_reliability.json"
    if verify_rel.exists():
        try:
            rel = json.loads(verify_rel.read_text())
            for s in rel.get("sources", []):
                u = (s.get("url") or "").strip()
                if u:
                    rel_by_url[u] = float(s.get("reliability_score", 0.5))
        except Exception:
            pass
    evidence_list: list[dict] = []
    seen_urls: set[str] = set()
    # From findings
    for f in sorted((proj_path / "findings").glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        url = (d.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        cluster = _source_cluster_id(url)
        evidence_list.append({
            "evidence_id": f"e-{hashlib.sha256((url + f.stem).encode()).hexdigest()[:12]}",
            "source_url": url,
            "source_type": (d.get("source_type") or "primary").strip().lower() if d.get("source_type") else "primary",
            "source_cluster_id": cluster,
            "independence_score": 0.7,  # Default; same cluster => lower independence when we have multiple from same domain
            "primary_source_flag": (d.get("source_type") or "primary").strip().lower() == "primary",
            "evidence_scope": _default_evidence_scope(),
            "scope_overlap_score": 0.0,  # Filled when linked to claim
            "directness_score": 0.6,
            "method_rigor_score": 0.5,
            "conflict_of_interest_flag": False,
            "reliability_score": rel_by_url.get(url, 0.5),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    # From sources (no _content) not already in findings
    for s in sorted((proj_path / "sources").glob("*.json")):
        if "_content" in s.name:
            continue
        try:
            d = json.loads(s.read_text())
        except Exception:
            continue
        url = (d.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        cluster = _source_cluster_id(url)
        evidence_list.append({
            "evidence_id": f"e-{hashlib.sha256((url + s.stem).encode()).hexdigest()[:12]}",
            "source_url": url,
            "source_type": "secondary",
            "source_cluster_id": cluster,
            "independence_score": 0.5,
            "primary_source_flag": False,
            "evidence_scope": _default_evidence_scope(),
            "scope_overlap_score": 0.0,
            "directness_score": 0.4,
            "method_rigor_score": 0.5,
            "conflict_of_interest_flag": False,
            "reliability_score": rel_by_url.get(url, 0.5),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    # Claim/evidence scope overlap and independence from ledger
    claims = load_ledger_jsonl(proj_path)
    url_to_refs: dict[str, list[dict]] = {}
    for c in claims:
        scope = c.get("claim_scope") or _default_evidence_scope()
        for sid in c.get("supporting_source_ids") or []:
            url = (sid if isinstance(sid, str) else str(sid)).strip()
            if not url:
                continue
            if url not in url_to_refs:
                url_to_refs[url] = []
            url_to_refs[url].append(scope)
    for e in evidence_list:
        url = e.get("source_url") or ""
        scopes = url_to_refs.get(url) or url_to_refs.get(url.strip()) or []
        if scopes:
            overlaps = [_scope_overlap(s, e.get("evidence_scope") or _default_evidence_scope()) for s in scopes]
            e["scope_overlap_score"] = round(max(overlaps), 4) if overlaps else 0.0
    cluster_counts: dict[str, int] = {}
    for e in evidence_list:
        cid = e.get("source_cluster_id") or ""
        cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
    for e in evidence_list:
        cid = e.get("source_cluster_id") or ""
        n = cluster_counts.get(cid, 1)
        base = e.get("independence_score", 0.7)
        e["independence_score"] = round(max(0.2, base - 0.1 * (n - 1)), 4)
    # Persist
    (proj_path / EVIDENCE_DIR).mkdir(parents=True, exist_ok=True)
    path = proj_path / EVIDENCE_DIR / EVIDENCE_INDEX_FILENAME
    lines = [json.dumps(e, ensure_ascii=False) for e in evidence_list]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    audit_log(proj_path, "aem_evidence_index_built", {"evidence_count": len(evidence_list)})
    return evidence_list


def load_evidence_index(proj_path: Path) -> list[dict]:
    path = proj_path / EVIDENCE_DIR / EVIDENCE_INDEX_FILENAME
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_evidence_index.py build <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "build":
        out = build_evidence_index(project_id)
        print(json.dumps({"ok": True, "evidence_count": len(out)}))
    else:
        print("Unknown command: use build", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
