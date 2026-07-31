from __future__ import annotations

import asyncio

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


def test_rdf_clamps_cutoff_before_triclinic_mic_shells_become_ambiguous():
    atoms = _random_periodic_atoms(count=400)
    safe = safe_rdf_cutoff(atoms)
    result = calculate_rdf(atoms, cutoff=safe * 2.0, bins=32, pair_mode="none")
    assert result.cutoff < safe
    assert result.requested_cutoff == pytest.approx(safe * 2.0)
    assert result.warnings


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
    assert list(result["partial"]) == ["Cu_surface|O_ads"]
    assert response.media_type == "text/csv"
    header = response.body.decode("utf-8").splitlines()[0]
    assert header == "r_angstrom,total_g_r,Cu_surface|O_ads"
