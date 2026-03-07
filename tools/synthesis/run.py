"""Orchestration: run_synthesis and main()."""
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

from tools.research_common import project_dir, load_project, get_claims_for_synthesis
from tools.synthesis.constants import MAX_FINDINGS, _model
from tools.synthesis.data import _load_findings, _load_sources, _semantic_relevance_sort
from tools.synthesis.ledger import (
    _build_claim_source_registry,
    _build_provenance_appendix,
    _build_ref_map,
    _ensure_source_finding_ids,
    normalize_to_strings,
)
from tools.synthesis.outline import _cluster_findings, _outline_sections
from tools.synthesis.checkpoint import _load_checkpoint, _save_checkpoint, _clear_checkpoint
from tools.synthesis.sections import (
    _epistemic_profile_from_ledger,
    _extract_section_key_points,
    _extract_used_claim_refs,
    _synthesize_section,
    _epistemic_reflect,
    _detect_gaps,
)
from tools.synthesis.blocks import (
    _evidence_summary_line,
    _key_numbers,
    _synthesize_research_situation_map,
    _synthesize_tipping_conditions,
    _synthesize_scenario_matrix,
    _synthesize_conclusions_next_steps,
    _synthesize_exec_summary,
    _synthesize_decision_matrix,
    _deduplicate_sections,
)
from tools.synthesis.contract import validate_synthesis_contract, SynthesisContractError, _factuality_guard


