import asyncio
import math

import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine

from v_ase.commensurate import (
    _deduplicate_candidates,
    commensurate_supercell_geometry,
    find_commensurate_angles,
    row_rotation_matrix,
)
from v_ase.server import (
    apply_commensurate_supercell,
    commensurate_rotation_candidates,
    preview_commensurate_supercell,
)
from v_ase.session import EditorSession, sessions


def graphene_cell():
    lattice = 2.46
    return np.array([
        [lattice, 0.0, 0.0],
        [0.5 * lattice, 0.5 * math.sqrt(3.0) * lattice, 0.0],
        [0.0, 0.0, 20.0],
    ])


def candidate_near(result, angle, tolerance=1e-5):
    return next(
        candidate
        for candidate in result["candidates"]
        if abs(candidate["angle_deg"] - angle) <= tolerance
    )


def test_commensurate_candidate_prefers_the_smallest_cell_within_the_strain_cutoff():
    candidates = [
        {"angle_deg": 12.001, "strain": 0.0, "area": 7},
        {"angle_deg": 12.002, "strain": 0.009, "area": 5},
    ]

    retained = _deduplicate_candidates(candidates, strain_tolerance=0.01)

    assert len(retained) == 1
    assert retained[0]["area"] == 5
    assert retained[0]["strain"] == pytest.approx(0.009)


def test_hexagonal_commensurate_series_reaches_the_tbg_reference_angle():
    result = find_commensurate_angles(
        graphene_cell(),
        [True, True, False],
        "Z",
        max_index=32,
        strain_tolerance=1e-6,
        chemical_symbols=["C", "C", "C", "C"],
    )

    assert result["lattice_family"] == "hexagonal"
    assert result["periodic_axes"] == [0, 1]
    assert result["axis_alignment"] == pytest.approx(1.0)

    first = candidate_near(result, 21.7867893)
    second = candidate_near(result, 13.1735511)
    magic = candidate_near(result, 1.05012088)
    assert (first["area"], second["area"], magic["area"]) == (7, 19, 2977)
    assert first["strain"] == pytest.approx(0.0, abs=1e-10)
    assert second["strain"] == pytest.approx(0.0, abs=1e-10)
    assert magic["strain"] == pytest.approx(0.0, abs=1e-10)
    assert magic["magic_reference"] is True
    assert np.linalg.det(np.asarray(first["source_matrix_3d"])) == pytest.approx(7.0)
    assert np.linalg.det(np.asarray(first["target_matrix_3d"])) == pytest.approx(7.0)
    assert first["source_notation"].startswith("(sqrt(7) x sqrt(7))")
    assert first["target_notation"].startswith("(sqrt(7) x sqrt(7))")
    assert first["supercell_supported"] is True


def test_magic_reference_is_not_claimed_for_non_carbon_hexagonal_cells():
    result = find_commensurate_angles(
        graphene_cell(),
        [True, True, False],
        "Z",
        max_index=32,
        strain_tolerance=1e-6,
        chemical_symbols=["B", "N"],
    )

    assert candidate_near(result, 1.05012088)["magic_reference"] is False


def test_hexagonal_boron_nitride_uses_the_same_exact_commensurate_geometry():
    result = find_commensurate_angles(
        graphene_cell(),
        [True, True, False],
        "Z",
        max_index=32,
        strain_tolerance=1e-8,
        chemical_symbols=["B", "N"],
    )

    assert result["lattice_family"] == "hexagonal"
    assert candidate_near(result, 21.7867893)["area"] == 7
    assert candidate_near(result, 13.1735511)["area"] == 19
    assert candidate_near(result, 1.05012088)["area"] == 2977
    assert all(
        candidate_near(result, angle)["strain"] == pytest.approx(0.0, abs=1e-10)
        for angle in (21.7867893, 13.1735511, 1.05012088)
    )


def test_commensurate_search_requires_two_projected_periodic_boundaries():
    with pytest.raises(ValueError, match="two independent periodic cell vectors"):
        find_commensurate_angles(
            np.diag([4.0, 5.0, 6.0]),
            [True, False, False],
            "Z",
        )


