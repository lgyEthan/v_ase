# v_ase Agent Skill

This file is the vendor-neutral control contract for AI agents using v_ase.
It works with Claude Code, Codex, browser agents, and any other system that can
run a command and evaluate JavaScript in a browser page. No model-specific
plugin or screenshot loop is required.

## Objective

Use semantic structure data to inspect, edit, analyze, style, and export atomic
structures. Read coordinates and state directly, choose a deterministic camera,
then request the final render from the same export pipeline used by the GUI.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Start A Session

```bash
v_ase gui STRUCTURE --for-ai
```

The first stdout line is one JSON handshake. Keep the process running. Important
fields are:

| Field | Meaning |
| --- | --- |
| `human_url` | Normal live GUI for browser control or immediate human takeover |
| `state_url` | Current semantic structure and trajectory state |
| `schema_url` | Machine-readable JSON Schema for `apply()` |
| `skill_url` | This guide served by the running v_ase process |
| `browser_api` | `window.v_aseAI` |
| `skill_path` | Installed copy of this Markdown file |

Useful startup variants:

```bash
v_ase gui TRAJECTORY --index : --for-ai
v_ase gui AMBIGUOUS_FILE --format POSCAR --for-ai
v_ase gui STRUCTURE --interactive --for-ai
v_ase gui HOST:/remote/path/TRAJECTORY --for-ai
```

For `HOST:/path` input, file parsing and trajectory storage stay on the remote
host. The browser receives the live frame data required for visualization; the
original file is not downloaded to the local machine.

## Connect

Open `human_url` with a browser automation tool, then:

```javascript
const ai = window.v_aseAI;
await ai.ready();
await ai.capabilities();
const state = await ai.describe();
```

The workspace page and active editor frame expose the same API. On the
workspace page these document methods are also available:

```javascript
await ai.documents();
await ai.activate(sessionId);
await ai.newDocument();
```

Use `documents()` before changing tabs. Every document has independent
coordinates, trajectory, visual state, history, and `.vase` project output.

## Required Agent Workflow

1. Call `ready()`.
2. Call `describe()` and reason from semantic data, not screenshots.
3. Apply one deterministic change at a time with `apply()`.
4. Call `describe()` after a physical edit and verify positions, labels, cell,
   PBC, constraints, selection, and frame.
5. Call `render()` for camera iteration.
6. Call `export()` only after the semantic state and camera are accepted.
7. Give `human_url` to the user whenever manual adjustment is preferred.

## Semantic State

`describe({includePositions: true})` returns:

- document name, View/Edit mode, frame, frame count, and atom count;
- visual labels, ASE chemical symbols, atomic numbers, positions, cell, and PBC;
- forces, charges, tags, magnetic moments, and serialized ASE constraints;
- label and element counts;
- ordered base/replica selection references and measurement text;
- display settings, camera state, and image export profile.

Set `includePositions: false` when only metadata is required for a very large
frame.

`state_url` provides the backend state without browser automation. Use the
browser `describe()` result when current replica selections, live camera, or
uncommitted viewport state matters.

## Apply Commands

`apply()` accepts any compatible combination of the following top-level keys:

| Key | Purpose |
| --- | --- |
| `frame` | Load a zero-based trajectory frame |
| `mode` | Switch to `"view"` or `"edit"` |
| `display` | Merge visual settings |
| `quality` | Set anti-aliasing and atom sphere quality |
| `applyConstraints` | Enable or disable ASE constraint enforcement for edits |
| `camera` | Set projection, axis view, explicit camera, fit, or screen orbit |
| `selection` | Replace or extend atom/replica selection |
| `operation` | Run one semantic structure or analysis operation |

Example:

```javascript
await ai.apply({
  frame: 0,
  mode: "view",
  quality: {antiAliasing: true, sphereQuality: "high"},
  display: {
    viewportBackground: "white",
    showBonds: true,
    showGrid: false,
    showAxes: false,
    showCell: true,
    projectionMode: "orthographic",
    atomDisplayMode: "3d",
    lightingMode: "studio-shadow",
    sunIntensity: 2.4
  },
  camera: {axis: "+Z", fit: "structure"}
});
```

### Camera

Deterministic axis views are `+X`, `-X`, `+Y`, `-Y`, `+Z`, and `-Z`.

```javascript
await ai.apply({camera: {axis: "+Z", fit: "structure"}});
```

Use an explicit camera when reproducibility matters:

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

Screen-relative orbit directions are `left`, `right`, `up`, `down`, `roll-cw`,
and `roll-ccw`:

