# Rendering Performance

v_ase keeps ASE as the authoritative scientific backend while avoiding an ASE
object rebuild for every visual operation. The frontend is designed around a
small number of GPU batches and explicit render requests.

## Rendering Pipeline

- **Demand rendering**: the viewport requests a frame only for camera movement,
  trajectory playback, transforms, selection, or display changes. There is no
  permanent `requestAnimationFrame` loop while the scene is idle.
- **Instanced atoms**: structures above the renderer threshold use shared unit
  sphere geometry and `THREE.InstancedMesh`. Position, radius, color, fixed-atom
  state, and visibility are stored per instance.
- **Instanced secondary geometry**: large bond sets, large selections, and
  full-material supercell atom/bond copies also use instancing.
- **Adaptive resolution**: device pixel ratio is capped at 1.5 above 1,000
  atoms, 1.25 above 5,000 atoms, and 1.0 at 15,000 atoms. Export resolution is
  independent and still uses the requested output dimensions. PNG export can
  temporarily substitute a chosen sphere quality and `0.5x`-`2.0x` tessellation
  scale, then restores the original shared geometries without rebuilding the
  live scene.
- **Non-mutating image cameras**: PNG export renders through a cloned active
  camera. Exact-view mode contains the original aspect in the requested frame,
  while physical mode derives its projection from the live Viewport `Atomic scale`
  value. Editing that value changes only the active camera, without rebuilding
  atom, bond, or supercell geometry.
  Neither path refits or changes the viewport camera.
- **Targeted visibility updates**: label-to-index maps let a Visible checkbox
  update only the affected atom instances. Hidden atoms are also excluded from
  selection and bond display.
- **Cached summaries**: cell basis data, reciprocal transforms, atom-type
  indices, force maximum, and orientation-widget state are reused until their
  source data changes.
- **Binary trajectory frames**: large LAMMPS dumps are byte-offset indexed and
  subsequent frames are served as float32 positions instead of large JSON
  payloads or complete ASE object lists.
- **Opt-in lighting cost**: Modeling mode keeps the existing balanced lights,
  disables shadow maps, and does not allocate a continuous render loop. Studio
  Sun activates one directional PBR light only when selected. The soft-shadow
  mode additionally enables a single fitted PCF shadow map.
- **Incremental live bonds**: interactive auto/pairwise bonding uses a cell-list
  search above 384 atoms and rebuilds bond instances only when the inferred pair
  topology changes. Manual pairs bypass neighbor inference entirely. Custom-color
  bonds use one instance per pair; split atom colors use two half-length instances
  while retaining one GPU draw call for the complete bond set. Positive supercells
  reuse these batches and add only the nearest-image records needed to bridge
  internal replica boundaries; the displayed outer boundary remains clipped.
- **Blender point groups**: optimized Blender export writes one point mesh per
  visual label, instances smooth spheres with Geometry Nodes, stores trajectory
  frames as point-mesh shape keys, groups bonds by material, and writes the unit
  cell as one multi-spline curve. Individual atom objects are opt-in.

Interactive atom edits still commit through ASE. In particular,
`Atoms.set_positions(..., apply_constraint=True)` remains the final authority
for constrained coordinates. Visualization-only mode skips calculator and edit
state that it cannot use, but preserves appearance, bonds, periodicity,
supercells, wrapping, trajectories, and exports.

## Validation

The 0.0.46 browser benchmark used a generated LAMMPS dump with 15,000 atoms and
16 frames (7.07 MiB) in default visualization mode. A fresh local server origin
was opened in the in-app Chromium browser at a 1280 x 720 CSS viewport.

| Check | Result |
| --- | ---: |
| Fully rendered first frame | 4.06 s |
| Displayed atoms | 15,000 |
| Detected trajectory frames | 16 |
| Canvas backing size | 1280 x 720 |
| Extra render frames during 0.9 s idle | 0 |
| Default lighting / shadow map | Modeling / off |
| Studio Sun activation | 79 ms |

The timing includes page navigation, static asset loading from the fresh origin,
API fetch, scene construction, camera fit, and the first completed canvas render.
It does not include Python environment startup. Results depend on browser, GPU,
storage, trajectory syntax, and machine load, so this table is a regression
reference rather than a universal hardware guarantee.

### Blender export benchmark

The 0.0.59 Blender integration benchmark generates a 15,000-atom, two-label
periodic scene, runs the generated Python in Blender 5.0.1, validates that only
two editable atom point groups contain all 15,000 atoms, and saves a native
`.blend` file.

| Check | Result |
| --- | ---: |
| Generated atoms | 15,000 |
| Atom scene objects | 2 point groups |
| Total Blender objects | fewer than 12 |
| Script execution and `.blend` save | 0.700 s |

The runtime test separately renders a colored Cu-O scene and verifies smooth
Geometry Nodes atoms, midpoint-split bonds, unit cell, orthographic camera,
trajectory shape keys, and exact Blender `SUN` source, target, direction, and
energy. Timing is machine-specific; the test enforces a conservative 20-second
regression ceiling rather than claiming a universal import time.

## Regression Checks

`tests/test_frontend_regressions.py` locks down the demand-rendering and
instancing architecture. Browser tests also verify live interactive bond
formation/breaking, repeated supercell bonds, displayed-supercell boundary
clipping in monoclinic cells, interactive-mode replica
exclusion, visualization-mode replica selection/measurement, atomic relabel
commits, independent persistent Measure and pointer-driven Hover HUDs, and
preservation of label-pair cutoffs across structure
updates. The full test suite covers the optimized LAMMPS reader, binary frame
metadata, constraints, periodic bonds, supercells, export, CLI entry points,
project/settings round-trips, Blender 5 runtime rendering, the 15,000-atom
Blender benchmark, and packaging.
