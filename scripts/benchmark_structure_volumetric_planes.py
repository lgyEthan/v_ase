"""Benchmark volumetric-plane sampling against an arbitrary atomic structure.

The input remains external and is never copied or modified.  A periodic scalar
field is synthesized from the atom positions so large, skew structures can be
used for repeatable plane-sampling performance and visual QA without claiming
that the generated field is a physical DFT observable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Sequence

import numpy as np
from ase.io import read
from scipy.ndimage import gaussian_filter

from v_ase.volumetric import VolumetricData, generate_volumetric_plane


DEFAULT_HKLS = ((0, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1))


def _triplet(value: str) -> tuple[int, int, int]:
    parts = value.lower().replace("x", ",").split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected three values, for example 144x128x160")
    try:
        result = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("grid dimensions must be integers") from exc
    if any(component < 16 for component in result):
        raise argparse.ArgumentTypeError("every grid dimension must be at least 16")
    return result


def _resolutions(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("resolutions must be comma-separated integers") from exc
    if not result or any(component < 16 or component > 1024 for component in result):
        raise argparse.ArgumentTypeError("plane resolutions must be between 16 and 1024")
    return result


def synthesize_periodic_field(atoms, shape: Sequence[int], sigma: float) -> np.ndarray:
    """Deposit atoms on a periodic grid and apply a bounded Gaussian kernel."""

    shape_array = np.asarray(shape, dtype=int)
    scaled = atoms.get_scaled_positions(wrap=True)
    indices = np.floor(scaled * shape_array[None, :]).astype(int) % shape_array[None, :]
    weights = atoms.get_atomic_numbers().astype(np.float32)
    weights /= max(float(np.max(weights)), 1.0)
    field = np.zeros(tuple(shape_array), dtype=np.float32)
    np.add.at(field, tuple(indices.T), weights)
    modes = tuple("wrap" if periodic else "nearest" for periodic in atoms.pbc)
    field = gaussian_filter(field, sigma=float(sigma), mode=modes, output=np.float32)
    field -= np.mean(field, dtype=np.float64)
    maximum = float(np.max(np.abs(field)))
    if maximum > 0:
        field /= maximum
    return np.ascontiguousarray(field, dtype=np.float32)


def _representative_offset(atoms, dataset: VolumetricData, hkl: Sequence[int]) -> float:
    """Choose the atom-dense slice along a reciprocal-space normal."""

    inverse = dataset._cell_inverse
    normal = inverse @ np.asarray(hkl, dtype=float)
    normal /= np.linalg.norm(normal)
    corners = np.asarray(
        [[a, b, c] for a in (0.0, 1.0) for b in (0.0, 1.0) for c in (0.0, 1.0)]
    ) @ dataset.cell
    projections = corners @ normal
    minimum = float(np.min(projections))
    maximum = float(np.max(projections))
    wrapped = atoms.get_scaled_positions(wrap=True) @ dataset.cell
    atom_projections = wrapped @ normal
    weights = atoms.get_atomic_numbers().astype(float)
    counts, edges = np.histogram(
        atom_projections,
        bins=256,
        range=(minimum, maximum),
        weights=weights,
    )
    peak = int(np.argmax(counts))
    in_peak = (atom_projections >= edges[peak]) & (atom_projections <= edges[peak + 1])
    if np.any(in_peak):
        return float(np.average(atom_projections[in_peak], weights=weights[in_peak]))
    return float((edges[peak] + edges[peak + 1]) * 0.5)


def _peak_rss_mib() -> float | None:
    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def benchmark(
    path: Path,
    *,
    shape: Sequence[int],
    sigma: float,
    resolutions: Sequence[int],
    hkls: Sequence[Sequence[int]] = DEFAULT_HKLS,
) -> tuple[dict, list[tuple[tuple[int, int, int], object]]]:
    started = time.perf_counter()
    atoms = read(path)
    read_seconds = time.perf_counter() - started
    if len(atoms) == 0:
        raise ValueError("benchmark structure contains no atoms")
    if abs(float(np.linalg.det(atoms.cell.array))) <= 1e-12:
        raise ValueError("benchmark structure requires a finite 3D cell")

    started = time.perf_counter()
    values = synthesize_periodic_field(atoms, shape, sigma)
    field_seconds = time.perf_counter() - started
    started = time.perf_counter()
    dataset = VolumetricData(
        name=f"Synthetic field for {path.name}",
        values=values,
        cell=atoms.cell.array,
        origin=np.zeros(3),
        pbc=atoms.pbc,
        atoms=atoms,
        precision="float32",
        quantity="synthetic_benchmark_field",
        units="normalized",
        source_format="generated",
        metadata={"benchmark_only": True, "gaussian_sigma_voxels": float(sigma)},
    )
    dataset_seconds = time.perf_counter() - started

    records = []
    plotted = []
    slowest = 0.0
    for resolution in resolutions:
        for raw_hkl in hkls:
            hkl = tuple(int(value) for value in raw_hkl)
            offset = _representative_offset(atoms, dataset, hkl)
            tracemalloc.start()
            started = time.perf_counter()
            plane = generate_volumetric_plane(
                dataset,
                hkl,
                offset,
                resolution=int(resolution),
            )
            plane_seconds = time.perf_counter() - started
            _current, temporary_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            started = time.perf_counter()
            cached = generate_volumetric_plane(
                dataset,
                hkl,
                offset,
                resolution=int(resolution),
            )
            cache_seconds = time.perf_counter() - started
            slowest = max(slowest, plane_seconds)
            records.append(
                {
                    "hkl": list(hkl),
                    "resolution": int(resolution),
                    "dimensions": [plane.width, plane.height],
                    "seconds": round(plane_seconds, 6),
                    "cached_seconds": round(cache_seconds, 6),
                    "temporary_peak_mib": round(temporary_peak / (1024 * 1024), 2),
                    "plane_bytes": int(plane.values.nbytes),
                    "minimum": float(plane.minimum),
                    "maximum": float(plane.maximum),
                    "cache_identity_preserved": cached is plane,
                }
            )
            if resolution == resolutions[0]:
                plotted.append((hkl, plane))

    result = {
        "input": str(path),
        "input_bytes": path.stat().st_size,
        "atoms": len(atoms),
        "formula": atoms.get_chemical_formula(),
        "cell": atoms.cell.array.tolist(),
        "pbc": atoms.pbc.tolist(),
        "grid_shape": list(values.shape),
        "grid_bytes": int(values.nbytes),
        "read_seconds": round(read_seconds, 6),
        "field_seconds": round(field_seconds, 6),
        "dataset_seconds": round(dataset_seconds, 6),
        "slowest_plane_seconds": round(slowest, 6),
        "plane_results": records,
        "peak_rss_mib": (
            round(peak_rss, 2) if (peak_rss := _peak_rss_mib()) is not None else None
        ),
    }
    result["total_setup_seconds"] = round(
        read_seconds + field_seconds + dataset_seconds,
        6,
    )
    return result, plotted


def save_plot(path: Path, plotted: Sequence[tuple[tuple[int, int, int], object]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    columns = 2
    rows = int(np.ceil(len(plotted) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(9.6, 4.4 * rows), squeeze=False)
    for axis, (hkl, plane) in zip(axes.flat, plotted):
        image = axis.imshow(
            plane.values,
            origin="lower",
            cmap="viridis",
            interpolation="bilinear",
            vmin=plane.minimum,
            vmax=plane.maximum,
        )
        axis.set_title(f"({hkl[0]} {hkl[1]} {hkl[2]})")
        axis.set_axis_off()
        figure.colorbar(image, ax=axis, fraction=0.045, pad=0.03)
    for axis in axes.flat[len(plotted):]:
        axis.set_visible(False)
    figure.suptitle("Internal synthetic volumetric-plane QA")
    figure.tight_layout()
    figure.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--shape", type=_triplet, default=(144, 128, 160))
    parser.add_argument("--sigma", type=float, default=1.35)
    parser.add_argument("--resolutions", type=_resolutions, default=(256, 512, 1024))
    parser.add_argument("--plot-output", type=Path)
    parser.add_argument("--max-setup-seconds", type=float)
    parser.add_argument("--max-plane-seconds", type=float)
    args = parser.parse_args()

    result, plotted = benchmark(
        args.input.expanduser().resolve(),
        shape=args.shape,
        sigma=args.sigma,
        resolutions=args.resolutions,
    )
    if args.plot_output:
        save_plot(args.plot_output.expanduser().resolve(), plotted)
        result["plot_output"] = str(args.plot_output.expanduser().resolve())
    print(json.dumps(result, indent=2))
    if (
        args.max_setup_seconds is not None
        and result["total_setup_seconds"] > args.max_setup_seconds
    ):
        return 1
    if (
        args.max_plane_seconds is not None
        and result["slowest_plane_seconds"] > args.max_plane_seconds
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
