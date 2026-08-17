"""Scientific and state-integrity tests for atom and molecule insertion."""

from __future__ import annotations

import asyncio
import itertools
import threading
import time

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule
from ase.calculators.lj import LennardJones
from ase.constraints import FixAtoms, FixedLine
from ase.geometry import find_mic
from fastapi import HTTPException
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from scipy.spatial import ConvexHull

import v_ase.repulsion as repulsion_module
from v_ase.add_atoms import (
    AdditionRepulsionCalculator,
    MOLECULE_GROUP_ARRAY,
    RigidMoleculeConstraint,
    apply_atom_addition_positions,
    atom_addition_domain_preview,
    cancel_atom_addition,
    cell_cartesian_bounds,
    finish_atom_addition,
    expand_molecules,
    molecule_catalog,
    project_positions_to_region,
    resolve_molecule_density,
    sample_cartesian_box_positions,
    sample_homogeneous_positions,
    sample_insertion_positions,
    sample_regular_positions,
    sample_unit_cell_positions,
    sample_unit_cell_positions_outside_box,
    start_atom_addition,
    start_atom_addition_relaxation,
    uniform_rotation_matrices,
    update_atom_addition_region,
)
from v_ase.insertion_regions import (
    box_cell_intersection_volume,
    build_insertion_domain,
    normalize_insertion_regions,
)
from v_ase.io import atom_labels, set_atom_labels
from v_ase.repulsion import cpu_thread_options
from v_ase.session import EditorSession
from v_ase.session import sessions
from v_ase.server import (
    apply_positions,
    atom_addition_molecule_catalog,
    atom_addition_pair_cutoffs,
    cancel_random_atom_addition,
    finish_random_atom_addition,
    start_random_atom_addition,
)
from v_ase.viewer import find_free_port, view


TRICLINIC_CELL = np.asarray([
    [7.4, 0.0, 0.0],
    [2.1, 6.3, 0.0],
    [-0.8, 1.4, 5.7],
])


def make_host() -> Atoms:
    atoms = Atoms(
        "CuON",
        positions=[
            [1.2, 1.4, 1.8],
            [4.8, 2.1, 2.7],
            [3.1, 4.2, 4.5],
        ],
        cell=TRICLINIC_CELL,
        pbc=True,
    )
    set_atom_labels(atoms, ["Cu_surface", "O_bridge", "N_anchor"])
    atoms.set_tags([8, 4, 2])
    atoms.set_initial_charges([0.2, -0.4, 0.1])
    atoms.new_array("mlip_uncertainty", np.asarray([0.03, 0.08, 0.05]))
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(2, [0.0, 0.0, 1.0]),
    ])
    return atoms


def test_multi_region_volume_is_exact_for_allow_union_minus_reject_union():
    regions = normalize_insertion_regions([
        {"id": "left", "role": "allow", "bounds": [0, 6, 0, 6, 0, 6]},
        {"id": "right", "role": "allow", "bounds": [4, 10, 4, 10, 4, 10]},
        {"id": "void", "role": "reject", "bounds": [5, 7, 5, 7, 5, 7]},
    ])
    domain = build_insertion_domain(
        cell=np.diag([10.0, 10.0, 10.0]),
        pbc=[False, False, False],
        regions=regions,
        pbc_aware=False,
    )
    # 216 + 216 - 8 overlap - 8 rejected = 416 A^3.
    assert domain.volume == pytest.approx(416.0, abs=1e-10)
    probes = np.asarray([[1, 1, 1], [5.5, 5.5, 5.5], [8, 8, 8], [2, 8, 2]])
    np.testing.assert_array_equal(domain.contains(probes), [True, False, True, False])


def _reference_box_cell_intersection_volume(bounds, cell):
    """Independent 12-half-space reference used only by regression tests."""
    lower = np.asarray(bounds[::2], dtype=float)
    upper = np.asarray(bounds[1::2], dtype=float)
    inverse = np.linalg.inv(cell)
    normals: list[np.ndarray] = []
    limits: list[float] = []
    for axis in range(3):
        direction = np.zeros(3, dtype=float)
        direction[axis] = 1.0
        normals.extend((direction, -direction))
        limits.extend((upper[axis], -lower[axis]))
        reciprocal = inverse[:, axis]
        normals.extend((reciprocal, -reciprocal))
        limits.extend((1.0, 0.0))
    normal_array = np.asarray(normals)
    limit_array = np.asarray(limits)
    vertices = []
    for indices in itertools.combinations(range(12), 3):
        matrix = normal_array[list(indices)]
        if abs(float(np.linalg.det(matrix))) < 1e-12:
            continue
        point = np.linalg.solve(matrix, limit_array[list(indices)])
        if np.all(normal_array @ point <= limit_array + 1e-9):
            vertices.append(point)
    if len(vertices) < 4:
        return 0.0
    unique = np.unique(np.round(vertices, decimals=12), axis=0)
    return float(ConvexHull(unique).volume) if len(unique) >= 4 else 0.0


def test_fast_box_cell_intersection_matches_independent_triclinic_reference():
    generator = np.random.default_rng(90210)
    for _ in range(128):
        cell = np.asarray([
            [generator.uniform(2.0, 9.0), 0.0, 0.0],
            [generator.uniform(-4.0, 4.0), generator.uniform(2.0, 9.0), 0.0],
            [
                generator.uniform(-4.0, 4.0),
                generator.uniform(-4.0, 4.0),
                generator.uniform(2.0, 9.0),
            ],
        ])
        corners = np.asarray(list(itertools.product((0.0, 1.0), repeat=3))) @ cell
        cell_lower = corners.min(axis=0)
        span = corners.max(axis=0) - cell_lower
        first = cell_lower + generator.uniform(-0.5, 1.2, 3) * span
        second = cell_lower + generator.uniform(-0.2, 1.5, 3) * span
        lower = np.minimum(first, second)
        upper = np.maximum(first, second)
        upper = np.maximum(upper, lower + 1e-3)
        bounds = tuple(np.column_stack((lower, upper)).reshape(-1))
        expected = _reference_box_cell_intersection_volume(bounds, cell)
        actual = box_cell_intersection_volume(bounds, cell)
        assert actual == pytest.approx(expected, rel=2e-9, abs=2e-9)


def test_nonperiodic_structure_requires_allow_region_and_uses_exact_box_volume():
    empty_cell = np.zeros((3, 3))
    with pytest.raises(ValueError, match="requires at least one Allow region"):
        build_insertion_domain(
            cell=empty_cell,
            pbc=[False, False, False],
            regions=normalize_insertion_regions([
                {"id": "reject", "role": "reject", "bounds": [1, 2, 1, 2, 1, 2]},
            ]),
        )
    domain = build_insertion_domain(
        cell=empty_cell,
        pbc=[False, False, False],
        regions=normalize_insertion_regions([
            {"id": "allow", "role": "allow", "bounds": [0, 4, 0, 4, 0, 4]},
            {"id": "reject", "role": "reject", "bounds": [1, 2, 1, 2, 1, 2]},
        ]),
    )
    assert domain.volume == pytest.approx(63.0, abs=1e-12)
    points, info = domain.random_points(4000, seed=91)
    assert np.all(domain.contains(points))
    assert info["accepted"] == 4000


def test_triclinic_periodic_region_volume_is_lattice_translation_invariant():
    initial = normalize_insertion_regions([
        {"id": "window", "role": "allow", "bounds": [-0.8, 2.2, -0.5, 2.0, 1.0, 4.0]},
    ])
    translated = [initial[0].translated(TRICLINIC_CELL[1])]
    first = build_insertion_domain(
        cell=TRICLINIC_CELL,
        pbc=[True, True, True],
        regions=initial,
        pbc_aware=True,
    )
    second = build_insertion_domain(
        cell=TRICLINIC_CELL,
        pbc=[True, True, True],
        regions=translated,
        pbc_aware=True,
    )
    assert len(first.images) > 1
    assert first.volume == pytest.approx(second.volume, rel=1e-10, abs=1e-10)
    points, _ = second.random_points(1000, seed=14)
    assert np.all(second.contains(points))


def test_periodic_allow_and_reject_regions_wrap_with_exact_known_volume():
    domain = build_insertion_domain(
        cell=np.diag([10.0, 10.0, 10.0]),
        pbc=[True, True, True],
        regions=normalize_insertion_regions([
            {"id": "boundary-window", "role": "allow", "bounds": [8, 12, 0, 10, 0, 10]},
            {"id": "boundary-mask", "role": "reject", "bounds": [9, 11, 0, 10, 0, 10]},
        ]),
        pbc_aware=True,
    )
    # The wrapped Allow interval is x in [8, 10] U [0, 2]. The wrapped Reject
    # removes x in [9, 10] U [0, 1], leaving two 1 A-wide slabs.
    assert domain.volume == pytest.approx(200.0, abs=1e-10)
    probes = np.asarray([
        [0.5, 5.0, 5.0],
        [1.5, 5.0, 5.0],
        [5.0, 5.0, 5.0],
        [8.5, 5.0, 5.0],
        [9.5, 5.0, 5.0],
    ])
    np.testing.assert_array_equal(domain.contains(probes), [False, True, False, True, False])


def test_periodic_domain_confinement_uses_shortest_minimum_image_displacement():
    cell = np.diag([10.0, 10.0, 10.0])
    domain = build_insertion_domain(
        cell=cell,
        pbc=[True, True, True],
        regions=normalize_insertion_regions([
            {"id": "edge", "role": "allow", "bounds": [0, 1, 0, 10, 0, 10]},
        ]),
        pbc_aware=True,
    )
    point = np.asarray([[9.9, 5.0, 5.0]])
    projected = domain.project_points(point)
    assert bool(domain.contains(projected)[0])
    displacement = domain.displacements_to_domain(point)
    np.testing.assert_allclose(displacement, [[0.1, 0.0, 0.0]], atol=2e-7)

    direct = build_insertion_domain(
        cell=cell,
        pbc=[True, True, True],
        regions=domain.regions,
        pbc_aware=False,
    )
    assert direct.displacements_to_domain(point)[0, 0] == pytest.approx(-8.9, abs=2e-7)


