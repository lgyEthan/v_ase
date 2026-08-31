"""Per-user v_ase preferences stored outside structure and project files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from typing import Any


PREFERENCES_SCHEMA = "v_ase.user_preferences.v1"
MAX_PREFERENCES_BYTES = 8 * 1024 * 1024
_PREFERENCES_FILENAME = "preferences.json"
_preferences_lock = threading.RLock()


def preferences_directory() -> Path:
    """Return the platform-native directory for the current OS user's settings."""
    override = os.environ.get("V_ASE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "v_ase"
    if os.name == "nt":
        root = os.environ.get("APPDATA")
        return (Path(root) if root else Path.home() / "AppData" / "Roaming") / "v_ase"
    root = os.environ.get("XDG_CONFIG_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".config") / "v_ase"


def preferences_path() -> Path:
    return preferences_directory() / _PREFERENCES_FILENAME


def _empty_preferences() -> dict[str, Any]:
    return {"schema": PREFERENCES_SCHEMA}


def _read_preferences() -> dict[str, Any]:
    path = preferences_path()
    try:
        if not path.is_file() or path.stat().st_size > MAX_PREFERENCES_BYTES:
            return _empty_preferences()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return _empty_preferences()
    if not isinstance(value, dict) or value.get("schema") != PREFERENCES_SCHEMA:
        return _empty_preferences()
    return value


def _write_preferences(preferences: dict[str, Any]) -> None:
    payload = json.dumps(
        preferences,
        ensure_ascii=True,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    if len(payload) > MAX_PREFERENCES_BYTES:
        raise ValueError("User preferences are too large to save.")
    directory = preferences_directory()
    directory.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=".preferences-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.chmod(temporary_name, 0o600)
        except OSError:
            pass
        os.replace(temporary_name, preferences_path())
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def load_visual_defaults() -> dict[str, Any] | None:
    """Return a detached visual-default payload, or ``None`` when unset."""
    with _preferences_lock:
        settings = _read_preferences().get("visual_defaults")
        if not isinstance(settings, dict):
            return None
        return json.loads(json.dumps(settings, ensure_ascii=True, allow_nan=False))


def save_visual_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    """Replace the current user's visual defaults and return a detached copy."""
    if not isinstance(settings, dict):
        raise ValueError("Visual defaults must be a JSON object.")
    detached = json.loads(json.dumps(settings, ensure_ascii=True, allow_nan=False))
    with _preferences_lock:
        preferences = _read_preferences()
        preferences["visual_defaults"] = detached
        _write_preferences(preferences)
    return json.loads(json.dumps(detached))


def clear_visual_defaults() -> bool:
    """Delete only saved visual defaults and report whether they existed."""
    with _preferences_lock:
        preferences = _read_preferences()
        existed = isinstance(preferences.pop("visual_defaults", None), dict)
        if len(preferences) == 1 and preferences.get("schema") == PREFERENCES_SCHEMA:
            try:
                preferences_path().unlink()
            except FileNotFoundError:
                pass
            except OSError:
                _write_preferences(preferences)
        else:
            _write_preferences(preferences)
        return existed
