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
- bounded volumetric datasets and current analysis results;
- undo/redo history in interactive mode;
- browser selection, camera, and visual settings;
- independent `.vase` save state.

Inactive document iframes suspend rendering and movie playback. Backend
calculations may continue, but all documents share physical CPU/GPU resources
through the process and operating system.

## Per-Atom Colorscales

Appearance can color all atoms or only the current selection from Cartesian
coordinates, stored force magnitude, numeric ASE per-atom arrays, and existing
per-atom calculator results. Scalar arrays are used directly; vector and
compact tensor arrays expose a norm and components. Every colormap registered
by the installed Matplotlib version is available, with reverse and gamma
contrast. The default current-frame fit resolves one vmin/vmax pair and locks
it across trajectory playback. A deliberate full-trajectory scan accumulates
global extrema frame by frame without allocating a complete value cube;
manual vmin/vmax remains available. Image, video, standalone HTML, and geometry
exports use the same resolved range. The catalog, values, and lookup table are
loaded only while the option is enabled; disabling it immediately restores
label, element, and per-atom appearance without per-frame colorscale work.

## Human-Agent Collaboration

v_ase is the scientific application in the collaboration cycle. Structured
Agent commands and human GUI edits enter the same v_ase document; the live GUI,
exact semantic state, and revisions leave v_ase for the researcher and Agent.
The visible cycle is bidirectional: Agent commands appear in the researcher's
GUI, direct GUI refinements emit a new revision, and the Agent must re-read that
revision before its next mutation.
`v_ase gui FILE --cli` controls the same workspace a researcher opens through
`human_url`. The first stdout line is the `v_ase.ai.v1` discovery handshake;
later lines are compact `v_ase.collaboration.v1` NDJSON events. Commands are
structured HTTP JSON requests to the handshake's `command_url`, not stdin
messages. `v_ase api` is the supported terminal client; the visible browser
executes commands against the same live document.
`v_ase api ... schema` exposes operation and export parameter maps, while
`capabilities` and `describe` report live features, calculator state, visual
state, and scientific state.

Each `EditorSession` owns a bounded document event queue and monotonic
collaboration revision. `EditorWorkspace` merges events from all tabs into a
separate ordered stream while preserving each event's `session_id` and
`document_revision`. Browser input classifies committed mutations as human,
agent, or system and coalesces high-frequency camera, selection, and control
changes before publishing. Events contain changed semantic paths and compact
context, never complete coordinates.

`describe()` returns the active document revision. `apply()` accepts
`expectedRevision`; a mismatch fails before mutation so a stale agent command
cannot overwrite a newer human GUI edit. On any human event, the agent
activates the affected tab, re-reads semantic state, updates its plan, and
continues from the new revision.

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
and destination are selected after the file is chosen. When the active
document is empty, the file directly replaces that document and the
destination chooser is skipped.

A `.vase` project restores all saved state when replacing a document or opening
in a new tab. When appended, only its selected structure frames are used. The
backend maintains a trajectory-wide ordered label/type catalog so Appearance
rows and pairwise bond controls remain valid when frames introduce labels not
present in the active frame.

Specialized readers preserve data ASE cannot represent directly:

- repeated POSCAR/CONTCAR species blocks become ordered labels such as `O_1`,
  `O_2`, and `O_3` while retaining the original ASE chemical symbol;
- custom extxyz labels map to ASE-valid chemical symbols and remain separate
  labels;
- LAMMPS dump/data integer types remain raw labels;
- masses may infer chemical TYPE where available;
- large numeric LAMMPS dumps use a memory-mapped frame index.

Label identity is stored in the `v_ase_atom_type` ASE array for archive
compatibility. New code accesses it through `atom_labels()` and
`set_atom_labels()`.

`v_ase.volumetric` is the canonical scalar-grid pipeline. It reads VASP
CHGCAR/CHG, LOCPOT, PARCHG, and ELFCAR plus Gaussian Cube and XSF. Quantum
ESPRESSO data uses its official Cube/XSF output rather than a second private
grid dialect. Every dataset owns one explicitly selected float32 or float64 3D
grid, cell, origin, PBC, endpoint convention, quantity, units, component, and
stable ID. Grid size, shape, finiteness, dtype, and cell volume are validated
before a session accepts it. FP32 is the lower-memory default; FP64 preserves
double-precision input values and uses twice the scalar-grid memory.

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
coordinates only. A one-atom Measure shows the displayed Cartesian and
fractional position plus standard ASE attributes, every stored per-atom array,
and every already available per-atom calculator result. This detail is loaded
for only the selected base index and current frame; inspecting an atom never
evaluates its calculator.

