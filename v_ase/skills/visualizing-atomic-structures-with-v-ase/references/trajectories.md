# Trajectories

## Contents

- Frames and properties
- Match indices and inspect energy
- Scalar coloring and vectors
- Movies and scientific fidelity
- Coordinate fidelity

## Frames and properties

Pause playback before an exact frame read, edit or render. Frames are zero-based;
the GUI may label them from one. `set-playback` controls movie playback;
`vase_pause_playback` is the typed pause shortcut. Use `vase_frame_properties` and
`vase_atom_scalar_catalog(frame=...)` to discover stored arrays and field IDs.
Never guess array syntax: the catalog may return an ID such as
`array::synthetic_response::scalar`. The native/CLI query returns data directly;
no separate HTTP fetch is needed on the current interface.
For human keyboard navigation, plain arrow keys orbit/tilt the camera;
Option+Left/Right on macOS or Alt+Left/Right on Windows/Linux steps only the
selected timeline. Space toggles its playback. Editable fields retain their
native arrow behavior. Agent tools should set the frame explicitly.

Read a scalar's values/range only when needed. Stored forces and charges are
stored data, not a request to evaluate a calculator. Missing values are missing,
not zero. `all_frames` can be large; prefer a range query or the relevant frame.

## Match indices and inspect energy

To add a frame in the desktop editor, right-click the viewport or timeline
and choose **Duplicate to next frame**. Copy before making the next geometry
edit. **Duplicate frame to end** appends instead. The copy becomes active.
The desktop shortcuts are Command/Ctrl+T and Command/Ctrl+Shift+T. These are
editor controls for changing the loaded trajectory.

**Delete current frame** in the same menu removes a source frame in Edit
mode. The next frame becomes active, or the preceding frame if the removed
one was last. The final remaining frame stays open as a single structure.
Undo restores the removed frame with its arrays and saved calculator data.

The **Selected atoms → Apply to** control defaults to **All frames** when
frame counts and element compositions match and the selected indices have
matching elements, effective labels and any available atom IDs. Differences
outside the selected labels are allowed. The eligibility check follows edits,
frame deletion and Undo/Redo. **Current frame only** requires confirmation
and invalidates label-dependent RDF and Polyhedra results on success.
Saved energies, forces and frame-specific assignments remain associated
with their structures. Explicit scope preference is saved in the project.

In **Per-label appearance**, rename the row to replace its label by name
across all frames, including trajectories with inconsistent index layouts.
Rules and display settings move with a rename. A confirmed merge uses
the destination's settings. Expand a row to delete it. A label with usage
in any frame requires a destination for its atoms. A globally empty label
remains reusable until explicitly deleted.

In **Edit structure**, the timeline's **Match** control assigns atoms by
element against the first source frame. Every frame must have the same
element multiplicities. **Minimum image** uses the reference cell and its
PBC mask. **Cartesian distance** uses direct distances. **SOAP + translation**
uses DScribe environments to propose translation candidates and ranks their
minimum-image assignments by species-balanced RMS. Matching only reorders the atoms;
no translations or rotations are applied. Coordinate arrays, per-atom
properties, constraints, and cached results follow the permutation. One Undo
restores the original order. DScribe is bundled on desktop and available as the
`soap` extra in Python.

**Overlays → Energy graph** uses stored energy in eV, with the saved NEB path
length when available. Missing values are gaps. The graph marker follows loaded
frames. Click or drag the graph to seek, drag its header to move it, or resize
at its lower-right corner. Resizing can snap the right or bottom edge to the
corresponding edge of another floating graph. Click the graph, its header or
its Scene row to open the shared **Graph settings** inspector. Select samples,
ASE fit or tangents in **Data series** to change the legend name, lines or
markers. Background, grid, cursor, font and tick labels are graph-wide. **Axis
limits** controls each bound and applies valid limits as you type. A blank
bound stays automatic. The viewport and HTML graph show the requested range.
Graph appearance can be saved as a named preset.
The inspector can also save the background as a per-user default for new
documents. **Export image** saves the styled graph as PNG and **Export CSV**
saves the numerical values, including any enabled fitted or tangent series.

The optional **NEB** inspector section fits the loaded band or its last
selected number of images with ASE's `fit_images`. It uses stored energies
and per-atom forces with common atom order. **Minimum image (PBC)** is enabled
by default and requires consistent periodic axes and cell vectors. Set
`energy_overlay.neb.mic` to `false` for a Cartesian path axis and tangent spans.
ASE projects forces using stored Cartesian directions in both modes. Choose
this option separately from atom-index matching. Enable
the fitted line and force tangents independently. Tangent length scales about
the image and preserves the slope. The fit uses its own path in Å and keeps
the source frame indices for scrubbing.

The typed `vase_apply_scene` display patch accepts `energy_overlay` with
`style`, `layout`, `axes` and `neb` fields. Use the full display schema for their
bounds. Set `vase_export_html(options={"include_graph": true})` to include
the graph explicitly. The preview, poster and interactive view use the same
placement relative to the exported frame. Opening the export dialog pauses
the trajectory. The Energy marker and timeline stay synchronized offline.
An already calculated Distribution joins the export when it is floated.

