from ase.build import molecule
from ase.calculators.emt import EMT
from v_ase import view_edit

atoms = molecule("H2O")
atoms.calc = EMT()

print("Launching v_ase with Relax support...")
print("Click the 'Relax' button in the side panel to optimize the geometry.")

edited_atoms = view_edit(atoms, allow_relax=True, block=True)
