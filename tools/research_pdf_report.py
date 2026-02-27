#!/usr/bin/env python3
"""
Generate an AEM-native Intelligence Artifact PDF from research data.

Not a research report — a structured map of knowledge, uncertainty, and action.
Structure:
  Cover  → Outcome Layer → Claim State Map → Belief Trajectory
  → Evidence Landscape → Disagreement Layer → Insight Layer
  → Action Layer → Full Report (Auditor Mode) → References

Usage:  python3 research_pdf_report.py <project_id>
"""
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import operator_root, project_dir

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
_N = "#0B1437"       # navy
_S = "#1E293B"       # slate
_A = "#3B82F6"       # accent
_AD = "#1D4ED8"      # accent dark
_BG = "#F8FAFC"      # light bg
_BD = "#E2E8F0"      # border
_T = "#1E293B"       # text
_TL = "#64748B"      # text light
_G = "#059669"       # green
_Y = "#D97706"       # yellow
_R = "#DC2626"       # red
_P = "#7C3AED"       # purple
_O = "#EA580C"       # orange

# Claim lifecycle states
STATE_STABLE    = "stable"
STATE_TENTATIVE = "tentative"
STATE_CONTESTED = "contested"
STATE_DECAYING  = "decaying"

STATE_COLORS = {
    STATE_STABLE:    _G,
    STATE_TENTATIVE: _Y,
    STATE_CONTESTED: _O,
    STATE_DECAYING:  _R,
}
STATE_BG = {
    STATE_STABLE:    "#ECFDF5",
    STATE_TENTATIVE: "#FFFBEB",
    STATE_CONTESTED: "#FFF7ED",
    STATE_DECAYING:  "#FEF2F2",
}

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
_CSS = f"""
@page {{ size: A4; margin: 0; }}
@page content {{
  margin: 2cm 2cm 2.2cm 2cm;
  @top-left {{
    content: "INTELLIGENCE ARTIFACT";
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 6.5pt; font-weight: 700;
    letter-spacing: 0.16em; color: {_TL}; padding-top: 0.2cm;
  }}
  @top-right {{
    content: string(proj-label);
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 6.5pt; color: {_TL}; padding-top: 0.2cm;
  }}
  @bottom-center {{
    content: counter(page) " / " counter(pages);
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 7pt; color: {_TL};
  }}
  @bottom-right {{
    content: "Confidential";
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 6pt; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase; color: #CBD5E1;
  }}
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 9pt; line-height: 1.6; color: {_T};
}}

/* ===== COVER ===== */
.cover {{ width: 210mm; height: 297mm; position: relative; overflow: hidden; page-break-after: always; }}
.cover-bg {{ position: absolute; inset: 0; background: linear-gradient(155deg, {_N} 0%, #162557 45%, {_AD} 100%); }}
.cover-dots {{ position: absolute; inset: 0; opacity: 0.03;
  background-image: radial-gradient(circle at 20% 30%, white 1px, transparent 1px), radial-gradient(circle at 80% 70%, white 1px, transparent 1px);
  background-size: 36px 36px; }}
.cover-bar {{ position: absolute; top: 0; left: 0; width: 5px; height: 100%; background: linear-gradient(180deg, {_A} 0%, #818CF8 50%, #A78BFA 100%); }}
.cover-inner {{ position: relative; z-index: 2; padding: 3cm 2.2cm 1.8cm 2.5cm; color: white; height: 100%; display: flex; flex-direction: column; }}
.cover-tag {{ display: inline-block; padding: 4px 14px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.18); border-radius: 16px; font-size: 7pt; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.8); margin-bottom: 1.5cm; }}
.cover-title {{ font-size: 26pt; font-weight: 800; line-height: 1.1; letter-spacing: -0.02em; margin-bottom: 0.6cm; max-width: 92%; }}
.cover-question {{ font-size: 11pt; line-height: 1.5; color: rgba(255,255,255,0.7); max-width: 85%; font-style: italic; margin-bottom: auto; }}
.cover-grid {{ display: flex; gap: 0.8cm; margin-top: 1cm; padding-top: 0.7cm; border-top: 1px solid rgba(255,255,255,0.1); }}
.cover-cell {{ flex: 1; }}
.cover-lbl {{ font-size: 6pt; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.4); margin-bottom: 2px; }}
.cover-val {{ font-size: 10pt; font-weight: 700; color: rgba(255,255,255,0.9); }}
.cover-foot {{ margin-top: 0.7cm; padding-top: 0.5cm; border-top: 1px solid rgba(255,255,255,0.07); display: flex; justify-content: space-between; align-items: center; }}
.cover-brand {{ font-size: 8pt; font-weight: 800; letter-spacing: 0.12em; color: rgba(255,255,255,0.55); }}
.cover-date {{ font-size: 7.5pt; color: rgba(255,255,255,0.35); }}

/* ===== SECTION HEADERS ===== */
.sh {{ page: content; font-size: 13pt; font-weight: 800; color: {_N}; margin: 1.4em 0 0.5em; padding-bottom: 0.25em; border-bottom: 2px solid {_A}; display: flex; align-items: center; }}
.sh-n {{ display: inline-block; width: 24px; height: 24px; background: {_N}; color: white; font-size: 10pt; font-weight: 800; border-radius: 50%; text-align: center; line-height: 24px; margin-right: 10px; flex-shrink: 0; }}
.sh-sub {{ page: content; font-size: 9pt; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: {_TL}; margin: 1.2em 0 0.4em; }}

/* ===== OUTCOME LAYER ===== */
.epi-snap {{ page: content; display: flex; gap: 10px; margin: 0.8em 0 1em; }}
.epi-card {{ flex: 1; border-radius: 8px; padding: 12px 14px; text-align: center; border: 1px solid; }}
.epi-card .ev {{ font-size: 20pt; font-weight: 800; line-height: 1.1; }}
.epi-card .el {{ font-size: 6.5pt; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: {_TL}; margin-top: 3px; }}
.epi-stable   {{ background: {STATE_BG[STATE_STABLE]};    border-color: {_G}; }}
.epi-stable .ev   {{ color: {_G}; }}
.epi-tentative {{ background: {STATE_BG[STATE_TENTATIVE]}; border-color: {_Y}; }}
.epi-tentative .ev {{ color: {_Y}; }}
.epi-contested {{ background: {STATE_BG[STATE_CONTESTED]}; border-color: {_O}; }}
.epi-contested .ev {{ color: {_O}; }}
.epi-unresolved {{ background: #F5F3FF; border-color: {_P}; }}
.epi-unresolved .ev {{ color: {_P}; }}

.conclusion-card {{ page: content; background: white; border: 1px solid {_BD}; border-left: 4px solid; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 0.4em 0; page-break-inside: avoid; }}
.cc-row {{ display: flex; justify-content: space-between; align-items: flex-start; }}
.cc-text {{ font-size: 9.5pt; font-weight: 600; color: {_N}; flex: 1; padding-right: 10px; line-height: 1.4; }}
.badge {{ display: inline-block; padding: 2px 9px; border-radius: 10px; font-size: 6.5pt; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; white-space: nowrap; }}
.b-stable {{ background: {STATE_BG[STATE_STABLE]}; color: {_G}; border: 1px solid {_G}; }}
.b-tentative {{ background: {STATE_BG[STATE_TENTATIVE]}; color: {_Y}; border: 1px solid {_Y}; }}
.b-contested {{ background: {STATE_BG[STATE_CONTESTED]}; color: {_O}; border: 1px solid {_O}; }}
.b-decaying {{ background: {STATE_BG[STATE_DECAYING]}; color: {_R}; border: 1px solid {_R}; }}
.b-high {{ background: #ECFDF5; color: {_G}; border: 1px solid {_G}; }}
.b-med {{ background: #FFFBEB; color: {_Y}; border: 1px solid {_Y}; }}
.b-low {{ background: #FEF2F2; color: {_R}; border: 1px solid {_R}; }}
.b-confirmed {{ background: #ECFDF5; color: {_G}; border: 1px solid {_G}; }}
.b-disputed {{ background: #FEF2F2; color: {_R}; border: 1px solid {_R}; }}
.b-missing {{ background: {_BG}; color: {_TL}; border: 1px solid {_BD}; }}
.cc-rel {{ font-size: 7.5pt; color: {_TL}; margin-top: 4px; font-style: italic; }}

/* ===== CLAIM STATE MAP TABLE ===== */
.csm {{ page: content; width: 100%; border-collapse: collapse; margin: 0.6em 0 1em; font-size: 8pt; }}
.csm th {{ background: {_N}; color: white; font-weight: 700; font-size: 6.5pt; letter-spacing: 0.06em; text-transform: uppercase; padding: 7px 8px; text-align: left; }}
.csm td {{ padding: 7px 8px; border-bottom: 1px solid {_BD}; vertical-align: top; }}
.csm tr:nth-child(even) td {{ background: {_BG}; }}
.csm .claim-col {{ max-width: 200px; font-weight: 500; }}
.state-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
.conf-bar {{ display: inline-block; height: 5px; border-radius: 3px; vertical-align: middle; }}
.conf-bg {{ display: inline-block; width: 50px; height: 5px; background: {_BD}; border-radius: 3px; vertical-align: middle; }}

/* ===== BELIEF TRAJECTORY ===== */
.traj-row {{ page: content; display: flex; gap: 0; margin: 0.5em 0; page-break-inside: avoid; }}
.traj-step {{ flex: 1; padding: 8px 10px; font-size: 7.5pt; text-align: center; position: relative; }}
.traj-step .ts-label {{ font-weight: 700; color: {_N}; margin-bottom: 2px; font-size: 7pt; letter-spacing: 0.06em; text-transform: uppercase; }}
.traj-step .ts-val {{ font-size: 8pt; color: {_S}; }}
.traj-arrow {{ flex: 0 0 20px; display: flex; align-items: center; justify-content: center; font-size: 10pt; color: {_TL}; }}

/* ===== EVIDENCE CLUSTER ===== */
.ev-cluster {{ page: content; border: 1px solid {_BD}; border-radius: 8px; padding: 12px 14px; margin: 0.5em 0; page-break-inside: avoid; }}
.ev-cluster-hdr {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
.ev-cluster-title {{ font-size: 9pt; font-weight: 700; color: {_N}; }}
.ev-cluster-count {{ font-size: 7.5pt; color: {_TL}; }}
.ev-cluster ul {{ list-style: none; padding: 0; margin: 0; }}
.ev-cluster li {{ padding: 3px 0 3px 12px; position: relative; font-size: 8pt; color: {_S}; }}
.ev-cluster li::before {{ content: ""; position: absolute; left: 0; top: 8px; width: 5px; height: 5px; border-radius: 50%; }}
.cluster-strong {{ border-left: 4px solid {_G}; }}
.cluster-strong li::before {{ background: {_G}; }}
.cluster-moderate {{ border-left: 4px solid {_Y}; }}
.cluster-moderate li::before {{ background: {_Y}; }}
.cluster-sparse {{ border-left: 4px solid {_R}; }}
.cluster-sparse li::before {{ background: {_R}; }}

/* ===== DISAGREEMENT TABLE ===== */
.dis-table {{ page: content; width: 100%; border-collapse: collapse; margin: 0.6em 0 1em; font-size: 8pt; }}
.dis-table th {{ background: {_O}; color: white; font-weight: 700; font-size: 6.5pt; letter-spacing: 0.06em; text-transform: uppercase; padding: 7px 8px; text-align: left; }}
.dis-table td {{ padding: 7px 8px; border-bottom: 1px solid {_BD}; vertical-align: top; }}
.dis-table tr:nth-child(even) td {{ background: #FFF7ED; }}

/* ===== INSIGHT CARDS ===== */
.insight-card {{ page: content; border-radius: 8px; padding: 12px 16px; margin: 0.5em 0; page-break-inside: avoid; }}
.insight-structural {{ background: linear-gradient(135deg, #EFF6FF 0%, {_BG} 100%); border: 1px solid #BFDBFE; border-left: 4px solid {_A}; }}
.insight-pattern {{ background: linear-gradient(135deg, #F5F3FF 0%, {_BG} 100%); border: 1px solid #DDD6FE; border-left: 4px solid {_P}; }}
.insight-decision {{ background: linear-gradient(135deg, #ECFDF5 0%, {_BG} 100%); border: 1px solid #A7F3D0; border-left: 4px solid {_G}; }}
.insight-type {{ font-size: 6.5pt; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 4px; }}
.insight-structural .insight-type {{ color: {_AD}; }}
.insight-pattern .insight-type {{ color: {_P}; }}
.insight-decision .insight-type {{ color: {_G}; }}
.insight-text {{ font-size: 9pt; color: {_S}; line-height: 1.5; }}

/* ===== ACTION CARDS ===== */
.action-card {{ page: content; background: white; border: 1px solid {_BD}; border-radius: 8px; padding: 10px 14px; margin: 0.4em 0; page-break-inside: avoid; display: flex; gap: 10px; align-items: flex-start; }}
.action-icon {{ flex: 0 0 24px; height: 24px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 8pt; font-weight: 800; color: white; }}
.action-monitor {{ background: {_P}; }}
.action-retrieve {{ background: {_A}; }}
.action-decide {{ background: {_G}; }}
.action-forecast {{ background: {_O}; }}
.action-body {{ flex: 1; }}
.action-body .ab-type {{ font-size: 6.5pt; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: {_TL}; margin-bottom: 2px; }}
.action-body .ab-text {{ font-size: 8.5pt; color: {_S}; line-height: 1.4; }}

/* ===== AUDITOR MODE ===== */
.auditor-div {{ page: content; margin: 1.8em 0 1em; padding: 12px 18px; background: {_N}; color: white; border-radius: 8px; text-align: center; }}
.auditor-div h2 {{ font-size: 10pt; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; margin: 0; border: none; padding: 0; color: white; }}
.auditor-div p {{ font-size: 7.5pt; color: rgba(255,255,255,0.55); margin: 3px 0 0; }}

.report-body {{ page: content; }}
.report-body h1 {{ font-size: 14pt; font-weight: 800; color: {_N}; margin: 1.6em 0 0.4em; border-bottom: 2px solid {_A}; padding-bottom: 0.2em; }}
.report-body h2 {{ font-size: 11pt; font-weight: 700; color: {_N}; margin: 1.4em 0 0.3em; padding-bottom: 0.15em; border-bottom: 1px solid {_BD}; padding-left: 12px; position: relative; }}
.report-body h2::before {{ content: ""; position: absolute; left: 0; top: 2px; bottom: 3px; width: 3px; border-radius: 2px; background: {_A}; }}
.report-body h3 {{ font-size: 9.5pt; font-weight: 700; color: {_S}; margin: 1em 0 0.25em; }}
.report-body p {{ margin: 0.25em 0 0.7em; text-align: justify; hyphens: auto; }}
.report-body ul, .report-body ol {{ margin: 0.25em 0 0.7em; padding-left: 1.1em; }}
.report-body li {{ margin: 0.15em 0; }}
.report-body li strong:first-child {{ color: {_N}; }}
.report-body a {{ color: {_AD}; text-decoration: none; border-bottom: 1px solid rgba(59,130,246,0.2); }}
.report-body blockquote {{ border-left: 3px solid {_A}; background: {_BG}; padding: 6px 12px; margin: 0.5em 0; border-radius: 0 6px 6px 0; font-style: italic; color: {_TL}; }}
.report-body em {{ color: {_TL}; }}
.report-body hr {{ border: none; height: 1px; background: {_BD}; margin: 1em 0; }}
.report-body table {{ width: 100%; border-collapse: collapse; margin: 0.5em 0 0.8em; font-size: 8.5pt; }}
.report-body th {{ background: {_N}; color: white; font-weight: 600; font-size: 7pt; letter-spacing: 0.05em; text-transform: uppercase; padding: 6px 8px; text-align: left; }}
.report-body td {{ padding: 5px 8px; border-bottom: 1px solid {_BD}; }}
.report-body tr:nth-child(even) td {{ background: {_BG}; }}
.report-body code {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 8pt; background: #F1F5F9; padding: 1px 4px; border-radius: 3px; color: {_AD}; }}
.report-body pre {{ background: {_N}; color: #E2E8F0; padding: 10px 14px; border-radius: 6px; font-size: 7.5pt; line-height: 1.5; margin: 0.5em 0 0.8em; }}
.report-body pre code {{ background: none; padding: 0; color: inherit; }}
.verified-tag {{ display: inline-block; padding: 1px 6px; background: #ECFDF5; border: 1px solid {_G}; border-radius: 8px; font-size: 6.5pt; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {_G}; }}
.verified-claim {{ border-left: 3px solid {_G}; background: #F0FDF4; padding: 4px 10px; margin: 0.3em 0; border-radius: 0 5px 5px 0; }}

/* ===== REFERENCES ===== */
.references {{ page: content; margin-top: 1.2em; }}
.references ol {{ list-style: none; padding-left: 0; counter-reset: ref; }}
.references li {{ counter-increment: ref; position: relative; padding: 6px 8px 6px 32px; margin: 0; border-bottom: 1px solid #F1F5F9; font-size: 7.5pt; line-height: 1.4; }}
.references li:nth-child(even) {{ background: {_BG}; }}
.references li::before {{ content: counter(ref); position: absolute; left: 4px; top: 6px; width: 16px; height: 16px; background: {_N}; color: white; font-size: 6pt; font-weight: 700; border-radius: 50%; text-align: center; line-height: 16px; }}
.references li a {{ color: {_AD}; text-decoration: none; font-weight: 600; font-size: 8pt; }}
.references .ref-url {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 6.5pt; color: {_TL}; word-break: break-all; }}
.no-refs {{ color: {_TL}; font-style: italic; padding: 8px 0; }}

.disclaimer {{ page: content; margin-top: 1.2em; padding: 10px 14px; background: {_BG}; border: 1px solid {_BD}; border-radius: 6px; font-size: 6.5pt; color: {_TL}; line-height: 1.4; }}
.disclaimer strong {{ color: {_T}; }}
.proj-label {{ string-set: proj-label content(); display: none; }}
.empty-note {{ color: {_TL}; font-style: italic; font-size: 8.5pt; padding: 6px 0; }}
"""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _derive_title(md: str, question: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return (question[:120] if question and len(question) > 10 else "Research Report")


def _load_latest_report_md(proj_dir: Path):
    reports_dir = proj_dir / "reports"
    if not reports_dir.exists():
        return None
    md_files = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.name, reverse=True)
    if not md_files:
        return None
    path = md_files[0]
    ts = path.stem.replace("report_", "").replace("_revised", "").strip()
    md = path.read_text(encoding="utf-8", errors="replace")
    md = re.sub(r"\n---\s*\n\s*## References\s*\n.*", "", md, flags=re.DOTALL | re.IGNORECASE)
    md = re.sub(r"\n#+\s*References\s*\n.*", "", md, flags=re.DOTALL | re.IGNORECASE)
    return md.rstrip(), ts


