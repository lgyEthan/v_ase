"""Batch atom and molecule insertion with isolated repulsive placement.

The implementation follows the established project convention used by the
author's structure-generation utilities: existing atoms are the host, inserted
atoms are tagged as the mobile population, and pair-specific minimum distances
drive a soft harmonic repulsion.  Sampling and temporary optimization are kept
separate so the host structure is never committed from the optimizer copy.
"""

from __future__ import annotations

import itertools
import math
import re
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Sequence

import numpy as np
from ase import Atom, Atoms
from ase.build import molecule
from ase.collections import g2
from ase.constraints import FixAtoms, FixConstraint
from ase.data import atomic_masses, atomic_numbers, covalent_radii, vdw_radii
from ase.geometry.minkowski_reduction import minkowski_reduce
from ase.optimize import FIRE
from scipy.constants import Avogadro

from .io import (
    atom_labels,
    base_symbol_for_atom_type,
    normalize_atom_type_label,
    set_atom_labels,
)
from .insertion_regions import (
    InsertionDomain,
    InsertionRegion,
    build_insertion_domain,
    finite_cell_or_none,
    normalize_insertion_regions,
)
from .repulsion import VAseRepulsionCalculator, copy_calculator
from .websocket_manager import ws_manager


ADD_ATOMS_SCHEMA = "v_ase.add_atoms.v1"
MAX_RANDOM_ATOMS = 100_000
MAX_MOLECULES = 20_000
MAX_EXACT_HOMOGENEOUS_ENTITIES = 1_024
MOLECULE_GROUP_ARRAY = "v_ase_molecule_group"
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
            "The Allow region has too little overlap with the primary unit cell. "
            "Enlarge or move the region."
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
            "The Reject region leaves too little accessible volume inside the "
            "primary unit cell. Shrink or move the region."
        )
    positions = np.concatenate(accepted, axis=0)[:requested]
    return positions, {
        "attempted": int(attempted),
        "accepted": int(requested),
        "acceptance_fraction": float(eligible_count / max(1, attempted)),
    }


