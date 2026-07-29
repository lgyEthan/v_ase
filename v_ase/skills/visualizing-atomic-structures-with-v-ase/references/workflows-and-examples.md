# Workflows And Examples

## Contents

1. Publication Image
2. Natural-Language Defect Edit
3. Phosphorene Slice Rotation
4. Constraint-Aware Edit
5. Ordered Measurement
6. Trajectory Analysis And Video
7. Periodic Supercell Measurement
8. Multi-Document Human Handoff
9. Offline View-Only Handoff

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

## Natural-Language Defect Edit

Input: `examples/readme_scene_assets/ai_graphene_source.cif`.

Example user intent:

> Remove the carbon nearest the cell center, convert its three nearest
> neighbors to pyridinic nitrogen, add a Li_site atom 2.15 A above the vacancy,
> preserve PBC and bonds, use a clean oblique studio-shadow view, and render a
> 4K image.

This request explicitly authorizes deletion and element changes. Resolve the
indices from semantic state, never from pixel coordinates:

```javascript
await ai.apply({mode: "edit", applyConstraints: true});
const before = await ai.describe({includePositions: true});
if (before.atomCount !== 72 || before.chemicalSymbols.some(symbol => symbol !== "C")) {
  throw new Error("Expected the generated 72-atom graphene source.");
}

const center = [0, 1, 2].map(axis =>
  0.5 * (before.cell[0][axis] + before.cell[1][axis])
);
center[2] = before.positions.reduce((sum, position) => sum + position[2], 0)
  / before.atomCount;
const distance = (left, right) => Math.hypot(
  left[0] - right[0],
  left[1] - right[1],
  left[2] - right[2]
);
const vacancy = before.positions
  .map((position, index) => ({index, distance: distance(position, center)}))
  .sort((left, right) => left.distance - right.distance)[0].index;
const neighborsBefore = before.positions
  .map((position, index) => ({
    index,
    distance: index === vacancy
      ? Number.POSITIVE_INFINITY
      : distance(position, before.positions[vacancy])
  }))
  .sort((left, right) => left.distance - right.distance)
  .slice(0, 3)
  .map(entry => entry.index);
const vacancyPosition = [...before.positions[vacancy]];

await ai.apply({
  selection: {clear: true, indices: [vacancy]},
  operation: {name: "delete-selection", indices: [vacancy]}
});
const neighborsAfter = neighborsBefore.map(
  index => index - (index > vacancy ? 1 : 0)
);
await ai.apply({
  selection: {clear: true, indices: neighborsAfter},
  operation: {
    name: "set-identity",
    indices: neighborsAfter,
    label: "N_pyridinic",
    element: "N"
  }
});
const liPosition = [
  vacancyPosition[0],
  vacancyPosition[1],
  vacancyPosition[2] + 2.15
];
await ai.apply({
  operation: {
    name: "add-atom",
    label: "Li_site",
    element: "Li",
    position: liPosition
  }
});
await ai.apply({
  display: {
    showBonds: true,
    showGrid: false,
    showAxes: false,
    viewportBackground: "white",
    lightingMode: "studio-shadow",
    labelColors: {
      C: "#686d73",
      N_pyridinic: "#3157d5",
      Li_site: "#8f4fd6"
    },
    labelMaterials: {
      C: "standard",
      N_pyridinic: "metal",
      Li_site: "metal"
    }
  },
  quality: {antiAliasing: true, sphereQuality: "ultra"},
  camera: {
    projection: "orthographic",
    position: [center[0] + 9, center[1] - 12, center[2] + 23],
    target: center,
    up: [0, 0, 1],
    fit: "structure"
  }
});

const final = await ai.describe({includePositions: true});
if (
  final.atomCount !== 72
  || final.chemicalSymbols.filter(symbol => symbol === "N").length !== 3
  || final.labels.filter(label => label === "N_pyridinic").length !== 3
  || final.chemicalSymbols.filter(symbol => symbol === "Li").length !== 1
  || final.labels.filter(label => label === "Li_site").length !== 1
) {
  throw new Error("The pyridinic N3/Li-site edit failed semantic verification.");
}
const liIndex = final.labels.indexOf("Li_site");
if (Math.abs(final.positions[liIndex][2] - liPosition[2]) > 1e-8) {
  throw new Error("Li adsorption height failed semantic verification.");
}
```

