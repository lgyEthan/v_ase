---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible structures, trajectories, volumetric fields, isosurfaces, and RDF data through its CLI and live HTTP JSON API. Use when a user needs atomistic visualization, DFT grid analysis, structure measurement, periodic-cell operations, constraints, trajectory movies, publication rendering, reusable 3D export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic HTTP JSON commands. Do not infer scientific state from screenshots when `describe` provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Install the tested release:

```bash
python -m pip install "v_ase-gui==0.2.31"
```

Start the terminal-oriented API session yourself:

```bash
v_ase gui --cli
v_ase gui STRUCTURE --cli
v_ase gui STRUCTURE --interactive --cli
```

The filename-free form opens a scratch document directly in Edit. Use the combined
file form for physical atom edits while retaining the structured CLI/API bridge and the same human GUI.

This is a persistent server/event-stream process, not a finite command. Start
it with the agent runtime's long-running process facility. As soon as the
runner yields the first output or a process/session handle, read the first
stdout line and continue with separate `v_ase api` commands; do **not** wait
for `v_ase gui ... --cli` to exit. Keep its handle so stdout events can be
polled and terminate it only after verification and handoff are complete.

The user gives natural-language instructions to the external agent, not to
v_ase. `--cli` does not contain an LLM, parse natural language, or accept
commands from stdin. It launches the normal local v_ase application without
opening a browser and exposes a structured loopback API.

Read the first stdout line as JSON. Keep the process running in its persistent
session and continue reading stdout as NDJSON without blocking other commands.
The handshake contains:

- `human_url`: the same regular GUI for human watching and refinement;
- `state_url`: read-only current semantic state;
- `events_url`: long-polled human/agent change stream;
- `event_protocol`: `v_ase.collaboration.v1`;
- `event_delivery`: `ndjson-after-handshake`;
- `event_scope`: `workspace` or `document`;
- `schema_url`: JSON Schema for `apply()`;
- `skill_url`: this canonical skill;
- `command_url`: HTTP JSON endpoint for the same live workspace;
- `command_methods`: supported semantic methods;
- `command_transport`: `http-json-bridge`;
- `browser_api`: optional in-page fallback, `window.v_aseAI`;
- `accepts_natural_language`: `false`;
- `stdin_commands`: `false`;
- `skill_path`: the installed canonical `SKILL.md`.

Open `human_url` in a browser and wait for the viewport to load. Then call the
live API from another terminal:

```bash
v_ase api "$COMMAND_URL" ready
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" capabilities
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'
```

No API key or external service is required. The loopback URL contains a session
identifier; do not publish it while a private structure is open.
The `v_ase api` command accepts structured JSON only. It is not an LLM and does
not accept natural-language instructions.

The shared document has three required bidirectional links:

```text
user <-> external agent       natural-language request and feedback
external agent <-> v_ase CLI structured operations, exact state, revisions
user <-> v_ase GUI           live inspection and direct visual refinement
```

Treat all three links as a required feedback cycle, not a one-way handoff.
Every Agent command must become visible in `human_url`. Every later human GUI
edit must be consumed as a revision event, followed by a fresh `describe`
before the Agent sends another mutation.

Use the `describe` method with `{"includePositions":false}` for compact metadata
inspection and request full positions only when coordinate-dependent work
requires them.
This avoids repeated screenshot interpretation and can reduce context/token
use. Rendered pixels remain the final authority for visual-quality checks.

## Required Workflow

Use this sequence for every task:

1. **Connect**: parse the handshake, keep consuming later NDJSON events, and
   open `human_url` so the human and agent share one live document.
2. **Plan**: call `schema`, `capabilities`, and `describe`; identify the document,
   frame, atom indices, labels, elements, cell, PBC, constraints, and camera; preserve ordered VASP labels such as `O_1`/`O_2` while verifying their ASE element separately.
   Require `capabilities.operations` to equal the keys of
   `schema.operation_parameters` and `capabilities.exports` to equal the keys
   of `schema.export_parameters`. Stop on a mismatch because the installed
   Python package and browser assets are not synchronized.
3. **Validate**: confirm atom count and topology before reusing indices. Confirm
   Edit mode before physical changes.
4. **Execute**: apply one semantic change at a time with the latest
   `collaboration.revision` as `expectedRevision`.
