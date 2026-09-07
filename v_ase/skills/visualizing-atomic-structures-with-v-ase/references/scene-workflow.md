# Scene workflow

## Inspect the actual figure

`vase_scene_snapshot` defaults to a short summary, including the camera source,
image dimensions, rendering readiness and interaction state. Geometry is opt-in:
`sections=["atoms","bonds","planes"]`. Filter by element, visual label or base
index. Coordinates include the display translation and periodic cell offsets.
The `screen`/`pixels` fields refer to the output canvas, not the GUI chrome.
`render.outputCamera` also reports the projection after physical-scale and output
aspect adjustments; `render.camera` identifies the source camera configuration.
Visibility is enabled geometry intersecting the camera frustum; transparent
compositing and occlusion still require the final image.

Pages contain `total`, `offset`, `limit` and `nextOffset`. Send the returned
`sceneFingerprint` as `expected_scene_fingerprint` for subsequent pages. A scene
change rejects continuation; restart at offset zero. A geometry request scanning
more than 200,000 references is rejected with filtering guidance. The default
summary remains available. Commensurate proposals are explicitly identified;
base indices must not be mistaken for proposal row indices.

## Patch related visual settings

Discover `vase_apply_scene`; provide the inspected document/revision and a typed
`patch`. A two-setting edit uses one patch. `display` exposes the existing typed
visual settings, so a patch can coordinate atom style, exact manual edge lists,
colorscales, displacement presentation, surfaces, planes, camera and frame.
Use existing dataset and field IDs. Stored scientific arrays are not accepted.

The initially loaded `vase_style_scene` is the short-schema entry point for common
toggles, atom mode/scale and background. It uses the same transaction internally.
Use it directly for simple edits instead of loading the full display schema.

Omitted fields survive. Label/atom/pair maps merge, preserving unmentioned entries
and unmentioned fields in existing style entries. Arrays are replacements:
provide the complete intended `manual_bond_pairs` or `volumetric_planes` list.
`map_mode="replace"` makes a supplied map an explicit replacement, including {}.
Do not change global bond style merely to override pair styles; inspect the
resolved segment appearance. To hide bonds use `show_bonds=false` only.

`plane_selection={"plane_ids":[]}` deselects planes explicitly. `clear_selections`
clears all selection types; do not combine it with explicit selection fields.
The raw operation is `select-volumetric-planes`. Selecting nonempty plane IDs
follows GUI rules and clears atom selection and the light handle. Do not combine
an atom selection with a nonempty plane selection in one `apply-scene` patch.
Publication export neutralizes selection appearance without changing selection,
which is preferable when selection also defines a colorscale or analysis scope.

## Completion and failure

The transaction validates before editing, waits for tracked rendering work, and
records one scene undo step. Interactive input is held during the transaction.
On failure it restores the prior visual/frame state and reports `rolled_back`;
if restoration also fails it reports `unknown` and requires inspection.
The receipt provides applied requested values, changed paths, readiness and a
new revision. Receipts may explicitly truncate large values or long change lists.
Do not describe every profile after a complete small receipt.

`vase_undo`/`vase_redo` restore scene transactions as one unit. Physical mutations
remain separate dedicated tools, with their own scientific validation and history.
Use `vase_scene_readiness(wait=false)` to monitor pending work without reading
geometry. Exact capture requires paused playback and settled requested overlays.
