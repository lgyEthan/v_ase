import asyncio
import math

import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, FixedPlane
from ase.io import write
from fastapi import HTTPException

from v_ase.commensurate import (
    _deduplicate_candidates,
    commensurate_csv,
    commensurate_supercell_geometry,
    find_commensurate_angles,
    find_lattice_matches,
    host_guest_supercell_geometry,
    row_rotation_matrix,
)
from v_ase.server import (
    _normalized_affine_line_direction,
    _normalized_affine_plane_normal,
    apply_commensurate_supercell,
    commensurate_rotation_candidates,
    load_commensurate_guest_path,
    preview_commensurate_supercell,
)
from v_ase.project import read_project_archive, replace_session_from_project, write_project_archive
from v_ase.io import atom_labels, set_atom_labels
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


def test_host_guest_lattice_match_uses_the_smallest_valid_boundary_and_guest_strain():
    host = graphene_cell()
    guest = graphene_cell() * np.array([[2.50 / 2.46], [2.50 / 2.46], [1.0]])
    progress = []

    result = find_lattice_matches(
        host,
        [True, True, False],
        guest,
        [True, True, False],
        max_area_ratio=16,
        strain_tolerance=0.02,
        strain_target="guest",
        progress_callback=lambda value, stage: progress.append((value, stage)),
    )

    candidate = result["candidates"][0]
    assert result["mode"] == "host-guest"
    assert candidate["host_area_ratio"] == 1
    assert candidate["guest_area_ratio"] == 1
    assert candidate["strain"] == pytest.approx(0.016, abs=1e-10)
    assert candidate["strain_target"] == "guest"
    assert progress[0][0] > 0
    assert progress[-1] == (1.0, "Ranking valid commensurate matches")

    rotation = row_rotation_matrix([0, 0, 1], candidate["angle_deg"])
    transformed_guest = (
        np.asarray(candidate["guest_supercell"])
        @ rotation
        @ np.asarray(candidate["guest_deformation_matrix"])
    )
    assert transformed_guest == pytest.approx(np.asarray(candidate["suggested_cell"]), abs=1e-9)


def test_host_guest_lattice_match_can_put_the_residual_strain_on_the_host():
    host = graphene_cell()
    guest = graphene_cell() * np.array([[2.50 / 2.46], [2.50 / 2.46], [1.0]])
    candidate = find_lattice_matches(
        host,
        [True, True, False],
        guest,
        [True, True, False],
        max_area_ratio=4,
        strain_tolerance=0.02,
        strain_target="host",
    )["candidates"][0]

    assert candidate["strain_target"] == "host"
    assert np.asarray(candidate["guest_deformation_matrix"]) == pytest.approx(np.eye(3))
    transformed_host = (
        np.asarray(candidate["host_supercell"])
        @ np.asarray(candidate["host_deformation_matrix"])
    )
    assert transformed_host == pytest.approx(np.asarray(candidate["suggested_cell"]), abs=1e-9)


def test_commensurate_csv_carries_candidate_matrices_and_citations():
    result = find_lattice_matches(
        graphene_cell(),
        [True, True, False],
        graphene_cell(),
        [True, True, False],
        max_area_ratio=2,
        strain_tolerance=1e-8,
    )
    text = commensurate_csv(result).decode("utf-8")

    assert "v_ase.commensurate.v1" in text
    assert "10.1016/j.cpc.2015.08.038" in text
    assert "10.1088/1361-648X/aa66f3" in text
    assert "10.1016/j.cpc.2017.05.007" not in text
    assert "host_matrix" in text


def test_host_guest_preview_keeps_cells_independent_and_can_hide_atoms():
    host_cell = graphene_cell()
    guest_cell = graphene_cell() * np.array([[2.50 / 2.46], [2.50 / 2.46], [1.0]])
    candidate = find_lattice_matches(
        host_cell,
        [True, True, False],
        guest_cell,
        [True, True, False],
        max_area_ratio=4,
        strain_tolerance=0.02,
    )["candidates"][0]
    geometry = host_guest_supercell_geometry(
        host_cell=host_cell,
        host_positions=[[0, 0, 0], [1.23, 0.71, 0]],
        guest_cell=guest_cell,
        guest_positions=[[0, 0, 0], [1.25, 0.72, 0]],
        candidate=candidate,
        guest_offset=[0, 0, 3.35],
        padding_cells=1,
    )

    assert geometry["mode"] == "host-guest"
    assert set(geometry["components"]) == {"host", "guest"}
    assert np.asarray(geometry["host_cell"]) == pytest.approx(np.asarray(geometry["cell"]))
    assert np.asarray(geometry["guest_cell"]) == pytest.approx(np.asarray(geometry["cell"]))
    assert geometry["guest_offset"] == [0.0, 0.0, 3.35]

    cells_only = host_guest_supercell_geometry(
        host_cell=host_cell,
        host_positions=[[0, 0, 0]],
        guest_cell=guest_cell,
        guest_positions=[[0, 0, 0]],
        candidate=candidate,
        include_atoms=False,
    )
    assert cells_only["positions"] == []
    assert cells_only["preview_atom_count"] == 0


