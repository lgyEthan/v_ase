# Workflows And Examples

## Contents

1. Analyze, Style, And Render
   - Per-Atom Property Colorscale And Stored Forces
   - Publication Image
2. Edit Structures
   - Natural-Language Defect Edit
   - Random Multi-Species Insertion And Repulsion
   - Phosphorene Cumulative Tail Rotation
   - Rotate Around A Specific Atom
   - Constraint-Aware Edit
3. Measure And Animate
   - Ordered Measurement
   - Trajectory Analysis And Video
4. Analyze Scalar Fields
   - Volumetric Difference And Isosurface
   - RDF And CSV
5. Match Periodic Interfaces
   - Bounded Commensurate 2D Cells
   - XY Registry Map
   - Periodic Supercell Measurement
6. Collaborate And Share
   - Multi-Document Live Collaboration
   - Offline View-Only Handoff

These templates are starting points. Preserve the plan, validate, execute, and
verify sequence even when parameters change.

Every JavaScript snippet uses concise method notation. A vendor-neutral agent
must send the same method and parameter object through `v_ase api`; direct
`window.v_aseAI` access is only an optional browser-controller shortcut. The
revision-safe logic is:

```javascript
async function applyCurrent(command) {
  const state = await ai.describe({includePositions: false});
  return await ai.apply({
    expectedRevision: state.collaboration.revision,
    ...command
  });
}
```

## Analyze, Style, And Render

### Per-Atom Property Colorscale And Stored Forces

Use the live catalog rather than assuming how a DFT code or MLIP named its
per-atom output. This example colors only a selected region by a stored
uncertainty array and then restores the prior atom appearance:

```javascript
const capabilities = await ai.capabilities();
const catalog = await fetch(capabilities.atomColorScale.scalarCatalogUrl)
  .then(response => response.json());
const uncertainty = catalog.fields.find(field => (
  field.source === "array"
  && ["uncertainty", "mlip_uncertainty", "local_uncertainty"].includes(field.name)
  && field.reduction === "scalar"
));
if (!uncertainty) {
  throw new Error(`No scalar uncertainty field is available. Found: ${
    catalog.fields.map(field => field.label).join(", ")
  }`);
}

await applyCurrent({
  selection: {clear: true, indices: [0, 1, 2, 3]},
  operation: {
    name: "set-atom-colorscale",
    enabled: true,
    field: uncertainty.id,
    map: "viridis",
    scope: "selected",
    rangeMode: "trajectory",
    gamma: 1.0
  }
});
const colored = await ai.describe({includePositions: false});
if (!colored.display.atomColorScaleEnabled) {
  throw new Error("The per-atom colorscale was not enabled.");
}

await applyCurrent({
  operation: {name: "set-atom-colorscale", enabled: false}
});
```

For stored forces use `force:norm`. Coordinates are always available as
`position:x`, `position:y`, and `position:z`. Numeric vector or tensor arrays
offer a norm and compact component views. Arbitrary finite numeric columns in
LAMMPS dumps are cataloged by their exact names. Enabling may load one bounded
trajectory scalar cache and one sampled color lookup table; disabling must
restore the prior appearance without another scalar or colormap request.

Use `rangeMode:"current"` for the fast default: it fits the active frame once
and keeps the resulting range fixed as playback advances. Use
`rangeMode:"trajectory"` when colors must be quantitatively comparable across
every frame; v_ase loads a bounded scalar buffer once and reuses it, or scans
larger inputs in the backend. Verify that the full scan does not also request a
prefetched single frame. Use `rangeMode:"manual"` with explicit `minimum` and
`maximum` for cross-document comparisons. Set `gamma` between `0.1` and `5.0`
to change contrast without reloading scalar values or the Matplotlib lookup
table.

To show stored forces over the same locked colorscale, update display state
without evaluating a calculator:

```javascript
await applyCurrent({display: {
  showForceVectors: true,
  forceVectorStyle: "3d",
  forceVectorScale: 2.5,
  forceVectorThickness: 0.10,
  forceVectorColor: "#c43f5e"
}});
```

