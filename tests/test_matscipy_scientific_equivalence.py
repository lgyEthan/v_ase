from __future__ import annotations

import numpy as np
from ase import Atoms
from ase.geometry import find_mic
from ase.neighborlist import primitive_neighbor_list as ase_primitive_neighbor_list

import v_ase.analysis as analysis_module
import v_ase.repulsion as repulsion_module
from v_ase.analysis import calculate_rdf
from v_ase.export import _display_bonds
from v_ase.io import set_atom_labels
from v_ase.repulsion import RepulsionCalculator


def _ase_primitive(quantities, **kwargs):
    return ase_primitive_neighbor_list(
        quantities,
        pbc=kwargs["pbc"],
        cell=kwargs["cell"],
        positions=kwargs["positions"],
        cutoff=kwargs["cutoff"],
        numbers=kwargs.get("numbers"),
        self_interaction=kwargs.get("self_interaction", False),
        use_scaled_positions=kwargs.get("use_scaled_positions", False),
    )


def _ase_atoms_neighbours(quantities, atoms, cutoff, *, self_interaction=False):
    return ase_primitive_neighbor_list(
        quantities,
        pbc=atoms.pbc,
        cell=atoms.cell,
        positions=atoms.positions,
        cutoff=cutoff,
        numbers=atoms.numbers,
        self_interaction=self_interaction,
        use_scaled_positions=False,
    )


def test_periodic_rdf_matches_ase_oracle_for_long_triclinic_cutoff(monkeypatch):
    rng = np.random.default_rng(20260821)
    cell = np.asarray([
        [4.2, 0.0, 0.0],
        [1.6, 3.8, 0.0],
        [1.1, 0.7, 3.4],
    ])
    atoms = Atoms(
        "Cu6O6",
        scaled_positions=rng.uniform(-0.4, 1.4, size=(12, 3)),
        cell=cell,
        pbc=True,
    )
    set_atom_labels(
        atoms,
        ["Cu_surface" if index % 2 == 0 else "O_ads" for index in range(len(atoms))],
    )
    options = {
        "cutoff": 6.2,
        "bins": 64,
        "pair_mode": "all",
        "frame_index": 3,
    }
    actual = calculate_rdf(atoms, **options)

    monkeypatch.setattr(analysis_module, "neighbour_list", _ase_atoms_neighbours)
    expected = calculate_rdf(atoms, **options)

    np.testing.assert_allclose(actual.radius, expected.radius, rtol=0, atol=0)
    np.testing.assert_allclose(actual.total, expected.total, rtol=0, atol=2e-14)
    assert actual.partial.keys() == expected.partial.keys()
    for key in actual.partial:
        np.testing.assert_allclose(actual.partial[key], expected.partial[key], rtol=0, atol=2e-14)
    assert actual.periodic_image_extent == expected.periodic_image_extent
    assert actual.periodic_image_span == expected.periodic_image_span


def _repulsion_result(atoms):
    target = atoms.copy()
    target.calc = RepulsionCalculator(
        pair_cutoffs={
            "H_a|H_a": 2.1,
            "H_a|H_b": 2.6,
            "H_b|H_b": 1.8,
            "H|H": 2.3,
        },
        cutoff_mode="absolute",
        k_repulsion=2.7,
        max_force_norm=None,
        mic=True,
        backend="numpy",
    )
    return target.get_potential_energy(), target.get_forces()


def test_repulsion_energy_and_forces_match_ase_oracle_with_partial_pbc(monkeypatch):
    cell = np.asarray([
        [4.5, 0.0, 0.0],
        [1.1, 5.2, 0.0],
        [0.8, 0.5, 4.1],
    ])
    atoms = Atoms(
        "H6",
        positions=[
            [-0.3, -3.2, 0.4],
            [1.1, -2.9, 0.8],
            [4.2, 6.8, 3.9],
            [5.0, 7.2, 4.5],
            [2.2, 1.1, -0.4],
            [3.5, 1.4, 0.2],
        ],
        cell=cell,
        pbc=[True, False, True],
    )
    set_atom_labels(atoms, ["H_a", "H_b", "H_a", "H_b", "H_a", "H_b"])
    actual_energy, actual_forces = _repulsion_result(atoms)
    assert actual_energy > 0.0
    assert np.linalg.norm(actual_forces) > 0.0

    monkeypatch.setattr(repulsion_module, "primitive_neighbour_list", _ase_primitive)
    expected_energy, expected_forces = _repulsion_result(atoms)

    np.testing.assert_allclose(actual_energy, expected_energy, rtol=0, atol=2e-12)
    np.testing.assert_allclose(actual_forces, expected_forces, rtol=0, atol=3e-12)


