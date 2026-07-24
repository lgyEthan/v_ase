from ase.build import molecule
from ase.calculators.emt import EMT
from ase.constraints import FixAtoms
from v_ase import view


def run_pro_demo():
    atoms = molecule("H2O")
    atoms.calc = EMT()
    atoms.set_constraint(FixAtoms(indices=[0]))

    print("Launching v_ase...")
    print("Try the following:")
    print("  1. Press 'G', then 'X', then type '1.5' to move hydrogen.")
    print("  2. Select atoms and run Relax to inspect the EMT trajectory.")
    print("  3. Drag a selection box with Left Mouse.")
    print("  4. Close the browser document to return the edited Atoms object.")

    edited_atoms = view(atoms, viz_only=False)
    print("\nStructure returned successfully.")
    print(f"Final oxygen position: {edited_atoms.positions[0]}")


if __name__ == "__main__":
    run_pro_demo()
