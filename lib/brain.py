"""
Cognitive Core — The Operator's Brain.

Implements the Structured Cognitive Loop (SCL):
  Perceive → Think → Decide → Act → Reflect → Remember

Each phase produces a reasoning trace stored in memory.
The brain uses LLM for reasoning but degrades gracefully without it.

Usage:
  from lib.brain import Brain
  brain = Brain()
  result = brain.run_cycle(goal="Decide what to do next")
  # or individual phases:
  state = brain.perceive()
  plan = brain.think(state, goal="...")
  decision = brain.decide(plan)
"""

import json
import os
import subprocess
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory import Memory
from . import brain_context

BASE = Path.home() / "operator"
CONF = BASE / "conf"
JOBS = BASE / "jobs"
WORKFLOWS = BASE / "workflows"
KNOWLEDGE = BASE / "knowledge"
FACTORY = BASE / "factory"
RESEARCH = BASE / "research"

GOVERNANCE_LEVELS = {
    0: "report_only",
    1: "suggest",
    2: "act_and_report",
    3: "full_autonomous",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trace_id() -> str:
    return hashlib.sha256(f"trace:{time.time_ns()}".encode()).hexdigest()[:12]


def _load_secrets() -> dict[str, str]:
    secrets = {}
    path = CONF / "secrets.env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()
    return secrets


class Brain:
    def __init__(self, governance_level: int = 2):
        self.memory = Memory()
        self.governance_level = min(max(governance_level, 0), 3)
        self._llm_client = None
        self._secrets = _load_secrets()

    @property
    def llm(self):
        if self._llm_client is None:
            from openai import OpenAI
            api_key = self._secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                self._llm_client = OpenAI(api_key=api_key)
            else:
                raise RuntimeError("No OPENAI_API_KEY found in secrets or environment")
        return self._llm_client

    def _llm_reason(self, system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini") -> str:
        import sys as _sys
        _sys.path.insert(0, str(Path.home() / "operator"))
        from tools.research_common import llm_retry

        @llm_retry()
        def _call():
            return self.llm.responses.create(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
            )

        resp = _call()
        return resp.output_text.strip()

    def _llm_json(self, system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini") -> dict | list:
        import re
        text = self._llm_reason(system_prompt, user_prompt, model)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    # ------------------------------------------------------------------
    # Phase 1: PERCEIVE — Gather current state
    # ------------------------------------------------------------------

    def perceive(self) -> dict:
        """Build a comprehensive perception of the current system state."""
        state = {}

        # System health
        try:
            import shutil
            disk = shutil.disk_usage("/")
            state["system"] = {
                "disk_used_pct": round(disk.used / disk.total * 100, 1),
                "load": round(os.getloadavg()[0], 2),
                "time": _utcnow(),
            }
        except Exception:
            state["system"] = {"time": _utcnow()}

        # Recent jobs
        recent_jobs = []
        if JOBS.exists():
            job_files = sorted(JOBS.glob("*/*/job.json"), reverse=True)[:10]
            for f in job_files:
                try:
                    j = json.loads(f.read_text())
                    recent_jobs.append({
                        "id": j.get("id"),
                        "workflow": j.get("workflow_id"),
                        "status": j.get("status"),
                        "duration_s": j.get("duration_s"),
                        "error": j.get("error"),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
        state["recent_jobs"] = recent_jobs

        # Available workflows
        state["workflows"] = sorted([f.stem for f in WORKFLOWS.glob("*.sh")]) if WORKFLOWS.exists() else []

        # Client status
        clients = []
        client_dir = FACTORY / "clients"
        if client_dir.exists():
            for f in client_dir.glob("*.json"):
                try:
                    c = json.loads(f.read_text())
                    clients.append({"id": c["id"], "name": c.get("name"), "topics": c.get("topics", [])})
                except (json.JSONDecodeError, OSError):
                    pass
        state["clients"] = clients

        # Goals
        goals_dir = KNOWLEDGE / "goals"
        if goals_dir.exists():
            for f in goals_dir.glob("*.md"):
                try:
                    state.setdefault("goals", []).append(f.read_text()[:500])
                except OSError:
                    pass

        # Priorities
        prio_path = KNOWLEDGE / "priorities.md"
        if prio_path.exists():
            try:
                state["priorities"] = prio_path.read_text()[:500]
            except OSError:
                pass

        # Research projects (phase, question, status; not done first)
        research_projects = []
        if RESEARCH.exists():
            for proj_dir in sorted(RESEARCH.iterdir(), reverse=True):
                if not proj_dir.is_dir() or not proj_dir.name.startswith("proj-"):
                    continue
                proj_json = proj_dir / "project.json"
                if not proj_json.exists():
                    continue
                try:
                    d = json.loads(proj_json.read_text())
                    research_projects.append({
                        "id": d.get("id", proj_dir.name),
                        "question": (d.get("question", "") or "")[:150],
                        "phase": d.get("phase", "?"),
                        "status": d.get("status", "?"),
                        "last_phase_at": d.get("last_phase_at", d.get("created_at", "")),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
            # Sort: not done first, then by last_phase_at
            def _research_sort(p):
                return (0 if p.get("status") != "done" else 1, p.get("last_phase_at", "") or "")
            research_projects.sort(key=_research_sort)
            state["research_projects"] = research_projects[:25]
        else:
            state["research_projects"] = []

        # Research playbooks (domain, strategy for Think)
        research_playbooks = []
        playbooks_dir = RESEARCH / "playbooks"
        if playbooks_dir.exists():
            for f in sorted(playbooks_dir.glob("*.json")):
                try:
                    d = json.loads(f.read_text())
                    research_playbooks.append({
                        "domain": d.get("domain", d.get("id", f.stem)),
                        "name": d.get("name", ""),
                        "strategy": (d.get("strategy", "") or "")[:400],
                    })
                except (json.JSONDecodeError, OSError):
                    pass
        state["research_playbooks"] = research_playbooks

        # Memory state (only high-quality reflections for planning; low-quality telemetry only)
        state["memory"] = self.memory.state_summary()
        state["memory"]["recent_reflections"] = [
            r for r in state["memory"].get("recent_reflections", [])
            if (r.get("quality") or 0) >= 0.6
        ]
        # Optional query: focus context on current research topic (utility-ranked retrieval)
        goal = ""
        for p in (state.get("research_projects") or []):
            if p.get("status") != "done" and (p.get("question") or "").strip():
                goal = (p.get("question") or "").strip()[:500]
                break
        state["research_context"] = brain_context.compile(self.memory, query=goal or None)

        # Governance level
        state["governance"] = {
            "level": self.governance_level,
            "mode": GOVERNANCE_LEVELS.get(self.governance_level, "unknown"),
        }

        n_research = len(state.get("research_projects", []))
        n_not_done = sum(1 for p in state.get("research_projects", []) if p.get("status") != "done")
        self.memory.record_episode("perceive", f"Perceived system state: {len(recent_jobs)} recent jobs, {len(clients)} clients, {n_research} research projects ({n_not_done} not done)", metadata={"state_keys": list(state.keys())})

        return state

    # ------------------------------------------------------------------
    # Phase 2: THINK — Reason about what to do
    # ------------------------------------------------------------------

    def think(self, state: dict, goal: str = "Decide the most impactful next action") -> dict:
        """Use LLM to reason about current state and generate a plan."""
        trace_id = _trace_id()

        system_prompt = """You are the cognitive core of an autonomous operator system.
You THINK about the current state and a given goal, then produce a structured plan.

Your output MUST be valid JSON with this structure:
{
  "analysis": "2-3 sentence analysis of the current situation",
  "priorities": ["most important thing", "second", "third"],
  "plan": [
    {"action": "workflow_id or description", "reason": "why this action", "urgency": "high|medium|low"}
  ],
  "risks": ["potential risk 1"],
  "confidence": 0.0-1.0
}

Be specific. Reference actual workflows, clients, and data from the state.
If memory shows past failures, account for them.
If playbooks exist for relevant domains, follow their strategies.

Research: If state contains "research_projects" with projects where status != "done" and phase is not "done", consider suggesting "research-cycle" as an action with the project id as reason/context (e.g. action "research-cycle", reason "advance project <project_id>"). Prefer one research-cycle per plan step. Use the workflow id "research-cycle" and the request must be the project id. Research playbooks in state (research_playbooks) describe strategies for different research domains; use them when planning research-related actions.

STRATEGIC PRINCIPLES: If state.research_context contains strategic_principles, treat them as hard-won lessons from past projects:
- GUIDING principles are proven strategies — follow them when applicable.
- CAUTIONARY principles are past failures — actively avoid repeating them.
- Higher metric_score = more validated through repeated success.
Incorporate applicable principles into your plan reasoning."""

        # Extract principles before truncation so they are never cut off
        principles_block = ""
        sp = state.get("research_context", {}).get("strategic_principles", [])
        if sp:
            lines = []
            for p in sp[:10]:
                tag = (p.get("principle_type") or "guiding").upper()
                score = p.get("metric_score", 0.5)
                desc = (p.get("description") or "")[:200]
                lines.append(f"- [{tag}] (score: {score:.2f}) {desc}")
            principles_block = "\n\nSTRATEGIC PRINCIPLES:\n" + "\n".join(lines)

        state_compact = json.dumps(state, indent=2, default=str)
        if len(state_compact) > 12000:
            state_compact = state_compact[:12000] + "\n... (truncated)"

        user_prompt = f"GOAL: {goal}\n\nCURRENT STATE:\n{state_compact}{principles_block}"

        try:
            plan = self._llm_json(system_prompt, user_prompt)
        except Exception as e:
            plan = {
                "analysis": f"LLM reasoning failed: {e}",
                "priorities": ["fix LLM connectivity"],
                "plan": [],
                "risks": ["cannot reason without LLM"],
                "confidence": 0.1,
            }

        self.memory.record_decision(
            phase="think",
            inputs={"goal": goal, "state_keys": list(state.keys())},
            reasoning=plan.get("analysis", ""),
            decision=json.dumps(plan.get("plan", [])[:3]),
            confidence=float(plan.get("confidence", 0.5)),
            trace_id=trace_id,
        )

        plan["_trace_id"] = trace_id
        return plan

    # ------------------------------------------------------------------
    # Phase 3: DECIDE — Select specific action(s) to take
    # ------------------------------------------------------------------

    def decide(self, plan: dict) -> dict:
        """Select the specific action to execute based on the plan and governance level."""
        trace_id = plan.get("_trace_id", _trace_id())
        actions = plan.get("plan", [])

        if not actions:
            decision = {
                "action": "none",
                "reason": "No actions in plan",
                "approved": False,
                "governance_check": GOVERNANCE_LEVELS.get(self.governance_level),
            }
        else:
            top_action = actions[0]
            governance_mode = GOVERNANCE_LEVELS.get(self.governance_level)

            if self.governance_level == 0:
                approved = False
                note = "Report-only mode: action logged but not executed"
            elif self.governance_level == 1:
                approved = False
                note = "Suggest mode: action proposed, awaiting human approval"
            elif self.governance_level == 2:
                approved = True
                note = "Act+Report mode: executing and reporting"
            else:
                approved = True
                note = "Full autonomous mode: executing"

            decision = {
                "action": top_action.get("action", "unknown"),
                "reason": top_action.get("reason", ""),
                "urgency": top_action.get("urgency", "medium"),
                "approved": approved,
                "governance_check": governance_mode,
                "governance_note": note,
                "all_planned": [a.get("action") for a in actions],
            }

        self.memory.record_decision(
            phase="decide",
            inputs={"plan_actions": [a.get("action") for a in actions], "governance_level": self.governance_level},
            reasoning=decision.get("reason", ""),
            decision=decision.get("action", "none"),
            confidence=float(plan.get("confidence", 0.5)),
            trace_id=trace_id,
        )

        decision["_trace_id"] = trace_id
        return decision

    # ------------------------------------------------------------------
    # Phase 4: ACT — Execute the decided action
    # ------------------------------------------------------------------

    def act(self, decision: dict) -> dict:
        """Execute the decided action through the job engine."""
        trace_id = decision.get("_trace_id", _trace_id())
        action = decision.get("action", "none")

        if not decision.get("approved", False):
            result = {
                "executed": False,
                "reason": decision.get("governance_note", "Not approved"),
                "action": action,
            }
            self.memory.record_episode(
                "act_skipped",
                f"Action '{action}' not executed: {result['reason']}",
            )
            result["_trace_id"] = trace_id
            return result

        workflow = action if (WORKFLOWS / f"{action}.sh").exists() else None

        if workflow:
            try:
                op = str(BASE / "bin" / "op")
                reason = (decision.get("reason") or "").strip()
                if workflow == "research-cycle":
                    import re
                    if reason.startswith("proj-"):
                        request = reason
                    else:
                        m = re.search(r"proj-[a-zA-Z0-9_-]+", reason)
                        request = m.group(0) if m else reason or "unknown"
                else:
                    request = f"brain::{reason}"
                job_dir = subprocess.check_output(
                    [op, "job", "new", "--workflow", workflow, "--request", request],
                    text=True,
                ).strip()

                run_result = subprocess.run(
                    [op, "run", job_dir, "--timeout", "180"],
                    capture_output=True,
                    text=True,
                    timeout=200,
                )

                job_id = Path(job_dir).name
                status = run_result.stdout.strip()

                result = {
                    "executed": True,
                    "workflow": workflow,
                    "job_id": job_id,
                    "job_dir": job_dir,
                    "status": status,
                    "exit_code": run_result.returncode,
                }

                self.memory.record_episode(
                    "act",
                    f"Executed workflow '{workflow}' → job {job_id} → {status}",
                    job_id=job_id,
                    workflow_id=workflow,
                )

            except Exception as e:
                result = {
                    "executed": True,
                    "workflow": workflow,
                    "status": "FAILED",
                    "error": str(e),
                }
                self.memory.record_episode(
                    "act_error",
                    f"Workflow '{workflow}' failed: {e}",
                    workflow_id=workflow,
                )
        else:
            result = {
                "executed": False,
                "reason": f"No workflow found for action: {action}",
                "action": action,
            }
            self.memory.record_episode("act_no_workflow", f"No workflow for: {action}")

        result["_trace_id"] = trace_id
        return result

    # ------------------------------------------------------------------
    # Phase 5: REFLECT — Evaluate the outcome
    # ------------------------------------------------------------------

    def reflect(self, action_result: dict, goal: str = "") -> dict:
        """Use LLM to reflect on the action's outcome and extract learnings."""
        trace_id = action_result.get("_trace_id", _trace_id())
        job_id = action_result.get("job_id", "unknown")

        job_context = ""
        if action_result.get("job_dir"):
            log_path = Path(action_result["job_dir"]) / "log.txt"
            if log_path.exists():
                job_context = log_path.read_text()[-2000:]
            artifacts_dir = Path(action_result["job_dir"]) / "artifacts"
            if artifacts_dir.exists():
                art_names = [f.name for f in artifacts_dir.iterdir() if f.is_file()]
                job_context += f"\nArtifacts: {art_names}"

        system_prompt = """You are reflecting on a completed action. Evaluate it honestly.

Output valid JSON:
{
  "outcome_summary": "What happened in 1-2 sentences",
  "went_well": "What worked",
  "went_wrong": "What didn't work (or 'nothing' if all good)",
  "learnings": "Key takeaway for future runs",
  "quality_score": 0.0-1.0,
  "should_retry": false,
  "playbook_update": "Strategy suggestion for this type of task (or null)"
}

Be honest and specific. A failed job with useful error info is more valuable than a vague success."""

        user_prompt = f"GOAL: {goal}\n\nACTION RESULT:\n{json.dumps(action_result, indent=2, default=str)}\n\nJOB LOG (tail):\n{job_context[-3000:]}"

        try:
            reflection = self._llm_json(system_prompt, user_prompt)
        except Exception as e:
            status = action_result.get("status", "unknown")
            exit_code = action_result.get("exit_code", -1)
            job_dir = action_result.get("job_dir", "")
            log_text = ""
            if job_dir:
                log_path = Path(job_dir) / "log.txt"
                if log_path.exists():
                    try:
                        log_text = log_path.read_text()[-500:]
                    except Exception:
                        pass
            if status == "DONE" and exit_code == 0:
                q = 0.75
                outcome = "Job completed successfully"
                went_well = "Execution completed without errors"
                went_wrong = "LLM reflection unavailable — using metrics-based assessment"
            elif status == "FAILED":
                q = 0.25
                outcome = f"Job failed (exit code {exit_code})"
                went_well = "none"
                went_wrong = f"Job failed: {log_text[-200:]}" if log_text else "Unknown failure"
            else:
                q = 0.4
                outcome = f"Job status: {status}"
                went_well = "Partial completion"
                went_wrong = "Unclear outcome"
            reflection = {
                "outcome_summary": outcome,
                "went_well": went_well,
                "went_wrong": went_wrong,
                "learnings": f"Metrics-based reflection (LLM unavailable: {e})",
                "quality_score": q,
                "should_retry": status == "FAILED",
                "playbook_update": None,
            }

        quality = float(reflection.get("quality_score", 0.5))

        self.memory.record_reflection(
            job_id=job_id,
            outcome=reflection.get("outcome_summary", ""),
            quality=quality,
            workflow_id=action_result.get("workflow"),
            goal=goal,
            went_well=reflection.get("went_well"),
            went_wrong=reflection.get("went_wrong"),
            learnings=reflection.get("learnings"),
        )

        self.memory.record_quality(
            job_id=job_id,
            score=quality,
            workflow_id=action_result.get("workflow"),
            notes=reflection.get("learnings", ""),
        )

        if reflection.get("playbook_update"):
            domain = action_result.get("workflow", "general")
            self.memory.upsert_playbook(
                domain=domain,
                strategy=reflection["playbook_update"],
                evidence=[f"job:{job_id}"],
                success_rate=quality,
            )

        self.memory.record_decision(
            phase="reflect",
            inputs={"job_id": job_id, "status": action_result.get("status")},
            reasoning=reflection.get("outcome_summary", ""),
            decision=f"quality={quality:.2f}, retry={reflection.get('should_retry', False)}",
            confidence=quality,
            trace_id=trace_id,
            job_id=job_id,
        )

        reflection["_trace_id"] = trace_id
        return reflection

    # ------------------------------------------------------------------
    # Full Cycle: PERCEIVE → THINK → DECIDE → ACT → REFLECT
    # ------------------------------------------------------------------

    def run_cycle(self, goal: str = "Decide and execute the most impactful next action") -> dict:
        """Run a complete cognitive cycle."""
        trace_id = _trace_id()

        self.memory.record_episode("cycle_start", f"Cognitive cycle started: {goal}")

        state = self.perceive()
        plan = self.think(state, goal)
        plan["_trace_id"] = trace_id

        decision = self.decide(plan)
        decision["_trace_id"] = trace_id

        action_result = self.act(decision)
        action_result["_trace_id"] = trace_id

        reflection = self.reflect(action_result, goal)

        cycle_result = {
            "trace_id": trace_id,
            "goal": goal,
            "governance": GOVERNANCE_LEVELS.get(self.governance_level),
            "plan_summary": plan.get("analysis", ""),
            "decision": decision.get("action", "none"),
            "executed": action_result.get("executed", False),
            "status": action_result.get("status", "not_executed"),
            "quality": float(reflection.get("quality_score", 0.5)),
            "learnings": reflection.get("learnings", ""),
            "should_retry": reflection.get("should_retry", False),
        }

        self.memory.record_episode(
            "cycle_complete",
            f"Cycle complete: {cycle_result['decision']} → {cycle_result['status']} (quality: {cycle_result['quality']:.2f})",
            metadata=cycle_result,
        )

        return cycle_result

    # ------------------------------------------------------------------
    # Standalone Reflection (for existing jobs not run through brain)
    # ------------------------------------------------------------------

    def reflect_on_job(self, job_dir: str, goal: str = "") -> dict:
        """Reflect on a job that was run outside the cognitive loop."""
        job_path = Path(job_dir) / "job.json"
        if not job_path.exists():
            return {"error": f"job.json not found in {job_dir}"}

        job = json.loads(job_path.read_text())
        action_result = {
            "executed": True,
            "workflow": job.get("workflow_id"),
            "job_id": job.get("id"),
            "job_dir": str(job_dir),
            "status": job.get("status"),
            "exit_code": job.get("exit_code"),
        }

        return self.reflect(action_result, goal or job.get("request", ""))

    def close(self):
        self.memory.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
