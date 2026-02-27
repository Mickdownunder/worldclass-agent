#!/usr/bin/env python3
"""
Experience Distiller (EvolveR-based): summarize completed research trajectories into
guiding and cautionary principles. Includes Dedup (among new) and Match-or-Create (vs DB).
Usage: research_experience_distiller.py <project_id>
"""
import json
import os
import sys
from pathlib import Path
from collections import deque

# Allow importing operator lib and tools
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SIMILARITY_THRESHOLD_KEYWORDS = 2  # min shared significant words to consider for LLM same-check
MAX_PAIRS_FOR_DEDUP = 20  # cap LLM calls for pairwise dedup
TOP_CANDIDATES_FOR_MATCH = 5


def _llm_same_principle(principle_a: str, principle_b: str, project_id: str, model: str) -> bool:
    """LLM: Are these two principles saying the same thing? Yes/No."""
    from tools.research_common import llm_call
    system = "You are a research analyst. Answer only Yes or No. Do not explain."
    user = f"Principle A: {principle_a[:400]}\n\nPrinciple B: {principle_b[:400]}\n\nAre A and B saying the same thing? Answer only Yes or No."
    try:
        result = llm_call(model, system, user, project_id=project_id)
        text = (result.text or "").strip().upper()
        return text.startswith("YES")
    except Exception:
        return False


def _llm_equivalent_to_existing(new_principle: str, existing_principle: str, project_id: str, model: str) -> bool:
    """LLM: Is this new principle equivalent to this existing one? Yes/No."""
    from tools.research_common import llm_call
    system = "You are a research analyst. Answer only Yes or No. Do not explain."
    user = f"New principle: {new_principle[:400]}\n\nExisting principle: {existing_principle[:400]}\n\nIs the new principle equivalent to the existing one (same meaning)? Answer only Yes or No."
    try:
        result = llm_call(model, system, user, project_id=project_id)
        text = (result.text or "").strip().upper()
        return text.startswith("YES")
    except Exception:
        return False


def _dedup_principles(principles_data: list[dict], project_id: str, model: str) -> list[dict]:
    """
    Among new principles: pairwise LLM same-check, BFS connected components, keep one rep per cluster.
    Returns list of representative principles (deduplicated).
    """
    if len(principles_data) <= 1:
        return principles_data
    # Build similarity graph: for each pair with some keyword overlap, ask LLM
    n = len(principles_data)
    text_by_i = {i: (p.get("principle") or p.get("description") or "")[:500] for i, p in enumerate(principles_data)}
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    pairs_done = 0
    for i in range(n):
        for j in range(i + 1, n):
            if pairs_done >= MAX_PAIRS_FOR_DEDUP:
                break
            a, b = text_by_i[i], text_by_i[j]
            if not a or not b:
                continue
            words_a = set(w for w in a.lower().split() if len(w) > 3)
            words_b = set(w for w in b.lower().split() if len(w) > 3)
            if len(words_a & words_b) < SIMILARITY_THRESHOLD_KEYWORDS:
                continue
            if _llm_same_principle(a, b, project_id, model):
                adj[i].append(j)
                adj[j].append(i)
            pairs_done += 1
        if pairs_done >= MAX_PAIRS_FOR_DEDUP:
            break
    # BFS connected components; keep index with longest description as representative
    visited = set()
    representatives = []
    for start in range(n):
        if start in visited:
            continue
        comp = []
        q = deque([start])
        while q:
            u = q.popleft()
            if u in visited:
                continue
            visited.add(u)
            comp.append(u)
            for v in adj[u]:
                if v not in visited:
                    q.append(v)
        rep_idx = max(comp, key=lambda i: len(text_by_i[i]))
        representatives.append(principles_data[rep_idx])
    return representatives


