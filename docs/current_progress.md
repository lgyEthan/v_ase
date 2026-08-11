# Current Implementation Contract

This document is the concise implementation source of truth for maintainers.
User-facing behavior belongs in the [README](../README.md); scientific
cell-rotation details belong in
[unit_cell_aware_rotate.md](unit_cell_aware_rotate.md).

## Product Contract

- Distribution: `v_ase-gui`
- Python package and console command: `v_ase`
- Primary Python entry point: `from v_ase.visualize import view`
- CLI entry points: `v_ase gui` and `v_ase gui FILE`
- Default mode: visualization-only
- Editable mode: `--interactive` or `view(..., viz_only=False)`
- Runtime mode switch: top-bar **View / Edit**
- Full project format: `.vase`
- Shareable view format: self-contained view-only HTML with optional `.vase`
  recovery
- Reusable presentation preset: visual-settings JSON

`view_edit()` remains a compatibility alias for interactive mode. New examples
and documentation use `view()`.

## Ownership Boundaries

### Python Backend

- `v_ase/io.py`: canonical file-format aliases and structure/trajectory input.
- `v_ase/volumetric.py`: bounded VASP/Cube/XSF scalar-grid input,
  combinations, repetition, and marching-cubes extraction. Its VASP header
  reader capability-detects ASE's configuration helper at call time and falls
  back to the ASE 3.23/3.24 public POSCAR reader; importing this module must
  never make ordinary structure loading depend on a newer ASE-internal name.
- `v_ase/analysis.py`: triclinic-safe total/partial RDF and CSV.
- `v_ase/add_atoms.py`: deterministic multi-species insertion regions,
  triclinic/Cartesian sampling, temporary-host pairwise repulsion, and exact
  Finish/Cancel reconstruction.
- `v_ase/commensurate.py`: bounded 2D coincidence-cell search, scientific
  notation, common-cell geometry, and one-primitive-cell boundary shells.
- `v_ase/session.py`: document state, history, calculator-preserving copies,
  trajectory sources, and workspace lifetime.
- `v_ase/server.py`: local FastAPI and WebSocket contract.
- `v_ase/project.py`: visual-settings migration, validated `.vase` archives,
  and bounded extraction of project-embedded HTML.
- `v_ase/serialization.py`: browser payloads and ASE visual defaults.
- `v_ase/export.py`: scientific, image-supporting, Blender, 3DM, OBJ, and
  standalone offline HTML export with optional project recovery.
- `v_ase/ai.py`: vendor-neutral AI handshake and installed agent guide.
- `v_ase/viewer.py`: Python API and local server lifecycle.

### Browser Frontend

- `static/main.js`: application state, UI workflows, API orchestration, and
  trajectory playback.
- `static/renderer.js`: Three.js scene, camera, instancing, bonds, constraints,
  supercells, lighting, measurements, and capture.
- `static/selection.js`: click and box-selection hit testing.
- `static/transform.js`: modal move/rotate state.
- `static/trajectory.js`: video-frame count and Cartesian/MIC interpolation.
- `static/api.js`: typed local HTTP payload handling and download helpers.
- `static/workspace.js`: independent multi-document shell.

## Core Invariants

1. The caller's original `Atoms` object is never mutated.
2. Structural edits use a working copy and preserve supported calculators.
   Add Atoms additionally keeps an immutable pre-session baseline; temporary
   host `FixAtoms` exists only on its detached optimization copy and never
   mutates document constraints, arrays, labels, calculators, or host
   coordinates. Cartesian insertion boxes may be allowed or prohibited,
   default to post-scatter escape, translate with `G`, and reject `R`.
3. ASE is authoritative for constrained commits:
   `Atoms.set_positions(..., apply_constraint=True)`.
4. Browser previews may be immediate, but committed coordinates return from the
   backend.
5. Left drag is box selection; middle drag is unrestricted orbit.
6. Renderer inertia/damping is disabled.
7. Visualization mode does not attach the fallback calculator or maintain
   interactive edit history it cannot use.
8. Interactive supercell replicas are display-only until committed as the
   current cell; visualization-mode replicas remain selectable and measurable.
9. Label identity and chemical TYPE are independent. Labels key appearance,
   selection, and pair specifications; ASE chemical symbols control element
   defaults and calculations.
