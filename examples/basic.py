from ase.build import molecule
from v_ase import view

atoms = molecule("H2O")

print("Launching v_ase...")
print("Controls:")
print(" - Left drag: box selection")
print(" - Middle drag: orbit")
print(" - G: move, R: rotate")
print(" - X/Y/Z: axis lock")

edited_atoms = view(atoms, viz_only=False)
print("Final positions:")
print(edited_atoms.positions)
