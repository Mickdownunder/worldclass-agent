"""
Build HTML sections for the Intelligence Artifact PDF (cover, outcome layer, claim map, etc.).
"""
import json
import re
from pathlib import Path

from tools.pdf_report.tokens import esc, STATE_COLORS, STATE_BG, _N, _A, _G, _Y, _R, _TL, _BD, _BG, _AD, _P, _O
from tools.pdf_report import claims


def section_header(n, text):
    return f'<div class="sh"><span class="sh-n">{n}</span><span>{esc(text)}</span></div>'


def build_cover(title, question, status, sources, duration, cost, date, project_id, epi_counts):
    epi_str = f"{epi_counts.get('stable',0)} stable &middot; {epi_counts.get('tentative',0)} tentative &middot; {epi_counts.get('contested',0)} contested"
    return f"""<div class="cover">
  <div class="cover-tag">Intelligence Artifact &middot; AEM</div>
  <div class="cover-title">{esc(title)}</div>
  <div class="cover-question">{esc(question)}</div>
  <div class="cover-grid">
    <table><tr>
      <td><div class="cover-lbl">Status</div><div class="cover-val">{esc(status)}</div></td>
      <td><div class="cover-lbl">Epistemic State</div><div class="cover-val">{epi_str}</div></td>
      <td><div class="cover-lbl">Sources</div><div class="cover-val">{sources}</div></td>
      <td><div class="cover-lbl">Duration</div><div class="cover-val">{esc(duration)}</div></td>
      <td><div class="cover-lbl">Cost</div><div class="cover-val">{cost}</div></td>
    </tr></table>
  </div>
  <div class="cover-foot">
    <span class="cover-brand">OPENCLAW OPERATOR</span>
    <span class="cover-date">{date}</span>
  </div>
</div>
<div class="proj-label">{esc(project_id)}</div>"""


def build_outcome_layer(enriched_claims, exec_summary, epi_counts):
    import markdown as _mk

    snap = f"""<div class="epi-snap"><table><tr>
  <td><div class="epi-card epi-stable"><div class="ev">{epi_counts.get('stable',0)}</div><div class="el">Stable</div></div></td>
  <td><div class="epi-card epi-tentative"><div class="ev">{epi_counts.get('tentative',0)}</div><div class="el">Tentative</div></div></td>
  <td><div class="epi-card epi-contested"><div class="ev">{epi_counts.get('contested',0)}</div><div class="el">Contested</div></div></td>
  <td><div class="epi-card epi-unresolved"><div class="ev">{epi_counts.get('unresolved',0)}</div><div class="el">Unresolved</div></div></td>
</tr></table></div>"""

    cards = []
    for ec in enriched_claims[:5]:
        state = ec["state"]
        conf_lbl, conf_cls = claims.confidence_label(ec["confidence"])
        color = STATE_COLORS.get(state, _TL)
        relevance = "Decision-relevant" if ec["confidence"] >= 0.9 else ("Context-relevant" if ec["confidence"] >= 0.7 else "Needs validation")
        cards.append(f"""<div class="conclusion-card" style="border-left-color:{color};">
  <div class="cc-row"><table><tr>
    <td class="cc-text">{esc(ec['text'][:200])}</td>
    <td style="width:80px;text-align:right;"><span class="badge b-{state}">{state}</span></td>
  </tr></table></div>
  <div class="cc-rel"><span class="badge {conf_cls}">{conf_lbl} confidence</span> &nbsp; {esc(relevance)}</div>
</div>""")

    sa_html = _mk.markdown(exec_summary, extensions=["smarty"]) if exec_summary else '<p class="empty-note">No executive summary available.</p>'

    return f"""{snap}
<div class="sh-sub">Research Conclusions</div>
{"".join(cards)}
<div class="sh-sub">Short Answer</div>
<div style="page:content;background:{_BG};border:1px solid {_BD};border-left:4px solid {_A};border-radius:0 8px 8px 0;padding:12px 16px;margin:0.8em 0;font-size:9pt;line-height:1.6;">
{sa_html}
</div>"""


