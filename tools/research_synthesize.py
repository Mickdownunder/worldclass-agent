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
    return os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gemini-3.1-pro-preview")


def _relevance_score(finding: dict, question: str) -> float:
    """Score finding relevance to research question via keyword overlap."""
    q_words = set(re.findall(r'\b[a-z]{3,}\b', question.lower()))
    text = ((finding.get("excerpt") or "") + " " + (finding.get("title") or "")).lower()
    f_words = set(re.findall(r'\b[a-z]{3,}\b', text))
    if not q_words or not f_words:
        return 0.0
    return len(q_words & f_words) / len(q_words)


def _load_findings(proj_path: Path, max_items: int = MAX_FINDINGS, question: str = "") -> list[dict]:
    findings = []
    for f in sorted((proj_path / "findings").glob("*.json")):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    if question and findings:
        findings.sort(key=lambda f: _relevance_score(f, question), reverse=True)
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


def _build_claim_source_registry(
    claim_ledger: list[dict],
    sources: list[dict],
    ref_list_with_titles: list[tuple[str, str]],
) -> str:
    """Build Claim Evidence Registry table: claim (short) | source | URL | date | tier. No LLM."""
    url_to_title = dict(ref_list_with_titles)
    url_to_date = {}
    for s in sources:
        u = (s.get("url") or "").strip()
        if u:
            url_to_date[u] = (s.get("published_date") or s.get("date") or "").strip()[:20]
    lines = ["| # | Claim (short) | Source | URL | Date | Tier |", "| --- | --- | --- | --- | --- | --- |"]
    for i, c in enumerate(claim_ledger[:50], 1):
        text = (c.get("text") or "")[:60].replace("|", " ").replace("\n", " ")
        urls = c.get("supporting_source_ids") or []
        first_url = urls[0] if urls else ""
        title = (url_to_title.get(first_url) or "").strip()[:50].replace("|", " ")
        url_short = (first_url[:55] + "...") if len(first_url) > 55 else first_url
        date = url_to_date.get(first_url, "")
        tier = (c.get("verification_tier") or "").strip() or "UNVERIFIED"
        lines.append(f"| {i} | {text} | {title} | {url_short} | {date} | {tier} |")
    return "\n".join(lines)


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


def _claim_ledger_block(claim_ledger: list[dict]) -> str:
    """Build CLAIM LEDGER text for section prompt: one line per claim_ref with short text."""
    lines = []
    for c in claim_ledger[:40]:
        cid = (c.get("claim_id") or "").strip()
        if not cid:
            continue
        ver = c.get("claim_version", 1)
        try:
            ver = int(ver)
        except (TypeError, ValueError):
            ver = 1
        text = (c.get("text") or "")[:120].replace("\n", " ")
        lines.append(f"[claim_ref: {cid}@{ver}] {text}")
    return "\n".join(lines) if lines else ""


def _extract_section_key_points(body: str, max_points: int = 5) -> list[str]:
    """Extract 3-5 key points from a section body for anti-repetition (no LLM)."""
    points = []
    for para in (body or "").split("\n\n"):
        para = para.strip()
        if not para or len(para) < 30:
            continue
        first = re.sub(r"\s+", " ", para)[:150].strip()
        if first and first not in points:
            points.append(first)
        if len(points) >= max_points:
            break
    return points[:max_points]


