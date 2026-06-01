from ase.build import molecule
from ase.constraints import FixAtoms
from v_ase import view_edit

atoms = molecule("C2H6")
# Fix the two Carbon atoms
atoms.set_constraint(FixAtoms(indices=[0, 1]))

print("Launching v_ase with constraints...")
print("Carbon atoms (indices 0, 1) should be fixed and cannot be moved.")

edited_atoms = view_edit(atoms, block=True)