5. **Synchronize**: on a human event, pause mutations, activate its document,
   call `describe`, and preserve the newer human change.
6. **Verify**: call `describe` after every structure, trajectory, constraint,
   selection, or camera change.
7. **Render**: call `render` at the requested dimensions with `--save`. Inspect
   the returned dimensions, options, byte count, and decoded image.
8. **Export**: call `export` only after state and camera verification. Use
   `--save OUTPUT` for results containing a `dataUrl`.
9. **Collaborate**: keep `human_url` and the event stream active while the user
   wants to watch or refine the result.

Do not report completion when only an HTTP response succeeded. Verify the
resulting semantic state and rendered output.

## Degrees Of Freedom

- **Low freedom**: deletion, identity/element changes, constraint edits,
  materialized supercells, volumetric linear combinations, relaxation and its repulsion cutoff definition,
  overwrite-prone exports, deleting a saved personal visual default, and
  release publishing. Use exact documented commands and verify afterward.
- **Medium freedom**: camera placement, bond cutoffs, materials, lighting,
  per-atom colorscale field/range/map, displacement/RDF parameters, bounded
  commensurate search limits, planar-translation `(hkl)`/grid/metric selection, isovalue and
  surface styling, interpolation, and rendering quality. Start with the
  documented templates, then tune against the requested result.
- **High freedom**: choosing a visually clear viewpoint, palette, or
  composition when the user has not specified one. Preserve scientific
  identity and disclose aesthetic choices.

## Semantic Command Map

Choose commands by scientific task, then read the corresponding one-level
reference before executing a multi-step workflow:

| Task | Primary state or operation |
| --- | --- |
| Inspect and measure | `describe`, `selection`, ordered `measurement`, lazy single-atom properties |
| Edit or build a structure | `set-unit-cell`, `build-bulk`, `move-selection`, `rotate-selection`, `scale-selection`, `add-atom`, `scatter-atoms`, `scatter-molecules`, constraints |
| Work with periodic interfaces | display replication, cell transforms, commensurate search, rigid `(hkl)` translation |
| Analyze trajectories | frame selection, displacement, RDF, colorscale, stored force vectors |
| Analyze scalar fields | volumetric datasets, isosurfaces, planes, field combinations |
| Style and render | `display`, `quality`, `camera`, persistent `renderArea`, `render` |
| Save or share | `export`, compact `.vase`, portable HTML projects, media, and geometry formats |

### Live Methods

The HTTP bridge has seven document methods:

```bash
v_ase api "$COMMAND_URL" ready
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" capabilities
v_ase api "$COMMAND_URL" describe --params '{"includePositions":true}'
v_ase api "$COMMAND_URL" apply --params-file command.json
v_ase api "$COMMAND_URL" render --params-file render.json --save preview.png
v_ase api "$COMMAND_URL" export --params-file export.json --save result.html
```

Workspace pages additionally support:

```bash
v_ase api "$COMMAND_URL" documents
v_ase api "$COMMAND_URL" activate --params '{"sessionId":"SESSION_ID"}'
v_ase api "$COMMAND_URL" newDocument
```

