"""Machine-readable discovery helpers for v_ase agent sessions."""

from __future__ import annotations

import json
import sys
import threading
from importlib.resources import files
from typing import IO, Any
from urllib.parse import parse_qs, urljoin, urlsplit


AI_PROTOCOL = "v_ase.ai.v1"
COLLABORATION_PROTOCOL = "v_ase.collaboration.v1"
COLLABORATION_POLL_SECONDS = 1.0
AI_SKILL_RELATIVE_PATH = (
    "skills",
    "visualizing-atomic-structures-with-v-ase",
    "SKILL.md",
)


def ai_skill_path() -> str:
    """Return the installed agent guide path when the package is unpacked."""
    return str(files("v_ase").joinpath(*AI_SKILL_RELATIVE_PATH))


def ai_handshake(url: str) -> dict[str, object]:
    """Describe one live v_ase session without exposing local structure files."""
    parsed = urlsplit(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    query = parse_qs(parsed.query)
    session_id = (query.get("session_id") or [None])[0]
    workspace_id = (query.get("workspace_id") or [None])[0]
    command_url = (
        f"{base_url}/api/ai/command/workspace/{workspace_id}"
        if workspace_id
        else (
            f"{base_url}/api/ai/command/session/{session_id}"
            if session_id
            else None
        )
    )
    return {
        "protocol": AI_PROTOCOL,
        "status": "ready",
        "url": url,
        "human_url": url,
        "session_id": session_id,
        "workspace_id": workspace_id,
        "schema_url": f"{base_url}/api/ai/schema",
        "skill_url": f"{base_url}/api/ai/skill",
        "state_url": (
            f"{base_url}/api/ai/state/{session_id}"
            if session_id
            else None
        ),
        "events_url": (
            f"{base_url}/api/ai/workspace-events/{workspace_id}"
            if workspace_id
            else (
                f"{base_url}/api/ai/events/{session_id}"
                if session_id
                else None
            )
        ),
        "command_url": command_url,
        "command_methods": [
            "ready",
            "schema",
            "describe",
            "capabilities",
            *(
                ["documents", "activate", "newDocument"]
                if workspace_id
                else []
            ),
            "apply",
            "render",
            "export",
        ],
        "event_protocol": COLLABORATION_PROTOCOL,
        "event_delivery": "ndjson-after-handshake",
        "event_scope": "workspace" if workspace_id else "document",
        "browser_api": "window.v_aseAI",
        "command_transport": "http-json-bridge",
        "accepts_natural_language": False,
        "stdin_commands": False,
        "skill_path": ai_skill_path(),
        "note": (
            "This CLI process launches the session, prints this handshake, "
            "and then emits committed changes as NDJSON. An external agent "
            "opens human_url and controls that same live document by POSTing "
            "{\"method\": ..., \"params\": ...} to command_url. v_ase does "
            "not parse natural language or command messages from stdin. "
            "After each event, POST method describe for authoritative live "
            "state. state_url contains backend bootstrap data, not every live "
            "camera or visual setting."
        ),
    }


def stream_collaboration_events(
    handshake: dict[str, Any],
    stop_event: threading.Event,
    *,
    output: IO[str] | None = None,
    error: IO[str] | None = None,
) -> None:
    """Long-poll one session and write compact collaboration events as NDJSON."""
    output = output or sys.stdout
    error = error or sys.stderr
    events_url = handshake.get("events_url")
    state_url = handshake.get("state_url")
    if not events_url:
        return

    import requests

    after_revision = 0
    consecutive_errors = 0
    while not stop_event.is_set():
        try:
            response = requests.get(
                str(events_url),
                params={
                    "after": after_revision,
                    "timeout": COLLABORATION_POLL_SECONDS,
                },
                timeout=COLLABORATION_POLL_SECONDS + 2,
            )
            response.raise_for_status()
            payload = response.json()
            consecutive_errors = 0
            if payload.get("gap"):
                gap_event = {
                    "protocol": COLLABORATION_PROTOCOL,
                    "type": "state.resync-required",
                    "revision": int(payload.get("revision") or after_revision),
                    "source": "system",
                    "categories": ["state"],
                    "changed_paths": [],
                    "session_id": handshake.get("session_id"),
                    "workspace_id": handshake.get("workspace_id"),
                    "event_scope": handshake.get("event_scope"),
                    "summary": (
                        "Older collaboration events expired; POST method "
                        "describe to command_url before continuing."
                    ),
                    "state_url": state_url,
                    "command_url": handshake.get("command_url"),
                }
                print(
                    json.dumps(gap_event, separators=(",", ":")),
                    file=output,
                    flush=True,
                )
            for raw_event in payload.get("events") or []:
                event = dict(raw_event)
                state_path = event.get("state_path")
                event["state_url"] = (
                    urljoin(str(events_url), str(state_path))
                    if state_path
                    else state_url
                )
                print(
                    json.dumps(event, separators=(",", ":")),
                    file=output,
                    flush=True,
                )
                after_revision = max(
                    after_revision,
                    int(event.get("revision") or 0),
                )
            after_revision = max(
                after_revision,
                int(payload.get("revision") or 0),
            )
        except requests.RequestException as exc:
            if stop_event.is_set():
                break
            consecutive_errors += 1
            if consecutive_errors == 1:
                print(
                    f"v_ase collaboration event stream is reconnecting: {exc}",
                    file=error,
                    flush=True,
                )
            stop_event.wait(min(2.0, 0.25 * consecutive_errors))
        except (TypeError, ValueError, KeyError) as exc:
            print(
                f"v_ase ignored an invalid collaboration event response: {exc}",
                file=error,
                flush=True,
            )
            stop_event.wait(0.5)


def start_collaboration_event_stream(
    handshake: dict[str, Any],
    *,
    output: IO[str] | None = None,
    error: IO[str] | None = None,
) -> tuple[threading.Event, threading.Thread]:
    """Start a daemon that emits GUI/agent changes after the CLI handshake."""
    stop_event = threading.Event()
    thread = threading.Thread(
        target=stream_collaboration_events,
        args=(handshake, stop_event),
        kwargs={"output": output, "error": error},
        daemon=True,
        name="v_ase-collaboration-events",
    )
    thread.start()
    return stop_event, thread
