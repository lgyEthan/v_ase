from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.cell import Cell
from ase.neighborlist import primitive_neighbor_list as ase_primitive_neighbor_list

from v_ase.neighbors import neighbour_list, primitive_neighbour_list


ROOT = Path(__file__).resolve().parents[1]


def _canonical(result):
    i, j, vectors, distances = result
    order = np.lexsort((
        np.round(distances, 12),
        np.round(vectors[:, 2], 12),
        np.round(vectors[:, 1], 12),
        np.round(vectors[:, 0], 12),
        j,
        i,
    ))
    return i[order], j[order], vectors[order], distances[order]


def _assert_same_pairs(actual, expected):
    actual_i, actual_j, actual_vectors, actual_distances = _canonical(actual)
    expected_i, expected_j, expected_vectors, expected_distances = _canonical(expected)
    np.testing.assert_array_equal(actual_i, expected_i)
    np.testing.assert_array_equal(actual_j, expected_j)
    np.testing.assert_allclose(actual_vectors, expected_vectors, rtol=0, atol=1e-12)
    np.testing.assert_allclose(actual_distances, expected_distances, rtol=0, atol=1e-12)


def _canonical_shifted(result):
    indices_i, indices_j, shifts, vectors, distances = result
    shifts = np.asarray(shifts, dtype=int)
    vectors = np.asarray(vectors, dtype=float)
    distances = np.asarray(distances, dtype=float)
    order = np.lexsort((
        np.round(distances, 12),
        np.round(vectors[:, 2], 12),
        np.round(vectors[:, 1], 12),
        np.round(vectors[:, 0], 12),
        shifts[:, 2],
        shifts[:, 1],
        shifts[:, 0],
        indices_j,
        indices_i,
    ))
    return (
        np.asarray(indices_i)[order],
        np.asarray(indices_j)[order],
        shifts[order],
        vectors[order],
        distances[order],
    )


def _assert_same_shifted_pairs(actual, expected):
    actual = _canonical_shifted(actual)
    expected = _canonical_shifted(expected)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])
    np.testing.assert_array_equal(actual[2], expected[2])
    np.testing.assert_allclose(actual[3], expected[3], rtol=0, atol=2e-12)
    np.testing.assert_allclose(actual[4], expected[4], rtol=0, atol=2e-12)


def test_triclinic_periodic_search_matches_independent_ase_oracle():
    rng = np.random.default_rng(20260821)
    cell = np.asarray([
        [8.0, 0.0, 0.0],
        [1.7, 7.4, 0.0],
        [0.8, 1.1, 6.8],
    ])
    atoms = Atoms(
        "Cu20O20",
        scaled_positions=rng.random((40, 3)),
        cell=cell,
        pbc=True,
    )
    cutoff = 7.5
    actual = neighbour_list("ijDd", atoms, cutoff)
    expected = ase_primitive_neighbor_list(
        "ijDd",
        pbc=atoms.pbc,
        cell=atoms.cell,
        positions=atoms.positions,
        cutoff=cutoff,
        numbers=atoms.numbers,
        self_interaction=False,
        use_scaled_positions=False,
    )
    _assert_same_pairs(actual, expected)


def test_cell_free_search_uses_exact_cartesian_distances():
    rng = np.random.default_rng(71)
    positions = rng.uniform(-4.0, 7.0, size=(80, 3))
    cutoff = 2.4
    actual = primitive_neighbour_list(
        "ijDd",
        pbc=[False, False, False],
        cell=np.zeros((3, 3)),
        positions=positions,
        cutoff=cutoff,
        numbers=np.ones(len(positions), dtype=int),
    )
    expected = ase_primitive_neighbor_list(
        "ijDd",
        pbc=[False, False, False],
        cell=np.zeros((3, 3)),
        positions=positions,
        cutoff=cutoff,
        numbers=np.ones(len(positions), dtype=int),
        self_interaction=False,
        use_scaled_positions=False,
    )
    _assert_same_pairs(actual, expected)