def build_claim_state_map(enriched_claims):
    if not enriched_claims:
        return '<p class="empty-note">No claims extracted.</p>'
    rows = []
    for ec in enriched_claims:
        state = ec["state"]
        color = STATE_COLORS.get(state, _TL)
        conf = ec["confidence"]
        conf_pct = int(conf * 100)
        conf_lbl, _ = claims.confidence_label(conf)
        n_ev = len(ec.get("sources", []))
        failure = ec.get("failure_boundary", "—")
        conf_color = _G if conf >= 0.9 else (_Y if conf >= 0.7 else _R)
        rows.append(f"""<tr>
  <td class="claim-col">{esc(ec['text'][:150])}</td>
  <td><span class="state-dot" style="background:{color};"></span>{state}</td>
  <td><span class="conf-bg"><span class="conf-bar" style="width:{conf_pct}%;background:{conf_color};"></span></span> {conf_pct}%</td>
  <td>{n_ev}</td>
  <td>{esc(ec.get('counter', '—'))}</td>
  <td style="font-size:7pt;">{esc(failure)}</td>
</tr>""")

    return f"""<table class="csm">
  <tr><th>Claim</th><th>State</th><th>Confidence</th><th>Evidence</th><th>Counter</th><th>Failure Boundary</th></tr>
  {"".join(rows)}
</table>"""


def build_belief_trajectory(enriched_claims, phase_history):
    if not enriched_claims:
        return '<p class="empty-note">No belief trajectory data.</p>'

    rows = []
    for ec in enriched_claims[:5]:
        state = ec["state"]
        color = STATE_COLORS.get(state, _TL)
        n_src = len(ec.get("sources", []))
        ver = "Pass" if ec.get("verified") else "Fail"
        flow = f'Hypothesis &rarr; {n_src} sources &rarr; {ver} &rarr; <strong style="color:{color};">{state.upper()}</strong>'
        rows.append(f"""<tr>
  <td style="width:55%;">{esc(ec['text'][:100])}</td>
  <td class="traj-flow">{flow}</td>
  <td style="text-align:center;"><span class="badge b-{state}">{state}</span></td>
</tr>""")

    return f"""<table class="traj-wrap">
  <tr><th>Claim</th><th>Trajectory</th><th>State</th></tr>
  {"".join(rows)}
</table>"""


def build_evidence_landscape(source_reliability):
    if not source_reliability:
        return '<p class="empty-note">No source reliability data.</p>'

    strong = [(s, re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s.get("url", ""))) for s in source_reliability if s.get("reliability_score", 0) >= 0.8]
    moderate = [(s, re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s.get("url", ""))) for s in source_reliability if 0.5 <= s.get("reliability_score", 0) < 0.8]
    sparse = [(s, re.sub(r"https?://(?:www\.)?([^/]+).*", r"\1", s.get("url", ""))) for s in source_reliability if s.get("reliability_score", 0) < 0.5]

    def cluster_html(items, cls, label):
        if not items:
            return ""
        lis = "".join(f'<li>{esc(domain)} ({int(s.get("reliability_score",0)*100)}%)</li>' for s, domain in items[:8])
        return f"""<div class="ev-cluster {cls}">
  <div class="ev-cluster-hdr"><span class="ev-cluster-title">{label}</span> <span class="ev-cluster-count">({len(items)} sources)</span></div>
  <ul>{lis}</ul>
</div>"""

    return (
        cluster_html(strong, "cluster-strong", "Strong Evidence Cluster (≥80% reliability)")
        + cluster_html(moderate, "cluster-moderate", "Moderate Evidence Cluster (50–79%)")
        + cluster_html(sparse, "cluster-sparse", "Sparse / Weak Zone (<50%)")
        or '<p class="empty-note">No source clusters.</p>'
    )


def build_disagreement_layer(gaps, enriched_claims=None):
    from tools.pdf_report.tokens import STATE_CONTESTED

    rows = []

    for title, desc in (gaps or []):
        pos_a = desc if desc else title
        pos_b = "Insufficient data to establish counter-position"
        resolution = "Additional primary sources required"
        if "unclear" in desc.lower() or "unspecified" in desc.lower():
            resolution = "Clarification from authoritative source needed"
        elif "unavailable" in desc.lower() or "lacking" in desc.lower():
            resolution = "Data collection / FOIA / financial disclosure"
        rows.append(f"""<tr>
  <td><strong>{esc(title[:80])}</strong></td>
  <td style="font-size:7pt;">{esc(pos_a[:100])}</td>
  <td style="font-size:7pt;">{esc(pos_b)}</td>
  <td style="font-size:7pt;">{esc(resolution)}</td>
</tr>""")

    for ec in (enriched_claims or []):
        if ec.get("state") != STATE_CONTESTED:
            continue
        text_short = ec["text"][:80]
        rows.append(f"""<tr>
  <td><strong>{esc(text_short)}</strong></td>
  <td style="font-size:7pt;">Claim not verified ({int(ec['confidence']*100)}% conf, {len(ec.get('sources',[]))} source(s))</td>
  <td style="font-size:7pt;">Requires independent corroboration</td>
  <td style="font-size:7pt;">{esc(ec.get('failure_boundary','—'))}</td>
</tr>""")

    if not rows:
        return '<p class="empty-note">No disagreements or contradictions identified.</p>'

    return f"""<table class="dis-table">
  <tr><th>Topic</th><th>Position A</th><th>Position B</th><th>Resolution Condition</th></tr>
  {"".join(rows[:6])}
</table>"""