def _md_to_html(md: str) -> str:
    import markdown
    html = markdown.markdown(md, extensions=["extra", "nl2br", "smarty"])
    def add_h2_id(m):
        title = m.group(1)
        slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-").lower()[:50]
        return f'<h2 id="{slug}">{title}</h2>'
    html = re.sub(r"<h2>(.+?)</h2>", add_h2_id, html)
    html = re.sub(r"\[VERIFIED(?::[^\]]+)?\]", '<span class="verified-tag">VERIFIED</span>', html)
    def wrap_verified(m):
        if "verified-tag" in m.group(1):
            return f'<div class="verified-claim"><p>{m.group(1)}</p></div>'
        return m.group(0)
    html = re.sub(r"<p>(.*?)</p>", wrap_verified, html, flags=re.DOTALL)
    return html


def _format_duration(proj_data: dict) -> str:
    pt = proj_data.get("phase_timings") or {}
    if not pt:
        created = proj_data.get("created_at") or ""
        if created:
            try:
                from datetime import datetime, timezone
                start = datetime.fromisoformat(created.replace("Z", "+00:00"))
                d = (datetime.now(timezone.utc) - start).total_seconds()
                return f"{int(d)}s" if d < 60 else (f"{d/60:.1f}m" if d < 3600 else f"{d/3600:.1f}h")
            except Exception:
                pass
        return "—"
    total_s = sum(t.get("duration_s") or 0 for t in pt.values())
    return f"{int(total_s)}s" if total_s < 60 else (f"{total_s/60:.1f}m" if total_s < 3600 else f"{total_s/3600:.1f}h")


