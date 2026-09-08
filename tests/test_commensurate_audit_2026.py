"""Independent integer/affine oracles for the September 2026 science audit."""

from itertools import product
import math

import numpy as np
import pytest

from v_ase.commensurate import (
    _ORIENTED_BASIS_TRANSFORMS,
    _batch_lattice_match_kinematics,
    _hnf_matrices,
    _integer_supercell_lattice_points,
    find_commensurate_angles,
    find_lattice_matches,
    host_guest_supercell_geometry,
    row_rotation_matrix,
)


def hexagonal_cell():
    return np.array([[2.46, 0, 0], [1.23, math.sqrt(3) * 1.23, 0], [0, 0, 20.]])


@pytest.mark.parametrize("host_sign,guest_sign", [(1, -1), (-1, 1), (-1, -1)])
@pytest.mark.parametrize("strain_target", ["host", "guest"])
def test_left_handed_cells_match_without_reflecting_atoms(host_sign, guest_sign, strain_target):
    host = np.array([[3.1, .2, 0], [.8, 4.2, 0], [0, 0, 17.]])
    guest = host @ row_rotation_matrix([0, 0, 1], 31.7)
    host[1] *= host_sign
    guest[1] *= guest_sign
    candidates = find_lattice_matches(
        host, [1, 1, 0], guest, [1, 1, 0], max_area_ratio=1,
        strain_tolerance=1e-10, strain_target=strain_target,
    )["candidates"]
    assert candidates
    candidate = candidates[0]
    assert candidate["strain"] == pytest.approx(0, abs=1e-12)
    rotation = row_rotation_matrix([0, 0, 1], candidate["angle_deg"])
    for side, extra_rotation in (("host", np.eye(3)), ("guest", rotation)):
        deformation = np.asarray(candidate[f"{side}_deformation_matrix"])
        np.testing.assert_allclose(deformation, np.eye(3), atol=1e-10)
        assert np.linalg.det(deformation) > 0
        actual = np.asarray(candidate[f"{side}_supercell"]) @ extra_rotation @ deformation
        np.testing.assert_allclose(
            actual[candidate[f"{side}_periodic_axes"]],
            np.asarray(candidate["suggested_cell"])[candidate["host_periodic_axes"]], atol=1e-8,
        )


@pytest.mark.parametrize("reverse_plane", [False, True])
def test_same_lattice_twist_preserves_normal_with_oblique_vacuum(reverse_plane):
    cell = hexagonal_cell()
    cell[2] = [7, 5, 20]
    if reverse_plane:
        cell[1] *= -1
    candidates = find_commensurate_angles(cell, [1, 1, 0], "Z", max_index=2)["candidates"]
    candidate = min(candidates, key=lambda item: abs(item["angle_deg"] - 21.7867893))
    deformation = np.asarray(candidate["deformation_matrix"])
    np.testing.assert_allclose(deformation, np.eye(3), atol=1e-9)
    source = np.asarray(candidate["source_matrix_3d"]) @ cell
    rotation = row_rotation_matrix([0, 0, 1], candidate["angle_deg"])
    axes = candidate["periodic_axes"]
    np.testing.assert_allclose(
        (source @ rotation @ deformation)[axes],
        np.asarray(candidate["suggested_cell"])[axes], atol=1e-8,
    )


@pytest.mark.parametrize("side", [-1, 1])
@pytest.mark.parametrize("transpose", [False, True])
def test_small_strain_survives_a_gauss_reduction_shear_boundary(side, transpose):
    host = np.array([[1., 0, 0], [side * .499, 3, 0], [0, 0, 10.]])
    guest = host.copy()
    guest[1, 0] = side * .501
    if transpose:
        host[:2] = np.array([[0, 1], [-1, 0]]) @ host[:2]
        guest[:2] = np.array([[0, 1], [-1, 0]]) @ guest[:2]
    # Independent affine construction proves a <=0.034% strain match exists.
    direct = np.linalg.solve(guest[:2, :2], host[:2, :2])
    expected_strain = np.max(np.abs(np.linalg.svd(direct, compute_uv=False) - 1))
    result = find_lattice_matches(host, [1, 1, 0], guest, [1, 1, 0],
                                  max_area_ratio=1, strain_tolerance=.001)
    assert result["candidates"]
    assert result["candidates"][0]["strain"] == pytest.approx(expected_strain, abs=1e-12)


