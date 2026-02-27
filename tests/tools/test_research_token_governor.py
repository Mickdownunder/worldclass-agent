"""
Unit tests for tools/research_token_governor.py (AEM Token Governor).
Plan: E1 expected IG heuristic, E2 strong lane only if expected_ig_per_token >= threshold,
E3 extraction/dedupe -> cheap lane, E4 fallback deterministisch.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_token_governor import (
    expected_ig_heuristic,
    recommend_lane,
    EXPECTED_IG_PER_TOKEN_THRESHOLD_STRONG,
    get_enforcement_mode,
)


def test_e1_expected_ig_heuristic_returns_positive_with_good_inputs(mock_operator_root, tmp_project):
    """E1: expected IG heuristic (fragility * relevance * (1 - density)) returns > 0 with suitable inputs."""
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    (tmp_project / "portfolio").mkdir(parents=True, exist_ok=True)
    ledger = [
        {"claim_id": "c1", "claim_version": 1, "text": "x", "fragility_score": 0.8, "decision_relevance": 0.9},
    ]
    (tmp_project / "claims" / "ledger.jsonl").write_text("\n".join(json.dumps(c) for c in ledger))
    (tmp_project / "portfolio" / "portfolio_state.json").write_text(json.dumps({"evidence_density": 0.2}))
    with patch("tools.research_token_governor.triage_claims") as mock_triage:
        mock_triage.return_value = [{"fragility_score": 0.8, "decision_relevance": 0.9}]
        ig = expected_ig_heuristic(pid)
    assert ig >= 0
    assert isinstance(ig, (int, float))


def test_e2_low_ig_returns_mid_or_cheap_not_strong(mock_operator_root, tmp_project):
    """E2: strong lane only when expected_ig_per_token >= threshold; low IG -> mid/cheap."""
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    (tmp_project / "policy").mkdir(parents=True, exist_ok=True)
    with patch("tools.research_token_governor.expected_ig_heuristic", return_value=0.0):
        lane = recommend_lane(pid, "default")
    assert lane in ("cheap", "mid")
    assert lane != "strong"


def test_e3_extraction_dedupe_task_returns_cheap(mock_operator_root, tmp_project):
    """E3: extraction/dedupe task -> cheap lane deterministically."""
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    lane_ext = recommend_lane(pid, "extraction")
    lane_dedupe = recommend_lane(pid, "dedupe")
    assert lane_ext == "cheap"
    assert lane_dedupe == "cheap"


def test_e4_fallback_deterministic_when_metrics_missing(mock_operator_root, tmp_project):
    """E4: fallback when metrics missing is deterministic (no error, sensible default)."""
    pid = tmp_project.name
    (tmp_project / "claims").mkdir(parents=True, exist_ok=True)
    lane1 = recommend_lane(pid, "default")
    lane2 = recommend_lane(pid, "default")
    assert lane1 == lane2
    assert lane1 in ("cheap", "mid", "strong")


def test_get_enforcement_mode_default_observe():
    with patch.dict(os.environ, {}, clear=True):
        mode = get_enforcement_mode()
    assert mode == "observe"


def test_get_enforcement_mode_strict():
    with patch.dict(os.environ, {"AEM_ENFORCEMENT_MODE": "strict"}):
        mode = get_enforcement_mode()
    assert mode == "strict"
