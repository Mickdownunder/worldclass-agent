"""Unit tests for tools/research_knowledge_seed.py — empty prior_knowledge, no crash when Memory fails."""
import json
import sys
from unittest.mock import patch, MagicMock
import pytest

from tools.research_knowledge_seed import main

# Module uses ROOT = Path(__file__).resolve().parent.parent and proj_dir = ROOT / "research" / project_id.


def test_project_without_findings_writes_empty_prior_knowledge(tmp_project, mock_operator_root):
    """Project exists; Memory returns empty principles/findings: prior_knowledge.json with empty lists."""
    mock_mem = MagicMock()
    mock_mem.retrieve_with_utility.side_effect = lambda q, t, k: []
    mock_mem.record_retrieval.return_value = None
    mock_mem.close.return_value = None
    with patch("lib.memory.Memory", return_value=mock_mem), patch("tools.research_knowledge_seed.ROOT", mock_operator_root), patch("tools.research_knowledge_seed.sys.exit"):
        sys.argv = ["", tmp_project.name]
        main()
    path = tmp_project / "prior_knowledge.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["principles"] == []
    assert data["findings"] == []
    assert data["principle_ids"] == []
    assert data["finding_ids"] == []


def test_no_crash_when_memory_unavailable(tmp_project, mock_operator_root):
    """Memory() raises: exit 0 (non-fatal), no unhandled exception."""
    with patch("lib.memory.Memory", side_effect=RuntimeError("DB unavailable")), patch("tools.research_knowledge_seed.ROOT", mock_operator_root):
        sys.argv = ["", tmp_project.name]
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0
