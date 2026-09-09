---
name: visualizing-atomic-structures-with-v-ase
description: Inspect, edit, analyze and render atomic structures, trajectories and scalar fields in the shared v_ase GUI through MCP tools. Use for ASE-compatible scientific visualization and human-editable atomistic figures.
---

# Atomic structures with v_ase

Use the live document's structured state. MCP is the primary interface;
CLI and native function adapters share the same scientific backend.
Lengths are Angstrom, angles degrees, atom/frame indices zero-based.
For rotation/scaling, the GUI label “Selection COM” currently denotes an
unweighted coordinate centroid; use an explicit pivot for a mass-weighted center.

For a ChatGPT plugin, use its registered MCP connection. The person's computer
runs v_ase; cloud-side localhost is not that computer. Consult the setup guide
only for a missing connection, not before ordinary figure work.
A reachable tunnel alone does not establish GUI readiness. Keep a GUI browser
connected for scene operations; CLI/MCP-owned backends survive closing that tab.

## Start with the decision the task needs

- **Figure refinement:** `vase_scene_snapshot()` reads a compact summary of the
  actual render camera, framing, atom mode, bond visibility, selection and
  readiness. Do not request coordinates or every profile for a two-setting edit.
- **Identify a motif or exact bonds:** request `sections:["atoms","bonds"]`,
  filter `elements`, `labels` or `indices`, and use bounded pages. World positions
  include visual translation and periodic `cellOffset`; screen coordinates use
  the stated output dimensions. `intersectsFrustum` does not establish occlusion.
- **Physical edits or scientific analysis:** `vase_describe(profile="structure")`
  supplies physical identity, cell, PBC and constraints. Add arrays only when the
  requested calculation needs them. Use the appropriate short workflow below.
- **No loaded structure:** discover files and `load-structure`. Replacing a
  populated document requires user intent; a new workspace tab preserves it.

Use `vase_search_tools(query="specific feature", limit=4)` for an unknown
feature or exact tool name. Search results are short; use the exact returned
tool name. Call `vase_tool_schema(names=[...])` only if the host has not already
loaded the needed schema. Never print `ALL_TOOLS`, match namespace boilerplate,
load the full catalog or reread a long reference to find one parameter.

## Make the smallest sufficient change

Use the initially available `vase_style_scene` for common display toggles.
For related advanced visual/frame changes, use one `vase_apply_scene` transaction.
Its typed `patch` contains `display`, `frame`, `camera`, `render_area`, `quality`,
`selection`, `plane_selection` or `clear_selections`. Omitted fields survive.
Override maps merge by default, including existing fields within a pair style;
arrays explicitly replace their lists. `map_mode="replace"` replaces only maps
that were supplied. Physical coordinates, cells, species and stored arrays are
outside this transaction; use their dedicated tools for authorized physical work.

A flat figure with hidden bonds needs only `vase_style_scene`:

```json
{
  "expected_document_id": "DOCUMENT_ID_FROM_SNAPSHOT",
  "expected_revision": 12,
  "atom_display_mode": "2d",
  "show_bonds": false
}
```

`12` is illustrative: use the revision actually returned by the current document.
**Hiding bonds does not require resetting cutoffs, ranges or pair styles.**
Use `configure-bonds` to change a bonding policy or exact edge list, not to toggle
visibility. Pair and endpoint overrides can supersede a global style; inspect
renderer-resolved bond segments rather than forcing an inactive fallback value.
For an exact motif use `index_pairs` (raw API: exact `indexPairs`); this preserves
visual label identities. Do not invent visual labels to select one edge.

Inputs use snake_case. Responses and raw CLI/HTTP/JavaScript use camelCase.
User-defined labels, array IDs and map keys retain their spelling. Use
`documentId` plus scene `revision` (legacy describe: `collaboration.revision`)
for `expected_document_id` and `expected_revision`. Every ordinary edit needs
both guards. Readiness/stop tools document their exceptions for advancing frames.

The transaction returns `applied`, changed paths, readiness and the new revision.
Use those values directly. Read another focused snapshot only if a receipt is
truncated, a relevant result is absent, or a human event changed the document.
A failed transaction reports `rolled_back` or `unknown`; do not claim completion
from a successful transport response alone.

## Render the scene you inspected

