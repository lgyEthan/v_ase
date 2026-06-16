import asyncio
import json

import numpy as np

from v_ase.io import ATOM_TYPE_ARRAY, read_fast_lammps_dump
from v_ase.server import get_frame_positions
from v_ase.session import EditorSession, sessions


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
    assert result.atoms.arrays[ATOM_TYPE_ARRAY].tolist() == ["1", "8"]
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