Edit additionally enables:

- modal `G` move and `R` rotate;
- numeric input, axis locking, Selection COM, active-atom, origin, cell-center
  pivot, and increment controls;
- add, delete, copy, paste, undo, and redo;
- constraints editing and calculator-backed relaxation.

### Add Atoms Workspace: ASE Bulk Builder

**+ Add atoms > Build with ASE** exposes the usable construction paths of the
installed `ase.build.bulk` implementation without probing ASE on every control
change. A process-local catalog caches reference elements, supported crystal
prototypes, compatible native/orthorhombic/cubic cell shapes, and conditional
arguments. The lightweight catalog is generated once; every preview and final
build still calls ASE so installed-version behavior remains authoritative.

Automatic reference mode filters formula suggestions by actual constructible
cell shape. Explicit prototypes expose only their relevant lattice fields.
Custom compounds have no invented defaults: `CuO`, for example, reports that
both a crystal prototype and lattice parameter `a` are required. Validation
also rejects incompatible shapes, nonfinite or nonpositive lengths, conflicting
`c` and `c/a`, and malformed fractional basis arrays before mutation.

The final action replaces the active document with one periodic frame while
preserving visual configuration. A nonempty structure or finite scratch cell
requires explicit confirmation, and complete original/trajectory state is
stored as one Undo entry. Loaded volumetric data, an active commensurate guest,
or an active relaxation must be resolved before replacement.

### Add Atoms Workspace: Direct Placement

Edit mode exposes one persistent Add Atoms workspace rather than treating
creation as an isolated button click. **Single** retains cursor/view-center or
exact-coordinate placement. **Batch** accepts any number of independent ASE
TYPE, visual LABEL, and Count rows or molecules from ASE's installed G2
catalog. A reproducible seed controls random positions and molecular
orientations.

The default domain is the complete unit-cell parallelepiped. Any number of
Cartesian **Allow regions** can restrict that base through their union, and any
number of **Reject regions** are then subtracted from it. Region IDs remain
stable across edits. Overlaps are counted once, and the accessible volume is
evaluated analytically by partitioning at every box face and intersecting each
boundary partition with the exact cell polyhedron. No voxel approximation is
used. A structure without a finite cell requires at least one Allow region;
Reject-only input is rejected because it has no finite base domain.

Sampling uniform fractional coordinates in `[0, 1)^3` and multiplying by the
full cell matrix is volume-uniform for orthogonal, monoclinic, and triclinic cells. **Homogeneous**
placement instead uses low-discrepancy centers, with maximin refinement for up
to 1,024 entities and bounded-memory direct low-discrepancy placement above
that size. Its default Cartesian metric maximizes physical distances in
angstrom; the fractional metric
balances normalized cell coordinates. Optional PBC-aware spacing uses the
exact triclinic minimum image. Each Cartesian region and every periodic image
is clipped against the primary cell polyhedron. This prevents skew-cell
bounding-box corners and periodic faces from being counted twice. With region
MIC enabled, the intact source cuboid remains at its original Cartesian bounds,
including any part outside the primary cell. Only nonzero lattice-translated
pieces are clipped into the opposite face, and shared fragment edges are drawn
once. This uses the full cell vectors, not a same-Cartesian-coordinate shortcut
or a collection of overlapping wrapped boxes.

Regions define initial placement. Inserted atoms may leave the Boolean domain
during repulsive placement by default; optional confinement projects them back
to the nearest valid generated boundary candidate. Across periodic faces, the
confinement force uses the shortest triclinic minimum-image displacement rather
than a direct Cartesian jump through the cell. Click or Shift-click rows or
overlays to select one or more regions. `G` translates the entire selected
group while preserving every stable ID and updating all six bounds. `R` is
rejected because a rotated region cannot be represented by Cartesian min/max
fields. All overlays disappear on Finish or Cancel. Changing region MIC in an
active, stopped session rebuilds both the backend domain and rendered images;
the control is locked while its optimizer is running.

