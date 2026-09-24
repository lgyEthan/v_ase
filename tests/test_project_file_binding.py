import asyncio
import errno
import os
from types import SimpleNamespace

import pytest
from ase import Atoms
from fastapi import HTTPException
from starlette.requests import Request

from v_ase.session import EditorSession
from v_ase.server import load_project, write_current_project
from v_ase.project import write_project_archive
from v_ase.project_files import (
    bind_project_source,
    current_project_binding,
    replace_bound_project,
)


def test_session_bound_project_save_and_conflicts(tmp_path):
    source = tmp_path / "opened.vase"
    source.write_bytes(b"original")
    unrelated = tmp_path / "unrelated.vase"
    unrelated.write_bytes(b"keep")
    session = SimpleNamespace(project_file_binding=None)
    binding = bind_project_source(session, source, "vase")
    assert "path" not in current_project_binding(session)

    with pytest.raises(PermissionError):
        replace_bound_project(session, "wrong", binding["version"], "vase", b"bad")
    assert source.read_bytes() == b"original"

    updated = replace_bound_project(session, binding["id"], binding["version"], "vase", b"saved")
    assert source.read_bytes() == b"saved"
    assert unrelated.read_bytes() == b"keep"
    assert updated["version"] != binding["version"]
    with pytest.raises(FileExistsError):
        replace_bound_project(session, binding["id"], binding["version"], "vase", b"stale")

    source.write_bytes(b"external change")
    with pytest.raises(FileExistsError):
        replace_bound_project(session, binding["id"], updated["version"], "vase", b"overwrite")
    assert source.read_bytes() == b"external change"


def test_bound_project_rejects_symlink_replacement(tmp_path):
    source = tmp_path / "opened.html"
    source.write_bytes(b"original")
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"untouched")
    session = SimpleNamespace(project_file_binding=None)
    binding = bind_project_source(session, source, "html")
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(ValueError):
        replace_bound_project(session, binding["id"], binding["version"], "html", b"bad")
    assert outside.read_bytes() == b"untouched"


def test_bound_project_save_survives_unsupported_directory_fsync(tmp_path, monkeypatch):
    source = tmp_path / 'opened.vase'
    source.write_bytes(b'original')
    session = SimpleNamespace(project_file_binding=None)
    binding = bind_project_source(session, source, 'vase')
    real_open = os.open

    def open_without_directory_fd(path, flags, *args, **kwargs):
        if os.fspath(path) == os.fspath(tmp_path):
            raise OSError(errno.EINVAL, 'directory descriptors unsupported')
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr('v_ase.project_files.os.open', open_without_directory_fd)
    result = replace_bound_project(session, binding['id'], binding['version'], 'vase', b'updated')
    assert source.read_bytes() == b'updated'
    assert result['version'] == current_project_binding(session)['version']


def test_server_project_write_is_bound_and_reports_external_conflict(tmp_path, monkeypatch):
    source = tmp_path / "opened.vase"
    source.write_bytes(b"old")
    atoms = Atoms("H", positions=[[0, 0, 0]])
    session = EditorSession("bound-write", atoms.copy(), atoms.copy(),
                            config={"viz_only": True})
    binding = bind_project_source(session, source, "vase")
    monkeypatch.setattr("v_ase.server.get_session", lambda _id: session)
    payload = {
        "binding_id": binding["id"],
        "expected_version": binding["version"],
        "format": "vase",
        "settings": {"display": {}},
    }
    result = asyncio.run(write_current_project("bound-write", payload))
    assert result["version"] != binding["version"]
    assert source.read_bytes().startswith(b"PK")
    source.write_bytes(b"external")
    with pytest.raises(HTTPException) as error:
        asyncio.run(write_current_project("bound-write", {**payload, "expected_version": result["version"]}))
    assert error.value.status_code == 409
    assert source.read_bytes() == b"external"


def test_uploaded_project_replacement_clears_previous_server_write_authority(tmp_path, monkeypatch):
    original = tmp_path / "original.vase"
    replacement = tmp_path / "replacement.vase"
    first = Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]])
    second = Atoms("He", positions=[[2, 0, 0]])
    session = EditorSession("project-replace", first.copy(), first.copy(),
                            config={"viz_only": True})
    replacement_session = EditorSession("project-replacement", second.copy(), second.copy(),
                                        config={"viz_only": True})
    write_project_archive(original, session, {"display": {}})
    write_project_archive(replacement, replacement_session, {"display": {}})
    bind_project_source(session, original, "vase")
    monkeypatch.setattr("v_ase.server.get_session", lambda _id: session)
    body = replacement.read_bytes()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request({"type": "http", "method": "POST", "path": "/api/project/load/project-replace"},
                      receive=receive)
    result = asyncio.run(load_project("project-replace", request))
    assert session.working_atoms.get_chemical_symbols() == ["He"]
    assert current_project_binding(session) is None
    assert result["metadata"]["project_file_binding"] is None
    assert original.read_bytes().startswith(b"PK")


def test_corrupt_project_upload_preserves_previous_document_and_binding(tmp_path, monkeypatch):
    original = tmp_path / 'original.vase'
    atoms = Atoms('H', positions=[[0, 0, 0]])
    session = EditorSession('corrupt-replace', atoms.copy(), atoms.copy(), config={'viz_only': True})
    write_project_archive(original, session, {'display': {}})
    binding = bind_project_source(session, original, 'vase')
    identity = session.scientific_content_identity()
    monkeypatch.setattr('v_ase.server.get_session', lambda _id: session)

    async def receive():
        return {'type': 'http.request', 'body': b'not a project', 'more_body': False}

    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/project/load/corrupt-replace'},
                      receive=receive)
    with pytest.raises(HTTPException):
        asyncio.run(load_project('corrupt-replace', request))
    assert current_project_binding(session)['id'] == binding['id']
    assert session.scientific_content_identity() == identity
    assert original.read_bytes().startswith(b'PK')


@pytest.mark.parametrize('saved_view', [True, False])
def test_project_mode_is_saved_without_frontend_and_replaces_destination_mode(tmp_path, saved_view):
    from v_ase.project import read_project_archive, replace_session_from_project
    atoms = Atoms('H', positions=[[0, 0, 0]])
    original = EditorSession('original-mode', atoms.copy(), atoms.copy(), config={'viz_only': saved_view})
    destination = EditorSession('destination-mode', atoms.copy(), atoms.copy(), config={'viz_only': not saved_view})
    path = write_project_archive(tmp_path / 'mode.vase', original, {'display': {}})
    loaded = read_project_archive(path)
    assert loaded.settings['documentMode'] == ('view' if saved_view else 'edit')
    replace_session_from_project(destination, loaded)
    assert destination.config['viz_only'] is saved_view
    assert (destination.working_atoms.calc is None) is saved_view


def test_legacy_project_mode_is_typed_and_has_a_deterministic_fallback():
    from v_ase.project import project_viz_only
    assert project_viz_only({'display': {'vizOnly': True}})
    assert not project_viz_only({'display': {'vizOnly': False}})
    assert not project_viz_only({})
    assert not project_viz_only({'documentMode': {}, 'display': {'vizOnly': 'false'}})
