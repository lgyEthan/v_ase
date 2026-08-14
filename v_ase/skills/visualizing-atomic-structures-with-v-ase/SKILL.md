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
python -m pip install "v_ase-gui==0.2.15"
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
   frame, atom indices, labels, elements, cell, PBC, constraints, and camera.
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
  materialized supercells, volumetric linear combinations, relaxation,
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
| Inspect and measure | `describe`, `selection`, ordered `measurement` |
| Edit a structure | `set-unit-cell`, `move-selection`, `rotate-selection`, `scale-selection`, `add-atom`, `scatter-atoms`, `scatter-molecules`, constraints |
| Work with periodic interfaces | display replication, cell transforms, commensurate search, rigid `(hkl)` translation |
| Analyze trajectories | frame selection, displacement, RDF, colorscale, stored force vectors |
| Analyze scalar fields | volumetric datasets, isosurfaces, planes, field combinations |
| Style and render | `display`, `quality`, `camera`, `render` |
| Save or share | `export`, `.vase`, media, HTML, and geometry formats |

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
`applyConstraints`, `camera`, `selection`, and `operation`. Query `schema`
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
For batch insertion, use `scatter-atoms` or `scatter-molecules` only on a
single Edit-mode document. The document may start empty: define a periodic
cell with `set-unit-cell`, or define at least one finite Allow region for a
nonperiodic scratch model. Both scatter operations start one reversible Add
Atoms session.
`placementMode:"random"` is volume-uniform in the full triclinic cell;
`placementMode:"homogeneous"` spreads centers with either physical Cartesian
distance in angstrom, the default, or normalized fractional spacing. Set
`pbcAware:false` only when periodic images must not affect homogeneous spacing.
`placementMode:"regular"` selects one global Cartesian lattice; set
`regularSpacing` for exact Angstrom spacing or omit it for deterministic
automatic spacing. It differs from random and maximin homogeneous placement.
Prefer `regionMode:"regions"` with stable `regions` objects containing `id`,
`name`, `role:"allow"|"reject"`, and Cartesian
`bounds:[xmin,xmax,ymin,ymax,zmin,zmax]`. The exact domain is the finite cell
intersected with the Allow union, or the complete cell when no Allow exists,
minus the Reject union. Without a finite cell, at least one Allow region is
mandatory. `regionMic:true` maps region images through complete triclinic
lattice vectors. In the GUI, keep the intact Cartesian source cuboid visible;
draw only its cell-clipped nonzero periodic images at the opposite faces and
deduplicate shared fragment edges. Never replace the source box with a pile of
wrapped fragments. Legacy `regionMode:"box"` remains accepted for one region.
Regions define initial placement: `allowEscape` defaults to `true`, so
repulsive placement may leave the combined domain.

Before `scatter-molecules`, read `capabilities().addAtoms.moleculeCatalog`
instead of guessing an ASE molecule name. Molecules are placed and rotated
about the native ASE template origin. `randomOrientation:true` samples
unbiased 3D rotations. `rigidMolecules:true` is the default and preserves each
molecule's internal geometry during repulsion; whole-molecule `G`/`R` edits
remain valid, while partial edits that distort a rigid molecule are rejected.
Use `rigidMolecules:false` only when atomwise internal motion is intended.
For density-driven placement, set `quantityMode:"density"` and
`targetDensityGcm3`; molecule Count values become integer composition ratios.
v_ase reduces their greatest common divisor before selecting complete batches.
Read `describe().addAtoms.density` and verify target, actual, exact accessible
volume, primitive ratio, and integer molecule count. Never infer density from
a Cartesian bounding box or round each molecular species independently.
For staged inserted content, GUI `G` maps to semantic `move-selection` and GUI
`R` maps to `rotate-selection`; include every atom of each rigid molecule in
the active selection before either operation.
`update-add-atoms-region` accepts a complete `regions` array or one `regionId`
with `regionName`, `regionRole`, `regionMic`, and/or `bounds`; it never moves
staged atoms. Periodic confinement must use the same `regionMic` state and the
shortest triclinic minimum-image displacement.
The GUI multi-selects region rows or edge overlays, applies `G` to move the
selected group, applies `S` with optional global Cartesian `X`/`Y`/`Z` lock to
scale the selected bounds about their shared center, and deliberately rejects
`R`. Use `scale-add-atoms-regions` for the same semantic operation. Region
fills provide depth but are never selection targets, so a nested box remains
selectable by its edges. Verify stable IDs and the exact domain in
`describe().addAtoms`, then optionally run `relax-added-atoms` with explicit
pair cutoffs, MIC, and the requested `device`/`cpuThreads`. The operation
attaches one complete `AdditionRepulsionCalculator` to the staged structure
and advances it with FIRE; do not implement pairwise coordinate pushes or
call MIC per atom pair. Its temporary `Add Atoms placement` timeline retains
every optimizer step and must exist only while the staging mode remains active.
Wait until
`is_relaxing` is false before `finish-add-atoms`. Use `stop-added-atoms` only
to interrupt the optimizer, and `cancel-add-atoms` to restore the exact host,
constraints, per-atom arrays, and pre-session history. Never use batch
insertion on a trajectory because it would create inconsistent frame topology.
While staging, `describe().constraints.fixed_indices` may include the host as
a semantic constraint summary for its temporary fixed overlay. The committed
ASE constraints remain unchanged; the overlay does not change atom radii or
saved appearance and applies only the fixed-material surface. Verify this
again after finish or cancel.
Use `scale-selection` for physical atom-coordinate scaling about a requested
pivot. It changes spacing in global Cartesian `X`, `Y`, `Z`, or all axes and
never changes atom radii, bond diameter, or the unit cell.
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
- Never reuse indices after topology or frame changes without `describe()`.
- Treat `scatter-atoms` and `scatter-molecules` as reversible staging
  operations, not committed topology changes. Do not finish until inserted
  identities, region, pairwise cutoffs, MIC, rigid geometry when requested,
  and exact host preservation have been verified.
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
  volume, periodic region images, default escape policy, multi-selected live
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
- trajectory: frame count, active frame, stable selection, analysis reference;
- volumetric: dataset ID, grid dimensions, cell, origin, PBC, units,
  component, FP32/FP64 precision, memory size, visible default/custom
  isovalue, raw or absolute-value histogram, mesh count, live color/opacity
  state, planar-section IDs, nonzero hkl, signed Angstrom offsets, resolution,
  colormap/range/opacity, cache reuse, and supercell/translation alignment;
  verify suffixed VASP names such as
  `PARCHG_*`, `LOCPOT.*`, and `CHGCAR-*` are identified by contents/type;
