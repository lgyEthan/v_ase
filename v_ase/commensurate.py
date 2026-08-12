"""Commensurate in-plane rotation candidates for periodic 2D cells.

The search compares integer supercell boundary matrices after removing the
best rigid in-plane rotation.  The remaining principal stretch is the cell
boundary mismatch shown by the interactive rotate guide.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from math import ceil, cos, gcd, radians, sin, sqrt
from typing import Callable, Iterable, Sequence

import numpy as np
from ase.build.supercells import lattice_points_in_supercell


_AXES = {
    "X": np.array([1.0, 0.0, 0.0]),
    "Y": np.array([0.0, 1.0, 0.0]),
    "Z": np.array([0.0, 0.0, 1.0]),
}

_ORIENTED_BASIS_TRANSFORMS = (
    np.array([[1, 0], [0, 1]], dtype=int),
    np.array([[-1, 0], [0, -1]], dtype=int),
    # Signed row swaps cover square reduced bases.
    np.array([[0, 1], [-1, 0]], dtype=int),
    np.array([[0, -1], [1, 0]], dtype=int),
    # Gauss-reduced hexagonal cells can use 60- or 120-degree bases.  These
    # determinant-one shears and their negatives span both descriptions.
    np.array([[1, 0], [1, 1]], dtype=int),
    np.array([[-1, 0], [-1, -1]], dtype=int),
    np.array([[1, 1], [0, 1]], dtype=int),
    np.array([[-1, -1], [0, -1]], dtype=int),
)


@dataclass(frozen=True)
class ProjectedLattice:
    basis: np.ndarray
    periodic_axes: tuple[int, int]
    axis_alignment: float


COMMENSURATE_REFERENCES = (
    {
        "title": "CellMatch: Combining two unit cells into a common supercell with minimal strain",
        "authors": "Lazic",
        "doi": "10.1016/j.cpc.2015.08.038",
    },
    {
        "title": "Method for determining optimal supercell representation of interfaces",
        "authors": "Stradi et al.",
        "doi": "10.1088/1361-648X/aa66f3",
        "arxiv": "1702.00933",
    },
)

TBG_COMMENSURATE_REFERENCE = {
    "title": "Continuum model of the twisted graphene bilayer",
    "authors": "Lopes dos Santos, Peres, and Castro Neto",
    "doi": "10.1103/PhysRevB.86.155449",
}

MAX_LATTICE_MATCH_AREA_RATIO = 128


ProgressCallback = Callable[[float, str], None]


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


def _plane_frame(
    cell: Sequence[Sequence[float]],
    pbc: Sequence[bool],
    axis: str | Sequence[float],
) -> tuple[np.ndarray, np.ndarray, ProjectedLattice]:
    """Return a shared Cartesian frame and the host lattice projected into it."""

    _, normal = _axis_vector(axis)
    projected = project_periodic_lattice(cell, pbc, axis)
    matrix = np.asarray(cell, dtype=float)
    first = matrix[projected.periodic_axes[0]]
    first = first - normal * float(np.dot(first, normal))
    e1 = first / np.linalg.norm(first)
    e2 = np.cross(normal, e1)
    e2 /= np.linalg.norm(e2)
    frame = np.vstack([e1, e2, normal])
    return frame, normal, projected


def project_periodic_lattice_in_frame(
    cell: Sequence[Sequence[float]],
    pbc: Sequence[bool],
    normal: Sequence[float],
    frame: Sequence[Sequence[float]],
) -> ProjectedLattice:
    """Project a second lattice into an existing host-oriented plane frame."""

    matrix = np.asarray(cell, dtype=float)
    periodic = np.asarray(pbc, dtype=bool)
    unit_normal = _unit_vector(normal)
    axes = np.asarray(frame, dtype=float)
    if matrix.shape != (3, 3) or axes.shape != (3, 3):
        raise ValueError("Lattice matching requires finite 3 x 3 cells and a shared frame.")
    e1, e2 = axes[:2]
    candidates: list[tuple[float, int, int, np.ndarray, np.ndarray, float]] = []
    periodic_indices = np.flatnonzero(periodic)
    for offset, first_index in enumerate(periodic_indices):
        for second_index in periodic_indices[offset + 1 :]:
            first = matrix[first_index]
            second = matrix[second_index]
            first_projected = first - unit_normal * float(np.dot(first, unit_normal))
            second_projected = second - unit_normal * float(np.dot(second, unit_normal))
            projected_area = abs(float(np.dot(
                np.cross(first_projected, second_projected), unit_normal
            )))
            original_cross = np.cross(first, second)
            original_area = float(np.linalg.norm(original_cross))
            if projected_area <= 1e-10 or original_area <= 1e-10:
                continue
            alignment = abs(float(np.dot(original_cross / original_area, unit_normal)))
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
            "Guest lattice matching needs two independent periodic cell vectors "
            "in the host in-plane frame."
        )

    _, first_index, second_index, first, second, alignment = max(
        candidates,
        key=lambda item: item[0],
    )
    basis = np.array([
        [float(np.dot(first, e1)), float(np.dot(first, e2))],
        [float(np.dot(second, e1)), float(np.dot(second, e2))],
    ])
    periodic_axes = (first_index, second_index)
    if np.linalg.det(basis) < 0:
        basis = basis[[1, 0]]
        periodic_axes = (second_index, first_index)
    return ProjectedLattice(
        basis=basis,
        periodic_axes=periodic_axes,
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


def _optimal_rotation_deformation(
    source: np.ndarray,
    target: np.ndarray,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Return the proper rotation, principal strain, and row deformation."""

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
    angle = _normalize_angle(float(np.degrees(np.arctan2(rotation[0, 1], rotation[0, 0]))))
    return angle, strain, rotation, deformation


def _deformation_strain_metrics(deformation: np.ndarray) -> dict:
    """Return conservative and paper-compatible in-plane strain measures.

    ``max_principal_strain`` is the largest absolute change in a principal
    stretch and remains the conservative acceptance criterion.  Stradi et al.
    plot the mean absolute small-strain components
    ``(|eps_xx| + |eps_yy| + |eps_xy|) / 3``; that value is retained separately
    so the paper-style projection never changes the cutoff semantics.
    """

    matrix = np.asarray(deformation, dtype=float)
    if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
        raise ValueError("In-plane deformation must be a finite 2 x 2 matrix.")
    principal_stretches = np.linalg.svd(matrix, compute_uv=False)
    linear_strain = 0.5 * (matrix + matrix.T) - np.eye(2)
    max_principal = float(np.max(np.abs(principal_stretches - 1.0)))
    mean_absolute = float(
        (
            abs(linear_strain[0, 0])
            + abs(linear_strain[1, 1])
            + abs(linear_strain[0, 1])
        )
        / 3.0
    )
    return {
        "max_principal_strain": max_principal,
        "mean_absolute_strain": mean_absolute,
        "principal_stretches": principal_stretches.tolist(),
        "linear_strain_tensor_2d": linear_strain.tolist(),
    }


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
    angle, strain, _, deformation = _optimal_rotation_deformation(
        source_matrix @ basis,
        target_matrix @ basis,
    )
    metrics = _deformation_strain_metrics(deformation)
    return {
        "angle_deg": angle,
        "strain": strain,
        **metrics,
        "area": int(area),
        "source_matrix": np.asarray(source_matrix, dtype=int).tolist(),
        "target_matrix": np.asarray(target_matrix, dtype=int).tolist(),
        "family": family,
        "magic_reference": bool(magic_reference),
    }


def _signed_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= 1e-14:
        return 0.0
    cross = float(first[0] * second[1] - first[1] * second[0])
    dot = float(np.dot(first, second))
    return _normalize_angle(float(np.degrees(np.arctan2(cross, dot))))


def _matrix_text(matrix: np.ndarray) -> str:
    rows = [",".join(str(int(value)) for value in row) for row in np.asarray(matrix, dtype=int)]
    return f"[[{rows[0]}],[{rows[1]}]]"


def _supercell_notation(basis: np.ndarray, matrix: np.ndarray) -> str:
    """Return compact surface-science notation when the geometry permits it."""

    matrix = np.asarray(matrix, dtype=int)
    if matrix.shape != (2, 2):
        return _matrix_text(matrix)
    if matrix[0, 1] == 0 and matrix[1, 0] == 0 and matrix[0, 0] > 0 and matrix[1, 1] > 0:
        return f"{matrix[0, 0]} × {matrix[1, 1]}"

    transformed = matrix @ np.asarray(basis, dtype=float)
    original_lengths = np.linalg.norm(basis, axis=1)
    transformed_lengths = np.linalg.norm(transformed, axis=1)
    if np.min(original_lengths) <= 1e-12:
        return _matrix_text(matrix)
    length_scale = transformed_lengths / original_lengths
    determinant = abs(int(round(np.linalg.det(matrix))))
    root = sqrt(determinant)
    source_cosine = float(np.dot(basis[0], basis[1]) / np.prod(original_lengths))
    target_cosine = float(
        np.dot(transformed[0], transformed[1])
        / max(float(np.prod(transformed_lengths)), 1e-14)
    )
    if (
        determinant > 0
        and np.max(np.abs(length_scale - root)) <= 2e-6
        and abs(source_cosine - target_cosine) <= 2e-6
    ):
        multiplier = str(int(round(root))) if abs(root - round(root)) <= 1e-8 else f"√{determinant}"
        rotation = _signed_angle_deg(basis[0], transformed[0])
        if abs(abs(source_cosine) - 0.5) <= 2e-6:
            rotation = (rotation + 30.0) % 60.0 - 30.0
        elif abs(source_cosine) <= 2e-6:
            rotation = (rotation + 45.0) % 90.0 - 45.0
        if abs(rotation) < 5e-8:
            rotation = 0.0
        return f"({multiplier} × {multiplier}) R{rotation:.2f}°"
    return _matrix_text(matrix)


