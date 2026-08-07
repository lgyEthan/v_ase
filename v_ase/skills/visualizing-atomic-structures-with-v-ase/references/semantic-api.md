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
10. Volumetric And RDF Analysis
11. Interface Theme And Personal Defaults
12. Rendering
13. Export
14. Multi-Document Control

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
selection references, measurements, display settings, camera, image export
profile, `preferences.interfaceTheme`,
`preferences.personalVisualDefaults`, `analysis.volumetricDatasets`, the
current RDF summary, and `collaboration.revision`.

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
| `rotate-to-commensurate` | `angleDeg`, selection/`indices`; optional `axis`, `pivot`, `strainTolerance`, `maxIndex`, `maxAreaRatio`, `maxAngleDifferenceDeg`, `showAtoms` | Rotate to the nearest validated 2D periodic match and show its bounded common-cell proposal; preview atoms remain off unless requested |
| `load-commensurate-guest` | `path`; optional `format`, `gap`, search controls | Load or replace the guest structure from inside the CLI launch directory; its minimum z is placed 3 Angstrom above host maximum z unless `gap` is supplied |
| `remove-commensurate-guest` | none | Remove the loaded guest without changing the host; a current atom selection can then act as a same-lattice guest |
| `calculate-commensurate` | optional `mode`, `axis`, `angleDeg`, `strainTarget`, `strainTolerance`, `maxIndex`, `maxAreaRatio`, `showAtoms` | Search bounded same-lattice or host/guest integer common cells and open the 3D overview plus paper strain projection; omitting `angleDeg` selects the smallest admissible cell, while supplying it selects the nearest admissible angle |
| `apply-commensurate-cell` | active proposal | Materialize the validated common cell as the ASE unit cell |
| `dismiss-commensurate-cell` | none | Close the proposal and restore the pre-preview camera |
| `calculate-registry-map` | selection/`indices`; optional `metric`, `gridX`, `gridY` | Scan one periodic XY cell of selected-component translations and open the heatmap |
| `undo` / `redo` | none | Traverse structure or visualization-setting history |
| `reset-coordinates` | none | Restore loaded coordinates and original cell |
| `start-relaxation` | `fmax`, `steps`, optional `calculator` | Start optimization |
| `stop-relaxation` | none | Request optimizer stop |
| `refresh-displacements` | optional `display` | Recompute displacement vectors |
| `load-volumetric` | `path`, optional `format`, `precision` | Load one VASP, Cube, or XSF grid as FP32 or FP64 |
| `show-volumetric` | `datasetId`, `level`, optional surface controls | Build one isosurface |
| `combine-volumetric` | `datasetIds`, `coefficients`, optional `name`, `precision` | Create a linear grid combination |
| `remove-volumetric` | `datasetId` | Remove one grid from the document |
| `calculate-rdf` | optional `cutoff`, `bins`, `pairMode`, `activePairs` | Calculate total and partial RDF curves |
| `set-atom-colorscale` | optional `enabled`, `field`, `map`, `reverse`, `scope`, `rangeMode`, `minimum`, `maximum`, `gamma` | Lazily color all or selected atoms by a discovered numeric per-atom value with a trajectory-consistent range |

## Per-Atom Colorscales

Do not guess MLIP or calculator field names. Read
`capabilities().atomColorScale.scalarCatalogUrl` to discover the current
frame's field IDs, labels, reductions, components, and units. Read
`colormapCatalogUrl` for every registered Matplotlib map. Catalog access is
explicitly lazy so an ordinary view incurs no colorscale work.

```javascript
const capabilities = await ai.capabilities();
const scalarCatalog = await fetch(capabilities.atomColorScale.scalarCatalogUrl)
  .then(response => response.json());
const uncertainty = scalarCatalog.fields.find(field => (
  field.source === "array" && field.name === "mlip_uncertainty"
));
await ai.apply({
  selection: {clear: true, indices: [0, 1, 2, 3]},
  operation: {
    name: "set-atom-colorscale",
    enabled: true,
    field: uncertainty.id,
    map: "viridis",
    scope: "selected",
    rangeMode: "trajectory",
    gamma: 1.0,
    reverse: false
  }
});
```

