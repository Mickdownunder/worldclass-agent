"""
Intelligence Artifact PDF report: sections (cover, outcome, claim map, etc.) and PDF rendering.
Entry point: main() for CLI usage. Call via tools/research_pdf_report.py which sets sys.path.
"""
import json
import sys
from pathlib import Path

from tools.research_common import project_dir
from tools.pdf_report import data, sections, render


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: research_pdf_report.py <project_id>", file=sys.stderr)
        return 2
    project_id = sys.argv[1].strip()
    proj_dir = project_dir(project_id)
    if not proj_dir.exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        return 1

    result = data.load_latest_report_md(proj_dir)
    if not result:
        print("No report markdown found.", file=sys.stderr)
        return 1
    report_md, ts = result

    try:
        proj_data = json.loads((proj_dir / "project.json").read_text())
    except Exception:
        proj_data = {}

    verify = data.load_verify_data(proj_dir)
    enriched_claims, epi_counts = data.build_enriched_claims(
        report_md,
        verify["claim_evidence"],
        verify["claim_verification"],
        verify["src_rel_map"],
    )

    q = (proj_data.get("question") or "").strip() or "No question"
    status = (proj_data.get("status") or "unknown").strip()
    from datetime import datetime, timezone
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cost = f"${float(proj_data.get('current_spend', 0) or 0):.2f}"
    duration = data.format_duration(proj_data)
    metrics = proj_data.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {})
    sources = str(metrics.get("unique_source_count", "—"))
    title = data.derive_title(report_md, q)
    phase_history = proj_data.get("phase_history", [])
    weaknesses = verify["critique"].get("weaknesses", [])
    suggestions = verify["critique"].get("suggestions", [])
    exec_summary = data.extract_exec_summary(report_md)
    conclusion = data.extract_conclusion(report_md)
    key_findings = data.extract_key_findings(report_md)
    gaps = data.extract_gaps(report_md)
    next_steps = data.extract_next_steps(report_md)
    body_html = data.md_to_html(report_md)
    references_html = sections.build_references_html(proj_dir, verify["claim_evidence"])

    cover_html = sections.build_cover(
        title, q, status.upper(), sources, duration, cost, date, project_id, epi_counts
    )
    outcome_html = sections.build_outcome_layer(enriched_claims, exec_summary, epi_counts)
    claim_map_html = sections.build_claim_state_map(enriched_claims)
    trajectory_html = sections.build_belief_trajectory(enriched_claims, phase_history)
    evidence_html = sections.build_evidence_landscape(verify["source_reliability"])
    disagreement_html = sections.build_disagreement_layer(gaps, enriched_claims)
    insight_html = sections.build_insight_layer(conclusion, key_findings, weaknesses)
    action_html = sections.build_action_layer(next_steps, suggestions, weaknesses)

    html = render.build_full_html(
        project_id=project_id,
        title=title,
        date=date,
        body_html=body_html,
        references_html=references_html,
        cover_html=cover_html,
        outcome_html=outcome_html,
        claim_map_html=claim_map_html,
        trajectory_html=trajectory_html,
        evidence_html=evidence_html,
        disagreement_html=disagreement_html,
        insight_html=insight_html,
        action_html=action_html,
    )

    try:
        pdf_path = proj_dir / "reports" / f"report_{ts}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        render.write_pdf(html, pdf_path, str(proj_dir))
        print(str(pdf_path))
        return 0
    except ImportError:
        print("WeasyPrint not installed. pip install weasyprint markdown", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"PDF generation failed: {e}", file=sys.stderr)
        return 1