# ---------------------------------------------------------------------------
# Claim lifecycle derivation
# ---------------------------------------------------------------------------
def _derive_claim_state(claim_v, claim_e, source_rel_map):
    """Derive epistemic lifecycle state from verification + evidence data."""
    verified = claim_v.get("verified", False) or claim_e.get("is_verified", False)
    confidence = claim_v.get("confidence", 0.5)
    sources = claim_v.get("supporting_sources", []) or claim_e.get("supporting_source_ids", [])
    n_sources = len(sources)

    avg_rel = 0.0
    if sources and source_rel_map:
        rels = [source_rel_map.get(s, 0.5) for s in sources]
        avg_rel = sum(rels) / len(rels) if rels else 0.5

    if not verified:
        return STATE_CONTESTED
    if verified and n_sources >= 3 and confidence >= 0.9 and avg_rel >= 0.7:
        return STATE_STABLE
    if verified and avg_rel < 0.5:
        return STATE_DECAYING
    return STATE_TENTATIVE


def _confidence_label(c):
    if c >= 0.9:
        return "high", "b-high"
    if c >= 0.7:
        return "medium", "b-med"
    return "low", "b-low"


# ---------------------------------------------------------------------------
# Extract from markdown
# ---------------------------------------------------------------------------
def _extract_section(md, pattern):
    m = re.search(pattern, md, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_exec_summary(md):
    return _extract_section(md, r"##\s*\d*\.?\s*Executive\s+Summary\s*\n+(.*?)(?=\n---|\n##)")


def _extract_conclusion(md):
    return _extract_section(md, r"##\s*\d*\.?\s*(?:Conclusion|Thesis).*?\n+(.*?)(?=\n---|\n##|\Z)")


def _extract_bullet_items(md, section_pattern):
    block = _extract_section(md, section_pattern)
    if not block:
        return []
    items = []
    for item in re.findall(r"-\s*\*\*(.+?)\*\*[:\s]*\n?\s*(.*?)(?=\n-\s*\*\*|\Z)", block, re.DOTALL):
        items.append((item[0].strip(), item[1].strip()))
    if not items:
        for line in block.split("\n"):
            line = line.strip().lstrip("- ")
            if line:
                items.append((line, ""))
    return items


def _extract_gaps(md):
    return _extract_bullet_items(md, r"##\s*\d*\.?\s*(?:Contradictions|Gaps|Contradictions\s*/\s*Gaps).*?\n+(.*?)(?=\n---|\n##)")


def _extract_next_steps(md):
    return _extract_bullet_items(md, r"##\s*\d*\.?\s*(?:Suggested\s+Next\s+Steps|Next\s+Steps|Retrieval|Recommendations).*?\n+(.*?)(?=\n---|\n##|\Z)")


def _extract_key_findings(md):
    return _extract_bullet_items(md, r"##\s*\d*\.?\s*(?:Key\s+Findings).*?\n+(.*?)(?=\n---|\n##)")


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def _sh(n, text):
    return f'<div class="sh"><span class="sh-n">{n}</span><span>{_esc(text)}</span></div>'


def _build_cover(title, question, status, sources, duration, cost, date, project_id, epi_counts):
    epi_str = f"{epi_counts.get('stable',0)} stable · {epi_counts.get('tentative',0)} tentative · {epi_counts.get('contested',0)} contested"
    return f"""<div class="cover">
  <div class="cover-bg"></div><div class="cover-dots"></div><div class="cover-bar"></div>
  <div class="cover-inner">
    <div class="cover-tag">Intelligence Artifact · AEM</div>
    <div class="cover-title">{_esc(title)}</div>
    <div class="cover-question">{_esc(question)}</div>
    <div class="cover-grid">
      <div class="cover-cell"><div class="cover-lbl">Status</div><div class="cover-val">{_esc(status)}</div></div>
      <div class="cover-cell"><div class="cover-lbl">Epistemic State</div><div class="cover-val">{_esc(epi_str)}</div></div>
      <div class="cover-cell"><div class="cover-lbl">Sources</div><div class="cover-val">{sources}</div></div>
      <div class="cover-cell"><div class="cover-lbl">Duration</div><div class="cover-val">{_esc(duration)}</div></div>
      <div class="cover-cell"><div class="cover-lbl">Cost</div><div class="cover-val">{cost}</div></div>
    </div>
    <div class="cover-foot">
      <div class="cover-brand">OPENCLAW OPERATOR</div>
      <div class="cover-date">{date}</div>
    </div>
  </div>
</div>
<div class="proj-label">{_esc(project_id)}</div>"""


def _build_outcome_layer(enriched_claims, exec_summary, epi_counts):
    import markdown as _mk

    # Epistemic snapshot cards
    snap = f"""<div class="epi-snap">
  <div class="epi-card epi-stable"><div class="ev">{epi_counts.get('stable',0)}</div><div class="el">Stable Claims</div></div>
  <div class="epi-card epi-tentative"><div class="ev">{epi_counts.get('tentative',0)}</div><div class="el">Tentative Claims</div></div>
  <div class="epi-card epi-contested"><div class="ev">{epi_counts.get('contested',0)}</div><div class="el">Contested Claims</div></div>
  <div class="epi-card epi-unresolved"><div class="ev">{epi_counts.get('unresolved',0)}</div><div class="el">Unresolved Questions</div></div>
</div>"""

    # Top conclusions with confidence
    cards = []
    for ec in enriched_claims[:5]:
        state = ec["state"]
        conf_lbl, conf_cls = _confidence_label(ec["confidence"])
        color = STATE_COLORS.get(state, _TL)
        relevance = "Decision-relevant" if ec["confidence"] >= 0.9 else ("Context-relevant" if ec["confidence"] >= 0.7 else "Needs validation")
        cards.append(f"""<div class="conclusion-card" style="border-left-color:{color};">
  <div class="cc-row">
    <div class="cc-text">{_esc(ec['text'][:200])}</div>
    <span class="badge b-{state}">{state}</span>
  </div>
  <div class="cc-rel"><span class="badge {conf_cls}">{conf_lbl} confidence</span> &nbsp; {_esc(relevance)}</div>
</div>""")

    # Short answer
    sa_html = _mk.markdown(exec_summary, extensions=["smarty"]) if exec_summary else '<p class="empty-note">No executive summary available.</p>'

    return f"""{snap}
<div class="sh-sub">Research Conclusions</div>
{"".join(cards)}
<div class="sh-sub">Short Answer</div>
<div style="page:content;background:{_BG};border:1px solid {_BD};border-left:4px solid {_A};border-radius:0 8px 8px 0;padding:12px 16px;margin:0.8em 0;font-size:9pt;line-height:1.6;">
{sa_html}
</div>"""


def _build_claim_state_map(enriched_claims):
    if not enriched_claims:
        return '<p class="empty-note">No claims extracted.</p>'
    rows = []
    for ec in enriched_claims:
        state = ec["state"]
        color = STATE_COLORS.get(state, _TL)
        conf = ec["confidence"]
        conf_pct = int(conf * 100)
        conf_lbl, _ = _confidence_label(conf)
        n_ev = len(ec.get("sources", []))
        failure = ec.get("failure_boundary", "—")
        conf_color = _G if conf >= 0.9 else (_Y if conf >= 0.7 else _R)
        rows.append(f"""<tr>
  <td class="claim-col">{_esc(ec['text'][:150])}</td>
  <td><span class="state-dot" style="background:{color};"></span>{state}</td>
  <td><span class="conf-bg"><span class="conf-bar" style="width:{conf_pct}%;background:{conf_color};"></span></span> {conf_pct}%</td>
  <td>{n_ev}</td>
  <td>{_esc(ec.get('counter', '—'))}</td>
  <td style="font-size:7pt;">{_esc(failure)}</td>
</tr>""")

    return f"""<table class="csm">
  <tr><th>Claim</th><th>State</th><th>Confidence</th><th>Evidence</th><th>Counter</th><th>Failure Boundary</th></tr>
  {"".join(rows)}
</table>"""


def _build_belief_trajectory(enriched_claims, phase_history):
    if not enriched_claims:
        return '<p class="empty-note">No belief trajectory data.</p>'

    phases_display = {
        "focus": ("Focus", "Question scoping"),
        "connect": ("Connect", "Source discovery"),
        "verify": ("Verify", "Claim testing"),
        "synthesize": ("Synthesize", "Report generation"),
        "done": ("Done", "Final state"),
    }

    rows = []
    for ec in enriched_claims[:4]:
        state = ec["state"]
        color = STATE_COLORS.get(state, _TL)
        n_src = len(ec.get("sources", []))
        steps = []
        steps.append(f'<div class="traj-step"><div class="ts-label">Initial</div><div class="ts-val">Hypothesis</div></div>')
        steps.append(f'<div class="traj-arrow">→</div>')
        steps.append(f'<div class="traj-step"><div class="ts-label">Evidence</div><div class="ts-val">{n_src} sources found</div></div>')
        steps.append(f'<div class="traj-arrow">→</div>')
        if ec.get("counter") and ec["counter"] != "—":
            steps.append(f'<div class="traj-step" style="background:#FEF2F2;border-radius:4px;"><div class="ts-label">Challenge</div><div class="ts-val">{_esc(ec["counter"][:40])}</div></div>')
            steps.append(f'<div class="traj-arrow">→</div>')
        steps.append(f'<div class="traj-step"><div class="ts-label">Verification</div><div class="ts-val">{"Passed" if ec.get("verified") else "Failed"}</div></div>')
        steps.append(f'<div class="traj-arrow">→</div>')
        steps.append(f'<div class="traj-step" style="background:{STATE_BG.get(state, _BG)};border-radius:4px;border:1px solid {color};"><div class="ts-label">State</div><div class="ts-val" style="color:{color};font-weight:700;">{state.upper()}</div></div>')

        rows.append(f"""<div style="margin:0.6em 0;font-size:7.5pt;font-weight:600;color:{_N};">{_esc(ec['text'][:100])}...</div>
<div class="traj-row">{"".join(steps)}</div>""")

    return "\n".join(rows)


def _build_evidence_landscape(source_reliability):
    if not source_reliability:
        return '<p class="empty-note">No source reliability data.</p>'

    strong = [(s, re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s.get("url", ""))) for s in source_reliability if s.get("reliability_score", 0) >= 0.8]
    moderate = [(s, re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s.get("url", ""))) for s in source_reliability if 0.5 <= s.get("reliability_score", 0) < 0.8]
    sparse = [(s, re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s.get("url", ""))) for s in source_reliability if s.get("reliability_score", 0) < 0.5]

    def cluster_html(items, cls, label):
        if not items:
            return ""
        lis = "".join(f'<li>{_esc(domain)} ({int(s.get("reliability_score",0)*100)}%)</li>' for s, domain in items[:8])
        return f"""<div class="ev-cluster {cls}">
  <div class="ev-cluster-hdr"><div class="ev-cluster-title">{label}</div><div class="ev-cluster-count">{len(items)} sources</div></div>
  <ul>{lis}</ul>
</div>"""

    return (
        cluster_html(strong, "cluster-strong", "Strong Evidence Cluster (≥80% reliability)")
        + cluster_html(moderate, "cluster-moderate", "Moderate Evidence Cluster (50–79%)")
        + cluster_html(sparse, "cluster-sparse", "Sparse / Weak Zone (<50%)")
        or '<p class="empty-note">No source clusters.</p>'
    )


