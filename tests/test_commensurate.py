import asyncio
import json
import math
from pathlib import Path
import time

import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, FixedPlane
from ase.io import read, write
from fastapi import HTTPException

from v_ase.commensurate import (
    _ORIENTED_BASIS_TRANSFORMS,
    _batch_lattice_match_kinematics,
    _deduplicate_candidates,
    _deduplicate_lattice_matches,
    _deformation_strain_metrics,
    _lattice_match_candidate,
    _optimal_rotation_deformation,
    _plane_frame,
    _supercell_records,
    commensurate_csv,
    commensurate_supercell_geometry,
    find_commensurate_angles,
    find_lattice_matches,
    host_guest_supercell_geometry,
    project_periodic_lattice_in_frame,
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


def commensurate_fixture_directory():
    return Path(__file__).resolve().parents[1] / "examples" / "commensurate_host_guest"


def test_stradi_mean_absolute_strain_uses_the_published_component_definition():
    deformation = np.array([
        [1.01, 0.004],
        [0.004, 0.98],
    ])

    metrics = _deformation_strain_metrics(deformation)

    np.testing.assert_allclose(
        np.asarray(metrics["linear_strain_tensor_2d"]),
        np.array([[0.01, 0.004], [0.004, -0.02]]),
        atol=1e-15,
    )
    assert metrics["mean_absolute_strain"] == pytest.approx(
        (0.01 + 0.02 + 0.004) / 3.0
    )
    assert metrics["max_principal_strain"] == pytest.approx(
        np.max(np.abs(np.linalg.svd(deformation, compute_uv=False) - 1.0))
    )


@pytest.mark.parametrize(
    ("epsilon_xx_percent", "epsilon_yy_percent", "epsilon_xy_percent", "paper_mean_percent"),
    [
        (-0.26, -0.27, 0.0, 0.18),
        (-0.26, -1.79, 0.0, 0.68),
        (-0.27, -2.06, 0.0, 0.78),
        (-0.26, -0.26, 0.0, 0.18),
        (-2.06, -2.06, 0.0, 1.37),
        (-0.27, 5.79, 0.0, 2.02),
    ],
)
def test_stradi_table_3_mean_strain_values_are_reproduced(
    epsilon_xx_percent,
    epsilon_yy_percent,
    epsilon_xy_percent,
    paper_mean_percent,
):
    """Reproduce the published Al/InAs mean-strain column from Table 3.

    The component values printed by the paper are themselves rounded to two
    decimals, so their reconstructed means are compared within one final-table
    rounding unit rather than treated as hidden full-precision source data.
    """

    deformation = np.array([
        [1.0 + epsilon_xx_percent / 100.0, epsilon_xy_percent / 100.0],
        [epsilon_xy_percent / 100.0, 1.0 + epsilon_yy_percent / 100.0],
    ])
    reconstructed_percent = (
        _deformation_strain_metrics(deformation)["mean_absolute_strain"] * 100.0
    )

    assert reconstructed_percent == pytest.approx(paper_mean_percent, abs=0.011)


def test_graphene_cu111_host_guest_fixture_matches_its_independent_reference():
    directory = commensurate_fixture_directory()
    expected = json.loads((directory / "expected.json").read_text())
    host = read(directory / expected["host_file"])
    guest = read(directory / expected["guest_file"])
    settings = expected["settings"]
    reference = expected["expected_smallest_match"]

    graphene_lattice = expected["primitive_lattices_angstrom"]["graphene"]
    cu111_lattice = expected["primitive_lattices_angstrom"]["cu111_from_fcc_3.615"]
    graphene_boundary = math.sqrt(13.0) * graphene_lattice
    cu111_boundary = math.sqrt(12.0) * cu111_lattice
    analytic_stretch = graphene_boundary / cu111_boundary
    graphene_boundary_angle = math.degrees(math.atan2(math.sqrt(3.0) / 2.0, 3.5))
    analytic_angle = 30.0 - graphene_boundary_angle
    assert reference["absolute_angle_deg"] == pytest.approx(analytic_angle, abs=1e-8)
    assert reference["maximum_principal_strain"] == pytest.approx(
        analytic_stretch - 1.0,
        abs=1e-12,
    )
    assert reference["mean_absolute_strain"] == pytest.approx(
        2.0 * (analytic_stretch - 1.0) / 3.0,
        abs=1e-12,
    )
    assert reference["total_atom_count"] == (
        len(host) * reference["host_area_ratio"]
        + len(guest) * reference["guest_area_ratio"]
    )

    result = find_lattice_matches(
        host.cell.array,
        host.pbc,
        guest.cell.array,
        guest.pbc,
        max_area_ratio=settings["maximum_area_ratio"],
        strain_tolerance=settings["maximum_strain_fraction"],
        strain_target=settings["strain_target"],
    )

    candidate = min(
        result["candidates"],
        key=lambda item: (
            max(item["host_area_ratio"], item["guest_area_ratio"]),
            abs(item["angle_deg"]),
        ),
    )
    assert abs(candidate["angle_deg"]) == pytest.approx(reference["absolute_angle_deg"], abs=1e-8)
    assert candidate["host_area_ratio"] == reference["host_area_ratio"]
    assert candidate["guest_area_ratio"] == reference["guest_area_ratio"]
    assert candidate["max_principal_strain"] == pytest.approx(
        reference["maximum_principal_strain"], abs=1e-12
    )
    assert candidate["mean_absolute_strain"] == pytest.approx(
        reference["mean_absolute_strain"], abs=1e-12
    )
    assert candidate["host_notation"].startswith(reference["host_notation_prefix"])
    assert candidate["guest_notation"].startswith(reference["guest_notation_prefix"])
    assert candidate["host_matrix"] == reference["host_matrix"]
    assert candidate["guest_matrix"] == reference["guest_matrix"]


def test_graphene_mos2_visual_fixture_has_the_documented_rectangular_match():
    directory = commensurate_fixture_directory()
    host = read(directory / "graphene_host.extxyz")
    guest = read(directory / "mos2_guest.extxyz")

    result = find_lattice_matches(
        host.cell.array,
        host.pbc,
        guest.cell.array,
        guest.pbc,
        max_area_ratio=16,
        strain_tolerance=0.025,
        strain_target="guest",
    )
    candidate = next(
        item
        for item in result["candidates"]
        if item["angle_deg"] == pytest.approx(-19.10660535, abs=1e-8)
    )

    assert candidate["host_area_ratio"] == 14
    assert candidate["guest_area_ratio"] == 4
    assert candidate["host_matrix"] == [[3, -1], [-1, 5]]
    assert candidate["guest_matrix"] == [[2, 0], [0, 2]]
    assert candidate["host_notation"] == "(√7 × √21) R-19.11°"
    assert candidate["guest_notation"] == "2 × 2"
    assert candidate["cell_lengths_angstrom"] == pytest.approx(
        [math.sqrt(7.0) * 2.46, math.sqrt(21.0) * 2.46],
        abs=1e-8,
    )
    assert candidate["cell_angle_deg"] == pytest.approx(90.0, abs=1e-10)
    assert candidate["max_principal_strain"] == pytest.approx(
        0.023356639185,
        abs=1e-12,
    )


def test_host_guest_search_is_invariant_to_an_equivalent_integer_cell_basis():
    host = np.array([
        [3.1, 0.2, 0.0],
        [0.8, 4.2, 0.0],
        [0.0, 0.0, 17.0],
    ])
    equivalent_basis = np.array([[3, 2], [-2, -1]], dtype=int)
    assert round(np.linalg.det(equivalent_basis)) == 1
    guest = host.copy()
    guest[:2] = equivalent_basis @ host[:2]

    result = find_lattice_matches(
        host,
        [True, True, False],
        guest,
        [True, True, False],
        max_area_ratio=1,
        strain_tolerance=1e-10,
    )

    assert result["suggestion_count"] >= 1
    candidate = min(result["candidates"], key=lambda item: item["strain"])
    assert candidate["host_area_ratio"] == 1
    assert candidate["guest_area_ratio"] == 1
    assert candidate["strain"] == pytest.approx(0.0, abs=1e-12)


def test_vectorized_kinematics_matches_svd_for_general_oblique_boundaries():
    generator = np.random.default_rng(20260803)
    host = generator.normal(size=(64, 2, 2))
    guest = generator.normal(size=(64, 2, 2))
    host += np.eye(2)[None, :, :] * 2.5
    guest += np.eye(2)[None, :, :] * 2.5

    angles, guest_strains, host_strains = _batch_lattice_match_kinematics(host, guest)

    for index in range(len(host)):
        angle, guest_strain, rotation, _ = _optimal_rotation_deformation(
            guest[index],
            host[index],
        )
        host_deformation = np.linalg.solve(host[index], guest[index] @ rotation)
        host_strain = np.max(np.abs(np.linalg.svd(host_deformation, compute_uv=False) - 1.0))
        assert angles[0, index] == pytest.approx(angle, abs=1e-10)
        assert guest_strains[0, index] == pytest.approx(guest_strain, abs=1e-10)
        assert host_strains[0, index] == pytest.approx(host_strain, abs=1e-10)


def test_accelerated_host_guest_search_matches_exhaustive_small_search():
    host = np.array([
        [3.1, 0.25, 0.0],
        [0.65, 4.05, 0.0],
        [0.0, 0.0, 18.0],
    ])
    guest = np.array([
        [3.04, -0.12, 0.0],
        [0.48, 4.09, 0.0],
        [0.0, 0.0, 19.0],
    ])
    pbc = [True, True, False]
    maximum = 5
    tolerance = 0.08

    accelerated = find_lattice_matches(
        host,
        pbc,
        guest,
        pbc,
        max_area_ratio=maximum,
        strain_tolerance=tolerance,
        strain_target="guest",
    )

    frame, normal, host_projected = _plane_frame(host, pbc, "Z")
    guest_projected = project_periodic_lattice_in_frame(guest, pbc, normal, frame)
    exhaustive = []
    for host_record in _supercell_records(host_projected.basis, maximum):
        for guest_record in _supercell_records(guest_projected.basis, maximum):
            orientation_candidates = []
            for transform in _ORIENTED_BASIS_TRANSFORMS:
                orientation_candidates.append(_lattice_match_candidate(
                    host_cell=host,
                    guest_cell=guest,
                    host_projected=host_projected,
                    guest_projected=guest_projected,
                    normal=normal,
                    host_record=host_record,
                    guest_record=guest_record,
                    strain_target="guest",
                    guest_orientation_transform=transform,
                ))
            minimum_strain = min(
                float(candidate["strain"])
                for candidate in orientation_candidates
            )
            canonical = min(
                (
                    candidate
                    for candidate in orientation_candidates
                    if float(candidate["strain"]) <= minimum_strain + 1e-11
                ),
                key=lambda candidate: abs(float(candidate["angle_deg"])),
            )
            if canonical["strain"] <= tolerance + 1e-12:
                exhaustive.append(canonical)
    expected = _deduplicate_lattice_matches(exhaustive)

    def projected(candidates):
        return {
            round(float(candidate["angle_deg"]), 2): (
                int(candidate["host_area_ratio"]),
                int(candidate["guest_area_ratio"]),
                round(float(candidate["strain"]), 10),
            )
            for candidate in candidates
        }

    assert projected(accelerated["candidates"]) == projected(expected)


def test_vectorized_host_guest_search_keeps_large_interactive_bounds_responsive():
    host = graphene_cell()
    guest = graphene_cell() * np.array([[2.504 / 2.46], [2.504 / 2.46], [1.0]])

    started = time.perf_counter()
    result = find_lattice_matches(
        host,
        [True, True, False],
        guest,
        [True, True, False],
        max_area_ratio=64,
        strain_tolerance=0.03,
    )
    elapsed = time.perf_counter() - started

    assert result["evaluated_pair_count"] > 250_000
    assert result["suggestion_count"] > 100
    assert elapsed < 12.0


def test_host_guest_search_rejects_noninteractive_area_bounds_explicitly():
    with pytest.raises(ValueError, match="between 1 and 128"):
        find_lattice_matches(
            graphene_cell(),
            [True, True, False],
            graphene_cell(),
            [True, True, False],
            max_area_ratio=129,
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
    assert "max_principal_strain" in text
    assert "mean_absolute_strain" in text
    assert "total_atom_count" in text


def test_host_guest_preview_keeps_cells_independent_and_can_hide_atoms():
    host_cell = graphene_cell()
    guest_cell = graphene_cell() * np.array([[2.50 / 2.46], [2.50 / 2.46], [1.0]])
    search = find_lattice_matches(
        host_cell,
        [True, True, False],
        guest_cell,
        [True, True, False],
        max_area_ratio=4,
        strain_tolerance=0.02,
    )
    assert search["exact_rotational_symmetry_deg"] is None
    candidate = search["candidates"][0]
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
    assert len(geometry["host_lattice_origins"]) == candidate["host_area_ratio"]
    assert len(geometry["guest_lattice_origins"]) == candidate["guest_area_ratio"]

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

    parent_preview = host_guest_supercell_geometry(
        host_cell=host_cell,
        host_positions=[[0, 0, 0], [1.23, 0.71, 0]],
        guest_cell=guest_cell,
        guest_positions=[[0, 0, 0], [1.25, 0.72, 0]],
        candidate=candidate,
        guest_offset=[0, 0, 3.35],
        display_angle_deg=13.0,
        parent_lattice_preview=True,
        parent_grid_radius=6,
        include_atoms=False,
    )
    assert parent_preview["parent_lattices_fixed"] is True
    assert parent_preview["host_grid_shape"] == [12, 12]
    assert parent_preview["guest_grid_shape"] == [12, 12]
    assert np.asarray(parent_preview["host_parent_cell"]) == pytest.approx(host_cell)
    rotation = row_rotation_matrix([0, 0, 1], 13.0)
    assert np.asarray(parent_preview["guest_parent_cell"]) == pytest.approx(
        guest_cell @ rotation
    )
    assert len(parent_preview["host_grid_lattice_origins"]) == 12 * 12
    assert len(parent_preview["guest_grid_lattice_origins"]) == 12 * 12


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
    assert candidate["host_atom_count"] == 2
    assert candidate["guest_atom_count"] == 2
    assert candidate["total_atom_count"] == 4
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
    assert loaded["guest"]["default_gap"] == pytest.approx(3.0)
    assert loaded["guest"]["suggested_offset"] == pytest.approx([0.0, 0.0, 3.0])
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


def test_host_guest_default_order_keeps_the_smallest_cell_when_area_limit_grows():
    directory = commensurate_fixture_directory()
    host = read(directory / "graphene_host.extxyz")
    guest = read(directory / "cu111_guest.extxyz")

    result = find_lattice_matches(
        host.cell.array,
        host.pbc,
        guest.cell.array,
        guest.pbc,
        max_area_ratio=64,
        strain_tolerance=0.01,
        strain_target="guest",
    )

    suggested = result["candidates"][0]
    assert suggested["host_area_ratio"] == 13
    assert suggested["guest_area_ratio"] == 12
    assert abs(suggested["angle_deg"]) == pytest.approx(16.10211375, abs=1e-8)


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
    assert result["exact_rotational_symmetry_deg"] == pytest.approx(60.0)
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
    assert first["source_notation"].startswith("(√7 × √7)")
    assert first["target_notation"].startswith("(√7 × √7)")
    assert first["supercell_supported"] is True


def test_hexagonal_commensurate_curve_matches_the_analytic_tbg_series():
    """Validate every available m,m+1 point, not only three named angles."""

    result = find_commensurate_angles(
        graphene_cell(),
        [True, True, False],
        "Z",
        max_index=32,
        strain_tolerance=1e-8,
        chemical_symbols=["C", "C", "C", "C"],
    )
    assert any(
        reference.get("doi") == "10.1103/PhysRevB.86.155449"
        for reference in result["references"]
    )

    for m in range(1, 32):
        n = m + 1
        area = m * m + m * n + n * n
        cosine = (m * m + n * n + 4 * m * n) / (2 * area)
        angle = math.degrees(math.acos(np.clip(cosine, -1.0, 1.0)))
        candidate = candidate_near(result, angle, tolerance=1e-5)
        assert candidate["area"] == area
        assert candidate["strain"] == pytest.approx(0.0, abs=1e-10)
        assert candidate["mean_absolute_strain"] == pytest.approx(0.0, abs=1e-10)


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


def test_approximate_hexagonal_family_does_not_claim_exact_rotational_symmetry():
    strained = graphene_cell()
    strained[1, 0] *= 1.0002
    result = find_commensurate_angles(
        strained,
        [True, True, False],
        "Z",
        max_index=4,
        strain_tolerance=0.01,
    )

    assert result["lattice_family"] == "hexagonal"
    assert result["exact_rotational_symmetry_deg"] is None


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


def test_commensurate_geometry_has_exact_core_inside_expanded_parent_lattices():
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
    assert geometry["padding_cells"] >= 2
    assert geometry["requested_padding_cells"] == 1
    assert set(geometry["components"]) == {"reference", "rotating"}
    assert len(geometry["host_lattice_origins"]) == geometry["area_ratio"]
    assert len(geometry["guest_lattice_origins"]) == geometry["area_ratio"]
    assert geometry["grid_padding_cells"] > geometry["padding_cells"]
    assert len(geometry["host_grid_lattice_origins"]) > len(
        geometry["host_lattice_origins"]
    )
    assert len(geometry["guest_grid_lattice_origins"]) > len(
        geometry["guest_lattice_origins"]
    )
    assert all(value >= 3 for value in geometry["host_grid_shape"])
    assert all(value >= 3 for value in geometry["guest_grid_shape"])
    assert geometry["host_notation"] == candidate["target_notation"]
    assert geometry["guest_notation"] == candidate["source_notation"]
    assert np.asarray(geometry["host_primitive_vectors"]).shape == (2, 3)
    assert np.asarray(geometry["guest_primitive_vectors"]).shape == (2, 3)
    assert np.asarray(geometry["cell"]) == pytest.approx(
        np.asarray(candidate["target_matrix_3d"]) @ atoms.cell.array
    )


def test_parent_lattice_preview_extent_is_independent_of_common_cell_candidate():
    atoms = bilayer_atoms()
    result = find_commensurate_angles(
        atoms.cell.array,
        atoms.pbc,
        "Z",
        max_index=6,
        strain_tolerance=1e-6,
        chemical_symbols=atoms.get_chemical_symbols(),
    )
    candidates = (
        candidate_near(result, 21.7867893),
        candidate_near(result, 13.1735511),
    )
    pivot = atoms.positions[:2].mean(axis=0)
    previews = [
        commensurate_supercell_geometry(
            cell=atoms.cell.array,
            positions=atoms.positions,
            selected_indices=[0, 1],
            candidate=candidate,
            pivot=pivot,
            display_angle_deg=candidate["angle_deg"],
            positions_include_display_rotation=False,
            parent_lattice_preview=True,
            parent_grid_radius=8,
            include_atoms=False,
        )
        for candidate in candidates
    ]

    for preview in previews:
        assert preview["parent_lattices_fixed"] is True
        assert preview["host_grid_shape"] == [16, 16]
        assert preview["guest_grid_shape"] == [16, 16]
        assert np.asarray(preview["host_parent_cell"]) == pytest.approx(atoms.cell.array)
        assert len(preview["host_grid_lattice_origins"]) == 16 * 16
        assert len(preview["guest_grid_lattice_origins"]) == 16 * 16

        host_origins = np.asarray(preview["host_grid_lattice_origins"], dtype=float)
        host_vectors = np.asarray(preview["host_primitive_vectors"], dtype=float)
        guest_origins = np.asarray(preview["guest_grid_lattice_origins"], dtype=float)
        guest_vectors = np.asarray(preview["guest_primitive_vectors"], dtype=float)
        np.testing.assert_allclose(
            host_origins.mean(axis=0) + 0.5 * (host_vectors[0] + host_vectors[1]),
            np.zeros(3),
            atol=1e-12,
        )
        np.testing.assert_allclose(
            guest_origins.mean(axis=0) + 0.5 * (guest_vectors[0] + guest_vectors[1]),
            np.asarray(preview["guest_offset"], dtype=float),
            atol=1e-12,
        )

    assert previews[0]["host_grid_lattice_origins"] == previews[1][
        "host_grid_lattice_origins"
    ]
    assert previews[0]["common_cell"] != previews[1]["common_cell"]
    assert previews[0]["guest_grid_lattice_origins"] != previews[1][
        "guest_grid_lattice_origins"
    ]

    rotation = row_rotation_matrix([0, 0, 1], candidates[0]["angle_deg"])
    expected_offset = np.zeros(3)
    assert previews[0]["guest_offset"] == pytest.approx(expected_offset)
    assert previews[0]["guest_grid_lattice_origins"][0] == pytest.approx(
        expected_offset
        + np.asarray([-8, -8, 0], dtype=float)
        @ (atoms.cell.array @ rotation)
    )


def test_direct_angle_preview_matches_already_rotated_transform_positions():
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
    rotated_positions, pivot = rotated_first_layer(atoms, candidate)

    transform_preview = commensurate_supercell_geometry(
        cell=atoms.cell.array,
        positions=rotated_positions,
        selected_indices=[0, 1],
        candidate=candidate,
        pivot=pivot,
        padding_cells=1,
        display_angle_deg=candidate["angle_deg"],
        positions_include_display_rotation=True,
    )
    direct_input_preview = commensurate_supercell_geometry(
        cell=atoms.cell.array,
        positions=atoms.get_positions(),
        selected_indices=[0, 1],
        candidate=candidate,
        pivot=pivot,
        padding_cells=1,
        display_angle_deg=candidate["angle_deg"],
        positions_include_display_rotation=False,
    )

    assert direct_input_preview["atom_indices"] == transform_preview["atom_indices"]
    assert direct_input_preview["lattice_indices"] == transform_preview["lattice_indices"]
    assert direct_input_preview["components"] == transform_preview["components"]
    np.testing.assert_allclose(
        np.asarray(direct_input_preview["positions"]),
        np.asarray(transform_preview["positions"]),
        atol=1e-11,
    )
    np.testing.assert_allclose(
        np.asarray(direct_input_preview["guest_cell"]),
        np.asarray(transform_preview["guest_cell"]),
        atol=1e-12,
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
    assert preview["preview"]["padding_cells"] >= 2
    assert preview["preview"]["requested_padding_cells"] == 1
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
