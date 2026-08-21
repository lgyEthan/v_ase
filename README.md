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
structure operations, then export publication images, videos, reusable 3D
scenes, or a self-contained HTML project.

![Phosphorene nanoribbon manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

The animation builds a phosphorene nanoribbon twist one ridge at a time. Each
amber box selects the remaining ridges, the Transform controls apply an exact
X-axis rotation, and the sequence reaches a 13.85 degree twist before the
completed structure is inspected from above and below.

## Highlights

| Why use v_ase? | What it provides |
| --- | --- |
| **ASE-native workflow** | Open ASE-supported structures and trajectories from the terminal or Python, retain scientific metadata, and return to the same environment after inspection or editing. |
| **Direct 3D structure editing** | Start from a file or an empty document, define a cell, insert atoms or molecules, and use `G`, `R`, and physical `S` transforms in the same local browser. [Explore editing](#edit-structures). |
| **Periodic interfaces and analysis** | Build supercells, search commensurate 2D cells, optimize a rigid translation in any compatible periodic `(hkl)` plane, measure ordered geometry, plot periodic RDFs or finite pair distributions, and inspect volumetric fields. [Explore interfaces](#periodic-cells-and-interfaces) and [analysis](#analyze-structures-and-fields). |
| **External AI collaboration** | Give a scientific request to an external AI Agent; the bundled Skill lets it operate exact revisioned state while you watch and refine the same GUI. [See the collaboration workflow](#work-with-an-ai-agent). |
| **Portable HTML projects** | Save the structure, trajectory, camera, labels, bonds, lighting, analysis state, and visualization settings in one HTML file. Preview it with macOS Quick Look, open the offline 3D view in a browser, or restore the embedded project in v_ase. [See HTML projects](#project-or-shareable-html). |
| **Publication and reusable output** | Switch the whole scene between 3D materials and a flat 2D diagram, lock a persistent Render Area, then prepare images, videos, HTML, Blender scenes, and compact `.vase` projects. [See styling](#style-atoms-bonds-and-rendering) and [export options](#export-and-save). |

![A self-contained v_ase HTML project in macOS Quick Look and an offline browser](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_html_quicklook.gif)

An **HTML Project** is both a shareable offline 3D document and a complete
save file. macOS Quick Look reads its optimized poster without installing
v_ase, while opening the same file in a browser enables orbit, pan, zoom, and
trajectory playback. Loading it with `v_ase gui FILE.html` restores the
embedded structure or trajectory and all saved visualization settings.

![Human and external AI agent working in one live v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.png)

Human instructions remain natural language, while the Agent uses the Skill and structured CLI/API for exact atom identities,
camera settings, validation, and export; the result appears in the same live GUI,
refine it directly when needed, and v_ase returns that edit to the Agent as a
new revision. v_ase does not embed an LLM.

## Installation And Launch

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

`v_ase gui` without a filename opens an empty **Edit** document so a cell and
atoms can be built immediately. Opening a filename starts in **View**, which is
optimized for large-data inspection, trajectories, measurement, appearance,
bonds, supercells, and export. The **Open File** dialog lets you choose View or
Edit before each structure is loaded. Use the top-bar switch or start a file
directly in Edit when atomic coordinates must change:

```bash
v_ase gui structure.vasp --interactive
```

No Node.js installation or hosted account is required. Closing the v_ase
browser document releases the blocking terminal process.
The complete local viewer URL is always printed before v_ase waits, even when
automatic browser launch reports success. If no tab appears, Ctrl+click that
URL or copy it into any local browser.

## Find A Workflow

| Goal | Action |
| --- | --- |
| Inspect a structure | Middle-drag to orbit, wheel to zoom, left-click to select |
| Build from an empty document | Run `v_ase gui`, define **Structure > Cell & Replication** if needed, then open **+ Add atoms** |
| Build a periodic crystal with ASE | In **Edit**, open **+ Add atoms > Build with ASE**, choose a compatible formula/prototype/cell shape, validate, then build |
| Edit coordinates | Enter **Edit**, select atoms, press `Esc` to focus the viewport, then use `G`, `R`, or physical `S` |
| Insert atoms or molecules | In **Edit**, open **+ Add atoms**, choose **Single** or **Batch**, then place atoms or ASE molecules |
| Measure geometry | Select 2, 3, or 4 atoms in the required order |
| Play a trajectory | Use the bottom timeline or `Space`; FPS and Skip update live |
| Plot pair statistics | Use **Analysis > Radial Distribution Function** for fully periodic bulk cells or **Pair-distribution function** for finite structures |
| View a charge or potential grid | Open CHGCAR/LOCPOT/PARCHG/Cube/XSF, then use **Analysis > Volumetric Data** |
| Style a figure | Use **Structure > Appearance/Bonding** and **View** |
| Draw a flat structural diagram | Choose **View > Viewport rendering > 2D flat** |
| Lock an export composition | Enable **Export > Render Area**, disable **Follow viewport**, and use **Set from Current View** |
| Match the app to the computer theme | Keep **View > Interface theme** on **System**, or choose Light/Dark explicitly |
| Reuse the current visual style automatically | Use **Export > Visual Settings > Set Current as Default** |
| Repeat or wrap a cell | Use **Structure > Cell & Replication** |
| Save the whole session | Use **Export > v_ase Project** and choose compact `.vase` or browser-ready HTML |
| Move a visual preset to another computer | Use **Export Preset**, then **Import Preset** |
| Share an offline 3D view | Use **Export > Rendered media > HTML View**; the lightweight view-only file is the default |
| Hand the scene to an AI | Provide the bundled agent skill; the agent starts the CLI/API session itself |

> **Viewport tip:** after selecting atoms, press `Esc` to close the control
> panel before using `G`, `R`, or `S`. The selection is preserved and keyboard focus
> returns to the 3D viewport.

**Structure**, **Analysis**, and **Export** each expose a **Section** menu in
the panel header. Selecting an item opens it and scrolls directly to that
section; scrolling the panel updates the menu to show the section currently in
view. The interface uses the same compact, readable type hierarchy and control
dimensions across builders, panels, dialogs, and exported HTML views. On a
narrow window the top action strip scrolls horizontally instead of placing
camera, render, reset, and help controls on top of one another.

The guide is organized by task:

- [Edit structures](#edit-structures): select, move, insert, and rotate atoms.
- [Match periodic cells and interfaces](#periodic-cells-and-interfaces):
  replication, common cells, and rigid planar translation.
- [Analyze structures and fields](#analyze-structures-and-fields): ordered
  geometry, trajectories, forces, RDF, and volumetric data.
- [Use constraints and relaxation](#constraints-and-relaxation): ASE-enforced
  motion and optimization trajectories.
- [Style and render](#style-atoms-bonds-and-rendering): appearance, bonds,
  lighting, media, projects, and reusable visual settings.
- [Work with an AI Agent](#work-with-an-ai-agent): share one revisioned GUI
  document through the bundled semantic CLI Skill.

## Edit Structures

Use **Edit** when atom coordinates must change. Selection, measurement,
appearance, bonds, replication, wrapping, visual translation, and export
remain available in the default **View** mode.

### Select

- Left-click selects one atom; `Shift` + click extends or removes selection.
- Left-drag draws a visible selection box.
- Appearance rows select complete label groups without merging distinct labels.
- Ordered single-atom selections are retained for geometry measurement.
- In View, repeated supercell atoms are independent visual references for
  measurement, appearance, and hiding. In Edit, clicking or box-selecting a
  replica selects its unique base atom in the editable unit cell. The primary
  atom keeps the normal full selection halo, while every displayed periodic
  equivalent receives a smaller, lower-opacity yellow ring. Atom opacity and
  appearance remain unchanged, so the editable primary is clear without
  disguising the surrounding periodic structure.

### Move

Press `G` after selecting atoms. Lock the move with `X`, `Y`, or `Z`, type an
exact displacement in angstrom, then confirm with left-click or `Enter`.
Configured ASE constraints remain authoritative when **Apply constraints** is
enabled.

`Ctrl+C` and `Ctrl+V` paste an exact-coordinate duplicate. The copy keeps its
label, element, every per-atom ASE array, compatible atom constraint,
single-point per-atom result, and per-atom material. Whole-structure energy is
not copied because it is no longer valid after atom count changes.

### Build From Scratch

![Building an amorphous structure from an empty v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_scratch_amorphous.gif)

Run `v_ase gui` to start in an empty Edit document. A complete structure can be
built without loading an input file:

1. Enter the Cartesian `3 x 3` matrix under **Structure > Cell & Replication**,
   choose the periodic axes, and click **Set Unit Cell**. This defines the ASE
   cell without moving existing atoms.
2. Open **+ Add atoms > Batch**, choose atom types, labels, counts, and an
   initial distribution, then place the batch in the cell or in explicit Allow
   regions.
3. Open **Structure > Relaxation** from the placement card, choose the shared
   calculator, cutoff, device, `fmax`, and step settings, then start placement
   relaxation. The fallback calculator also works for finite structures with
   no unit cell, provided a finite Allow region defines the insertion domain.
4. Review the placement timeline and click **Finish** when the staged structure
   is ready.

The center Open prompt disappears as soon as a cell, region, or atom edit makes
the scratch document meaningful.

#### Build A Bulk Crystal With ASE

Open **+ Add atoms > Build with ASE** in Edit mode to generate a periodic crystal
through the installed `ase.build.bulk` implementation. The controls are
conditional rather than a static list:

- **Automatic from ASE** lists reference elements compatible with the selected
  cell shape. For example, `Cu` with **Cubic** produces the same structure as
  `bulk("Cu", cubic=True)`; an hcp reference element is not offered as a cubic
  reference.
- Selecting an explicit prototype enables only its relevant arguments and
  compatible native, orthorhombic, or cubic cell shapes.
- A compound without ASE reference lattice data reports the exact missing
  values. For example, `CuO` requires a prototype such as **Rocksalt** and a
  lattice parameter `a` before it can be built.
- **Validate** runs the real installed ASE builder and reports atom count, cell
  lengths, and angles before the document changes. Lengths are in angstrom and
  fractional basis coordinates use an `N x 3` JSON array.

Building creates one periodic trajectory frame. It replaces the current
structure only after confirmation, retains the current visual settings, and is
fully reversible with Undo.

### Add Atoms

![Oxygen distributed through a bulk-like Cu(111) insertion region](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_atoms_allowed.gif)

Eighteen `O_subsurface` atoms start in a finite teal **Allow region** spanning
the three bulk-like interior layers of a five-layer Cu(111) slab. The side view
shows the staged atoms begin at reproducible random positions, then separate
from nearby Cu and one another under explicit Cu-O and O-O repulsive cutoffs.
Every original `Cu_surface` coordinate remains fixed throughout placement.

Open **+ Add atoms** in **Edit** mode. The launcher stays at the upper-left of
the viewport below the app header, leaving bottom-left notifications visible:

- **Single** places one atom at an exact position or the current view center.
- **Batch > Atoms** accepts multiple Type, Label, and Count rows. **Batch >
  Molecules** accepts every molecule available through the installed ASE G2
  catalog and supports several molecule species in one placement.
- Typing a valid element symbol into an atom Label also selects that Type. For
  example, entering `O` chooses oxygen immediately; the Type control remains
  available when a distinct visual label or an explicit override is needed.
- **Random** gives each physical volume element equal probability in an
  orthogonal or triclinic cell. A seed makes the result reproducible.
  Periodic sampling uses one half-open primary periodic cell, so a boundary
  position is never counted again through a neighboring image.
- **Homogeneous** spreads the requested centers with a low-discrepancy
  sequence and maximin refinement for batches up to 1,024 entities. Larger
  batches keep the bounded-memory low-discrepancy sequence directly.
  **Cartesian distance / Å** is the default and maximizes physical
  nearest-neighbor spacing. **Fractional spacing** instead balances normalized
  lattice coordinates. Periodic-aware spacing uses the exact minimum image.
- **Regular grid** places centers on one global Cartesian lattice. Enter an
  exact grid spacing in angstrom or leave it on Auto. Sites are clipped to the
  complete Allow-minus-Reject domain, and periodic boundary duplicates are
  removed with a half-open primary-cell convention. If the requested spacing
  cannot provide enough sites, v_ase reports that condition instead of silently
  changing a user-entered value.
- With a finite cell, an empty region list uses the complete primary cell.
  Multiple Allow regions are combined, then every Reject region is subtracted.
  Overlap is counted once. Without a finite cell, at least one Allow region is
  required because Reject regions alone do not define a bounded volume.
- Each region uses Cartesian `xmin`/`xmax`, `ymin`/`ymax`, and `zmin`/`zmax`.
  The accessible volume is calculated from exact box/cell intersections,
  including triclinic cells; it is not estimated from voxels.
- Click or Shift-click region rows, or click their viewport **edges**. Filled
  faces remain non-pickable, so a smaller nested box can always be reached.
  Press `G` to move one region or the complete selected group while every bound
  updates live. Press `S`, optionally followed by `X`, `Y`, or `Z`, to scale the
  selected boxes about their shared center. `R` is unavailable because rotated
  Cartesian min/max boxes would no longer represent the displayed values.
- With region MIC enabled, the intact source cuboid remains visible even when
  it crosses a cell face. Its clipped periodic fragment also appears at the
  symmetry-equivalent opposite face. Shared fragment edges are drawn once, and
  the same lattice-vector mapping controls sampling in orthogonal or triclinic
  cells.
- Regions describe initial placement. **Enforce Allow and Reject regions
  during relaxation** is off by default, so repulsive placement can find
  nearby free volume. Turn it on to keep every staged atom inside the Allow
  union and outside every Reject region throughout placement relaxation.
  Rigid molecules are constrained by their ASE template origin, preserving
  their internal geometry while avoiding per-atom boundary work. **Finish** commits the staged
  coordinates; it does not project an unrelaxed batch into the domain by
  itself.
- **Temporarily fix existing atoms** keeps the loaded structure stationary
  while only inserted content follows pairwise repulsion. It is enabled by
  default. This staging overlay does not change atom radii, label colors, or
  any saved appearance setting; it applies only the fixed-material surface so
  the stationary host remains identifiable.
- **Keep inserted atoms selected** is enabled by default. Use `G` or `R` to
  move or rotate only the staged content before repulsive placement; **Select
  added** restores that selection at any time.
- The placement card opens **Structure > Relaxation**. Its calculator,
  independent label-pair contact distances, strength, device, CPU threads, `fmax`, and
  step count are the same controls used for ordinary structure relaxation.
  Starting relaxation while Add Atoms is active routes that shared setup
  through one `AdditionRepulsionCalculator` attached to the complete staged
  structure. CPU and CUDA use the same pair model; unavailable CUDA requests
  fall back to CPU. Minimum-image vectors are evaluated by the calculator for
  the complete structure rather than by moving atom pairs independently.

**Place atoms** and **Place molecules** remain available after each completed
placement relaxation. Edit the species rows or Allow/Reject regions, place
another batch, and relax again without pressing **Finish**. Every batch is
accumulated in one reversible staging session. The structure that existed when
the session first opened remains the immutable host baseline; all content
inserted by any later placement belongs to the staged mobile set. **Select
added** selects that complete accumulated set. **Finish** commits all batches,
while **Cancel** restores the exact pre-session structure and discards them.

The insertion regions exist only while Add Atoms is active. **Finish** commits the
inserted content but reconstructs every pre-existing coordinate, array, label,
calculator, and constraint from the original structure. **Cancel** restores
that original structure completely. For trajectories, open the target frame
in a new tab before starting a batch.

Placement relaxation creates an **Add Atoms placement** timeline containing
every FIRE optimizer step. It can be scrubbed or played while the mode remains
active. Placing another batch changes the staged topology, so the temporary
timeline starts again from that expanded structure; the next relaxation fills
it with the new optimizer steps. Finishing or cancelling the mode closes the
panel and removes the temporary regions and timeline.

The animations use the included
[Cu(111)/O placement example](examples/readme_scene_assets/cu111_oxygen_add_atoms.traj).

#### Add Molecules

![Rigid water molecules placed around edge- and basal-hydroxylated graphene-oxide layers](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_molecules.gif)

The example uses two finite-width graphene-oxide ribbons in a fully periodic
cell with `6 Å` layer spacing. Every ribbon edge is OH-passivated, while basal
OH groups occupy reproducibly randomized sites and non-collinear orientations
instead of one crystallographic row. The x-expanded cell leaves distinct left
and right solvent chambers. Two `2 Å`-thick magenta **Reject regions** cover
only the GO planes; their complement is the solvent domain. Exact box/cell
Boolean geometry gives `1926.683 Å³` of accessible volume. A target density of
`1.00 g/cm³` resolves to 64 rigid H2O molecules at `0.994 g/cm³`.

Choose a molecule and label from **Batch > Molecules**. **Count** places the
requested integer composition. **Density** treats each Count value as a
composition ratio, reduces all values to their primitive integer ratio,
calculates the exact accessible volume, chooses the nearest complete
composition batch, and displays both target and realizable density in `g/cm³`
before placement. Molecular
coordinates are placed and rotated about ASE's native coordinate origin;
**Randomize molecular orientation** samples unbiased three-dimensional
rotations. The default **Preserve molecular geometry** mode evaluates
atom-pair repulsion against the host and other molecules, excludes internal
repulsion, and projects every optimizer step onto each molecule's rigid
translation and rotation. Turn it off for ordinary atomwise relaxation.

Open the included
[periodic graphene-oxide structure](examples/readme_scene_assets/layered_water_channel.traj)
to reproduce the workflow. The source region outlines remain visible while the
waters are inserted and repelled. Every graphene-oxide atom remains exact,
while the 64 randomly oriented waters move as rigid bodies with all O-H
distances and H-O-H angles preserved.

### Rotate Selected Atoms

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

### Scale Selected Atom Spacing

Press `S` after selecting two or more atoms. Type a positive scale factor, or
press `X`, `Y`, or `Z` first to scale only along that **global Cartesian** axis.
Scaling is performed about the configured rotation pivot and changes physical
atom coordinates: `S`, `X`, `1.5`, `Enter` multiplies every selected atom's
X displacement from the pivot by `1.5`. It does not change atom radii, bond
thickness, material settings, or the unit cell. ASE constraints remain
authoritative when **Apply constraints** is enabled.

## Periodic Cells And Interfaces

Display replication, integer cell transforms, common-cell matching, and
periodic rigid translation are related but distinct operations. Display replication
changes only what is visible. **Set Supercell as Cell** materializes a
replicated structure. **Cell Transform** applies an integer matrix to the cell
and every compatible trajectory frame.

In **View**, displayed replicas use the same color, material, and opacity as
the primary atoms and remain selectable for measurements. In **Edit**, the
editable primary cell is centered for odd repetitions such as `3 x 3 x 1`, its
cell boundary receives a stronger contrast halo, and every atom remains fully
opaque. Selecting any replica maps to one unique editable base atom: the base
gets the normal full halo and all equivalent replicas receive smaller,
lower-opacity rings. This exposes the periodic mapping without making a
displayed copy look independently editable.

### Commensurate Atoms: Match Periodic 2D Cells

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
and guest cells are orange. They remain the dominant guides while the guest
rotates. Their displayed grid dimensions are chosen once from the configured
bounded search and remain fixed while the angle and candidate change. A green
common-cell boundary appears only when the current angle resolves
an actual common-cell candidate; it is not shown as a misleading proposal at
the initial unmatched angle. The candidate-dependent green boundary may change
size, but it never resizes either black/orange parent superlattice. The current
camera is preserved.
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
area ratio is `16`. Enabling the workspace, selecting a layer, or loading a
guest preserves the current angle instead of jumping to a candidate. The graph
and candidate list expose bounded matches; moving the guest angle resolves the
valid candidate at that angle. No common-cell boundary is shown when every
candidate exceeds the chosen area or strain bound, or while the current angle
remains unmatched.

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

![Graphene and MoS2 host/guest common-cell search with a live angle plane](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate_host_guest.gif)

The visual example deliberately uses two visibly different parent lattices:
graphene with `a = 2.46 Å` and MoS2 with `a = 3.18 Å`.

```bash
v_ase gui examples/commensurate_host_guest/graphene_host.extxyz
```

Enable **Structure > Transform > Commensurate atoms**, then load
[`mos2_guest.extxyz`](examples/commensurate_host_guest/mos2_guest.extxyz)
with **Load or Replace Guest Structure**. Keep guest strain `2.5%`, interlayer
gap `3 Å`, and maximum area ratio `16`. At `|19.10660535|°`, the first visible
bounded match is a rectangular graphene `(√7 × √21) R±19.11°` host
cell (area ratio 14) against a MoS2 `2 × 2` guest cell (area ratio 4), with
`2.336%` maximum principal strain. The black host and orange guest
parent grids remain anchored and keep constant extent throughout the sweep;
only the orange guest orientation changes. A green common-cell boundary
appears only when the current angle satisfies the active bounds. Atom and bond
visibility is an independent switch and never changes merely because a
candidate appears.

The [example guide](examples/commensurate_host_guest/README.md) also keeps the
graphene/Cu(111) fixture and [`expected.json`](examples/commensurate_host_guest/expected.json)
as the stricter numerical regression for maximum-principal and paper-style
mean strain.

The equations, numerical references, basis-invariance check, and measured
search bounds are collected in
[Commensurate Cell Scientific Validation](docs/commensurate_validation.md).

Normal `R` rotates selected atoms. **Cell Transform** is a separate periodic
operation that applies an integer matrix to the cell and every trajectory
frame. Display replication is separate again: it only repeats what is shown.
The common-cell equations, limits, and assumptions are documented in
[unit_cell_aware_rotate.md](docs/unit_cell_aware_rotate.md).

### Planar Translation

Select the layer, adsorbate, or other component that should move and open
**Analysis > Planar Translation**. Choose a nonzero Miller plane `(h k l)`.
v_ase constructs two primitive integer lattice translations lying exactly in
that plane, so the workflow remains valid for skew and triclinic cells rather
than assuming Cartesian XY. The requested plane must contain two translations
allowed by the structure's PBC.

**Activate Mode** immediately shows the physical periodic translation cell.
Press `G` to move all selected atoms by one shared in-plane vector; the unit
cell, unselected atoms, and every internal vector within the selected component
remain fixed. The unit cell stays visible throughout the mode. The map is not a
prerequisite: **Optimize Translation** can record calculator trials directly on
the initially blank plane.

Use **Calculate Map** only when a sampled geometric comparison is useful. v_ase
scans one primitive periodic `(hkl)` translation cell on the requested grid
while a staged progress display reports the active step. Starting either mode
without selected moving atoms, or after selecting the complete structure,
produces a direct error instead of an ambiguous calculation.

The default **Short-contact score** is a dimensionless, covalent-radius-scaled
geometry proxy. **Bond-strain RMS** instead uses enabled interfacial pairwise
bond cutoffs and reports normalized bond-length mismatch for those pairs. Both
scores are lower-is-better geometric screening metrics, not energies. Validate
the proposed registry with an appropriate electronic-structure or force-field
calculation before drawing physical conclusions.

The Plotly map uses physical Angstrom coordinates, draws the exact skew
translation-cell boundary and basis, and marks the best sampled point and the
current translation. While the mode is active, `G` stays in the chosen plane
and the marker follows the shared vector continuously. The graph's save icon
exports both plane-lattice coordinates and the corresponding Cartesian
translation, metric values, selected indices, `(hkl)`, and basis vectors as
CSV. RDF, commensurate, and planar-translation plots all expose the same
adjacent save icon.

![Periodic planar translation scan with current and optimum translations](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_registry_map.png)

The shown graphene/h-BN example uses **Bond-strain RMS** with explicit C-B and
C-N interfacial cutoffs, so the heatmap remains a geometric comparison rather
than an implied energy surface.

**Optimize Translation** minimizes exactly two shared coordinates in the chosen
periodic plane. It uses the attached calculator, or the repulsive calculator
when none is attached, and reports the norm of the selected component's net
force projected into that plane in `eV/Å`. No individual atom is relaxed: the
cell, all unselected coordinates, and every selected pairwise internal vector
remain unchanged. For `(0 0 1)` this also preserves every selected z
coordinate; for a general plane the invariant is the complete rigid component.

![Rigid planar translation trials without a precomputed colorscale map](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_registry_relax.gif)

**Activate Mode** enters the reversible mode, **Optimize Translation** records each
accepted optimizer step on its own timeline, and **Apply & Exit** commits one
undoable translation. **Cancel** restores the exact pre-mode structure. The
mode timeline disappears when either exit action finishes. Calculating a map
later overlays its geometry score without changing any trial or coordinate.

## Analyze Structures And Fields

### Ordered Geometry

![Ordered distance angle and torsion measurement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_measurement.gif)

The numbered `a1` to `a4` markers record selection order and are deliberately
different from atom indices.

| Ordered selection | Reported result |
| --- | --- |
| 1 atom | Label, element, displayed Cartesian/fractional position, and all available per-atom properties |
| 2 atoms | Direct distance and minimum-image distance |
| 3 atoms | Angle `a1-a2-a3`, centered on `a2` |
| 4 atoms | Signed torsion `a1-a2-a3-a4` |
| 5 or more | Total count and per-label counts |

The connector, angle arc, torsion axis, and compact value badge stay attached
to the selected atoms. Hover information is independent, so moving the pointer
does not replace a saved measurement.

For one selected atom, **Inspect > Selection > Measure** lists ASE attributes
such as atomic number, mass, tag, initial charge, and initial magnetic moment,
then every stored per-atom `Atoms.arrays` value and per-atom calculator result.
Vector and tensor shapes are retained. The data is fetched only for that atom
and the displayed trajectory frame; selecting a repeated View-mode atom uses
its on-screen replica position with the base atom's properties. Attached
calculators are never evaluated merely to populate Measure.

### Trajectories And Displacement

Multi-frame inputs add a timeline below the viewport. Scrubbing updates the
frame continuously, selected atom indices persist when topology permits, FPS
changes apply during playback, and **Skip** advances by `skip + 1` source
frames per tick. Bond topology is evaluated independently for each frame, so
bonds form or break when a pair crosses its cutoff.

Active analysis follows the displayed structure as well. Per-atom colors and
force vectors load that frame's stored values, displacement vectors retain the
chosen reference but move to the new endpoint, and an open RDF or finite
pair-distribution plot remains visible during source playback, Relaxation
playback, and live `G`/`R`/`S` edits. Every committed structure change triggers
a fresh curve; while it is calculated, the previous curve stays visible rather
than closing the drawer. For ordinary source or completed relaxation
trajectories, v_ase prepares every frame after the first calculation. For
larger frame/bin/partial-curve combinations, it keeps a bounded rolling cache
around the displayed frame instead of retaining an unbounded result table.
Changing RDF settings, labels, or structure invalidates the affected cache.
Volumetric
datasets explicitly associated with trajectory frames switch with the atoms;
if a frame has no matching field, v_ase hides the previous field instead of
presenting it as data for the new structure.

Video export uses FPS as playback speed. Optional `N x` interpolation creates
`(source_frames - 1) * N + 1` output frames. Minimum-image interpolation uses
periodic cells to avoid jumps across a boundary. Interpolation takes longer
because more frames are rendered.

![Trajectory displacement analysis](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_displacement.png)

For trajectories, **Analysis > Displacement** compares the current frame with
the previous frame or a chosen reference. Minimum-image correction, vector
scale, thickness, color, and 2D/3D style are configurable. Displayed
supercells repeat the vectors, and visual translation moves both endpoints
without changing the physical displacement.

### Map Per-Atom Data

**Atom colorscale** maps a numeric per-atom property onto any registered
Matplotlib colormap. The property list is discovered from the open structure
and includes coordinates, stored-force magnitude, scalar/component/norm views
of numeric `Atoms.arrays`, and per-atom calculator results such as charge,
magnetic moment, local energy, uncertainty, or model-specific MLIP outputs.
Numeric LAMMPS atom columns are exposed by their stored names.

![Trajectory-wide force-magnitude colorscale with locked limits and matching Cartesian force vectors](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_atom_colorscale.gif)

The example moves one O probe above a 192-atom Cu(111) slab through 14 frames.
A smooth screened external-probe field is stored in a
`SinglePointCalculator` on every frame. Its response extends through the first,
second, and third lateral neighbor shells instead of coloring only the nearest
three atoms. All 193 atoms participate in one trajectory-wide range, while the
zero-force probe remains at the lower endpoint. The complete trajectory is
scanned once to lock one `vmin` and `vmax`. At every frame, both colors and
arrows are reloaded from that same stored Cartesian force array. Arrow
direction is the current Cartesian force direction and arrow length is
`scale × |F|`; neither remains frozen while the probe moves. Force
arrows can use 2D or 3D geometry, custom color, thickness, and scale. If a
frame has no stored forces, v_ase reports that fact instead of evaluating a
calculator merely to draw arrows.

Use **Selected atoms only** to preserve the established appearance of every
other atom. **Fit current frame** resolves one range from the active frame and
keeps it fixed during playback. **Scan trajectory** resolves one global range
across every frame. Manual `vmin`/`vmax`, map reversal, and gamma contrast are
applied consistently to playback and export. The feature is lazy: disabling
it immediately restores the prior appearance without loading another scalar
array or colormap.

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

![Signed isosurface threshold moving across a fixed volumetric distribution](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric.gif)

The animation moves the actual isovalue slider across a broad fixed range;
the positive and negative meshes update at every captured level. Drag
**Isosurface opacity** to change only transparency without regenerating the
mesh. Multiple compatible
datasets can be combined with coefficients such as `+1, -1, -1` for a
charge-density difference. Grid values stay in the local v_ase backend; the
browser receives only the generated surface mesh.
Signed mode treats the isovalue as a nonzero magnitude and renders the
positive and negative crossings that remain inside the displayed field range.

The example is a deterministic analytic multi-center graphene pz field
generated by the repository. It demonstrates the controls and is not
presented as a DFT result.

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
settles. A newly entered `(hkl)` is the transform authority immediately; you
do not need to wait for the settled high-resolution texture before pressing
`G` or `R`.

![Interactive hkl scalar-field plane clipped to the displayed cell](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric_plane.gif)

The `(1 0 0)` plane is swept continuously through a 104 × 104 × 104 field and
settles at 1024-pixel sampling with one fixed `vmin` and `vmax`. Alternating
positive and negative multi-center lobes therefore remain smooth and directly
comparable throughout the animation. The oblique camera, white background,
atoms, and cell remain fixed.
The same external `v_ase api` operations available to an AI Agent add and move
the plane; every committed offset is reflected in the live GUI and returned by
`describe().analysis.volumetricPlanes`.

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

### Radial And Pair-distribution Functions

The same Analysis control chooses the statistically correct quantity from the
current boundary conditions. A fully periodic 3D cell is labeled **Radial
Distribution Function** and reports bulk `g(r)`. A structure with no periodic
axes is labeled **Pair-distribution function** and reports the probability
density of unordered pair distances in `Å⁻¹`. Both open in a resizable Plotly
drawer below the viewport. The total curve is always included; pair curves
default to active bond-label pairs and can be switched to active bonds whose
two endpoints are currently selected, all label pairs, or total-only. In the
selected mode, changing the selection refreshes only when its active label-pair
set changes; the partial curves keep the full-structure RDF normalization.
Set the bin count and cutoff, then use the graph's save icon to export exactly
the plotted columns as CSV or close the drawer with its adjacent close button.
The graph is tied to the coordinates currently on screen, not only to the
original input trajectory. It therefore follows manual atom transforms and
the separate optimization timeline produced by Relaxation without dismissing
the drawer.

Periodic RDF uses exact spherical shell volumes and ASE's periodic neighbor
search in the full triclinic cell. The requested cutoff is not limited to a
`2 x 2 x 2` replica or reduced at the unique minimum-image radius: v_ase
includes every periodic image whose distance falls inside the sphere and
reports the image span used. The finite pair distribution uses direct
Cartesian distances without inventing a bulk density; at a cutoff containing
all pairs, its probability density integrates to one. Partial-PBC slab and
wire systems remain rejected because they require a geometry-specific boundary
correction.

The dotted `g(r) = 1` reference makes the bulk limit explicit. In the
deterministic amorphous Cu-Zr example below, total, Cu-Cu, Cu-Zr, and Zr-Zr
curves are plotted together. Their broad short-range peaks decay into a flat
long-range plateau rather than falling with the finite display cell.

![Pairwise amorphous Cu-Zr RDF curves approaching the bulk limit](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_rdf.png)

## Constraints And Relaxation

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
For ASE `Hookean(a1, a2, rt, k)`, the spring is inactive while `r ≤ rt` and the
restoring-force magnitude is `k(r - rt)` after `r > rt`. v_ase reads `rt` and
`k` from the live ASE constraint. The displayed atom distance controls the
exact inactive/threshold/engaged transition, and the 3D helix appears only
when `r > rt`; no numeric annotation is added to clutter a dense structure.
The rendering does not change the ASE force law.

![Hookean constraint](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.png)

![Hookean motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

```bash
v_ase gui examples/readme_scene_assets/hookean.traj --interactive
```

### Relaxation

![Repulsive relaxation trajectory](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_relaxation.gif)

**Structure > Relaxation** places every optimization step on a dedicated mode
timeline. A single loaded structure gains a relaxation movie after the first
run. If a source trajectory is already open, source and relaxation timelines
remain separate and the active timeline is clearly selected. Leaving
**Exit Relaxation Mode** can be used while the optimizer is running or after it
stops. v_ase safely invalidates the active worker, removes the temporary
timeline, and asks whether to **Keep Current** relaxed coordinates or **Restore
Before Relaxation** exactly. Choosing Continue leaves the mode active. A
stopped run can be started again without reopening the document. Very short
runs may finish before the interface visibly enters its running state; their
initial, optimizer, and final frames still remain on the Relaxation timeline.
**Clear Trajectory** removes an accumulated optimization movie without leaving
the mode and asks whether to retain the displayed frame or the final frame.

The included example starts from a deliberately compressed C60 geometry and
runs ASE FIRE with v_ase's repulsive fallback calculator:

- [crowded initial C60](examples/readme_scene_assets/crowded_c60_initial.cif)
- [relaxed C60](examples/readme_scene_assets/crowded_c60_relaxed.cif)
- [optimization trajectory](examples/readme_scene_assets/crowded_c60_relaxation.traj)

```bash
v_ase gui examples/readme_scene_assets/crowded_c60_initial.cif --interactive
```

The fallback calculator is intended for removing obvious close contacts, not
for predictive chemistry. Repulsion is deliberately independent from visible
bonds: a pair such as `H_water-H_water` can repel even when no H-H bond is
drawn. **Absolute pair distances** is the default. Its label-pair table uses
one physical onset distance `r_cut,ij` in angstrom for every pair; disabling a
row or entering `0 Å` makes only that pair non-repulsive. New rows start from
ASE covalent-radius sums, with van der Waals radii available as an alternative
reference. **Reference distances x contact multiplier** retains a
dimensionless multiplier for workflows that want all enabled reference
distances scaled together. A global absolute distance remains available as a
fallback when no pair table is supplied.

Below either onset distance, the pair potential is
`E = 1/2 k (r_cut - r)^2`. Because there is no restoring term beyond the
cutoff, neither mode constrains the final separation to equal `r_cut`;
optimizer tolerance and other forces determine where the run stops. Attach a
scientific ASE calculator when optimized energies or forces will be used as
physical results.

## Style Atoms, Bonds, And Rendering

**Structure > Appearance** controls each stable atom label:

- ASE chemical TYPE and independent visual label;
- visibility and selection availability;
- color, radius, and opacity (`0` transparent through `1` opaque);
- Standard, Metal, or Rubber material;
- all/partial/none selection checkbox.

View mode can split or rename visual labels and apply label/per-atom appearance
without changing ASE element types or coordinates. For a trajectory with a
stable atom count and element order, the same atom indices keep that label in
every frame. If topology differs, v_ase opens a modal and applies the label to
the current frame only. The chemical TYPE field remains disabled until Edit.
These visual identities are included in complete `.vase` and HTML project
saves. Label color, radius, opacity, visibility, and material are also retained
by reusable visual presets and supported geometry exports. Edit mode can keep
additional per-atom material overrides. Relabeling does not reorder the table
or merge otherwise distinct atom types accidentally.

![View-mode label and appearance editing on Cu5O4](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_cu5o4_view_appearance.gif)

The recording begins with a viewport box-selection around the 32 substrate Cu
atoms. It then enters `Cu_substrate` in **Selected atoms > Label**, applies the
**Metal** material, presses the shared **Apply** once, and changes that label's
color and radius to white and `2.0 Å` in the Appearance table. Oxide Cu and O remain unchanged. The final
side-to-top orbit verifies that the operation is visual only: every atom keeps
its original Cu or O ASE element and coordinate.

![Standard Metal and Rubber atom materials](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_materials.png)

The comparison uses three identical Cu13 clusters with the same element color
and radius, so only the optical material changes:

| Material | Visual response | Typical use |
| --- | --- | --- |
| Standard | Balanced diffuse color and compact highlight | General structures and chemically neutral figures |
| Metal | Strong environment reflection and bright metallic highlight | Metals, electrodes, and reflective surfaces |
| Rubber | High roughness with broad, muted highlights | Soft visual grouping and low-glare nonmetal regions |

Materials affect rendering only. ASE elements, coordinates, calculators, and
constraints are unchanged. Numeric property coloring and force-vector analysis
are documented under [Map Per-Atom Data](#map-per-atom-data).

![Pairwise Cu O bonds in a Cu2O(111) film on Cu(111)](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_bonds.png)

**Structure > Bonding** provides automatic inference, explicit label-pair
cutoffs, and manual index pairs. A pair cutoff of zero disables that pair.
Changes apply immediately. Bonds support:

- cell-local or periodic minimum-image display;
- cylinder or flat 2D geometry;
- custom color or two half-bonds using the atom colors;
- configurable diameter, opacity, and Standard, Metal, Rubber, or Unlit material;
- independent label-pair appearance overrides, including per-pair flat 2D
  geometry while the rest of the scene remains 3D, plus one-click Apply All;
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

**2D flat** is a scene-wide display mode, not a bond-only shortcut. It keeps
atom colors and radii while disabling lighting and 3D materials, draws atoms
and bonds with background-aware outlines, marks FixAtoms with an X, and
flattens force/displacement arrows, unit-cell edges, and Add Atoms regions.
Depth testing still preserves which atom or bond lies in front. Switching back
to **3D materials** restores the previously selected materials and lighting
without rebuilding scientific state.

The top-bar renderer switches between fast modeling light and Sun/soft-shadow
rendering. Sun source, target, intensity, and direction can be manipulated in
the viewport and carried into Blender export. Hovering any compact top-bar
icon briefly opens its plain-language description; this includes the renderer,
grid, view-orbit, open, reset, and help controls.

### Interface Theme And Personal Defaults

**View > Interface theme** controls the application chrome and its default
viewport treatment. **System** is the default: the chrome follows the browser
or operating-system preference while the scientific viewport remains white,
giving the mixed layout used for ordinary work. **Light** keeps both chrome
and viewport light. **Dark** explicitly switches both the interface and atom
viewport to dark. A manually selected viewport background still takes
precedence when restoring a visual preset.

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
| Export Image | PNG by default; JPEG, PDF, and lossless WebP from the exact Render Area |
| Export Video | Constant-frame-rate H.264 MOV or MPEG-4 AVI with optional interpolation |
| Export Blender | Optimized scene script with atoms, bonds, cell, camera, and Sun |
| Export 3DM | Instanced Rhino geometry, metadata, and saved camera views |
| Export OBJ | OBJ/MTL, camera, and metadata in a ZIP |
| Export HTML View | Offline, view-only 3D document; lightweight by default, with optional `.vase` recovery |
| Save `.vase` | Compact project with structure/trajectory and complete visual state |
| HTML Project | Browser-ready project with complete embedded `.vase` recovery by default |
| Export/Import Preset | Portable visual settings file without coordinates |

Image, video, and HTML use one shared persistent **Render Area**. The gray
outside mask shows exactly what will be excluded; atom picking inside the gate
uses the same camera and therefore selects the visible atom under the pointer.
Keep **Follow viewport** enabled while composing, or disable it and use **Set
from Current View** to lock the export camera while continuing to orbit, edit,
restyle, or relight the working viewport. In Edit, select the eye indicator and
press `G` to translate the fixed Render Area camera and target together.
Its aspect ratio, crop, lighting, atom scale, and overlays match saved output.
HTML View defaults to grid off, axes on, and unit cell on.

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
browser. The save dialog shows the exact shared Render Area crop and lets you
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
only that exact Render Area crop: no v_ase logo, header, decorative border, or
page margin is included. This lets macOS Finder/Quick Look show the structure
without executing WebGL. In a browser, the first prepared WebGL frame replaces
the poster with a short cross-fade as soon as the first live frame is ready,
before camera input begins. Both surfaces occupy the same rectangle, so the
structure does not jump. View-only controls appear only after pointer or
keyboard activity.

HTML width and height inherit the image/video Render Area. They define the
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

## Work With An AI Agent

![A natural-language request passing through an external AI Agent into the same live revisioned v_ase GUI](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.gif)

You describe the scientific result to an external AI Agent in ordinary
language. The Agent translates that request into exact **CLI** operations;
v_ase renders those operations immediately, and you inspect or refine the same
document through the **GUI**. The same document stays open in one live GUI, so
the Agent's changes and your direct refinements never split into separate
copies. The bundled
[v_ase Skill](v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md)
teaches that Agent the exact state queries, edits, validation checks, camera
commands, and exports. v_ase itself does not contain an LLM or interpret
natural language.

The figure labels only the interface used on each bidirectional link:

| Link | What crosses it |
| --- | --- |
| **Natural language** | Your requested result, clarification, and the Agent's completion report |
| **CLI** | Revision-checked operations to v_ase; exact state and newer revisions back to the Agent |
| **GUI** | The live rendered result to you; your direct visual refinements back to the same document |

1. **You ↔ AI Agent:** request the scientific result in natural language; the
   Agent can ask for clarification and report what it changed.
2. **AI Agent ↔ v_ase CLI:** the Agent sends structured, revision-checked
   operations and receives exact atomistic state plus every newer revision.
3. **You ↔ v_ase GUI:** watch the same live result and fine-tune it directly.
   Each committed GUI edit returns through the CLI event stream, so the Agent
   reads that human change before continuing.

The animation shows the complete cycle: your request, its structured operation
sequence, each live structural and camera change, a direct GUI radius/bond
refinement, the resulting revision event, Agent re-verification, and the final
natural-language completion. A manual GUI edit becomes the next document
revision rather than an invisible side change.

For example:

> Starting from pristine 6 × 6 graphene, create a pyridinic N3 vacancy, place
> Li 2.15 Å above the vacancy, then render a 4K +Z view with +Y up.

The Agent resolves atom identities and coordinates from semantic state instead
of estimating them from screenshots, performs the authorized topology edits,
sets the requested camera, and validates the final render. Structured state can
also reduce repeated image interpretation and can reduce token use while
retaining exact labels, positions, cells, constraints, and camera parameters.
In the shown result, the three substituted atoms use the `N_pyridinic` label
and the adsorbate uses `Li_site`, so both the GUI and the Agent refer to the
same chemical roles.

![Natural-language pyridinic N3 graphene edit in the shared GUI](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_edit.gif)

The live schema covers structure edits, constraints, trajectories, cameras,
appearance, force vectors, volumetric surfaces and planes, colorscales, RDF,
commensurate cells, planar translation maps, rendering, and export. The bundled release
tests require advertised operations, browser handlers, and Skill instructions
to remain synchronized.

The example is generated locally from `ase.build.graphene`:

- [source graphene CIF](examples/readme_scene_assets/ai_graphene_source.cif)
- [intermediate pyridinic N3 CIF](examples/readme_scene_assets/ai_pyridinic_n3_graphene.cif)
- [final N3/Li-site CIF](examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.cif)
- [ASE trajectory preserving labels](examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.traj)

### Agent Setup

The AI Agent runs separately from v_ase. Give it the complete
[v_ase Skill directory](https://github.com/lgyEthan/v_ase/tree/main/v_ase/skills/visualizing-atomic-structures-with-v-ase),
then describe the result you want. The agent starts the machine-readable v_ase
session, gives you the live GUI URL, and performs verified changes in that same
document.

The Skill is vendor-neutral and can be used by Codex, Claude Code, ChatGPT
desktop agents, Gemini-based agents, agentic IDEs, or another agent that can
run local commands.

```text
You <-> AI Agent       natural-language request and feedback
AI Agent <-> v_ase CLI structured operations, exact state, and revisions
You <-> v_ase GUI      live inspection and direct visual refinement
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
selected file can be confirmed with **Open** or `Enter`; one confirmation
starts one load and does not reopen the picker. It can:

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
example, `Cu O O` with counts `160 15 1` becomes `Cu`, `O_1`, and `O_2` in
the original block/index order while every oxygen remains ASE element `O`.
This preserves intentionally separate POTCAR, magnetic, and core-hole groups
for visualization and pair analysis without changing the ASE structure.
Custom labels retain their complete text when they are renamed.

## Controls

| Input | Action |
| --- | --- |
| Left click / Shift + click | Select / extend selection |
| Left drag | Box select |
| Middle drag | Orbit without inertia |
| Shift + middle drag | Pan |
| Wheel | Zoom |
| `G` / `R` / `S` | Move / rotate / physically scale selected atom spacing |
| `X`, `Y`, `Z` during `G`/`R`/`S` | Lock the global Cartesian transform axis |
| `X`, `Y`, `Z` otherwise | Align camera to an axis |
| Number keys | Exact move distance, rotation angle, or scale factor |
| `Enter` or left click | Confirm transform |
| `Esc` or right click | Cancel transform |
| `Ctrl+C`, `Ctrl+V` | Copy and paste exact-coordinate atoms with per-atom state |
| `Ctrl+Z`, `Ctrl+Shift+Z` | Undo and redo structure and visualization-setting changes; camera navigation is excluded |
| `Delete` / `Backspace` | Hide exact visual instances in View; physically delete base atoms in Edit |
| `Space` | Play or pause the active timeline |

Undo follows user actions rather than intermediate animation frames. One
confirmed `G`/`R`/`S` gesture, one Apply, one atom/molecule placement batch,
or one completed relaxation start is one history step. Repeated placement
inside an active Add session can therefore be undone and redone batch by
batch; cancelling that session still restores its exact pre-session baseline.
| Left / Right Arrow | Previous / next frame in the active timeline |
| `Tab` or `Esc` | Open a collapsed control panel |
| `Esc` with the panel open | Close it and return focus to the viewport |

The **?** button contains the complete shortcut table.

## Remote Servers

Run one command locally after installing the same current v_ase release on the
local computer and remote host:

```bash
v_ase gui USER@SERVER:/absolute/path/to/STRUCTURE
```

An SSH config alias works:

```bash
v_ase gui physics:/absolute/path/to/trajectory.extxyz
```

No port number is required. v_ase selects private ports, starts the backend
beside the remote file, carries that backend and the port forward over one SSH
connection, and opens the local browser. Keeping both operations on the same
SSH connection is important for cluster aliases that distribute logins across
multiple nodes.

Processing is split deliberately:

- **Remote host:** source-file I/O, ASE parsing, trajectory cache, volumetric
  sampling and isosurface generation, and backend calculations.
- **Local computer:** the browser UI, camera interaction, and WebGL rendering.

The source file is not downloaded. A current remote v_ase sends only the frame
or derived rendering data requested by the browser through the encrypted SSH
tunnel. The remote installation is therefore required because the Python
backend and its ASE dependencies execute next to the remote data. Upgrade the
remote installation before opening a large trajectory or using a newly added
backend feature. Use `ProxyJump` in `~/.ssh/config` when an intermediate login
host is required.

In View mode, XDATCAR is byte-indexed once and native ASE `.traj` files use
their random-access container. Startup parses only the first requested frame;
scrubbing asks the remote process for later frames on demand. Uncommon XDATCAR
headers automatically fall back to ASE's compatible reader instead of being
misinterpreted. Edit mode still materializes frames because physical topology
operations require editable ASE objects.

If `v_ase` is not on the non-interactive SSH `PATH`, select the exact remote
environment for one launch. This does not source `.bashrc` or activate Conda:

```bash
v_ase gui physics:/absolute/path/to/POSCAR \
  --remote-python /home/user/miniconda3/envs/vase/bin/python
```

For a host used repeatedly, save the Python executable once. Use the exact
host text that appears to the left of `:` in the file argument:

```bash
v_ase remote configure physics \
  --python /home/user/miniconda3/envs/vase/bin/python
v_ase remote show
v_ase gui physics:/absolute/path/to/POSCAR
```

The one-launch `--remote-python` value overrides the saved host setting. Inspect
one mapping with `v_ase remote show physics`, or remove it with
`v_ase remote remove physics`. The configuration stores only host names and
absolute Python paths in the local user configuration directory; the remote
source file and SSH credentials are never copied into it.

## License

v_ase is licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE)
(`AGPL-3.0-or-later`). You may use,
modify, and redistribute the software under that license; distributions and
modified network services must satisfy its source-availability and
same-license requirements. Copyright (C) 2026 v_ase contributors.

The bundled Three.js module retains its own MIT license in
[`v_ase/static/vendor/THREE_LICENSE`](v_ase/static/vendor/THREE_LICENSE).

## Citation

Use the repository's **Cite this repository** menu or
[`CITATION.cff`](https://github.com/lgyEthan/v_ase/blob/main/CITATION.cff) to
cite the exact software version.

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

The terminal always prints the complete local URL before attempting to open a
browser. Ctrl+click it or copy the text beginning with `http://` into Chrome,
Edge, Firefox, or another browser. Keep the terminal process running. This
fallback remains visible even when a WSL interop command exits successfully
without creating a browser tab.

Example with sensitive session identifiers masked:

```text
(base) giyeok@DESKTOP-XXXX:~$ v_ase gui
v_ase viewer URL (Ctrl+click or copy into a browser):
http://127.0.0.1:58039/workspace?workspace_id=xxxx&session_id=xxxx
gio: http://127.0.0.1:58039/workspace?workspace_id=xxxx&session_id=xxxx: Operation not supported
```

For better WSL performance, keep trajectories under the Linux filesystem
rather than `/mnt/c/...`.

</details>

<details>
<summary>Remote launch cannot find <code>v_ase</code>, or it is installed only in a Conda/venv environment</summary>

An interactive login shell may activate Conda or alter `PATH`, while the
non-interactive SSH command used by `HOST:/path` may not. Point v_ase directly
at the Python executable that contains the remote installation:

```bash
v_ase gui USER@SERVER:/absolute/path/to/STRUCTURE \
  --remote-python /home/user/miniconda3/envs/vase/bin/python
```

Verify the path independently when needed:

```bash
ssh USER@SERVER '/home/user/miniconda3/envs/vase/bin/python -m v_ase.cli --version'
```

For repeated launches, save the same path with `v_ase remote configure
USER@SERVER --python /home/user/miniconda3/envs/vase/bin/python`. The transient
flag always wins, so it can temporarily select a different environment without
changing the saved default. If neither setting is present, v_ase retains the
normal `PATH`-based behavior that works on clusters where the entry point is
already exported to non-interactive SSH sessions.

</details>

<details>
<summary>Remote launch reports unrecognized <code>--no-browser</code> or <code>--stream-frames</code></summary>

Upgrade the local launcher to v_ase 0.2.14 or later. It detects the remote CLI
before starting the viewer and automatically uses a compatible command:

```bash
python -m pip install --upgrade "v_ase-gui>=0.2.14"
v_ase gui USER@SERVER:/absolute/path/to/STRUCTURE
```

The fallback keeps the structure file on the server. Upgrade the remote
installation as well to retain on-demand frame streaming for large
trajectories and newer features such as explicit volumetric precision:

```bash
ssh USER@SERVER 'python -m pip install --upgrade v_ase-gui'
```

</details>

<details>
<summary>A remote URL opens and then reports <code>ERR_CONNECTION_RESET</code></summary>

Upgrade the local launcher to v_ase 0.2.17 or later:

```bash
python -m pip install --upgrade "v_ase-gui>=0.2.17"
```

Older launchers created the remote backend and the port forward with separate
SSH connections. A load-balanced cluster alias could place those connections
on different login nodes. Current releases keep both on one SSH connection.
The remote file remains on the server in either case.

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
<summary>What does selecting or deleting a replicated supercell atom change?</summary>

In **View**, each displayed replica is independently selectable for
measurement and appearance. **Hide Selected** removes only that visual
instance and its bonds; the ASE structure is unchanged. Structural analysis
warns that hidden atoms remain in the backend and offers **Switch to Edit &
Delete** when physical removal is intended.

In **Edit**, every replica maps to its corresponding base atom in the editable
unit cell. Click or box selection is deduplicated across periodic images. The
base atom keeps the normal full selection halo and all equivalent displayed
replicas receive smaller, lower-opacity rings; their atom opacity is unchanged.
Use **Set Supercell as Cell** only when every displayed copy must become a real
ASE atom in a larger physical cell.

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

- For a loaded large structure or trajectory, use View unless editing is required.
- Current XDATCAR and native ASE `.traj` inputs are indexed for on-demand View
  loading automatically, including through `HOST:/path` remote sessions.
- Use `--stream-frames` for other supported virtual trajectory readers when
  launching a backend manually.
- Keep browser hardware acceleration enabled.
- Close unused v_ase tabs; inactive tabs pause rendering but retain document
  state in memory.
- In WSL, keep data in the Linux filesystem.

</details>

<details>
<summary>Open or Add to trajectory reports a file-reader error</summary>

v_ase shows the final useful reader message rather than a generic Internal
Server Error. If it says the format could not be determined, choose the
matching **Reader** explicitly or use a recognized extension. Missing-file,
permission, directory, invalid-text, and truncated-file failures have targeted
messages. For an unrecognized failure, the dialog shows the final exception
line while the complete traceback remains only in the terminal log.

</details>

<details>
<summary>Pair statistics report that fully periodic 3D boundaries are required</summary>

Finite structures with all PBC axes off use the finite **Pair-distribution
function** automatically. Fully periodic 3D structures use bulk RDF `g(r)`.
Partial-PBC slabs and wires are not silently treated as either case; use a
method with the boundary correction appropriate to that geometry.

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