Placement may initially contain short contacts. The placement card links to
the same **Structure > Relaxation** controls used by ordinary optimization:
calculator, bonding-relative or absolute cutoff, strength, device, CPU threads,
`fmax`, and steps have one source of truth. When an Add session is active, the
common Start action routes those values through the Add placement adapter. It
uses the ASE minimum-image convention and harmonic overlap penalty on one
complete detached optimizer copy. By default the structure present when the
session first opened is temporarily fixed while every inserted batch moves.
That mask is never appended to the document's ASE constraints.

Placement can be repeated without Finish. After a completed relaxation, the
species rows and regions remain editable; another atom or molecule batch is
appended to the existing staged topology and may be relaxed together with all
earlier inserted content. One immutable pre-session baseline and one Undo entry
cover the complete sequence. Cancel restores that exact baseline. Finish
rebuilds the host from it and appends only the final accumulated content, so
host coordinates, arrays, labels, calculator, and constraints remain
byte-for-byte or object-state equivalent as appropriate.

Molecule centers use the same region and placement rules. Count mode uses the
requested integer counts. Density mode interprets those counts as a composition
ratio, first reduces it by the greatest common divisor, converts the exact
accessible volume from Angstrom cubed to cubic centimeters, and selects the
nearest complete primitive-composition multiplier from ASE atomic masses and
the Avogadro constant. The UI reports target and actual density; it never
inserts fractional molecules. Changing regions after
scattering preserves staged topology and updates only the reported actual
density.

The ASE molecule
template is placed and rotated around its native coordinate origin. Random
orientation samples unbiased rotations in three dimensions. Rigid placement
is the default: intramolecular repulsion is excluded, optimizer forces are
projected onto rigid translation and rotation, and every accepted position is
projected back onto the immutable template geometry. Atomwise placement is an
explicit alternative. While rigid placement is active, interactive edits must
move or rotate a complete molecule and cannot distort one atom independently.

Accepted placement-relaxation steps are exposed through a temporary Add Atoms
timeline. It can be scrubbed or played while the workspace is active. Appending
a batch resets this temporary timeline because the staged atom count changed;
the next relaxation records the expanded topology. Finish or Cancel removes it.

Batch insertion is current-frame scoped. A loaded trajectory must be reduced
to the intended structure in a new document before the workspace starts, which
avoids silently changing only one frame of a scientific trajectory.

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
- `FixedLine`: each constrained atom receives one short, radius-scaled axis
  through its center that remains visible without selection. During `G`, a
  longer line anchored at the original position shows the full permitted
  direction. It never uses a ring or plane disc.
- `FixedPlane`: each atom receives its own radius-scaled ring, crosshair, and
  normal marker that remain visible without selection; multiple constraints
  are never collapsed to a selection center. During `G`, every selected
  FixedPlane atom also receives a larger translucent plane, perimeter, and
  crosshair anchored at its original position. This motion-only geometric overlay is
  rendered above the atom scene so the allowed plane remains readable while
  the constrained atom moves.
- `FixScaled`: allowed fractional directions are converted through the current
  cell and displayed as line/plane/fixed behavior.
- Hookean: threshold, inactive gap, and active state update from the current
  distance. The active segment is a shaded three-dimensional helical spring,
  not a screen-plane zigzag; the Blender scene uses the same spatial model.

Persistent directional guides use shared materials, remain local to their
owning atom, and are depth-tested so they do not read as selection outlines
through unrelated geometry. The larger FixedPlane motion surface exists only
during `G`, uses low opacity, and clears on commit or cancel.

Selection uses a yellow back-face sphere outline without a billboard ring.
This keeps Blender-style selection feedback distinct from the geometric ring
reserved for FixedPlane and plane-like FixScaled constraints.

Every selected-atom rotation displays a finite axis through the active pivot,
a neutral start reference, and an amber current reference. The current
reference follows free and axis-locked mouse rotation continuously.
Commensurate/magnetic candidates are separate cyan rays and do not duplicate
the zero-degree start reference.

Turning **Apply constraints** off permits unrestricted coordinate editing
without deleting the ASE constraints.

## Labels And Appearance

Chemical TYPE and visual LABEL are independent:

- TYPE is an ASE chemical symbol and controls element defaults and calculators.
- LABEL identifies a visual/chemical group and keys selection, visibility,
  explicit color/radius/opacity overrides, and pairwise bond cutoffs.

