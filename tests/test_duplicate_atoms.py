import numpy as np
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, Hookean
from ase.calculators.singlepoint import SinglePointCalculator

from v_ase.io import ATOM_LABEL_ARRAY, set_atom_labels
from v_ase.server import duplicate_indices_in_atoms


def test_duplicate_preserves_exact_coordinates_arrays_labels_and_constraints():
    atoms = Atoms(
        "HOC",
        positions=[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [2.4, 0.0, 0.0]],
        cell=[8, 8, 8],
        pbc=True,
    )
    set_atom_labels(atoms, ["H_tip", "O_site", "C_bulk"])
    atoms.set_array("uncertainty", np.asarray([0.1, 0.2, 0.3]))
    atoms.set_tags([4, 5, 6])
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(indices=[1], direction=[0, 0, 1]),
        Hookean(0, 1, rt=1.5, k=2.0),
        Hookean(1, 2, rt=1.5, k=3.0),
        Hookean(1, [3.0, 2.0, 1.0], rt=0.4, k=4.0),
    ])
    source_forces = np.arange(9, dtype=float).reshape(3, 3) * 0.1
    atoms.calc = SinglePointCalculator(
        atoms,
        energy=-1.0,
        forces=source_forces,
        charges=np.asarray([-0.1, -0.2, 0.3]),
    )

    duplicated, new_indices = duplicate_indices_in_atoms(atoms, [0, 1])

    assert new_indices == [3, 4]
    np.testing.assert_allclose(duplicated.positions[3:], atoms.positions[:2])
    np.testing.assert_allclose(duplicated.arrays["uncertainty"], [0.1, 0.2, 0.3, 0.1, 0.2])
    np.testing.assert_array_equal(duplicated.get_tags(), [4, 5, 6, 4, 5])
    assert duplicated.arrays[ATOM_LABEL_ARRAY].tolist() == [
        "H_tip", "O_site", "C_bulk", "H_tip", "O_site"
    ]

    fixed = [constraint for constraint in duplicated.constraints if isinstance(constraint, FixAtoms)]
    assert len(fixed) == 2
    assert fixed[1].index.tolist() == [3]
    lines = [constraint for constraint in duplicated.constraints if isinstance(constraint, FixedLine)]
    assert len(lines) == 2
    assert lines[1].index.tolist() == [4]
    springs = [constraint for constraint in duplicated.constraints if isinstance(constraint, Hookean)]
    assert len(springs) == 5
    copied_pairs = [constraint for constraint in springs if constraint._type == "two atoms" and list(constraint.indices) == [3, 4]]
    assert len(copied_pairs) == 1
    copied_points = [constraint for constraint in springs if constraint._type == "point" and int(constraint.index) == 4]
    assert len(copied_points) == 1
    assert duplicated.calc is not None
    np.testing.assert_allclose(
        duplicated.calc.results["forces"],
        np.concatenate([source_forces, source_forces[:2]], axis=0),
    )
    np.testing.assert_allclose(
        duplicated.calc.results["charges"],
        [-0.1, -0.2, 0.3, -0.1, -0.2],
    )
    assert "energy" not in duplicated.calc.results
