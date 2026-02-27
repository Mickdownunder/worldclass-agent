#!/usr/bin/env python3
"""
Multi-pass section-by-section synthesis for research-firm-grade reports (5K–15K words).
Replaces single-call synthesis: topic clustering, full source content, playbook-driven structure.

Usage:
  research_synthesize.py <project_id>
  Writes full markdown to stdout. Pipeline captures to ART/report.md and runs post-processing.
"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, llm_call, get_claims_for_synthesis

MAX_FINDINGS = 80
EXCERPT_CHARS = 2000
SOURCE_CONTENT_CHARS = 6000
SECTION_WORDS_MIN, SECTION_WORDS_MAX = 500, 1500


def _model() -> str:
    return os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gemini-2.0-flash")


def _load_findings(proj_path: Path, max_items: int = MAX_FINDINGS) -> list[dict]:
    findings = []
    for f in sorted((proj_path / "findings").glob("*.json")):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    return findings[:max_items]


def _load_sources(proj_path: Path) -> list[dict]:
    sources = []
    for f in (proj_path / "sources").glob("*.json"):
        if "_content" in f.name:
            continue
        try:
            sources.append(json.loads(f.read_text()))
        except Exception:
            pass
    return sources


def _load_source_content(proj_path: Path, url: str, max_chars: int = SOURCE_CONTENT_CHARS) -> str:
    import hashlib
    key = hashlib.sha256(url.encode()).hexdigest()[:12]
    cf = proj_path / "sources" / f"{key}_content.json"
    if not cf.exists():
        return ""
    try:
        d = json.loads(cf.read_text())
        text = (d.get("text") or d.get("abstract") or "").strip()
        return text[:max_chars]
    except Exception:
        return ""


def _cluster_findings(findings: list[dict], question: str, project_id: str) -> list[list[int]]:
    """Group findings into 3–7 thematic clusters. Returns list of clusters; each cluster = list of finding indices."""
    if len(findings) <= 3:
        return [list(range(len(findings)))]
    items = json.dumps(
        [{"i": i, "title": f.get("title"), "excerpt": (f.get("excerpt") or "")[:500]} for i, f in enumerate(findings)],
        indent=2, ensure_ascii=False
    )[:12000]
    system = """You are a research analyst. Group the numbered findings into 3–7 thematic clusters.
Return JSON: {"clusters": [[0,1,3], [2,5], [4,6,...], ...]} where each inner list is a list of finding indices (0-based).
Each finding index must appear in exactly one cluster. Preserve all indices."""
    user = f"QUESTION: {question}\n\nFINDINGS:\n{items}\n\nReturn only valid JSON with key 'clusters'."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
        out = json.loads(text)
        clusters = out.get("clusters", [])
        if isinstance(clusters, list) and all(isinstance(c, list) for c in clusters):
            return clusters
    except Exception:
        pass
    # Fallback: one cluster per 5 findings
    return [list(range(i, min(i + 5, len(findings)))) for i in range(0, len(findings), 5)]


def _outline_sections(question: str, clusters: list[list[int]], playbook_instructions: str | None, project_id: str) -> list[str]:
    """Return section titles for deep analysis (one per cluster)."""
    cluster_summaries = [f"Cluster {i+1}: {len(c)} findings" for i, c in enumerate(clusters)]
    extra = f"\nPlaybook instructions: {playbook_instructions}" if playbook_instructions else ""
    system = """You are a research analyst. Given the research question and cluster summary, propose section titles for the deep analysis.
