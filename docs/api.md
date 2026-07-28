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
    show_bonds=True,
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
- The browser's top-bar **View / Edit** switch can change this capability
  during the same session. Entering Edit materializes lazy trajectory frames
  before editing is enabled.
- `block=True` waits until the browser document closes or the local API
  finalizes the session.
- `block=False` returns an `ASEEditor` handle.
- `return_mode` is `atoms`, `positions`, or `none`.
- `respect_constraints=True` commits coordinates through ASE constraint logic.
- `close_on_disconnect=True` lets a closed browser document release a blocking
  Python or CLI call.
- `show_bonds=True` is the default; pass `False` for an atom-only initial view.

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

`view(..., open_browser=False)` suppresses automatic browser launch. With
`block=False`, inspect `ASEEditor.url`; with blocking CLI use, v_ase prints the
URL before waiting for the browser document to close. The server remains bound
to `127.0.0.1`. The CLI's `HOST:/path` form creates and manages the SSH
forwarding connection automatically; custom Python deployments remain
responsible for their own transport.

## CLI

```bash
v_ase gui
v_ase gui FILE
v_ase gui HOST:/REMOTE/FILE
v_ase gui FILE --interactive
v_ase gui FILE --for-ai
v_ase gui AMBIGUOUS --format FORMAT
v_ase gui FILE --no-browser
```

The default is View mode. `--interactive` starts in Edit mode. The top-bar
switch can change mode after startup without reopening the file.
`HOST:/REMOTE/FILE` is an scp-style remote target. The local v_ase process
starts the remote backend over SSH, selects both loopback endpoints, creates
the forwarding connection, opens the browser, and tears everything down after
the browser closes:

```bash
v_ase gui physics:/data/trajectory.lammpstrj
```

The file reader, ASE objects, session state, and scientific operations remain
on the remote host. The original file is never copied to the local computer.
Remote trajectories disable inline and whole-trajectory browser caches; frame
changes request only the needed frame through the encrypted tunnel.

`--no-browser` is still available for headless local sessions. `--stream-frames`
applies the same per-frame transfer policy to a local trajectory. `--port`
remains an advanced override for a predetermined local integration endpoint;
neither option is required for `HOST:/REMOTE/FILE`.

`--for-ai` suppresses automatic browser launch, prints one JSON handshake, and
keeps the session alive. Its semantic state and browser control schema avoid
pixel-based structure inspection; the reported `human_url` opens the same live
document for normal use.

The browser **Open** dialog can replace the active document, append selected
frames to its trajectory, or open an independent workspace tab. `.vase`
settings are restored for replace/new-tab operations and intentionally ignored
for trajectory append.

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

atoms.calc = RepulsionCalculator(
    device="cpu",
    cpu_threads=4,
    cutoff_scale=0.70,
    k_repulsion=1.0,
)
energy = atoms.get_potential_energy()
forces = atoms.get_forces()
```

Torch is optional. The calculator uses NumPy when torch is absent and can use
torch CPU or CUDA when available. Browser DEVICE/CPU controls apply only to
this built-in calculator. `cutoff_scale` multiplies its pair-distance
thresholds; `k_repulsion` scales the repulsive force. Both are editable under
**Structure > Relaxation** and persist with supported calculator state.

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
- structure load/append, frame switching, wrap, reset, history, copy/paste,
  add/delete;
- coordinate commit and constraint editing;
- calculator and relaxation control;
- POSCAR, ASE Pickle, lossless WebP/optimized PNG image support, video support,
  Blender, 3DM, and OBJ export;
- visual-settings and `.vase` save/load;
- binary current-frame and full-trajectory coordinate transfer.
- semantic AI schema, skill guide, and current-frame state.

Mutable structure requests and structure/CAD exports carry `frame_index`. The
server switches to that frame before applying browser coordinates or producing
output, preventing a fast scrub from leaking the previous frame's cell,
constraints, or coordinates into the operation.

Canonical atom identity update:

```text
POST /api/atom-identity/{session_id}
```

Uploaded structures are appended without replacing visual state through:

```text
POST /api/file/append/{session_id}
```

Large compatible trajectories expose contiguous float32 coordinates through:

```text
GET /api/trajectory/positions/{session_id}
GET /api/frame/positions/{session_id}/{frame}
```

Trajectory displacement analysis is available through:

```text
POST /api/analysis/displacement/{session_id}
```

The payload selects the current/reference frames and MIC policy. Common unique
particle-ID arrays are preferred; equal-size frames fall back to atom index.
Different-size frames without IDs return a physical-mapping error.

Agent discovery and semantic state are available through:

```text
GET /api/ai/schema
GET /api/ai/skill
GET /api/ai/state/{session_id}
```

Image encoding is available through:

```text
POST /api/export/image/{session_id}?format=webp
POST /api/export/image/{session_id}?format=png
```

The endpoint accepts the exact browser-rendered PNG bytes. WebP conversion is
lossless; PNG conversion is a lossless IDAT recompression. Both responses keep
the original pixel dimensions and RGBA values.

The live browser exposes `window.v_aseAI.ready()`, `capabilities()`,
`describe()`, `apply()`, `render()`, and `export()`. `apply()` covers frame and
mode changes, quality, display and camera state, selection, constrained
transforms, identity and constraint edits, wrapping, translation, atom
creation/deletion, supercells, history, reset, relaxation, and displacement
analysis. `export()` covers image, video, POSCAR, ASE Pickle, Blender, Rhino
3DM, OBJ, `.vase`, and visual settings. Rendering and image export use the same
capture path as the human Export workspace.

WebSockets stream relaxation updates and own browser-document/workspace
lifetime. Closing the last connected browser document finalizes blocking calls
after a short reconnect grace period.
