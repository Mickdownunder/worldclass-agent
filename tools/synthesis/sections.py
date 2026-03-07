"""Section synthesis: one section per cluster, epistemic reflect, gap detection."""
import json
import os
import re
from pathlib import Path

from tools.research_common import llm_call, get_optimized_system_prompt
from tools.synthesis.constants import EXCERPT_CHARS, SOURCE_CONTENT_CHARS, _model
from tools.synthesis.data import _load_source_content
from tools.synthesis.ledger import _claim_ledger_block, normalize_to_strings


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


def _extract_used_claim_refs(text: str) -> set[str]:
    """Extract all claim_ref IDs (e.g. 'cl_1@1') from section body text."""
    return set(re.findall(r'\[claim_ref:\s*([^\]]+)\]', text or ""))


def _epistemic_profile_from_ledger(claim_ledger: list[dict]) -> str:
    """Tier distribution string for epistemic context in prompts. No LLM."""
    tier_counts: dict[str, int] = {"AUTHORITATIVE": 0, "VERIFIED": 0, "TENTATIVE": 0, "UNVERIFIED": 0}
    for c in claim_ledger:
        tier = (c.get("verification_tier") or "UNVERIFIED").strip().upper()
        if c.get("is_verified") and tier not in ("VERIFIED", "AUTHORITATIVE"):
            tier = "VERIFIED"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    return (
        f"AUTHORITATIVE: {tier_counts['AUTHORITATIVE']}, "
        f"VERIFIED: {tier_counts['VERIFIED']}, "
        f"TENTATIVE: {tier_counts['TENTATIVE']}, "
        f"UNVERIFIED: {tier_counts['UNVERIFIED']}"
    )