Changing a TYPE updates element color/radius defaults but keeps the label.
Changing a label to a valid element name or `Element_suffix` updates TYPE to the
parsed element. A non-element label changes only the label.

Appearance row order is established from the first loaded label order and does
not change after edits. Labels with the same chemical TYPE remain distinct.
Assigning an exact existing label in Edit merges the selected atoms into that
group instead of creating a suffix. If that target group has one chemical TYPE,
it is authoritative for the merged atoms.

Standard, Metal, and Rubber material presets are supported. View stores
materials and opacity by label. Edit can override material per selected atom.
Label opacity is clamped to `0..1`, participates in visual history, and remains
separate from visibility. Materials and label opacity are part of visual
presets, `.vase` projects, HTML, and geometry export payloads; reusable settings
omit per-atom overrides so they remain portable to structures with different
atom counts. Metal uses a shared on-demand PMREM studio environment with high
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

## Commensurate Cells And Planar Translation

Commensurate matching treats host and guest as independent periodic
sublattices. Cells-only preview is the default. Optional atom preview repeats
both parent lattices across the fixed display window when the atom budget
permits, keeps host and guest atoms opaque, infers bonds independently within
each component, and never invents host-guest bonds. Host, guest, and proposed
common cells use distinct guides. GUI activation, layer selection, and guest
loading preserve the current direct angle. The black host and orange guest
lattices remain primary and keep a candidate-independent display extent while
the mobile lattice rotates; the green common-cell guide is hidden until the
current angle resolves an actual bounded candidate. Only that candidate guide
changes size when the resolved integer cell changes.

The Plotly angle-area-strain view uses discrete candidate points above an
angle-area floor, a live current-angle plane, and dotted equivalent-angle
guides only for exact square or hexagonal symmetry. It has no candidate stems.
The accepted candidate set is unchanged by the visualization.

Planar Translation builds an exact primitive translation lattice in a requested
periodic `(hkl)` plane. Its optional map spans one complete plane cell; the
short-contact or pair-length score is geometric screening, not an energy. The
reversible rigid mode works without a precomputed map and uses the attached
calculator or repulsive fallback to optimize only two common plane coordinates
for the selected component. Host coordinates, cell, and all selected internal
vectors remain invariant. Selected z coordinates are additionally invariant
for `(0 0 1)`. Accepted steps use a mode-only timeline; Apply & Exit creates
one undo entry and Cancel restores the exact baseline.

## Trajectories And Relaxation

Compatible in-memory trajectories can be serialized as contiguous float32
coordinates. Large numeric LAMMPS dumps retain only the active ASE frame plus
file offsets and expose the same binary coordinate contract.

Playback loads the binary array once, then updates GPU instance translations
without per-frame HTTP, JSON, geometry rebuilds, or complete matrix rewrites.
Manual scrubbing still synchronizes the backend frame.

The fallback repulsion calculator exposes two alternative onset definitions
and one force strength under Structure > Relaxation. **Bonding** mode applies
the default `0.70` multiplier to each active label-pair cutoff from the current
Bonding setup. Automatic same-class pairs suppressed only from visual bond
rendering use a covalent contact cutoff so overlapping scratch atoms still
separate; explicit Pairwise disabled and `0 Å` entries remain inactive.
**Absolute** mode uses one user-entered distance in Angstrom for every enabled
pair. The harmonic pair energy and force are zero at and beyond either onset,
so the value is not a hard minimum-separation constraint. Bonding settings
remain visualization state, but their active cutoff table is synchronized into
the fallback calculator before relaxation.

Add Atoms uses the same visible calculator, cutoff, strength, device, `fmax`,
and step controls as whole-structure relaxation, but a staging adapter changes
which degrees of freedom are optimized. It can keep the immutable pre-session
host fixed, moves all accumulated inserted content, and emits bounded progress
over the document WebSocket. Its optimizer allocates only while active, and its
timeline remains distinct from the source trajectory and generic relaxation.

Base-atom selections survive frame changes and are removed only when the new
frame does not contain the selected index or its label is hidden. Measurements
are recomputed from the newly displayed positions.

