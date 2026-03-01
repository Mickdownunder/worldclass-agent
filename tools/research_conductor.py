#!/usr/bin/env python3
"""
Research Conductor: dynamic orchestration of research phases.
Decides WHAT to do next (search_more, read_more, verify, synthesize) from bounded state.
Epistemic judgments stay in existing tools; conductor only picks the next action.

Design:
- Minimal bounded state: 6 metrics (no raw findings in state).
- Exactly 4 actions: search_more, read_more, verify, synthesize.
- LLM picks action from state; deterministic fallback if LLM fails.
- Max 25 steps hard limit.

Modes:
- shadow: read state, decide action, append to conductor_decisions.json (no execution).
- run: conductor as master (when RESEARCH_USE_CONDUCTOR=1); loop until synthesize or limit.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import (
    project_dir,
    load_project,
    llm_call,
    audit_log,
)
from tools.research_budget import check_budget, get_budget_limit
from tools.research_coverage import assess_coverage
from tools.research_coverage import _load_json, _iter_findings, _iter_source_meta

# Bounded state: 6 metrics only (no raw findings)
CONDUCTOR_ACTIONS = ["search_more", "read_more", "verify", "synthesize"]
MAX_STEPS = 25
MAX_CONSECUTIVE_TOOL_FAILURES = 3


@dataclass
class ConductorState:
    """Minimal bounded state for conductor decisions. No raw findings."""
    findings_count: int
    source_count: int
    coverage_score: float  # 0-1
    verified_claims: int
    budget_spent_pct: float  # 0-1
    steps_taken: int
    findings_delta: int = 0  # change since last conductor decision
    sources_delta: int = 0  # change since last conductor decision


def read_state(project_id: str) -> ConductorState:
    """Build conductor state from project files. Strict boundary: no raw findings."""
    proj = project_dir(project_id)
    project = load_project(proj)
    if not proj.exists():
        return ConductorState(
            findings_count=0,
            source_count=0,
            coverage_score=0.0,
            verified_claims=0,
            budget_spent_pct=0.0,
            steps_taken=0,
            findings_delta=0,
            sources_delta=0,
        )

    # findings_count
    findings_dir = proj / "findings"
    findings_count = len(list(findings_dir.glob("*.json"))) if findings_dir.exists() else 0

    # source_count (unique sources, exclude _content)
    sources_dir = proj / "sources"
    source_count = 0
    if sources_dir.exists():
        source_count = len([f for f in sources_dir.glob("*.json") if not f.name.endswith("_content.json")])

    # coverage_score 0-1 from latest coverage or coverage tool (conductor-written first when in run_cycle)
    coverage_score = 0.0
    for name in ["coverage_conductor.json", "coverage_round3.json", "coverage_round2.json", "coverage_round1.json"]:
        p = proj / name
        if p.exists():
            try:
                data = json.loads(p.read_text())
                coverage_score = float(data.get("coverage_rate", 0))
                break
            except Exception:
                pass
    if coverage_score == 0.0 and (proj / "research_plan.json").exists():
        plan = _load_json(proj / "research_plan.json", {})
        findings = _iter_findings(proj)
        sources = _iter_source_meta(proj)
        result = assess_coverage(plan, findings, sources)
        coverage_score = float(result.get("coverage_rate", 0))
    if coverage_score >= 1.0 and findings_count < 40:
        coverage_score = min(0.95, findings_count / 50.0)

    # verified_claims from quality_gate or claim_ledger
    verified_claims = 0
    qg = project.get("quality_gate") or {}
    eg = qg.get("evidence_gate") or {}
    metrics = eg.get("metrics") if isinstance(eg, dict) else {}
    if isinstance(metrics, dict):
        verified_claims = int(metrics.get("verified_claim_count", 0))
    if verified_claims == 0:
        ledger_path = proj / "verify" / "claim_ledger.json"
        if ledger_path.exists():
            try:
                data = json.loads(ledger_path.read_text())
                claims = data.get("claims", [])
                verified_claims = sum(1 for c in claims if c.get("is_verified") or c.get("verified"))
            except Exception:
                pass

    # budget_spent_pct 0-1
    budget_info = check_budget(project_id)
    limit = budget_info.get("budget_limit") or (get_budget_limit(project) if project else 1.0)
    current = budget_info.get("current_spend", 0.0)
    budget_spent_pct = min(1.0, round(current / limit, 4)) if limit else 0.0

    # steps_taken: phase_history length, conductor_state, or sum of conductor_overrides
    phase_history = project.get("phase_history") or []
    steps_taken = len(phase_history)
    conductor_file = proj / "conductor_state.json"
    if conductor_file.exists():
        try:
            cdata = json.loads(conductor_file.read_text())
            steps_taken = int(cdata.get("steps_taken", steps_taken))
        except Exception:
            pass
    overrides_path = proj / "conductor_overrides.json"
    if overrides_path.exists():
        try:
            ov = json.loads(overrides_path.read_text())
            steps_taken = sum(ov.values()) if isinstance(ov, dict) else steps_taken
        except Exception:
            pass

    findings_delta = 0
    sources_delta = 0
    decisions_path = proj / "conductor_decisions.json"
    if decisions_path.exists():
        try:
            entries = json.loads(decisions_path.read_text())
            if isinstance(entries, list) and entries:
                last = entries[-1].get("state") or {}
                if isinstance(last, dict):
                    findings_delta = findings_count - int(last.get("findings_count", 0))
                    sources_delta = source_count - int(last.get("source_count", 0))
        except Exception:
            pass

    return ConductorState(
        findings_count=findings_count,
        source_count=source_count,
        coverage_score=round(coverage_score, 4),
        verified_claims=verified_claims,
        budget_spent_pct=budget_spent_pct,
        steps_taken=min(steps_taken, MAX_STEPS),
        findings_delta=findings_delta,
        sources_delta=sources_delta,
    )


def _deterministic_fallback(state: ConductorState, phase: str) -> str:
    """Fixed sequence: search -> read -> verify -> synthesize when LLM fails."""
    order = ["search_more", "read_more", "verify", "synthesize"]
    phase_to_next = {
        "explore": "read_more",
        "focus": "read_more",
        "connect": "verify",
        "verify": "synthesize",
        "synthesize": "synthesize",
        "done": "synthesize",
    }
    next_action = phase_to_next.get(phase, "search_more")
    if state.steps_taken >= MAX_STEPS or state.budget_spent_pct >= 0.95:
        return "synthesize"
    if phase in ("explore", "focus") and state.coverage_score >= 0.85:
        return "verify"
    if phase == "verify" and state.verified_claims >= 3:
        return "synthesize"
    return next_action if next_action in order else order[0]


def decide_action(
    state: ConductorState,
    question: str,
    compressed_context: str = "",
    phase: str = "",
    project_id: str = "",
) -> str:
    """LLM picks action from 4 options; on failure use deterministic fallback."""
    model = os.environ.get("RESEARCH_CONDUCTOR_MODEL", "gemini-2.5-flash")
    state_dict = asdict(state)
    research_mode = "standard"
    if project_id:
        try:
            proj = project_dir(project_id)
            if proj.exists():
                project = load_project(proj)
                research_mode = ((project.get("config") or {}).get("research_mode") or "standard").strip().lower()
        except Exception:
            pass
    system = """You are a research conductor. You decide ONLY the next action for a research pipeline.