def _build_disagreement_layer(gaps):
    if not gaps:
        return '<p class="empty-note">No disagreements or contradictions identified.</p>'

    rows = []
    for title, desc in gaps:
        pos_a = desc if desc else title
        pos_b = "Insufficient data to establish counter-position"
        resolution = "Additional primary sources required"
        if "unclear" in desc.lower() or "unspecified" in desc.lower():
            resolution = "Clarification from authoritative source needed"
        elif "unavailable" in desc.lower() or "lacking" in desc.lower():
            resolution = "Data collection / FOIA / financial disclosure"
        rows.append(f"""<tr>
  <td><strong>{_esc(title)}</strong></td>
  <td style="font-size:7.5pt;">{_esc(pos_a[:120])}</td>
  <td style="font-size:7.5pt;">{_esc(pos_b)}</td>
  <td style="font-size:7.5pt;">{_esc(resolution)}</td>
</tr>""")

    return f"""<table class="dis-table">
  <tr><th>Topic</th><th>Position A</th><th>Position B</th><th>Resolution Condition</th></tr>
  {"".join(rows)}
</table>"""


def _build_insight_layer(conclusion, key_findings, weaknesses):
    structural = ""
    pattern = ""
    decision = ""

    if conclusion:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', conclusion) if s.strip()]
        structural = sentences[0] if len(sentences) > 0 else ""
        pattern = sentences[1] if len(sentences) > 1 else ""
        decision = sentences[-1] if len(sentences) > 2 else ""

    if not structural and key_findings:
        structural = key_findings[0][1] if key_findings[0][1] else key_findings[0][0]
    if not pattern and len(key_findings) > 1:
        pattern = key_findings[1][1] if key_findings[1][1] else key_findings[1][0]
    if not decision and weaknesses:
        decision = f"Key gap: {weaknesses[0]}"

    cards = []
    if structural:
        cards.append(f'<div class="insight-card insight-structural"><div class="insight-type">Structural Insight</div><div class="insight-text">{_esc(structural)}</div></div>')
    if pattern:
        cards.append(f'<div class="insight-card insight-pattern"><div class="insight-type">Pattern Insight</div><div class="insight-text">{_esc(pattern)}</div></div>')
    if decision:
        cards.append(f'<div class="insight-card insight-decision"><div class="insight-type">Decision Insight</div><div class="insight-text">{_esc(decision)}</div></div>')

    return "\n".join(cards) or '<p class="empty-note">No insights derived.</p>'


