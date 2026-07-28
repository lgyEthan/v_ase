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

Browser Open has three explicit destinations:

- replace the current document while retaining its visual settings for
  ordinary structures;
- append selected frames to the current trajectory while retaining its current
  frame, camera, and visual settings;
- upload into a new independent workspace document.

Open invokes the operating system file picker immediately. Reader, frame range,
and destination are selected after the file is chosen.

A `.vase` project restores all saved state when replacing a document or opening
in a new tab. When appended, only its selected structure frames are used. The
backend maintains a trajectory-wide ordered label/type catalog so Appearance
rows and pairwise bond controls remain valid when frames introduce labels not
present in the active frame.

Specialized readers preserve data ASE cannot represent directly:

- repeated POSCAR/CONTCAR species blocks become ordered labels such as `O1`,
  `O2`, and `O3` while retaining the original ASE chemical symbol;
- custom extxyz labels map to ASE-valid chemical symbols and remain separate
  labels;
- LAMMPS dump/data integer types remain raw labels;
- masses may infer chemical TYPE where available;
- large numeric LAMMPS dumps use a memory-mapped frame index.

Label identity is stored in the `v_ase_atom_type` ASE array for archive
compatibility. New code accesses it through `atom_labels()` and
`set_atom_labels()`.

## View And Edit Modes

View is the default. It supports:

- camera navigation and axis alignment;
- click/box/label selection and measurements;
- trajectory scrubbing and playback;
- bonds, appearance, wrapping, supercells, visual translation, lighting, and
  exports.

It does not attach the fallback calculator or invoke edit-only workflows.
Positive supercell images are selectable and measurable using a base index and
cell offset. Two-point measurements report the displayed direct distance, the
periodic MIC distance, and, when a replica is involved, the distance after both
atoms are mapped into the original unit cell. Angles and torsions use displayed
coordinates only.

Edit additionally enables:

- modal `G` move and `R` rotate;
- numeric input, axis locking, pivot and increment controls;
- add, delete, copy, paste, undo, and redo;
- constraints editing and calculator-backed relaxation.

Display-only supercell images remain uneditable until **Set Supercell as Cell**
creates a real ASE supercell.

**Translate atoms** is a View/Edit scene offset rather than an ASE coordinate
edit. Cartesian or fractional values are absolute, apply after display
repetition, and move atom-attached overlays while the cell stays fixed. The
input retains the applied value; applying zero restores the unshifted scene.

The top-bar **View / Edit** switch changes mode without reopening the document.
Entering Edit materializes a lazy trajectory into editable ASE frames before
the switch completes. Returning to View preserves coordinates and creates
numbered labels only when atoms in one label have different per-atom visual
materials. Position-only edits do not split labels.

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
- `FixedLine`: each constrained atom receives a short, radius-scaled axis and
  compact perpendicular collar that remain visible without selection.
- `FixedPlane`: each atom receives its own radius-scaled ring, crosshair, and
  normal marker that remain visible without selection; multiple constraints
  are never collapsed to a selection center.
- `FixScaled`: allowed fractional directions are converted through the current
  cell and displayed as line/plane/fixed behavior.
- Hookean: threshold, inactive gap, and active state update from the current
  distance. The active segment is a shaded three-dimensional helical spring,
  not a screen-plane zigzag; the Blender scene uses the same spatial model.

Directional guides use shared materials, remain local to their owning atom,
and are depth-tested so they do not read as selection outlines through unrelated
geometry.

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
Assigning an exact existing label in Edit merges the selected atoms into that
group instead of creating a suffix. If that target group has one chemical TYPE,
it is authoritative for the merged atoms.

Standard, Metal, and Rubber material presets are supported. View stores
materials by label. Edit can override material per selected atom. Materials are
part of `.vase` projects and static export payloads; reusable settings omit
per-atom overrides so they remain portable to structures with different atom
counts. Metal uses a shared on-demand PMREM studio environment with high
metalness and low roughness; no reflection environment is allocated until a
metal preset is present.

New documents start with an atom-radius scale of `0.60x`. Explicit values in
projects and reusable settings remain authoritative.