Coordinates use `position:x`, `position:y`, and `position:z`; stored force
magnitude uses `force:norm`. Numeric multidimensional arrays expose a norm and,
for compact vectors/tensors, individual components. Fast LAMMPS trajectories
also register every finite numeric atom column, including arbitrary `c_*`,
`f_*`, and model-specific scalar names. The operation never asks an attached
calculator to evaluate missing results. Disable it with
`{"name":"set-atom-colorscale","enabled":false}` to restore the pre-existing
atom appearance immediately.

`rangeMode` has three exact meanings:

- `"current"` resolves one finite `vmin`/`vmax` pair from the active frame and
  locks it while the trajectory frame changes;
- `"trajectory"` scans all frames and accumulates one global finite range. A
  bounded frame-by-atom scalar buffer is loaded once and reused during
  playback; inputs beyond that cache budget use a backend extrema scan;
- `"manual"` requires finite `minimum` and `maximum` with
  `maximum > minimum`.

Use `capabilities().atomColorScale.rangeUrl` to inspect a current-frame or
full-trajectory range before applying it. A selected-only scan uses the current
selection on every frame and fails if it contains no finite value. `gamma` is a
contrast transform in the valid range `0.1..5.0`; `1.0` is unchanged. Once a
range is resolved, viewport playback and image, video, HTML, and geometry
exports use that same range. Do not refit each frame during playback.
The full-range load supersedes scheduled next-frame prefetch, so one range scan
must not trigger duplicate frame requests. Disabling the colorscale removes
all per-frame recoloring work and restores the previous visual appearance.

Atom labels are exact user-facing identifiers, not fixed-width display
abbreviations. Preserve the complete label returned by `describe`; do not
truncate it before `set-identity`, bond-pair, RDF-pair, or export operations.

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

Commensurate search, rotation, and explicit materialization are deliberately
separate. The rigorously supported plane is global XY with rotation about
global Z.

Enabling the workspace without a selection shows only the host primitive cell
and vectors. For a same-lattice twist, select the rotating component; v_ase
then gives that component a separate, rotatable copy of the current cell:

```javascript
const proposed = await ai.apply({
  mode: "edit",
  selection: {clear: true, indices: [0, 1]},
  operation: {
    name: "calculate-commensurate",
    mode: "same-lattice",
    axis: "Z",
    angleDeg: 0,
    strainTolerance: 0.01,
    maxAreaRatio: 16,
    showAtoms: false
  }
});
```

For different lattices, first load or replace the guest from a path confined to
the directory in which `v_ase gui ... --cli` was launched. The default `gap`
is 3 Angstrom, defined as guest minimum z minus host maximum z:

```javascript
await ai.apply({operation: {
  name: "load-commensurate-guest",
  path: "layers/hbn.cif",
  gap: 3.0
}});
const searched = await ai.apply({operation: {
  name: "calculate-commensurate",
  mode: "host-guest",
  axis: "Z",
  angleDeg: 0,
  strainTarget: "guest",
  strainTolerance: 0.01,
  maxAreaRatio: 16,
  showAtoms: false
}});
```

Inspect `searched.analysis.commensurate` and
`searched.analysis.commensurateProposal`. They report the guest, mode, current
angle, references, host/guest matrices and area ratios, crystallographic
notation, selected strain target, cells-only/atom preview counts, and whether
materialization is supported. Candidate rows also expose max principal strain,
mean absolute strain, and host/guest/total atom counts. Use
`rotate-to-commensurate` only after choosing a particular same-lattice
candidate angle. A loaded guest replaces any selected same-lattice guest for
the search. Set `showAtoms:true` only when the human needs the atom/bond halo;
cells-only is clearer and cheaper. Host primitive cells/vectors are black,
guest cells/vectors are orange, and the proposed common cell is teal. Changing
the direct guest angle must not move or reframe the camera.

