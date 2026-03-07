"""Block synthesis: RSM, decision matrix, tipping, scenario, exec summary, conclusions; text utils."""
import json
import re
from tools.research_common import llm_call
from tools.synthesis.constants import _model
from tools.synthesis.ledger import normalize_to_strings


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

Be specific and concise. No filler.
Use measured, professional language appropriate for an institutional research report. Avoid dramatic qualifiers like "fundamental", "irreversible", "massive", "unprecedented". State impact precisely with data, not rhetoric."""
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


def _synthesize_scenario_matrix(
    question: str,
    claim_ledger: list[dict],
    thesis: dict,
    tipping_text: str,
    project_id: str,
) -> str:
    """Scenario matrix: Base / Aggressive / Regulatory with probabilities and implications."""
    system = """You are a research strategist. Given verified claims, thesis, and tipping conditions, produce a Scenario Matrix with exactly 3 rows:

| Scenario | Probability | Key Driver | Implication |
| --- | --- | --- | --- |
| Base Case | X% | ... | ... |
| Aggressive / Bull | Y% | ... | ... |
| Regulatory Block / Bear | Z% | ... | ... |

Probabilities must sum to ~100%. Be specific to the actual market dynamics. No generic scenarios. Return only the markdown table (no heading)."""
    claims_text = json.dumps(
        [{"text": (c.get("text") or "")[:150], "tier": c.get("verification_tier", "UNVERIFIED")} for c in claim_ledger[:25]],
        ensure_ascii=False,
    )[:5000]
    thesis_text = json.dumps(thesis, ensure_ascii=False)[:1500] if thesis else "{}"
    user = f"QUESTION: {question}\n\nCLAIMS:\n{claims_text}\n\nTHESIS:\n{thesis_text}\n\nTIPPING CONDITIONS:\n{(tipping_text or '')[:2000]}\n\nWrite the Scenario Matrix table only."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception:
        return ""


def _synthesize_exec_summary(full_report_body: str, question: str, project_id: str, epistemic_profile: str = "") -> str:
    """Generate a one-page Executive Brief (max 400 words) for C-level readers."""
    system = """You are a research analyst. Write a one-page Executive Brief (max 400 words) that a C-level executive can read in 2 minutes. Structure:
(1) Bottom Line (2 sentences)
(2) Key Evidence (3–4 bullet points with numbers)
(3) Risk Assessment (1 sentence)
(4) Recommended Action (1 sentence)

Do not use citations [N] in the brief.
Use measured, professional language appropriate for an institutional report. Avoid dramatic qualifiers like "fundamental", "irreversible", "massive", "unprecedented". State impact precisely with data, not rhetoric."""
    user = f"RESEARCH QUESTION: {question}\n\nFULL REPORT (excerpt):\n{full_report_body[:12000]}\n\nWrite only the Executive Brief (no heading, max 400 words)."
    if epistemic_profile:
        user += f"\n\nEPISTEMIC PROFILE: {epistemic_profile}. If TENTATIVE+UNVERIFIED > 60% of claims, frame as emerging patterns, not confirmed facts."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        return (result.text or "").strip()
    except Exception:
        return ""


def _normalize_sentence(s: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return " ".join((s or "").lower().split()).strip()


def _sentence_overlap(a: str, b: str) -> float:
    """Word-set overlap: len(a & b) / min(len(a), len(b)). Returns 0–1."""
    wa = set(re.findall(r"\b[a-z0-9]{2,}\b", a.lower()))
    wb = set(re.findall(r"\b[a-z0-9]{2,}\b", b.lower()))
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    return inter / min(len(wa), len(wb))


def _deduplicate_sections(parts: list[str]) -> list[str]:
    """Remove sentences that are >80% identical to a sentence in an earlier section. Lightweight, no LLM."""
    if not parts:
        return parts
    SENTENCE_RE = re.compile(r"[^.!?]+[.!?]|\S[^.!?]*$")
    out: list[str] = []
    all_previous: list[str] = []
    for body in parts:
        sentences = [s.strip() for s in SENTENCE_RE.findall(body) if len(s.strip()) > 20]
        kept: list[str] = []
        for sent in sentences:
            norm = _normalize_sentence(sent)
            if not norm or len(norm) < 15:
                kept.append(sent)
                continue
            is_dup = any(_sentence_overlap(norm, _normalize_sentence(p)) >= 0.8 for p in all_previous)
            if not is_dup:
                kept.append(sent)
                all_previous.append(sent)
        out.append(" ".join(kept) if kept else body)
    return out


def _synthesize_conclusions_next_steps(
    thesis: dict, contradictions: list, question: str, project_id: str,
    epistemic_profile: str = "", research_mode: str = "standard", discovery_brief: dict | None = None,
) -> tuple[str, str]:
    """Conclusions (300–500 words) and Recommended Next Steps (200–400 words). Discovery mode: hypothesis generation."""
    discovery_brief = discovery_brief or {}
    if research_mode == "discovery":
        system = """You are a research strategist. Given findings, patterns, and discovery signals, produce:
