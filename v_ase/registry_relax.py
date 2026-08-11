"""Rigid two-degree-of-freedom registry relaxation sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import traceback
import uuid
from typing import Any, Sequence

import numpy as np
from scipy.optimize import minimize

from .commensurate import project_periodic_lattice
from .repulsion import ensure_default_calculator
from .session import copy_atoms_with_calc
from .websocket_manager import ws_manager


_STOP_SIGNAL = "REGISTRY_RELAXATION_STOPPED"


@dataclass
class RegistryRelaxationSession:
    session_id: str
    baseline_atoms: Any
    frame_index: int
    selected_indices: list[int]
    periodic_axes: tuple[int, int]
    plane_basis: np.ndarray
    translation_basis: np.ndarray
    current_coordinates: np.ndarray = field(default_factory=lambda: np.zeros(2))
    status: str = "ready"
    is_relaxing: bool = False
    stop_requested: bool = False
    run_id: int = 0
    step: int = 0
    max_steps: int = 0
    energy: float | None = None
    projected_force: float | None = None
    generalized_gradient: float | None = None
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def translation_vector(self) -> np.ndarray:
        return np.asarray(self.current_coordinates, dtype=float) @ self.translation_basis

    def fractional_translation(self) -> np.ndarray:
        return np.mod(np.asarray(self.current_coordinates, dtype=float), 1.0)

    def summary(self) -> dict[str, Any]:
        return {
            "schema": "v_ase.registry-relaxation.v1",
            "session_id": self.session_id,
            "status": self.status,
            "is_relaxing": self.is_relaxing,
            "selected_indices": list(self.selected_indices),
            "periodic_axes": list(self.periodic_axes),
            "coordinate_basis": "fractional-cell",
            "reference_component": "unselected-host",
            "mobile_component": "selected-guest",
            "translation_cartesian": self.translation_vector().tolist(),
            "translation_fractional": self.fractional_translation().tolist(),
            "step": int(self.step),
            "max_steps": int(self.max_steps),
            "energy": self.energy,
            "projected_force": self.projected_force,
            # Keep the unreleased field as an alias while callers migrate to
            # the physically explicit projected-force name.
            "generalized_force": self.projected_force,
            "generalized_gradient": self.generalized_gradient,
            "force_definition": "norm of the selected-component net force projected into the periodic interface plane",
            "force_units": "eV/angstrom",
        }


def registry_relaxation_summary(session: Any) -> dict[str, Any] | None:
    mode = getattr(session, "registry_relaxation", None)
    return mode.summary() if isinstance(mode, RegistryRelaxationSession) else None


def _validated_selection(natoms: int, indices: Sequence[int]) -> list[int]:
    selected = sorted({int(value) for value in indices})
    if not selected:
        raise ValueError("Select the movable guest/interface atoms first.")
    if selected[0] < 0 or selected[-1] >= natoms:
        raise ValueError("Rigid registry relaxation contains an invalid atom index.")
    if len(selected) >= natoms:
        raise ValueError("Leave at least one unselected host atom as the registry reference.")
    return selected


def _orthonormal_plane_basis(cell: np.ndarray, axes: tuple[int, int]) -> np.ndarray:
    first = np.asarray(cell[axes[0]], dtype=float)
    second = np.asarray(cell[axes[1]], dtype=float)
    first_length = float(np.linalg.norm(first))
    normal = np.cross(first, second)
    normal_length = float(np.linalg.norm(normal))
    if first_length <= 1e-12 or normal_length <= 1e-12:
        raise ValueError("Rigid registry relaxation requires two independent periodic vectors.")
    first_unit = first / first_length
    normal /= normal_length
    second_unit = np.cross(normal, first_unit)
    if float(np.dot(second_unit, second)) < 0:
        second_unit *= -1.0
    return np.asarray([first_unit, second_unit], dtype=float)


def start_registry_relaxation_mode(session: Any, selected_indices: Sequence[int]) -> dict[str, Any]:
    if getattr(session, "registry_relaxation", None) is not None:
        raise ValueError("Finish or cancel the active XY translation relaxation first.")
    if getattr(session, "atom_addition", None) is not None:
        raise ValueError("Finish or cancel Add Atoms before XY translation relaxation.")
    if getattr(session, "is_relaxing", False):
        raise ValueError("Stop the active structure relaxation first.")
    selected = _validated_selection(len(session.working_atoms), selected_indices)
    baseline = copy_atoms_with_calc(session.working_atoms)
    try:
        projected = project_periodic_lattice(baseline.cell.array, baseline.pbc, "Z")
    except ValueError as exc:
        raise ValueError(
            "Rigid registry relaxation requires an interface cell in the global XY plane."
        ) from exc
    if projected.axis_alignment < 0.985:
        raise ValueError(
            "Rigid registry relaxation requires an interface cell in the global XY plane."
        )
    axes = tuple(int(value) for value in projected.periodic_axes)
    mode = RegistryRelaxationSession(
        session_id=str(uuid.uuid4()),
        baseline_atoms=baseline,
        frame_index=int(session.current_frame),
        selected_indices=selected,
        periodic_axes=axes,
        plane_basis=_orthonormal_plane_basis(baseline.cell.array, axes),
        translation_basis=np.asarray(baseline.cell.array[list(axes)], dtype=float),
    )
    session.registry_relaxation = mode
    return mode.summary()


def _coordinates_for(mode: RegistryRelaxationSession, coordinates: np.ndarray) -> np.ndarray:
    positions = np.asarray(mode.baseline_atoms.positions, dtype=float).copy()
    translation = np.asarray(coordinates, dtype=float) @ mode.translation_basis
    positions[np.asarray(mode.selected_indices, dtype=int)] += translation
    return positions


def _rigid_translation_derivatives(
    mode: RegistryRelaxationSession,
    forces: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Return dE/dq and the Cartesian in-plane force norm.

    The optimizer variables ``q`` are dimensionless coefficients of the two
    periodic cell vectors.  Their energy gradient therefore has units of eV,
    while the convergence quantity shown to users is the selected component's
    net Cartesian force projected into the interface plane, in eV/angstrom.
    """

    selected = np.asarray(mode.selected_indices, dtype=int)
    net_force = np.sum(np.asarray(forces, dtype=float)[selected], axis=0)
    gradient = -np.asarray([
        float(np.dot(net_force, mode.translation_basis[0])),
        float(np.dot(net_force, mode.translation_basis[1])),
    ])
    projected_components = np.asarray(mode.plane_basis, dtype=float) @ net_force
    return gradient, float(np.linalg.norm(projected_components))


