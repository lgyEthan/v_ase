<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase atomistic logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.python.org/pypi/v_ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.python.org/pypi/v_ase-gui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`v_ase` was developed for researchers who want the convenience of ASE and the
flexibility of Blender in one atomistic workflow. ASE is convenient because
structures and trajectories can be opened directly from Python or the terminal.
Blender is flexible because objects can be selected, moved, rotated, inspected,
and edited in a real 3D scene. `v_ase` combines those two strengths: an
`ase gui`-style entry point for scientific files, plus direct 3D editing for
atomic structures.

It is intended to replace:

```bash
ase gui FILE
```

with:

```bash
v_ase gui FILE
```

For example:

```bash
v_ase gui
v_ase gui POSCAR
v_ase gui structure.vasp
v_ase gui movie.extxyz
v_ase gui relaxation.traj
```

Run `v_ase gui` without a filename to open an empty workspace, then use **Open**
to choose an ASE structure, trajectory, or `.vase` project in the browser. A
reader selector is available for ambiguous filenames, and a blocking loading
overlay remains visible until the complete file is ready.

The viewer opens locally in your browser. By default, `v_ase gui [FILE]` starts in
a lightweight visualization mode for fast inspection, trajectory playback,
bonding, supercell preview, appearance edits, wrapping, and export. Add
`--interactive` when you want Blender-style atom editing: left click and box
drag select atoms, `G` moves atoms, `R` rotates atoms, `X/Y/Z` lock axes, and
numeric input gives exact transforms. For normal blocking CLI use, closing the
browser tab or window finalizes the current session and returns control to the
terminal.

![v_ase overview](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/readme_overview.png)

## Highlights

- Open an empty file-loading workspace with `v_ase gui`, or open ASE structures,
  trajectories, and `.vase` projects directly with `v_ase gui FILE` or
  `from v_ase.visualize import view`.
- Inspect large systems in the lightweight default viewer, with GPU-instanced
  atoms, bonds, supercells, and live trajectory playback.
- Add `--interactive` for Blender-style selection, move, rotate, axis locking,
  numeric transforms, copy/paste, undo, and atom creation.
- Visualize and edit ASE constraints including `FixAtoms`, `FixedLine`,
  `FixedPlane`, `FixScaled`, and threshold-aware `Hookean` springs.
- Preview the exact output frame at the requested pixel aspect ratio, render
  with Modeling, Studio Sun, or Sun + Soft Shadow, then export images, video,
  POSCAR, a structure-only ASE pickle, an editable Blender scene script, Rhino
  3DM geometry, or a portable OBJ/MTL bundle.
- Save reusable visual presets as JSON or restore the complete scientific and
  visual working state from a portable `.vase` project.

## Why v_ase

`v_ase` combines two workflows researchers normally have to keep separate:

| ASE convenience | Blender flexibility | Scientific continuity |
| --- | --- | --- |
| Open structures and trajectories from Python or the terminal. | Select, inspect, move, rotate, and style atoms directly in 3D. | Keep ASE cells, PBC, constraints, calculators, labels, and trajectory data connected to the visualization. |

The default mode is a fast visualizer for routine inspection. Interactive mode
adds structure editing only when it is needed, while the same appearance,
bonding, measurement, trajectory, rendering, and export controls remain
available in both workflows.

## Feature Reference

- `v_ase gui` opens an empty workspace with browser file loading; `v_ase gui
  FILE` opens POSCAR, VASP, extxyz, traj, `.vase`, and other supported files
  directly.
- Blocking CLI sessions behave like `ase gui`: the terminal waits while the
  browser tab is open, then continues after the tab/window is closed.
- Python API for notebooks and scripts: `from v_ase.visualize import view`.
- Lightweight OVITO-style inspection is the default CLI mode, keeping bonds,
  supercell, appearance, visual type labels, measurements, projection, wrapping,
  and export controls responsive for large structures.
