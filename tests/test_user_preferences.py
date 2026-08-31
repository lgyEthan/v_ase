from __future__ import annotations

import asyncio
import json
import os

from ase.build import molecule
import pytest

from v_ase.preferences import (
    MAX_PREFERENCES_BYTES,
    PREFERENCES_SCHEMA,
    clear_visual_defaults,
    load_visual_defaults,
    preferences_path,
    save_visual_defaults,
)
from v_ase.server import (
    delete_user_visual_defaults,
    get_user_visual_defaults,
    set_user_visual_defaults,
)
from v_ase.session import EditorSession, sessions
from v_ase.viewer import view


@pytest.fixture
def isolated_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv("V_ASE_CONFIG_DIR", str(tmp_path / "preferences"))
    return tmp_path / "preferences"


def test_visual_defaults_round_trip_and_clear(isolated_preferences):
    settings = {
        "schema": "v_ase.visual_settings.v3",
        "display": {
            "atomRadiusScale": 0.82,
            "bondStyle": "flat",
            "lightingMode": "rendered",
        },
    }

    assert load_visual_defaults() is None
    saved = save_visual_defaults(settings)
    saved["display"]["atomRadiusScale"] = 99

    assert load_visual_defaults() == settings
    payload = json.loads(preferences_path().read_text(encoding="utf-8"))
    assert payload["schema"] == PREFERENCES_SCHEMA
    assert payload["visual_defaults"] == settings
    if os.name != "nt":
        assert preferences_path().stat().st_mode & 0o077 == 0

    assert clear_visual_defaults() is True
    assert load_visual_defaults() is None
    assert clear_visual_defaults() is False


def test_corrupt_or_oversized_preferences_fall_back_without_raising(isolated_preferences):
    path = preferences_path()
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_visual_defaults() is None

    path.write_bytes(b"x" * (MAX_PREFERENCES_BYTES + 1))
    assert load_visual_defaults() is None


def test_visual_default_endpoint_normalizes_and_removes_legacy_keys(isolated_preferences):
    atoms = molecule("H2O")
    session = EditorSession("preference-api-test", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session
    payload = {
        "settings": {
            "display": {
                "bondMode": "element",
                "elementBondCutoffs": {"H|O": 1.2},
            }
        }
    }

    saved = asyncio.run(set_user_visual_defaults(session.session_id, payload))
    assert saved["configured"] is True
    display = saved["settings"]["display"]
    assert display["bondMode"] == "pairwise"
    assert "elementBondCutoffs" not in display
    assert display["pairwiseBondRanges"]["H|O"] == {
        "enabled": True,
        "min": 0.0,
        "max": 1.2,
    }

    loaded = asyncio.run(get_user_visual_defaults(session.session_id))
    assert loaded == saved
    cleared = asyncio.run(delete_user_visual_defaults(session.session_id))
    assert cleared["configured"] is False
    assert cleared["removed"] is True
    assert asyncio.run(get_user_visual_defaults(session.session_id))["settings"] is None


def test_view_rejects_unknown_interface_theme():
    with pytest.raises(ValueError, match="theme must be"):
        view(molecule("H2"), theme="sepia")