def _publish_step(
    session: Any,
    mode: RegistryRelaxationSession,
    atoms: Any,
    coordinates: np.ndarray,
    *,
    energy: float,
    projected_force: float,
    generalized_gradient: float,
    run_id: int,
) -> None:
    with mode.lock:
        if (
            mode.stop_requested
            or mode.run_id != run_id
            or getattr(session, "registry_relaxation", None) is not mode
        ):
            raise RuntimeError(_STOP_SIGNAL)
        mode.current_coordinates = np.asarray(coordinates, dtype=float).copy()
        mode.step += 1
        mode.energy = float(energy)
        mode.projected_force = float(projected_force)
        mode.generalized_gradient = float(generalized_gradient)
        atoms.set_positions(_coordinates_for(mode, mode.current_coordinates), apply_constraint=False)
        session.working_atoms = copy_atoms_with_calc(atoms)
        session.sync_current_frame()
        payload = {
            "type": "registry_relax_step",
            "session_id": session.session_id,
            **mode.summary(),
            "positions": atoms.positions.astype(float).tolist(),
        }
    ws_manager.broadcast_sync(payload, session.session_id)


def _run_registry_relaxation(
    session: Any,
    mode: RegistryRelaxationSession,
    *,
    run_id: int,
    fmax: float,
    steps: int,
) -> None:
    status = "error"
    message = None
    atoms = copy_atoms_with_calc(mode.baseline_atoms)
    ensure_default_calculator(atoms)
    cache: dict[str, Any] = {}

    def evaluate(coordinates: np.ndarray) -> tuple[float, np.ndarray]:
        with mode.lock:
            if (
                mode.stop_requested
                or mode.run_id != run_id
                or getattr(session, "registry_relaxation", None) is not mode
            ):
                raise RuntimeError(_STOP_SIGNAL)
        values = np.asarray(coordinates, dtype=float)
        if cache.get("coordinates") is not None and np.array_equal(cache["coordinates"], values):
            return cache["energy"], cache["gradient"]
        atoms.set_positions(_coordinates_for(mode, values), apply_constraint=False)
        energy = float(atoms.get_potential_energy())
        forces = np.asarray(atoms.get_forces(apply_constraint=False), dtype=float)
        gradient, projected_force = _rigid_translation_derivatives(mode, forces)
        cache.update({
            "coordinates": values.copy(),
            "energy": energy,
            "gradient": gradient,
            "projected_force": projected_force,
        })
        return energy, gradient

    def callback(intermediate) -> None:
        coordinates = np.asarray(getattr(intermediate, "x", intermediate), dtype=float)
        energy, gradient = evaluate(coordinates)
        _publish_step(
            session,
            mode,
            atoms,
            coordinates,
            energy=energy,
            projected_force=float(cache["projected_force"]),
            generalized_gradient=float(np.linalg.norm(gradient)),
            run_id=run_id,
        )

    try:
        initial = np.asarray(mode.current_coordinates, dtype=float).copy()
        energy, gradient = evaluate(initial)
        _publish_step(
            session,
            mode,
            atoms,
            initial,
            energy=energy,
            projected_force=float(cache["projected_force"]),
            generalized_gradient=float(np.linalg.norm(gradient)),
            run_id=run_id,
        )
        singular_values = np.linalg.svd(mode.translation_basis, compute_uv=False)
        minimum_scale = max(float(np.min(singular_values)), 1e-12)
        # L-BFGS-B tests the infinity norm of dE/dq.  This conservative
        # conversion guarantees that satisfying gtol also satisfies the
        # requested Cartesian in-plane force tolerance.
        fractional_gtol = max(minimum_scale * float(fmax) / np.sqrt(2.0), 1e-12)
        result = minimize(
            evaluate,
            initial,
            method="L-BFGS-B",
            jac=True,
            bounds=((-0.5, 0.5), (-0.5, 0.5)),
            callback=callback,
            options={
                "gtol": fractional_gtol,
                "maxiter": int(steps),
                "maxls": 30,
                "ftol": 1e-12,
            },
        )
        final_coordinates = np.asarray(result.x, dtype=float)
        final_energy, final_gradient = evaluate(final_coordinates)
        if (
            mode.step == 0
            or not np.allclose(final_coordinates, mode.current_coordinates, atol=1e-12)
        ):
            _publish_step(
                session,
                mode,
                atoms,
                final_coordinates,
                energy=final_energy,
                projected_force=float(cache["projected_force"]),
                generalized_gradient=float(np.linalg.norm(final_gradient)),
                run_id=run_id,
            )
        final_projected_force = float(cache["projected_force"])
        status = "converged" if final_projected_force <= fmax else "steps"
        if not result.success and status != "steps":
            message = str(result.message)
    except Exception as exc:
        if str(exc) == _STOP_SIGNAL:
            status = "stopped"
        else:
            message = str(exc)
            traceback.print_exc()
    finally:
        with mode.lock:
            if getattr(session, "registry_relaxation", None) is mode and mode.run_id == run_id:
                mode.is_relaxing = False
                mode.stop_requested = False
                mode.status = status
                payload = {
                    "type": "registry_relax_finished",
                    "session_id": session.session_id,
                    **mode.summary(),
                    "message": message,
                    "positions": session.working_atoms.positions.astype(float).tolist(),
                }
                ws_manager.broadcast_sync(payload, session.session_id)


