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


@dataclass
class ConductorState:
    """Minimal bounded state for conductor decisions. No raw findings."""
    findings_count: int
    source_count: int
    coverage_score: float  # 0-1
    verified_claims: int
    budget_spent_pct: float  # 0-1
    steps_taken: int


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
        )

    # findings_count
    findings_dir = proj / "findings"
    findings_count = len(list(findings_dir.glob("*.json"))) if findings_dir.exists() else 0

    # source_count (unique sources, exclude _content)
    sources_dir = proj / "sources"
    source_count = 0
    if sources_dir.exists():
        source_count = len([f for f in sources_dir.glob("*.json") if not f.name.endswith("_content.json")])

    # coverage_score 0-1 from latest coverage or coverage tool
    coverage_score = 0.0
    for name in ["coverage_round3.json", "coverage_round2.json", "coverage_round1.json"]:
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

    # steps_taken: phase_history length or conductor_step_count
    phase_history = project.get("phase_history") or []
    steps_taken = len(phase_history)
    conductor_file = proj / "conductor_state.json"
    if conductor_file.exists():
        try:
            cdata = json.loads(conductor_file.read_text())
            steps_taken = int(cdata.get("steps_taken", steps_taken))
        except Exception:
            pass

    return ConductorState(
        findings_count=findings_count,
        source_count=source_count,
        coverage_score=round(coverage_score, 4),
        verified_claims=verified_claims,
        budget_spent_pct=budget_spent_pct,
        steps_taken=min(steps_taken, MAX_STEPS),
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
    system = """You are a research conductor. You decide ONLY the next action for a research pipeline.
State (bounded metrics only):
- findings_count, source_count: evidence gathered
- coverage_score (0-1): topic coverage from coverage tool
- verified_claims: number of verified claims
- budget_spent_pct (0-1): budget used
- steps_taken: steps so far (max 25)

Allowed actions ONLY (reply with exactly one word):
- search_more: need more sources or broader coverage
- read_more: have sources to read, need more content/findings
- verify: have enough evidence, run verification
- synthesize: enough evidence and verification, write report

Reply with exactly one word: search_more, read_more, verify, or synthesize. No explanation."""

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
    """Run a research tool via subprocess. Returns True if exit 0, or (True, stdout_text) if capture_stdout."""
    root = Path(__file__).resolve().parent.parent
    tool_path = root / "tools" / tool
    cmd = [sys.executable, str(tool_path)] + list(args)
    env = os.environ.copy()
    env["OPERATOR_ROOT"] = str(root)
    env["RESEARCH_PROJECT_ID"] = project_id
    try:
        r = subprocess.run(cmd, cwd=cwd or str(root), env=env, timeout=600, capture_output=True, text=True)
        if capture_stdout:
            return r.returncode == 0, (r.stdout or "")
        return r.returncode == 0
    except Exception:
        return (False, "") if capture_stdout else False


def run_cycle(project_id: str) -> bool:
    """
    Phase C: Conductor as master. Loop until synthesize complete or max steps.
    Executes actions via existing Python tools; context manager + supervisor after steps.
    Returns True if cycle completed (synthesize done or done phase).
    """
    root = Path(__file__).resolve().parent.parent
    proj = project_dir(project_id)
    if not proj.exists():
        return False
    project = load_project(proj)
    question = (project.get("question") or "")[:2000]
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
            ok_syn, out_syn = _run_tool(project_id, "research_synthesize.py", project_id, capture_stdout=True)
            if ok_syn and out_syn.strip():
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                (proj / "reports").mkdir(parents=True, exist_ok=True)
                (proj / "reports" / f"report_{ts}.md").write_text(out_syn, encoding="utf-8")
            try:
                from tools.research_critic import critique_report
                project = load_project(proj)
                critique_report(proj, project, None, project_id=project_id)
            except Exception:
                pass
            advance_phase(proj, "done")
            return True

        if action == "verify":
            _run_tool(project_id, "research_verify.py", project_id, "source_reliability")
            _run_tool(project_id, "research_verify.py", project_id, "claim_verification")
            _run_tool(project_id, "research_verify.py", project_id, "fact_check")
            _run_tool(project_id, "research_verify.py", project_id, "claim_ledger")
            gate_ok, gate_out = _run_tool(project_id, "research_quality_gate.py", project_id, capture_stdout=True)
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
            continue

        if action == "read_more":
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
                _run_tool(project_id, "research_parallel_reader.py", project_id, "explore", "--input-file", str(order_file), "--read-limit", "10", "--workers", "8")
            _run_tool(project_id, "research_deep_extract.py")
            try:
                add_compressed_batch(project_id)
                from tools.research_dynamic_outline import merge_evidence_into_outline
                merge_evidence_into_outline(project_id)
                from tools.research_supervisor import run_supervisor
                run_supervisor(project_id)
            except Exception:
                pass
            continue

        if action == "search_more":
            plan_path = proj / "research_plan.json"
            if not plan_path.exists():
                _run_tool(project_id, "research_planner.py", question, project_id)
            plan_path = proj / "research_plan.json"
            if plan_path.exists():
                ok, out = _run_tool(project_id, "research_web_search.py", "--queries-file", str(plan_path), "--max-per-query", "5", capture_stdout=True)
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
    if len(sys.argv) < 3:
        print("Usage: research_conductor.py <shadow|run|run_cycle> <project_id> [phase] [artifacts_dir]", file=sys.stderr)
        sys.exit(2)
    mode = sys.argv[1].lower()
    project_id = sys.argv[2]
    phase = sys.argv[3] if len(sys.argv) > 3 else ""
    art_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    if not project_id or not project_dir(project_id).exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)

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
