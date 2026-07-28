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
- Reusable presentation preset: visual-settings JSON

`view_edit()` remains a compatibility alias for interactive mode. New examples
and documentation use `view()`.

## Ownership Boundaries

### Python Backend

- `v_ase/io.py`: canonical file-format aliases and structure/trajectory input.
- `v_ase/session.py`: document state, history, calculator-preserving copies,
  trajectory sources, and workspace lifetime.
- `v_ase/server.py`: local FastAPI and WebSocket contract.
- `v_ase/project.py`: visual-settings migration and validated `.vase` archives.
- `v_ase/serialization.py`: browser payloads and ASE visual defaults.
- `v_ase/export.py`: scientific, image-supporting, Blender, 3DM, and OBJ export.
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
21. Pair-specification mode uses explicit label-pair enabled/min/max records.
    These visible records are the sole topology rule in that mode and update
    live without an apply button.
22. Metal materials allocate one shared low-resolution PMREM reflection
    environment on first use. Standard/rubber-only scenes do not pay that
    allocation or preprocessing cost.
23. The control panel has five semantic workspaces: Inspect, Structure,
    Analysis, View, and Export. Appearance and bonding are Structure sections
    because both participate in atom identity and scientific structure
    interpretation.
24. Cartesian or fractional whole-structure translation applies to every
    trajectory frame and never changes the unit cell. Fractional vectors use
    the complete, potentially non-orthogonal cell matrix.
25. Browser history interleaves structural mutations and camera changes.
    `Ctrl+Z` and `Ctrl+Shift+Z` restore the most recent action in chronological
    order, including orbit, pan, zoom, projection, axis alignment, toolbar
    rotation, and atomic-scale camera changes.
26. Native save destinations are selected before export generation begins.
    Canceling the picker must not call structure generation, image rendering,
    video capture/transcoding, or CAD/Blender scene construction. Browsers
    without the File System Access API retain the download fallback.
27. Every browser mutation and structure/CAD export carries the displayed
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
    releases blocking CLI/Python calls after the final page closes. This
    contract applies through SSH local port forwarding as well as localhost.
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
    radius instead of viewport size.
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
43. Commensurate candidates are deterministic cell-boundary matches. The guide
    is enabled by default, magnetic snapping is disabled by default, and neither
    feature depends on the current bond list.
44. `--for-ai` emits one JSON handshake and keeps the same live document
    available for human takeover. Agents obtain semantic structure state over
    HTTP and use `window.v_aseAI` to set frame, display, selection, and camera
    before rendering through the exact Export Image capture path.
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
projects made before enabled/min/max specifications. Loaders migrate it to
`pairwiseBondRanges`, as well as the previous `elementBondCutoffs`, `elementRadii`,
`elementColors`, `elementVisible`, and bond mode `element` names. Saved output
contains only canonical v3 keys.

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
- Visual Settings JSON contains presentation state but no coordinates.
- `.vase` is a validated ZIP archive containing every trajectory frame, current
  frame, edits, cells/PBC, constraints, labels, safe arrays and metadata,
  cached standard results, supported built-in calculator configuration, and
  visual settings. It does not reference the source file.
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
  create a second hidden structure state.

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
   bonds, constraints, preview/export parity, and multiple documents.
5. 15,000-atom browser benchmark with zero idle render frames.
6. Blender runtime and 15,000-atom optimized scene benchmark when Blender is
   available.
7. Rhino export tests in an environment containing `rhino3dm`.
8. Wheel and sdist build, metadata check, clean-environment installation,
   `v_ase --version`, and console entry-point execution.
9. Documentation and displayed/static version synchronization.
10. Headless Linux installation and real browser rendering through the managed
    one-command SSH workflow, including per-frame trajectory transfer and CLI
    release after the browser tab closes.
11. AI handshake, semantic state, deterministic browser control, exact
    lossless WebP/PNG rendering, semantic export, and immediate human takeover
    of the same workspace.

Run installed-wheel verification from outside the repository checkout. The
checkout contains build metadata, so invoking pip from its root can make pip
mistake that metadata for an installed distribution during repeated local
release checks. The complete mandatory publication sequence is maintained in
[release_checklist.md](release_checklist.md).
