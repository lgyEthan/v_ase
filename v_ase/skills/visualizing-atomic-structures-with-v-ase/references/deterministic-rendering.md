# Deterministic rendering

## Minimal display edits

Start with the compact scene snapshot. Preserve accepted orientation, framing,
colors, radii and scientific data unless the user requests their change.
For flat atoms with hidden bonds use the initially loaded `vase_style_scene`:
`atom_display_mode="2d", show_bonds=false`.
Do not load coordinates, all appearance profiles or every tool schema for this.

## Exact bonds and appearance

Visual bonds are a drawing policy, independent of calculator interactions.
Hiding bonds changes visibility only. A label-pair allow-list is a different
request: use `vase_configure_bonds` with explicit pairs and
`disable_unspecified=true` only when policy replacement is intended.

For exact edges use `index_pairs`, preserving existing cutoffs/ranges/styles.
Resolve atoms through current scene/structure state; do not copy example indices.
A full manual-edge list can also be set within a scene patch with
`bond_mode="manual"`, `manual_bond_pairs=[...]`, and `show_bonds=true`.
An off-crop edge remains a configured edge. Use `visible_only=false` when checking
that all other atoms are unbonded. Pixel agreement alone cannot prove the graph.

Renderer segments resolve global, label-pair and endpoint appearance. A global
fallback need not equal a pair override when the override supplies the requested
style. Keep effective colors/materials/thicknesses correct instead of chasing an
irrelevant fallback representation. `clear_endpoint_overrides` is appropriate
only when explicitly replacing those overrides.

## Camera and crop

Use the snapshot's `render.source`, camera and output dimensions. The viewport,
stored Render Area and image-export profile can have different cameras. Preserve
the actual export source for an accepted figure. `camera_source="explicit"` on
render requires `options.camera`; otherwise use auto, viewport, render-area or
image-export as the task requires.

For new composition discover `vase_compose_view`: define view normal, screen up,
anchor/target and fit extent from structure geometry. Prefer a deterministic
composition to repeated orbit/zoom guesses. For an orthographic export, output
height and `ortho_scale` determine scale; output dimensions determine aspect.
The snapshot accounts for display translation and periodic replicas.

## Selection and final rendering

Publication rendering is the default. It suppresses atom-selection outlines and
uses neutral plane borders while retaining scientific constraint markings.
`selection_appearance="interactive"` preserves selected appearance; it is not a
screenshot of GUI panels. `include_plane_borders=false` omits plane perimeters.
Plane selection is explicit in `interaction` and the optional plane section.

Check readiness and state, render at the requested dimensions, and inspect the
returned artifact with `vase_inspect_image`. Use a draft only if composition is
uncertain. If a render differs with the same camera, inspect selection, effective
styles, readiness and source before changing unrelated settings. Never create
and remove dummy scene objects as a selection workaround.