def run_synthesis(project_id: str) -> str:
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    project = load_project(proj_path)
    question = project.get("question", "")
    research_mode = ((project.get("config") or {}).get("research_mode") or "standard").strip().lower()
    discovery_brief: dict = {}
    if research_mode == "discovery":
        da_path = proj_path / "discovery_analysis.json"
        if da_path.exists():
            try:
                discovery_brief = json.loads(da_path.read_text()).get("discovery_brief", {}) or {}
            except Exception:
                pass
    verify_dir = proj_path / "verify"
    findings = _load_findings(proj_path, question=question)
    sources = _load_sources(proj_path)
    claim_ledger = get_claims_for_synthesis(proj_path)
    claim_ledger = _ensure_source_finding_ids(claim_ledger, proj_path)
    findings = _semantic_relevance_sort(question, findings, project_id)
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
        report_sections = (project.get("config") or {}).get("report_sections")
        if isinstance(report_sections, list):
            report_sections = [str(s) for s in report_sections if s][:15]
        else:
            report_sections = None
        if playbook_id:
            playbook_path = proj_path.parent / "playbooks" / f"{playbook_id}.json"
            if not playbook_path.exists():
                playbook_path = Path(os.environ.get("OPERATOR_ROOT", "/root/operator")) / "research" / "playbooks" / f"{playbook_id}.json"
            if playbook_path.exists():
                try:
                    pb = json.loads(playbook_path.read_text())
                    playbook_instructions = pb.get("synthesis_instructions")
                    if report_sections is None and isinstance(pb.get("report_sections"), list):
                        report_sections = [str(s) for s in pb["report_sections"] if s][:15]
                except Exception:
                    pass
        entity_context = None
        graph_path = proj_path / "connect" / "entity_graph.json"
        if graph_path.exists():
            try:
                graph = json.loads(graph_path.read_text())
                entities = graph.get("entities", [])[:25]
                rels = graph.get("relations", [])[:15]
                names = [e.get("name") for e in entities if e.get("name")]
                rel_strs = [f"{r.get('from')} {r.get('relation_type', '')} {r.get('to')}" for r in rels if r.get("from") and r.get("to")]
                if names or rel_strs:
                    entity_context = "Entities: " + ", ".join(names[:20]) + ("; Relations: " + "; ".join(rel_strs[:10]) if rel_strs else "")
            except Exception:
                pass
        try:
            from tools.research_progress import step as progress_step
            progress_step(project_id, "Generating outline")
        except Exception:
            pass
        section_titles = _outline_sections(question, clusters, playbook_instructions, project_id, report_sections=report_sections, entity_context=entity_context)
        deep_parts = []
        start_index = 0

    now = datetime.now(timezone.utc)
    report_date = now.strftime("%Y-%m-%d")
    ts = now.strftime("%Y%m%dT%H%M%SZ")

    parts = []
    parts.append(f"# Research Report\n\n**Report as of: {report_date}**  \nProject: `{project_id}`  \nQuestion: {question}\n")
    parts.append("\n" + _evidence_summary_line(claim_ledger, research_mode) + "\n\n")
    parts.append("## KEY NUMBERS\n\n")
    parts.append(_key_numbers(findings, claim_ledger, project_id))
    parts.append("\n\n---\n\n")
    if research_mode == "discovery" and discovery_brief:
        parts.append("## Discovery Map\n\n")
        parts.append("### Novel Connections\n\n")
        for nc in discovery_brief.get("novel_connections", [])[:5]:
            parts.append(f"- {nc}\n")
        parts.append("\n### Emerging Concepts\n\n")
        for ec in discovery_brief.get("emerging_concepts", [])[:5]:
            parts.append(f"- {ec}\n")
        parts.append("\n### Research Frontier (where experts disagree)\n\n")
        for rf in discovery_brief.get("research_frontier", [])[:5]:
            parts.append(f"- {rf}\n")
        parts.append("\n### Unexplored Opportunities\n\n")
        for uo in discovery_brief.get("unexplored_opportunities", [])[:5]:
            parts.append(f"- {uo}\n")
        if discovery_brief.get("key_hypothesis"):
            parts.append(f"\n### Key Hypothesis\n\n> {discovery_brief['key_hypothesis']}\n\n")
        parts.append("\n---\n\n")

    epistemic_profile = _epistemic_profile_from_ledger(claim_ledger)
    cited_urls: set[str] = set()
    for c in claim_ledger:
        for u in normalize_to_strings(c.get("supporting_source_ids")):
            if u:
                cited_urls.add(u)
    checkpoint_bodies = list(ck["bodies"]) if (ck and ck.get("bodies")) else []
    accumulated_summary: list[str] = []
    accumulated_claim_refs: set[str] = set()
    for b in checkpoint_bodies:
        accumulated_summary.extend(_extract_section_key_points(b))
        accumulated_claim_refs.update(_extract_used_claim_refs(b))
    tools_dir = Path(__file__).resolve().parent.parent
    operator_root = tools_dir.parent
    for i in range(start_index, len(clusters)):
        cluster = clusters[i]
        title = section_titles[i] if i < len(section_titles) else f"Analysis: Topic {i+1}"
        section_findings = [findings[j] for j in cluster if 0 <= j < len(findings)]
        if cited_urls:
            section_findings = sorted(
                section_findings,
                key=lambda f: (0 if ((f.get("url") or "").strip() in cited_urls) else 1),
            )
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
        body = _synthesize_section(title, section_findings, ref_map, proj_path, question, project_id, rel_sources, claim_ledger, previous_sections_summary=accumulated_summary, used_claim_refs=accumulated_claim_refs, epistemic_profile=epistemic_profile, research_mode=research_mode, discovery_brief=discovery_brief)
        body = _epistemic_reflect(body, claim_ledger, project_id)
        accumulated_summary.extend(_extract_section_key_points(body))
        accumulated_claim_refs.update(_extract_used_claim_refs(body))
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
                            r = subprocess.run(
                                [sys.executable, str(tools_dir / "research_web_reader.py"), url],
                                capture_output=True, text=True, timeout=30, cwd=str(operator_root)
                            )
                            if r.returncode == 0:
                                try:
                                    wr = json.loads(r.stdout)
                                    if wr.get("text"):
                                        new_f = {"url": url, "title": wr.get("title", ""), "excerpt": (wr.get("text") or "")[:1500]}
                                        section_findings = section_findings + [new_f]
                                        body = _synthesize_section(title, section_findings, ref_map, proj_path, question, project_id, rel_sources, claim_ledger, previous_sections_summary=accumulated_summary, used_claim_refs=accumulated_claim_refs, epistemic_profile=epistemic_profile, research_mode=research_mode, discovery_brief=discovery_brief)
                                except Exception:
                                    pass
                except Exception:
                    pass
        checkpoint_bodies.append(body)
        deep_parts.append(f"## {title}\n\n{body}")
        _save_checkpoint(proj_path, clusters, section_titles, checkpoint_bodies)
    checkpoint_bodies = _deduplicate_sections(checkpoint_bodies)
    deep_parts = [f"## {section_titles[start_index + j]}\n\n{checkpoint_bodies[j]}" for j in range(len(checkpoint_bodies))]
    parts.append("\n\n".join(deep_parts))
    parts.append("\n\n---\n\n")

    source_count = len(sources)
    read_count = len(list((proj_path / "sources").glob("*_content.json")))
    findings_count_actual = len(list((proj_path / "findings").glob("*.json")))
    parts.append("## Methodology\n\n")
    parts.append(f"This report is based on **{findings_count_actual} findings** from **{source_count} sources** ")
    parts.append(f"({read_count} successfully read). ")
    parts.append(f"Synthesis model: {_model()}. Verification and claim ledger applied. ")
    parts.append(f"Report generated at {ts}.\n\n")

    if contradictions:
        parts.append("## Contradictions & Open Questions\n\n")
        for c in contradictions[:10]:
            parts.append(f"- **{c.get('claim', c.get('topic', 'Unknown'))}**: {c.get('summary', c.get('description', ''))}\n")
        parts.append("\n")

    parts.append("## Verification Summary\n\n| # | Claim | Status | Sources |\n| --- | --- | --- | ---|\n")
    for i, c in enumerate(claim_ledger[:50], 1):
        text = (c.get("text") or "")[:80].replace("|", " ")
        tier = (c.get("verification_tier") or "").strip().upper()
        if tier == "AUTHORITATIVE":
            status = "AUTHORITATIVE"
        elif tier == "VERIFIED" or c.get("is_verified"):
            status = "VERIFIED"
        elif tier == "ESTABLISHED":
            status = "ESTABLISHED"
        elif tier == "EMERGING":
            status = "EMERGING"
        elif tier == "SPECULATIVE":
            status = "SPECULATIVE"
        elif (c.get("falsification_status") or "").strip() == "PASS_TENTATIVE":
            status = "TENTATIVE"
        else:
            status = "UNVERIFIED"
        n_src = len(normalize_to_strings(c.get("supporting_source_ids")))
        parts.append(f"| {i} | {text}... | {status} | {n_src} |\n")
    parts.append("\n")

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

    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id, "Generating Scenario Matrix")
    except Exception:
        pass
    scenario = _synthesize_scenario_matrix(question, claim_ledger, thesis, tipping, project_id)
    if scenario:
        parts.append("## Scenario Matrix\n\n")
        parts.append(scenario)
        parts.append("\n\n")

    concl, next_steps = _synthesize_conclusions_next_steps(thesis, contradictions, question, project_id, epistemic_profile=epistemic_profile, research_mode=research_mode, discovery_brief=discovery_brief)
    parts.append("## Conclusions & Thesis\n\n")
    parts.append(concl)
    parts.append("\n\n## Recommended Next Steps\n\n")
    parts.append(next_steps)
    parts.append("\n\n---\n\n")

    _clear_checkpoint(proj_path)
    full_so_far = "\n".join(str(p) for p in parts)
    exec_summary = _synthesize_exec_summary(full_so_far, question, project_id, epistemic_profile=epistemic_profile)
    idx_after_key = full_so_far.find("\n\n---\n\n")
    if idx_after_key >= 0:
        idx_after_key += len("\n\n---\n\n")
    else:
        idx_after_key = 0
    if exec_summary:
        report_body = (
            full_so_far[:idx_after_key] +
            "## Executive Summary\n\n" + exec_summary + "\n\n---\n\n" +
            full_so_far[idx_after_key:]
        )
    else:
        report_body = full_so_far

    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id, "Generating Executive Decision Synthesis")
    except Exception:
        pass
    decision_matrix = _synthesize_decision_matrix(question, claim_ledger, thesis, tipping, project_id)
    if decision_matrix:
        methodology_idx = report_body.find("## Methodology")
        if methodology_idx >= 0:
            report_body = (
                report_body[:methodology_idx] +
                "## Executive Decision Synthesis\n\n" + decision_matrix + "\n\n---\n\n" +
                report_body[methodology_idx:]
            )
        else:
            first_section = report_body.find("\n## ")
            if first_section >= 0:
                report_body = (
                    report_body[:first_section] +
                    "\n\n## Executive Decision Synthesis\n\n" + decision_matrix + "\n\n---\n\n" +
                    report_body[first_section:]
                )

    registry_md = _build_claim_source_registry(claim_ledger, sources, ref_list)
    report_body += "\n\n## Claim Evidence Registry\n\n"
    report_body += registry_md
    provenance_md = _build_provenance_appendix(claim_ledger)
    report_body += "\n\n## Provenance\n\n"
    report_body += provenance_md
    report_body += "\n\n## Appendix B: Methodology Details\n\n"
    report_body += f"- Synthesis model: {_model()}\n- Findings cap: {MAX_FINDINGS}\n- Report timestamp: {ts}\n\n"
    report_body += "## References\n\n"
    for i, (url, title) in enumerate(ref_list, 1):
        if title:
            report_body += f"[{i}] {title}  \n    {url}\n\n"
        else:
            report_body += f"[{i}] {url}\n\n"

    factuality = _factuality_guard(report_body, findings, claim_ledger)
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
        "factuality_guard": factuality,
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


def main() -> None:
    try:
        from tools.research_tool_registry import ensure_tool_context
        ensure_tool_context("research_synthesize.py")
    except ImportError:
        pass
    if len(sys.argv) < 2:
        print("Usage: research_synthesize.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    try:
        report = run_synthesis(project_id)
        print(report, flush=True)
    except Exception as e:
        print(f"# Synthesis Error\n\n{e}", file=sys.stderr)
        sys.exit(1)