def test_host_guest_api_previews_cells_then_materializes_one_editable_structure():
    host = Atoms(
        "C2",
        positions=[[0, 0, 0], [1.23, 0.71, 0]],
        cell=graphene_cell(),
        pbc=[True, True, False],
    )
    guest_cell = graphene_cell() * np.array([[2.50 / 2.46], [2.50 / 2.46], [1.0]])
    guest = Atoms(
        "BN",
        positions=[[0, 0, 0], [1.25, 0.72, 0]],
        cell=guest_cell,
        pbc=[True, True, False],
    )
    session = EditorSession("host-guest-api", host.copy(), host.copy())
    session.commensurate_guest_atoms = guest.copy()
    session.commensurate_guest_name = "hbn.xyz"
    sessions[session.session_id] = session
    search_payload = {
        "mode": "host-guest",
        "axis": "Z",
        "max_area_ratio": 4,
        "strain_tolerance": 0.02,
        "strain_target": "guest",
    }
    result = asyncio.run(commensurate_rotation_candidates(session.session_id, search_payload))
    candidate = result["candidates"][0]
    payload = {
        **search_payload,
        "candidate": candidate,
        "show_atoms": False,
        "guest_offset": [0, 0, 3.35],
        "frame_index": 0,
    }
    preview = asyncio.run(preview_commensurate_supercell(session.session_id, payload))
    assert preview["search"]["mode"] == "host-guest"
    assert preview["preview"]["include_atoms"] is False
    assert np.asarray(preview["preview"]["host_cell"]) == pytest.approx(
        np.asarray(preview["preview"]["guest_cell"])
    )

    payload["show_atoms"] = True
    response = asyncio.run(apply_commensurate_supercell(session.session_id, payload))
    assert response["metadata"]["natoms"] == 4
    assert session.commensurate_guest_atoms is None
    assert session.working_atoms.get_chemical_symbols() == ["C", "C", "B", "N"]


def test_agent_guest_path_is_confined_to_the_launch_directory(tmp_path):
    host = Atoms("C", positions=[[0, 0, 0]], cell=graphene_cell(), pbc=[1, 1, 0])
    guest = Atoms(
        "BN",
        positions=[[0, 0, 0], [1.25, 0.72, 0]],
        cell=graphene_cell() * np.array([[2.50 / 2.46], [2.50 / 2.46], [1.0]]),
        pbc=[1, 1, 0],
    )
    write(tmp_path / "guest.extxyz", guest)
    session = EditorSession(
        "guest-agent-path",
        host.copy(),
        host.copy(),
        config={"launch_directory": str(tmp_path)},
    )
    sessions[session.session_id] = session

    loaded = asyncio.run(load_commensurate_guest_path(session.session_id, {
        "path": "guest.extxyz",
    }))
    assert loaded["guest"]["name"] == "guest.extxyz"
    assert session.commensurate_guest_atoms.get_chemical_symbols() == ["B", "N"]

    with pytest.raises(HTTPException, match="outside the terminal launch directory"):
        asyncio.run(load_commensurate_guest_path(session.session_id, {
            "path": "../guest.extxyz",
        }))


def test_commensurate_affine_transform_distinguishes_lines_from_plane_normals():
    affine = np.array([
        [1.8, 0.35, 0.0],
        [0.0, 0.9, 0.0],
        [0.0, 0.0, 1.0],
    ])
    line = np.asarray(_normalized_affine_line_direction([1, 1, 0], affine))
    plane = np.asarray(_normalized_affine_plane_normal([1, 1, 0], affine))
    expected_line = np.asarray([1, 1, 0]) @ affine
    expected_line /= np.linalg.norm(expected_line)
    assert line == pytest.approx(expected_line)

    original_tangent = np.asarray([1.0, -1.0, 0.0])
    transformed_tangent = original_tangent @ affine
    assert np.dot(transformed_tangent, plane) == pytest.approx(0.0, abs=1e-12)
    assert abs(np.dot(transformed_tangent, line)) > 1e-3


def test_vase_project_roundtrips_the_pending_guest_workspace(tmp_path):
    host = Atoms("C", positions=[[0, 0, 0]], cell=graphene_cell(), pbc=[1, 1, 0])
    guest = Atoms("BN", positions=[[0, 0, 0], [1.2, 0.7, 0]], cell=graphene_cell(), pbc=[1, 1, 0])
    set_atom_labels(guest, ["B_top", "N_top"])
    session = EditorSession("guest-project", host.copy(), host.copy())
    session.commensurate_guest_atoms = guest.copy()
    session.commensurate_guest_name = "guest-layer.xyz"
    destination = tmp_path / "guest.vase"

    write_project_archive(destination, session, {"display": {"commensurateGuide": True}})
    project = read_project_archive(destination)
    assert project.commensurate_guest_name == "guest-layer.xyz"
    assert atom_labels(project.commensurate_guest_atoms) == ["B_top", "N_top"]

    restored = EditorSession("guest-restored", host.copy(), host.copy())
    replace_session_from_project(restored, project)
    assert restored.commensurate_guest_name == "guest-layer.xyz"
    assert atom_labels(restored.commensurate_guest_atoms) == ["B_top", "N_top"]


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