10. View uses label-level visual state. Edit may add per-atom material
    overrides. Returning to View converts only distinct material variants into
    stable numbered labels; coordinate-only differences never split a label.
11. Entering Edit materializes a lazy trajectory into complete ASE frames
    before edits are enabled. The current frame, coordinates, labels,
    constraints, and calculators remain synchronized.
    Random batch insertion is intentionally rejected while a source contains
    multiple frames; the user must open the target frame in a separate
    document so a single-frame structural edit cannot masquerade as a
    trajectory-wide edit.
12. Settings survive structure refreshes and trajectory changes. Ordinary file
    replacement reconciles the active visual state; `.vase` replacement
    restores it.
13. Demand rendering must remain idle when camera, structure, playback, and UI
    are unchanged.
14. Appending files extends the current trajectory without changing its active
    visual state. The trajectory-wide label/type catalog is authoritative for
    Appearance and pair-specification controls, including labels absent from the
    current frame.
15. Opening in a new workspace tab creates a separate backend session. Opening
    `.vase` this way restores the complete project; appending `.vase` imports
    only its selected structure frames.
16. New documents start with orthographic projection and a white viewport.
    Ordered two-atom measurements report direct and minimum-image distances.
    If a visualization replica is selected, a third unit-cell-mapped distance
    is shown. Three- and four-atom angles/torsions use displayed coordinates
    without a second MIC result.
17. New documents start with `0.60x` atom radius and `0.25 A` bond diameter.
    Explicit project and reusable-setting values override these defaults.
18. Five-or-more selection summaries retain the total and append counts in
    stable first-seen label order.
19. Browser Open invokes the operating system picker directly. If source and
    relaxation trajectories coexist, the explicit timeline selector determines
    which source receives playback, Space, and Left/Right Arrow navigation;
    the inactive timeline remains visible in a second row.
20. The default viewport clear color is exact white. Modeling lights lift atom
    midtones consistently without allocating rendered-mode shadows, and the
    white-background grid remains low contrast.
21. Pair-specification mode uses explicit label-pair enabled/max records.
    These visible records are the sole topology rule in that mode and update
    live without an apply button. Legacy minimum values normalize to zero.
22. Metal materials allocate one shared low-resolution PMREM reflection
    environment on first use. Standard/rubber-only scenes do not pay that
    allocation or preprocessing cost.
23. The control panel has five semantic workspaces: Inspect, Structure,
    Analysis, View, and Export. Appearance and bonding are Structure sections
    because both participate in atom identity and scientific structure
    interpretation.
24. Physical Cartesian or fractional `translate-all` applies to every
    trajectory frame and never changes the unit cell. Fractional vectors use
    the complete, potentially non-orthogonal cell matrix.
25. Browser history interleaves structural mutations and visual settings.
    `Ctrl+Z` and `Ctrl+Shift+Z` restore the most recent action in chronological
    order, including projection, atomic scale, appearance, bonds, lighting,
    and view styling. Orbit, pan, zoom, axis alignment, and toolbar camera
    rotation are deliberately excluded, so geometry undo is never buried
    behind navigation steps. Continuous visual inputs are debounced into one
    action and snapshot only after the edit settles, avoiding per-event copies
    of large atom-material maps.
26. Native save destinations are selected before export generation begins.
    Canceling the picker must not call structure generation, image rendering,
    video capture/transcoding, or Blender/3D scene construction. Browsers
    without the File System Access API retain the download fallback. Image
    export uses one monotonic render/capture/encode/write progress sequence,
    reports ETA, and emits 100% only after the selected file is complete.
27. Every browser mutation and structure/3D-scene export carries the displayed
    `frame_index`. The backend synchronizes that frame before consuming
    coordinates, constraints, labels, calculator state, or export payloads.
28. Trajectory-wide physical operations validate and transform every frame
    using that frame's own cell and PBC. Fractional translation, wrapping,
    diagonal repetition, and matrix supercells never copy the active frame's
    lattice onto another frame.
29. Base-atom selection survives trajectory frame changes and is pruned only
    when an index is absent or hidden. Measurements update against the newly
    displayed coordinates without requiring reselection.
30. Displacement analysis maps common unique particle IDs when available and
    otherwise uses stable indices only for equal-size frames. Unequal
    topologies without IDs are rejected instead of fabricating a mapping.
    MIC uses the current frame's cell/PBC and is explicit in the result.
