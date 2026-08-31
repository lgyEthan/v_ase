# Python API

The primary Python API accepts ASE objects, sequences of frames, and supported
paths. It copies caller-owned data before creating a document.

## `view()`

```python
from v_ase.visualize import view

result = view(
    atoms_or_frames_or_path,
    notebook=None,
    block=True,
    port=None,
    show_cell=True,
    show_axes=True,
    show_bonds=True,
    respect_constraints=True,
    allow_relax=True,
    viz_only=True,
    theme="auto",
    return_mode="atoms",
    trajectory_source=None,
    initial_frame=0,
    initial_design_settings=None,
    document_name=None,
    close_on_disconnect=True,
    open_browser=True,
    stream_trajectory=False,
    volumetric_datasets=None,
    volumetric_precision="fp32",
)
```

The same public objects are lazily available from `v_ase`:

```python
from v_ase import ASEEditor, view, view_edit, view_file
```

### Accepted input

`atoms_or_frames_or_path` can be:

- one `ase.Atoms`;
- a sequence of compatible `Atoms` frames;
- a structure or trajectory path;
- a `.vase` or project-embedded HTML path; or
- a supported volumetric path.

The original `Atoms` and frame sequence are never mutated. Returned objects are
detached copies of current document state.

### Session and mode arguments

| Argument | Meaning |
| --- | --- |
| `viz_only=True` | Start in lightweight View mode without the fallback calculator |
| `viz_only=False` | Start in Edit with topology/history/constraint/relaxation workflows |
| `block=True` | Wait until browser finalization and return according to `return_mode` |
| `block=False` | Return an `ASEEditor` immediately |
| `close_on_disconnect=True` | Final browser-page close can finalize the session |
| `open_browser=False` | Do not invoke the OS browser launcher; use the handle/printed URL |
| `port=None` | Select a free loopback port automatically |

The top-bar View/Edit switch can change capability after launch. Entering Edit
can materialize a lazy trajectory before enabling mutation.

### Display arguments

`show_cell`, `show_axes`, and `show_bonds` select initial visibility. Explicit
project or visual-settings state can override generic defaults when restored.

`theme="auto"` and `"system"` follow the browser/OS preference. `"light"` and
`"dark"` request an explicit initial interface theme unless that browser has a
persisted user choice.

### Constraint and relaxation arguments

`respect_constraints=True` commits positions through ASE constraint logic. It
does not remove constraints when false; it only disables enforcement for the
relevant commits. `allow_relax` controls availability of relaxation workflows.

### Return modes

With `block=True`:

- `return_mode="atoms"` returns a detached `Atoms`;
- `return_mode="positions"` returns the final Cartesian array;
- `return_mode="none"` returns `None`.

An invalid value raises `ValueError` after session finalization.

### Trajectory and volumetric arguments

`initial_frame` selects the first displayed frame. `stream_trajectory=True`
requests per-frame browser transfer rather than a complete inline coordinate
cache. Normal users should pass a file path and let v_ase select its indexed or
streaming source; `trajectory_source` is the advanced hook for an already
constructed source object.

For volumetric paths, `volumetric_precision` is `"fp32"` (default) or
`"fp64"`. `volumetric_datasets` accepts already constructed v_ase datasets for
advanced embedding. `initial_design_settings` and `document_name` provide an
initial visual state and tab label.

## Blocking edit example

```python
from ase.build import molecule
from v_ase import view

source = molecule("H2O")
edited = view(source, viz_only=False)

assert edited is not source
print(edited.positions)
```

Closing the document finalizes the call. Cancel returns the original document
copy; normal finalization returns the current working structure.

## Non-blocking `ASEEditor`

```python
from ase.build import bulk
from v_ase import view

editor = view(bulk("Cu"), block=False, open_browser=False)
print(editor.url)

current = editor.get_atoms()
positions = editor.get_positions()

editor.export_poscar("POSCAR")
editor.export_pickle("atoms.pkl")
editor.close()
```

Public members:

| Member | Behavior |
| --- | --- |
| `url` | Full workspace/document loopback URL |
| `notebook_url` | Inline view endpoint for rich display |
| `get_atoms()` | Detached current `Atoms`, or `None` after close |
| `get_positions()` | Detached current Cartesian coordinates |
| `set_atoms(atoms)` | Replace working atoms and add history in the live session |
| `export_poscar(path)` | Write the current structure as VASP POSCAR |
| `export_pickle(path)` | Write safe current ASE interchange data |
| `close()` | Release document, workspace, temporary resources, and final server owner |

Call `close()` when a non-blocking handle no longer needs its session. It is
idempotent.

## File convenience API

```python
from v_ase import view_file

view_file("trajectory.extxyz")
view_file("project.vase")
```

`view_file()` forwards to `view()` and uses the same canonical input pipeline.

## Compatibility edit alias

```python
from v_ase import view_edit

edited = view_edit(atoms)
```

`view_edit()` is retained for existing code and is equivalent to
`view(atoms, viz_only=False, ...)`. New code should use `view()` so the mode is
explicit alongside the other arguments.

## Notebook display

Inside Jupyter, `notebook=None` follows the process-local `%v_ase` preference
and active-kernel detection. See [Notebooks and remote systems](notebooks-remote.md)
for inline/browser examples and lifecycle details.

## Labels

Use the canonical helper instead of accessing the storage array directly:

```python
from v_ase.io import atom_labels, set_atom_labels

labels = atom_labels(atoms)
set_atom_labels(atoms, ["Cu_surface", "O_adsorbate", ...])
```

The archive-compatible array name is `v_ase_atom_type`, but helper functions
validate length and keep the LABEL/ASE TYPE distinction clear.

## Repulsion calculator exports

```python
from v_ase.calculators import RepulsionCalculator
```

`RepulsionCalculator`, `DefaultRepulsionCalculator`, `Conditioner`, and
`VAseRepulsionCalculator` are compatibility names for the v_ase overlap-
repulsion implementation. It is intended for resolving short contacts and
interactive conditioning, not as a predictive chemical potential.

For the underlying local HTTP routes and calculator configuration details, see
[Public API](api.md).
