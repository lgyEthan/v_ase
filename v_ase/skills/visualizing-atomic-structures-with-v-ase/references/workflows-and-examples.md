# Workflows And Examples

## Contents

1. Publication Image
2. Phosphorene Slice Rotation
3. Constraint-Aware Edit
4. Ordered Measurement
5. Trajectory Analysis And Video
6. Periodic Supercell Measurement
7. Multi-Document Human Handoff

These templates are starting points. Preserve the plan, validate, execute, and
verify sequence even when parameters change.

## Publication Image

Input: an ASE-readable structure and a request for a clean 4K top view.

```bash
v_ase gui structure.vasp --for-ai
```

```javascript
const ai = window.v_aseAI;
await ai.ready();
const before = await ai.describe({includePositions: false});
if (!before.atomCount) throw new Error("The structure is empty.");

await ai.apply({
  display: {
    viewportBackground: "white",
    showBonds: true,
    showCell: true,
    showGrid: false,
    showAxes: false,
    atomDisplayMode: "3d",
    lightingMode: "studio-shadow",
    sunIntensity: 2.4
  },
  quality: {antiAliasing: true, sphereQuality: "ultra"},
  camera: {axis: "+Z", fit: "structure"}
});

const configured = await ai.describe({includePositions: false});
if (configured.camera.projection !== "orthographic") {
  await ai.apply({camera: {projection: "orthographic", fit: "structure"}});
}

const image = await ai.render({
  format: "webp",
  width: 3840,
  height: 2160,
  options: {
    includeGrid: false,
    includeAxes: false,
    includeCell: true,
    transparentBackground: false,
    backgroundColor: "#ffffff",
    scaleMode: "viewport",
    sphereQuality: "ultra",
    renderMode: "studio-shadow"
  }
});

if (image.width !== 3840 || image.height !== 2160 || image.bytes <= 0) {
  throw new Error("The 4K render failed validation.");
}
```

Output: a lossless WebP data URL and the same live view at `human_url`.

## Phosphorene Cumulative Tail Rotation

Input: `examples/readme_scene_assets/phosphorene_nanosheet.cif`.

For a human-assisted edit, open Edit mode and select the first
crystallographic slice through the end of the ribbon. Set the pivot to
Selection COM, then use `R`, `X`, and an exact 15-degree value. Confirm the
edit, advance the selection boundary by one slice, and repeat from the edited
coordinates. Do not compute every operation from the original flat sheet.

For deterministic semantic editing:

```javascript
await ai.apply({mode: "edit", applyConstraints: true});
const initial = await ai.describe({includePositions: true});
const x = initial.positions.map(position => position[0]);
const xMin = Math.min(...x);
const xMax = Math.max(...x);
const sliceCount = 11;
const sliceWidth = (xMax - xMin + 1e-8) / sliceCount;
const sliceIds = x.map(value =>
  Math.min(sliceCount - 1, Math.floor((value - xMin) / sliceWidth))
);

for (let sliceStart = 0; sliceStart < sliceCount - 1; sliceStart += 1) {
  const tail = sliceIds
    .map((sliceId, index) => sliceId >= sliceStart ? index : -1)
    .filter(index => index >= 0);
  await ai.apply({
    selection: {clear: true, indices: tail},
    operation: {
      name: "rotate-selection",
      axis: [1, 0, 0],
      angleDeg: 15,
      pivot: "selection",
      applyConstraints: true
    }
  });
}

const final = await ai.describe({includePositions: true});
if (final.atomCount !== initial.atomCount) {
  throw new Error("Cumulative phosphorene rotation changed atom count.");
}
if (final.positions.every((position, index) =>
  position.every((value, axis) =>
    Math.abs(value - initial.positions[index][axis]) < 1e-8
  )
)) {
  throw new Error("Cumulative phosphorene rotation did not change coordinates.");
}
```

For every operation verify:

```javascript
const state = await ai.describe({includePositions: false});
if (state.mode !== "edit" || state.selection.length === 0) {
  throw new Error("The active tail selection or Edit mode was lost.");
}
```

The browser media must also show:

```text
selection outline -> pivot axis -> fixed start line -> moving current line
```

The generated trajectory records the editing sequence for documentation, but
the workflow above is the authority: each step starts from the previous
confirmed structure.

## Constraint-Aware Edit