An open radial or finite pair-distribution drawer follows both source frames
and operation-specific relaxation frames. Coordinate previews and committed
`G`/`R`/`S` edits invalidate only the affected cached curve; the drawer and
previous curve remain visible until the current displayed coordinates finish
recalculation.

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
duplicates from changing playback duration. Transcoding rebuilds constant
timestamps from frame order, so rendering delays cannot drop, duplicate, or
retime source frames. The progress indicator combines rendering, upload,
encoding, and file writing, stays monotonic, reports ETA, and reaches 100% only
after the destination write succeeds. Displacement vectors are recalculated
from each real or interpolated frame before that frame is captured.

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

Structure relaxation is an explicit mode. Leaving it removes its temporary
optimizer timeline without deleting the current optimized structure. Add
Atoms placement and rigid planar translation follow the same timeline ownership
rule while retaining their own commit/cancel semantics.

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

## Volumetric And RDF Analysis

Volumetric datasets are document state, not renderer-only assets. The backend
owns the scalar values and metadata; the frontend receives only dataset
descriptors and extracted indexed isosurface meshes.

Supported operations:

- load one VASP, Cube, or XSF grid and immediately show a valid default
  isosurface for the newest dataset;
- form an arbitrary finite linear combination of compatible grids;
- extract one positive surface or paired positive/negative surfaces;
- optionally Gaussian-smear only the displayed field with periodic wrapping
  and nonperiodic reflection before extraction;
- optionally fair the extracted indexed mesh while fixing cell-boundary
  vertices;
- restyle positive/negative colors and opacity live without rerunning marching
  cubes;
- create one or more cell-clipped `(hkl)` sections in View or Edit mode with a
  signed distance from the stored volumetric grid origin;
- edit selected plane resolution, colormap, range, opacity, visibility, and
  shared multi-plane values without changing atom coordinates;
- remove a dataset;
- repeat meshes for a display supercell and move them with visual translation;
- repeat the underlying grid when a physical diagonal supercell is
  materialized.

Import precision is chosen before parsing. FP32 and FP64 remain distinct
through linear combinations and `.vase` save/load. A combination promotes to
FP64 when any source is FP64 unless an explicit output precision is supplied.

Linear combinations require identical shape, cell, origin, PBC, endpoint
convention, and scalar units. There is no implicit resampling. A materialized
non-diagonal cell transform is rejected while volumetric data is present
because it cannot preserve the sampled field without a separately validated
resampling algorithm. Undo restores atoms, trajectories, cells, and
volumetric datasets atomically.
Coordinate reset also restores the originally loaded atom frames and scalar
grids as one state after a materialized diagonal supercell.

Marching cubes closes periodic seams before extracting the surface. `stepSize`
1 preserves the loaded grid; 2 and 4 are explicit interactive previews.
Field smearing is measured in grid voxels, preserves the source dtype, and
never mutates the stored scalar array. Its last result is cached per dataset
so a signed positive/negative request filters the grid once. Mesh smoothing is
a shrinkage-reducing two-pass Laplacian fairing stage after marching cubes;
zero passes returns the original extracted vertices. Extracted meshes use
indexed float32 geometry.

The Volumetric Data panel separates isosurfaces, planar sections, and field
arithmetic into internal workspaces. View mode exposes the full plane editor
as non-destructive analysis state. Edit mode adds viewport transforms: `G`
moves each selected plane along its own normal, while `R` changes the
reciprocal-space normal. The panel distance, slider, hkl fields, and list
labels remain synchronized during the live transform. Plane sampling clips
against the exact displayed triclinic cell or supercell and transfers only the
selected compact raster to the browser.

Volumetric refinement separates pre-extraction field filtering from
post-extraction mesh fairing so each control has one explicit numerical
meaning. Boundary modes use the documented `wrap` and `reflect` semantics of
[SciPy `gaussian_filter`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html).
The implementation and parameter contract are independently tested against
v_ase's periodic-grid representation.
The semantic state keeps source dataset descriptors separate from a generated
surface summary containing rendered levels, post-smearing range, mesh counts,
and refinement settings. Invalid semantic refinement values are rejected;
volumetric imports publish analysis-only collaboration changes.