The `apply` method accepts `frame`, `mode`, `display`, `quality`,
`applyConstraints`, `camera`, `renderArea`, `selection`, and `operation`. Query `schema`
and `capabilities` instead of assuming that a command or parameter exists.
`schema` returns operation and export parameter maps without requiring the
browser to execute a document command.
The capability name lists are generated from those live maps. Treat a missing
name as unsupported instead of trying a hidden browser method. Every
advertised name is dispatched in the same visible GUI document.
For per-atom coloring, follow the lazy scalar and Matplotlib catalog URLs from
`capabilities().atomColorScale`, then use `set-atom-colorscale`; never guess a
model-specific array name. Use `rangeMode:"current"` for a fast active-frame
fit that remains locked during playback, `rangeMode:"trajectory"` for one
global scan across all frames, or `rangeMode:"manual"` with explicit
`minimum`/`maximum`. A bounded trajectory scan is cached once for playback;
larger scans remain backend-side. Set `gamma` in `0.1..5.0` (`1.0` is
neutral), and never normalize trajectory colors independently per frame.
Numeric LAMMPS atom columns are valid catalog fields alongside coordinates,
stored forces, ASE arrays, charges, magnetic moments, and calculator results.
Stored Cartesian forces can also be shown directly with display fields
`showForceVectors`, `forceVectorStyle`, `forceVectorScale`,
`forceVectorThickness`, and `forceVectorColor`. Arrow direction must equal the
stored vector direction and arrow length is `forceVectorScale * |F|`; never
evaluate an attached calculator merely to create an arrow. On trajectories,
reload both scalar colors and Cartesian vectors from the same active frame;
never reuse a force-vector buffer from another frame.
For a rotation around one atom, pass that atom last in the explicit `indices`
array and set `pivot: "active"`; verify that its coordinate is unchanged.
For an ASE bulk crystal, the human UI path is **+ Add atoms > Build with ASE**.
Read `capabilities().bulkBuilder.catalogUrl`, use its `previewUrl`, then call
`build-bulk`; never invent lattice data or replace content without human-approved
`confirmReplace:true`. Verify formula, atom count, cell, PBC, and Undo.
For batch insertion, use `scatter-atoms` or `scatter-molecules` only on one
Edit-mode structure. Define a periodic cell or at least one finite Allow region
for an empty nonperiodic document. The first scatter starts one reversible Add
Atoms session; later `scatter-atoms` or `scatter-molecules` calls append after
region edits or completed relaxation. The immutable host always means the
structure before the first scatter; every inserted batch remains staged/mobile.
Use `placementMode:"random"` for volume-uniform sampling,
`"homogeneous"` for maximin Cartesian or fractional spacing, and `"regular"`
for one global Cartesian lattice. Use `pbcAware` and `regularSpacing` explicitly
when they matter.
Prefer stable multi-region objects with `id`, `name`, `role:"allow"|"reject"`,
and Cartesian `bounds`. The exact domain is cell intersect Allow union minus
Reject union; without a finite cell an Allow region is mandatory. `regionMic`
uses complete triclinic lattice vectors. `constrainToDomain` defaults false;
when true, every staged atom remains in the Allow union and outside every
Reject region, while rigid molecules are tested by their native ASE template
origin. `allowEscape` is the inverse compatibility field. Use
`update-add-atoms-region` and `scale-add-atoms-regions`; GUI region `G` moves,
`S` scales with optional Cartesian axis lock, and `R` is deliberately rejected.
Before `scatter-molecules`, read `capabilities().addAtoms.moleculeCatalog`.
Native ASE origins and Haar-uniform orientation are retained.
`rigidMolecules:true` preserves geometry; select complete molecules for `G`/`R`.
For density mode, set `quantityMode:"density"` and `targetDensityGcm3`, then
verify exact accessible volume, integer composition, and actual density.
After every placement, verify stable region IDs, `placement_count`,
`last_batch_new_count`, total `new_count`, and immutable-host preservation in
`describe().addAtoms`.
Use the common `start-relaxation` operation for placement relaxation with the
same `calculator` object as **Structure > Relaxation**. The active Add session
routes it through one complete `AdditionRepulsionCalculator`;
`relax-added-atoms` is a compatibility alias. Never push coordinate pairs or
call MIC per pair. Wait for `is_relaxing:false` before appending or finishing.
Appending resets the topology-specific Add timeline; later relaxation records
the expanded structure. Use common `stop-relaxation` or compatibility
`stop-added-atoms` to interrupt, and `cancel-add-atoms` to restore the exact
pre-session host/history. Never batch-insert into a trajectory.
The temporary host fixed overlay may appear in semantic constraint summaries,
but never changes committed ASE constraints, atom radius, or saved appearance.
Use `scale-selection` for physical atom-coordinate scaling about a requested
pivot. It changes spacing in global Cartesian `X`, `Y`, `Z`, or all axes and
never changes atom radii, bond diameter, or the unit cell.
Use `display.atomDisplayMode:"2d"` for a flat unlit scene that keeps atom color/radius/depth, outlines atoms/bonds, marks FixAtoms with X, and flattens vectors/cells/regions; `"3d"` restores materials.
Top-level `renderArea` locks the shared image/video/HTML camera; capture once with `{"enabled":true,"followViewport":false,"fromCurrentView":true}` or provide
explicit camera state, then verify `describe().renderArea` before exporting.
For scalar-field sections, use `add-volumetric-plane` with a dataset ID and a
nonzero hkl normal, `update-volumetric-planes` with the current plane IDs for
atomic multi-plane edits, and `remove-volumetric-planes` to delete them. Read
`describe().analysis.volumetricPlanes` after every operation; do not infer a
plane ID, colormap, sampled range, or signed offset from the viewport. A user
can create and edit planes from **Analysis > Volumetric Data > Planes** in
View mode without changing ASE coordinates. Edit mode additionally supports
viewport `G` along each selected plane normal and `R` for its orientation; the
visible distance and hkl controls update during the transform but semantic
state after commit remains the authority.

