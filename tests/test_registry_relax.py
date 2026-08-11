"""Physical invariants for rigid in-plane registry relaxation."""

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
        self.target = np.asarray(target, dtype=float)
        self.stiffness = float(stiffness)

    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        displacement = np.mean(
            atoms.positions[self.selected] - self.reference[self.selected],
            axis=0,
        )
        residual = displacement[:2] - self.target
        energy = 0.5 * self.stiffness * float(np.dot(residual, residual))
        forces = np.zeros((len(atoms), 3), dtype=float)
        forces[self.selected, :2] = -self.stiffness * residual / len(self.selected)
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
    assert summary["coordinate_basis"] == "fractional-cell"
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


def test_registry_mode_rejects_non_xy_interfaces_and_whole_structure_selection():
    session, selected = make_registry_session("registry-invalid")
    with np.testing.assert_raises_regex(ValueError, "unselected host"):
        start_registry_relaxation_mode(session, range(len(session.working_atoms)))

    session.working_atoms.cell = [
        [6.0, 0.0, 0.0],
        [0.0, 5.5, 0.0],
        [0.0, 0.0, 12.0],
    ]
    session.working_atoms.pbc = [True, False, True]
    with np.testing.assert_raises_regex(ValueError, "global XY plane"):
        start_registry_relaxation_mode(session, selected)
