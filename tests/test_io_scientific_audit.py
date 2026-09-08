"""Scientific values and atom identity must survive fast display I/O."""
from pathlib import Path

import numpy as np
import pytest

from v_ase.io import read_custom_lammps_dump, read_fast_lammps_dump


def write_frames(path: Path, rows, timestep=0):
    blocks = []
    for index, frame in enumerate(rows):
        blocks.append(
            f"ITEM: TIMESTEP\n{timestep + index}\nITEM: NUMBER OF ATOMS\n{len(frame)}\n"
            "ITEM: BOX BOUNDS pp pp pp\n0 10\n0 10\n0 10\n"
            "ITEM: ATOMS id type mol x y z fx fy fz q\n"
            + "\n".join(frame) + "\n"
        )
    path.write_text("".join(blocks))


@pytest.mark.parametrize("base", [2**24, 2**53, 2**63 - 3])
def test_large_integer_ids_track_atoms_exactly_across_reordered_frames(tmp_path, base):
    path = tmp_path / "ids.lammpstrj"
    write_frames(path, [
        [f"{base} 1 {base+1} 1 0 0 0 0 0 0", f"{base+1} 1 {base} 2 0 0 0 0 0 0"],
        [f"{base+1} 1 {base} 3 0 0 0 0 0 0", f"{base} 1 {base+1} 4 0 0 0 0 0 0"],
    ], timestep=2**53 + 17)
    result = read_fast_lammps_dump(path)
    np.testing.assert_array_equal(result.atoms.arrays["lammps_id"], [base, base + 1])
    np.testing.assert_array_equal(result.trajectory.read_positions(1)[:, 0], [4, 3])
    for frame in [result.trajectory.read_atoms(1), read_custom_lammps_dump(path)[1]]:
        np.testing.assert_array_equal(frame.arrays["lammps_id"], [base, base + 1])
        np.testing.assert_array_equal(frame.arrays["mol"], [base + 1, base])
        np.testing.assert_array_equal(frame.positions[:, 0], [4, 3])
        assert frame.info["timestep"] == 2**53 + 18


def test_scientific_materialization_rereads_fp64_while_display_stream_stays_fp32(tmp_path):
    path = tmp_path / "precision.lammpstrj"
    write_frames(path, [["1 1 0 100000000.125 0 0 100000000.25 0 0 0.123456789123456"]])
    original = path.read_bytes()
    result = read_fast_lammps_dump(path)
    preview = result.trajectory.read_positions(0)
    assert preview.dtype == np.float32
    assert preview[0, 0] == 100000000
    for atoms in [result.atoms, result.trajectory.read_atoms(0)]:
        assert atoms.positions[0, 0] == 100000000.125
        assert atoms.arrays["forces"][0, 0] == 100000000.25
        assert atoms.get_initial_charges()[0] == 0.123456789123456
    assert path.read_bytes() == original


@pytest.mark.parametrize("reader", [read_fast_lammps_dump, read_custom_lammps_dump])
@pytest.mark.parametrize("ids", [(3, 3), (0, 1), (-2, 1)])
def test_invalid_identity_never_silently_becomes_a_valid_trajectory(tmp_path, reader, ids):
    path = tmp_path / "invalid.lammpstrj"
    write_frames(path, [[f"{i} 1 0 {j} 0 0 0 0 0 0" for j, i in enumerate(ids)]])
    with pytest.raises(ValueError, match="positive and unique"):
        reader(path)


def test_large_identity_change_is_rejected_even_when_float32_values_coincide(tmp_path):
    path = tmp_path / "changed.lammpstrj"
    base = 2**53
    write_frames(path, [[f"{base} 1 0 1 0 0 0 0 0 0"], [f"{base+1} 1 0 2 0 0 0 0 0 0"]])
    result = read_fast_lammps_dump(path)
    with pytest.raises(ValueError, match="ids changed"):
        result.trajectory.read_positions(1)