def _build_action_layer(next_steps, suggestions, weaknesses):
    actions = []

    # Monitoring triggers from weaknesses
    for w in weaknesses[:2]:
        actions.append(("monitor", "Monitoring Trigger", w))

    # Next retrieval from suggestions
    for s in suggestions[:2]:
        actions.append(("retrieve", "Next Retrieval", s))

    # Decision implications from next_steps
    for title, desc in next_steps[:2]:
        actions.append(("decide", "Decision Implication", f"{title}: {desc}" if desc else title))

    # Forecast from remaining
    if len(next_steps) > 2:
        for title, desc in next_steps[2:4]:
            actions.append(("forecast", "Forecast Item", f"{title}: {desc}" if desc else title))

    if not actions:
        return '<p class="empty-note">No actions derived.</p>'

    icons = {"monitor": ("M", "action-monitor"), "retrieve": ("R", "action-retrieve"), "decide": ("D", "action-decide"), "forecast": ("F", "action-forecast")}
    cards = []
    for kind, label, text in actions:
        icon_letter, icon_cls = icons.get(kind, ("?", "action-monitor"))
        cards.append(f"""<div class="action-card">
  <div class="action-icon {icon_cls}">{icon_letter}</div>
  <div class="action-body"><div class="ab-type">{label}</div><div class="ab-text">{_esc(text)}</div></div>
</div>""")

    return "\n".join(cards)


