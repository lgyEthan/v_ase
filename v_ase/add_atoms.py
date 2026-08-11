"""Random atom insertion and isolated repulsive placement for Edit mode.

The implementation follows the established project convention used by the
author's structure-generation utilities: existing atoms are the host, inserted
atoms are tagged as the mobile population, and pair-specific minimum distances
drive a soft harmonic repulsion.  Sampling and temporary optimization are kept
separate so the host structure is never committed from the optimizer copy.
"""

from __future__ import annotations

import itertools
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
from ase import Atom, Atoms
from ase.constraints import FixAtoms
from ase.data import atomic_numbers, covalent_radii, vdw_radii
from ase.optimize import FIRE

from .io import (
    atom_labels,
    base_symbol_for_atom_type,
    normalize_atom_type_label,
    set_atom_labels,
)
from .repulsion import VAseRepulsionCalculator, copy_calculator
from .websocket_manager import ws_manager


ADD_ATOMS_SCHEMA = "v_ase.add_atoms.v1"
MAX_RANDOM_ATOMS = 100_000
_CELL_TOLERANCE = 1e-10
_STOP_SIGNAL = "V_ASE_ADD_ATOMS_OPTIMIZATION_STOPPED"


def _copy_atoms_with_calculator(atoms: Atoms) -> Atoms:
    copied = atoms.copy()
    if atoms.calc is not None:
        copied.calc = copy_calculator(atoms.calc)
    return copied