Input: move selected atoms while honoring FixedLine, FixedPlane, FixAtoms, or
FixScaled constraints.

```javascript
await ai.apply({mode: "edit", applyConstraints: true});
const before = await ai.describe({includePositions: true});

await ai.apply({
  selection: {clear: true, indices: [3]},
  operation: {
    name: "move-selection",
    vector: [0.2, 0.0, 0.3],
    applyConstraints: true
  }
});

const after = await ai.describe({includePositions: true});
if (after.atomCount !== before.atomCount) {
  throw new Error("Unexpected topology change.");
}
if (!after.constraints) {
  throw new Error("Constraint state was not returned.");
}

await ai.apply({operation: "undo"});
const restored = await ai.describe({includePositions: true});
```

Do not compare only the requested vector. ASE may project it onto the allowed
line or plane; the returned coordinates are authoritative.

During human FixedPlane movement, verify that each constrained atom retains its
compact local plane marker and that `G` adds a larger translucent guide at the
atom's original position. A group COM plane is an implementation error.

## Ordered Measurement

Input: `examples/readme_scene_assets/ethane_measurement.cif`.

```javascript
await ai.apply({
  selection: {clear: true, indices: [3, 0, 1, 6]}
});
const measured = await ai.describe({includePositions: true});
if (measured.selection.length !== 4 || !measured.measurement) {
  throw new Error("Ordered H-C-C-H torsion was not produced.");
}
```

Never sort the ordered selection. Two atoms measure direct and MIC distance,
three use `a1-a2-a3`, and four use the signed `a1-a2-a3-a4` torsion.

## Trajectory Analysis And Video

Input: a trajectory with stable topology.

```javascript
const initial = await ai.describe({includePositions: false});
if (initial.frameCount < 2) throw new Error("A movie requires multiple frames.");

await ai.apply({
  frame: initial.frameCount - 1,
  selection: {clear: true, indices: [0, 1]},
  operation: {
    name: "refresh-displacements",
    display: {
      showDisplacements: true,
      displacementReferenceMode: "frame",
      displacementReferenceFrame: 0,
      displacementMic: true,
      displacementStyle: "3d",
      displacementScale: 1.0,
      displacementThickness: 0.08
    }
  }
});

const analyzed = await ai.describe({includePositions: false});
if (analyzed.frame !== initial.frameCount - 1) {
  throw new Error("Trajectory frame verification failed.");
}

const movie = await ai.export({
  format: "video",
  container: "mov",
  width: 1920,
  height: 1080,
  fps: 30,
  interpolationMultiplier: 2,
  interpolationMic: true,
  options: {
    backgroundColor: "#ffffff",
    includeGrid: false,
    includeAxes: false,
    includeCell: true,
    renderMode: "studio-shadow"
  }
});

if (movie.mimeType !== "video/quicktime" || movie.bytes <= 0) {
  throw new Error("MOV export failed validation.");
}
```

Interpolation can be expensive. Inform the user before choosing a multiplier
above one.

## Periodic Supercell Measurement

Use View mode when the user only needs displayed replicas:

```javascript
await ai.apply({
  mode: "view",
  display: {
    supercell: [2, 2, 1],
    translationMode: "fractional",
    translation: [0.25, 0, 0]
  },
  selection: {
    clear: true,
    references: [
      {index: 0, cellOffset: [0, 0, 0]},
      {index: 0, cellOffset: [1, 0, 0]}
    ]
  }
});
const measured = await ai.describe({includePositions: true});
```

The translation above is a scene offset applied after repetition. It is saved
in Visual Settings and `.vase`, but `measured.positions` and ASE exports remain
physical coordinates. Use `[0,0,0]` to remove it.

Use `set-supercell` only when the user explicitly wants new atoms and a
materialized larger cell. It changes topology in every frame and requires Edit
mode.

## Multi-Document Human Handoff

```javascript
const docs = await ai.documents();
const active = docs.find(document => document.active);
await ai.newDocument();
const updated = await ai.documents();
```

Every document is independent. Before modifying a document:

1. call `documents()`;
2. activate its `sessionId`;
3. call `describe()` again;
4. apply and verify changes;
5. save a distinct `.vase` project.

Give the handshake's `human_url` to the user for manual pointer edits. The user
and AI operate the same state, not copies.
