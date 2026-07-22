# Features & Architecture

## Core Features
### Interactive Editing
Users can select atoms and transform them in 3D space. The positions are synchronized back to the Python ASE `Atoms` object in real-time.

### Blender-Style Workflow
The visualizer adopts the modal operator pattern from Blender:
1. Select atoms.
2. Press `G` or `R`.
3. (Optional) Press `X`, `Y`, or `Z` to lock axis.
4. Move mouse to transform.
5. Click or press `Enter` to confirm, or `Esc` to cancel.

### Editor Actions
The current editor supports copy/paste, undo/redo, Delete/Backspace deletion,
reset, wrap, POSCAR export, pickle export, physically scaled PNG image
export, WebM video export, Blender scene export, and calculator-backed
relaxation controls. Visual presets can be saved as JSON, while `.vase`
projects preserve complete structures or trajectories together with display
state.

### Calculator Handling
Existing ASE calculators are preserved, including `SinglePointCalculator`.
In the default lightweight visualization mode, v_ase does not attach a fallback
calculator and hides repulsion calculator controls. When `--interactive` is
enabled and no calculator is attached, v_ase installs a default soft repulsion
calculator so Relax can still remove close contacts. The default calculator uses
NumPy when torch is unavailable. If torch is installed, it can run on CPU or
CUDA; torch is optional and is not a package dependency.

The top-right `DEVICE` and `CPU` controls apply only to this default repulsion
calculator and are applied immediately when changed. User-provided calculators
are expected to manage their own execution backend and are not modified by these
controls.

The default model is available through the public calculator API:

```python
from v_ase.calculators import RepulsionCalculator

atoms.calc = RepulsionCalculator(device="cpu", cpu_threads=4)
```

`Conditioner`, `DefaultRepulsionCalculator`, `from v_ase import
RepulsionCalculator`, and the compatibility module `v_ase.calculator` all point
to the same ASE calculator class.

