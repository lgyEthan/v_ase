"""Independent geometrical and energy-gradient checks for insertion."""
import itertools

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule
from scipy.optimize import LinearConstraint, minimize

from v_ase.add_atoms import AdditionRepulsionCalculator, _InsertionDistanceMetric
from v_ase.insertion_regions import build_insertion_domain
from v_ase.repulsion import RepulsionCalculator
from v_ase.neighbors import find_mic


def _finite_difference_forces(atoms, h=1e-6):
    original = atoms.positions.copy()
    result = np.empty_like(original)
    for i, axis in itertools.product(range(len(atoms)), range(3)):
        atoms.positions[:] = original
        atoms.positions[i, axis] += h
        above = atoms.get_potential_energy()
        atoms.positions[i, axis] -= 2 * h
        below = atoms.get_potential_energy()
        result[i, axis] = -(above - below) / (2 * h)
    atoms.positions[:] = original
    return result


def test_cartesian_partial_pbc_metric_ignores_nonperiodic_lattice_tilt():
    cell = np.array([[3., 0, 0], [2., 1, 0], [8., 4., 1.]])
    points = np.array([[0., 0, 2.2], [.7, -.3, 10.], [1.2, .8, -.7]])
    shifts = np.array(list(itertools.product(range(-8, 9), range(-8, 9), [0]))) @ cell
    expected = np.min(np.sum((points[:, None, :] + shifts[None, :, :]) ** 2, axis=2), axis=1)
    metric = _InsertionDistanceMetric(cell, [True, True, False], 'cartesian', True)
    np.testing.assert_allclose(metric.squared(points, np.zeros(3)), expected, atol=1e-12)
    np.testing.assert_allclose(find_mic(points, cell, [True, True, False])[1]**2, expected, atol=1e-12)
    # A huge finite axis must not hide skew periodic vectors behind a global
    # Gram-matrix orthogonality tolerance.
    tall_cell = cell.copy()
    tall_cell[2] = [8., 4., 1e9]
    tall_metric = _InsertionDistanceMetric(tall_cell, [True, True, False], 'cartesian', True)
    np.testing.assert_allclose(tall_metric.squared(points, np.zeros(3)), expected, atol=1e-12)


def test_shared_mic_has_no_unreduced_short_vector_shortcut_and_is_rotation_invariant():
    cell = np.array([[4., 0, 0], [3.8, 1, 0], [.2, .1, 3.]])
    point = np.array([-.49557537, .44776208, .34318780]) @ cell
    shifts = np.array(list(itertools.product(range(-4, 5), repeat=3))) @ cell
    images = point + shifts
    expected = images[np.argmin(np.sum(images * images, axis=1))]
    actual, distance = find_mic(point, cell)
    np.testing.assert_allclose(actual, expected, atol=1e-12)
    assert distance == pytest.approx(np.linalg.norm(expected))
    rotation, _ = np.linalg.qr(np.random.default_rng(79).normal(size=(3, 3)))
    rotated, _ = find_mic(point @ rotation, cell @ rotation)
    np.testing.assert_allclose(rotated, expected @ rotation, atol=1e-12)


@pytest.mark.parametrize('fixed_index', [0, -1])
def test_rigid_atomwise_constraint_conflict_rejects_start_without_mutation(fixed_index):
    from ase.constraints import FixAtoms
    from v_ase.add_atoms import start_atom_addition, start_atom_addition_relaxation
    from v_ase.session import EditorSession
    atoms = Atoms(cell=[8.] * 3, pbc=True)
    session = EditorSession('rigid-constraint-audit', atoms.copy(), atoms.copy())
    start_atom_addition(session, {
        'content_kind': 'molecules', 'molecules': [{'name': 'H2O', 'count': 1}],
        'rigid_molecules': True, 'seed': 19,
    })
    session.working_atoms.set_constraint(FixAtoms(indices=[fixed_index]))
    before = session.working_atoms.positions.copy()
    history = len(session.history)
    with pytest.raises(ValueError, match='atomwise constraints'):
        start_atom_addition_relaxation(session, {'steps': 1})
    np.testing.assert_array_equal(session.working_atoms.positions, before)
    assert len(session.history) == history
    assert session.atom_addition.status == 'scattered'
    assert not session.atom_addition.is_relaxing