The **3D overview** puts rotation on the explicit horizontal x axis, common-cell
area ratio on depth layers, and max principal strain on the vertical axis; its
live plane follows the current guest angle. **Paper strain projection** plots the
Stradi mean absolute strain against actual common-cell atom count and colors
markers by angle. Candidate acceptance always uses max principal strain, so
switching views cannot change the proposal. Export semantic data without
reading pixels:

```bash
v_ase api "$COMMAND_URL" export --save common-cells.csv --params '{
  "format":"commensurate-csv",
  "mode":"host-guest",
  "strainTarget":"guest",
  "strainTolerance":0.01,
  "maxAreaRatio":16
}'
```

Only after explicit user approval and a supported single-structure proposal:

```javascript
await ai.apply({operation: "apply-commensurate-cell"});
```

Use `dismiss-commensurate-cell` to keep the rotated coordinates without
materializing the proposal. Use `remove-commensurate-guest` to discard an
unmaterialized external guest. Never replace this workflow with ordinary
`display.supercell`, `set-supercell`, or one guessed integer matrix; those are
different operations. A match minimizes a bounded cell-boundary mismatch, not
an electronic energy.

Registry-map scan after selecting the moving interface component:

```javascript
const registry = await ai.apply({
  selection: {clear: true, indices: [40, 41, 42, 43]},
  operation: {
    name: "calculate-registry-map",
    metric: "short-contact",
    gridX: 48,
    gridY: 48
  }
});
```

`metric` is `"short-contact"` or `"bond-strain"`. Bond strain requires at
least one enabled selected-to-host pairwise cutoff. Inspect
`registry.analysis.registryMap`: the optimum and current coordinates are
fractional in the two periodic in-plane cell vectors and lower is better.
While the map is active, GUI `G` movement is restricted to XY and updates the
current map marker. Export the calculated grid directly:

```bash
v_ase api "$COMMAND_URL" export --save registry.csv --params '{
  "format":"registry-csv",
  "metric":"short-contact",
  "gridX":48,
  "gridY":48
}'
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

`viewportBackground` changes the live GUI. It does not rewrite
`imageExport.options.backgroundColor`; set the export color explicitly when
the rendered file must match the viewport.

Transform and commensurate settings:

| Setting | Values |
| --- | --- |
| `rotatePivot` | `"selection"`, `"active"`, `"origin"`, or `"cell"` |
| `commensurateGuide` | show periodic 2D match candidates |
| `commensurateMode` | `"same-lattice"` or `"host-guest"` |
| `commensurateSnap` | snap to a candidate |
| `commensurateStrainTarget` | `"guest"` (default) or `"host"` |
| `commensurateStrainTolerance` | fractional boundary strain |
| `commensurateMaxIndex` | integer search bound |
| `commensurateMaxAreaRatio` | maximum proposed common-cell area ratio; default `16`, valid range `1..128` |
| `commensurateSnapRangeDeg` | angular snap window |
| `commensurateShowAtoms` | include preview atoms and one-cell boundary-bond halo; default false |
| `commensurateGuestAngleDeg` | selected or loaded guest rotation about global Z |
| `commensurateGuestOffset` | guest Cartesian display/materialization offset |
| `registryMetric` | `"short-contact"` or `"bond-strain"` |
| `registryGridX`, `registryGridY` | fractional XY grid dimensions, 4 through 160 |

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

## Volumetric And RDF Analysis

Use `load-volumetric` for VASP `CHGCAR`/`CHG`, `LOCPOT`, `PARCHG`, and
`ELFCAR`, or for Gaussian Cube and XSF grids written by Quantum ESPRESSO and
other DFT codes. VASP stem detection accepts `.`, `_`, and `-` suffixes, for
example `PARCHG_band_12`, `LOCPOT.vacuum`, and `CHGCAR-difference`. The path is
resolved inside the directory from which the GUI was launched:

```javascript
await ai.apply({
  operation: {
    name: "load-volumetric",
    path: "charge/CHGCAR",
    precision: "fp64"
  }
});
const state = await ai.describe({includePositions: false});
const densityId = state.analysis.volumetricDatasets.at(-1).id;
```

`load-volumetric` immediately displays the newest dataset at an in-range
default isovalue. Use `show-volumetric` to replace that default with an exact
scientific level, signed/single mode, colors, mesh detail, and opacity.

Use explicit `format` only when the filename is ambiguous. Accepted aliases
include `"chgcar"`, `"locpot"`, `"parchg"`, `"elfcar"`, `"cube"`,
`"qe-cube"`, `"xsf"`, and `"qe-xsf"`. Precision is `"fp32"`/`"float32"`
or `"fp64"`/`"float64"`. When omitted, loading uses the current **Import
precision** setting. Verify `precision` and `memory_bytes` in the returned
dataset descriptor. FP64 preserves double-precision values and uses twice the
grid memory.

Create an isosurface with a finite level and a dataset ID returned by
`describe()`:

```javascript
await ai.apply({
  operation: {
    name: "show-volumetric",
    datasetId: densityId,
    level: 0.015,
    surfaceMode: "signed",
    stepSize: 1,
    smearingSigma: 0.4,
    smoothingIterations: 6,
    opacity: 0.72,
    positiveColor: "#2a9d8f",
    negativeColor: "#d1495b"
  }
});
```

`surfaceMode` is `"single"` or `"signed"` and `stepSize` is `1`, `2`, or
`4`. A smaller step preserves more grid detail and takes more time.
Signed mode interprets `level` as a nonzero magnitude and requests
`+abs(level)` plus `-abs(level)`. If smearing leaves only one sign inside the
displayed scalar range, v_ase keeps that valid surface and reports
`partialSignedSurface: true`; it never silently invents the missing surface.
`smearingSigma` is `0` through `8` grid voxels and filters only a display copy
of the scalar field. It wraps periodic axes and reflects nonperiodic axes.
`smoothingIterations` is an integer from `0` through `30` and fairs only the
extracted mesh while keeping cell-boundary vertices fixed. Set either to `0`
to disable that stage. Smearing can change small-scale topology and the
displayed scalar range, so begin near `0.3` to `0.5` and verify the surface;
do not present a heavily smeared surface as raw data.
`opacity` is `0.05` through `1`; colors are six-digit `#RRGGBB` strings.
Invalid semantic values are rejected rather than rounded or clamped.

GUI opacity/color input and repeated `show-volumetric` commands restyle the
existing mesh immediately; marching cubes is rerun only when the dataset,
isovalue, sign mode, detail, smearing, or smoothing changes. Isosurfaces
repeat with `display.supercell` and move with visual translation. A physical
`set-supercell` operation repeats the stored volumetric grid as well as every
trajectory frame.
Identical mesh requests use a bounded per-dataset LRU cache. The complete
scalar grid stays in the backend and the browser receives an aligned binary
mesh, so agents must validate the dataset summary and mesh metadata rather
than attempting to transfer or decode the full grid through `describe()`.
`reset-coordinates` restores the originally loaded atom frames, cell, and
scalar grids together after a materialized diagonal supercell. Undo and Redo
retain the same atom/grid pairing.

After generation, `describe().analysis.volumetricSurface` reports
`renderedLevels`, `surfaceCount`, `triangleCount`, `displayMinimum`,
`displayMaximum`, `smearingSigma`, `smoothingIterations`, and
`partialSignedSurface`. The source dataset descriptor remains separate under
`analysis.volumetricDatasets`; comparing that descriptor before and after is
the API-level check that display-only refinement did not replace the source.
Bitwise source-array identity is enforced by the package regression suite
because the semantic API intentionally does not transmit full scalar grids.