def test_virtual_dump_rejects_species_changes_and_safe_reader_preserves_them(tmp_path):
    import asyncio
    from fastapi import HTTPException
    from v_ase.server import get_frame_positions
    from v_ase.session import EditorSession, sessions

    path = tmp_path / "reactive.lammpstrj"
    write_frames(path, [["1 1 0 1 0 0 0 0 0 0"], ["1 8 0 2 0 0 0 0 0 0"]])
    result = read_fast_lammps_dump(path)
    with pytest.raises(ValueError, match="atom types changed.*Edit mode"):
        result.trajectory.read_positions(1)
    with pytest.raises(ValueError, match="atom types changed"):
        result.trajectory.read_atoms(1)
    assert [atoms.get_chemical_symbols() for atoms in read_custom_lammps_dump(path)] == [["H"], ["O"]]
    session = EditorSession("changing-species", result.atoms.copy(), result.atoms.copy(),
                            trajectory_source=result.trajectory)
    sessions[session.session_id] = session
    with pytest.raises(HTTPException, match="atom types changed") as error:
        asyncio.run(get_frame_positions(session.session_id, 1))
    assert error.value.status_code == 400
    assert session.current_frame == 0
    np.testing.assert_array_equal(session.working_atoms.positions, result.atoms.positions)


@pytest.mark.parametrize("changed", ["cell", "origin"])
def test_small_lattice_changes_cannot_use_a_positions_only_cache(changed):
    from ase import Atoms
    from v_ase.server import trajectory_layout_compatible
    from v_ase.session import EditorSession

    first = Atoms("H", cell=[10, 10, 10], pbc=True)
    second = first.copy()
    if changed == "cell":
        second.cell[0, 0] += 1e-6
    else:
        second.set_celldisp([1e-6, 0, 0])
    session = EditorSession("changing-lattice", first.copy(), first.copy(),
                            trajectory_frames=[first, second])
    assert trajectory_layout_compatible(session) is False


@pytest.mark.parametrize("coordinates", ["x y z", "xs ys zs", "xu yu zu", "xsu ysu zsu"])
@pytest.mark.parametrize("general", [False, True])
def test_triclinic_dump_cell_boundary_flags_and_cartesian_origin(tmp_path, coordinates, general):
    # Restricted box bounds enclose all eight corners; they are not cell lengths.
    cell = np.array([[4., 0, 0], [-1.5, 5, 0], [0.75, -0.5, 6]])
    origin = np.array([2., -3., 1.])
    fractional = np.array([[.2, .3, .4], [.8, .6, .1]])
    if general:
        rotation = np.array([[0., 1., 0], [-1., 0, 0], [0, 0, 1]])
        cell = cell @ rotation
        header = "abc origin pp ff pp"
        bounds = "\n".join(" ".join(map(str, [*row, offset])) for row, offset in zip(cell, origin))
    else:
        header = "xy xz yz pp ff pp"
        bounds = ".5 6.75 -1.5\n-3.5 2 .75\n1 7 -.5"
    expected = fractional @ cell + origin
    scaled = coordinates.startswith(("xs ", "xsu "))
    values = fractional if scaled else expected
    path = tmp_path / "skew.lammpstrj"
    path.write_text("ITEM: TIMESTEP\n0\nITEM: NUMBER OF ATOMS\n2\nITEM: BOX BOUNDS "
                    + header + "\n" + bounds + "\nITEM: ATOMS id type " + coordinates + "\n"
                    + "\n".join(f"{i+1} 1 " + " ".join(map(str, row)) for i, row in enumerate(values)) + "\n")
    fast = read_fast_lammps_dump(path)
    for atoms in [fast.atoms, fast.trajectory.read_atoms(0), read_custom_lammps_dump(path)[0]]:
        np.testing.assert_allclose(atoms.cell, cell, atol=1e-12)
        np.testing.assert_array_equal(atoms.pbc, [True, False, True])
        np.testing.assert_allclose(atoms.positions, expected, atol=1e-12)
        np.testing.assert_allclose(atoms.get_celldisp(), origin, atol=1e-12)
    np.testing.assert_allclose(fast.trajectory.read_positions(0), expected, atol=5e-7)