## Minimal End-To-End Example

This example reads state, creates a deterministic orthographic view, measures
two atoms, renders the exact export frame, and exports it without a screenshot
crop:

```bash
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'

v_ase api "$COMMAND_URL" apply --params '{
  "expectedRevision": CURRENT_REVISION,
  "display":{
    "viewportBackground":"white",
    "showBonds":true,
    "showGrid":false,
    "showAxes":false,
    "showCell":true,
    "lightingMode":"studio-shadow"
  },
  "quality":{"antiAliasing":true,"sphereQuality":"ultra"},
  "camera":{"axis":"+Z","fit":"structure"},
  "selection":{"clear":true,"indices":[0,1]}
}'

v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'

v_ase api "$COMMAND_URL" render --save preview.webp --params '{
  "format":"webp",
  "width":3840,
  "height":2160,
  "options":{
    "includeGrid":false,
    "includeAxes":false,
    "includeCell":true,
    "transparentBackground":false,
    "backgroundColor":"#ffffff",
    "scaleMode":"viewport",
    "sphereQuality":"ultra",
    "renderMode":"studio-shadow"
  }
}'
```

Replace `CURRENT_REVISION` with the integer returned by the first `describe`.
Verify the second response has two selected atoms and a non-empty measurement;
verify the saved image is 3840 x 2160 and nonblank.
`viewportBackground` controls the interactive GUI only. Exported media uses
`options.backgroundColor` independently, so set it explicitly when the file
must match the viewport background.

For physical editing, trajectory analysis, video, 3D scene export, and failure
handling, use the references below rather than improvising field names.

## Safety Boundaries

- Never delete atoms, overwrite a project, materialize a supercell, change
  chemical elements, start relaxation, or publish files without explicit user
  intent.
- Never call `restore-app-visual-defaults` without explicit human approval.
  It deletes the OS user's saved visual preference and requires
  `confirm: true`.
- Never treat a visual label as an ASE element. Verify `chemicalSymbols`.
- Never infer a periodic replica from screen position. Use `cellOffset`.
- In View, `delete-selection` hides exact visual references and does not modify
  ASE topology. Switch to Edit only after explicit intent to delete the unique
  corresponding base indices; deduplicate repeated images first.
- Never reuse indices after topology or frame changes without `describe()`.
- Treat `scatter-atoms` and `scatter-molecules` as reversible staging
  operations, not committed topology changes. Repeated calls append to the
  same staging session; verify total and last-batch counts and never mistake an
  earlier inserted batch for the immutable host. Do not finish until inserted
  identities, region, shared Relaxation calculator/cutoff state, MIC, rigid
  geometry when requested, and exact host preservation have been verified.
- Keep `applyConstraints: true` unless the user explicitly requests free
  editing.
- Treat ASE backend positions returned after an edit as authoritative.
- Prefer a new output filename. `v_ase api --save` refuses replacement unless
  `--force` is passed; use `--force` only after explicit approval.
- Do not expose local paths, session URLs, tokens, or private structure data in
  public output.
- Treat a newer human collaboration revision as authoritative. Never remove
  `expectedRevision` merely to force a stale command through.

## Validation Before Completion

For any nontrivial task, verify all applicable items:

- structure: count, labels, elements, positions, cell, PBC, constraints;
- batch insertion: single-document eligibility, optional scratch cell, mixed
  entry counts, random seed, homogeneous spacing diagnostics, regular Cartesian
  spacing, exact triclinic Boolean domain, stable multi-region IDs, Allow-union
  and Reject-union semantics, no-cell Allow requirement, analytic accessible
  volume, periodic region images, default unconstrained policy and explicit
  Allow/Reject relaxation confinement, multi-selected live
  `G` bounds, global-Cartesian `S` bounds, edge-only nested-region selection,
  one intact source box plus deduplicated nonzero wrapped fragments, rejected
  region rotation, pairwise cutoffs, MIC, temporary host
  freeze, asynchronous status, mode-only movie timeline, and exact host
  coordinate/constraint/array preservation after finish or cancel; for
  molecules also verify count versus density mode, integer composition ratio,
  target/actual density, rigid geometry, and committed molecule count;