Charge-density differences use a linear combination:

```javascript
await ai.apply({
  operation: {
    name: "combine-volumetric",
    datasetIds: [combinedId, fragmentAId, fragmentBId],
    coefficients: [1, -1, -1],
    name: "charge-density difference",
    precision: "fp64"
  }
});
```

The source grids must have identical dimensions, cell, origin, PBC, and units.
When `precision` is omitted, the output promotes to FP64 if any input is FP64;
otherwise it remains FP32. Do not resample or combine mismatched grids
silently. Use `remove-volumetric` with `datasetId` to discard a dataset.

RDF requires a fully periodic 3D cell. The backend accepts a cutoff beyond the
unique-MIC radius and enumerates every periodic image inside that sphere. It
does not truncate the calculation to a fixed `2 x 2 x 2` replica. The result
reports `requestedCutoff`, `cutoff`, `uniqueMicCutoff`,
`periodicImageExtent`, and `periodicImageSpan`:

```javascript
await ai.apply({
  operation: {
    name: "calculate-rdf",
    cutoff: 6.0,
    bins: 300,
    pairMode: "active"
  }
});
const result = await ai.describe({includePositions: false});
```

`pairMode` is:

- `"active"`: partial curves for currently enabled pairwise bond labels;
- `"all"`: every distinct visual-label pair;
- `"none"`: total RDF only.

Supply `activePairs` explicitly when reproducibility must not depend on the
current bond panel, for example `[["Cu_surface", "O_ads"]]`. The total curve is
always present. Partial curves follow the conventional concentration relation:
for a binary system,
`g = c_a^2 g_aa + 2 c_a c_b g_ab + c_b^2 g_bb`.
`bins` must be between 8 and 5000.
The GUI adds a dotted `g(r) = 1` reference for the homogeneous bulk limit.
For a sufficiently large amorphous periodic model, verify that the
long-distance total curve fluctuates around one rather than decaying with
radius.

Export the calculated values without reading Plotly pixels:

```bash
v_ase api "$COMMAND_URL" export --save rdf.csv --params '{
  "format":"rdf-csv",
  "cutoff":6.0,
  "bins":300,
  "pairMode":"all"
}'
```

## Interface Theme And Personal Defaults

The application interface theme is independent of
`display.viewportBackground`. Use `system` to follow the browser/OS color
scheme or choose an explicit light/dark interface:

```javascript
await ai.apply({operation: {
  name: "set-interface-theme",
  theme: "system"
}});
```

`describe().preferences.interfaceTheme` reports the stored preference and the
currently resolved theme. The operation is `set-interface-theme`; accepted
values are `system`, `light`, and `dark`.

To make the current reusable visual setup the OS user's starting style for new
structures and tabs:

```javascript
await ai.apply({operation: "set-personal-visual-default"});
```

`set-personal-visual-default` stores appearance, bonds, lighting, viewport,
display replication, visual translation, render quality, and image-export
defaults. It excludes coordinates, trajectory data, cell contents, absolute
camera placement, and per-atom appearance overrides. Verify
`describe().preferences.personalVisualDefaults === true` afterward.

Deleting that preference is a low-freedom operation. Obtain explicit human
approval, then send the mandatory confirmation:

```javascript
await ai.apply({operation: {
  name: "restore-app-visual-defaults",
  confirm: true
}});
```

`restore-app-visual-defaults` deletes the saved personal default and applies
the built-in visual settings to the active tab without changing coordinates,
trajectory frames, or cell contents. Without `confirm: true`, v_ase rejects
the command. Portable `settings` export is separate and does not become the
OS user's automatic default merely by being exported.

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
| `rdf-csv` | total RDF and requested partial curves as CSV |
| `commensurate-csv` | angle/area candidates, both strain definitions, atom counts, integer matrices, notation, and citations |
| `registry-csv` | complete fractional XY registry grid and metric metadata |

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