## Scalar coloring and vectors

**Home** and **End** jump to the ends of the selected timeline. The Scene
navigator opens Overlays by default and offers Energy graph for saved energy on a trajectory, Displacements
for trajectories, Force vectors when available, and Water surface for detected
H₂O. The entries follow changes in the loaded data.

Use the discovered `set-atom-colorscale` tool. Set field, map, range mode, scope
and bounds explicitly when comparing panels. Fixed bounds support cross-frame
comparison; per-frame automatic bounds can hide magnitude changes. Keep user
labels separate from array IDs and chemical elements. Preview custom maps only
when requested; named maps are discovered through the colormap catalog.
For comparable atom sizes, use `set-atom-radius-mapping` with
`rangeMode:"trajectory"` and `fit:true`, then inspect the locked limits.
Interpolated video samples interpolate continuous raw scalar values before
mapping; tags/flags/masks use the nearest endpoint and missing properties use
factor 1 with an explicit unavailable status.
Optimization frames derive coordinate factors from displayed optimizer
positions. A stored property absent from that optimizer frame uses neutral
factor 1; it must not borrow a same-index value from the loaded trajectory.

Displacements depend on reference frame, coordinate convention and MIC choice.
Set those controls explicitly and refresh displacements for the intended frame.
A displacement arrow is not a force or an MD-derived trajectory unless the source
actually supports that interpretation. Force-vector tools use stored force data.
Use scene readiness to confirm that frame, scalar colors and vectors are current.

## Movies and scientific fidelity

Loaded source trajectories and temporary optimization trajectories are distinct.
Exported interpolation adds display frames; it does not create simulated dynamics.
Use explicit interpolation/MIC/FPS settings. Movie dimensions must be even; use
the export schema for bounds. Scientific array identity, frame count and cell/PBC
must survive visualization-only work. Use a project or appropriate ASE format
when scientific data must remain editable.
MIC interpolation chooses a nearest lattice image in the midpoint cell metric
for the whole frame interval, then interpolates each endpoint's fractional
coordinates and cell. It searches periodic rows only; componentwise rounding is
insufficient for skew cells. Singular endpoint cells retain Cartesian fallback
with `micApplied=false`. Search limits (10,000 candidates/atom; 2,000,000/frame)
raise an error; use a reduced cell or explicitly disable MIC when appropriate.

Fast LAMMPS display streams use FP32. Loading an ASE frame for edits or scientific
export rereads numeric values in FP64, with exact int64 atom/molecule identities.
Large IDs must not be recovered from scalar display colors or FP32 positions.
Global calculator tensors/vectors are not per-atom scalar fields just because
their leading dimension happens to equal the atom count.
LAMMPS orthogonal, restricted and general triclinic boxes preserve their
Cartesian origin. Inspect `cellOrigin` in semantic structure state (raw JSON:
`cell_origin`); it also positions cell guides and interpolates between frames.
The general `abc origin` header can omit boundary flags; such files use finite
boundaries unless the user explicitly sets PBC. Fast View requires stable types;
for changing species reopen in Edit with the safe reader. Rejected frame loads
preserve the previous frame and return an actionable error.

## Coordinate fidelity

Browser frame transport requests float64 coordinates for both cached and streamed
trajectories. Scientific edits and project/structure exports preserve those
double-precision values. Scalar/vector visualization buffers may use float32;
this does not replace original per-atom arrays in scientific exports.

Colorscale selected scope is fixed at application time, like radius scope. GUI
First/Last source frames use 1-based inclusive values; semantic animation export
uses inclusive 0-based `startFrame`/`endFrame`. GIF `loop:false` plays once;
`loop:true` loops forever. Coordinates, colors and radii commit together during
playback; the previous canvas stays visible while scalar data loads.

Committed physical edits invalidate cached trajectory positions, including
requests started before the edit. Frame switching and animation export must
retain those edits in the original source frame; read structure positions after
a roundtrip when validating a scientific workflow. A selected scalar field is
retained if one frame omits it: missing values use the base appearance, while the
field and locked range remain available for subsequent frames.

Stored-force visualization lives in **Style → Forces** (visibility, arrow style,
scale, thickness, color and frame-specific availability). It only reads stored
values; it never runs a calculator. **Analyze → Displacements** retains reference
comparison, MIC and statistics because those derive data from frame pairs.

A single-frame structure or frame 0 in previous-frame mode has no displacement
comparison: the GUI reports availability, clears old arrows and completes scene
readiness. This is not stale data. Actual failed requests still block readiness
and report the error. Stored force vectors refresh after physical edits.

Internal desktop tabs use Command+Option+Left/Right (Mac) or Ctrl+Alt+Left/Right
(Windows); Command/Ctrl+1–8 selects a positional tab and 9 the last. These are
distinct from Alt/Option-only frame stepping. Browser reservation can limit
internal tab chords. GUI deletion in Edit asks current/all frame scope;
semantic `delete-selection` defaults to current and must explicitly use
`frameScope:"all"` for identical-index deletion across every frame. Missing
indices in shorter frames are skipped, even when elements change. Undo restores
the whole chosen scope, including labels, arrays and constraints.
