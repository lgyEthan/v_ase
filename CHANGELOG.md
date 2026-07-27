# Changelog

## 0.0.85

- Replaced the camera toolbar glyphs with shaded, volumetric curved arrows in
  the established up/down, left/right, counterclockwise/clockwise order.
- Corrected screen-relative clockwise and counterclockwise camera roll.
- Refined automatic bonds using ASE's literature covalent radii with
  chemistry-aware pair classes: metal-metal and H-H contacts stay off by
  default while metal-ligand distances receive a practical coordination range.
- Added a unit-cell-mapped distance for selected supercell replicas and removed
  ambiguous MIC variants from angle and torsion measurements.
- Upgraded Metal to a high-metalness, low-roughness material with one shared,
  on-demand studio reflection environment; Blender, 3DM, and OBJ material
  exports use matching stronger metallic parameters.
- Added Chromium projection, Cu-Cu/Cu-O cutoff, replica-measurement, 15,000-atom
  instancing, and rendered-pixel contrast coverage.

## 0.0.84

- Preserved repeated POSCAR/CONTCAR species blocks as distinct visual labels.
  For example, `O Cu O` with counts `1 14 5` is exposed as `O1`, `Cu`, and
  `O2` while ASE chemical symbols remain `O`, `Cu`, and `O`.
- Numbered every occurrence when a species appears in three or more blocks,
  and handled multiple independently repeated species in their original file
  order.
- Added reader and browser-payload regression coverage for repeated VASP
  species groups.
- Bound local-server release to the acquired server instance so a delayed old
  session cannot stop a newer session when the operating system reuses a port.

## 0.0.83

- Made the default viewport an exact white field with lower-contrast grid
  guides and brighter, view-consistent modeling light for clearer atoms.
- Changed **Open** to begin in the directory where `v_ase gui` was launched,
  with direct local loading and a system-picker fallback for other locations.
- Restricted local browsing and loading to the launch-directory tree, including
  resolved symlink targets, and preserved that root across workspace tabs.
- Added backend path-security, browser Open, visual-state, and regression
  coverage for the new behavior.

## 0.0.82

- Added per-label atom counts after the total for selections of five or more
  atoms.
- Reordered and redrew the camera controls as three paired curved-arrow groups:
  up/down, left/right, and counterclockwise/clockwise roll.
- Corrected view-relative clockwise and counterclockwise camera roll direction.
- Set new-document defaults to `0.60x` atom radius and `0.25 A` bond diameter
  while preserving explicit values from saved projects and settings.
- Added real-Chromium coverage for the new defaults, camera order and direction,
  and multi-label selection summaries.

## 0.0.81

- Made both `Tab` and `Esc` open a collapsed control panel while retaining
  modal close, transform cancel, and open-panel close priorities for `Esc`.
- Added direct-coordinate values alongside minimum-image-convention distances,
  angles, and torsions in the inspector, persistent Measure HUD, and viewport
  measurement overlay.
- Changed new documents to a white viewport background from the first rendered
  frame while retaining the dark background option and saved project choices.
- Added real-Chromium coverage for periodic direct/MIC measurements, the
  two-way `Esc` panel workflow, and white-background initialization.

## 0.0.80

- Added explicit Open actions for replacing the current document, appending
  structures to its trajectory, or opening an independent workspace tab.
- Preserved the active camera, appearance, bonds, lighting, and current frame
  when appending files; `.vase` append imports structures only.
- Added a trajectory-wide label/type catalog so new frame labels immediately
  appear in Appearance and pairwise-bond controls.
- Moved the new-tab button directly after the resizable document tabs.
- Replaced the six camera-step icons with compact curved rotation arrows.
- Added backend, real-Chromium, and multi-document regression coverage for all
  three Open paths.

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
