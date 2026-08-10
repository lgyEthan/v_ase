---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible structures, trajectories, volumetric fields, isosurfaces, and RDF data through its CLI and live HTTP JSON API. Use when a user needs atomistic visualization, DFT grid analysis, structure measurement, periodic-cell operations, constraints, trajectory movies, publication rendering, reusable 3D export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic HTTP JSON commands. Do not infer
scientific state from screenshots when the `describe` method provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Install the tested release:

```bash
python -m pip install "v_ase-gui==0.1.18"
```

Start the terminal-oriented API session yourself:

```bash
v_ase gui STRUCTURE --cli
```

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

The control path is:

```text
user request -> external agent + this Skill -> CLI handshake/event stream
-> v_ase api -> HTTP JSON bridge -> same live human GUI
-> human GUI edit -> NDJSON event -> agent re-describes and continues
```

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
  commensurate search limits, XY registry grid/metric selection, isovalue and
  surface styling, interpolation, and rendering quality. Start with the
  documented templates, then tune against the requested result.
- **High freedom**: choosing a visually clear viewpoint, palette, or
  composition when the user has not specified one. Preserve scientific
  identity and disclose aesthetic choices.

## Core Semantic Commands

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
For a rotation around one atom, pass that atom last in the explicit `indices`
array and set `pivot: "active"`; verify that its coordinate is unchanged.
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
- AI contract: exact schema/capability operation and export set equality, an
  external `v_ase api` mutation visible in the normal GUI, and matching GUI
  and `describe().collaboration.revision` state;
- trajectory: frame count, active frame, stable selection, analysis reference;
- volumetric: dataset ID, grid dimensions, cell, origin, PBC, units,
  component, FP32/FP64 precision, memory size, visible default/custom
  isovalue, raw or absolute-value histogram, mesh count, live color/opacity
  state, planar-section IDs, nonzero hkl, signed Angstrom offsets, resolution,
  colormap/range/opacity, cache reuse, and supercell/translation alignment;
  verify suffixed VASP names such as
  `PARCHG_*`, `LOCPOT.*`, and `CHGCAR-*` are identified by contents/type;
- RDF: current frame, 3D PBC, requested/effective cutoff, unique-MIC reference,
  required periodic-image span, bins, pair mode, plotted curves, `g(r) = 1`
  bulk reference, long-range behavior, warnings, and exported CSV columns;
- appearance: visibility, radii, colors, materials, bonds, cell, background;
- per-atom colorscale: exact catalog field ID, scope, map, reverse state,
  gamma, resolved `vmin`/`vmax`, current/trajectory/manual range source, and
  identical locked range across every trajectory frame and export; for large
  trajectories verify one full-range load, no duplicate frame prefetch, fast
  cached recoloring, and zero colorscale work after disabling;
- preferences: resolved interface theme, system/light/dark preference, saved
  personal-default state, and the intended scope before storing or restoring;
- camera: projection, position, target, up vector, framing, expected direction;
- manipulation overlays: rotation axis, fixed start reference, moving current
  reference, and separate commensurate candidates when a human is editing;
- commensurate workspace: global-Z/XY restriction, no-selection host-only
  state, selected same-lattice guest versus loaded guest structure, 3 Angstrom
  default loaded-guest gap, direct guest angle, preserved camera, candidate
  angle, smallest admissible area ratio, Host/Guest strain target,
  host/guest integer matrices, readable square-root notation, black/orange/teal
  host/guest/common cells, cells-only default, primitive lattices tiled through
  the proposal, optional one-primitive-cell atom/bond halo, horizontal rotation
  graph axis, live angle plane, graph CSV, and materialization support. With no
  explicit angle, require the smallest-area admissible proposal; with an
  explicit angle, require the nearest admissible candidate. Confirm
  that the conservative max principal strain
  controls acceptance, while the Paper strain projection reports mean
  absolute strain against actual host-plus-guest atom count. `maxAreaRatio`
  defaults to 16 and accepts only 1 through 128. Never call
  `apply-commensurate-cell` without explicit user intent;
- XY registry map: selected moving component, periodic axes, grid dimensions,
  geometry metric, optimum and current fractional coordinates, lower-is-better
  warning, live XY move marker, and exported CSV; never call a geometry score
  an energy minimum;
- constraints: persistent per-atom FixedLine/FixedPlane markers, one long
  original-position FixedLine direction guide during `G`, and one
  original-position FixedPlane motion guide per selected atom during `G`;
  FixedLine uses one center axis, while rings and discs are plane-only;
- render: exact dimensions, format, options, nonblank decoded pixels;
- export: MIME type, filename, byte count, and reopenability where supported;
- standalone HTML: both lightweight and project-embedded modes load from
  `file://` with saved camera/trajectory, view-only controls, and zero network requests;
  the exact static poster and first live WebGL frame must share one unmoving
  crop without application chrome;
  embedded mode must also restore through `v_ase gui FILE.html`;
- notebook: `%v_ase inline` and `%v_ase browser` switch the process-local
  display target, while `%v_ase auto` restores automatic active-kernel
  detection; an explicit `notebook=` value overrides that preference for one
  call;
- video: exact decoded frame count and `frames / FPS` duration, with visible
  displacement vectors present in the captured frames when enabled.

If an instruction in this skill prevents a correct result, inspect the live
schema and implementation, correct the skill and add a regression test. Do not
work around a stale skill silently.

## References

Read only the references needed for the current task:

- [Agent setup](references/agent-setup.md): exact files to give Codex, Claude
  Code, ChatGPT desktop agents, Gemini-based agents, agentic IDEs, and clients
  without native skill loaders.
- [Live collaboration](references/collaboration.md): same-document human/agent
  workflow, NDJSON events, optimistic revisions, multi-tab routing, and
  recovery.
- [CLI and environments](references/cli-and-environments.md): installation,
  input formats, local/remote/server use, dependencies, and process lifecycle.
- [Semantic API](references/semantic-api.md): complete state, command, display,
  volumetric/RDF analysis, render, and export fields.
- [Workflows and examples](references/workflows-and-examples.md): tested
  structure editing, volumetric, RDF, trajectory, rendering, and
  multi-document recipes.
- [Safety and errors](references/safety-and-errors.md): destructive actions,
  common errors, fallbacks, and verification requirements.
- [Evaluation](references/evaluation.md): trigger tests, capability audit, and
  release-time end-to-end scenarios.
