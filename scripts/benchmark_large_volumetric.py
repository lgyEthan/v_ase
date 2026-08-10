"""Benchmark large volumetric imports and isosurface generation.

Pass any CHG/CHGCAR, LOCPOT, PARCHG, ELFCAR, Cube, or XSF file. The
benchmark does not modify or copy the input and reports process peak RSS.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

from v_ase.volumetric import (
    generate_isosurface,
    generate_volumetric_plane,
    read_volumetric_file,
)


def benchmark(
    path: Path,
    *,
    precision: str,
    step_size: int,
    smearing_sigma: float,
    smoothing_iterations: int,
    plane_resolution: int,
) -> dict:
    started = time.perf_counter()
    datasets = read_volumetric_file(path, precision=precision)
    parse_seconds = time.perf_counter() - started
    dataset = datasets[0]
    if dataset.minimum < 0 < dataset.maximum:
        magnitude = max(abs(dataset.minimum), abs(dataset.maximum)) * 0.18
        level = magnitude if magnitude < dataset.maximum else -magnitude
    else:
        level = dataset.minimum + (dataset.maximum - dataset.minimum) * 0.22

    started = time.perf_counter()
    mesh = generate_isosurface(
        dataset,
        level,
        step_size=step_size,
        smearing_sigma=smearing_sigma,
        smoothing_iterations=smoothing_iterations,
    )
    mesh_seconds = time.perf_counter() - started
    started = time.perf_counter()
    cached = generate_isosurface(
        dataset,
        level,
        step_size=step_size,
        smearing_sigma=smearing_sigma,
        smoothing_iterations=smoothing_iterations,
    )
    cache_seconds = time.perf_counter() - started

    plane_hkl = np.asarray([0.0, 0.0, 1.0])
    plane_normal = np.linalg.solve(dataset.cell, plane_hkl)
    plane_normal /= np.linalg.norm(plane_normal)
    corners = np.asarray([
        [a, b, c]
        for a in (0.0, 1.0)
        for b in (0.0, 1.0)
        for c in (0.0, 1.0)
    ]) @ dataset.cell
    projections = corners @ plane_normal
    plane_offset = float((np.min(projections) + np.max(projections)) * 0.5)
    started = time.perf_counter()
    plane = generate_volumetric_plane(
        dataset,
        plane_hkl,
        plane_offset,
        resolution=plane_resolution,
    )
    plane_seconds = time.perf_counter() - started
    started = time.perf_counter()
    cached_plane = generate_volumetric_plane(
        dataset,
        plane_hkl,
        plane_offset,
        resolution=plane_resolution,
    )
    plane_cache_seconds = time.perf_counter() - started

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mib = peak_rss / (1024 * 1024) if sys.platform == "darwin" else peak_rss / 1024
    return {
        "input": str(path),
        "input_bytes": path.stat().st_size,
        "datasets": len(datasets),
        "shape": list(dataset.values.shape),
        "precision": dataset.precision,
        "step_size": step_size,
        "smearing_sigma": smearing_sigma,
        "smoothing_iterations": smoothing_iterations,
        "grid_bytes": dataset.values.nbytes,
        "parse_seconds": round(parse_seconds, 4),
        "mesh_seconds": round(mesh_seconds, 4),
        "cached_mesh_seconds": round(cache_seconds, 6),
        "level": level,
        "vertices": len(mesh.vertices),
        "triangles": len(mesh.faces),
        "mesh_bytes": mesh.vertices.nbytes + mesh.faces.nbytes,
        "cache_identity_preserved": cached is mesh,
        "histogram_bins": len(dataset.summary()["histogram"]["counts"]),
        "histogram_voxels": sum(dataset.summary()["histogram"]["counts"]),
        "absolute_histogram_voxels": sum(
            dataset.summary()["absolute_histogram"]["counts"]
        ),
        "plane_hkl": plane_hkl.tolist(),
        "plane_resolution": plane_resolution,
        "plane_dimensions": [plane.width, plane.height],
        "plane_seconds": round(plane_seconds, 4),
        "cached_plane_seconds": round(plane_cache_seconds, 6),
        "plane_bytes": plane.values.nbytes,
        "plane_cache_identity_preserved": cached_plane is plane,
        "peak_rss_mib": round(peak_rss_mib, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--precision", choices=("fp32", "fp64"), default="fp32")
    parser.add_argument("--step-size", type=int, choices=range(1, 9), default=1)
    parser.add_argument("--smearing-sigma", type=float, default=0.0)
    parser.add_argument("--smoothing-iterations", type=int, default=4)
    parser.add_argument("--plane-resolution", type=int, default=512)
    parser.add_argument("--max-parse-seconds", type=float)
    args = parser.parse_args()

    result = benchmark(
        args.input.expanduser().resolve(),
        precision=args.precision,
        step_size=args.step_size,
        smearing_sigma=args.smearing_sigma,
        smoothing_iterations=args.smoothing_iterations,
        plane_resolution=args.plane_resolution,
    )
    print(json.dumps(result, indent=2))
    if (
        args.max_parse_seconds is not None
        and result["parse_seconds"] > args.max_parse_seconds
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
