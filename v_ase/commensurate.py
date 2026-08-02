"""Commensurate in-plane rotation candidates for periodic 2D cells.

The search compares integer supercell boundary matrices after removing the
best rigid in-plane rotation.  The remaining principal stretch is the cell
boundary mismatch shown by the interactive rotate guide.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, gcd, radians, sin, sqrt
from typing import Iterable, Sequence

import numpy as np
from ase.build.supercells import lattice_points_in_supercell


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
        return f"{matrix[0, 0]} x {matrix[1, 1]}"

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
        multiplier = str(int(round(root))) if abs(root - round(root)) <= 1e-8 else f"sqrt({determinant})"
        rotation = _signed_angle_deg(basis[0], transformed[0])
        if abs(abs(source_cosine) - 0.5) <= 2e-6:
            rotation = (rotation + 30.0) % 60.0 - 30.0
        elif abs(source_cosine) <= 2e-6:
            rotation = (rotation + 45.0) % 90.0 - 45.0
        if abs(rotation) < 5e-8:
            rotation = 0.0
        return f"({multiplier} x {multiplier}) R{rotation:.2f} deg"
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


def commensurate_supercell_geometry(
    *,
    cell: Sequence[Sequence[float]],
    positions: Sequence[Sequence[float]],
    selected_indices: Sequence[int],
    candidate: dict,
    pivot: Sequence[float],
    padding_cells: int = 1,
    max_preview_atoms: int = 120_000,
) -> dict:
    """Build an opaque common-cell preview plus one primitive-cell halo.

    The current positions must already contain the selected layer's candidate
    rotation.  The reference component is repeated with the target boundary;
    the selected component is repeated with the source boundary and receives
    only the residual deformation required to reach the common target cell.
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
    rotation = row_rotation_matrix(normal, float(candidate.get("angle_deg", 0.0)))
    source_core = _integer_supercell_lattice_points(parent_cell, source_matrix)
    target_core = _integer_supercell_lattice_points(parent_cell, target_matrix)
    source_points = _primitive_halo_points(source_core, periodic_axes, int(padding_cells))
    target_points = _primitive_halo_points(target_core, periodic_axes, int(padding_cells))
    preview_count = len(source_points) * len(selected) + len(target_points) * len(reference)
    if preview_count > int(max_preview_atoms):
        raise ValueError(
            f"Suggested preview would contain {preview_count:,} atoms; "
            f"the interactive preview limit is {int(max_preview_atoms):,}."
        )

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
        transformed_shift = primitive_shift @ rotation @ deformation
        for index in selected:
            transformed_position = center + (coordinates[index] - center) @ deformation
            preview_positions.append((transformed_position + transformed_shift).tolist())
            atom_indices.append(index)
            lattice_indices.append(list(point))
            components.append("rotating")
            core_mask.append(bool(core))

    for point, core in target_points:
        append_reference(point, core)
    for point, core in source_points:
        append_selected(point, core)

    return {
        "positions": preview_positions,
        "atom_indices": atom_indices,
        "lattice_indices": lattice_indices,
        "components": components,
        "core_mask": core_mask,
        "core_atom_count": source_area * len(coordinates),
        "preview_atom_count": preview_count,
        "padding_cells": int(padding_cells),
        "cell": (target_matrix @ parent_cell).tolist(),
        "source_cell": (source_matrix @ parent_cell).tolist(),
        "source_matrix_3d": source_matrix.tolist(),
        "target_matrix_3d": target_matrix.tolist(),
        "area_ratio": source_area,
        "deformation_matrix": deformation.tolist(),
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