def test_equivalent_hexagonal_primitive_basis_keeps_the_high_area_analytic_series():
    cell = hexagonal_cell()
    cell[:2] = np.array([[3, 2], [-2, -1]]) @ cell[:2]
    result = find_commensurate_angles(cell, [1, 1, 0], "Z", max_index=32,
                                     strain_tolerance=1e-10)
    assert result["lattice_family"] == "hexagonal"
    assert result["exact_rotational_symmetry_deg"] == 60
    smallest = min(result["candidates"], key=lambda item: abs(item["angle_deg"]))
    assert abs(smallest["angle_deg"]) == pytest.approx(1.0501208798, abs=1e-8)
    assert smallest["area_ratio"] == 2977
    np.testing.assert_allclose(smallest["deformation_matrix"], np.eye(3), atol=1e-9)


@pytest.mark.parametrize("angle,index", [(90., 1), (36.86989764584402, 5)])
def test_square_coincidence_cells_remove_the_common_centering_factor(angle, index):
    result = find_commensurate_angles(np.diag([2., 2., 20.]), [1, 1, 0], "Z", max_index=4)
    candidate = min(result["candidates"], key=lambda item: abs(item["angle_deg"] - angle))
    assert candidate["angle_deg"] == pytest.approx(angle, abs=1e-8)
    assert candidate["area_ratio"] == index
    np.testing.assert_allclose(candidate["deformation_matrix"], np.eye(3), atol=1e-9)


def test_aligned_periodic_pair_is_preferred_to_larger_tilted_projection():
    cell = np.array([[3., 0, 0], [0, 3, 0], [10, 10, 20.]])
    result = find_lattice_matches(cell, [1, 1, 1], cell, [1, 1, 1], max_area_ratio=1)
    assert result["host_periodic_axes"] == result["guest_periodic_axes"] == [0, 1]
    assert result["candidates"][0]["strain"] == 0


def test_compression_and_expansion_cutoffs_follow_the_side_that_is_strained():
    host = np.diag([2., 2., 20.])
    guest = np.diag([2.2, 2.2, 20.])
    arguments = (host, [1, 1, 0], guest, [1, 1, 0])
    guest_result = find_lattice_matches(*arguments, max_area_ratio=1,
                                        strain_tolerance=.095, strain_target="guest")
    host_result = find_lattice_matches(*arguments, max_area_ratio=1,
                                       strain_tolerance=.095, strain_target="host")
    assert guest_result["candidates"][0]["strain"] == pytest.approx(1 - 1 / 1.1)
    assert host_result["candidates"] == []


def test_all_finite_orientations_agree_with_independent_svd_near_half_turn():
    generator = np.random.default_rng(20260908)
    host = generator.normal(size=(17, 2, 2)) + np.eye(2)[None] * 3
    guest = generator.normal(size=(17, 2, 2)) + np.eye(2)[None] * 3
    host[0] = row_rotation_matrix([0, 0, 1], -179.999)[:2, :2]
    guest[0] = np.eye(2)
    angles, guest_strains, host_strains = _batch_lattice_match_kinematics(host, guest)
    assert len(_ORIENTED_BASIS_TRANSFORMS) == 20
    assert angles[0, 0] == pytest.approx(-179.999, abs=1e-10)
    for variant, transform in enumerate(_ORIENTED_BASIS_TRANSFORMS):
        for pair, (h, g) in enumerate(zip(host, guest)):
            direct = np.linalg.solve(transform @ g, h)
            singular = np.linalg.svd(direct, compute_uv=False)
            assert guest_strains[variant, pair] == pytest.approx(max(abs(singular - 1)), abs=1e-11)
            assert host_strains[variant, pair] == pytest.approx(max(abs(1 / singular - 1)), abs=1e-11)
            left, _, right = np.linalg.svd((transform @ g).T @ h)
            if np.linalg.det(left @ right) < 0:
                left[:, -1] *= -1
            rotation = left @ right
            expected_angle = math.degrees(math.atan2(rotation[0, 1], rotation[0, 0]))
            angle_error = (angles[variant, pair] - expected_angle + 180) % 360 - 180
            assert abs(angle_error) < 1e-10