def _synthesize_section(
    section_title: str,
    findings_for_section: list[dict],
    ref_map: dict[str, int],
    proj_path: Path,
    question: str,
    project_id: str,
    rel_sources: dict,
    claim_ledger: list[dict] | None = None,
    previous_sections_summary: list[str] | None = None,
) -> str:
    """One LLM call for one deep-analysis section (500–1500 words). When claim_ledger is provided, section must use [claim_ref: id@version] for every claim-bearing sentence."""
    claim_ledger = claim_ledger or []
    previous_sections_summary = previous_sections_summary or []
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

    claim_block = _claim_ledger_block(claim_ledger)
    system = """You are a research analyst. Write a single analytical section of a professional report.
Use inline citations as [1], [2] etc. to match the reference list provided. Write 500–1500 words.
State confidence where relevant (e.g. "HIGH confidence (3 sources)" or "LOW (single source)").
Do not repeat URLs in the body; use only [N] references.
Do not repeat information already covered in previous sections.
CRITICAL RULES:
- Every sentence MUST be complete. Never end mid-sentence.
- Do NOT create tables or matrices with "TBD", "N/A", or empty cells. If you lack data for a comparison, write prose explaining what is known and what is missing instead.
- Do NOT promise data you do not have. If country-specific or granular data is absent from the findings, say so explicitly rather than creating placeholder structures."""
    if previous_sections_summary:
        system += "\n\nAlready covered in previous sections (do not repeat):\n- " + "\n- ".join(previous_sections_summary[:15])
    if claim_block:
        system += """
For every factual claim or finding you state, you MUST cite the claim from the CLAIM LEDGER by including exactly one [claim_ref: claim_id@version] in that sentence. Example: "The effect was significant [claim_ref: cl_1@1]." Use only claim_refs from the CLAIM LEDGER list below. Do not introduce new claims; only cite existing ledger claims."""
    user = f"""RESEARCH QUESTION: {question}

SECTION TITLE: {section_title}

REFERENCE MAPPING (use these numbers in citations):
{ref_block}

FINDINGS FOR THIS SECTION:
{content_block}

FULL SOURCE CONTENT (use for depth):
{full_block[:20000]}
"""
    if claim_block:
        user += f"""
CLAIM LEDGER (you MUST use these exact refs for every claim-bearing sentence; include [claim_ref: id@version] in the same sentence as the claim):
{claim_block}

Write the section markdown (no title repeated; start with body). Every sentence that states a factual claim must contain [claim_ref: id@version] from the list above."""
    else:
        user += "\nWrite the section markdown (no title repeated; start with body)."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if text and len(text) > 100:
            last_line = text.rstrip().splitlines()[-1].strip()
            if last_line and len(last_line) > 20 and last_line[-1] not in '.!?:)]*>"–':
                text += "\n\n*[Note: This section may have been truncated during generation.]*"
        return text
    except Exception as e:
        return f"*Section synthesis failed: {e}*"


def _synthesize_research_situation_map(question: str, claim_ledger: list[dict], findings: list[dict], project_id: str) -> str:
    """Research Situation Map: what is known, partially known, and missing."""
    system = """You are a research intelligence analyst. Given a research question, claims with their verification status, and findings, produce a Research Situation Map.

Format (markdown, no heading):
- **Strong evidence:** areas where claims are verified/authoritative
- **Partial evidence:** areas with findings but unverified claims
- **Missing evidence:** areas the question asks about but no findings exist
- **Key uncertainty driver:** the single biggest reason for remaining uncertainty

Be specific to the actual topic. 4-8 lines total. No filler."""
    claims_text = json.dumps([{"text": c.get("text", "")[:120], "tier": c.get("verification_tier", "UNVERIFIED")} for c in claim_ledger[:20]], ensure_ascii=False)
    findings_text = json.dumps([{"excerpt": (f.get("excerpt") or "")[:200]} for f in findings[:15]], ensure_ascii=False)[:4000]
    user = f"QUESTION: {question}\nCLAIMS:\n{claims_text}\nFINDINGS:\n{findings_text}\n\nWrite the Research Situation Map (no heading, just content)."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception:
        return ""


def _synthesize_decision_matrix(
    question: str,
    claim_ledger: list[dict],
    thesis: dict,
    tipping_text: str,
    project_id: str,
) -> str:
    """One-page decision matrix: who wins, when, why; dimension-by-dimension; overall recommendation with confidence."""
    system = """You are a research strategist. Given the research question, verified claims, thesis, and tipping conditions, produce an Executive Decision Synthesis (about 1 page). Format as markdown with no top-level heading. Include:
1) Dimension-by-dimension winner or comparison (what the evidence says per dimension)
2) Conditions under which each conclusion flips (when would the answer change?)
3) Overall recommendation with confidence (HIGH/MEDIUM/LOW)

Be specific and concise. No filler."""
    claims_text = json.dumps(
        [{"text": (c.get("text") or "")[:150], "tier": c.get("verification_tier", "UNVERIFIED")} for c in claim_ledger[:30]],
        ensure_ascii=False,
    )[:6000]
    thesis_text = json.dumps(thesis, ensure_ascii=False)[:1500] if thesis else "{}"
    user = f"QUESTION: {question}\n\nCLAIMS:\n{claims_text}\n\nTHESIS:\n{thesis_text}\n\nTIPPING CONDITIONS:\n{(tipping_text or '')[:2000]}\n\nWrite the Executive Decision Synthesis (no heading)."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception:
        return ""


def _synthesize_tipping_conditions(question: str, claim_ledger: list[dict], project_id: str) -> str:
    """What new evidence would change the conclusions?"""
    system = """You are a research intelligence analyst. Given unverified/contested claims, identify 3-5 specific findings that would change the conclusion.

Return a markdown table (no heading):
| Finding needed | Effect on conclusion |
| --- | --- |

Each row: specific evidence that could be found, and what it would resolve. Be concrete, not generic."""
    claims_text = json.dumps([{"text": c.get("text", "")[:150], "tier": c.get("verification_tier", "UNVERIFIED"), "reason": c.get("verification_reason", "")} for c in claim_ledger[:20]], ensure_ascii=False)
    user = f"QUESTION: {question}\nCLAIMS:\n{claims_text}\n\nWrite the tipping conditions table (no heading)."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception:
        return ""


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

