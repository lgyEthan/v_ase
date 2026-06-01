# API Reference

## `view` function

```python
from v_ase.visualize import view

edited_atoms = view(atoms)
```

`view_edit` remains available as an alias for existing examples.

## `view_edit` function

```python
def view_edit(
    atoms,
    *,
    notebook=False,
    block=True,
    port=None,
    show_cell=True,
    show_axes=True,
    show_bonds=False,
    respect_constraints=True,
    allow_relax=True,
    export=True,
    return_mode="atoms",
)
```

### Parameters
- **atoms**: An ASE `Atoms` object, a sequence of `Atoms` frames, or an ASE-readable trajectory file path.
- **notebook**: Set to `True` when using in Jupyter. Renders as an IFrame.
- **block**: If `True`, the function waits until the user clicks "Done" or "Cancel".
- **port**: Optional port for the local server.
- **respect_constraints**: If `True`, prevents moving atoms marked as fixed in ASE.
- **allow_relax**: Enables the "Relax" button if a calculator is attached.

## `view_file` function

```python
from v_ase import view_file

view_file("trajectory.extxyz")
view_file("calculation.traj")
```

`view_file` delegates to `ase.io.read(..., index=":")`, so any multi-frame
format supported by ASE can be opened in movie mode.

## `ASEEditor` class
Returned when `block=False`.

- **get_atoms()**: Returns a copy of the currently edited atoms.
- **get_positions()**: Returns the current positions.
- **close()**: Closes the session.
