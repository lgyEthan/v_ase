# Workflows And Examples

## Contents

1. Analyze, Style, And Render
   - Per-Atom Property Colorscale And Stored Forces
   - Reproduce A Reference Figure Without Editing The Structure
   - Publication Image
2. Edit Structures
   - Natural-Language Defect Edit
   - Build An ASE Bulk Crystal
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
   - Rigid Translation
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

For an exact user-defined palette, replace the preset `map` with `"custom"`
and provide `customMap`. Use continuous mode for interpolated scalar fields or
discrete mode for explicit value classes:

```javascript
await applyCurrent({operation: {
  name: "set-atom-colorscale",
  enabled: true,
  field: uncertainty.id,
  map: "custom",
  customMap: {
    mode: "discrete",
    stops: [
      {position: 0.0, color: "#20364A"},
      {position: 0.35, color: "#58A58C"},
      {position: 0.7, color: "#F0C75E"},
      {position: 1.0, color: "#C84B52"}
    ]
  },
  rangeMode: "manual",
  minimum: 0,
  maximum: 1
}});
```

Verify that `describe().display.atomColorScaleCustomMap` exactly preserves the
mode and stops before exporting.

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
For a full-structure request, use `scope:"all"` and require the mapped-color
count to equal the number of finite-valued visible atoms. Selected-only scope
is an explicit masking workflow, not a valid fallback for missing full colors.

### Reproduce A Reference Figure Without Editing The Structure

A paper image is a visual target, not a substitute for atomistic state. Read
the input structure with `describe({includePositions:true})`, inspect the
reference pixels, and write a compact composition specification before sending
any mutation. The specification must answer all of these questions:

1. Which ASE elements and exact zero-based atom indices form each visible
   scientific role or height/layer group?
2. How many periodic motifs are visible along each lattice direction? This is
   display replication, never a physical supercell edit.
3. Which periodic atom references define the motif center, view normal, and
   screen-vertical feature? Include `cellOffset` for boundary-spanning motifs.
4. Which visual label pairs are bonded, and which pairs are explicitly absent?
5. What final rendered radii, colors, materials, opacity, projection, crop, and
   background are visible? Do not reuse chemical-element defaults when the
   figure distinguishes substrate, active layer, adsorbate, or height groups.

Keep the document in View mode. Split scientific roles by exact index while
preserving `chemicalSymbols`:

```javascript
await applyCurrent({operation: {
  name: "set-visual-label",
  indices: SUBSTRATE_INDICES,
  label: "substrate"
}});
await applyCurrent({operation: {
  name: "set-visual-label",
  indices: ACTIVE_LAYER_INDICES,
  label: "active_layer"
}});
```

Use `style-atoms` for the final rendered radius in Angstrom. For a touching-sphere
request, calculate the relevant nearest-neighbor distance from semantic
coordinates with MIC and set `radiusAngstrom = 0.5 * d_nn`; do not confuse this
with `labelRadii`, which is affected by the global scale.

```javascript
await applyCurrent({operation: {
  name: "style-atoms",
  labels: ["substrate"],
  color: "#f4f4f1",
  material: "unlit",
  radiusAngstrom: SUBSTRATE_NEAREST_NEIGHBOR_DISTANCE / 2,
  opacity: 1
}});
await applyCurrent({operation: {
  name: "style-atoms",
  labels: ["active_layer"],
  color: "#b87333",
  material: "standard",
  radiusAngstrom: ACTIVE_LAYER_RADIUS
}});
```

Make the bond policy authoritative. `disableUnspecified:true` prevents a
chemically plausible but visually unwanted pair from reappearing after a label
split or frame change:

```javascript
await applyCurrent({operation: {
  name: "configure-bonds",
  disableUnspecified: true,
  clearEndpointOverrides: true,
  pairs: [{
    labels: ["active_layer", "adsorbate"],
    enabled: true,
    maximumAngstrom: ACTIVE_BOND_CUTOFF,
    style: "flat",
    thicknessAngstrom: 0.12,
    colorMode: "custom",
    color: "#202020",
    opacity: 1
  }]
}});
```

When the reference draws no bonds, do not invent a chemically reasonable
network. Send the explicit empty allow-list:

```javascript
await applyCurrent({operation: {
  name: "configure-bonds",
  disableUnspecified: true,
  pairs: []
}});
```

