"""Periodic in-plane registry maps for selected interfacial atoms."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import math
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from ase import Atoms
from ase.data import covalent_radii
from ase.geometry import find_mic

from .io import atom_labels


MAX_REGISTRY_GRID = 160
ProgressCallback = Callable[[float, str], None]


def normalized_hkl(hkl: Sequence[int | float]) -> tuple[int, int, int]:
    """Return a primitive, sign-canonical Miller-index triplet."""

    raw = np.asarray(hkl, dtype=float)
    if raw.shape != (3,) or not np.all(np.isfinite(raw)):
        raise ValueError("hkl must contain three finite integer values.")
    rounded = np.rint(raw).astype(np.int64)
    if not np.allclose(raw, rounded, atol=1e-10):
        raise ValueError("hkl must contain integer Miller indices.")
    divisor = math.gcd(math.gcd(abs(int(rounded[0])), abs(int(rounded[1]))), abs(int(rounded[2])))
    if divisor == 0:
        raise ValueError("hkl cannot be (0, 0, 0).")
    primitive = rounded // divisor
    first = next(int(value) for value in primitive if value != 0)
    if first < 0:
        primitive *= -1
    return tuple(int(value) for value in primitive)


def _extended_gcd(left: int, right: int) -> tuple[int, int, int]:
    old_remainder, remainder = abs(int(left)), abs(int(right))
    old_left, current_left = 1, 0
    old_right, current_right = 0, 1
    while remainder:
        quotient = old_remainder // remainder
        old_remainder, remainder = remainder, old_remainder - quotient * remainder
        old_left, current_left = current_left, old_left - quotient * current_left
        old_right, current_right = current_right, old_right - quotient * current_right
    return (
        old_remainder,
        old_left if left >= 0 else -old_left,
        old_right if right >= 0 else -old_right,
    )


@dataclass(frozen=True)
class LatticePlane:
    hkl: tuple[int, int, int]
    integer_basis: np.ndarray
    translation_basis: np.ndarray
    plane_basis: np.ndarray
    translation_basis_2d: np.ndarray
    normal: np.ndarray
    periodic_axes: tuple[int, ...]


def lattice_plane(cell: Sequence[Sequence[float]], pbc: Sequence[bool], hkl=(0, 0, 1)) -> LatticePlane:
    """Build a primitive periodic translation lattice for one ``(hkl)`` plane.

    Cell vectors are rows.  Integer translation vectors ``t`` satisfy
    ``h*t[0] + k*t[1] + l*t[2] = 0`` and therefore remain in the plane.
    """

    indices = normalized_hkl(hkl)
    h, k, l = indices
    if h == 0 and k == 0:
        integer_basis = np.asarray([[1, 0, 0], [0, 1, 0]], dtype=np.int64)
    else:
        divisor, coefficient_h, coefficient_k = _extended_gcd(h, k)
        integer_basis = np.asarray([
            [k // divisor, -h // divisor, 0],
            [coefficient_h * l, coefficient_k * l, -divisor],
        ], dtype=np.int64)
    first_nonzero = next(int(value) for value in integer_basis[0] if value != 0)
    if first_nonzero < 0:
        integer_basis *= -1
    if not np.array_equal(np.cross(integer_basis[0], integer_basis[1]), np.asarray(indices)):
        raise RuntimeError("Failed to construct a primitive lattice-plane basis.")

    periodic = np.asarray(pbc, dtype=bool)
    if periodic.shape != (3,):
        raise ValueError("pbc must contain three values.")
    blocked = np.flatnonzero(~periodic)
    if blocked.size and np.any(integer_basis[:, blocked] != 0):
        raise ValueError(
            f"The ({h} {k} {l}) plane does not contain two translations allowed by the current PBC."
        )

    cell_array = np.asarray(cell, dtype=float)
    if cell_array.shape != (3, 3) or not np.all(np.isfinite(cell_array)):
        raise ValueError("A finite 3x3 unit cell is required for planar translation.")
    translation_basis = integer_basis @ cell_array
    normal = np.cross(translation_basis[0], translation_basis[1])
    normal_length = float(np.linalg.norm(normal))
    first_length = float(np.linalg.norm(translation_basis[0]))
    if normal_length <= 1e-12 or first_length <= 1e-12:
        raise ValueError("The selected hkl plane has a degenerate periodic translation basis.")
    normal /= normal_length
    first_unit = translation_basis[0] / first_length
    second_unit = np.cross(normal, first_unit)
    if float(np.dot(second_unit, translation_basis[1])) < 0:
        second_unit *= -1
    plane_basis = np.asarray([first_unit, second_unit], dtype=float)
    translation_basis_2d = translation_basis @ plane_basis.T
    used_axes = tuple(
        int(axis)
        for axis in range(3)
        if periodic[axis] and np.any(integer_basis[:, axis] != 0)
    )
    return LatticePlane(
        hkl=indices,
        integer_basis=integer_basis,
        translation_basis=np.asarray(translation_basis, dtype=float),
        plane_basis=plane_basis,
        translation_basis_2d=np.asarray(translation_basis_2d, dtype=float),
        normal=normal,
        periodic_axes=used_axes,
    )


def _canonical_pair(left: str, right: str) -> str:
    first, second = sorted((str(left), str(right)))
    return f"{first}|{second}"


def _pair_cutoff_table(values: Any) -> dict[str, float]:
    table: dict[str, float] = {}
    if isinstance(values, dict):
        iterator = values.items()
    else:
        iterator = []
        for item in values or []:
            if isinstance(item, dict):
                left = item.get("left")
                right = item.get("right")
                if left is not None and right is not None:
                    iterator.append((_canonical_pair(left, right), item))
    for key, raw in iterator:
        if isinstance(raw, dict):
            enabled = raw.get("enabled", True) is not False
            maximum = raw.get("max", raw.get("cutoff", 0.0))
        else:
            enabled = True
            maximum = raw
        try:
            cutoff = float(maximum)
        except (TypeError, ValueError):
            continue
        if enabled and np.isfinite(cutoff) and cutoff > 0:
            tokens = str(key).split("|", 1)
            if len(tokens) == 2:
                table[_canonical_pair(tokens[0], tokens[1])] = cutoff
    return table


@dataclass(frozen=True)
class RegistryMapResult:
    x_fractional: np.ndarray
    y_fractional: np.ndarray
    values: np.ndarray
    metric: str
    metric_label: str
    selected_indices: tuple[int, ...]
    host_indices: tuple[int, ...]
    hkl: tuple[int, int, int]
    periodic_axes: tuple[int, ...]
    plane_integer_basis: np.ndarray
    translation_basis: np.ndarray
    plane_basis: np.ndarray
    translation_basis_2d: np.ndarray
    plane_normal: np.ndarray
    optimum_fractional: tuple[float, float]
    optimum_value: float
    baseline_pair_count: int
    warnings: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "schema": "v_ase.registry-map.v2",
            "x_fractional": self.x_fractional.tolist(),
            "y_fractional": self.y_fractional.tolist(),
            "values": self.values.tolist(),
            "metric": self.metric,
            "metric_label": self.metric_label,
            "selected_indices": list(self.selected_indices),
            "host_indices": list(self.host_indices),
            "reference_component": "unselected-host",
            "mobile_component": "selected-guest",
            "hkl": list(self.hkl),
            "periodic_axes": list(self.periodic_axes),
            "plane_integer_basis": self.plane_integer_basis.tolist(),
            "translation_basis_angstrom": self.translation_basis.tolist(),
            "plane_basis_cartesian": self.plane_basis.tolist(),
            "translation_basis_2d_angstrom": self.translation_basis_2d.tolist(),
            "plane_normal_cartesian": self.plane_normal.tolist(),
            "translation_domain_fractional": [[0.0, 1.0], [0.0, 1.0]],
            "optimum_fractional": list(self.optimum_fractional),
            "optimum_value": self.optimum_value,
            "baseline_pair_count": self.baseline_pair_count,
            "warnings": list(self.warnings),
            "lower_is_better": True,
            "references": [],
        }


def calculate_registry_map(
    atoms: Atoms,
    selected_indices: Sequence[int],
    *,
    grid_x: int = 32,
    grid_y: int = 32,
    metric: str = "short-contact",
    pair_cutoffs: Any = None,
    hkl: Sequence[int | float] = (0, 0, 1),
    progress_callback: ProgressCallback | None = None,
) -> RegistryMapResult:
    """Scan one host unit cell of in-plane translations.

    ``short-contact`` is a dimensionless geometry score based on covalent-radius
    normalized interfacial distances. ``bond-strain`` tracks the interfacial
    bonds present at the unshifted geometry and reports their RMS relative
    extension. Neither score is an electronic energy.
    """

    selected = tuple(sorted({int(value) for value in selected_indices}))
    if not selected:
        raise ValueError("Select the guest/interface atoms before calculating a registry map.")
    if selected[0] < 0 or selected[-1] >= len(atoms):
        raise ValueError("Registry-map selection contains an invalid atom index.")
    selected_set = set(selected)
    host = tuple(index for index in range(len(atoms)) if index not in selected_set)
    if not host:
        raise ValueError("Registry mapping needs unselected host atoms as a reference.")

    nx, ny = int(grid_x), int(grid_y)
    if nx < 4 or ny < 4 or nx > MAX_REGISTRY_GRID or ny > MAX_REGISTRY_GRID:
        raise ValueError(f"Registry grid dimensions must be between 4 and {MAX_REGISTRY_GRID}.")
    mode = str(metric or "short-contact").strip().lower()
    if mode not in {"short-contact", "bond-strain"}:
        raise ValueError("Registry metric must be short-contact or bond-strain.")

    plane = lattice_plane(atoms.cell.array, atoms.pbc, hkl)
    cell = np.asarray(atoms.cell.array, dtype=float)
    positions = np.asarray(atoms.get_positions(), dtype=float)
    base_vectors = positions[np.asarray(selected)][:, None, :] - positions[np.asarray(host)][None, :, :]
    flattened = base_vectors.reshape(-1, 3)
    mic_vectors, baseline_distances = find_mic(flattened, cell, pbc=atoms.pbc)
    baseline_distances = np.asarray(baseline_distances, dtype=float).reshape(len(selected), len(host))

    atomic_numbers = np.asarray(atoms.get_atomic_numbers(), dtype=int)
    selected_radii = covalent_radii[atomic_numbers[np.asarray(selected)]][:, None]
    host_radii = covalent_radii[atomic_numbers[np.asarray(host)]][None, :]
    reference_lengths = np.maximum(selected_radii + host_radii, 0.2)
    labels = np.asarray(atom_labels(atoms), dtype=str)
    cutoff_table = _pair_cutoff_table(pair_cutoffs)
    baseline_mask = np.zeros_like(baseline_distances, dtype=bool)
    if mode == "bond-strain":
        if not cutoff_table:
            raise ValueError(
                "Bond-strain mapping requires at least one enabled pairwise bond cutoff."
            )
        for selected_row, atom_index in enumerate(selected):
            for host_column, host_index in enumerate(host):
                cutoff = cutoff_table.get(_canonical_pair(labels[atom_index], labels[host_index]), 0.0)
                baseline_mask[selected_row, host_column] = (
                    cutoff > 0 and baseline_distances[selected_row, host_column] <= cutoff
                )
        if not np.any(baseline_mask):
            raise ValueError(
                "No selected-to-host bond lies inside the enabled pairwise cutoffs at the current registry."
            )

    x_values = np.arange(nx, dtype=float) / nx
    y_values = np.arange(ny, dtype=float) / ny
    values = np.empty((ny, nx), dtype=float)
    total = nx * ny

    def report(done: int, stage: str = "Scanning in-plane translations") -> None:
        if progress_callback is not None:
            progress_callback(done / max(total, 1), stage)

    report(0, "Preparing periodic interfacial distances")
    completed = 0
    for y_index, y_fraction in enumerate(y_values):
        for x_index, x_fraction in enumerate(x_values):
            translation = (
                x_fraction * plane.translation_basis[0]
                + y_fraction * plane.translation_basis[1]
            )
            _, distances = find_mic(flattened + translation, cell, pbc=atoms.pbc)
            distances = np.asarray(distances, dtype=float).reshape(len(selected), len(host))
            if mode == "short-contact":
                ratio = distances / reference_lengths
                # A bounded, smooth proxy for short-range overlap. The score
                # is normalized per selected atom and is not labeled energy.
                values[y_index, x_index] = float(
                    np.sum(np.exp(-np.power(ratio, 6.0))) / len(selected)
                )
            else:
                relative = distances[baseline_mask] / reference_lengths[baseline_mask] - 1.0
                values[y_index, x_index] = float(np.sqrt(np.mean(relative * relative)))
            completed += 1
        report(completed)

    optimum_flat = int(np.nanargmin(values))
    optimum_y, optimum_x = np.unravel_index(optimum_flat, values.shape)
    metric_label = (
        "Normalized short-contact score"
        if mode == "short-contact"
        else "Interfacial pair-length mismatch RMS"
    )
    warnings = (
        "Geometry-only score; validate the suggested registry with an appropriate energy calculation.",
    )
    return RegistryMapResult(
        x_fractional=x_values,
        y_fractional=y_values,
        values=values,
        metric=mode,
        metric_label=metric_label,
        selected_indices=selected,
        host_indices=host,
        hkl=plane.hkl,
        periodic_axes=plane.periodic_axes,
        plane_integer_basis=plane.integer_basis,
        translation_basis=plane.translation_basis,
        plane_basis=plane.plane_basis,
        translation_basis_2d=plane.translation_basis_2d,
        plane_normal=plane.normal,
        optimum_fractional=(float(x_values[optimum_x]), float(y_values[optimum_y])),
        optimum_value=float(values[optimum_y, optimum_x]),
        baseline_pair_count=int(np.count_nonzero(baseline_mask)),
        warnings=warnings,
    )


def registry_map_csv(result: RegistryMapResult) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["# schema", "v_ase.registry-map.v2"])
    writer.writerow(["# metric", result.metric])
    writer.writerow(["# metric_label", result.metric_label])
    writer.writerow(["# lower_is_better", "true"])
    writer.writerow(["# selected_indices", " ".join(str(value) for value in result.selected_indices)])
    writer.writerow(["# mobile_component", "selected-guest"])
    writer.writerow(["# reference_component", "unselected-host"])
    writer.writerow(["# translation_domain_fractional", "0 <= u < 1; 0 <= v < 1"])
    writer.writerow(["# hkl", *result.hkl])
    writer.writerow(["# periodic_axes", *result.periodic_axes])
    writer.writerow(["# plane_integer_basis_a", *result.plane_integer_basis[0]])
    writer.writerow(["# plane_integer_basis_b", *result.plane_integer_basis[1]])
    writer.writerow([
        "# translation_basis_a_angstrom",
        *[f"{float(value):.12g}" for value in result.translation_basis[0]],
    ])
    writer.writerow([
        "# translation_basis_b_angstrom",
        *[f"{float(value):.12g}" for value in result.translation_basis[1]],
    ])
    for warning in result.warnings:
        writer.writerow(["# note", warning])
    writer.writerow([
        "x_fractional",
        "y_fractional",
        "dx_angstrom",
        "dy_angstrom",
        "dz_angstrom",
        "value",
    ])
    for y_index, y_fraction in enumerate(result.y_fractional):
        for x_index, x_fraction in enumerate(result.x_fractional):
            translation = (
                float(x_fraction) * result.translation_basis[0]
                + float(y_fraction) * result.translation_basis[1]
            )
            writer.writerow([
                f"{float(x_fraction):.12g}",
                f"{float(y_fraction):.12g}",
                *[f"{float(value):.12g}" for value in translation],
                f"{float(result.values[y_index, x_index]):.12g}",
            ])
    return stream.getvalue().encode("utf-8")