31. Video interpolation is export-only and never mutates the source trajectory.
    `1x` preserves one output frame per source frame; `Nx` emits
    `(source_frames - 1) * N + 1` frames. MIC interpolation uses both adjacent
    cells, their shared periodic axes, and wrapped fractional coordinates.
    Manual canvas capture plus explicit transcoder FPS/frame-count settings
    prevent refresh-rate-dependent duplicates.
32. WSL browser launch bypasses Linux `gio` and prefers `wslview` or Windows
    executables. Headless operation can suppress automatic launch while keeping
    the HTTP server loopback-only.
33. Each top-level workspace page owns a unique browser-client identifier.
    Page teardown sends a keepalive close signal in addition to closing its
    WebSocket. The backend ignores stale sockets belonging to closing pages,
    preserves a workspace while any other browser client remains active, and
    releases blocking CLI/Python calls after the final page closes.
    `close_on_disconnect=False` explicitly opts API sessions out of workspace
    autoclose. This contract applies through SSH local port forwarding as well
    as localhost.
34. CLI sessions select an unused loopback port automatically when `--port` is
    omitted. No public listener or administrator-assigned port is required.
35. An scp-style `HOST:/path` input makes remote use a one-command workflow.
    The local launcher starts remote v_ase, allocates both private endpoints,
    creates and monitors the SSH tunnel, opens the local browser, and cleans up
    both SSH processes when the browser closes.
36. Remote sessions force frame streaming for every trajectory size. Source
    files, ASE objects, and full trajectory caches stay on the server; the
    browser receives the current frame only.
37. `FixedLine` and `FixedPlane` guides are persistent per-atom overlays. They
    remain visible without selection, stay local to each constrained atom, are
    depth-tested against the structure, and scale from the displayed atom
    radius instead of viewport size. FixedLine uses one straight axis through
    the atom center without any ring; FixedPlane uses a local ring, crosshair,
    and normal. Line-like and plane-like FixScaled constraints inherit those
    respective designs. During `G`, a selected FixedLine atom gets one longer
    original-position direction guide, while each selected FixedPlane atom
    gets its own low-opacity guide surface, perimeter, and crosshair. Motion
    guides clear on commit or cancel.
38. Unit-cell edges use one instanced cylinder primitive in the viewport and
    expose color, Angstrom thickness, and material controls. Supercell previews
    reuse the same style and deduplicate shared edges so repeated cells do not
    become darker at overlaps.
39. New documents show bonds by default. Explicit projects, reusable settings,
    and `--hide-bonds` override this default without changing bond topology.
40. Anti-aliasing and atom smoothness are viewport-quality controls under View.
    Label radius, color, visibility, chemical TYPE, label text, and material
    remain under Structure > Atoms & Appearance.
41. Camera toolbar tilt and orbit use the camera world quaternion to derive
    screen right, up, and forward. Their meaning stays screen-relative after
    cell transforms, axis views, roll, and arbitrary camera motion.
42. Repulsion configuration is calculator state, not display state. Its default
    pair cutoff scale is `0.70`, strength is user-configurable, and both values
    survive working-frame and trajectory calculator copies.
43. Commensurate candidates are deterministic cell-boundary matches. The
    workspace and magnetic snapping are both disabled by default, and neither
    feature depends on the current bond list. Enabling the workspace starts the
    bounded search immediately and reports staged progress.
44. `--cli` is a terminal-oriented API mode, not an embedded AI model. An
    agent invokes it itself, parses the first-line JSON handshake, and consumes
    later revisioned NDJSON events. Agents obtain semantic structure state over
    the loopback HTTP JSON bridge and use `v_ase api` with `command_url` to set
    frame, display, selection, structure, and camera before rendering through
    the exact Export Image capture path. `human_url` is the same live document,
    so human GUI refinements are emitted back to the CLI rather than requiring
    a separate takeover copy. Page-main-world JavaScript access is optional.
    v_ase does not parse natural language or stdin commands; the external agent
    translates the user's request into structured semantic calls.
    User documentation presents this as a cycle centered on v_ase: structured
    commands and GUI edits enter v_ase, while the live GUI and exact
    state/revision leave v_ase through separately labeled arrows.
    `v_ase api ... schema` exposes the live apply schema plus operation/export
    parameter maps without a browser round trip; `describe` reports whether a
    calculator is attached and identifies it.