- radial or finite pair distribution: current frame, `analysisKind`, PBC,
  requested/effective cutoff, bins, pair mode, plotted curves, normalization,
  and exported CSV columns; for 3D periodic RDF also verify the unique-MIC
  reference, required periodic-image span, `g(r) = 1` bulk reference,
  long-range behavior, and warnings; for a no-PBC finite structure verify the
  unordered-pair probability-density integral instead of calling it bulk RDF;
- appearance: visibility, radii, colors, materials, bonds, cell, background;
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
- preferences: resolved interface theme, system/light/dark preference, saved
  personal-default state, and the intended scope before storing or restoring;
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
- planar translation: nonzero integer `(hkl)`, two exact primitive periodic
  lattice translations satisfying `h*u + k*v + l*w = 0`, selected moving
  component, unselected host, visible physical plane cell, and a live shared
  translation marker. The sampled short-contact or pair-length map is optional
  and is a lower-is-better geometry screen, never an energy. For rigid
  optimization verify the attached calculator or explicit repulsive fallback,
  exactly two common plane coordinates, invariant host/cell/selected internal
  geometry, projected net selected force in `eV/angstrom`, a mode-only
  timeline, one undo step on finish, and exact pre-mode restoration on cancel;
- constraints: persistent per-atom FixedLine/FixedPlane markers, one long
  original-position FixedLine direction guide during `G`, and one
  original-position FixedPlane motion guide per selected atom during `G`;
  FixedLine uses one center axis, while rings and discs are plane-only;
  for `Hookean(a1, a2, rt, k)`, require no active spring at `r <= rt`, a visible
  annotation-free 3D helix at `r > rt`, and ASE force magnitude
  `k * (r - rt)` without altering backend constraint semantics; verify the same
  threshold transition on every trajectory frame;
- relaxation modes: source, structure-relaxation, Add Atoms placement, and
  rigid planar-translation timelines remain distinguishable; stopping permits
  restart; exiting an active or finished structure relaxation explicitly keeps
  the current coordinates or restores the exact pre-relaxation baseline, then
  removes only that temporary optimizer timeline;
- render: exact dimensions, format, options, nonblank decoded pixels;
- export: MIME type, filename, byte count, and reopenability where supported;
- standalone HTML: both lightweight and project-embedded modes load from
  `file://` with saved camera/trajectory, view-only controls, and zero network requests;
  the exact static poster and first live WebGL frame must share one unmoving
  crop without application chrome;
  embedded mode must also restore through `v_ase gui FILE.html`;
- notebook: `%v_ase inline`, `%v_ase browser`, and `%v_ase auto` select the
  process display target; an explicit `notebook=` overrides one call;
- remote SSH: `HOST:/path` keeps source data remote; CLI negotiation warns on
  compatibility fallback and rejects unsupported explicit features;
- video: exact decoded frame count and `frames / FPS` duration, with visible
  displacement vectors present in the captured frames when enabled.

If an instruction in this skill prevents a correct result, inspect the live
schema and implementation, correct the skill and add a regression test. Do not
work around a stale skill silently.

## References

Read only the references needed for the current task:

- [Agent setup](references/agent-setup.md): exact files to give Codex, Claude Code,
  ChatGPT desktop agents, Gemini-based agents, agentic IDEs, and clients without native skill loaders.
- [Live collaboration](references/collaboration.md): same-document human/agent workflow,
  NDJSON events, optimistic revisions, multi-tab routing, and recovery.
- [CLI and environments](references/cli-and-environments.md): installation,
  input formats, local/remote/server use, dependencies, and process lifecycle.
- [Semantic API](references/semantic-api.md): complete state, command, display,
  colorscale/force, periodic-interface, volumetric/RDF analysis, render, and
  export fields.
- [Workflows and examples](references/workflows-and-examples.md): tested edit,
  periodic-interface, analysis, trajectory, rendering, collaboration, and
  export recipes grouped in the same order as the user guide.
- [Safety and errors](references/safety-and-errors.md): destructive actions,
  common errors, fallbacks, and verification requirements.
- [Evaluation](references/evaluation.md): trigger tests, capability audit, and
  release-time end-to-end scenarios.