# Explicit claim_ref format: [claim_ref: id@ver] or [claim_ref: id1@v1; id2@v2] (semicolon-separated). Machine-parseable.
CLAIM_REF_PATTERN = re.compile(r"\[claim_ref:\s*([^\]]+)\]", re.IGNORECASE)


def _normalize_ref(ref: str) -> str | None:
    """Normalize to claim_id@version; return None if invalid."""
    ref = (ref or "").strip()
    if not ref or "@" not in ref:
        return None
    parts = ref.split("@", 1)
    cid, ver = parts[0].strip(), parts[1].strip()
    if not cid:
        return None
    try:
        int(ver)
    except ValueError:
        return None
    return f"{cid}@{ver}"


def extract_claim_refs_from_report(report: str) -> list[str]:
    """Extract all claim_ref values from report. Returns list of normalized refs (id@version)."""
    refs: list[str] = []
    for m in CLAIM_REF_PATTERN.finditer(report):
        inner = m.group(1).strip()
        for part in re.split(r"[;,]", inner):
            r = _normalize_ref(part)
            if r:
                refs.append(r)
    return refs


def _build_valid_claim_ref_set(claim_ledger: list[dict]) -> set[str]:
    """Set of valid claim_ref strings (claim_id@version) from ledger."""
    out: set[str] = set()
    for c in claim_ledger:
        cid = (c.get("claim_id") or "").strip()
        if not cid:
            continue
        ver = c.get("claim_version", 1)
        try:
            ver = int(ver)
        except (TypeError, ValueError):
            ver = 1
        out.add(f"{cid}@{ver}")
    return out


def _sentence_contains_valid_claim_ref(sentence: str, valid_refs: set[str]) -> bool:
    """True if sentence contains at least one [claim_ref: X@Y] with X@Y in valid_refs."""
    for m in CLAIM_REF_PATTERN.finditer(sentence):
        inner = m.group(1).strip()
        for part in re.split(r"[;,]", inner):
            r = _normalize_ref(part)
            if r and r in valid_refs:
                return True
    return False


