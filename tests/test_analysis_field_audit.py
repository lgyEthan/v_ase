"""Independent geometry and analysis oracles for scalar fields and pair counts."""

from itertools import product

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.calculator import Calculator

from v_ase.analysis import calculate_rdf
from v_ase.atom_scalars import atom_property_snapshot, atom_scalar_catalog, atom_scalar_values
from v_ase.io import set_atom_labels
from v_ase.volumetric import (
    VolumetricData,
    combine_volumetric_datasets,
    generate_isosurface,
    generate_volumetric_plane,
)


@pytest.mark.parametrize("endpoint_inclusive", [False, True])
@pytest.mark.parametrize("axis", [0, 1, 2])
def test_periodic_plane_interpolates_the_closing_interval(endpoint_inclusive, axis):
    line = np.array([0., 1., 0., -1.])
    if endpoint_inclusive:
        line = np.append(line, line[0])
    view_shape = [1, 1, 1]
    view_shape[axis] = len(line)
    shape = [5, 5, 5]
    shape[axis] = len(line)
    values = np.broadcast_to(line.reshape(view_shape), shape).copy()
    cell = np.array([[2., 0., 0.], [.4, 3., 0.], [.2, .3, 4.]])
    origin = np.array([1.2, -.4, 2.3])
    pbc = np.zeros(3, dtype=bool)
    pbc[axis] = True
    dataset = VolumetricData(
        "closing interval", values, cell, origin=origin, pbc=pbc,
        endpoint_inclusive=endpoint_inclusive, precision="fp64",
    )
    before = dataset.summary()
    hkl = np.eye(3)[axis]
    normal_length = np.linalg.norm(np.linalg.solve(cell, hkl))
    plane = generate_volumetric_plane(
        dataset, hkl, .875 / normal_length, resolution=32,
    )
    # 0.875 is halfway from the sample -1 at 0.75 to the closing 0 at 1.
    np.testing.assert_allclose(plane.values, -.5, atol=2e-6)
    assert plane.minimum == pytest.approx(-.5, abs=2e-6)
    assert plane.maximum == pytest.approx(-.5, abs=2e-6)
    np.testing.assert_array_equal(dataset.values, values)
    assert dataset.summary() == before


def test_oblique_mixed_boundary_plane_matches_separable_linear_interpolation():
    shape = (4, 5, 6)
    lines = [np.array([0., 1., 0., -1.]), np.array([1., 0., -1., 0., 2.]), np.arange(6.)]
    values = lines[0][:, None, None] + 2 * lines[1][None, :, None] + 3 * lines[2][None, None, :]
    cell = np.array([[2., 0., 0.], [.7, 3., 0.], [.5, .4, 4.]])
    origin = np.array([1.2, -.4, 2.3])
    dataset = VolumetricData("separable", values, cell, origin=origin, pbc=[True, True, False], precision="fp64")
    plane = generate_volumetric_plane(dataset, [1, 1, 1], 3., repetitions=[2, 3, 1], resolution=80)

    # Recover raster Cartesian positions from the public polygon and texture
    # coordinates, independently of the sampler's reciprocal-basis construction.
    transform = np.linalg.lstsq(
        np.column_stack([plane.polygon_uv, np.ones(len(plane.polygon_uv))]),
        plane.polygon_vertices, rcond=None,
    )[0]
    u, v = np.meshgrid(np.linspace(0, 1, plane.width), np.linspace(0, 1, plane.height))
    points = np.stack([u, v, np.ones_like(u)], axis=-1) @ transform
    fractional = (points - origin) @ np.linalg.inv(cell)
    expected = np.zeros(u.shape)
    for axis, samples in enumerate(lines):
        component = np.mod(fractional[..., axis], 1.) if axis < 2 else np.clip(fractional[..., axis], 0., 1.)
        if axis < 2:
            knots = np.arange(shape[axis] + 1) / shape[axis]
            samples = np.append(samples, samples[0])
        else:
            knots = np.arange(shape[axis]) / shape[axis]
        expected += (axis + 1) * np.interp(component, knots, samples)
    np.testing.assert_allclose(plane.values, expected, atol=2e-5)


@pytest.mark.parametrize("translation", [0., 1e6, -1e6])
def test_combination_rejects_shifted_origins_independent_of_translation(translation):
    datasets = [
        VolumetricData(str(shift), np.ones((2, 2, 2)), np.eye(3), origin=[translation + shift, 0, 0])
        for shift in (0., .1)
    ]
    with pytest.raises(ValueError, match="same origin"):
        combine_volumetric_datasets(datasets, [1, -1])


