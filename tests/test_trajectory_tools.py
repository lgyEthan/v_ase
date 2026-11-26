import asyncio
import uuid

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.constraints import FixAtoms
from ase.utils.forcecurve import fit_images

from v_ase.io import atom_labels, set_atom_labels
from v_ase.project import read_project_archive, replace_session_from_project, write_project_archive
from v_ase.server import apply_positions, match_loaded_trajectory, redo, switch_session_mode, undo
from v_ase.session import EditorSession, copy_atoms_with_calc, sessions
from v_ase.trajectory_tools import match_trajectory_indices, trajectory_energy_series


@pytest.fixture
def registered_trajectory():
    created = []

    def register(frames):
        reference = frames[0]
        session = EditorSession(
            str(uuid.uuid4()), copy_atoms_with_calc(reference), copy_atoms_with_calc(reference),
            trajectory_frames=[copy_atoms_with_calc(frame) for frame in frames],
            original_frames=[copy_atoms_with_calc(frame) for frame in frames],
            config={"viz_only": False},
        )
        sessions[session.session_id] = session
        created.append(session.session_id)
        return session

    yield register
    for session in created:
        sessions.pop(session, None)


def test_mic_and_cartesian_matching_preserve_arrays_constraints_and_calculator(registered_trajectory):
    reference = Atoms("CuCuO", positions=[[.3, 0, 0], [4.9, 0, 0], [2, 1, 1]],
                      cell=[10, 7, 8], pbc=[True, False, False])
    moving = Atoms("OCuCu", positions=[[2, 1, 1], [4.7, 0, 0], [9.8, 0, 0]],
                   cell=reference.cell, pbc=reference.pbc)
    set_atom_labels(moving, ["O", "Cu_right", "Cu_left"])
    moving.set_array("serial", np.array([40, 20, 10]))
    moving.set_constraint(FixAtoms(indices=[2]))
    moving.calc = SinglePointCalculator(moving, energy=-5.0, forces=np.arange(9).reshape(3, 3))

    assert atom_labels(match_trajectory_indices([reference, moving], "cartesian")[1]) == [
        "Cu_right", "Cu_left", "O",
    ]
    session = registered_trajectory([reference, moving])
    asyncio.run(match_loaded_trajectory(session.session_id, {}))
    ordered = session.trajectory_frames[1]
    assert atom_labels(ordered) == ["Cu_left", "Cu_right", "O"]
    np.testing.assert_array_equal(ordered.positions, moving.positions[[2, 1, 0]])
    np.testing.assert_array_equal(ordered.arrays["serial"], [10, 20, 40])
    np.testing.assert_array_equal(ordered.constraints[0].get_indices(), [0])
    assert ordered.get_potential_energy() == -5.0
    np.testing.assert_array_equal(ordered.get_forces(apply_constraint=False), moving.calc.results["forces"][[2, 1, 0]])
    asyncio.run(undo(session.session_id))
    assert atom_labels(session.trajectory_frames[1]) == atom_labels(moving)
    asyncio.run(redo(session.session_id))
    assert atom_labels(session.trajectory_frames[1]) == atom_labels(ordered)


def test_soap_translation_matches_wrapped_and_shuffled_positions():
    pytest.importorskip("dscribe")
    reference = Atoms("CuOCuCuO", scaled_positions=[
        [.06, .18, .20], [.24, .13, .20], [.42, .72, .36], [.72, .81, .34], [.89, .40, .38]
    ], cell=[[7, 0, 0], [-1, 7, 0], [0, 0, 14]], pbc=[True, True, False])
    moving = reference.copy()
    moving.translate([3.3, -3.5, 2.0])
    moving.wrap()
    order = [2, 3, 1, 0, 4]
    assert not np.array_equal(
        match_trajectory_indices([reference, moving[order]], "mic")[1].positions, moving.positions,
    )
    result = match_trajectory_indices([reference, moving[order]], "soap-translation")
    np.testing.assert_array_equal(result[1].positions, moving.positions)
    np.testing.assert_array_equal(result[0].positions, reference.positions)


def test_legacy_view_labels_become_editable_frame_labels(tmp_path, registered_trajectory):
    source = registered_trajectory([
        Atoms("Cu2", positions=[[0, 0, 0], [distance, 0, 0]])
        for distance in (1, 1.5)
    ])
    path = tmp_path / "legacy-view.vase"
    write_project_archive(path, source, {
        "documentMode": "view",
        "viewIdentityOverrides": {"scope": "trajectory", "labels": ["Cu_sub", "Cu"]},
    })
    target = registered_trajectory([Atoms("He")])
    replace_session_from_project(target, read_project_archive(path))
    switch_session_mode(target, viz_only=False)
    asyncio.run(apply_positions(target.session_id, {"positions": [[0, .5, 0], [1, 0, 0]]}))
    for frame in target.trajectory_frames:
        assert atom_labels(frame) == ["Cu_sub", "Cu"]
        assert frame.get_chemical_symbols() == ["Cu", "Cu"]