### Display Tools
Bonds are rendered as live cylinder objects and update during transform previews,
relaxation updates, and trajectory frame changes. In interactive mode, auto and
pairwise-cutoff bonds are re-inferred from every G/R preview position, so bonds
break or form as soon as distances cross the active cutoff, before commit.
Manual pair topology remains fixed and only its cylinder geometry is updated.
The bond mode, global scale, label-pair `rcut` map, periodic-image policy, and
manual pairs persist across backend structure refreshes and label edits. Bonding
can use covalent-radius inference, label-pair cutoff rows, or an explicit pair
list such as `0-1, 1-2`. The displayed cell or positive supercell is the default
bond domain: bonds cross internal replica boundaries, but are clipped when the
other endpoint lies outside the displayed supercell. `Periodic image bonds`
opts into minimum-image vectors and cylinders extending toward outside images. This matches
VESTA's explicit distinction between keeping atom searches inside the boundary
and searching atoms beyond it, as documented in the [VESTA manual](https://jp-minerals.org/vesta/en/doc/VESTAch8.html).

Bond appearance is independent of topology inference. Thickness controls the
3D cylinder diameter or 2D flat-ribbon width. Color can be one freely selected
custom value or two midpoint-split segments using the endpoint atom colors.
Flat ribbons remain camera-facing during navigation. These settings persist in
visual-settings JSON files and are reproduced in PNG/WebM and Blender export.

Atomic scale belongs to the live Viewport controls. Editing its pixels-per-Angstrom
value changes the active orthographic zoom or perspective target distance
immediately; mouse-wheel zoom updates the same value, and a derived readout reports
the visible width and height in Angstrom. PNG export then has two framing contracts.
`Current viewport` clones the active camera and preserves its complete composition;
a different output aspect ratio is centered with margins rather than cropped or
shifted. `Atomic scale from View` uses that global value, making images from
different structures directly comparable (`field width in Å = image width in px /
px-per-Å`). Orthographic projection is uniform through depth, while perspective
uses the camera target plane as its scale reference. Export-only sphere quality
and a `0.5x`-`2.0x` smoothness multiplier temporarily replace atom geometry for
the render and then restore the live scene.

Orthographic projection is the default view, with perspective available as a
viewport option. Unit cell, axes, grid, and supercell preview controls are
exposed in the inspector. Supercell preview is only enabled when a valid unit
cell exists and PBC is true in the requested direction; otherwise the UI shows
a warning and resets the invalid multiplier. Every replica uses the base atom's
full material. Bonds are instanced in every repeated cell and separately bridge
internal supercell boundaries, including skewed/monoclinic cell vectors. In visualization mode,
replicas have stable `base-index + cell-offset` identities and support click,
Shift-click, box selection, element selection, `Ctrl+A`, hover metadata, and
displayed-coordinate center/distance/angle measurements. Interactive mode keeps
replicas outside atom edit selection until the supercell is committed.

Selection measurements and hover inspection use separate viewport HUDs. The
Measure HUD remains visible while the selection is retained and summarizes only
the selected count, distance, or angle with adjacent distances. Hover metadata
updates independently as the pointer moves over atoms.

### Inspector Navigation and Lighting
The inspector is divided into Inspect, Structure, Display, and Output sections
instead of one long mixed panel. Interactive-only constraint and relaxation
controls remain hidden in visualization mode, while Cell & Replication stays
available. The inspector starts fully collapsed and opens from a compact panel-edge handle.
The edge tab is centered vertically on the panel. Its visible 19 x 38 px surface
sits inside a transparent 28 x 48 px hit area, balancing legibility with reliable
mouse and touch interaction. Its 60-degree SVG chevron points toward the next
panel state without using text glyphs. Width, explicit collapsed state, and
active section are persisted locally.

The lighting control sits in the top toolbar immediately to the right of the
calculator controls, away from the viewport orientation gizmo. Its compact
icon uses the same sphere in both states: a matte object for Modeling and a
highlighted object with a ground shadow when rendered lighting is active. The
settings card opens directly below the toolbar control.

`Tab` opens the inspector only while it is collapsed. Once open, Tab remains
available for normal form navigation. `Esc` commits the active field, collapses
the inspector, focuses the viewport, and makes `G`/`R` immediately available
again; during a transform, Esc retains its usual cancel behavior.

The viewport renderer has three explicit modes:

- **Modeling**: the original balanced-light path, with no shadow map and no
  extra render loop.
- **Studio Sun**: physically based materials under ambient, hemisphere, and one
  directional Sun light.
- **Sun + Soft Shadow**: the same setup with one PCF soft shadow map. The
  orthographic shadow camera is fitted around the complete visible structure,
  including positive supercell previews, while the directional rays remain
  parallel and independent of source distance.

Sun brightness, source, and target update in real time. Enable Direction handles,
select either the source or target in the viewport, and use Blender-style `G`/`R`,
optional `X`/`Y`/`Z` axis locking, numeric input, `Enter`, and `Esc`. `Source + G`
translates source and target together, preserving the light direction. `Target + G`
moves only the target. `R` always rotates the target around the source, regardless
of which handle initiated the transform, and free mouse rotation follows the
same visible direction as atom rotation. Direct handle dragging does not change
the light. Image export accepts independent lighting values, so a
high-quality still can be produced while the live viewport remains in Modeling.
Blender export creates a `SUN` at the same position, rotates its local `-Z` toward
the same target, and assigns the same numeric intensity to Blender light energy.
The implementation stays on stable Three.js WebGL2 because the project's fixed-
atom material uses a custom shader hook; Three.js currently documents WebGPU as
experimental and does not support `onBeforeCompile()` materials there. See the
[Three.js WebGPU renderer notes](https://threejs.org/manual/en/webgpurenderer).

### Trajectory/Movie Playback
`view()` and `view_edit()` accept an `Atoms` object, a sequence of `Atoms`
frames, or an ASE-readable trajectory path. Multi-frame inputs expose an
OVITO-style timeline panel with previous/next, play/pause, frame slider, FPS,
and frame skip controls. Skip advances by `skip + 1` frames per playback tick,
so `0` means no skipped frames.

In the default visualization mode, large numeric LAMMPS text dumps use an
offset-indexed virtual trajectory path. v_ase parses the first frame into ASE,
keeps the remaining frames as file offsets, and serves frame changes as binary
float32 coordinates instead of rebuilding every frame as a full ASE object.

### File Type and Label Handling
The CLI accepts ASE-readable formats plus v_ase-specific helpers for custom
labels. extxyz labels such as `H_type5` are preserved as GUI labels while being
mapped to ASE-valid base elements. LAMMPS dump/data integer types are preserved
as raw GUI labels; valid integer ids are also interpreted as atomic numbers for
default color/radius distinction, while out-of-range ids fall back to internal
`H`.

### Appearance Editing
The Appearance table is label-oriented and stable under edits. Changing a label
does not reorder rows. If a label prefix names a real element, for example
`O_bridge`, the TYPE dropdown and default radius follow that element. When the
base element changes, stale radius/color overrides from the old label are not
blindly copied.

### ASE Pickle, Visual Presets, and `.vase` Projects
Output exposes three intentionally separate save paths:

- ASE Pickle stores the current ASE `Atoms` structure for Python reuse,
  including coordinates, labels, cell/PBC, constraints, portable atom arrays,
  and valid `SinglePointCalculator` results. Visualization state, arbitrary
  calculator implementations, and other trajectory frames are excluded.

- Visual Settings is a JSON preset for display, camera, Sun, quality,
  appearance, supercell preview, and complete bond configuration. Loading a
  preset intersects label-specific data with labels present in the new
  structure, ignores absent labels, creates defaults for new labels and label
  pairs, and drops invalid manual atom-index pairs.
- A `.vase` project is a validated ZIP archive containing an ASE trajectory,
  active frame, edited coordinates, cells, PBC, constraints, atom labels,
  safe per-atom arrays, JSON-compatible frame metadata, cached standard ASE
  calculator results, and the visual preset. It never unpickles executable
  Python objects. Cached results are reconstructed with
  `SinglePointCalculator`; the built-in repulsion calculator is reconstructed
  from validated primitive configuration. External calculator implementations
  and undo history are not embedded.

The CLI detects `.vase` directly, so `v_ase gui work.vase` restores the project.
Starting with `v_ase gui` opens an empty workspace whose browser Open flow can
stream structures, trajectories, and `.vase` projects into the same session.
Visualization-mode coordinates changed locally by Wrap are included in the
saved current frame.

### Rendering Performance
The viewport renders on demand instead of running a permanent animation loop.
Camera movement, trajectory playback, transforms, and UI changes request a
frame; an unchanged viewport remains idle. Large structures use Three.js
`InstancedMesh` batches for atoms, bonds, selection outlines, and supercell
repeats. Per-instance transforms, colors, and visibility avoid
creating one JavaScript object and draw call per atom.

The renderer also lowers device pixel ratio progressively for large atom counts,
uses a cell-list bond search, caches type/cell/force summaries, and serves large
LAMMPS trajectory frames as binary float32 positions. Measurement method and
current benchmark results are documented in [Rendering Performance](performance.md).

### Blender Scene Format
The Blender exporter emits a Python scene because this works without Blender in
the v_ase Python environment. The default optimized mode groups atoms by visual
label into editable point meshes and creates smooth sphere instances through
Geometry Nodes. Trajectory frames become point-mesh shape keys; bonds become
material-grouped curves or meshes; the cell is one multi-spline object. This
avoids the Python object-creation bottleneck for large structures. An Individual
objects mode remains available when atom-per-object editing is required.

Principled atom/bond/cell materials, the viewport camera, and a real Blender
`SUN` with source and target Empties are retained. Blender can run the script
headlessly and save a native `.blend` with `bpy.ops.wm.save_as_mainfile`. OBJ
would discard camera, constraints, trajectory behavior, instancing semantics,
and the richer material and lighting state.

### ASE Constraint Compatibility
The visualizer respects ASE constraints:
- **FixAtoms**: Atoms marked as fixed cannot be moved or rotated and are shown by a micro-etched atom material shader on the atom itself, with normal depth occlusion and no extra see-through marker.
- **FixedLine / FixedPlane**: Selected atoms move only along the line or inside the plane. Guides are selected-only: FixedLine uses a thin fading axis, and FixedPlane uses a translucent plane with perimeter, crosshair, and normal tick.
- **Show Overlays**: A viewport toggle hides selection outlines, selected constraint guides, Hookean overlays, and fixed-atom material marking when users need a clean structure view.
- **Interactive constraints**: The Constraints panel can apply or clear `FixAtoms`, `FixedLine`, and `FixedPlane` for the selected atoms.
- **Set Positions**: The backend uses `atoms.set_positions(..., apply_constraint=True)`, ensuring that even if the UI sends a move, ASE will enforce the physical constraints.

## Architecture
- **Backend**: FastAPI running through Uvicorn in a daemon thread. It serves static assets and provides REST endpoints for state updates, export, wrap/reset, and relaxation control.
- **Frontend**: A single-page application built with **Three.js**. It uses `Raycaster` for selection and a state-machine for transformations.
- **Communication**: JSON-over-HTTP for editing/export plus WebSockets for live relaxation updates.
    - `GET /api/atoms/{session_id}`: Fetches the current atoms state.
    - `GET /api/frame/positions/{session_id}/{frame_index}`: Fetches one virtual LAMMPS trajectory frame as binary float32 positions.
    - `POST /api/apply/{session_id}`: Applies new coordinates through ASE constraint logic.
    - `POST /api/add/{session_id}`: Appends atoms for paste operations.
    - `POST /api/delete/{session_id}`: Deletes selected atoms and remaps constraints.
    - `POST /api/constraints/{session_id}`: Applies or clears selected-atom FixAtoms, FixedLine, and FixedPlane constraints.
    - `POST /api/calculator/{session_id}`: Updates default repulsion calculator CPU/CUDA settings.
    - `POST /api/frame/{session_id}`: Switches the active trajectory frame.
    - `POST /api/wrap/{session_id}`: Wraps atoms into the unit cell.
    - `POST /api/export/poscar/{session_id}`: Exports the current structure as POSCAR.
    - `POST /api/file/load/{session_id}`: Streams a structure, trajectory, or `.vase` project selected in the browser into the active session.
    - `POST /api/export/pickle/{session_id}`: Exports the current ASE structure with valid single-point results, without visualization state or arbitrary calculators.
    - `POST /api/export/blender/{session_id}`: Exports a Blender Python scene.
    - `POST /api/settings/save/{session_id}`: Exports reusable visual settings as JSON.
    - `POST /api/settings/load/{session_id}`: Validates and loads JSON settings, with restricted legacy-pickle migration.
    - `POST /api/project/save/{session_id}`: Exports the complete current state as `.vase`.
    - `POST /api/project/load/{session_id}`: Replaces the session from a validated `.vase` archive.
    - `POST /api/relax/start/{session_id}`: Starts geometry optimization.
    - `POST /api/relax/stop/{session_id}`: Requests geometry optimization stop.
    - `WS /ws/{session_id}`: Streams relaxation positions, energy, and fmax. In blocking CLI mode, browser tab/window close is detected through this socket and releases the waiting terminal after a short reconnect grace period.
