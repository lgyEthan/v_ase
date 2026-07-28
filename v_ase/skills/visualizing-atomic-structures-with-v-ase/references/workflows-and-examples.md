# Workflows And Examples

## Contents

1. Publication Image
2. Constraint-Aware Edit
3. Trajectory Analysis And Video
4. Periodic Supercell Measurement
5. Multi-Document Human Handoff

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
  display: {supercell: [2, 2, 1]},
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
