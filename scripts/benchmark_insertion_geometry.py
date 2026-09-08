"""Bounded, reproducible timings for exact insertion/MIC geometry kernels.

Run from the repository root with the same Python environment as the tests.
Timings describe this machine and workload; they are not scaling guarantees.
"""

from __future__ import annotations

import json
import statistics
import time

import numpy as np
from ase.geometry import find_mic as ase_find_mic

from v_ase.add_atoms import sample_insertion_positions
from v_ase.insertion_regions import build_insertion_domain
from v_ase.neighbors import find_mic


def median_seconds(operation, repeats=5):
    operation()
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        operation()
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


def main():
    cell = np.array([[4., 0., 0.], [2., 3., 0.], [.4, .2, 4.]])
    vectors = np.random.default_rng(3).uniform(-3., 3., (24, 3)) @ cell
    results = {'repeats': 5, 'mic_calls_per_repeat': 1024, 'mic_vectors_per_call': 24}
    for name, implementation in [('ase_mic', ase_find_mic), ('cached_exact_mic', find_mic)]:
        def run_mic():
            for _ in range(1024):
                implementation(vectors, cell, pbc=True)
        results[name + '_seconds'] = median_seconds(run_mic)
    results['mic_speed_ratio'] = results['ase_mic_seconds'] / results['cached_exact_mic_seconds']
    points = np.random.default_rng(3).uniform(-1., 8., (24, 3))
    cases = [
        ('orthogonal', np.diag([10.] * 3), []),
        ('skew', np.array([[4., 0., 0.], [2., 3., 0.], [0., 0., 4.]]), []),
        ('overlapping_rejects', np.diag([10.] * 3), [
            {'id': 'a', 'role': 'reject', 'bounds': [1, 5, 1, 5, 1, 5]},
            {'id': 'b', 'role': 'reject', 'bounds': [3, 7, 3, 7, 3, 7]},
        ]),
    ]
    for name, projection_cell, regions in cases:
        domain = build_insertion_domain(cell=projection_cell, pbc=[False] * 3, regions=regions)
        results[name + '_projection_24_seconds'] = median_seconds(
            lambda: domain.displacements_to_domain(points),
        )
    for basis in ('cartesian', 'fractional'):
        results[basis + '_homogeneous_128_seconds'] = median_seconds(lambda: sample_insertion_positions(
            np.diag([10.] * 3), [True] * 3, 128, placement_mode='homogeneous',
            coordinate_basis=basis, seed=19,
        ))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
