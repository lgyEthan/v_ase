from __future__ import annotations

from pathlib import Path

import numpy as np
from ase import Atoms
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
