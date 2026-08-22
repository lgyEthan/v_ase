"""Physical invariants for rigid planar and Cartesian translation."""

from __future__ import annotations

import time

import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes

from v_ase.registry_relax import (
    _coordinates_for,
    _rigid_translation_derivatives,
    cancel_registry_relaxation_mode,
    finish_registry_relaxation_mode,
    run_registry_relaxation,
    set_registry_translation,
    start_registry_relaxation_mode,
)
from v_ase.session import EditorSession, copy_atoms_with_calc


class RigidTranslationWell(Calculator):
    """Analytic two-dimensional well used to verify the generalized force."""

    implemented_properties = ["energy", "forces"]

    def __init__(self, reference, selected, target=(0.7, -0.45), stiffness=3.0):
        super().__init__()
        self.reference = np.asarray(reference, dtype=float).copy()
        self.selected = np.asarray(selected, dtype=int)
        requested = np.asarray(target, dtype=float)
        self.target = (
            np.asarray([requested[0], requested[1], 0.0], dtype=float)
            if requested.shape == (2,)
            else requested
        )
        self.stiffness = float(stiffness)

    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        displacement = np.mean(
            atoms.positions[self.selected] - self.reference[self.selected],
            axis=0,
        )
        residual = displacement - self.target
        energy = 0.5 * self.stiffness * float(np.dot(residual, residual))
        forces = np.zeros((len(atoms), 3), dtype=float)
        forces[self.selected] = -self.stiffness * residual / len(self.selected)
        self.results = {"energy": energy, "forces": forces}


def make_registry_session(session_id="registry-relax"):
    atoms = Atoms(
        "Cu2O2",
        positions=[
            [1.0, 1.0, 1.0],
            [4.0, 4.0, 1.0],
            [1.4, 1.3, 3.2],
            [3.1, 2.4, 3.2],
        ],
        cell=[[6.0, 0.0, 0.0], [1.2, 5.5, 0.0], [0.0, 0.0, 12.0]],
        pbc=[True, True, False],
    )
    selected = [2, 3]
    atoms.calc = RigidTranslationWell(atoms.positions, selected)
    return EditorSession(session_id, atoms.copy(), atoms), selected


def wait_for_mode(session, timeout=10.0):
    deadline = time.monotonic() + timeout
    while session.registry_relaxation.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not session.registry_relaxation.is_relaxing


