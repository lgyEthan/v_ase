# Semantic API

## Contents

1. Transport And Connection
2. State
3. Apply Command
4. Camera
5. Selection And Measurement
6. Structure Operations
7. Appearance And Bonds
8. Cell, View, Lighting, And Constraints
9. Trajectory Analysis
10. Rendering
11. Export
12. Multi-Document Control

## Transport And Connection

`v_ase gui STRUCTURE --cli` launches the application. The first stdout line is
the JSON handshake; later stdout lines are revisioned collaboration events.
It does not read commands from stdin and does not accept natural language. An
external agent opens `human_url`, then POSTs commands through `command_url`.
The supported terminal client is:

```bash
v_ase api "$COMMAND_URL" ready
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" capabilities
v_ase api "$COMMAND_URL" describe --params '{"includePositions":false}'
```

Every request sends `{"method":METHOD,"params":VALUE}` and returns one envelope
whose semantic value is under `result`. Use `--params-file` for complex JSON
and `--save OUTPUT` for render/export data URLs. The optional
`window.v_aseAI` object exposes the same method names for controllers that can
reliably evaluate page-main-world JavaScript. Do not require that access.

The examples below use `ai.method(...)` as concise method-and-parameter
notation. A vendor-neutral agent must send the same method and parameter object
with `v_ase api`.

`ready()` returns protocol, readiness, session ID, document name, and current
collaboration revision.
`schema` returns the live `apply` JSON Schema plus `operation_parameters` and
`export_parameters`. `capabilities()` returns supported state fields, command
groups, operations, exports, `schemaUrl`, and the same parameter maps.

Read [Live Human-Agent Collaboration](collaboration.md) before sharing control
with a human. It defines the NDJSON event fields, multi-tab routing, and
revision conflict behavior.

## State

```bash
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'
```

`describe()` returns document name, View/Edit mode, frame and frame count, atom
count, labels, ASE elements, atomic numbers, positions, cell, PBC, constraints,
forces, calculator attachment/name/details, charges, tags, magnetic moments,
selection references, measurements, display settings, camera, image export profile, and
`collaboration.revision`.

Scientific state in `describe()` is summarized to keep large structures
token-efficient: symmetry operations, per-atom equivalence arrays, phonon
participation arrays, and complex eigenvectors are omitted. Use the direct
endpoint under `schema.scientific_endpoints` only when those full arrays are
required.

Use `includePositions: false` for metadata-only inspection of a very large
frame. Re-enable positions before coordinate-dependent work.

Mutation methods return semantic state after the requested change. `render()`
and `export()` instead return a data URL with format, MIME type, filename, byte
count, and render dimensions where applicable.

## Apply Command

`apply()` accepts any compatible combination:

| Key | Purpose |
| --- | --- |
| `expectedRevision` | Reject a stale mutation instead of overwriting a newer human edit |
| `frame` | Load a zero-based trajectory frame |
| `mode` | `"view"` or `"edit"` |
| `display` | Merge visual settings |
| `quality` | Anti-aliasing and sphere quality |
| `applyConstraints` | Enable or disable constraint enforcement |
| `camera` | Projection, axis, explicit camera, fit, or screen orbit |
| `selection` | Replace or extend atom/replica selection |
| `operation` | One semantic structure or analysis operation |

Do not send unknown keys. Use `schema`, `capabilities()`, and `schema_url` as
the current authority. Read `collaboration.revision` immediately before a mutation and pass
it as `expectedRevision`:

```javascript
const before = await ai.describe({includePositions: true});
const after = await ai.apply({
  expectedRevision: before.collaboration.revision,
  selection: {clear: true, indices: [0, 4, 9]}
});
```

If the revision changed, call `describe()` and review the newer human edit
before constructing another command.

## Camera

Deterministic axis views:

```javascript
await ai.apply({camera: {axis: "+Z", fit: "structure"}});
```

Accepted axes are `+X`, `-X`, `+Y`, `-Y`, `+Z`, and `-Z`.

Explicit reproducible camera:

```javascript
await ai.apply({
  camera: {
    projection: "orthographic",
    position: [12, -16, 10],
    target: [2, 2, 1],
    up: [0, 0, 1]
  }
});
```

Screen-relative orbit:

```javascript
await ai.apply({
  camera: {orbit: {direction: "left", degrees: 15}}
});
```