def run_registry_relaxation(session: Any, payload: dict[str, Any]) -> dict[str, Any]:
    mode = getattr(session, "registry_relaxation", None)
    if not isinstance(mode, RegistryRelaxationSession):
        raise ValueError("Activate XY translation relaxation first.")
    if mode.is_relaxing:
        raise ValueError("XY translation relaxation is already running.")
    fmax = float(payload.get("fmax", 0.05))
    steps = int(payload.get("steps", 100))
    if not np.isfinite(fmax) or fmax <= 0:
        raise ValueError("fmax must be greater than 0.")
    if steps < 1 or steps > 100_000:
        raise ValueError("steps must be from 1 through 100000.")
    mode.status = "relaxing"
    mode.is_relaxing = True
    mode.stop_requested = False
    mode.step = 0
    mode.max_steps = steps
    mode.run_id += 1
    thread = threading.Thread(
        target=_run_registry_relaxation,
        kwargs={
            "session": session,
            "mode": mode,
            "run_id": mode.run_id,
            "fmax": fmax,
            "steps": steps,
        },
        daemon=True,
        name=f"v_ase-registry-{session.session_id[:8]}",
    )
    thread.start()
    return mode.summary()


def stop_registry_relaxation(session: Any) -> bool:
    mode = getattr(session, "registry_relaxation", None)
    if not isinstance(mode, RegistryRelaxationSession) or not mode.is_relaxing:
        return False
    with mode.lock:
        mode.stop_requested = True
    return True


def finish_registry_relaxation_mode(session: Any) -> dict[str, Any]:
    mode = getattr(session, "registry_relaxation", None)
    if not isinstance(mode, RegistryRelaxationSession):
        raise ValueError("There is no active XY translation relaxation to finish.")
    with mode.lock:
        if mode.is_relaxing:
            raise ValueError("Stop or wait for XY translation relaxation before applying it.")
        final_atoms = copy_atoms_with_calc(session.working_atoms)
        session.working_atoms = copy_atoms_with_calc(mode.baseline_atoms)
        session.sync_current_frame()
        session.push_history()
        session.working_atoms = final_atoms
        session.sync_current_frame()
        session.registry_relaxation = None
        return mode.summary()


def cancel_registry_relaxation_mode(session: Any) -> None:
    mode = getattr(session, "registry_relaxation", None)
    if not isinstance(mode, RegistryRelaxationSession):
        return
    with mode.lock:
        mode.stop_requested = True
        mode.run_id += 1
        mode.is_relaxing = False
        session.working_atoms = copy_atoms_with_calc(mode.baseline_atoms)
        session.sync_current_frame()
        session.registry_relaxation = None