Compose periodic translation, replication, camera roll, target, and framing in
one `compose-view` transaction. The example below moves a boundary-spanning
motif to fractional cell center along `a` and `b`, views from `+c`, and makes a
specific atom-to-atom feature vertical. `viewFromCellAxis` is the
target-to-camera direction. `verticalReferences[0] -> verticalReferences[1]`
points upward on screen after projection into the image plane.

```javascript
await applyCurrent({operation: {
  name: "compose-view",
  displaySupercell: [3, 3, 1],
  centerMotif: {
    references: MOTIF_REFERENCES,
    targetFractional: [0.5, 0.5, 0.5],
    axes: ["a", "b"]
  },
  viewFromCellAxis: "+c",
  verticalReferences: [VERTICAL_START_REFERENCE, VERTICAL_END_REFERENCE],
  targetReferences: MOTIF_REFERENCES,
  projection: "orthographic",
  fit: "displayed",
  padding: 0.07
}});
```

When an accepted camera direction must survive a later crop correction, do not
send another lattice direction or vertical reference. Preserve it explicitly:

```javascript
await applyCurrent({operation: {
  name: "compose-view",
  preserveOrientation: true,
  targetReferences: CENTRAL_REFERENCES,
  fit: "references",
  fitReferences: OUTERMOST_VISIBLE_REFERENCES,
  padding: 0.04
}});
```

For a genuinely planar reference, include `atomDisplayMode:"2d"`. This is a
scene-level flat rendering mode, unlike assigning `material:"unlit"` to a 3D
sphere.

`displaySupercell` is centered about the base cell and `fit:"displayed"` uses
those actual negative and positive replica offsets. Do not emulate replication
with camera zoom. Do not use `set-supercell` unless the user explicitly asks to
change atom count and cell.

If the reference shows only a bounded subset of a larger existing periodic
cell, use `fit:"references"` with `fitReferences` (or base-cell
`fitIndices`). Choose the subset from the visible motif and atom count in the
reference, not from an arbitrary fractional crop. `targetReferences` may be a
small central anchor, but `fitReferences` must enumerate the outermost atoms or
replicas that define all four crop boundaries; fitting only the center causes
over-zoom and clipped edge atoms. This changes framing only;
atoms outside the frame remain present and the structure is untouched.

When one visual bond is missing, compare the actual periodic edge set before
changing a cutoff. Increasing an already enabled cutoff is a no-op when every
distance in that label pair is already below it. Identify whether the missing
edge is an omitted label pair or a periodic image, add only that edge class,
then verify the rendered bond count. Do not compensate by enabling every
same-element pair.
For a uniform pair color/material, also clear stale endpoint overrides so a
previous selected-atom style does not split or recolor the authoritative pair.
If the reference intentionally draws only a selected chain or motif, use
`indexPairs` for those exact atom edges instead of enabling the corresponding
label pair everywhere in the periodic structure. Send the index list alone
when existing pair cutoffs and appearance must be preserved; do not add an
empty pair allow-list or disable unrelated label policies.

Render a small proof first. Compare the reference and proof in this order:
panel aspect ratio, visible motif/atom count, periodic anchor/translation,
view normal, vertical feature,
substrate-versus-active layer classification, atom occlusion/radius, bond
allow-list, crop, then color/material. Change one semantic category at a time.
For split labels of one element, preserve an explicit role-pair allow-list;
never replace selected edges with all possible same-element role pairs.
After each iteration verify unchanged atom count, `chemicalSymbols`, positions,
cell, PBC, and constraints. A visually close result with altered topology is a
failed reproduction.

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

