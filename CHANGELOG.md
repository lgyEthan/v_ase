# Changelog

## 0.0.98

- Re-rendered the shared transparent V_ASE logo at `4800 x 1476` with Ultra
  sphere quality and restored the dark-teal and warm-gold brand palette.
- Added an asset regression check so the documentation and packaged interface
  keep the same native-resolution RGBA logo.

## 0.0.97

- Moved anti-aliasing and atom smoothness into View while keeping label and
  atom appearance controls with Structure.
- Made camera tilt and orbit derive from the live screen basis, including
  arbitrary rolled views and transformed cells.
- Reworked Metal into a stronger shared studio-reflection material and added
  persistent high-contrast atom and bond outlines in flat 2D mode.
- Enabled bonds and the commensurate guide by default, kept magnetic snapping
  opt-in, and verified the exact hexagonal angle family for graphene and h-BN.
- Added editable repulsion cutoff scale and force strength with a `0.70`
  default cutoff scale, plus stable constraint-vector keyboard entry.
- Added `--for-ai`, semantic structure state, deterministic browser control,
  exact renderer output, a machine-readable schema, and an installed
  vendor-neutral agent guide with immediate human takeover.

## 0.0.96

- Rebuilt the transparent rendered V_ASE logo with a dark-teal atom substrate,
  metallic gold lettering, and stronger studio-light definition.
- Made per-atom `FixedLine` and `FixedPlane` guides visible without selection,
  local to each constrained atom, radius-scaled, and consistent in stroke
  weight; FixedLine adds a compact axis collar for visibility at difficult
  camera angles.
- Added unit-cell color, Angstrom thickness, and material controls, using
  deduplicated instanced edges for both the base and repeated supercell cells.
- Tightened the Appearance table proportions, corrected responsive overflow,
  separated translation guidance from its action button, and refreshed common
  control surfaces.
- Reorganized the README around installation and practical workflows, with an
  explicit viewport-focus tip for atom transforms.

## 0.0.95

- Added one-command remote viewing with `v_ase gui HOST:/path`, including
  automatic remote/local endpoint allocation, SSH forwarding, browser launch,
  and cleanup after the browser closes.
- Kept remote source files and backend processing on the server and forced
  trajectory frame streaming so complete trajectory coordinate caches are
  never downloaded to the browser.
- Replaced manual port-forward instructions with the single remote-file command
  and added SSH alias and ProxyJump guidance.

## 0.0.94

- Made automatic loopback-port selection the documented default for remote
  servers and clusters, with fixed ports retained only for scripted mappings.
- Added same-port and alternate-local-port SSH forwarding examples and
  clarified that no administrator port allocation or public listener is
  required.
- Revalidated an automatically selected port with an 18-atom periodic
  structure through a live physics-cluster SSH tunnel and local browser.

## 0.0.93

- Added a first-class remote-server and cluster workflow with loopback-only
  SSH forwarding and direct login-to-compute-node examples.
- Made top-level workspace closure reliable through SSH tunnels by combining a
  per-browser keepalive close signal with WebSocket disconnect detection.
- Preserved multi-browser workspaces when one page closes and added unit,
  Chromium, and live cluster coverage for terminal release after the final tab
  closes.

## 0.0.92

- Added optional `1x`-`64x` linear video-frame interpolation with
  frame-specific cell interpolation and a minimum-image-convention toggle.
- Made browser video capture deterministic by requesting canvas frames
  explicitly and transcoding to the selected FPS and exact output frame count.
- Added WSL-aware Windows browser launch, a headless `--no-browser` workflow,
  and documented secure SSH port forwarding for remote servers.
- Rebuilt the empty white workspace around explicit high-contrast text,
  controls, focus states, and a larger rendered V_ASE mark.
- Added a consolidated user troubleshooting guide for installation, WSL,
  remote servers, file readers, browser sessions, save behavior, and optional
  exports.

## 0.0.91

- Added an Analysis workspace with previous/specific-frame displacement
  vectors, optional MIC, particle-ID mapping, summary statistics, 2D/3D
  styles, and two-batch GPU instancing.
- Preserved valid atom selections and live measurements across trajectory
  frames.
- Made all browser mutations and structure/CAD exports frame-scoped, and
  verified translation, wrapping, repetition, and matrix supercells against
  every frame's own cell and PBC.
- Made View-to-Edit transitions tolerate variable-topology trajectories by
  merging valid identity records and preserving unmatched backend atoms.
- Moved Repulsion calculator controls into Structure > Relaxation, consolidated
  the control panel into one five-workspace tab row, and refreshed the rendered
  V_ASE logo used by the application and package documentation.

## 0.0.90

- Redrew the four 3D camera-orbit controls with continuous hooked silhouettes,
  direction-specific tails, volumetric shading, and the established VESTA
  order; corrected the actual up/down camera directions.
- Consolidated Appearance and Bonds into a scroll-linked Structure workspace
  alongside Cell, Transform, Constraints, and Relaxation.
- Added explicit Cartesian/Angstrom and fractional whole-trajectory
  translation while keeping the unit cell unchanged.
- Extended undo/redo to camera orbit, pan, zoom, projection, toolbar rotation,
  axis alignment, and atomic-scale changes, interleaved with structural edits.
- Moved native destination selection ahead of structure, image, video,
  Blender, Rhino, OBJ, project, and settings export generation.

## 0.0.89

- Redrew the first four camera controls as depth-coded orbit arrows with a
  shaded rear tail, front face, overlap seam, and highlight. Their start and
  end geometry now follows the vertical and horizontal VESTA-style paths
  instead of rotating one flat glyph for every direction.
- Corrected the upward and downward view actions to follow the visible arrow
  direction and retained exact inverse-operation camera recovery.
- Added Chromium coverage for every volumetric icon layer, the distinct
  vertical/horizontal paths, and all six camera operations.

## 0.0.88

- Rebuilt the camera toolbar arrows to match their screen-relative motion,
  including corrected up/down tilt direction and inverse-operation browser
  coverage.
- Split View, Appearance, Bonds, and Export into independent control-panel
  workspaces.
- Replaced single pair cutoffs with live label-pair specifications containing
  enabled, minimum-distance, and maximum-distance fields; removed the separate
  bond apply action.
- Unified viewport, Blender, Rhino, and OBJ automatic bond rules and preserved
  legacy cutoff-only settings alongside the new range format.
- Refreshed the README UI, constraint media, and bond-configuration example.

## 0.0.87

- Made X/Y/Z view toggles compare the complete canonical camera pose, including
  screen-up orientation. Pressing an axis key after rolling that axis view now
  restores its canonical positive view; only another press from that exact pose
  flips to the negative view.
- Added real-browser coverage for canonical restoration and positive/negative
  toggling on all three axes.

## 0.0.86

- Open now invokes the operating system file picker immediately instead of
  showing an intermediate launch-directory file list.
- Added an explicit source/relaxation timeline selector. Playback, Space, and
  Left/Right Arrow stepping target only the selected timeline while the other
  timeline remains visible as a secondary row.
- Added serialized frame stepping so repeated keyboard input cannot race
  asynchronous trajectory loads.

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
