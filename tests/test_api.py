import threading
import time
from inspect import signature
from types import SimpleNamespace

import numpy as np
from ase.build import molecule
from ase.calculators.emt import EMT

from v_ase import view
from v_ase.session import (
    EditorSession,
    create_workspace,
    finalize_workspace,
    sessions,
)
from v_ase.viewer import (
    ASEEditor,
    _LocalServer,
    _local_servers,
    _local_servers_lock,
    open_browser_url,
    release_local_server,
)


def test_view_defaults_to_lightweight_visualization_mode():
    assert signature(view).parameters["viz_only"].default is True


def test_nonblocking_editor_releases_server_when_workspace_finishes(monkeypatch):
    atoms = molecule("H2O")
    session = EditorSession(
        "nonblocking-autoclose",
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    workspace = create_workspace(session)
    released = threading.Event()
    monkeypatch.setattr(
        "v_ase.viewer.release_local_server",
        lambda port, **kwargs: released.set(),
    )
    editor = ASEEditor(
        session.session_id,
        54321,
        workspace_id=workspace.workspace_id,
    )

    finalize_workspace(workspace.workspace_id)

    assert released.wait(timeout=2)
    assert session.session_id not in sessions
    editor.close()


def test_stale_server_lease_cannot_stop_a_reused_port():
    class StoppedThread:
        def is_alive(self):
            return False

        def join(self, timeout=None):
            return None

    port = -1
    stale = _LocalServer(
        server=SimpleNamespace(should_exit=False, force_exit=False),
        thread=StoppedThread(),
    )
    current = _LocalServer(
        server=SimpleNamespace(should_exit=False, force_exit=False),
        thread=StoppedThread(),
    )
    with _local_servers_lock:
        _local_servers[port] = current
    try:
        release_local_server(port, expected_handle=stale)

        assert _local_servers[port] is current
        assert current.owners == 1
        assert current.server.should_exit is False
    finally:
        release_local_server(port, expected_handle=current, force=True)

    assert port not in _local_servers


def test_wsl_browser_launch_uses_windows_interop_without_linux_webbrowser(monkeypatch):
    launched = []
    monkeypatch.setattr("v_ase.viewer._running_under_wsl", lambda: True)
    monkeypatch.setattr(
        "v_ase.viewer.shutil.which",
        lambda command: "/mnt/c/Windows/explorer.exe" if command == "explorer.exe" else None,
    )
    monkeypatch.setattr(
        "v_ase.viewer._spawn_browser_command",
        lambda command: launched.append(command) or True,
    )
    monkeypatch.setattr(
        "v_ase.viewer.webbrowser.open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("gio path used")),
    )

    url = "http://127.0.0.1:58039/workspace?workspace_id=xxxx&session_id=xxxx"
    assert open_browser_url(url) is True
    assert launched == [["/mnt/c/Windows/explorer.exe", url]]


def test_blocking_view_always_prints_url_when_browser_launch_reports_success(
    monkeypatch,
    capsys,
):
    existing_sessions = set(sessions)
    launched = []
    monkeypatch.setattr("v_ase.viewer.acquire_local_server", lambda _app, _port: object())
    monkeypatch.setattr("v_ase.viewer.release_local_server", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "v_ase.viewer.open_browser_url",
        lambda url: launched.append(url) or True,
    )

    def finish_new_session():
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            new_sessions = set(sessions) - existing_sessions
            if new_sessions:
                sessions[next(iter(new_sessions))].done_event.set()
                return
            time.sleep(0.01)
        raise AssertionError("v_ase blocking session was not created")

    thread = threading.Thread(target=finish_new_session)
    thread.start()
    view(molecule("H2"), block=True, port=58039, open_browser=True)
    thread.join(timeout=2.0)

    stderr = capsys.readouterr().err
    assert launched and launched[0].startswith("http://127.0.0.1:58039/workspace?")
    assert launched[0] in stderr
    assert "Ctrl+click or copy into a browser" in stderr


def test_view_returns_committed_structure_without_mutating_input():
    atoms = molecule("H2O")
    atoms0 = atoms.copy()
    existing_sessions = set(sessions)

    def simulate_finalize():
        time.sleep(2)
        for session_id in set(sessions) - existing_sessions:
            session = sessions[session_id]
            new_pos = session.working_atoms.get_positions()
            new_pos[0] += 0.5
            session.working_atoms.set_positions(new_pos)
            session.result_atoms = session.working_atoms.copy()
            session.done_event.set()

    thread = threading.Thread(target=simulate_finalize)
    thread.start()
    edited = view(atoms, block=True)
    thread.join()

    assert edited is not atoms, "Should return a copy, not the original"
    assert not np.allclose(edited.positions, atoms0.positions), "Positions should be changed"
    assert np.allclose(atoms.positions, atoms0.positions), "Original atoms should NOT be mutated"


def test_view_restores_original_structure_for_cancelled_session():
    atoms = molecule("H2O")
    atoms0 = atoms.copy()
    existing_sessions = set(sessions)

    def simulate_cancel():
        time.sleep(1)
        for session_id in set(sessions) - existing_sessions:
            session = sessions[session_id]
            session.cancelled = True
            session.done_event.set()

    thread = threading.Thread(target=simulate_cancel)
    thread.start()
    edited = view(atoms, block=True)
    thread.join()

    assert np.allclose(edited.positions, atoms0.positions), "Should return original positions on cancel"


def test_calculator_preservation():
    """Verify calculator survives structural edits."""
    atoms = molecule("H2O")
    atoms.calc = EMT()

    original = atoms.copy()
    original.calc = atoms.calc
    working = atoms.copy()
    working.calc = atoms.calc

    sess = EditorSession("test", original, working)
    assert sess.working_atoms.calc is not None
    
    from ase import Atom

    new_atoms = sess.working_atoms.copy()
    new_atoms.append(Atom("H", position=[0, 0, 0]))
    sess.preserve_calculator(new_atoms)

    assert sess.working_atoms.calc is not None, "Calculator should be preserved after append"
    assert len(sess.working_atoms) == 4