def test_reject_box_leaves_atoms_outside_any_of_its_slabs_unpenalized():
    atoms = Atoms('He2', positions=[[.2, 2., 2.], [.2, .3, .4]])
    atoms.calc = RepulsionCalculator(region=[0, 1] * 3, set_region_as_prohibited=True,
                                     k_repulsion=0, backend='numpy')
    assert atoms.get_potential_energy() == pytest.approx(.5 * .2**2)
    np.testing.assert_allclose(atoms.get_forces(), [[0, 0, 0], [-.2, 0, 0]])
    np.testing.assert_allclose(atoms.get_forces(), _finite_difference_forces(atoms), atol=2e-10)


def test_skew_cell_confinement_uses_euclidean_normal_and_conservative_force():
    cell = np.array([[4., 0, 0], [2., 3., 0], [0, 0, 4.]])
    point = np.array([-.3, 1., 1.])
    domain = build_insertion_domain(cell=cell, pbc=[False] * 3, regions=[])
    normal = np.array([3., -2., 0]) / np.sqrt(13)
    delta = -(point @ normal) * normal
    np.testing.assert_allclose(domain.displacements_to_domain([point]), [delta], atol=1e-10)
    atoms = Atoms('He', positions=[point], cell=cell)
    atoms.calc = AdditionRepulsionCalculator(insertion_domain=domain, k_repulsion=0, backend='numpy')
    np.testing.assert_allclose(atoms.get_forces(), [delta], atol=1e-10)
    np.testing.assert_allclose(atoms.get_forces(), _finite_difference_forces(atoms), atol=2e-9)


def test_overlapping_rejects_project_to_the_nearest_joint_boundary():
    domain = build_insertion_domain(cell=np.diag([10.] * 3), pbc=[False] * 3, regions=[
        {'id': 'a', 'role': 'reject', 'bounds': [2, 6, 2, 6, 0, 10]},
        {'id': 'b', 'role': 'reject', 'bounds': [4, 8, 4, 8, 0, 10]},
    ])
    point = np.array([5.2, 5., 5.])
    np.testing.assert_allclose(domain.displacements_to_domain([point]), [[.8, -1., 0]], atol=1e-10)
    assert domain.contains(domain.project_points([point]))[0]
    atoms = Atoms('He', positions=[point], cell=domain.cell)
    atoms.calc = AdditionRepulsionCalculator(insertion_domain=domain, k_repulsion=0, backend='numpy')
    np.testing.assert_allclose(atoms.get_forces(), _finite_difference_forces(atoms), atol=2e-9)


def test_skew_box_intersection_projection_matches_independent_constrained_minimizer():
    cell = np.array([[4., 0, 0], [2., 3., 0], [.5, .4, 4.]])
    lower, upper = np.array([1., .8, .5]), np.array([5., 2.8, 3.5])
    bounds = np.column_stack((lower, upper)).reshape(-1).tolist()
    domain = build_insertion_domain(cell=cell, pbc=[False] * 3, regions=[
        {'id': 'clip', 'role': 'allow', 'bounds': bounds},
    ])
    for point in np.random.default_rng(701).uniform(-2., 8., size=(24, 3)):
        result = minimize(
            lambda x: .5 * np.sum((x - point)**2), np.mean([lower, upper], axis=0),
            jac=lambda x: x - point, method='SLSQP', bounds=list(zip(lower, upper)),
            constraints=[LinearConstraint(np.linalg.inv(cell).T, 0., 1.)],
            options={'ftol': 1e-12, 'maxiter': 100},
        )
        assert result.success, result.message
        projected = point + domain.displacements_to_domain([point])[0]
        np.testing.assert_allclose(projected, result.x, atol=2e-8)