1. "conclusions": 3-5 key hypotheses derived from the research. Each hypothesis must be labeled [ESTABLISHED], [EMERGING], or [SPECULATIVE]. Frame as testable propositions. Include at least one hypothesis based on non-obvious connections from the Discovery Map.
2. "next_steps": Prioritized list of experiments, prototypes, or deeper investigations to validate the most promising hypotheses. Use [HIGH]/[MEDIUM] priority.
Return JSON only: {"conclusions": "markdown", "next_steps": "markdown"}"""
        user = f"QUESTION: {question}\nTHESIS: {thesis.get('current', '')}\nCONTRADICTIONS: {json.dumps(contradictions)[:1500]}\nDISCOVERY KEY HYPOTHESIS: {discovery_brief.get('key_hypothesis', '')}\n\nReturn only valid JSON."
    else:
        system = """You are a research analyst. Given thesis and contradictions, produce two sections.
Return JSON: {"conclusions": "markdown text 300-500 words", "next_steps": "markdown text 200-400 words, prioritized list with [HIGH]/[MEDIUM]."}
If alternative hypotheses are provided, include a short 'Alternative hypotheses' or 'Position A vs B' subsection in conclusions where relevant."""
        user = f"QUESTION: {question}\nTHESIS: {thesis.get('current', '')} (confidence: {thesis.get('confidence', 0)})\nCONTRADICTIONS: {json.dumps(contradictions)[:2000]}\n\nReturn only valid JSON."
        alts = thesis.get("alternatives") or []
        if alts:
            user += f"\nALTERNATIVE HYPOTHESES (consider mentioning): {json.dumps(alts, ensure_ascii=False)[:1500]}"
        if thesis.get("contradiction_summary"):
            user += f"\nCONTRADICTION SUMMARY: {thesis.get('contradiction_summary', '')[:500]}"
        if epistemic_profile:
            user += f"\nEPISTEMIC PROFILE: {epistemic_profile}. If TENTATIVE+UNVERIFIED > 60% of claims, frame conclusions as emerging patterns, not confirmed facts."
    try:
        result = llm_call(_model(), system, user, project_id=project_id)
        text = (result.text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
        out = json.loads(text)
        concl = out.get("conclusions", "")
        next_steps = out.get("next_steps", "")
        if isinstance(concl, list):
            concl = "\n".join(str(x) for x in concl)
        if isinstance(next_steps, list):
            next_steps = "\n".join(str(x) for x in next_steps)
        return str(concl), str(next_steps)
    except Exception:
        return thesis.get("current", ""), "1. [HIGH] Run additional verification.\n2. [MEDIUM] Expand source set."


def _evidence_summary_line(claim_ledger: list[dict], research_mode: str = "standard") -> str:
    """One-line evidence summary. Discovery mode: established/emerging/speculative counts."""
    if not claim_ledger:
        return "**Evidence summary:** 0 claims (no claim ledger)."
    if research_mode == "discovery":
        established = sum(1 for c in claim_ledger if (c.get("verification_tier") or "").strip().upper() == "ESTABLISHED")
        emerging = sum(1 for c in claim_ledger if (c.get("verification_tier") or "").strip().upper() == "EMERGING")
        speculative = len(claim_ledger) - established - emerging
        return f"**Discovery profile:** {established} established, {emerging} emerging, {speculative} speculative insights."
    verified_only = 0
    authoritative = 0
    for c in claim_ledger:
        tier = (c.get("verification_tier") or "").strip().upper()
        if tier == "AUTHORITATIVE":
            authoritative += 1
        elif c.get("is_verified") or tier == "VERIFIED":
            verified_only += 1
    total_verified = verified_only + authoritative
    unver = len(claim_ledger) - total_verified
    total = len(claim_ledger)
    return f"**Evidence summary:** {total_verified} von {total} Kernclaims verifiziert ({authoritative} authoritative), {unver} unverifiziert/contested."


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
            return "\n".join(str(x) for x in nums[:10])
    except Exception:
        pass
    return "**—** | Key numbers to be filled from findings."