def test_repulsion_force_is_negative_energy_gradient_and_conserves_momentum():
    atoms = Atoms(
        "H5",
        positions=[
            [0.0, 0.0, 0.0],
            [1.1, 0.2, 0.1],
            [0.3, 1.4, -0.2],
            [1.4, 1.2, 0.4],
            [0.8, 0.6, 1.3],
        ],
        pbc=False,
    )
    atoms.calc = RepulsionCalculator(
        pair_cutoffs={"H|H": 2.25},
        cutoff_mode="absolute",
        k_repulsion=1.9,
        max_force_norm=None,
        mic=False,
        backend="numpy",
    )
    analytic = atoms.get_forces()
    step = 1.0e-6
    numerical = np.zeros_like(analytic)
    original = atoms.positions.copy()
    for atom_index in range(len(atoms)):
        for axis in range(3):
            atoms.positions[:] = original
            atoms.positions[atom_index, axis] += step
            atoms.calc.reset()
            energy_plus = atoms.get_potential_energy()
            atoms.positions[:] = original
            atoms.positions[atom_index, axis] -= step
            atoms.calc.reset()
            energy_minus = atoms.get_potential_energy()
            numerical[atom_index, axis] = -(energy_plus - energy_minus) / (2.0 * step)
    atoms.positions[:] = original

    np.testing.assert_allclose(analytic, numerical, rtol=0, atol=2e-8)
    np.testing.assert_allclose(np.sum(analytic, axis=0), 0.0, rtol=0, atol=2e-12)
    center = np.mean(original, axis=0)
    torque = np.sum(np.cross(original - center, analytic), axis=0)
    np.testing.assert_allclose(torque, 0.0, rtol=0, atol=2e-12)


def test_repulsion_is_invariant_to_periodic_lattice_translation():
    cell = np.asarray([
        [4.0, 0.0, 0.0],
        [1.3, 3.7, 0.0],
        [0.9, 0.6, 3.5],
    ])
    atoms = Atoms(
        "H4",
        scaled_positions=[
            [0.05, 0.12, 0.08],
            [0.32, 0.18, 0.15],
            [0.68, 0.74, 0.61],
            [0.91, 0.79, 0.72],
        ],
        cell=cell,
        pbc=True,
    )
    baseline_energy, baseline_forces = _repulsion_result(atoms)
    assert baseline_energy > 0.0
    assert np.linalg.norm(baseline_forces) > 0.0
    translated = atoms.copy()
    translated.positions[1] += 2 * cell[0] - cell[1] + cell[2]
    translated_energy, translated_forces = _repulsion_result(translated)

    np.testing.assert_allclose(translated_energy, baseline_energy, rtol=0, atol=2e-12)
    np.testing.assert_allclose(translated_forces, baseline_forces, rtol=0, atol=3e-12)


def test_export_bond_uses_exact_ase_mic_for_strongly_skewed_cell():
    cell = np.asarray([
        [3.0, 0.0, 0.0],
        [2.6158972002528644, 1.1486959245499533, 0.0],
        [1.5757616109566956, 0.6454809793612374, 0.7332782990120118],
    ])
    direct = np.asarray([-0.5492369411735343, 0.045482589579532995, 0.5349735207449247])
    data = {
        "positions": [[0.0, 0.0, 0.0], direct.tolist()],
        "symbols": ["A", "B"],
        "chemical_symbols": ["H", "He"],
        "cell": cell.tolist(),
        "pbc": [True, True, True],
        "visual": {"covalent_radii": [0.31, 0.28]},
    }
    display = {
        "showBonds": True,
        "showPeriodicBonds": True,
        "bondMode": "pairwise",
        "pairwiseBondCutoffs": {"A-B": 1.0},
    }

    bonds = _display_bonds(data, display)
    expected_vector, expected_distance = find_mic(direct, cell, pbc=True)

    assert len(bonds) == 1
    np.testing.assert_allclose(bonds[0]["end"], expected_vector, rtol=0, atol=2e-12)
    np.testing.assert_allclose(bonds[0]["length"], expected_distance, rtol=0, atol=2e-12)
