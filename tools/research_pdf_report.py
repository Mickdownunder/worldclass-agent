#!/usr/bin/env python3
"""
Generate a professional PDF report from the latest research report markdown and project data.
WeasyPrint (HTML/CSS to PDF). Non-fatal if WeasyPrint is missing or fails.

Usage:
  python3 research_pdf_report.py <project_id>
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import operator_root, project_dir

_REPORT_CSS = """
@page {
  size: A4;
  margin: 2cm;
  @bottom-center {
    content: "Page " counter(page) " of " counter(pages);
    font-size: 9pt;
    color: #666;
  }
}
body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a2e; }
h1 { font-size: 18pt; color: #0f1629; margin-top: 1.2em; margin-bottom: 0.5em; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }
h2 { font-size: 14pt; color: #0f1629; margin-top: 1em; margin-bottom: 0.4em; }
h3 { font-size: 12pt; color: #333; margin-top: 0.8em; }
p { margin: 0.5em 0 1em; }
ul, ol { margin: 0.5em 0 1em; padding-left: 1.5em; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
.metadata-box { background: #f5f5f8; border: 1px solid #ddd; border-radius: 6px; padding: 14px 18px; margin: 1em 0; font-size: 10pt; }
.metadata-box table { width: 100%; border-collapse: collapse; }
.metadata-box td { padding: 4px 8px 4px 0; vertical-align: top; }
.title-page { text-align: left; margin-bottom: 2em; }
.title-page .report-title { font-size: 22pt; font-weight: 700; color: #0f1629; margin-bottom: 0.3em; }
.title-page .question { font-size: 14pt; color: #333; margin: 1em 0; line-height: 1.4; }
.title-page .meta-line { font-size: 10pt; color: #555; margin: 0.3em 0; }
.quality-badge { display: inline-block; padding: 6px 12px; border-radius: 6px; font-size: 11pt; font-weight: 700; margin: 0.5em 0; }
.quality-high { background: #dcfce7; color: #166534; border: 2px solid #16a34a; }
.quality-mid { background: #fef9c3; color: #854d0e; border: 2px solid #eab308; }
.quality-low { background: #fee2e2; color: #991b1b; border: 2px solid #ef4444; }
.toc { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 18px; margin: 1em 0; font-size: 10pt; }
.toc h2 { font-size: 12pt; margin: 0 0 0.5em 0; border: none; padding: 0; }
.toc ul { list-style: none; padding-left: 0; margin: 0; }
.toc li { margin: 0.25em 0; padding-left: 0; }
.toc a { color: #2563eb; }
.methodology-section { background: #f5f5f8; border-left: 4px solid #6366f1; padding: 10px 14px; margin: 1em 0; border-radius: 0 6px 6px 0; }
.status-badge { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 10pt; font-weight: 600; }
.status-done { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
.status-failed { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
.status-other { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
.verified-tag { background: #dcfce7; border-left: 4px solid #16a34a; padding: 2px 6px; font-size: 9pt; font-weight: 600; color: #166534; }
.verified-claim { border-left: 4px solid #16a34a; background: #f0fdf4; padding-left: 10px; margin: 0.6em 0; }
.references { margin-top: 2em; }
.references ol { list-style: decimal; padding-left: 1.5em; }
.references li { margin: 0.4em 0; font-family: ui-monospace, monospace; font-size: 9pt; }
"""

_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Research Report - {project_id}</title>
  <style>{css}</style>
</head>
<body>
  <div class="title-page">
    <div class="report-title">Research Report</div>
    <div class="question">{question_esc}</div>
    <div class="meta-line">Report as of: {report_date}</div>
    <div class="meta-line">Generated: {date} | Project: {project_id}</div>
    <div class="meta-line">Status: <span class="status-badge {status_class}">{status}</span></div>
    {quality_badge_html}
    <div class="metadata-box">
      <table>
        <tr><td>Duration</td><td>{duration}</td><td>Cost</td><td>{cost}</td></tr>
        <tr><td>Sources</td><td>{sources}</td><td>Findings</td><td>{findings}</td></tr>
        <tr><td>Claims verified</td><td>{claims_verified}</td><td>Critic score</td><td>{critic_score}</td></tr>
      </table>
    </div>
  </div>
  {toc_html}
  <div class="report-body">
    {body_html}
  </div>
  <div class="references">
    <h2>References</h2>
    {references_html}
  </div>
</body>
</html>
"""


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _load_latest_report_md(proj_dir: Path) -> tuple[str, str] | None:
    reports_dir = proj_dir / "reports"
    if not reports_dir.exists():
        return None
    md_files = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.name, reverse=True)
    if not md_files:
        return None
    path = md_files[0]
    # report_20260226T123456Z.md or report_20260226T123456Z_revised.md
    name = path.stem
    ts = name.replace("report_", "").replace("_revised", "").strip()
    md = path.read_text(encoding="utf-8", errors="replace")
    # Remove LLM/template-generated References section; we add it from data in the PDF template
    md = re.sub(r"\n---\s*\n\s*## References\s*\n.*", "", md, flags=re.DOTALL | re.IGNORECASE)
    md = re.sub(r"\n#+\s*References\s*\n.*", "", md, flags=re.DOTALL | re.IGNORECASE)
    md = md.rstrip()
    return md, ts


def _md_to_html(md: str) -> str:
    import markdown
    html = markdown.markdown(md, extensions=["extra", "nl2br"])
    # Add id to each h2 for TOC links
    def add_h2_id(m):
        title = m.group(1)
        slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-").lower()[:50]
        return f'<h2 id="{slug}">{title}</h2>'
    html = re.sub(r"<h2>(.+?)</h2>", add_h2_id, html)
    # Style [VERIFIED] and [VERIFIED:xxx] as verified-tag
    html = re.sub(r"\[VERIFIED(?::[^\]]+)?\]", r'<span class="verified-tag">VERIFIED</span>', html)
    # Wrap paragraphs containing verified-tag in verified-claim div for sidebar styling
    def wrap_verified(m):
        content = m.group(1)
        if "verified-tag" in content:
            return f'<div class="verified-claim"><p>{content}</p></div>'
        return m.group(0)
    html = re.sub(r"<p>(.*?)</p>", wrap_verified, html, flags=re.DOTALL)
    return html


def _build_references(proj_dir: Path, claim_ledger: list) -> str:
    ref_map = {}
    for fp in sorted((proj_dir / "findings").glob("*.json")):
        try:
            fd = json.loads(fp.read_text())
            url = (fd.get("url") or "").strip()
            if url and url not in ref_map:
                ref_map[url] = (fd.get("title") or "").strip()
        except Exception:
            pass
    for sp in sorted((proj_dir / "sources").glob("*.json")):
        if "_content" in sp.name:
            continue
        try:
            sd = json.loads(sp.read_text())
            url = (sd.get("url") or "").strip()
            if url and url not in ref_map:
                ref_map[url] = (sd.get("title") or "").strip()
        except Exception:
            pass
    cited = set()
    for c in claim_ledger:
        for u in c.get("supporting_source_ids", []):
            cited.add(u.strip())
    refs = [(u, ref_map.get(u, "")) for u in cited if u in ref_map]
    refs.sort(key=lambda r: (r[1] or r[0]).lower())
    if not refs:
        return "<p>No references.</p>"
    lines = []
    for i, (url, title) in enumerate(refs, 1):
        if title:
            lines.append(f'<li><a href="{_escape(url)}">{_escape(title)}</a><br/><span style="font-size:8pt;color:#666;">{_escape(url)}</span></li>')
        else:
            lines.append(f'<li><a href="{_escape(url)}">{_escape(url)}</a></li>')
    return f"<ol>{''.join(lines)}</ol>"


def _toc_from_md(md: str) -> str:
    """Build Table of Contents from H2 headings in markdown."""
    import re
    toc_entries = []
    for m in re.finditer(r"^##\s+(.+)$", md, re.MULTILINE):
        title = m.group(1).strip()
        slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-").lower()[:50]
        toc_entries.append(f'<li><a href="#{slug}">{_escape(title)}</a></li>')
    if not toc_entries:
        return ""
    return '<div class="toc"><h2>Table of Contents</h2><ul>' + "".join(toc_entries) + "</ul></div>"


def _quality_badge(critic_score: str) -> str:
    try:
        s = float(critic_score)
        if s >= 0.7:
            cls, label = "quality-high", f"Quality: {s:.2f}"
        elif s >= 0.5:
            cls, label = "quality-mid", f"Quality: {s:.2f}"
        else:
            cls, label = "quality-low", f"Quality: {s:.2f}"
        return f'<div class="quality-badge {cls}">{_escape(label)}</div>'
    except (TypeError, ValueError):
        return ""


def _format_duration(proj_data: dict) -> str:
    pt = proj_data.get("phase_timings") or {}
    if not pt:
        created = proj_data.get("created_at") or ""
        if created:
            try:
                from datetime import datetime, timezone
                start = datetime.fromisoformat(created.replace("Z", "+00:00"))
                delta = (datetime.now(timezone.utc) - start).total_seconds()
                if delta < 60:
                    return f"{int(delta)}s"
                if delta < 3600:
                    return f"{delta/60:.1f}m"
                return f"{delta/3600:.1f}h"
            except Exception:
                pass
        return "—"
    total_s = sum(t.get("duration_s") or 0 for t in pt.values())
    if total_s < 60:
        return f"{int(total_s)}s"
    if total_s < 3600:
        return f"{total_s/60:.1f}m"
    return f"{total_s/3600:.1f}h"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: research_pdf_report.py <project_id>", file=sys.stderr)
        return 2
    project_id = sys.argv[1].strip()
    proj_dir = project_dir(project_id)
    if not proj_dir.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        return 1

    result = _load_latest_report_md(proj_dir)
    if not result:
        print("No report markdown found.", file=sys.stderr)
        return 1
    report_md, ts = result

    try:
        proj_data = json.loads((proj_dir / "project.json").read_text())
    except Exception:
        proj_data = {}

    claim_ledger = []
    for p in [proj_dir / "verify" / "claim_evidence_map_latest.json", proj_dir / "verify" / "claim_ledger.json"]:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                claim_ledger = data.get("claims", [])
                break
            except Exception:
                pass

    verified_count = sum(1 for c in claim_ledger if c.get("is_verified"))
    claims_str = f"{verified_count}/{len(claim_ledger)}" if claim_ledger else "—"

    critic_score = "—"
    for p in [proj_dir / "verify" / "critique.json"]:
        if p.exists():
            try:
                c = json.loads(p.read_text())
                s = c.get("score")
                if s is not None:
                    critic_score = f"{float(s):.2f}"
            except Exception:
                pass

    q = (proj_data.get("question") or "").strip() or "No question"
    status = (proj_data.get("status") or "unknown").strip()
    status_class = "status-done" if status == "done" else "status-failed" if status == "failed" else "status-other"
    from datetime import datetime, timezone
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cost = f"${float(proj_data.get('current_spend', 0) or 0):.2f}"
    duration = _format_duration(proj_data)
    sources = str(proj_data.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {}).get("unique_source_count", "—"))
    findings = str(proj_data.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {}).get("findings_count", "—"))

    body_html = _md_to_html(report_md)
    references_html = _build_references(proj_dir, claim_ledger)
    toc_html = _toc_from_md(report_md)
    quality_badge_html = _quality_badge(critic_score)
    try:
        report_date = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        report_date = date

    html = _REPORT_TEMPLATE.format(
        css=_REPORT_CSS,
        question_esc=_escape(q),
        project_id=_escape(project_id),
        date=date,
        report_date=report_date,
        status=_escape(status.upper()),
        status_class=status_class,
        quality_badge_html=quality_badge_html,
        toc_html=toc_html,
        duration=_escape(duration),
        cost=cost,
        sources=sources,
        findings=findings,
        claims_verified=claims_str,
        critic_score=critic_score,
        body_html=body_html,
        references_html=references_html,
    )

    try:
        from weasyprint import HTML
        pdf_path = proj_dir / "reports" / f"report_{ts}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html, base_url=str(proj_dir)).write_pdf(pdf_path)
        print(str(pdf_path))
        return 0
    except ImportError:
        print("WeasyPrint not installed. pip install weasyprint markdown", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"PDF generation failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