Directions are `left`, `right`, `up`, `down`, `roll-cw`, and `roll-ccw`.
Camera navigation does not enter undo history. `undo` and `redo` are reserved
for structure mutations and visualization settings.

## Selection And Measurement

Base-atom selection uses zero-based indices:

```javascript
await ai.apply({selection: {clear: true, indices: [0, 4, 9]}});
```

Periodic replica selection in View mode uses stable references:

```javascript
await ai.apply({
  selection: {
    clear: true,
    references: [
      {index: 4, cellOffset: [0, 0, 0]},
      {index: 4, cellOffset: [1, 0, 0]}
    ]
  }
});
```

Measurements are ordered:

- one atom: atom summary;
- two atoms: direct, MIC, and replica-to-unit-cell distances when applicable;
- three atoms: angle `a1-a2-a3`;
- four atoms: ordered torsion;
- larger selections: total and per-label counts.

Never sort a user-defined two-, three-, or four-atom measurement order.

## Structure Operations

Pass `operation` as a name string or object:

| Operation | Fields | Effect |
| --- | --- | --- |
| `wrap` | none | Wrap current View frame or all Edit frames |
| `translate-all` | `vector`, `coordinateMode` | Physically move every atom, leave cell fixed |
| `set-supercell` | `reps` | Materialize repeated cell in every frame |
| `make-supercell` | integer `matrix` | Apply ASE `make_supercell` |
| `add-atom` | `label`/`element`, `position` | Add one atom |
| `delete-selection` | selection or `indices` | Delete and remap constraints |
| `set-identity` | selection/`indices`, `label`, optional `element` | Set visual label and optional ASE element |
| `set-constraints` | selection/`indices`; `fixAtoms`; `kind` = `fixed_line`/`fixed_plane`; `vector`; `clearDirectional` | Edit supported constraints |
| `move-selection` | `vector` | Translate selected atoms |
| `rotate-selection` | `axis`, `angleDeg`, optional `pivot` | Rotate selected atoms |
| `undo` / `redo` | none | Traverse structure or visualization-setting history |
| `reset-coordinates` | none | Restore loaded coordinates and original cell |
| `start-relaxation` | `fmax`, `steps`, optional `calculator` | Start optimization |
| `stop-relaxation` | none | Request optimizer stop |
| `refresh-displacements` | optional `display` | Recompute displacement vectors |

All physical edits except View-mode wrapping require Edit mode. For a
nonphysical scene offset in either mode, set `display.translation` and
`display.translationMode` instead of calling `translate-all`:

```javascript
await ai.apply({mode: "edit"});
await ai.apply({
  selection: {clear: true, indices: [3, 4, 5]},
  operation: {
    name: "rotate-selection",
    axis: [0, 0, 1],
    angleDeg: 30,
    pivot: "selection",
    applyConstraints: true
  }
});
```

```javascript
await ai.apply({
  mode: "view",
  display: {
    supercell: [2, 2, 1],
    translationMode: "fractional",
    translation: [0.5, 0, 0]
  }
});
```

Visual translation is an absolute display setting, is evaluated after
supercell repetition, moves atoms/bonds/constraints/analysis overlays together,
and does not alter ASE coordinates or the unit cell. Setting it to `[0,0,0]`
removes the offset.

`pivot` is `"selection"`, `"active"`, `"origin"`, `"cell"`, or an explicit
three-vector. For `"active"`, the last entry in the explicit `indices` array is
the pivot atom and remains fixed.

Constraint edit:

```javascript
await ai.apply({
  selection: {clear: true, indices: [10, 11]},
  operation: {
    name: "set-constraints",
    fixAtoms: false,
    kind: "fixed_plane",
    vector: [0, 0, 1]
  }
});
```

Use `clearDirectional: true` to remove FixedLine/FixedPlane while preserving
FixAtoms. Constraints are ultimately applied by the ASE backend.

## Appearance And Bonds

Atom settings:

| Setting | Values |
| --- | --- |
| `atomRadiusScale` | positive global radius multiplier |
| `labelRadii` | `{label: radius}` |
| `labelColors` | `{label: "#rrggbb"}` |
| `labelVisible` | `{label: boolean}` |
| `labelMaterials` | `{label: "standard"|"metal"|"rubber"}` |
| `atomMaterials` | `{atomIndex: material}` in Edit |
| `atomDisplayMode` | `"3d"` or `"2d"` |

Bond settings:

