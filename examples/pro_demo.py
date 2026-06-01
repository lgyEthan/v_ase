from ase.build import molecule
from ase.calculators.emt import EMT
from ase.constraints import FixAtoms
from v_ase import view

def run_pro_demo():
    # 1. Create structure
    atoms = molecule("H2O")
    
    # 2. Setup Physics
    atoms.calc = EMT()
    atoms.set_constraint(FixAtoms(indices=[0])) # Fix Oxygen
    
    print("Launching v_ase...")
    print("Try the following:")
    print("  1. Press 'G' then 'X' then type '1.5' to move hydrogen.")
    print("  2. Select atoms and click 'RELAX' to see EMT trajectory.")
    print("  3. Drag a selection box with Left Mouse.")
    print("  4. Press 'Done' to return the edited Atoms object.")
    
    # 3. Launch Editor (blocking mode)
    edited_atoms = view(atoms, block=True)
    
    if edited_atoms:
        print("\nStructure returned successfully!")
        print(f"Final Oxygen position: {edited_atoms.positions[0]}")
    else:
        print("\nCancelled.")

if __name__ == "__main__":
    run_pro_demo()