For each known nonzero force `F`, verify that the arrow direction is
`F / |F|` and its length is `forceVectorScale * |F|`. Keep the same resolved
colorscale minimum and maximum on every trajectory frame and export.

### Publication Image

Input: an ASE-readable structure and a request for a clean 4K top view.

```bash
v_ase gui structure.vasp --cli
```

```javascript
const before = await ai.describe({includePositions: false});
if (!before.atomCount) throw new Error("The structure is empty.");

await applyCurrent({
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
  await applyCurrent({camera: {projection: "orthographic", fit: "structure"}});
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

Output: save the lossless WebP with
`v_ase api "$COMMAND_URL" render ... --save figure.webp`; the same live view
remains visible at `human_url`.

## Edit Structures

### Natural-Language Defect Edit

Input: `examples/readme_scene_assets/ai_graphene_source.cif`.

Example user intent:

> Remove the carbon nearest the cell center, convert its three nearest
> neighbors to pyridinic nitrogen, add a Li_site atom 2.15 A above the vacancy,
> keep the existing bonds, use a clean oblique studio-shadow view, and render a
> 4K image.

This request explicitly authorizes deletion and element changes. Resolve the
indices from semantic state, never from pixel coordinates:

```javascript
await applyCurrent({mode: "edit", applyConstraints: true});
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

