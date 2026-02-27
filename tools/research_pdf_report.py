#!/usr/bin/env python3
"""
Generate a premium epistemic PDF report from research data.
WeasyPrint (HTML/CSS to PDF). Non-fatal if WeasyPrint is missing or fails.

Structure (Reader-mode first, Auditor-mode below):
  Page 1: Cover
  Page 2: Executive Outcome + Key Metrics + Short Answer
  Page 3: Claim Summary Table + Confidence Distribution
  Page 4+: Evidence Landscape + Source Composition
  Then:   Gap Analysis
  Then:   Retrieval Plan / Next Steps
  Then:   Full Report Body (Auditor mode)
  Last:   References + Disclaimer

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

# ---------------------------------------------------------------------------
# Brand colours & design tokens
# ---------------------------------------------------------------------------
_NAVY = "#0B1437"
_SLATE = "#1E293B"
_ACCENT = "#3B82F6"
_ACCENT_DK = "#1D4ED8"
_BG = "#F8FAFC"
_BORDER = "#E2E8F0"
_TEXT = "#1E293B"
_TEXT_LT = "#64748B"
_GREEN = "#059669"
_YELLOW = "#D97706"
_RED = "#DC2626"
_PURPLE = "#7C3AED"

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
_CSS = f"""
@page {{
  size: A4;
  margin: 0;
}}
@page content {{
  margin: 2cm 2cm 2.4cm 2cm;
  @top-left {{
    content: "RESEARCH REPORT";
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 7pt;
    font-weight: 700;
    letter-spacing: 0.14em;
    color: {_TEXT_LT};
    padding-top: 0.2cm;
  }}
  @top-right {{
    content: string(proj-label);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 7pt;
    color: {_TEXT_LT};
    padding-top: 0.2cm;
  }}
  @bottom-center {{
    content: counter(page) " / " counter(pages);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 7.5pt;
    color: {_TEXT_LT};
  }}
  @bottom-right {{
    content: "Confidential";
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 6.5pt;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #CBD5E1;
  }}
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  font-size: 9.5pt;
  line-height: 1.6;
  color: {_TEXT};
}}