- Large scenes use shared unit-sphere geometry, GPU instancing for atoms, bonds,
  selection outlines, and supercell replicas, adaptive pixel ratio,
  and demand rendering. An idle viewport does not continuously consume GPU
  frames. See [Rendering Performance](https://github.com/lgyEthan/v_ase/blob/main/docs/performance.md)
  for architecture and reproducible benchmark details.
- Orthographic projection is the default view, with perspective available from
  the View panel. `Atomic scale` is a live viewport control in `Display > Viewport`,
  not an image-export-only setting: changing its `px/Å` value immediately zooms
  the current structure, the field below reports the visible width and height in
  Å, and wheel zoom updates the value in return. This follows
  [VESTA's live magnification model](https://www.jp-minerals.org/vesta/en/doc/VESTAch11.html)
  and its separation of display magnification from raster-image export.
- The control panel is organized into Inspect, Structure, Display, and
  Export & Save sections. It starts collapsed and opens from a compact edge
  handle, leaving the viewport unobstructed until controls are needed. v_ase
  remembers the active section, explicit collapsed state, and panel width.
  `Tab` opens the panel only while it is collapsed. Inside the panel, `Tab`
  remains normal form navigation; `Esc` commits the active field, closes the
  panel, and returns keyboard focus to the viewport. Controls inside each
  category start expanded.
- Viewport lighting is opt-in and its compact rendered-sphere control
  sits in the top toolbar, immediately beside the calculator controls. Its lit
  state adds a clear highlight and ground shadow, while the matte sphere remains
  recognizable as the same renderer control when lighting is off. Modeling keeps the
  original low-overhead, evenly-lit view; Studio Sun adds real-time PBR
  directional lighting; Sun + Soft Shadow adds a structure-fitted shadow map
  without a finite-frustum seam across large or off-origin structures. The Sun
  source and direction target are independently selectable viewport objects.
  `Source + G` translates the complete Sun rig without changing its direction;
  `Target + G` moves only the target to aim the light. `R` always rotates the
  target around the source, whichever handle is selected. Axis locks, numeric
  input, `Enter`, and `Esc` work for both handles.
  Source, target, and strength also remain editable in the lighting panel.
- Add `--interactive` for Blender-like atom editing: middle-mouse orbit,
  shift-middle pan, wheel zoom, click/box selection, `G` move, `R` rotate, axis
  locking, numeric transforms, `Enter`, `Esc`, copy/paste/undo/delete.
- Selection measurements: two selected atoms show distance, and three selected
  atoms show two distances plus the central angle. A compact persistent Measure
  HUD stays independent from the changing hover-atom metadata. In visualization
  mode, supercell replicas are independently selectable and their displayed
  Cartesian positions contribute to center, distance, and angle statistics.
- Calculator handling preserves existing ASE calculators, including
  `SinglePointCalculator`. The default lightweight visualization mode does not
  attach a fallback calculator; `--interactive` enables the soft repulsion
  fallback used for built-in relaxation.
- Torch is optional, not a package dependency. When torch is installed, the
  default repulsion calculator can use torch CPU or CUDA; otherwise it falls
  back to NumPy.
- ASE constraint-aware editing and visualization:
  `FixAtoms`, `FixCartesian`, `FixedLine`, `FixedPlane`, `FixScaled`, and
  `Hookean`. `FixAtoms` are rendered with a faceted, micro-etched material so
  they remain distinguishable without changing the element color. VASP
  selective-dynamics `FixScaled` masks are interpreted in fractional
  coordinates and displayed as cell-aware `FixedPlane` or `FixedLine` guides.
- Interactive constraint editing for selected atoms: apply or clear `FixAtoms`,
  `FixedLine`, and `FixedPlane` from the Constraints panel.
- Hookean constraints are visualized as threshold-aware hook/latch springs.
- Trajectory playback with live frame slider, FPS control, frame skip, image
  export, and video export.
- Interactive relaxation streams an optimization trajectory into the bottom
  timeline. Static single-structure sessions stay uncluttered until relaxation
  creates frames; loaded trajectory files keep their own movie timeline while a
  separate Relax row exposes the latest optimization path.
- Cell-local bonds, opt-in periodic-image bonds, label-pair cutoff tables,
  manual atom-index pairs, supercell preview, `make_supercell(P)` cell transform,
  and wrap atoms into cell. In interactive mode, auto and pairwise-cutoff bonds
  form and break live during G/R previews; the chosen mode, scales, pair-specific
  `rcut` values, MIC policy, and manual pairs persist when the structure or
  trajectory frame changes.
- Custom extxyz atom type labels such as `H_type5` are preserved for GUI type
  settings even when ASE cannot parse them as real elements.
- LAMMPS `lammpstrj` and `.data` integer types stay visible as labels. Valid
  integer type ids are also used as atomic numbers for color/radius distinction;
  out-of-range ids fall back to ASE-valid `H` while preserving the raw label.
- Appearance label edits keep row order stable. Labels with element prefixes
  such as `O_bridge` automatically update the TYPE dropdown, ASE GUI color, and
  default radius. Labels sharing one chemical TYPE share that TYPE's default
  color; per-label colors change only through an explicit Appearance override.
- Export POSCAR, a current-frame ASE pickle, PNG image, WebM video, Blender
  Python scene script, Rhino 3DM scene, and OBJ/MTL bundle. The pickle preserves
  labels, cell/PBC, constraints, portable atom arrays, and valid
  `SinglePointCalculator` results, but excludes
  visualization settings and arbitrary executable calculator objects.
  Image export can keep the live camera direction and magnification while using
  the requested output ratio as its exact crop gate, or use the global View
  `Atomic scale` for directly comparable images from different structures.
  `Preview Area` fills a screen-fixed frame with that exact export camera and
  scene; orbiting or zooming changes the atoms without moving the frame itself.
  Export-only atom smoothness and its quality multiplier are independent of
  viewport performance settings. Image export can also use
  viewport lighting or an independent Modeling, Studio Sun, or Sun + Soft Shadow
  setup. Blender export includes the viewport camera,
  unit cell, bonds, smooth atoms, and a true Blender `SUN` object with the same
  source position, target-derived direction, color, and numeric strength used
  in v_ase. Optimized export uses editable point groups and Geometry Nodes;
  individual atom objects remain available as an explicit export mode.
  Rhino 3DM export uses native spheres, Brep cylinders or flat bond meshes,
  repeated unit-cell lines, Å model units, layers, materials, and per-object
  atom metadata. OBJ export needs no extra Python package and downloads a ZIP
  containing `v_ase_scene.obj` plus `v_ase_scene.mtl` so atom and bond colors
  survive import.
- Save Visual Settings as a reusable JSON preset. Matching labels recover their
  appearance and pairwise bond cutoffs, missing labels are ignored, and labels
  new to the opened structure receive ASE-derived defaults.
- Save a complete `.vase` project containing the current structure or
  trajectory, active frame, coordinates, cell, PBC, constraints, labels,
  portable atom arrays, cached calculator results, camera, lighting, bonds,
  quality settings, and supercell preview.

## Installation

### From PyPI

```bash
python -m pip install v_ase-gui
```

### From GitHub

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install --upgrade pip
python -m pip install -e .
```

No conda and no Node.js are required. Three.js is vendored inside the package.

### Optional Packages

Core viewing, editing, Blender/OBJ/image/video export, ASE pickle, POSCAR,
settings, and `.vase` projects need no package beyond the normal installation.
Install an extra only for the feature that needs it:

| Feature | Install | When it is needed |
| --- | --- | --- |
| Rhino 3DM export | `python -m pip install "v_ase-gui[rhino]"` | Adds `rhino3dm` and enables **Export 3DM**. Without it, v_ase reports the exact install command and leaves all other exports available. |
| Jupyter integration | `python -m pip install "v_ase-gui[jupyter]"` | Adds Notebook and JupyterLab for notebook workflows; the CLI and Python `view()` API do not require this extra. |
| Torch acceleration | Follow the [official PyTorch installer](https://pytorch.org/get-started/locally/) for the target CPU/CUDA platform. | Optional acceleration for the interactive fallback repulsion calculator only. It is not used by visualization or any exporter. |

For an editable GitHub checkout, use `python -m pip install -e ".[rhino]"`
instead. OBJ export is implemented with the Python standard library and has no
optional dependency.

If pip reports `ERROR: Error while checking for conflicts` after saying
`Requirement already satisfied: v_ase-gui`, the package is already installed;
the failure is usually caused by a different installed package with broken
metadata (`version=None`) in that Python environment. Use:

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade --force-reinstall --no-deps v_ase-gui
python -m pip check
```

If `pip check` still crashes, create a clean virtual environment or repair the
package with invalid metadata before installing scientific packages into that
environment.

## Quick Start

Open a structure file:

```bash
v_ase gui
v_ase gui POSCAR
v_ase gui structure.vasp
v_ase gui trajectory.extxyz
v_ase gui relaxation.traj
v_ase gui project.vase
```

The direct file form also works:

```bash
v_ase POSCAR
```

`v_ase gui` opens first and lets you choose a structure, trajectory, or `.vase`
project from the **Open** button. The reader and ASE frame index can be selected
before loading, including for an extensionless input. Opening another ordinary
structure or trajectory in the same session retains the current visual setup and
camera, reconciles label-specific values against the new structure, and assigns
defaults to newly encountered labels. Opening a `.vase` project instead restores
that project's complete saved state.

Use from Python:

```python
from ase.build import molecule
from v_ase.visualize import view

atoms = molecule("H2O")
edited = view(atoms)
print(edited.positions)
```

Useful CLI options:

```bash
v_ase gui structure.vasp --show-bonds
v_ase gui trajectory.extxyz --index :
v_ase gui trajectory.extxyz --index -1
v_ase gui ABCD --format POSCAR
v_ase gui ABCD --format XDATCAR
v_ase gui ABCD --format vasprun.xml
v_ase gui ABCD --format lammpstrj
v_ase gui ABCD --format data
v_ase gui ABCD --format vase
v_ase gui POSCAR --interactive
v_ase gui POSCAR --output edited.vasp
v_ase gui POSCAR --no-block
```

`--format` forces the input reader when the filename is ambiguous. It accepts
common aliases such as `POSCAR`, `XDATCAR`, `vasprun.xml`, `lammpstrj`, `traj`,
`xyz`, `extxyz`, `data`, and `vase`, plus raw ASE format names.

## Example Structures

The README and demo structures can be regenerated from source:

```bash
python examples/readme_scenes.py
```

This writes single-structure `.traj` files under `examples/readme_scene_assets/`.
Open them with normal v_ase commands:

```bash
v_ase gui examples/readme_scene_assets/fixedline.traj --show-bonds
v_ase gui examples/readme_scene_assets/fixedplane.traj --show-bonds
v_ase gui examples/readme_scene_assets/hookean.traj --show-bonds
v_ase gui examples/readme_scene_assets/ferrocene.traj --show-bonds
v_ase gui examples/readme_scene_assets/showcase.traj --show-bonds
```

Constraint guide design variants can be inspected without starting the app by
opening `docs/design/constraint_guides_preview.html` in a browser. It compares
five always-visible FixedLine marker candidates and five FixedPlane marker
candidates on one constrained structure.

## Case 1: Selection, FixedLine, and FixedPlane

Selected atoms get yellow Blender-style outlines. `FixAtoms` entries keep their
atom color but switch to a faceted, micro-etched material, so they read as
immobile without looking selected. `FixedLine` and `FixedPlane` guides stay
hidden until the constrained atom is selected, then appear as a thin fading axis
or a translucent CAD-style plane. When multiple FixedPlane atoms are selected,
each atom keeps its own compact local plane marker so the constraint never looks
anchored at the selection COM. `Show Overlays` can hide all of these guides for
a clean structure view.

`FixedLine` is shown as a Li ion moving along a carbon nanotube channel. The ion
can slide parallel to the tube axis, but not leave the channel direction:

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

`FixedPlane` is shown as a Li ion moving over a Cu(111) surface. The guide is an
unbounded plane field through the selected atom, not a finite patch, so the
surface-parallel XY constraint reads as diffusion over the surface rather than
rotation:

![FixedPlane movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

Example:

```python
from ase.build import molecule
from ase.constraints import FixAtoms, FixedLine, FixedPlane
from v_ase.visualize import view

atoms = molecule("H2O")
atoms.set_constraint([
    FixAtoms(indices=[0]),
    FixedLine(1, [1, 0, 0]),
    FixedPlane(2, [0, 0, 1]),
])

view(atoms)
```

When `Apply constraints` is enabled, move and rotate previews are projected onto
the allowed line or plane and the backend commit uses
`atoms.set_positions(..., apply_constraint=True)`.

## Case 2: Hookean Constraints

`Hookean` constraints are drawn with physical meaning. The `rt` threshold is
placed in Angstroms along the constrained direction. Below the threshold the
spring is inactive and shows slack. Beyond the threshold the latch engages and
the spring becomes active. The example below uses a 9-atom ethanol-like
adsorbate on Cu(111). The O-H group moves with oxygen while the C-O bond is
pulled, so the graphic reads as a bond-retention constraint rather than an
arbitrary long-range tether.

![Hookean threshold-aware spring](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/readme_hookean.png)

Example:

```python
from ase.build import molecule
from ase.constraints import Hookean
from v_ase.visualize import view

atoms = molecule("H2O")
atoms.set_constraint(Hookean(0, 1, rt=1.15, k=5.0))
view(atoms)
```

For trajectories, the Hookean graphic updates frame by frame, so inactive,
near-threshold, and active states can be inspected as a movie.

![Hookean constraint motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

## Case 3: Rotate and Move

Transforms follow Blender-style keyboard flow:

```text
G X 1.2 Enter
R Z 30 Enter
```

Supported behavior:

- `G`: move selected atoms.
- `R`: rotate selected atoms.
- `X`, `Y`, `Z`: lock transform axis in transform mode.
- Numeric input: exact displacement or angle.
- Left click or `Enter`: confirm.
- `Esc`: cancel.
- Optional move increment in Angstrom.
- Optional rotate increment in degrees.
- Rotate pivots: selection center, global origin, or unit-cell center.
- Cell-boundary commensurate-angle guides for axis-locked 2D rotation.
- Optional magnetic snapping to low-strain integer-supercell matches.

![Rotate mode](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/readme_rotate.png)

Here a ferrocene molecule is used to show a selected cyclopentadienyl ring
rotating about the X axis while the rest of the molecule remains in place:

![Ferrocene X-axis rotate](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_rotate_x.gif)

For axis-locked rotation, the colored axis guide is drawn through the active
pivot. If the pivot is the origin, the axis passes through the origin; if the
pivot is the selection center of mass, it passes through that COM.

For periodic 2D cells, enable `Commensurate guide` and use `R` followed by an
axis. v_ase compares integer supercell boundaries after removing their best
rigid rotation, then draws candidate rays and keeps their angles in a compact
`CELL MATCHES` strip that stays readable from every camera direction. The
active ray is labelled in the viewport, while the Structure panel reports its
principal boundary strain and area multiplier. `Magnetic angle snap` can pull the
rotation into a candidate within a configurable angular range without blocking
any other angle; the unchanged `0 deg` identity is always a valid snap target.
Hexagonal cells include the standard `21.7868 deg`,
`13.1736 deg`, and `1.0501 deg` commensurate series. The `1.0501 deg` carbon
marker is a TBG geometric reference near the electronic magic-angle regime,
not an electronic-energy calculation. Equations and references are in the
[cell-aware rotation note](docs/unit_cell_aware_rotate.md).

## Case 4: Bonds, Periodicity, and Supercells

Bonding can be automatic, label-pair based, or manually specified.

- Auto cutoff uses covalent radii.
- By default, bonds are drawn only when both endpoint images lie inside the
  currently displayed cell or supercell. Internal replica boundaries remain
  bonded; only the outer boundary of the displayed supercell clips the bond.
  This avoids cylinders ending at invisible image atoms.
- `Periodic image bonds` enables minimum-image distances and draws bonds toward
  neighboring-cell images. This mirrors [VESTA's boundary-search
  distinction](https://jp-minerals.org/vesta/en/doc/VESTAch8.html) between
  keeping a search inside the boundary and explicitly searching atoms beyond it.
- `Pairwise cutoff` exposes pair-specific `rcut` rows keyed by editable labels,
  so `Cu_surface-Cu_bulk` remains distinct even though both atoms are Cu. A
  cutoff of `0` disables that label pair immediately.
- `Manual pair` accepts explicit atom-index pairs such as `0-1, 1-2`.
- During interactive G/R previews, auto and pairwise-cutoff pairs are re-inferred
  immediately. Manual pair topology remains fixed while its cylinders follow the
  moving atoms.
- Bond settings persist across transform commits, frame changes, structure
  refreshes, and atom-label edits.
- Bond appearance supports adjustable thickness, a lit 3D cylinder or
  camera-facing flat ribbon, and either one custom color or a midpoint split
  using the colors of the two bonded atoms. Custom and split colors are applied
  to the rendered bond materials, and the same settings are used by image,
  video, and Blender exports.
- Edited control values commit consistently when you press `Enter`, press
  `Tab`, or move focus to another control.
- Supercell preview shows replicas with exactly the same atom material, color,
  and lighting response as the source cell in both operating modes, plus
  repeated unit-cell lines and continuous bonds across every internal replica
  boundary. Bond clipping follows the outer displayed-supercell boundary rather
  than each source-cell boundary. In the default visualization mode, replicas
  support click, Shift-click, box selection, `Ctrl+A`, hover metadata, and
  displayed-coordinate measurements. In interactive mode they remain
  inspection-only and cannot enter an atom edit.
- `Set Supercell as Cell` converts the preview into real editable atoms.
- `Cell Transform` accepts a full integer `make_supercell(P)` matrix.

For 2D periodic supercell/twist workflows, the cell transform applies:

```text
H' = P H
```

to every trajectory frame. Non-periodic axes are protected from accidental
mixing, tilting, or repetition.

## Case 5: Trajectories

Multi-frame `Atoms` lists and ASE-readable trajectory files can be played as a
movie.

```bash
v_ase gui relaxation.traj
v_ase gui movie.extxyz --index :
```

Controls:

- frame slider updates live while dragging
- play/pause button
- `Space`: play or pause
- FPS control updates immediately while playback is running
- Skip control advances by `skip + 1` frames per playback tick while preserving
  the selected FPS
- export image and export video

## Case 6: Custom Atom Types in extxyz and LAMMPS

Some workflows store type labels such as `H_type5`, `O_type2`, or `Si_type1`
inside the `species` column. ASE itself cannot treat these strings as chemical
elements, so v_ase reads them as GUI atom types while mapping them internally to
valid ASE base elements.

Example extxyz line:

```text
H_type5 82.30128 7.97802 11.47478
```

In v_ase:

- ASE backend uses base element `H`.
- GUI labels remain `H_type5`.
- default color and radius follow the ASE TYPE (`H`, `O`, and so on), independent
  of the custom label. Appearance still provides explicit per-label overrides.
- Appearance radius controls are grouped by `H_type5`, `O_type2`, etc.
- Bond cutoff pair tables also use the preserved type labels.

For LAMMPS dump/data files, integer type ids are kept as GUI labels. If the type
id is a valid atomic number, v_ase uses that element internally for default
colors and radii:

- `type=1` -> backend `H`, GUI label `1`
- `type=8` -> backend `O`, GUI label `8`
- `type=14` -> backend `Si`, GUI label `14`

If a type id is outside the periodic table range, v_ase keeps the raw label and
uses ASE-valid `H` internally so the structure can still be opened.

## Case 7: Default Repulsion Calculator

If an input `Atoms` object already has a calculator, v_ase preserves and uses
that calculator. This includes `SinglePointCalculator` results loaded from
trajectory-style files and any calculator attached by the user before calling
`view()`.

In the default lightweight visualization mode, v_ase does not attach a fallback
calculator and does not show calculator device controls. This keeps large-file
inspection focused on rendering, bonding, supercell preview, wrapping, and
export.

In `--interactive`, if no calculator is attached, v_ase installs a default soft
repulsion calculator. The model applies harmonic pair repulsion below
covalent-radius contact thresholds, so Relax can remove close contacts without
requiring an external calculator. The top-right calculator controls are enabled
only for this default calculator:

- `DEVICE`: `CPU` by default; `CUDA` is available when torch and CUDA are
  available in the current Python environment.
- `CPU`: number of CPU threads for torch CPU execution. The default is 4, capped
  by the machine CPU count.

Torch is intentionally not listed as a required dependency. If torch is absent,
the repulsion calculator uses a NumPy implementation. Installing torch can make
the default repulsion model faster, especially with CUDA hardware, but other ASE
calculators remain fully user-defined and are not affected by these controls.

The repulsion calculator is also available as a normal ASE calculator from the
public Python API:

```python
from v_ase.calculators import RepulsionCalculator

atoms.calc = RepulsionCalculator(device="cpu", cpu_threads=4)
```

Convenience aliases are also provided for scripts that prefer shorter or
compatibility-oriented imports:

```python
from v_ase import RepulsionCalculator
from v_ase.calculator import RepulsionCalculator
from v_ase.repulsion import RepulsionCalculator
```

`Conditioner` is kept as an alias for the same calculator class, matching the
reference model naming while still behaving like an ASE `Calculator`.

During relaxation, structure updates stream to the browser. In `--interactive`,
if atoms are moved while relaxation is running, the current relaxation is stopped
and restarted from the edited coordinates. The default visualization mode keeps
atom editing and repulsion-calculator controls out of the UI.

## Case 8: Export

From the right panel:

- `Export POSCAR`
- `Export ASE Pickle`
- `Export Blender`
- `Export 3DM`
- `Export OBJ`
- `Preview Area`
- `Export Image`
- `Export Video`

Image export provides resolution, transparency, grid, axes, atom smoothness,
and render-lighting controls. Atomic scale is deliberately controlled from
`Display > Viewport`, where changing `px/Å` zooms the visible structure immediately.
The accompanying viewport-span readout gives the visible width and height in Å.
This mirrors VESTA's treatment of magnification as a property of the live 3D view,
rather than a value hidden inside raster export. `Current viewport` preserves
the live camera direction, target, and magnification, then uses the requested
output aspect ratio as a centered crop gate. The image always fills the output
without letterboxing. `Atomic scale from View` uses the current global pixels per
Angstrom (`px/Å`), so the same value produces the same physical scale across
different structures. For an output width `W` and scale `s`, the horizontal
field is `W / s` Å. In perspective projection this scale is defined at the camera
target plane; orthographic export has uniform scale at every depth.

Set `image W` and `image H`, then enable `Preview Area` to see the actual export
camera rendered inside a fixed screen-space frame. The frame uses the requested
pixel aspect ratio and the same full-frame camera projection, lighting,
grid/axes policy, and atom-surface quality path as PNG export. Zooming
changes the apparent atom size inside the frame while the frame remains fixed.

`Atom smoothness` selects the export sphere preset, and `Smoothness scale`
multiplies its tessellation from `0.5×` to `2.0×`. Both affect only the PNG render,
so a large scene can stay lightweight in the viewport while a publication image
uses smoother atom surfaces. Studio Sun and soft-shadow images can likewise be
exported without changing the viewport from Modeling mode.

`Export ASE Pickle` writes the current modified `Atoms` object for later Python
use. Coordinates, chemical types, v_ase labels, cell/PBC, constraints, tags,
charges, magnetic moments, and portable atom arrays remain attached. A
calculator is included only when it is a still-valid `SinglePointCalculator`;
live Python calculator implementations are deliberately omitted. The pickle
does not contain camera, lighting, bonds, atom appearance, or other visual state.

Blender export downloads `v_ase_blender_scene.py`:

```bash
blender --python v_ase_blender_scene.py
```

`Optimized instances` is the default Blender atom mode. It emits one editable
point mesh per visual label and uses Geometry Nodes to instance smooth
icospheres, avoiding thousands of Python object-creation calls. Trajectories
become point-mesh shape keys, bonds are grouped into multi-spline curves or
combined flat meshes by material, and the unit cell is one multi-spline object.
The `Individual objects` option remains available when every atom must be a
separate Blender object.

Studio lighting is exported as a true Blender `SUN` parented to a source Empty
and aimed at a target Empty. Source position, target-derived direction, RGB
color, and numeric energy match the v_ase controls. Atom, bond, and cell colors
use standard Principled BSDF nodes, so they remain colored in Blender Rendered
mode. The active camera and projection are also reproduced.

The Python scene format works even when Blender is not installed in the Python
environment running v_ase. Run the script in Blender and save it once to obtain
a native `.blend`.

`Export 3DM` is intended for editable CAD handoff. It writes one native sphere
per displayed atom, editable Brep cylinders or flat meshes for bonds, and unit
cell curves on separate `Atoms`, `Bonds`, and `Unit Cell` layers. Coordinates
and document units are Angstrom, label/element/index/cell-offset metadata is
attached to every atom object, and the current label colors, radii, bond style,
bond thickness, split/custom colors, visibility, and supercell preview are
preserved. Install the optional backend first:

```bash
python -m pip install "v_ase-gui[rhino]"
```

`Export OBJ` is dependency-free. Because standard OBJ stores color definitions
in a companion MTL file, v_ase downloads `v_ase_obj_scene.zip` containing both
`v_ase_scene.obj` and `v_ase_scene.mtl`. Extract both files into the same
directory before import. Atoms and bond segments are separately named objects,
with smooth mesh normals, configured radii/thickness/colors, visible supercell
repetitions, and unit-cell line objects. OBJ is a static geometry interchange
format: it does not retain the camera, Sun rig, trajectory animation,
constraints, or Blender instancing semantics. Use Blender export or `.vase`
when those features matter.

## Case 9: Save and Restore

The Export & Save workspace separates structure export from two save operations:

- **ASE Pickle (`.pkl`)** stores the current ASE structure for Python reuse:
  coordinates, chemical types and labels, cell/PBC, constraints, portable atom
  arrays, and valid `SinglePointCalculator` results. It excludes visualization
  settings, the rest of a loaded trajectory, and arbitrary calculator objects.

- **Visual Settings (`.json`)** stores reusable presentation state: bond mode,
  pairwise cutoffs, manual pairs, bond material, label colors/radii/visibility,
  atom smoothness and anti-aliasing, camera/projection, grid/axes/cell,
  supercell preview, and Sun source/target/intensity. It does not store atomic
  coordinates. When applied to another structure, matching labels reuse saved
  values, absent labels are ignored, and newly encountered labels and bond pairs
  receive defaults.
- **v_ase Project (`.vase`)** stores the complete current project: all loaded
  trajectory frames, current frame, edited or wrapped coordinates, cell, PBC,
  ASE constraints, atom labels, portable per-atom arrays, JSON-compatible frame
  metadata, cached standard calculator results, and the complete visual setup.

Open a saved project directly:

```bash
v_ase gui research_state.vase
```

The same project can be selected from the browser **Open** command after starting
an empty workspace with `v_ase gui`. A `.vase` load replaces the complete working
state. By contrast, opening an ordinary structure or trajectory while a document
is already active preserves the current visual settings and camera; matching
labels retain their presentation values while missing/new labels are safely
dropped/defaulted.

`.vase` is a validated ZIP container and does not unpickle arbitrary Python
objects. Cached standard ASE results are restored through
`SinglePointCalculator`. The built-in v_ase repulsion calculator is safely
reconstructed from its numeric/string configuration so relaxation can resume;
an arbitrary external calculator object is intentionally not embedded because
it may contain executable code or machine-specific state.

### Desktop Integration

The file format is ready for OS association, but `pip install` does not register
a universal double-click handler. A packaged desktop launcher is required:

- macOS: an app bundle declaring the document type with
  [`CFBundleDocumentTypes`](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundledocumenttypes).
- Windows: an installer registering a `.vase` ProgID and open command as
  described by [Microsoft file-type registration](https://learn.microsoft.com/en-us/windows/win32/shell/how-to-register-a-file-type-for-a-new-application).
- Linux desktops: a MIME definition, `.desktop` launcher, and association under
  the [freedesktop MIME-apps specification](https://specifications.freedesktop.org/mime-apps/latest-single/).

macOS Finder Quick Look also requires a signed Quick Look preview extension for
the custom content type. Apple supports view-controller or data-based custom
previews, but an installed Python wheel alone cannot register one. The `.vase`
archive therefore does not embed executable HTML; a future macOS app can add a
read-only rotatable preview through Apple's
[`QLPreviewingController`](https://developer.apple.com/documentation/quicklookui/qlpreviewingcontroller).

## Python API

```python
from v_ase import view_edit, view_file

edited_atoms = view_edit(
    atoms,
    notebook=False,
    block=True,
    show_cell=True,
    show_axes=True,
    show_bonds=False,
    respect_constraints=True,
    allow_relax=True,
    return_mode="atoms",
)

view_file("trajectory.extxyz")
```

`return_mode` can be:

- `"atoms"`: edited ASE `Atoms`
- `"positions"`: edited `Nx3` positions array
- `"none"`: no return value

## Controls

| Input | Action |
| --- | --- |
| Left click | Select atom or confirm transform |
| Shift + left click | Add/remove selection |
| Left drag | Box select |
| Middle drag | Orbit viewport |
| Shift + middle drag | Pan viewport |
| Mouse wheel | Zoom |
| `G` | Move selected atoms or the selected Sun handle |
| `R` | Rotate selected atoms or rotate the Sun target around its source |
| `X`, `Y`, `Z` | Align view in select mode, lock axis in transform mode |
| Number keys | Numeric transform input |
| `Enter` | Confirm transform |
| `Esc` | Cancel transform; otherwise close an open control panel and return focus to the viewport |
| `Ctrl+C` / `Ctrl+V` | Copy / paste atoms |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Delete` / `Backspace` | Delete selected atoms |
| `Space` | Play/pause trajectory |
| `Tab` | Open the control panel while it is collapsed; inside an open panel it remains normal form navigation |
| Sun source + `G` | Move the complete Sun rig (source and target) |
| Sun target + `G` | Aim the Sun by moving only its target |
| Either Sun handle + `R` | Rotate the target around the source |

## Notes

- The local editor server binds to `127.0.0.1`.
- Relaxation uses the calculator already attached to the `Atoms` object. In
  `--interactive`, v_ase adds its default soft repulsion calculator only when
  no calculator is attached; visualization mode adds no calculator.
- Torch is optional. It is never required by `pip install v_ase-gui`, but when
  available it can accelerate the default repulsion calculator on CPU or CUDA.
- POSCAR exports a VASP structure. ASE Pickle exports the current `Atoms` with
  structural metadata and constraints; only valid `SinglePointCalculator`
  results are carried, and visualization settings are excluded.
- Visual Settings JSON is structure-independent presentation state. `.vase` is
  the full portable project state; it stores cached standard calculator results
  but not arbitrary executable calculator objects or undo history.
- The bundled browser UI is local-first; no Node.js build step is required.
