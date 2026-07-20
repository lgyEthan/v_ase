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
  visualization-mode supercell copies also use instancing.
- **Adaptive resolution**: device pixel ratio is capped at 1.5 above 1,000
  atoms, 1.25 above 5,000 atoms, and 1.0 at 15,000 atoms. Export resolution is
  independent and still uses the requested output dimensions.
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
- **Incremental live bonds**: interactive auto/element bonding uses a cell-list
  search above 384 atoms and rebuilds bond instances only when the inferred pair
  topology changes. Manual pairs bypass neighbor inference entirely.

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

## Regression Checks

`tests/test_frontend_regressions.py` locks down the demand-rendering and
instancing architecture. Browser tests also verify live interactive bond
formation/breaking and preservation of element-pair cutoffs across structure
updates. The full test suite covers the optimized LAMMPS reader, binary frame
metadata, constraints, periodic bonds, supercells, export, CLI entry points,
and packaging.
