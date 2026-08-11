from __future__ import annotations

import asyncio
from itertools import product

import numpy as np
import pytest
from ase import Atoms

from v_ase.analysis import calculate_rdf, rdf_csv, safe_rdf_cutoff
from v_ase.io import set_atom_labels
from v_ase.server import radial_distribution_analysis, radial_distribution_csv
from v_ase.session import EditorSession, sessions


def _random_periodic_atoms(seed=7, count=1800):
    rng = np.random.default_rng(seed)
    cell = np.array(
        [[22.0, 0.0, 0.0], [3.0, 21.0, 0.0], [1.0, 2.0, 20.0]]
    )
    positions = rng.random((count, 3)) @ cell
    symbols = ["Cu" if index % 2 == 0 else "O" for index in range(count)]
    atoms = Atoms(symbols, positions=positions, cell=cell, pbc=True)
    set_atom_labels(
        atoms,
        ["Cu_surface" if index % 2 == 0 else "O_ads" for index in range(count)],
    )
    return atoms


def test_rdf_is_flat_for_uniform_periodic_structure_across_multiple_cutoffs():
    atoms = _random_periodic_atoms()
    safe = safe_rdf_cutoff(atoms)
    for fraction in (0.35, 0.6, 0.9):
        result = calculate_rdf(atoms, cutoff=safe * fraction, bins=48, pair_mode="none")
        middle = result.total[8:-4]
        assert np.mean(middle) == pytest.approx(1.0, abs=0.10)
        assert np.std(middle) < 0.18


def test_rdf_keeps_requested_cutoff_beyond_unique_mic_radius():
    atoms = _random_periodic_atoms(count=400)
    safe = safe_rdf_cutoff(atoms)
    requested = safe * 1.35
    result = calculate_rdf(atoms, cutoff=requested, bins=32, pair_mode="none")
    assert result.cutoff == pytest.approx(requested)
    assert result.requested_cutoff == pytest.approx(requested)
    assert result.warnings == ()
    assert max(result.periodic_image_extent) >= 1


def test_rdf_automatically_counts_images_beyond_a_two_by_two_by_two_cell():
    primitive = Atoms(
        "H",
        positions=[[0.0, 0.0, 0.0]],
        cell=np.eye(3) * 2.0,
        pbc=True,
    )
    cutoff = 5.01
    primitive_result = calculate_rdf(
        primitive,
        cutoff=cutoff,
        bins=101,
        pair_mode="none",
    )

    # The requested sphere reaches shifts +/-2 in every direction. A fixed
    # 2x2x2 construction cannot contain those images, whereas ASE's periodic
    # neighbor search enumerates them directly.
    assert primitive_result.periodic_image_extent == (2, 2, 2)
    assert primitive_result.periodic_image_span == (5, 5, 5)
    assert primitive_result.cutoff == pytest.approx(cutoff)
    assert primitive_result.payload()["unique_mic_cutoff"] == pytest.approx(1.0)

    repeated = primitive.repeat((2, 2, 2))
    repeated_result = calculate_rdf(
        repeated,
        cutoff=cutoff,
        bins=101,
        pair_mode="none",
    )
    np.testing.assert_allclose(
        repeated_result.total,
        primitive_result.total,
        rtol=0,
        atol=1e-12,
    )


def test_rdf_includes_nonzero_shift_copies_of_a_single_basis_atom():
    atoms = Atoms(
        "He",
        positions=[[0.0, 0.0, 0.0]],
        cell=np.eye(3) * 2.0,
        pbc=True,
    )
    result = calculate_rdf(atoms, cutoff=2.05, bins=82, pair_mode="all")
    shell_index = int(np.searchsorted(
        np.linspace(0.0, result.cutoff, result.bins + 1),
        2.0,
        side="right",
    ) - 1)
    edges = np.linspace(0.0, result.cutoff, result.bins + 1)
    shell_volume = (4.0 * np.pi / 3.0) * (
        edges[shell_index + 1] ** 3 - edges[shell_index] ** 3
    )
    expected = 6.0 / ((1.0 / atoms.get_volume()) * shell_volume)

    assert result.total[shell_index] == pytest.approx(expected)
    assert result.partial["He|He"][shell_index] == pytest.approx(expected)