def test_triclinic_periodic_confinement_targets_the_wrapped_region_image():
    cell = np.asarray([
        [10.0, 0.0, 0.0],
        [3.0, 8.0, 0.0],
        [0.0, 0.0, 10.0],
    ])
    regions = normalize_insertion_regions([
        {
            "id": "tilted-edge",
            "role": "allow",
            "bounds": [2.8, 3.2, 7.8, 8.2, 0.0, 10.0],
        },
    ])
    point = np.asarray([[9.5, 0.05, 5.0]])

    periodic = build_insertion_domain(
        cell=cell,
        pbc=[True, True, True],
        regions=regions,
        pbc_aware=True,
    )
    projected = periodic.project_points(point)
    assert bool(periodic.contains(projected)[0])
    np.testing.assert_allclose(
        periodic.displacements_to_domain(point),
        [[0.3, 0.0, 0.0]],
        atol=2e-7,
    )

    direct = build_insertion_domain(
        cell=cell,
        pbc=[True, True, True],
        regions=regions,
        pbc_aware=False,
    )
    assert np.linalg.norm(direct.displacements_to_domain(point)[0]) > 9.0


def test_density_ratios_are_reduced_before_selecting_complete_batches():
    volume = 1000.0
    primitive_mass = float(
        molecule("H2O").get_masses().sum() + molecule("CO2").get_masses().sum()
    )
    target = primitive_mass / (6.02214076e23 * volume * 1e-24)
    resolved, density = resolve_molecule_density(
        [
            {"name": "H2O", "label": "water", "count": 2, "atom_count": 3},
            {"name": "CO2", "label": "co2", "count": 2, "atom_count": 3},
        ],
        target_density_g_cm3=target,
        accessible_volume_angstrom3=volume,
    )
    assert [entry["requested_ratio"] for entry in resolved] == [2, 2]
    assert [entry["ratio"] for entry in resolved] == [1, 1]
    assert [entry["count"] for entry in resolved] == [1, 1]
    assert density["composition_multiplier"] == 1
    assert density["actual_g_cm3"] == pytest.approx(target, rel=2e-10)

    water_target = float(molecule("H2O").get_masses().sum()) / (
        6.02214076e23 * volume * 1e-24
    )
    single, single_density = resolve_molecule_density(
        [{"name": "H2O", "label": "water", "count": 3, "atom_count": 3}],
        target_density_g_cm3=water_target,
        accessible_volume_angstrom3=volume,
    )
    assert single[0]["ratio"] == 1
    assert single[0]["count"] == 1
    assert single_density["molecule_count"] == 1


@pytest.mark.parametrize("invalid", [1.9, "2", True])
def test_fractional_string_and_boolean_counts_are_rejected_without_mutation(invalid):
    host = make_host()
    atom_session = EditorSession("invalid-atom-count", host.copy(), host.copy())
    with pytest.raises(ValueError, match="Atom count must be an integer"):
        start_atom_addition(atom_session, {
            "entries": [{"element": "H", "label": "H_added", "count": invalid}],
            "region_mode": "cell",
        })
    assert atom_session.atom_addition is None
    assert_host_unchanged(host, atom_session.working_atoms)

    molecule_session = EditorSession(
        "invalid-molecule-count",
        host.copy(),
        host.copy(),
    )
    with pytest.raises(ValueError, match="Molecule count must be an integer"):
        start_atom_addition(molecule_session, {
            "content_kind": "molecules",
            "molecules": [{"name": "H2O", "label": "water", "count": invalid}],
            "region_mode": "cell",
        })
    assert molecule_session.atom_addition is None
    assert_host_unchanged(host, molecule_session.working_atoms)


def test_density_preview_uses_exact_accessible_volume_and_reports_realized_density():
    atoms = Atoms(cell=np.diag([20.0, 20.0, 20.0]), pbc=True)
    preview = atom_addition_domain_preview(atoms, {
        "content_kind": "molecules",
        "molecules": [{"name": "H2O", "label": "water", "count": 1}],
        "molecule_quantity_mode": "density",
        "target_density_g_cm3": 0.997,
        "region_mode": "regions",
        "regions": [
            {"id": "allow", "role": "allow", "bounds": [0, 20, 0, 20, 0, 20]},
            {"id": "reject", "role": "reject", "bounds": [0, 10, 0, 10, 0, 10]},
        ],
        "region_mic": False,
    })
    assert preview["domain"]["volume_angstrom3"] == pytest.approx(7000.0, abs=1e-9)
    density = preview["density"]
    resolved_count = preview["resolved_molecules"][0]["count"]
    assert resolved_count == density["molecule_count"]
    assert density["target_g_cm3"] == pytest.approx(0.997)
    assert abs(density["actual_g_cm3"] - 0.997) < 0.003


def test_density_preview_keeps_exact_volume_when_target_is_not_realizable():
    atoms = Atoms(cell=np.diag([2.0, 2.0, 2.0]), pbc=True)
    preview = atom_addition_domain_preview(atoms, {
        "content_kind": "molecules",
        "molecules": [{"name": "H2O", "label": "water", "count": 1}],
        "molecule_quantity_mode": "density",
        "target_density_g_cm3": 0.001,
        "region_mode": "regions",
        "regions": [],
    })
    assert preview["domain"]["volume_angstrom3"] == pytest.approx(8.0, abs=1e-12)
    assert "fewer than one composition batch" in preview["density_error"]
    assert "density" not in preview


def test_multi_region_session_update_preserves_region_ids_and_host_state():
    host = make_host()
    session = EditorSession("multi-region", host.copy(), host.copy())
    start_atom_addition(session, {
        "entries": [{"element": "H", "label": "H_added", "count": 12}],
        "region_mode": "regions",
        "regions": [
            {"id": "allow-a", "role": "allow", "bounds": [0, 3, 0, 3, 0, 3]},
            {"id": "allow-b", "role": "allow", "bounds": [4, 7, 3, 6, 2, 5]},
            {"id": "reject-a", "role": "reject", "bounds": [1, 2, 1, 2, 1, 2]},
        ],
        "region_mic": True,
        "seed": 21,
    })
    before = session.atom_addition
    moved = [region.translated([0.25, -0.4, 0.1]).to_json() for region in before.regions]
    summary = update_atom_addition_region(
        session,
        {"regions": moved, "region_mic": False},
    )
    assert [region["id"] for region in summary["regions"]] == [
        "allow-a", "allow-b", "reject-a"
    ]
    np.testing.assert_allclose(session.working_atoms.positions[: len(host)], host.positions)
    assert summary["accessible_volume_angstrom3"] > 0.0
    assert summary["region_mode"] == "regions"
    assert summary["domain"]["pbc_aware"] is False
    restored = update_atom_addition_region(session, {"region_mic": True})
    assert restored["domain"]["pbc_aware"] is True


def assert_host_unchanged(reference: Atoms, candidate: Atoms) -> None:
    count = len(reference)
    np.testing.assert_array_equal(candidate.positions[:count], reference.positions)
    np.testing.assert_array_equal(candidate.cell.array, reference.cell.array)
    np.testing.assert_array_equal(candidate.pbc, reference.pbc)
    assert atom_labels(candidate)[:count] == atom_labels(reference)
    assert set(candidate.arrays) >= set(reference.arrays)
    for name, values in reference.arrays.items():
        np.testing.assert_array_equal(candidate.arrays[name][:count], values)
    assert [repr(item) for item in candidate.constraints] == [
        repr(item) for item in reference.constraints
    ]
    if reference.calc is not None:
        assert type(candidate.calc) is type(reference.calc)
        assert dict(candidate.calc.parameters) == dict(reference.calc.parameters)


def test_triclinic_unit_cell_sampling_is_volume_uniform_and_reproducible():
    first = sample_unit_cell_positions(TRICLINIC_CELL, 80_000, seed=1847)
    second = sample_unit_cell_positions(TRICLINIC_CELL, 80_000, seed=1847)
    np.testing.assert_array_equal(first, second)

    fractional = first @ np.linalg.inv(TRICLINIC_CELL)
    assert np.all(fractional >= 0.0)
    assert np.all(fractional < 1.0)
    np.testing.assert_allclose(fractional.mean(axis=0), 0.5, atol=0.004)
    np.testing.assert_allclose(fractional.var(axis=0), 1.0 / 12.0, atol=0.002)

    occupancy, _ = np.histogramdd(
        fractional,
        bins=(4, 4, 4),
        range=((0, 1), (0, 1), (0, 1)),
    )
    expected = len(first) / occupancy.size
    # A generous six-sigma multinomial bound catches spatial bias without
    # making the deterministic statistical test fragile.
    sigma = np.sqrt(expected * (1.0 - 1.0 / occupancy.size))
    assert float(np.max(np.abs(occupancy - expected))) < 6.0 * sigma


def test_cartesian_box_sampling_uses_only_one_periodic_representation():
    bounds = cell_cartesian_bounds(TRICLINIC_CELL)
    positions, diagnostics = sample_cartesian_box_positions(
        TRICLINIC_CELL,
        [True, True, True],
        bounds,
        20_000,
        seed=29,
    )
    fractional = positions @ np.linalg.inv(TRICLINIC_CELL)
    assert np.all(fractional >= 0.0)
    assert np.all(fractional < 1.0)
    for axis in range(3):
        assert np.all(positions[:, axis] >= bounds[2 * axis])
        assert np.all(positions[:, axis] <= bounds[2 * axis + 1])
    assert diagnostics["attempted"] > diagnostics["accepted"]
    assert 0.0 < diagnostics["acceptance_fraction"] < 1.0


def test_prohibited_box_sampling_is_uniform_in_one_triclinic_cell():
    bounds = [2.0, 4.5, 1.4, 3.8, 1.2, 4.1]
    positions, diagnostics = sample_unit_cell_positions_outside_box(
        TRICLINIC_CELL,
        bounds,
        30_000,
        seed=907,
    )
    fractional = positions @ np.linalg.inv(TRICLINIC_CELL)
    assert np.all(fractional >= 0.0)
    assert np.all(fractional < 1.0)
    lower = np.asarray(bounds[::2])
    upper = np.asarray(bounds[1::2])
    assert not np.any(np.all((positions >= lower) & (positions <= upper), axis=1))
    assert 0.0 < diagnostics["acceptance_fraction"] < 1.0


def test_prohibited_region_projection_moves_only_inside_mobile_atoms():
    positions = np.asarray([
        [2.0, 2.0, 2.0],
        [2.5, 2.4, 2.3],
        [5.0, 5.0, 5.0],
    ])
    projected = project_positions_to_region(
        positions,
        cell=np.diag([8.0, 8.0, 8.0]),
        pbc=True,
        mode="box",
        bounds=[1.0, 3.0, 1.0, 3.0, 1.0, 3.0],
        indices=[1, 2],
        prohibited=True,
    )
    np.testing.assert_array_equal(projected[0], positions[0])
    assert not np.all((projected[1] >= 1.0) & (projected[1] <= 3.0))
    np.testing.assert_array_equal(projected[2], positions[2])


