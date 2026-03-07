from tools import control_plane_intake as cpi


def test_submit_ui_research_continue_emits_request_and_dispatch(monkeypatch):
    events = []
    handoffs = []

    def fake_emit(project_id, event_type, payload):
        event = {"event_id": f"evt-{len(events) + 1}", "project_id": project_id, "event": event_type, **payload}
        events.append(event)
        return event

    monkeypatch.setattr(cpi, "emit_event", fake_emit)
    monkeypatch.setattr(cpi, "_run_june_handoff", lambda args, timeout: handoffs.append((args, timeout)) or {"ok": True, "projectId": "proj-123"})

    result = cpi.submit_ui_research_continue("proj-123")

    assert result == {
        "ok": True,
        "command": "ui-research-continue",
        "jobId": "proj-123",
        "projectId": "proj-123",
        "requestEventId": "evt-1",
    }
    assert handoffs == [([
        "ui-research-continue",
        "--project-id",
        "proj-123",
        "--request-event-id",
        "evt-1",
    ], 30)]
    assert [event["event"] for event in events] == ["research_continue_requested", "research_continue_dispatched"]
    assert events[-1]["runner"] == "june-control-plane-handoff"


def test_submit_ui_research_start_hands_off_to_june(monkeypatch):
    events = []
    handoffs = []

    def fake_emit(project_id, event_type, payload):
        event = {"event_id": f"evt-{len(events) + 1}", "project_id": project_id, "event": event_type, **payload}
        events.append(event)
        return event

    monkeypatch.setattr(cpi, "emit_event", fake_emit)
    monkeypatch.setattr(
        cpi,
        "_run_june_handoff",
        lambda args, timeout: handoffs.append((args, timeout)) or {"ok": True, "projectId": "proj-123", "runUntilDone": True},
    )

    result = cpi.submit_ui_research_start("Question?", "discovery", True)

    assert result == {
        "ok": True,
        "command": "ui-research-start",
        "jobId": "proj-123",
        "projectId": "proj-123",
        "requestEventId": "evt-1",
        "runUntilDone": True,
    }
    assert handoffs == [([
        "ui-research-start",
        "--question",
        "Question?",
        "--research-mode",
        "discovery",
        "--run-until-done",
        "1",
    ], 180)]
    assert [event["event"] for event in events] == ["research_start_requested", "research_continue_dispatched"]
    assert events[0]["project_id"] == "proj-123"
    assert events[-1]["runner"] == "june-control-plane-handoff"