| Setting | Values |
| --- | --- |
| `showBonds` | boolean |
| `bondMode` | `"auto"`, `"pairwise"`, or `"manual"` |
| `bondCutoffScale` | automatic cutoff multiplier |
| `pairwiseBondRanges` | label-pair `{enabled,max}` records |
| `pairwiseLabelColumnWidth` | resizable pair-label column width in pixels |
| `manualBondPairs` | atom-index pairs |
| `showPeriodicBonds` | include periodic/MIC boundary bonds |
| `bondStyle` | `"cylinder"` or `"flat"` |
| `bondThickness` | bond diameter in Angstrom |
| `bondColorMode` | `"split"` or `"custom"` |
| `bondCustomColor` | `"#rrggbb"` |

Pairwise bond keys use visual labels. A pair with `enabled: false` and `max: 0`
is disabled. Bonds update per frame and during interactive edits.

## Cell, View, Lighting, And Constraints

| Setting | Values |
| --- | --- |
| `supercell` | display repetition `[nx,ny,nz]` |
| `translation` | absolute visual atom offset `[x,y,z]` |
| `translationMode` | `"cartesian"` or `"fractional"` |
| `showCell`, `showAxes`, `showGrid`, `showOverlays` | boolean |
| `cellThickness` | diameter in Angstrom |
| `cellColor` | `"#rrggbb"` |
| `cellMaterial` | `"unlit"`, `"standard"`, or `"metal"` |
| `projectionMode` | `"orthographic"` or `"perspective"` |
| `viewportBackground` | `"white"` or `"dark"` |
| `lightingMode` | `"modeling"`, `"studio"`, or `"studio-shadow"` |
| `sunIntensity` | non-negative number |
| `sunPosition`, `sunTarget` | finite three-vectors |
| `sunGizmo` | boolean |

Transform and commensurate settings:

| Setting | Values |
| --- | --- |
| `rotatePivot` | `"selection"`, `"active"`, `"origin"`, or `"cell"` |
| `commensurateGuide` | show periodic 2D match candidates |
| `commensurateSnap` | snap to a candidate |
| `commensurateStrainTolerance` | fractional boundary strain |
| `commensurateMaxIndex` | integer search bound |
| `commensurateSnapRangeDeg` | angular snap window |

Constraint visualization includes FixAtoms, FixScaled, FixedLine, FixedPlane,
and Hookean. FixedLine uses one straight axis through the atom center and never
uses a ring. During `G`, it adds a longer direction guide through the original
position. FixedPlane uses a local ring, crosshair, and normal marker. FixScaled
adopts the line or plane design from its allowed Cartesian degrees of freedom.
These compact per-atom markers remain visible without selection.
Selected atoms retain a yellow sphere outline without a billboard ring, so a
selection cannot be mistaken for a plane constraint.
During an interactive `G` transform, every selected FixedPlane atom
shows a larger permitted-plane surface anchored at its original position.
Hookean active state is a 3D helix after its cutoff.

Interactive atom rotation shows an axis through the selected pivot, a fixed
start reference, and a moving current reference. Commensurate candidates are
separate guides. These overlays are visual state and do not alter the ASE
coordinates returned by `describe()`.

## Trajectory Analysis

Set frames with `apply({frame: n})`. Selection persists when topology permits.

Displacement example:

```javascript
await ai.apply({
  frame: 12,
  operation: {
    name: "refresh-displacements",
    display: {
      showDisplacements: true,
      displacementReferenceMode: "frame",
      displacementReferenceFrame: 0,
      displacementMic: true,
      displacementStyle: "3d",
      displacementScale: 1.0,
      displacementThickness: 0.08,
      displacementColor: "#e58b2a"
    }
  }
});
```

Reference mode is `"previous"` or `"frame"`. Style is `"3d"` or `"2d"`.
Vectors begin at each atom's currently visible position, repeat across the
displayed supercell, and keep their physical value when visual translation
moves both endpoints.

## Symmetry And Phonons

The symmetry alpha exposes these operations through `apply()`:

- `analyze-symmetry`
- `symmetry-path`
- `standardize-symmetry`
- `generate-phonon-displacements`
- `inspect-phonon-modes`
- `generate-phonon-mode`

Use the exact parameters and verification rules in
`references/symmetry-and-phonons.md`. The first two are nonmutating.
Standardization and generated trajectories require Edit mode and replace the
current trajectory after creating an Undo checkpoint. A completed phonopy YAML
is uploaded to the direct endpoint reported by `schema.scientific_endpoints`;
binary file upload is deliberately not embedded in an `apply()` JSON object.