def test_homogeneous_cartesian_and_fractional_metrics_are_distinct_and_reproducible():
    cell = np.asarray([[14.0, 0.0, 0.0], [2.0, 4.0, 0.0], [-1.0, 1.0, 3.0]])
    cartesian, cartesian_info = sample_homogeneous_positions(
        cell,
        [True, True, True],
        32,
        coordinate_basis="cartesian",
        seed=7,
    )
    repeated, _ = sample_homogeneous_positions(
        cell,
        [True, True, True],
        32,
        coordinate_basis="cartesian",
        seed=7,
    )
    fractional, fractional_info = sample_homogeneous_positions(
        cell,
        [True, True, True],
        32,
        coordinate_basis="fractional",
        seed=7,
    )
    np.testing.assert_array_equal(cartesian, repeated)

    inverse = np.linalg.inv(cell)

    def nearest(points, *, physical):
        delta = (points[:, None, :] - points[None, :, :]) @ inverse
        delta -= np.rint(delta)
        if physical:
            delta = delta @ cell
        distances = np.linalg.norm(delta, axis=2)
        np.fill_diagonal(distances, np.inf)
        return distances.min(axis=1)

    assert nearest(cartesian, physical=True).min() > nearest(fractional, physical=True).min()
    assert nearest(fractional, physical=False).min() > nearest(cartesian, physical=False).min()
    assert cartesian_info["coordinate_basis"] == "cartesian"
    assert fractional_info["coordinate_basis"] == "fractional"


@pytest.mark.parametrize("count", [17, 31, 63])
def test_homogeneous_cartesian_placement_reduces_local_environment_variation(count):
    cell = np.asarray([[12.0, 0.0, 0.0], [2.5, 7.0, 0.0], [-1.0, 1.5, 5.0]])
    positions, diagnostics = sample_homogeneous_positions(
        cell,
        [True, True, True],
        count,
        coordinate_basis="cartesian",
        seed=41,
    )
    delta = positions[:, None, :] - positions[None, :, :]
    mic, _ = find_mic(delta.reshape(-1, 3), cell, pbc=True)
    distances = np.linalg.norm(mic.reshape(count, count, 3), axis=2)
    np.fill_diagonal(distances, np.inf)
    nearest = distances.min(axis=1)
    assert diagnostics["placement_algorithm"] == "maximin-low-discrepancy"
    assert diagnostics["spacing_metric"] == "angstrom"
    assert diagnostics["nearest_distance_min"] == pytest.approx(nearest.min())
    assert diagnostics["nearest_distance_cv"] == pytest.approx(
        nearest.std() / nearest.mean()
    )
    assert diagnostics["nearest_distance_cv"] < 0.10
    assert diagnostics["covering_radius_estimate"] < 1.6 * nearest.mean()


def test_regular_cartesian_grid_is_exact_and_deduplicates_periodic_boundaries():
    positions, diagnostics = sample_regular_positions(
        np.diag([10.0, 10.0, 10.0]),
        [True, True, True],
        8,
        spacing=5.0,
    )
    assert len(positions) == 8
    assert set(np.unique(positions)) == {0.0, 5.0}
    fractional = positions / 10.0
    assert np.all((fractional >= 0.0) & (fractional < 1.0))
    assert diagnostics["regular_spacing_angstrom"] == pytest.approx(5.0)
    assert diagnostics["nearest_distance_min"] == pytest.approx(5.0)
    assert diagnostics["nearest_distance_cv"] == pytest.approx(0.0)


def test_regular_grid_clips_exactly_to_nonperiodic_allow_minus_reject_domain():
    regions = [
        {"id": "allow", "name": "Allow", "role": "allow", "bounds": [0, 6, 0, 6, 0, 6]},
        {"id": "reject", "name": "Reject", "role": "reject", "bounds": [2, 4, 2, 4, 2, 4]},
    ]
    positions, diagnostics = sample_regular_positions(
        np.zeros((3, 3)),
        [False, False, False],
        12,
        regions=regions,
        spacing=2.0,
    )
    domain = build_insertion_domain(
        cell=np.zeros((3, 3)),
        pbc=[False, False, False],
        regions=normalize_insertion_regions(regions),
    )
    assert np.all(domain.contains(positions))
    assert diagnostics["placement_algorithm"] == "cartesian-regular-grid"
    assert np.allclose(positions / 2.0, np.rint(positions / 2.0))


def test_regular_grid_rejects_spacing_with_too_few_accessible_sites():
    with pytest.raises(ValueError, match="provides only"):
        sample_regular_positions(
            np.diag([10.0, 10.0, 10.0]),
            [True, True, True],
            9,
            spacing=10.0,
        )


def test_cartesian_homogeneous_metric_uses_exact_triclinic_minimum_image():
    cell = np.asarray([
        [4.0, 0.0, 0.0],
        [3.8, 1.0, 0.0],
        [0.2, 0.1, 3.0],
    ])
    points = np.asarray([[1.34594834, -0.56450564, -0.23002065]]) @ cell
    from v_ase.add_atoms import _metric_distance_squared

    distance_squared = _metric_distance_squared(
        points,
        np.zeros(3),
        cell=cell,
        pbc=[True, True, True],
        coordinate_basis="cartesian",
        pbc_aware=True,
    )
    expected = (np.asarray([1.34594834, -0.56450564, -0.23002065]) - [1, 0, 0]) @ cell
    np.testing.assert_allclose(distance_squared, [expected @ expected], atol=1e-12)


def test_cached_cartesian_metric_uses_reduced_lattice_safe_radius():
    from v_ase.add_atoms import _InsertionDistanceMetric

    cell = np.asarray([
        [4.0, 0.0, 0.0],
        [3.8, 1.0, 0.0],
        [0.2, 0.1, 3.0],
    ])
    fractional = np.asarray([
        [-0.49557537, 0.44776208, 0.34318780],
        [0.47231122, -0.49142012, -0.30771493],
    ])
    vectors = fractional @ cell
    metric = _InsertionDistanceMetric(cell, [True, True, True], "cartesian", True)
    actual = metric.squared(vectors, np.zeros(3))
    shifts = np.asarray(list(itertools.product(range(-2, 3), repeat=3)), dtype=float)
    images = vectors[None, :, :] + (shifts @ cell)[:, None, :]
    expected = np.min(np.einsum("sni,sni->sn", images, images), axis=0)
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize("pbc", ([True, True, True], [True, False, True]))
def test_cached_cartesian_metric_matches_ase_for_triclinic_vectors(pbc):
    from v_ase.add_atoms import _InsertionDistanceMetric

    generator = np.random.default_rng(703)
    vectors = generator.uniform(-3.0, 3.0, size=(4000, 3)) @ TRICLINIC_CELL
    metric = _InsertionDistanceMetric(TRICLINIC_CELL, pbc, "cartesian", True)
    actual = metric.squared(vectors, np.zeros(3))
    expected_vectors, _ = find_mic(vectors, TRICLINIC_CELL, pbc=pbc)
    expected = np.einsum("ij,ij->i", expected_vectors, expected_vectors)
    np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=1e-12)


def test_random_cartesian_and_fractional_sampling_remain_volume_uniform_in_triclinic_cell():
    for basis in ("cartesian", "fractional"):
        positions, diagnostics = sample_insertion_positions(
            TRICLINIC_CELL,
            [True, True, True],
            40_000,
            placement_mode="random",
            coordinate_basis=basis,
            seed=281,
        )
        fractional = positions @ np.linalg.inv(TRICLINIC_CELL)
        assert np.all((fractional >= 0.0) & (fractional < 1.0))
        np.testing.assert_allclose(fractional.mean(axis=0), 0.5, atol=0.006)
        assert diagnostics["coordinate_basis"] == basis


def test_ase_molecule_catalog_and_rotations_cover_installed_g2_data():
    catalog = molecule_catalog()
    names = {entry["name"] for entry in catalog}
    assert {"H2O", "CO2", "C6H6", "NH3"} <= names
    assert len(catalog) == len(names) >= 150
    rotations = uniform_rotation_matrices(2048, seed=91)
    identities = rotations @ np.swapaxes(rotations, 1, 2)
    np.testing.assert_allclose(
        identities,
        np.repeat(np.eye(3)[None, :, :], len(rotations), axis=0),
        atol=1e-12,
    )
    np.testing.assert_allclose(np.linalg.det(rotations), 1.0, atol=1e-12)
    # A Haar-uniform rotation has no preferred direction for a rotated axis.
    np.testing.assert_allclose(rotations[:, :, 0].mean(axis=0), 0.0, atol=0.035)