- AI contract: exact schema/capability operation and export set equality, an
  external `v_ase api` mutation visible in the same live GUI, and matching GUI
  and `describe().collaboration.revision` state;
- trajectory: frame count, active frame, stable selection, analysis reference, and cached RDF playback across loaded and relaxation timelines;
- volumetric: dataset ID, grid dimensions, cell, origin, PBC, units,
  component, FP32/FP64 precision, memory size, visible default/custom
  isovalue, raw or absolute-value histogram, mesh count, live color/opacity
  state, planar-section IDs, nonzero hkl, signed Angstrom offsets, resolution,
  colormap/range/opacity, cache reuse, and supercell/translation alignment;
  verify suffixed VASP names such as
  `PARCHG_*`, `LOCPOT.*`, and `CHGCAR-*` are identified by contents/type;
- radial or finite pair distribution: displayed frame, `analysisKind`, PBC, cutoff, bins, curves, normalization, CSV, and selected-active-bond filtering with full-structure normalization;
  for 3D periodic RDF verify the unique-MIC reference, image span, `g(r) = 1` bulk limit, long-range behavior, and warnings; for no PBC verify the unordered-pair probability-density integral;
  require open plots to follow `G`/`R`/`S`, committed edits, and relaxation frames without closing;
- appearance: visibility, radii, colors, per-label opacity, materials, bonds,
  global bond material/opacity, independent pair style/material/color/opacity,
  pair-flat geometry inside a 3D scene, cell, and background;
- per-atom colorscale: exact catalog field ID, scope, map, reverse state,
  gamma, resolved `vmin`/`vmax`, current/trajectory/manual range source, and
  identical locked range across every trajectory frame and export; for large
  trajectories verify one full-range load, no duplicate frame prefetch, fast
  cached recoloring, and zero colorscale work after disabling;
- for `scope:"all"`, require one finite mapped color for every finite-valued
  visible atom on every frame; a partial subset is a failed application;
- force vectors: stored-force availability, exact Cartesian direction,
  `scale * |F|` length, 2D/3D style, thickness/color, replica placement, and
  an explicit unavailable state rather than calculator evaluation;
- preferences: resolved interface theme, System mixed chrome/white-viewport
  behavior, explicit Light/Dark viewport behavior, saved personal-default
  state, and the intended scope before storing or restoring;
- camera: projection, position, target, up vector, framing, expected direction;
- manipulation overlays: rotation axis, fixed start reference, moving current
  reference, and separate commensurate candidates when a human is editing;
- commensurate workspace: global-Z/XY restriction, no-selection host-only
  state, selected same-lattice guest versus loaded guest structure, 3 Angstrom
  default loaded-guest gap, direct guest angle, preserved camera, candidate
  angle, smallest admissible area ratio, Host/Guest strain target,
  host/guest integer matrices, readable square-root notation, black/orange/green
  host/guest/common cells, cells-only default, candidate-independent parent
  lattice windows, grid dimensions and
  readable `N x M` coverage, optional one-primitive-cell atom/bond halo,
  horizontal rotation axis plus orthogonal area-depth and strain-height axes,
  a gridded Plotly 3D candidate surface, candidate points, a live current-angle
  plane, and dotted symmetry periods only when exact lattice symmetry justifies
  them; verify graph CSV and materialization support. GUI activation,
  selection, and guest loading preserve the current direct angle: black host
  and orange guest parent grids retain identical dimensions while the mobile
  lattice rotates, and the green common-cell boundary appears only when that
  angle resolves a bounded match. Only the candidate boundary may change size. For
  an explicit semantic search with no angle, require the smallest-area admissible
  proposal; with an explicit angle, require the nearest admissible candidate. Confirm
  that the conservative max principal strain
  controls acceptance, while the Paper strain projection reports mean
  absolute strain against actual host-plus-guest atom count. `maxAreaRatio`
  defaults to 16 and accepts only 1 through 128. Never call
  `apply-commensurate-cell` without explicit user intent;
