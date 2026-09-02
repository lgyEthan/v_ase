---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible structures, trajectories, volumetric fields, isosurfaces, and RDF data through its CLI and live HTTP JSON API. Use when a user needs atomistic visualization, DFT grid analysis, structure measurement, periodic-cell operations, constraints, trajectory movies, publication rendering, reusable 3D export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic HTTP JSON commands; do not infer scientific state from screenshots when `describe` provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Install the tested release:

```bash
python -m pip install "v_ase-gui==0.2.36"
```

Start the terminal-oriented API session yourself:

```bash
v_ase gui --cli
v_ase gui STRUCTURE --cli
v_ase gui STRUCTURE --interactive --cli
```

The filename-free form opens a scratch document directly in Edit. Use the combined file form for physical atom edits while retaining the structured CLI/API bridge and the same human GUI.

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

Read the first stdout line as JSON. It identifies `human_url`, `command_url`,
schema/skill/state/event URLs, supported methods, protocol, scope, and installed
skill path. It also states `accepts_natural_language:false` and
`stdin_commands:false`. Keep reading later stdout as revisioned NDJSON.

Open `human_url` in a browser and wait for the viewport to load. Then call the
live API from another terminal:

```bash
v_ase api "$COMMAND_URL" ready
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" describe --profile summary
v_ase api "$COMMAND_URL" schema --operation-schema OPERATION_NAME
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

The bare CLI `schema` and `describe` calls are deliberately compact. Repeat
`--operation-schema` for related operations, and request one state profile with
`--profile structure|appearance|bonding|render|analysis` only when needed.
Use `--include-positions` only for coordinate-dependent work. Do not repeatedly
load the complete schema, capabilities payload, or `full` state. Rendered pixels
remain the final authority for visual-quality checks.

## Required Workflow

Use this sequence for every task:

1. **Connect**: parse the handshake, keep consuming later NDJSON events, and
   open `human_url` so the human and agent share one live document.
2. **Plan**: call compact `schema` and `describe --profile summary`. Request only
   the schema for operations that will actually be used and only the focused
   state needed to identify atom indices, labels, elements, cell, PBC,
   constraints, appearance, bonds, or render camera. Preserve ordered VASP
   labels such as `O_1`/`O_2` while verifying their ASE element separately.
3. **Validate**: confirm atom count and topology before reusing indices. Confirm
   Edit mode before physical changes.
4. **Execute**: apply one semantic change at a time with the latest
   settled `collaboration.revision` returned by `describe` as
   `expectedRevision`.
5. **Synchronize**: on a human event, pause mutations, activate its document,
   call `describe`, and preserve the newer human change.
6. **Verify**: inspect the compact apply response's `mutation.changedPaths`.
   Request a focused `describe` only when the returned summary cannot prove the
   result or after a human collaboration event.
7. **Render**: inspect `describe --profile render`, then call `render` at draft
   dimensions with `--save`. Verify `effectiveRender.source`, exact camera,
   dimensions, options, byte count, and decoded image before one final render.
8. **Export**: call `export` only after state and camera verification. Use
   `--save OUTPUT` for results containing a `dataUrl`.
9. **Collaborate**: keep `human_url` and the event stream active while the user
   wants to watch or refine the result.

Do not report completion when only an HTTP response succeeded. Verify the
resulting semantic state and rendered output.

The CLI omits render/export `dataUrl` strings from stdout by default so Base64
does not consume the Agent context. Use `--save OUTPUT` for normal work.
`--print-data-url` is an explicit opt-in for callers that truly require the
raw payload.

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
| Save or share | `export`, compact `.vase`, portable HTML projects, media, and geometry formats; the GUI uses one Save Project dialog whose rendered-view option changes output to HTML |

### Live Methods

The HTTP bridge has seven document methods:

```bash
v_ase api "$COMMAND_URL" ready
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" schema --operation-schema move-selection
v_ase api "$COMMAND_URL" describe --profile structure --include-positions
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
`applyConstraints`, `camera`, `renderArea`, `selection`, `operation`, and
`responseProfile`. The terminal client adds `responseProfile:"summary"` unless
another `--response-profile` is requested, so every mutation returns a small
state plus exact `mutation.changedPaths`. Browser callers retain the complete
legacy response unless they opt into a profile. Query the focused live schema
instead of assuming that a command or parameter exists. Treat a missing name
as unsupported instead of trying a hidden browser method. Every advertised
name is dispatched in the same visible GUI document.
For reference-figure or natural-language rendering, read the
`deterministic-rendering.md` reference before issuing
commands. Convert the request into explicit motif, repetition, anchor, view
normal, screen vertical, layer-role, radius, bond, and framing constraints.
Use display replication rather than a physical supercell edit. An exact `indexPairs`
request preserves every label-pair cutoff and appearance
policy; use `pairs` with `disableUnspecified:true` only for an intentional
label-pair allow-list, including the explicit no-bond state. Do not invent visual labels
or repeatedly guess orbit and zoom. Inspect `mutation.changedPaths`
and the `render` profile's `effectiveRender` camera before judging pixels.