State (bounded metrics only):
- findings_count, source_count: evidence gathered
- coverage_score (0-1): topic coverage from coverage tool
- verified_claims: number of verified claims
- budget_spent_pct (0-1): budget used
- steps_taken: total conductor overrides so far (max 25)
- findings_delta, sources_delta: change since last decision. If both are 0 or near 0, additional rounds of the same phase are unlikely to help — proceed to next phase.

IMPORTANT PHASE CONTEXT:
- verified_claims is ALWAYS 0 before the verify phase runs. This is expected.
- In explore/focus/connect phases: decide based on coverage_score and findings_count, NOT verified_claims.
- Only consider verified_claims when current phase is verify or synthesize.
- If coverage_score >= 0.8 and findings_count >= 30, the research base is strong enough to proceed.

Allowed actions ONLY (reply with exactly one word):
- search_more: need more sources or broader coverage (coverage_score < 0.7)
- read_more: have sources to read, need more content/findings (findings_count < 20)
- verify: have enough evidence, run verification (coverage >= 0.8 AND findings >= 30)
- synthesize: enough evidence and verification done, write report

Reply with exactly one word: search_more, read_more, verify, or synthesize. No explanation."""
    if research_mode == "discovery":
        system += """

DISCOVERY MODE: Prioritize BREADTH over DEPTH.
- Prefer 'search_more' to find diverse perspectives over 'read_more' for confirmation.
- Only 'verify' if findings_count >= 30 (verify late, explore early).
- 'synthesize' when you have 8+ unique source domains and 20+ findings.
Do NOT send back to verify if you already have diverse findings."""

    user_parts = [
        f"State: {json.dumps(state_dict)}",
        f"Research question: {question[:500]}",
        f"Current phase (pipeline): {phase}",
    ]
    if compressed_context:
        user_parts.append(f"Compressed context (recent): {compressed_context[:800]}")
    user_parts.append("Which single action next? Reply one word only.")
    user = "\n".join(user_parts)

    try:
        result = llm_call(model, system, user, project_id=project_id)
        text = (result.text or "").strip().lower()
        for action in CONDUCTOR_ACTIONS:
            if action in text or text == action.replace("_", ""):
                return action
        # Parse "synthesize" etc from response
        if "synthesiz" in text:
            return "synthesize"
        if "verify" in text:
            return "verify"
        if "read" in text or "read_more" in text:
            return "read_more"
        if "search" in text or "search_more" in text:
            return "search_more"
    except Exception:
        pass
    return _deterministic_fallback(state, phase)


# Phase-transition gate: proposed_next -> action conductor should want to proceed
PHASE_TO_ACTION = {
    "explore": "search_more",
    "focus": "read_more",
    "connect": "read_more",  # connect is cross-referencing findings, similar to reading
    "verify": "verify",
    "synthesize": "synthesize",
    "done": "synthesize",
}
ACTION_TO_PHASE = {
    "search_more": "explore",
    "read_more": "focus",
    "verify": "verify",
    "synthesize": "synthesize",
}


def _load_overrides(project_id: str) -> dict[str, int]:
    """Load conductor override counts per transition (current_phase->proposed_next)."""
    proj = project_dir(project_id)
    path = proj / "conductor_overrides.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_override(project_id: str, key: str) -> None:
    """Increment override count for this transition (max 1 override per transition)."""
    overrides = _load_overrides(project_id)
    overrides[key] = overrides.get(key, 0) + 1
    proj = project_dir(project_id)
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "conductor_overrides.json").write_text(
        json.dumps(overrides, indent=2)
    )


def gate_check(project_id: str, proposed_next: str) -> str:
    """
    Hybrid gate: conductor advises whether to proceed or repeat a phase.
    Returns proposed_next if we should advance, or alternative phase to run again.
    Safety: RESEARCH_CONDUCTOR_GATE=0 disables; budget_spent_pct >= 0.8 or max-1-override force proceed.
    """
    if os.environ.get("RESEARCH_CONDUCTOR_GATE", "1") == "0":
        return proposed_next
    proj = project_dir(project_id)
    if not proj.exists():
        return proposed_next
    project = load_project(proj)
    current_phase = (project.get("phase") or "explore").strip().lower()
    if proposed_next == "done":
        return proposed_next
    state = read_state(project_id)
    research_mode = ((project.get("config") or {}).get("research_mode") or "standard").strip().lower()
    # Discovery: only allow synthesize when enough breadth (configurable)
    if research_mode == "discovery" and proposed_next == "synthesize":
        min_findings = max(1, int(os.environ.get("RESEARCH_DISCOVERY_SYNTHESIZE_MIN_FINDINGS", "15")))
        min_sources = max(1, int(os.environ.get("RESEARCH_DISCOVERY_SYNTHESIZE_MIN_SOURCES", "8")))
        if state.findings_count >= min_findings and state.source_count >= min_sources:
            return proposed_next
    # Strong satisfaction: avoid endless explore/focus loops
    if current_phase in ("explore", "focus", "connect") and state.coverage_score >= 0.8 and state.findings_count >= 30:
        return proposed_next
    # Softer satisfaction for explore: coverage already good and enough findings → proceed (conductor not "always unsatisfied")
    if current_phase == "explore" and proposed_next == "focus":
        if state.coverage_score >= 0.72 and state.findings_count >= 25:
            return proposed_next
    if state.budget_spent_pct >= 0.8:
        return proposed_next
    key = f"{current_phase}->{proposed_next}"
    # Cap overrides: after 1 extra round for explore->focus, force advance (don't loop forever)
    max_overrides = 1 if key == "explore->focus" else 2
    if _load_overrides(project_id).get(key, 0) >= max_overrides:
        return proposed_next
    question = (project.get("question") or "")[:2000]
    compressed = ""
    try:
        from tools.research_context_manager import get_compressed_context
        compressed = get_compressed_context(project_id) or ""
    except Exception:
        pass
    if not compressed:
        plan_path = proj / "research_plan.json"
        if plan_path.exists():
            try:
                plan = json.loads(plan_path.read_text())
                queries = plan.get("queries", [])[:5]
                compressed = "Research queries: " + ", ".join((q.get("query") or "")[:60] for q in queries)
            except Exception:
                pass
        findings_dir = proj / "findings"
        if findings_dir.exists():
            try:
                latest = sorted(findings_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)[-3:]
                summaries = []
                for f in latest:
                    try:
                        d = json.loads(f.read_text())
                        summaries.append((d.get("excerpt") or "")[:100])
                    except Exception:
                        pass
                if summaries:
                    compressed += " | Latest findings: " + "; ".join(summaries)
            except Exception:
                pass
    action = decide_action(
        state, question, compressed, phase=current_phase, project_id=project_id
    )
    log_shadow_decision(project_id, current_phase, state, action)
    expected = PHASE_TO_ACTION.get(proposed_next, proposed_next)
    if action == expected:
        return proposed_next
    if action == "synthesize" and proposed_next in ("synthesize", "done"):
        return proposed_next
    override_phase = ACTION_TO_PHASE.get(action, proposed_next)
    _save_override(project_id, key)
    return override_phase


def log_shadow_decision(project_id: str, phase: str, state: ConductorState, action: str) -> None:
    """Append one shadow decision to conductor_decisions.json (per run / per project)."""
    proj = project_dir(project_id)
    proj.mkdir(parents=True, exist_ok=True)
    decisions_path = proj / "conductor_decisions.json"
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": phase,
        "state": asdict(state),
        "action": action,
    }
    entries = []
    if decisions_path.exists():
        try:
            raw = decisions_path.read_text()
            if raw.strip():
                entries = json.loads(raw)
                if not isinstance(entries, list):
                    entries = [entries]
        except Exception:
            entries = []
    entries.append(entry)
    decisions_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    audit_log(proj, "conductor_shadow_decision", {"phase": phase, "action": action})


def write_conductor_step_count(project_id: str, steps_taken: int) -> None:
    """Persist steps_taken for next read_state (when conductor is master)."""
    proj = project_dir(project_id)
    path = proj / "conductor_state.json"
    data = {"steps_taken": steps_taken, "updated_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(data, indent=2))


def save_conductor_state(project_id: str, state: ConductorState) -> None:
    """Persist full state for supervisor anomaly detection (e.g. coverage stagnation)."""
    proj = project_dir(project_id)
    path = proj / "conductor_state.json"
    data = {
        **asdict(state),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))


def run_shadow(project_id: str, phase: str, artifacts_dir: Path | None = None) -> str:
    """Shadow mode: read state, decide action, log to conductor_decisions.json. Returns chosen action."""
    state = read_state(project_id)
    proj = project_dir(project_id)
    project = load_project(proj)
    question = (project.get("question") or "")[:2000]
    compressed = ""
    try:
        from tools.research_context_manager import get_compressed_context
        compressed = get_compressed_context(project_id) or ""
    except Exception:
        pass
    action = decide_action(state, question, compressed, phase=phase, project_id=project_id)
    log_shadow_decision(project_id, phase, state, action)
    save_conductor_state(project_id, state)
    return action


def _run_tool(project_id: str, tool: str, *args: str, cwd: Path | None = None, capture_stdout: bool = False):
    """Run a research tool via subprocess. Returns True if exit 0, or (True, stdout_text) if capture_stdout.
    On non-zero exit, appends an entry to conductor_tool_errors.log in the project dir."""
    root = Path(__file__).resolve().parent.parent
    tool_path = root / "tools" / tool
    cmd = [sys.executable, str(tool_path)] + list(args)
    env = os.environ.copy()
    env["OPERATOR_ROOT"] = str(root)
    env["RESEARCH_PROJECT_ID"] = project_id
    try:
        r = subprocess.run(cmd, cwd=cwd or str(root), env=env, timeout=600, capture_output=True, text=True)
        if r.returncode != 0:
            try:
                proj = project_dir(project_id)
                log_path = proj / "conductor_tool_errors.log"
                err_snippet = (r.stderr or r.stdout or "")[:500].replace("\n", " ")
                entry = {
                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "tool": tool,
                    "args": list(args)[:10],
                    "returncode": r.returncode,
                    "stderr_snippet": err_snippet,
                }
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass
        if capture_stdout:
            return r.returncode == 0, (r.stdout or "")
        return r.returncode == 0
    except Exception as e:
        try:
            proj = project_dir(project_id)
            log_path = proj / "conductor_tool_errors.log"
            entry = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tool": tool,
                "args": list(args)[:10],
                "error": str(e)[:300],
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return (False, "") if capture_stdout else False


def run_cycle(project_id: str) -> bool:
    """
    Phase C: Conductor as master. Loop until synthesize complete or max steps.
    Executes actions via existing Python tools; context manager + supervisor after steps.
    Returns True if cycle completed (synthesize done or done phase).
    Stops after MAX_CONSECUTIVE_TOOL_FAILURES consecutive tool failures and sets status.
    """
    root = Path(__file__).resolve().parent.parent
    proj = project_dir(project_id)
    if not proj.exists():
        return False
    project = load_project(proj)
    question = (project.get("question") or "")[:2000]
    consecutive_failures: list[int] = [0]

    def run_tool(tool: str, *args: str, capture_stdout: bool = False) -> Any:
        out = _run_tool(project_id, tool, *args, capture_stdout=capture_stdout)
        ok = out[0] if isinstance(out, tuple) else out
        if ok:
            consecutive_failures[0] = 0
        else:
            consecutive_failures[0] += 1
        return out

    def check_abort() -> bool:
        if consecutive_failures[0] >= MAX_CONSECUTIVE_TOOL_FAILURES:
            try:
                project = load_project(proj)
                project["status"] = "failed_conductor_tool_errors"
                project["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                (proj / "project.json").write_text(json.dumps(project, indent=2) + "\n")
            except Exception:
                pass
            return True
        return False

    for step in range(MAX_STEPS):
        state = read_state(project_id)
        project = load_project(proj)
        status = (project.get("status") or "").strip()
        phase = project.get("phase", "explore")
        if phase == "done" or status.startswith("failed") or status in ("cancelled", "abandoned"):
            return True
        if state.budget_spent_pct >= 0.95 or state.steps_taken >= MAX_STEPS:
            break
        try:
            from tools.research_context_manager import get_compressed_context, add_compressed_batch
            compressed = get_compressed_context(project_id) or ""
        except Exception:
            compressed = ""
        action = decide_action(state, question, compressed, phase=phase, project_id=project_id)
        save_conductor_state(project_id, state)
        write_conductor_step_count(project_id, state.steps_taken + 1)

        if action == "synthesize":
            try:
                from tools.research_progress import step as progress_step
                progress_step(project_id, "Conductor: synthesizing report")
            except Exception:
                pass
            ok_syn, out_syn = run_tool("research_synthesize.py", project_id, capture_stdout=True)
            if ok_syn and out_syn.strip():
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                (proj / "reports").mkdir(parents=True, exist_ok=True)
                (proj / "reports" / f"report_{ts}.md").write_text(out_syn, encoding="utf-8")
                run_tool("research_synthesize_postprocess.py", project_id)
            try:
                from tools.research_critic import critique_report
                project = load_project(proj)
                critique_report(proj, project, None, project_id=project_id)
            except Exception:
                pass
            advance_phase(proj, "done")
            return True

        if action == "verify":
            try:
                from tools.research_progress import step as progress_step
                progress_step(project_id, "Conductor: running verification")
            except Exception:
                pass
            run_tool("research_verify.py", project_id, "source_reliability")
            run_tool("research_verify.py", project_id, "claim_verification")
            run_tool("research_verify.py", project_id, "fact_check")
            run_tool("research_verify.py", project_id, "claim_ledger")
            gate_ok, gate_out = run_tool("research_quality_gate.py", project_id, capture_stdout=True)
            if check_abort():
                return False
            if gate_ok and gate_out.strip():
                try:
                    gate = json.loads(gate_out)
                    if gate.get("pass"):
                        project = load_project(proj)
                        project.setdefault("quality_gate", {})["evidence_gate"] = {"status": "passed", "decision": "pass", "metrics": gate.get("metrics", {})}
                        (proj / "project.json").write_text(json.dumps(project, indent=2) + "\n")
                        advance_phase(proj, "synthesize")
                except Exception:
                    pass
            if check_abort():
                return False
            continue

        if action == "read_more":
            try:
                from tools.research_progress import step as progress_step
                progress_step(project_id, "Conductor: reading more sources")
            except Exception:
                pass
            # Build list of unread source paths
            sources_dir = proj / "sources"
            read_list = []
            if sources_dir.exists():
                for f in sources_dir.glob("*.json"):
                    if f.name.endswith("_content.json"):
                        continue
                    if not (sources_dir / (f.stem + "_content.json")).exists():
                        read_list.append(str(f))
            if read_list:
                order_file = proj / "conductor_read_order.txt"
                order_file.write_text("\n".join(read_list[:15]))
                run_tool("research_parallel_reader.py", project_id, "explore", "--input-file", str(order_file), "--read-limit", "10", "--workers", "8")
            run_tool("research_deep_extract.py", project_id)
            try:
                add_compressed_batch(project_id)
                from tools.research_dynamic_outline import merge_evidence_into_outline
                merge_evidence_into_outline(project_id)
                from tools.research_supervisor import run_supervisor
                run_supervisor(project_id)
            except Exception:
                pass
            ok_cov, out_cov = _run_tool(project_id, "research_coverage.py", project_id, capture_stdout=True)
            if ok_cov and out_cov and out_cov.strip():
                try:
                    (proj / "coverage_conductor.json").write_text(out_cov, encoding="utf-8")
                except Exception:
                    pass
            if check_abort():
                return False
            continue

        if action == "search_more":
            try:
                from tools.research_progress import step as progress_step
                progress_step(project_id, "Conductor: searching for more sources")
            except Exception:
                pass
            plan_path = proj / "research_plan.json"
            if not plan_path.exists():
                run_tool("research_planner.py", question, project_id)
            plan_path = proj / "research_plan.json"
            if plan_path.exists():
                ok, out = run_tool("research_web_search.py", "--queries-file", str(plan_path), "--max-per-query", "5", capture_stdout=True)
                if ok and out.strip():
                    try:
                        import hashlib
                        results = json.loads(out) if out.strip().startswith("[") else json.loads(out)
                        if isinstance(results, list):
                            for item in results[:25]:
                                url = (item.get("url") or "").strip()
                                if url:
                                    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
                                    (proj / "sources").mkdir(parents=True, exist_ok=True)
                                    (proj / "sources" / f"{fid}.json").write_text(json.dumps({**item, "confidence": 0.5}))
                    except Exception:
                        pass
            ok_cov, out_cov = _run_tool(project_id, "research_coverage.py", project_id, capture_stdout=True)
            if ok_cov and out_cov and out_cov.strip():
                try:
                    (proj / "coverage_conductor.json").write_text(out_cov, encoding="utf-8")
                except Exception:
                    pass
            if check_abort():
                return False
            continue
    return False


def advance_phase(proj: Path, next_phase: str) -> None:
    """Advance project phase (mirrors research_advance_phase)."""
    try:
        from tools.research_advance_phase import advance
        advance(proj, next_phase)
    except Exception:
        pass


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        from tools.research_tool_registry import ensure_tool_context
        ensure_tool_context("research_conductor.py")
    except ImportError:
        pass
    if len(sys.argv) < 3:
        print(
            "Usage: research_conductor.py <shadow|run|run_cycle|gate> <project_id> [phase|proposed_next] [artifacts_dir]",
            file=sys.stderr,
        )
        sys.exit(2)
    mode = sys.argv[1].lower()
    project_id = sys.argv[2]
    phase = sys.argv[3] if len(sys.argv) > 3 else ""
    art_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    if not project_id or not project_dir(project_id).exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)

    if mode == "gate":
        if not phase:
            print("Usage: research_conductor.py gate <project_id> <proposed_next_phase>", file=sys.stderr)
            sys.exit(2)
        result_phase = gate_check(project_id, phase.strip().lower())
        print(result_phase)
        sys.exit(0)

    if mode == "shadow":
        action = run_shadow(project_id, phase, art_path)
        print(json.dumps({"action": action, "phase": phase}, indent=2))
    elif mode == "run":
        state = read_state(project_id)
        proj = project_dir(project_id)
        project = load_project(proj)
        question = (project.get("question") or "")[:2000]
        compressed = ""
        try:
            from tools.research_context_manager import get_compressed_context
            compressed = get_compressed_context(project_id) or ""
        except Exception:
            pass
        current_phase = project.get("phase", "explore")
        action = decide_action(state, question, compressed, phase=current_phase, project_id=project_id)
        write_conductor_step_count(project_id, state.steps_taken + 1)
        print(json.dumps({"action": action, "state": asdict(state)}, indent=2))
    elif mode == "run_cycle":
        ok = run_cycle(project_id)
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