Return JSON: {"sections": ["Section Title One", "Section Title Two", ...]} with one title per cluster, in order."""
    user = f"QUESTION: {question}\n\nCLUSTERS: {json.dumps(cluster_summaries)}{extra}\n\nReturn only valid JSON."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
        out = json.loads(text)
        sections = out.get("sections", [])
        if isinstance(sections, list) and len(sections) >= len(clusters):
            return sections[:len(clusters)]
    except Exception:
        pass
    return [f"Analysis: Topic {i+1}" for i in range(len(clusters))]


def _build_ref_map(findings: list[dict], claim_ledger: list[dict]) -> tuple[dict[str, int], list[tuple[str, str]]]:
    """Build url -> ref number (1-based) and ordered list (url, title) for References."""
    cited = set()
    for c in claim_ledger:
        for u in (c.get("supporting_source_ids") or []):
            cited.add(u.strip())
    for f in findings:
        u = (f.get("url") or "").strip()
        if u:
            cited.add(u)
    ref_list = sorted(cited)
    ref_map = {u: i + 1 for i, u in enumerate(ref_list)}
    titles = {}
    for f in findings:
        u = (f.get("url") or "").strip()
        if u and f.get("title"):
            titles[u] = f["title"]
    ref_list_with_titles = [(u, titles.get(u, "")) for u in ref_list]
    return ref_map, ref_list_with_titles


def _detect_gaps(section_body: str, section_title: str, question: str, project_id: str) -> list[dict]:
    """WARP-style gap detection: LLM returns list of {description, suggested_query} where evidence is insufficient."""
    if not section_body or len(section_body) < 200:
        return []
    system = """You are a research analyst. Given a draft section, identify 0-3 GAPS where evidence is missing or weak.
Return JSON: {"gaps": [{"description": "what is missing", "suggested_query": "search query to find evidence"}]}.
If the section is well-supported, return {"gaps": []}. Output only valid JSON."""
    user = f"QUESTION: {question}\n\nSECTION: {section_title}\n\nDRAFT:\n{section_body[:4000]}\n\nReturn JSON with key 'gaps'."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
        out = json.loads(text)
        gaps = out.get("gaps", [])
        return gaps[:3] if isinstance(gaps, list) else []
    except Exception:
        return []


def _synthesize_section(
    section_title: str,
    findings_for_section: list[dict],
    ref_map: dict[str, int],
    proj_path: Path,
    question: str,
    project_id: str,
    rel_sources: dict,
) -> str:
    """One LLM call for one deep-analysis section (500–1500 words)."""
    ref_lines = []
    for f in findings_for_section[:15]:
        url = (f.get("url") or "").strip()
        ref_num = ref_map.get(url)
        if ref_num:
            ref_lines.append(f"[{ref_num}] {url} — {(f.get('title') or '')[:60]}")
    ref_block = "\n".join(ref_lines[:20])
    excerpts = []
    for f in findings_for_section[:15]:
        url = (f.get("url") or "").strip()
        ref_num = ref_map.get(url, "?")
        exc = (f.get("excerpt") or "")[:EXCERPT_CHARS]
        low = rel_sources.get(url, {}).get("reliability_score", 1) < 0.3
        tag = " [LOW RELIABILITY]" if low else ""
        excerpts.append(f"[{ref_num}] {url}{tag}\n{exc}")
    content_block = "\n\n---\n\n".join(excerpts)
    # Top 3–5 source full content
    urls_in_section = list({(f.get("url") or "").strip() for f in findings_for_section if f.get("url")})[:5]
    full_content = []
    for u in urls_in_section:
        text = _load_source_content(proj_path, u)
        if text:
            full_content.append(f"Source {u}:\n{text[:SOURCE_CONTENT_CHARS]}")
    full_block = "\n\n".join(full_content) if full_content else "(no full content)"
    system = """You are a research analyst. Write a single analytical section of a professional report.
Use inline citations as [1], [2] etc. to match the reference list provided. Write 500–1500 words.
State confidence where relevant (e.g. "HIGH confidence (3 sources)" or "LOW (single source)").
Do not repeat URLs in the body; use only [N] references."""
    user = f"""RESEARCH QUESTION: {question}

SECTION TITLE: {section_title}

REFERENCE MAPPING (use these numbers in citations):
{ref_block}

FINDINGS FOR THIS SECTION:
{content_block}

FULL SOURCE CONTENT (use for depth):
{full_block[:20000]}

Write the section markdown (no title repeated; start with body)."""
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception as e:
        return f"*Section synthesis failed: {e}*"


def _synthesize_exec_summary(full_report_body: str, question: str, project_id: str) -> str:
    """Generate executive summary last (300–500 words)."""
    system = """You are a research analyst. Write an Executive Summary (300–500 words) that stands alone and answers the research question.
