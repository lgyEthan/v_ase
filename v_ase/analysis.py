"""Numerically validated structural analysis routines."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from itertools import combinations_with_replacement
from typing import Any, Iterable, Sequence

import numpy as np
from ase import Atoms

from .io import atom_labels
from .neighbors import neighbour_list


MAX_RDF_BINS = 5000
DEFAULT_RDF_BINS = 200


@dataclass(frozen=True)
class RdfResult:
    radius: np.ndarray
    total: np.ndarray
    partial: dict[str, np.ndarray]
    requested_cutoff: float
    cutoff: float
    safe_cutoff: float
    bins: int
    pair_mode: str
    warnings: tuple[str, ...]
    periodic_image_extent: tuple[int, int, int]
    periodic_image_span: tuple[int, int, int]
    analysis_kind: str
    title: str
    y_label: str
    normalization: str
    frame_index: int = 0

    def payload(self) -> dict[str, Any]:
        return {
            "schema": "v_ase.rdf.v1",
            "radius": self.radius.tolist(),
            "total": self.total.tolist(),
            "partial": {
                key: values.tolist()
                for key, values in self.partial.items()
            },
            "requested_cutoff": self.requested_cutoff,
            "cutoff": self.cutoff,
            "unique_mic_cutoff": self.safe_cutoff,
            # Retained for v_ase.rdf.v1 clients released before 0.1.2.
            "safe_cutoff": self.safe_cutoff,
            "bins": self.bins,
            "pair_mode": self.pair_mode,
            "warnings": list(self.warnings),
            "periodic_image_extent": list(self.periodic_image_extent),
            "periodic_image_span": list(self.periodic_image_span),
            "analysis_kind": self.analysis_kind,
            "title": self.title,
            "y_label": self.y_label,
            "normalization": self.normalization,
            "frame_index": self.frame_index,
        }


def _cell_face_heights(cell: np.ndarray) -> np.ndarray:
    volume = abs(float(np.linalg.det(cell)))
    heights = np.empty(3, dtype=float)
    for axis in range(3):
        other = [index for index in range(3) if index != axis]
        area = float(np.linalg.norm(np.cross(cell[other[0]], cell[other[1]])))
        if area <= 1e-14:
            raise ValueError("RDF requires a non-degenerate three-dimensional cell.")
        heights[axis] = volume / area
    return heights


def safe_rdf_cutoff(atoms: Atoms) -> float:
    """Return the unique-MIC reference radius for an arbitrary triclinic cell.

    This remains the automatic cutoff when none is supplied. Explicit larger
    cutoffs are valid: :func:`calculate_rdf` counts every required periodic
    image instead of reducing the requested radius.
    """

    if len(atoms) < 1:
        raise ValueError("RDF requires at least one atom.")
    pbc = np.asarray(atoms.pbc, dtype=bool)
    if not np.any(pbc):
        if len(atoms) < 2:
            raise ValueError("A finite-system pair-distribution function requires at least two atoms.")
        span = np.ptp(np.asarray(atoms.positions, dtype=float), axis=0)
        cutoff = float(np.linalg.norm(span))
        return max(cutoff, 1e-8)
    if not np.all(pbc):
        raise ValueError(
            "RDF normalization currently requires periodic boundaries in x, y, and z. "
            "A partial-PBC slab or wire needs a geometry-specific boundary correction "
            "and is not reported as either bulk g(r) or a finite pair distribution."
        )
    cell = np.asarray(atoms.cell.array, dtype=float)
    if cell.shape != (3, 3) or abs(float(np.linalg.det(cell))) <= 1e-12:
        raise ValueError("RDF requires a finite three-dimensional unit cell.")
    return 0.5 * float(np.min(_cell_face_heights(cell)))


def _selected_label_pairs(
    labels: np.ndarray,
    pair_mode: str,
    active_pairs: Iterable[Any] | None,
) -> tuple[str, list[str], dict[str, int], set[tuple[str, str]]]:
    ordered_labels = list(dict.fromkeys(labels.tolist()))
    counts = {
        label: int(np.count_nonzero(labels == label))
        for label in ordered_labels
    }
    mode = str(pair_mode or "active").lower()
    if mode not in {"active", "selected", "all", "none"}:
        raise ValueError("RDF pair mode must be active, selected, all, or none.")
    if mode == "all":
        selected_pairs = {
            _canonical_pair(left, right)
            for left, right in combinations_with_replacement(ordered_labels, 2)
        }
    elif mode in {"active", "selected"}:
        selected_pairs = parse_pair_keys(active_pairs)
    else:
        selected_pairs = set()
    return mode, ordered_labels, counts, selected_pairs


def _finite_pair_distribution(
    atoms: Atoms,
    *,
    requested: float,
    safe_cutoff: float,
    bins: int,
    pair_mode: str,
    active_pairs: Iterable[Any] | None,
    frame_index: int,
) -> RdfResult:
    """Return a boundary-unbiased probability density for a finite structure."""
    natoms = len(atoms)
    if natoms < 2:
        raise ValueError("A finite-system pair-distribution function requires at least two atoms.")
    edges = np.linspace(0.0, requested, bins + 1, dtype=float)
    radius = 0.5 * (edges[:-1] + edges[1:])
    widths = np.diff(edges)
    labels = np.asarray(atom_labels(atoms), dtype=str)
    mode, ordered_labels, counts, selected_pairs = _selected_label_pairs(
        labels,
        pair_mode,
        active_pairs,
    )
    # Request the next representable float so a pair exactly on the public
    # cutoff retains NumPy histogram's inclusive final-edge behavior.
    search_cutoff = np.nextafter(requested, np.inf)
    indices_i, indices_j, distances = neighbour_list(
        "ijd",
        atoms,
        search_cutoff,
        self_interaction=False,
    )
    unordered = (indices_i < indices_j) & (distances <= requested)
    indices_i = np.asarray(indices_i[unordered], dtype=int)
    indices_j = np.asarray(indices_j[unordered], dtype=int)
    distances = np.asarray(distances[unordered], dtype=float)
    total_histogram = np.histogram(distances, bins=edges)[0].astype(float)

    partial_histograms: dict[str, np.ndarray] = {}
    labels_i = labels[indices_i]
    labels_j = labels[indices_j]
    for left, right in combinations_with_replacement(ordered_labels, 2):
        if _canonical_pair(left, right) not in selected_pairs:
            continue
        if left == right:
            mask = (labels_i == left) & (labels_j == right)
        else:
            mask = (
                ((labels_i == left) & (labels_j == right))
                | ((labels_i == right) & (labels_j == left))
            )
        partial_histograms[pair_key(left, right)] = np.histogram(
            distances[mask],
            bins=edges,
        )[0].astype(float)

    total_population = float(natoms * (natoms - 1) // 2)
    total = np.divide(
        total_histogram,
        total_population * widths,
        out=np.zeros_like(total_histogram),
        where=widths > 0,
    )
    partial: dict[str, np.ndarray] = {}
    for left, right in combinations_with_replacement(ordered_labels, 2):
        key = pair_key(left, right)
        histogram = partial_histograms.get(key)
        if histogram is None:
            continue
        population = (
            counts[left] * (counts[left] - 1) / 2
            if left == right
            else counts[left] * counts[right]
        )
        normalization = float(population) * widths
        partial[key] = np.divide(
            histogram,
            normalization,
            out=np.zeros_like(histogram),
            where=normalization > 0,
        )

    return RdfResult(
        radius=radius,
        total=total,
        partial=partial,
        requested_cutoff=requested,
        cutoff=requested,
        safe_cutoff=safe_cutoff,
        bins=bins,
        pair_mode=mode,
        warnings=(),
        periodic_image_extent=(0, 0, 0),
        periodic_image_span=(1, 1, 1),
        analysis_kind="pair-distribution",
        title="Pair-distribution function",
        y_label="Pair probability / Å⁻¹",
        normalization="finite unordered-pair probability density; integral is one at full cutoff",
        frame_index=int(frame_index),
    )


def _canonical_pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def pair_key(left: str, right: str) -> str:
    first, second = _canonical_pair(str(left), str(right))
    return f"{first}|{second}"


def parse_pair_keys(values: Iterable[Any] | None) -> set[tuple[str, str]]:
    parsed: set[tuple[str, str]] = set()
    for value in values or []:
        if isinstance(value, str):
            tokens = value.split("|", 1)
        elif isinstance(value, Sequence) and len(value) == 2:
            tokens = [str(value[0]), str(value[1])]
        else:
            continue
        if len(tokens) == 2 and tokens[0] and tokens[1]:
            parsed.add(_canonical_pair(tokens[0], tokens[1]))
    return parsed


def calculate_rdf(
    atoms: Atoms,
    *,
    cutoff: float | None = None,
    bins: int = DEFAULT_RDF_BINS,
    pair_mode: str = "active",
    active_pairs: Iterable[Any] | None = None,
    frame_index: int = 0,
) -> RdfResult:
    """Compute a periodic total and label-resolved instantaneous RDF.

    The histogram uses directed neighbors and the simulation-cell number
    density.  Partial curves follow the concentration weighting convention
    ``g = sum(c_a*c_b*g_ab)`` with a factor of two for mixed pairs.
    """

    safe_cutoff = safe_rdf_cutoff(atoms)
    requested = float(cutoff) if cutoff is not None else safe_cutoff
    if not np.isfinite(requested) or requested <= 0:
        raise ValueError("RDF cutoff must be a positive finite distance.")
    clean_bins = int(bins)
    if clean_bins < 8 or clean_bins > MAX_RDF_BINS:
        raise ValueError(f"RDF bins must be between 8 and {MAX_RDF_BINS}.")

    warnings: list[str] = []
    effective = requested

    pbc = np.asarray(atoms.pbc, dtype=bool)
    if not np.any(pbc):
        return _finite_pair_distribution(
            atoms,
            requested=requested,
            safe_cutoff=safe_cutoff,
            bins=clean_bins,
            pair_mode=pair_mode,
            active_pairs=active_pairs,
            frame_index=frame_index,
        )

    # Matscipy enumerates all periodic cell shifts required by the scalar cutoff.
    # With self_interaction=False it removes only the zero-shift i == j pair,
    # while retaining physically distinct copies of the same basis atom.
    indices_i, indices_j, shifts, distances = neighbour_list(
        "ijSd",
        atoms,
        effective,
        self_interaction=False,
    )
    if len(shifts):
        periodic_image_extent_array = np.max(np.abs(shifts), axis=0).astype(int)
    else:
        periodic_image_extent_array = np.zeros(3, dtype=int)
    periodic_image_extent = tuple(
        int(value) for value in periodic_image_extent_array
    )
    periodic_image_span = tuple(
        2 * int(value) + 1 for value in periodic_image_extent_array
    )
    edges = np.linspace(0.0, effective, clean_bins + 1, dtype=float)
    radius = 0.5 * (edges[:-1] + edges[1:])
    shell_volume = (4.0 * np.pi / 3.0) * (edges[1:] ** 3 - edges[:-1] ** 3)
    cell_volume = abs(float(np.linalg.det(np.asarray(atoms.cell.array, dtype=float))))
    natoms = len(atoms)

    total_histogram = np.histogram(distances, bins=edges)[0].astype(float)
    total_normalization = (float(natoms) ** 2 / cell_volume) * shell_volume
    total = np.divide(
        total_histogram,
        total_normalization,
        out=np.zeros_like(total_histogram),
        where=total_normalization > 0,
    )

    # Let NumPy size the Unicode dtype from the actual labels. A fixed-width
    # dtype can silently merge distinct user labels that share a long prefix.
    labels = np.asarray(atom_labels(atoms), dtype=str)
    mode, ordered_labels, counts, selected_pairs = _selected_label_pairs(
        labels,
        pair_mode,
        active_pairs,
    )

    partial: dict[str, np.ndarray] = {}
    empty_labels = np.asarray([], dtype=labels.dtype)
    labels_i = labels[indices_i] if len(indices_i) else empty_labels
    labels_j = labels[indices_j] if len(indices_j) else empty_labels
    for left, right in combinations_with_replacement(ordered_labels, 2):
        canonical = _canonical_pair(left, right)
        if canonical not in selected_pairs:
            continue
        if left == right:
            mask = (labels_i == left) & (labels_j == right)
            pair_population = float(counts[left] ** 2)
        else:
            mask = (
                ((labels_i == left) & (labels_j == right))
                | ((labels_i == right) & (labels_j == left))
            )
            pair_population = float(2 * counts[left] * counts[right])
        histogram = np.histogram(distances[mask], bins=edges)[0].astype(float)
        normalization = (pair_population / cell_volume) * shell_volume
        partial[pair_key(left, right)] = np.divide(
            histogram,
            normalization,
            out=np.zeros_like(histogram),
            where=normalization > 0,
        )

    return RdfResult(
        radius=radius,
        total=total,
        partial=partial,
        requested_cutoff=requested,
        cutoff=effective,
        safe_cutoff=safe_cutoff,
        bins=clean_bins,
        pair_mode=mode,
        warnings=tuple(warnings),
        periodic_image_extent=periodic_image_extent,
        periodic_image_span=periodic_image_span,
        analysis_kind="radial-distribution",
        title="Radial distribution function",
        y_label="g(r)",
        normalization="bulk number-density normalized radial distribution",
        frame_index=int(frame_index),
    )


def rdf_csv(result: RdfResult) -> bytes:
    """Serialize the plotted RDF columns without locale-dependent formatting."""

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    partial_names = list(result.partial)
    total_column = (
        "total_pair_probability_per_angstrom"
        if result.analysis_kind == "pair-distribution"
        else "total_g_r"
    )
    writer.writerow(["r_angstrom", total_column, *partial_names])
    for row_index, radius in enumerate(result.radius):
        writer.writerow(
            [
                f"{float(radius):.12g}",
                f"{float(result.total[row_index]):.12g}",
                *[
                    f"{float(result.partial[name][row_index]):.12g}"
                    for name in partial_names
                ],
            ]
        )
    return stream.getvalue().encode("utf-8")
