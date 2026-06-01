import pytest
from ase.build import molecule
from v_ase import view
import numpy as np

def test_view_import():
    from v_ase import view
    assert callable(view)

def test_atoms_copy():
    atoms = molecule("H2O")
    # We can't easily test blocking UI in CI, but we can test the session logic
    from v_ase.server import sessions, EditorSession
    import uuid
    
    session_id = str(uuid.uuid4())
    session = EditorSession(session_id, atoms.copy(), atoms.copy())
    assert session.original_atoms is not session.working_atoms
    assert len(session.original_atoms) == 3
