<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-2f855a.svg)](LICENSE)

`v_ase` brings ASE's convenient terminal and Python workflow together with
direct, Blender-style 3D structure editing. Open a structure or trajectory
with one command, inspect and measure it in a local browser, edit it manually
or let an external AI agent translate a natural-language request into verified
structure operations, then export publication images, videos, and reusable 3D
scenes.

![Phosphorene nanoribbon manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

The animation builds a phosphorene nanoribbon twist one ridge at a time. Each
amber box selects the remaining ridges, the Transform controls apply an exact
X-axis rotation, and the sequence reaches a 13.85 degree twist before the
completed structure is inspected from above and below.

| Work directly in v_ase | Included |
| --- | --- |
| Structures and trajectories | ASE-supported formats, live timeline, per-frame bonds |
| Geometry editing | Ordered selection, `G` move, `R` rotate, exact transforms, random multi-species insertion |
| Scientific inspection | Distances, angles, torsions, displacement vectors, RDF, constraints |
| Volumetric fields | VASP and Cube/XSF grids, isosurfaces, density differences |
| Figure preparation | Appearance, bonds, lighting, exact preview, image/video export |
| Reproducible sessions | Self-contained `.vase` projects and reusable visual settings |
| Agent workflows | Semantic state/command API and a vendor-neutral AI skill |

## Quick Start

Install from PyPI:

```bash
python -m pip install v_ase-gui
```

Or install the current GitHub source:

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e .
```

Start an empty workspace or open a file:

```bash
v_ase gui
v_ase gui FILE
```

Examples:

```bash
v_ase gui POSCAR
v_ase gui trajectory.extxyz
v_ase gui relaxation.traj
v_ase gui project.vase
```

The default **View** mode is optimized for visualization, trajectories,
measurement, appearance, bonds, supercells, and export. Use the top-bar mode
switch or start directly in **Edit** when atomic coordinates must change:

```bash
v_ase gui structure.vasp --interactive
```

No Node.js installation or hosted account is required. Closing the v_ase
browser document releases the blocking terminal process.

## Common Tasks

| Goal | Action |
| --- | --- |
| Inspect a structure | Middle-drag to orbit, wheel to zoom, left-click to select |
| Edit coordinates | Enter **Edit**, select atoms, press `Esc` to focus the viewport, then use `G` or `R` |
| Insert one or many atoms | In **Edit**, open **+ Add atoms** and choose **Single** or **Random batch** |
| Measure geometry | Select 2, 3, or 4 atoms in the required order |
| Play a trajectory | Use the bottom timeline or `Space`; FPS and Skip update live |
| Plot an RDF | Use **Analysis > Radial Distribution Function** |
| View a charge or potential grid | Open CHGCAR/LOCPOT/PARCHG/Cube/XSF, then use **Analysis > Volumetric Data** |
| Style a figure | Use **Structure > Appearance/Bonding** and **View** |
| Match the app to the computer theme | Keep **View > Interface theme** on **System**, or choose Light/Dark explicitly |
| Reuse the current visual style automatically | Use **Export > Visual Settings > Set Current as Default** |
| Repeat or wrap a cell | Use **Structure > Cell & Replication** |
| Save the whole session | Use **Export > v_ase Project** and choose compact `.vase` or browser-ready HTML |
| Move a visual preset to another computer | Use **Export Preset**, then **Import Preset** |
| Share an offline 3D view | Use **Export > Rendered media > HTML View**; the lightweight view-only file is the default |
| Hand the scene to an AI | Provide the bundled agent skill; the agent starts the CLI/API session itself |

> **Viewport tip:** after selecting atoms, press `Esc` to close the control
> panel before using `G` or `R`. The selection is preserved and keyboard focus
> returns to the 3D viewport.

## Work With An AI Agent

You describe the scientific result to an external AI Agent. The bundled
[v_ase Skill](#agent-setup) teaches that Agent the exact CLI operations,
validation checks, and export steps. The Agent works through v_ase while the
same document remains visible and editable in the normal GUI.

![Human and external AI agent working in one live v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.png)

1. **You → Agent:** describe the source system, requested scientific change,
   and final camera in ordinary language.
2. **Agent → v_ase:** the Agent uses the Skill and structured CLI/API to read,
   modify, validate, and render exact atom data.
3. **v_ase → you:** the result appears in the same live GUI. A manual GUI edit
   becomes the next document revision seen by the Agent.

v_ase does not interpret the natural-language request or embed an LLM. The
external Agent translates it into exact, structured CLI/API operations.

For example, a human can ask:

> From pristine 6 × 6 graphene, create a pyridinic N3 vacancy, place Li 2.15 Å
> above it, and render a +Z top view with +Y up at 4K.

The Agent identifies atoms from structured state rather than estimating them
from screenshots, preserves the three substituted sites as `N_pyridinic`, and
labels the adsorbate `Li_site`. It sets the requested `+Z` view and `+Y` up
direction before rendering.
Reading structured atom state instead of repeatedly interpreting screenshots
can reduce token use while keeping coordinates, labels, and camera settings
directly verifiable.

The GIF below is recorded from the ordinary live GUI while a separate
`v_ase api` process sends each selection and atom edit through the public CLI
bridge. It does not use hidden in-page commands: the Agent and the human are
looking at the same revisioned document.

![Natural-language pyridinic N3 graphene edit](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_edit.gif)

The live `schema` is the authority for every supported operation and export.
v_ase checks that the operation/export lists reported to an Agent, the browser
handlers that update the GUI, and the bundled Skill stay identical. This
includes structure edits, constraints, trajectories, cameras, appearance,
volumetric fields and planes, colorscales, RDF, commensurate analysis,
rendering, and file export.

The example assets are generated from `ase.build.graphene`:

- [source graphene CIF](examples/readme_scene_assets/ai_graphene_source.cif)
- [intermediate pyridinic N3 CIF](examples/readme_scene_assets/ai_pyridinic_n3_graphene.cif)
- [final N3/Li-site CIF](examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.cif)
- [ASE trajectory preserving labels](examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.traj)

Codex, Claude Code, and GitHub Copilot names and marks belong to their
respective owners. They identify compatible external clients in the diagram;
no affiliation or endorsement is implied.

## Structure Manipulation

Use **Edit** when atom coordinates must change. Selection, measurement,
appearance, bonds, replication, wrapping, visual translation, and export
remain available in the default **View** mode.

### Select

- Left-click selects one atom; `Shift` + click extends or removes selection.
- Left-drag draws a visible selection box.
- Appearance rows select complete label groups without merging distinct labels.
- Ordered single-atom selections are retained for geometry measurement.

### Move

Press `G` after selecting atoms. Lock the move with `X`, `Y`, or `Z`, type an
exact displacement in angstrom, then confirm with left-click or `Enter`.
Configured ASE constraints remain authoritative when **Apply constraints** is
enabled.

### Add Atoms — New In v0.2.1

![Random multi-species insertion and repulsive placement in a triclinic cell](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_atoms.gif)

Open **+ Add atoms** in **Edit** mode:

- **Single** places one atom at an exact position or the current view center.
- **Random batch** accepts multiple Type, Label, and Count rows and scatters
  them together. A random seed makes the initial placement reproducible.
- **Unit cell** samples the full volume of an orthogonal or triclinic cell.
  **Cartesian box** limits placement to a visible `xmin`/`xmax`,
  `ymin`/`ymax`, `zmin`/`zmax` region inside its half-open primary periodic cell,
  so skew-cell boundaries are not sampled twice.
- **Temporarily fix existing atoms** keeps the loaded structure stationary
  while only the inserted atoms follow the pairwise repulsion. It is enabled
  by default.
- Choose covalent, van der Waals, or explicit element-pair cutoffs, then click
  **Repel** to remove short contacts with the minimum image convention.

The teal cell or box exists only while Add Atoms is active. **Finish** commits
the inserted atoms but reconstructs every pre-existing coordinate, array,
label, calculator, and constraint from the original structure. **Cancel**
removes the inserted atoms and restores that original structure completely.
For trajectories, open the target frame in a new tab before starting a random
batch.

The animation uses the included
[triclinic nanoporous Si example](examples/readme_scene_assets/triclinic_nanoporous_add_atoms.traj):
18 `Li_mobile` and 10 `H_probe` atoms are scattered with seed `2021`, then
placed using editable element-pair cutoffs while the `Si_framework` host stays
fixed.

### Rotate

Press `R` after selecting atoms. Choose **Selection COM**, **Active atom (last
selected)**, **Origin**, or **Unit-cell center** as the pivot, lock an axis if
needed, and enter an exact angle. To rotate around a particular atom, select
the moving atoms first and Shift-select the pivot atom last. For a panel-driven
edit, use **Structure > Transform > Exact selection rotation** to choose the
axis and angle, then click **Rotate Selection**. Both methods honor the current
constraint and undo settings. Every active rotation shows:

- the rotation axis through the chosen pivot;
- a neutral line fixed at the direction where the operation started;
- an amber line that follows the current structure;
- cyan candidate lines only when the commensurate guide is enabled.

#### Ferrocene: Use Fe As The Active Pivot

![Ferrocene pivot rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_pivot.gif)

Select the upper cyclopentadienyl ring first, then Shift-select Fe last. With
**Active atom (last selected)** enabled, Fe remains fixed at the exact rotation
pivot:

1. `R`, `Z` rotates the ring around the axis through Fe.
2. `R`, `X` folds the same ring around an X axis through Fe.

The active atom can be any selected atom; it does not need to coincide with the
global origin or the selection center.

#### Phosphorene: Build The Twist One Edit At A Time

![Cumulative phosphorene manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

The animation records a sequence of normal v_ase edits:

1. Keep the first puckered ridge fixed. Left-drag the visible amber box from
   the **second ridge through the end** of the ribbon, then release to commit
   the yellow outlined selection.
2. Open **Structure > Transform**, keep **Selection COM**, choose axis `X`,
   enter `1.538889` degrees, and click **Rotate Selection**.
3. Close the panel, left-drag a new box from the **third ridge through the
   end**, enter the same exact angle, and rotate again from the edited
   coordinates.
4. Continue advancing the box-selection boundary by one 12-atom ridge. After
   9 rotations, the final ridge is rotated by exactly 13.85 degrees.
5. Orbit the completed structure from above to below to inspect the full
   three-dimensional twist.

The amber box shows the current selection area, the yellow outline identifies
the atoms affected by the next edit, and bonds update after each rotation.

Black phosphorene has two puckered sublayers in one armchair unit cell. The
`5 x 6` model contains 10 puckered ridges with 12 atoms per ridge. Green and
purple distinguish the upper and lower P sublayers; both remain phosphorus in
the ASE structure.

The relaxed source coordinates come from the
[supporting information of Villegas et al.](https://www.rsc.org/suppdata/c6/cp/c6cp05566d/c6cp05566d1.pdf).
The 13.85 degree target is one of the H-APNR angles tabulated by
[Jang et al.](https://www.rsc.org/suppdata/c6/nr/c6nr04354b/c6nr04354b1.pdf),
and the green/purple sublayer convention follows published phosphorene
structure diagrams such as
[Zhang et al.](https://doi.org/10.1038/srep13927). The example demonstrates
geometry editing and is not an energy-minimized final structure.

#### Commensurate Atoms: Match Periodic 2D Cells

![Graphene hBN commensurate rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate.gif)

**Commensurate atoms** finds periodic in-plane common cells without changing the
ASE structure until a proposal is explicitly accepted. It is off by default.
When enabled, the first preview is cells-only:

- with no selected atoms, only the host primitive cell and vectors are shown;
- with a selected layer, those atoms become the guest and inherit a separate
  copy of the host cell;
- loading a guest structure replaces the selected guest with its own atoms and
  periodic cell.

Host primitive cells and vectors are black on the default white background,
guest cells are orange, and the suggested common-cell boundary is teal. As a
candidate or guest angle changes, both primitive lattices remain tiled through
their proposed supercells in real time. The current camera is preserved.
**Show preview atoms** optionally adds opaque supercell atoms, a
one-primitive-cell halo, and all enabled bonds across the preview boundary.

The bounded search reports progress and opens an interactive graph:

| Graph | Meaning |
| --- | --- |
| **Angle × cell size × strain** | Rotation is the explicit horizontal axis; common-cell area forms depth layers and maximum principal strain is vertical; a live plane follows the current angle |
| **Paper strain projection** | Mean absolute strain versus the actual host-plus-guest atom count, with angle shown by color |

The graph's save icon exports the plotted angle, strain, host/guest integer
matrices, atom counts, surface notation, and method citations as CSV.
**Maximum strain** always uses the conservative maximum principal stretch;
switching graphs does not change accepted candidates. **Maximum area ratio**
defaults to `16` and is explicitly bounded at `128` so the interactive search
remains exhaustive instead of silently sampling a larger space.

Two workflows use the same bounded integer-boundary search:

| Workflow | Host | Guest / rotating component |
| --- | --- | --- |
| Same-lattice twist | Unselected atoms and the current periodic cell | Selected atoms using a separate copy of that cell |
| Host/guest interface | The open structure and its cell | A second structure loaded with **Load or Replace Guest Structure** |

For a same-lattice graphene/hBN twist, select the hBN layer before enabling the
workspace. For a separate interface, load the guest file after enabling it.
The loaded guest is positioned so `guest min z − host max z = 3 Å` by default;
the **Interlayer gap / Å** field changes that separation. v_ase rotates the guest
atoms and guest cell together and never substitutes the host cell. **Apply
residual strain to** chooses whether the host or guest receives the remaining
in-plane deformation and defaults to the guest.

The proposal reports both integer matrices, both area ratios, residual strain,
and readable surface notation such as `(√7 × √7) R19.11°`. The default maximum
area ratio is `16`. On first selection or guest load, v_ase proposes the
smallest-area cell that satisfies the strain bound. Moving the guest angle then
tracks the valid candidate nearest that angle. No proposal is made when every
valid cell exceeds the chosen area or strain bound.

Commensurate matching is deliberately restricted to two periodic vectors in
the global XY plane and rotation about global Z. This is the rigorously defined
2D interface workflow; ordinary free atom rotation remains available when the
workspace is off. **Set Suggested Cell as Structure** materializes the current
validated proposal only in Edit mode. Trajectories and active volumetric fields
remain preview-only because applying one inferred layer-specific cell to every
frame or sampled field would be ambiguous.

The boundary-matching method follows the published integer-supercell and
minimal-strain formulations in
[CellMatch](https://doi.org/10.1016/j.cpc.2015.08.038) and the
[optimal interface-supercell method](https://doi.org/10.1088/1361-648X/aa66f3).
A full same-lattice hexagonal regression follows the commensurate integer-cell
family in the
[twisted-bilayer graphene geometry](https://doi.org/10.1103/PhysRevB.86.155449).
A suggested cell is a geometric periodic match, not an electronic energy
minimum.

### Separate Host And Guest Example

![Graphene and Cu(111) host/guest common-cell search](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate_host_guest.png)

The repository includes a deterministic graphene/Cu(111) validation pair:

```bash
v_ase gui examples/commensurate_host_guest/graphene_host.extxyz
```

Enable **Structure > Transform > Commensurate atoms**, then load
[`cu111_guest.extxyz`](examples/commensurate_host_guest/cu111_guest.extxyz)
with **Load or Replace Guest Structure**. Keep guest strain `1%`, interlayer gap
`3 Å`, and maximum area ratio `16`. The smallest match is graphene `√13`
against Cu(111) `√12` at `|16.10211375|°`.
The common cell contains 26 graphene atoms plus 12 Cu atoms. The
[example guide](examples/commensurate_host_guest/README.md) and
[`expected.json`](examples/commensurate_host_guest/expected.json) give the
exact maximum-principal and paper-style mean-strain values used by the tests.

The equations, numerical references, basis-invariance check, and measured
search bounds are collected in
[Commensurate Cell Scientific Validation](docs/commensurate_validation.md).

Normal `R` rotates selected atoms. **Cell Transform** is a separate periodic
operation that applies an integer matrix to the cell and every trajectory
frame. Display replication is separate again: it only repeats what is shown.
The common-cell equations, limits, and assumptions are documented in
[unit_cell_aware_rotate.md](docs/unit_cell_aware_rotate.md).

## Measurement And Analysis

![Ordered distance angle and torsion measurement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_measurement.gif)

The numbered `a1` to `a4` markers record selection order and are deliberately
different from atom indices.

| Ordered selection | Reported result |
| --- | --- |
| 1 atom | Label, element, position, force, charge, tag, magnetic moment |
| 2 atoms | Direct distance and minimum-image distance |
| 3 atoms | Angle `a1-a2-a3`, centered on `a2` |
| 4 atoms | Signed torsion `a1-a2-a3-a4` |
| 5 or more | Total count and per-label counts |

The connector, angle arc, torsion axis, and compact value badge stay attached
to the selected atoms. Hover information is independent, so moving the pointer
does not replace a saved measurement.

![Trajectory displacement analysis](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_displacement.png)

For trajectories, **Analysis > Displacement** compares the current frame with
the previous frame or a chosen reference. Minimum-image correction, vector
scale, thickness, color, and 2D/3D style are configurable. Displayed
supercells repeat the vectors, and visual translation moves both endpoints
without changing the physical displacement.

### XY Registry Map

After choosing a periodic interface cell, select the layer or adsorbate that
should translate and open **Analysis > XY Registry Map**. Starting the analysis
without a selection produces a direct selection warning. v_ase scans one full
periodic XY cell on the requested fractional grid while a staged progress
display reports the active step.

The default **Short-contact score** is a dimensionless, covalent-radius-scaled
geometry proxy. **Bond-strain RMS** instead uses enabled interfacial pairwise
bond cutoffs and reports normalized bond-length mismatch for those pairs. Both
scores are lower-is-better geometric screening metrics, not energies. Validate
the proposed registry with an appropriate electronic-structure or force-field
calculation before drawing physical conclusions.

The Plotly heatmap marks the best grid point and the current translation. While
the map is active, `G` is constrained to the periodic XY plane and the marker
follows the move continuously in fractional coordinates. The graph's save icon
exports the complete fractional X/Y grid, metric values, selected indices, and
method notes as CSV. RDF, commensurate, and registry plots all expose the same
adjacent save icon.

### Volumetric Fields

Open a VASP `CHGCAR`, `CHG`, `PARCHG`, `LOCPOT`, or `ELFCAR` directly. Common
suffixes used to distinguish calculations are recognized too, including names
such as `PARCHG_band_12`, `LOCPOT.vacuum`, and `CHGCAR-difference`. Quantum
ESPRESSO and other electronic-structure codes can use Gaussian Cube or XSF
grid output:

```bash
v_ase gui CHGCAR
v_ase gui LOCPOT
v_ase gui charge-density.cube
v_ase gui charge-density.xsf
```

**Analysis > Volumetric Data** separates the active dataset into three focused
workspaces: **Isosurface**, **Planes**, and **Combine**. Isosurface controls
cover the threshold, signed positive/negative surfaces, mesh detail, field
smearing, mesh smoothing, colors, and opacity without mixing those controls
with planar sections or field arithmetic.
Opening a volumetric file, or adding the first scalar field, immediately shows
an isosurface at a valid default level. A compact value-distribution ridge is
drawn directly above the isovalue slider, so dense and sparse parts of the
field remain visible while the threshold moves. Single-surface mode shows the
raw-value distribution; signed mode shows the `|value|` distribution used by
its magnitude slider. This histogram is calculated once when the dataset is
loaded and does not regenerate the surface.

Drag **Isosurface opacity** to update
the current surface live without regenerating its mesh. Multiple compatible
datasets can be combined with coefficients such as `+1, -1, -1` for a
charge-density difference. Grid values stay in the local v_ase backend; the
browser receives only the generated surface mesh.
Signed mode treats the isovalue as a nonzero magnitude and renders the
positive and negative crossings that remain inside the displayed field range.

![Smooth signed benzene pi-field isosurfaces with live opacity control](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric.gif)

**Planar Sections** samples the selected scalar field on one or more `(hkl)`
planes. Each plane has a signed offset in Angstrom along its reciprocal-space
normal measured from the volumetric grid origin, 128-1024 pixel sampling, any
available Matplotlib colormap, reverse, automatic or manual `vmin`/`vmax`, and
opacity. The sampled map is clipped to the displayed unit cell or supercell,
including skew cells, rather than drawn as an unbounded rectangle. Only the
compact 2D slice is transferred to the browser; the full 3D grid remains in
the backend.

Select several planes in the list to edit them together. Values shared by all
selected planes remain visible; mixed fields are left blank until a new value
is entered, then that value is applied to every selected plane. In **View**
mode, create and configure planes directly in the panel; this changes only the
visual analysis state and never edits ASE atom coordinates. In **Edit** mode,
the same panel remains available, and a selected plane can also be moved with
`G` only along its normal. Press `R`, optionally followed by `X`, `Y`, or `Z`,
to rotate its normal. The distance field, slider, and `(hkl)` fields follow the
viewport transform live. Movement uses a lower-resolution preview while the
pointer is active and restores the configured resolution after the transform
settles.

![Interactive hkl scalar-field plane clipped to the displayed cell](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric_plane.gif)

The plane in this GIF is added and swept by the same external `v_ase api`
operations available to an AI Agent; every committed offset is reflected in
the live GUI and returned by `describe().analysis.volumetricPlanes`.

**Field smearing σ** applies a Gaussian filter measured in grid voxels before
the isosurface is extracted. Periodic directions wrap across the cell;
nonperiodic directions reflect at their boundary. **Mesh smoothing passes**
then reduce voxel stair-steps on the extracted mesh while keeping cell-boundary
vertices fixed. The source scalar field, its saved precision, integral, and
charge-density-difference inputs are never modified. Set either control to
`0` to disable that stage. Because field smearing can merge small features or
change the range crossed by an isovalue, use the smallest value that removes
visible grid artifacts and verify the resulting topology.

Choose the import precision before opening or adding a scalar field. **FP32**
is the lower-memory default; **FP64** preserves double-precision grid values
and uses twice the grid memory. The same choice is available from the CLI:

```bash
v_ase gui CHGCAR --volumetric-precision fp64
```

The Python API exposes the same choice:

```python
from v_ase.visualize import view

view("CHGCAR", volumetric_precision="fp64")
```

Visual translation and displayed cell replication move or repeat the
isosurface together with the atoms. **Set Supercell as Cell** repeats both the
ASE structure and periodic scalar grid exactly for diagonal integer
replications. A general non-diagonal cell matrix is rejected while scalar
grids are loaded because preserving that sampled field would require an
explicit interpolation choice.
After a materialized diagonal supercell, **Reset Coordinates** restores the
original atoms, cell, and scalar grid together; Undo/Redo keeps the same
atomic field pairing.

Large scalar grids are parsed and meshed in the backend. Repeating the same
dataset, level, detail, smearing, and smoothing request reuses a bounded mesh
cache; changing only color or opacity updates the existing browser geometry.
This keeps ordinary structure viewing unaffected when no volumetric dataset is
loaded and avoids sending the complete FFT grid to the browser.

### Radial Distribution Function

**Analysis > Radial Distribution Function** plots the current frame in a
resizable Plotly drawer below the viewport. The total RDF is always included.
Pair curves default to the active bond-label pairs and can be switched to all
label pairs or total-only. Set the bin count and cutoff, then export exactly
the plotted columns as CSV.

RDF uses exact spherical shell volumes and ASE's periodic neighbor search in
the full triclinic cell. The requested cutoff is not limited to a `2 x 2 x 2`
replica or reduced at the unique minimum-image radius: v_ase includes every
periodic image whose distance falls inside the sphere and reports the image
span used. Bulk normalization is reported only for cells periodic in all three
directions; partial-PBC and finite systems require a separate boundary
correction and are rejected instead of returning a misleading bulk `g(r)`.

The dotted `g(r) = 1` reference makes the bulk limit explicit. In the
amorphous Cu-Zr example below, the broad short-range peak decays into a flat
long-range plateau rather than falling with the finite display cell.

![Amorphous Cu-Zr structure and RDF approaching the bulk limit](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_rdf.png)

## Constraints

ASE remains authoritative when **Apply constraints** is enabled. Constraint
visualization is local to each atom rather than merged at a group center.

### FixedLine

A short cyan line passes through each constrained atom and remains visible
without selection. Starting `G` displays a longer guide through the atom's
original position while ASE restricts movement to that direction. FixedLine
does not use a ring or plane disc.

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

```bash
v_ase gui examples/readme_scene_assets/fixedline.traj --interactive
```

### FixedPlane And FixScaled

Each constrained atom keeps its own local ring, crosshair, and normal marker.
When `G` starts, a larger translucent guide plane appears at that atom's
original position so the permitted surface remains visible while the atom
moves. Multiple selected atoms retain independent planes; no center-of-mass
plane is substituted.

VASP selective dynamics read as `FixScaled` are displayed from their allowed
fractional directions.

![FixedPlane movement and guide plane](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

```bash
v_ase gui examples/readme_scene_assets/fixedplane.traj --interactive
```

### FixAtoms

Fixed atoms keep their element color but use a distinct constrained surface
treatment. They remain identifiable without looking selected.

### Hookean

Hookean constraints show their inactive cutoff and engaged state separately.
After the constrained distance passes `rt`, a shaded 3D helical spring appears
between the constrained atoms.

![Hookean constraint](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.png)

![Hookean motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

```bash
v_ase gui examples/readme_scene_assets/hookean.traj --interactive
```

## Relaxation

![Repulsive relaxation trajectory](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_relaxation.gif)

**Structure > Relaxation** places every optimization step on a dedicated
timeline. A single loaded structure gains a relaxation movie after the first
run. If a source trajectory is already open, source and relaxation timelines
remain separate and the active timeline is clearly selected.

The included example starts from a deliberately compressed C60 geometry and
runs ASE FIRE with v_ase's repulsive fallback calculator:

- [crowded initial C60](examples/readme_scene_assets/crowded_c60_initial.cif)
- [relaxed C60](examples/readme_scene_assets/crowded_c60_relaxed.cif)
- [optimization trajectory](examples/readme_scene_assets/crowded_c60_relaxation.traj)

```bash
v_ase gui examples/readme_scene_assets/crowded_c60_initial.cif --interactive
```

The fallback calculator is intended for removing obvious close contacts, not
for predictive chemistry. Its cutoff scale and strength are editable. Attach a
scientific ASE calculator when the optimized energy or forces will be used as
physical results.

## Trajectories

Multi-frame inputs add a timeline below the viewport. Scrubbing updates the
frame continuously, selected atom indices persist when topology permits, FPS
changes apply during playback, and **Skip** advances by `skip + 1` source
frames per tick.

Bond topology is evaluated for each frame, so bonds form or break when a
pair crosses its cutoff. Appearance, pair settings, supercell display, camera,
and analysis settings remain active across the movie.

Video export uses FPS as playback speed. Optional `N x` interpolation creates
`(source_frames - 1) * N + 1` output frames. Minimum-image interpolation uses
periodic cells to avoid jumps across a boundary. Interpolation takes longer
because more frames are rendered.

## Appearance, Bonds, And Rendering

**Structure > Appearance** controls each stable atom label:

- ASE chemical TYPE and independent visual label;
- visibility and selection availability;
- color and radius;
- Standard, Metal, or Rubber material;
- all/partial/none selection checkbox.

View mode applies appearance by label. Edit mode can keep per-atom material
overrides. Relabeling does not reorder the table or merge otherwise distinct
atom types accidentally.

![Standard Metal and Rubber atom materials](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_materials.png)

The comparison uses three identical Cu13 clusters with the same element color
and radius, so only the optical material changes:

| Material | Visual response | Typical use |
| --- | --- | --- |
| Standard | Balanced diffuse color and compact highlight | General structures and chemically neutral figures |
| Metal | Strong environment reflection and bright metallic highlight | Metals, electrodes, and reflective surfaces |
| Rubber | High roughness with broad, muted highlights | Soft visual grouping and low-glare nonmetal regions |

Materials affect rendering only. ASE elements, coordinates, calculators, and
constraints are unchanged.

**Atom colorscale** maps a numeric per-atom property onto any registered
Matplotlib colormap. The property list is discovered from the open structure
and includes:

- Cartesian `x`, `y`, and `z` coordinates;
- force magnitude when stored forces are available;
- scalar, component, and vector-norm views of numeric `Atoms.arrays` values;
- per-atom calculator results such as charge, magnetic moment, local energy,
  uncertainty, or model-specific MLIP outputs.

LAMMPS trajectories also expose arbitrary numeric atom columns, so fields such
as `c_uncertainty`, `c_energy`, or custom descriptors can be selected without
converting the dump to another format.

![Trajectory-wide MLIP uncertainty colorscale with one locked range](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_atom_colorscale.gif)

Use **Selected atoms only** to color the current selection while preserving
the established appearance of every other atom. **Fit current frame** is the
default range: it derives `vmin` and `vmax` once from the visible frame, then
keeps that range fixed while the trajectory plays. **Scan trajectory** finds a
single range across every frame. For bounded large trajectories, the scan
stores one compact scalar cache and reuses it during playback; larger sources
fall back to backend range scanning. Entering either `vmin` or `vmax` switches
to a manual range. Every frame and export uses the resolved range consistently.

Reverse any map or adjust **Contrast (gamma)** from `0.1` to `5.0`; gamma is
applied immediately in the browser without another scalar or colormap request.
The feature remains lazy: while its toggle is off, v_ase does not load a
colormap registry, extract scalar arrays, or run per-frame colorscale work.
Turning it off immediately restores the existing label, element, and per-atom
appearance.

![Pairwise Cu O bonds in a Cu2O(111) film on Cu(111)](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_bonds.png)

**Structure > Bonding** provides automatic inference, explicit label-pair
cutoffs, and manual index pairs. A pair cutoff of zero disables that pair.
Changes apply immediately. Bonds support:

- cell-local or periodic minimum-image display;
- cylinder or flat 2D geometry;
- custom color or two half-bonds using the atom colors;
- configurable diameter;
- live formation and breaking during Edit transforms.

The top view shows a `6 x 6 Cu2O(111)` film on `7 x 7 Cu(111)`, with one
interfacial oxygen positioned over a substrate Cu top site.
The Cu(111) substrate uses a nearest-neighbor touching-sphere radius.
`Cu_oxide-O_oxide` and `Cu_substrate-O_oxide` bonds are enabled, while
`Cu_substrate-Cu_substrate`, `Cu_oxide-Cu_oxide`, cross-region Cu-Cu, and
O-O pairs are disabled. Dark metallic substrate Cu, bright standard-material
oxide Cu, and matte red oxide O separate the phases without changing ASE
elements. Each bond is split into the colors of its two endpoint atoms, so the
Cu-O connectivity remains readable without an unrelated custom bond color.
Separate oxide and substrate labels let each interaction be enabled or
assigned its own cutoff independently.

```bash
v_ase gui examples/readme_scene_assets/cu2o111_on_cu111_pairwise_bonds.traj
```

**View** controls projection, atomic scale, anti-aliasing, sphere smoothness,
background, 2D/3D display, grid, axes, unit cell, overlays, and cell material.
The **Axes** and **Unit Cell** switches update the working viewport
immediately; they are not export-only settings. Hiding world axes does not
remove the compact orientation gizmo. New documents use orthographic
projection and a true-white background.

The top-bar renderer switches between fast modeling light and Sun/soft-shadow
rendering. Sun source, target, intensity, and direction can be manipulated in
the viewport and carried into Blender export.

### Interface Theme And Personal Defaults

**View > Interface theme** controls the application chrome independently from
the white/dark 3D viewport background. **System** is the default and follows
the browser or operating-system light/dark preference, including changes made
while v_ase is open. **Light** and **Dark** keep an explicit choice in that
browser.

Under **Export > Visual Settings**, **Set Current as Default** stores the
current reusable appearance, bonds, lighting, viewport, display replication,
visual translation, and render-quality choices for the current OS user. New
structures and new tabs start with that style. Atom coordinates, trajectory
frames, cell contents, absolute camera placement, and per-atom appearance
overrides are not included.

**Restore App Defaults** deletes the saved personal default and applies the
built-in v_ase style to the active tab. v_ase lists what will change and waits
for **Proceed**; the structure itself is left untouched. **Export Preset** and
**Import Preset** remain the portable file-based option for moving a visual
preset between users or computers.

## Export And Save

| Command | Result |
| --- | --- |
| Export POSCAR | Current physical ASE structure in VASP format |
| Export ASE Pickle | ASE `Atoms`, labels, constraints, arrays, and a valid `SinglePointCalculator` |
| Export Image | PNG by default; JPEG, PDF, and lossless WebP from the exact preview frame |
| Export Video | Constant-frame-rate H.264 MOV or MPEG-4 AVI with optional interpolation |
| Export Blender | Optimized scene script with atoms, bonds, cell, camera, and Sun |
| Export 3DM | Instanced Rhino geometry, metadata, and saved camera views |
| Export OBJ | OBJ/MTL, camera, and metadata in a ZIP |
| Export HTML View | Offline, view-only 3D document; lightweight by default, with optional `.vase` recovery |
| Save `.vase` | Compact project with structure/trajectory and complete visual state |
| HTML Project | Browser-ready project with complete embedded `.vase` recovery by default |
| Export/Import Preset | Portable visual settings file without coordinates |

Image, video, and HTML use one shared **Preview Area** composition. Its aspect
ratio, camera, crop, lighting, atom scale, and included overlays match the
saved output. HTML View defaults to grid off, axes on, and unit cell on; all
three overlays can be changed before saving.

The system save picker is opened before expensive rendering or scene
generation when the browser supports it. Canceling the picker cancels the
export. Chrome may then show **This site can view changes you make to this
file**. That message is Chrome's File System Access permission notice: v_ase
can write only to the destination selected in that picker. Browser code cannot
hide the notice while retaining destination selection before rendering.

Image export uses one determinate progress bar for rendering, pixel capture,
upload, encoding, download, and the final file write. It reports estimated
remaining time and reaches 100% once, only after the destination is complete.
Video export follows the same monotonic rule across all frames and encoding.
Every source frame is retained exactly once at `1x`; interpolation adds
in-between frames. Visible displacement vectors and other selected scene
overlays are recalculated for each rendered frame.

### Project Or Shareable HTML

Under **Export > v_ase Project**, use **Save .vase** for the smallest complete
project. It contains every loaded frame, coordinates, cells, PBC, labels,
constraints, safe calculator results, camera, appearance, bonds, lighting,
analysis, and export settings. It is self-contained and never references the
original input file.

Use **HTML Project** or **HTML View** when the result should open directly in a
browser. The save dialog shows the exact shared Preview Area crop and lets you
choose grid, axes, and unit-cell visibility. Every generated HTML:

- opens offline without v_ase, Python, a server, or a CDN;
- restores the saved camera, viewport styling, bonds, constraint overlays,
  displacement vectors, supercell, visual translation, and trajectory;
- allows orbit, pan, zoom, frame stepping, and movie playback;
- exposes no atom, structure, appearance, or project editing controls.

**HTML View** leaves **Embed editable .vase project** off by default and creates
the smaller view-only handoff. **HTML Project** enables it by default and stores
the complete `.vase` inside the same HTML. Embedded documents expose
**Download .vase**, and either command restores the full editable project:

```bash
v_ase gui project.vase
v_ase gui project.html
```

With project embedding disabled, the file is smaller and remains a portable
view-only document. It cannot be restored as an editable v_ase project. v_ase
reports this explicitly if that lightweight HTML is opened as input.

The exported frame is stored as an automatically optimized high-resolution
poster as well as an interactive 3D scene. The initial HTML surface contains
only that exact Preview Area crop: no v_ase logo, header, decorative border, or
page margin is included. This lets macOS Finder/Quick Look show the structure
without executing WebGL. In a browser, the first prepared WebGL frame replaces
the poster with a short cross-fade as soon as the first live frame is ready,
before camera input begins. Both surfaces occupy the same rectangle, so the
structure does not jump. View-only controls appear only after pointer or
keyboard activity.

HTML width and height inherit the image/video Preview Area. They define the
saved camera aspect and crop, not a fixed live WebGL resolution. The
interactive renderer automatically follows the browser size and display pixel
density.

HTML is larger than `.vase` because it contains the browser renderer and
immediately readable scene data. Embedding adds a Base64 copy of `.vase` on
top of that. Keep `.vase` as the compact editable source of truth.

Opening an ordinary structure in an existing tab keeps the current visual
settings; opening `.vase` or project-embedded HTML restores the saved project.

Rhino export requires the optional dependency:

```bash
python -m pip install "v_ase-gui[rhino]"
```

OBJ export has no optional Python dependency.

## Agent Setup

The AI agent runs separately from v_ase. Give it the complete
[v_ase Skill directory](https://github.com/lgyEthan/v_ase/tree/main/v_ase/skills/visualizing-atomic-structures-with-v-ase),
then describe the result you want. The agent starts the machine-readable v_ase
session, gives you the live GUI URL, and performs verified changes in that same
document.

The Skill is vendor-neutral and can be used by Codex, Claude Code, ChatGPT
desktop agents, Gemini-based agents, agentic IDEs, or another agent that can
run local commands.

```text
your natural-language request
  -> external AI agent + v_ase Skill
  -> v_ase structured CLI
  <-> the same live v_ase GUI you can watch and edit
```

`--cli` is not an embedded AI model. It is the structured connection the
external agent launches for itself. It exposes atomistic state and safe
operations, and reports committed GUI changes back to the agent. Revision
checks prevent an older agent command from silently replacing a newer human
edit.

### What To Give The AI

Prefer the complete skill directory. If the client accepts only individual
files, provide the following:

| Always provide | Add when the task needs it |
| --- | --- |
| [`SKILL.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md) | [`semantic-api.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/semantic-api.md) for live state, edits, camera, render, or export |
| [`agent-setup.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/agent-setup.md) | [`collaboration.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/collaboration.md) while a human and agent share the live GUI |
|  | [`workflows-and-examples.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/workflows-and-examples.md) for multi-step scientific workflows |
|  | [`cli-and-environments.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/cli-and-environments.md) for installation, server, WSL, or process handling |
|  | [`safety-and-errors.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/safety-and-errors.md) before destructive edits, relaxation, or file output |
|  | [`evaluation.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/evaluation.md) when changing or releasing v_ase itself |

For an AI client without a native skill loader, attach the files above and use:

```text
Read SKILL.md and agent-setup.md. Use v_ase's structured CLI to inspect and
edit the structure, give me the live GUI URL so I can watch or refine it, honor
newer GUI changes before continuing, and verify both scientific state and the
final rendered output.
```

The compatibility document
[`skills_v_ase.md`](v_ase/skills_v_ase.md) points existing integrations to the
same canonical skill and reference set.

### Install The Skill

Clients with skill-folder support should install the complete directory:

```bash
# Codex
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase "$CODEX_HOME/skills/"

# Claude Code, from a project root
mkdir -p .claude/skills
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase .claude/skills/
```

For another AI, use its documented local skill directory if it supports the
same `SKILL.md` convention. Otherwise attach the files listed above or make
them readable in the project and include the bootstrap instruction.

Detailed CLI fields and command examples live in the Skill references rather
than this user guide:

- [Agent setup](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/agent-setup.md)
- [Live collaboration](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/collaboration.md)
- [Semantic API](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/semantic-api.md)

## Documents And File Opening

The top-bar **Open** button starts with the operating system file picker. A
selected file can:

1. replace the active document;
2. append structures to its current trajectory;
3. open in a new independent v_ase tab.

If the active document is empty, the selected file opens there immediately;
the destination chooser is shown only when a document already contains a
structure or trajectory.

The **+** beside the document tabs creates an empty independent document. Each
tab owns its structure, trajectory, camera, selection, history, settings,
calculator, and `.vase` output.

Adding `.vase` to an existing trajectory imports only its structures and keeps
the current tab's visual state. Replacing a tab or opening a new one restores
the complete `.vase` project.

## Python

```python
from ase.build import molecule
from v_ase.visualize import view

atoms = molecule("H2O")
view(atoms)  # View mode
```

Inside Jupyter Notebook or JupyterLab, the same call automatically displays a
view-only interactive model directly below the cell:

```python
view(atoms)
```

The notebook output supports orbit, pan, zoom, and trajectory playback. After
importing `view`, use the `%v_ase` line magic to switch the default at any time:

```python
%v_ase inline
view(atoms)  # interactive output below this cell

%v_ase browser
editor = view(atoms, block=False)  # full interface in an external browser

%v_ase auto  # restore automatic Jupyter detection
```

`%load_ext v_ase.notebook` registers the same magic explicitly when needed.
Passing `notebook="inline"` / `True` or `notebook="browser"` / `False` to one
`view()` call overrides the current magic setting.

When retaining an inline handle, display it explicitly:

```python
from IPython.display import display

editor = view(atoms)
display(editor)
```

Return an edited ASE object:

```python
edited = view(atoms, viz_only=False)
print(edited.positions)
```

`view()` accepts one ASE `Atoms`, a sequence of frames, or a supported file
path. `view_edit()` remains a compatibility alias for Edit mode.

## File Formats

Common structure inputs include POSCAR/CONTCAR, VASP files, XDATCAR,
`vasprun.xml`, XYZ/extxyz, ASE `.traj`, LAMMPS dump/data, CIF, and `.vase`.
Volumetric inputs include VASP CHGCAR/CHG/PARCHG/LOCPOT/ELFCAR and Gaussian
Cube/XSF grids. VASP scalar names may carry `.`, `_`, or `-` suffixes for
separate calculations. ASE readers cover additional structure formats.

Use `--format` when an ambiguous filename does not identify the reader:

```bash
v_ase gui ABCD --format POSCAR
v_ase gui ABCD --format vasprun.xml
v_ase gui ABCD --format lammpstrj
v_ase gui ABCD --format data
v_ase gui ABCD --format CHGCAR
v_ase gui ABCD --format qe-cube
v_ase gui ABCD --format qe-xsf
```

Use `--index :` for every frame, `--index -1` for the last frame, or an integer
for one frame.

Repeated POSCAR/CONTCAR species blocks remain separate visual labels. For
example, `O Cu O` with counts `1 14 5` becomes `O1`, `Cu`, and `O2` while all
oxygen atoms remain ASE element `O`. Custom labels retain their complete text
when they are renamed or used for pair analysis.

## Controls

| Input | Action |
| --- | --- |
| Left click / Shift + click | Select / extend selection |
| Left drag | Box select |
| Middle drag | Orbit without inertia |
| Shift + middle drag | Pan |
| Wheel | Zoom |
| `G` / `R` | Move / rotate selected atoms |
| `X`, `Y`, `Z` during `G`/`R` | Lock transform axis |
| `X`, `Y`, `Z` otherwise | Align camera to an axis |
| Number keys | Exact move distance or rotation angle |
| `Enter` or left click | Confirm transform |
| `Esc` or right click | Cancel transform |
| `Ctrl+C`, `Ctrl+V` | Copy and paste atoms |
| `Ctrl+Z`, `Ctrl+Shift+Z` | Undo and redo structure and visualization-setting changes; camera navigation is excluded |
| `Delete` / `Backspace` | Delete selected atoms |
| `Space` | Play or pause the active timeline |
| Left / Right Arrow | Previous / next frame in the active timeline |
| `Tab` or `Esc` | Open a collapsed control panel |
| `Esc` with the panel open | Close it and return focus to the viewport |

The **?** button contains the complete shortcut table.

## Remote Servers

Install v_ase on both the local computer and remote host, then run one command
locally:

```bash
v_ase gui USER@SERVER:/absolute/path/to/STRUCTURE
```

An SSH config alias works:

```bash
v_ase gui physics:/absolute/path/to/trajectory.extxyz
```

v_ase selects private ports automatically, starts the backend beside the
remote file, creates the SSH tunnel, and opens the local browser. The source
file and full trajectory cache remain on the server; only the current frame
data required for local Three.js rendering crosses the tunnel. Use `ProxyJump`
in `~/.ssh/config` when a login node is required.

## License

v_ase releases from `0.1.11` onward are licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE)
(`AGPL-3.0-or-later`). You may use,
modify, and redistribute the software under that license; distributions and
modified network services must satisfy its source-availability and
same-license requirements. Copyright (C) 2026 v_ase contributors.

The bundled Three.js module retains its own MIT license in
[`v_ase/static/vendor/THREE_LICENSE`](v_ase/static/vendor/THREE_LICENSE).

## Troubleshooting

<details>
<summary><code>v_ase</code> command is not found</summary>

Install and run with the same Python environment:

```bash
python -m pip install --upgrade v_ase-gui
python -m v_ase.cli --version
```

If the module command works but the console command does not, reactivate the
environment or add its Python scripts directory to `PATH`.

</details>

<details>
<summary>The browser does not open, or WSL prints <code>gio: ... Operation not supported</code></summary>

The terminal also prints the complete local URL. Ctrl+click it or copy the text
beginning with `http://` into Chrome, Edge, Firefox, or another browser. Keep
the terminal process running.

Example with sensitive session identifiers masked:

```text
(base) giyeok@DESKTOP-XXXX:~$ v_ase gui
gio: http://127.0.0.1:58039/workspace?workspace_id=xxxx&session_id=xxxx: Operation not supported
```

For better WSL performance, keep trajectories under the Linux filesystem
rather than `/mnt/c/...`.

</details>

<details>
<summary>A file is detected with the wrong format</summary>

Force the reader:

```bash
v_ase gui FILE --format POSCAR
v_ase gui FILE --format vasprun.xml
v_ase gui FILE --format lammpstrj
v_ase gui FILE --format data
```

</details>

<details>
<summary>Startup fails with <code>cannot import name 'read_vasp_configuration'</code></summary>

This was an ASE 3.23/3.24 compatibility defect in v_ase 0.1.1 through 0.1.5.
Upgrade v_ase in the same environment that provides the failing executable:

```bash
python -m pip install --upgrade "v_ase-gui>=0.1.6"
v_ase --version
```

v_ase 0.1.6 and later support the declared `ase>=3.23` range without making
ordinary structure loading depend on a newer VASP-internal helper.

</details>

<details>
<summary>Replicated supercell atoms cannot be selected</summary>

In **Edit**, displayed replicas are noneditable previews. Use
**Set Supercell as Cell** to create real ASE atoms and an editable larger cell.
In **View**, displayed replicas are selectable and participate in center,
distance, and other measurements.

</details>

<details>
<summary>Video export is unavailable or slow</summary>

Video export requires at least two frames and browser `MediaRecorder` support.
MOV/AVI conversion uses the bundled `imageio-ffmpeg`. Interpolation renders
additional frames and requires stable atom count, element, label, and ordering
between adjacent source frames. The selected FPS controls playback time:
72 frames at 30 FPS produce 2.40 seconds. The progress indicator reaches 100%
only after encoding and the destination write both finish.

</details>

<details>
<summary>Chrome says this site can view changes made to the saved file</summary>

This is a Chrome security notice for the File System Access API. v_ase opens
the system save picker before a costly image, video, Blender, or 3D scene export so
canceling does not waste time. It receives write access only to the file you
choose. Chrome does not allow a page to suppress this notice; using an ordinary
browser download would remove advance destination selection.

</details>

<details>
<summary>A large trajectory opens or plays slowly</summary>

- Keep the default View mode unless editing is required.
- Use `--stream-frames` when frame data should be loaded on demand.
- Keep browser hardware acceleration enabled.
- Close unused v_ase tabs; inactive tabs pause rendering but retain document
  state in memory.
- In WSL, keep data in the Linux filesystem.

</details>

<details>
<summary>RDF reports that fully periodic 3D boundaries are required</summary>

v_ase does not label a finite or partial-PBC histogram as a bulk RDF. Define a
valid 3D periodic cell for bulk `g(r)`, or use a method with the boundary
correction appropriate to the finite, slab, or wire geometry.

</details>

<details>
<summary>Volumetric datasets cannot be combined</summary>

Density differences require identical grid dimensions, cell vectors, origin,
PBC, endpoint convention, and units. Generate all component grids on the same
FFT mesh, or resample them deliberately before opening them in v_ase.

</details>

<details>
<summary>Installation fails while pip checks an unrelated package version</summary>

A package version reported as `None` usually belongs to a different incomplete
or manually installed distribution in that environment. Run
`python -m pip check`, repair that distribution, or use a clean environment:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install v_ase-gui
```

</details>

Run `v_ase --help` or `v_ase gui --help` for all CLI options. Report
reproducible problems at
[GitHub Issues](https://github.com/lgyEthan/v_ase/issues).
