#!/usr/bin/env python3
"""
Research Supervisor: lightweight anomaly detection after each conductor step.
Checks: source relevance drift, coverage stagnation, budget trajectory, context saturation.
Used by conductor (after each action) when conductor is master; can run in shadow for logging.

Usage:
  research_supervisor.py <project_id>
  Output: JSON list of anomalies { "type": str, "severity": str, "message": str, "suggestion": str }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project
from tools.research_conductor import read_state


def _load_previous_state(proj: Path) -> dict | None:
    """Load previous conductor state for comparison (e.g. coverage/findings last step)."""
    path = proj / "conductor_state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _coverage_stagnation(proj: Path, current_state: Any) -> list[dict]:
    """Detect if reads are not adding coverage (same or lower coverage despite more reads)."""
    anomalies = []
    prev = _load_previous_state(proj)
    if prev is None:
        return anomalies
    prev_cov = prev.get("coverage_score")
    prev_findings = prev.get("findings_count", 0)
    curr_cov = getattr(current_state, "coverage_score", 0)
    curr_findings = getattr(current_state, "findings_count", 0)
    if prev_cov is not None and curr_findings > prev_findings and curr_cov <= (prev_cov or 0):
        anomalies.append({
            "type": "coverage_stagnation",
            "severity": "medium",
            "message": "Findings increased but coverage did not improve",
            "suggestion": "Consider search_more on uncovered topics or read_more on higher-relevance sources",
        })
    return anomalies


def _source_relevance_drift(proj: Path, question: str) -> list[dict]:
    """Heuristic: recent sources with low overlap to question terms may indicate drift."""
    question_terms = set((question or "").lower().split())
    question_terms = {t.strip(".,;:") for t in question_terms if len(t) >= 4}
    if not question_terms:
        return []
    sources_dir = proj / "sources"
    if not sources_dir.exists():
        return []
    low_relevance = 0
    total = 0
    for f in list(sources_dir.glob("*.json"))[-20:]:
        if f.name.endswith("_content.json"):
            continue
        total += 1
        try:
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            text = f"{d.get('title','')} {d.get('description','')}".lower()
            overlap = sum(1 for t in question_terms if t in text)
            if overlap < 2:
                low_relevance += 1
        except Exception:
            pass
    anomalies = []
    if total >= 5 and low_relevance / total >= 0.6:
        anomalies.append({
            "type": "source_relevance_drift",
            "severity": "high",
            "message": "Many recent sources have low overlap with research question",
            "suggestion": "search_more with tighter queries or read_more on higher-ranked sources",
        })
    return anomalies


def _budget_trajectory(state: Any) -> list[dict]:
    """Warn if budget is high and we're not yet at synthesize."""
    anomalies = []
    pct = getattr(state, "budget_spent_pct", 0)
    steps = getattr(state, "steps_taken", 0)
    if pct >= 0.85 and steps < 20:
        anomalies.append({
            "type": "budget_trajectory",
            "severity": "medium",
            "message": f"Budget at {pct:.0%} with {steps} steps",
            "suggestion": "Consider verify then synthesize soon to avoid overrun",
        })
    return anomalies


def _context_saturation(proj: Path) -> list[dict]:
    """Warn if compressed context is very large (too many findings, compress more)."""
    anomalies = []
    ctx_path = proj / "conductor_context.json"
    if not ctx_path.exists():
        return anomalies
    try:
        data = json.loads(ctx_path.read_text(encoding="utf-8", errors="replace"))
        full = data.get("full_compressed", "") or ""
        if len(full) > 8000:
            anomalies.append({
                "type": "context_saturation",
                "severity": "low",
                "message": "Compressed context is large; may degrade next decision quality",
                "suggestion": "Compress more aggressively or summarize older batches",
            })
    except Exception:
        pass
    return anomalies


def run_supervisor(project_id: str) -> list[dict]:
    """Run all anomaly checks. Returns list of anomaly dicts."""
    proj = project_dir(project_id)
    if not proj.exists():
        return []
    project = load_project(proj)
    question = (project.get("question") or "")[:2000]
    state = read_state(project_id)

    anomalies = []
    anomalies.extend(_coverage_stagnation(proj, state))
    anomalies.extend(_source_relevance_drift(proj, question))
    anomalies.extend(_budget_trajectory(state))
    anomalies.extend(_context_saturation(proj))
    return anomalies


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_supervisor.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    anomalies = run_supervisor(project_id)
    print(json.dumps(anomalies, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
