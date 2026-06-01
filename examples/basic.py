from ase.build import molecule
from v_ase import view_edit

# Create a simple water molecule
atoms = molecule("H2O")

print("Launching v_ase...")
print("Controls:")
print(" - Left Drag: Selection")
print(" - Middle Drag: Orbit")
print(" - G: Grab, R: Rotate")
print(" - X/Y/Z: Axis Locking")
print(" - Numeric input followed by Enter works during G/R")

edited_atoms = view_edit(atoms, block=True)

if edited_atoms:
    print("Editing finished.")
    print("New positions:")
    print(edited_atoms.positions)
else:
    print("Editing cancelled.")