Render with the Publication Image request above and verify exact dimensions,
nonblank decoded pixels, three blue nitrogen atoms around one vacancy, and the
purple Li site above the plane. Save to a new filename. The README source,
intermediate, and expected final structures are generated from
`ase.build.graphene`; no external coordinates or private data are used:

- `examples/readme_scene_assets/ai_graphene_source.cif`;
- `examples/readme_scene_assets/ai_pyridinic_n3_graphene.cif`;
- `examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.cif`;
- `examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.traj`.

## Phosphorene Cumulative Tail Rotation

Input: `examples/readme_scene_assets/phosphorene_nanosheet.cif`.

For a human-assisted edit, open Edit mode and keep the first puckered ridge
fixed. Use a visible left-drag box to select the second ridge through the end
of the ribbon. In **Structure > Transform > Exact selection rotation**, set
the pivot to Selection COM, axis to X, angle to
`36 / 15 = 2.4` degrees, and click **Rotate Selection**. Close the panel,
left-drag from the third ridge through the end, and repeat from the committed
coordinates. A ridge is one phosphorus sublayer in a half armchair cell, not
the two-ridge crystallographic cell. The final ridge must accumulate exactly
36 degrees, matching the largest H-APNR angle tabulated by Jang et al.
(DOI 10.1039/C6NR04354B). This is a deterministic editing workflow that
borrows the literature angle; do not describe it as the paper's periodic DFT
cell or as an energy-minimized structure.

For deterministic semantic editing:

```javascript
await ai.apply({mode: "edit", applyConstraints: true});
const initial = await ai.describe({includePositions: true});
const x = initial.positions.map(position => position[0]);
const xPlanes = [...new Set(x.map(value => value.toFixed(6)))]
  .map(Number)
  .sort((a, b) => a - b);
if (xPlanes.length !== 32) {
  throw new Error(`Expected 32 phosphorene x planes, found ${xPlanes.length}.`);
}
const planeByX = new Map(xPlanes.map((value, index) => [value.toFixed(6), index]));
const ridgeIds = x.map(value =>
  Math.floor(planeByX.get(value.toFixed(6)) / 2)
);
const ridgeCount = 16;
const targetTwistDeg = 36;
const incrementDeg = targetTwistDeg / (ridgeCount - 1);

for (let ridgeStart = 1; ridgeStart < ridgeCount; ridgeStart += 1) {
  const tail = ridgeIds
    .map((ridgeId, index) => ridgeId >= ridgeStart ? index : -1)
    .filter(index => index >= 0);
  await ai.apply({
    selection: {clear: true, indices: tail},
    operation: {
      name: "rotate-selection",
      axis: [1, 0, 0],
      angleDeg: incrementDeg,
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
const fixedReference = ridgeIds
  .map((ridgeId, index) => ridgeId === 0 ? index : -1)
  .filter(index => index >= 0);
if (fixedReference.some(index =>
  final.positions[index].some((value, axis) =>
    Math.abs(value - initial.positions[index][axis]) > 1e-8
  )
)) {
  throw new Error("The fixed reference ridge moved during cumulative twist.");
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
the workflow above is the authority: every step starts from the previous
confirmed structure. Published media colors the upper and lower phosphorus
sublayers green and purple while preserving `P` as the ASE element.

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

## Offline View-Only Handoff

Use this only after the scene, trajectory, camera, and overlays are verified:

```javascript
const before = await ai.describe({includePositions: false});
if (!before.atomCount) throw new Error("The document is empty.");

const shared = await ai.export({format: "html"});
if (shared.mimeType !== "text/html" || shared.bytes <= 0) {
  throw new Error("HTML export did not produce a document.");
}
```

Decode `shared.dataUrl` to the requested destination. Reopen the result with
network access disabled and verify:

1. `window.v_aseStandalone.ready` resolves;
2. the canvas is nonblank and uses the saved camera;
3. orbit, pan, zoom, and trajectory controls work;
4. no structure, appearance, settings, or export editor is present;
5. no HTTP/HTTPS request occurs;
6. the embedded `.vase` download has a nonzero byte count.

HTML is a shareable view, not the editable source of truth. Keep or deliver
the `.vase` project whenever subsequent v_ase editing is expected.
