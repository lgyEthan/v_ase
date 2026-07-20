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

Interactive atom edits still commit through ASE. In particular,
`Atoms.set_positions(..., apply_constraint=True)` remains the final authority
for constrained coordinates. Visualization-only mode skips calculator and edit
state that it cannot use, but preserves appearance, bonds, periodicity,
supercells, wrapping, trajectories, and exports.

## Validation

The 0.0.45 browser benchmark used a generated LAMMPS dump with 15,000 atoms and
16 frames (7.98 MB) in default visualization mode. A fresh local server origin
was opened in the in-app Chromium browser at a 1280 x 720 CSS viewport.

| Check | Result |
| --- | ---: |
| Fully rendered first frame | 3.19 s |
| Displayed atoms | 15,000 |
| Detected trajectory frames | 16 |
| Canvas backing size | 1280 x 720 |
| Extra render frames during 0.9 s idle | 0 |
| Live slider input | Frame 1 to frame 8 without mouse release |
| Viz-only x=2 supercell | 30,000 visible atom instances |

The timing includes page navigation, static asset loading from the fresh origin,
API fetch, scene construction, camera fit, and the first completed canvas render.
It does not include Python environment startup. Results depend on browser, GPU,
storage, trajectory syntax, and machine load, so this table is a regression
reference rather than a universal hardware guarantee.

## Regression Checks

`tests/test_frontend_regressions.py` locks down the demand-rendering and
instancing architecture. The full test suite also covers the optimized LAMMPS
reader, binary frame metadata, constraints, periodic bonds, supercells, export,
CLI entry points, and packaging.