def build_insight_layer(conclusion, key_findings, weaknesses):
    def _clean_md(text):
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        return text.strip()

    structural = ""
    pattern_ins = ""
    decision = ""

    if key_findings and len(key_findings) >= 1:
        kf = key_findings[0]
        structural = _clean_md(f"{kf[0]}: {kf[1]}" if kf[1] else kf[0])
    if key_findings and len(key_findings) >= 2:
        kf = key_findings[1]
        pattern_ins = _clean_md(f"{kf[0]}: {kf[1]}" if kf[1] else kf[0])

    if not structural and conclusion:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', _clean_md(conclusion)) if s.strip() and len(s) > 20]
        structural = sentences[0] if len(sentences) > 0 else ""
        if not pattern_ins:
            pattern_ins = sentences[1] if len(sentences) > 1 else ""

    if weaknesses:
        decision = f"Key gap: {_clean_md(weaknesses[0])}"
    elif conclusion:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', _clean_md(conclusion)) if s.strip() and len(s) > 20]
        decision = sentences[-1] if len(sentences) > 2 else ""

    cards = []
    if structural:
        cards.append(f'<div class="insight-card insight-structural"><div class="insight-type">Structural Insight</div><div class="insight-text">{esc(structural[:300])}</div></div>')
    if pattern_ins:
        cards.append(f'<div class="insight-card insight-pattern"><div class="insight-type">Pattern Insight</div><div class="insight-text">{esc(pattern_ins[:300])}</div></div>')
    if decision:
        cards.append(f'<div class="insight-card insight-decision"><div class="insight-type">Decision Insight</div><div class="insight-text">{esc(decision[:300])}</div></div>')

    return "\n".join(cards) or '<p class="empty-note">No insights derived.</p>'


def build_action_layer(next_steps, suggestions, weaknesses):
    def _strip_md(t):
        t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
        t = re.sub(r'\*(.+?)\*', r'\1', t)
        return t.strip()

    actions = []

    for w in weaknesses[:2]:
        actions.append(("monitor", "Monitoring Trigger", _strip_md(w)))

    for s in suggestions[:2]:
        actions.append(("retrieve", "Next Retrieval", _strip_md(s)))

    for title, desc in next_steps[:2]:
        text = _strip_md(f"{title}: {desc}" if desc else title)
        actions.append(("decide", "Decision Implication", text))

    if len(next_steps) > 2:
        for title, desc in next_steps[2:4]:
            text = _strip_md(f"{title}: {desc}" if desc else title)
            actions.append(("forecast", "Forecast Item", text))

    if not actions:
        return '<p class="empty-note">No actions derived.</p>'

    icons = {"monitor": ("M", "action-monitor"), "retrieve": ("R", "action-retrieve"), "decide": ("D", "action-decide"), "forecast": ("F", "action-forecast")}
    cards = []
    for kind, label, text in actions:
        icon_letter, icon_cls = icons.get(kind, ("?", "action-monitor"))
        cards.append(f"""<div class="action-card"><table><tr>
  <td style="width:30px;"><div class="action-icon {icon_cls}">{icon_letter}</div></td>
  <td><div class="action-body"><div class="ab-type">{label}</div><div class="ab-text">{esc(text[:250])}</div></div></td>
</tr></table></div>""")

    return "\n".join(cards)


def build_references_html(proj_dir, claim_ledger):
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
            lines.append(f'<li><a href="{esc(url)}">{esc(title)}</a><br/><span class="ref-url">{esc(url)}</span></li>')
        else:
            lines.append(f'<li><a href="{esc(url)}">{esc(url)}</a></li>')
    return f"<ol>{''.join(lines)}</ol>"
