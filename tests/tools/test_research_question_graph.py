"""Unit tests for tools/research_question_graph.py (AEM)."""
import json
import pytest
from tools.research_question_graph import (
    build_question_graph,
    write_question_graph,
    get_question_graph,
    ensure_questions_dir,
)


def test_build_question_graph_empty_question(mock_operator_root, tmp_project):
    (tmp_project / "project.json").write_text(json.dumps({"id": tmp_project.name, "question": "", "phase": "explore"}))
    graph = build_question_graph(tmp_project.name)
    assert graph.get("questions") == []


def test_build_question_graph_has_required_fields(mock_operator_root, tmp_project):
    graph = build_question_graph(tmp_project.name)
    assert "questions" in graph
    assert "version" in graph
    if graph["questions"]:
        q = graph["questions"][0]
        assert "question_id" in q
        assert "text" in q
        assert "state" in q
        assert "uncertainty" in q
        assert "evidence_gap_score" in q
        assert "linked_claims" in q
        assert "last_updated" in q


def test_write_and_get_question_graph(mock_operator_root, tmp_project):
    pid = tmp_project.name
    write_question_graph(pid)
    g = get_question_graph(pid)
    assert (tmp_project / "questions" / "questions.json").exists()
    assert g.get("version") == "v1"
