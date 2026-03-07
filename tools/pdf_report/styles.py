"""
CSS for the Intelligence Artifact PDF (WeasyPrint). Uses design tokens from tokens.py.
"""
from tools.pdf_report.tokens import (
    _N, _S, _A, _AD, _BG, _BD, _T, _TL, _G, _Y, _R, _P, _O,
    STATE_STABLE, STATE_TENTATIVE, STATE_CONTESTED, STATE_DECAYING,
    STATE_BG,
)


def get_css() -> str:
    """Return the full CSS string for the report."""
    return f"""
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
.cover {{
  width: 210mm; height: 297mm;
  background: linear-gradient(155deg, {_N} 0%, #162557 45%, {_AD} 100%);
  page-break-after: always;
  padding: 3cm 2.2cm 1.8cm 2.5cm;
  color: white;
  border-left: 5px solid {_A};
}}
.cover-tag {{ display: inline-block; padding: 4px 14px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.18); border-radius: 16px; font-size: 7pt; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.8); margin-bottom: 1.2cm; }}
.cover-title {{ font-size: 22pt; font-weight: 800; line-height: 1.15; letter-spacing: -0.02em; margin-bottom: 0.5cm; }}
.cover-question {{ font-size: 10pt; line-height: 1.5; color: rgba(255,255,255,0.7); font-style: italic; margin-bottom: 2cm; }}
.cover-grid {{ margin-top: 0.8cm; padding-top: 0.6cm; border-top: 1px solid rgba(255,255,255,0.12); }}
.cover-grid table {{ width: 100%; border-collapse: collapse; }}
.cover-grid td {{ padding: 4px 8px; vertical-align: top; text-align: center; }}
.cover-lbl {{ font-size: 6pt; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.4); margin-bottom: 2px; }}
.cover-val {{ font-size: 10pt; font-weight: 700; color: rgba(255,255,255,0.9); }}
.cover-foot {{ margin-top: 0.6cm; padding-top: 0.4cm; border-top: 1px solid rgba(255,255,255,0.08); }}
.cover-brand {{ font-size: 8pt; font-weight: 800; letter-spacing: 0.12em; color: rgba(255,255,255,0.55); display: inline-block; }}
.cover-date {{ font-size: 7.5pt; color: rgba(255,255,255,0.35); float: right; }}

/* ===== SECTION HEADERS ===== */
.sh {{ page: content; font-size: 13pt; font-weight: 800; color: {_N}; margin: 1.4em 0 0.5em; padding-bottom: 0.25em; border-bottom: 2px solid {_A}; display: flex; align-items: center; }}
.sh-n {{ display: inline-block; width: 24px; height: 24px; background: {_N}; color: white; font-size: 10pt; font-weight: 800; border-radius: 50%; text-align: center; line-height: 24px; margin-right: 10px; flex-shrink: 0; }}
.sh-sub {{ page: content; font-size: 9pt; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: {_TL}; margin: 1.2em 0 0.4em; }}

/* ===== OUTCOME LAYER ===== */
.epi-snap {{ page: content; margin: 0.8em 0 1em; }}
.epi-snap table {{ width: 100%; border-collapse: separate; border-spacing: 8px 0; }}
.epi-card {{ border-radius: 8px; padding: 10px 12px; text-align: center; border: 1px solid; }}
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
.cc-row {{ width: 100%; }}
.cc-row table {{ width: 100%; border-collapse: collapse; }}
.cc-row table td {{ padding: 0; vertical-align: top; }}
.cc-text {{ font-size: 9pt; font-weight: 600; color: {_N}; padding-right: 10px; line-height: 1.4; }}
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
.csm {{ page: content; width: 100%; border-collapse: collapse; margin: 0.6em 0 1em; font-size: 7.5pt; }}
.csm th {{ background: {_N}; color: white; font-weight: 700; font-size: 6pt; letter-spacing: 0.06em; text-transform: uppercase; padding: 5px 6px; text-align: left; }}
.csm td {{ padding: 5px 6px; border-bottom: 1px solid {_BD}; vertical-align: top; word-wrap: break-word; }}
.csm tr:nth-child(even) td {{ background: {_BG}; }}
.csm .claim-col {{ width: 35%; font-weight: 500; font-size: 7pt; line-height: 1.35; }}
.state-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
.conf-bar {{ display: inline-block; height: 5px; border-radius: 3px; vertical-align: middle; }}
.conf-bg {{ display: inline-block; width: 50px; height: 5px; background: {_BD}; border-radius: 3px; vertical-align: middle; }}

/* ===== BELIEF TRAJECTORY ===== */
.traj-wrap {{ page: content; width: 100%; border-collapse: collapse; margin: 0.5em 0 1em; font-size: 7pt; }}
.traj-wrap th {{ background: {_N}; color: white; font-weight: 700; font-size: 6pt; letter-spacing: 0.06em; text-transform: uppercase; padding: 5px 6px; text-align: left; }}
.traj-wrap td {{ padding: 5px 6px; border-bottom: 1px solid {_BD}; vertical-align: middle; font-size: 7pt; }}
.traj-wrap tr:nth-child(even) td {{ background: {_BG}; }}
.traj-flow {{ font-size: 7pt; color: {_S}; white-space: nowrap; }}

/* ===== EVIDENCE CLUSTER ===== */
.ev-cluster {{ page: content; border: 1px solid {_BD}; border-radius: 8px; padding: 12px 14px; margin: 0.5em 0; page-break-inside: avoid; }}
.ev-cluster-hdr {{ margin-bottom: 8px; }}
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
.action-card {{ page: content; background: white; border: 1px solid {_BD}; border-radius: 8px; padding: 10px 14px; margin: 0.4em 0; page-break-inside: avoid; }}
.action-card table {{ width: 100%; border-collapse: collapse; }}
.action-card table td {{ padding: 0; vertical-align: top; }}
.action-icon {{ width: 24px; height: 24px; border-radius: 6px; font-size: 8pt; font-weight: 800; color: white; text-align: center; line-height: 24px; }}
.action-monitor {{ background: {_P}; }}
.action-retrieve {{ background: {_A}; }}
.action-decide {{ background: {_G}; }}
.action-forecast {{ background: {_O}; }}
.action-body {{ padding-left: 10px; }}
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