def _epistemic_reflect(body: str, claim_ledger: list[dict], project_id: str) -> str:
    """Quick LLM check: does the section language match claim verification status? Fallback: return original."""
    used_refs = re.findall(r'\[claim_ref:\s*([^\]]+)\]', body or "")
    if not used_refs:
        return body
    ref_set = set(used_refs)
    relevant: list[str] = []
    for c in claim_ledger:
        cid = (c.get("claim_id") or "").strip()
        if not cid:
            continue
        ver = c.get("claim_version", 1)
        ref_key = f"{cid}@{ver}"
        if ref_key in ref_set or ref_key.split("@")[0] == cid:
            tier = (c.get("verification_tier") or "UNVERIFIED").strip().upper()
            relevant.append(f"{ref_key}: {tier}")
    if not relevant:
        return body
    system = """You are an epistemic consistency reviewer. Check if the text uses language appropriate to each claim's verification status. Fix ONLY language violations (e.g. "confirms" for a TENTATIVE claim -> "suggests"). Do NOT change content, structure, citations, or claim_refs. Return the corrected text only, no explanations."""
    user = f"CLAIM STATUS:\n" + "\n".join(relevant) + f"\n\nTEXT:\n{body}"
    try:
        result = llm_call("gemini-2.5-flash", system, user, project_id=project_id)
        corrected = (result.text or "").strip()
        if corrected and len(corrected) > len(body) * 0.5:
            return corrected
    except Exception:
        pass
    return body


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
    claim_ledger: list[dict] | None = None,
    previous_sections_summary: list[str] | None = None,
    used_claim_refs: set[str] | None = None,
    epistemic_profile: str = "",
    research_mode: str = "standard",
    discovery_brief: dict | None = None,
) -> str:
    """One LLM call for one deep-analysis section (500–1500 words). When claim_ledger is provided, section must use [claim_ref: id@version] for every claim-bearing sentence."""
    claim_ledger = claim_ledger or []
    previous_sections_summary = previous_sections_summary or []
    used_claim_refs = used_claim_refs or set()
    discovery_brief = discovery_brief or {}
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
    urls_in_section = list({(f.get("url") or "").strip() for f in findings_for_section if f.get("url")})[:5]
    full_content = []
    for u in urls_in_section:
        text = _load_source_content(proj_path, u)
        if text:
            full_content.append(f"Source {u}:\n{text[:SOURCE_CONTENT_CHARS]}")
    full_block = "\n\n".join(full_content) if full_content else "(no full content)"

    claim_block = _claim_ledger_block(claim_ledger)

    if research_mode == "discovery":
        base_system = """You are a research innovation analyst. Write a single analytical section that identifies novel patterns, emerging concepts, and unexplored connections.

Structure your analysis around:
1. What is genuinely new or different about this approach/idea?
2. What existing problems does it solve (or create)?
3. What are the implications if this pattern accelerates?

Use inline citations [1], [2] etc. Write 500-1500 words.
Label each insight with its maturity: [ESTABLISHED], [EMERGING], or [SPECULATIVE].
For SPECULATIVE insights, explicitly state your reasoning chain.
Focus on connections between ideas that sources don't make explicitly.
Do NOT repeat ideas from previous sections.
End with '**Key insights:**' -- 2-3 bullet points on what is genuinely novel here."""
    else:
        base_system = """You are a research analyst. Write a single analytical section of a professional report.
Use inline citations as [1], [2] etc. to match the reference list provided. Write 500–1500 words.
State confidence where relevant (e.g. "HIGH confidence (3 sources)" or "LOW (single source)").
Do not repeat URLs in the body; use only [N] references.
Do not repeat information already covered in previous sections.
Use measured, professional language appropriate for an institutional research report.
Avoid dramatic qualifiers like "fundamental", "irreversible", "massive", "unprecedented", "unwiderruflich", "unausweichlich". State impact precisely with data, not rhetoric.
CRITICAL RULES:
- Every sentence MUST be complete. Never end mid-sentence.
- Do NOT create tables or matrices with "TBD", "N/A", or empty cells. If you lack data for a comparison, write prose explaining what is known and what is missing instead.
- Do NOT promise data you do not have. If country-specific or granular data is absent from the findings, say so explicitly rather than creating placeholder structures.
At the end of the section, add a short block '**Key findings:**' with 2–3 bullet points that summarize the main evidence-based conclusions of this section."""

    try:
        project_data = json.loads((proj_path / "project.json").read_text())
        domain = project_data.get("domain", "general")
    except Exception:
        domain = "general"
    system = get_optimized_system_prompt(domain, base_system)

    if epistemic_profile:
        system += f"""

EPISTEMIC PROFILE OF THIS RESEARCH: {epistemic_profile}
If TENTATIVE + UNVERIFIED > 60% of claims, your conclusions MUST be framed as "emerging patterns" or "structural tendencies", never as confirmed facts."""
    if previous_sections_summary:
        system += "\n\nAlready covered in previous sections (do not repeat):\n- " + "\n- ".join(previous_sections_summary[:15])
        system += "\n\nCRITICAL: Do NOT restate these specific data points even to introduce context. Refer to them with 'as noted above' if absolutely necessary, max once per section."
    if claim_block:
        system += """
For every factual claim or finding you state, you MUST cite the claim from the CLAIM LEDGER by including exactly one [claim_ref: claim_id@version] in that sentence. Example: "The effect was significant [claim_ref: cl_1@1]." Use only claim_refs from the CLAIM LEDGER list below. Do not introduce new claims; only cite existing ledger claims.

EPISTEMIC LANGUAGE RULES (MANDATORY):
Each claim in the CLAIM LEDGER has a verification status: [VERIFIED], [AUTHORITATIVE], [TENTATIVE], or [UNVERIFIED].
You MUST match your language to the claim's status:
- [VERIFIED]: Use definitive language ("confirms", "demonstrates", "establishes").
- [AUTHORITATIVE]: Use strong but qualified language ("strongly indicates", "authoritatively reported").
- [TENTATIVE]: Use hedging language ("suggests", "indicates", "appears to", "preliminary evidence points to"). NEVER use "confirms" or "proves" for TENTATIVE claims.
- [UNVERIFIED]: Use cautious language ("reportedly", "unverified reports suggest", "claimed but not independently confirmed").
If the majority of claims are TENTATIVE or UNVERIFIED, your conclusions MUST reflect this uncertainty. Use "structural tendency" or "emerging pattern" instead of definitive statements. Do NOT write "bestätigt" or "zwingend" for tentative findings."""
    user = f"""RESEARCH QUESTION: {question}

SECTION TITLE: {section_title}

REFERENCE MAPPING (use these numbers in citations):
{ref_block}

FINDINGS FOR THIS SECTION:
{content_block}

FULL SOURCE CONTENT (use for depth):
{full_block[:20000]}
"""
    if discovery_brief:
        user += f"""

DISCOVERY SIGNALS (use these to identify non-obvious connections):
- Novel connections: {json.dumps(discovery_brief.get('novel_connections', [])[:5], ensure_ascii=False)}
- Emerging concepts: {json.dumps(discovery_brief.get('emerging_concepts', [])[:5], ensure_ascii=False)}
- Research frontier: {json.dumps(discovery_brief.get('research_frontier', [])[:3], ensure_ascii=False)}
- Key hypothesis: {discovery_brief.get('key_hypothesis', '')}

Weave these signals into your analysis. Highlight where YOUR section's findings support or challenge the key hypothesis."""
    if claim_block:
        already_cited_note = ""
        if used_claim_refs:
            already_cited_note = f"\n\nALREADY CITED IN PREVIOUS SECTIONS (avoid re-citing unless adding genuinely new analysis): {', '.join(sorted(used_claim_refs)[:30])}\nPrefer claims NOT yet cited. If you must reference an already-cited claim, add new analytical insight rather than restating what was said."
        user += f"""
CLAIM LEDGER (you MUST use these exact refs for every claim-bearing sentence; include [claim_ref: id@version] in the same sentence as the claim):
{claim_block}{already_cited_note}

Write the section markdown (no title repeated; start with body). Every sentence that states a factual claim must contain [claim_ref: id@version] from the list above."""
    else:
        user += "\nWrite the section markdown (no title repeated; start with body)."
    if os.environ.get("RESEARCH_SYNTHESIS_STRUCTURED_SECTIONS") == "1":
        user += "\n\nReturn JSON only: {\"body_md\": \"<full section markdown>\", \"claim_refs_used\": [\"cl_1@1\", ...], \"key_points\": [\"...\", ...]}."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if os.environ.get("RESEARCH_SYNTHESIS_STRUCTURED_SECTIONS") == "1" and text:
            try:
                if "```" in text:
                    text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
                parsed = json.loads(text)
                if isinstance(parsed.get("body_md"), str) and len(parsed["body_md"]) > 50:
                    text = parsed["body_md"]
            except (json.JSONDecodeError, TypeError):
                pass
        if text and len(text) > 100:
            last_line = text.rstrip().splitlines()[-1].strip()
            if last_line and len(last_line) > 20 and last_line[-1] not in '.!?:)]*>"–':
                text += "\n\n*[Note: This section may have been truncated during generation.]*"
        return text
    except Exception as e:
        return f"*Section synthesis failed: {e}*"