await applyCurrent({renderArea: {
  enabled: true,
  followViewport: false,
  fromCurrentView: true
}});
const framed = await ai.describe({includePositions: false});
if (!framed.renderArea.enabled || framed.renderArea.followViewport) {
  throw new Error("The independent Render Area was not locked.");
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

### Build An ASE Bulk Crystal

The matching human control is **+ Add atoms > Build with ASE**.

Use the installed ASE catalog instead of guessing which reference element,
prototype, or output cell is valid. This example starts from an empty Edit
document and builds cubic rocksalt CuO with explicit lattice data:

```javascript
const capabilities = await ai.capabilities();
const catalog = await fetch(capabilities.bulkBuilder.catalogUrl).then(response => response.json());
const rocksalt = catalog.structures.find(item => item.id === "rocksalt");
if (!rocksalt?.cell_modes.includes("cubic")) {
  throw new Error("The installed ASE build does not advertise cubic rocksalt.");
}

const request = {
  formula: "CuO",
  crystalstructure: "rocksalt",
  cell_mode: "cubic",
  a: 4.27
};
const preview = await fetch(capabilities.bulkBuilder.previewUrl, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(request)
}).then(response => response.json());
if (!preview.valid || preview.atom_count !== 8) {
  throw new Error(preview.message || "Unexpected ASE bulk preview.");
}

await applyCurrent({mode: "edit"});
const before = await ai.describe({includePositions: false});
if (before.atomCount > 0 || before.cell.some(row => row.some(value => value !== 0))) {
  throw new Error("Obtain human replacement approval before continuing.");
}
await applyCurrent({operation: {
  name: "build-bulk",
  formula: "CuO",
  crystalStructure: "rocksalt",
  cellMode: "cubic",
  a: 4.27
}});

const built = await ai.describe({includePositions: true});
if (
  built.atomCount !== 8
  || built.frameCount !== 1
  || !built.pbc.every(Boolean)
  || built.chemicalSymbols.filter(symbol => symbol === "Cu").length !== 4
  || built.chemicalSymbols.filter(symbol => symbol === "O").length !== 4
) {
  throw new Error("The ASE-built CuO document failed semantic verification.");
}
```

For a nonempty document, obtain explicit human approval and resend the same
operation with `confirmReplace:true`. The replacement is one Undo entry and
retains visual settings. Never infer lattice parameters that the catalog or
user did not provide.

### Batch Atom And Molecule Insertion

Use this low-freedom workflow to place atom or molecule populations and move
only that staged content away from short contacts. It requires one Edit-mode
document, not a trajectory. The document may be empty when a cell is defined
first or when the request supplies at least one finite Allow region.

```javascript
const baseline = await ai.describe({includePositions: true});
if (baseline.frameCount !== 1) {
  throw new Error("Open the target frame as a standalone structure first.");
}
await applyCurrent({mode: "edit"});
if (baseline.atomCount === 0 && !baseline.cell.some(row => row.some(value => value !== 0))) {
  await applyCurrent({operation: {
    name: "set-unit-cell",
    cell: [[12, 0, 0], [1.5, 11, 0], [0.5, 0.8, 10]],
    pbc: [true, true, true]
  }});
}
await applyCurrent({operation: {
  name: "scatter-atoms",
  entries: [
    {element: "Li", label: "Li_mobile", count: 30},
    {element: "H", label: "H_probe", count: 10}
  ],
  regionMode: "regions",
  regionMic: true,
  regions: [
    {id: "left-channel", name: "Left channel", role: "allow",
     bounds: [1.0, 4.5, 1.0, 8.0, 0.0, 14.0]},
    {id: "right-channel", name: "Right channel", role: "allow",
     bounds: [5.5, 9.0, 1.0, 8.0, 0.0, 14.0]},
    {id: "protected-site", name: "Protected site", role: "reject",
     bounds: [3.5, 6.5, 3.0, 6.0, 3.0, 11.0]}
  ],
  constrainToDomain: false,
  seed: 2021,
  freezeExisting: true,
  cutoffBasis: "covalent",
  cutoffScale: 1.0
}});

const scattered = await ai.describe({includePositions: true});
if (
  !scattered.addAtoms?.active
  || scattered.addAtoms.new_count !== 40
  || scattered.atomCount !== baseline.atomCount + 40
) {
  throw new Error("Random insertion did not produce the requested topology.");
}
if (
  scattered.addAtoms.regions.map(region => region.id).join(",")
    !== "left-channel,right-channel,protected-site"
  || !(scattered.addAtoms.domain.volume_angstrom3 > 0)
) {
  throw new Error("The exact multi-region domain or stable IDs were not preserved.");
}

await applyCurrent({operation: {
  name: "start-relaxation",
  fmax: 0.05,
  steps: 300,
  calculator: {
    device: "cpu",
    cpu_threads: 4,
    cutoff_mode: "absolute",
    cutoff_basis: "covalent",
    pair_cutoffs: scattered.addAtoms.pair_cutoffs,
    k_repulsion: 2.0,
    k_boundary: 5.0
  }
}});
```

Consume events or poll compact `describe` state until
`addAtoms.is_relaxing === false`. Do not issue another placement or structural
operation while it is active. If the optimizer must be interrupted, use common
`stop-relaxation` (or compatibility `stop-added-atoms`), wait for the stopped
state, inspect the latest positions, and either continue or cancel.

For a deterministic lattice instead of random scattering, set
`placementMode:"regular"` and optional `regularSpacing` in Angstrom. For a
spatially balanced but non-lattice initialization, use
`placementMode:"homogeneous"`. To resize active Allow/Reject regions without
moving staged atoms, call `scale-add-atoms-regions`; to change inserted atom
spacing itself, select the atoms and call `scale-selection`. Verify the latter
does not change the cell, atom radii, or bond diameter.

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

// Region edits and another atom or molecule placement stay in the same
// reversible staging session. The original host is still the only fixed base.
const revisedRegions = [
  {id: "left-channel", name: "Left channel", role: "allow",
   bounds: [1.0, 5.0, 1.0, 8.0, 0.0, 14.0]},
  {id: "right-channel", name: "Right channel", role: "allow",
   bounds: [5.5, 9.0, 1.0, 8.0, 0.0, 14.0]},
  {id: "protected-site", name: "Protected site", role: "reject",
   bounds: [3.5, 6.5, 3.0, 6.0, 3.0, 11.0]}
];
await applyCurrent({operation: {
  name: "update-add-atoms-region",
  regions: revisedRegions,
  regionMic: true,
  constrainToDomain: false
}});
await applyCurrent({operation: {
  name: "scatter-molecules",
  molecules: [{name: "H2O", label: "water", count: 2}],
  regions: revisedRegions,
  placementMode: "homogeneous",
  coordinateBasis: "cartesian",
  randomOrientation: true,
  rigidMolecules: true,
  freezeExisting: true,
  seed: 2022
}});
const expanded = await ai.describe({includePositions: false});
if (
  expanded.addAtoms?.placement_count !== 2
  || expanded.addAtoms.last_batch_new_count !== 6
  || expanded.addAtoms.new_count !== 46
  || expanded.atomCount !== baseline.atomCount + 46
) {
  throw new Error("Repeated placement did not remain in one staging session.");
}
await applyCurrent({operation: {
  name: "start-relaxation",
  fmax: 0.05,
  steps: 300,
  calculator: {
    device: "cpu", cpu_threads: 4, cutoff_mode: "absolute",
    cutoff_basis: "covalent", pair_cutoffs: expanded.addAtoms.pair_cutoffs,
    k_repulsion: 2.0, k_boundary: 5.0
  }
}});
for (;;) {
  placed = await ai.describe({includePositions: false});
  if (!placed.addAtoms?.is_relaxing) break;
  await new Promise(resolve => setTimeout(resolve, 500));
}
await applyCurrent({operation: "finish-add-atoms"});

const committed = await ai.describe({includePositions: true});
if (committed.addAtoms !== null || committed.atomCount !== baseline.atomCount + 46) {
  throw new Error("Add Atoms was not committed cleanly.");
}
for (let index = 0; index < baseline.atomCount; index += 1) {
  const error = Math.hypot(...committed.positions[index].map(
    (value, axis) => value - baseline.positions[index][axis]
  ));
  if (error > 1e-12) throw new Error(`Host atom ${index} moved by ${error} A.`);
}
```

For Cartesian regions, use six Angstrom bounds. The exact domain is the finite
cell intersected with the Allow union, or the complete cell when there is no
Allow, minus the Reject union. Without a finite cell, require an Allow region.
`constrainToDomain:false` is the default and means the Boolean domain only
defines initial positions; set it true only when repulsive placement must keep
every staged atom in the Allow union and outside every Reject region. Rigid
molecules use their native ASE template origin for this constraint.
`allowEscape` is the inverse compatibility field.
`update-add-atoms-region` accepts a complete region array or one
stable region ID and changes geometry, role, name, `regionMic`, or escape
policy without moving staged atoms. Verify the returned exact volume, periodic images,
sampling diagnostics, mode-only placement timeline, and host invariants before
optimization. Use `cancel-add-atoms` at any point before finish to restore
coordinates, constraints, arrays, labels, history, and redo state exactly.
For GUI validation, require one intact source cuboid with its original six
Cartesian bounds plus only cell-clipped, nonzero lattice-shift fragments at the
opposite periodic faces. Shared fragment edges must not be drawn twice.

For molecules, discover the installed catalog and preserve geometry unless
the user explicitly requests atomwise internal motion. The concrete density
checks below use `examples/readme_scene_assets/layered_water_channel.traj`:

```javascript
const capabilities = await ai.capabilities();
if (!capabilities.addAtoms.moleculeCatalog.some(item => item.name === "H2O")) {
  throw new Error("H2O is unavailable in the installed ASE molecule catalog.");
}
await applyCurrent({operation: {
  name: "scatter-molecules",
  molecules: [{name: "H2O", label: "channel_water", count: 1}],
  quantityMode: "density",
  targetDensityGcm3: 0.65,
  regionMode: "regions",
  regionMic: true,
  regions: [
    {id: "lower-slit", role: "allow",
     bounds: [1, 7, 0.7, 9.13804859, 0.65, 5.35]},
    {id: "upper-periodic-slit", role: "allow",
     bounds: [1, 7, 0.7, 9.13804859, 6.65, 11.35]},
    {id: "upper-gate", role: "reject",
     bounds: [3, 5, 3.2, 6.6, 8, 10.4]}
  ],
  placementMode: "random",
  pbcAware: true,
  randomOrientation: true,
  rigidMolecules: true,
  freezeExisting: true,
  seed: 1207
}});
const staged = await ai.describe({includePositions: true});
if (
  staged.addAtoms?.content_kind !== "molecules"
  || staged.addAtoms.molecule_count !== 10
  || staged.addAtoms.new_count !== 30
  || staged.addAtoms.density?.target_g_cm3 !== 0.65
  || Math.abs(
    staged.addAtoms.density?.actual_g_cm3 - 0.6509035344988875
  ) > 1e-12
  || Math.abs(staged.addAtoms.domain.volume_angstrom3 - 459.58594030630485) > 1e-8
) {
  await applyCurrent({operation: "cancel-add-atoms"});
  throw new Error("Molecule staging failed semantic verification.");
}
```

In density mode, Count is a composition ratio. Reduce it to the primitive
integer ratio before choosing a complete multiplier. Verify the reported
primitive ratio, actual density, and integer composition multiplier; do not
recompute volume from the Cartesian cell bounding box or round each species
separately.

Verify every reported molecule group has the same pair-distance matrix as its
ASE template before and after repulsive placement. Whole-group `G`/`R`
transforms are valid in rigid mode; a transform that changes only part of one
molecule must fail. Finish only after the host coordinates, constraints,
labels, arrays, and calculator are unchanged. Otherwise cancel and report the
failed invariant.

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
With one selected atom, the Inspector shows its displayed Cartesian/fractional
position and lazily retrieves every stored ASE per-atom array and calculator
result for the active frame. Replica inspection keeps the replica's displayed
position but reads properties from its base index. Use
`capabilities().atomProperties` for the equivalent machine-readable payload;
this inspection must not evaluate an attached calculator.

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
const sync = analyzed.analysis.frameSynchronization;
if (sync.displayedFrame !== analyzed.frame
    || sync.displacementFrame !== analyzed.frame) {
  throw new Error("Enabled trajectory analysis is stale.");
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

For GUI RDF playback, calculate the distribution once before pressing Play.
Confirm the drawer remains mounted while frames advance and that
`describe().analysis.frameSynchronization.rdfFrame` follows `displayedFrame`.
Ordinary trajectories may be fully prepared; large result products must use a
bounded rolling cache rather than retain every curve indefinitely.

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
The current hkl is authoritative as soon as its input commits; the Agent does
not need to wait for a pending high-resolution slice before starting `G` or
`R`.

Do not combine grids with different dimensions, cell, origin, PBC, or units.
Do not hide that validation error by interpolating one grid onto another.

### Radial And Finite Pair Distributions

Input: either a fully periodic 3D structure/trajectory frame for bulk RDF, or
a finite structure with every PBC axis disabled for a Pair-distribution
function. Partial PBC is rejected.

```javascript
const before = await ai.describe({includePositions: false});
const pbcCount = before.pbc.filter(Boolean).length;
if (pbcCount !== 0 && pbcCount !== 3) {
  throw new Error("Pair-distribution analysis rejects partial periodicity.");
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
if (pbcCount === 3 && rdf.analysisKind !== "rdf") {
  throw new Error("A fully periodic document must report bulk RDF normalization.");
}
if (pbcCount === 0 && rdf.analysisKind !== "pair-distribution") {
  throw new Error("A finite document must report Pair-distribution function normalization.");
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
3. with `pairMode:"selected"`, both endpoints of at least one active bond are
   selected and changing to a different active label pair refreshes the curves;
   selecting another bond of the same label pair must reuse the existing result;
4. the requested cutoff is retained and all required periodic-image extents
   are reported, even when a fixed `2 x 2 x 2` repetition is insufficient;
5. CSV radius count equals `bins`;
6. a homogeneous periodic test system approaches `g(r) = 1` away from the
   first few bins across several cutoffs, including beyond the unique-MIC
   reference;
7. a finite no-PBC full-range result integrates to one unordered-pair
   probability, while a shorter explicit cutoff integrates to the fraction of
   pairs inside that distance.

## Match Periodic Interfaces

### Bounded Commensurate 2D Cells

Use this workflow only for cells with two periodic in-plane vectors. The
commensurate rotation axis is global Z and the lattice search is restricted to
the XY plane. Enabling the workspace calculates a bounded family of integer
host/guest supercells immediately. In the GUI it preserves the current direct
guest angle instead of jumping to the smallest candidate. Black host and
orange guest parent lattices remain visible at unmatched angles; the green
common-cell boundary and materialization controls appear only when the current
angle resolves a bounded match. The parent-grid dimensions are fixed for the
configured bounded search and must not resize as the angle or nearest candidate
changes; only the green candidate boundary changes size. An explicit semantic
`calculate-commensurate` request with no `angleDeg` still selects the smallest
valid match under the strain cutoff and default `maxAreaRatio` of 16. The
interactive area bound is `1..128`; do not silently clamp or sample a larger
request, and never silently materialize a proposal.

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
the candidate selected by the explicit request. **3D overview** uses angle, area ratio, and max
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
Verify the distinct host and guest parent-lattice outlines and both integer
matrices. Require the common-cell outline only after the direct angle resolves
the selected candidate. With `showAtoms: true`, require opaque core atoms, a
one-primitive-cell boundary shell, and all preview bonds across the proposed
supercell. Remove a guest with `remove-commensurate-guest`.

For the visual different-lattice check, launch
`examples/commensurate_host_guest/graphene_host.extxyz` and load
`examples/commensurate_host_guest/mos2_guest.extxyz`. The parent lattice
constants are `2.46 Å` and `3.18 Å`, so their black/orange primitive grids must
be visibly different and remain fixed in extent. With guest strain `2.5%` and
`maxAreaRatio:16`, require a rectangular graphene
`(√7 × √21) R±19.11°` area-14 / MoS2 `2 × 2` area-4 match at
`|19.10660535|` degrees with maximum principal strain `0.023357` to displayed
precision. Both parent grids share one fixed in-plane origin. Atom visibility
must remain independent of candidate validity. Treat that as a shared in-plane
origin contract rather than deriving a display offset from the atom-rotation
pivot.

For the stricter deterministic numerical check, load
`examples/commensurate_host_guest/cu111_guest.extxyz` instead. With guest
strain `1%` and `maxAreaRatio:16`, require the smallest graphene `√13` /
Cu(111) `√12` match at `|16.10211375|` degrees, max principal strain
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

### Rigid Translation

Run this after selecting the component that should move together. Choose a
nonzero integer `(hkl)` whose plane contains two translations allowed by the
current PBC. The optional map samples one primitive plane-lattice period while
leaving source coordinates unchanged. No selection, a whole-structure
selection, or an incompatible partially periodic plane must produce a clear
error rather than an empty graph:

```javascript
await applyCurrent({
  selection: {clear: true, indices: [36, 37, 38, 39]},
  operation: {
    name: "calculate-registry-map",
    indices: [36, 37, 38, 39],
    metric: "short-contact",
    gridX: 48,
    gridY: 48,
    hkl: [1, 0, 0]
  }
});
```

`short-contact` is a covalent-radii-scaled overlap score. `bond-strain` is the
RMS normalized deviation of enabled interfacial label-pair distances from
their references and can receive explicit `pairCutoffs`. Both are geometry
scores, not energies; lower values indicate less geometric penalty and must not
be described as a relaxed stacking energy.

The GUI displays a blank physical plane before a map is calculated. While the
rigid mode is active, `G` is projected into the requested plane and every
selected atom receives one identical Cartesian vector. The live marker must
track the unwrapped two-coordinate plane translation, and the graph must show
the exact skew periodic boundary and basis in Angstrom. Export a calculated
grid through the graph's save icon or the exact semantic export:

```bash
v_ase api "$COMMAND_URL" export --save registry.csv --params '{
  "format":"registry-csv",
  "indices":[36,37,38,39],
  "metric":"short-contact",
  "gridX":48,
  "gridY":48,
  "hkl":[1,0,0]
}'
```

CSV rows must retain the two plane-lattice coefficients, Cartesian translation,
`(hkl)`, primitive integer and Cartesian bases, metric, selected indices, and
metric definition. No paper citation is required for the generic geometry
score. RDF, commensurate, and planar-translation Plotly drawers all expose the
same icon-only CSV control beside the graph title.

The map is not required for manual or optimized translation. Activate the mode,
optionally set an exact initial vector, then refine only the common component
translation with the current calculator:

```javascript
await applyCurrent({operation: {
  name: "start-registry-relaxation",
  indices: [36, 37, 38, 39],
  hkl: [1, 0, 0]
}});
await applyCurrent({operation: {
  name: "set-registry-translation",
  coordinates: [0.125, -0.25]
}});
await applyCurrent({operation: {
  name: "run-registry-relaxation",
  fmax: 0.05,
  steps: 100
}});
```

Wait for `analysis.registryRelaxation.is_relaxing === false`. Verify every host
coordinate, the 3x3 cell, and all selected pairwise internal vectors exactly.
Every selected displacement must equal
`coordinates[0] * translation_basis_angstrom[0] + coordinates[1] *
translation_basis_angstrom[1]`; no individual atom may relax. For `(0,0,1)`,
selected z is also unchanged. `projected_force` is the selected component's net
Cartesian force projected into the chosen plane, in `eV/angstrom`. Inspect the
temporary `registry` timeline, then use `finish-registry-relaxation` to commit
one undoable edit or `cancel-registry-relaxation` to restore the exact pre-mode
structure. Both actions remove that temporary timeline.

For a rigid x/y/z search, activate Cartesian mode instead. This does not require
a periodic cell and does not relax individual atoms:

```javascript
await applyCurrent({operation: {
  name: "start-registry-relaxation",
  indices: [36, 37, 38, 39],
  space: "cartesian",
  maxDisplacement: 3.0
}});
await applyCurrent({operation: {
  name: "set-registry-translation",
  coordinates: [0.2, -0.1, 0.4]
}});
await applyCurrent({operation: {
  name: "run-registry-relaxation",
  fmax: 0.05,
  steps: 100
}});
```

`maxDisplacement` is a separate `±` bound for each Cartesian component. Verify
the analytic gradient against the negative selected net force, require one
identical displacement for every selected atom, and require exact host, cell,
constraint, and selected-internal-vector invariance. Commit or cancel with the
same operations as plane mode.

For visual alignment only, select the desired atom or atoms and apply:

```javascript
await applyCurrent({operation: {name: "center-selection-at-origin"}});
```

One atom uses its displayed position. Multiple atoms use the mass-weighted COM,
including selected periodic references. Verify that scene translation changes
while every ASE coordinate and cell value remains unchanged.

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

View replicas remain independent visual references. To hide only one displayed
image without changing ASE topology, select its exact `cellOffset`, run
`delete-selection`, and verify the resulting key in
`display.hiddenAtomReferences`. Structural analyses still use the complete ASE
structure and therefore require the GUI warning to be acknowledged. If the
user instead authorizes physical deletion, switch to Edit and delete the
deduplicated base index.

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
network access disabled and require zero network requests. Verify:

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