def _finite_cell(cell: Any) -> np.ndarray:
    matrix = np.asarray(cell, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("Random unit-cell placement requires a finite 3 x 3 cell.")
    if abs(float(np.linalg.det(matrix))) <= _CELL_TOLERANCE:
        raise ValueError("Random unit-cell placement requires a non-degenerate 3D cell.")
    return matrix


def cell_cartesian_corners(cell: Any) -> np.ndarray:
    """Return the eight Cartesian corners of a row-vector ASE cell."""
    matrix = _finite_cell(cell)
    fractional = np.asarray(list(itertools.product((0.0, 1.0), repeat=3)))
    return fractional @ matrix


def cell_cartesian_bounds(cell: Any) -> list[float]:
    """Return [xmin, xmax, ymin, ymax, zmin, zmax] for the cell AABB."""
    corners = cell_cartesian_corners(cell)
    return [
        float(corners[:, 0].min()),
        float(corners[:, 0].max()),
        float(corners[:, 1].min()),
        float(corners[:, 1].max()),
        float(corners[:, 2].min()),
        float(corners[:, 2].max()),
    ]


def normalize_cartesian_bounds(bounds: Sequence[Any]) -> list[float]:
    if not isinstance(bounds, Sequence) or len(bounds) != 6:
        raise ValueError("Cartesian bounds must contain xmin, xmax, ymin, ymax, zmin, and zmax.")
    normalized = [float(value) for value in bounds]
    if not np.all(np.isfinite(normalized)):
        raise ValueError("Cartesian bounds must be finite.")
    for axis in range(3):
        lower, upper = normalized[axis * 2 : axis * 2 + 2]
        if upper <= lower:
            name = "xyz"[axis]
            raise ValueError(f"{name}max must be greater than {name}min.")
    return normalized


def _bounds_arrays(bounds: Sequence[Any]) -> tuple[np.ndarray, np.ndarray]:
    normalized = normalize_cartesian_bounds(bounds)
    return np.asarray(normalized[::2]), np.asarray(normalized[1::2])


def _primary_cell_mask(
    positions: np.ndarray,
    cell: np.ndarray,
    pbc: Sequence[bool],
) -> np.ndarray:
    periodic = np.asarray(pbc, dtype=bool)
    if not np.any(periodic):
        return np.ones(len(positions), dtype=bool)
    inverse = np.linalg.inv(cell)
    fractional = positions @ inverse
    selected = fractional[:, periodic]
    # Half-open primary-cell bounds avoid assigning probability to both
    # periodic representations of a boundary point.
    return np.all((selected >= 0.0) & (selected < 1.0), axis=1)


def sample_unit_cell_positions(
    cell: Any,
    count: int,
    *,
    seed: int | None = None,
) -> np.ndarray:
    """Sample volume-uniform Cartesian points in any triclinic ASE cell.

    A linear map from a uniform fractional cube has a constant Jacobian equal
    to ``abs(det(cell))``.  It is therefore volume-uniform without assuming an
    orthorhombic cell.
    """
    matrix = _finite_cell(cell)
    requested = _validated_count(count)
    generator = np.random.default_rng(seed)
    return generator.random((requested, 3), dtype=np.float64) @ matrix


def sample_cartesian_box_positions(
    cell: Any,
    pbc: Sequence[bool],
    bounds: Sequence[Any],
    count: int,
    *,
    seed: int | None = None,
    max_batches: int = 256,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sample uniformly from a Cartesian box intersected with the primary cell.

    Restricting periodic fractional coordinates to the half-open primary cell
    prevents the same physical voxel from receiving probability once per image
    when the triclinic cell's Cartesian bounding box overlaps periodic images.
    """
    matrix = _finite_cell(cell)
    requested = _validated_count(count)
    periodic = np.asarray(pbc, dtype=bool)
    if periodic.shape != (3,):
        raise ValueError("pbc must contain exactly three boolean values.")
    lower, upper = _bounds_arrays(bounds)
    generator = np.random.default_rng(seed)
    accepted: list[np.ndarray] = []
    accepted_count = 0
    eligible_count = 0
    attempted = 0

    for _ in range(max(1, int(max_batches))):
        remaining = requested - accepted_count
        if remaining <= 0:
            break
        batch_size = min(1_000_000, max(2048, remaining * 6))
        candidates = generator.uniform(lower, upper, size=(batch_size, 3))
        attempted += batch_size
        mask = _primary_cell_mask(candidates, matrix, periodic)
        eligible_count += int(np.count_nonzero(mask))
        if np.any(mask):
            chunk = candidates[mask][:remaining]
            accepted.append(chunk)
            accepted_count += len(chunk)

    if accepted_count < requested:
        raise ValueError(
            "The Cartesian insertion box has too little overlap with the primary "
            "unit cell. Enlarge or move the box."
        )
    positions = np.concatenate(accepted, axis=0)[:requested]
    return positions, {
        "attempted": int(attempted),
        "accepted": int(requested),
        "acceptance_fraction": float(eligible_count / max(1, attempted)),
    }


def sample_unit_cell_positions_outside_box(
    cell: Any,
    bounds: Sequence[Any],
    count: int,
    *,
    seed: int | None = None,
    max_batches: int = 256,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sample uniformly from one triclinic cell excluding a Cartesian AABB.

    Candidates are uniform in fractional coordinates, so every physical voxel
    in the primary cell has the same probability before the Cartesian
    exclusion test.  This avoids weighting overlapping images of a skew cell.
    """
    matrix = _finite_cell(cell)
    lower, upper = _bounds_arrays(bounds)
    requested = _validated_count(count)
    generator = np.random.default_rng(seed)
    accepted: list[np.ndarray] = []
    accepted_count = 0
    eligible_count = 0
    attempted = 0

    for _ in range(max(1, int(max_batches))):
        remaining = requested - accepted_count
        if remaining <= 0:
            break
        batch_size = min(1_000_000, max(2048, remaining * 6))
        candidates = generator.random((batch_size, 3), dtype=np.float64) @ matrix
        attempted += batch_size
        inside = np.all((candidates >= lower) & (candidates <= upper), axis=1)
        eligible = candidates[~inside]
        eligible_count += len(eligible)
        if len(eligible):
            chunk = eligible[:remaining]
            accepted.append(chunk)
            accepted_count += len(chunk)

    if accepted_count < requested:
        raise ValueError(
            "The prohibited Cartesian box leaves too little accessible volume "
            "inside the primary unit cell. Shrink or move the box."
        )
    positions = np.concatenate(accepted, axis=0)[:requested]
    return positions, {
        "attempted": int(attempted),
        "accepted": int(requested),
        "acceptance_fraction": float(eligible_count / max(1, attempted)),
    }


def _validated_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Atom count must be an integer.") from exc
    if count < 1 or count > MAX_RANDOM_ATOMS:
        raise ValueError(f"Atom count must be from 1 through {MAX_RANDOM_ATOMS:,}.")
    return count


def normalize_add_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_entries = payload.get("entries")
    if raw_entries is None:
        raw_entries = [{
            "element": payload.get("element") or payload.get("base_symbol") or "H",
            "label": payload.get("label") or payload.get("symbol") or payload.get("element") or "H",
            "count": payload.get("count", 1),
        }]
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("entries must contain at least one atom specification.")

    entries: list[dict[str, Any]] = []
    total = 0
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("Each atom entry must be an object.")
        label = normalize_atom_type_label(raw.get("label") or raw.get("element") or "")
        if not label:
            raise ValueError("Every atom entry requires a non-empty label or element.")
        element = base_symbol_for_atom_type(raw.get("element") or label)
        count = _validated_count(raw.get("count", 1))
        total += count
        if total > MAX_RANDOM_ATOMS:
            raise ValueError(f"Total atom count cannot exceed {MAX_RANDOM_ATOMS:,}.")
        entries.append({"element": element, "label": label, "count": count})
    return entries


def expanded_entry_values(entries: Iterable[dict[str, Any]]) -> tuple[list[str], list[str]]:
    elements: list[str] = []
    labels: list[str] = []
    for entry in entries:
        elements.extend([str(entry["element"])] * int(entry["count"]))
        labels.extend([str(entry["label"])] * int(entry["count"]))
    return elements, labels


def canonical_pair_key(first: str, second: str) -> str:
    return "-".join(sorted((str(first), str(second))))


def default_pair_cutoffs(
    symbols: Iterable[str],
    *,
    basis: str = "covalent",
    scale: float = 0.7,
) -> dict[str, float]:
    """Build NARA-style explicit pair thresholds in angstrom."""
    normalized_basis = str(basis or "covalent").strip().lower()
    if normalized_basis not in {"covalent", "vdw", "pairwise"}:
        raise ValueError("Repulsion cutoff basis must be covalent, vdw, or pairwise.")
    try:
        normalized_scale = float(scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("Repulsion cutoff scale must be finite.") from exc
    if not np.isfinite(normalized_scale) or normalized_scale <= 0 or normalized_scale > 3:
        raise ValueError("Repulsion cutoff scale must be greater than 0 and at most 3.")

    unique = sorted({base_symbol_for_atom_type(symbol) for symbol in symbols})
    cutoffs: dict[str, float] = {}
    for index, first in enumerate(unique):
        for second in unique[index:]:
            first_number = atomic_numbers[first]
            second_number = atomic_numbers[second]
            if normalized_basis == "vdw":
                threshold = float(vdw_radii[first_number] + vdw_radii[second_number])
                if not np.isfinite(threshold):
                    threshold = float(covalent_radii[first_number] + covalent_radii[second_number])
            else:
                threshold = float(covalent_radii[first_number] + covalent_radii[second_number])
            cutoffs[canonical_pair_key(first, second)] = threshold * normalized_scale
    return cutoffs


def normalize_pair_cutoffs(
    values: Any,
    symbols: Iterable[str],
    *,
    basis: str,
    scale: float,
) -> dict[str, float]:
    defaults = default_pair_cutoffs(symbols, basis=basis, scale=scale)
    if values is None:
        return defaults
    if not isinstance(values, dict):
        raise ValueError("pair_cutoffs must be an element-pair to distance object.")
    result = defaults if str(basis).lower() != "pairwise" else {}
    valid_symbols = {base_symbol_for_atom_type(symbol) for symbol in symbols}
    for raw_key, raw_value in values.items():
        parts = str(raw_key).split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid pair cutoff key '{raw_key}'. Use Element-Element.")
        first = base_symbol_for_atom_type(parts[0])
        second = base_symbol_for_atom_type(parts[1])
        if first not in valid_symbols or second not in valid_symbols:
            raise ValueError(f"Pair cutoff '{raw_key}' refers to an element not in the structure.")
        value = float(raw_value)
        if not np.isfinite(value) or value < 0 or value > 20:
            raise ValueError("Pair cutoff distances must be finite values from 0 through 20 angstrom.")
        result[canonical_pair_key(first, second)] = value
    return dict(sorted(result.items()))


def append_atoms(
    baseline: Atoms,
    elements: Sequence[str],
    labels: Sequence[str],
    positions: np.ndarray,
) -> Atoms:
    if len(elements) != len(labels) or len(elements) != len(positions):
        raise ValueError("Elements, labels, and positions must have the same length.")
    result = _copy_atoms_with_calculator(baseline)
    result_labels = atom_labels(result)
    for element, label, position in zip(elements, labels, positions):
        result.append(Atom(base_symbol_for_atom_type(element), position=np.asarray(position, dtype=float)))
        result_labels.append(normalize_atom_type_label(label))
    set_atom_labels(result, result_labels)
    return result


def project_positions_to_region(
    positions: np.ndarray,
    *,
    cell: Any,
    pbc: Sequence[bool],
    mode: str,
    bounds: Sequence[Any] | None,
    indices: Sequence[int],
    prohibited: bool = False,
) -> np.ndarray:
    """Project mobile positions onto the allowed side of a region boundary."""
    matrix = _finite_cell(cell)
    inverse = np.linalg.inv(matrix)
    periodic = np.asarray(pbc, dtype=bool)
    output = np.asarray(positions, dtype=float).copy()
    mobile = np.asarray(indices, dtype=int)
    if not len(mobile):
        return output
    epsilon = 1e-9

    if mode == "cell":
        fractional = output[mobile] @ inverse
        for axis in range(3):
            if periodic[axis]:
                fractional[:, axis] %= 1.0
            else:
                fractional[:, axis] = np.clip(fractional[:, axis], epsilon, 1.0 - epsilon)
        output[mobile] = fractional @ matrix
        return output

    lower, upper = _bounds_arrays(bounds or cell_cartesian_bounds(matrix))
    current = output[mobile]
    if prohibited:
        inside = np.all((current >= lower) & (current <= upper), axis=1)
        for row in np.flatnonzero(inside):
            point = current[row]
            distances = np.concatenate((point - lower, upper - point))
            face = int(np.argmin(distances))
            axis = face % 3
            if face < 3:
                point[axis] = lower[axis] - epsilon
            else:
                point[axis] = upper[axis] + epsilon
        output[mobile] = current
        return output
    # Alternating projections converge to the intersection of the Cartesian
    # box and the periodic primary-cell slabs without imposing an orthogonal
    # cell approximation.
    for _ in range(16):
        current = np.clip(current, lower + epsilon, upper - epsilon)
        if np.any(periodic):
            fractional = current @ inverse
            for axis in np.flatnonzero(periodic):
                fractional[:, axis] = np.clip(fractional[:, axis], epsilon, 1.0 - epsilon)
            current = fractional @ matrix
    current = np.clip(current, lower + epsilon, upper - epsilon)
    if not np.all(_primary_cell_mask(current, matrix, periodic)):
        raise ValueError("The Cartesian insertion region could not retain atoms inside the primary cell.")
    output[mobile] = current
    return output


class AdditionRepulsionCalculator(VAseRepulsionCalculator):
    """Temporary calculator with triclinic cell-boundary forces."""

    def __init__(self, *args, cell_region: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.cell_region = bool(cell_region)

    def _boundary_energy_forces(self, atoms: Atoms):
        energy, forces = super()._boundary_energy_forces(atoms)
        if not self.cell_region:
            return energy, forces
        matrix = _finite_cell(atoms.cell.array)
        inverse = np.linalg.inv(matrix)
        fractional = atoms.positions @ inverse
        reciprocal_gradients = inverse.T
        periodic = np.asarray(atoms.pbc, dtype=bool)
        tags = atoms.get_tags()
        for atom_index, point in enumerate(fractional):
            if tags[atom_index] != 3 and not self.work_on_relax_atoms_too:
                continue
            for axis in range(3):
                if periodic[axis]:
                    continue
                gradient = reciprocal_gradients[axis]
                gradient_norm = float(np.linalg.norm(gradient))
                if gradient_norm <= _CELL_TOLERANCE:
                    continue
                normal = gradient / gradient_norm
                if point[axis] < 0.0:
                    distance = -float(point[axis]) / gradient_norm
                    forces[atom_index] += self.k_boundary * distance * normal
                    energy += 0.5 * self.k_boundary * distance**2
                elif point[axis] > 1.0:
                    distance = (float(point[axis]) - 1.0) / gradient_norm
                    forces[atom_index] -= self.k_boundary * distance * normal
                    energy += 0.5 * self.k_boundary * distance**2
        return energy, forces


@dataclass
class AtomAdditionSession:
    session_id: str
    baseline_atoms: Atoms
    frame_index: int
    history_index: int
    redo_before: list[Any]
    region_mode: str
    bounds: list[float]
    region_role: str
    allow_escape: bool
    entries: list[dict[str, Any]]
    elements: list[str]
    labels: list[str]
    new_indices: list[int]
    pair_cutoffs: dict[str, float]
    cutoff_basis: str
    cutoff_scale: float
    seed: int | None
    freeze_existing: bool = True
    is_relaxing: bool = False
    stop_requested: bool = False
    run_id: int = 0
    status: str = "scattered"
    step: int = 0
    max_steps: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def host_count(self) -> int:
        return len(self.baseline_atoms)

    def summary(self) -> dict[str, Any]:
        return {
            "schema": ADD_ATOMS_SCHEMA,
            "id": self.session_id,
            "active": True,
            "status": self.status,
            "region_mode": self.region_mode,
            "bounds": list(self.bounds),
            "region_role": self.region_role,
            "allow_escape": self.allow_escape,
            "cell": np.asarray(self.baseline_atoms.cell.array, dtype=float).tolist(),
            "pbc": np.asarray(self.baseline_atoms.pbc, dtype=bool).tolist(),
            "entries": [dict(entry) for entry in self.entries],
            "new_indices": list(self.new_indices),
            "host_count": self.host_count,
            "new_count": len(self.new_indices),
            "pair_cutoffs": dict(self.pair_cutoffs),
            "cutoff_basis": self.cutoff_basis,
            "cutoff_scale": self.cutoff_scale,
            "seed": self.seed,
            "freeze_existing": self.freeze_existing,
            "temporary_fixed_indices": (
                list(range(self.host_count)) if self.freeze_existing else []
            ),
            "is_relaxing": self.is_relaxing,
            "step": self.step,
            "max_steps": self.max_steps,
        }


def atom_addition_summary(session: Any) -> dict[str, Any] | None:
    addition = getattr(session, "atom_addition", None)
    return addition.summary() if isinstance(addition, AtomAdditionSession) else None


def _random_seed(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        seed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Random seed must be an integer or blank.") from exc
    if seed < 0 or seed > np.iinfo(np.uint32).max:
        raise ValueError("Random seed must fit in an unsigned 32-bit integer.")
    return seed


def start_atom_addition(session: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if getattr(session, "atom_addition", None) is not None:
        raise ValueError("Finish or cancel the active Add Atoms session first.")
    if getattr(session, "is_relaxing", False):
        raise ValueError("Stop the active structure relaxation before adding atoms.")
    if getattr(session, "trajectory_source", None) is not None or int(
        getattr(session, "frame_count", 1)
    ) > 1:
        raise ValueError(
            "Random atom insertion requires a single structure. Open the target "
            "trajectory frame in a new tab before starting Add Atoms."
        )

    entries = normalize_add_entries(payload)
    elements, labels = expanded_entry_values(entries)
    baseline = _copy_atoms_with_calculator(session.working_atoms)
    matrix = _finite_cell(baseline.cell.array)
    mode = str(payload.get("region_mode") or "cell").strip().lower()
    if mode not in {"cell", "box"}:
        raise ValueError("region_mode must be cell or box.")
    bounds = (
        cell_cartesian_bounds(matrix)
        if mode == "cell"
        else normalize_cartesian_bounds(payload.get("bounds") or cell_cartesian_bounds(matrix))
    )
    region_role = str(payload.get("region_role") or "allowed").strip().lower()
    if region_role not in {"allowed", "prohibited"}:
        raise ValueError("region_role must be allowed or prohibited.")
    if mode == "cell" and region_role == "prohibited":
        raise ValueError("The whole unit cell cannot be used as a prohibited insertion region.")
    allow_escape = bool(payload.get("allow_escape", True))
    seed = _random_seed(payload.get("seed"))
    count = len(elements)
    if mode == "cell":
        positions = sample_unit_cell_positions(matrix, count, seed=seed)
        sampling = {"attempted": count, "accepted": count, "acceptance_fraction": 1.0}
    elif region_role == "allowed":
        positions, sampling = sample_cartesian_box_positions(
            matrix,
            baseline.pbc,
            bounds,
            count,
            seed=seed,
        )
    else:
        positions, sampling = sample_unit_cell_positions_outside_box(
            matrix,
            bounds,
            count,
            seed=seed,
        )

    basis = str(payload.get("cutoff_basis") or "covalent").strip().lower()
    cutoff_scale = float(payload.get("cutoff_scale", 0.7))
    all_elements = [*baseline.get_chemical_symbols(), *elements]
    pair_cutoffs = normalize_pair_cutoffs(
        payload.get("pair_cutoffs"),
        all_elements,
        basis=basis,
        scale=cutoff_scale,
    )

    redo_before = list(session.redo_stack)
    session.push_history(include_trajectory=True)
    history_index = len(session.history) - 1
    working = append_atoms(baseline, elements, labels, positions)
    new_indices = list(range(len(baseline), len(working)))
    addition = AtomAdditionSession(
        session_id=str(uuid.uuid4()),
        baseline_atoms=baseline,
        frame_index=int(session.current_frame),
        history_index=history_index,
        redo_before=redo_before,
        region_mode=mode,
        bounds=bounds,
        region_role=region_role,
        allow_escape=allow_escape,
        entries=entries,
        elements=elements,
        labels=labels,
        new_indices=new_indices,
        pair_cutoffs=pair_cutoffs,
        cutoff_basis=basis,
        cutoff_scale=cutoff_scale,
        seed=seed,
        freeze_existing=bool(payload.get("freeze_existing", True)),
    )
    session.atom_addition = addition
    session.working_atoms = working
    session.invalidate_trajectory_layout()
    session.sync_current_frame()
    session.refresh_trajectory_identity()
    summary = addition.summary()
    summary["sampling"] = sampling
    return summary


def update_atom_addition_region(session: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Update the active Cartesian box without moving any atoms."""
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession):
        raise ValueError("There is no active Add Atoms session.")
    with addition.lock:
        if addition.is_relaxing:
            raise ValueError("Stop repulsive placement before moving the insertion box.")
        if addition.region_mode != "box":
            raise ValueError("Only a Cartesian insertion box can be moved.")
        addition.bounds = normalize_cartesian_bounds(payload.get("bounds"))
        if "region_role" in payload:
            role = str(payload.get("region_role") or "").strip().lower()
            if role not in {"allowed", "prohibited"}:
                raise ValueError("region_role must be allowed or prohibited.")
            addition.region_role = role
        if "allow_escape" in payload:
            addition.allow_escape = bool(payload.get("allow_escape"))
        return addition.summary()


def _restore_cancelled_addition(session: Any, addition: AtomAdditionSession) -> None:
    history_state = None
    if (
        addition.history_index == len(session.history) - 1
        and addition.history_index >= 0
    ):
        history_state = session.history.pop()
    if history_state is not None:
        session._restore_history_state(history_state)
    else:
        session.working_atoms = _copy_atoms_with_calculator(addition.baseline_atoms)
        session.invalidate_trajectory_layout()
        session.sync_current_frame()
        session.refresh_trajectory_identity()
    session.redo_stack = list(addition.redo_before)


def cancel_atom_addition(session: Any) -> None:
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession):
        return
    with addition.lock:
        addition.stop_requested = True
        addition.run_id += 1
        addition.is_relaxing = False
        session.atom_addition = None
        _restore_cancelled_addition(session, addition)


def stop_atom_addition_relaxation(session: Any) -> bool:
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession) or not addition.is_relaxing:
        return False
    with addition.lock:
        addition.stop_requested = True
    return True


def finish_atom_addition(session: Any) -> dict[str, Any]:
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession):
        raise ValueError("There is no active Add Atoms session to finish.")
    with addition.lock:
        if session.atom_addition is not addition:
            raise ValueError("The active Add Atoms session changed unexpectedly.")
        if addition.is_relaxing:
            raise ValueError("Stop or wait for repulsive placement before finishing Add Atoms.")
        current = session.working_atoms
        if len(current) < addition.host_count + len(addition.new_indices):
            raise ValueError("The active Add Atoms topology changed unexpectedly.")
        added_positions = np.asarray(current.positions[addition.new_indices], dtype=float)
        committed = append_atoms(
            addition.baseline_atoms,
            addition.elements,
            addition.labels,
            added_positions,
        )
        session.atom_addition = None
        session.working_atoms = committed
        session.invalidate_trajectory_layout()
        session.sync_current_frame()
        session.refresh_trajectory_identity()
        return {
            "schema": ADD_ATOMS_SCHEMA,
            "added": len(addition.new_indices),
            "indices": list(range(addition.host_count, len(committed))),
        }


def _temporary_optimizer_atoms(
    session: Any,
    addition: AtomAdditionSession,
    *,
    pair_cutoffs: dict[str, float],
    k_repulsion: float,
    k_boundary: float,
    mic: bool,
) -> Atoms:
    temporary = session.working_atoms.copy()
    tags = temporary.get_tags()
    tags[:] = 1
    tags[addition.new_indices] = 3
    temporary.set_tags(tags)
    constraints = list(temporary.constraints)
    if addition.freeze_existing and addition.host_count:
        constraints.append(FixAtoms(indices=np.arange(addition.host_count)))
    temporary.set_constraint(constraints)
    temporary.calc = AdditionRepulsionCalculator(
        min_bondinfo=pair_cutoffs,
        region=(
            addition.bounds
            if not addition.allow_escape and addition.region_mode == "box"
            else None
        ),
        set_region_as_prohibited=addition.region_role == "prohibited",
        k_boundary=k_boundary,
        k_repulsion=k_repulsion,
        cutoff_scale=1.0,
        max_force_norm=10.0,
        mic=mic,
        work_on_relax_atoms_too=not addition.freeze_existing,
        cell_region=not addition.allow_escape and addition.region_mode == "cell",
        device="cpu",
    )
    return temporary


def _publish_addition_positions(
    session: Any,
    addition: AtomAdditionSession,
    temporary: Atoms,
    *,
    step: int,
    max_steps: int,
    energy: float,
    fmax: float,
    run_id: int,
) -> None:
    with addition.lock:
        if (
            addition.stop_requested
            or run_id != addition.run_id
            or getattr(session, "atom_addition", None) is not addition
        ):
            raise RuntimeError(_STOP_SIGNAL)
        if addition.allow_escape:
            committed_positions = np.asarray(temporary.positions, dtype=float)
        else:
            committed_positions = project_positions_to_region(
                temporary.positions,
                cell=temporary.cell.array,
                pbc=temporary.pbc,
                mode=addition.region_mode,
                bounds=addition.bounds,
                indices=addition.new_indices,
                prohibited=addition.region_role == "prohibited",
            )
        temporary.set_positions(committed_positions, apply_constraint=True)
        current = session.working_atoms
        if len(current) != len(temporary):
            raise RuntimeError(_STOP_SIGNAL)
        current.set_positions(temporary.positions, apply_constraint=False)
        session.sync_current_frame()
        addition.step = int(step)
        ws_manager.broadcast_sync(
            {
                "type": "add_atoms_relax_step",
                "session_id": session.session_id,
                "addition_id": addition.session_id,
                "step": int(step),
                "max_steps": int(max_steps),
                "energy": float(energy),
                "fmax": float(fmax),
                "positions": temporary.positions.astype(float).tolist(),
            },
            session.session_id,
        )


def _run_addition_relaxation(
    session: Any,
    addition: AtomAdditionSession,
    *,
    run_id: int,
    fmax: float,
    steps: int,
    pair_cutoffs: dict[str, float],
    k_repulsion: float,
    k_boundary: float,
    mic: bool,
) -> None:
    status = "converged"
    error_message = None
    temporary = None
    optimizer = None
    try:
        temporary = _temporary_optimizer_atoms(
            session,
            addition,
            pair_cutoffs=pair_cutoffs,
            k_repulsion=k_repulsion,
            k_boundary=k_boundary,
            mic=mic,
        )
        optimizer = FIRE(temporary, logfile=None, dt=0.04, maxstep=0.12)

        def callback():
            with addition.lock:
                if (
                    addition.stop_requested
                    or run_id != addition.run_id
                    or getattr(session, "atom_addition", None) is not addition
                ):
                    raise RuntimeError(_STOP_SIGNAL)
            forces = temporary.get_forces()
            current_fmax = (
                float(np.sqrt((forces**2).sum(axis=1).max()))
                if len(forces)
                else 0.0
            )
            _publish_addition_positions(
                session,
                addition,
                temporary,
                step=optimizer.nsteps,
                max_steps=steps,
                energy=float(temporary.get_potential_energy()),
                fmax=current_fmax,
                run_id=run_id,
            )

        optimizer.attach(callback, interval=1)
        optimizer.run(fmax=fmax, steps=steps)
        if optimizer.nsteps >= steps:
            status = "steps"
        callback()
    except Exception as exc:
        if str(exc) == _STOP_SIGNAL:
            status = "stopped"
        else:
            status = "error"
            error_message = str(exc)
            traceback.print_exc()
    finally:
        with addition.lock:
            if getattr(session, "atom_addition", None) is addition and run_id == addition.run_id:
                addition.is_relaxing = False
                addition.stop_requested = False
                addition.status = "relaxed" if status in {"converged", "steps"} else status
                payload = {
                    "type": "add_atoms_relax_finished",
                    "session_id": session.session_id,
                    "addition_id": addition.session_id,
                    "status": status,
                    "step": int(optimizer.nsteps if optimizer is not None else addition.step),
                    "max_steps": int(steps),
                    "message": error_message,
                    "positions": (
                        temporary.positions.astype(float).tolist()
                        if temporary is not None and status != "error"
                        else None
                    ),
                }
                ws_manager.broadcast_sync(payload, session.session_id)


def start_atom_addition_relaxation(
    session: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession):
        raise ValueError("Scatter atoms before starting repulsive placement.")
    if addition.is_relaxing:
        raise ValueError("Repulsive placement is already running.")
    try:
        fmax = float(payload.get("fmax", 0.05))
        steps = int(payload.get("steps", 250))
        k_repulsion = float(payload.get("k_repulsion", 2.0))
        k_boundary = float(payload.get("k_boundary", 5.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Repulsive placement settings must be numeric.") from exc
    if not np.isfinite(fmax) or fmax <= 0:
        raise ValueError("fmax must be greater than 0.")
    if steps < 1 or steps > 100_000:
        raise ValueError("steps must be from 1 through 100000.")
    if not np.isfinite(k_repulsion) or k_repulsion < 0 or k_repulsion > 1000:
        raise ValueError("Repulsion strength must be from 0 through 1000.")
    if not np.isfinite(k_boundary) or k_boundary <= 0 or k_boundary > 1000:
        raise ValueError("Boundary strength must be greater than 0 and at most 1000.")

    all_elements = [*addition.baseline_atoms.get_chemical_symbols(), *addition.elements]
    pair_cutoffs = normalize_pair_cutoffs(
        payload.get("pair_cutoffs", addition.pair_cutoffs),
        all_elements,
        basis="pairwise",
        scale=1.0,
    )
    addition.pair_cutoffs = pair_cutoffs
    addition.freeze_existing = bool(payload.get("freeze_existing", addition.freeze_existing))
    addition.allow_escape = bool(payload.get("allow_escape", addition.allow_escape))
    addition.status = "relaxing"
    addition.is_relaxing = True
    addition.stop_requested = False
    addition.step = 0
    addition.max_steps = steps
    addition.run_id += 1
    run_id = addition.run_id
    thread = threading.Thread(
        target=_run_addition_relaxation,
        kwargs={
            "session": session,
            "addition": addition,
            "run_id": run_id,
            "fmax": fmax,
            "steps": steps,
            "pair_cutoffs": pair_cutoffs,
            "k_repulsion": k_repulsion,
            "k_boundary": k_boundary,
            "mic": bool(payload.get("mic", True)),
        },
        daemon=True,
        name=f"v_ase-add-atoms-{session.session_id[:8]}",
    )
    thread.start()
    return addition.summary()