- rigid translation: plane mode requires a nonzero integer `(hkl)` and two exact
  primitive periodic translations satisfying `h*u + k*v + l*w = 0`; Cartesian
  mode uses one common x/y/z vector in Angstrom and an explicit per-axis bound.
  Both require a selected moving component plus an unselected host and preserve
  host/cell/selected internal geometry exactly. The sampled plane map is
  optional and is a lower-is-better geometry screen, never an energy. Verify
  the attached calculator or explicit repulsive fallback, the analytic
  derivative from the selected-component net force, a mode-only timeline, one
  undo step on finish, and exact pre-mode restoration on cancel. Visual
  `center-selection-at-origin` instead uses one atom or a mass-weighted COM and
  changes only scene translation, never ASE positions;
- constraints: persistent per-atom FixedLine/FixedPlane markers, one long
  original-position FixedLine direction guide during `G`, and one
  original-position FixedPlane motion guide per selected atom during `G`;
  FixedLine uses one center axis, while rings and discs are plane-only;
  for `Hookean(a1, a2, rt, k)`, require no active spring at `r <= rt`, a visible
  annotation-free 3D helix at `r > rt`, and ASE force magnitude
  `k * (r - rt)` without altering backend constraint semantics; verify the same
  threshold transition on every trajectory frame;
- relaxation modes: source, structure, Add Atoms, and rigid-translation timelines remain distinguishable; stop permits restart; `clear-relaxation-trajectory` retains the displayed or final frame while leaving the mode active; exit keeps current coordinates or restores the exact baseline and removes only that optimizer timeline;
- built-in repulsion: visual bonds and contact repulsion are independent. The default absolute mode uses enabled label-pair onset distances in Angstrom, seeded from ASE covalent-radius sums or optional van der Waals sums; zero disables only that pair. Scaled mode multiplies the same reference table by a dimensionless contact multiplier. Neither onset is a hard distance constraint. matscipy's compiled label-pair search is an implementation acceleration only; it does not alter the onset, MIC, energy, or force contract. Partial-PBC searches preserve periodic cell vectors and never return an image shift on a finite axis; exported periodic bonds use ASE's exact triclinic `find_mic`.
- history: one confirmed transform gesture, Apply action, placement batch, or relaxation start is one undo step. During Add Atoms, Undo/Redo traverses individual batches and Cancel still restores the exact pre-session baseline.
- render: exact dimensions, format, options, nonblank decoded pixels;
- export: MIME type, filename, byte count, and reopenability where supported;
- standalone HTML: both lightweight and project-embedded modes load from
  `file://` with saved camera/trajectory, view-only controls, and zero network requests;
  the exact static poster and first live WebGL frame must share one unmoving
  crop without application chrome;
  embedded mode must also restore through `v_ase gui FILE.html`;
- notebook: `%v_ase inline`, `%v_ase browser`, and `%v_ase auto` select the
  process display target; an explicit `notebook=` overrides one call;
- remote SSH: `HOST:/path` keeps data work remote while the local browser
  renders; one SSH connection pins backend/forward to one load-balanced node;
  use transient `--remote-python /absolute/path/to/python` or a saved
  `v_ase remote configure HOST --python ...` mapping when the required remote
  environment is absent from the non-interactive SSH `PATH`;
- trajectory analysis: after every displayed-frame change, verify that active
  RDF/pair-distribution results, per-atom colors, force and displacement
  vectors, and frame-associated volumetric fields identify the same frame;
  hide unavailable frame fields instead of reusing stale scalar data;
- video: exact decoded frame count and `frames / FPS` duration, with visible
  displacement vectors present in the captured frames when enabled.

If an instruction in this skill prevents a correct result, inspect the live
schema and implementation, correct the skill and add a regression test. Do not
work around a stale skill silently.
## References

Read only the references needed for the current task:

- [Agent setup](references/agent-setup.md): files for agents and clients without native skill loaders.
- [Live collaboration](references/collaboration.md): human/agent events, revisions, tabs, and recovery.
- [CLI and environments](references/cli-and-environments.md): install, input, local/remote use, and lifecycle.
- [Semantic API](references/semantic-api.md): state, commands, display, analysis, render, and export.
- [Workflows and examples](references/workflows-and-examples.md): tested recipes in user-guide order.
- [Safety and errors](references/safety-and-errors.md): destructive actions,
  common errors, fallbacks, and verification requirements.
- [Evaluation](references/evaluation.md): trigger tests, capability audit, and
  release-time end-to-end scenarios.