def test_rank_deficient_partial_periodic_search_preserves_periodic_images():
    rng = np.random.default_rng(91)
    positions = rng.random((60, 3)) * np.asarray([9.0, 8.0, 6.0])
    cell = np.asarray([[9.0, 0.0, 0.0], [1.1, 8.0, 0.0], [0.0, 0.0, 0.0]])
    pbc = np.asarray([True, True, False])
    cutoff = 2.2
    actual = primitive_neighbour_list(
        "ijDd",
        pbc=pbc,
        cell=cell,
        positions=positions,
        cutoff=cutoff,
        numbers=np.ones(len(positions), dtype=int),
    )
    expected = ase_primitive_neighbor_list(
        "ijDd",
        pbc=pbc,
        cell=cell,
        positions=positions,
        cutoff=cutoff,
        numbers=np.ones(len(positions), dtype=int),
        self_interaction=False,
        use_scaled_positions=False,
    )
    _assert_same_pairs(actual, expected)


def test_native_pair_cutoff_table_matches_ase_for_encoded_label_types():
    rng = np.random.default_rng(301)
    positions = rng.random((90, 3)) @ np.asarray([
        [10.0, 0.0, 0.0],
        [1.2, 9.0, 0.0],
        [0.4, 0.8, 8.0],
    ])
    type_ids = np.asarray([(index % 4) + 1 for index in range(len(positions))])
    cutoffs = {
        (1, 1): 1.1,
        (1, 2): 2.0,
        (1, 4): 1.7,
        (2, 3): 2.4,
        (3, 4): 1.5,
        (4, 4): 2.2,
    }
    cell = np.asarray([
        [10.0, 0.0, 0.0],
        [1.2, 9.0, 0.0],
        [0.4, 0.8, 8.0],
    ])
    actual = primitive_neighbour_list(
        "ijDd",
        pbc=True,
        cell=cell,
        positions=positions,
        cutoff=cutoffs,
        numbers=type_ids,
    )
    expected = ase_primitive_neighbor_list(
        "ijDd",
        pbc=[True, True, True],
        cell=cell,
        positions=positions,
        cutoff=cutoffs,
        numbers=type_ids,
        self_interaction=False,
        use_scaled_positions=False,
    )
    _assert_same_pairs(actual, expected)


