from __future__ import annotations

import asyncio
import io
import json
import threading
from collections import deque

from ase import Atoms

from v_ase.ai import ai_handshake, stream_collaboration_events
from v_ase.server import (
    ai_semantic_state,
    poll_ai_collaboration_events,
    poll_collaboration_source,
    poll_ai_workspace_collaboration_events,
    publish_ai_collaboration_event,
)
from v_ase.session import (
    EditorSession,
    create_workspace,
    create_workspace_session,
    sessions,
    workspaces,
)


def test_session_collaboration_events_are_revisioned_and_compact():
    session = EditorSession("collaboration-session", Atoms("H"), Atoms("H"))
    first = session.publish_collaboration_event({
        "source": "human",
        "categories": ["camera"],
        "changed_paths": ["camera"],
        "summary": "The viewport camera changed.",
        "atom_count": 1,
    })
    second = session.publish_collaboration_event({
        "source": "agent",
        "categories": ["display"],
        "changed_paths": ["display.showBonds"],
        "summary": "Agent changed bond visibility.",
        "atom_count": 1,
    })

    assert first["revision"] == 1
    assert second["revision"] == 2
    payload = session.collaboration_events_after(1, timeout=0)
    assert payload["revision"] == 2
    assert payload["gap"] is False
    assert [event["revision"] for event in payload["events"]] == [2]
    assert "positions" not in payload["events"][0]
    assert payload["events"][0]["state_path"].endswith(
        "/api/ai/state/collaboration-session"
    )


def test_new_listener_is_told_to_resync_when_retained_history_starts_after_one():
    session = EditorSession("collaboration-gap", Atoms("H"), Atoms("H"))
    session.collaboration_events = deque(maxlen=2)
    for revision in range(3):
        session.publish_collaboration_event({
            "source": "human",
            "categories": ["camera"],
            "changed_paths": ["camera"],
            "summary": f"Camera change {revision}.",
        })

    payload = session.collaboration_events_after(0, timeout=0)

    assert payload["revision"] == 3
    assert payload["gap"] is True
    assert [event["revision"] for event in payload["events"]] == [2, 3]


def test_collaboration_endpoints_publish_poll_and_expose_revision():
    session = EditorSession("collaboration-api", Atoms("H2"), Atoms("H2"))
    sessions[session.session_id] = session
    try:
        event = asyncio.run(publish_ai_collaboration_event(
            session.session_id,
            {
                "source": "human",
                "categories": ["selection", "camera"],
                "changedPaths": ["selection.references", "camera"],
                "summary": "Human selected two atoms and changed the camera.",
                "frame": 0,
                "atom_count": 2,
                "selection_count": 2,
            },
        ))
        polled = asyncio.run(poll_ai_collaboration_events(
            session.session_id,
            after=0,
            timeout=0,
        ))
        state = asyncio.run(ai_semantic_state(session.session_id))
    finally:
        sessions.pop(session.session_id, None)

    assert event["protocol"] == "v_ase.collaboration.v1"
    assert event["source"] == "human"
    assert event["categories"] == ["selection", "camera"]
    assert event["changed_paths"] == ["selection.references", "camera"]
    assert polled["events"] == [event]
    assert state["ai"]["collaboration_revision"] == event["revision"]


def test_cli_event_stream_emits_ndjson_with_authoritative_state_url(monkeypatch):
    handshake = ai_handshake(
        "http://127.0.0.1:49152/workspace"
        "?workspace_id=workspace&session_id=session"
    )
    stop = threading.Event()
    stdout = io.StringIO()
    stderr = io.StringIO()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            stop.set()
            return {
                "protocol": "v_ase.collaboration.v1",
                "revision": 3,
                "gap": False,
                "events": [{
                    "protocol": "v_ase.collaboration.v1",
                    "type": "state.changed",
                    "revision": 3,
                    "source": "human",
                    "categories": ["display"],
                    "changed_paths": ["display.labelColors.O"],
                    "summary": "Human changed an atom color.",
                }],
            }

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Response())
    stream_collaboration_events(
        handshake,
        stop,
        output=stdout,
        error=stderr,
    )

    lines = [line for line in stdout.getvalue().splitlines() if line]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["revision"] == 3
    assert event["source"] == "human"
    assert event["state_url"] == handshake["state_url"]
    assert stderr.getvalue() == ""


