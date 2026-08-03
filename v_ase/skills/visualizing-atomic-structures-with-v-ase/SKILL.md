---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible atomic structures and trajectories through its CLI and live HTTP JSON API. Use when a user needs atomistic visualization, structure measurement, crystallographic symmetry, finite-displacement inputs, physical phonon eigenmodes, periodic-cell operations, constraints, trajectory movies, publication rendering, reusable 3D export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic HTTP JSON commands. Do not infer
scientific state from screenshots when the `describe` method provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Install this isolated symmetry alpha from a checkout of the `symmetry` branch:

```bash
python -m pip install -e ".[symmetry,phonon]"
```

The branch version is `0.0.120a6+symmetry`: it identifies main viewer state
`0.0.120` as the fork base and alpha iteration 6 as symmetry-only work. It is
intentionally not installed
from or published to PyPI. Use the checked-out branch as the source of truth.

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
  materialized supercells, symmetry standardization, phonon-mode trajectory
  generation, relaxation, and overwrite-prone exports. Use exact documented
  commands and verify afterward.
- **Medium freedom**: camera placement, bond cutoffs, materials, lighting,
  displacement analysis, interpolation, and rendering quality. Start with the
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
For a rotation around one atom, pass that atom last in the explicit `indices`
array and set `pivot: "active"`; verify that its coordinate is unchanged.

Scientific operations in this branch are `analyze-symmetry`,
`symmetry-path`, `standardize-symmetry`,
`generate-phonon-displacements`, `phonon-band-structure`,
`inspect-phonon-modes`, and `generate-phonon-mode`. Symmetry analysis,
reciprocal-path queries, and phonon-band calculation are nonmutating.
Standardization and generated trajectories require Edit mode, replace the
current trajectory, and create an Undo checkpoint. Read
`references/symmetry-and-phonons.md` before using them. A loaded phonopy
project must match the active atom order, elements, lattice metric, and
periodic positions. `describe()` keeps scientific state compact; use the direct
scientific endpoint only when full symmetry operations or complex
eigenvectors are required. Never interpret a band plot's horizontal coordinate
as an atom-motion direction: it is distance along a reciprocal q path, while
the selected `(q, mode)` eigenvector defines the real-space motion.

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

For physical editing, trajectory analysis, video, 3D scene export, and failure
handling, use the references below rather than improvising field names.

## Safety Boundaries

- Never delete atoms, overwrite a project, materialize a supercell, change
  chemical elements, start relaxation, or publish files without explicit user
  intent.
- Never treat a visual label as an ASE element. Verify `chemicalSymbols`.
- Never call an arbitrary displacement a phonon eigenmode. Physical modes
  require loaded force constants and a calculated eigenvector at the q-point.
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
- trajectory: frame count, active frame, stable selection, analysis reference;
- symmetry: type basis, tolerance, space group/orbits, warning list, and
  unchanged state for analysis-only commands;
- phonons: force-constant availability, q-point, 1-based band, frequency,
  polarization, `P.T @ q` commensurability, amplitude, and output frame count;
- appearance: visibility, radii, colors, materials, bonds, cell, background;
- camera: projection, position, target, up vector, framing, expected direction;
- manipulation overlays: rotation axis, fixed start reference, moving current
  reference, and separate commensurate candidates when a human is editing;
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
- notebook: `%v_ase inline`, `%v_ase browser`, and `%v_ase auto` switch the
  process-local display target, while an explicit `notebook=` value overrides
  that preference for one call;
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
  analysis, render, and export fields.
- [Symmetry and phonons](references/symmetry-and-phonons.md): crystallographic
  identity, finite-displacement preparation, force-constant loading, q-point
  modes, commensurability, exact commands, and scientific verification.
- [Workflows and examples](references/workflows-and-examples.md): tested
  structure editing, trajectory, rendering, and multi-document recipes.
- [Safety and errors](references/safety-and-errors.md): destructive actions,
  common errors, fallbacks, and verification requirements.
- [Evaluation](references/evaluation.md): trigger tests, capability audit, and
  release-time end-to-end scenarios.