def test_molecule_catalog_is_discoverable_before_switching_to_edit_mode():
    host = make_host()
    session = EditorSession(
        "molecule-catalog-view-mode",
        host.copy(),
        host.copy(),
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    try:
        response = asyncio.run(atom_addition_molecule_catalog(session.session_id))
    finally:
        sessions.pop(session.session_id, None)
    names = {entry["name"] for entry in response["molecules"]}
    assert {"H2O", "CO2", "NH3", "C6H6"} <= names


def test_molecule_placement_uses_native_ase_origin_when_orientation_is_fixed():
    anchors = np.asarray([[2.0, 3.0, 4.0], [7.0, 8.0, 9.0]])
    result = expand_molecules(
        [{"name": "H2O", "label": "water", "count": 2}],
        anchors,
        random_orientation=False,
        seed=10,
    )
    reference = molecule("H2O").positions
    np.testing.assert_allclose(result["positions"][result["groups"][0]], reference + anchors[0])
    np.testing.assert_allclose(result["positions"][result["groups"][1]], reference + anchors[1])


def test_rigid_constraint_preserves_geometry_net_force_and_torque():
    reference = molecule("H2O").positions
    group = np.arange(3)
    atoms = molecule("H2O")
    constraint = RigidMoleculeConstraint([group], [reference])
    proposed = atoms.positions + np.asarray([
        [0.4, -0.2, 0.1], [-0.3, 0.1, 0.2], [0.2, 0.3, -0.2],
    ])
    constraint.adjust_positions(atoms, proposed)
    expected = np.linalg.norm(reference[:, None, :] - reference[None, :, :], axis=2)
    actual = np.linalg.norm(proposed[:, None, :] - proposed[None, :, :], axis=2)
    np.testing.assert_allclose(actual, expected, atol=1e-12)

    atoms.positions[:] = proposed
    original_forces = np.asarray([
        [1.2, -0.4, 0.3], [-0.5, 1.1, -0.2], [0.7, 0.2, 0.8],
    ])
    projected = original_forces.copy()
    center = atoms.positions.mean(axis=0)
    torque_before = np.sum(np.cross(atoms.positions - center, original_forces), axis=0)
    constraint.adjust_forces(atoms, projected)
    torque_after = np.sum(np.cross(atoms.positions - center, projected), axis=0)
    np.testing.assert_allclose(projected.sum(axis=0), original_forces.sum(axis=0), atol=1e-12)
    np.testing.assert_allclose(torque_after, torque_before, atol=1e-12)


def test_rigid_molecule_repulsion_excludes_intramolecular_pairs():
    atoms = molecule("H2O")
    atoms.set_cell([12.0, 12.0, 12.0])
    atoms.center()
    atoms.set_pbc(True)
    atoms.set_tags([3, 3, 3])
    reference = atoms.positions.copy()
    atoms.calc = AdditionRepulsionCalculator(
        min_bondinfo={"H-H": 10.0, "H-O": 10.0, "O-O": 10.0},
        k_repulsion=5.0,
        cutoff_scale=1.0,
        mic=True,
        work_on_relax_atoms_too=False,
        rigid_groups=[[0, 1, 2]],
        rigid_references=[reference],
    )
    np.testing.assert_allclose(atoms.get_forces(), np.zeros((3, 3)), atol=1e-12)
    assert atoms.get_potential_energy() == pytest.approx(0.0, abs=1e-12)


def test_homogeneous_cartesian_box_and_prohibited_region_respect_primary_cell():
    bounds = [1.2, 5.5, 0.8, 4.7, 0.5, 4.9]
    allowed, allowed_info = sample_insertion_positions(
        TRICLINIC_CELL,
        [True, True, True],
        24,
        placement_mode="homogeneous",
        coordinate_basis="cartesian",
        region_mode="box",
        bounds=bounds,
        region_role="allowed",
        pbc_aware=True,
        seed=19,
    )
    prohibited, prohibited_info = sample_insertion_positions(
        TRICLINIC_CELL,
        [True, True, True],
        24,
        placement_mode="homogeneous",
        coordinate_basis="cartesian",
        region_mode="box",
        bounds=bounds,
        region_role="prohibited",
        pbc_aware=True,
        seed=19,
    )
    lower = np.asarray(bounds[::2])
    upper = np.asarray(bounds[1::2])
    assert np.all((allowed >= lower) & (allowed <= upper))
    assert not np.any(np.all((prohibited >= lower) & (prohibited <= upper), axis=1))
    inverse = np.linalg.inv(TRICLINIC_CELL)
    for points in (allowed, prohibited):
        fractional = points @ inverse
        assert np.all((fractional >= 0.0) & (fractional < 1.0))
    assert allowed_info["placement_mode"] == "homogeneous"
    assert prohibited_info["region_role"] == "prohibited"


def test_random_addition_cancel_restores_every_host_property_and_history():
    host = make_host()
    session = EditorSession("add-cancel", host.copy(), host.copy())
    redo_marker = session._history_state()
    session.redo_stack.append(redo_marker)

    result = start_atom_addition(session, {
        "entries": [
            {"element": "Li", "label": "Li_mobile", "count": 12},
            {"element": "H", "label": "H_probe", "count": 5},
        ],
        "region_mode": "cell",
        "seed": 11,
        "freeze_existing": True,
    })

    assert result["new_count"] == 17
    assert len(session.working_atoms) == len(host) + 17
    assert result["temporary_fixed_indices"] == list(range(len(host)))
    cancel_atom_addition(session)

    assert session.atom_addition is None
    assert len(session.working_atoms) == len(host)
    assert_host_unchanged(host, session.working_atoms)
    assert session.redo_stack == [redo_marker]
    assert not session.history


@pytest.mark.parametrize("finish", [False, True])
def test_addition_cancel_and_finish_preserve_reusable_host_calculator(finish):
    host = make_host()
    host.calc = LennardJones(epsilon=0.7, sigma=2.1, rc=5.0)
    original = host.copy()
    original.calc = LennardJones(epsilon=0.7, sigma=2.1, rc=5.0)
    working = host.copy()
    working.calc = LennardJones(epsilon=0.7, sigma=2.1, rc=5.0)
    session = EditorSession(f"add-calculator-{finish}", original, working)

    start_atom_addition(session, {
        "element": "H",
        "label": "H_inserted",
        "count": 2,
        "seed": 21,
    })
    if finish:
        finish_atom_addition(session)
        assert len(session.working_atoms) == len(host) + 2
        assert np.isfinite(session.working_atoms.get_potential_energy())
    else:
        cancel_atom_addition(session)
        assert len(session.working_atoms) == len(host)

    assert type(session.working_atoms.calc) is LennardJones
    assert dict(session.working_atoms.calc.parameters) == dict(host.calc.parameters)


def test_random_addition_rejects_trajectory_topology_changes():
    first = make_host()
    second = make_host()
    second.positions += [0.1, -0.2, 0.3]
    session = EditorSession(
        "add-trajectory",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )

    with pytest.raises(ValueError, match="requires a single structure"):
        start_atom_addition(session, {
            "element": "Li",
            "label": "Li_new",
            "count": 4,
            "region_mode": "cell",
            "seed": 5,
        })

    assert session.atom_addition is None
    assert len(session.trajectory_frames) == 2
    assert_host_unchanged(first, session.working_atoms)


def test_random_addition_finish_reconstructs_host_from_immutable_baseline():
    host = make_host()
    session = EditorSession("add-finish", host.copy(), host.copy())
    start_atom_addition(session, {
        "element": "Li",
        "label": "Li_inserted",
        "count": 8,
        "region_mode": "box",
        "bounds": cell_cartesian_bounds(TRICLINIC_CELL),
        "seed": 9,
    })

    # Simulate temporary host motion from an unfrozen optimizer. Finish must
    # discard it while retaining the inserted coordinates.
    session.working_atoms.positions[: len(host)] += 0.314
    inserted_before = session.working_atoms.positions[len(host) :].copy()
    result = finish_atom_addition(session)

    assert result["added"] == 8
    assert_host_unchanged(host, session.working_atoms)
    np.testing.assert_allclose(session.working_atoms.positions[len(host) :], inserted_before)
    assert atom_labels(session.working_atoms)[len(host) :] == ["Li_inserted"] * 8
    assert session.atom_addition is None


def test_finish_rejects_untracked_topology_or_identity_changes():
    host = make_host()
    session = EditorSession("add-topology-guard", host.copy(), host.copy())
    start_atom_addition(session, {
        "element": "Li",
        "label": "Li_inserted",
        "count": 2,
        "region_mode": "cell",
        "seed": 12,
    })
    session.working_atoms.append("H")
    with pytest.raises(ValueError, match="topology changed unexpectedly"):
        finish_atom_addition(session)
    assert session.atom_addition is not None

    session.working_atoms = session.working_atoms[:-1]
    session.working_atoms[-1].symbol = "H"
    with pytest.raises(ValueError, match="element mapping changed unexpectedly"):
        finish_atom_addition(session)
    assert session.atom_addition is not None


def test_add_atoms_box_role_and_escape_policy_are_independent_and_movable():
    host = make_host()
    session = EditorSession("add-region-policy", host.copy(), host.copy())
    bounds = [2.0, 4.5, 1.4, 3.8, 1.2, 4.1]
    summary = start_atom_addition(session, {
        "element": "Li",
        "label": "Li_inserted",
        "count": 24,
        "region_mode": "box",
        "region_role": "prohibited",
        "allow_escape": True,
        "bounds": bounds,
        "seed": 17,
    })
    assert summary["region_role"] == "prohibited"
    assert summary["allow_escape"] is True
    inserted = session.working_atoms.positions[summary["new_indices"]]
    lower = np.asarray(bounds[::2])
    upper = np.asarray(bounds[1::2])
    assert not np.any(np.all((inserted >= lower) & (inserted <= upper), axis=1))

    moved = [2.3, 4.8, 1.1, 3.5, 1.5, 4.4]
    updated = update_atom_addition_region(session, {
        "bounds": moved,
        "allow_escape": False,
    })
    assert updated["bounds"] == moved
    assert updated["region_role"] == "prohibited"
    assert updated["allow_escape"] is False
    np.testing.assert_array_equal(
        session.working_atoms.positions[summary["new_indices"]],
        inserted,
    )


def test_addition_repulsion_uses_mic_and_moves_only_tag_three_atoms():
    atoms = Atoms(
        "CuH",
        positions=[[0.10, 5.0, 5.0], [9.85, 5.0, 5.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    atoms.set_tags([1, 3])
    atoms.calc = AdditionRepulsionCalculator(
        min_bondinfo={"Cu-H": 1.0},
        cutoff_scale=1.0,
        k_repulsion=2.0,
        mic=True,
        work_on_relax_atoms_too=False,
    )
    forces = atoms.get_forces()

    np.testing.assert_array_equal(forces[0], np.zeros(3))
    assert np.linalg.norm(forces[1]) > 0.0

    without_mic = atoms.copy()
    without_mic.set_tags([1, 3])
    without_mic.calc = AdditionRepulsionCalculator(
        min_bondinfo={"Cu-H": 1.0},
        cutoff_scale=1.0,
        k_repulsion=2.0,
        mic=False,
        work_on_relax_atoms_too=False,
    )
    np.testing.assert_array_equal(without_mic.get_forces(), np.zeros((2, 3)))


def test_repulsive_placement_keeps_host_exact_after_finish(monkeypatch):
    host = make_host()
    session = EditorSession("add-relax", host.copy(), host.copy())
    monkeypatch.setattr("v_ase.add_atoms.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    start_atom_addition(session, {
        "element": "H",
        "label": "H_new",
        "count": 6,
        "region_mode": "cell",
        "seed": 71,
        "freeze_existing": True,
    })
    response = start_atom_addition_relaxation(session, {
        "steps": 12,
        "fmax": 0.1,
        "k_repulsion": 2.0,
        "pair_cutoffs": {
            "Cu-H": 2.1,
            "H-H": 1.2,
            "H-N": 1.6,
            "H-O": 1.5,
        },
    })
    assert response["is_relaxing"] is True
    deadline = time.monotonic() + 10.0
    while session.atom_addition.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.02)
    assert session.atom_addition.is_relaxing is False

    finish_atom_addition(session)
    assert_host_unchanged(host, session.working_atoms)
    assert len(session.working_atoms) == len(host) + 6


def test_repulsive_placement_uses_selected_compute_resources_and_keeps_every_step(
    monkeypatch,
):
    host = make_host()
    session = EditorSession("add-relax-resources", host.copy(), host.copy())
    messages = []
    monkeypatch.setattr(
        "v_ase.add_atoms.ws_manager.broadcast_sync",
        lambda message, *_args, **_kwargs: messages.append(message),
    )
    start_atom_addition(session, {
        "element": "H",
        "label": "H_mobile",
        "count": 4,
        "region_mode": "cell",
        "seed": 19,
        "freeze_existing": True,
    })
    threads = min(2, cpu_thread_options()[-1])
    response = start_atom_addition_relaxation(session, {
        "steps": 4,
        "fmax": 1e-12,
        "k_repulsion": 2.0,
        "pair_cutoffs": {"Cu-H": 4.5, "H-H": 3.0, "H-N": 4.0, "H-O": 4.0},
        "device": "cpu",
        "cpu_threads": threads,
    })

    assert response["requested_device"] == "cpu"
    assert response["cpu_threads"] == threads
    deadline = time.monotonic() + 10.0
    while session.atom_addition.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.02)
    assert session.atom_addition.is_relaxing is False
    steps = sorted({
        int(message["step"])
        for message in messages
        if message.get("type") == "add_atoms_relax_step"
    })
    assert steps == list(range(0, max(steps) + 1))
    assert session.atom_addition.requested_device == "cpu"
    assert session.atom_addition.effective_device == "cpu"
    assert session.atom_addition.cpu_threads == threads


def test_repulsive_placement_calculator_always_receives_the_complete_staged_structure(
    monkeypatch,
):
    host = make_host()
    session = EditorSession("add-relax-full-structure", host.copy(), host.copy())
    monkeypatch.setattr(
        "v_ase.add_atoms.ws_manager.broadcast_sync",
        lambda *_args, **_kwargs: None,
    )
    summary = start_atom_addition(session, {
        "element": "H",
        "label": "H_mobile",
        "count": 5,
        "region_mode": "cell",
        "seed": 29,
        "freeze_existing": True,
    })
    evaluations = []
    original_calculate = AdditionRepulsionCalculator.calculate

    def record_complete_structure(calculator, atoms=None, *args, **kwargs):
        target = atoms if atoms is not None else calculator.atoms
        evaluations.append((len(target), np.asarray(target.get_tags(), dtype=int).copy()))
        return original_calculate(calculator, atoms, *args, **kwargs)

    monkeypatch.setattr(AdditionRepulsionCalculator, "calculate", record_complete_structure)
    start_atom_addition_relaxation(session, {
        "steps": 3,
        "fmax": 1e-12,
        "pair_cutoffs": {"Cu-H": 4.0, "H-H": 3.0, "H-N": 4.0, "H-O": 4.0},
    })
    deadline = time.monotonic() + 10.0
    while session.atom_addition.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.02)

    assert evaluations
    expected_count = len(host) + summary["new_count"]
    assert all(count == expected_count for count, _tags in evaluations)
    assert all(np.count_nonzero(tags == 3) == summary["new_count"] for _count, tags in evaluations)