def _build_references_html(proj_dir, claim_ledger):
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
        for u in (c.get("supporting_source_ids", []) or c.get("supporting_sources", [])):
            cited.add(u.strip())
    refs = [(u, ref_map.get(u, "")) for u in cited if u in ref_map]
    refs.sort(key=lambda r: (r[1] or r[0]).lower())
    if not refs:
        return '<p class="no-refs">No references collected.</p>'
    lines = []
    for url, title in refs:
        if title:
            lines.append(f'<li><a href="{_esc(url)}">{_esc(title)}</a><br/><span class="ref-url">{_esc(url)}</span></li>')
        else:
            lines.append(f'<li><a href="{_esc(url)}">{_esc(url)}</a></li>')
    return f"<ol>{''.join(lines)}</ol>"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
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

    # ----- Load structured data -----
    claim_evidence = []
    for p in [proj_dir / "verify" / "claim_evidence_map_latest.json", proj_dir / "verify" / "claim_ledger.json"]:
        if p.exists():
            try:
                claim_evidence = json.loads(p.read_text()).get("claims", [])
                break
            except Exception:
                pass

    claim_verification = []
    cv_path = proj_dir / "verify" / "claim_verification.json"
    if cv_path.exists():
        try:
            claim_verification = json.loads(cv_path.read_text()).get("claims", [])
        except Exception:
            pass

    fact_check = []
    fc_path = proj_dir / "verify" / "fact_check.json"
    if fc_path.exists():
        try:
            fact_check = json.loads(fc_path.read_text()).get("facts", [])
        except Exception:
            pass

    source_reliability = []
    sr_path = proj_dir / "verify" / "source_reliability.json"
    if sr_path.exists():
        try:
            source_reliability = json.loads(sr_path.read_text()).get("sources", [])
        except Exception:
            pass

    critique = {}
    cr_path = proj_dir / "verify" / "critique.json"
    if cr_path.exists():
        try:
            critique = json.loads(cr_path.read_text())
        except Exception:
            pass

    # Build source reliability map
    src_rel_map = {}
    for s in source_reliability:
        url = (s.get("url") or "").strip()
        if url:
            src_rel_map[url] = s.get("reliability_score", 0.5)

    # ----- Enrich claims with lifecycle state -----
    enriched_claims = []
    cv_map = {}
    for cv in claim_verification:
        key = cv.get("claim", "")[:80]
        cv_map[key] = cv

    gaps_raw = _extract_gaps(report_md)
    gap_texts = " ".join(t + " " + d for t, d in gaps_raw).lower()

    for ce in claim_evidence:
        text = ce.get("text", "") or ce.get("claim", "")
        cv = cv_map.get(text[:80], {})
        confidence = cv.get("confidence", 0.5)
        sources = ce.get("supporting_source_ids", []) or cv.get("supporting_sources", [])
        verified = ce.get("is_verified", False) or cv.get("verified", False)

        state = _derive_claim_state(
            {"verified": verified, "confidence": confidence, "supporting_sources": sources},
            ce, src_rel_map
        )

        # Detect counter-evidence from gaps
        counter = "—"
        for gt, gd in gaps_raw:
            if any(w in gt.lower() for w in text.lower().split()[:4] if len(w) > 4):
                counter = gd[:100] if gd else gt
                break

        # Failure boundary
        if confidence >= 0.9 and len(sources) >= 3:
            failure = "Stable unless primary sources retracted"
        elif confidence >= 0.7:
            failure = "Weakens if single supporting source contradicted"
        else:
            failure = "Fails with any credible counter-evidence"

        enriched_claims.append({
            "text": text,
            "state": state,
            "confidence": confidence,
            "verified": verified,
            "sources": sources,
            "counter": counter,
            "failure_boundary": failure,
        })

    # Epistemic counts
    epi_counts = {
        "stable": sum(1 for c in enriched_claims if c["state"] == STATE_STABLE),
        "tentative": sum(1 for c in enriched_claims if c["state"] == STATE_TENTATIVE),
        "contested": sum(1 for c in enriched_claims if c["state"] == STATE_CONTESTED),
        "unresolved": len(gaps_raw),
    }

    # Metadata
    q = (proj_data.get("question") or "").strip() or "No question"
    status = (proj_data.get("status") or "unknown").strip()
    from datetime import datetime, timezone
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cost = f"${float(proj_data.get('current_spend', 0) or 0):.2f}"
    duration = _format_duration(proj_data)
    metrics = proj_data.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {})
    sources = str(metrics.get("unique_source_count", "—"))
    findings = str(metrics.get("findings_count", "—"))
    title = _derive_title(report_md, q)
    phase_history = proj_data.get("phase_history", [])
    weaknesses = critique.get("weaknesses", [])
    suggestions = critique.get("suggestions", [])
    exec_summary = _extract_exec_summary(report_md)
    conclusion = _extract_conclusion(report_md)
    key_findings = _extract_key_findings(report_md)
    gaps = _extract_gaps(report_md)
    next_steps = _extract_next_steps(report_md)
    body_html = _md_to_html(report_md)
    references_html = _build_references_html(proj_dir, claim_evidence)

    # ----- Assemble HTML -----
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Intelligence Artifact – {_esc(project_id)}</title>
<style>{_CSS}</style></head>
<body>