def test_partial_periodic_domain_is_a_slab_independent_of_finite_vector_tilt():
    cell = np.array([[3., 0, 0], [2., 1., 0], [8., 4., 1.]])
    domain = build_insertion_domain(cell=cell, pbc=[True, True, False], regions=[], pbc_aware=True)
    points = np.array([[0., 0, 2.2], [1., 2., -.4]])
    expected = np.array([[0., 0, -1.2], [0., 0, .4]])
    np.testing.assert_allclose(domain.displacements_to_domain(points), expected, atol=2e-10)
    np.testing.assert_allclose(domain.displacements_to_domain(points + 3*cell[1]), expected, atol=2e-10)
    assert np.all(domain.contains(domain.project_points(points)))


def test_periodic_repulsion_matches_explicit_image_sum_and_energy_derivatives():
    cell = np.array([[2.4, 0, 0], [1.8, 2, 0], [.3, .4, 3.]])
    atoms = Atoms('H3', positions=[[.1, .2, .3], [1.2, .5, .8], [-.2, 1.4, 1.1]],
                  cell=cell, pbc=[True, True, False])
    atoms.calc = RepulsionCalculator(cutoff_distance=2.7, k_repulsion=1.3, backend='numpy')
    energy, forces = 0., np.zeros((3, 3))
    shifts = list(itertools.product(range(-3, 4), range(-3, 4), [0]))
    for i, j, shift in itertools.product(range(3), range(3), shifts):
        if i == j and shift == (0, 0, 0):
            continue
        delta = atoms.positions[j] - atoms.positions[i] + np.array(shift) @ cell
        distance = np.linalg.norm(delta)
        if distance < 2.7:
            energy += .25 * 1.3 * (2.7-distance)**2
            pair_force = .5 * 1.3 * (2.7-distance) * delta / distance
            forces[i] -= pair_force
            forces[j] += pair_force
    assert atoms.get_potential_energy() == pytest.approx(energy)
    np.testing.assert_allclose(atoms.get_forces(), forces, atol=3e-12)
    np.testing.assert_allclose(atoms.get_forces(), _finite_difference_forces(atoms), atol=4e-9)


@pytest.mark.parametrize('cell', [
    np.diag([1., 5., 5.]), np.diag([1., 0., 0.]),
    [[1., 0., 0.], [2., 0., 0.], [3., 0., 0.]],
])
def test_missing_exact_overlap_is_restored_even_when_other_pair_images_exist(monkeypatch, cell):
    import v_ase.repulsion as module
    atoms = Atoms('H2', positions=[[0., 0., 2.], [1., 0., 2.]],
                  cell=cell, pbc=[True, False, False])
    atoms.calc = RepulsionCalculator(cutoff_distance=1.2, backend='numpy')
    expected_energy, expected_forces = atoms.get_potential_energy(), atoms.get_forces().copy()
    original = module.primitive_neighbour_list
    def omit_zero_distance(*args, **kwargs):
        i, j, vectors, distances = original(*args, **kwargs)
        keep = distances > 1e-12
        return i[keep], j[keep], vectors[keep], distances[keep]
    monkeypatch.setattr(module, 'primitive_neighbour_list', omit_zero_distance)
    atoms.calc.reset()
    assert atoms.get_potential_energy() == pytest.approx(expected_energy)
    np.testing.assert_allclose(atoms.get_forces(), expected_forces, atol=1e-12)