Render with the requested dimensions and camera source. Omitted dimensions use
the current image profile. `options.selection_appearance="publication"` is the
default: atom selection outlines are suppressed and plane borders are neutral,
without clearing live selections. Set `include_plane_borders=false` to omit
plane borders, or `selection_appearance="interactive"` when selected appearance
is intentionally part of the image. Scientific constraint markings remain.

`vase_select_volumetric_planes(plane_ids=[])` explicitly deselects planes.
Clearing atom selection alone does not clear plane selection. A scene patch with
`clear_selections=true` clears atoms, replicas, planes and light/render-area handles.
Selecting nonempty plane IDs follows GUI rules and clears atom selection and the
light handle. Do not request both atom and nonempty plane selections in one patch.
Do not add and delete dummy planes to affect their selection appearance.

The render waits for tracked frame/field/color/vector work. Inspect
`vase_scene_readiness` when it reports pending, stale or failed work; fix that
specific cause instead of guessing camera angles or changing unrelated styles.
Pause playback before an exact figure. Rendering does not start a calculator.

`vase_render` returns an artifact URI plus exact camera/options/dimensions.
Use `vase_inspect_image(uri=...)` for final visual QA: MCP returns image content.
Native-function hosts embed validated artifact bytes as image input. Never print
Base64 or count a file path as image inspection. Use one final render when the
state establishes the result; add a draft only when visual composition needs it.

## Collaboration and retry

The person and agent share one document. Consume `vase_events` when relevant,
review human changes, and preserve the newer revision. Do not repeatedly poll
unchanged state during an isolated edit, force stale commands, or reuse indices
after a topology change. Frame-dependent IDs and scalar fields must be discovered
for the relevant frame.

For uncertain mutation replies, an optional `request_id` may be reused with
**identical arguments**. A changed plan or revision gets a new ID. Receipt replay
is bounded to the live document (up to 128 entries / 8 MiB), not a durable
exactly-once guarantee across reloads. Large replay responses may be compact.
A replay can refer to an earlier revision; inspect current state before new work.

Do not infer equilibrium from repulsive overlap removal, chemical bonds from
visual edges, or a physical DFT quantity from a synthetic scalar field. Keep the
user's scientific provenance and requested constraints. Use new export names
unless replacement was requested. Existing user authorization continues to apply.
For preparation or analysis, report the chosen boundary convention and search
limits. A step-limited optimizer is not converged; inspect its returned status
and final force. Feature-specific numerical limits are in the focused guides.

## Focused workflows

Use `vase_read_guide(topic=...)` only when its workflow is needed. An optional
exact `section` reads that heading; `offset`/`nextOffset` page a long excerpt.
Parameter definitions belong in tools, not copied JSON manuals.

| Topic | Use when | Bundled reference |
| --- | --- | --- |
| scene | Scene patches, projection, selection, rollback | [Scene workflow](references/scene-workflow.md) |
| rendering | Reference figures, cameras and effective bonds | [Deterministic rendering](references/deterministic-rendering.md) |
| polyhedra | 2D/3D faces, periodic ligand sites, connectors, color and opacity | [Polyhedra](references/polyhedra.md) |
| structures | Load, build, edit, wrap, transform and replicate | [Structures](references/structures.md) |
| trajectories | Frames, stored scalar colors, displacement/force vectors | [Trajectories](references/trajectories.md) |
| volumetric | DFT grids, signed surfaces, sections and combinations | [Volumetric data](references/volumetric.md) |
| rdf | Normalization, periodic images and RDF export | [RDF](references/rdf.md) |
| interfaces | Commensurate cells, registry maps and rigid translations | [Interfaces](references/interfaces.md) |
| insertion | Random/homogeneous atoms, molecules and repulsion | [Insertion](references/insertion.md) |
| constraints | Fixed atoms, directional constraints and relaxation | [Constraints](references/constraints.md) |
| exports | Project, image, movie, geometry and scientific tables | [Exports](references/exports.md) |
| collaboration | Multiple documents and human refinement | [Collaboration](references/collaboration.md) |
| setup | MCP/native integration or transport recovery | [Native tools](references/native-tools.md) |
| errors | Typed failures and targeted recovery | [Safety and errors](references/safety-and-errors.md) |

The long `semantic-api.md` and `workflows-and-examples.md` references remain for
legacy users; do not load them for an ordinary MCP figure task. Release/evaluation
procedures are separate from a user's visualization task.