45. Image storage optimization is post-render only. Lossless WebP and optimized
    PNG preserve the requested dimensions and exact RGBA pixels; PNG keeps the
    browser source when recompression is not smaller.
46. Hookean active-state geometry is a shaded three-dimensional helix in both
    the live viewport and generated Blender scene. Cutoff and inactive-gap
    graphics remain separate so the physical threshold is readable.
47. The installed vendor-neutral agent contract is the canonical
    `v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md`, with
    one-level progressive references. Every release validates metadata,
    trigger cases, semantic capability parity, browser end-to-end workflows,
    rendered output, README, GitHub, and PyPI together.
48. Cartesian or fractional visual translation is an absolute display setting
    available in View and Edit. It is applied after display supercell
    repetition to atoms, bonds, constraints, selections, and analysis
    overlays, while the ASE coordinates and cell remain unchanged. Visual
    Settings and `.vase` preserve it; Reset Coordinates preserves it; full
    Reset returns it to zero.
49. Displacement vectors keep their physical backend values, begin at each
    currently visible atom position, and repeat over every displayed
    supercell image. Visual translation moves both endpoints equally.
50. Every atom rotation shows the active pivot axis, a fixed neutral start
    reference, and an amber current reference. The current reference follows
    the actual free or axis-locked rotation sign. Commensurate/magnetic
    candidates remain separate cyan guides and never replace or duplicate the
    start reference.
51. README scientific scenes are generated from canonical Python constructors
    and captured from the real browser UI. The phosphorene hero records
    actual pointer-down/move/up marquee selection from ridge 2 through the
    tail, the exact-rotation panel's Selection COM/X/angle controls, and the
    repeated marquee advanced to ridge 3. Successively shorter tail selections
    remain separated by one physical puckered sublayer ridge. The first ridge
    stays fixed and 9 constraint-aware backend commits on a short, wide 5 x 6
    ribbon accumulate the paper-tabulated 13.85-degree H-APNR target at the
    final ridge. A final camera-only orbit moves from above the edited ribbon
    to below it. Upper/lower ridges use green/purple visual labels while both
    remain ASE phosphorus.
    Ferrocene demonstrates Z and X rotations around a central Fe selected as
    the active last-selected atom. Graphene/hBN shows
    start/current/commensurate references with world axes hidden, ordered
    ethane selection shows distance/angle/torsion in a viewport-only crop, and
    a separate trajectory scene shows displacement analysis. The bonding scene
    is a top-view, top-registered 6 x 6 primitive Cu2O(111) mesh on 7 x 7
    Cu(111). Dark metallic substrate Cu, bright standard oxide Cu, and matte
    red O separate the phases; Cu-O bonds use split endpoint colors while
    every Cu-Cu/O-O pair remains disabled. Tests validate the -1.22% coincidence
    strain, explicit
    interfacial O/Cu top anchor, all nine coincidence phases, scene
    construction, and live View toggles before media are published.
52. Export dialogs use a fixed action footer and independently scrollable body.
    Cancel and Export therefore remain visible at short desktop viewport
    heights while all render controls remain reachable.
53. PNG is the image-export default. JPEG, single-page raster PDF, and lossless
    WebP are explicit alternatives; opaque formats flatten transparency onto
    white without changing dimensions.
54. Video capture preserves ordered source samples and transcoding rebuilds
    constant timestamps from output frame number and selected FPS. Rendering,
    upload, encoding, and destination writing share one monotonic progress/ETA
    display; 100% means the file write completed. Displacement vectors are
    recomputed before every captured real or interpolated frame.
55. File Open directly replaces an empty document. Replace/Add/New Tab choices
    appear only when the active document already contains atoms.
56. The bundled agent skill is vendor-neutral. Codex, Claude Code, ChatGPT
    desktop agents, Gemini-based agents, agentic IDEs, and other local agents
    receive the same canonical `SKILL.md`, agent setup reference, task-specific
    references, and `--cli` startup JSON. Documentation never relies on a
    vendor-specific directory unless that client explicitly supports one.
57. Selection keeps the required yellow sphere outline but has no separate
    billboard halo ring. FixedPlane and plane-like FixScaled are the only
    directional constraints that use local ring geometry.
