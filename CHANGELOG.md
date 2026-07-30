# Changelog

## 0.0.116

- Added an **Active atom (last selected)** rotation pivot so a selected atom
  can serve as the exact center for mouse and numeric rotations.
- Added `pivot: "active"` to semantic rotation operations, using the last
  explicit atom index as the pivot.
- Re-recorded the Ferrocene workflow with Fe as the active pivot for both Z
  rotation and X-axis ring folding.
- Increased Cu-O bond thickness and applied a high-contrast custom color in
  the Cu2O(111)/Cu(111) README scene while retaining the touching-sphere
  metallic Cu substrate.
- Synchronized README, internal documentation, and the installed agent skill.

## 0.0.115

- Aligned rotation start/current guides to the selected structure's dominant
  in-plane direction, with a unit-cell direction fallback instead of a
  corner-derived diagonal.
- Removed orbit, pan, zoom, axis alignment, and toolbar camera motion from
  `Ctrl+Z`/`Ctrl+Shift+Z`; structure and visualization-setting history remains
  chronological and undoable.
- Renamed the machine-readable automation switch to `--cli` and clarified that
  an external agent launches this local API mode itself; v_ase does not bundle
  an LLM.
- Fixed standalone HTML startup sizing, added a rendered HTML-save preview,
  and validated offline `file://` display, trajectory state, and pointer orbit.
- Updated the Cu2O(111)/Cu(111) bonding example so the Cu(111) substrate uses
  a nearest-neighbor touching-sphere radius.
- Synchronized README, user/developer documentation, and the installed
  vendor-neutral agent skill with the revised behavior.

## 0.0.114

- Replaced the persistent FixedLine dual rails with one radius-scaled center
  axis and added a longer original-position direction guide during `G`.
- Increased ordered-measurement marker and value readability and re-recorded
  the README measurement example at a closer scale.
- Removed documentation-production commentary and unnecessary construction
  details from the public README while retaining the phosphorene and
  Cu2O(111)/Cu(111) user workflows.
- Regenerated the affected README media and synchronized user, developer, and
  agent documentation.

## 0.0.113

- Reworked the README phosphorene manipulation into a shorter, wider `5 x 6`
  ribbon with nine real marquee-selection/Selection-COM edits at the
  paper-tabulated `13.85` degree H-APNR target.
- Added a camera-only above-to-below orbit after the final phosphorene edit so
  the complete three-dimensional deformation remains visible.
- Made the Cu2O(111)/Cu(111) scene's top-site interface registry explicit,
  documented its `6 x 6` primitive oxide mesh on `7 x 7 Cu(111)`, and added
  the DFT top/bridge/hollow interface reference.
- Re-recorded the Cu2O/Cu bond example from a strict top view with the complete
  coincidence cell and pairwise controls in frame.
- Updated README assets, generated examples, scientific regressions, internal
  progress notes, and the vendor-neutral agent skill.

## 0.0.112

- Replaced the simple oxygen-on-Cu bond demo with a generated coherent
  `3 x 3 Cu2O(111) / 7 x 7 Cu(111)` interface, separate substrate/oxide
  labels, and independently controlled oxide and interface Cu-O bonds.
- Added an HTML save choice between a smaller standalone view and a
  project-embedded view with complete `.vase` recovery.
- Split project save into explicit **Save .vase** and **Save HTML** actions.
- Added validated, bounded-memory reopening of project-embedded HTML through
  the CLI, Python viewer, current-tab replacement, trajectory append, and
  multi-tab file workflows.
- Updated the README, internal docs, agent skill, scene assets, and browser
  regressions for the new bond example and project formats.

## 0.0.111

- Replaced the long 11 x 3 phosphorene README ribbon with a compact 8 x 4
  model: the physical width increases, the armchair length decreases, and the
  36-degree target now takes 15 exact 2.4-degree edits instead of 21.
- Regenerated the source CIF, final CIF, trajectory, overview, and live browser
  GIF while preserving the real marquee-selection and Transform-panel workflow.
- Updated README, installed AI skill guidance, and scientific regressions for
  the 16-ridge, 8-atoms-per-ridge construction.

## 0.0.110

- Added **Exact selection rotation** controls to Structure > Transform so a
  selected set can be rotated around X, Y, or Z by a typed angle using the
  existing pivot, ASE constraints, backend commit, and undo history.
- Increased the live left-drag marquee contrast on light and dark viewport
  backgrounds.
- Re-recorded the phosphorene hero through production pointer and form events:
  the visible box selects ridge 2 through the tail, the Transform panel applies
  the exact Selection-COM/X angle, and the boundary advances to ridge 3 before
  continuing through all 21 verified edits.
