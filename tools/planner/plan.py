"""Build research plan via LLM and optional Memory v2 strategy overlay."""
import json
import sys
from pathlib import Path
from typing import Any

from tools.research_common import llm_call, research_root
from tools.planner.constants import PLANNER_MODEL
from tools.planner.helpers import json_only
from tools.planner.sanitize import sanitize_plan
from tools.planner.fallback import fallback_plan
from tools.planner.prior import load_prior_knowledge_and_questions, research_mode_for_project
from tools.planner import memory as planner_memory


def load_project_plan(project_id: str) -> dict[str, Any]:
    plan_path = research_root() / project_id / "research_plan.json"
    if not plan_path.exists():
        return {"topics": [], "entities": [], "perspectives": []}
    try:
        return json.loads(plan_path.read_text())
    except Exception:
        return {"topics": [], "entities": [], "perspectives": []}


def build_plan(question: str, project_id: str) -> dict[str, Any]:
    research_mode = research_mode_for_project(project_id)
    prior_snippet, questions_snippet, _ = load_prior_knowledge_and_questions(project_id)

    if research_mode == "discovery":
        system = """You are a research strategist for DISCOVERY mode: breadth over depth, novel connections, hypothesis generation.
Goal: Maximize diversity of sources, perspectives, and adjacent fields. We are NOT trying to verify one answer — we are exploring what is unknown, where evidence is missing, and what competing hypotheses exist."""
        user = f"""
QUESTION: {question}{prior_snippet}{questions_snippet}

Create a DISCOVERY research plan (broad, hypothesis-seeking). Return JSON with keys:
1) topics: [{{id,name,priority,description,source_types,min_sources}}] — include adjacent fields and "where evidence is missing"
2) entities: [specific systems, papers, people, approaches]
3) perspectives: [5-8 diverse perspectives, e.g. clinical researcher, skeptic, industry, policy, adjacent domain]
4) queries: [{{query,topic_id,type,perspective}}]
   - 20-40 queries (more than standard)
   - English
   - max 12 words each
   - Include: competing hypotheses, emerging approaches, gaps, "what we don't know", adjacent fields
   - type: "web" | "academic" | "medical" — use "academic"/"medical" for papers and trials where relevant
   - Every entity and topic from multiple angles (supporting, critical, alternative)
5) complexity: prefer "moderate" or "complex" for discovery
6) estimated_sources_needed: integer (e.g. 30-60 for breadth)

Return ONLY JSON."""
    else:
        system = "You are a senior research strategist planning a comprehensive investigation."
        user = f"""
QUESTION: {question}{prior_snippet}{questions_snippet}

Create a research plan. Return JSON with keys:
1) topics: [{{id,name,priority,description,source_types,min_sources}}]
2) entities: [specific systems/papers/people]
3) perspectives: [3-6 perspectives]
4) queries: [{{query,topic_id,type,perspective}}]
   - 15-30 queries
   - English
   - max 10 words each
   - every entity gets at least one dedicated query
   - each topic gets queries from multiple perspectives
   - type: "web" | "academic" | "medical"
   - Use "medical" for health/biomedical/clinical queries (searches PubMed)
   - Use "academic" for scientific/technical papers (Semantic Scholar + ArXiv)
   - Use "web" for general information
5) complexity: simple|moderate|complex
6) estimated_sources_needed: integer

Return ONLY JSON.
""".strip()

    try:
        resp = llm_call(PLANNER_MODEL, system, user, project_id=project_id)
        base = sanitize_plan(json_only(resp.text), question)
        print(f"PLANNER: LLM plan generated ({len(base.get('queries', []))} queries, {len(base.get('topics', []))} topics){' [discovery]' if research_mode == 'discovery' else ''}", file=sys.stderr)
    except Exception as exc:
        print(f"PLANNER: LLM call failed ({type(exc).__name__}: {exc}), using fallback", file=sys.stderr)
        base = fallback_plan(question)
    strategy_ctx = planner_memory.load_strategy_context(question, project_id)
    plan = planner_memory.apply_strategy_to_plan(base, strategy_ctx)
    planner_memory.persist_strategy_context(project_id, strategy_ctx)
    return plan