@pytest.mark.parametrize("seed", [17, 41, 89])
@pytest.mark.parametrize(
    ("cell", "pbc"),
    [
        (np.zeros((3, 3)), [False, False, False]),
        (np.diag([6.0, 5.0, 4.0]), [False, False, False]),
        (
            np.asarray([[6.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
            [True, False, False],
        ),
        (
            np.asarray([[6.0, 0.0, 0.0], [1.3, 5.2, 0.0], [0.0, 0.0, 0.0]]),
            [True, True, False],
        ),
        (
            np.asarray([[6.0, 0.0, 0.0], [1.2, 5.0, 0.0], [0.7, 0.4, 4.5]]),
            [True, False, True],
        ),
        (np.diag([6.0, 5.0, 4.0]), [True, True, True]),
        (
            np.asarray([[6.0, 0.0, 0.0], [2.1, 4.8, 0.0], [1.4, 0.9, 3.9]]),
            [True, True, True],
        ),
    ],
    ids=[
        "cell-free",
        "finite-cell",
        "periodic-wire",
        "periodic-slab",
        "full-cell-partial-pbc",
        "orthogonal-periodic",
        "triclinic-periodic",
    ],
)
def test_search_matrix_matches_ase_for_unwrapped_positions_and_cutoff_forms(seed, cell, pbc):
    rng = np.random.default_rng(seed)
    completed = np.asarray(Cell(cell).complete(), dtype=float)
    positions = rng.uniform(-0.65, 1.65, size=(24, 3)) @ completed
    type_ids = np.asarray([(index % 3) + 1 for index in range(len(positions))])
    cutoff_forms = [
        2.15,
        np.linspace(0.45, 1.10, len(positions)),
        {
            (1, 1): 1.25,
            (1, 2): 2.05,
            (1, 3): 1.65,
            (2, 2): 1.45,
            (2, 3): 2.30,
            (3, 3): 1.85,
        },
    ]

    for cutoff in cutoff_forms:
        actual = primitive_neighbour_list(
            "ijSDd",
            pbc=pbc,
            cell=cell,
            positions=positions,
            cutoff=cutoff,
            numbers=type_ids,
        )
        expected = ase_primitive_neighbor_list(
            "ijSDd",
            pbc=pbc,
            cell=cell,
            positions=positions,
            cutoff=cutoff,
            numbers=type_ids,
            self_interaction=False,
            use_scaled_positions=False,
        )
        _assert_same_shifted_pairs(actual, expected)

        indices_i, indices_j, shifts, vectors, distances = actual
        reconstructed = (
            positions[np.asarray(indices_j, dtype=int)]
            - positions[np.asarray(indices_i, dtype=int)]
            + np.asarray(shifts, dtype=float) @ np.asarray(cell, dtype=float)
        )
        np.testing.assert_allclose(vectors, reconstructed, rtol=0, atol=2e-12)
        np.testing.assert_allclose(
            distances,
            np.linalg.norm(vectors, axis=1),
            rtol=0,
            atol=2e-12,
        )
        nonperiodic = ~np.asarray(pbc, dtype=bool)
        if np.any(nonperiodic):
            np.testing.assert_array_equal(np.asarray(shifts)[:, nonperiodic], 0)


def test_atoms_wrapper_routes_full_rank_partial_pbc_through_finite_axis_guard():
    cell = np.asarray([
        [5.0, 0.0, 0.0],
        [1.2, 4.6, 0.0],
        [0.7, 0.5, 4.1],
    ])
    atoms = Atoms(
        "H6",
        positions=[
            [-0.4, -3.0, 0.2],
            [1.0, -2.7, 0.6],
            [4.7, 7.1, 3.8],
            [5.4, 7.3, 4.4],
            [2.0, 1.2, -0.3],
            [3.4, 1.6, 0.4],
        ],
        cell=cell,
        pbc=[True, False, True],
    )

    actual = neighbour_list("ijSDd", atoms, 2.4)
    expected = ase_primitive_neighbor_list(
        "ijSDd",
        pbc=atoms.pbc,
        cell=atoms.cell,
        positions=atoms.positions,
        cutoff=2.4,
        numbers=atoms.numbers,
        self_interaction=False,
        use_scaled_positions=False,
    )

    _assert_same_shifted_pairs(actual, expected)
    np.testing.assert_array_equal(np.asarray(actual[2])[:, 1], 0)


def test_cutoff_boundary_keeps_ase_strict_less_than_semantics():
    finite = Atoms("H2", positions=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], pbc=False)
    exact_i, exact_j = neighbour_list("ij", finite, 1.0)
    assert len(exact_i) == len(exact_j) == 0

    above_i, above_j = neighbour_list("ij", finite, np.nextafter(1.0, np.inf))
    np.testing.assert_array_equal(above_i, [0, 1])
    np.testing.assert_array_equal(above_j, [1, 0])

    periodic = Atoms("He", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3) * 2.0, pbc=True)
    exact_shifts = neighbour_list("S", periodic, 2.0)
    assert exact_shifts.shape == (0, 3)
    above_shifts = neighbour_list("S", periodic, np.nextafter(2.0, np.inf))
    assert len(above_shifts) == 6
    assert {tuple(value) for value in above_shifts.tolist()} == {
        (-1, 0, 0),
        (0, -1, 0),
        (0, 0, -1),
        (0, 0, 1),
        (0, 1, 0),
        (1, 0, 0),
    }


def test_integer_cutoff_and_empty_inputs_are_normalized_at_the_adapter_boundary():
    atoms = Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]], pbc=False)
    indices_i, indices_j = neighbour_list("ij", atoms, 2)
    np.testing.assert_array_equal(indices_i, [0, 1])
    np.testing.assert_array_equal(indices_j, [1, 0])

    empty_i, empty_vectors = neighbour_list("iD", Atoms(), 2)
    assert empty_i.dtype == np.int32
    assert empty_i.shape == (0,)
    assert empty_vectors.shape == (0, 3)


def test_runtime_modules_do_not_import_ase_neighbor_lists():
    for relative in ("v_ase/analysis.py", "v_ase/repulsion.py", "v_ase/export.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "ase.neighborlist" not in source
    assert "scipy.spatial" not in (ROOT / "v_ase/export.py").read_text(encoding="utf-8")
