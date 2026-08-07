import asyncio
import json

import numpy as np
from ase import Atoms

from v_ase.io import ATOM_LABEL_ARRAY, read_fast_lammps_dump
from v_ase.server import (
    get_frame_positions,
    per_atom_scalar_range,
    per_atom_scalar_values,
    session_atoms_to_json,
    trajectory_layout_compatible,
    trajectory_position_array,
    update_session_mode,
)
from v_ase.session import EditorSession, replace_session_frames, sessions


def write_dump(path):
    path.write_text(
        """ITEM: TIMESTEP
0
ITEM: NUMBER OF ATOMS
2
ITEM: BOX BOUNDS pp pp pp
0 10
0 10
0 10
ITEM: ATOMS id type mol x y z q
2 8 1 4.0 5.0 6.0 -0.5
1 1 1 1.0 2.0 3.0 0.5
ITEM: TIMESTEP
10
ITEM: NUMBER OF ATOMS
2
ITEM: BOX BOUNDS pp pp pp
0 10
0 10
0 10
ITEM: ATOMS id type mol x y z q
1 1 1 1.5 2.5 3.5 0.4
2 8 1 4.5 5.5 6.5 -0.4
""",
        encoding="utf-8",
    )


def test_fast_lammps_dump_preserves_labels_and_virtual_frame_endpoint(tmp_path):
    dump_path = tmp_path / "tiny.lammpstrj"
    write_dump(dump_path)

    result = read_fast_lammps_dump(dump_path, ":")
    assert result.trajectory.frame_count == 2
    assert len(result.atoms) == 2
    assert result.atoms.get_chemical_symbols() == ["H", "O"]
    assert result.atoms.arrays[ATOM_LABEL_ARRAY].tolist() == ["1", "8"]
    np.testing.assert_allclose(result.atoms.positions, [[1, 2, 3], [4, 5, 6]])

    session = EditorSession(
        session_id="fast-lammps-test",
        original_atoms=result.atoms.copy(),
        working_atoms=result.atoms.copy(),
        original_frames=[result.atoms.copy()],
        trajectory_frames=[result.atoms.copy()],
        trajectory_source=result.trajectory,
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    try:
        response = asyncio.run(get_frame_positions(session.session_id, 1))
        assert response.headers["X-V-Ase-Atoms"] == "2"
        assert response.headers["X-V-Ase-Frames"] == "2"
        assert json.loads(response.headers["X-V-Ase-Pbc"]) == [True, True, True]
        values = np.frombuffer(response.body, dtype=np.float32).reshape(2, 3)
        np.testing.assert_allclose(values, [[1.5, 2.5, 3.5], [4.5, 5.5, 6.5]])
        assert session.current_frame == 1
        np.testing.assert_allclose(session.working_atoms.positions, values)
    finally:
        sessions.pop(session.session_id, None)


def test_virtual_lammps_trajectory_exposes_background_binary_cache(tmp_path):
    dump_path = tmp_path / "tiny.lammpstrj"
    write_dump(dump_path)
    result = read_fast_lammps_dump(dump_path, ":")
    session = EditorSession(
        session_id="fast-lammps-cache-test",
        original_atoms=result.atoms.copy(),
        working_atoms=result.atoms.copy(),
        original_frames=[result.atoms.copy()],
        trajectory_frames=[result.atoms.copy()],
        trajectory_source=result.trajectory,
        config={"viz_only": True},
    )

    payload = session_atoms_to_json(session)
    assert "trajectory_positions" not in payload
    assert payload["metadata"]["trajectory_positions_binary"] is True

    values = trajectory_position_array(session)
    assert values.shape == (2, 2, 3)
    assert values.dtype == np.float32
    np.testing.assert_allclose(
        values,
        [
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
            [[1.5, 2.5, 3.5], [4.5, 5.5, 6.5]],
        ],
    )


def test_remote_style_virtual_trajectory_streams_only_requested_frames(tmp_path):
    dump_path = tmp_path / "tiny-streamed.lammpstrj"
    write_dump(dump_path)
    result = read_fast_lammps_dump(dump_path, ":")
    session = EditorSession(
        session_id="fast-lammps-stream-test",
        original_atoms=result.atoms.copy(),
        working_atoms=result.atoms.copy(),
        original_frames=[result.atoms.copy()],
        trajectory_frames=[result.atoms.copy()],
        trajectory_source=result.trajectory,
        config={"viz_only": True, "stream_trajectory": True},
    )
    sessions[session.session_id] = session
    try:
        payload = session_atoms_to_json(session)
        assert payload["metadata"]["trajectory_streaming"] is True
        assert payload["metadata"]["trajectory_positions_binary"] is False
        assert "trajectory_positions" not in payload
        assert trajectory_position_array(session) is None

        response = asyncio.run(get_frame_positions(session.session_id, 1))
        values = np.frombuffer(response.body, dtype=np.float32).reshape(2, 3)
        np.testing.assert_allclose(
            values,
            [[1.5, 2.5, 3.5], [4.5, 5.5, 6.5]],
        )
    finally:
        sessions.pop(session.session_id, None)


def test_virtual_lammps_trajectory_materializes_all_frames_for_edit_mode(tmp_path):
    dump_path = tmp_path / "tiny-mode-switch.lammpstrj"
    write_dump(dump_path)
    result = read_fast_lammps_dump(dump_path, ":")
    session = EditorSession(
        session_id="fast-lammps-mode-switch",
        original_atoms=result.atoms.copy(),
        working_atoms=result.atoms.copy(),
        original_frames=[result.atoms.copy()],
        trajectory_frames=[result.atoms.copy()],
        trajectory_source=result.trajectory,
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    try:
        payload = asyncio.run(update_session_mode(session.session_id, {
            "viz_only": False,
            "labels": ["water_H", "water_O"],
            "chemical_symbols": ["H", "O"],
            "positions": [[1.25, 2.25, 3.25], [4.25, 5.25, 6.25]],
        }))

        assert session.trajectory_source is None
        assert session.frame_count == 2
        assert payload["metadata"]["frame_count"] == 2
        assert payload["symbols"] == ["water_H", "water_O"]
        np.testing.assert_allclose(
            session.trajectory_frames[0].positions,
            [[1.25, 2.25, 3.25], [4.25, 5.25, 6.25]],
        )
        np.testing.assert_allclose(
            session.trajectory_frames[1].positions,
            [[1.5, 2.5, 3.5], [4.5, 5.5, 6.5]],
        )
        assert all(
            frame.arrays[ATOM_LABEL_ARRAY].tolist() == ["water_H", "water_O"]
            for frame in session.trajectory_frames
        )
        assert all(frame.calc is not None for frame in session.trajectory_frames)
    finally:
        sessions.pop(session.session_id, None)


def test_fast_lammps_dump_empty_file_has_clear_error(tmp_path):
    dump_path = tmp_path / "empty.lammpstrj"
    dump_path.write_bytes(b"")

    with np.testing.assert_raises_regex(ValueError, "No frames found"):
        read_fast_lammps_dump(dump_path, ":")


def test_fast_lammps_updates_frame_scalars_for_trajectory_colorscales(tmp_path):
    dump_path = tmp_path / "dynamic-scalars.lammpstrj"
    dump_path.write_text(
        """ITEM: TIMESTEP
0
ITEM: NUMBER OF ATOMS
2
ITEM: BOX BOUNDS pp pp pp
0 5
0 5
0 5
ITEM: ATOMS id type x y z q fx fy fz c_uncertainty
1 1 0 0 0 -0.2 1 0 0 0.1
2 8 1 0 0 0.2 0 1 0 0.2
ITEM: TIMESTEP
1
ITEM: NUMBER OF ATOMS
2
ITEM: BOX BOUNDS pp pp pp
0 5
0 5
0 5
ITEM: ATOMS id type x y z q fx fy fz c_uncertainty
1 1 0.1 0 0 -0.8 2 0 0 1.1
2 8 1.1 0 0 0.8 0 3 0 1.2
""",
        encoding="utf-8",
    )

    result = read_fast_lammps_dump(dump_path, ":")
    frame = result.trajectory.read_atoms(1)

    np.testing.assert_allclose(frame.get_initial_charges(), [-0.8, 0.8])
    np.testing.assert_allclose(frame.arrays["forces"], [[2, 0, 0], [0, 3, 0]])
    np.testing.assert_allclose(frame.arrays["c_uncertainty"], [1.1, 1.2])
    np.testing.assert_array_equal(frame.arrays["lammps_type"], [1, 8])

    np.testing.assert_allclose(
        result.trajectory.read_scalar_values(1, "force:norm"),
        [2.0, 3.0],
    )
    np.testing.assert_allclose(
        result.trajectory.read_scalar_values(
            1,
            "array::c_uncertainty::scalar",
        ),
        [1.1, 1.2],
    )

    session = EditorSession(
        session_id="fast-lammps-scalar-range",
        original_atoms=result.atoms.copy(),
        working_atoms=result.atoms.copy(),
        original_frames=[result.atoms.copy()],
        trajectory_frames=[result.atoms.copy()],
        trajectory_source=result.trajectory,
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    original_read_atoms = result.trajectory.read_atoms
    result.trajectory.read_atoms = lambda _index: (_ for _ in ()).throw(
        AssertionError("fast scalar scans must not materialize ASE Atoms")
    )
    try:
        scalar_range = asyncio.run(per_atom_scalar_range(
            session.session_id,
            {
                "field_id": "array::c_uncertainty::scalar",
                "frame_index": 0,
                "all_frames": True,
            },
        ))
        assert np.isclose(scalar_range["minimum"], 0.1)
        assert np.isclose(scalar_range["maximum"], 1.2)
        response = asyncio.run(per_atom_scalar_values(
            session.session_id,
            {
                "field_id": "array::c_uncertainty::scalar",
                "frame_index": 0,
                "all_frames": True,
            },
        ))
        np.testing.assert_allclose(
            np.frombuffer(response.body, dtype=np.float32).reshape(2, 2),
            [[0.1, 0.2], [1.1, 1.2]],
        )
    finally:
        result.trajectory.read_atoms = original_read_atoms
        sessions.pop(session.session_id, None)


def test_trajectory_layout_cache_is_invalidated_explicitly():
    first = Atoms("HO", positions=[[0, 0, 0], [1, 0, 0]], cell=[5, 5, 5], pbc=True)
    second = first.copy()
    session = EditorSession(
        "layout-cache-test",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        config={"viz_only": True},
    )

    assert trajectory_layout_compatible(session) is True
    assert session._trajectory_layout_compatible is True

    changed = second.copy()
    changed.set_cell([6, 5, 5])
    replace_session_frames(session, [first, changed])
    assert session._trajectory_layout_compatible is None
    assert trajectory_layout_compatible(session) is False