def embed_2d_supercell_matrix(
    matrix: Sequence[Sequence[int]],
    periodic_axes: Sequence[int],
) -> np.ndarray:
    """Embed a 2 x 2 in-plane integer matrix in ASE's 3 x 3 row convention."""

    in_plane = np.asarray(matrix, dtype=int)
    axes = tuple(int(axis) for axis in periodic_axes)
    if in_plane.shape != (2, 2) or len(axes) != 2 or len(set(axes)) != 2:
        raise ValueError("A commensurate supercell needs a 2 x 2 matrix and two periodic axes.")
    if any(axis < 0 or axis > 2 for axis in axes):
        raise ValueError("Periodic cell axes must be between zero and two.")
    embedded = np.eye(3, dtype=int)
    for row, cell_row in enumerate(axes):
        embedded[cell_row, :] = 0
        for column, cell_column in enumerate(axes):
            embedded[cell_row, cell_column] = int(in_plane[row, column])
    return embedded


def row_rotation_matrix(axis: Sequence[float], angle_deg: float) -> np.ndarray:
    """Return a right-handed rotation for row-vector Cartesian coordinates."""

    unit = _unit_vector(axis)
    x, y, z = unit
    angle = radians(float(angle_deg))
    c = cos(angle)
    s = sin(angle)
    one_minus_c = 1.0 - c
    column_rotation = np.array([
        [c + x * x * one_minus_c, x * y * one_minus_c - z * s, x * z * one_minus_c + y * s],
        [y * x * one_minus_c + z * s, c + y * y * one_minus_c, y * z * one_minus_c - x * s],
        [z * x * one_minus_c - y * s, z * y * one_minus_c + x * s, c + z * z * one_minus_c],
    ])
    return column_rotation.T


def enrich_supercell_candidate(
    candidate: dict,
    *,
    cell: Sequence[Sequence[float]],
    periodic_axes: Sequence[int],
    axis: str | Sequence[float],
    projected_basis: np.ndarray,
    axis_alignment: float,
) -> dict:
    """Attach reproducible matrices, common-cell geometry, and paper notation."""

    _, normal = _axis_vector(axis)
    source_2d = np.asarray(candidate["source_matrix"], dtype=int)
    target_2d = np.asarray(candidate["target_matrix"], dtype=int)
    source_3d = embed_2d_supercell_matrix(source_2d, periodic_axes)
    target_3d = embed_2d_supercell_matrix(target_2d, periodic_axes)
    parent_cell = np.asarray(cell, dtype=float)
    source_cell = source_3d @ parent_cell
    target_cell = target_3d @ parent_cell
    rotation = row_rotation_matrix(normal, float(candidate["angle_deg"]))
    rotated_source_cell = source_cell @ rotation
    try:
        deformation = np.linalg.solve(rotated_source_cell, target_cell)
        finite_deformation = bool(np.all(np.isfinite(deformation)))
    except np.linalg.LinAlgError:
        deformation = np.eye(3)
        finite_deformation = False

    source_area = abs(int(round(np.linalg.det(source_2d))))
    target_area = abs(int(round(np.linalg.det(target_2d))))
    supported = bool(
        finite_deformation
        and axis_alignment >= 0.985
        and source_area > 0
        and source_area == target_area
    )
    reason = None
    if axis_alignment < 0.985:
        reason = "The locked axis must be normal to the periodic plane before a common cell can be materialized."
    elif source_area <= 0 or source_area != target_area:
        reason = "The source and reference supercells must have the same positive area."
    elif not finite_deformation:
        reason = "The proposed common-cell deformation is singular."

    periodic_vectors = target_cell[np.asarray(tuple(periodic_axes), dtype=int)]
    lengths = np.linalg.norm(periodic_vectors, axis=1)
    cosine = float(
        np.dot(periodic_vectors[0], periodic_vectors[1])
        / max(float(lengths[0] * lengths[1]), 1e-14)
    )
    angle = float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
    return {
        **candidate,
        "area_ratio": target_area,
        "axis": str(axis).upper() if isinstance(axis, str) else [float(value) for value in normal],
        "periodic_axes": [int(value) for value in periodic_axes],
        "source_matrix_3d": source_3d.tolist(),
        "target_matrix_3d": target_3d.tolist(),
        "source_notation": _supercell_notation(projected_basis, source_2d),
        "target_notation": _supercell_notation(projected_basis, target_2d),
        "source_matrix_text": _matrix_text(source_2d),
        "target_matrix_text": _matrix_text(target_2d),
        "suggested_cell": target_cell.tolist(),
        "deformation_matrix": deformation.tolist(),
        "cell_lengths_angstrom": [round(float(value), 8) for value in lengths],
        "cell_angle_deg": round(angle, 8),
        "supercell_supported": supported,
        "supercell_reason": reason,
        "preview_padding_cells": 1,
    }


def _integer_supercell_lattice_points(
    cell: Sequence[Sequence[float]],
    matrix: Sequence[Sequence[int]],
) -> list[tuple[int, int, int]]:
    """Return primitive-cell translations inside an integer supercell."""

    parent_cell = np.asarray(cell, dtype=float)
    transform = np.asarray(matrix, dtype=int)
    supercell = transform @ parent_cell
    fractional = lattice_points_in_supercell(transform)
    cartesian = fractional @ supercell
    try:
        integer_points = np.rint(cartesian @ np.linalg.inv(parent_cell)).astype(int)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Commensurate supercell requires a non-singular 3D cell.") from exc
    if not np.allclose(integer_points @ parent_cell, cartesian, atol=2e-7):
        raise ValueError("Could not recover integer primitive-cell translations for the proposed cell.")
    return sorted({tuple(int(value) for value in row) for row in integer_points})


def _primitive_halo_points(
    core_points: Sequence[Sequence[int]],
    periodic_axes: Sequence[int],
    padding_cells: int,
) -> list[tuple[tuple[int, int, int], bool]]:
    """Add a primitive-cell shell around a supercell lattice-point set."""

    core = {tuple(int(value) for value in point) for point in core_points}
    if padding_cells <= 0:
        return [(point, True) for point in sorted(core)]
    axes = tuple(int(axis) for axis in periodic_axes)
    offsets = [np.zeros(3, dtype=int)]
    for first in range(-padding_cells, padding_cells + 1):
        for second in range(-padding_cells, padding_cells + 1):
            offset = np.zeros(3, dtype=int)
            offset[axes[0]] = first
            offset[axes[1]] = second
            offsets.append(offset)
    expanded = set(core)
    for point in core:
        source = np.asarray(point, dtype=int)
        for offset in offsets:
            expanded.add(tuple(int(value) for value in source + offset))
    return [(point, point in core) for point in sorted(expanded)]


def _primitive_lattice_window(
    periodic_axes: Sequence[int],
    radius: int,
) -> list[tuple[int, int, int]]:
    """Return a candidate-independent square window of primitive translations."""

    axes = tuple(int(axis) for axis in periodic_axes)
    if len(axes) != 2 or len(set(axes)) != 2:
        raise ValueError("A parent-lattice window requires two distinct periodic axes.")
    extent = max(0, int(radius))
    points: list[tuple[int, int, int]] = []
    for first in range(-extent, extent + 1):
        for second in range(-extent, extent + 1):
            point = np.zeros(3, dtype=int)
            point[axes[0]] = first
            point[axes[1]] = second
            points.append(tuple(int(value) for value in point))
    return points


