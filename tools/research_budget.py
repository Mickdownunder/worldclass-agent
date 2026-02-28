#!/usr/bin/env python3
"""Budget Circuit Breaker: tracks cumulative OpenAI token costs per project.

Prevents runaway spend by checking budget before each pipeline phase.

Usage:
  research_budget.py check <project_id>
    -> {"ok": bool, "current_spend": float, "budget_limit": float}
  research_budget.py track <project_id> <model> <input_tokens> <output_tokens>
    -> {"current_spend": float, "added": float}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, save_project

# Cost per token (USD).  Format: model -> (input_cost_per_token, output_cost_per_token)
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4.1-mini":              (0.40 / 1_000_000,  1.60 / 1_000_000),
    "gpt-4.1":                   (2.00 / 1_000_000,  8.00 / 1_000_000),
    "gpt-4o-mini":               (0.15 / 1_000_000,  0.60 / 1_000_000),
    "gpt-5.2":                   (1.75 / 1_000_000, 14.00 / 1_000_000),
    # Gemini
    "gemini-3.1-pro-preview":    (2.00 / 1_000_000, 12.00 / 1_000_000),
    "gemini-3.1-pro":            (2.00 / 1_000_000, 12.00 / 1_000_000),
    "gemini-2.5-pro":            (1.25 / 1_000_000, 10.00 / 1_000_000),
    "gemini-2.5-flash":          (0.30 / 1_000_000,  2.50 / 1_000_000),
    "gemini-2.0-flash":          (0.10 / 1_000_000,  0.40 / 1_000_000),
}

_FALLBACK_COST: tuple[float, float] = (2.00 / 1_000_000, 12.00 / 1_000_000)

# API costs per call (USD). Semantic Scholar and arXiv are free.
API_COSTS: dict[str, float] = {
    "brave_search": 0.005,   # ~$5/1000 queries
    "serper_search": 0.001,  # ~$1/1000 queries (plan-dependent)
    "jina_reader": 0.002,    # ~$2/1000 reads (free tier: 0)
    "semantic_scholar": 0.0,
    "arxiv": 0.0,
}

DEFAULT_BUDGET_LIMIT = 5.00


def get_budget_limit(project: dict) -> float:
    """Read budget_limit from project config, defaulting to DEFAULT_BUDGET_LIMIT."""
    try:
        return float(project.get("config", {}).get("budget_limit", DEFAULT_BUDGET_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_LIMIT


def track_usage(project_id: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Add token cost to project's current_spend and persist. Returns new current_spend."""
    per_in, per_out = MODEL_COSTS.get(model, _FALLBACK_COST)
    added = per_in * input_tokens + per_out * output_tokens

    proj_path = project_dir(project_id)
    data = load_project(proj_path)
    data["current_spend"] = round(data.get("current_spend", 0.0) + added, 8)
    data.setdefault("spend_breakdown", {})
    llm_key = f"llm_{model}"
    data["spend_breakdown"][llm_key] = round(
        data["spend_breakdown"].get(llm_key, 0.0) + added, 8
    )
    save_project(proj_path, data)
    return data["current_spend"]


def track_api_call(project_id: str, api_name: str, count: int = 1) -> float:
    """Track API cost (web search, reader, etc.) and add to project spend. Returns new current_spend."""
    cost = API_COSTS.get(api_name, 0.0) * count
    if cost <= 0:
        return load_project(project_dir(project_id)).get("current_spend", 0.0)
    proj_path = project_dir(project_id)
    data = load_project(proj_path)
    data["current_spend"] = round(data.get("current_spend", 0.0) + cost, 8)
    data.setdefault("spend_breakdown", {})
    data["spend_breakdown"][api_name] = round(data["spend_breakdown"].get(api_name, 0.0) + cost, 8)
    save_project(proj_path, data)
    return data["current_spend"]


def check_budget(project_id: str) -> dict:
    """Check if project is within budget. Returns {ok, current_spend, budget_limit}."""
    proj_path = project_dir(project_id)
    data = load_project(proj_path)
    current_spend = data.get("current_spend", 0.0)
    limit = get_budget_limit(data)
    return {
        "ok": current_spend < limit,
        "current_spend": round(current_spend, 6),
        "budget_limit": limit,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: research_budget.py <check|track> <project_id> [model input_tokens output_tokens]", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    project_id = sys.argv[2]

    if cmd == "check":
        result = check_budget(project_id)
        print(json.dumps(result, indent=2))
    elif cmd == "track":
        if len(sys.argv) < 6:
            print("Usage: research_budget.py track <project_id> <model> <input_tokens> <output_tokens>", file=sys.stderr)
            sys.exit(2)
        model = sys.argv[3]
        input_tokens = int(sys.argv[4])
        output_tokens = int(sys.argv[5])
        new_spend = track_usage(project_id, model, input_tokens, output_tokens)
        per_in, per_out = MODEL_COSTS.get(model, _FALLBACK_COST)
        added = per_in * input_tokens + per_out * output_tokens
        print(json.dumps({"current_spend": round(new_spend, 6), "added": round(added, 8)}, indent=2))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