def test_energy_series_uses_cached_results_and_marks_edited_frame_missing():
    frames = []
    for index in range(3):
        frame = Atoms("Cu", positions=[[index, 0, 0]])
        frame.info.update(path_length_A=index / 4, delta_energy_eV=index / 8)
        frame.calc = SinglePointCalculator(frame, energy=-2 + index / 8)
        frames.append(frame)
    frames[1].translate([0, .5, 0])
    assert trajectory_energy_series(frames) == {
        "values": [-2, None, -1.75], "path": [0, .25, .50], "relativeOnly": False,
    }


def test_neb_uses_ase_fit_and_force_tangents_for_the_last_band():
    frames = []
    for index, (x, energy, force) in enumerate(zip(
        (0., .25, .8, 1.4), (-8., -7.9, -7.5, -7.85), (0., -.6, -.15, .35),
    )):
        atoms = Atoms("CuO", positions=[[0, 0, 0], [x + .4, .1, .2]], cell=[8, 8, 8], pbc=True)
        atoms.set_constraint(FixAtoms(indices=[0]))
        atoms.calc = SinglePointCalculator(atoms, energy=energy, forces=[[2 * index, 0, 0], [force, 0, 0]])
        frames.append(atoms)
    expected = fit_images(frames[-3:])
    result = trajectory_energy_series(iter(frames), neb_images=3)
    band = result["neb"]
    assert band["start"] == 1
    np.testing.assert_allclose(band["path"], expected.path)
    np.testing.assert_allclose(band["fitPath"], expected.fit_path)
    np.testing.assert_allclose(band["fitEnergies"], expected.fit_energies)
    for tangent, (xs, ys) in zip(band["tangents"], expected.lines):
        assert tangent["halfWidth"] == pytest.approx((xs[-1] - xs[0]) / 2)
        assert tangent["slope"] == pytest.approx((ys[-1] - ys[0]) / (xs[-1] - xs[0]))
    assert "neb" not in trajectory_energy_series(frames)


def test_neb_reports_missing_saved_forces_without_losing_raw_energy():
    frames = [Atoms("Cu", positions=[[index, 0, 0]]) for index in range(3)]
    frames[0].calc = SinglePointCalculator(frames[0], energy=-4., forces=[[0., 0., 0.]])
    frames[1].calc = SinglePointCalculator(frames[1], energy=-3.)
    frames[2].calc = SinglePointCalculator(frames[2], energy=-3.5, forces=[[0., 0., 0.]])
    result = trajectory_energy_series(frames, neb_images=0)
    assert result["values"] == [-4., -3., -3.5]
    assert "Frame 2 has no valid saved per-atom forces" in result["nebError"]
    assert "neb" not in result


def test_neb_cartesian_fit_uses_stored_coordinates_after_periodic_index_matching():
    frames = []
    for x, energy, force in [(7.75, -4., .2), (0., -3.2, -.3), (.25, -3.6, .1)]:
        atoms = Atoms("CuO", positions=[[3, 0, 0], [x, 0, 0]], cell=[8, 9, 10], pbc=[True, False, False])
        atoms.calc = SinglePointCalculator(atoms, energy=energy, forces=[[0., 0., 0.], [force, 0., 0.]])
        frames.append(atoms)
    shuffled = frames[1][[1, 0]]
    shuffled.calc = SinglePointCalculator(shuffled, energy=frames[1].get_potential_energy(),
                                          forces=frames[1].calc.results["forces"][[1, 0]])
    ordered = match_trajectory_indices([frames[0], shuffled, frames[2]])
    before = [atoms.positions.copy() for atoms in ordered]
    minimum_image = trajectory_energy_series(ordered, neb_images=0)["neb"]
    cartesian = trajectory_energy_series(ordered, neb_images=0, neb_mic=False)["neb"]
    np.testing.assert_allclose(minimum_image["path"], [0, .25, .50])
    np.testing.assert_allclose(minimum_image["fitEnergies"], fit_images(ordered).fit_energies)
    np.testing.assert_allclose(cartesian["path"], [0, 7.75, 8.])
    # ASE uses the raw displacement direction for the force projection in both
    # cases. The tangent spans are measured on the selected path axis.
    assert minimum_image["tangents"][0] == pytest.approx({"slope": .2, "halfWidth": .125})
    assert cartesian["tangents"][0] == pytest.approx({"slope": .2, "halfWidth": 3.875})
    for atoms, positions in zip(ordered, before):
        np.testing.assert_array_equal(atoms.positions, positions)
        assert atoms.pbc.tolist() == [True, False, False]
        assert not atoms.calc.check_state(atoms)
