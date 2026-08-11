"""Periodic in-plane registry maps for selected interfacial atoms."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from ase import Atoms
from ase.data import covalent_radii
from ase.geometry import find_mic

from .commensurate import project_periodic_lattice
from .io import atom_labels


MAX_REGISTRY_GRID = 160
ProgressCallback = Callable[[float, str], None]


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
    periodic_axes: tuple[int, int]
    translation_basis: np.ndarray
    optimum_fractional: tuple[float, float]
    optimum_value: float
    baseline_pair_count: int
    warnings: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "schema": "v_ase.registry-map.v1",
            "x_fractional": self.x_fractional.tolist(),
            "y_fractional": self.y_fractional.tolist(),
            "values": self.values.tolist(),
            "metric": self.metric,
            "metric_label": self.metric_label,
            "selected_indices": list(self.selected_indices),
            "host_indices": list(self.host_indices),
            "reference_component": "unselected-host",
            "mobile_component": "selected-guest",
            "periodic_axes": list(self.periodic_axes),
            "translation_basis_angstrom": self.translation_basis.tolist(),
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

    projected = project_periodic_lattice(atoms.cell.array, atoms.pbc, "Z")
    if projected.axis_alignment < 0.985:
        raise ValueError(
            "Registry mapping is restricted to structures whose periodic interface plane is XY."
        )
    axis_a, axis_b = projected.periodic_axes
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
            translation = x_fraction * cell[axis_a] + y_fraction * cell[axis_b]
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
        periodic_axes=(int(axis_a), int(axis_b)),
        translation_basis=np.asarray([cell[axis_a], cell[axis_b]], dtype=float),
        optimum_fractional=(float(x_values[optimum_x]), float(y_values[optimum_y])),
        optimum_value=float(values[optimum_y, optimum_x]),
        baseline_pair_count=int(np.count_nonzero(baseline_mask)),
        warnings=warnings,
    )


def registry_map_csv(result: RegistryMapResult) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["# schema", "v_ase.registry-map.v1"])
    writer.writerow(["# metric", result.metric])
    writer.writerow(["# metric_label", result.metric_label])
    writer.writerow(["# lower_is_better", "true"])
    writer.writerow(["# selected_indices", " ".join(str(value) for value in result.selected_indices)])
    writer.writerow(["# mobile_component", "selected-guest"])
    writer.writerow(["# reference_component", "unselected-host"])
    writer.writerow(["# translation_domain_fractional", "0 <= u < 1; 0 <= v < 1"])
    writer.writerow(["# periodic_axes", *result.periodic_axes])
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