- Added browser validation for panel-driven rotation commit/undo and capture
  validation for exact selected indices and the final 36-degree target.

## 0.0.109

- Added **Export HTML View**, which creates one offline, view-only 3D document
  with the saved camera, appearance, bonds, constraints, displacement vectors,
  supercell, visual translation, and trajectory playback.
- Embedded the complete validated `.vase` archive inside every HTML View so
  recipients can recover the lossless editable project without the original
  input file or a running v_ase server.
- Inlined the Three.js runtime, renderer, styles, scene data, and project
  archive without CDN or network dependencies.
- Added semantic-agent HTML export support and browser regressions covering
  GUI download, offline `file://` reopening, camera orbit, trajectory
  navigation, view-only controls, and zero network requests.
- Documented the roles and storage tradeoffs of canonical `.vase` projects
  versus shareable standalone HTML views.

## 0.0.108

- Replaced the FixedLine collar/ring marker with a straight axis and two
  compact linear rails. FixedLine and line-like FixScaled now contain no ring
  geometry, while FixedPlane and plane-like FixScaled retain their local ring,
  crosshair, and normal marker.
- Removed the separate billboard selection halo while retaining the yellow
  back-face sphere outline, so selection cannot be confused with FixedPlane.
- Rebuilt the ferrocene manipulation animation to demonstrate both an
  Origin/Z orbit and a Selection-COM/X ring fold in one reproducible workflow.
- Reframed the phosphorene and ordered-measurement media around the complete
  structure and the active geometry, without spending the frame on the control
  panel.
- Replaced the generic bond example with an oxygen-covered Cu(111) slab whose
  label-pair rules explicitly disable Cu-Cu and O-O while enabling Cu-O.
- Extended the natural-language graphene edit through atom creation: the
  verified result now contains a pyridinic N3 vacancy and a `Li_site` atom
  exactly 2.15 A above it.
- Added a vendor-neutral agent setup reference covering Codex, Claude Code,
  ChatGPT desktop agents, Gemini-based agents, agentic IDEs, generic local
  agents, live startup JSON, semantic control, and human handoff.
- Expanded scene, browser, README, and agent-contract regressions for the
  updated scientific workflows and constraint geometry.

## 0.0.107

- Added debounced visual-state history so Ctrl+Z/Ctrl+Shift+Z restores atom
  colors, radii, materials, bonds, lighting, view styling, and export display
  settings without copying large per-atom maps on every input event.
- Replaced repeated image-export completion cycles with one monotonic
  render/capture/encode/write progress bar, an estimated remaining time, and a
  single 100% state after the selected destination is complete.
- Added a semantic AI editing example that builds a pyridinic N3 graphene
  vacancy from an ASE-generated source, verifies the resulting structure, and
  publishes source/result CIF files and current-interface media.
- Added a same-geometry Standard/Metal/Rubber comparison and documented the
  optical meaning of each material without conflating it with ASE chemistry.
- Enlarged and regenerated the FixedLine documentation capture while retaining
  the nanotube channel context.
- Expanded browser, scene-asset, README, and agent-skill evaluation coverage
  for the new workflows.

## 0.0.106

- Replaced the arbitrary 15-degree phosphorene edits with the 36-degree
  H-APNR target tabulated by Jang et al., distributed across the ribbon
  instead of repeated as a per-cell angle.
- Split every armchair unit cell into its two physical puckered sublayer
  ridges, so each edit advances by one 6-atom ridge rather than rotating two
  ridges together.
- Kept the first ridge fixed, removed the initial rigid-body rotation, and
  verified that the final ridge accumulates exactly 36 degrees over 21 edits.
- Styled the upper and lower phosphorus sublayers with the green/purple
  convention used in published phosphorene structure diagrams while
  preserving phosphorus as the ASE chemical element.
- Regenerated the phosphorene example structures, trajectory, README hero, and
  browser-captured manipulation media.

## 0.0.105

- Rebuilt the README around the actual select, move, rotate, measure, and
  analyze workflows instead of presenting finished example files as the main
  manipulation demonstration.
- Replaced the phosphorene hero with cumulative tail selections: every
  15-degree Selection-COM rotation starts from the previously edited
  coordinates.
- Added current-UI ferrocene pivot and graphene/hBN commensurate GIFs, with
  world axes hidden in the latter so start, current, and candidate references
  remain readable.
- Added ordered distance/angle/torsion media and a separate trajectory
  displacement analysis image.
- Added browser regression coverage proving that live View toggles hide and
  restore the world axes and unit cell.
- Updated the agent skill, evaluation gates, and internal progress contract to
  match the published workflows.

## 0.0.104

