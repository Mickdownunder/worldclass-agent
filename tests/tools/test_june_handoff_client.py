from types import SimpleNamespace

from tools import june_handoff_client as client


def test_submit_research_start_emits_linked_events(monkeypatch):
    events = []
    handoffs = []

    monkeypatch.setattr(client.uuid, "uuid4", lambda: SimpleNamespace(hex="evt1234567890abcdffff"))
    monkeypatch.setattr(
        client,
        "_run_june_handoff",
        lambda args, timeout: handoffs.append((args, timeout)) or {"ok": True, "projectId": "proj-123", "runUntilDone": True},
    )
    monkeypatch.setattr(
        client,
        "emit_event",
        lambda project_id, event_type, payload, event_id=None: events.append(
            {"project_id": project_id, "event": event_type, "payload": payload, "event_id": event_id}
        ) or {"event_id": event_id or "evt-generated"},
    )

    result = client.submit_research_start(
        "Question?",
        source_command="research_council",
        research_mode="discovery",
        run_until_done=True,
        parent_project_id="proj-456",
        hypothesis_to_test="Hypothesis",
    )

    assert result["projectId"] == "proj-123"
    assert handoffs == [([
        "research-start",
        "--question",
        "Question?",
        "--research-mode",
        "discovery",
        "--run-until-done",
        "1",
        "--source-command",
        "research_council",
        "--request-event-id",
        "evt1234567890abc",
        "--parent-project-id",
        "proj-456",
        "--hypothesis-to-test",
        "Hypothesis",
    ], 180)]
    assert events[0]["event"] == "research_start_requested"
    assert events[0]["event_id"] == "evt1234567890abc"
    assert events[0]["payload"]["parent_project_id"] == "proj-456"
    assert events[1]["event"] == "research_continue_dispatched"


def test_submit_research_continue_can_request_single_cycle(monkeypatch):
    events = []
    handoffs = []

    monkeypatch.setattr(client.uuid, "uuid4", lambda: SimpleNamespace(hex="evt2234567890abcdffff"))
    monkeypatch.setattr(
        client,
        "_run_june_handoff",
        lambda args, timeout: handoffs.append((args, timeout)) or {"ok": True, "projectId": "proj-123"},
    )
    monkeypatch.setattr(
        client,
        "emit_event",
        lambda project_id, event_type, payload, event_id=None: events.append(
            {"project_id": project_id, "event": event_type, "payload": payload, "event_id": event_id}
        ) or {"event_id": event_id or "evt-generated"},
    )

    result = client.submit_research_continue("proj-123", source_command="run-research-over-days", max_cycles=1)

    assert result["projectId"] == "proj-123"
    assert handoffs == [([
        "research-continue",
        "--project-id",
        "proj-123",
        "--source-command",
        "run-research-over-days",
        "--request-event-id",
        "evt2234567890abc",
        "--max-cycles",
        "1",
    ], 30)]
    assert events[0]["payload"]["requested_action"] == "continue_one_cycle"
    assert events[0]["payload"]["max_cycles"] == 1
    assert events[1]["event"] == "research_continue_dispatched"
