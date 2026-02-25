#!/usr/bin/env python3
"""
Offline scorecard for research reports/projects (Continuous Eval).
Metrics: claim_support_rate, citation_precision, faithfulness, source_diversity, novelty_score.
Results written to project eval/ and optionally to Memory quality_scores.

Usage:
  research_eval.py <project_id>
  research_eval.py --all   (all done projects)
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, research_root, load_project


def _scorecard(project_id: str) -> dict:
    proj = project_dir(project_id)
    if not proj.exists():
        return {"error": f"Project not found: {project_id}"}
    project = load_project(proj)
    out = {
        "project_id": project_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claim_support_rate": 0.0,
        "citation_precision": 0.0,
        "faithfulness": 0.0,
        "source_diversity": 0.0,
        "novelty_score": 0.0,
    }
    verify = proj / "verify"
    # claim_support_rate: primary = claim_ledger.json (is_verified); fallback = claim_verification.json (verified) for projects without ledger
    used_ledger = False
    if (verify / "claim_ledger.json").exists():
        try:
            ledger = json.loads((verify / "claim_ledger.json").read_text())
            claims = ledger.get("claims", [])
            if claims:
                supported = sum(1 for c in claims if c.get("is_verified"))
                out["claim_support_rate"] = round(supported / len(claims), 3)
            used_ledger = True
        except Exception:
            pass
    if not used_ledger and (verify / "claim_verification.json").exists():
        try:
            cv = json.loads((verify / "claim_verification.json").read_text())
            claims = cv.get("claims", [])
            if claims:
                supported = sum(1 for c in claims if c.get("verified"))
                out["claim_support_rate"] = round(supported / len(claims), 3)
        except Exception:
            pass
    # citation_precision: share of sources with reliability >= 0.6
    if (verify / "source_reliability.json").exists():
        try:
            rel = json.loads((verify / "source_reliability.json").read_text())
            sources = rel.get("sources", [])
            if sources:
                reliable = sum(1 for s in sources if (s.get("reliability_score") or 0) >= 0.6)
                out["citation_precision"] = round(reliable / len(sources), 3)
        except Exception:
            pass
    # source_diversity: distinct domains (from URLs), normalized 0-1 (cap at 10 sources = 1)
    sources_dir = proj / "sources"
    if sources_dir.exists():
        urls = set()
        for f in sources_dir.glob("*.json"):
            if f.name.endswith("_content.json"):
                continue
            try:
                d = json.loads(f.read_text())
                u = (d.get("url") or "").strip()
                if u:
                    domain = u.split("/")[2] if "/" in u else u
                    urls.add(domain)
            except Exception:
                pass
        out["source_diversity"] = round(min(1.0, len(urls) / 10.0), 3)
    # faithfulness: heuristic - has report and verify data
    reports_dir = proj / "reports"
    if reports_dir.exists() and list(reports_dir.glob("*.md")):
        out["faithfulness"] = round(out["claim_support_rate"] * 0.5 + out["citation_precision"] * 0.5, 3)
    # novelty_score: from number of findings / diversity
    findings_dir = proj / "findings"
    if findings_dir.exists():
        n_findings = len(list(findings_dir.glob("*.json")))
        out["novelty_score"] = round(min(1.0, n_findings / 20.0) * 0.5 + out["source_diversity"] * 0.5, 3)
    return out


def main():
    if len(sys.argv) < 2:
        print("Usage: research_eval.py <project_id> | research_eval.py --all", file=sys.stderr)
        sys.exit(2)
    arg = sys.argv[1]
    if arg == "--all":
        research = research_root()
        project_ids = [p.name for p in research.iterdir() if p.is_dir() and p.name.startswith("proj-")]
    else:
        project_ids = [arg]
    results = []
    for project_id in project_ids:
        card = _scorecard(project_id)
        if "error" in card:
            continue
        (project_dir(project_id) / "eval").mkdir(parents=True, exist_ok=True)
        out_path = project_dir(project_id) / "eval" / "scorecard_latest.json"
        out_path.write_text(json.dumps(card, indent=2))
        results.append(card)
        # Optionally record to Memory quality_scores (overall score = average of metrics)
        try:
            from lib.memory import Memory
            mem = Memory()
            avg = (card["claim_support_rate"] + card["citation_precision"] + card["faithfulness"] +
                   card["source_diversity"] + card["novelty_score"]) / 5.0
            mem.record_quality(
                job_id=f"eval-{project_id}",
                score=round(avg, 3),
                workflow_id="research-eval",
                dimension="research_scorecard",
                notes=json.dumps(card)[:500],
            )
            mem.close()
        except Exception:
            pass
    print(json.dumps({"scorecards": results}, indent=2))


if __name__ == "__main__":
    main()
