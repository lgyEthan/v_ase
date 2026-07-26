# Changelog

## 0.0.79

- Added a top-bar View/Edit switch that preserves the active structure,
  trajectory frame, camera, labels, bonds, appearance, and selection.
- Added Standard, Metal, and Rubber atom materials with label-level controls in
  View and selected-atom controls in Edit.
- Made exact label assignment merge selected atoms into existing groups while
  keeping ASE chemical identity synchronized.
- Converted per-atom material variants into numbered View labels without
  splitting position-only edits.
- Materialized lazy LAMMPS trajectories only when entering Edit, with a visible
  transition state and complete frame preservation.
- Matched material properties in Blender, 3DM, and OBJ exports.
- Retuned the default camera-facing lighting for clearer element separation
  across opposite views while retaining demand rendering and GPU instancing.
- Added real Chromium coverage for runtime mode transitions and a 15,000-atom
  material/render benchmark.

## 0.0.78

- Unified CLI, browser Open, and Python file input through one canonical reader.
- Added memory-mapped LAMMPS frame indexing and contiguous float32 browser
  trajectory playback.
- Reduced position-only updates to GPU instance translations and removed
  duplicate periodic bond searches.
- Replaced fixed local-server startup delay with readiness polling and added
  deterministic server shutdown for blocking and non-blocking sessions.
- Added displacement-validated bond neighbor caching, skew-cell-safe bins, and
  direct cylinder instance-buffer updates for dense live bonding.
- Removed one redundant full-trajectory copy during viewer initialization and
  skipped edit-only position snapshots in visualization mode.
- Canonicalized label-based appearance and pairwise bond setting names under
  `v_ase.visual_settings.v3`, with migration for earlier projects/settings.
- Made `view()` default to lightweight visualization mode, matching the CLI;
  interactive mode remains `view(..., viz_only=False)`.
- Removed unused mandatory IPython and Requests dependencies.
- Consolidated API, architecture, performance, shortcut, example, and release
  documentation around the current implementation.
- Added a reproducible 15,000-atom, 16-frame Chromium benchmark.

## 0.0.77

- Added independent multi-document tabs in one desktop workspace.
- Suspended inactive document rendering and movie playback.
- Kept structure, trajectory, calculator, camera, settings, history,
  relaxation, and `.vase` state isolated per document.

Earlier release details remain available in the Git history and PyPI release
artifacts.
