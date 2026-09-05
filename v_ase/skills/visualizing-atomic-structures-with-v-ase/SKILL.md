---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible structures, trajectories, volumetric fields, isosurfaces, and RDF data through typed MCP/function tools and its compatible CLI/HTTP JSON API. Use when a user needs atomistic visualization, DFT grid analysis, structure measurement, periodic-cell operations, constraints, trajectory movies, publication rendering, reusable 3D export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic HTTP JSON commands; do not infer scientific state from screenshots when `describe` provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Use the configured v_ase MCP tools when available. No model API key is needed
by v_ase. Install the core with `python -m pip install "v_ase-gui==0.3.2"`;
install `v_ase-gui[mcp]==0.3.2` for the optional official MCP server.

An MCP host can launch `v_ase mcp --discovery progressive` to open a shared GUI,
or use `v_ase mcp --connect COMMAND_URL` for an existing GUI. Read
`references/native-tools.md` only when setup or transport recovery
is needed. The skill is scientific workflow guidance; exact parameter schemas
come from the tools.

1. Call `vase_describe(profile="summary")`.
2. In progressive mode, use `vase_search_tools` with feature keywords or an
   exact tool name; otherwise use the already advertised tools.
3. Read only the focused structure, appearance, bonding, render, or analysis
   state required for the next decision.
4. Supply `documentId` as `expected_document_id` and the latest
   `collaboration.revision` as `expected_revision` to editing tools.
5. Consume `vase_events`, review human changes, and inspect final render artifacts.

Tool inputs use snake_case, including nested declared fields. State and raw
HTTP/JavaScript inputs retain camelCase. User-defined labels and map keys never
change. For example, `vase_configure_bonds(index_pairs=...)` maps to the exact
`indexPairs` semantic operation without shell quoting.

If no MCP or native function tools are available, use the CLI workflow in
`references/cli-and-environments.md`. `v_ase gui ... --cli`
is a persistent process: read the first stdout handshake and do **not** wait
for process exit. Open `human_url` and send structured commands through
`v_ase api`; the process does not accept natural language or stdin commands.
Keep its handle and later revision events available for human collaboration.

## Required Workflow

Use this sequence for every task:

1. **Connect**: use MCP/function tools or the CLI handshake and open the shared
   GUI. Keep consuming collaboration events while the human refines the document.
2. **Plan**: use compact describe and tool discovery (CLI: `schema` and
   `describe --profile summary`). Request only
   the schema for operations that will actually be used and only the focused
   state needed to identify atom indices, labels, elements, cell, PBC,
   constraints, appearance, bonds, or render camera. Preserve ordered VASP
   labels such as `O_1`/`O_2` while verifying their ASE element separately.
3. **Validate**: confirm atom count and topology before reusing indices. Confirm
   Edit mode before physical changes.
4. **Execute**: apply one semantic change at a time with the latest
   settled `collaboration.revision` returned by `describe` as
   `expected_revision` plus `expected_document_id` (raw API: `expectedRevision`
   and `expectedDocumentId`).
5. **Synchronize**: on a human event, pause mutations, activate its document,
   call `describe`, and preserve the newer human change.
6. **Verify**: inspect the compact apply response's `mutation.changedPaths`.
   Request a focused `describe` only when the returned summary cannot prove the
   result or after a human collaboration event.
7. **Render**: inspect `describe --profile render`, then call `render` at draft
   dimensions. Native tools save a resource automatically; CLI uses `--save`. Verify `effectiveRender.source`, exact camera,
   dimensions, options, byte count, and decoded image before one final render.
8. **Export**: call `export` only after state and camera verification. Use
   the returned artifact resource; CLI uses `--save OUTPUT` for a `dataUrl`.
9. **Collaborate**: keep `human_url` and the event stream active while the user
   wants to watch or refine the result.

Do not report completion when only an HTTP response succeeded. Verify the
resulting semantic state and rendered output.

The CLI omits render/export `dataUrl` strings from stdout by default so Base64
does not consume the Agent context. Use `--save OUTPUT` for normal work.
`--print-data-url` is an explicit opt-in for callers that truly require the
raw payload.

Use `vase_pause_playback` before reading an animated frame. Stop controls for
playback and optimization require document identity but allow revision omission
because the running process continuously advances it. This exception never
applies to ordinary edits. On a timeout, inspect state before repeating a command:
its outcome may be unknown.

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

For scientific work in 0.3.1, preserve the distinction between initialization,
overlap removal, and physical equilibrium. Read the scientific-interpretation
section of `semantic-api.md`: periodic repulsion includes self images, default
forces are conservative, homogeneous placement is bounded and correlated, RDF
depends on PBC, and volumetric combination uses `resultName` (never a second
`name` key). Reject tilted host/guest planes instead of projecting them flat.

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

- [Native tools](references/native-tools.md): MCP setup, native functions, discovery, resources, and typed errors.
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