def test_commensurate_api_uses_current_session_cell():
    atoms = Atoms(
        "C4",
        scaled_positions=[
            [0.0, 0.0, 0.25],
            [1 / 3, 2 / 3, 0.25],
            [0.0, 0.0, 0.75],
            [2 / 3, 1 / 3, 0.75],
        ],
        cell=graphene_cell(),
        pbc=[True, True, False],
    )
    session = EditorSession("commensurate-api", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session

    result = asyncio.run(commensurate_rotation_candidates(session.session_id, {
        "axis": "Z",
        "max_index": 32,
        "strain_tolerance": 0.001,
    }))

    assert result["axis"] == "Z"
    assert candidate_near(result, 1.05012088)["magic_reference"] is True


def bilayer_atoms():
    atoms = Atoms(
        "C4",
        positions=[
            [0.0, 0.0, 3.0],
            [1.23, 0.71014083, 3.0],
            [0.0, 0.0, 7.0],
            [1.23, 0.71014083, 7.0],
        ],
        cell=graphene_cell(),
        pbc=[True, True, False],
    )
    atoms.set_constraint([
        FixedLine([0, 1], [0, 0, 1]),
        FixAtoms(indices=[2, 3]),
    ])
    return atoms


def rotated_first_layer(atoms, candidate):
    positions = atoms.get_positions()
    pivot = positions[:2].mean(axis=0)
    rotation = row_rotation_matrix([0, 0, 1], candidate["angle_deg"])
    positions[:2] = pivot + (positions[:2] - pivot) @ rotation
    return positions, pivot


def test_commensurate_geometry_has_exact_core_and_one_primitive_cell_halo():
    atoms = bilayer_atoms()
    result = find_commensurate_angles(
        atoms.cell.array,
        atoms.pbc,
        "Z",
        max_index=4,
        strain_tolerance=1e-6,
        chemical_symbols=atoms.get_chemical_symbols(),
    )
    candidate = candidate_near(result, 21.7867893)
    positions, pivot = rotated_first_layer(atoms, candidate)
    geometry = commensurate_supercell_geometry(
        cell=atoms.cell.array,
        positions=positions,
        selected_indices=[0, 1],
        candidate=candidate,
        pivot=pivot,
        padding_cells=1,
    )

    assert geometry["area_ratio"] == 7
    assert geometry["core_atom_count"] == 28
    assert sum(geometry["core_mask"]) == 28
    assert geometry["preview_atom_count"] > geometry["core_atom_count"]
    assert set(geometry["components"]) == {"reference", "rotating"}
    assert np.asarray(geometry["cell"]) == pytest.approx(
        np.asarray(candidate["target_matrix_3d"]) @ atoms.cell.array
    )


def test_commensurate_preview_and_apply_use_bounded_area_and_preserve_constraints():
    atoms = bilayer_atoms()
    result = find_commensurate_angles(
        atoms.cell.array,
        atoms.pbc,
        "Z",
        max_index=4,
        strain_tolerance=1e-6,
        chemical_symbols=atoms.get_chemical_symbols(),
    )
    candidate = candidate_near(result, 21.7867893)
    positions, pivot = rotated_first_layer(atoms, candidate)
    session = EditorSession("commensurate-supercell", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session
    payload = {
        "positions": positions.tolist(),
        "selected_indices": [0, 1],
        "pivot": pivot.tolist(),
        "axis": "Z",
        "candidate": {
            "angle_deg": candidate["angle_deg"],
            "source_matrix": candidate["source_matrix"],
            "target_matrix": candidate["target_matrix"],
        },
        "max_index": 4,
        "strain_tolerance": 1e-6,
        "max_area_ratio": 16,
        "frame_index": 0,
    }

    preview = asyncio.run(preview_commensurate_supercell(session.session_id, payload))
    assert preview["candidate"]["area_ratio"] == 7
    assert preview["preview"]["padding_cells"] == 1
    assert preview["preview"]["core_atom_count"] == 28
    assert preview["materialization_supported"] is True

    response = asyncio.run(apply_commensurate_supercell(session.session_id, payload))
    assert len(session.working_atoms) == 28
    assert response["metadata"]["natoms"] == 28
    assert session.working_atoms.cell.array == pytest.approx(
        np.asarray(candidate["target_matrix_3d"]) @ atoms.cell.array
    )
    assert any(isinstance(constraint, FixedLine) for constraint in session.working_atoms.constraints)
    assert any(isinstance(constraint, FixAtoms) for constraint in session.working_atoms.constraints)


def test_commensurate_preview_rejects_a_cell_above_the_user_area_limit():
    atoms = bilayer_atoms()
    result = find_commensurate_angles(
        atoms.cell.array,
        atoms.pbc,
        "Z",
        max_index=4,
        strain_tolerance=1e-6,
    )
    candidate = candidate_near(result, 21.7867893)
    positions, pivot = rotated_first_layer(atoms, candidate)
    session = EditorSession("commensurate-area-limit", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session
    with pytest.raises(Exception, match="above the configured maximum"):
        asyncio.run(preview_commensurate_supercell(session.session_id, {
            "positions": positions.tolist(),
            "selected_indices": [0, 1],
            "pivot": pivot.tolist(),
            "axis": "Z",
            "candidate": {
                "angle_deg": candidate["angle_deg"],
                "source_matrix": candidate["source_matrix"],
                "target_matrix": candidate["target_matrix"],
            },
            "max_index": 4,
            "strain_tolerance": 1e-6,
            "max_area_ratio": 6,
            "frame_index": 0,
        }))