def _bounded_parent_atom_radius(
    requested_radius: int,
    atoms_per_lattice_cell: int,
    max_preview_atoms: int,
) -> int:
    """Fit a centered parent-lattice atom window inside the preview budget."""

    requested = max(0, int(requested_radius))
    atoms_per_cell = max(1, int(atoms_per_lattice_cell))
    available_cells = max(1, int(max_preview_atoms) // atoms_per_cell)
    maximum_width = max(1, int(sqrt(available_cells)))
    if maximum_width % 2 == 0:
        maximum_width -= 1
    return min(requested, max(0, (maximum_width - 1) // 2))


def _commensurate_grid_padding(area_ratio: int, atom_padding: int) -> int:
    """Return a small visual halo that keeps the common cell inside both grids.

    Atom previews use a deliberately tight halo because their cost scales with
    atom count.  Primitive-cell lines are cheap, so the lattice context extends
    at least one shell farther and grows mildly for unusually large proposals.
    """

    linear_extent = sqrt(max(1, int(area_ratio)))
    return max(int(atom_padding) + 1, min(4, int(ceil(linear_extent / 3.0))))


def _expanded_preview_points(
    components: Sequence[tuple[Sequence[Sequence[int]], Sequence[int], int]],
    *,
    requested_padding: int,
    area_ratio: int,
    include_atoms: bool,
    max_preview_atoms: int,
) -> tuple[list[list[tuple[tuple[int, int, int], bool]]], int, int]:
    """Expand every lattice consistently while respecting the preview budget.

    The common cell must sit inside recognizable parent lattices rather than at
    the edge of a one-cell atom halo.  Two or more primitive shells are cheap
    for ordinary 2D cells, while the bounded fallback keeps large proposals
    responsive without changing the scientific common-cell result.
    """

    minimum = max(0, int(requested_padding))
    # ``padding=0`` is the private materialization path and must remain an
    # exact common cell.  Any visible preview gets enough context to read both
    # parent lattices as continuous sublattices.
    desired = 0 if minimum == 0 else max(
        2,
        _commensurate_grid_padding(area_ratio, minimum),
    )
    if not include_atoms:
        return [
            _primitive_halo_points(core, axes, desired)
            for core, axes, _ in components
        ], desired, 0

    limit = max(1, int(max_preview_atoms))
    for padding in range(desired, -1, -1):
        expanded = [
            _primitive_halo_points(core, axes, padding)
            for core, axes, _ in components
        ]
        count = sum(
            len(points) * max(0, int(atom_count))
            for points, (_, _, atom_count) in zip(expanded, components)
        )
        if count <= limit:
            return expanded, padding, count
    raise ValueError(
        "The proposed common cell alone exceeds the interactive atom-preview limit."
    )


def _grid_lattice_metadata(
    points: Sequence[tuple[Sequence[int], bool]],
    periodic_axes: Sequence[int],
) -> tuple[list[list[int]], list[int]]:
    origins = [list(map(int, point)) for point, _ in points]
    axes = tuple(int(axis) for axis in periodic_axes)
    if not origins:
        return [], [0, 0]
    values = np.asarray(origins, dtype=int)
    shape = [
        int(values[:, axis].max() - values[:, axis].min() + 1)
        for axis in axes
    ]
    return origins, shape


def commensurate_supercell_geometry(
    *,
    cell: Sequence[Sequence[float]],
    positions: Sequence[Sequence[float]],
    selected_indices: Sequence[int],
    candidate: dict,
    pivot: Sequence[float],
    padding_cells: int = 1,
    include_atoms: bool = True,
    display_angle_deg: float | None = None,
    positions_include_display_rotation: bool = True,
    max_preview_atoms: int = 120_000,
    parent_lattice_preview: bool = False,
    parent_grid_radius: int = 0,
) -> dict:
    """Build an opaque common-cell preview inside expanded parent lattices.

    The reference component is repeated with the target boundary.  The selected
    component is repeated with the source boundary and receives the displayed
    rotation unless the supplied positions already contain it, followed by the
    residual deformation required to reach the common target cell.
    """

    parent_cell = np.asarray(cell, dtype=float)
    coordinates = np.asarray(positions, dtype=float)
    center = np.asarray(pivot, dtype=float)
    if parent_cell.shape != (3, 3) or not np.all(np.isfinite(parent_cell)):
        raise ValueError("Commensurate preview requires a finite 3 x 3 cell.")
    if coordinates.ndim != 2 or coordinates.shape[1] != 3 or not np.all(np.isfinite(coordinates)):
        raise ValueError("Commensurate preview requires finite Cartesian atom positions.")
    if center.shape != (3,) or not np.all(np.isfinite(center)):
        raise ValueError("Commensurate preview requires a finite rotation pivot.")

    selected = sorted({int(index) for index in selected_indices})
    if not selected or selected[0] < 0 or selected[-1] >= len(coordinates):
        raise ValueError("Select a non-empty valid atom subset for a commensurate layer.")
    selected_set = set(selected)
    reference = [index for index in range(len(coordinates)) if index not in selected_set]
    if not reference:
        raise ValueError("A commensurate preview needs both a rotating layer and a reference layer.")

    source_matrix = np.asarray(candidate.get("source_matrix_3d"), dtype=int)
    target_matrix = np.asarray(candidate.get("target_matrix_3d"), dtype=int)
    deformation = np.asarray(candidate.get("deformation_matrix"), dtype=float)
    periodic_axes = tuple(int(axis) for axis in candidate.get("periodic_axes", (0, 1)))
    if source_matrix.shape != (3, 3) or target_matrix.shape != (3, 3):
        raise ValueError("Commensurate candidate is missing reproducible 3 x 3 supercell matrices.")
    if deformation.shape != (3, 3) or not np.all(np.isfinite(deformation)):
        raise ValueError("Commensurate candidate has an invalid residual deformation.")
    source_area = int(round(np.linalg.det(source_matrix)))
    target_area = int(round(np.linalg.det(target_matrix)))
    if source_area <= 0 or target_area != source_area:
        raise ValueError("Commensurate source and target cells must have the same positive area.")
    if len(periodic_axes) != 2 or len(set(periodic_axes)) != 2:
        raise ValueError("Commensurate preview requires two distinct periodic cell axes.")

    _, normal = _axis_vector(candidate.get("axis", "Z"))
    display_angle = (
        float(candidate.get("angle_deg", 0.0))
        if display_angle_deg is None
        else float(display_angle_deg)
    )
    if not np.isfinite(display_angle):
        raise ValueError("Commensurate preview angle must be finite.")
    rotation = row_rotation_matrix(normal, display_angle)
    source_core = _integer_supercell_lattice_points(parent_cell, source_matrix)
    target_core = _integer_supercell_lattice_points(parent_cell, target_matrix)
    if parent_lattice_preview:
        grid_radius = max(2, int(parent_grid_radius))
        grid_window = _primitive_lattice_window(periodic_axes, grid_radius)
        source_core_set = set(source_core)
        target_core_set = set(target_core)
        source_grid_points = [(point, point in source_core_set) for point in grid_window]
        target_grid_points = [(point, point in target_core_set) for point in grid_window]
        atom_padding = _bounded_parent_atom_radius(
            grid_radius,
            len(coordinates),
            int(max_preview_atoms),
        )
        atom_window = _primitive_lattice_window(periodic_axes, atom_padding)
        source_points = [(point, point in source_core_set) for point in atom_window]
        target_points = [(point, point in target_core_set) for point in atom_window]
        preview_count = (
            len(source_points) * len(selected)
            + len(target_points) * len(reference)
        ) if include_atoms else 0
        grid_padding = grid_radius
    else:
        (source_points, target_points), atom_padding, preview_count = _expanded_preview_points(
            (
                (source_core, periodic_axes, len(selected)),
                (target_core, periodic_axes, len(reference)),
            ),
            requested_padding=int(padding_cells),
            area_ratio=source_area,
            include_atoms=bool(include_atoms),
            max_preview_atoms=int(max_preview_atoms),
        )
        grid_padding = _commensurate_grid_padding(source_area, atom_padding)
        source_grid_points = _primitive_halo_points(source_core, periodic_axes, grid_padding)
        target_grid_points = _primitive_halo_points(target_core, periodic_axes, grid_padding)
    preview_positions: list[list[float]] = []
    atom_indices: list[int] = []
    lattice_indices: list[list[int]] = []
    components: list[str] = []
    core_mask: list[bool] = []

    def append_reference(point: tuple[int, int, int], core: bool) -> None:
        shift = np.asarray(point, dtype=float) @ parent_cell
        for index in reference:
            preview_positions.append((coordinates[index] + shift).tolist())
            atom_indices.append(index)
            lattice_indices.append(list(point))
            components.append("reference")
            core_mask.append(bool(core))

    def append_selected(point: tuple[int, int, int], core: bool) -> None:
        primitive_shift = np.asarray(point, dtype=float) @ parent_cell
        transformed_shift = primitive_shift @ rotation
        if not parent_lattice_preview:
            transformed_shift = transformed_shift @ deformation
        for index in selected:
            relative = coordinates[index] - center
            if not positions_include_display_rotation:
                relative = relative @ rotation
            transformed_position = center + relative
            if not parent_lattice_preview:
                transformed_position = center + relative @ deformation
            preview_positions.append((transformed_position + transformed_shift).tolist())
            atom_indices.append(index)
            lattice_indices.append(list(point))
            components.append("rotating")
            core_mask.append(bool(core))

    if include_atoms:
        for point, core in target_points:
            append_reference(point, core)
        for point, core in source_points:
            append_selected(point, core)

    common_cell = target_matrix @ parent_cell
    candidate_guest_cell = source_matrix @ parent_cell @ rotation @ deformation
    if parent_lattice_preview:
        guest_origin = center - center @ rotation
        host_parent_cell = parent_cell
        guest_parent_cell = parent_cell @ rotation
        host_primitive = parent_cell
        guest_primitive = parent_cell @ rotation
        host_lattice_origins = [[0.0, 0.0, 0.0]]
        guest_lattice_origins = [guest_origin.tolist()]
    else:
        guest_origin = np.zeros(3, dtype=float)
        host_parent_cell = common_cell
        guest_parent_cell = candidate_guest_cell
        host_primitive = parent_cell
        guest_primitive = parent_cell @ rotation @ deformation
        host_lattice_origins = [
            (np.asarray(point, dtype=float) @ parent_cell).tolist()
            for point in target_core
        ]
        guest_lattice_origins = [
            (np.asarray(point, dtype=float) @ guest_primitive).tolist()
            for point in source_core
        ]
    target_grid_indices, host_grid_shape = _grid_lattice_metadata(
        target_grid_points,
        periodic_axes,
    )
    source_grid_indices, guest_grid_shape = _grid_lattice_metadata(
        source_grid_points,
        periodic_axes,
    )
    host_grid_lattice_origins = [
        (np.asarray(point, dtype=float) @ parent_cell).tolist()
        for point in target_grid_indices
    ]
    guest_grid_lattice_origins = [
        (guest_origin + np.asarray(point, dtype=float) @ guest_primitive).tolist()
        for point in source_grid_indices
    ]

    return {
        "mode": "same-lattice",
        "positions": preview_positions,
        "atom_indices": atom_indices,
        "lattice_indices": lattice_indices,
        "components": components,
        "core_mask": core_mask,
        "core_atom_count": source_area * len(coordinates),
        "preview_atom_count": preview_count,
        "padding_cells": atom_padding,
        "requested_padding_cells": int(padding_cells),
        "include_atoms": bool(include_atoms),
        "display_angle_deg": display_angle,
        "cell": common_cell.tolist(),
        "common_cell": common_cell.tolist(),
        "host_cell": common_cell.tolist(),
        "guest_cell": candidate_guest_cell.tolist(),
        "host_parent_cell": host_parent_cell.tolist(),
        "guest_parent_cell": guest_parent_cell.tolist(),
        "host_lattice_origins": host_lattice_origins,
        "guest_lattice_origins": guest_lattice_origins,
        "host_grid_lattice_origins": host_grid_lattice_origins,
        "guest_grid_lattice_origins": guest_grid_lattice_origins,
        "host_grid_shape": host_grid_shape,
        "guest_grid_shape": guest_grid_shape,
        "grid_padding_cells": grid_padding,
        "parent_grid_radius": int(grid_padding) if parent_lattice_preview else None,
        "parent_lattices_fixed": bool(parent_lattice_preview),
        "host_primitive_vectors": host_primitive[list(periodic_axes)].tolist(),
        "guest_primitive_vectors": guest_primitive[list(periodic_axes)].tolist(),
        "host_notation": str(candidate.get("target_notation", "Host cell")),
        "guest_notation": str(candidate.get("source_notation", "Guest cell")),
        "has_suggestion": True,
        "guest_offset": guest_origin.tolist(),
        "source_cell": (source_matrix @ parent_cell).tolist(),
        "source_matrix_3d": source_matrix.tolist(),
        "target_matrix_3d": target_matrix.tolist(),
        "area_ratio": source_area,
        "deformation_matrix": deformation.tolist(),
    }


def host_guest_supercell_geometry(
    *,
    host_cell: Sequence[Sequence[float]],
    host_positions: Sequence[Sequence[float]],
    guest_cell: Sequence[Sequence[float]],
    guest_positions: Sequence[Sequence[float]],
    candidate: dict,
    guest_offset: Sequence[float] = (0.0, 0.0, 0.0),
    padding_cells: int = 1,
    include_atoms: bool = True,
    display_angle_deg: float | None = None,
    max_preview_atoms: int = 120_000,
    parent_lattice_preview: bool = False,
    parent_grid_radius: int = 0,
) -> dict:
    """Build independent host and guest common-cell preview geometry."""

    host_parent = np.asarray(host_cell, dtype=float)
    guest_parent = np.asarray(guest_cell, dtype=float)
    host_coordinates = np.asarray(host_positions, dtype=float)
    guest_coordinates = np.asarray(guest_positions, dtype=float)
    offset = np.asarray(guest_offset, dtype=float)
    for name, cell in (("host", host_parent), ("guest", guest_parent)):
        if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
            raise ValueError(f"Commensurate {name} preview requires a finite 3 x 3 cell.")
    for name, positions in (("host", host_coordinates), ("guest", guest_coordinates)):
        if positions.ndim != 2 or positions.shape[1] != 3 or not np.all(np.isfinite(positions)):
            raise ValueError(f"Commensurate {name} preview requires finite Cartesian atom positions.")
    if offset.shape != (3,) or not np.all(np.isfinite(offset)):
        raise ValueError("Commensurate guest offset must be a finite three-vector.")

    host_matrix = np.asarray(candidate.get("host_matrix_3d"), dtype=int)
    guest_matrix = np.asarray(candidate.get("guest_matrix_3d"), dtype=int)
    host_deformation = np.asarray(candidate.get("host_deformation_matrix"), dtype=float)
    guest_deformation = np.asarray(candidate.get("guest_deformation_matrix"), dtype=float)
    if host_matrix.shape != (3, 3) or guest_matrix.shape != (3, 3):
        raise ValueError("Host/guest match is missing reproducible 3 x 3 supercell matrices.")
    if host_deformation.shape != (3, 3) or guest_deformation.shape != (3, 3):
        raise ValueError("Host/guest match is missing finite deformation matrices.")
    if not np.all(np.isfinite(host_deformation)) or not np.all(np.isfinite(guest_deformation)):
        raise ValueError("Host/guest match contains a non-finite deformation matrix.")

    host_axes = tuple(int(value) for value in candidate.get("host_periodic_axes", (0, 1)))
    guest_axes = tuple(int(value) for value in candidate.get("guest_periodic_axes", (0, 1)))
    host_core = _integer_supercell_lattice_points(host_parent, host_matrix)
    guest_core = _integer_supercell_lattice_points(guest_parent, guest_matrix)
    largest_area = max(len(host_core), len(guest_core))
    if parent_lattice_preview:
        grid_radius = max(2, int(parent_grid_radius))
        host_grid_window = _primitive_lattice_window(host_axes, grid_radius)
        guest_grid_window = _primitive_lattice_window(guest_axes, grid_radius)
        host_core_set = set(host_core)
        guest_core_set = set(guest_core)
        host_grid_points = [(point, point in host_core_set) for point in host_grid_window]
        guest_grid_points = [(point, point in guest_core_set) for point in guest_grid_window]
        atom_padding = _bounded_parent_atom_radius(
            grid_radius,
            len(host_coordinates) + len(guest_coordinates),
            int(max_preview_atoms),
        )
        host_atom_window = _primitive_lattice_window(host_axes, atom_padding)
        guest_atom_window = _primitive_lattice_window(guest_axes, atom_padding)
        host_points = [(point, point in host_core_set) for point in host_atom_window]
        guest_points = [(point, point in guest_core_set) for point in guest_atom_window]
        preview_count = (
            len(host_points) * len(host_coordinates)
            + len(guest_points) * len(guest_coordinates)
        ) if include_atoms else 0
        grid_padding = grid_radius
    else:
        (host_points, guest_points), atom_padding, preview_count = _expanded_preview_points(
            (
                (host_core, host_axes, len(host_coordinates)),
                (guest_core, guest_axes, len(guest_coordinates)),
            ),
            requested_padding=int(padding_cells),
            area_ratio=largest_area,
            include_atoms=bool(include_atoms),
            max_preview_atoms=int(max_preview_atoms),
        )
        grid_padding = _commensurate_grid_padding(largest_area, atom_padding)
        host_grid_points = _primitive_halo_points(host_core, host_axes, grid_padding)
        guest_grid_points = _primitive_halo_points(guest_core, guest_axes, grid_padding)
    display_angle = (
        float(candidate.get("angle_deg", 0.0))
        if display_angle_deg is None
        else float(display_angle_deg)
    )
    if not np.isfinite(display_angle):
        raise ValueError("Commensurate preview angle must be finite.")
    rotation = row_rotation_matrix([0.0, 0.0, 1.0], display_angle)
    positions: list[list[float]] = []
    atom_indices: list[int] = []
    lattice_indices: list[list[int]] = []
    components: list[str] = []
    core_mask: list[bool] = []

    if include_atoms:
        for point, core in host_points:
            shift = np.asarray(point, dtype=float) @ host_parent
            for index, position in enumerate(host_coordinates):
                transformed = position + shift
                if not parent_lattice_preview:
                    transformed = transformed @ host_deformation
                positions.append(transformed.tolist())
                atom_indices.append(index)
                lattice_indices.append(list(point))
                components.append("host")
                core_mask.append(bool(core))
        for point, core in guest_points:
            shift = np.asarray(point, dtype=float) @ guest_parent
            for index, position in enumerate(guest_coordinates):
                transformed = (position + shift) @ rotation
                if not parent_lattice_preview:
                    transformed = transformed @ guest_deformation
                transformed = transformed + offset
                positions.append(transformed.tolist())
                atom_indices.append(index)
                lattice_indices.append(list(point))
                components.append("guest")
                core_mask.append(bool(core))

    common_cell = np.asarray(candidate.get("suggested_cell"), dtype=float)
    candidate_host_boundary = (
        np.asarray(candidate.get("host_supercell"), dtype=float) @ host_deformation
    )
    candidate_guest_boundary = (
        np.asarray(candidate.get("guest_supercell"), dtype=float)
        @ rotation
        @ guest_deformation
    )
    if parent_lattice_preview:
        host_parent_boundary = host_parent
        guest_parent_boundary = guest_parent @ rotation
        host_primitive = host_parent
        guest_primitive = guest_parent @ rotation
        host_lattice_origins = [[0.0, 0.0, 0.0]]
        guest_lattice_origins = [offset.tolist()]
    else:
        host_parent_boundary = candidate_host_boundary
        guest_parent_boundary = candidate_guest_boundary
        host_primitive = host_parent @ host_deformation
        guest_primitive = guest_parent @ rotation @ guest_deformation
        host_lattice_origins = [
            (np.asarray(point, dtype=float) @ host_primitive).tolist()
            for point in host_core
        ]
        guest_lattice_origins = [
            (np.asarray(point, dtype=float) @ guest_primitive + offset).tolist()
            for point in guest_core
        ]
    host_grid_indices, host_grid_shape = _grid_lattice_metadata(host_grid_points, host_axes)
    guest_grid_indices, guest_grid_shape = _grid_lattice_metadata(guest_grid_points, guest_axes)
    host_grid_lattice_origins = [
        (np.asarray(point, dtype=float) @ host_primitive).tolist()
        for point in host_grid_indices
    ]
    guest_grid_lattice_origins = [
        (np.asarray(point, dtype=float) @ guest_primitive + offset).tolist()
        for point in guest_grid_indices
    ]
    return {
        "mode": "host-guest",
        "positions": positions,
        "atom_indices": atom_indices,
        "lattice_indices": lattice_indices,
        "components": components,
        "core_mask": core_mask,
        "core_atom_count": (
            len(host_core) * len(host_coordinates)
            + len(guest_core) * len(guest_coordinates)
        ) if include_atoms else 0,
        "preview_atom_count": preview_count,
        "padding_cells": atom_padding,
        "requested_padding_cells": int(padding_cells),
        "include_atoms": bool(include_atoms),
        "display_angle_deg": display_angle,
        "cell": common_cell.tolist(),
        "common_cell": common_cell.tolist(),
        "host_cell": candidate_host_boundary.tolist(),
        "guest_cell": candidate_guest_boundary.tolist(),
        "host_parent_cell": host_parent_boundary.tolist(),
        "guest_parent_cell": guest_parent_boundary.tolist(),
        "host_lattice_origins": host_lattice_origins,
        "guest_lattice_origins": guest_lattice_origins,
        "host_grid_lattice_origins": host_grid_lattice_origins,
        "guest_grid_lattice_origins": guest_grid_lattice_origins,
        "host_grid_shape": host_grid_shape,
        "guest_grid_shape": guest_grid_shape,
        "grid_padding_cells": grid_padding,
        "parent_grid_radius": int(grid_padding) if parent_lattice_preview else None,
        "parent_lattices_fixed": bool(parent_lattice_preview),
        "host_primitive_vectors": host_primitive[list(host_axes)].tolist(),
        "guest_primitive_vectors": guest_primitive[list(guest_axes)].tolist(),
        "host_notation": str(candidate.get("host_notation", "Host cell")),
        "guest_notation": str(candidate.get("guest_notation", "Guest cell")),
        "has_suggestion": True,
        "host_matrix_3d": host_matrix.tolist(),
        "guest_matrix_3d": guest_matrix.tolist(),
        "host_area_ratio": int(candidate.get("host_area_ratio", len(host_core))),
        "guest_area_ratio": int(candidate.get("guest_area_ratio", len(guest_core))),
        "guest_offset": offset.tolist(),
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


def _exact_rotational_symmetry_period(basis: np.ndarray) -> float | None:
    """Return an exact in-plane rotational period for ideal square/hex cells.

    This is intentionally much stricter than the family classifier used to
    choose a search algorithm.  Approximate experimental or strained cells do
    not receive symmetry-equivalence guides in the plot.
    """

    vectors = np.asarray(basis, dtype=float)
    if vectors.shape != (2, 2) or not np.all(np.isfinite(vectors)):
        return None
    lengths = np.linalg.norm(vectors, axis=1)
    if np.min(lengths) <= 1e-12 or not np.isclose(
        lengths[0], lengths[1], rtol=1e-9, atol=1e-10
    ):
        return None
    cosine = float(np.dot(vectors[0], vectors[1]) / (lengths[0] * lengths[1]))
    if np.isclose(abs(cosine), 0.5, rtol=0.0, atol=1e-9):
        return 60.0
    if np.isclose(cosine, 0.0, rtol=0.0, atol=1e-9):
        return 90.0
    return None


def _hexagonal_candidates(basis: np.ndarray, max_index: int, carbon_only: bool) -> Iterable[dict]:
    canonical = np.array(basis, copy=True)
    canonical_transform = np.eye(2, dtype=int)
    if float(np.dot(canonical[0], canonical[1])) < 0:
        canonical_transform[1, 1] = -1
        canonical = canonical_transform @ canonical

    def restore_original_basis(*matrices: np.ndarray) -> tuple[np.ndarray, ...]:
        """Map canonical matrices back without reversing cell handedness."""

        restored = tuple(np.asarray(matrix, dtype=int) @ canonical_transform for matrix in matrices)
        if restored and np.linalg.det(restored[0]) < 0:
            # Apply the same unimodular row operation to every boundary.  This
            # changes only the supercell basis, not the common lattice or the
            # relative rotation between source and target.
            positive_orientation = np.diag([-1, 1])
            restored = tuple(positive_orientation @ matrix for matrix in restored)
        return restored

    # The r=1 commensurate family.  m=31, n=32 gives 1.0501 degrees
    # and a 2977-fold primitive-cell area, the standard first-TBG-magic-angle
    # commensurate approximant.
    for m in range(1, max_index):
        n = m + 1
        source = np.array([[m, n], [-n, m + n]], dtype=int)
        target = np.array([[n, m], [-m, m + n]], dtype=int)
        area = m * m + m * n + n * n
        source, target = restore_original_basis(source, target)
        item = _candidate(
            basis,
            source,
            target,
            family="hexagonal-r1",
            area=area,
            magic_reference=carbon_only and m == 31,
        )
        yield item
        yield _candidate(
            basis,
            target,
            source,
            family="hexagonal-r1",
            area=area,
            magic_reference=item["magic_reference"],
        )

    identity = np.eye(2, dtype=int)
    sixty = np.array([[0, 1], [-1, 1]], dtype=int)
    for source, target in ((identity, sixty), (sixty, identity)):
        source, target = restore_original_basis(source, target)
        yield _candidate(
            basis,
            source,
            target,
            family="hexagonal-symmetry",
            area=1,
        )


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


def _supercell_records(basis: np.ndarray, max_area_ratio: int) -> list[dict]:
    records: list[dict] = []
    seen: set[tuple[int, tuple[int, ...]]] = set()
    for area in range(1, max_area_ratio + 1):
        for matrix in _hnf_matrices(area):
            reduced, reduced_matrix = _gauss_reduce(matrix @ basis, matrix)
            key = (
                area,
                tuple(int(value) for value in reduced_matrix.reshape(-1)),
            )
            if key in seen:
                continue
            seen.add(key)
            lengths = np.linalg.norm(reduced, axis=1)
            if np.min(lengths) <= 1e-12:
                continue
            # The same oriented 2D sublattice can be represented by acute or
            # obtuse reduced bases.  Shape screening must therefore use the
            # unsigned inter-vector cosine; the subsequent Procrustes solve
            # recovers the actual proper rotation from the full vectors.
            cosine = abs(float(np.dot(reduced[0], reduced[1]) / (lengths[0] * lengths[1])))
            sorted_lengths = np.sort(lengths)
            records.append({
                "area": int(area),
                "basis": reduced,
                "matrix": reduced_matrix,
                "descriptor": np.array([
                    float(np.log(sorted_lengths[0])),
                    float(np.log(sorted_lengths[1])),
                    cosine,
                ]),
            })
    return records


def _plane_deformation(
    source_cell: np.ndarray,
    source_axes: Sequence[int],
    target_cell: np.ndarray,
    target_axes: Sequence[int],
    normal: np.ndarray,
) -> np.ndarray:
    source_frame = np.vstack([
        source_cell[int(source_axes[0])],
        source_cell[int(source_axes[1])],
        normal,
    ])
    target_frame = np.vstack([
        target_cell[int(target_axes[0])],
        target_cell[int(target_axes[1])],
        normal,
    ])
    return np.linalg.solve(source_frame, target_frame)


def _lattice_match_candidate(
    *,
    host_cell: np.ndarray,
    guest_cell: np.ndarray,
    host_projected: ProjectedLattice,
    guest_projected: ProjectedLattice,
    normal: np.ndarray,
    host_record: dict,
    guest_record: dict,
    strain_target: str,
    guest_orientation_transform: np.ndarray | None = None,
) -> dict:
    host_boundary = np.asarray(host_record["basis"], dtype=float)
    orientation_transform = np.asarray(
        guest_orientation_transform
        if guest_orientation_transform is not None
        else _ORIENTED_BASIS_TRANSFORMS[0],
        dtype=int,
    )
    guest_boundary = orientation_transform @ np.asarray(guest_record["basis"], dtype=float)
    angle, guest_strain, _, guest_deformation_2d = _optimal_rotation_deformation(
        guest_boundary,
        host_boundary,
    )
    rotated_guest_boundary = guest_boundary @ np.array([
        [cos(radians(angle)), sin(radians(angle))],
        [-sin(radians(angle)), cos(radians(angle))],
    ])
    host_deformation_2d = np.linalg.solve(host_boundary, rotated_guest_boundary)
    guest_metrics = _deformation_strain_metrics(guest_deformation_2d)
    host_metrics = _deformation_strain_metrics(host_deformation_2d)
    guest_strain = float(guest_metrics["max_principal_strain"])
    host_strain = float(host_metrics["max_principal_strain"])
    active_strain = guest_strain if strain_target == "guest" else host_strain
    active_metrics = guest_metrics if strain_target == "guest" else host_metrics

    host_matrix_2d = np.asarray(host_record["matrix"], dtype=int)
    guest_matrix_2d = orientation_transform @ np.asarray(guest_record["matrix"], dtype=int)
    host_matrix_3d = embed_2d_supercell_matrix(
        host_matrix_2d,
        host_projected.periodic_axes,
    )
    guest_matrix_3d = embed_2d_supercell_matrix(
        guest_matrix_2d,
        guest_projected.periodic_axes,
    )
    host_supercell = host_matrix_3d @ host_cell
    guest_supercell = guest_matrix_3d @ guest_cell
    rotation_3d = row_rotation_matrix(normal, angle)
    rotated_guest_cell = guest_supercell @ rotation_3d

    if strain_target == "guest":
        common_cell = host_supercell.copy()
        host_deformation = np.eye(3)
        guest_deformation = _plane_deformation(
            rotated_guest_cell,
            guest_projected.periodic_axes,
            host_supercell,
            host_projected.periodic_axes,
            normal,
        )
    else:
        common_cell = host_supercell.copy()
        for host_axis, guest_axis in zip(
            host_projected.periodic_axes,
            guest_projected.periodic_axes,
        ):
            common_cell[int(host_axis)] = rotated_guest_cell[int(guest_axis)]
        host_deformation = _plane_deformation(
            host_supercell,
            host_projected.periodic_axes,
            common_cell,
            host_projected.periodic_axes,
            normal,
        )
        guest_deformation = np.eye(3)

    host_area = abs(int(round(np.linalg.det(host_matrix_2d))))
    guest_area = abs(int(round(np.linalg.det(guest_matrix_2d))))
    periodic_vectors = common_cell[np.asarray(host_projected.periodic_axes, dtype=int)]
    lengths = np.linalg.norm(periodic_vectors, axis=1)
    cosine = float(np.dot(periodic_vectors[0], periodic_vectors[1]) / max(
        float(lengths[0] * lengths[1]),
        1e-14,
    ))
    cell_angle = float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
    supported = bool(
        host_projected.axis_alignment >= 0.985
        and guest_projected.axis_alignment >= 0.985
        and host_area > 0
        and guest_area > 0
        and np.all(np.isfinite(common_cell))
        and np.all(np.isfinite(host_deformation))
        and np.all(np.isfinite(guest_deformation))
    )
    reason = None if supported else (
        "Both host and guest cells must define two in-plane periodic vectors "
        "whose normals align with the Z rotation axis."
    )
    return {
        "angle_deg": round(float(angle), 8),
        "strain": round(float(active_strain), 12),
        "max_principal_strain": round(float(active_strain), 12),
        "mean_absolute_strain": round(
            float(active_metrics["mean_absolute_strain"]),
            12,
        ),
        "linear_strain_tensor_2d": active_metrics["linear_strain_tensor_2d"],
        "principal_stretches": active_metrics["principal_stretches"],
        "guest_strain": round(float(guest_strain), 12),
        "host_strain": round(float(host_strain), 12),
        "guest_mean_absolute_strain": round(
            float(guest_metrics["mean_absolute_strain"]),
            12,
        ),
        "host_mean_absolute_strain": round(
            float(host_metrics["mean_absolute_strain"]),
            12,
        ),
        "guest_linear_strain_tensor_2d": guest_metrics["linear_strain_tensor_2d"],
        "host_linear_strain_tensor_2d": host_metrics["linear_strain_tensor_2d"],
        "strain_target": strain_target,
        "area": max(host_area, guest_area),
        "area_ratio": max(host_area, guest_area),
        "host_area_ratio": host_area,
        "guest_area_ratio": guest_area,
        "host_matrix": host_matrix_2d.tolist(),
        "guest_matrix": guest_matrix_2d.tolist(),
        "host_matrix_3d": host_matrix_3d.tolist(),
        "guest_matrix_3d": guest_matrix_3d.tolist(),
        # Compatibility aliases used by the existing same-lattice UI.
        "source_matrix": guest_matrix_2d.tolist(),
        "target_matrix": host_matrix_2d.tolist(),
        "source_matrix_3d": guest_matrix_3d.tolist(),
        "target_matrix_3d": host_matrix_3d.tolist(),
        "host_matrix_text": _matrix_text(host_matrix_2d),
        "guest_matrix_text": _matrix_text(guest_matrix_2d),
        "source_matrix_text": _matrix_text(guest_matrix_2d),
        "target_matrix_text": _matrix_text(host_matrix_2d),
        "host_notation": _supercell_notation(host_projected.basis, host_matrix_2d),
        "guest_notation": _supercell_notation(guest_projected.basis, guest_matrix_2d),
        "source_notation": _supercell_notation(guest_projected.basis, guest_matrix_2d),
        "target_notation": _supercell_notation(host_projected.basis, host_matrix_2d),
        "suggested_cell": common_cell.tolist(),
        "host_supercell": host_supercell.tolist(),
        "guest_supercell": guest_supercell.tolist(),
        "rotated_guest_cell": rotated_guest_cell.tolist(),
        "host_deformation_matrix": host_deformation.tolist(),
        "guest_deformation_matrix": guest_deformation.tolist(),
        "deformation_matrix": guest_deformation.tolist(),
        "guest_deformation_2d": guest_deformation_2d.tolist(),
        "cell_lengths_angstrom": [round(float(value), 8) for value in lengths],
        "cell_angle_deg": round(cell_angle, 8),
        "host_periodic_axes": [int(value) for value in host_projected.periodic_axes],
        "guest_periodic_axes": [int(value) for value in guest_projected.periodic_axes],
        "periodic_axes": [int(value) for value in host_projected.periodic_axes],
        "axis": "Z",
        "family": "host-guest-integer-boundary",
        "magic_reference": False,
        "supercell_supported": supported,
        "supercell_reason": reason,
        "preview_padding_cells": 1,
    }


def _deduplicate_lattice_matches(candidates: Iterable[dict]) -> list[dict]:
    best: dict[int, dict] = {}
    for candidate in candidates:
        angle = float(candidate["angle_deg"])
        key = int(round(angle * 100.0))
        rank = (
            int(candidate["area_ratio"]),
            int(candidate["host_area_ratio"]) + int(candidate["guest_area_ratio"]),
            float(candidate["strain"]),
            abs(angle),
        )
        previous = best.get(key)
        if previous is None:
            best[key] = candidate
            continue
        previous_rank = (
            int(previous["area_ratio"]),
            int(previous["host_area_ratio"]) + int(previous["guest_area_ratio"]),
            float(previous["strain"]),
            abs(float(previous["angle_deg"])),
        )
        if rank < previous_rank:
            best[key] = candidate
    return sorted(
        best.values(),
        key=lambda item: (
            int(item["area_ratio"]),
            int(item["host_area_ratio"]) + int(item["guest_area_ratio"]),
            float(item["strain"]),
            abs(float(item["angle_deg"])),
        ),
    )


def _batch_lattice_match_kinematics(
    host_boundaries: np.ndarray,
    guest_boundaries: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorize proper rotations and strains for all oriented basis variants.

    The leading dimension of each returned array indexes
    ``_ORIENTED_BASIS_TRANSFORMS``.  Testing these determinant-one signed row
    permutations makes the result invariant to acute versus obtuse reduced
    basis representations of the same physical sublattice.
    """

    host = np.asarray(host_boundaries, dtype=float)
    guest = np.asarray(guest_boundaries, dtype=float)
    if host.ndim != 3 or host.shape[1:] != (2, 2) or guest.shape != host.shape:
        raise ValueError("Batched lattice boundaries must have shape (N, 2, 2).")
    if len(host) == 0:
        empty = np.empty((len(_ORIENTED_BASIS_TRANSFORMS), 0), dtype=float)
        return empty, empty, empty

    angle_variants: list[np.ndarray] = []
    guest_strain_variants: list[np.ndarray] = []
    host_strain_variants: list[np.ndarray] = []

    def principal_stretches(deformation: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Closed-form singular values of a 2 x 2 matrix avoid hundreds of
        # thousands of tiny LAPACK calls during a large bounded search.  The
        # two hypot expressions are stable for identity and nearly isotropic
        # matrices, where trace/determinant formulas lose enough precision to
        # reject an exact match at a strict zero-strain tolerance.
        a = deformation[:, 0, 0]
        b = deformation[:, 0, 1]
        c = deformation[:, 1, 0]
        d = deformation[:, 1, 1]
        sum_term = np.hypot(a + d, b - c)
        difference_term = np.hypot(a - d, b + c)
        largest = 0.5 * (sum_term + difference_term)
        smallest = 0.5 * np.abs(sum_term - difference_term)
        return largest, smallest

    def solve_2x2(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        """Return ``left^-1 @ right`` without batched LAPACK dispatch."""

        a = left[:, 0, 0]
        b = left[:, 0, 1]
        c = left[:, 1, 0]
        d = left[:, 1, 1]
        determinant = a * d - b * c
        if np.any(np.abs(determinant) <= 1e-24):
            raise ValueError("Commensurate boundary matrix is singular.")
        e = right[:, 0, 0]
        f = right[:, 0, 1]
        g = right[:, 1, 0]
        h = right[:, 1, 1]
        result = np.empty_like(left)
        result[:, 0, 0] = (d * e - b * g) / determinant
        result[:, 0, 1] = (d * f - b * h) / determinant
        result[:, 1, 0] = (-c * e + a * g) / determinant
        result[:, 1, 1] = (-c * f + a * h) / determinant
        return result

    for transform in _ORIENTED_BASIS_TRANSFORMS:
        oriented_guest = transform @ guest
        covariance = np.swapaxes(oriented_guest, 1, 2) @ host
        cosine_numerator = covariance[:, 0, 0] + covariance[:, 1, 1]
        sine_numerator = covariance[:, 0, 1] - covariance[:, 1, 0]
        normalization = np.hypot(cosine_numerator, sine_numerator)
        normalization = np.maximum(normalization, 1e-30)
        cosine_values = cosine_numerator / normalization
        sine_values = sine_numerator / normalization
        rotation = np.empty_like(covariance)
        rotation[:, 0, 0] = cosine_values
        rotation[:, 0, 1] = sine_values
        rotation[:, 1, 0] = -sine_values
        rotation[:, 1, 1] = cosine_values

        rotated_guest = oriented_guest @ rotation
        guest_deformation = solve_2x2(rotated_guest, host)
        largest, smallest = principal_stretches(guest_deformation)
        guest_strain_variants.append(np.maximum(
            np.abs(largest - 1.0),
            np.abs(smallest - 1.0),
        ))
        # The host deformation is the exact inverse.  Reciprocal principal
        # stretches avoid a second matrix solve and preserve the same metric.
        host_strain_variants.append(np.maximum(
            np.abs(np.reciprocal(smallest) - 1.0),
            np.abs(np.reciprocal(largest) - 1.0),
        ))
        angles = np.degrees(np.arctan2(rotation[:, 0, 1], rotation[:, 0, 0]))
        angles = (angles + 180.0) % 360.0 - 180.0
        angles[np.isclose(angles, -180.0, atol=1e-10)] = 180.0
        angle_variants.append(angles)
    return (
        np.stack(angle_variants),
        np.stack(guest_strain_variants),
        np.stack(host_strain_variants),
    )


def find_lattice_matches(
    host_cell: Sequence[Sequence[float]],
    host_pbc: Sequence[bool],
    guest_cell: Sequence[Sequence[float]],
    guest_pbc: Sequence[bool],
    *,
    max_area_ratio: int = 16,
    strain_tolerance: float = 0.01,
    strain_target: str = "guest",
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Find bounded common cells for different 2D host and guest lattices.

    The guest cell is rigidly rotated about global Z.  The selected target
    lattice then receives the residual in-plane deformation.  No out-of-plane
    strain is introduced.
    """

    maximum = int(max_area_ratio)
    if maximum < 1 or maximum > MAX_LATTICE_MATCH_AREA_RATIO:
        raise ValueError(
            "Maximum commensurate area ratio must be between 1 and "
            f"{MAX_LATTICE_MATCH_AREA_RATIO}."
        )
    tolerance = float(strain_tolerance)
    if not np.isfinite(tolerance) or tolerance < 0 or tolerance > 0.25:
        raise ValueError("Boundary strain tolerance must be between 0 and 0.25.")
    target = str(strain_target or "guest").strip().lower()
    if target not in {"host", "guest"}:
        raise ValueError("Strain target must be either 'host' or 'guest'.")

    def report(progress: float, stage: str) -> None:
        if progress_callback is not None:
            progress_callback(max(0.0, min(1.0, float(progress))), stage)

    report(0.02, "Projecting host and guest periodic cells")
    frame, normal, host_projected = _plane_frame(host_cell, host_pbc, "Z")
    guest_projected = project_periodic_lattice_in_frame(
        guest_cell,
        guest_pbc,
        normal,
        frame,
    )
    if host_projected.axis_alignment < 0.985 or guest_projected.axis_alignment < 0.985:
        raise ValueError(
            "Commensurate host/guest matching is restricted to cells whose two "
            "periodic vectors lie in the XY plane."
        )

    report(0.08, "Enumerating host integer supercells")
    host_records = _supercell_records(host_projected.basis, maximum)
    report(0.20, "Enumerating guest integer supercells")
    guest_records = _supercell_records(guest_projected.basis, maximum)

    length_limit = max(0.0125, tolerance * 3.5)
    cosine_limit = max(0.025, tolerance * 5.0)
    descriptor_scale = np.array([length_limit, length_limit, cosine_limit])
    host_descriptors = np.stack([record["descriptor"] for record in host_records])
    guest_descriptors = np.stack([record["descriptor"] for record in guest_records])

    # A Chebyshev KD-tree query reproduces the three independent descriptor
    # cutoffs without the Python-level 27-bucket loop.  Exact rotations and
    # principal stretches are then evaluated in NumPy batches.  Only the best
    # pair per plotted angle bucket is enriched into a full candidate object.
    from scipy.spatial import cKDTree

    guest_tree = cKDTree(guest_descriptors / descriptor_scale)
    scaled_host = host_descriptors / descriptor_scale
    best_pairs: dict[int, tuple[int, int, int, tuple[float, ...]]] = {}
    evaluated = 0
    host_total = max(1, len(host_records))
    host_cell_array = np.asarray(host_cell, dtype=float)
    guest_cell_array = np.asarray(guest_cell, dtype=float)
    query_batch_size = 64
    kinematics_batch_size = 50_000
    for host_start in range(0, host_total, query_batch_size):
        host_end = min(host_total, host_start + query_batch_size)
        nearby_lists = guest_tree.query_ball_point(
            scaled_host[host_start:host_end],
            r=1.0 + 1e-12,
            p=np.inf,
        )
        counts = np.fromiter((len(values) for values in nearby_lists), dtype=int)
        pair_count = int(np.sum(counts))
        if pair_count:
            host_indices = np.repeat(np.arange(host_start, host_end, dtype=int), counts)
            guest_indices = np.concatenate([
                np.asarray(values, dtype=int)
                for values in nearby_lists
                if values
            ])
            evaluated += pair_count
            for pair_start in range(0, pair_count, kinematics_batch_size):
                pair_end = min(pair_count, pair_start + kinematics_batch_size)
                host_batch_indices = host_indices[pair_start:pair_end]
                guest_batch_indices = guest_indices[pair_start:pair_end]
                host_boundaries = np.stack([
                    host_records[index]["basis"]
                    for index in host_batch_indices
                ])
                guest_boundaries = np.stack([
                    guest_records[index]["basis"]
                    for index in guest_batch_indices
                ])
                angles, guest_strains, host_strains = _batch_lattice_match_kinematics(
                    host_boundaries,
                    guest_boundaries,
                )
                strain_variants = guest_strains if target == "guest" else host_strains
                columns = np.arange(strain_variants.shape[1])
                minimum_strains = np.min(strain_variants, axis=0)
                equivalent = np.isclose(
                    strain_variants,
                    minimum_strains[None, :],
                    rtol=1e-9,
                    atol=1e-11,
                )
                angle_rank = np.where(equivalent, np.abs(angles), np.inf)
                orientation_indices = np.argmin(angle_rank, axis=0)
                active_strains = strain_variants[orientation_indices, columns]
                active_angles = angles[orientation_indices, columns]
                for local_index in np.flatnonzero(active_strains <= tolerance + 1e-12):
                    host_index = int(host_batch_indices[local_index])
                    guest_index = int(guest_batch_indices[local_index])
                    orientation_index = int(orientation_indices[local_index])
                    angle = float(active_angles[local_index])
                    active_strain = float(active_strains[local_index])
                    host_area = int(host_records[host_index]["area"])
                    guest_area = int(guest_records[guest_index]["area"])
                    key = int(round(angle * 100.0))
                    rank = (
                        float(max(host_area, guest_area)),
                        float(host_area + guest_area),
                        active_strain,
                        abs(angle),
                    )
                    previous = best_pairs.get(key)
                    if previous is None or rank < previous[3]:
                        best_pairs[key] = (
                            host_index,
                            guest_index,
                            orientation_index,
                            rank,
                        )
        report(
            0.24 + 0.70 * host_end / host_total,
            "Comparing integer host/guest boundaries",
        )

    matches = [
        _lattice_match_candidate(
            host_cell=host_cell_array,
            guest_cell=guest_cell_array,
            host_projected=host_projected,
            guest_projected=guest_projected,
            normal=normal,
            host_record=host_records[host_index],
            guest_record=guest_records[guest_index],
            strain_target=target,
            guest_orientation_transform=_ORIENTED_BASIS_TRANSFORMS[orientation_index],
        )
        for host_index, guest_index, orientation_index, _ in best_pairs.values()
    ]
    candidates = _deduplicate_lattice_matches(matches)
    report(1.0, "Ranking valid commensurate matches")
    return {
        "axis": "Z",
        "mode": "host-guest",
        "lattice_family": "host-guest",
        "exact_rotational_symmetry_deg": None,
        "host_periodic_axes": list(host_projected.periodic_axes),
        "guest_periodic_axes": list(guest_projected.periodic_axes),
        "host_axis_alignment": round(float(host_projected.axis_alignment), 8),
        "guest_axis_alignment": round(float(guest_projected.axis_alignment), 8),
        "strain_tolerance": tolerance,
        "strain_target": target,
        "max_area_ratio": maximum,
        "evaluated_pair_count": evaluated,
        "suggestion_count": len(candidates),
        "references": [dict(reference) for reference in COMMENSURATE_REFERENCES],
        "warning": None if candidates else (
            "No host/guest common cell satisfies the current strain and area limits."
        ),
        "candidates": candidates,
    }


def commensurate_csv(search: dict) -> bytes:
    """Serialize plotted common-cell candidates with reproducibility metadata."""

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["# schema", "v_ase.commensurate.v1"])
    writer.writerow(["# mode", str(search.get("mode") or "same-lattice")])
    writer.writerow(["# axis", str(search.get("axis") or "Z")])
    writer.writerow(["# strain_tolerance", f"{float(search.get('strain_tolerance', 0.0)):.12g}"])
    writer.writerow(["# max_area_ratio", int(search.get("max_area_ratio", 0) or 0)])
    for reference in search.get("references") or COMMENSURATE_REFERENCES:
        citation = str(reference.get("title") or "").strip()
        doi = str(reference.get("doi") or "").strip()
        if citation:
            writer.writerow(["# reference", citation, f"doi:{doi}" if doi else ""])
    writer.writerow([
        "angle_deg",
        "strain",
        "max_principal_strain",
        "mean_absolute_strain",
        "host_strain",
        "guest_strain",
        "host_mean_absolute_strain",
        "guest_mean_absolute_strain",
        "area_ratio",
        "host_area_ratio",
        "guest_area_ratio",
        "total_atom_count",
        "host_atom_count",
        "guest_atom_count",
        "host_notation",
        "guest_notation",
        "host_matrix",
        "guest_matrix",
        "strain_target",
    ])
    for candidate in search.get("candidates") or []:
        writer.writerow([
            f"{float(candidate.get('angle_deg', 0.0)):.12g}",
            f"{float(candidate.get('strain', 0.0)):.12g}",
            f"{float(candidate.get('max_principal_strain', candidate.get('strain', 0.0))):.12g}",
            f"{float(candidate.get('mean_absolute_strain', candidate.get('strain', 0.0))):.12g}",
            f"{float(candidate.get('host_strain', candidate.get('strain', 0.0))):.12g}",
            f"{float(candidate.get('guest_strain', candidate.get('strain', 0.0))):.12g}",
            f"{float(candidate.get('host_mean_absolute_strain', candidate.get('mean_absolute_strain', 0.0))):.12g}",
            f"{float(candidate.get('guest_mean_absolute_strain', candidate.get('mean_absolute_strain', 0.0))):.12g}",
            int(candidate.get("area_ratio", candidate.get("area", 0)) or 0),
            int(candidate.get("host_area_ratio", candidate.get("area", 0)) or 0),
            int(candidate.get("guest_area_ratio", candidate.get("area", 0)) or 0),
            int(candidate.get("total_atom_count", 0) or 0),
            int(candidate.get("host_atom_count", 0) or 0),
            int(candidate.get("guest_atom_count", 0) or 0),
            str(candidate.get("host_notation", candidate.get("target_notation", ""))),
            str(candidate.get("guest_notation", candidate.get("source_notation", ""))),
            str(candidate.get("host_matrix", candidate.get("target_matrix", ""))),
            str(candidate.get("guest_matrix", candidate.get("source_matrix", ""))),
            str(candidate.get("strain_target", "guest")),
        ])
    return stream.getvalue().encode("utf-8")


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
            cosine = abs(float(
                np.dot(reduced[0], reduced[1])
                / max(lengths[0] * lengths[1], 1e-14)
            ))
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
        # Every retained candidate already satisfies the requested strain
        # tolerance.  Prefer the smallest physical cell within that admissible
        # set; use residual strain only as the tie-breaker.
        rank = (int(item["area"]), strain, abs(angle))
        if previous is None or rank < (
            int(previous["area"]), float(previous["strain"]), abs(float(previous["angle_deg"]))
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

    candidates = [
        enrich_supercell_candidate(
            candidate,
            cell=cell,
            periodic_axes=projected.periodic_axes,
            axis=axis,
            projected_basis=projected.basis,
            axis_alignment=projected.axis_alignment,
        )
        for candidate in _deduplicate_candidates(raw_candidates, strain_tolerance)
    ]
    for candidate in candidates:
        candidate.update({
            "mode": "same-lattice",
            "strain_target": "guest",
            "host_strain": 0.0,
            "guest_strain": candidate["strain"],
            "host_mean_absolute_strain": 0.0,
            "guest_mean_absolute_strain": candidate["mean_absolute_strain"],
            "host_linear_strain_tensor_2d": [[0.0, 0.0], [0.0, 0.0]],
            "guest_linear_strain_tensor_2d": candidate["linear_strain_tensor_2d"],
            "host_area_ratio": candidate["area_ratio"],
            "guest_area_ratio": candidate["area_ratio"],
            "host_matrix": candidate["target_matrix"],
            "guest_matrix": candidate["source_matrix"],
            "host_matrix_3d": candidate["target_matrix_3d"],
            "guest_matrix_3d": candidate["source_matrix_3d"],
            "host_notation": candidate["target_notation"],
            "guest_notation": candidate["source_notation"],
        })
    warning = None
    if projected.axis_alignment < 0.985:
        warning = (
            "The locked global axis is not normal to the selected periodic cell plane; "
            "candidates use its orthogonal projection."
        )
    return {
        "axis": axis_name,
        "mode": "same-lattice",
        "lattice_family": family,
        "exact_rotational_symmetry_deg": _exact_rotational_symmetry_period(
            projected.basis
        ),
        "periodic_axes": list(projected.periodic_axes),
        "axis_alignment": round(float(projected.axis_alignment), 8),
        "strain_tolerance": strain_tolerance,
        "max_index": max_index,
        "references": [
            *[dict(reference) for reference in COMMENSURATE_REFERENCES],
            dict(TBG_COMMENSURATE_REFERENCE),
        ],
        "warning": warning,
        "candidates": candidates,
    }