{_build_cover(title, q, status.upper(), sources, duration, cost, date, project_id, epi_counts)}

<!-- 1. OUTCOME LAYER -->
{_sh(1, "Outcome Layer")}
{_build_outcome_layer(enriched_claims, exec_summary, epi_counts)}

<!-- 2. CLAIM STATE MAP -->
{_sh(2, "Claim State Map")}
{_build_claim_state_map(enriched_claims)}

<!-- 3. BELIEF TRAJECTORY -->
{_sh(3, "Belief Trajectory")}
{_build_belief_trajectory(enriched_claims, phase_history)}

<!-- 4. EVIDENCE LANDSCAPE -->
{_sh(4, "Evidence Landscape")}
{_build_evidence_landscape(source_reliability)}

<!-- 5. DISAGREEMENT LAYER -->
{_sh(5, "Disagreement Layer")}
{_build_disagreement_layer(gaps)}

<!-- 6. INSIGHT LAYER -->
{_sh(6, "Insight Layer")}
{_build_insight_layer(conclusion, key_findings, weaknesses)}

<!-- 7. ACTION LAYER -->
{_sh(7, "Action Layer")}
{_build_action_layer(next_steps, suggestions, weaknesses)}

<!-- AUDITOR MODE -->
<div class="auditor-div">
  <h2>Full Report — Auditor Mode</h2>
  <p>Complete narrative with source attributions</p>
</div>
<div class="report-body">{body_html}</div>

<!-- REFERENCES -->
{_sh(8, "References")}
<div class="references">{references_html}</div>

<div class="disclaimer">
  <strong>Disclaimer:</strong> This intelligence artifact was generated by an automated epistemic research system (AEM).
  Claim states reflect algorithmic assessment of evidence quality. All findings should be independently validated.
  Generated {date}.
</div>

</body></html>"""

    try:
        from weasyprint import HTML as WP_HTML
        pdf_path = proj_dir / "reports" / f"report_{ts}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        WP_HTML(string=html, base_url=str(proj_dir)).write_pdf(pdf_path)
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