def test_ai_handshake_advertises_workspace_methods_only_for_workspaces():
    document = ai_handshake(
        "http://127.0.0.1:49152/?session_id=session"
    )
    workspace = ai_handshake(
        "http://127.0.0.1:49152/workspace"
        "?workspace_id=workspace&session_id=session"
    )

    workspace_only = {"documents", "activate", "newDocument"}
    assert workspace_only.isdisjoint(document["command_methods"])
    assert workspace_only.issubset(workspace["command_methods"])
    assert document["event_scope"] == "document"
    assert workspace["event_scope"] == "workspace"


def test_cli_event_stream_marks_workspace_gap_for_full_resynchronization(monkeypatch):
    handshake = ai_handshake(
        "http://127.0.0.1:49152/workspace"
        "?workspace_id=workspace&session_id=session"
    )
    stop = threading.Event()
    stdout = io.StringIO()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            stop.set()
            return {
                "protocol": "v_ase.collaboration.v1",
                "revision": 700,
                "gap": True,
                "events": [],
            }

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Response())
    stream_collaboration_events(handshake, stop, output=stdout)

    event = json.loads(stdout.getvalue())
    assert event["type"] == "state.resync-required"
    assert event["event_scope"] == "workspace"
    assert event["workspace_id"] == "workspace"
    assert event["session_id"] == "session"
    assert event["revision"] == 700


def test_cli_event_stream_stops_without_reconnect_noise(monkeypatch):
    import requests

    handshake = ai_handshake(
        "http://127.0.0.1:49152/workspace"
        "?workspace_id=workspace&session_id=session"
    )
    stop = threading.Event()
    stderr = io.StringIO()

    def interrupted_request(*args, **kwargs):
        stop.set()
        raise requests.ConnectionError("server closed")

    monkeypatch.setattr("requests.get", interrupted_request)
    stream_collaboration_events(handshake, stop, error=stderr)

    assert stderr.getvalue() == ""


def test_async_event_poll_wakes_on_new_revision():
    session = EditorSession("collaboration-wake", Atoms("H"), Atoms("H"))

    async def scenario():
        pending = asyncio.create_task(
            poll_collaboration_source(session, 0, 1.0)
        )
        await asyncio.sleep(0.02)
        session.publish_collaboration_event({
            "source": "human",
            "categories": ["selection"],
            "changed_paths": ["selection.references"],
            "summary": "Selection changed.",
        })
        return await pending

    payload = asyncio.run(scenario())

    assert payload["revision"] == 1
    assert payload["events"][0]["source"] == "human"


def test_workspace_stream_reports_changes_from_new_document_tabs():
    host = EditorSession("collaboration-host", Atoms("H"), Atoms("H"))
    sessions[host.session_id] = host
    workspace = create_workspace(host)
    child = create_workspace_session(workspace)
    try:
        document_event = asyncio.run(publish_ai_collaboration_event(
            child.session_id,
            {
                "source": "human",
                "categories": ["display"],
                "changed_paths": ["display.atomRadiusScale"],
                "summary": "Human changed the child document atom radius.",
                "atom_count": 0,
            },
        ))
        payload = asyncio.run(poll_ai_workspace_collaboration_events(
            workspace.workspace_id,
            after=0,
            timeout=0,
        ))
    finally:
        sessions.pop(child.session_id, None)
        sessions.pop(host.session_id, None)
        workspaces.pop(workspace.workspace_id, None)

    assert document_event["revision"] == 1
    assert payload["revision"] == 1
    assert len(payload["events"]) == 1
    workspace_event = payload["events"][0]
    assert workspace_event["session_id"] == child.session_id
    assert workspace_event["document_revision"] == document_event["revision"]
    assert workspace_event["workspace_id"] == workspace.workspace_id
