#!/usr/bin/env python3
"""
Post-process synthesized report: apply verified tags, deterministic References from claim_ledger,
claim_evidence_map, manifest. Used by research-cycle.sh and by Conductor after synthesize.

Usage:
  research_synthesize_postprocess.py <project_id> [artifacts_dir]
  If artifacts_dir is given, read report from artifacts_dir/report.md and write back there and to project.
  If omitted, read latest report_*.md from project reports/ and overwrite with processed version.
"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import get_claims_for_synthesis, project_dir
from tools.research_verify import apply_verified_tags_to_report


def _run(proj_dir: Path, art_dir: Path | None) -> bool:
    verify_dir = proj_dir / "verify"
    reports_dir = proj_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    verify_dir.mkdir(parents=True, exist_ok=True)

    report = ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if art_dir and (art_dir / "report.md").exists():
        report = (art_dir / "report.md").read_text(encoding="utf-8", errors="replace")
    else:
        reports = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            sys.stderr.write("No report to post-process.\n")
            return False
        report = reports[0].read_text(encoding="utf-8", errors="replace")
        ts = reports[0].stem.replace("report_", "").replace("_revised", "")
        if not ts or len(ts) < 8:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    claim_ledger = get_claims_for_synthesis(proj_dir)
    report = apply_verified_tags_to_report(report, claim_ledger)
    report = re.sub(
        r"\n---\s*\n\*?\*?(?:Sources|References)\*?\*?:?\s*\n.*",
        "",
        report,
        flags=re.DOTALL | re.IGNORECASE,
    ).rstrip()
    report = re.sub(
        r"\n#+\s*(?:Sources|References)\s*\n.*",
        "",
        report,
        flags=re.DOTALL | re.IGNORECASE,
    ).rstrip()

    ref_map = {}
    for fp in sorted((proj_dir / "findings").glob("*.json")):
        try:
            fd = json.loads(fp.read_text())
            fu = (fd.get("url") or "").strip()
            if fu and fu not in ref_map:
                ref_map[fu] = (fd.get("title") or "").strip()
        except Exception:
            pass
    for sp in sorted((proj_dir / "sources").glob("*.json")):
        if "_content" in sp.name:
            continue
        try:
            sd = json.loads(sp.read_text())
            su = (sd.get("url") or "").strip()
            if su and su not in ref_map:
                ref_map[su] = (sd.get("title") or "").strip()
        except Exception:
            pass

    cited_urls = set()
    for c in claim_ledger:
        for u in c.get("supporting_source_ids", []):
            cited_urls.add((u or "").strip())
    # Include all cited URLs; use ref_map for title when available
    refs = [(u, ref_map.get(u, "")) for u in cited_urls if u]
    refs.sort(key=lambda r: (r[1] or r[0]).lower())

    body_ok = len(report.strip()) >= 500
    if body_ok and refs:
        report += "\n\n---\n\n## References\n\n"
        for i, (url, title) in enumerate(refs, 1):
            if title:
                report += f"[{i}] {title}  \n    {url}\n\n"
            else:
                report += f"[{i}] {url}\n\n"

    if not body_ok:
        sys.stderr.write("WARN: Report body empty or too short — not saving.\n")
        return False

    report_filename = f"report_{ts}.md"
    (reports_dir / report_filename).write_text(report, encoding="utf-8")
    if art_dir:
        (art_dir / "report.md").write_text(report, encoding="utf-8")

    findings_by_url = {}
    for fp in sorted((proj_dir / "findings").glob("*.json")):
        try:
            fd = json.loads(fp.read_text())
            fu = (fd.get("url") or "").strip()
            if fu and fd.get("excerpt"):
                findings_by_url.setdefault(fu, fd["excerpt"][:500])
        except Exception:
            pass
    for sp in sorted((proj_dir / "sources").glob("*.json")):
        if "_content" in sp.name:
            continue
        try:
            sd = json.loads(sp.read_text())
            su = (sd.get("url") or "").strip()
            if su and su not in findings_by_url:
                snippet = (sd.get("description") or sd.get("title") or "")[:300]
                if snippet:
                    findings_by_url[su] = snippet
        except Exception:
            pass

    claim_evidence_map = {"report_id": report_filename, "ts": ts, "claims": []}
    for c in claim_ledger:
        evidence = []
        for src_url in c.get("supporting_source_ids", []):
            evidence.append({"url": src_url, "snippet": findings_by_url.get(src_url, "")})
        claim_evidence_map["claims"].append({
            "claim_id": c.get("claim_id"),
            "text": (c.get("text") or "")[:500],
            "is_verified": c.get("is_verified"),
            "verification_reason": c.get("verification_reason"),
            "supporting_source_ids": c.get("supporting_source_ids", []),
            "supporting_evidence": evidence,
        })
    (reports_dir / f"claim_evidence_map_{ts}.json").write_text(
        json.dumps(claim_evidence_map, indent=2), encoding="utf-8"
    )
    (verify_dir / "claim_evidence_map_latest.json").write_text(
        json.dumps(claim_evidence_map, indent=2), encoding="utf-8"
    )

    manifest_entries = []
    for rpt in sorted(reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime):
        name = rpt.name
        rpt_ts = name.replace("report_", "").replace("_revised", "").replace(".md", "")
        is_revised = "_revised" in name
        critique_score = None
        if (verify_dir / "critique.json").exists():
            try:
                critique_score = json.loads((verify_dir / "critique.json").read_text()).get("score")
            except Exception:
                pass
        manifest_entries.append({
            "filename": name,
            "generated_at": rpt_ts,
            "is_revised": is_revised,
            "quality_score": critique_score,
            "path": f"research/{proj_dir.name}/reports/{name}",
            "is_final": False,
        })
    if manifest_entries:
        manifest_entries[-1]["is_final"] = True
    (reports_dir / "manifest.json").write_text(
        json.dumps({
            "project_id": proj_dir.name,
            "report_count": len(manifest_entries),
            "reports": manifest_entries,
            "pipeline": {
                "synthesis_model": os.environ.get("RESEARCH_SYNTHESIS_MODEL", "unknown"),
                "critique_model": os.environ.get("RESEARCH_CRITIQUE_MODEL", "unknown"),
                "verify_model": os.environ.get("RESEARCH_VERIFY_MODEL", "unknown"),
                "gate_thresholds": {
                    "hard_pass_verified_min": 5,
                    "soft_pass_verified_min": 3,
                    "review_zone_rate": 0.4,
                },
            },
        }, indent=2),
        encoding="utf-8",
    )
    return True


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: research_synthesize_postprocess.py <project_id> [artifacts_dir]\n")
        return 2
    project_id = sys.argv[1].strip()
    art_dir = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].strip() else None
    proj_dir = project_dir(project_id)
    if not proj_dir.exists():
        sys.stderr.write(f"Project not found: {project_id}\n")
        return 1
    ok = _run(proj_dir, art_dir)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