# Hard synthesis contract (Spec §6.2–6.3): no new claims; every claim-bearing sentence maps to ledger via explicit claim_ref.
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
    import re as _re
    if _re.search(r'\d+\s*%|\d+\.\d+', s):
        return True
    return False


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
    Hard claim_ref-enforced contract (Spec §6.2–6.3):
    - Every claim_ref in report must resolve to an existing ledger entry.
    - Every claim-bearing sentence must carry at least one valid [claim_ref: id@version].
    - No new claims (claim-like sentence without valid ref => violation).
    When claim_ledger is empty (non-AEM), ref checks are skipped for backward compatibility.
    Returns dict: unknown_refs, unreferenced_claim_sentences, unreferenced_claim_sentence_count,
      new_claims_in_synthesis (same count), tentative_labels_ok, valid.
    """
    valid_refs = _build_valid_claim_ref_set(claim_ledger)
    refs_in_report = extract_claim_refs_from_report(report)
    unknown_refs = [r for r in refs_in_report if r not in valid_refs]
    # Unique unknown for count
    unknown_refs_unique = list(dict.fromkeys(unknown_refs))

    unreferenced_sentences: list[str] = []
    if valid_refs:
        # Only require explicit refs when we have a non-empty ledger (AEM path)
        sentences = re.split(r"(?<=[.!?])\s+", report)
        for sent in sentences:
            sent = sent.strip()
            if not sent or len(sent) < 20:
                continue
            if not _is_claim_like_sentence(sent):
                continue
            if not _sentence_contains_valid_claim_ref(sent, valid_refs):
                unreferenced_sentences.append(sent[:200])
    unreferenced_count = len(unreferenced_sentences)

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

    ref_valid = len(unknown_refs_unique) == 0 and (unreferenced_count == 0 or not valid_refs)
    valid = ref_valid and tentative_ok
    return {
        "unknown_refs": unknown_refs_unique,
        "unreferenced_claim_sentences": unreferenced_sentences,
        "unreferenced_claim_sentence_count": unreferenced_count,
        "new_claims_in_synthesis": unreferenced_count,
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
    findings = _load_findings(proj_path, question=question)
    sources = _load_sources(proj_path)
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
    accumulated_summary: list[str] = []
    for b in checkpoint_bodies:
        accumulated_summary.extend(_extract_section_key_points(b))
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
        body = _synthesize_section(title, section_findings, ref_map, proj_path, question, project_id, rel_sources, claim_ledger, previous_sections_summary=accumulated_summary)
        accumulated_summary.extend(_extract_section_key_points(body))
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
                                        body = _synthesize_section(title, section_findings, ref_map, proj_path, question, project_id, rel_sources, claim_ledger, previous_sections_summary=accumulated_summary)
                                except Exception:
                                    pass
                except Exception:
                    pass
        checkpoint_bodies.append(body)
        deep_parts.append(f"## {title}\n\n{body}")
        _save_checkpoint(proj_path, clusters, section_titles, checkpoint_bodies)
    parts.append("\n\n".join(deep_parts))
    parts.append("\n\n---\n\n")

    # Methodology (auto): use actual on-disk counts, not capped findings list
    source_count = len(sources)
    read_count = len(list((proj_path / "sources").glob("*_content.json")))
    findings_count_actual = len(list((proj_path / "findings").glob("*.json")))
    parts.append("## Methodology\n\n")
    parts.append(f"This report is based on **{findings_count_actual} findings** from **{source_count} sources** ")
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
    for i, c in enumerate(claim_ledger[:50], 1):
        text = (c.get("text") or "")[:80].replace("|", " ")
        fstatus = (c.get("falsification_status") or "").strip()
        tier = c.get("verification_tier", "")
        if fstatus == "PASS_TENTATIVE":
            status = "TENTATIVE"
        elif tier == "VERIFIED":
            status = "VERIFIED"
        elif tier == "AUTHORITATIVE":
            status = "AUTHORITATIVE"
        elif c.get("is_verified"):
            status = "VERIFIED"
        else:
            status = "UNVERIFIED"
        n_src = len(c.get("supporting_source_ids") or [])
        parts.append(f"| {i} | {text}... | {status} | {n_src} |\n")
    parts.append("\n")

    # Research Situation Map
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id, "Generating Research Situation Map")
    except Exception:
        pass
    situation_map = _synthesize_research_situation_map(question, claim_ledger, findings, project_id)
    if situation_map:
        parts.append("## Research Situation Map\n\n")
        parts.append(situation_map)
        parts.append("\n\n")

    # Tipping Conditions
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id, "Generating Tipping Conditions")
    except Exception:
        pass
    tipping = _synthesize_tipping_conditions(question, claim_ledger, project_id)
    if tipping:
        parts.append("## Tipping Conditions\n\n")
        parts.append(tipping)
        parts.append("\n\n")

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

    # Executive Decision Synthesis at top (after header, before KEY NUMBERS)
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id, "Generating Executive Decision Synthesis")
    except Exception:
        pass
    decision_matrix = _synthesize_decision_matrix(question, claim_ledger, thesis, tipping, project_id)
    if decision_matrix:
        first_section = report_body.find("\n## ")
        if first_section >= 0:
            report_body = (
                report_body[:first_section] +
                "\n\n## Executive Decision Synthesis\n\n" + decision_matrix + "\n\n---\n\n" +
                report_body[first_section:]
            )

    # Claim Evidence Registry (claim → source → URL → date → tier)
    registry_md = _build_claim_source_registry(claim_ledger, sources, ref_list)
    report_body += "\n\n## Claim Evidence Registry\n\n"
    report_body += registry_md
    report_body += "\n\n## Appendix B: Methodology Details\n\n"
    report_body += f"- Synthesis model: {_model()}\n- Findings cap: {MAX_FINDINGS}\n- Report timestamp: {ts}\n\n"
    report_body += "## References\n\n"
    for i, (url, title) in enumerate(ref_list, 1):
        if title:
            report_body += f"[{i}] {title}  \n    {url}\n\n"
        else:
            report_body += f"[{i}] {url}\n\n"

    # Hard synthesis contract (Spec §6.2–6.3): explicit claim_ref; validate; enforce/strict block on violation
    mode = (os.environ.get("AEM_ENFORCEMENT_MODE") or "observe").strip().lower()
    if mode not in ("observe", "enforce", "strict"):
        mode = "observe"
    validation = validate_synthesis_contract(report_body, claim_ledger, mode)
    contract_status = {
        "valid": validation["valid"],
        "mode": mode,
        "unknown_refs": validation.get("unknown_refs", []),
        "unreferenced_claim_sentence_count": validation.get("unreferenced_claim_sentence_count", 0),
        "tentative_labels_ok": validation.get("tentative_labels_ok", True),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        (proj_path / "synthesis_contract_status.json").write_text(
            json.dumps(contract_status, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
    if not validation["valid"] and mode in ("enforce", "strict"):
        raise SynthesisContractError(
            f"Synthesis contract violation: unknown_refs={validation.get('unknown_refs', [])}, "
            f"unreferenced_claim_sentence_count={validation.get('unreferenced_claim_sentence_count', 0)}, "
            f"tentative_labels_ok={validation.get('tentative_labels_ok')}"
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