Include confidence level and key takeaways. Do not use citations [N] in the summary."""
    user = f"RESEARCH QUESTION: {question}\n\nFULL REPORT (excerpt):\n{full_report_body[:12000]}\n\nWrite only the Executive Summary section (no heading)."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception:
        return ""


def _synthesize_conclusions_next_steps(thesis: dict, contradictions: list, question: str, project_id: str) -> tuple[str, str]:
    """Conclusions (300–500 words) and Recommended Next Steps (200–400 words)."""
    system = """You are a research analyst. Given thesis and contradictions, produce two sections.
Return JSON: {"conclusions": "markdown text 300-500 words", "next_steps": "markdown text 200-400 words, prioritized list with [HIGH]/[MEDIUM]."}"""
    user = f"QUESTION: {question}\nTHESIS: {thesis.get('current', '')} (confidence: {thesis.get('confidence', 0)})\nCONTRADICTIONS: {json.dumps(contradictions)[:2000]}\n\nReturn only valid JSON."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
        out = json.loads(text)
        return out.get("conclusions", ""), out.get("next_steps", "")
    except Exception:
        return thesis.get("current", ""), "1. [HIGH] Run additional verification.\n2. [MEDIUM] Expand source set."


def _key_numbers(findings: list[dict], claim_ledger: list[dict], project_id: str = "") -> str:
    """Extract 5–10 key data points for KEY NUMBERS box."""
    system = """From the findings and claims, extract 5–10 KEY NUMBERS (dates, amounts, counts, percentages).
