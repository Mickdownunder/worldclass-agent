#!/usr/bin/env python3
"""
Generate a deterministic abort report when the research pipeline fails.
No LLM calls — built entirely from existing project artifacts.

Usage:
  research_abort_report.py <project_id>
  Writes abort_report.md to the project's reports/ directory.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log


def _safe_json(path: Path) -> dict | list:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def generate_abort_report(project_id: str) -> str:
    proj = project_dir(project_id)
    if not proj.exists():
        return ""
    project = load_project(proj)
    question = project.get("question", "Unknown")
    status = project.get("status", "unknown")
    phase = project.get("phase", "unknown")
    spend = project.get("current_spend", 0.0)
    created = project.get("created_at", "")

    qg = project.get("quality_gate", {})
    eg = qg.get("evidence_gate", {})
    metrics = eg.get("metrics", {})
    reasons = eg.get("reasons", [])
    fail_code = eg.get("fail_code", status)

    sources_dir = proj / "sources"
    findings_dir = proj / "findings"
    verify_dir = proj / "verify"

    source_files = [f for f in sources_dir.glob("*.json") if not f.name.endswith("_content.json")] if sources_dir.exists() else []
    content_files = list(sources_dir.glob("*_content.json")) if sources_dir.exists() else []
    finding_files = list(findings_dir.glob("*.json")) if findings_dir.exists() else []

    read_attempts = metrics.get("read_attempts", 0)
    read_successes = metrics.get("read_successes", 0)
    read_failures = metrics.get("read_failures", 0)

    nonempty_content = 0
    for cf in content_files:
        try:
            d = json.loads(cf.read_text())
            if len((d.get("text") or "").strip()) > 50:
                nonempty_content += 1
        except Exception:
            pass

    sources_meta: list[dict] = []
    for sf in sorted(source_files, key=lambda f: f.name):
        try:
            d = json.loads(sf.read_text())
            sources_meta.append(d)
        except Exception:
            pass

    reliability: dict[str, float] = {}
    rel_file = verify_dir / "source_reliability.json"
    if rel_file.exists():
        try:
            rel = json.loads(rel_file.read_text())
            for s in rel.get("sources", []):
                url = (s.get("url") or "").strip()
                if url:
                    reliability[url] = s.get("reliability_score", 0.5)
        except Exception:
            pass

    claims_data: list[dict] = []
    ledger_file = verify_dir / "claim_ledger.json"
    if ledger_file.exists():
        try:
            claims_data = json.loads(ledger_file.read_text()).get("claims", [])
        except Exception:
            pass

    lines: list[str] = []
    lines.append(f"# Abort Report — {project_id}\n")
    lines.append(f"**Status:** `{status}` | **Phase:** `{phase}` | **Spend:** ${spend:.4f}")
    lines.append(f"**Created:** {created}")
    lines.append(f"**Fail Code:** `{fail_code}`\n")

    lines.append("## Research Question\n")
    lines.append(f"> {question}\n")

    lines.append("## Why It Failed\n")
    if reasons:
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append(f"- Pipeline stopped at phase `{phase}` with status `{status}`")
    lines.append("")

    FAIL_EXPLANATIONS = {
        "failed_insufficient_evidence": "Not enough findings or verified claims to produce a reliable report.",
        "failed_verification_inconclusive": "Claims could not be verified by 2+ independent sources.",
        "failed_reader_pipeline": "Content extraction failed for all sources.",
        "failed_reader_no_extractable_content": "No readable content could be extracted from any source.",
        "FAILED_BUDGET_EXCEEDED": "Project exceeded the configured budget limit.",
        "failed_quality_gate": "Report quality score was below the threshold.",
        "failed_source_diversity": "Too few high-reliability sources.",
    }
    explanation = FAIL_EXPLANATIONS.get(fail_code, "")
    if explanation:
        lines.append(f"**Explanation:** {explanation}\n")

    lines.append("## Pipeline Metrics\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Sources discovered | {len(source_files)} |")
    lines.append(f"| Read attempts | {read_attempts} |")
    lines.append(f"| Read successes | {read_successes} |")
    lines.append(f"| Read failures | {read_failures} |")
    lines.append(f"| Content with text | {nonempty_content} |")
    lines.append(f"| Findings extracted | {len(finding_files)} |")
    lines.append(f"| Claims extracted | {len(claims_data)} |")
    verified_count = sum(1 for c in claims_data if c.get("is_verified"))
    lines.append(f"| Verified claims | {verified_count} |")
    lines.append("")

    lines.append("## Top Sources (by reliability)\n")
    top_sources = sorted(sources_meta, key=lambda s: reliability.get(s.get("url", ""), 0.5), reverse=True)[:10]
    if top_sources:
        for s in top_sources:
            url = s.get("url", "")
            title = s.get("title", "Untitled")[:80]
            score = reliability.get(url, 0.5)
            sid = url.split("/")[2].replace("www.", "") if len(url.split("/")) > 2 else "?"
            has_content = any(
                cf.stem.replace("_content", "") in [sf.stem for sf in source_files]
                for cf in content_files
                if cf.stem.replace("_content", "") == Path(url).stem[:12]
            )
            read_status = "read" if nonempty_content > 0 else "unread"
            lines.append(f"- **{title}** ({sid}, reliability: {score:.0%})")
            lines.append(f"  {url}")
    else:
        lines.append("- No sources discovered.")
    lines.append("")

    if sources_meta:
        lines.append("## Key Facts from Search Metadata\n")
        lines.append("These facts appear in search result titles and descriptions (not from full article reads):\n")
        seen_facts: set[str] = set()
        for s in sources_meta:
            desc = (s.get("description") or "").strip()
            title = (s.get("title") or "").strip()
            url = s.get("url", "")
            for text in [title, desc]:
                if not text or len(text) < 20:
                    continue
                normalized = text[:100].lower()
                if normalized in seen_facts:
                    continue
                seen_facts.add(normalized)
                if len(seen_facts) > 15:
                    break
            if len(seen_facts) > 15:
                break
        for s in sources_meta[:15]:
            desc = (s.get("description") or "").strip()
            if desc and len(desc) > 30:
                url = s.get("url", "")
                domain = url.split("/")[2].replace("www.", "") if len(url.split("/")) > 2 else "?"
                lines.append(f"- *{domain}*: {desc[:200]}")
        lines.append("")

    if claims_data:
        lines.append("## Claims Extracted (Unverified)\n")
        for c in claims_data:
            v_icon = "VERIFIED" if c.get("is_verified") else "UNVERIFIED"
            reason = c.get("verification_reason", "")
            lines.append(f"- [{v_icon}] {c.get('text', '')}")
            if reason:
                lines.append(f"  _{reason}_")
        lines.append("")

    lines.append("## Recommendations\n")
    if read_failures > read_successes and read_attempts > 0:
        lines.append("- **High read failure rate.** Major news sites blocked scraping. Consider checking Jina API key or trying alternative search terms.")
    if len(finding_files) < 3 and nonempty_content >= 2:
        lines.append("- **Content was read but few findings extracted.** The relevance filter may be too strict for this question. Consider simplifying the research question.")
    if len(finding_files) < 3 and nonempty_content < 2:
        lines.append("- **Most sources could not be read.** Try re-running — scraping results vary by time of day and rate limits.")
    if verified_count == 0 and len(claims_data) > 0:
        lines.append("- **Claims found but none verified.** Each claim was only found in 1 source. More diverse sources needed for cross-verification.")
    if spend > 0:
        lines.append(f"- **Budget spent:** ${spend:.4f}. No additional cost from this abort report.")
    lines.append("- **Manual follow-up:** The top sources listed above contain the most promising leads for manual research.")
    lines.append("")

    lines.append(f"---\n*Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} — deterministic, zero additional API cost.*\n")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: research_abort_report.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    proj = project_dir(project_id)
    if not proj.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)

    report = generate_abort_report(project_id)
    if not report:
        print("No report generated.", file=sys.stderr)
        sys.exit(1)

    reports_dir = proj / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = reports_dir / f"abort_report_{ts}.md"
    out_path.write_text(report)

    audit_log(proj, "abort_report_generated", {"path": str(out_path)})
    print(json.dumps({"path": str(out_path), "size": len(report)}))


if __name__ == "__main__":
    main()