def test_rigid_native_origin_confinement_has_the_energy_rotation_derivative():
    atoms = molecule('H2O')
    reference = atoms.positions.copy()
    atoms.translate([-1., 2., 2.])
    atoms.calc = AdditionRepulsionCalculator(region=[0, 10, None, None, None, None],
        rigid_groups=[[0, 1, 2]], rigid_references=[reference], k_repulsion=0, backend='numpy')
    forces = atoms.get_forces()
    relative = atoms.positions - atoms.positions.mean(axis=0)
    torque = np.cross(relative, forces).sum(axis=0)
    original = atoms.positions.copy()
    angle = 1e-6
    energies = []
    for theta in (angle, -angle):
        rotation = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0],
                             [-np.sin(theta), 0, np.cos(theta)]])
        atoms.positions[:] = relative @ rotation.T + original.mean(axis=0)
        energies.append(atoms.get_potential_energy())
    atoms.positions[:] = original
    assert torque[1] == pytest.approx(-(energies[0] - energies[1]) / (2 * angle), abs=2e-10)
    np.testing.assert_allclose(forces, _finite_difference_forces(atoms), atol=2e-9)


def test_published_confinement_positions_energy_and_forces_describe_same_state(monkeypatch):
    import v_ase.add_atoms as module
    from v_ase.session import EditorSession
    cell = np.array([[4., 0, 0], [2., 3., 0], [0, 0, 4.]])
    empty = Atoms(cell=cell, pbc=False)
    session = EditorSession('confinement-report-audit', empty.copy(), empty.copy())
    module.start_atom_addition(session, {'element': 'He', 'count': 1, 'seed': 19,
                                       'constrain_to_domain': True})
    addition = session.atom_addition
    temporary = session.working_atoms.copy()
    temporary.positions[:] = [[-.3, 1., 1.]]
    temporary.calc = AdditionRepulsionCalculator(insertion_domain=addition.domain,
                                                k_repulsion=0, backend='numpy')
    messages = []
    monkeypatch.setattr(module.ws_manager, 'broadcast_sync', lambda message, *_: messages.append(message))
    module._publish_addition_positions(
        session, addition, temporary, step=0, max_steps=1,
        run_id=addition.run_id,
    )
    message = messages[-1]
    np.testing.assert_allclose(message['positions'], session.working_atoms.positions)
    assert addition.domain.contains(message['positions'])[0]
    assert message['energy'] == pytest.approx(0., abs=1e-18)
    assert message['fmax'] == pytest.approx(0., abs=1e-10)


def test_placement_converging_on_last_allowed_fire_step_reports_converged(monkeypatch):
    import v_ase.add_atoms as module
    from v_ase.session import EditorSession
    empty = Atoms(cell=[8.] * 3, pbc=False)
    session = EditorSession('final-step-convergence-audit', empty.copy(), empty.copy())
    module.start_atom_addition(session, {'element': 'H', 'count': 2, 'seed': 19})
    session.working_atoms.positions[:] = [[.4, .5, 2.], [1.2, .5, 2.]]
    messages = []
    monkeypatch.setattr(module.ws_manager, 'broadcast_sync', lambda message, *_: messages.append(message))
    module._run_addition_relaxation(
        session, session.atom_addition, run_id=session.atom_addition.run_id,
        fmax=.399, steps=1, pair_cutoffs={'H-H': 1.}, cutoff_mode='absolute',
        cutoff_distance=1., cutoff_scale=1., k_repulsion=2., k_boundary=1.,
        mic=False, device='cpu', cpu_threads=1,
    )
    final = messages[-1]
    assert final['type'] == 'add_atoms_relax_finished'
    assert final['step'] == 1
    assert final['status'] == 'converged'
    steps = [item for item in messages if item['type'] == 'add_atoms_relax_step']
    assert steps[0]['fmax'] > .399
    assert steps[-1]['fmax'] < .399