58. Collaboration uses `v_ase.collaboration.v1`. Each document has a bounded
    revisioned event history; each workspace merges all tab events while
    retaining `session_id` and `document_revision`. Browser-originated human,
    agent, and system changes are coalesced after commit and contain compact
    categories/paths rather than coordinates. `describe()` reports the current
    document revision, and `apply(expectedRevision=...)` rejects stale agent
    commands before they can overwrite a newer human edit.
59. Volumetric datasets are backend-owned, explicitly selected FP32 or FP64
    grids with stable IDs, cell, origin, PBC, endpoint convention, quantity,
    component, and units. VASP
    CHGCAR/CHG, LOCPOT, PARCHG, and ELFCAR plus Cube and XSF are accepted only
    after bounded shape, size, finiteness, and nondegenerate-cell validation.
    The first/newest imported grid is shown immediately at a valid default
    level; color and opacity edits update the existing browser mesh live.
    Optional Gaussian field smearing uses wrap boundaries on periodic axes and
    reflect boundaries elsewhere without mutating the stored grid. Independent
    boundary-preserving mesh fairing reduces voxel stair-steps after marching
    cubes. Both stages are explicit, bounded, persisted display settings and
    can be disabled with zero. Semantic state reports the rendered levels,
    mesh/triangle counts, post-smearing range, and partial signed-surface
    status without transmitting the source grid. The Volumetric Data panel
    separates isosurfaces, cell-clipped hkl planes, and field arithmetic.
    View mode edits plane hkl and signed grid-origin distance without changing
    ASE coordinates; Edit-mode G/R transforms synchronize the visible distance
    and hkl controls live. Selected-plane previews and settled renders request
    only the affected compact 2D rasters.
60. Volumetric combinations require identical dimensions, cell, origin, PBC,
    endpoint convention, and scalar units. Display repetition and visual
    translation transform the extracted mesh with atoms. A physical diagonal
    supercell repeats grid and atoms atomically; reset, undo, and redo restore
    the corresponding atom/grid state together. A non-diagonal materialized
    transform is rejected while a grid is loaded.
61. Bulk RDF requires full 3D PBC. The unique-MIC radius remains the automatic
    default, while explicit larger cutoffs enumerate every periodic image
    inside the requested sphere instead of assuming a fixed `2 x 2 x 2`
    repetition. Total and concentration-weighted visual-label partial curves
    share one ASE periodic neighbor search and reconstruct the total through
    the standard concentration-weighted relation. The Plotly view includes a
    `g(r) = 1` bulk-limit reference and the generated amorphous regression
    reaches a statistically flat long-range plateau.
62. `describe().analysis` and live capability discovery are authoritative for
    volumetric dataset IDs, RDF cutoffs/warnings, and partial curve names.
    Agents never receive the complete scalar grid or infer analysis from
    screenshots.
63. Commensurate matching is opt-in and defaults off. It is restricted to two
    in-plane periodic vectors and global-Z guest rotation. Enabling it searches
    integer host/guest supercells up to the configured area ratio (default
    `16`, explicit maximum `128`) and maximum-principal-strain cutoff, then
    proposes the smallest admissible common cell.
    Same-lattice twist uses a selected rotating layer; host/guest mode loads a
    separate guest structure and can place residual in-plane strain on the
    guest (default) or host. Cells-only preview is the default. Optional atoms
    expand both opaque parent lattices by at least two primitive shells when
    the preview budget permits. Host and guest bonds are inferred independently
    and cross-component bonds are excluded. The proposal is independent of display replication and
    manual Cell Transform, and it becomes ASE state only after the explicit
    **Set Suggested Cell as Structure** action. Trajectories and active
    volumetric fields remain preview-only. The server recomputes integer
    matrices, affine maps, and constraint remapping before materialization.
64. The commensurate Plotly drawer provides a 3D overview using angle, maximum
    host/guest area ratio, and active-target maximum principal strain. It uses
    discrete candidate points, a gridded angle-area floor, a moving current-angle
    plane, and dotted equivalent-angle guides only for exact lattice symmetry,
    plus a
    paper projection using mean absolute strain versus actual common-cell atom
    count. Both views share one accepted candidate set. A live angle plane and
    nearest-candidate marker follow guest rotation. Its icon-only CSV export
    retains both strain definitions, atom counts, integer matrices, and paper
    metadata. A deterministic graphene/Cu(111) host/guest fixture and complete
    numerical validation are provided under `examples/commensurate_host_guest`
    and `docs/commensurate_validation.md`.
    Planar Translation constructs a primitive periodic lattice in any compatible
    `(hkl)` plane. Its optional map scans a selected rigid component over one
    complete plane cell with either a short-contact or enabled-pair bond-strain
    geometry score. Live `G` motion is projected into the same plane, the cell
    and component internal vectors remain fixed, and CSV export includes the
    exact integer and Cartesian bases. These scores are geometry screens, not
    energies. A separate calculator-driven mode optimizes exactly two rigid
    plane coordinates, reports projected net selected force in eV/Angstrom,
    owns a temporary timeline, commits as one undo step, and cancels to the
    exact baseline.
