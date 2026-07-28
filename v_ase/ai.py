"""Machine-readable discovery helpers for v_ase agent sessions."""

from __future__ import annotations

from importlib.resources import files
from urllib.parse import parse_qs, urlsplit


AI_PROTOCOL = "v_ase.ai.v1"


def ai_skill_path() -> str:
    """Return the installed agent guide path when the package is unpacked."""
    return str(files("v_ase").joinpath("skills_v_ase.md"))


def ai_handshake(url: str) -> dict[str, object]:
    """Describe one live v_ase session without exposing local structure files."""
    parsed = urlsplit(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    query = parse_qs(parsed.query)
    session_id = (query.get("session_id") or [None])[0]
    workspace_id = (query.get("workspace_id") or [None])[0]
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
        "browser_api": "window.v_aseAI",
        "skill_path": ai_skill_path(),
        "note": (
            "Open human_url for the normal GUI. The same live session is used "
            "by both the semantic AI bridge and the human interface."
        ),
    }
