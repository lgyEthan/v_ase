---
name: visualizing-atomic-structures-with-v-ase
description: Inspect, edit, analyze and render atomic structures, trajectories and scalar fields in the shared v_ase GUI through MCP tools. Use for ASE-compatible scientific visualization and human-editable atomistic figures.
---

# Atomic structures with v_ase

Use the live document's structured state. MCP is the primary interface;
CLI and native function adapters share the same scientific backend.
The optional macOS/Windows desktop host uses the same GUI and API. To attach
to an existing desktop document, use Help → Copy agent connection URL and the
normal CLI/HTTP contract. Keep the app open; do not start another viewer or
change the user's Python environment for this connection.
Desktop installation and OS file-association guidance is in
`references/cli-and-environments.md`. OS defaults are user choices; do not
claim that installing the app forcibly takes over `.vase` or `.vasp` files.
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
User-defined labels, array IDs and map keys retain their spelling. Native tool names are
not raw operation names: mode and selection are top-level raw `apply` fields;
translation is `operation:{name:"move-selection",vector:[...]}`. Read the
focused apply schema when moving between native tools and CLI. Use
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

Multi-atom geometry is shown automatically only for an intentionally ordered
selection. A marquee, label, Select all, paste or default semantic selection is
bulk and reports a count without distance/angle/torsion. To request geometry
through the raw selection contract, provide 2–4 explicit ordered indices or
periodic references with `selection.intent="measure"`. For the native adapter,
pass the intent inside its `selection` argument, for example
`vase_set_selection(selection={indices:[0,1],intent:"measure"}, expected_document_id=..., expected_revision=...)`.
A single selected atom leads with its chemical element and user label in the
Measure readout, then exposes stored properties without a property-count summary.
For human refinement, the editor has a wide viewport and a single right
Style / Build / Analyze / Render workbench. Each workbench exposes its tool buttons directly. Style includes Atoms,
Bonds, Cell, Polyhedra and View & guides. The optional Objects drawer
overlays the viewport and opens contextual properties. Search is in the header;
File/Edit/View/Help sit above the canvas. Select/Move/Orbit/Measure sit below
it, with physical Rotate/Scale/Add in More. F fits the real camera when the
viewport has focus. On narrow screens the workbench stacks below the viewport. Project
Save reuses a retained writable browser or explicitly opened server project
target, Save As chooses a new one, and a download-only browser creates a copy rather than
silently overwriting the source. A changed tab uses Save/Discard/Cancel on close.
External changes to an opened server project are conflicts, not implicit
overwrite permission. Do not assume uploaded raw structures are writable
project destinations. A direct/notebook editor adopts a multi-tab workspace in
place so the original document and writable browser handle survive opening a
new tab. A project opened in a new tab retains its `.vase` or editable-HTML
format and HTML output profile; a browser upload without write authority still
saves a download copy in that original format. Browser-handle saves recheck the
source after rendering/serialization and reject a detected external change.
Dirty state includes edits to noncurrent trajectory frames and returns clean
when Undo restores the saved scientific content and visual settings. The
identity also changes for field imports, combinations and removals. Save,
Close and Replace settle pending physical edits; invalid scientific inputs
block Save before a destination is selected. Renderer Undo/Redo restores an
editable HTML project's separate output profile. A child-tab reload retains
its project provenance, including a new target adopted by Save As. The
Image, Video and Interactive HTML GUI routes have format-specific draft controls;
Cancel in their export dialogs leaves the saved project profile unchanged. The
Objects → Fields route selects live dataset/plane properties, while Analyze →
Fields owns import and combinations; both use the same underlying field state.
Objects → Vectors opens visibility/style for displacement and stored-force layers;
Analyze retains trajectory reference, MIC, statistics and stored-data status.
The top-level workspace exposes Fullscreen editing / Keyboard Lock when supported;
normal browser tabs may reserve ⌘W/⌘N on macOS or Ctrl+W/Ctrl+N on Windows/Linux, so visible File-menu actions
remain the reliable fallback. The editor exposes an optional `display.atomRadiusMapping`
definition. Choose an actual scalar catalog ID and lock finite range limits;
its factors multiply manual size without changing physical atom radii or bond
cutoffs. Inspect every output artifact visually before relying on a mapped-size
figure. The focused
`set-atom-radius-mapping` operation can configure the field,
current-frame or trajectory fit, transform, output multipliers, exponent and
frozen base-atom scope atomically. Inspect the appearance-focused state for the
effective mapping and readiness before rendering. For example, apply
`{"operation":{"name":"set-atom-radius-mapping","field":"array::fraction::scalar","rangeMode":"current","minMultiplier":0,"maxMultiplier":1}}`.

`vase_render` returns an artifact URI plus exact camera/options/dimensions.
Use `vase_inspect_image(uri=...)` for final visual QA: MCP returns image content.
Native-function hosts embed validated artifact bytes as image input. Never print
Base64 or count a file path as image inspection. Use one final render when the
state establishes the result; add a draft only when visual composition needs it.

For same-document human lighting refinement, see the toolbar controls in the
[scene guide](references/scene-workflow.md#human-lighting-controls).

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