/* ===== COVER ===== */
.cover {{
  width: 210mm; height: 297mm;
  position: relative; overflow: hidden;
  page-break-after: always;
}}
.cover-bg {{
  position: absolute; inset: 0;
  background: linear-gradient(155deg, {_NAVY} 0%, #162557 45%, {_ACCENT_DK} 100%);
}}
.cover-dots {{
  position: absolute; inset: 0; opacity: 0.035;
  background-image:
    radial-gradient(circle at 20% 30%, white 1px, transparent 1px),
    radial-gradient(circle at 80% 70%, white 1px, transparent 1px);
  background-size: 36px 36px;
}}
.cover-bar {{
  position: absolute; top: 0; left: 0; width: 5px; height: 100%;
  background: linear-gradient(180deg, {_ACCENT} 0%, #818CF8 50%, #A78BFA 100%);
}}
.cover-inner {{
  position: relative; z-index: 2;
  padding: 3.2cm 2.4cm 2cm 2.6cm;
  color: white; height: 100%;
  display: flex; flex-direction: column;
}}
.cover-tag {{
  display: inline-block;
  padding: 5px 14px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 16px;
  font-size: 7.5pt; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: rgba(255,255,255,0.85);
  margin-bottom: 1.8cm;
}}
.cover-title {{
  font-size: 28pt; font-weight: 800;
  line-height: 1.12; letter-spacing: -0.02em;
  margin-bottom: 0.7cm; max-width: 90%;
}}
.cover-question {{
  font-size: 12pt; line-height: 1.5;
  color: rgba(255,255,255,0.75);
  max-width: 82%; font-style: italic;
  margin-bottom: auto;
}}
.cover-grid {{
  display: flex; gap: 1cm; margin-top: 1.2cm;
  padding-top: 0.8cm; border-top: 1px solid rgba(255,255,255,0.12);
}}
.cover-cell {{ flex: 1; }}
.cover-cell-lbl {{
  font-size: 6.5pt; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: rgba(255,255,255,0.45); margin-bottom: 3px;
}}
.cover-cell-val {{
  font-size: 10.5pt; font-weight: 700;
  color: rgba(255,255,255,0.92);
}}
.cover-foot {{
  margin-top: 0.8cm; padding-top: 0.6cm;
  border-top: 1px solid rgba(255,255,255,0.08);
  display: flex; justify-content: space-between; align-items: center;
}}
.cover-brand {{ font-size: 8.5pt; font-weight: 800; letter-spacing: 0.1em; color: rgba(255,255,255,0.6); }}
.cover-date  {{ font-size: 8pt; color: rgba(255,255,255,0.4); }}

/* ===== OUTCOME BOX ===== */
.outcome-box {{
  page: content;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 1.2em;
  border: 2px solid;
}}
.outcome-passed {{
  background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 100%);
  border-color: {_GREEN};
}}
.outcome-failed {{
  background: linear-gradient(135deg, #FEF2F2 0%, #FFF1F2 100%);
  border-color: {_RED};
}}
.outcome-partial {{
  background: linear-gradient(135deg, #FFFBEB 0%, #FEF9C3 100%);
  border-color: {_YELLOW};
}}
.outcome-header {{
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px;
}}
.outcome-label {{
  font-size: 7pt; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: {_TEXT_LT};
}}
.outcome-verdict {{
  font-size: 14pt; font-weight: 800;
  letter-spacing: -0.01em;
}}
.outcome-passed .outcome-verdict {{ color: {_GREEN}; }}
.outcome-failed .outcome-verdict {{ color: {_RED}; }}
.outcome-partial .outcome-verdict {{ color: {_YELLOW}; }}
.outcome-metrics {{
  display: flex; gap: 10px; margin-top: 12px;
}}
.outcome-metric {{
  flex: 1;
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 8px;
  padding: 10px 12px;
  text-align: center;
}}
.outcome-metric .om-val {{
  font-size: 16pt; font-weight: 800; color: {_NAVY};
  line-height: 1.1;
}}
.outcome-metric .om-lbl {{
  font-size: 6.5pt; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: {_TEXT_LT}; margin-top: 2px;
}}
.outcome-weaknesses {{
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid rgba(0,0,0,0.06);
}}
.outcome-weaknesses .ow-title {{
  font-size: 7pt; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: {_TEXT_LT}; margin-bottom: 6px;
}}
.outcome-weaknesses ul {{
  list-style: none; padding: 0; margin: 0;
  columns: 1; font-size: 8.5pt;
}}
.outcome-weaknesses li {{
  padding: 2px 0 2px 14px; position: relative;
  color: {_SLATE};
}}
.outcome-weaknesses li::before {{
  content: ""; position: absolute;
  left: 0; top: 8px;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: {_YELLOW};
}}

/* ===== SHORT ANSWER ===== */
.short-answer {{
  page: content;
  background: {_BG};
  border: 1px solid {_BORDER};
  border-left: 4px solid {_ACCENT};
  border-radius: 0 8px 8px 0;
  padding: 16px 20px;
  margin: 1em 0 1.5em;
  font-size: 10pt;
  line-height: 1.65;
}}
.short-answer .sa-label {{
  font-size: 7pt; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: {_ACCENT_DK}; margin-bottom: 6px;
}}

/* ===== SECTION HEADERS ===== */
.section-num {{
  display: inline-block;
  width: 28px; height: 28px;
  background: {_NAVY};
  color: white;
  font-size: 11pt; font-weight: 800;
  border-radius: 50%;
  text-align: center; line-height: 28px;
  margin-right: 10px;
  vertical-align: middle;
}}
.section-hdr {{
  page: content;
  font-size: 14pt; font-weight: 800;
  color: {_NAVY};
  margin: 1.6em 0 0.6em;
  padding-bottom: 0.3em;
  border-bottom: 2px solid {_ACCENT};
  display: flex; align-items: center;
}}
.section-hdr-text {{
  letter-spacing: -0.01em;
}}

/* ===== CLAIM CARDS ===== */
.claim-card {{
  page: content;
  background: white;
  border: 1px solid {_BORDER};
  border-radius: 8px;
  padding: 14px 18px;
  margin: 0.7em 0;
  page-break-inside: avoid;
}}
.claim-card-hdr {{
  display: flex; justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}}
.claim-text {{
  font-size: 10pt; font-weight: 600;
  color: {_NAVY}; line-height: 1.45;
  flex: 1; padding-right: 12px;
}}
.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 7pt; font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}}
.badge-verified {{ background: #ECFDF5; color: {_GREEN}; border: 1px solid {_GREEN}; }}
.badge-unverified {{ background: #FEF2F2; color: {_RED}; border: 1px solid {_RED}; }}
.badge-tentative {{ background: #FFFBEB; color: {_YELLOW}; border: 1px solid {_YELLOW}; }}
.badge-confirmed {{ background: #ECFDF5; color: {_GREEN}; border: 1px solid {_GREEN}; }}
.badge-disputed  {{ background: #FEF2F2; color: {_RED}; border: 1px solid {_RED}; }}
.badge-missing   {{ background: {_BG}; color: {_TEXT_LT}; border: 1px solid {_BORDER}; }}

.claim-detail {{
  font-size: 8.5pt; color: {_TEXT_LT};
  margin-top: 4px; line-height: 1.45;
}}
.claim-detail strong {{
  color: {_SLATE}; font-weight: 600;
}}
.claim-sources {{
  margin-top: 6px; padding-top: 6px;
  border-top: 1px solid #F1F5F9;
  font-size: 7.5pt;
}}
.claim-sources a {{
  color: {_ACCENT_DK}; text-decoration: none;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  word-break: break-all;
}}

/* ===== EPISTEMIC TABLE ===== */
.epi-table {{
  page: content;
  width: 100%; border-collapse: collapse;
  margin: 0.8em 0 1.2em;
  font-size: 9pt;
}}
.epi-table th {{
  background: {_NAVY}; color: white;
  font-weight: 700; font-size: 7.5pt;
  letter-spacing: 0.06em; text-transform: uppercase;
  padding: 8px 12px; text-align: left;
}}
.epi-table td {{
  padding: 8px 12px;
  border-bottom: 1px solid {_BORDER};
}}
.epi-table tr:nth-child(even) td {{
  background: {_BG};
}}
.tier-dot {{
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}}
.tier-high {{ background: {_GREEN}; }}
.tier-medium {{ background: {_YELLOW}; }}
.tier-low {{ background: {_RED}; }}

/* ===== FACT CHECK TABLE ===== */
.fact-table {{
  page: content;
  width: 100%; border-collapse: collapse;
  margin: 0.8em 0 1.2em;
  font-size: 8.5pt;
}}
.fact-table th {{
  background: {_NAVY}; color: white;
  font-weight: 700; font-size: 7pt;
  letter-spacing: 0.06em; text-transform: uppercase;
  padding: 7px 10px; text-align: left;
}}
.fact-table td {{
  padding: 7px 10px;
  border-bottom: 1px solid {_BORDER};
  vertical-align: top;
}}
.fact-table tr:nth-child(even) td {{
  background: {_BG};
}}

/* ===== SOURCE TABLE ===== */
.source-table {{
  page: content;
  width: 100%; border-collapse: collapse;
  margin: 0.8em 0 1.2em;
  font-size: 8pt;
}}
.source-table th {{
  background: {_NAVY}; color: white;
  font-weight: 700; font-size: 7pt;
  letter-spacing: 0.06em; text-transform: uppercase;
  padding: 6px 10px; text-align: left;
}}
.source-table td {{
  padding: 6px 10px;
  border-bottom: 1px solid {_BORDER};
  vertical-align: top;
}}
.source-table tr:nth-child(even) td {{
  background: {_BG};
}}
.reliability-bar {{
  display: inline-block;
  height: 6px;
  border-radius: 3px;
  vertical-align: middle;
}}
.reliability-fill {{
  height: 6px; border-radius: 3px;
}}

/* ===== GAP CARD ===== */
.gap-card {{
  page: content;
  background: linear-gradient(135deg, #FFF7ED 0%, #FFFBEB 100%);
  border: 1px solid #FED7AA;
  border-left: 4px solid {_YELLOW};
  border-radius: 0 8px 8px 0;
  padding: 12px 16px;
  margin: 0.5em 0;
  page-break-inside: avoid;
}}
.gap-card .gap-text {{
  font-size: 9pt; color: {_SLATE};
}}

/* ===== SUGGESTION / NEXT STEPS ===== */
.next-card {{
  page: content;
  background: linear-gradient(135deg, #EFF6FF 0%, {_BG} 100%);
  border: 1px solid #BFDBFE;
  border-left: 4px solid {_ACCENT};
  border-radius: 0 8px 8px 0;
  padding: 12px 16px;
  margin: 0.5em 0;
  page-break-inside: avoid;
}}
.next-card .next-num {{
  display: inline-block;
  width: 18px; height: 18px;
  background: {_ACCENT};
  color: white; font-size: 8pt; font-weight: 700;
  border-radius: 50%; text-align: center; line-height: 18px;
  margin-right: 8px;
}}
.next-card .next-text {{
  font-size: 9pt; color: {_SLATE};
}}

/* ===== AUDITOR BODY ===== */
.auditor-divider {{
  page: content;
  margin: 2em 0 1em;
  padding: 14px 20px;
  background: {_NAVY};
  color: white;
  border-radius: 8px;
  text-align: center;
}}
.auditor-divider h2 {{
  font-size: 11pt; font-weight: 800;
  letter-spacing: 0.08em; text-transform: uppercase;
  margin: 0; border: none; padding: 0;
  color: white;
}}
.auditor-divider p {{
  font-size: 8pt; color: rgba(255,255,255,0.6);
  margin: 4px 0 0;
}}

.report-body {{
  page: content;
}}
.report-body h1 {{
  font-size: 16pt; font-weight: 800;
  color: {_NAVY}; margin: 1.8em 0 0.5em;
  border-bottom: 2px solid {_ACCENT};
  padding-bottom: 0.25em;
}}
.report-body h2 {{
  font-size: 12pt; font-weight: 700;
  color: {_NAVY}; margin: 1.6em 0 0.4em;
  padding-bottom: 0.2em;
  border-bottom: 1px solid {_BORDER};
  padding-left: 14px; position: relative;
}}
.report-body h2::before {{
  content: ""; position: absolute;
  left: 0; top: 2px; bottom: 4px;
  width: 4px; border-radius: 2px;
  background: {_ACCENT};
}}
.report-body h3 {{
  font-size: 10.5pt; font-weight: 700;
  color: {_SLATE}; margin: 1.2em 0 0.3em;
}}
.report-body p {{
  margin: 0.3em 0 0.8em;
  text-align: justify; hyphens: auto;
}}
.report-body ul, .report-body ol {{
  margin: 0.3em 0 0.8em; padding-left: 1.2em;
}}
.report-body li {{ margin: 0.2em 0; }}
.report-body li strong:first-child {{ color: {_NAVY}; }}
.report-body a {{
  color: {_ACCENT_DK}; text-decoration: none;
  border-bottom: 1px solid rgba(59,130,246,0.25);
}}
.report-body blockquote {{
  border-left: 3px solid {_ACCENT};
  background: {_BG}; padding: 8px 14px;
  margin: 0.6em 0; border-radius: 0 6px 6px 0;
  font-style: italic; color: {_TEXT_LT};
}}
.report-body em {{ color: {_TEXT_LT}; }}
.report-body hr {{
  border: none; height: 1px;
  background: {_BORDER}; margin: 1.2em 0;
}}
.report-body table {{
  width: 100%; border-collapse: collapse;
  margin: 0.6em 0 1em; font-size: 9pt;
}}
.report-body th {{
  background: {_NAVY}; color: white;
  font-weight: 600; font-size: 7.5pt;
  letter-spacing: 0.05em; text-transform: uppercase;
  padding: 7px 10px; text-align: left;
}}
.report-body td {{
  padding: 6px 10px;
  border-bottom: 1px solid {_BORDER};
}}
.report-body tr:nth-child(even) td {{ background: {_BG}; }}
.report-body code {{
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 8.5pt; background: #F1F5F9;
  padding: 1px 5px; border-radius: 3px;
  color: {_ACCENT_DK};
}}
.report-body pre {{
  background: {_NAVY}; color: #E2E8F0;
  padding: 12px 16px; border-radius: 8px;
  font-size: 8pt; line-height: 1.5;
  margin: 0.6em 0 1em;
}}
.report-body pre code {{
  background: none; padding: 0; color: inherit;
}}
.verified-tag {{
  display: inline-block; padding: 1px 7px;
  background: #ECFDF5; border: 1px solid {_GREEN};
  border-radius: 10px; font-size: 7pt; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: {_GREEN}; vertical-align: middle;
}}
.verified-claim {{
  border-left: 3px solid {_GREEN};
  background: #F0FDF4; padding: 5px 12px;
  margin: 0.4em 0; border-radius: 0 6px 6px 0;
}}

/* ===== REFERENCES ===== */
.references {{
  page: content; margin-top: 1.5em;
}}
.references ol {{
  list-style: none; padding-left: 0;
  counter-reset: ref;
}}
.references li {{
  counter-increment: ref;
  position: relative; padding: 7px 10px 7px 36px;
  margin: 0; border-bottom: 1px solid #F1F5F9;
  font-size: 8pt; line-height: 1.45;
}}
.references li:nth-child(even) {{ background: {_BG}; }}
.references li::before {{
  content: counter(ref);
  position: absolute; left: 6px; top: 7px;
  width: 18px; height: 18px;
  background: {_NAVY}; color: white;
  font-size: 6.5pt; font-weight: 700;
  border-radius: 50%; text-align: center; line-height: 18px;
}}
.references li a {{
  color: {_ACCENT_DK}; text-decoration: none; font-weight: 600; font-size: 8.5pt;
}}
.references .ref-url {{
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 7pt; color: {_TEXT_LT}; word-break: break-all;
}}
.no-refs {{ color: {_TEXT_LT}; font-style: italic; padding: 10px 0; }}

/* ===== DISCLAIMER ===== */
.disclaimer {{
  page: content; margin-top: 1.5em;
  padding: 12px 16px; background: {_BG};
  border: 1px solid {_BORDER}; border-radius: 6px;
  font-size: 7pt; color: {_TEXT_LT}; line-height: 1.45;
}}
.disclaimer strong {{ color: {_TEXT}; }}

/* Named string for running header */
.proj-label {{ string-set: proj-label content(); display: none; }}
"""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _derive_title(md: str, question: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    if m:
        return m.group(1).strip()
    if question and len(question) > 10:
        return question[:120]
    return "Research Report"


def _load_latest_report_md(proj_dir: Path) -> tuple[str, str] | None:
    reports_dir = proj_dir / "reports"
    if not reports_dir.exists():
        return None
    md_files = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.name, reverse=True)
    if not md_files:
        return None
    path = md_files[0]
    name = path.stem
    ts = name.replace("report_", "").replace("_revised", "").strip()
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
    html = re.sub(r"\[VERIFIED(?::[^\]]+)?\]", r'<span class="verified-tag">VERIFIED</span>', html)
    def wrap_verified(m):
        content = m.group(1)
        if "verified-tag" in content:
            return f'<div class="verified-claim"><p>{content}</p></div>'
        return m.group(0)
    html = re.sub(r"<p>(.*?)</p>", wrap_verified, html, flags=re.DOTALL)
    return html


def _extract_executive_summary(md: str) -> str:
    m = re.search(r"##\s*\d*\.?\s*Executive\s+Summary\s*\n+(.*?)(?=\n---|\n##)", md, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    paragraphs = [p.strip() for p in md.split("\n\n") if p.strip() and not p.strip().startswith("#")]
    return paragraphs[0] if paragraphs else ""


def _extract_gaps(md: str) -> list[str]:
    m = re.search(r"##\s*\d*\.?\s*(?:Contradictions|Gaps|Contradictions\s*/\s*Gaps).*?\n+(.*?)(?=\n---|\n##)", md, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)
    gaps = []
    for item in re.findall(r"-\s*\*\*(.+?)\*\*[:\s]*\n?\s*(.*?)(?=\n-\s*\*\*|\Z)", block, re.DOTALL):
        title, desc = item
        gaps.append(f"<strong>{_esc(title.strip())}</strong> — {_esc(desc.strip())}")
    if not gaps:
        for line in block.split("\n"):
            line = line.strip().lstrip("- ")
            if line:
                gaps.append(_esc(line))
    return gaps


def _extract_next_steps(md: str) -> list[str]:
    m = re.search(r"##\s*\d*\.?\s*(?:Suggested\s+Next\s+Steps|Next\s+Steps|Retrieval\s+Plan|Recommendations).*?\n+(.*?)(?=\n---|\n##|\Z)", md, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)
    steps = []
    for item in re.findall(r"-\s*\*\*(.+?)\*\*[:\s]*\n?\s*(.*?)(?=\n-\s*\*\*|\Z)", block, re.DOTALL):
        title, desc = item
        steps.append(f"<strong>{_esc(title.strip())}</strong> — {_esc(desc.strip())}")
    if not steps:
        for line in block.split("\n"):
            line = line.strip().lstrip("- ")
            if line:
                steps.append(_esc(line))
    return steps


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


def _build_references_html(proj_dir: Path, claim_ledger: list) -> str:
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
        return '<p class="no-refs">No references collected.</p>'
    lines = []
    for url, title in refs:
        if title:
            lines.append(f'<li><a href="{_esc(url)}">{_esc(title)}</a><br/><span class="ref-url">{_esc(url)}</span></li>')
        else:
            lines.append(f'<li><a href="{_esc(url)}">{_esc(url)}</a></li>')
    return f"<ol>{''.join(lines)}</ol>"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_cover(title, question, status, quality_display, sources, duration, cost, date, project_id):
    return f"""<div class="cover">
  <div class="cover-bg"></div>
  <div class="cover-dots"></div>
  <div class="cover-bar"></div>
  <div class="cover-inner">
    <div class="cover-tag">Deep Research Report</div>
    <div class="cover-title">{_esc(title)}</div>
    <div class="cover-question">{_esc(question)}</div>
    <div class="cover-grid">
      <div class="cover-cell"><div class="cover-cell-lbl">Status</div><div class="cover-cell-val">{_esc(status)}</div></div>
      <div class="cover-cell"><div class="cover-cell-lbl">Quality</div><div class="cover-cell-val">{_esc(quality_display)}</div></div>
      <div class="cover-cell"><div class="cover-cell-lbl">Sources</div><div class="cover-cell-val">{sources}</div></div>
      <div class="cover-cell"><div class="cover-cell-lbl">Duration</div><div class="cover-cell-val">{_esc(duration)}</div></div>
      <div class="cover-cell"><div class="cover-cell-lbl">Cost</div><div class="cover-cell-val">{cost}</div></div>
    </div>
    <div class="cover-foot">
      <div class="cover-brand">OPENCLAW OPERATOR</div>
      <div class="cover-date">{date}</div>
    </div>
  </div>
</div>
<div class="proj-label">{_esc(project_id)}</div>"""


def _build_outcome_box(proj_data, critic_score, sources, findings, claims_verified, verified_count, total_claims, weaknesses):
    qg = proj_data.get("quality_gate", {})
    gate_status = qg.get("quality_gate_status", "unknown")
    if gate_status == "passed":
        box_cls = "outcome-passed"
        verdict = "EVIDENCE SUFFICIENT"
    elif gate_status == "failed":
        box_cls = "outcome-failed"
        verdict = "INSUFFICIENT EVIDENCE"
    else:
        box_cls = "outcome-partial"
        verdict = gate_status.upper().replace("_", " ")

    try:
        score_pct = f"{float(critic_score) * 100:.0f}%"
    except (TypeError, ValueError):
        score_pct = "—"

    hi_rel = qg.get("evidence_gate", {}).get("metrics", {}).get("high_reliability_source_ratio")
    hi_rel_str = f"{hi_rel*100:.0f}%" if hi_rel is not None else "—"

    weakness_html = ""
    if weaknesses:
        items = "".join(f"<li>{_esc(w)}</li>" for w in weaknesses[:5])
        weakness_html = f"""<div class="outcome-weaknesses">
  <div class="ow-title">Known Weaknesses</div>
  <ul>{items}</ul>
</div>"""

    return f"""<div class="outcome-box {box_cls}">
  <div class="outcome-header">
    <div class="outcome-label">Executive Outcome</div>
    <div class="outcome-verdict">{verdict}</div>
  </div>
  <div class="outcome-metrics">
    <div class="outcome-metric"><div class="om-val">{score_pct}</div><div class="om-lbl">Quality Score</div></div>
    <div class="outcome-metric"><div class="om-val">{claims_verified}</div><div class="om-lbl">Claims Verified</div></div>
    <div class="outcome-metric"><div class="om-val">{sources}</div><div class="om-lbl">Sources</div></div>
    <div class="outcome-metric"><div class="om-val">{findings}</div><div class="om-lbl">Findings</div></div>
    <div class="outcome-metric"><div class="om-val">{hi_rel_str}</div><div class="om-lbl">High-Rel Sources</div></div>
  </div>
  {weakness_html}
</div>"""


def _build_short_answer(exec_summary: str):
    import markdown
    html = markdown.markdown(exec_summary, extensions=["smarty"])
    return f"""<div class="short-answer">
  <div class="sa-label">Short Answer</div>
  {html}
</div>"""


def _build_claim_cards(claim_ledger: list) -> str:
    if not claim_ledger:
        return '<p style="color:#64748B;font-style:italic;">No claims extracted for this report.</p>'
    cards = []
    for c in claim_ledger:
        verified = c.get("is_verified", False)
        badge_cls = "badge-verified" if verified else "badge-unverified"
        badge_text = "VERIFIED" if verified else "UNVERIFIED"
        reason = c.get("verification_reason", "")
        srcs = c.get("supporting_source_ids", [])
        src_html = ""
        if srcs:
            links = []
            for s in srcs[:4]:
                domain = re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s)
                links.append(f'<a href="{_esc(s)}">{_esc(domain)}</a>')
            src_html = f'<div class="claim-sources"><strong>Sources:</strong> {" · ".join(links)}</div>'
        cards.append(f"""<div class="claim-card">
  <div class="claim-card-hdr">
    <div class="claim-text">{_esc(c.get("text", ""))}</div>
    <span class="badge {badge_cls}">{badge_text}</span>
  </div>
  <div class="claim-detail"><strong>Evidence:</strong> {_esc(reason)}</div>
  {src_html}
</div>""")
    return "\n".join(cards)


def _build_epistemic_table(claim_ledger: list, fact_check: list) -> str:
    high = sum(1 for c in claim_ledger if c.get("is_verified") and len(c.get("supporting_source_ids", [])) >= 3)
    medium = sum(1 for c in claim_ledger if c.get("is_verified") and len(c.get("supporting_source_ids", [])) < 3)
    low = sum(1 for c in claim_ledger if not c.get("is_verified"))
    facts_confirmed = sum(1 for f in fact_check if f.get("verification_status") == "confirmed")
    facts_disputed = sum(1 for f in fact_check if f.get("verification_status") in ("disputed", "refuted"))
    facts_unconf = len(fact_check) - facts_confirmed - facts_disputed
    return f"""<table class="epi-table">
  <tr><th>Tier</th><th>Meaning</th><th>Claims</th><th>Facts Checked</th></tr>
  <tr><td><span class="tier-dot tier-high"></span>High</td><td>Multi-source primary, ≥3 independent sources</td><td><strong>{high}</strong></td><td><strong>{facts_confirmed}</strong> confirmed</td></tr>
  <tr><td><span class="tier-dot tier-medium"></span>Medium</td><td>Secondary corroborated, 2 sources</td><td><strong>{medium}</strong></td><td><strong>{facts_unconf}</strong> unconfirmed</td></tr>
  <tr><td><span class="tier-dot tier-low"></span>Low</td><td>Single-source or unverified</td><td><strong>{low}</strong></td><td><strong>{facts_disputed}</strong> disputed</td></tr>
</table>"""


def _build_source_composition(source_reliability: list) -> str:
    if not source_reliability:
        return '<p style="color:#64748B;font-style:italic;">No source reliability data available.</p>'
    rows = []
    for s in sorted(source_reliability, key=lambda x: x.get("reliability_score", 0), reverse=True)[:15]:
        url = s.get("url", "")
        domain = re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", url)
        score = s.get("reliability_score", 0)
        pct = int(score * 100)
        color = _GREEN if score >= 0.8 else _YELLOW if score >= 0.6 else _RED
        flags = ", ".join(s.get("flags", [])[:3])
        rows.append(f"""<tr>
  <td><strong>{_esc(domain)}</strong></td>
  <td><div style="width:60px;height:6px;background:#E2E8F0;border-radius:3px;display:inline-block;vertical-align:middle;"><div style="width:{pct}%;height:6px;background:{color};border-radius:3px;"></div></div> {pct}%</td>
  <td style="font-size:7pt;color:#64748B;">{_esc(flags)}</td>
</tr>""")
    return f"""<table class="source-table">
  <tr><th>Source</th><th>Reliability</th><th>Flags</th></tr>
  {"".join(rows)}
</table>"""


def _build_fact_table(fact_check: list) -> str:
    if not fact_check:
        return ""
    rows = []
    for f in fact_check:
        st = f.get("verification_status", "unknown")
        if st == "confirmed":
            badge = '<span class="badge badge-confirmed">Confirmed</span>'
        elif st in ("disputed", "refuted"):
            badge = '<span class="badge badge-disputed">Disputed</span>'
        else:
            badge = '<span class="badge badge-missing">Unconfirmed</span>'
        rows.append(f'<tr><td>{_esc(f.get("statement", ""))}</td><td>{badge}</td></tr>')
    return f"""<table class="fact-table">
  <tr><th>Statement</th><th>Status</th></tr>
  {"".join(rows)}
</table>"""


def _build_gap_cards(gaps: list[str]) -> str:
    if not gaps:
        return '<p style="color:#64748B;font-style:italic;">No gaps identified.</p>'
    return "\n".join(f'<div class="gap-card"><div class="gap-text">{g}</div></div>' for g in gaps)


def _build_next_cards(steps: list[str]) -> str:
    if not steps:
        return '<p style="color:#64748B;font-style:italic;">No next steps suggested.</p>'
    cards = []
    for i, s in enumerate(steps, 1):
        cards.append(f'<div class="next-card"><span class="next-num">{i}</span><span class="next-text">{s}</span></div>')
    return "\n".join(cards)


def _section_header(num: int, text: str) -> str:
    return f'<div class="section-hdr"><span class="section-num">{num}</span><span class="section-hdr-text">{_esc(text)}</span></div>'


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

    # Load structured data
    claim_ledger: list = []
    for p in [proj_dir / "verify" / "claim_evidence_map_latest.json", proj_dir / "verify" / "claim_ledger.json"]:
        if p.exists():
            try:
                claim_ledger = json.loads(p.read_text()).get("claims", [])
                break
            except Exception:
                pass

    fact_check: list = []
    fc_path = proj_dir / "verify" / "fact_check.json"
    if fc_path.exists():
        try:
            fact_check = json.loads(fc_path.read_text()).get("facts", [])
        except Exception:
            pass

    source_reliability: list = []
    sr_path = proj_dir / "verify" / "source_reliability.json"
    if sr_path.exists():
        try:
            source_reliability = json.loads(sr_path.read_text()).get("sources", [])
        except Exception:
            pass

    critique: dict = {}
    cr_path = proj_dir / "verify" / "critique.json"
    if cr_path.exists():
        try:
            critique = json.loads(cr_path.read_text())
        except Exception:
            pass

    # Derived values
    verified_count = sum(1 for c in claim_ledger if c.get("is_verified"))
    total_claims = len(claim_ledger)
    claims_str = f"{verified_count}/{total_claims}" if claim_ledger else "—"
    critic_score = f"{float(critique.get('score', 0)):.2f}" if critique.get("score") is not None else "—"
    weaknesses = critique.get("weaknesses", [])
    suggestions = critique.get("suggestions", [])

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

    try:
        score_f = float(critic_score)
        quality_display = f"{int(score_f * 100)}%" + (" ★" if score_f >= 0.7 else "")
    except (TypeError, ValueError):
        quality_display = "—"

    exec_summary = _extract_executive_summary(report_md)
    gaps = _extract_gaps(report_md)
    next_steps = _extract_next_steps(report_md)
    body_html = _md_to_html(report_md)
    references_html = _build_references_html(proj_dir, claim_ledger)

    try:
        report_date = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        report_date = date

    # ----- Assemble HTML -----
    cover = _build_cover(title, q, status.upper(), quality_display, sources, duration, cost, date, project_id)
    outcome = _build_outcome_box(proj_data, critic_score, sources, findings, claims_str, verified_count, total_claims, weaknesses)
    short_answer = _build_short_answer(exec_summary)
    claim_cards = _build_claim_cards(claim_ledger)
    epi_table = _build_epistemic_table(claim_ledger, fact_check)
    source_comp = _build_source_composition(source_reliability)
    fact_tbl = _build_fact_table(fact_check)
    gap_cards = _build_gap_cards(gaps)
    next_cards = _build_next_cards(next_steps if next_steps else suggestions)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Research Report – {_esc(project_id)}</title>
  <style>{_CSS}</style>
</head>
<body>
  {cover}

  <!-- ===== PAGE 2: EXECUTIVE OUTCOME ===== -->
  {_section_header(1, "Executive Outcome")}
  {outcome}
  {short_answer}

  <!-- ===== PAGE 3: CLAIM SUMMARY + CONFIDENCE ===== -->
  {_section_header(2, "Claim Summary")}
  {epi_table}
  {claim_cards}

  <!-- ===== EVIDENCE LANDSCAPE ===== -->
  {_section_header(3, "Evidence Landscape")}
  {fact_tbl}
  <h3 style="font-size:10pt;font-weight:700;color:{_NAVY};margin:1.2em 0 0.4em;">Source Composition</h3>
  {source_comp}

  <!-- ===== GAP ANALYSIS ===== -->
  {_section_header(4, "Gap Analysis")}
  {gap_cards}

  <!-- ===== RETRIEVAL PLAN / NEXT STEPS ===== -->
  {_section_header(5, "Retrieval Plan")}
  {next_cards}

  <!-- ===== AUDITOR MODE DIVIDER ===== -->
  <div class="auditor-divider">
    <h2>Full Report — Auditor Mode</h2>
    <p>Detailed narrative analysis with all source attributions</p>
  </div>

  <!-- ===== FULL REPORT BODY ===== -->
  <div class="report-body">
    {body_html}
  </div>

  <!-- ===== REFERENCES ===== -->
  {_section_header(6, "References")}
  <div class="references">
    {references_html}
  </div>

  <div class="disclaimer">
    <strong>Disclaimer:</strong> This report was generated by an automated deep-research system.
    While sources are verified where possible, findings should be independently validated
    before use in decision-making. Report generated {date}.
  </div>
</body>
</html>"""

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