def test_exact_overlap_mic_fallback_batches_candidate_vectors(monkeypatch):
    atoms = Atoms(
        "H4",
        positions=np.zeros((4, 3)),
        cell=[8.0, 8.0, 8.0],
        pbc=True,
    )
    atoms.set_tags([3, 3, 3, 3])
    monkeypatch.setattr(
        repulsion_module,
        "primitive_neighbor_list",
        lambda *_args, **_kwargs: (
            np.asarray([], dtype=int),
            np.asarray([], dtype=int),
            np.empty((0, 3), dtype=float),
            np.asarray([], dtype=float),
        ),
    )
    mic_shapes = []
    original_find_mic = repulsion_module.find_mic

    def record_batched_mic(vectors, *args, **kwargs):
        mic_shapes.append(np.asarray(vectors).shape)
        return original_find_mic(vectors, *args, **kwargs)

    monkeypatch.setattr(repulsion_module, "find_mic", record_batched_mic)
    atoms.calc = AdditionRepulsionCalculator(
        min_bondinfo={"H-H": 1.0},
        cutoff_scale=1.0,
        k_repulsion=2.0,
        mic=True,
        work_on_relax_atoms_too=True,
    )
    forces = atoms.get_forces()

    assert mic_shapes == [(6, 3)]
    assert np.linalg.norm(forces) > 0.0


def test_rigid_molecule_repulsion_preserves_geometry_and_host_state(monkeypatch):
    host = make_host()
    session = EditorSession("add-rigid-water", host.copy(), host.copy())
    monkeypatch.setattr("v_ase.add_atoms.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    summary = start_atom_addition(session, {
        "content_kind": "molecules",
        "molecules": [{"name": "H2O", "label": "water", "count": 4}],
        "region_mode": "cell",
        "placement_mode": "homogeneous",
        "coordinate_basis": "cartesian",
        "random_orientation": True,
        "rigid_molecules": True,
        "seed": 311,
        "freeze_existing": True,
    })
    addition = session.atom_addition
    references = [
        np.linalg.norm(reference[:, None, :] - reference[None, :, :], axis=2)
        for reference in addition.molecule_references
    ]
    assert summary["molecule_count"] == 4
    assert summary["new_count"] == 12

    start_atom_addition_relaxation(session, {
        "steps": 15,
        "fmax": 0.05,
        "pair_cutoffs": {
            "Cu-H": 1.8,
            "Cu-O": 2.2,
            "H-H": 1.0,
            "H-N": 1.5,
            "H-O": 1.2,
            "N-O": 1.8,
            "O-O": 2.4,
        },
    })
    deadline = time.monotonic() + 10.0
    while addition.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.02)
    assert addition.is_relaxing is False
    for group, reference_distances in zip(addition.molecule_groups, references):
        current = session.working_atoms.positions[group]
        distances = np.linalg.norm(current[:, None, :] - current[None, :, :], axis=2)
        np.testing.assert_allclose(distances, reference_distances, atol=2e-8)
    finish_atom_addition(session)
    assert_host_unchanged(host, session.working_atoms)


def test_rigid_molecule_interactive_edits_require_complete_rigid_bodies():
    host = make_host()
    session = EditorSession("add-rigid-edit", host.copy(), host.copy())
    summary = start_atom_addition(session, {
        "content_kind": "molecules",
        "molecules": [{"name": "H2O", "label": "water", "count": 2}],
        "region_mode": "cell",
        "random_orientation": False,
        "rigid_molecules": True,
        "seed": 912,
    })

    translated = session.working_atoms.positions.copy()
    translated[summary["new_indices"]] += [0.4, -0.2, 0.3]
    apply_atom_addition_positions(session, translated)
    np.testing.assert_allclose(
        session.working_atoms.positions[summary["new_indices"]],
        translated[summary["new_indices"]],
    )

    distorted = translated.copy()
    distorted[summary["molecule_groups"][0][0]] += [0.1, 0.0, 0.0]
    with pytest.raises(ValueError, match="complete rigid body"):
        apply_atom_addition_positions(session, distorted)
    np.testing.assert_allclose(session.working_atoms.positions, translated)


def test_cancel_waits_for_an_inflight_optimizer_commit_then_restores_host(monkeypatch):
    host = make_host()
    session = EditorSession("add-cancel-race", host.copy(), host.copy())
    monkeypatch.setattr("v_ase.add_atoms.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    start_atom_addition(session, {
        "element": "H",
        "label": "H_mobile",
        "count": 16,
        "region_mode": "cell",
        "seed": 33,
        "freeze_existing": True,
    })

    working = session.working_atoms
    original_set_positions = working.set_positions
    commit_entered = threading.Event()
    release_commit = threading.Event()

    def blocked_set_positions(*args, **kwargs):
        commit_entered.set()
        if not release_commit.wait(timeout=5.0):
            raise TimeoutError("Test did not release the optimizer commit.")
        return original_set_positions(*args, **kwargs)

    monkeypatch.setattr(working, "set_positions", blocked_set_positions)
    start_atom_addition_relaxation(session, {
        "steps": 20,
        "fmax": 0.01,
        "k_repulsion": 2.0,
        "pair_cutoffs": {
            "Cu-H": 3.0,
            "H-H": 2.0,
            "H-N": 2.5,
            "H-O": 2.5,
        },
    })
    assert commit_entered.wait(timeout=5.0)

    cancelled = threading.Event()

    def cancel():
        cancel_atom_addition(session)
        cancelled.set()

    cancel_thread = threading.Thread(target=cancel)
    cancel_thread.start()
    try:
        time.sleep(0.05)
        assert not cancelled.is_set()
    finally:
        release_commit.set()
        cancel_thread.join(timeout=5.0)

    assert cancelled.is_set()
    assert session.atom_addition is None
    assert_host_unchanged(host, session.working_atoms)


def test_add_atoms_api_allows_only_inserted_atom_transforms_without_mutating_host():
    host = make_host()
    session = EditorSession("add-api", host.copy(), host.copy(), config={"viz_only": False})
    sessions[session.session_id] = session

    pairs = asyncio.run(atom_addition_pair_cutoffs(session.session_id, {
        "elements": ["Li", "H"],
        "basis": "covalent",
        "scale": 0.7,
    }))
    assert {"Cu-Li", "H-Li", "H-H"} <= set(pairs["pair_cutoffs"])

    data = asyncio.run(start_random_atom_addition(session.session_id, {
        "entries": [
            {"element": "Li", "label": "Li_mobile", "count": 4},
            {"element": "H", "label": "H_probe", "count": 3},
        ],
        "region_mode": "cell",
        "seed": 410,
        "freeze_existing": True,
        "cutoff_basis": "pairwise",
        "pair_cutoffs": pairs["pair_cutoffs"],
    }))
    addition = data["metadata"]["atom_addition"]
    assert addition["active"] is True
    assert addition["new_count"] == 7
    assert 0.0 < addition["sampling"]["acceptance_fraction"] <= 1.0
    assert addition["sampling"]["coordinate_basis"] == "cartesian"
    assert set(range(len(host))) <= set(data["constraints"]["fixed_indices"])
    assert [repr(item) for item in session.atom_addition.baseline_atoms.constraints] == [
        repr(item) for item in host.constraints
    ]
    # Only index zero is truly constrained in the working ASE object. The rest
    # of the host is fixed only on the isolated optimizer copy and in display metadata.
    assert [repr(item) for item in session.working_atoms.constraints] == [
        repr(item) for item in host.constraints
    ]

    transformed = session.working_atoms.positions.copy()
    transformed[addition["new_indices"]] += [0.2, -0.1, 0.3]
    response = asyncio.run(apply_positions(session.session_id, {
        "positions": transformed.tolist(),
    }))
    np.testing.assert_allclose(
        response["positions"][len(host):],
        transformed[len(host):],
    )
    assert_host_unchanged(host, session.atom_addition.baseline_atoms)
    np.testing.assert_array_equal(session.working_atoms.positions[:len(host)], host.positions)

    stale = session.working_atoms.positions.copy()
    stale[0] += [0.1, 0.0, 0.0]
    with pytest.raises(HTTPException, match="Only atoms inserted") as exc_info:
        asyncio.run(apply_positions(session.session_id, {"positions": stale.tolist()}))
    assert exc_info.value.status_code == 409

    cancelled = asyncio.run(cancel_random_atom_addition(session.session_id))
    assert cancelled["metadata"]["atom_addition"] is None
    assert_host_unchanged(host, session.working_atoms)


