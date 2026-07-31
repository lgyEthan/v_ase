# Public API

## Python

### `view`

```python
from v_ase.visualize import view

viewer_result = view(
    atoms_or_frames,
    *,
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
    close_on_disconnect=True,
)
```

Accepted input:

- one ASE `Atoms`;
- a sequence of `Atoms` frames;
- a supported structure, trajectory, or `.vase` path.

Important options:

- `notebook=None` follows the process-local `%v_ase` display preference, then
  detects an active Jupyter kernel when that preference is `auto`. Use
  `%v_ase inline`, `%v_ase browser`, or `%v_ase auto` to switch subsequent
  `view()` calls without restarting the kernel. Pass `True` / `"inline"` or
  `False` / `"browser"` to override the preference for one call. Inline mode
  returns a view-only iframe below the cell; browser mode opens the complete
  external interface. Call `display(editor)` explicitly after assigning an
  inline handle.
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
- `close_on_disconnect=False` keeps the API session and its local server alive
  across workspace-tab disconnects until the session is finalized explicitly.
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
v_ase gui FILE --cli
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

`--cli` is a terminal-oriented local API mode, not an embedded AI model. An
automation agent invokes it itself. It suppresses automatic browser launch,
prints one JSON handshake as the first stdout line, then streams committed
workspace changes as NDJSON. Its semantic state and browser control schema
avoid pixel-based structure inspection; the reported `human_url` opens the
same live document for normal use and human refinement.

The CLI does not accept natural language or commands from stdin. Its first
stdout line is discovery metadata, later stdout lines are
`v_ase.collaboration.v1` events, and status is written to stderr. The
controlling external agent opens `human_url` and sends structured HTTP JSON
through `command_url`, normally with `v_ase api`. The handshake explicitly
reports `command_transport="http-json-bridge"`,
`accepts_natural_language=false`, and `stdin_commands=false`, plus
`events_url`, `event_protocol`, `event_delivery`, and `event_scope`.

```bash
v_ase api "$COMMAND_URL" describe --params '{"includePositions":false}'
v_ase api "$COMMAND_URL" apply --params-file command.json
v_ase api "$COMMAND_URL" render --params-file render.json --save figure.png
```

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
- display supercell and absolute Cartesian/fractional visual translation.

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

### Standalone HTML View

One view-only browser document containing:

- inlined Three.js, renderer code, styles, scene data, and trajectory frames;
- the saved camera, display, bonds, constraints, analysis overlays,
  supercell, and visual translation;
- optionally, the complete validated `.vase` archive as Base64 metadata.

It opens from `file://` without a server or network request and supports only
camera navigation and trajectory playback. `embed_project` defaults to
`false` for a smaller view-only handoff. Set it to `true` for a downloadable
`.vase` and lossless reopening through `v_ase gui FILE.html`. The human
**HTML Project** action enables project embedding by default.

HTML, image, and video share the same Preview Area camera crop and aspect
ratio. HTML dimensions are inherited from Preview Area and are not exposed as
a second independent resolution control. HTML defaults to grid off, axes on,
and unit cell on. An optimized high-resolution copy of the exact rendered
frame is embedded so macOS Finder/Quick Look can display only the structure
frame without executing JavaScript. In a browser, the full-frame poster and
the adaptive device-pixel-ratio WebGL canvas occupy the same integer-sized
rectangle; the first completed live frame automatically cross-fades over the
poster before camera input begins, without moving or resizing the scene.
View-only controls appear after activity and do not occupy layout space.

The generated project tag uses bounded Base64 decoding and the extracted ZIP
passes the same path, schema, size, and integrity checks as a direct `.vase`
file. HTML is larger than `.vase` because browser-ready scene data and runtime
code are included; project embedding adds the Base64 archive.

## Local Application API

The browser communicates only with a FastAPI server bound to `127.0.0.1`.
Endpoint groups:

- session and workspace lifecycle;
- structure load/append, frame switching, wrap, reset, history, copy/paste,
  add/delete;
- coordinate commit and constraint editing;
- calculator and relaxation control;
- POSCAR, ASE Pickle, lossless WebP/optimized PNG image support, video support,
  Blender, 3DM, OBJ, and standalone HTML export;
- visual-settings and `.vase` save/load;
- binary current-frame and full-trajectory coordinate transfer.
- semantic AI schema, operation/export parameter discovery, skill guide, and
  current-frame state.

Mutable structure requests and structure/3D-scene exports carry `frame_index`. The
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
Returned vectors retain physical values. The renderer anchors them at current
visible atom positions, repeats them over display supercells, and applies visual
translation equally to both endpoints.

Volumetric data is loaded through the ordinary file/path open or append
pipeline. VASP scalar grids, Cube, and XSF are detected before ASE structure
dispatch. Browser file/path endpoints accept `volumetric_precision` as
`float32` or `float64`; the semantic `load-volumetric` operation accepts
`precision` as FP32/FP64 aliases. Dataset descriptors report precision and
backend memory bytes. The newest nonconstant grid is selected and displayed at
an in-range default isovalue immediately. Surface color and opacity changes
restyle the current browser mesh without requesting marching cubes again. The
current document then exposes:

`view("CHGCAR", volumetric_precision="fp64")` applies the same selection to
Python path-based loading and records it as the next-import precision in the
live GUI.