def _distill_causal_principles(
    project_id: str,
    question: str,
    domain: str,
    strategy_used: str,
    findings_count: int,
    claim_breakdown: dict,
    critic_score: float,
    critic_weaknesses: list,
    what_helped: list,
    what_hurt: list,
    model: str,
) -> None:
    """Single cheap LLM call: extract 2-3 causal strategic principles. Store with type=causal. Runs for every run."""
    from tools.research_common import llm_call
    payload = {
        "question": question[:300],
        "strategy_used": strategy_used[:200],
        "findings_count": findings_count,
        "claim_breakdown": claim_breakdown,
        "critic_score": critic_score,
        "critic_weaknesses": critic_weaknesses[:5],
        "what_helped": what_helped,
        "what_hurt": what_hurt,
    }
    system = (
        "You are a research analyst. From this single run experience, extract 2-3 CAUSAL strategic principles: "
        "what caused success or failure (e.g. 'Manufacturing questions need SEC sources, not clinical DBs'). "
        "Return only valid JSON: {\"principles\": [{\"principle\": \"...\", \"evidence\": \"...\", \"type\": \"causal\"}]}. "
        "evidence = one short sentence from this run (e.g. 'proj-X: 0 verified claims from 38 clinical sources')."
    )
    user = f"Run summary:\n{json.dumps(payload, indent=2)}\n\nExtract 2-3 causal principles. Return only JSON."
    try:
        result = llm_call(model, system, user, project_id=project_id)
        text = (result.text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        principles_data = parsed.get("principles") or []
        if not isinstance(principles_data, list):
            return
        from lib.memory import Memory
        mem = Memory()
        for p in principles_data[:3]:
            desc = (p.get("principle") or p.get("description") or "").strip()
            if not desc or len(desc) < 10:
                continue
            evidence = (p.get("evidence") or "").strip()[:500]
            evidence_json = json.dumps([evidence]) if evidence else "[]"
            mem.insert_principle(
                principle_type="causal",
                description=desc[:2000],
                source_project_id=project_id,
                domain=domain or None,
                evidence_json=evidence_json,
                metric_score=0.5,
            )
        mem.close()
    except Exception as e:
        print(f"Causal distillation failed (non-fatal): {e}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_experience_distiller.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1].strip()
    proj_dir = ROOT / "research" / project_id
    if not proj_dir.is_dir():
        print(f"Project dir not found: {proj_dir}", file=sys.stderr)
        sys.exit(1)

    project_json = proj_dir / "project.json"
    if not project_json.exists():
        sys.exit(0)
    d = json.loads(project_json.read_text())
    status = d.get("status", "")
    domain = d.get("domain", "general")
    question = (d.get("question") or "")[:500]
    phase_timings = d.get("phase_timings", {})
    quality_gate = d.get("quality_gate", {})
    critic_score = quality_gate.get("critic_score")
    if critic_score is None:
        critic_score = quality_gate.get("evidence_gate", {}).get("metrics", {}).get("claim_support_rate", 0.5)
    if not isinstance(critic_score, (int, float)):
        critic_score = 0.5

    findings_count = len(list((proj_dir / "findings").glob("*.json")))
    source_count = len([f for f in (proj_dir / "sources").glob("*.json") if "_content" not in f.name])

    trajectory = {
        "topic": question,
        "domain": domain,
        "phases_completed": list(phase_timings.keys()),
        "phase_timings": phase_timings,
        "findings_count": findings_count,
        "source_count": source_count,
        "final_status": status,
        "critic_score": critic_score,
    }

    # Search queries (successful vs failed) from artifacts
    successful_queries, failed_queries = [], []
    artifacts_dir = proj_dir / "artifacts"
    if artifacts_dir.is_dir():
        for af in artifacts_dir.glob("*.json"):
            try:
                ad = json.loads(af.read_text())
                q = ad.get("query") or ad.get("search_query") or ""
                if q:
                    results_count = len(ad.get("results", []))
                    (successful_queries if results_count > 0 else failed_queries).append(q[:200])
            except Exception:
                pass
    trajectory["successful_queries"] = successful_queries[:10]
    trajectory["failed_queries"] = failed_queries[:10]

    # Source domain verification rates (sources + claim_ledger)
    from urllib.parse import urlparse
    source_domains: dict = {}
    sources_dir = proj_dir / "sources"
    if sources_dir.is_dir():
        for sf in sources_dir.glob("*.json"):
            if "_content" in sf.name:
                continue
            try:
                sd = json.loads(sf.read_text())
                url = sd.get("url") or ""
                if url:
                    dom = urlparse(url).netloc
                    if dom:
                        source_domains.setdefault(dom, {"total": 0, "verified": 0})
                        source_domains[dom]["total"] += 1
            except Exception:
                pass
    ledger_path = proj_dir / "verify" / "claim_ledger.json"
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text())
            claims = ledger if isinstance(ledger, list) else ledger.get("claims", [])
            for claim in claims:
                for src_url in (claim.get("source_urls") or []):
                    dom = urlparse(src_url).netloc
                    if dom in source_domains and (claim.get("status") == "VERIFIED" or claim.get("is_verified")):
                        source_domains[dom]["verified"] += 1
        except Exception:
            pass
    trajectory["top_source_domains"] = sorted(
        [{"domain": d, **v} for d, v in source_domains.items()],
        key=lambda x: x["verified"],
        reverse=True,
    )[:10]

    model = os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gpt-4o-mini")

    # Loop-backs from phase_history
    phase_history = d.get("phase_history") or []
    loop_back_count = 0
    seen_phases = set()
    for ph in phase_history:
        phase_name = ph if isinstance(ph, str) else (ph.get("phase") or "")
        if phase_name in seen_phases:
            loop_back_count += 1
        seen_phases.add(phase_name)
    trajectory["loop_back_count"] = loop_back_count

    # User feedback from feedback.jsonl
    feedback_path = proj_dir / "feedback.jsonl"
    if feedback_path.exists():
        try:
            fb_lines = feedback_path.read_text().strip().splitlines()
            trajectory["user_feedback_count"] = len(fb_lines)
            trajectory["user_feedback_summary"] = fb_lines[-1][:300] if fb_lines else ""
        except Exception:
            pass

    trajectory_str = json.dumps(trajectory, indent=2)

    gate_metrics = (quality_gate.get("evidence_gate") or {}).get("metrics") or {}
    # Priority 2: Causal distillation (EvolveR: every run produces learnings)
    strategy_used = ""
    ms_path = proj_dir / "memory_strategy.json"
    if ms_path.exists():
        try:
            ms_data = json.loads(ms_path.read_text())
            strategy_used = (ms_data.get("selected_strategy") or {}).get("name") or ms_data.get("mode") or ""
        except Exception:
            pass
    what_helped_list = []
    if gate_metrics.get("verified_claim_count", 0) >= 3:
        what_helped_list.append("multi_source_verification")
    if gate_metrics.get("claim_support_rate", 0) >= 0.6:
        what_helped_list.append("high_claim_support_rate")
    what_hurt_list = []
    if status.startswith("failed"):
        what_hurt_list.append(status)
    if gate_metrics.get("claim_support_rate", 1) < 0.4:
        what_hurt_list.append("low_claim_support_rate")
    critic_weaknesses = []
    critique_path = proj_dir / "verify" / "critique.json"
    if not critique_path.exists():
        critique_path = proj_dir / "artifacts" / "critique.json" if (proj_dir / "artifacts").is_dir() else None
    if critique_path and critique_path.exists():
        try:
            cq = json.loads(critique_path.read_text())
            critic_weaknesses = (cq.get("weaknesses") or [])[:5]
        except Exception:
            pass
    claim_breakdown = {
        "verified_claim_count": gate_metrics.get("verified_claim_count"),
        "claim_support_rate": gate_metrics.get("claim_support_rate"),
    }
    _distill_causal_principles(
        project_id=project_id,
        question=question,
        domain=domain,
        strategy_used=strategy_used,
        findings_count=findings_count,
        claim_breakdown=claim_breakdown,
        critic_score=critic_score,
        critic_weaknesses=critic_weaknesses,
        what_helped=what_helped_list,
        what_hurt=what_hurt_list,
        model=model,
    )

    success = (critic_score >= 0.7 and status == "done") or (status == "done" and critic_score >= 0.5)
    principle_type = "guiding" if success else "cautionary"
    if success:
        prompt_instruction = (
            "Extract 3-5 GUIDING principles for future research projects in this domain. "
            "Each principle must be abstract enough to generalize, grounded in the trajectory, and actionable. "
            "Also propose one executable strategy policy for similar future runs. "
            "Return JSON object: {principles:[{principle,evidence,confidence}], strategy_proposal:{name,domain,policy,expected_benefit}}. "
            "policy keys: preferred_query_types, domain_rank_overrides, relevance_threshold, critic_threshold, revise_rounds, required_source_mix."
        )
    else:
        prompt_instruction = (
            "Extract 2-3 CAUTIONARY principles — what to AVOID in future research. "
            "Also propose one conservative recovery strategy policy for similar failures. "
            "Return JSON object: {principles:[{principle,evidence,confidence}], strategy_proposal:{name,domain,policy,expected_benefit}}. "
            "policy keys: preferred_query_types, domain_rank_overrides, relevance_threshold, critic_threshold, revise_rounds, required_source_mix."
        )

    system = (
        "You are a research quality analyst. Given a completed research project trajectory, "
        "extract concise principles and an executable strategy. Output only valid JSON, no markdown."
    )
    user = f"Trajectory:\n{trajectory_str}\n\n{prompt_instruction}"

    try:
        from tools.research_common import llm_call
        result = llm_call(model, system, user, project_id=project_id)
    except Exception as e:
        print(f"Distiller LLM failed (non-fatal): {e}", file=sys.stderr)
        sys.exit(0)

    text = (result.text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Distiller JSON parse failed (non-fatal): {e}", file=sys.stderr)
        sys.exit(0)
    if isinstance(parsed, list):
        principles_data = parsed
        strategy_proposal = None
    elif isinstance(parsed, dict):
        principles_data = parsed.get("principles") or []
        strategy_proposal = parsed.get("strategy_proposal") if isinstance(parsed.get("strategy_proposal"), dict) else None
    else:
        sys.exit(0)
    if not isinstance(principles_data, list):
        principles_data = []

    # Dedup among new principles (EvolveR-style: pairwise + BFS clusters)
    principles_data = _dedup_principles(principles_data[:15], project_id, model)

    try:
        from lib.memory import Memory
        mem = Memory()
        for p in principles_data:
            desc = (p.get("principle") or p.get("description") or "").strip()
            if not desc or len(desc) < 10:
                continue
            evidence = p.get("evidence") or ""
            evidence_json = json.dumps([evidence]) if evidence else "[]"

            # Match or Create: search existing, LLM equivalent check, then update or insert
            candidates = mem.search_principles(desc, limit=TOP_CANDIDATES_FOR_MATCH, domain=domain or None, principle_type=principle_type)
            matched = False
            for c in candidates:
                existing_desc = (c.get("description") or "")[:500]
                if not existing_desc:
                    continue
                if _llm_equivalent_to_existing(desc, existing_desc, project_id, model):
                    mem.update_principle_usage_success(c["id"], success=success)
                    mem.append_principle_evidence(c["id"], project_id, evidence[:500])
                    matched = True
                    break
            if not matched:
                mem.insert_principle(
                    principle_type=principle_type,
                    description=desc[:2000],
                    source_project_id=project_id,
                    domain=domain or None,
                    evidence_json=evidence_json,
                    metric_score=0.5,
                )

        # Strategy proposal (Memory v2): executable policy with strict bounds.
        if isinstance(strategy_proposal, dict):
            raw_policy = strategy_proposal.get("policy") if isinstance(strategy_proposal.get("policy"), dict) else {}
            try:
                rel_thr = float(raw_policy.get("relevance_threshold", 0.55))
            except Exception:
                rel_thr = 0.55
            try:
                crit_thr = float(raw_policy.get("critic_threshold", 0.55))
            except Exception:
                crit_thr = 0.55
            try:
                rev_rounds = int(raw_policy.get("revise_rounds", 2))
            except Exception:
                rev_rounds = 2
            policy = {
                "preferred_query_types": raw_policy.get("preferred_query_types") if isinstance(raw_policy.get("preferred_query_types"), dict) else {},
                "domain_rank_overrides": raw_policy.get("domain_rank_overrides") if isinstance(raw_policy.get("domain_rank_overrides"), dict) else {},
                "relevance_threshold": max(0.50, min(0.65, rel_thr)),
                "critic_threshold": max(0.50, min(0.65, crit_thr)),
                "revise_rounds": max(1, min(4, rev_rounds)),
                "required_source_mix": raw_policy.get("required_source_mix") if isinstance(raw_policy.get("required_source_mix"), dict) else {},
            }
            strategy_name = str(strategy_proposal.get("name") or f"{domain}-adaptive-{principle_type}")[:120]
            spid = mem.upsert_strategy_profile(
                name=strategy_name,
                domain=domain or "general",
                policy=policy,
                score=0.58 if success else 0.45,
                confidence=0.45,
                status="active",
                metadata={
                    "source_project_id": project_id,
                    "principle_type": principle_type,
                    "expected_benefit": str(strategy_proposal.get("expected_benefit") or "")[:400],
                },
            )
            mem.record_memory_decision(
                decision_type="strategy_proposed",
                details={
                    "strategy_profile_id": spid,
                    "strategy_name": strategy_name,
                    "domain": domain,
                    "success": success,
                },
                project_id=project_id,
                phase="distill",
                strategy_profile_id=spid,
                confidence=0.55 if success else 0.4,
            )
        mem.close()
    except Exception as e:
        print(f"Distiller Memory write failed (non-fatal): {e}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
