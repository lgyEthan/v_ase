import numpy as np
import pytest
import asyncio
from ase import Atoms

from v_ase.registry import calculate_registry_map, registry_map_csv
from v_ase.server import registry_analysis, registry_analysis_csv
from v_ase.session import EditorSession, sessions


def interface_atoms():
    return Atoms(
        "C2N",
        positions=[
            [0.0, 0.0, 0.0],
            [1.5, 1.5, 0.0],
            [0.1, 0.1, 2.0],
        ],
        cell=np.diag([3.0, 3.0, 12.0]),
        pbc=[True, True, False],
    )


def test_registry_map_scans_one_periodic_cell_and_reports_the_optimum():
    progress = []
    result = calculate_registry_map(
        interface_atoms(),
        [2],
        grid_x=12,
        grid_y=10,
        progress_callback=lambda value, stage: progress.append((value, stage)),
    )

    assert result.values.shape == (10, 12)
    assert result.periodic_axes == (0, 1)
    assert result.translation_basis == pytest.approx(
        np.asarray([[3.0, 0.0, 0.0], [0.0, 3.0, 0.0]])
    )
    assert 0 <= result.optimum_fractional[0] < 1
    assert 0 <= result.optimum_fractional[1] < 1
    assert result.optimum_value == pytest.approx(np.min(result.values))
    assert progress[0][0] == 0
    assert progress[-1][0] == 1


def test_registry_bond_strain_requires_and_uses_enabled_interfacial_pairs():
    atoms = interface_atoms()
    atoms.positions[2] = [0.0, 0.0, 1.45]
    result = calculate_registry_map(
        atoms,
        [2],
        grid_x=8,
        grid_y=8,
        metric="bond-strain",
        pair_cutoffs={"C|N": {"enabled": True, "max": 1.7}},
    )
    assert result.baseline_pair_count >= 1
    assert result.metric_label == "Interfacial bond-strain RMS"

    with pytest.raises(ValueError, match="enabled pairwise bond cutoff"):
        calculate_registry_map(atoms, [2], metric="bond-strain")


def test_registry_map_rejects_an_empty_selection_and_exports_csv():
    atoms = interface_atoms()
    with pytest.raises(ValueError, match="Select the guest"):
        calculate_registry_map(atoms, [])

    result = calculate_registry_map(atoms, [2], grid_x=4, grid_y=4)
    text = registry_map_csv(result).decode("utf-8")
    assert "v_ase.registry-map.v1" in text
    assert "x_fractional,y_fractional,dx_angstrom,dy_angstrom,dz_angstrom,value" in text
    assert "translation_basis_a_angstrom" in text
    assert "Geometry-only score" in text


def test_registry_api_returns_the_plotted_grid_and_the_same_csv_columns():
    atoms = interface_atoms()
    session = EditorSession("registry-api", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session
    payload = {
        "selected_indices": [2],
        "grid_x": 6,
        "grid_y": 5,
        "metric": "short-contact",
        "frame_index": 0,
    }
    result = asyncio.run(registry_analysis(session.session_id, payload))
    response = asyncio.run(registry_analysis_csv(session.session_id, payload))

    assert result["schema"] == "v_ase.registry-map.v1"
    assert np.asarray(result["values"]).shape == (5, 6)
    assert (
        b"x_fractional,y_fractional,dx_angstrom,dy_angstrom,dz_angstrom,value"
        in response.body
    )