def test_combination_keeps_absolute_origin_serialization_tolerance():
    datasets = [
        VolumetricData(str(shift), np.ones((2, 2, 2)), np.eye(3), origin=[shift, 0, 0])
        for shift in (0., 5e-7)
    ]
    result = combine_volumetric_datasets(datasets, [1, -1])
    np.testing.assert_array_equal(result.values, 0.)


@pytest.mark.parametrize("baseline", [0., 1e8, -1e8])
@pytest.mark.parametrize("step", [1, 2, 4])
def test_fp64_isosurface_of_affine_field_is_invariant_to_scalar_baseline(baseline, step):
    values = baseline + np.broadcast_to(np.linspace(0, 1, 11)[:, None, None], (11, 7, 9))
    cell = np.array([[2., .2, .1], [.7, 3., 0.], [.5, .4, 4.]])
    origin = np.array([1.2, -.4, 2.3])
    dataset = VolumetricData(
        "affine", values, cell, origin=origin, pbc=False,
        endpoint_inclusive=True, precision="fp64",
    )
    before = dataset.summary()
    mesh = generate_isosurface(dataset, baseline + .55, step_size=step, smoothing_iterations=0)
    fractional = (mesh.vertices - origin) @ np.linalg.inv(cell)
    np.testing.assert_allclose(fractional[:, 0], .55, atol=4e-7)
    np.testing.assert_allclose(fractional[:, 1:].min(axis=0), [0, 0], atol=4e-7)
    np.testing.assert_allclose(fractional[:, 1:].max(axis=0), [1, 1], atol=4e-7)
    np.testing.assert_array_equal(dataset.values, values)
    assert dataset.summary() == before


def test_mesh_smoothing_keeps_finite_exclusive_grid_boundary_vertices_fixed():
    x, y, _z = np.meshgrid(*[np.arange(8) / 8 for _ in range(3)], indexing="ij")
    dataset = VolumetricData("finite", x + y, np.eye(3), pbc=False)
    raw = generate_isosurface(dataset, 1., smoothing_iterations=0)
    smooth = generate_isosurface(dataset, 1., smoothing_iterations=6)
    boundary = np.any(np.isclose(raw.vertices, 0.) | np.isclose(raw.vertices, 7 / 8), axis=1)
    np.testing.assert_array_equal(smooth.vertices[boundary], raw.vertices[boundary])
    assert smooth.metadata["fixed_boundary_vertices"] == int(np.count_nonzero(boundary))


@pytest.mark.parametrize("step", [1, 2, 4])
def test_coarse_periodic_surface_retains_the_final_cell_interval(step):
    samples = np.sin(2 * np.pi * np.arange(10) / 10)
    values = np.broadcast_to(samples[:, None, None], (10, 8, 8)).copy()
    dataset = VolumetricData("periodic", values, np.eye(3))
    mesh = generate_isosurface(dataset, -.15, step_size=step, smoothing_iterations=0)
    crossings = np.unique(mesh.vertices[:, 0])
    assert len(crossings) == 2
    # Independently interpolate each sign-changing interval between the chosen
    # samples. Coarse detail preserves endpoints, not unsampled fine features.
    indices = sorted(set(range(0, 11, step)) | {10})
    closed = np.append(samples, samples[0])
    expected = []
    for left, right in zip(indices, indices[1:]):
        if (closed[left] + .15) * (closed[right] + .15) < 0:
            expected.append((left + (right - left) * (-.15 - closed[left]) / (closed[right] - closed[left])) / 10)
    np.testing.assert_allclose(crossings, expected, atol=1e-7)
    assert mesh.vertices[:, 1:].max() == pytest.approx(1.)


