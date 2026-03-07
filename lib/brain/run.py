"""Brain class and full cycle orchestration."""
import json
import os
import re
from pathlib import Path

from lib.memory import Memory
from lib import plumber as _plumber

from lib.brain.act import act_phase
from lib.brain.decide import decide_phase
from lib.brain.helpers import _load_secrets, _trace_id
from lib.brain.perceive import perceive_phase
from lib.brain.reflect import reflect_phase
from lib.brain.think import think_phase
from lib.brain.understand import understand_phase
from lib.brain.constants import GOVERNANCE_LEVELS


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
        from tools.research_common import llm_call
        result = llm_call(model, system_prompt, user_prompt)
        return (result.text or "").strip()

    def _llm_json(self, system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini") -> dict | list:
        text = self._llm_reason(system_prompt, user_prompt, model)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    def perceive(self) -> dict:
        return perceive_phase(self.memory, self.governance_level)

    def understand(self, state: dict, goal: str = "") -> dict:
        return understand_phase(state, goal, self.memory)

    def think(self, state: dict, goal: str = "Decide the most impactful next action", understanding: dict | None = None) -> dict:
        return think_phase(state, goal, understanding or {}, self.memory, self._llm_json)

    def decide(self, plan: dict, retrieved_memory_ids: dict | None = None) -> dict:
        return decide_phase(plan, self.governance_level, self.memory, retrieved_memory_ids)

    def act(self, decision: dict) -> dict:
        return act_phase(
            decision,
            self.memory,
            self.governance_level,
            _plumber.run_plumber,
            self._llm_json,
        )

    def reflect(self, action_result: dict, goal: str = "", retrieved_principle_ids: list[str] | None = None) -> dict:
        return reflect_phase(
            action_result,
            goal,
            self.memory,
            retrieved_principle_ids or [],
            self._llm_json,
        )

    def run_cycle(self, goal: str = "Decide and execute the most impactful next action") -> dict:
        trace_id = _trace_id()
        self.memory.record_episode("cycle_start", f"Cognitive cycle started: {goal}")

        state = self.perceive()
        understanding = self.understand(state, goal=goal)
        plan = self.think(state, goal, understanding=understanding)
        plan["_trace_id"] = trace_id

        decision = self.decide(plan, retrieved_memory_ids=understanding.get("retrieved_memory_ids"))
        decision["_trace_id"] = trace_id

        action_result = self.act(decision)
        action_result["_trace_id"] = trace_id

        principle_ids = (understanding.get("retrieved_memory_ids") or {}).get("principle_ids") or []
        reflection = self.reflect(action_result, goal, retrieved_principle_ids=principle_ids)

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
            "Cycle complete: %s -> %s (quality: %.2f)" % (cycle_result["decision"], cycle_result["status"], cycle_result["quality"]),
            metadata=cycle_result,
        )
        return cycle_result

    def reflect_on_job(self, job_dir: str, goal: str = "") -> dict:
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