For physical edits, building, atom/molecule insertion, trajectory properties,
volumetric data, RDF, constraints, relaxation, commensurate cells, and rigid
translation, request the relevant operation schema and read only the matching
section of `semantic-api.md` or `workflows-and-examples.md`. Do not load those
large references for a rendering-only task.

Use `deterministic-rendering.md` for a complete compact render sequence and
`workflows-and-examples.md` only for the requested scientific workflow.

## Safety Boundaries

- Never delete atoms, overwrite a project, materialize a supercell, change
  chemical elements, start relaxation, or publish files without explicit user
  intent.
- `restore-app-visual-defaults` deletes saved preferences; require approval and `confirm:true`.
- Never treat a visual label as an ASE element. Verify `chemicalSymbols`.
- Never infer a periodic replica from screen position. Use `cellOffset`.
- View deletion only hides references. Require Edit and deduplicate periodic
  images before deleting physical base atoms.
- Never reuse indices after topology or frame changes without `describe()`.
- Treat atom/molecule scattering as reversible staging. Verify inserted counts,
  domain, calculator/MIC, rigid geometry, and immutable host before finish.
- Keep `applyConstraints: true` unless the user explicitly requests free
  editing.
- Treat ASE backend positions returned after an edit as authoritative.
- Prefer a new filename; `--force` requires approval. Never expose private paths,
  session URLs, tokens, or structure data.
- Treat a newer human collaboration revision as authoritative. Never remove
  `expectedRevision` merely to force a stale command through.

## Validation Before Completion

For the active task, verify the physical or visual invariants named in its
focused schema and reference. Always check:

- latest collaboration revision and intended document/frame;
- unchanged structure for visualization-only work;
- exact changed paths after each mutation;
- requested labels, selection, appearance, bond policy, camera source, and
  analysis frame where applicable;
- decoded nonblank output with exact dimensions and format;
- reopenability for projects or standalone HTML;
- `%v_ase inline`, `%v_ase browser`, or `%v_ase auto` only for notebook display;
- explicit human approval before destructive or overwrite-prone actions.

The exhaustive release matrix belongs in `evaluation.md`; do not load it for
ordinary visualization work.

If an instruction in this skill prevents a correct result, inspect the live
schema and implementation, correct the skill and add a regression test. Do not
work around a stale skill silently.
## References

Read only the references needed for the current task:

- [Agent setup](references/agent-setup.md): files for agents and clients without native skill loaders.
- [Live collaboration](references/collaboration.md): human/agent events, revisions, tabs, and recovery.
- [CLI and environments](references/cli-and-environments.md): install, input, local/remote use, and lifecycle.
- [Deterministic rendering](references/deterministic-rendering.md): token-efficient natural-language and reference-figure composition, exact bonds, cameras, and bounded visual verification.
- [Semantic API](references/semantic-api.md): state, commands, display, analysis, render, and export.
- [Workflows and examples](references/workflows-and-examples.md): tested recipes in user-guide order.
- [Safety and errors](references/safety-and-errors.md): destructive actions,
  common errors, fallbacks, and verification requirements.
- [Evaluation](references/evaluation.md): trigger tests, capability audit, and
  release-time end-to-end scenarios.
