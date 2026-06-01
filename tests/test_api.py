import pytest
import numpy as np
import threading
import time
from ase.build import molecule
from ase.calculators.emt import EMT
from v_ase import view
from v_ase.session import EditorSession

def test_view_return_logic_done():
    """Verify that Done returns the edited Atoms object and respects blocking."""
    atoms = molecule("H2O")
    atoms0 = atoms.copy()
    
    # We simulate a background process that triggers the 'Done' event
    session_id = None
    
    def simulate_user_action():
        time.sleep(2)
        from v_ase.session import sessions
        # Find the active session
        for sid, sess in sessions.items():
            # Simulate structural change
            new_pos = sess.working_atoms.get_positions()
            new_pos[0] += 0.5
            sess.working_atoms.set_positions(new_pos)
            sess.result_atoms = sess.working_atoms.copy()
            sess.done_event.set()

    thread = threading.Thread(target=simulate_user_action)
    thread.start()

    # Launch viewer (blocking)
    edited = view(atoms, block=True)
    
    # Assertions
    assert edited is not atoms, "Should return a copy, not the original"
    assert not np.allclose(edited.positions, atoms0.positions), "Positions should be changed"
    assert np.allclose(atoms.positions, atoms0.positions), "Original atoms should NOT be mutated"

def test_view_return_logic_cancel():
    """Verify that Cancel returns the original Atoms object."""
    atoms = molecule("H2O")
    atoms0 = atoms.copy()
    
    def simulate_cancel():
        time.sleep(1)
        from v_ase.server import sessions
        for sid, sess in sessions.items():
            sess.cancelled = True
            sess.done_event.set()

    threading.Thread(target=simulate_cancel).start()
    
    edited = view(atoms, block=True)
    
    assert np.allclose(edited.positions, atoms0.positions), "Should return original positions on cancel"

def test_calculator_preservation():
    """Verify calculator survives structural edits."""
    atoms = molecule("H2O")
    atoms.calc = EMT()

    original = atoms.copy()
    original.calc = atoms.calc
    working = atoms.copy()
    working.calc = atoms.calc

    sess = EditorSession("test", original, working)
    assert sess.working_atoms.calc is not None
    
    # Simulate structural addition
    from ase import Atom
    new_atoms = sess.working_atoms.copy()
    new_atoms.append(Atom("H", position=[0,0,0]))
    sess.preserve_calculator(new_atoms)
    
    assert sess.working_atoms.calc is not None, "Calculator should be preserved after append"
    assert len(sess.working_atoms) == 4