def test_long_cutoff_triclinic_rdf_matches_independent_periodic_enumeration():
    cell = np.array([
        [2.0, 0.0, 0.0],
        [0.7, 2.3, 0.0],
        [0.4, 0.3, 1.9],
    ])
    positions = np.array([
        [0.1, 0.2, 0.3],
        [1.4, 1.0, 1.2],
        [0.7, 1.8, 0.5],
    ])
    atoms = Atoms("HHeLi", positions=positions, cell=cell, pbc=True)
    cutoff = 5.5
    bins = 110

    result = calculate_rdf(atoms, cutoff=cutoff, bins=bins, pair_mode="none")

    brute_distances = []
    brute_shifts = []
    for atom_i in range(len(atoms)):
        for atom_j in range(len(atoms)):
            for shift in product(range(-5, 6), repeat=3):
                if atom_i == atom_j and shift == (0, 0, 0):
                    continue
                displacement = (
                    positions[atom_j]
                    - positions[atom_i]
                    + np.asarray(shift, dtype=float) @ cell
                )
                distance = float(np.linalg.norm(displacement))
                if distance < cutoff:
                    brute_distances.append(distance)
                    brute_shifts.append(shift)

    edges = np.linspace(0.0, cutoff, bins + 1)
    shell_volume = (4.0 * np.pi / 3.0) * (
        edges[1:] ** 3 - edges[:-1] ** 3
    )
    histogram = np.histogram(brute_distances, bins=edges)[0]
    normalization = (
        len(atoms) ** 2
        / atoms.get_volume()
        * shell_volume
    )
    expected = histogram / normalization
    expected_extent = tuple(
        int(value)
        for value in np.max(np.abs(np.asarray(brute_shifts)), axis=0)
    )

    np.testing.assert_allclose(result.total, expected, rtol=0, atol=1e-12)
    assert result.periodic_image_extent == expected_extent == (3, 3, 3)
    assert result.periodic_image_span == (7, 7, 7)


def test_pairwise_rdf_uses_labels_and_active_pair_selection():
    atoms = _random_periodic_atoms(count=500)
    result = calculate_rdf(
        atoms,
        cutoff=5.0,
        bins=40,
        pair_mode="active",
        active_pairs=["Cu_surface|O_ads"],
    )
    assert list(result.partial) == ["Cu_surface|O_ads"]
    assert len(result.partial["Cu_surface|O_ads"]) == 40
    csv_text = rdf_csv(result).decode("utf-8")
    assert csv_text.splitlines()[0] == "r_angstrom,total_g_r,Cu_surface|O_ads"


def test_pairwise_rdf_preserves_distinct_labels_with_long_common_prefix():
    atoms = _random_periodic_atoms(count=160)
    prefix = "surface_site_" + ("x" * 70)
    first_label = f"{prefix}_alpha"
    second_label = f"{prefix}_beta"
    labels = [
        first_label if index % 2 == 0 else second_label
        for index in range(len(atoms))
    ]
    set_atom_labels(atoms, labels)

    result = calculate_rdf(
        atoms,
        cutoff=4.0,
        bins=24,
        pair_mode="active",
        active_pairs=[[first_label, second_label]],
    )

    assert list(result.partial) == [f"{first_label}|{second_label}"]


def test_all_partial_rdfs_reconstruct_total_with_concentration_weights():
    atoms = _random_periodic_atoms(count=500)
    result = calculate_rdf(
        atoms,
        cutoff=5.0,
        bins=40,
        pair_mode="all",
    )
    reconstructed = (
        0.25 * result.partial["Cu_surface|Cu_surface"]
        + 0.50 * result.partial["Cu_surface|O_ads"]
        + 0.25 * result.partial["O_ads|O_ads"]
    )
    np.testing.assert_allclose(reconstructed, result.total, atol=1e-12)


def test_all_pairwise_rdf_keeps_mixed_pair_when_label_order_is_not_sorted():
    atoms = Atoms(
        "ZrCuCuZr",
        positions=[
            [0.0, 0.0, 0.0],
            [2.2, 0.0, 0.0],
            [0.0, 2.2, 0.0],
            [2.2, 2.2, 0.0],
        ],
        cell=[8.0, 8.0, 8.0],
        pbc=True,
    )
    set_atom_labels(
        atoms,
        ["Zr_glass", "Cu_glass", "Cu_glass", "Zr_glass"],
    )

    result = calculate_rdf(atoms, cutoff=3.8, bins=38, pair_mode="all")

    assert set(result.partial) == {
        "Cu_glass|Cu_glass",
        "Cu_glass|Zr_glass",
        "Zr_glass|Zr_glass",
    }


def test_rdf_refuses_partial_pbc_instead_of_reporting_boundary_biased_curve():
    atoms = Atoms(
        "H4",
        positions=np.eye(4, 3),
        cell=[10, 10, 20],
        pbc=[True, True, False],
    )
    with pytest.raises(ValueError, match="periodic boundaries in x, y, and z"):
        calculate_rdf(atoms, cutoff=3.0)


def test_rdf_http_contract_returns_plot_payload_and_matching_csv():
    atoms = _random_periodic_atoms(count=240)
    session = EditorSession("rdf-api", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session
    payload = {
        "cutoff": 4.5,
        "bins": 36,
        "pair_mode": "active",
        "active_pairs": [["Cu_surface", "O_ads"]],
    }
    try:
        result = asyncio.run(radial_distribution_analysis(session.session_id, payload))
        response = asyncio.run(radial_distribution_csv(session.session_id, payload))
    finally:
        sessions.pop(session.session_id, None)

    assert result["schema"] == "v_ase.rdf.v1"
    assert len(result["radius"]) == 36
    assert result["unique_mic_cutoff"] == pytest.approx(result["safe_cutoff"])
    assert result["periodic_image_span"] == [3, 3, 3]
    assert list(result["partial"]) == ["Cu_surface|O_ads"]
    assert response.media_type == "text/csv"
    header = response.body.decode("utf-8").splitlines()[0]
    assert header == "r_angstrom,total_g_r,Cu_surface|O_ads"
