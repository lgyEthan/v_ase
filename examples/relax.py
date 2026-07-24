from ase.build import molecule
from ase.calculators.emt import EMT
from v_ase import view

atoms = molecule("H2O")
atoms.calc = EMT()

print("Launching v_ase with Relax support...")
print("Use Relax in the Structure panel to optimize the geometry.")

edited_atoms = view(atoms, viz_only=False, allow_relax=True)