def test_huge_disjoint_periodic_region_skips_enumeration_and_large_ranges_reject_transactionally(monkeypatch):
    import v_ase.insertion_regions as regions_module
    from v_ase.add_atoms import start_atom_addition
    from v_ase.session import EditorSession
    original_product = regions_module.itertools.product
    def guarded_product(*args, **kwargs):
        assert all(not isinstance(arg, range) or arg.stop - arg.start <= 4096 for arg in args), \
            'Huge periodic ranges must be rejected before image enumeration.'
        return original_product(*args, **kwargs)
    monkeypatch.setattr(regions_module.itertools, 'product', guarded_product)
    distant = {'id': 'distant', 'role': 'reject', 'bounds': [-1e12, 1e12, 2, 3, 0, 1]}
    domain = build_insertion_domain(cell=np.eye(3), pbc=[True, False, False],
                                    regions=[distant], pbc_aware=True)
    assert domain.images == ()
    assert domain.volume == pytest.approx(1.)
    atoms = Atoms('He', positions=[[.2, .2, .2]], cell=np.eye(3), pbc=[True, False, False])
    session = EditorSession('bounded-region-audit', atoms.copy(), atoms.copy())
    before = session.working_atoms.positions.copy()
    history = len(session.history)
    with pytest.raises(ValueError, match='candidate periodic images'):
        start_atom_addition(session, {
            'element': 'H', 'count': 1, 'region_mic': True,
            'regions': [{'id': 'wide', 'role': 'reject', 'bounds': [-1e12, 1e12, 0, .5, 0, 1]}],
        })
    np.testing.assert_array_equal(session.working_atoms.positions, before)
    assert len(session.history) == history
    assert session.atom_addition is None


def test_full_cell_region_coverage_eliminates_redundant_periodic_images(monkeypatch):
    import v_ase.insertion_regions as module
    cell = np.array([[1., .123, .071], [.127, 1., .139], [.111, .117, 1.]])
    original_product = module.itertools.product
    def no_periodic_enumeration(*args, **kwargs):
        assert not any(isinstance(arg, range) for arg in args), \
            'A box covering the full cell needs no translated-image enumeration.'
        return original_product(*args, **kwargs)
    monkeypatch.setattr(module.itertools, 'product', no_periodic_enumeration)
    domain = build_insertion_domain(cell=cell, pbc=[True] * 3, regions=[
        {'id': 'cover', 'role': 'allow', 'bounds': [-6, 6] * 3},
    ])
    assert len(domain.images) == 1
    assert domain.volume == pytest.approx(abs(np.linalg.det(cell)), rel=1e-12)
    points, _ = domain.random_points(128, seed=19)
    assert np.all(domain.contains(points))
    with pytest.raises(ValueError, match='no accessible insertion volume'):
        build_insertion_domain(cell=cell, pbc=[True] * 3, regions=[
            {'id': 'cover', 'role': 'reject', 'bounds': [-6, 6] * 3},
        ])


def test_boolean_partition_limit_precedes_large_allocations_and_staging(monkeypatch):
    import math
    import v_ase.insertion_regions as module
    from v_ase.add_atoms import start_atom_addition
    from v_ase.session import EditorSession
    atoms = Atoms('He', positions=[[.2, .2, .2]], cell=np.eye(3), pbc=False)
    session = EditorSession('partition-limit-audit', atoms.copy(), atoms.copy())
    before, history = session.working_atoms.positions.copy(), len(session.history)
    # 32 separate boxes create 65 intervals along each axis (274,625 cells).
    # This nonempty domain exceeds the Cartesian partition work cap.
    regions = [
        {'id': str(i), 'role': 'allow', 'bounds': [(2*i+1)/66, (2*i+2)/66] * 3}
        for i in range(32)
    ]
    for name in ('zeros', 'ones'):
        original = getattr(module.np, name)
        def guarded_allocation(shape, *args, _original=original, **kwargs):
            if isinstance(shape, tuple) and len(shape) == 3:
                assert math.prod(shape) <= module.MAX_INSERTION_PARTITION_CELLS, \
                    'The partition work cap must precede mask/corner allocation.'
            return _original(shape, *args, **kwargs)
        monkeypatch.setattr(module.np, name, guarded_allocation)
    with pytest.raises(ValueError, match='250,000 Boolean partition cells'):
        start_atom_addition(session, {'element': 'H', 'count': 1, 'regions': regions})
    np.testing.assert_array_equal(session.working_atoms.positions, before)
    assert len(session.history) == history
    assert session.atom_addition is None
