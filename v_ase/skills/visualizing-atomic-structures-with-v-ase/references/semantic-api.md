# Semantic API

## Contents

1. Connection And State
2. Apply Command
3. Camera
4. Selection And Measurement
5. Structure Operations
6. Appearance And Bonds
7. Cell, View, Lighting, And Constraints
8. Trajectory Analysis
9. Rendering
10. Export
11. Multi-Document Control

## Connection And State

```javascript
const ai = window.v_aseAI;
await ai.ready();
const capabilities = await ai.capabilities();
const state = await ai.describe({includePositions: true});
```

`describe()` returns document name, View/Edit mode, frame and frame count, atom
count, labels, ASE elements, atomic numbers, positions, cell, PBC, constraints,
forces, charges, tags, magnetic moments, selection references, measurements,
display settings, camera, and image export profile.

Use `includePositions: false` for metadata-only inspection of a very large
frame. Re-enable positions before coordinate-dependent work.

## Apply Command

`apply()` accepts any compatible combination:

| Key | Purpose |
| --- | --- |
| `frame` | Load a zero-based trajectory frame |
| `mode` | `"view"` or `"edit"` |
| `display` | Merge visual settings |
| `quality` | Anti-aliasing and sphere quality |
| `applyConstraints` | Enable or disable constraint enforcement |
| `camera` | Projection, axis, explicit camera, fit, or screen orbit |
| `selection` | Replace or extend atom/replica selection |
| `operation` | One semantic structure or analysis operation |

Do not send unknown keys. Use `capabilities()` and `schema_url` as the current
authority.

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
Camera operations enter history and can be undone.

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
| `set-constraints` | selection/`indices`, constraint fields | Edit supported constraints |
| `move-selection` | `vector` | Translate selected atoms |
| `rotate-selection` | `axis`, `angleDeg`, optional `pivot` | Rotate selected atoms |
| `undo` / `redo` | none | Traverse structure or camera history |
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

`pivot` is `"selection"`, `"origin"`, `"cell"`, or an explicit three-vector.

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
| `rotatePivot` | `"selection"`, `"origin"`, or `"cell"` |
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

## Rendering

`render()` uses the exact image-export camera and aspect ratio:

```javascript
const image = await ai.render({
  format: "webp",
  width: 3840,
  height: 2160,
  options: {
    transparentBackground: false,
    backgroundColor: "#ffffff",
    includeGrid: false,
    includeAxes: false,
    includeCell: true,
    scaleMode: "viewport",
    sphereQuality: "ultra",
    sphereQualityScale: 1.25,
    renderMode: "studio-shadow",
    sunIntensity: 2.4,
    sunPosition: [8, -10, 14],
    sunTarget: [0, 0, 0]
  }
});
```

PNG is the default. Use WebP for compact lossless output, JPEG for compact
opaque output, or PDF for a single raster page. Every format preserves
requested pixel dimensions; JPEG and PDF flatten transparency onto white.
`scaleMode: "physical"` requires `pixelsPerAngstrom`; `"viewport"` preserves
live framing.

The result includes data URL, MIME type, dimensions, byte count, camera, and
effective options. Decode and inspect it; do not crop a page screenshot.

## Export

```javascript
const result = await ai.export({format: "poscar"});
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

```javascript
const sharedView = await ai.export({
  format: "html",
  embedProject: true
});
if (
  sharedView.mimeType !== "text/html"
  || !sharedView.filename.endsWith(".html")
  || sharedView.bytes <= 0
) {
  throw new Error("Standalone HTML export failed validation.");
}
```

The returned data URL is one offline document with no CDN dependency. It
allows camera navigation and trajectory playback but exposes no editing or
settings controls. `embedProject` defaults to `true`; keep it enabled for
lossless `.vase` recovery or set it to `false` for a smaller view-only file.
Decode the data URL, open it from `file://`, wait for
`window.v_aseStandalone.ready`, verify `document.body.dataset.viewOnly` is
`"true"`, and reject any HTTP/HTTPS request before reporting success. For
embedded mode, also verify `window.v_aseStandalone.hasEmbeddedProject` and
reopen the written file with `v_ase gui FILE.html`.

Video:

```javascript
const movie = await ai.export({
  format: "video",
  container: "mov",
  width: 1920,
  height: 1080,
  fps: 30,
  interpolationMultiplier: 2,
  interpolationMic: true,
  options: {
    includeGrid: false,
    includeAxes: false,
    includeCell: true,
    renderMode: "studio-shadow",
    sphereQuality: "high"
  }
});
```

For `N` source frames and multiplier `m`, output contains
`(N - 1) * m + 1` frames. Interpolation requires stable atom count, ordering,
elements, and labels.

## Multi-Document Control

On the workspace page:

```javascript
const docs = await ai.documents();
await ai.activate(docs[0].sessionId);
await ai.newDocument();
```

Each document has independent structure, trajectory, display, camera, history,
and `.vase` output. Call `documents()` before switching.