- Kept every export modal action visible at short viewport heights by making
  the dialog body independently scrollable with a fixed action footer.
- Made PNG the image default and added JPEG and single-page PDF alongside
  lossless WebP, with correct white compositing for opaque formats.
- Rebuilt video timestamps from ordered frame number and selected FPS so
  browser rendering latency cannot cause dropped, duplicated, or shortened
  MOV/AVI playback.
- Added one monotonic video progress indicator across rendering, upload,
  encoding, and file writing, with ETA and 100% reserved for a completed save.
- Recomputed and rendered displacement vectors for every real or interpolated
  video frame.
- Opened files directly into empty documents while retaining the
  Replace/Add/New Tab chooser for populated documents.
- Documented Chrome's unavoidable selected-file permission notice and expanded
  browser, media, and agent-skill regression coverage.

## 0.0.103

- Restored an explicit FixedPlane motion surface during `G`: every constrained
  atom keeps its own original-position plane, perimeter, and in-plane axes
  while ASE remains authoritative for the committed movement.
- Added universal atom-rotation references for the active pivot axis, fixed
  start direction, and moving current direction, while keeping commensurate
  and magnetic candidates visually separate.
- Rebuilt the README around practical use, AI control, structure manipulation,
  measurement, constraints, relaxation, trajectories, and export.
- Added reproducible literature-derived phosphorene nanosheet/nanoribbon CIFs,
  a 15-degree slice-twist trajectory, an ordered ethane measurement scene, and
  an actual ASE FIRE relaxation trajectory for compressed C60.
- Regenerated and visually checked the 1920 x 1080 README media, including the
  FixedPlane motion guide, phosphorene manipulation, commensurate candidates,
  measurement, and relaxation.
- Updated the canonical vendor-neutral agent skill, implementation contracts,
  and browser regression tests for the new guide semantics and examples.

## 0.0.102

- Made whole-scene atom translation a View/Edit visual setting instead of a
  coordinate mutation. Cartesian and fractional offsets are absolute, apply
  after display replication, persist in reusable settings, and leave the cell
  and ASE coordinates unchanged.
- Repeated displacement vectors across the displayed supercell, anchored them
  at each currently visible atom position, and translated both vector
  endpoints with the scene without changing the physical displacement.
- Preserved display replication and visual translation through Reset Coords
  while keeping full Reset authoritative for returning the visual offset to
  zero.
- Simplified pairwise bond specifications to enabled/max-only rows and added a
  user-resizable label-pair column.
- Added browser and export regression coverage for translated replicated
  structures, displacement geometry, settings/project round trips, CAD and
  Blender coordinates, and reset behavior.
- Preserved `close_on_disconnect=False` through workspace lifecycle handling,
  preventing an automatically opened or transient browser tab from terminating
  an API-controlled blocking session.

## 0.0.101

- Restored the approved brown/lime atomistic logo palette while preserving the
  native 6144 x 1890 transparent render and reducing overlap between the
  spheres that form `V_ASE`.
- Increased Hookean helix readability with length-aware coil pitch, a larger
  coil-to-wire ratio, and matching live viewport and Blender geometry.
- Replaced the legacy agent guide with a standards-compliant installable skill,
  one-level progressive references, explicit safety boundaries, trigger
  evaluations, and release-time semantic/rendered end-to-end gates.
- Made the canonical skill discoverable through the AI handshake, live skill
  endpoint, README, wheel, source distribution, and release contract.

## 0.0.100

- Added lossless WebP as the compact image default and losslessly optimized PNG
  output while preserving the requested dimensions and exact RGBA pixels.
- Reduced MOV/AVI storage with quality-based H.264/MPEG-4 profiles without
  resizing rendered frames.
- Replaced the screen-plane Hookean zigzag with a shaded three-dimensional
  helical spring in the live viewport and Blender export.
- Expanded the vendor-neutral AI bridge and installed agent skill to cover
  semantic editing, analysis, camera/quality control, image/video/scientific
  exports, CAD scenes, projects, settings, and multi-document control.
- Replaced the first README figure with a graphene/hBN commensurate rotation
  scene and synchronized all current renderer captures.
- Added a repository release contract that requires README, agent skill,
  rendered assets, GitHub, and PyPI to remain synchronized.

## 0.0.99

- Rebuilt the transparent V_ASE logo with a true native-resolution render:
  `128`-segment spheres fill a `7680 x 2362` WebGL capture before a
  premultiplied-alpha supersample down to `6144 x 1890`.
- Replaced the dark-teal and gold palette with neutral graphite and restrained
  mint, and fixed the physical export scale that previously upscaled a small
  viewport render into a large PNG.

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
