"""Independent analytic invariants for the 0.3.1 scientific audit."""

import numpy as np
import pytest
from ase import Atoms

from v_ase.analysis import calculate_rdf
from v_ase.commensurate import find_lattice_matches
from v_ase.repulsion import RepulsionCalculator
from v_ase.volumetric import VolumetricData, combine_volumetric_datasets


def test_default_repulsion_is_the_gradient_of_its_reported_energy():
    atoms = Atoms("H2", positions=[[0, 0, 0], [0.5, 0, 0]])
    atoms.calc = RepulsionCalculator(cutoff_distance=2, k_repulsion=20, backend="numpy")
    # U = k/2 (rc-r)^2, so |F| = k(rc-r) even above the old force cap.
    assert atoms.get_potential_energy() == pytest.approx(22.5)
    np.testing.assert_allclose(atoms.get_forces(), [[-30, 0, 0], [30, 0, 0]])


def test_repulsion_scalar_cutoff_and_reconfigured_radius_basis_are_authoritative():
    from ase.data import atomic_numbers, vdw_radii
    atoms = Atoms("H2", positions=[[0, 0, 0], [1.5, 0, 0]])
    atoms.calc = RepulsionCalculator(min_bondinfo=1.0, backend="numpy")
    assert atoms.get_potential_energy() == 0
    atoms.calc = RepulsionCalculator(backend="numpy")
    assert atoms.get_potential_energy() == 0
    atoms.calc.configure(cutoff_basis="vdw")
    rc = 2 * vdw_radii[atomic_numbers["H"]]
    assert atoms.get_potential_energy() == pytest.approx(0.5 * (rc - 1.5)**2)
    assert RepulsionCalculator(min_bondinfo="vdw").status()["cutoff_basis"] == "vdw"


def test_rdf_rejects_nonfinite_geometry_before_neighbor_search():
    atoms = Atoms("He", positions=[[float("nan"), 0, 0]], cell=[2]*3, pbc=True)
    with pytest.raises(ValueError, match="finite atomic positions"):
        calculate_rdf(atoms)
    atoms.positions[:] = 0
    atoms.cell[0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite three-dimensional"):
        calculate_rdf(atoms)


def test_periodic_repulsion_energy_is_extensive_including_self_images():
    primitive = Atoms("H", cell=[1, 1, 1], pbc=True)
    def evaluate(atoms):
        atoms.calc = RepulsionCalculator(cutoff_distance=1.2, backend="numpy")
        return atoms.get_potential_energy(), atoms.get_forces()
    energy, forces = evaluate(primitive)
    # Six neighbors, half pair weight: 3 * 1/2 * (1.2 - 1)^2.
    assert energy == pytest.approx(0.06)
    np.testing.assert_allclose(forces, 0, atol=1e-14)
    repeated_energy, repeated_forces = evaluate(primitive.repeat((2, 3, 2)))
    assert repeated_energy == pytest.approx(12 * energy)
    np.testing.assert_allclose(repeated_forces, 0, atol=1e-14)


def test_periodic_rdf_includes_the_exact_final_histogram_edge():
    atoms = Atoms("He", cell=[2, 2, 2], pbc=True)
    result = calculate_rdf(atoms, cutoff=2, bins=8, pair_mode="all")
    edges = np.linspace(0, 2, 9)
    shell = 4 * np.pi / 3 * (edges[-1] ** 3 - edges[-2] ** 3)
    assert result.total[-1] == pytest.approx(6 * 8 / shell)
    np.testing.assert_allclose(result.total[:-1], 0)


@pytest.mark.parametrize("bins", [True, 8.5, float("nan"), float("inf")])
def test_rdf_rejects_noninteger_bins(bins):
    with pytest.raises(ValueError, match="bins"):
        calculate_rdf(Atoms("He", cell=[2, 2, 2], pbc=True), bins=bins)


@pytest.mark.parametrize("pbc", [[False, False, False], [True, False, True]])
def test_endpoint_grid_integrates_linear_nonperiodic_field(pbc):
    x, y, z = np.meshgrid(*[np.linspace(0, 1, n) for n in (5, 7, 9)], indexing="ij")
    values = 2 + y if pbc[0] else 2 + x + 2*y + 3*z
    cell = np.array([[2, 0, 0], [0.4, 3, 0], [0.2, 0.3, 4]])
    dataset = VolumetricData("linear", values, cell, pbc=pbc, endpoint_inclusive=True, precision="float64")
    expected_mean = 2.5 if pbc[0] else 5
    assert dataset.integral == pytest.approx(expected_mean * 24)


def test_float32_field_combination_accumulates_cancellation_in_float64_slabs():
    datasets = [VolumetricData(str(v), np.full((3, 3, 3), v), np.eye(3)) for v in (1e8, 1, 1e8)]
    result = combine_volumetric_datasets(datasets, [1, 1, -1])
    assert result.precision == "float32"
    np.testing.assert_array_equal(result.values, 1)


def test_host_guest_match_rejects_tilt_instead_of_projecting_it_away():
    host = np.diag([2., 2., 10.])
    tilted = host.copy()
    tilted[0, 2] = 0.1
    with pytest.raises(ValueError, match="XY plane"):
        find_lattice_matches(host, [True, True, False], tilted, [True, True, False], max_area_ratio=1)


def test_regular_mixture_assigns_species_without_grid_order_segregation():
    from v_ase.add_atoms import start_atom_addition, sample_insertion_positions
    from v_ase.session import EditorSession
    empty = Atoms(cell=[8, 8, 8], pbc=True)
    session = EditorSession("mixture-audit", empty.copy(), empty.copy())
    sites, _ = sample_insertion_positions(empty.cell, empty.pbc, 64, placement_mode="regular")
    start_atom_addition(session, {
        "entries": [{"element": "Cu", "count": 32}, {"element": "Zr", "count": 32}],
        "placement_mode": "regular", "seed": 19,
    })
    expected = sites[np.random.default_rng(19).permutation(64)]
    np.testing.assert_array_equal(session.working_atoms.positions, expected)
    assert session.working_atoms.get_chemical_symbols() == ["Cu"] * 32 + ["Zr"] * 32
    assert not np.array_equal(expected, sites)


def test_rigid_molecule_excludes_internal_pairs_but_keeps_periodic_copies():
    from v_ase.add_atoms import AdditionRepulsionCalculator
    atoms = Atoms("H2", positions=[[0, 0, 0], [0.6, 0, 0]], cell=[1.5, 5, 5], pbc=True)
    atoms.calc = AdditionRepulsionCalculator(
        cutoff_distance=1.1, backend="numpy", rigid_groups=[[0, 1]],
        rigid_references=[atoms.positions.copy()],
    )
    # Exclude the 0.6 Å internal bond; retain the 0.9 Å intermolecular contact.
    assert atoms.get_potential_energy() == pytest.approx(0.5 * 0.2**2)


def test_commensurate_csv_marks_reference_cells_outside_the_area_limit():
    import csv
    import io
    from v_ase.commensurate import commensurate_csv
    exported = commensurate_csv({"max_area_ratio": 16, "candidates": [
        {"area_ratio": 7, "angle_deg": 21.7867893},
        {"area_ratio": 19, "angle_deg": 13.1735511},
    ]}).decode()
    rows = list(csv.DictReader(line for line in io.StringIO(exported) if not line.startswith("#")))
    assert [row["within_area_limit"] for row in rows] == ["1", "0"]
