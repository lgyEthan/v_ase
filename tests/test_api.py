import threading
import time
from inspect import signature

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
from v_ase.viewer import ASEEditor


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
        lambda port: released.set(),
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
