"""Physical edits must preserve untouched frames and undo the full chosen scope."""
import asyncio
import uuid

import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms, FixedPlane
from fastapi import HTTPException

from v_ase.io import atom_labels, set_atom_labels
from v_ase.server import apply_translation, delete_atoms, undo, redo
from v_ase.session import EditorSession, sessions


@pytest.fixture
def trajectory():
    frames = []
    for symbols, scale in [('HOC', 1), ('LiNaF', 2), ('He', 3)]:
        atoms = Atoms(symbols, positions=[[i, scale, 0] for i in range(len(Atoms(symbols)))],
                      cell=np.array([[4, 0, 0], [-1, 5, 0], [0, -1, 6]]) * scale, pbc=True)
        atoms.set_array('existence', np.arange(len(atoms), dtype=float) + .2)
        set_atom_labels(atoms, [f'{s}_2' for s in atoms.get_chemical_symbols()])
        atoms.set_constraint([FixAtoms(indices=[0])] + ([FixedPlane(2, [0, 0, 1])] if len(atoms) > 2 else []))
        frames.append(atoms)
    session = EditorSession(str(uuid.uuid4()), frames[0].copy(), frames[0].copy(),
                            trajectory_frames=[a.copy() for a in frames],
                            original_frames=[a.copy() for a in frames], config={'viz_only': False})
    sessions[session.session_id] = session
    yield session, frames
    sessions.pop(session.session_id, None)


@pytest.mark.parametrize('scope', ['current', 'all'])
def test_delete_scope_constraints_arrays_and_complete_undo(trajectory, scope):
    session, original = trajectory
    asyncio.run(delete_atoms(session.session_id, {'indices': [1, 2], 'frame_scope': scope}))
    assert [len(a) for a in session.trajectory_frames] == ([1, 1, 1] if scope == 'all' else [1, 3, 1])
    assert atom_labels(session.trajectory_frames[0]) == ['H_2']
    assert session.trajectory_frames[0].arrays['existence'].tolist() == [.2]
    if scope == 'all':
        assert atom_labels(session.trajectory_frames[1]) == ['Li_2']
        assert len(session.trajectory_frames[1].constraints) == 1
    for i, frame in enumerate(session.trajectory_frames):
        assert np.array_equal(frame.cell, original[i].cell)
    assert len(session.history) == 1
    asyncio.run(undo(session.session_id))
    for actual, expected in zip(session.trajectory_frames, original):
        assert atom_labels(actual) == atom_labels(expected)
        assert np.array_equal(actual.positions, expected.positions)
        assert np.array_equal(actual.arrays['existence'], expected.arrays['existence'])
        assert [c.todict() for c in actual.constraints] == [c.todict() for c in expected.constraints]
    asyncio.run(redo(session.session_id))
    assert [len(a) for a in session.trajectory_frames] == ([1, 1, 1] if scope == 'all' else [1, 3, 1])


@pytest.mark.parametrize('scope', ['current', 'all'])
@pytest.mark.parametrize('mode', ['cartesian', 'fractional'])
def test_rigid_translation_uses_each_cell_without_relaxation(trajectory, scope, mode):
    session, original = trajectory
    vector = np.array([.2, -.1, .3])
    asyncio.run(apply_translation(session.session_id, {
        'vector': vector.tolist(), 'coordinate_mode': mode,
        'indices': [0, 2], 'frame_scope': scope,
    }))
    for number, (actual, before) in enumerate(zip(session.trajectory_frames, original)):
        expected = before.positions.copy()
        if number == 0 or scope == 'all':
            shift = vector @ before.cell.array if mode == 'fractional' else vector
            expected[[i for i in [0, 2] if i < len(before)]] += shift
        assert np.allclose(actual.positions, expected)
        assert np.array_equal(actual.cell, before.cell)
        assert [c.todict() for c in actual.constraints] == [c.todict() for c in before.constraints]
    assert not session.is_relaxing and not session.registry_relaxation
    asyncio.run(undo(session.session_id))
    assert all(np.array_equal(a.positions, b.positions) for a, b in zip(session.trajectory_frames, original))
    asyncio.run(redo(session.session_id))
    assert not np.array_equal(session.working_atoms.positions, original[0].positions)


def test_translation_failure_in_later_frame_is_atomic(trajectory):
    session, original = trajectory
    session.trajectory_frames[1].set_cell([0, 0, 0])
    with pytest.raises(HTTPException):
        asyncio.run(apply_translation(session.session_id, {
            'vector': [.2, 0, 0], 'coordinate_mode': 'fractional', 'frame_scope': 'all'}))
    assert not session.history
    assert np.array_equal(session.working_atoms.positions, original[0].positions)
    assert np.array_equal(session.trajectory_frames[0].positions, original[0].positions)


@pytest.mark.parametrize('indices', [[-1], [99], [1.5], [True]])
def test_invalid_delete_is_not_an_undo_action(trajectory, indices):
    session, original = trajectory
    with pytest.raises(HTTPException):
        asyncio.run(delete_atoms(session.session_id, {'indices': indices, 'frame_scope': 'all'}))
    assert not session.history and len(session.working_atoms) == len(original[0])


@pytest.mark.parametrize('scope', [[], {}, True, 'selected'])
def test_invalid_edit_scope_is_reported_without_mutation(trajectory, scope):
    session, original = trajectory
    for operation, payload in [(delete_atoms, {'indices': [0]}),
                               (apply_translation, {'vector': [1, 0, 0]})]:
        with pytest.raises(HTTPException) as error:
            asyncio.run(operation(session.session_id, {**payload, 'frame_scope': scope}))
        assert error.value.status_code == 400
    assert not session.history
    assert np.array_equal(session.working_atoms.positions, original[0].positions)


def test_delete_every_atom_can_leave_empty_frames_and_undo(trajectory):
    session, original = trajectory
    asyncio.run(delete_atoms(session.session_id, {'indices': [0, 1, 2], 'frame_scope': 'all'}))
    assert [len(a) for a in session.trajectory_frames] == [0, 0, 0]
    asyncio.run(undo(session.session_id))
    assert [len(a) for a in session.trajectory_frames] == [3, 3, 1]
