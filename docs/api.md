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

## Command Line

```bash
v_ase gui FILE
v_ase FILE
v_ase gui ABCD --format POSCAR
v_ase gui ABCD --format lammpstrj
v_ase gui ABCD --format data
v_ase gui movie.extxyz --viz-only
```

`--format` is used when the filename is ambiguous. Common aliases include
`POSCAR`, `XDATCAR`, `vasprun.xml`, `lammpstrj`, `traj`, `xyz`, `extxyz`, and
`data`.

LAMMPS dump/data integer types are preserved as raw GUI labels. Valid type ids
are interpreted as atomic numbers for default visualization; out-of-range ids
fall back to internal `H` while keeping the raw label.

## Local Editing Endpoints

The browser UI talks to a local FastAPI server bound to `127.0.0.1`.

- `GET /api/atoms/{session_id}`: Fetches the current atoms state.
- `POST /api/apply/{session_id}`: Applies new coordinates through ASE constraint logic.
- `POST /api/constrain/{session_id}`: Previews constraint-corrected coordinates.
- `POST /api/add/{session_id}`: Appends atoms for paste operations.
- `POST /api/delete/{session_id}`: Deletes atoms and remaps constraints.
- `POST /api/frame/{session_id}`: Switches the active trajectory frame.
- `POST /api/wrap/{session_id}`: Wraps atoms into the unit cell.
- `POST /api/export/poscar/{session_id}`: Exports POSCAR.
- `POST /api/export/pickle/{session_id}`: Exports pickle.
- `POST /api/export/blender/{session_id}`: Exports a Blender Python scene.
- `POST /api/relax/start/{session_id}`: Starts geometry optimization.
- `POST /api/relax/stop/{session_id}`: Requests geometry optimization stop.
- `WS /ws/{session_id}`: Streams relaxation positions, energy, and fmax.

## `ASEEditor` class
Returned when `block=False`.

- **get_atoms()**: Returns a copy of the currently edited atoms.
- **get_positions()**: Returns the current positions.
- **close()**: Closes the session.
