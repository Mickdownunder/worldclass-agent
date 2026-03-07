"""Unit tests for tools/research_portfolio_scoring.py — run_portfolio_scoring, main, duplicate/flood penalty."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# project_dir is used from research_common; we need tmp_project with claims/ledger.jsonl
from tools.research_portfolio_scoring import run_portfolio_scoring, main
from tools.research_claim_state_machine import save_ledger_jsonl


def _project_id_from_path(proj_path: Path) -> str:
    return proj_path.name


def test_run_portfolio_scoring_empty_claims(tmp_project):
    """No claims: evidence_density 0, no flood/duplicate penalty, score 1.0."""
    (tmp_project / "claims").mkdir(exist_ok=True)
    save_ledger_jsonl(tmp_project, [])
    project_id = _project_id_from_path(tmp_project)
    with patch("tools.research_portfolio_scoring.project_dir", return_value=tmp_project):
        state = run_portfolio_scoring(project_id)
    assert state["evidence_density"] == 0.0
    assert state["flood_penalty"] == 0
    assert state["duplicate_penalty"] == 0
    assert state["portfolio_score"] == 1.0
    assert state["claims_count"] == 0


def test_run_portfolio_scoring_duplicate_penalty(tmp_project):
    """Two claims same scope and high text overlap: duplicate_penalty > 0."""
    (tmp_project / "claims").mkdir(exist_ok=True)
    scope = {"population": "adults", "geography": "EU", "timeframe": "2020", "domain": "health"}
    claims = [
        {"claim_id": "c1", "claim_scope": scope, "text": "Vitamin D deficiency is common in northern countries", "supporting_source_ids": ["s1"]},
        {"claim_id": "c2", "claim_scope": scope, "text": "Vitamin D deficiency is common in northern regions", "supporting_source_ids": ["s2"]},
    ]
    save_ledger_jsonl(tmp_project, claims)
    project_id = _project_id_from_path(tmp_project)
    with patch("tools.research_portfolio_scoring.project_dir", return_value=tmp_project):
        state = run_portfolio_scoring(project_id)
    assert state["claims_count"] == 2
    assert state["duplicate_penalty"] > 0
    assert state["portfolio_score"] < 1.0


def test_run_portfolio_scoring_flood_penalty(tmp_project):
    """Many sources per claim so evidence_density > 0.8: flood_penalty > 0."""
    (tmp_project / "claims").mkdir(exist_ok=True)
    # 5 claims * 5 sources = 25; density = min(1, 25/25) = 1.0 -> flood = (1-0.8)*0.2 = 0.04
    claims = [
        {"claim_id": f"c{i}", "claim_scope": {}, "text": f"Claim {i}", "supporting_source_ids": [f"s{i}_{j}" for j in range(5)]}
        for i in range(5)
    ]
    save_ledger_jsonl(tmp_project, claims)
    project_id = _project_id_from_path(tmp_project)
    with patch("tools.research_portfolio_scoring.project_dir", return_value=tmp_project):
        state = run_portfolio_scoring(project_id)
    assert state["evidence_density"] >= 0.8
    assert state["flood_penalty"] > 0
    assert state["portfolio_score"] < 1.0


def test_main_wrong_arg_count_exits_2():
    """Fewer than 3 args: main() exits with 2."""
    old_argv = sys.argv
    sys.argv = ["research_portfolio_scoring.py", "run"]
    try:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
    finally:
        sys.argv = old_argv


def test_main_unknown_command_exits_2(tmp_project):
    """Command not 'run': main() exits with 2."""
    project_id = _project_id_from_path(tmp_project)
    old_argv = sys.argv
    sys.argv = ["research_portfolio_scoring.py", "badcmd", project_id]
    try:
        with patch("tools.research_portfolio_scoring.project_dir", return_value=tmp_project):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 2
    finally:
        sys.argv = old_argv


def test_main_project_not_found_exits_1():
    """project.json missing: main() exits with 1."""
    old_argv = sys.argv
    sys.argv = ["research_portfolio_scoring.py", "run", "nonexistent-proj"]
    try:
        with patch("tools.research_portfolio_scoring.project_dir") as pdir:
            from pathlib import Path
            fake_path = Path("/tmp/nonexistent-proj")
            pdir.return_value = fake_path
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
    finally:
        sys.argv = old_argv


def test_main_run_success_prints_state(tmp_project, capsys):
    """main run with valid project: runs scoring, prints JSON state."""
    (tmp_project / "claims").mkdir(exist_ok=True)
    save_ledger_jsonl(tmp_project, [])
    project_id = _project_id_from_path(tmp_project)
    old_argv = sys.argv
    sys.argv = ["research_portfolio_scoring.py", "run", project_id]
    try:
        with patch("tools.research_portfolio_scoring.project_dir", return_value=tmp_project):
            main()
        out = capsys.readouterr()
        state = json.loads(out.out.strip())
        assert "portfolio_score" in state
        assert state["claims_count"] == 0
    finally:
        sys.argv = old_argv
