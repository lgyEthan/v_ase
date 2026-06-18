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
- **block**: If `True`, the function waits until the local session is finalized through the API. The visible top-bar Done/Cancel buttons are intentionally not shown to avoid accidental closure during editing.
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
v_ase gui POSCAR --interactive
```

`--format` is used when the filename is ambiguous. Common aliases include
`POSCAR`, `XDATCAR`, `vasprun.xml`, `lammpstrj`, `traj`, `xyz`, `extxyz`, and
`data`.

`v_ase gui FILE` opens in lightweight visualization mode by default. Use
`--interactive` when atom coordinate edits, deletion, copy/paste, constraints
editing, or interactive relaxation restart are needed.

LAMMPS dump/data integer types are preserved as raw GUI labels. Valid type ids
are interpreted as atomic numbers for default visualization; out-of-range ids
fall back to internal `H` while keeping the raw label.

## Calculator Behavior

Existing ASE calculators are preserved and used directly. In the default
lightweight visualization mode, v_ase does not attach a fallback calculator.
When `--interactive` is enabled and no calculator is attached, v_ase attaches
its default soft repulsion calculator. This default calculator can use torch CPU
or CUDA when torch is installed, but torch is not a package dependency; NumPy is
used automatically when torch is absent.

The same model can be loaded directly and used like any other ASE calculator:

```python
from v_ase.calculators import RepulsionCalculator

atoms.calc = RepulsionCalculator(device="cpu", cpu_threads=4)
energy = atoms.get_potential_energy()
forces = atoms.get_forces()
```

`from v_ase import RepulsionCalculator`, `from v_ase.calculator import
RepulsionCalculator`, and `from v_ase.repulsion import RepulsionCalculator` are
also supported. `Conditioner` is an alias for the same class.

The browser exposes `DEVICE` and `CPU` controls only for the default repulsion
calculator. These controls do not affect user-provided ASE calculators.

## Local Editing Endpoints

The browser UI talks to a local FastAPI server bound to `127.0.0.1`.

- `GET /api/atoms/{session_id}`: Fetches the current atoms state.
- `POST /api/apply/{session_id}`: Applies new coordinates through ASE constraint logic.
- `POST /api/constrain/{session_id}`: Previews constraint-corrected coordinates.
- `POST /api/add/{session_id}`: Appends atoms for paste operations.
- `POST /api/delete/{session_id}`: Deletes atoms and remaps constraints.
- `POST /api/constraints/{session_id}`: Applies or clears selected-atom `FixAtoms`, `FixedLine`, and `FixedPlane` constraints.
- `POST /api/calculator/{session_id}`: Updates default repulsion calculator device/thread settings.
- `POST /api/frame/{session_id}`: Switches the active trajectory frame.
- `POST /api/wrap/{session_id}`: Wraps atoms into the unit cell.
- `POST /api/export/poscar/{session_id}`: Exports POSCAR.
- `POST /api/export/pickle/{session_id}`: Exports pickle.
- `POST /api/export/blender/{session_id}`: Exports a Blender Python scene.
- `POST /api/relax/start/{session_id}`: Starts geometry optimization.
- `POST /api/relax/stop/{session_id}`: Requests geometry optimization stop.
- `WS /ws/{session_id}`: Streams relaxation positions, energy, and fmax. For
  blocking CLI sessions, a closed browser tab/window disconnects this socket;
  after a short reconnect grace period the backend finalizes the current
  working structure and releases the terminal.

## `ASEEditor` class
Returned when `block=False`.

- **get_atoms()**: Returns a copy of the currently edited atoms.
- **get_positions()**: Returns the current positions.
- **close()**: Closes the session.
