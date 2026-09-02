# Deterministic Rendering From Natural Language

Use this reference when an external AI agent must turn a user's visual description
or a supplied reference figure into the same live v_ase GUI scene. It is optimized
for accurate results with few CLI round trips. Read other references only when the
task also requires physical editing, analysis, volumetric data, or export details.

## Contents

1. Minimal control loop
2. Translate visual intent into scene constraints
3. Inspect only the required state
4. Atom identity and appearance
5. Periodic composition and camera
6. Exact bond control
7. Render-camera authority
8. Verification and bounded refinement
9. Complete command template
10. Failure recovery

## 1. Minimal Control Loop

The human speaks natural language to the external agent. v_ase itself accepts
structured JSON, not natural language. Keep the GUI at `human_url` open so the
human sees every result.

Run the compact discovery call once:

```bash
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" describe --profile summary
```

The CLI's bare `schema` command returns only method, operation, export, and state
profile names. Do not request the complete schema. Before an unfamiliar operation,
request only that operation:

```bash
v_ase api "$COMMAND_URL" schema \
  --operation-schema compose-view \
  --operation-schema style-atoms \
  --operation-schema configure-bonds
```

Repeat `--operation-schema` to fetch up to 16 related contracts in one response.
For a rendering-only task, do not call the broad `capabilities` method. The
`render` state profile already includes compact appearance, so do not request
both `appearance` and `render` unless complete per-index overrides are needed.

Use one focused state profile at a time:

```bash
v_ase api "$COMMAND_URL" describe --profile structure --include-positions
v_ase api "$COMMAND_URL" describe --profile appearance
v_ase api "$COMMAND_URL" describe --profile bonding --include-positions
v_ase api "$COMMAND_URL" describe --profile render
```

Every `apply` sent through `v_ase api` returns the compact `summary` profile plus
`mutation.changedPaths` by default. Request `--response-profile appearance`,
`bonding`, or `render` only when that mutation needs immediate focused verification.
Never request `full` after every operation.

## 2. Translate Visual Intent Into Scene Constraints

Before sending commands, turn the request into this scene specification:

| Constraint | Decide explicitly |
| --- | --- |
| Physical scope | Visualization only, or an intentional ASE structure edit |
| Scene dimensionality | Flat illustration (`2d`) or shaded/material-aware (`3d`) |
| Visible repetition | Display supercell counts; never alter topology just to show repeats |
| Motif anchor | Which atom, midpoint, center of mass, or periodic motif is at image center |
| View normal | Global Cartesian direction or crystallographic cell direction |
| Screen vertical | A vector or two periodic atom references that define camera roll |
| Layer roles | Exact zero-based indices that need distinct visual labels |
| Atom appearance | Final color, material, opacity, and rendered radius in Angstrom |
| Bond policy | None, label-pair policy, or an exact list of atom-index edges |
| Framing | Outermost atoms/references, padding, projection, and output aspect ratio |
| Export | Draft dimensions, final dimensions, format, background, cell/axis/grid visibility |

Do not substitute a guessed orbit angle for a specified crystallographic normal.
Do not modify coordinates, cell, PBC, elements, constraints, or trajectory frames
when the request is only about visualization.

Natural-language examples map as follows:

- "top view along the surface normal" means an orthographic view from the
  corresponding cell axis, normally `viewFromCellAxis:"+c"` after verifying the
  cell orientation.
- "make this chain vertical" means use two exact periodic references as
  `verticalReferences`; it does not mean trial-and-error camera rolls.
- "center the oxide motif" means identify the motif indices/references and use
  `centerMotif` plus matching target or fit references.
- "show three repeats across and two upward" means display replication, not
  `make-supercell`.
- "touching spheres" means set final rendered radii so the requested projected
  neighbors meet; it does not mean increasing global zoom.
- "paper-style 2D circles" means `atomDisplayMode:"2d"`, not merely an unlit
  material on shaded spheres.

## 3. Inspect Only The Required State

Start with `summary`. It provides compressed `identityGroups` with inclusive
zero-based `indexRanges`, counts, cell/PBC, selection, revision, and a
`stateFingerprint`.