def quotient_fingerprint(matrix):
    """Classify a row lattice by exact membership in Z² modulo its index."""
    a, b, c, d = map(int, np.asarray(matrix).flat)
    index = abs(a * d - b * c)
    return tuple(
        (x, y) for x, y in product(range(index), repeat=2)
        if (x * d - y * c) % index == 0 and (-x * b + y * a) % index == 0
    )


def test_hnf_enumeration_covers_independently_classified_small_integer_lattices():
    for index in range(1, 5):
        actual = [quotient_fingerprint(matrix) for matrix in _hnf_matrices(index)]
        independent = {
            quotient_fingerprint(np.array(entries).reshape(2, 2))
            for entries in product(range(-4, 5), repeat=4)
            if abs(entries[0] * entries[3] - entries[1] * entries[2]) == index
        }
        assert len(actual) == len(set(actual))
        assert set(actual) == independent


@pytest.mark.parametrize("matrix", [
    [[2, 1, 0], [0, 3, 0], [0, 0, 1]],
    [[0, 2, 1], [1, 0, 1], [0, 1, 3]],
    [[-2, 1, 0], [1, 2, 1], [0, 1, 1]],
])
def test_integer_points_match_an_independent_half_open_cell_oracle(matrix):
    matrix = np.asarray(matrix)
    points = _integer_supercell_lattice_points(np.eye(3), matrix)
    # Exhaustively test a Cartesian bounding box only in this tiny oracle.
    vertices = np.asarray(list(product((0, 1), repeat=3))) @ matrix
    ranges = [range(int(low), int(high) + 1) for low, high in zip(vertices.min(0), vertices.max(0))]
    expected = []
    for point in product(*ranges):
        fractional = np.linalg.solve(matrix.T, point)
        if np.all(fractional >= -1e-10) and np.all(fractional < 1 - 1e-10):
            expected.append(point)
    assert points == sorted(expected)
    assert len(points) == abs(round(np.linalg.det(matrix)))


def test_large_shear_keeps_exact_atom_identity_without_a_large_bounding_box():
    matrix = np.array([[3, 3_000_001, 0], [0, 4, 0], [0, 0, 1]])
    points = _integer_supercell_lattice_points(np.diag([1., 2., 1e-10]), matrix)
    assert len(points) == len(set(points)) == 12
    fractions = np.asarray(points) @ np.linalg.inv(matrix)
    assert np.all(fractions >= -1e-9) and np.all(fractions < 1 - 1e-9)
    # Distinct primitive translations represent distinct periodic images.
    fingerprints = {tuple(np.rint(frac * 12).astype(int) % 12) for frac in fractions}
    assert len(fingerprints) == 12


@pytest.mark.parametrize("matrix", [np.zeros((3, 3)), np.full((3, 3), np.nan),
                                    np.diag([1., 1., 1.5])])
def test_invalid_integer_cells_fail_explicitly(matrix):
    with pytest.raises(ValueError, match="integer|non-singular"):
        _integer_supercell_lattice_points(np.eye(3), matrix)


def test_host_guest_preview_preserves_each_atom_identity_for_every_quotient():
    host = hexagonal_cell()
    guest = host * np.array([[2.504 / 2.46], [2.504 / 2.46], [1.]])
    result = find_lattice_matches(host, [1, 1, 0], guest, [1, 1, 0],
                                  max_area_ratio=7, strain_tolerance=.03)
    candidate = next(item for item in result["candidates"] if item["area_ratio"] == 7)
    geometry = host_guest_supercell_geometry(
        host_cell=host, host_positions=[[.1, .2, 0], [.6, .7, .1]],
        guest_cell=guest, guest_positions=[[.3, .4, 2]], candidate=candidate,
        padding_cells=0,
    )
    identities = list(zip(geometry["components"], geometry["atom_indices"],
                          map(tuple, geometry["lattice_indices"])))
    assert len(identities) == len(set(identities)) == 21
    for side, atom_count in (("host", 2), ("guest", 1)):
        for atom in range(atom_count):
            assert sum(component == side and index == atom
                       for component, index, _ in identities) == 7


@pytest.mark.parametrize("guest,pbc", [
    (np.full((3, 3), np.nan), [1, 1, 0]),
    (np.eye(3), [1, 1, 0, 0]),
])
def test_invalid_guest_geometry_fails_with_an_explicit_value_error(guest, pbc):
    with pytest.raises(ValueError, match="finite|PBC"):
        find_lattice_matches(np.eye(3), [1, 1, 0], guest, pbc)