@pytest.mark.parametrize("name, shape, natoms", [
    ("stress", (6,), 6), ("stress", (3, 3), 3), ("dipole", (3,), 3),
    ("polarization", (3,), 3), ("dielectric_tensor", (3, 3), 3),
    ("eigenvalues", (2, 3, 4), 2),
])
def test_known_global_calculator_results_are_never_presented_as_per_atom(name, shape, natoms):
    class StoredOnlyCalculator(Calculator):
        def calculate(self, *args, **kwargs):
            pytest.fail("Atom scalar inspection must not evaluate a calculator")

    atoms = Atoms("H" * natoms)
    atoms.new_array(name, np.arange(natoms, dtype=float))
    atoms.calc = StoredOnlyCalculator()
    atoms.calc.results = {
        name: np.arange(np.prod(shape), dtype=float).reshape(shape),
        "charges": np.arange(natoms, dtype=float),
        "stresses": np.ones((natoms, 6)),
        "custom_score": np.full(natoms, .25),
    }
    catalog = atom_scalar_catalog(atoms)
    assert not any(item["source"] == "result" and item["name"] == name for item in catalog)
    assert {"charges", "stresses", "custom_score"} <= {item["name"] for item in catalog if item["source"] == "result"}
    snapshot = atom_property_snapshot(atoms, 0)
    assert not any(item["source"] == "calculator" and item["name"] == name for item in snapshot)
    assert any(item["source"] == "array" and item["name"] == name for item in snapshot)
    with pytest.raises(ValueError, match="not available"):
        atom_scalar_values(atoms, f"result::{name}::norm")
    np.testing.assert_array_equal(atom_scalar_values(atoms, "result::charges::scalar"), np.arange(natoms))


def test_triclinic_finite_grid_integrates_multiaffine_field_exactly():
    x, y, z = np.meshgrid(*[np.linspace(0, 1, n) for n in (4, 7, 9)], indexing="ij")
    cell = np.array([[2., 0., 0.], [.8, 3., 0.], [.5, .4, 4.]])
    dataset = VolumetricData("multiaffine", (1 + 2*x) * (2-y) * (1+z), cell, pbc=False, endpoint_inclusive=True, precision="fp64")
    # The three analytic one-dimensional integrals are 2, 1.5, and 1.5.
    assert dataset.integral == pytest.approx(2 * 1.5 * 1.5 * 24, abs=1e-12)


def test_skew_rdf_matches_reciprocal_bounded_explicit_image_enumeration():
    cell = np.array([[2., 0., 0.], [1.95, .2, 0.], [.3, .1, 1.5]])
    atoms = Atoms("HHe", scaled_positions=[[.1, .2, .3], [.7, .65, .3]], cell=cell, pbc=True)
    set_atom_labels(atoms, ["B", "A"])
    cutoff = .47
    inverse = np.linalg.inv(cell)
    fractional = atoms.positions @ inverse
    radius_bounds = cutoff * np.linalg.norm(inverse, axis=0)
    distances = []
    for i, j in product(range(len(atoms)), repeat=2):
        delta = fractional[j] - fractional[i]
        bounds = [range(int(np.ceil(-radius_bounds[k] - delta[k])), int(np.floor(radius_bounds[k] - delta[k])) + 1) for k in range(3)]
        for shift in product(*bounds):
            if i == j and shift == (0, 0, 0):
                continue
            distance = np.linalg.norm(atoms.positions[j] - atoms.positions[i] + np.asarray(shift) @ cell)
            if distance <= cutoff:
                distances.append(distance)
    assert len(distances) == 16
    result = calculate_rdf(atoms, cutoff=cutoff, bins=23, pair_mode="all")
    edges = np.linspace(0, cutoff, 24)
    expected = np.histogram(distances, bins=edges)[0] / (len(atoms)**2 / atoms.get_volume() * 4*np.pi/3 * np.diff(edges**3))
    np.testing.assert_allclose(result.total, expected, atol=1e-12)
    np.testing.assert_allclose(result.total, .25*result.partial["A|A"] + .25*result.partial["B|B"] + .5*result.partial["A|B"], atol=1e-12)


@pytest.mark.parametrize("periodic", [False, True])
@pytest.mark.parametrize("mode", ["none", "active", "selected"])
def test_total_distribution_is_independent_of_distinct_site_labels(periodic, mode):
    rng = np.random.default_rng(103)
    atoms = Atoms("Ar200", scaled_positions=rng.random((200, 3)), cell=[20]*3, pbc=periodic)
    reference = calculate_rdf(atoms, cutoff=3., bins=100, pair_mode=mode)
    set_atom_labels(atoms, [f"site_{i}" for i in range(len(atoms))])
    distinct = calculate_rdf(atoms, cutoff=3., bins=100, pair_mode=mode)
    np.testing.assert_array_equal(distinct.total, reference.total)
    assert distinct.partial == reference.partial == {}