Bulk radial distribution functions use a matscipy periodic directed-neighbor
search and exact spherical shell-volume normalization. The default radius is
the unique-MIC reference, but an explicit larger cutoff is retained: every
periodic cell shift contributing a pair inside the requested sphere is
enumerated, including shifts beyond a fixed `2 x 2 x 2` repetition. Partial
or finite PBC is rejected rather than shown with an invalid bulk normalization.
The total curve is always returned. Optional visual-label pair curves use the
concentration-weighted relation `g = sum(c_a c_b g_ab)`, with a factor of two
for mixed pairs. Pair selection
can follow enabled bond labels, include all label pairs, or be disabled.

The shared pair-search adapter is numerically checked against ASE for
cell-free and finite systems, rank-one wires, rank-two slabs, full-rank
partial PBC, and orthogonal or triclinic 3D PBC. Partial-periodic searches keep
the original periodic lattice rows and require zero image shift on every
finite axis, including when coordinates lie outside that finite cell extent.
Exported periodic bonds use ASE `find_mic` for the final vector rather than
component-wise fractional wrapping.

The Analysis drawer uses the locally installed Plotly bundle and remains
resizable below the viewport. RDF computation stays in the backend; the
browser receives numeric arrays for plotting and CSV export. A dotted
`g(r) = 1` reference identifies the homogeneous bulk limit so a valid
long-range amorphous plateau is visually explicit. Hidden RDF and volumetric
surfaces incur no per-frame render work.

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
measurements and pointer hover metadata use separate persistent HUDs. One-atom
property detail is scroll-bounded in the Inspector while the viewport HUD keeps
only position and property count. Five or more selected atoms show the total
followed by stable first-seen label counts.

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

Image export defaults to PNG and also supports JPEG, single-page raster PDF,
and lossless WebP. PNG and WebP preserve rendered dimensions and exact RGBA
pixels. PNG is losslessly recompressed server-side by rebuilding its IDAT
stream; it is never resampled. JPEG and PDF are composited onto white because
they do not preserve the transparent canvas. The original browser PNG is
retained when recompression is not smaller.

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
- Image: PNG by default, plus JPEG, PDF, or lossless WebP at the exact
  requested dimensions.
- Video: H.264 MOV or MPEG-4 AVI with source-frame or interpolated playback.
- Export/Import Preset: portable, structure-independent visual settings JSON.
- Personal default: OS-user appearance, bonds, lighting, viewport,
  replication, visual translation, and render-quality startup settings for
  new structures and tabs. Coordinates, cell contents, trajectory data,
  absolute camera placement, and per-atom overrides are excluded.
- Interface theme: System follows the local browser/OS preference; explicit
  Light and Dark choices persist in that browser and remain separate from the
  3D viewport background.
- `.vase`: complete validated project archive.
- `.vase` volumetric state: validated compressed NPZ members with bounded
  expected arrays; no executable pickle payload.
- Standalone HTML View: a single offline, view-only document containing
  inlined Three.js/runtime assets plus browser-ready scene and trajectory
  data. It shares the image/video Preview Area crop, defaults to grid off with
  axes and unit cell on, and embeds an optimized high-resolution Finder/Quick
  Look poster containing only that frame. The poster and adaptive live WebGL
  canvas use one integer-sized viewport and cross-fade automatically after the
  first live frame is ready, before camera input begins, so no header, logo,
  margin, border, or layout jump appears. The default output is lightweight; a
  save-time option embeds the complete validated `.vase` archive for lossless
  reopening.
- Project save: **Save .vase** writes the compact canonical project, while
  **HTML Project** defaults to embedding the complete project in a
  browser-ready copy.
- Blender: optimized label-group point meshes, Geometry Nodes spheres,
  trajectory shape keys, bonds, optional cell, camera, and Sun.
- Rhino 3DM: block-instanced atoms/bonds with metadata and saved views; optional
  `rhino3dm` dependency.
- OBJ: static OBJ/MTL plus camera/metadata JSON sidecar; no optional dependency.
- RDF CSV: radius, total `g(r)`, and requested partial curves.

Blender's optimized mode intentionally avoids one object per atom. Individual
objects remain available only when atom-by-atom Blender editing is required.

## Browser Lifetime

The CLI and blocking Python API wait while their browser document is connected.
The document WebSocket tolerates short reload/reconnect gaps. Closing the tab or
window finalizes the session, returns the current working structure, cleans
temporary files, stops the managed local server, and releases the terminal.

Multi-document desktop mode uses an additional workspace WebSocket so closing
the shell releases all child documents.