65. Workspace activation and browser resizing update the camera-signature
    baseline but are not collaboration edits. A `describe()` revision is not
    invalidated by iframe activation or framebuffer aspect changes; deliberate
    human camera controls continue to publish revisioned camera events.
66. Source, structure-relaxation, Add Atoms placement, and rigid planar timelines
    have explicit owners. Closing a mode removes only its temporary optimizer
    timeline; commit/cancel behavior remains operation-specific.

## Canonical Names And Compatibility

Visual settings use schema `v_ase.visual_settings.v3`.

Canonical display keys:

- `pairwiseBondCutoffs`
- `pairwiseBondRanges`
- `labelRadii`
- `labelColors`
- `labelVisible`
- `labelMaterials`
- `atomMaterials`
- bond mode `pairwise`

`pairwiseBondCutoffs` remains a maximum-distance compatibility mirror for
projects made before enabled/max specifications. Loaders migrate it to
`pairwiseBondRanges`, as well as the previous `elementBondCutoffs`, `elementRadii`,
`elementColors`, `elementVisible`, and bond mode `element` names. Saved output
contains only canonical v3 keys. Legacy pair minimums are accepted but
normalized to zero.

Canonical Python label helpers are `atom_labels()` and `set_atom_labels()`.
`atom_type_labels()`, `set_atom_type_labels()`, and `ATOM_TYPE_ARRAY` remain
compatibility aliases for code written against v_ase 0.0.77 or earlier.

POSCAR/CONTCAR species headers are also part of label identity. If one element
appears in multiple species blocks, each occurrence receives an ordered visual
label (`O1`, `O2`, ...), while the ASE atomic numbers and symbols remain
unchanged.

Canonical atom-identity route:

```text
POST /api/atom-identity/{session_id}
```

The old `/api/atom-types/{session_id}` route remains hidden and forwards to the
same implementation for compatibility.

## Data And Save Contracts

- ASE Pickle contains the current `Atoms`, labels, constraints, portable arrays,
  and valid `SinglePointCalculator` results. It excludes visual state and
  arbitrary executable calculators.
- Portable Visual Settings JSON contains presentation state but no coordinates.
- Personal visual defaults persist reusable startup styling per OS user; they
  exclude coordinates, trajectory data, cell contents, absolute camera
  placement, and per-atom overrides. Restore requires explicit confirmation.
- The interface theme defaults to System and follows the browser/OS light-dark
  preference; explicit Light/Dark choices are browser-persistent and do not
  change the viewport background.
- `.vase` is a validated ZIP archive containing every trajectory frame, current
  frame, edits, cells/PBC, constraints, labels, safe arrays and metadata,
  cached standard results, supported built-in calculator configuration, and
  visual settings. Volumetric grids are compressed bounded NPZ members with
  expected arrays and no executable pickle payload. The project does not
  reference the source file.
- Standalone HTML export embeds browser-ready scene data and all runtime assets.
  Lightweight HTML omits `.vase` by default; **HTML Project** embeds the
  validated archive by default. Both use the exact image/video Preview Area
  camera crop, include an optimized high-resolution Finder/Quick Look poster,
  open from `file://`, provide view navigation and trajectory playback only,
  and make no network request. The poster is the complete initial preview
  surface with no application chrome; it shares one fixed rectangle with the
  live device-resolution canvas and cross-fades automatically after the first
  live frame, before camera input, without a layout change.
- Jupyter display is process-local and switchable with `%v_ase inline`,
  `%v_ase browser`, and `%v_ase auto`. Per-call `notebook="inline"` /
  `"browser"` values override the current preference.
- Browser Open keeps visual state for ordinary structures and trajectories.
  Opening `.vase` restores the project state instead.
