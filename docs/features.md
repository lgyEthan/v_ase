# Architecture And Feature Contracts

## Application Model

v_ase is a local FastAPI application with a Three.js frontend. A document maps
to one `EditorSession`; a desktop window maps to one workspace containing one
or more document sessions.

Each document owns:

- original and working ASE structures;
- loaded or virtual trajectory state;
- current frame and optional relaxation trajectory;
- calculator and constraint state;
- undo/redo history in interactive mode;
- browser selection, camera, and visual settings;
- independent `.vase` save state.

Inactive document iframes suspend rendering and movie playback. Backend
calculations may continue, but all documents share physical CPU/GPU resources
through the process and operating system.

## Input Pipeline

`v_ase.io.read_structure_frames()` is the canonical structure reader used by
the CLI, browser file Open, and Python file API. Format aliases are resolved by
`resolve_input_format()`.

Specialized readers preserve data ASE cannot represent directly:

- custom extxyz labels map to ASE-valid chemical symbols and remain separate
  labels;
- LAMMPS dump/data integer types remain raw labels;
- masses may infer chemical TYPE where available;
- large numeric LAMMPS dumps use a memory-mapped frame index.

Label identity is stored in the `v_ase_atom_type` ASE array for archive
compatibility. New code accesses it through `atom_labels()` and
`set_atom_labels()`.

## Visualization And Interactive Modes

Visualization mode is the default. It supports:

- camera navigation and axis alignment;
- click/box/label selection and measurements;
- trajectory scrubbing and playback;
- bonds, appearance, wrapping, supercells, lighting, and exports.

It does not attach the fallback calculator or invoke edit-only workflows.
Positive supercell images are selectable and measurable using a base index and
cell offset.

Interactive mode additionally enables:

- modal `G` move and `R` rotate;
- numeric input, axis locking, pivot and increment controls;
- add, delete, copy, paste, undo, and redo;
- constraints editing and calculator-backed relaxation.

Display-only supercell images remain uneditable until **Set Supercell as Cell**
creates a real ASE supercell.

## Constraint Contract

Frontend transforms are previews. A confirmed transform is sent to Python and
committed through:

```python
atoms.set_positions(candidate, apply_constraint=True)
```

The backend result replaces the preview. This keeps ASE authoritative for
`FixAtoms`, `FixCartesian`, `FixScaled`, `FixedLine`, `FixedPlane`, Hookean, and
other supported position constraints.

Constraint rendering:

- `FixAtoms`: element color is retained with a distinct fixed material surface.
- `FixedLine`: each constrained atom receives its own directional guide.
- `FixedPlane`: each atom receives its own bounded plane guide; multiple
  constraints are never collapsed to a selection center.
- `FixScaled`: allowed fractional directions are converted through the current
  cell and displayed as line/plane/fixed behavior.
- Hookean: threshold, inactive gap, and active spring state update from the
  current distance.

Turning **Apply constraints** off permits unrestricted coordinate editing
without deleting the ASE constraints.

## Labels And Appearance

Chemical TYPE and visual LABEL are independent:

- TYPE is an ASE chemical symbol and controls element defaults and calculators.
- LABEL identifies a visual/chemical group and keys selection, visibility,
  explicit color/radius overrides, and pairwise bond cutoffs.

Changing a TYPE updates element color/radius defaults but keeps the label.
Changing a label to a valid element name or `Element_suffix` updates TYPE to the
parsed element. A non-element label changes only the label.

Appearance row order is established from the first loaded label order and does
not change after edits. Labels with the same chemical TYPE remain distinct.

## Bonds

Bond topology modes:

- **Automatic**: covalent radii with a global scale and conservative tolerance.
- **Pairwise cutoff**: explicit label-pair distance; `0` disables the pair.
- **Manual pair**: explicit atom-index topology.

Automatic and pairwise topology is inferred for each trajectory frame and every
interactive transform preview. Manual topology remains fixed while geometry
stretches.

For large structures, a cell-list search and displacement-validated neighbor
candidate cache replace the quadratic pair loop. Actual distances and cutoffs
are still checked every frame. Periodic nearest-image candidates are reused to
derive direct base-cell bonds and supercell bridge records. Repeated bonds
cross internal supercell boundaries and are clipped only at the displayed
outer boundary. **Periodic image bonds** separately enables bonds extending
toward images outside the displayed cell.

Bond appearance is independent of topology: cylinder or flat style, diameter,
custom color, or midpoint-split endpoint colors.

## Trajectories And Relaxation

Compatible in-memory trajectories can be serialized as contiguous float32
coordinates. Large numeric LAMMPS dumps retain only the active ASE frame plus
file offsets and expose the same binary coordinate contract.

Playback loads the binary array once, then updates GPU instance translations
without per-frame HTTP, JSON, geometry rebuilds, or complete matrix rewrites.
Manual scrubbing still synchronizes the backend frame.

Relaxation has its own timeline. For a loaded trajectory, each source frame can
own a relaxation path. Space-bar playback follows the loaded trajectory and
uses a relaxed override when one exists. A single loaded structure with a
relaxation path plays the optimization timeline.

## Rendering

The viewport is demand-rendered. Camera input, frame updates, transforms, and
display changes request a frame; an unchanged scene remains idle.

GPU batching covers:

- atoms grouped by geometry/material;
- bonds grouped by style/material;
- selection outlines;
- visualization-mode supercell replicas.

Position-only updates alter translation columns in instance matrices. Cached
geometries, materials, label indices, cell bases, and selection proxies are
reused.

Rendering modes:

- **Modeling**: balanced lightweight lighting, no shadow map.
- **Studio Sun**: physically based materials under one directional Sun rig.
- **Sun + Soft Shadow**: one fitted PCF shadow map added to Studio Sun.

The Sun is directional: rays remain parallel regardless of source distance.
Source and target can be selected and transformed. Moving the source translates
the complete rig; moving the target changes aim; rotating either handle pivots
the target around the source.

## Camera, Measurement, And Output Preview

Orthographic projection is default; perspective is optional. Atomic scale is a
live pixels-per-Angstrom contract and updates with wheel zoom.

Sequential one-to-four atom selections produce ordered point, distance, angle,
and signed torsion measurements. Selection measurements and pointer hover
metadata use separate persistent HUDs.

Output Preview uses a cloned camera and a fixed screen-space frame with the
requested output aspect ratio. Preview, PNG, and trajectory video share one
authoritative profile for:

- camera and framing;
- dimensions and atom smoothness;
- background/transparency;
- grid, axes, and unit cell;
- renderer and Sun settings.

## Save And Export

- ASE Pickle: current-frame ASE interchange only.
- Visual Settings JSON: structure-independent presentation preset.
- `.vase`: complete validated project archive.
- Blender: optimized label-group point meshes, Geometry Nodes spheres,
  trajectory shape keys, bonds, optional cell, camera, and Sun.
- Rhino 3DM: block-instanced atoms/bonds with metadata and saved views; optional
  `rhino3dm` dependency.
- OBJ: static OBJ/MTL plus camera/metadata JSON sidecar; no optional dependency.

Blender's optimized mode intentionally avoids one object per atom. Individual
objects remain available only when atom-by-atom Blender editing is required.

## Browser Lifetime

The CLI and blocking Python API wait while their browser document is connected.
The document WebSocket tolerates short reload/reconnect gaps. Closing the tab or
window finalizes the session, returns the current working structure, cleans
temporary files, stops the managed local server, and releases the terminal.

Multi-document desktop mode uses an additional workspace WebSocket so closing
the shell releases all child documents.