await applyCurrent({
  selection: {clear: true, indices: [vacancy]},
  operation: {name: "delete-selection", indices: [vacancy]}
});
const neighborsAfter = neighborsBefore.map(
  index => index - (index > vacancy ? 1 : 0)
);
await applyCurrent({
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
await applyCurrent({
  operation: {
    name: "add-atom",
    label: "Li_site",
    element: "Li",
    position: liPosition
  }
});
await applyCurrent({
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

### Random Multi-Species Insertion And Repulsion

Use this low-freedom workflow to scatter several atom populations and move
only those new atoms away from short contacts. It requires one periodic
structure, not a trajectory.

```javascript
const baseline = await ai.describe({includePositions: true});
if (baseline.frameCount !== 1) {
  throw new Error("Open the target frame as a standalone structure first.");
}
await applyCurrent({mode: "edit"});
await applyCurrent({operation: {
  name: "scatter-atoms",
  entries: [
    {element: "Li", label: "Li_mobile", count: 30},
    {element: "H", label: "H_probe", count: 10}
  ],
  regionMode: "cell",
  seed: 2021,
  freezeExisting: true,
  cutoffBasis: "covalent",
  cutoffScale: 0.7
}});

const scattered = await ai.describe({includePositions: true});
if (
  !scattered.addAtoms?.active
  || scattered.addAtoms.new_count !== 40
  || scattered.atomCount !== baseline.atomCount + 40
) {
  throw new Error("Random insertion did not produce the requested topology.");
}

await applyCurrent({operation: {
  name: "relax-added-atoms",
  pairCutoffs: scattered.addAtoms.pair_cutoffs,
  freezeExisting: true,
  strength: 2.0,
  boundaryStrength: 5.0,
  fmax: 0.05,
  steps: 300,
  mic: true
}});
```

Consume events or poll compact `describe` state until
`addAtoms.is_relaxing === false`. Do not issue another structural operation
while it is active. If the optimizer must be interrupted, use
`stop-added-atoms`, wait for the stopped state, inspect the latest positions,
and either continue or cancel.

```javascript
let placed;
for (;;) {
  placed = await ai.describe({includePositions: false});
  if (!placed.addAtoms?.is_relaxing) break;
  await new Promise(resolve => setTimeout(resolve, 500));
}
if (placed.addAtoms.status === "error") {
  await applyCurrent({operation: "cancel-add-atoms"});
  throw new Error("Repulsive placement failed; the exact baseline was restored.");
}
await applyCurrent({operation: "finish-add-atoms"});

const committed = await ai.describe({includePositions: true});
if (committed.addAtoms !== null || committed.atomCount !== baseline.atomCount + 40) {
  throw new Error("Add Atoms was not committed cleanly.");
}
for (let index = 0; index < baseline.atomCount; index += 1) {
  const error = Math.hypot(...committed.positions[index].map(
    (value, axis) => value - baseline.positions[index][axis]
  ));
  if (error > 1e-12) throw new Error(`Host atom ${index} moved by ${error} A.`);
}
```

For a Cartesian region, replace the region fields with
`regionMode:"box"` and six Angstrom bounds. Verify the returned region and
sampling diagnostics before optimization. Use `cancel-add-atoms` at any point
before finish to restore coordinates, constraints, arrays, labels, history,
and redo state exactly.

### Phosphorene Cumulative Tail Rotation

Input: `examples/readme_scene_assets/phosphorene_nanosheet.cif`.

For a human-assisted edit, open Edit mode and keep the first puckered ridge
fixed. Use a visible left-drag box to select the second ridge through the end
of the ribbon. In **Structure > Transform > Exact selection rotation**, set
the pivot to Selection COM, axis to X, angle to
`13.85 / 9 = 1.538889` degrees, and click **Rotate Selection**. Close the panel,
left-drag from the third ridge through the end, and repeat from the committed
coordinates. A ridge is one phosphorus sublayer in a half armchair cell, not
the two-ridge crystallographic cell. The final ridge must accumulate exactly
13.85 degrees, matching an H-APNR angle tabulated by Jang et al.
(DOI 10.1039/C6NR04354B). This is a deterministic editing workflow that
borrows the literature angle; do not describe it as the paper's periodic DFT
cell or as an energy-minimized structure. The canonical README capture uses a
short, wide 5 x 6 repeat, nine physical ridge edits, and a camera-only
above-to-below orbit after the final coordinate commit.

### Rotate Around A Specific Atom

For a human edit, select the moving atoms first, Shift-select the desired pivot
atom last, and choose **Active atom (last selected)** under
**Structure > Transform**. The pivot atom remains selected but does not move.

For semantic editing, preserve the intended order in `indices` and use
`pivot: "active"`:

```javascript
await applyCurrent({
  mode: "edit",
  operation: {
    name: "rotate-selection",
    indices: [1, 2, 3, 0],
    axis: [1, 0, 0],
    angleDeg: 30,
    pivot: "active"
  }
});
```

Here atom `0` is the pivot because it is the last explicit index.

For deterministic semantic editing:

```javascript
await applyCurrent({mode: "edit", applyConstraints: true});
const initial = await ai.describe({includePositions: true});
const x = initial.positions.map(position => position[0]);
const xPlanes = [...new Set(x.map(value => value.toFixed(6)))]
  .map(Number)
  .sort((a, b) => a - b);
if (xPlanes.length !== 20) {
  throw new Error(`Expected 20 phosphorene x planes, found ${xPlanes.length}.`);
}
const planeByX = new Map(xPlanes.map((value, index) => [value.toFixed(6), index]));
const ridgeIds = x.map(value =>
  Math.floor(planeByX.get(value.toFixed(6)) / 2)
);
const ridgeCount = 10;
const targetTwistDeg = 13.85;
const incrementDeg = targetTwistDeg / (ridgeCount - 1);

for (let ridgeStart = 1; ridgeStart < ridgeCount; ridgeStart += 1) {
  const tail = ridgeIds
    .map((ridgeId, index) => ridgeId >= ridgeStart ? index : -1)
    .filter(index => index >= 0);
  await applyCurrent({
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

### Constraint-Aware Edit

Input: move selected atoms while honoring FixedLine, FixedPlane, FixAtoms, or
FixScaled constraints.

```javascript
await applyCurrent({mode: "edit", applyConstraints: true});
const before = await ai.describe({includePositions: true});

await applyCurrent({
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

await applyCurrent({operation: "undo"});
const restored = await ai.describe({includePositions: true});
```

Do not compare only the requested vector. ASE may project it onto the allowed
line or plane; the returned coordinates are authoritative.

During human FixedPlane movement, verify that each constrained atom retains its
compact local plane marker and that `G` adds a larger translucent guide at the
atom's original position. A group COM plane is an implementation error.

## Measure And Animate

### Ordered Measurement

Input: `examples/readme_scene_assets/ethane_measurement.cif`.

```javascript
await applyCurrent({
  selection: {clear: true, indices: [3, 0, 1, 6]}
});
const measured = await ai.describe({includePositions: true});
if (measured.selection.length !== 4 || !measured.measurement) {
  throw new Error("Ordered H-C-C-H torsion was not produced.");
}
```

Never sort the ordered selection. Two atoms measure direct and MIC distance,
three use `a1-a2-a3`, and four use the signed `a1-a2-a3-a4` torsion.

### Trajectory Analysis And Video

Input: a trajectory with stable topology. For repository validation, use
`examples/readme_scene_assets/crowded_c60_relaxation.traj`; it contains 42
frames and is the canonical multi-frame fixture. Do not use a single-frame
README scene to validate frame stepping or movie export.

```javascript
const initial = await ai.describe({includePositions: false});
if (initial.frameCount < 2) throw new Error("A movie requires multiple frames.");

await applyCurrent({
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

## Analyze Scalar Fields

### Volumetric Difference And Isosurface

Input: one structure and three charge grids generated on the same FFT grid,
for example `combined/CHGCAR`, `fragment-a/CHGCAR`, and
`fragment-b/CHGCAR`.

Directly loaded VASP grids may use `.`, `_`, or `-` suffixes, so calculation
outputs such as `PARCHG_band_12` and `LOCPOT.vacuum` do not require a manual
format override.

```javascript
for (const path of [
  "combined/CHGCAR",
  "fragment-a/CHGCAR",
  "fragment-b/CHGCAR"
]) {
  await applyCurrent({
    operation: {name: "load-volumetric", path, precision: "fp64"}
  });
}

// Each load displays its newest grid at a valid default level. The exact
// signed difference surface is set explicitly below after combination.
const loaded = await ai.describe({includePositions: false});
const grids = loaded.analysis.volumetricDatasets.slice(-3);
if (grids.length !== 3 || grids.some(grid => !grid.id)) {
  throw new Error("The three charge grids were not loaded.");
}

await applyCurrent({
  operation: {
    name: "combine-volumetric",
    datasetIds: grids.map(grid => grid.id),
    coefficients: [1, -1, -1],
    name: "charge-density difference",
    precision: "fp64"
  }
});

const combined = await ai.describe({includePositions: false});
const difference = combined.analysis.volumetricDatasets.at(-1);
if (!difference || difference.name !== "charge-density difference") {
  throw new Error("The charge-density difference was not created.");
}

await applyCurrent({
  display: {
    supercell: [2, 2, 1],
    translationMode: "fractional",
    translation: [0.25, 0, 0]
  },
  operation: {
    name: "show-volumetric",
    datasetId: difference.id,
    level: 0.003,
    surfaceMode: "signed",
    stepSize: 1,
    smearingSigma: 0.4,
    smoothingIterations: 6,
    opacity: 0.68,
    positiveColor: "#2a9d8f",
    negativeColor: "#d1495b"
  }
});
```

Validation:

1. `describe().analysis.volumetricDatasets` identifies all four grids.
2. Every source and the difference report `precision: "float64"` and the
   expected `memory_bytes`.
3. `describe().analysis.volumetricSurface` reports the rendered levels,
   surface and triangle counts, post-smearing range, and refinement settings.
   Signed mode has both mesh groups when `+abs(level)` and `-abs(level)` both
   cross that reported range; otherwise it explicitly reports a partial
   signed surface.
4. The source dataset descriptor is identical before and after changing
   `smearingSigma`. The package regression suite, rather than the semantic
   summary API, verifies that the underlying FP32/FP64 array remains bitwise
   unchanged.
5. Mesh smoothing fixes vertices on the cell boundary and does not open a
   periodic seam.
6. Changing opacity restyles the current mesh immediately without changing
   the mesh count.
7. The mesh repeats exactly with the displayed `2 x 2 x 1` supercell.
8. Both mesh and atoms use the same fractional visual translation.
9. Repeating the source grids physically is done only after explicit
   `set-supercell`; undo restores atom count, cell, and grid dimensions.

Add and edit two planar sections without transferring the 3D grid:

```javascript
await applyCurrent({
  operation: {
    name: "add-volumetric-plane",
    datasetId: difference.id,
    planeName: "basal section",
    hkl: [0, 0, 1],
    offsetAngstrom: 3.0,
    resolution: 512,
    colormap: "coolwarm",
    autoRange: true,
    opacity: 0.9
  }
});
await applyCurrent({
  operation: {
    name: "add-volumetric-plane",
    datasetId: difference.id,
    planeName: "cross section",
    hkl: [1, 1, 0],
    resolution: 256,
    colormap: "viridis",
    autoRange: true
  }
});

const planeState = await ai.describe({includePositions: false});
const planeIds = planeState.analysis.volumetricPlanes.map(plane => plane.id);
await applyCurrent({
  operation: {
    name: "update-volumetric-planes",
    planeIds,
    autoRange: false,
    vmin: -0.02,
    vmax: 0.02,
    opacity: 0.84
  }
});
```

Verify the raw and absolute histograms each contain 256 bins and sum to the
dataset voxel count. Verify both plane IDs, exact hkl/offset/range fields, and
the displayed supercell repetitions in `analysis.volumetricPlanes`. Render
once with `[1,1,1]` and again with `[2,2,1]`; each plane must remain clipped to
the corresponding skew cell while the 3D source-grid memory is unchanged.
For GUI manipulation, first remain in View mode and open **Analysis >
Volumetric Data > Planes**. Create a plane, enter hkl and signed distance, and
confirm the ASE atom coordinates are unchanged. Then enter Edit mode, select
one plane, press `G`, move it along the visible normal, and confirm the number
field and slider follow the live offset before the settled full-resolution
render replaces the preview. Press `R`, constrain if needed, and confirm the
three hkl fields follow the live normal and the committed descriptor matches.

Do not combine grids with different dimensions, cell, origin, PBC, or units.
Do not hide that validation error by interpolating one grid onto another.

### RDF And CSV

Input: a fully periodic 3D structure or trajectory frame.

```javascript
const before = await ai.describe({includePositions: false});
if (before.pbc.some(value => !value)) {
  throw new Error("Bulk RDF requires full 3D periodicity.");
}

await applyCurrent({
  operation: {
    name: "calculate-rdf",
    cutoff: 8.0,
    bins: 400,
    pairMode: "active",
    activePairs: [["Cu_surface", "O_ads"]]
  }
});

const analyzed = await ai.describe({includePositions: false});
const rdf = analyzed.analysis.rdf;
if (!rdf || rdf.bins !== 400 || !rdf.partialCurves.includes("Cu_surface|O_ads")) {
  throw new Error("The requested partial RDF was not calculated.");
}
if (Math.abs(rdf.cutoff - 8.0) > 1e-12 || rdf.periodicImageSpan.length !== 3) {
  throw new Error("RDF did not retain the requested cutoff and image span.");
}
```

For an amorphous bulk model, also inspect the total curve beyond its
short-range peaks. It should fluctuate around the plotted `g(r) = 1` reference;
a systematic decline indicates an invalid finite-cell normalization.

Export the exact numeric result:

```bash
v_ase api "$COMMAND_URL" export --save rdf.csv --params '{
  "format":"rdf-csv",
  "cutoff":8.0,
  "bins":400,
  "pairMode":"active",
  "activePairs":[["Cu_surface","O_ads"]]
}'
```

Validation:

1. the total curve is always present;
2. requested partial labels are present;
3. the requested cutoff is retained and all required periodic-image extents
   are reported, even when a fixed `2 x 2 x 2` repetition is insufficient;
4. CSV radius count equals `bins`;
5. a homogeneous periodic test system approaches `g(r) = 1` away from the
   first few bins across several cutoffs, including beyond the unique-MIC
   reference.

## Match Periodic Interfaces

### Bounded Commensurate 2D Cells

Use this workflow only for cells with two periodic in-plane vectors. The
commensurate rotation axis is global Z and the lattice search is restricted to
the XY plane. Enabling the workspace calculates a bounded family of integer
host/guest supercells immediately. It previews the smallest valid match under
the strain cutoff and the default `maxAreaRatio` of 16; it never silently
materializes the proposal. The interactive area bound is `1..128`; do not
silently clamp or sample a larger request.

#### Same-lattice twist

Select the layer that rotates and calculate the complete angle/area/strain
family. Cells-only preview is the default:

```javascript
const analyzed = await applyCurrent({
  selection: {clear: true, indices: [36, 37, 38, 39]},
  operation: {
    name: "calculate-commensurate",
    mode: "same-lattice",
    indices: [36, 37, 38, 39],
    axis: "Z",
    angleDeg: 21.2,
    strainTolerance: 0.01,
    maxAreaRatio: 16,
    maxIndex: 32,
    showAtoms: false,
    snap: false
  }
});
```

Validate `analyzed.analysis.commensurate`: it must contain the candidate table,
positive-determinant host/guest integer matrices, area ratios, max principal
strain, mean absolute strain, actual atom counts, the current-angle marker, and
the smallest valid proposal. **3D overview** uses angle, area ratio, and max
principal strain. **Paper strain projection** uses mean absolute strain on x,
actual host-plus-guest atom count on y, and angle as marker color. Both views
must use the same accepted candidate set. The moving angle plane and current
marker must follow rotation without repeating the bounded search.

`rotate-to-commensurate` is the stricter Edit-mode shortcut for rotating the
selected layer to the nearest validated angle:

```javascript
await applyCurrent({
  mode: "edit",
  selection: {clear: true, indices: [36, 37, 38, 39]},
  operation: {
    name: "rotate-to-commensurate",
    axis: "Z",
    angleDeg: 21.2,
    pivot: "com",
    strainTolerance: 0.01,
    maxAreaRatio: 16,
    maxAngleDifferenceDeg: 2,
    showAtoms: false,
    applyConstraints: true
  }
});
```

#### Different host and guest lattices

Load the guest from inside the directory where the GUI was launched. The
operation preserves the current host and calculates a separate guest lattice;
the guest angle and offset then move the guest structure as one layer:

```javascript
await applyCurrent({
  operation: {
    name: "load-commensurate-guest",
    path: "layers/hbn.cif",
    format: "cif",
    calculate: true,
    strainTarget: "guest",
    strainTolerance: 0.01,
    maxAreaRatio: 16,
    maxIndex: 32,
    angleDeg: 0,
    showAtoms: false
  }
});
```

Use `strainTarget: "guest"` unless the user explicitly asks to deform the host.
Verify the distinct host, guest, and proposed common-cell outlines and both
integer matrices. With `showAtoms: true`, require opaque core atoms, a
one-primitive-cell boundary shell, and all preview bonds across the proposed
supercell. Remove a guest with `remove-commensurate-guest`.

For a deterministic different-lattice check, launch
`examples/commensurate_host_guest/graphene_host.extxyz` and load
`examples/commensurate_host_guest/cu111_guest.extxyz`. With guest strain `1%`
and `maxAreaRatio:16`, require the smallest graphene `√13` / Cu(111)
`√12` match at `|16.10211375|` degrees, max principal strain
`0.001665824397`, mean absolute strain `0.001110549598`, and 38 total atoms.

The preview is scientific state, not an ASE topology change. A trajectory or a
document containing volumetric grids remains preview-only. For one editable
structure, materialize only after explicit approval:

```javascript
await applyCurrent({operation: {name: "apply-commensurate-cell"}});
```

Re-describe and verify atom count, cell determinant, PBC, remapped constraints,
labels, and cleared proposal state. Never bypass an unsupported materialization
with `make-supercell`; report `materializationReason`. Use
`dismiss-commensurate-cell` when no topology change is wanted.

Export the graph table only after calculation:

```bash
v_ase api "$COMMAND_URL" export --save commensurate.csv --params '{
  "format":"commensurate-csv",
  "mode":"host-guest",
  "strainTarget":"guest",
  "strainTolerance":0.01,
  "maxAreaRatio":16,
  "maxIndex":32
}'
```

The CSV must include angle, matrices, area, max principal strain, mean absolute
strain, host/guest/total atom counts, and the CellMatch and Stradi et al.
references carried by the bounded-search implementation.

### XY Registry Map

Run this after selecting the layer to translate. It scans one fractional XY
period while leaving source coordinates unchanged. No selection must produce a
clear error rather than an empty graph:

```javascript
await applyCurrent({
  selection: {clear: true, indices: [36, 37, 38, 39]},
  operation: {
    name: "calculate-registry-map",
    indices: [36, 37, 38, 39],
    metric: "short-contact",
    gridX: 48,
    gridY: 48
  }
});
```

`short-contact` is a covalent-radii-scaled overlap score. `bond-strain` is the
RMS normalized deviation of enabled interfacial label-pair distances from
their references and can receive explicit `pairCutoffs`. Both are geometry
scores, not energies; lower values indicate less geometric penalty and must not
be described as a relaxed stacking energy.

While the map is active, `G` is constrained to XY. The live marker must track
the selected layer's current fractional translation, including periodic wrap,
and the map must show the unit-cell boundary. Export the complete grid through
the graph's save icon or the exact semantic export:

```bash
v_ase api "$COMMAND_URL" export --save registry.csv --params '{
  "format":"registry-csv",
  "indices":[36,37,38,39],
  "metric":"short-contact",
  "gridX":48,
  "gridY":48
}'
```

CSV rows must retain fractional X/Y, Cartesian translation, metric, selected
indices, and metric definition. No paper citation is required for the generic
geometry score. RDF, commensurate, and registry Plotly drawers all expose the
same icon-only CSV control beside the graph title.

### Periodic Supercell Measurement

Use View mode when the user only needs displayed replicas:

```javascript
await applyCurrent({
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

## Collaborate And Share

### Multi-Document Live Collaboration

```javascript
const workspace = await ai.documents();
const active = workspace.documents.find(document => document.active);
await ai.newDocument();
const updated = await ai.documents();
```

Every document is independent. Before modifying a document:

1. call `documents()`;
2. activate its `sessionId`;
3. call `describe()` again;
4. apply with that document's current `collaboration.revision` as
   `expectedRevision`;
5. consume later CLI NDJSON events and re-describe after a human edit;
6. apply and verify changes;
7. save a distinct `.vase` project.

Give the handshake's `human_url` to the user immediately. The user and agent
operate the same state, not copies. A workspace event identifies the edited tab
with `session_id` and its `document_revision`; activate it before reviewing the
new semantic state.

### Offline View-Only Handoff

Use this only after the scene, trajectory, camera, and overlays are verified:

```javascript
const before = await ai.describe({includePositions: false});
if (!before.atomCount) throw new Error("The document is empty.");

const shared = await ai.export({format: "html", embedProject: false});
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
6. `hasEmbeddedProject` is false and no `.vase` download control is present.

HTML is a shareable view, not the editable source of truth. Keep or deliver
the `.vase` project whenever subsequent v_ase editing is expected. If one
self-contained HTML handoff must also preserve editable recovery, export a
second document with `embedProject: true`, then require
`hasEmbeddedProject === true`, a nonzero `.vase` download, and successful
reopening through `v_ase gui FILE.html`.