- Browser Open uses the native operating system picker and streams the selected
  file into the local session.
- Browser **Add to trajectory** appends the selected structure frames and
  intentionally ignores `.vase` visual settings.
- Browser **Open in new tab** uploads into a newly created, independent session
  before making that tab active.
- Video interpolation settings are reusable visual state. Interpolated
  coordinates are temporary render samples and are excluded from `.vase`, ASE
  Pickle, and the source trajectory.
- The AI state endpoint is read-only and current-frame scoped. Browser-side AI
  mutations use the same validated UI/backend paths as human actions and never
  create a second hidden structure state. The CLI's post-handshake NDJSON stream
  reports committed GUI/agent changes and requires semantic re-synchronization;
  it is not a command channel. Commands use the separate loopback
  `command_url`; `v_ase api` sends JSON through WebSocket to the live browser
  and returns the browser result over HTTP.

## Performance Contract

- Atoms, bonds, selections, and supercell replicas use GPU instancing.
- Displacement arrows use two instanced batches: one shaft and one head batch,
  independent of atom count.
- The renderer is request-driven and has no permanent animation loop.
- Large numeric LAMMPS dumps are memory-mapped and byte-offset indexed.
- Compatible trajectories are transferred once as contiguous float32
  coordinates for playback.
- Position-only frame updates modify instance translation columns rather than
  rebuilding geometry or complete matrices.
- Auto and pairwise bonds use a cell-list search with a displacement-validated
  neighbor candidate cache for large structures.
- Bond cutoff checks remain live each frame; cylinder instance matrices are
  written directly into GPU buffers.
- Supercell boundary topology is inferred once per update and reused for direct
  and replica-bridge bonds.
- Modeling mode allocates no shadow map; rendered lighting cost is opt-in.
- Material presets reuse cached `MeshPhysicalMaterial` and instanced groups;
  the default one-label/one-material scene remains one atom draw group.
- Hidden displacement analysis performs no backend calculation and allocates
  no arrow meshes. Color, thickness, scale, and 2D/3D restyling reuse the
  latest vectors without repeating the backend calculation.
- Hidden volumetric surfaces allocate no browser geometry. The full bounded
  FP32 or FP64 grid stays in Python; the browser receives only descriptors and
  the requested indexed isosurface. Marching cubes and RDF run off the event
  loop.
- Total and selected partial RDF curves share one periodic neighbor-list pass.
  The local Plotly drawer is created only when RDF is requested.
- Inactive workspace tabs suspend rendering and playback.
- Local servers use readiness polling and are stopped/joined by their owning
  editor or blocking session. Release is lease-bound so a delayed prior session
  cannot stop a newer server that reused the same port number.

Current benchmark method and results are in [performance.md](performance.md).

## Validation Before Release

1. `python -m compileall -q v_ase tests scripts`
2. JavaScript syntax checks for every first-party module.
3. Full `pytest` suite.
4. Real Chromium browser workflows, including large trajectories, supercells,
   bonds, constraints, volumetric surfaces, RDF/CSV, same-lattice and
   independent-host/guest common cells, planar translation maps, preview/export parity,
   and multiple documents.
5. 15,000-atom browser benchmark with zero idle render frames.
6. Blender runtime and 15,000-atom optimized scene benchmark when Blender is
   available.
7. Rhino export tests in an environment containing `rhino3dm`.
8. Wheel and sdist build, metadata check, clean-environment installation,
   `v_ase --version`, console entry-point execution, and an import plus VASP
   scalar-grid read against the declared minimum/legacy ASE compatibility
   range.
9. Documentation and displayed/static version synchronization.
10. Headless Linux installation and real browser rendering through the managed
    one-command SSH workflow, including per-frame trajectory transfer and CLI
    release after the browser tab closes.
11. AI handshake, a separate `v_ase api` subprocess, workspace NDJSON
    collaboration events, stale-revision rejection, semantic state,
    deterministic browser control without main-world evaluation, exact
    lossless WebP/PNG rendering, semantic export, and concurrent human
    refinement of the same workspace.

Run installed-wheel verification from outside the repository checkout. The
checkout contains build metadata, so invoking pip from its root can make pip
mistake that metadata for an installed distribution during repeated local
release checks. The complete mandatory publication sequence is maintained in
[release_checklist.md](release_checklist.md).