def sample_cartesian_unit_cell_positions(
    cell: Any,
    count: int,
    *,
    seed: int | None = None,
    bounds: Sequence[Any] | None = None,
    prohibited: bool = False,
    max_batches: int = 256,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sample Cartesian-volume-uniform points in one primary triclinic cell.

    Candidates are generated in the cell's Cartesian bounding box and accepted
    only when all three fractional coordinates belong to the half-open primary
    cell.  Optional Cartesian bounds select or exclude an insertion box without
    counting overlapping periodic images more than once.
    """
    matrix = _finite_cell(cell)
    requested = _validated_count(count)
    cell_lower, cell_upper = _bounds_arrays(cell_cartesian_bounds(matrix))
    box_lower = box_upper = None
    if bounds is not None:
        box_lower, box_upper = _bounds_arrays(bounds)
    generator = np.random.default_rng(seed)
    inverse = np.linalg.inv(matrix)
    accepted: list[np.ndarray] = []
    accepted_count = 0
    eligible_count = 0
    attempted = 0

    for _ in range(max(1, int(max_batches))):
        remaining = requested - accepted_count
        if remaining <= 0:
            break
        batch_size = min(1_000_000, max(4096, remaining * 8))
        candidates = generator.uniform(cell_lower, cell_upper, size=(batch_size, 3))
        attempted += batch_size
        fractional = candidates @ inverse
        mask = np.all((fractional >= 0.0) & (fractional < 1.0), axis=1)
        if box_lower is not None and box_upper is not None:
            inside = np.all((candidates >= box_lower) & (candidates <= box_upper), axis=1)
            mask &= ~inside if prohibited else inside
        eligible = candidates[mask]
        eligible_count += len(eligible)
        if len(eligible):
            chunk = eligible[:remaining]
            accepted.append(chunk)
            accepted_count += len(chunk)

    if accepted_count < requested:
        role = "outside the Reject region" if prohibited else "inside the Allow region"
        raise ValueError(
            f"The primary cell has too little Cartesian volume {role}. "
            "Resize or move the Allow or Reject region."
        )
    return np.concatenate(accepted, axis=0)[:requested], {
        "attempted": int(attempted),
        "accepted": int(requested),
        "acceptance_fraction": float(eligible_count / max(1, attempted)),
    }


def sample_fractional_region_positions(
    cell: Any,
    bounds: Sequence[Any] | None,
    count: int,
    *,
    prohibited: bool = False,
    seed: int | None = None,
    max_batches: int = 256,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sample uniformly in fractional space, then apply a Cartesian box test."""
    matrix = _finite_cell(cell)
    requested = _validated_count(count)
    lower = upper = None
    if bounds is not None:
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
        candidates = generator.random((batch_size, 3), dtype=np.float64) @ matrix
        attempted += batch_size
        mask = np.ones(batch_size, dtype=bool)
        if lower is not None and upper is not None:
            inside = np.all((candidates >= lower) & (candidates <= upper), axis=1)
            mask = ~inside if prohibited else inside
        eligible = candidates[mask]
        eligible_count += len(eligible)
        if len(eligible):
            chunk = eligible[:remaining]
            accepted.append(chunk)
            accepted_count += len(chunk)
    if accepted_count < requested:
        raise ValueError(
            "The requested insertion region has too little overlap with the primary cell."
        )
    return np.concatenate(accepted, axis=0)[:requested], {
        "attempted": int(attempted),
        "accepted": int(requested),
        "acceptance_fraction": float(eligible_count / max(1, attempted)),
    }


def _normalize_placement_mode(value: Any) -> str:
    mode = str(value or "random").strip().lower()
    if mode not in {"random", "homogeneous", "regular"}:
        raise ValueError("placement_mode must be random, homogeneous, or regular.")
    return mode


def _normalize_coordinate_basis(value: Any) -> str:
    basis = str(value or "cartesian").strip().lower()
    if basis not in {"cartesian", "fractional"}:
        raise ValueError("coordinate_basis must be cartesian or fractional.")
    return basis


def _domain_candidates(
    cell: np.ndarray,
    count: int,
    *,
    coordinate_basis: str,
    region_mode: str,
    bounds: Sequence[Any] | None,
    region_role: str,
    seed: int | None,
) -> tuple[np.ndarray, int]:
    """Generate a deterministic low-discrepancy candidate pool."""
    from scipy.stats import qmc

    target = max(1, int(count))
    matrix = _finite_cell(cell)
    inverse = np.linalg.inv(matrix)
    cell_lower, cell_upper = _bounds_arrays(cell_cartesian_bounds(matrix))
    box_lower = box_upper = None
    if region_mode == "box":
        box_lower, box_upper = _bounds_arrays(bounds or cell_cartesian_bounds(matrix))
    engine = qmc.Sobol(d=3, scramble=True, seed=seed)
    chunks: list[np.ndarray] = []
    accepted_count = 0
    attempted = 0
    batch_size = 1 << int(math.ceil(math.log2(max(2048, min(131072, target * 4)))))

    for _ in range(64):
        raw = engine.random(batch_size)
        attempted += batch_size
        if coordinate_basis == "fractional":
            candidates = raw @ matrix
            mask = np.ones(batch_size, dtype=bool)
        else:
            candidates = cell_lower + raw * (cell_upper - cell_lower)
            fractional = candidates @ inverse
            mask = np.all((fractional >= 0.0) & (fractional < 1.0), axis=1)
        if box_lower is not None and box_upper is not None:
            inside = np.all((candidates >= box_lower) & (candidates <= box_upper), axis=1)
            mask &= ~inside if region_role == "prohibited" else inside
        eligible = candidates[mask]
        if len(eligible):
            chunks.append(eligible[: target - accepted_count])
            accepted_count += len(chunks[-1])
        if accepted_count >= target:
            break
    if accepted_count < target:
        raise ValueError(
            "The requested insertion region is too small for homogeneous placement."
        )
    return np.concatenate(chunks, axis=0)[:target], attempted


class _InsertionDistanceMetric:
    """Reusable Cartesian or normalized-fractional insertion metric.

    ASE's general MIC implementation performs a Minkowski reduction on every
    call. Greedy maximin placement compares against hundreds of selected
    points, so the reduced cell and Voronoi-relevant translations are cached
    once here while retaining the same exact triclinic search.
    """

    def __init__(
        self,
        cell: np.ndarray,
        pbc: Sequence[bool],
        coordinate_basis: str,
        pbc_aware: bool,
    ):
        self.cell = _finite_cell(cell)
        self.inverse = np.linalg.inv(self.cell)
        self.periodic = np.asarray(pbc, dtype=bool)
        self.coordinate_basis = _normalize_coordinate_basis(coordinate_basis)
        self.pbc_aware = bool(pbc_aware)
        self.reduced_cell: np.ndarray | None = None
        self.reduced_inverse: np.ndarray | None = None
        self.neighbor_vectors: np.ndarray | None = None
        self.naive_safe_squared: float | None = None

        if (
            self.coordinate_basis != "cartesian"
            or not self.pbc_aware
            or not np.any(self.periodic)
        ):
            return
        gram = self.cell @ self.cell.T
        off_diagonal = gram - np.diag(np.diag(gram))
        scale = max(1.0, float(np.max(np.abs(np.diag(gram)))))
        if float(np.max(np.abs(off_diagonal))) <= 1e-12 * scale:
            return

        reduced, _ = minkowski_reduce(self.cell, pbc=self.periodic)
        ranges = [range(-int(periodic), int(periodic) + 1) for periodic in self.periodic]
        shifts = np.asarray(list(itertools.product(*ranges)), dtype=float)
        self.reduced_cell = np.asarray(reduced, dtype=float)
        self.reduced_inverse = np.linalg.inv(self.reduced_cell)
        self.neighbor_vectors = shifts @ self.reduced_cell
        if bool(np.all(self.periodic)):
            # A skew lattice can have a short combination such as b - a even
            # when every original cell vector is long. The reduced basis
            # exposes the shortest lattice vectors, so only displacements
            # inside half that length can skip the general MIC search.
            shortest = float(np.min(np.linalg.norm(self.reduced_cell, axis=1)))
            self.naive_safe_squared = (0.5 * shortest) ** 2

    def squared(self, points: np.ndarray, reference: np.ndarray) -> np.ndarray:
        vectors = np.asarray(points, dtype=float) - np.asarray(reference, dtype=float)
        fractional = vectors @ self.inverse
        if self.coordinate_basis == "fractional":
            if self.pbc_aware:
                fractional[:, self.periodic] -= np.rint(fractional[:, self.periodic])
            return np.einsum("ij,ij->i", fractional, fractional, optimize=True)
        if not self.pbc_aware or not np.any(self.periodic):
            return np.einsum("ij,ij->i", vectors, vectors, optimize=True)
        if self.reduced_cell is None:
            fractional[:, self.periodic] -= np.rint(fractional[:, self.periodic])
            delta = fractional @ self.cell
            return np.einsum("ij,ij->i", delta, delta, optimize=True)

        if self.naive_safe_squared is not None:
            fractional[:, self.periodic] -= np.rint(fractional[:, self.periodic])
            naive = fractional @ self.cell
            result = np.einsum("ij,ij->i", naive, naive, optimize=True)
            unsafe = result >= self.naive_safe_squared
            if not np.any(unsafe):
                return result
            general_vectors = vectors[unsafe]
        else:
            result = np.empty(len(vectors), dtype=float)
            unsafe = np.ones(len(vectors), dtype=bool)
            general_vectors = vectors

        reduced_fractional = general_vectors @ self.reduced_inverse
        reduced_fractional[:, self.periodic] %= 1.0
        wrapped = reduced_fractional @ self.reduced_cell
        images = wrapped[None, :, :] + self.neighbor_vectors[:, None, :]
        squared = np.einsum("sni,sni->sn", images, images, optimize=True)
        result[unsafe] = np.min(squared, axis=0)
        return result


class _EuclideanInsertionMetric:
    def squared(self, points: np.ndarray, reference: np.ndarray) -> np.ndarray:
        vectors = np.asarray(points, dtype=float) - np.asarray(reference, dtype=float)
        return np.einsum("ij,ij->i", vectors, vectors, optimize=True)


def _greedy_maximin_indices(
    candidates: np.ndarray,
    count: int,
    *,
    metric: Any,
    center: np.ndarray,
) -> np.ndarray:
    """Select a deterministic, space-filling subset from candidate points."""
    requested = int(count)
    if requested >= len(candidates):
        return np.arange(len(candidates), dtype=int)
    first = int(np.argmin(metric.squared(candidates, center)))
    chosen = np.empty(requested, dtype=int)
    chosen[0] = first
    available = np.ones(len(candidates), dtype=bool)
    available[first] = False
    minimum = metric.squared(candidates, candidates[first])
    minimum[first] = -1.0
    for index in range(1, requested):
        selected = int(np.argmax(minimum))
        chosen[index] = selected
        available[selected] = False
        current = metric.squared(candidates, candidates[selected])
        np.minimum(minimum, current, out=minimum)
        minimum[~available] = -1.0
    return chosen


def _placement_quality(
    positions: np.ndarray,
    *,
    domain: InsertionDomain,
    metric: Any,
    seed: int,
) -> dict[str, float]:
    """Return physical spacing and void-coverage diagnostics.

    Nearest-neighbor values are exact for the placed points.  The covering
    radius is evaluated on a deterministic low-discrepancy probe set, making
    it suitable as a regression metric without introducing stochastic output.
    """
    values = np.asarray(positions, dtype=float)
    if len(values) < 2:
        return {
            "nearest_distance_min": 0.0,
            "nearest_distance_mean": 0.0,
            "nearest_distance_cv": 0.0,
            "covering_radius_estimate": 0.0,
        }
    nearest_squared = np.full(len(values), np.inf, dtype=float)
    for index, reference in enumerate(values):
        distances = metric.squared(values, reference)
        distances[index] = np.inf
        nearest_squared[index] = float(np.min(distances))
    nearest = np.sqrt(np.maximum(nearest_squared, 0.0))

    probe_count = min(8192, max(2048, len(values) * 16))
    probes, _ = domain.sobol_points(
        probe_count,
        coordinate_basis="cartesian",
        seed=int(seed),
    )
    probe_minimum = np.full(len(probes), np.inf, dtype=float)
    for reference in values:
        np.minimum(probe_minimum, metric.squared(probes, reference), out=probe_minimum)
    mean = float(np.mean(nearest))
    return {
        "nearest_distance_min": float(np.min(nearest)),
        "nearest_distance_mean": mean,
        "nearest_distance_cv": float(np.std(nearest) / mean) if mean > 0 else 0.0,
        "covering_radius_estimate": float(np.sqrt(np.max(np.maximum(probe_minimum, 0.0)))),
    }


def _regular_grid_candidates(
    lower: np.ndarray,
    upper: np.ndarray,
    spacing: float,
    *,
    maximum: int = 2_000_000,
) -> np.ndarray:
    axes: list[np.ndarray] = []
    for axis in range(3):
        extent = float(upper[axis] - lower[axis])
        if extent <= 0:
            raise ValueError("Regular placement requires a finite 3D domain.")
        count = max(1, int(math.floor(extent / spacing)) + 1)
        # Centering leaves equal margin on both sides while preserving the
        # requested Cartesian spacing exactly.
        width = (count - 1) * spacing
        start = 0.5 * float(lower[axis] + upper[axis] - width)
        axes.append(start + np.arange(count, dtype=float) * spacing)
    candidate_count = int(np.prod([len(axis) for axis in axes], dtype=np.int64))
    if candidate_count > maximum:
        raise ValueError(
            "Regular spacing creates more than 2,000,000 candidate sites. "
            "Increase the spacing or reduce the insertion region."
        )
    mesh = np.meshgrid(*axes, indexing="ij")
    return np.column_stack([component.reshape(-1) for component in mesh])


def sample_regular_positions(
    cell: Any,
    pbc: Sequence[bool],
    count: int,
    *,
    region_mode: str = "cell",
    bounds: Sequence[Any] | None = None,
    region_role: str = "allowed",
    regions: Sequence[InsertionRegion] | Sequence[dict[str, Any]] | None = None,
    pbc_aware: bool = True,
    region_mic: bool = False,
    spacing: float | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Place entities on a global Cartesian lattice clipped to the domain.

    An explicit spacing is never silently changed.  Automatic spacing is
    reduced deterministically until the exact requested count can be selected.
    For irregular Boolean regions, a Cartesian-lattice subset is selected by
    the same physical maximin metric used by homogeneous placement.
    """
    requested = _validated_count(count)
    normalized_regions = (
        tuple(regions)
        if regions is not None and all(isinstance(region, InsertionRegion) for region in regions)
        else normalize_insertion_regions(
            regions,
            legacy_mode=region_mode,
            legacy_bounds=bounds,
            legacy_role=region_role,
        )
    )
    domain = build_insertion_domain(
        cell=cell,
        pbc=pbc,
        regions=normalized_regions,
        pbc_aware=region_mic,
    )
    lower, upper = _bounds_arrays(domain.base_bounds)
    explicit = spacing not in (None, "")
    if explicit:
        selected_spacing = float(spacing)
        if not np.isfinite(selected_spacing) or selected_spacing <= 0:
            raise ValueError("Regular Cartesian spacing must be a positive finite value in angstrom.")
    else:
        selected_spacing = float((domain.volume / requested) ** (1.0 / 3.0))
        selected_spacing = max(selected_spacing, 1e-6)

    candidates = np.empty((0, 3), dtype=float)
    attempted = 0
    iterations = 1 if explicit else 80
    for _ in range(iterations):
        grid = _regular_grid_candidates(lower, upper, selected_spacing)
        attempted += len(grid)
        mask = domain.contains(grid)
        if domain.cell is not None and np.any(domain.pbc):
            fractional = grid @ np.linalg.inv(domain.cell)
            mask &= np.all(
                (~domain.pbc)[None, :]
                | ((fractional >= -1e-10) & (fractional < 1.0 - 1e-10)),
                axis=1,
            )
        candidates = grid[mask]
        if len(candidates) >= requested:
            break
        if explicit:
            break
        selected_spacing *= 0.96
    if len(candidates) < requested:
        raise ValueError(
            f"Regular spacing {selected_spacing:.6g} A provides only {len(candidates)} accessible "
            f"sites for {requested} requested entities. Reduce the spacing or enlarge the Allow region."
        )

    metric = (
        _InsertionDistanceMetric(domain.cell, pbc, "cartesian", pbc_aware)
        if domain.cell is not None
        else _EuclideanInsertionMetric()
    )
    center = 0.5 * (lower + upper)
    if requested <= MAX_EXACT_HOMOGENEOUS_ENTITIES:
        chosen = _greedy_maximin_indices(
            candidates,
            requested,
            metric=metric,
            center=center,
        )
    else:
        # The full grid remains deterministic and regular.  Evenly spaced
        # indices avoid the severe leading-corner bias of candidates[:count].
        chosen = np.floor(
            np.arange(requested, dtype=float) * len(candidates) / requested
        ).astype(int)
    positions = candidates[chosen].copy()
    diagnostics: dict[str, Any] = {
        "attempted": int(attempted),
        "candidate_sites": int(len(candidates)),
        "accepted": int(requested),
        "acceptance_fraction": float(len(candidates) / max(1, attempted)),
        "placement_algorithm": "cartesian-regular-grid",
        "coordinate_basis": "cartesian",
        "pbc_aware": bool(pbc_aware),
        "regular_spacing_angstrom": float(selected_spacing),
        "regular_spacing_mode": "manual" if explicit else "automatic",
    }
    if requested <= MAX_EXACT_HOMOGENEOUS_ENTITIES:
        diagnostics.update(_placement_quality(
            positions,
            domain=domain,
            metric=metric,
            seed=911,
        ))
    return positions, diagnostics


def _metric_distance_squared(
    points: np.ndarray,
    reference: np.ndarray,
    *,
    cell: np.ndarray,
    pbc: Sequence[bool],
    coordinate_basis: str,
    pbc_aware: bool,
) -> np.ndarray:
    metric = _InsertionDistanceMetric(cell, pbc, coordinate_basis, pbc_aware)
    return metric.squared(points, reference)


def sample_homogeneous_positions(
    cell: Any,
    pbc: Sequence[bool],
    count: int,
    *,
    coordinate_basis: str = "cartesian",
    region_mode: str = "cell",
    bounds: Sequence[Any] | None = None,
    region_role: str = "allowed",
    regions: Sequence[InsertionRegion] | Sequence[dict[str, Any]] | None = None,
    pbc_aware: bool = True,
    region_mic: bool = False,
    seed: int | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return a reproducible homogeneous point set for one insertion region.

    Up to ``MAX_EXACT_HOMOGENEOUS_ENTITIES`` points use greedy maximin
    selection from a low-discrepancy candidate pool.  Larger requests keep the
    bounded-memory low-discrepancy sequence directly.  Cartesian mode ranks
    Euclidean distances in angstrom; fractional mode ranks normalized lattice
    coordinates.  Periodic dimensions use MIC only when requested.
    """
    requested = _validated_count(count)
    basis = _normalize_coordinate_basis(coordinate_basis)
    normalized_regions = (
        tuple(regions)
        if regions is not None and all(isinstance(region, InsertionRegion) for region in regions)
        else normalize_insertion_regions(
            regions,
            legacy_mode=region_mode,
            legacy_bounds=bounds,
            legacy_role=region_role,
        )
    )
    domain = build_insertion_domain(
        cell=cell,
        pbc=pbc,
        regions=normalized_regions,
        pbc_aware=region_mic,
    )
    matrix = domain.cell
    if requested <= 128:
        pool_factor = 20
    elif requested <= 512:
        pool_factor = 12
    elif requested <= MAX_EXACT_HOMOGENEOUS_ENTITIES:
        pool_factor = 6
    else:
        pool_factor = 1
    pool_target = min(200_000, max(requested, requested * pool_factor, 2048))
    effective_seed = 0 if seed is None else int(seed)
    candidates, attempted = domain.sobol_points(
        pool_target,
        coordinate_basis=basis,
        seed=effective_seed,
    )
    if requested > MAX_EXACT_HOMOGENEOUS_ENTITIES:
        return candidates[:requested].copy(), {
            "attempted": int(attempted),
            "accepted": int(requested),
            "acceptance_fraction": float(len(candidates) / max(1, attempted)),
            "placement_algorithm": "low-discrepancy",
            "coordinate_basis": basis,
            "pbc_aware": bool(pbc_aware),
        }

    domain_lower, domain_upper = _bounds_arrays(domain.base_bounds)
    center = 0.5 * (domain_lower + domain_upper)
    metric = (
        _InsertionDistanceMetric(matrix, pbc, basis, pbc_aware)
        if matrix is not None
        else _EuclideanInsertionMetric()
    )
    chosen = _greedy_maximin_indices(
        candidates,
        requested,
        metric=metric,
        center=center,
    )
    positions = candidates[chosen].copy()
    diagnostics: dict[str, Any] = {
        "attempted": int(attempted),
        "accepted": int(requested),
        "acceptance_fraction": float(len(candidates) / max(1, attempted)),
        "placement_algorithm": "maximin-low-discrepancy",
        "coordinate_basis": basis,
        "pbc_aware": bool(pbc_aware),
    }
    diagnostics.update(_placement_quality(
        positions,
        domain=domain,
        metric=metric,
        seed=effective_seed + 1,
    ))
    diagnostics["spacing_metric"] = "angstrom" if basis == "cartesian" else "fractional"
    return positions, diagnostics


def sample_insertion_positions(
    cell: Any,
    pbc: Sequence[bool],
    count: int,
    *,
    placement_mode: str = "random",
    coordinate_basis: str = "cartesian",
    region_mode: str = "cell",
    bounds: Sequence[Any] | None = None,
    region_role: str = "allowed",
    regions: Sequence[InsertionRegion] | Sequence[dict[str, Any]] | None = None,
    pbc_aware: bool = True,
    region_mic: bool = False,
    seed: int | None = None,
    regular_spacing: float | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    placement = _normalize_placement_mode(placement_mode)
    basis = _normalize_coordinate_basis(coordinate_basis)
    normalized_regions = (
        tuple(regions)
        if regions is not None and all(isinstance(region, InsertionRegion) for region in regions)
        else normalize_insertion_regions(
            regions,
            legacy_mode=region_mode,
            legacy_bounds=bounds,
            legacy_role=region_role,
        )
    )
    domain = build_insertion_domain(
        cell=cell,
        pbc=pbc,
        regions=normalized_regions,
        pbc_aware=region_mic,
    )
    if placement == "regular":
        positions, diagnostics = sample_regular_positions(
            cell,
            pbc,
            count,
            region_mode=region_mode,
            bounds=bounds,
            region_role=region_role,
            regions=normalized_regions,
            pbc_aware=pbc_aware,
            region_mic=region_mic,
            spacing=regular_spacing,
        )
        diagnostics.update({
            "placement_mode": "regular",
            "region_mode": region_mode,
            "region_role": region_role,
            "accessible_volume_angstrom3": domain.volume,
        })
        return positions, diagnostics
    if placement == "homogeneous":
        positions, diagnostics = sample_homogeneous_positions(
            cell,
            pbc,
            count,
            coordinate_basis=basis,
            region_mode=region_mode,
            bounds=bounds,
            region_role=region_role,
            regions=normalized_regions,
            pbc_aware=pbc_aware,
            region_mic=region_mic,
            seed=seed,
        )
        diagnostics.update({
            "placement_mode": "homogeneous",
            "region_mode": region_mode,
            "region_role": region_role,
        })
        diagnostics["accessible_volume_angstrom3"] = domain.volume
        return positions, diagnostics
    positions, diagnostics = domain.random_points(count, seed=seed)
    diagnostics.update({
        "placement_mode": "random",
        "placement_algorithm": "random",
        "coordinate_basis": basis,
        "pbc_aware": bool(pbc_aware),
        "region_mode": region_mode,
        "region_role": region_role,
        "accessible_volume_angstrom3": domain.volume,
    })
    return positions, diagnostics


def _validated_count(value: Any) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("Atom count must be an integer.")
    if isinstance(value, (int, np.integer)):
        count = int(value)
    elif isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        count = int(value)
    else:
        raise ValueError("Atom count must be an integer.")
    if count < 1 or count > MAX_RANDOM_ATOMS:
        raise ValueError(f"Atom count must be from 1 through {MAX_RANDOM_ATOMS:,}.")
    return count


def _validated_molecule_count(value: Any) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("Molecule count must be an integer.")
    if isinstance(value, (int, np.integer)):
        count = int(value)
    elif isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        count = int(value)
    else:
        raise ValueError("Molecule count must be an integer.")
    if count < 1 or count > MAX_MOLECULES:
        raise ValueError(f"Molecule count must be from 1 through {MAX_MOLECULES:,}.")
    return count


@lru_cache(maxsize=1)
def molecule_catalog() -> tuple[dict[str, Any], ...]:
    """Return the installed ASE G2 molecule catalog with stable metadata."""
    catalog: list[dict[str, Any]] = []
    for name in g2.names:
        template = molecule(name)
        symbols = template.get_chemical_symbols()
        catalog.append({
            "name": str(name),
            "formula": template.get_chemical_formula(mode="hill"),
            "atom_count": len(template),
            "elements": sorted(set(symbols)),
        })
    return tuple(catalog)


def normalize_molecule_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_entries = payload.get("molecules") or payload.get("molecule_entries")
    if raw_entries is None and payload.get("molecule"):
        raw_entries = [{
            "name": payload.get("molecule"),
            "label": payload.get("label") or payload.get("molecule"),
            "count": payload.get("count", 1),
        }]
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("molecules must contain at least one molecule specification.")
    available = {entry["name"] for entry in molecule_catalog()}
    normalized: list[dict[str, Any]] = []
    total_molecules = 0
    total_atoms = 0
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("Each molecule entry must be an object.")
        name = str(raw.get("name") or raw.get("molecule") or "").strip()
        if name not in available:
            raise ValueError(
                f"ASE molecule '{name}' is unavailable. Query the molecule catalog before retrying."
            )
        count = _validated_molecule_count(raw.get("count", 1))
        label = normalize_atom_type_label(raw.get("label") or name)
        label = re.sub(r"[^A-Za-z0-9_.+-]+", "_", label).strip("_") or name
        template = molecule(name)
        total_molecules += count
        total_atoms += count * len(template)
        if total_molecules > MAX_MOLECULES:
            raise ValueError(f"Total molecule count cannot exceed {MAX_MOLECULES:,}.")
        if total_atoms > MAX_RANDOM_ATOMS:
            raise ValueError(f"Total inserted atom count cannot exceed {MAX_RANDOM_ATOMS:,}.")
        normalized.append({
            "name": name,
            "label": label,
            "count": count,
            "atom_count": len(template),
            "formula": template.get_chemical_formula(mode="hill"),
        })
    return normalized


def molecule_molar_mass(name: str) -> float:
    template = molecule(str(name))
    return float(sum(atomic_masses[number] for number in template.numbers))


def resolve_molecule_density(
    entries: Sequence[dict[str, Any]],
    *,
    target_density_g_cm3: Any,
    accessible_volume_angstrom3: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Scale molecular composition ratios to the nearest realizable density."""
    try:
        target_density = float(target_density_g_cm3)
    except (TypeError, ValueError) as exc:
        raise ValueError("Target molecular density must be numeric in g/cm^3.") from exc
    volume = float(accessible_volume_angstrom3)
    if not np.isfinite(target_density) or target_density <= 0.0 or target_density > 100.0:
        raise ValueError("Target molecular density must be greater than 0 and at most 100 g/cm^3.")
    if not np.isfinite(volume) or volume <= _CELL_TOLERANCE:
        raise ValueError("Molecular density requires a positive accessible insertion volume.")

    raw_ratios = [int(entry["count"]) for entry in entries]
    ratio_divisor = 0
    for ratio in raw_ratios:
        ratio_divisor = math.gcd(ratio_divisor, ratio)
    primitive_ratios = [ratio // max(1, ratio_divisor) for ratio in raw_ratios]

    batch_molar_mass = 0.0
    batch_molecules = 0
    batch_atoms = 0
    for entry, ratio in zip(entries, primitive_ratios):
        batch_molar_mass += ratio * molecule_molar_mass(str(entry["name"]))
        batch_molecules += ratio
        batch_atoms += ratio * int(entry["atom_count"])
    batch_mass_grams = batch_molar_mass / Avogadro
    target_mass_grams = target_density * volume * 1e-24
    multiplier = int(math.floor(target_mass_grams / batch_mass_grams + 0.5))
    if multiplier < 1:
        first_density = batch_mass_grams / (volume * 1e-24)
        raise ValueError(
            "The target density corresponds to fewer than one composition batch in the "
            f"accessible volume. The first realizable density is {first_density:.6g} g/cm^3."
        )
    if multiplier * batch_molecules > MAX_MOLECULES:
        raise ValueError(f"Density placement cannot exceed {MAX_MOLECULES:,} molecules.")
    if multiplier * batch_atoms > MAX_RANDOM_ATOMS:
        raise ValueError(f"Density placement cannot exceed {MAX_RANDOM_ATOMS:,} inserted atoms.")
    resolved = [
        {
            **entry,
            "requested_ratio": int(entry["count"]),
            "ratio": ratio,
            "count": ratio * multiplier,
        }
        for entry, ratio in zip(entries, primitive_ratios)
    ]
    actual_mass_grams = multiplier * batch_mass_grams
    actual_density = actual_mass_grams / (volume * 1e-24)
    return resolved, {
        "mode": "density",
        "target_g_cm3": target_density,
        "actual_g_cm3": float(actual_density),
        "accessible_volume_angstrom3": volume,
        "composition_multiplier": multiplier,
        "molecule_count": multiplier * batch_molecules,
        "atom_count": multiplier * batch_atoms,
    }


def actual_molecule_density(
    entries: Sequence[dict[str, Any]],
    accessible_volume_angstrom3: float,
) -> float:
    volume = float(accessible_volume_angstrom3)
    if volume <= _CELL_TOLERANCE:
        raise ValueError("Molecular density requires a positive accessible insertion volume.")
    molar_mass = sum(
        int(entry["count"]) * molecule_molar_mass(str(entry["name"]))
        for entry in entries
    )
    return float((molar_mass / Avogadro) / (volume * 1e-24))


def uniform_rotation_matrices(count: int, *, seed: int | None = None) -> np.ndarray:
    """Return Haar-uniform SO(3) matrices using normalized random quaternions."""
    requested = _validated_molecule_count(count)
    generator = np.random.default_rng(seed)
    u1, u2, u3 = generator.random((3, requested))
    qx = np.sqrt(1.0 - u1) * np.sin(2.0 * np.pi * u2)
    qy = np.sqrt(1.0 - u1) * np.cos(2.0 * np.pi * u2)
    qz = np.sqrt(u1) * np.sin(2.0 * np.pi * u3)
    qw = np.sqrt(u1) * np.cos(2.0 * np.pi * u3)
    matrices = np.empty((requested, 3, 3), dtype=float)
    matrices[:, 0, 0] = 1 - 2 * (qy * qy + qz * qz)
    matrices[:, 0, 1] = 2 * (qx * qy - qz * qw)
    matrices[:, 0, 2] = 2 * (qx * qz + qy * qw)
    matrices[:, 1, 0] = 2 * (qx * qy + qz * qw)
    matrices[:, 1, 1] = 1 - 2 * (qx * qx + qz * qz)
    matrices[:, 1, 2] = 2 * (qy * qz - qx * qw)
    matrices[:, 2, 0] = 2 * (qx * qz - qy * qw)
    matrices[:, 2, 1] = 2 * (qy * qz + qx * qw)
    matrices[:, 2, 2] = 1 - 2 * (qx * qx + qy * qy)
    return matrices


def _molecule_atom_labels(symbols: Sequence[str], label: str) -> list[str]:
    suffix = re.sub(r"[^A-Za-z0-9_.+-]+", "_", str(label)).strip("_")
    if not suffix:
        return [str(symbol) for symbol in symbols]
    return [f"{symbol}_{suffix}" for symbol in symbols]


def expand_molecules(
    entries: Sequence[dict[str, Any]],
    anchors: np.ndarray,
    *,
    random_orientation: bool,
    seed: int | None,
) -> dict[str, Any]:
    """Place ASE molecule templates about their native coordinate origin."""
    molecule_count = sum(int(entry["count"]) for entry in entries)
    if len(anchors) != molecule_count:
        raise ValueError("Molecule anchor count does not match the requested molecule count.")
    rotations = (
        uniform_rotation_matrices(molecule_count, seed=seed)
        if random_orientation
        else np.repeat(np.eye(3, dtype=float)[None, :, :], molecule_count, axis=0)
    )
    elements: list[str] = []
    labels: list[str] = []
    positions: list[np.ndarray] = []
    groups: list[list[int]] = []
    references: list[np.ndarray] = []
    names: list[str] = []
    cursor = 0
    entity = 0
    for entry in entries:
        template = molecule(str(entry["name"]))
        reference = np.asarray(template.positions, dtype=float)
        symbols = template.get_chemical_symbols()
        atom_labels_for_template = _molecule_atom_labels(symbols, str(entry["label"]))
        for _ in range(int(entry["count"])):
            transformed = reference @ rotations[entity].T + anchors[entity]
            positions.extend(transformed)
            elements.extend(symbols)
            labels.extend(atom_labels_for_template)
            groups.append(list(range(cursor, cursor + len(template))))
            references.append(reference.copy())
            names.append(str(entry["name"]))
            cursor += len(template)
            entity += 1
    return {
        "elements": elements,
        "labels": labels,
        "positions": np.asarray(positions, dtype=float),
        "groups": groups,
        "references": references,
        "names": names,
    }


def molecule_entry_elements(entries: Sequence[dict[str, Any]]) -> list[str]:
    """Return the chemical elements represented by molecule specifications."""
    values: list[str] = []
    for entry in entries:
        values.extend(molecule(str(entry["name"])).get_chemical_symbols())
    return values


class RigidMoleculeConstraint(FixConstraint):
    """Project many inserted molecules onto independent rigid-body motion.

    Position proposals are aligned to immutable molecular references with a
    proper Kabsch rotation. Atomic forces are orthogonally projected onto the
    rigid-body modes while retaining each molecule's net force and torque.
    """

    def __init__(
        self,
        groups: Sequence[Sequence[int]],
        references: Sequence[np.ndarray],
    ):
        if len(groups) != len(references):
            raise ValueError("Rigid molecule groups and references must have the same length.")
        self.groups = [np.asarray(group, dtype=int) for group in groups]
        self.references = [np.asarray(reference, dtype=float).copy() for reference in references]
        for group, reference in zip(self.groups, self.references):
            if reference.shape != (len(group), 3):
                raise ValueError("Each rigid reference must be an N x 3 array matching its group.")
            if len(set(map(int, group))) != len(group):
                raise ValueError("A rigid molecule group cannot contain duplicate atom indices.")
        self._refresh_batches()

    def _refresh_batches(self) -> None:
        by_size: dict[int, list[int]] = {}
        for index, group in enumerate(self.groups):
            by_size.setdefault(len(group), []).append(index)
        self._batches: list[tuple[np.ndarray, np.ndarray]] = []
        for count, indices in sorted(by_size.items()):
            if count <= 1:
                continue
            self._batches.append((
                np.stack([self.groups[index] for index in indices]),
                np.stack([self.references[index] for index in indices]),
            ))

    @staticmethod
    def _proper_rotation(reference: np.ndarray, target: np.ndarray) -> np.ndarray:
        centered_reference = reference - reference.mean(axis=0)
        centered_target = target - target.mean(axis=0)
        left, _, right_t = np.linalg.svd(centered_reference.T @ centered_target)
        rotation = left @ right_t
        if np.linalg.det(rotation) < 0.0:
            left[:, -1] *= -1.0
            rotation = left @ right_t
        return rotation

    def adjust_positions(self, atoms: Atoms, new: np.ndarray) -> None:
        for groups, references in self._batches:
            proposed = np.asarray(new[groups], dtype=float)
            centered_reference = references - references.mean(axis=1, keepdims=True)
            centered_proposed = proposed - proposed.mean(axis=1, keepdims=True)
            covariance = np.einsum(
                "gni,gnj->gij", centered_reference, centered_proposed, optimize=True
            )
            left, _, right_t = np.linalg.svd(covariance)
            rotation = left @ right_t
            reflected = np.linalg.det(rotation) < 0.0
            if np.any(reflected):
                left[reflected, :, -1] *= -1.0
                rotation[reflected] = left[reflected] @ right_t[reflected]
            aligned = np.einsum(
                "gni,gij->gnj", centered_reference, rotation, optimize=True
            )
            aligned += proposed.mean(axis=1, keepdims=True)
            new[groups.reshape(-1)] = aligned.reshape(-1, 3)

    def adjust_forces(self, atoms: Atoms, forces: np.ndarray) -> None:
        positions = np.asarray(atoms.positions, dtype=float)
        identity = np.eye(3)
        for groups, _ in self._batches:
            group_positions = positions[groups]
            relative = group_positions - group_positions.mean(axis=1, keepdims=True)
            group_forces = np.asarray(forces[groups], dtype=float)
            translation = group_forces.mean(axis=1)
            centered_forces = group_forces - translation[:, None, :]
            torque = np.sum(np.cross(relative, centered_forces), axis=1)
            squared_norm_sum = np.sum(relative * relative, axis=(1, 2))
            outer_sum = np.einsum("gni,gnj->gij", relative, relative, optimize=True)
            inertia = squared_norm_sum[:, None, None] * identity - outer_sum
            angular = np.einsum(
                "gij,gj->gi", np.linalg.pinv(inertia, rcond=1e-12), torque, optimize=True
            )
            projected = translation[:, None, :] + np.cross(angular[:, None, :], relative)
            forces[groups.reshape(-1)] = projected.reshape(-1, 3)

    def get_removed_dof(self, atoms: Atoms) -> int:
        removed = 0
        identity = np.eye(3)
        for reference in self.references:
            count = len(reference)
            if count <= 1:
                continue
            relative = reference - reference.mean(axis=0)
            inertia = np.zeros((3, 3), dtype=float)
            for vector in relative:
                inertia += float(vector @ vector) * identity - np.outer(vector, vector)
            rigid_dof = min(3 * count, 3 + int(np.linalg.matrix_rank(inertia, tol=1e-10)))
            removed += 3 * count - rigid_dof
        return int(removed)

    def index_shuffle(self, atoms: Atoms, ind: Sequence[int]) -> None:
        reverse = {int(old): new for new, old in enumerate(np.asarray(ind, dtype=int))}
        next_groups: list[np.ndarray] = []
        next_references: list[np.ndarray] = []
        for group, reference in zip(self.groups, self.references):
            keep = [offset for offset, index in enumerate(group) if int(index) in reverse]
            if not keep:
                continue
            next_groups.append(np.asarray([reverse[int(group[offset])] for offset in keep], dtype=int))
            next_references.append(reference[keep].copy())
        self.groups = next_groups
        self.references = next_references
        self._refresh_batches()

    def copy(self):
        return RigidMoleculeConstraint(self.groups, self.references)


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
    *,
    molecule_group_ids: Sequence[int] | None = None,
) -> Atoms:
    if len(elements) != len(labels) or len(elements) != len(positions):
        raise ValueError("Elements, labels, and positions must have the same length.")
    result = _copy_atoms_with_calculator(baseline)
    result_labels = atom_labels(result)
    for element, label, position in zip(elements, labels, positions):
        result.append(Atom(base_symbol_for_atom_type(element), position=np.asarray(position, dtype=float)))
        result_labels.append(normalize_atom_type_label(label))
    set_atom_labels(result, result_labels)
    if molecule_group_ids is not None:
        if len(molecule_group_ids) != len(elements):
            raise ValueError("Molecule group ids must match the inserted atom count.")
        existing = baseline.arrays.get(MOLECULE_GROUP_ARRAY)
        base_groups = (
            np.asarray(existing, dtype=np.int64).copy()
            if existing is not None and len(existing) == len(baseline)
            else np.full(len(baseline), -1, dtype=np.int64)
        )
        offset = int(base_groups[base_groups >= 0].max() + 1) if np.any(base_groups >= 0) else 0
        inserted = np.asarray(molecule_group_ids, dtype=np.int64)
        inserted = np.where(inserted >= 0, inserted + offset, -1)
        result.set_array(MOLECULE_GROUP_ARRAY, None)
        result.set_array(
            MOLECULE_GROUP_ARRAY,
            np.concatenate((base_groups, inserted)),
            dtype=np.int64,
        )
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


def rigid_transform_origin(reference: np.ndarray, current: np.ndarray) -> np.ndarray:
    """Recover the transformed ASE template origin from one rigid group."""
    source = np.asarray(reference, dtype=float)
    target = np.asarray(current, dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("Rigid molecule reference and current positions must have matching N x 3 shapes.")
    if len(source) == 1:
        return target[0] - source[0]
    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left, _, right_t = np.linalg.svd(covariance)
    rotation = left @ right_t
    if np.linalg.det(rotation) < 0:
        left[:, -1] *= -1
        rotation = left @ right_t
    return target_center - source_center @ rotation


def project_rigid_groups_to_region(
    positions: np.ndarray,
    *,
    cell: Any,
    pbc: Sequence[bool],
    mode: str,
    bounds: Sequence[Any] | None,
    groups: Sequence[Sequence[int]],
    references: Sequence[np.ndarray],
    prohibited: bool,
) -> np.ndarray:
    """Translate rigid groups so each transformed ASE origin satisfies the region."""
    output = np.asarray(positions, dtype=float).copy()
    if len(groups) != len(references):
        raise ValueError("Rigid molecule groups and references must have the same length.")
    for group, reference in zip(groups, references):
        indices = np.asarray(group, dtype=int)
        origin = rigid_transform_origin(reference, output[indices])
        projected = project_positions_to_region(
            np.asarray([origin], dtype=float),
            cell=cell,
            pbc=pbc,
            mode=mode,
            bounds=bounds,
            indices=[0],
            prohibited=prohibited,
        )[0]
        output[indices] += projected - origin
    return output


def _cartesian_region_penalty(
    point: np.ndarray,
    *,
    region: Sequence[float | None],
    prohibited: bool,
    strength: float,
) -> tuple[float, np.ndarray]:
    energy = 0.0
    force = np.zeros(3, dtype=float)
    if prohibited:
        lower = np.asarray(region[::2], dtype=object)
        upper = np.asarray(region[1::2], dtype=object)
        bounded = np.asarray([
            lower[axis] is not None and upper[axis] is not None
            for axis in range(3)
        ], dtype=bool)
        if not np.any(bounded):
            return energy, force
        inside = all(
            not bounded[axis]
            or float(lower[axis]) < float(point[axis]) < float(upper[axis])
            for axis in range(3)
        )
        if not inside:
            return energy, force
        faces: list[tuple[float, int, float]] = []
        for axis in np.flatnonzero(bounded):
            faces.append((float(point[axis]) - float(lower[axis]), int(axis), -1.0))
            faces.append((float(upper[axis]) - float(point[axis]), int(axis), 1.0))
        distance, axis, direction = min(faces, key=lambda item: item[0])
        force[axis] = strength * distance * direction
        energy = 0.5 * strength * distance**2
        return energy, force

    for axis in range(3):
        coord = float(point[axis])
        lower = region[axis * 2]
        upper = region[axis * 2 + 1]
        if lower is None and upper is None:
            continue
        if not prohibited:
            if lower is not None and coord < float(lower):
                displacement = float(lower) - coord
                force[axis] += strength * displacement
                energy += 0.5 * strength * displacement**2
            if upper is not None and coord > float(upper):
                displacement = coord - float(upper)
                force[axis] -= strength * displacement
                energy += 0.5 * strength * displacement**2
    return energy, force


class AdditionRepulsionCalculator(VAseRepulsionCalculator):
    """Temporary calculator with triclinic cell-boundary forces."""

    def __init__(
        self,
        *args,
        cell_region: bool = False,
        insertion_domain: InsertionDomain | None = None,
        rigid_groups: Sequence[Sequence[int]] | None = None,
        rigid_references: Sequence[np.ndarray] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.cell_region = bool(cell_region)
        self.insertion_domain = insertion_domain
        self.rigid_groups = [list(map(int, group)) for group in (rigid_groups or [])]
        self.rigid_references = [np.asarray(item, dtype=float) for item in (rigid_references or [])]
        if len(self.rigid_groups) != len(self.rigid_references):
            raise ValueError("Rigid molecule groups and references must have the same length.")
        self._rigid_group_by_atom = {
            atom_index: group_index
            for group_index, group in enumerate(self.rigid_groups)
            for atom_index in group
        }

    def _neighbor_pairs(self, atoms: Atoms, min_bondinfo):
        pairs = super()._neighbor_pairs(atoms, min_bondinfo)
        if not self._rigid_group_by_atom:
            return pairs
        return [
            pair for pair in pairs
            if self._rigid_group_by_atom.get(int(pair[0]), -1)
            != self._rigid_group_by_atom.get(int(pair[1]), -2)
        ]

    def _boundary_energy_forces(self, atoms: Atoms):
        energy = 0.0
        forces = np.zeros((len(atoms), 3), dtype=float)
        if (
            self.insertion_domain is None
            and not self.cell_region
            and not any(value is not None for value in self.region)
        ):
            return energy, forces
        grouped = {index for group in self.rigid_groups for index in group}
        tags = atoms.get_tags()
        if self.insertion_domain is not None:
            atom_indices = [
                atom_index
                for atom_index in range(len(atoms))
                if atom_index not in grouped
                and (tags[atom_index] == 3 or self.work_on_relax_atoms_too)
            ]
            if atom_indices:
                current = np.asarray(atoms.positions[atom_indices], dtype=float)
                delta = self.insertion_domain.displacements_to_domain(current)
                forces[atom_indices] += self.k_boundary * delta
                energy += 0.5 * self.k_boundary * float(np.sum(delta * delta))
            for group, reference in zip(self.rigid_groups, self.rigid_references):
                indices = np.asarray(group, dtype=int)
                origin = rigid_transform_origin(reference, atoms.positions[indices])
                delta = self.insertion_domain.displacements_to_domain(
                    np.asarray([origin])
                )[0]
                forces[indices] += self.k_boundary * delta / max(1, len(indices))
                energy += 0.5 * self.k_boundary * float(delta @ delta)
            return energy, forces
        for atom_index, point in enumerate(atoms.positions):
            if atom_index in grouped:
                continue
            if tags[atom_index] != 3 and not self.work_on_relax_atoms_too:
                continue
            atom_energy, atom_force = _cartesian_region_penalty(
                point,
                region=self.region,
                prohibited=self.set_region_as_prohibited,
                strength=self.k_boundary,
            )
            energy += atom_energy
            forces[atom_index] += atom_force
        for group, reference in zip(self.rigid_groups, self.rigid_references):
            indices = np.asarray(group, dtype=int)
            origin = rigid_transform_origin(reference, atoms.positions[indices])
            group_energy, group_force = _cartesian_region_penalty(
                origin,
                region=self.region,
                prohibited=self.set_region_as_prohibited,
                strength=self.k_boundary,
            )
            energy += group_energy
            forces[indices] += group_force / max(1, len(indices))
        if not self.cell_region:
            return energy, forces
        matrix = _finite_cell(atoms.cell.array)
        inverse = np.linalg.inv(matrix)
        reciprocal_gradients = inverse.T
        periodic = np.asarray(atoms.pbc, dtype=bool)
        origins: list[tuple[list[int], np.ndarray]] = []
        for group, reference in zip(self.rigid_groups, self.rigid_references):
            indices = np.asarray(group, dtype=int)
            origins.append((list(group), rigid_transform_origin(reference, atoms.positions[indices])))
        for atom_index, cartesian in enumerate(atoms.positions):
            if atom_index in grouped:
                continue
            if tags[atom_index] != 3 and not self.work_on_relax_atoms_too:
                continue
            point = cartesian @ inverse
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
        for group, origin in origins:
            point = origin @ inverse
            group_force = np.zeros(3, dtype=float)
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
                    group_force += self.k_boundary * distance * normal
                    energy += 0.5 * self.k_boundary * distance**2
                elif point[axis] > 1.0:
                    distance = (float(point[axis]) - 1.0) / gradient_norm
                    group_force -= self.k_boundary * distance * normal
                    energy += 0.5 * self.k_boundary * distance**2
            indices = np.asarray(group, dtype=int)
            forces[indices] += group_force / max(1, len(indices))
        return energy, forces


@dataclass
class AtomAdditionSession:
    session_id: str
    baseline_atoms: Atoms
    frame_index: int
    history_index: int
    redo_before: list[Any]
    domain: InsertionDomain
    regions: list[InsertionRegion]
    allow_escape: bool
    entries: list[dict[str, Any]]
    elements: list[str]
    labels: list[str]
    new_indices: list[int]
    pair_cutoffs: dict[str, float]
    cutoff_basis: str
    cutoff_scale: float
    seed: int | None
    content_kind: str = "atoms"
    placement_mode: str = "random"
    regular_spacing: float | None = None
    coordinate_basis: str = "cartesian"
    pbc_aware: bool = True
    random_orientation: bool = True
    rigid_molecules: bool = True
    molecule_groups: list[list[int]] = field(default_factory=list)
    molecule_references: list[np.ndarray] = field(default_factory=list, repr=False)
    molecule_names: list[str] = field(default_factory=list)
    molecule_group_ids: list[int] = field(default_factory=list)
    density: dict[str, Any] | None = None
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

    @property
    def region_mode(self) -> str:
        return "regions" if self.regions else "cell"

    @property
    def bounds(self) -> list[float]:
        if self.regions:
            return list(self.regions[0].bounds)
        if self.domain.cell is not None:
            return cell_cartesian_bounds(self.domain.cell)
        return list(self.domain.base_bounds)

    @property
    def region_role(self) -> str:
        if not self.regions:
            return "allowed"
        return "prohibited" if self.regions[0].role == "reject" else "allowed"

    def summary(self) -> dict[str, Any]:
        return {
            "schema": ADD_ATOMS_SCHEMA,
            "id": self.session_id,
            "active": True,
            "status": self.status,
            "region_mode": self.region_mode,
            "bounds": list(self.bounds),
            "region_role": self.region_role,
            "regions": [region.to_json() for region in self.regions],
            "domain": self.domain.to_json(),
            "accessible_volume_angstrom3": self.domain.volume,
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
            "content_kind": self.content_kind,
            "placement_mode": self.placement_mode,
            "regular_spacing": self.regular_spacing,
            "coordinate_basis": self.coordinate_basis,
            "pbc_aware": self.pbc_aware,
            "random_orientation": self.random_orientation,
            "rigid_molecules": self.rigid_molecules,
            "molecule_count": len(self.molecule_groups),
            "molecule_groups": [list(group) for group in self.molecule_groups],
            "molecule_names": list(self.molecule_names),
            "density": dict(self.density) if self.density else None,
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


def insertion_domain_from_payload(atoms: Atoms, payload: dict[str, Any]) -> InsertionDomain:
    mode = str(payload.get("region_mode") or "cell").strip().lower()
    if mode not in {"cell", "box", "regions"}:
        raise ValueError("region_mode must be cell, box, or regions.")
    legacy_bounds = payload.get("bounds")
    if mode == "box" and legacy_bounds is None:
        matrix = finite_cell_or_none(atoms.cell.array)
        if matrix is None:
            raise ValueError(
                "A structure without a finite unit cell requires explicit Cartesian box bounds."
            )
        legacy_bounds = cell_cartesian_bounds(matrix)
    regions = normalize_insertion_regions(
        payload.get("regions"),
        legacy_mode=mode,
        legacy_bounds=legacy_bounds,
        legacy_role=payload.get("region_role") or "allowed",
    )
    return build_insertion_domain(
        cell=atoms.cell.array,
        pbc=atoms.pbc,
        regions=regions,
        pbc_aware=bool(payload.get("region_mic", payload.get("mic", True))),
    )


def atom_addition_domain_preview(atoms: Atoms, payload: dict[str, Any]) -> dict[str, Any]:
    domain = insertion_domain_from_payload(atoms, payload)
    result: dict[str, Any] = {"domain": domain.to_json()}
    content_kind = str(payload.get("content_kind") or "atoms").strip().lower()
    quantity_mode = str(payload.get("molecule_quantity_mode") or "count").strip().lower()
    if content_kind == "molecules" and quantity_mode == "density":
        entries = normalize_molecule_entries(payload)
        try:
            resolved, density = resolve_molecule_density(
                entries,
                target_density_g_cm3=payload.get("target_density_g_cm3"),
                accessible_volume_angstrom3=domain.volume,
            )
        except ValueError as exc:
            # Keep the exact volume visible while the target or composition is
            # adjusted to a realizable integer molecule count.
            result["density_error"] = str(exc)
        else:
            result["density"] = density
            result["resolved_molecules"] = resolved
    return result


def start_atom_addition(session: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if getattr(session, "atom_addition", None) is not None:
        raise ValueError("Finish or cancel the active Add Atoms session first.")
    if getattr(session, "is_relaxing", False):
        raise ValueError("Stop the active structure relaxation before adding atoms.")
    if getattr(session, "trajectory_source", None) is not None or int(
        getattr(session, "frame_count", 1)
    ) > 1:
        raise ValueError(
            "Batch atom and molecule insertion requires a single structure. Open the target "
            "trajectory frame in a new tab before starting Add Atoms."
        )

    baseline = _copy_atoms_with_calculator(session.working_atoms)
    domain = insertion_domain_from_payload(baseline, payload)
    content_kind = str(payload.get("content_kind") or "atoms").strip().lower()
    if content_kind not in {"atoms", "molecules"}:
        raise ValueError("content_kind must be atoms or molecules.")
    placement_mode = _normalize_placement_mode(payload.get("placement_mode"))
    coordinate_basis = _normalize_coordinate_basis(payload.get("coordinate_basis"))
    regular_spacing_value = payload.get("regular_spacing")
    regular_spacing = None
    if regular_spacing_value not in (None, ""):
        regular_spacing = float(regular_spacing_value)
        if not np.isfinite(regular_spacing) or regular_spacing <= 0:
            raise ValueError("Regular Cartesian spacing must be positive or left blank for Auto.")
    pbc_aware = bool(payload.get("pbc_aware", True))
    allow_escape = bool(payload.get("allow_escape", True))
    seed = _random_seed(payload.get("seed"))
    random_orientation = bool(payload.get("random_orientation", True))
    rigid_molecules = bool(payload.get("rigid_molecules", True))
    molecule_groups: list[list[int]] = []
    molecule_references: list[np.ndarray] = []
    molecule_names: list[str] = []
    molecule_group_ids: list[int] = []
    density: dict[str, Any] | None = None
    if content_kind == "molecules":
        entries = normalize_molecule_entries(payload)
        quantity_mode = str(payload.get("molecule_quantity_mode") or "count").strip().lower()
        if quantity_mode not in {"count", "density"}:
            raise ValueError("molecule_quantity_mode must be count or density.")
        if quantity_mode == "density":
            entries, density = resolve_molecule_density(
                entries,
                target_density_g_cm3=payload.get("target_density_g_cm3"),
                accessible_volume_angstrom3=domain.volume,
            )
        entity_count = sum(int(entry["count"]) for entry in entries)
        anchors, sampling = sample_insertion_positions(
            baseline.cell.array,
            baseline.pbc,
            entity_count,
            placement_mode=placement_mode,
            coordinate_basis=coordinate_basis,
            region_mode="regions",
            regions=domain.regions,
            pbc_aware=pbc_aware,
            region_mic=domain.pbc_aware,
            seed=seed,
            regular_spacing=regular_spacing,
        )
        expanded = expand_molecules(
            entries,
            anchors,
            random_orientation=random_orientation,
            seed=None if seed is None else (seed + 1) % (np.iinfo(np.uint32).max + 1),
        )
        elements = expanded["elements"]
        labels = expanded["labels"]
        positions = expanded["positions"]
        molecule_references = expanded["references"]
        molecule_names = expanded["names"]
        for group_index, group in enumerate(expanded["groups"]):
            molecule_groups.append([len(baseline) + index for index in group])
            molecule_group_ids.extend([group_index] * len(group))
    else:
        entries = normalize_add_entries(payload)
        elements, labels = expanded_entry_values(entries)
        entity_count = len(elements)
        positions, sampling = sample_insertion_positions(
            baseline.cell.array,
            baseline.pbc,
            entity_count,
            placement_mode=placement_mode,
            coordinate_basis=coordinate_basis,
            region_mode="regions",
            regions=domain.regions,
            pbc_aware=pbc_aware,
            region_mic=domain.pbc_aware,
            seed=seed,
            regular_spacing=regular_spacing,
        )
    sampling["entity_count"] = int(entity_count)
    sampling["content_kind"] = content_kind

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
    working = append_atoms(
        baseline,
        elements,
        labels,
        positions,
        molecule_group_ids=molecule_group_ids if content_kind == "molecules" else None,
    )
    new_indices = list(range(len(baseline), len(working)))
    addition = AtomAdditionSession(
        session_id=str(uuid.uuid4()),
        baseline_atoms=baseline,
        frame_index=int(session.current_frame),
        history_index=history_index,
        redo_before=redo_before,
        domain=domain,
        regions=list(domain.regions),
        allow_escape=allow_escape,
        entries=entries,
        elements=elements,
        labels=labels,
        new_indices=new_indices,
        pair_cutoffs=pair_cutoffs,
        cutoff_basis=basis,
        cutoff_scale=cutoff_scale,
        seed=seed,
        content_kind=content_kind,
        placement_mode=placement_mode,
        regular_spacing=regular_spacing,
        coordinate_basis=coordinate_basis,
        pbc_aware=pbc_aware,
        random_orientation=random_orientation,
        rigid_molecules=rigid_molecules,
        molecule_groups=molecule_groups,
        molecule_references=molecule_references,
        molecule_names=molecule_names,
        molecule_group_ids=molecule_group_ids,
        density=density,
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
    """Update all active Cartesian regions without moving staged atoms."""
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession):
        raise ValueError("There is no active Add Atoms session.")
    with addition.lock:
        if addition.is_relaxing:
            raise ValueError("Stop repulsive placement before changing insertion regions.")
        if "regions" in payload:
            regions = normalize_insertion_regions(payload.get("regions"))
        elif not any(
            key in payload for key in ("region_id", "name", "region_role", "bounds")
        ):
            regions = tuple(addition.regions)
        else:
            if not addition.regions:
                raise ValueError("There is no Cartesian insertion region to update.")
            region_id = str(payload.get("region_id") or addition.regions[0].id)
            regions = []
            found = False
            for region in addition.regions:
                if region.id != region_id:
                    regions.append(region)
                    continue
                found = True
                regions.append(InsertionRegion(
                    id=region.id,
                    name=str(payload.get("name") or region.name),
                    role=(
                        normalize_insertion_regions([{
                            "id": region.id,
                            "name": region.name,
                            "role": payload.get("region_role"),
                            "bounds": payload.get("bounds") or region.bounds,
                        }])[0].role
                        if "region_role" in payload
                        else region.role
                    ),
                    bounds=tuple(normalize_cartesian_bounds(payload.get("bounds") or region.bounds)),
                ))
            if not found:
                raise ValueError(f"Insertion region '{region_id}' was not found.")
            regions = tuple(regions)
        domain = build_insertion_domain(
            cell=addition.baseline_atoms.cell.array,
            pbc=addition.baseline_atoms.pbc,
            regions=regions,
            pbc_aware=bool(payload.get("region_mic", addition.domain.pbc_aware)),
        )
        addition.regions = list(domain.regions)
        addition.domain = domain
        if addition.density:
            addition.density["accessible_volume_angstrom3"] = domain.volume
            addition.density["actual_g_cm3"] = actual_molecule_density(
                addition.entries,
                domain.volume,
            )
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
        expected_count = addition.host_count + len(addition.new_indices)
        if len(current) != expected_count:
            raise ValueError("The active Add Atoms topology changed unexpectedly.")
        expected_indices = list(range(addition.host_count, expected_count))
        if addition.new_indices != expected_indices:
            raise ValueError("The active Add Atoms index mapping changed unexpectedly.")
        if current.get_chemical_symbols()[addition.host_count:] != addition.elements:
            raise ValueError("The staged Add Atoms element mapping changed unexpectedly.")
        if atom_labels(current)[addition.host_count:] != addition.labels:
            raise ValueError("The staged Add Atoms label mapping changed unexpectedly.")
        added_positions = np.asarray(current.positions[addition.new_indices], dtype=float)
        committed = append_atoms(
            addition.baseline_atoms,
            addition.elements,
            addition.labels,
            added_positions,
            molecule_group_ids=(
                addition.molecule_group_ids
                if addition.content_kind == "molecules"
                else None
            ),
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
            "content_kind": addition.content_kind,
            "molecule_count": len(addition.molecule_groups),
        }


def apply_atom_addition_positions(
    session: Any,
    positions: Sequence[Sequence[float]],
) -> dict[str, Any]:
    """Apply an interactive transform to staged atoms without touching the host.

    Add Atoms owns one reversible history entry for its whole staging lifetime,
    so G/R edits update that staged state directly instead of adding nested undo
    entries.  Submitted host coordinates must still match the current host;
    this makes a stale or over-broad client transform fail before mutation.
    """
    addition = getattr(session, "atom_addition", None)
    if not isinstance(addition, AtomAdditionSession):
        raise ValueError("There is no active Add Atoms session.")
    with addition.lock:
        if addition.is_relaxing:
            raise ValueError("Stop repulsive placement before moving inserted atoms.")
        current = session.working_atoms
        proposed = np.asarray(positions, dtype=float)
        if proposed.shape != current.positions.shape or not np.all(np.isfinite(proposed)):
            raise ValueError("Submitted Add Atoms coordinates must be a finite N x 3 array.")
        if addition.host_count and not np.allclose(
            proposed[: addition.host_count],
            current.positions[: addition.host_count],
            rtol=0.0,
            atol=1e-8,
        ):
            raise ValueError("Only atoms inserted by the active Add Atoms session can be moved.")
        if addition.content_kind == "molecules" and addition.rigid_molecules:
            for group, reference in zip(
                addition.molecule_groups,
                addition.molecule_references,
            ):
                indices = np.asarray(group, dtype=int)
                if len(indices) <= 1:
                    continue
                reference_distances = np.linalg.norm(
                    reference[:, None, :] - reference[None, :, :],
                    axis=2,
                )
                proposed_group = proposed[indices]
                proposed_distances = np.linalg.norm(
                    proposed_group[:, None, :] - proposed_group[None, :, :],
                    axis=2,
                )
                if not np.allclose(
                    proposed_distances,
                    reference_distances,
                    rtol=1e-7,
                    atol=1e-7,
                ):
                    raise ValueError(
                        "Preserve molecular geometry is active. Move or rotate each "
                        "inserted molecule as a complete rigid body, or disable that option."
                    )
        updated = np.asarray(current.positions, dtype=float).copy()
        updated[addition.new_indices] = proposed[addition.new_indices]
        current.set_positions(updated, apply_constraint=False)
        session.sync_current_frame()
        return addition.summary()


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
    rigid_groups: list[list[int]] = []
    rigid_references: list[np.ndarray] = []
    if addition.content_kind == "molecules" and addition.rigid_molecules:
        for group, reference in zip(addition.molecule_groups, addition.molecule_references):
            rigid_groups.append(list(group))
            rigid_references.append(np.asarray(reference, dtype=float))
        if rigid_groups:
            constraints.append(RigidMoleculeConstraint(rigid_groups, rigid_references))
    temporary.set_constraint(constraints)
    temporary.calc = AdditionRepulsionCalculator(
        min_bondinfo=pair_cutoffs,
        region=None,
        set_region_as_prohibited=False,
        k_boundary=k_boundary,
        k_repulsion=k_repulsion,
        cutoff_scale=1.0,
        max_force_norm=10.0,
        mic=bool(mic and addition.domain.cell is not None),
        work_on_relax_atoms_too=not addition.freeze_existing,
        cell_region=False,
        insertion_domain=addition.domain if not addition.allow_escape else None,
        rigid_groups=rigid_groups,
        rigid_references=rigid_references,
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
            committed_positions = np.asarray(temporary.positions, dtype=float).copy()
            grouped: set[int] = set()
            if addition.content_kind == "molecules" and addition.rigid_molecules:
                origins = np.asarray([
                    rigid_transform_origin(reference, committed_positions[np.asarray(group, dtype=int)])
                    for group, reference in zip(
                        addition.molecule_groups,
                        addition.molecule_references,
                    )
                ])
                projected_origins = addition.domain.project_points(origins)
                for group, origin, projected in zip(
                    addition.molecule_groups,
                    origins,
                    projected_origins,
                ):
                    committed_positions[np.asarray(group, dtype=int)] += projected - origin
                grouped = {index for group in addition.molecule_groups for index in group}
            ungrouped = [index for index in addition.new_indices if index not in grouped]
            if ungrouped:
                committed_positions[ungrouped] = addition.domain.project_points(
                    committed_positions[ungrouped]
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
        raise ValueError("Start an Add Atoms or Add Molecules session before repulsive placement.")
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
