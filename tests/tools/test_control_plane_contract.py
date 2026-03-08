import pytest

from tools.control_plane_contract import build_control_plane_event, build_intake_response


def test_build_control_plane_event_rejects_missing_owner_for_start_request():
    with pytest.raises(ValueError, match="control_plane_owner"):
        build_control_plane_event(
            project_id="proj-123",
            event_type="research_start_requested",
            payload={
                "source": "ui",
                "authority_scope": "external_ingress",
                "question": "What now?",
                "research_mode": "standard",
                "run_until_done": True,
                "init_job_id": "job-123",
            },
            ts="2026-03-07T00:00:00Z",
            event_id="evt-1",
        )


def test_build_intake_response_rejects_incomplete_success_payload():
    with pytest.raises(ValueError, match="request_event_id"):
        build_intake_response(
            command="ui-research-continue",
            ok=True,
            job_id="proj-123",
            project_id="proj-123",
        )


def test_build_control_plane_event_accepts_optional_handoff_metadata():
    event = build_control_plane_event(
        project_id="proj-123",
        event_type="research_start_requested",
        payload={
            "source": "research_council",
            "authority_scope": "canonical_intake",
            "control_plane_owner": "june",
            "question": "What now?",
            "research_mode": "discovery",
            "run_until_done": True,
            "init_job_id": "delegated_to_june",
            "source_command": "research_council",
            "mission_id": "mis-123",
            "parent_project_id": "proj-456",
            "hypothesis_to_test": "Hypothesis",
        },
        ts="2026-03-08T00:00:00Z",
        event_id="evt-2",
    )

    assert event["source_command"] == "research_council"
    assert event["mission_id"] == "mis-123"
    assert event["parent_project_id"] == "proj-456"
    assert event["hypothesis_to_test"] == "Hypothesis"


def test_build_control_plane_event_accepts_project_initialized_contract():
    event = build_control_plane_event(
        project_id="proj-123",
        event_type="research_project_initialized",
        payload={
            "source": "june-control-plane-handoff",
            "authority_scope": "canonical_intake",
            "control_plane_owner": "june",
            "request_event_id": "evt-2",
            "question": "What now?",
            "research_mode": "discovery",
            "source_command": "mission-executor-prebind",
            "mission_id": "mis-123",
        },
        ts="2026-03-08T00:00:00Z",
        event_id="evt-3",
    )

    assert event["event"] == "research_project_initialized"
    assert event["mission_id"] == "mis-123"
    assert event["request_event_id"] == "evt-2"