```javascript
await ai.apply({camera: {orbit: {direction: "left", degrees: 15}}});
```

Camera operations change only the view. `undo` can restore camera history.

### Selection And Measurement

Select base atoms by zero-based index:

```javascript
await ai.apply({selection: {clear: true, indices: [0, 4, 9]}});
```

In View mode, select a periodic replica with a stable reference:

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

`describe().measurement` reports:

- one atom: selected atom summary;
- two atoms: direct, MIC, and replica-to-unit-cell distance when applicable;
- three atoms: ordered angle;
- four atoms: ordered torsion;
- larger selections: total and per-label counts.

Do not sort a user-defined 2/3/4-atom measurement order.

### Structure Operations

Pass a string for parameter-free operations or an object with `name`.

| Operation | Required or common fields | Effect |
| --- | --- | --- |
| `wrap` | none | Wrap current visible frame in View; all frames in Edit |
| `translate-all` | `vector`, optional `coordinateMode` | Move every atom, leave cell fixed |
| `set-supercell` | `reps: [nx,ny,nz]` | Materialize the repeated cell in every frame |
| `make-supercell` | `matrix: [[...],[...],[...]]` | Apply integer ASE `make_supercell` transform |
| `add-atom` | `label` or `element`, `position` | Add one atom |
| `delete-selection` | selection or `indices` | Delete atoms and remap supported constraints |
| `set-identity` | selection/`indices`, `label`, optional `element` | Change visual label and optional ASE element |
| `set-constraints` | selection/`indices`, fields below | Edit FixAtoms/FixedLine/FixedPlane |
| `move-selection` | `vector` | Translate selected atoms |
| `rotate-selection` | `axis`, `angleDeg`, optional `pivot` | Rotate selected atoms |
| `undo` / `redo` | none | Traverse structure or camera history |
| `reset-coordinates` | none | Restore loaded coordinates and original cell |
| `start-relaxation` | optional `fmax`, `steps`, `calculator` | Start ASE optimization and relaxation timeline |
| `stop-relaxation` | none | Request optimizer stop |
| `refresh-displacements` | optional `display` | Recompute trajectory displacement vectors |

Examples:

```javascript
await ai.apply({
  operation: {
    name: "translate-all",
    vector: [0.5, 0, 0],
    coordinateMode: "cartesian",
    applyConstraints: true
  }
});

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

`pivot` can be `"selection"` (default), `"origin"`, `"cell"`, or an explicit
three-vector.

Edit constraints:

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

Use `clearDirectional: true` to remove FixedLine/FixedPlane while leaving
FixAtoms unchanged. Use `fixAtoms: true` or `false` independently.

All physical editing operations require Edit mode. Unless `applyConstraints` is
false, the ASE backend is authoritative and applies the current constraints to
the requested positions.

## Complete Visual Configuration

Set these through `apply({display: {...}})`. Values not provided are preserved.

### Atoms And Materials

| Setting | Values |
| --- | --- |
| `atomRadiusScale` | Global positive radius multiplier |
| `labelRadii` | `{label: radius}` |
| `labelColors` | `{label: "#rrggbb"}` |
| `labelVisible` | `{label: boolean}` |
| `labelMaterials` | `{label: "standard"|"metal"|"rubber"}` |
| `atomMaterials` | `{atomIndex: "standard"|"metal"|"rubber"}` in Edit |
| `atomDisplayMode` | `"3d"` or `"2d"` |

Visual labels and ASE elements are intentionally separate. A label such as
`O_bridge` can retain chemical element `O`. `set-identity` changes the label
only unless `element` is provided.

### Bonds

| Setting | Values |
| --- | --- |
| `showBonds` | boolean |
| `bondMode` | `"auto"`, `"pairwise"`, or `"manual"` |
| `bondCutoffScale` | automatic cutoff multiplier |
| `pairwiseBondRanges` | `{"A-B": {enabled,min,max}}`, keyed by labels |
| `manualBondPairs` | atom-index pairs |
| `showPeriodicBonds` | include MIC bonds crossing the displayed boundary |
| `bondStyle` | `"cylinder"` or `"flat"` |
| `bondThickness` | bond diameter in Angstrom |
| `bondColorMode` | `"split"` or `"custom"` |
| `bondCustomColor` | `"#rrggbb"` |

Pairwise `max: 0` with `enabled: false` disables that label pair. Bonds are
recomputed per trajectory frame and during interactive transforms. Displayed
supercells repeat both atoms and internal bonds.

### Cell, View, And Lighting

| Setting | Values |
| --- | --- |
| `supercell` | non-materialized display repetition `[nx,ny,nz]` |
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

### Transform And Commensurate Guide

| Setting | Values |
| --- | --- |
| `rotatePivot` | `"selection"`, `"origin"`, or `"cell"` |
| `commensurateGuide` | show periodic 2D cell-match candidates |
| `commensurateSnap` | magnetically snap to a candidate |
| `commensurateStrainTolerance` | fractional boundary strain, for example `0.01` |
| `commensurateMaxIndex` | integer search bound |
| `commensurateSnapRangeDeg` | snap window in degrees |

For graphene, hBN, and other periodic 2D cells, select the layer in Edit and use
`rotate-selection` for a committed numeric transform. The interactive GUI's
`R` plus locked axis additionally displays cell-match rays and candidate angles.

### Trajectory Displacement Analysis

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

`displacementReferenceMode` is `"previous"` or `"frame"`. The reference frame
is zero-based. Style is `"3d"` or `"2d"`.

## Render A Final Image

`render()` never needs a screenshot crop. It uses the exact image export camera,
aspect ratio, lighting, crop, and overlays.

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

Formats:

- `"webp"`: default lossless compact image; same decoded RGBA pixels and
  dimensions as the source render;
- `"png"`: optimized lossless PNG for maximum compatibility.

The result contains `dataUrl`, `mimeType`, dimensions, camera, and options.
Decode the data URL directly. Do not re-screenshot the page.

For physical scale, use `scaleMode: "physical"` and
`pixelsPerAngstrom`. Otherwise use `"viewport"` to preserve the live camera
framing.

## Export Data And Scenes

`export()` returns a filename, MIME type, byte count, and data URL without
opening a save picker:

```javascript
const result = await ai.export({format: "poscar"});
```

Supported formats:

| Format | Output |
| --- | --- |
| `image` | Lossless WebP or PNG; accepts `render()` fields and `imageFormat` |
| `video` | MOV/H.264 or AVI/MPEG-4 trajectory |
| `poscar` | Current structure |
| `pickle` | ASE Atoms, labels, constraints, arrays, valid SinglePointCalculator |
| `blender` | Optimized Blender Python scene |
| `3dm` | Rhino scene; requires `v_ase-gui[rhino]` |
| `obj` | OBJ/MTL/camera metadata ZIP |
| `project` | Self-contained `.vase` structure/trajectory and visual state |
| `settings` | Reusable visual settings without coordinates |

Video example:

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

Image export example:

```javascript
const still = await ai.export({
  format: "image",
  imageFormat: "png",
  width: 3840,
  height: 2160,
  options: {
    renderMode: "studio-shadow",
    includeGrid: false,
    includeAxes: false
  }
});
```

With `N` source frames and interpolation multiplier `m`, output has
`(N - 1) * m + 1` frames. Interpolation requires stable atom count, ordering,
elements, and labels. MIC interpolation uses each frame's cell and PBC.

For large binary exports, prefer the regular GUI save picker or direct backend
HTTP request instead of carrying a Base64 data URL through the agent runtime.

## Human GUI Features

The same session also provides:

- multi-tab independent documents;
- operating-system file picker with replace, append-to-trajectory, and new-tab
  modes;
- box selection, ordered measurements, hover metadata, and replica selection;
- Blender-style `G`/`R`, axis locks, numeric input, increments, copy/paste,
  delete, and history;
- FixedLine, FixedPlane, FixAtoms, FixScaled, and Hookean visualization;
- trajectory playback, FPS/skip, relaxation trajectory, and displacement
  vectors;
- visual settings and `.vase` project save/load;
- image Preview Area and system save destination selection.

Use the GUI for freehand pointer transforms or browser-native file pickers. Use
the semantic bridge for deterministic agent work.

## Failure Handling

- If an edit says it requires Edit mode, call `apply({mode: "edit"})`.
- If a constraint changes the requested coordinates, trust the returned backend
  positions.
- If a frame has different topology, call `describe()` again before reusing
  indices.
- If an optional 3DM export fails, install `python -m pip install
  "v_ase-gui[rhino]"`.
- If browser video capture is unavailable, use a Chromium-family browser with
  `MediaRecorder`.
- Never infer an atom's ASE element from color alone; use `chemicalSymbols`.
- Never infer a periodic replica from screen location; use `cellOffset`.

## Human Takeover

Open `human_url` at any time. The user sees the same document, current frame,
camera, selection, edits, and visual settings. Switching between View and Edit
does not create a second session.