def test_add_atoms_api_finish_commits_only_inserted_atoms():
    host = make_host()
    session = EditorSession("add-api-finish", host.copy(), host.copy(), config={"viz_only": False})
    sessions[session.session_id] = session
    asyncio.run(start_random_atom_addition(session.session_id, {
        "element": "Ne",
        "label": "Ne_void",
        "count": 5,
        "region_mode": "box",
        "bounds": cell_cartesian_bounds(TRICLINIC_CELL),
        "seed": 17,
    }))
    inserted = session.working_atoms.positions[len(host):].copy()
    session.working_atoms.positions[:len(host)] += 1.0

    data = asyncio.run(finish_random_atom_addition(session.session_id))
    assert data["metadata"]["atom_addition"] is None
    assert data["metadata"]["atom_addition_result"]["added"] == 5
    assert_host_unchanged(host, session.working_atoms)
    np.testing.assert_allclose(session.working_atoms.positions[len(host):], inserted)


def test_browser_random_add_atoms_mode_scatter_relax_and_finish():
    host = make_host()
    port = find_free_port()
    editor = view(
        host,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")

            page.evaluate("window.__ASE_APP__.toast('Layout check')")
            page.wait_for_selector("#toast-container .toast.show")
            launcher_layout = page.evaluate("""() => {
                const launcher = document.getElementById('create-atom-widget').getBoundingClientRect();
                const header = document.getElementById('top-bar').getBoundingClientRect();
                const toast = document.querySelector('#toast-container .toast.show').getBoundingClientRect();
                return {
                    left: launcher.left,
                    top: launcher.top,
                    right: launcher.right,
                    bottom: launcher.bottom,
                    headerBottom: header.bottom,
                    toastLeft: toast.left,
                    toastTop: toast.top,
                    toastRight: toast.right,
                    toastBottom: toast.bottom,
                };
            }""")
            assert launcher_layout["left"] == pytest.approx(18, abs=1)
            assert launcher_layout["top"] >= launcher_layout["headerBottom"] + 12
            assert (
                launcher_layout["right"] <= launcher_layout["toastLeft"]
                or launcher_layout["left"] >= launcher_layout["toastRight"]
                or launcher_layout["bottom"] <= launcher_layout["toastTop"]
                or launcher_layout["top"] >= launcher_layout["toastBottom"]
            )

            host_visual_radii = page.evaluate("""async () => {
                await window.v_aseAI.apply({
                    display: {
                        atomRadiusScale: 0.73,
                        labelRadii: {
                            Cu_surface: 1.11,
                            O_bridge: 0.84,
                            N_anchor: 0.69
                        }
                    }
                });
                const renderer = window.__ASE_APP__.renderer;
                return [0, 1, 2].map(index => renderer.atomMeshByIndex.get(index).scale.x);
            }""")

            page.click("#btn-create-atom-toggle")
            page.fill("#create-atom-label", "O_single")
            assert page.locator("#create-atom-type").input_value() == "O"
            page.click("#add-atoms-tab-batch")
            page.locator(".add-atoms-session-actions").scroll_into_view_if_needed()
            panel_layout = page.evaluate("""() => {
                const card = document.getElementById('create-atom-card').getBoundingClientRect();
                const body = document.getElementById('add-atoms-pane-batch');
                const actions = document.querySelector('.add-atoms-session-actions').getBoundingClientRect();
                return {
                    cardTop: card.top,
                    cardBottom: card.bottom,
                    viewportHeight: window.innerHeight,
                    actionsTop: actions.top,
                    actionsBottom: actions.bottom,
                    bodyClientHeight: body.clientHeight,
                    bodyScrollHeight: body.scrollHeight,
                };
            }""")
            assert panel_layout["cardTop"] >= 0
            assert panel_layout["cardBottom"] <= panel_layout["viewportHeight"]
            assert panel_layout["actionsTop"] >= panel_layout["cardTop"]
            assert panel_layout["actionsBottom"] <= panel_layout["cardBottom"] + 1
            assert panel_layout["bodyScrollHeight"] > panel_layout["bodyClientHeight"]
            drag_handle = page.locator("#create-atom-drag")
            drag_box = drag_handle.bounding_box()
            assert drag_box is not None
            page.mouse.move(
                drag_box["x"] + drag_box["width"] / 2,
                drag_box["y"] + drag_box["height"] / 2,
            )
            page.mouse.down()
            page.mouse.move(10_000, 10_000, steps=4)
            page.mouse.up()
            dragged_layout = page.evaluate("""() => {
                const panel = document.getElementById('create-atom-widget').getBoundingClientRect();
                const header = document.getElementById('top-bar').getBoundingClientRect();
                return {
                    left: panel.left,
                    right: panel.right,
                    top: panel.top,
                    bottom: panel.bottom,
                    width: window.innerWidth,
                    height: window.innerHeight,
                    headerBottom: header.bottom
                };
            }""")
            assert dragged_layout["left"] >= 8
            assert dragged_layout["right"] <= dragged_layout["width"] - 8 + 1
            assert dragged_layout["top"] >= dragged_layout["headerBottom"] + 8
            assert dragged_layout["bottom"] <= dragged_layout["height"] - 8 + 1

            drag_box = drag_handle.bounding_box()
            assert drag_box is not None
            page.mouse.move(
                drag_box["x"] + drag_box["width"] / 2,
                drag_box["y"] + drag_box["height"] / 2,
            )
            page.mouse.down()
            page.mouse.move(-10_000, -10_000, steps=4)
            page.mouse.up()
            clamped_layout = page.locator("#create-atom-widget").bounding_box()
            assert clamped_layout is not None
            assert clamped_layout["x"] >= 8
            assert clamped_layout["y"] >= dragged_layout["headerBottom"] + 8
            page.locator("#add-atoms-placement-random").scroll_into_view_if_needed()
            assert page.locator("#add-atoms-spacing-basis-row").is_hidden()
            assert page.locator("#add-atoms-placement-pbc-row").is_hidden()
            assert page.locator("#add-atoms-allow-escape").is_checked()
            page.click("#btn-add-atoms-allow-region")
            page.click("#btn-add-atoms-reject-region")
            assert page.locator("#add-atoms-region-list .add-atoms-region-item").count() == 2
            page.locator("#add-atoms-region-list .add-atoms-region-item").first.click(
                modifiers=["Shift"]
            )
            page.wait_for_function(
                "window.__ASE_APP__.renderer.addAtomsRegionGroup.visible === true"
            )
            assert page.evaluate(
                "window.__ASE_APP__.renderer.addAtomsRegionGroup.children.length"
            ) >= 2
            periodic_box_visuals = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.setAddAtomsRegions({
                    visible: true,
                    pbcAware: true,
                    pbc: [true, true, true],
                    cell: app.state.atoms.cell,
                    selectedIds: ['crossing-box'],
                    regions: [{
                        id: 'crossing-box',
                        name: 'Crossing box',
                        role: 'allow',
                        bounds: [-1, 2, 1, 3, 1, 3],
                    }],
                });
                const children = app.renderer.addAtomsRegionGroup.children;
                const sourceFill = children.find(child => (
                    child.userData?.insertionRegionSourceBox
                    && !child.userData?.cellEdgeInstances
                ));
                sourceFill.geometry.computeBoundingBox();
                const wrappedFills = children.filter(child => (
                    child.userData?.insertionRegionWrappedFragment
                    && !child.userData?.cellEdgeInstances
                ));
                const wrappedEdges = children.filter(child => (
                    child.userData?.insertionRegionWrappedFragment
                    && child.userData?.cellEdgeInstances
                ));
                const matrices = [];
                wrappedEdges.forEach(mesh => {
                    for (let index = 0; index < mesh.count; index++) {
                        const offset = index * 16;
                        const values = Array.from(
                            mesh.instanceMatrix.array.slice(offset, offset + 16)
                        );
                        matrices.push(values.map(value => Math.round(value * 1e7)).join(':'));
                    }
                });
                const result = {
                    sourceBounds: [
                        sourceFill.geometry.boundingBox.min.x,
                        sourceFill.geometry.boundingBox.max.x,
                        sourceFill.geometry.boundingBox.min.y,
                        sourceFill.geometry.boundingBox.max.y,
                        sourceFill.geometry.boundingBox.min.z,
                        sourceFill.geometry.boundingBox.max.z,
                    ],
                    sourceFillCount: children.filter(child => (
                        child.userData?.insertionRegionSourceBox
                        && !child.userData?.cellEdgeInstances
                    )).length,
                    sourceEdgeCount: children.filter(child => (
                        child.userData?.insertionRegionSourceBox
                        && child.userData?.cellEdgeInstances
                    )).length,
                    wrappedFillCount: wrappedFills.length,
                    wrappedEdgeCount: wrappedEdges.length,
                    wrappedShifts: wrappedFills.map(child => child.userData.shift),
                    wrappedSegmentCount: matrices.length,
                    uniqueWrappedSegmentCount: new Set(matrices).size,
                };
                app.updateAddAtomsRegionPreview();
                return result;
            }""")
            assert periodic_box_visuals["sourceFillCount"] == 1
            assert periodic_box_visuals["sourceEdgeCount"] == 1
            assert periodic_box_visuals["sourceBounds"] == pytest.approx(
                [-1, 2, 1, 3, 1, 3]
            )
            assert periodic_box_visuals["wrappedFillCount"] >= 1
            assert periodic_box_visuals["wrappedEdgeCount"] == 1
            assert all(
                any(component != 0 for component in shift)
                for shift in periodic_box_visuals["wrappedShifts"]
            )
            assert periodic_box_visuals["wrappedSegmentCount"] == (
                periodic_box_visuals["uniqueWrappedSegmentCount"]
            )
            full_period_box = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const orthogonalCell = [[8, 0, 0], [0, 8, 0], [0, 0, 8]];
                app.renderer.setAddAtomsRegions({
                    visible: true,
                    pbcAware: true,
                    pbc: [true, true, true],
                    cell: orthogonalCell,
                    selectedIds: ['full-period-box'],
                    regions: [{
                        id: 'full-period-box',
                        name: 'Full-period box',
                        role: 'reject',
                        bounds: [0, 8, 0, 8, 1, 3],
                    }],
                });
                const children = app.renderer.addAtomsRegionGroup.children;
                const wrapped = children.filter(child => (
                    child.userData?.insertionRegionWrappedFragment
                    && !child.userData?.cellEdgeInstances
                ));
                const result = {
                    source: children.filter(child => (
                        child.userData?.insertionRegionSourceBox
                        && !child.userData?.cellEdgeInstances
                    )).length,
                    wrapped: wrapped.length,
                };
                app.updateAddAtomsRegionPreview();
                return result;
            }""")
            assert full_period_box == {"source": 1, "wrapped": 0}
            region_picking = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const pickables = app.renderer.addAtomsRegionGroup.userData.pickables || [];
                const fills = app.renderer.addAtomsRegionGroup.children.filter(
                    child => child.userData?.addAtomsRegion && !child.userData?.cellEdgeInstances
                );
                return {
                    pickableCount: pickables.length,
                    edgeOnly: pickables.every(child => child.userData?.cellEdgeInstances === true),
                    fillCount: fills.length,
                    fillIsPickable: fills.some(fill => pickables.includes(fill)),
                };
            }""")
            assert region_picking["pickableCount"] >= 1
            assert region_picking["edgeOnly"] is True
            assert region_picking["fillCount"] >= 1
            assert region_picking["fillIsPickable"] is False

            first = page.locator("#add-atoms-entries .add-atoms-entry-row").first
            first.locator(".add-atoms-entry-label").fill("O_batch")
            assert first.locator(".add-atoms-entry-type").input_value() == "O"
            first.locator(".add-atoms-entry-type").select_option("Li")
            first.locator(".add-atoms-entry-label").fill("Li_mobile")
            first.locator(".add-atoms-entry-count").fill("8")
            page.click("#btn-add-atoms-entry")
            second = page.locator("#add-atoms-entries .add-atoms-entry-row").nth(1)
            second.locator(".add-atoms-entry-type").select_option("H")
            second.locator(".add-atoms-entry-label").fill("H_probe")
            second.locator(".add-atoms-entry-count").fill("1.5")
            page.fill("#add-atoms-seed", "2021")
            page.wait_for_function(
                "document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').length > 0"
            )
            page.click("#btn-add-atoms-scatter")
            page.wait_for_function(
                "document.getElementById('add-atoms-status-text')?.textContent?.includes('positive integers')"
            )
            assert page.evaluate("window.__ASE_APP__.state.atoms.positions.length") == len(host)
            assert sessions[editor.session_id].atom_addition is None
            second.locator(".add-atoms-entry-count").fill("5")
            page.click("#btn-add-atoms-scatter")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 16"
            )
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.new_count === 13"
            )
            assert page.locator("#add-atoms-mode-badge").is_visible()
            assert page.locator("#btn-add-atoms-finish").is_enabled()
            assert page.evaluate(
                "window.__ASE_APP__.state.selected.size"
            ) == 13
            assert page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.region_mode"
            ) == "regions"
            frozen_host_visual = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return [0, 1, 2].map(index => {
                    const mesh = renderer.atomMeshByIndex.get(index);
                    return {radius: mesh.scale.x, fixed: mesh.userData.fixed};
                });
            }""")
            assert [item["radius"] for item in frozen_host_visual] == pytest.approx(
                host_visual_radii,
                abs=1e-12,
            )
            assert all(item["fixed"] for item in frozen_host_visual)

            mic = page.locator("#add-atoms-mic")
            mic.set_checked(False)
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI.active.domain.pbc_aware === false"
            )
            assert sessions[editor.session_id].atom_addition.domain.pbc_aware is False
            mic.set_checked(True)
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI.active.domain.pbc_aware === true"
            )
            assert sessions[editor.session_id].atom_addition.domain.pbc_aware is True

            original_regions = page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.regions.map(region => ({id: region.id, bounds: [...region.bounds]}))"
            )
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.setAddAtomsRegionSelection(app.addAtomsUI.active.regions.map(region => region.id));
                app.renderer.domElement.focus();
            }""")
            page.keyboard.press("r")
            assert page.evaluate("window.__ASE_APP__.transform.mode") == "IDLE"
            page.keyboard.press("g")
            page.keyboard.press("x")
            page.keyboard.type("1")
            page.keyboard.press("Enter")
            page.wait_for_function(
                "regions => window.__ASE_APP__.addAtomsUI.active.regions.every((region, index) => Math.abs(region.bounds[0] - regions[index].bounds[0] - 1) < 1e-8)",
                arg=original_regions,
            )
            moved_regions = page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.regions.map(region => ({id: region.id, bounds: [...region.bounds]}))"
            )
            assert [region["id"] for region in moved_regions] == [
                region["id"] for region in original_regions
            ]
            for original, moved in zip(original_regions, moved_regions):
                assert moved["bounds"][:2] == pytest.approx(
                    [original["bounds"][0] + 1, original["bounds"][1] + 1]
                )
                assert moved["bounds"][2:] == pytest.approx(original["bounds"][2:])

            all_lower = np.asarray([
                min(region["bounds"][0] for region in moved_regions),
                min(region["bounds"][2] for region in moved_regions),
                min(region["bounds"][4] for region in moved_regions),
            ])
            all_upper = np.asarray([
                max(region["bounds"][1] for region in moved_regions),
                max(region["bounds"][3] for region in moved_regions),
                max(region["bounds"][5] for region in moved_regions),
            ])
            shared_pivot = 0.5 * (all_lower + all_upper)
            page.evaluate("window.__ASE_APP__.renderer.domElement.focus()")
            page.keyboard.press("s")
            page.keyboard.press("x")
            page.keyboard.type("2")
            page.keyboard.press("Enter")
            page.wait_for_function(
                "regions => window.__ASE_APP__.addAtomsUI.active.regions.every((region, index) => Math.abs(region.bounds[0] - regions[index].bounds[0]) > 1e-6)",
                arg=moved_regions,
            )
            scaled_regions = page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.regions.map(region => ({id: region.id, bounds: [...region.bounds]}))"
            )
            for moved, scaled in zip(moved_regions, scaled_regions):
                expected = list(moved["bounds"])
                expected[0] = shared_pivot[0] + 2 * (expected[0] - shared_pivot[0])
                expected[1] = shared_pivot[0] + 2 * (expected[1] - shared_pivot[0])
                assert scaled["bounds"] == pytest.approx(expected)
            assert [region.id for region in sessions[editor.session_id].atom_addition.regions] == [
                region["id"] for region in scaled_regions
            ]

            backend = sessions[editor.session_id]
            assert [repr(item) for item in backend.working_atoms.constraints] == [
                repr(item) for item in host.constraints
            ]
            assert_host_unchanged(host, backend.atom_addition.baseline_atoms)

            assert page.locator("#add-atoms-device").is_visible()
            assert page.locator("#add-atoms-cpus option").count() >= 1
            thread_value = "2" if page.locator('#add-atoms-cpus option[value="2"]').count() else "1"
            page.select_option("#add-atoms-device", "cpu")
            page.select_option("#add-atoms-cpus", thread_value)
            page.fill("#add-atoms-steps", "20")
            page.click("#btn-add-atoms-relax")
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.is_relaxing === true"
            )
            assert page.locator("#add-atoms-mic").is_disabled()
            assert page.locator("#add-atoms-device").is_disabled()
            assert backend.atom_addition.requested_device == "cpu"
            assert backend.atom_addition.cpu_threads == int(thread_value)
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.is_relaxing === false",
                timeout=20_000,
            )
            mode_timeline = page.evaluate("""() => ({
                active: window.__ASE_APP__.state.relaxTrajectory.active,
                kind: window.__ASE_APP__.state.relaxTrajectory.kind,
                frames: window.__ASE_APP__.state.relaxTrajectory.frames.length
            })""")
            assert mode_timeline["active"] is True
            assert mode_timeline["kind"] == "add-atoms"
            assert mode_timeline["frames"] >= 2
            assert_host_unchanged(host, backend.atom_addition.baseline_atoms)

            page.click("#btn-add-atoms-finish")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.metadata.atom_addition === null"
            )
            assert page.locator("#create-atom-widget").evaluate(
                "element => element.classList.contains('collapsed')"
            )
            collapsed_layout = page.locator("#create-atom-widget").bounding_box()
            assert collapsed_layout is not None
            assert collapsed_layout["x"] == pytest.approx(launcher_layout["left"], abs=1)
            assert collapsed_layout["y"] == pytest.approx(launcher_layout["top"], abs=1)
            assert page.evaluate(
                "window.__ASE_APP__.renderer.addAtomsRegionGroup.visible"
            ) is False
            assert page.evaluate("""() => ({
                active: window.__ASE_APP__.state.relaxTrajectory.active,
                kind: window.__ASE_APP__.state.relaxTrajectory.kind
            })""") == {"active": False, "kind": None}
            assert_host_unchanged(host, backend.working_atoms)
            assert len(backend.working_atoms) == len(host) + 13
            assert atom_labels(backend.working_atoms)[-13:] == ["Li_mobile"] * 8 + ["H_probe"] * 5
            browser.close()
    finally:
        editor.close()


def test_browser_scratch_relaxation_lifecycle_and_physical_scale():
    port = find_free_port()
    editor = view(
        Atoms(),
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1360, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 0")
            assert page.locator("[data-runtime-mode='edit']").get_attribute("aria-pressed") == "true"
            assert page.locator("#empty-workspace").is_visible()

            page.click("#btn-create-atom-toggle")
            page.click("#add-atoms-tab-batch")
            page.click("#btn-add-atoms-allow-region")
            assert page.locator("#empty-workspace").is_hidden()
            page.click("#btn-add-atoms-delete-region")
            assert page.locator("#empty-workspace").is_visible()
            page.click("#btn-create-atom-close")

            seed_positions = [
                [0.02 * (index % 5), 0.02 * ((index // 5) % 4), 0.02 * (index // 20)]
                for index in range(40)
            ]
            page.evaluate("""async positions => {
                const app = window.__ASE_APP__;
                const symbols = new Array(positions.length).fill('H');
                const data = await app.api.addAtoms(symbols, positions, symbols);
                app.setAtomsData(data, {clearSelection: true});
            }""", seed_positions)
            page.wait_for_function("window.__ASE_APP__.state.atoms.positions.length === 40")
            assert page.locator("#empty-workspace").is_hidden()
            assert page.evaluate("window.__ASE_APP__.state.atoms.metadata.has_calculator") is True
            assert page.evaluate("window.__ASE_APP__.state.atoms.cell.flat().every(value => value === 0)") is True
            assert page.locator("#distribution-panel-title").inner_text() == "Pair-distribution function"
            page.evaluate("document.getElementById('rdf-bins').value = '64'")
            page.evaluate("document.getElementById('btn-rdf-calculate').click()")
            page.wait_for_function(
                "window.__ASE_APP__.state.rdfResult?.analysis_kind === 'pair-distribution'",
                timeout=10_000,
            )
            page.wait_for_function(
                "document.getElementById('analysis-drawer-title')?.textContent === 'Pair-distribution function'",
                timeout=10_000,
            )
            finite_distribution = page.evaluate("""() => {
                const result = window.__ASE_APP__.state.rdfResult;
                const dr = result.cutoff / result.bins;
                return {
                    title: document.getElementById('analysis-drawer-title').textContent,
                    integral: result.total.reduce((sum, value) => sum + value, 0) * dr,
                };
            }""")
            assert finite_distribution["title"] == "Pair-distribution function"
            assert finite_distribution["integral"] == pytest.approx(1.0, abs=1e-10)
            page.evaluate("window.__ASE_APP__.closeAnalysisDrawer()")

            page.evaluate("""() => {
                document.getElementById('relax-fmax').value = '0.000001';
                document.getElementById('relax-steps').value = '5000';
            }""")
            page.evaluate("document.getElementById('btn-relax').click()")
            page.wait_for_function("window.__ASE_APP__.state.isRelaxing === true", timeout=10_000)
            page.evaluate("document.getElementById('btn-stop-relax').click()")
            page.wait_for_function("window.__ASE_APP__.state.isRelaxing === false", timeout=10_000)
            assert page.locator("#btn-relax").is_enabled()
            assert page.locator("#btn-stop-relax").is_disabled()

            page.evaluate("document.getElementById('relax-steps').value = '80'")
            page.evaluate("document.getElementById('btn-relax').click()")
            page.wait_for_function("""() => {
                const state = window.__ASE_APP__.state;
                return state.isRelaxing === true || (
                    state.relaxTrajectory?.kind === 'relaxation'
                    && state.relaxTrajectory?.finished === true
                    && state.relaxTrajectory?.frames?.length >= 2
                );
            }""", timeout=10_000)
            page.wait_for_function("""() => {
                const state = window.__ASE_APP__.state;
                return state.isRelaxing === false
                    && state.relaxTrajectory?.kind === 'relaxation'
                    && state.relaxTrajectory?.finished === true
                    && state.relaxTrajectory?.frames?.length >= 2;
            }""", timeout=20_000)
            relaxed = page.evaluate("window.__ASE_APP__.state.atoms.positions")
            assert np.max(np.linalg.norm(np.asarray(relaxed) - np.asarray(seed_positions), axis=1)) > 0.05

            page.evaluate("() => { void window.__ASE_APP__.exitRelaxationMode(); }")
            page.wait_for_selector("#relax-exit-restore")
            page.click("#relax-exit-restore")
            page.wait_for_function(
                "positions => window.__ASE_APP__.state.atoms.positions.every((point, index) => point.every((value, axis) => Math.abs(value - positions[index][axis]) < 1e-9))",
                arg=seed_positions,
            )
            assert page.locator("#btn-relax").is_enabled()
            assert page.locator("#btn-exit-relax-mode").is_hidden()

            before_scale = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection({update: false});
                app.state.atoms.positions.forEach((_, index) => app.addSelectionReference(index));
                app.updateSelectionVisuals();
                app.updateUI();
                app.renderer.domElement.focus();
                return {
                    positions: app.state.atoms.positions.map(point => [...point]),
                    radii: app.state.atoms.positions.map((_, index) => app.renderer.atomVisualRadius(index)),
                    cell: app.state.atoms.cell.map(row => [...row]),
                    bondThickness: app.state.display.bondThickness,
                };
            }""")
            pivot = np.asarray(before_scale["positions"], dtype=float).mean(axis=0)
            expected = np.asarray(before_scale["positions"], dtype=float)
            expected[:, 0] = pivot[0] + 1.5 * (expected[:, 0] - pivot[0])
            page.keyboard.press("s")
            page.keyboard.press("x")
            page.keyboard.type("1.5")
            page.keyboard.press("Enter")
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.wait_for_function(
                "target => window.__ASE_APP__.state.atoms.positions.every((point, index) => point.every((value, axis) => Math.abs(value - target[index][axis]) < 1e-8))",
                arg=expected.tolist(),
            )
            after_scale = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    positions: app.state.atoms.positions,
                    radii: app.state.atoms.positions.map((_, index) => app.renderer.atomVisualRadius(index)),
                    cell: app.state.atoms.cell,
                    bondThickness: app.state.display.bondThickness,
                };
            }""")
            np.testing.assert_allclose(after_scale["positions"], expected, atol=1e-8)
            np.testing.assert_allclose(after_scale["radii"], before_scale["radii"], atol=1e-12)
            np.testing.assert_allclose(after_scale["cell"], before_scale["cell"], atol=0)
            assert after_scale["bondThickness"] == before_scale["bondThickness"]

            cell = [[6.0, 0.0, 0.0], [1.5, 7.0, 0.0], [0.4, 0.8, 8.0]]
            page.evaluate("""async cell => {
                const app = window.__ASE_APP__;
                const data = await app.api.setUnitCell(cell, [true, true, false], false);
                app.setAtomsData(data, {clearSelection: false});
            }""", cell)
            page.wait_for_function("window.__ASE_APP__.hasUsableCell() === true")
            np.testing.assert_allclose(
                page.evaluate("window.__ASE_APP__.state.atoms.cell"),
                cell,
            )
            assert page.evaluate("window.__ASE_APP__.state.atoms.pbc") == [True, True, False]
            browser.close()
    finally:
        editor.close()


def test_browser_add_molecules_homogeneous_transform_rigid_relax_and_finish():
    host = make_host()
    port = find_free_port()
    editor = view(
        host,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            page.click("#btn-create-atom-toggle")
            page.click("#add-atoms-tab-batch")
            page.click("#add-atoms-content-molecules")
            page.wait_for_function(
                "document.querySelector('#add-molecule-entries select')?.options.length >= 150"
            )
            row = page.locator("#add-molecule-entries .add-molecule-entry-row").first
            row.locator(".add-molecule-entry-name").select_option("H2O")
            row.locator(".add-molecule-entry-label").fill("water")
            row.locator(".add-molecule-entry-count").fill("1")
            page.click("#add-molecules-quantity-density")
            page.fill("#add-molecules-target-density", "0.34")
            page.wait_for_function(
                "document.querySelector('#add-molecules-actual-density')?.textContent.includes('3 molecules')"
            )
            page.click("#add-atoms-placement-homogeneous")
            assert page.locator("#add-atoms-spacing-basis-row").is_visible()
            assert page.locator("#add-atoms-placement-pbc-row").is_visible()
            page.select_option("#add-atoms-coordinate-basis", "cartesian")
            page.fill("#add-atoms-seed", "991")
            assert page.locator("#add-molecules-random-orientation").is_checked()
            assert page.locator("#add-molecules-rigid").is_checked()
            assert page.locator("#add-atoms-select-added").is_checked()
            page.click("#btn-add-atoms-scatter")
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.molecule_count === 3"
            )
            assert page.evaluate("window.__ASE_APP__.state.selected.size") == 9
            assert page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.placement_mode"
            ) == "homogeneous"
            assert page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.coordinate_basis"
            ) == "cartesian"
            expected_density = (
                3
                * float(molecule("H2O").get_masses().sum())
                / (6.02214076e23 * abs(float(np.linalg.det(TRICLINIC_CELL))) * 1e-24)
            )
            assert page.evaluate(
                "window.__ASE_APP__.addAtomsUI.active.density.actual_g_cm3"
            ) == pytest.approx(expected_density, rel=1e-10)

            backend = sessions[editor.session_id]
            addition = backend.atom_addition
            before = backend.working_atoms.positions.copy()
            references = [
                np.linalg.norm(reference[:, None, :] - reference[None, :, :], axis=2)
                for reference in addition.molecule_references
            ]
            page.evaluate("window.__ASE_APP__.renderer.domElement.focus()")
            page.keyboard.press("r")
            page.keyboard.press("z")
            page.keyboard.type("30")
            page.keyboard.press("Enter")
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.wait_for_timeout(150)
            np.testing.assert_array_equal(backend.working_atoms.positions[:len(host)], host.positions)
            assert not np.allclose(backend.working_atoms.positions[len(host):], before[len(host):])

            page.keyboard.press("g")
            page.keyboard.press("x")
            page.keyboard.type("0.4")
            page.keyboard.press("Enter")
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.wait_for_timeout(150)
            np.testing.assert_array_equal(backend.working_atoms.positions[:len(host)], host.positions)

            page.fill("#add-atoms-steps", "12")
            page.click("#btn-add-atoms-relax")
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.is_relaxing === true"
            )
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.is_relaxing === false",
                timeout=20_000,
            )
            for group, expected in zip(addition.molecule_groups, references):
                current = backend.working_atoms.positions[group]
                distances = np.linalg.norm(current[:, None, :] - current[None, :, :], axis=2)
                np.testing.assert_allclose(distances, expected, atol=2e-8)

            page.click("#btn-add-atoms-finish")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.metadata.atom_addition === null"
            )
            assert page.locator("#create-atom-widget").evaluate(
                "element => element.classList.contains('collapsed')"
            )
            assert_host_unchanged(host, backend.working_atoms)
            groups = backend.working_atoms.arrays[MOLECULE_GROUP_ARRAY]
            assert set(groups[:len(host)]) == {-1}
            assert sorted(set(groups[len(host):])) == [0, 1, 2]
            browser.close()
    finally:
        editor.close()