def test_registry_relaxation_changes_only_one_common_xy_translation(monkeypatch):
    session, selected = make_registry_session()
    monkeypatch.setattr("v_ase.registry_relax.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    baseline = session.working_atoms.positions.copy()
    baseline_cell = session.working_atoms.cell.array.copy()
    internal = baseline[selected[1]] - baseline[selected[0]]

    summary = start_registry_relaxation_mode(session, selected)
    assert summary["periodic_axes"] == [0, 1]
    assert summary["coordinate_basis"] == "fractional-plane-lattice"
    assert summary["reference_component"] == "unselected-host"
    assert summary["mobile_component"] == "selected-guest"
    run_registry_relaxation(session, {"fmax": 1e-7, "steps": 100})
    wait_for_mode(session)

    final = session.working_atoms.positions.copy()
    np.testing.assert_allclose(final[:2], baseline[:2], atol=0.0)
    np.testing.assert_allclose(final[selected[1]] - final[selected[0]], internal, atol=1e-12)
    np.testing.assert_allclose(final[selected, 2], baseline[selected, 2], atol=1e-12)
    np.testing.assert_allclose(session.working_atoms.cell.array, baseline_cell, atol=0.0)
    np.testing.assert_allclose(
        np.mean(final[selected] - baseline[selected], axis=0),
        [0.7, -0.45, 0.0],
        atol=2e-5,
    )
    coefficients, *_ = np.linalg.lstsq(
        session.registry_relaxation.translation_basis.T,
        np.array([0.7, -0.45, 0.0]),
        rcond=None,
    )
    np.testing.assert_allclose(
        session.registry_relaxation.fractional_translation(),
        np.mod(coefficients, 1.0),
        atol=2e-5,
    )
    assert session.registry_relaxation.projected_force < 1e-6
    assert session.registry_relaxation.generalized_gradient < 1e-5
    assert session.registry_relaxation.summary()["force_units"] == "eV/angstrom"


def test_registry_force_and_fractional_gradient_have_correct_units():
    session, selected = make_registry_session("registry-gradient-units")
    start_registry_relaxation_mode(session, selected)
    mode = session.registry_relaxation
    forces = np.zeros((len(session.working_atoms), 3), dtype=float)
    forces[selected] = [[0.7, -0.4, 0.3], [0.5, 0.2, -0.3]]

    gradient, projected_force = _rigid_translation_derivatives(mode, forces)
    net_force = np.sum(forces[selected], axis=0)
    expected_gradient = -mode.translation_basis @ net_force
    expected_projected = np.linalg.norm(mode.plane_basis @ net_force)

    np.testing.assert_allclose(gradient, expected_gradient, atol=1e-14)
    np.testing.assert_allclose(projected_force, expected_projected, atol=1e-14)
    assert projected_force == np.linalg.norm(net_force[:2])


def test_registry_fractional_gradient_matches_energy_finite_difference():
    session, selected = make_registry_session("registry-gradient-finite-difference")
    start_registry_relaxation_mode(session, selected)
    mode = session.registry_relaxation
    coordinates = np.array([0.037, -0.052], dtype=float)
    atoms = copy_atoms_with_calc(mode.baseline_atoms)

    def energy(values):
        atoms.set_positions(_coordinates_for(mode, values), apply_constraint=False)
        return float(atoms.get_potential_energy())

    atoms.set_positions(_coordinates_for(mode, coordinates), apply_constraint=False)
    forces = np.asarray(atoms.get_forces(apply_constraint=False), dtype=float)
    gradient, _ = _rigid_translation_derivatives(mode, forces)
    epsilon = 1e-6
    finite_difference = np.zeros(2)
    for axis in range(2):
        offset = np.zeros(2)
        offset[axis] = epsilon
        finite_difference[axis] = (
            energy(coordinates + offset) - energy(coordinates - offset)
        ) / (2.0 * epsilon)

    np.testing.assert_allclose(gradient, finite_difference, rtol=1e-7, atol=1e-8)


def test_registry_relaxation_cancel_restores_exact_baseline(monkeypatch):
    session, selected = make_registry_session("registry-cancel")
    monkeypatch.setattr("v_ase.registry_relax.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    baseline = session.working_atoms.positions.copy()
    start_registry_relaxation_mode(session, selected)
    run_registry_relaxation(session, {"fmax": 1e-7, "steps": 100})
    wait_for_mode(session)
    assert not np.array_equal(session.working_atoms.positions, baseline)

    cancel_registry_relaxation_mode(session)
    assert session.registry_relaxation is None
    np.testing.assert_array_equal(session.working_atoms.positions, baseline)
    assert not session.history


def test_registry_relaxation_finish_is_one_undoable_change(monkeypatch):
    session, selected = make_registry_session("registry-finish")
    monkeypatch.setattr("v_ase.registry_relax.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    baseline = session.working_atoms.positions.copy()
    start_registry_relaxation_mode(session, selected)
    run_registry_relaxation(session, {"fmax": 1e-7, "steps": 100})
    wait_for_mode(session)
    final = session.working_atoms.positions.copy()

    result = finish_registry_relaxation_mode(session)
    assert result["status"] == "converged"
    assert session.registry_relaxation is None
    np.testing.assert_allclose(session.working_atoms.positions, final)
    assert len(session.history) == 1

    session.undo()
    np.testing.assert_array_equal(session.working_atoms.positions, baseline)


def test_registry_mode_rejects_incompatible_periodic_planes_and_whole_structure_selection():
    session, selected = make_registry_session("registry-invalid")
    with np.testing.assert_raises_regex(ValueError, "unselected host"):
        start_registry_relaxation_mode(session, range(len(session.working_atoms)))

    session.working_atoms.cell = [
        [6.0, 0.0, 0.0],
        [0.0, 5.5, 0.0],
        [0.0, 0.0, 12.0],
    ]
    session.working_atoms.pbc = [True, False, True]
    with np.testing.assert_raises_regex(ValueError, "does not contain two translations"):
        start_registry_relaxation_mode(session, selected)


def test_registry_relaxation_supports_a_skew_non_axis_aligned_periodic_plane(monkeypatch):
    session, selected = make_registry_session("registry-hkl")
    monkeypatch.setattr("v_ase.registry_relax.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    cell = np.asarray([
        [6.0, 0.4, 0.2],
        [1.2, 5.5, 0.3],
        [0.7, 0.8, 10.0],
    ])
    session.working_atoms.cell = cell
    session.working_atoms.pbc = True
    baseline = session.working_atoms.positions.copy()
    target_coordinates = np.asarray([0.08, -0.035])
    target_translation = target_coordinates @ cell[[1, 2]]
    session.working_atoms.calc = RigidTranslationWell(
        baseline,
        selected,
        target=target_translation,
    )

    summary = start_registry_relaxation_mode(session, selected, hkl=(1, 0, 0))
    assert summary["hkl"] == [1, 0, 0]
    np.testing.assert_array_equal(summary["plane_integer_basis"], [[0, 1, 0], [0, 0, 1]])
    run_registry_relaxation(session, {"fmax": 1e-8, "steps": 100})
    wait_for_mode(session)

    final = session.working_atoms.positions.copy()
    np.testing.assert_allclose(final[:2], baseline[:2], atol=0.0)
    np.testing.assert_allclose(
        final[selected[1]] - final[selected[0]],
        baseline[selected[1]] - baseline[selected[0]],
        atol=1e-12,
    )
    np.testing.assert_allclose(
        np.mean(final[selected] - baseline[selected], axis=0),
        target_translation,
        atol=2e-5,
    )
    np.testing.assert_allclose(
        session.registry_relaxation.current_coordinates,
        target_coordinates,
        atol=2e-5,
    )
    np.testing.assert_allclose(session.working_atoms.cell.array, cell, atol=0.0)


def test_manual_registry_translation_is_exact_reversible_and_preserves_the_cell():
    session, selected = make_registry_session("registry-manual-hkl")
    session.working_atoms.pbc = True
    baseline = session.working_atoms.positions.copy()
    baseline_cell = session.working_atoms.cell.array.copy()
    start_registry_relaxation_mode(session, selected, hkl=(1, 0, 0))
    mode = session.registry_relaxation
    coordinates = np.asarray([0.23, -0.17])

    summary = set_registry_translation(session, coordinates)
    expected = baseline.copy()
    expected[selected] += coordinates @ mode.translation_basis
    np.testing.assert_allclose(session.working_atoms.positions, expected, atol=1e-12)
    np.testing.assert_allclose(summary["translation_coordinates"], coordinates)
    np.testing.assert_allclose(session.working_atoms.cell.array, baseline_cell, atol=0.0)

    set_registry_translation(session, [0.0, 0.0])
    np.testing.assert_allclose(session.working_atoms.positions, baseline, atol=0.0)
    cancel_registry_relaxation_mode(session)
    np.testing.assert_allclose(session.working_atoms.positions, baseline, atol=0.0)
    assert not session.history


def test_cartesian_rigid_translation_optimizes_xyz_without_cell_or_internal_deformation(
    monkeypatch,
):
    session, selected = make_registry_session("registry-cartesian")
    monkeypatch.setattr("v_ase.registry_relax.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    session.working_atoms.cell = np.zeros((3, 3))
    session.working_atoms.pbc = False
    baseline = session.working_atoms.positions.copy()
    target = np.asarray([0.7, -0.45, 0.8])
    session.working_atoms.calc = RigidTranslationWell(
        baseline,
        selected,
        target=target,
    )
    internal = baseline[selected[1]] - baseline[selected[0]]

    summary = start_registry_relaxation_mode(
        session,
        selected,
        translation_space="cartesian",
        max_displacement=2.0,
    )
    assert summary["translation_space"] == "cartesian"
    assert summary["coordinate_basis"] == "cartesian-angstrom"
    assert summary["degrees_of_freedom"] == 3
    assert summary["translation_fractional"] is None
    assert summary["max_displacement_angstrom"] == 2.0
    run_registry_relaxation(session, {"fmax": 1e-7, "steps": 100})
    wait_for_mode(session)

    final = session.working_atoms.positions.copy()
    np.testing.assert_array_equal(final[:2], baseline[:2])
    np.testing.assert_allclose(final[selected[1]] - final[selected[0]], internal, atol=1e-12)
    np.testing.assert_allclose(
        np.mean(final[selected] - baseline[selected], axis=0),
        target,
        atol=2e-5,
    )
    np.testing.assert_array_equal(session.working_atoms.cell.array, np.zeros((3, 3)))
    assert session.registry_relaxation.projected_force < 1e-6


def test_cartesian_rigid_gradient_matches_finite_difference():
    session, selected = make_registry_session("registry-cartesian-gradient")
    start_registry_relaxation_mode(
        session,
        selected,
        translation_space="cartesian",
        max_displacement=3.0,
    )
    mode = session.registry_relaxation
    coordinates = np.asarray([0.11, -0.07, 0.23])
    atoms = copy_atoms_with_calc(mode.baseline_atoms)

    def energy(values):
        atoms.set_positions(_coordinates_for(mode, values), apply_constraint=False)
        return float(atoms.get_potential_energy())

    atoms.set_positions(_coordinates_for(mode, coordinates), apply_constraint=False)
    forces = np.asarray(atoms.get_forces(apply_constraint=False), dtype=float)
    gradient, rigid_force = _rigid_translation_derivatives(mode, forces)
    epsilon = 1e-6
    finite_difference = np.zeros(3)
    for axis in range(3):
        offset = np.zeros(3)
        offset[axis] = epsilon
        finite_difference[axis] = (
            energy(coordinates + offset) - energy(coordinates - offset)
        ) / (2.0 * epsilon)

    np.testing.assert_allclose(gradient, finite_difference, rtol=1e-7, atol=1e-8)
    np.testing.assert_allclose(rigid_force, np.linalg.norm(-gradient), atol=1e-14)


def test_cartesian_rigid_translation_obeys_explicit_per_axis_bound(monkeypatch):
    session, selected = make_registry_session("registry-cartesian-bounds")
    monkeypatch.setattr("v_ase.registry_relax.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    baseline = session.working_atoms.positions.copy()
    session.working_atoms.calc = RigidTranslationWell(
        baseline,
        selected,
        target=(4.0, 0.0, 0.0),
    )
    start_registry_relaxation_mode(
        session,
        selected,
        translation_space="cartesian",
        max_displacement=0.25,
    )
    run_registry_relaxation(session, {"fmax": 1e-9, "steps": 100})
    wait_for_mode(session)

    np.testing.assert_allclose(
        session.registry_relaxation.current_coordinates,
        [0.25, 0.0, 0.0],
        atol=1e-8,
    )
    assert session.registry_relaxation.status == "steps"


def test_manual_cartesian_rigid_translation_is_exact_and_reversible():
    session, selected = make_registry_session("registry-cartesian-manual")
    baseline = session.working_atoms.positions.copy()
    baseline_cell = session.working_atoms.cell.array.copy()
    start_registry_relaxation_mode(
        session,
        selected,
        translation_space="cartesian",
        max_displacement=3.0,
    )
    coordinates = np.asarray([0.4, -0.3, 0.7])

    summary = set_registry_translation(session, coordinates)
    expected = baseline.copy()
    expected[selected] += coordinates
    np.testing.assert_allclose(session.working_atoms.positions, expected, atol=0.0)
    np.testing.assert_allclose(summary["translation_coordinates"], coordinates)
    np.testing.assert_allclose(summary["translation_cartesian"], coordinates)
    np.testing.assert_array_equal(session.working_atoms.cell.array, baseline_cell)

    set_registry_translation(session, [0.0, 0.0, 0.0])
    np.testing.assert_array_equal(session.working_atoms.positions, baseline)