Use `structure --include-positions` only when indices, distances, motifs, or camera
roll depend on coordinates. Set `--include-properties` only when tags, charges,
magnetic moments, forces, or full identity arrays are required.

Use `appearance` for visual settings. Per-index overrides are represented by counts
unless `--include-overrides` is requested. Use `bonding` for active label-pair
policies and exact manual edges; inactive all-zero pair tables are intentionally
omitted. Use `render` for camera and export framing.

After a human GUI event, stop issuing mutations and call `describe --profile
summary`. Pass its latest `collaboration.revision` as `expectedRevision`.

## 4. Atom Identity And Appearance

`set-visual-label` assigns a role to exact indices in View mode without changing
ASE elements. Use it for substrate, adsorbate, layer, fixed-region, and highlighted
site roles. Use `set-identity` only when the user intends a physical element or
identity edit in Edit mode.

`style-atoms` accepts exact indices, visual labels, elements, or their union. The
fields are independent: omitting color, material, opacity, or radius preserves it.
`radiusAngstrom` is the final rendered atom radius after global scale.
`radiusScale` is a per-index multiplier; never send both.

For a substrate where only the top layer remains element-colored:

1. Determine substrate and top-layer index ranges from coordinates and labels.
2. Assign a substrate-only visual label to the lower-layer indices.
3. Style that visual label without changing the shared ASE element.
4. Inspect `appearance`; do not duplicate hundreds of per-index values in later
   commands.

## 5. Periodic Composition And Camera

Use `compose-view` for a reproducible periodic figure. It combines only visual
replication, visual translation, motif centering, camera direction and roll,
target, fit bounds, scene dimensionality, projection, and padding.

Important distinctions:

- `displaySupercell` repeats the visible scene and leaves ASE topology unchanged.
- `centerMotif` applies visual translation after replication.
- `viewFromCellAxis` is one of `+a`, `-a`, `+b`, `-b`, `+c`, `-c`.
- `viewDirection` is an explicit target-to-camera Cartesian vector.
- `verticalReferences` contains exactly two `{index, cellOffset}` references and
  fixes screen roll from their projected direction.
- `targetReferences` determines the camera center.
- `fitReferences` determines visible extent and atom count without changing the
  center.
- `fit:"displayed"` frames the complete displayed repetitions.
- `fit:"references"` frames only the requested periodic references.
- `preserveOrientation:true` changes target/crop while preserving accepted view
  normal and roll. It cannot be combined with orientation fields.

`cellOffset` is a three-integer periodic image offset. Use it whenever the anchor,
vertical feature, or outer fit atom is a replica. Never infer a replica from its
screen location.

Composition order is semantic, not trial-and-error:

1. choose display repetitions;
2. place the motif;
3. set view normal;
4. set screen vertical;
5. set target and fit extent;
6. choose 2D/3D and projection;
7. apply padding.

## 6. Exact Bond Control

There are three independent requests:

### No visual bonds

```json
{"name":"configure-bonds","pairs":[],"disableUnspecified":true}
```

This explicitly disables all label-pair policies.

### Label-pair allow-list

Send `pairs` and `disableUnspecified:true`. Each pair can set
`maximumAngstrom`, `style`, `material`, `thicknessAngstrom`, `colorMode`, `color`,
and `opacity`. This intentionally changes the label-pair policy.

### Exact selected edges

```json
{"name":"configure-bonds","indexPairs":[[2,20],[2,29],[11,29]]}
```

An index-only request switches to those exact zero-based base-atom edges while
preserving every existing label-pair cutoff, range, and appearance setting. Periodic
display replicas use the renderer's minimum-image connection for each base edge.
Do not send `pairs:[]` or `disableUnspecified:true` merely to select exact edges.

If exact edges also need a new shared appearance, send the required real label-pair
entries together with `indexPairs`. Do not fabricate visual labels to encode edges.
Use `clearEndpointOverrides:true` only when stale atom-level bond appearance is
known and the requested pair style must replace it.

After the mutation, inspect `mutation.changedPaths`. An index-only request must not
report changes under `display.pairwiseBondCutoffs`, `display.pairwiseBondRanges`, or
`display.pairwiseBondStyles`.

