"""Commensurate in-plane rotation candidates for periodic 2D cells.

The search compares integer supercell boundary matrices after removing the
best rigid in-plane rotation.  The remaining principal stretch is the cell
boundary mismatch shown by the interactive rotate guide.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import Iterable, Sequence

import numpy as np


_AXES = {
    "X": np.array([1.0, 0.0, 0.0]),
    "Y": np.array([0.0, 1.0, 0.0]),
    "Z": np.array([0.0, 0.0, 1.0]),
}


@dataclass(frozen=True)
class ProjectedLattice:
    basis: np.ndarray
    periodic_axes: tuple[int, int]
    axis_alignment: float


def _unit_vector(values: Sequence[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError("Rotation axis must be a finite three-vector.")
    length = float(np.linalg.norm(vector))
    if length <= 1e-12:
        raise ValueError("Rotation axis must be non-zero.")
    return vector / length


def _axis_vector(axis: str | Sequence[float]) -> tuple[str, np.ndarray]:
    if isinstance(axis, str):
        name = axis.upper()
        if name not in _AXES:
            raise ValueError("Commensurate rotation axis must be X, Y, or Z.")
        return name, _AXES[name].copy()
    return "CUSTOM", _unit_vector(axis)


def project_periodic_lattice(
    cell: Sequence[Sequence[float]],
    pbc: Sequence[bool],
    axis: str | Sequence[float],
) -> ProjectedLattice:
    """Project the best pair of periodic cell vectors onto the rotation plane."""

    matrix = np.asarray(cell, dtype=float)
    periodic = np.asarray(pbc, dtype=bool)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("Commensurate rotation requires a finite 3 x 3 cell.")
    if periodic.shape != (3,):
        raise ValueError("Commensurate rotation requires three PBC flags.")
    _, normal = _axis_vector(axis)

    candidates: list[tuple[float, int, int, np.ndarray, np.ndarray, float]] = []
    periodic_indices = np.flatnonzero(periodic)
    for offset, first_index in enumerate(periodic_indices):
        for second_index in periodic_indices[offset + 1 :]:
            first = matrix[first_index]
            second = matrix[second_index]
            first_projected = first - normal * float(np.dot(first, normal))
            second_projected = second - normal * float(np.dot(second, normal))
            projected_area = abs(float(np.dot(np.cross(first_projected, second_projected), normal)))
            original_cross = np.cross(first, second)
            original_area = float(np.linalg.norm(original_cross))
            if projected_area <= 1e-10 or original_area <= 1e-10:
                continue
            alignment = abs(float(np.dot(original_cross / original_area, normal)))
            candidates.append((
                projected_area,
                int(first_index),
                int(second_index),
                first_projected,
                second_projected,
                alignment,
            ))

    if not candidates:
        raise ValueError(
            "Commensurate rotation needs two independent periodic cell vectors "
            "in the plane perpendicular to the locked rotation axis."
        )

    _, first_index, second_index, first, second, alignment = max(candidates, key=lambda item: item[0])
    e1 = first / np.linalg.norm(first)
    e2 = np.cross(normal, e1)
    e2 /= np.linalg.norm(e2)
    basis = np.array([
        [float(np.dot(first, e1)), float(np.dot(first, e2))],
        [float(np.dot(second, e1)), float(np.dot(second, e2))],
    ])
    if np.linalg.det(basis) < 0:
        basis[:, 1] *= -1.0
    return ProjectedLattice(
        basis=basis,
        periodic_axes=(first_index, second_index),
        axis_alignment=alignment,
    )


def _optimal_rotation_and_strain(source: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    """Return signed row-vector rotation angle and maximum principal stretch."""

    covariance = source.T @ target
    left, _, right_t = np.linalg.svd(covariance)
    rotation = left @ right_t
    if np.linalg.det(rotation) < 0:
        left[:, -1] *= -1.0
        rotation = left @ right_t
    rotated = source @ rotation
    deformation = np.linalg.solve(rotated, target)
    principal_stretches = np.linalg.svd(deformation, compute_uv=False)
    strain = float(np.max(np.abs(principal_stretches - 1.0)))
    angle = float(np.degrees(np.arctan2(rotation[0, 1], rotation[0, 0])))
    return _normalize_angle(angle), strain


def _normalize_angle(angle: float) -> float:
    normalized = (float(angle) + 180.0) % 360.0 - 180.0
    if normalized <= -180.0 + 1e-10:
        return 180.0
    return normalized


def _candidate(
    basis: np.ndarray,
    source_matrix: np.ndarray,
    target_matrix: np.ndarray,
    *,
    family: str,
    area: int,
    magic_reference: bool = False,
) -> dict:
    angle, strain = _optimal_rotation_and_strain(source_matrix @ basis, target_matrix @ basis)
    return {
        "angle_deg": angle,
        "strain": strain,
        "area": int(area),
        "source_matrix": np.asarray(source_matrix, dtype=int).tolist(),
        "target_matrix": np.asarray(target_matrix, dtype=int).tolist(),
        "family": family,
        "magic_reference": bool(magic_reference),
    }


def _lattice_family(basis: np.ndarray) -> str:
    first, second = basis
    first_length = float(np.linalg.norm(first))
    second_length = float(np.linalg.norm(second))
    if min(first_length, second_length) <= 1e-12:
        return "oblique"
    length_mismatch = abs(first_length - second_length) / max(first_length, second_length)
    cosine = float(np.dot(first, second) / (first_length * second_length))
    if length_mismatch <= 0.025 and abs(abs(cosine) - 0.5) <= 0.025:
        return "hexagonal"
    if length_mismatch <= 0.025 and abs(cosine) <= 0.025:
        return "square"
    return "oblique"


def _hexagonal_candidates(basis: np.ndarray, max_index: int, carbon_only: bool) -> Iterable[dict]:
    canonical = np.array(basis, copy=True)
    if float(np.dot(canonical[0], canonical[1])) < 0:
        canonical[1] *= -1.0

    # The r=1 commensurate family.  m=31, n=32 gives 1.0501 degrees
    # and a 2977-fold primitive-cell area, the standard first-TBG-magic-angle
    # commensurate approximant.
    for m in range(1, max_index):
        n = m + 1
        source = np.array([[m, n], [-n, m + n]], dtype=int)
        target = np.array([[n, m], [-m, m + n]], dtype=int)
        area = m * m + m * n + n * n
        item = _candidate(
            canonical,
            source,
            target,
            family="hexagonal-r1",
            area=area,
            magic_reference=carbon_only and m == 31,
        )
        yield item
        yield _candidate(
            canonical,
            target,
            source,
            family="hexagonal-r1",
            area=area,
            magic_reference=item["magic_reference"],
        )

    identity = np.eye(2, dtype=int)
    sixty = np.array([[0, 1], [-1, 1]], dtype=int)
    for source, target in ((identity, sixty), (sixty, identity)):
        yield _candidate(canonical, source, target, family="hexagonal-symmetry", area=1)


def _square_candidates(basis: np.ndarray, max_index: int) -> Iterable[dict]:
    limit = min(max_index, 48)
    for m in range(1, limit + 1):
        for n in range(1, m + 1):
            if gcd(m, n) != 1:
                continue
            source = np.array([[m, n], [-n, m]], dtype=int)
            target = np.array([[m, -n], [n, m]], dtype=int)
            area = m * m + n * n
            yield _candidate(basis, source, target, family="square", area=area)
            yield _candidate(basis, target, source, family="square", area=area)


def _gauss_reduce(basis: np.ndarray, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    reduced = np.array(basis, dtype=float, copy=True)
    transform = np.array(matrix, dtype=int, copy=True)
    for _ in range(64):
        if np.dot(reduced[1], reduced[1]) < np.dot(reduced[0], reduced[0]) - 1e-12:
            reduced[[0, 1]] = reduced[[1, 0]]
            transform[[0, 1]] = transform[[1, 0]]
        denominator = float(np.dot(reduced[0], reduced[0]))
        if denominator <= 1e-14:
            break
        multiple = int(np.rint(float(np.dot(reduced[0], reduced[1])) / denominator))
        if multiple == 0:
            break
        reduced[1] -= multiple * reduced[0]
        transform[1] -= multiple * transform[0]
    if np.linalg.det(reduced) < 0:
        reduced[1] *= -1.0
        transform[1] *= -1
    return reduced, transform


def _hnf_matrices(determinant: int) -> Iterable[np.ndarray]:
    for first in range(1, determinant + 1):
        if determinant % first:
            continue
        second = determinant // first
        for offset in range(second):
            yield np.array([[first, offset], [0, second]], dtype=int)


def _generic_candidates(basis: np.ndarray, max_index: int, strain_tolerance: float) -> Iterable[dict]:
    # A bounded CellMatch-style search over inequivalent integer boundary
    # matrices.  Symmetric lattices use the analytic paths above so this
    # generic branch can remain small and interactive.
    max_area = min(72, max(8, max_index * 2))
    screening_tolerance = max(strain_tolerance * 1.5, 0.0025)
    for area in range(1, max_area + 1):
        reduced_cells = []
        for matrix in _hnf_matrices(area):
            reduced, reduced_matrix = _gauss_reduce(matrix @ basis, matrix)
            lengths = np.linalg.norm(reduced, axis=1)
            cosine = float(np.dot(reduced[0], reduced[1]) / max(lengths[0] * lengths[1], 1e-14))
            descriptor = np.array([np.log(lengths[0]), np.log(lengths[1]), cosine])
            reduced_cells.append((reduced, reduced_matrix, descriptor))
        for first_index, (first_cell, first_matrix, first_descriptor) in enumerate(reduced_cells):
            for second_cell, second_matrix, second_descriptor in reduced_cells[first_index + 1 :]:
                if np.max(np.abs(first_descriptor[:2] - second_descriptor[:2])) > screening_tolerance * 2.5:
                    continue
                if abs(first_descriptor[2] - second_descriptor[2]) > screening_tolerance * 3.0:
                    continue
                item = _candidate(
                    basis,
                    first_matrix,
                    second_matrix,
                    family="integer-boundary",
                    area=area,
                )
                if item["strain"] <= strain_tolerance + 1e-12:
                    yield item
                    yield _candidate(
                        basis,
                        second_matrix,
                        first_matrix,
                        family="integer-boundary",
                        area=area,
                    )


def _deduplicate_candidates(candidates: Iterable[dict], strain_tolerance: float) -> list[dict]:
    best: dict[int, dict] = {}
    for item in candidates:
        angle = _normalize_angle(item["angle_deg"])
        strain = float(item["strain"])
        if not np.isfinite(angle) or not np.isfinite(strain):
            continue
        if abs(angle) < 0.025 or strain > strain_tolerance + 1e-9:
            continue
        item = {**item, "angle_deg": round(angle, 8), "strain": round(strain, 12)}
        key = int(round(angle * 200.0))  # 0.005 degree buckets
        previous = best.get(key)
        rank = (strain, int(item["area"]), abs(angle))
        if previous is None or rank < (
            float(previous["strain"]), int(previous["area"]), abs(float(previous["angle_deg"]))
        ):
            best[key] = item
    return sorted(best.values(), key=lambda item: (abs(item["angle_deg"]), item["strain"], item["area"]))


def find_commensurate_angles(
    cell: Sequence[Sequence[float]],
    pbc: Sequence[bool],
    axis: str | Sequence[float],
    *,
    max_index: int = 32,
    strain_tolerance: float = 0.01,
    chemical_symbols: Sequence[str] | None = None,
) -> dict:
    """Find low-strain periodic rotation candidates for the current 2D cell.

    ``strain_tolerance`` is a fraction (``0.01`` means one percent).  Candidate
    strain is the largest absolute principal stretch needed to map the rotated
    source supercell boundary onto its integer target boundary.
    """

    axis_name, _ = _axis_vector(axis)
    if axis_name == "CUSTOM":
        axis_name = "CUSTOM"
    max_index = int(max_index)
    if max_index < 2 or max_index > 64:
        raise ValueError("Max lattice index must be between 2 and 64.")
    strain_tolerance = float(strain_tolerance)
    if not np.isfinite(strain_tolerance) or strain_tolerance < 0 or strain_tolerance > 0.25:
        raise ValueError("Boundary strain tolerance must be between 0 and 0.25.")

    projected = project_periodic_lattice(cell, pbc, axis)
    family = _lattice_family(projected.basis)
    symbols = list(chemical_symbols or [])
    carbon_only = bool(symbols) and all(symbol == "C" for symbol in symbols)

    if family == "hexagonal":
        raw_candidates = _hexagonal_candidates(projected.basis, max_index, carbon_only)
    elif family == "square":
        raw_candidates = _square_candidates(projected.basis, max_index)
    else:
        raw_candidates = _generic_candidates(projected.basis, max_index, strain_tolerance)

    candidates = _deduplicate_candidates(raw_candidates, strain_tolerance)
    warning = None
    if projected.axis_alignment < 0.985:
        warning = (
            "The locked global axis is not normal to the selected periodic cell plane; "
            "candidates use its orthogonal projection."
        )
    return {
        "axis": axis_name,
        "lattice_family": family,
        "periodic_axes": list(projected.periodic_axes),
        "axis_alignment": round(float(projected.axis_alignment), 8),
        "strain_tolerance": strain_tolerance,
        "max_index": max_index,
        "warning": warning,
        "candidates": candidates,
    }