```text
POST /api/volumetric/difference/{session_id}
POST /api/volumetric/isosurface/{session_id}
POST /api/volumetric/delete/{session_id}
```

The difference endpoint accepts stable dataset IDs and finite coefficients and
requires matching dimensions, cell, origin, PBC, endpoint convention, and
units. The isosurface payload accepts optional `smearing_sigma` in grid voxels
from `0` through `8`, plus `smoothing_iterations` from `0` through `30`.
Smearing uses wrapped boundaries on periodic axes and reflected boundaries on
nonperiodic axes. It filters a display copy without modifying the stored FP32
or FP64 field. Mesh smoothing is applied after marching cubes and fixes
cell-boundary vertices. The endpoint returns indexed vertices and faces with
the applied refinement values in its binary header; the complete source grid
remains backend-owned. Physical diagonal supercell application repeats every
stored grid and records it in the same undo entry as atoms and trajectory
frames.

The semantic `show-volumetric` operation validates the same ranges instead of
silently clamping values. Signed mode uses `+abs(level)` and `-abs(level)`,
requires a nonzero level, and may retain only one sign if smearing moves the
other sign outside the displayed scalar range. `describe()` exposes the
resulting mesh counts, rendered levels, post-smearing range, and refinement
settings under `analysis.volumetricSurface`; it does not transmit source grid
arrays.

RDF endpoints are:

```text
POST /api/analysis/rdf/{session_id}
POST /api/analysis/rdf-csv/{session_id}
```

Payload fields are `cutoff`, `bins`, `pairMode`, and `activePairs`. Full 3D
PBC is required. The response includes the retained requested/effective
cutoff, unique-MIC reference, actual periodic-image extent/span, warnings,
total `g(r)`, and concentration-weighted partial curves. CSV uses the same
calculation path. The Plotly drawer adds a `g(r) = 1` bulk-limit reference;
the periodic amorphous regression checks that the long-range curve remains
flat around that reference.

Agent discovery and semantic state are available through:

```text
GET /api/ai/schema
GET /api/ai/skill
GET /api/ai/state/{session_id}
POST /api/ai/events/{session_id}
GET /api/ai/events/{session_id}?after={revision}&timeout={seconds}
GET /api/ai/workspace-events/{workspace_id}?after={revision}&timeout={seconds}
```

Browser-originated events are compact notifications, not state patches. They
contain source, categories, changed paths, document/frame context, and a
monotonic revision. Workspace events also contain the affected `session_id`
and `document_revision`. Position arrays are intentionally omitted; agents
must activate the affected document and call `describe()`.

Image encoding is available through:

```text
POST /api/export/image/{session_id}?format=webp
POST /api/export/image/{session_id}?format=png
POST /api/export/image/{session_id}?format=jpg
POST /api/export/image/{session_id}?format=pdf
```

The endpoint accepts the exact browser-rendered PNG bytes. WebP conversion is
lossless; PNG conversion is a lossless IDAT recompression. JPEG and PDF flatten
transparency onto white. Every response keeps the original pixel dimensions.
PNG is the browser UI and semantic API default.

The human image-export workflow selects its destination before rendering and
uses one monotonic progress sequence across browser render, pixel capture,
upload, server encoding, response download, and destination write. Estimated
remaining time is derived from completed pipeline work; 100% is emitted once,
after the output file is complete.

The live HTTP bridge exposes `ready`, `capabilities`, `describe`, `apply`,
`render`, and `export`; workspace scope also exposes `documents`, `activate`,
and `newDocument`. The optional `window.v_aseAI` object mirrors these methods
for page-main-world controllers. `capabilities()` advertises
`expectedRevision` in its `apply` fields, and `describe()` reports the current
document collaboration revision. `apply()` accepts that revision as an
optimistic-concurrency guard and rejects stale commands before they can
overwrite a newer human GUI edit. It covers frame and mode changes, quality,
display and camera state, selection, constrained transforms, identity and
constraint edits, wrapping, physical translation, atom creation/deletion,
supercells, history, reset, relaxation, and displacement analysis. Visual
translation and display supercells are ordinary `display` settings available
in View and Edit. `rotate-selection` accepts `pivot: "active"`; the last
explicit atom index is the fixed rotation pivot.
It also covers volumetric loading, compatible-grid combinations, isosurface
settings/removal, and RDF calculation. `describe().analysis` returns
volumetric dataset descriptors and the current RDF summary without serializing
the scalar grid into agent context.
`export()` covers image, video, POSCAR,
ASE Pickle, Blender, Rhino 3DM, OBJ, standalone HTML, `.vase`, and visual
settings, plus RDF CSV. Rendering and image export use the same capture path
as the human Export workspace.

`describe()` is the primary machine-readable output and includes document,
mode, frame, atom identity, positions when requested, cell/PBC, constraints,
properties, selection, measurement, display, camera, and image-export state.
It also includes volumetric dataset metadata and RDF curve names, cutoff
metadata, warnings, and frame.
`apply()` returns the updated semantic state and revision. Human and agent
mutations are classified separately, coalesced after committed UI changes,
published to the document and workspace streams, and retained in bounded
history. `render()` and `export()` return data URLs plus filename, MIME type,
byte count, format, and dimensions where applicable.

WebSockets stream relaxation updates and own browser-document/workspace
lifetime. Closing the last connected browser document finalizes blocking calls
after a short reconnect grace period.
