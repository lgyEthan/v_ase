# Trajectories

## Frames and properties

Pause playback before an exact frame read, edit or render. Frames are zero-based;
the GUI may label them from one. `set-playback` controls movie playback;
`vase_pause_playback` is the typed pause shortcut. Use `vase_frame_properties` and
`vase_atom_scalar_catalog(frame=...)` to discover stored arrays and field IDs.
Never guess array syntax: the catalog may return an ID such as
`array::synthetic_response::scalar`. The native/CLI query returns data directly;
no separate HTTP fetch is needed on the current interface.

Read a scalar's values/range only when needed. Stored forces and charges are
stored data, not a request to evaluate a calculator. Missing values are missing,
not zero. `all_frames` can be large; prefer a range query or the relevant frame.

## Scalar coloring and vectors

Use the discovered `set-atom-colorscale` tool. Set field, map, range mode, scope
and bounds explicitly when comparing panels. Fixed bounds support cross-frame
comparison; per-frame automatic bounds can hide magnitude changes. Keep user
labels separate from array IDs and chemical elements. Preview custom maps only
when requested; named maps are discovered through the colormap catalog.

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