## Rendering

`render()` uses the exact image-export camera and aspect ratio:

```bash
v_ase api "$COMMAND_URL" render --save figure.webp --params '{
  "format":"webp",
  "width":3840,
  "height":2160,
  "options":{
    "transparentBackground":false,
    "backgroundColor":"#ffffff",
    "includeGrid":false,
    "includeAxes":false,
    "includeCell":true,
    "scaleMode":"viewport",
    "sphereQuality":"ultra",
    "sphereQualityScale":1.25,
    "renderMode":"studio-shadow",
    "sunIntensity":2.4,
    "sunPosition":[8,-10,14],
    "sunTarget":[0,0,0]
  }
}'
```

PNG is the default. Use WebP for compact lossless output, JPEG for compact
opaque output, or PDF for a single raster page. Every format preserves
requested pixel dimensions; JPEG and PDF flatten transparency onto white.
`scaleMode: "physical"` requires `pixelsPerAngstrom`; `"viewport"` preserves
live framing.

The result includes data URL, MIME type, dimensions, byte count, camera, and
effective options. Decode and inspect it; do not crop a page screenshot.

## Export

```bash
v_ase api "$COMMAND_URL" export --params '{"format":"poscar"}' \
  --save POSCAR
```

Supported formats:

| Format | Output |
| --- | --- |
| `image` | PNG/JPEG/PDF/WebP, using render fields plus `imageFormat` |
| `video` | MOV/H.264 or AVI/MPEG-4 |
| `poscar` | current structure |
| `pickle` | ASE state and valid SinglePointCalculator |
| `blender` | optimized Blender Python scene |
| `3dm` | Rhino scene, optional dependency |
| `obj` | OBJ/MTL/camera metadata ZIP |
| `html` | offline view-only 3D document; `.vase` recovery is optional |
| `project` | self-contained `.vase` project |
| `settings` | reusable visual settings without coordinates |

Standalone HTML:

```bash
v_ase api "$COMMAND_URL" export --save shared-view.html --params '{
  "format":"html",
  "width":1920,
  "height":1080,
  "embedProject":false,
  "options":{
    "includeGrid":false,
    "includeAxes":true,
    "includeCell":true
  }
}'
```

The returned data URL is one offline document with no CDN dependency. It
allows camera navigation and trajectory playback but exposes no editing or
settings controls. HTML uses the same export-camera composition as image and
video. Grid defaults off; axes and unit cell default on. `embedProject`
defaults to `false` for a smaller view-only file. Set it to `true` only when
lossless `.vase` recovery is required; the human **HTML Project** action uses
that embedded mode by default.
Decode the data URL, open it from `file://`, wait for
`window.v_aseStandalone.ready`, verify `document.body.dataset.viewOnly` is
`"true"`, and reject any HTTP/HTTPS request before reporting success. For
embedded mode, also verify `window.v_aseStandalone.hasEmbeddedProject` and
reopen the written file with `v_ase gui FILE.html`.
The document also carries the exact rendered frame as a static poster, so
macOS Finder/Quick Look can preview it without executing JavaScript. The poster
contains only the Preview Area frame: no v_ase logo, header, page margin, or
decorative border. Its optimized high-resolution raster and the adaptive
device-pixel-ratio WebGL canvas share one integer-sized viewport. In a browser
the first completed live frame automatically cross-fades over the poster
before camera input begins, without moving or resizing the structure.

Video:

```bash
v_ase api "$COMMAND_URL" export --save trajectory.mov --timeout 1800 --params '{
  "format":"video",
  "container":"mov",
  "width":1920,
  "height":1080,
  "fps":30,
  "interpolationMultiplier":2,
  "interpolationMic":true,
  "options":{
    "includeGrid":false,
    "includeAxes":false,
    "includeCell":true,
    "renderMode":"studio-shadow",
    "sphereQuality":"high"
  }
}'
```

For `N` source frames and multiplier `m`, output contains
`(N - 1) * m + 1` frames. Interpolation requires stable atom count, ordering,
elements, and labels.

## Multi-Document Control

On the workspace page:

```bash
v_ase api "$COMMAND_URL" documents
v_ase api "$COMMAND_URL" activate --params '{"sessionId":"SESSION_ID"}'
v_ase api "$COMMAND_URL" newDocument
```

Each document has independent structure, trajectory, display, camera, history,
and `.vase` output. Call `documents()` before switching.