New documents also use an exact `#ffffff` viewport clear color. Modeling-mode
hemisphere, ambient, and camera-facing fills keep element colors readable from
opposite crystallographic views without enabling shadow maps. White-mode grid
lines use reduced contrast so the background remains visually white.
Anti-aliasing and atom smoothness are View quality controls; label color,
radius, visibility, material, text, and chemical TYPE remain Structure
appearance controls.

Unit-cell edges use shared instanced cylinder geometry. Their color, diameter in
Angstrom, and Unlit/Standard/Metal material are visual settings. Repeated cells
reuse the same style and shared boundaries are deduplicated.

## Bonds

Bond topology modes:

- **Automatic**: ASE covalent radii from Cordero et al.
  ([DOI 10.1039/B801115J](https://doi.org/10.1039/B801115J)) with additive
  tolerance by pair class. H-H and metal-metal contacts are excluded by
  default; metal-ligand, H-containing, and other covalent pairs use separate
  tolerances.
- **Pair specifications**: each label pair has an enabled state and explicit
  maximum distance. The maximum is the complete topology rule for that
  mode; a disabled row or zero maximum produces no bond. Initial specifications
  are deterministic element-radius suggestions, not values learned from a
  previous structure or user setting. The label-pair column can be resized.
- **Manual index pairs**: explicit atom-index topology.

Automatic and pair-specification topology is inferred for each trajectory frame
and every interactive transform preview. Manual topology remains fixed while
geometry stretches. All bond controls are live; there is no separate apply
operation.

For large structures, a cell-list search and displacement-validated neighbor
candidate cache replace the quadratic pair loop. Actual distances and cutoffs
are still checked every frame. Periodic nearest-image candidates are reused to
derive direct base-cell bonds and supercell bridge records. Repeated bonds
cross internal supercell boundaries and are clipped only at the displayed
outer boundary. **Periodic image bonds** separately enables bonds extending
toward images outside the displayed cell.

Bond appearance is independent of topology: cylinder or flat style, diameter,
custom color, or midpoint-split endpoint colors. The new-document bond diameter
is `0.25 A`, and bonds are visible by default. Saved explicit values and
`--hide-bonds` remain authoritative.

## Trajectories And Relaxation

Compatible in-memory trajectories can be serialized as contiguous float32
coordinates. Large numeric LAMMPS dumps retain only the active ASE frame plus
file offsets and expose the same binary coordinate contract.

Playback loads the binary array once, then updates GPU instance translations
without per-frame HTTP, JSON, geometry rebuilds, or complete matrix rewrites.
Manual scrubbing still synchronizes the backend frame.

The fallback repulsion calculator exposes a pair-cutoff scale and force
strength under Structure > Relaxation. New calculator instances use a `0.70`
cutoff scale and `1.0` strength. These are calculator parameters and do not
change visualization bond cutoffs.

Base-atom selections survive frame changes and are removed only when the new
frame does not contain the selected index or its label is hidden. Measurements
are recomputed from the newly displayed positions.

Displacement arrows begin at the currently visible atom position, repeat over
the displayed supercell, and retain the physical vector returned by the
backend. A visual translation shifts both endpoints equally.

Video export uses source frames directly at `1x`. An optional integer
interpolation multiplier inserts linear subframes between adjacent snapshots;
the output count is `(Nsource - 1) * multiplier + 1`. MIC mode converts each
endpoint through its own cell, follows the shortest displacement along axes
that are periodic in both frames, interpolates a changing cell, and wraps the
temporary fractional position for rendering. Atom count, order, labels, and
chemical types must remain stable when interpolation is enabled.
Canvas samples are requested explicitly and MOV/AVI transcoding receives both
the selected FPS and expected frame count, preventing browser refresh-rate
duplicates from changing playback duration.

Files appended from the Open dialog become frames in the active source
trajectory. The active frame and document visual state are preserved; newly
introduced labels and chemical types are reconciled without renaming existing
groups.

Relaxation has its own timeline. For a loaded trajectory, each source frame can
own a relaxation path. When both source and relaxation trajectories exist, a
timeline selector chooses which one receives transport controls, Space-bar
playback, and Left/Right Arrow frame stepping. The other source remains visible
as a secondary timeline. A loaded source frame still uses its relaxed override
when one exists.

## Displacement Analysis

The Analysis workspace compares the current trajectory frame with the previous
frame or an explicitly selected reference frame. It returns one mapped vector
per common particle and reports mean, RMS, and maximum magnitude.

Mapping is physically conservative:

- a shared unique `lammps_id`, `atom_id`, `particle_id`, `ids`, or `id` array
  maps particles across reordered or unequal-size frames;
- equal-size frames without IDs use stable atom indices;
- unequal-size frames without a common unique ID array are rejected.

Minimum-image correction is optional and uses ASE `find_mic()` with the
current frame's own cell and PBC. The renderer draws all arrows with one
instanced shaft batch and one instanced head batch. 3D/flat style, scale,
thickness, and color changes restyle the cached result without recalculation.
Hidden analysis has no calculation or render cost.

## Rendering

The viewport is demand-rendered. Camera input, frame updates, transforms, and
display changes request a frame; an unchanged scene remains idle.

GPU batching covers:

- atoms grouped by geometry/material;
- bonds grouped by style/material;
- selection outlines;
- visualization-mode supercell replicas.
- displacement-vector shafts and heads.

Position-only updates alter translation columns in instance matrices. Cached
geometries, materials, label indices, cell bases, and selection proxies are
reused.

Atom presets use cached `MeshPhysicalMaterial` instances. A scene with one
label and one material remains one instanced atom group; only distinct visual
materials add groups.

Rendering modes:

- **Modeling**: balanced lightweight lighting, no shadow map.
- **Studio Sun**: physically based materials under one directional Sun rig.
- **Sun + Soft Shadow**: one fitted PCF shadow map added to Studio Sun.

The Sun is directional: rays remain parallel regardless of source distance.
Source and target can be selected and transformed. Moving the source translates
the complete rig; moving the target changes aim; rotating either handle pivots
the target around the source.

## Camera, Measurement, And Output Preview

Orthographic projection and a white viewport background are default;
perspective and a dark background are optional. Atomic scale is a live
pixels-per-Angstrom contract and updates with wheel zoom.

Sequential one-to-four atom selections produce ordered point, distance, angle,
and signed torsion measurements. Direct-coordinate and
minimum-image-convention (MIC) values are shown together; displayed supercell
replicas retain their on-screen coordinate measurement contract. Selection
measurements and pointer hover metadata use separate persistent HUDs. Five or
more selected atoms show the total followed by stable first-seen label counts.

The camera-step toolbar is ordered as the three view-relative pairs up/down,
left/right, and counterclockwise/clockwise roll. Up/down and left/right use
separate depth-coded paths with shaded rear tails and front faces; roll remains
a screen-plane operation. The camera world quaternion defines this basis, so
the controls remain screen-relative after arbitrary view roll, cell transforms,
and axis alignment. Opposite buttons are exact camera-pose inverses.

Output Preview uses a cloned camera and a fixed screen-space frame with the
requested output aspect ratio. Preview, image output, and trajectory video share one
authoritative profile for:

- camera and framing;
- dimensions and atom smoothness;
- background/transparency;
- grid, axes, and unit cell;
- renderer and Sun settings.

Image export supports lossless WebP and PNG. WebP is the compact default and
preserves the rendered dimensions and exact RGBA pixels. PNG output is
losslessly recompressed server-side by rebuilding its IDAT stream; it is never
resampled. The original browser PNG is retained when recompression is not
smaller.

Video export preserves the selected pixel dimensions. MOV uses H.264 with a
slow encoder preset and visually lossless-oriented quality settings; AVI uses
MPEG-4 with a bounded quality level. Compression changes encoding efficiency,
not the requested width or height.

Frame-scoped mutation and export requests include the browser's current
`frame_index`. Trajectory-wide translation, wrapping, repetition, and matrix
supercell operations apply independently with each frame's own cell and PBC.
This trajectory-wide translation is the physical Edit operation, distinct from
the View/Edit visual translation saved in display settings.

## Save And Export

- ASE Pickle: current-frame ASE interchange only.
- Image: lossless WebP or optimized PNG at the exact requested dimensions.
- Video: H.264 MOV or MPEG-4 AVI with source-frame or interpolated playback.
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