Return JSON: {"key_numbers": ["**$116M** | Series B", "**28 Feb 2025** | Launch date", ...]}.
One line per item, bold the number. Only include verified or clearly sourced data."""
    items = json.dumps(
        [{"excerpt": (f.get("excerpt") or "")[:400]} for f in findings[:30]],
        ensure_ascii=False
    )[:8000]
    claims = json.dumps([c.get("text", "")[:200] for c in claim_ledger[:20]], ensure_ascii=False)[:4000]
    user = f"FINDINGS:\n{items}\n\nCLAIMS:\n{claims}\n\nReturn only valid JSON."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
        out = json.loads(text)
        nums = out.get("key_numbers", [])
        if isinstance(nums, list):
            return "\n".join(nums[:10])
    except Exception:
        pass
    return "**—** | Key numbers to be filled from findings."


SYNTHESIZE_CHECKPOINT = "synthesize_checkpoint.json"

# Hard synthesis contract (Spec §6.2–6.3): no new claims; every claim-bearing sentence maps to ledger.
def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _is_claim_like_sentence(sentence: str) -> bool:
    """Heuristic: sentence that looks like a factual claim (length + signals)."""
    s = (sentence or "").strip()
    words = s.split()
    if len(words) < 10:
        return False
    lower = s.lower()
    signals = ("found that", "study shows", "report states", "data indicate", "percent", "%", "research suggests", "evidence shows", "according to")
    if any(sig in lower for sig in signals):
        return True
    if any(c.isdigit() for c in s):
        return True
    return len(words) >= 18  # Long declarative sentence likely a claim


def _sentence_overlaps_claim(sentence: str, claim_texts_normalized: list[str]) -> bool:
    """True if sentence overlaps substantially with any claim text (substring or word overlap)."""
    norm = _normalize_for_match(sentence)
    if not norm:
        return False
    words = set(re.findall(r"\b[a-z0-9]{2,}\b", norm))
    for ct in claim_texts_normalized:
        if norm in ct or ct in norm:
            return True
        cw = set(re.findall(r"\b[a-z0-9]{2,}\b", ct))
        if cw and words and len(words & cw) / max(len(words), 1) >= 0.25:
            return True
    return False


def validate_synthesis_contract(report: str, claim_ledger: list[dict], mode: str) -> dict:
    """
    Returns dict: unreferenced_claim_sentence_count, new_claims_in_synthesis (same), tentative_labels_ok, valid.
    valid = (unreferenced == 0 and new_claims == 0) and (tentative_labels_ok or mode != "strict").
    """
    claim_texts = [c.get("text") or "" for c in claim_ledger if (c.get("text") or "").strip()]
    claim_texts_normalized = [_normalize_for_match(t) for t in claim_texts]
    unreferenced = 0
    sentences = re.split(r"[.!?]\s+", report)
    for sent in sentences:
        if not _is_claim_like_sentence(sent):
            continue
        if not _sentence_overlaps_claim(sent, claim_texts_normalized):
            unreferenced += 1
    tentative_ok = True
    tentative_claims = [c for c in claim_ledger if (c.get("falsification_status") or "").strip() == "PASS_TENTATIVE"]
    if tentative_claims:
        report_lower = report.lower()
        for c in tentative_claims:
            text_snippet = (c.get("text") or "")[:60]
            if text_snippet and _normalize_for_match(text_snippet) not in _normalize_for_match(report):
                continue
            if "tentative" not in report_lower and "[tentative]" not in report_lower and "pass_tentative" not in report_lower:
                tentative_ok = False
                break
    valid = unreferenced == 0 and tentative_ok
    if mode == "strict":
        valid = valid and unreferenced == 0
    return {
        "unreferenced_claim_sentence_count": unreferenced,
        "new_claims_in_synthesis": unreferenced,
        "tentative_labels_ok": tentative_ok,
        "valid": valid,
    }


class SynthesisContractError(Exception):
    """Raised when synthesis violates hard contract and mode is strict."""
    pass


def _load_checkpoint(proj_path: Path) -> dict | None:
    p = proj_path / SYNTHESIZE_CHECKPOINT
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if not isinstance(data.get("clusters"), list) or not isinstance(data.get("section_titles"), list) or not isinstance(data.get("bodies"), list):
            return None
        return data
    except Exception:
        return None


def _save_checkpoint(proj_path: Path, clusters: list, section_titles: list, bodies: list) -> None:
    p = proj_path / SYNTHESIZE_CHECKPOINT
    try:
        p.write_text(json.dumps({"clusters": clusters, "section_titles": section_titles, "bodies": bodies}, indent=2, ensure_ascii=False))
    except Exception:
        pass


def _clear_checkpoint(proj_path: Path) -> None:
    (proj_path / SYNTHESIZE_CHECKPOINT).unlink(missing_ok=True)


def run_synthesis(project_id: str) -> str:
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    project = load_project(proj_path)
    question = project.get("question", "")
    verify_dir = proj_path / "verify"
    findings = _load_findings(proj_path)
    sources = _load_sources(proj_path)
    # Dual-source: AEM claims/ledger.jsonl or fallback verify/claim_ledger.json (Spec §6.1)
    claim_ledger = get_claims_for_synthesis(proj_path)
    contradictions = []
    if (proj_path / "contradictions.json").exists():
        try:
            contradictions = json.loads((proj_path / "contradictions.json").read_text()).get("contradictions", [])
        except Exception:
            pass
    rel_sources = {}
    if (verify_dir / "source_reliability.json").exists():
        try:
            rel = json.loads((verify_dir / "source_reliability.json").read_text())
            rel_sources = {s.get("url"): s for s in rel.get("sources", [])}
        except Exception:
            pass
    thesis = {}
    if (proj_path / "thesis.json").exists():
        try:
            thesis = json.loads((proj_path / "thesis.json").read_text())
        except Exception:
            pass
    if not isinstance(thesis, dict):
        thesis = {}

    ref_map, ref_list = _build_ref_map(findings, claim_ledger)

    ck = _load_checkpoint(proj_path)
    if ck and len(ck["bodies"]) > 0 and len(ck["bodies"]) <= len(ck.get("section_titles", [])):
        clusters = ck["clusters"]
        section_titles = ck["section_titles"]
        deep_parts = [f"## {section_titles[i]}\n\n{ck['bodies'][i]}" for i in range(len(ck["bodies"]))]
        start_index = len(ck["bodies"])
    else:
        clusters = _cluster_findings(findings, question, project_id)
        playbook_id = (project.get("config") or {}).get("playbook_id")
        playbook_instructions = None
        if playbook_id:
            playbook_path = proj_path.parent / "playbooks" / f"{playbook_id}.json"
            if not playbook_path.exists():
                playbook_path = Path(os.environ.get("OPERATOR_ROOT", "/root/operator")) / "research" / "playbooks" / f"{playbook_id}.json"
            if playbook_path.exists():
                try:
                    pb = json.loads(playbook_path.read_text())
                    playbook_instructions = pb.get("synthesis_instructions")
                except Exception:
                    pass
        try:
            from tools.research_progress import step as progress_step
            progress_step(project_id, "Generating outline")
        except Exception:
            pass
        section_titles = _outline_sections(question, clusters, playbook_instructions, project_id)
        deep_parts = []
        start_index = 0

    now = datetime.now(timezone.utc)
    report_date = now.strftime("%Y-%m-%d")
    ts = now.strftime("%Y%m%dT%H%M%SZ")

    parts = []
    parts.append(f"# Research Report\n\n**Report as of: {report_date}**  \nProject: `{project_id}`  \nQuestion: {question}\n")
    parts.append("\n## KEY NUMBERS\n\n")
    parts.append(_key_numbers(findings, claim_ledger, project_id))
    parts.append("\n\n---\n\n")

    checkpoint_bodies = list(ck["bodies"]) if (ck and ck.get("bodies")) else []
    for i in range(start_index, len(clusters)):
        cluster = clusters[i]
        title = section_titles[i] if i < len(section_titles) else f"Analysis: Topic {i+1}"
        section_findings = [findings[j] for j in cluster if 0 <= j < len(findings)]
        if not section_findings:
            checkpoint_bodies.append("_No findings for this cluster._")
            deep_parts.append(f"## {title}\n\n_No findings for this cluster._")
            _save_checkpoint(proj_path, clusters, section_titles, checkpoint_bodies)
            continue
        try:
            from tools.research_progress import step as progress_step
            progress_step(project_id, f"Writing section {i+1}/{len(clusters)}: {title}", i+1, len(clusters))
        except Exception:
            pass
        body = _synthesize_section(title, section_findings, ref_map, proj_path, question, project_id, rel_sources)
        if os.environ.get("RESEARCH_WARP_DEEPEN") == "1" and i == 0 and len(body) > 300:
            try:
                from tools.research_progress import step as progress_step
                progress_step(project_id, "Deepening gaps")
            except Exception:
                pass
            gaps = _detect_gaps(body, title, question, project_id)
            if gaps and gaps[0].get("suggested_query"):
                try:
                    from tools.research_web_search import search_brave, search_serper
                    from tools.research_common import load_secrets
                    secrets = load_secrets()
                    q = gaps[0]["suggested_query"][:100]
                    res = search_brave(q, 5) if secrets.get("BRAVE_API_KEY") else (search_serper(q, 5) if secrets.get("SERPER_API_KEY") else [])
                    if res and len(res) > 0:
                        url = res[0].get("url", "")
                        if url:
                            import subprocess
                            r = subprocess.run(
                                [sys.executable, str(Path(__file__).resolve().parent / "research_web_reader.py"), url],
                                capture_output=True, text=True, timeout=30, cwd=str(Path(__file__).resolve().parent.parent)
                            )
                            if r.returncode == 0:
                                try:
                                    wr = json.loads(r.stdout)
                                    if wr.get("text"):
                                        new_f = {"url": url, "title": wr.get("title", ""), "excerpt": (wr.get("text") or "")[:1500]}
                                        section_findings = section_findings + [new_f]
                                        body = _synthesize_section(title, section_findings, ref_map, proj_path, question, project_id, rel_sources)
                                except Exception:
                                    pass
                except Exception:
                    pass
        checkpoint_bodies.append(body)
        deep_parts.append(f"## {title}\n\n{body}")
        _save_checkpoint(proj_path, clusters, section_titles, checkpoint_bodies)
    parts.append("\n\n".join(deep_parts))
    parts.append("\n\n---\n\n")

    # Methodology (auto)
    source_count = len(sources)
    read_count = len(list((proj_path / "sources").glob("*_content.json")))
    parts.append("## Methodology\n\n")
    parts.append(f"This report is based on **{len(findings)} findings** from **{source_count} sources** ")
    parts.append(f"({read_count} successfully read). ")
    parts.append(f"Synthesis model: {_model()}. Verification and claim ledger applied. ")
    parts.append(f"Report generated at {ts}.\n\n")

    # Contradictions
    if contradictions:
        parts.append("## Contradictions & Open Questions\n\n")
        for c in contradictions[:10]:
            parts.append(f"- **{c.get('claim', c.get('topic', 'Unknown'))}**: {c.get('summary', c.get('description', ''))}\n")
        parts.append("\n")

    # Verification Summary table (Tentative label for PASS_TENTATIVE per Spec §6.3)
    parts.append("## Verification Summary\n\n| # | Claim | Status | Sources |\n| --- | --- | --- | ---|\n")
    for i, c in enumerate(claim_ledger[:25], 1):
        text = (c.get("text") or "")[:80].replace("|", " ")
        fstatus = (c.get("falsification_status") or "").strip()
        if fstatus == "PASS_TENTATIVE":
            status = "TENTATIVE"
        elif c.get("is_verified"):
            status = "VERIFIED"
        else:
            status = "UNVERIFIED"
        n_src = len(c.get("supporting_source_ids") or [])
        parts.append(f"| {i} | {text}... | {status} | {n_src} |\n")
    parts.append("\n")

    # Conclusions & Next Steps
    concl, next_steps = _synthesize_conclusions_next_steps(thesis, contradictions, question, project_id)
    parts.append("## Conclusions & Thesis\n\n")
    parts.append(concl)
    parts.append("\n\n## Recommended Next Steps\n\n")
    parts.append(next_steps)
    parts.append("\n\n---\n\n")

    # Executive Summary (generated last, inserted after KEY NUMBERS)
    _clear_checkpoint(proj_path)
    full_so_far = "\n".join(parts)
    exec_summary = _synthesize_exec_summary(full_so_far, question, project_id)
    insert_idx = full_so_far.find("## Methodology")
    if insert_idx > 0 and exec_summary:
        report_body = (
            full_so_far[:insert_idx] +
            "\n## Executive Summary\n\n" + exec_summary + "\n\n---\n\n" +
            full_so_far[insert_idx:]
        )
    else:
        report_body = full_so_far

    # Appendices & References
    report_body += "\n\n## Appendix A: Source Details\n\n| # | Title | URL | Type | Reliability |\n| --- | --- | --- | --- | --- |\n"
    for i, (url, title) in enumerate(ref_list[:50], 1):
        rel = rel_sources.get(url, {})
        score = rel.get("reliability_score", "")
        report_body += f"| {i} | {(title or '')[:50]} | {url[:60]}... | web | {score} |\n"
    report_body += "\n\n## Appendix B: Methodology Details\n\n"
    report_body += f"- Synthesis model: {_model()}\n- Findings cap: {MAX_FINDINGS}\n- Report timestamp: {ts}\n\n"
    report_body += "## References\n\n"
    for i, (url, title) in enumerate(ref_list, 1):
        if title:
            report_body += f"[{i}] {title}  \n    {url}\n\n"
        else:
            report_body += f"[{i}] {url}\n\n"

    # Hard synthesis contract (Spec §6.2–6.3): validate; strict/enforce block on violation
    mode = (os.environ.get("AEM_ENFORCEMENT_MODE") or "observe").strip().lower()
    if mode not in ("observe", "enforce", "strict"):
        mode = "observe"
    validation = validate_synthesis_contract(report_body, claim_ledger, mode)
    if not validation["valid"] and mode in ("enforce", "strict"):
        raise SynthesisContractError(
            f"Synthesis contract violation: unreferenced_claim_sentence_count={validation['unreferenced_claim_sentence_count']}, "
            f"new_claims_in_synthesis={validation['new_claims_in_synthesis']}, tentative_labels_ok={validation['tentative_labels_ok']}"
        )

    return report_body


def main():
    if len(sys.argv) < 2:
        print("Usage: research_synthesize.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    try:
        report = run_synthesis(project_id)
        print(report)
    except Exception as e:
        print(f"# Synthesis Error\n\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