## 7. Render-Camera Authority

Before rendering, run:

```bash
v_ase api "$COMMAND_URL" describe --profile render
```

Read `effectiveRender.source` and `effectiveRender.camera`. The source is one of:

- `explicit-request`: `render` received `options.camera`;
- `render-area`: the stored Render Area camera is active;
- `image-export-profile`: a stored export camera is retained while the Render Area
  overlay is hidden;
- `viewport`: the live working camera is used.

Never assume that the viewport camera is the export camera. A `render` result returns
the exact camera actually used, not merely the current viewport camera.

Select a source explicitly when necessary:

```bash
v_ase api "$COMMAND_URL" render --save draft.webp --params '{
  "format":"webp","width":800,"height":625,"cameraSource":"render-area",
  "options":{"includeGrid":false,"includeAxes":false,"includeCell":true,
             "backgroundColor":"#ffffff"}
}'
```

Allowed `cameraSource` values are `auto`, `viewport`, `render-area`, `image-export`,
and `explicit`. `explicit` requires a complete `options.camera` object.

## 8. Verification And Bounded Refinement

Use semantic checks before pixels:

1. `mutation.changedPaths` contains only intended state paths.
2. Structure `stateFingerprint` changes only for intended structure edits. For a
   visual-only task, compare a structure profile before and after if any doubt exists.
3. The requested scene dimensionality, repetitions, labels, exact bond count, camera
   source, projection, target, and screen-up direction match the specification.
4. Render one draft at 600-1000 pixels on the long side and inspect it visually.
5. Correct one semantic cause at a time: motif anchor, orientation, visible extent,
   radii, occlusion, color/material, or bond policy.
6. Render the requested final dimensions once.

Stop after two draft refinements unless the user explicitly asks for further visual
tuning. Do not alternate undo/redo or repeatedly re-read full state. If the same
`stateFingerprint` and effective render camera produce the same defect, another
identical render cannot fix it.

## 9. Complete Command Template

```bash
# One compact discovery pass.
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" describe --profile summary

# Read exact contracts only for operations that will be used.
v_ase api "$COMMAND_URL" schema \
  --operation-schema style-atoms \
  --operation-schema configure-bonds \
  --operation-schema compose-view

# Read coordinates and current render authority once.
v_ase api "$COMMAND_URL" describe --profile structure --include-positions
v_ase api "$COMMAND_URL" describe --profile render

# Each apply automatically returns summary plus mutation.changedPaths.
v_ase api "$COMMAND_URL" apply --params-file style.json
v_ase api "$COMMAND_URL" apply --params-file bonds.json \
  --response-profile bonding
v_ase api "$COMMAND_URL" apply --params-file composition.json \
  --response-profile render

# One draft and one final image; Base64 never enters the agent context.
v_ase api "$COMMAND_URL" render --params-file draft.json --save draft.webp
v_ase api "$COMMAND_URL" render --params-file final.json --save final.png
```

Each apply file should include the latest `expectedRevision`. Re-read only `summary`
after a revision conflict or human event.

## 10. Failure Recovery

| Symptom | Correct response |
| --- | --- |
| Unsupported field or wrong nesting | Request only that operation's schema; do not guess another wrapper shape |
| Revision conflict | Read summary, review the human event, rebuild the command with the new revision |
| Correct viewport but wrong export crop | Inspect `render` profile and effective camera source |
| Exact edges changed unrelated pair settings | Use index-only `configure-bonds`; report a regression if pair-policy paths changed |
| Too many tokens or repeated long outputs | Stop reading full schema/state; use focused profiles and CLI default apply response |
| Correct semantics but wrong image | Inspect the draft and change one composition constraint, not arbitrary orbit/zoom values |
| Wrong periodic motif count | Change display replication or fit references; do not edit the physical supercell |
| Correct colors but wrong layer role | Recompute index ranges from structure coordinates and use visualization-only labels |

If a documented command conflicts with the live focused schema, the live schema is
authoritative. Record the mismatch, correct the canonical skill, and add a regression
instead of silently inventing a workaround.
