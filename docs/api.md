# Public API

## Python

### `view`

```python
from v_ase.visualize import view

viewer_result = view(
    atoms_or_frames,
    *,
    notebook=False,
    block=True,
    port=None,
    show_cell=True,
    show_axes=True,
    show_bonds=False,
    respect_constraints=True,
    allow_relax=True,
    viz_only=True,
    theme="auto",
    return_mode="atoms",
    close_on_disconnect=True,
)
```

Accepted input:

- one ASE `Atoms`;
- a sequence of `Atoms` frames;
- a supported structure, trajectory, or `.vase` path.

Important options:

- `viz_only=True` uses the lightweight viewer and does not attach the fallback
  calculator.
- `viz_only=False` enables atom editing, constraints editing, history,
  copy/paste, deletion, creation, and relaxation.
- `block=True` waits until the browser document closes or the local API
  finalizes the session.
- `block=False` returns an `ASEEditor` handle.
- `return_mode` is `atoms`, `positions`, or `none`.
- `respect_constraints=True` commits coordinates through ASE constraint logic.
- `close_on_disconnect=True` lets a closed browser document release a blocking
  Python or CLI call.

The caller's input object is copied and is never mutated.

### Compatibility Alias

```python
from v_ase import view_edit

edited = view_edit(atoms)
```

`view_edit()` is retained for compatibility and is equivalent to
`view(atoms, viz_only=False, ...)`. New code should use `view()`.

### `view_file`

```python
from v_ase import view_file

view_file("trajectory.extxyz")
view_file("saved_project.vase")
```

`view_file()` forwards to `view()` and uses the canonical v_ase input pipeline.
Supported large numeric LAMMPS dumps receive the virtual, byte-indexed
trajectory path automatically.

### `ASEEditor`

Returned by `view(..., block=False)`.

```python
editor.url
editor.get_atoms()
editor.get_positions()
editor.set_atoms(atoms)
editor.export_poscar("POSCAR")
editor.export_pickle("atoms.pkl")
editor.close()
```

`get_atoms()` returns a detached copy. `close()` releases the session,
temporary files, workspace documents, and the managed local server when it is
the final owner.

## CLI

```bash
v_ase gui
v_ase gui FILE
v_ase gui FILE --interactive
v_ase gui AMBIGUOUS --format FORMAT
```

The default is visualization mode. `--interactive` enables structural editing.

Common format aliases:

| Alias | Reader |
| --- | --- |
| `POSCAR`, `CONTCAR`, `vasp` | VASP structure |
| `XDATCAR` | VASP trajectory |
| `vasprun.xml`, `vasp-xml` | VASP XML |
| `lammpstrj` | LAMMPS text dump |
| `data` | LAMMPS data |
| `xyz`, `extxyz` | XYZ/extended XYZ |
| `traj` | ASE trajectory |
| `vase` | v_ase project |

`--index :` loads all frames, `--index -1` loads the last frame, and an integer
loads one frame.

LAMMPS integer types remain distinct GUI labels. Valid integer values are used
as atomic numbers for initial element defaults; invalid values use internal
hydrogen while preserving the raw label. Custom extxyz labels such as
`H_type5` are mapped to ASE-valid chemical symbols without losing the label.

## Calculator

User-supplied ASE calculators are preserved. Interactive mode attaches the
built-in soft repulsion calculator only when the input has no calculator.
Visualization mode does not attach it.

```python
from v_ase.calculators import RepulsionCalculator

atoms.calc = RepulsionCalculator(device="cpu", cpu_threads=4)
energy = atoms.get_potential_energy()
forces = atoms.get_forces()
```

Torch is optional. The calculator uses NumPy when torch is absent and can use
torch CPU or CUDA when available. Browser DEVICE/CPU controls apply only to
this built-in calculator.

Compatibility imports remain available from `v_ase`, `v_ase.calculator`, and
`v_ase.repulsion`. `Conditioner` is an alias for the same class.

## Save Formats

### ASE Pickle

Current-frame Python interchange. It retains:

- coordinates, chemical symbols, labels, cell, and PBC;
- ASE constraints and portable arrays;
- valid cached `SinglePointCalculator` results.

It excludes visual settings, other trajectory frames, and arbitrary executable
calculator implementations.

### Visual Settings JSON

Reusable presentation preset containing:

- label appearance and visibility;
- bond configuration;
- camera, projection, and atomic scale;
- lighting, quality, and overlays;
- supercell preview.

Coordinates are never included. Loading reconciles label-specific values with
the new structure, ignores absent labels, and creates defaults for new labels
and pairs.

### `.vase`

Self-contained project archive containing:

- all trajectory frames and the active frame;
- edited coordinates, cells/PBC, constraints, labels, safe arrays, and metadata;
- cached standard calculator results and supported built-in calculator config;
- complete visual settings.

The archive is ZIP-based, validated before extraction, and does not unpickle
executable Python objects.

## Local Application API

The browser communicates only with a FastAPI server bound to `127.0.0.1`.
Endpoint groups:

- session and workspace lifecycle;
- structure load, frame switching, wrap, reset, history, copy/paste, add/delete;
- coordinate commit and constraint editing;
- calculator and relaxation control;
- POSCAR, ASE Pickle, image/video support, Blender, 3DM, and OBJ export;
- visual-settings and `.vase` save/load;
- binary current-frame and full-trajectory coordinate transfer.

Canonical atom identity update:

```text
POST /api/atom-identity/{session_id}
```

Large compatible trajectories expose contiguous float32 coordinates through:

```text
GET /api/trajectory/positions/{session_id}
GET /api/frame/positions/{session_id}/{frame}
```

WebSockets stream relaxation updates and own browser-document/workspace
lifetime. Closing the last connected browser document finalizes blocking calls
after a short reconnect grace period.
