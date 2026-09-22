# Trajectories

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

## Scalar coloring and vectors

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
