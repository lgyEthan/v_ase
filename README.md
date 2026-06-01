# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.python.org/pypi/v_ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.python.org/pypi/v_ase-gui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`v_ase` is built around convenience and flexibility. It keeps the
low-friction workflow of `ase gui`: open ASE-readable structures and
trajectories directly from a terminal or Python session. It adds the flexibility
of a Blender-like 3D visualizer: select, move, rotate, copy, delete, wrap, and
export atoms directly in an interactive browser viewport.

The goal is to put the practical convenience of ASE and the hands-on flexibility
of a 3D molecular editor in the same tool.

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
v_ase gui POSCAR
v_ase gui structure.vasp
v_ase gui movie.extxyz
v_ase gui relaxation.traj
```

The viewer opens locally in your browser. Middle mouse tumbles the camera,
left click and box drag select atoms, `G` moves atoms, `R` rotates atoms,
`X/Y/Z` lock axes, numeric input gives exact transforms, and trajectory files
show playback controls for frame-by-frame movie inspection.

![v_ase overview](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/readme_overview.png)

## Highlights

- `v_ase gui FILE` command-line workflow for POSCAR, VASP, extxyz, traj, and
  other ASE-readable files.
- Python API for notebooks and scripts: `from v_ase.visualize import view`.
- Blender-like viewport interaction: middle-mouse orbit, shift-middle pan,
  wheel zoom, click/box selection, `G` move, `R` rotate, axis locking, numeric
  transforms, `Enter`, `Esc`, copy/paste/undo/delete.
- ASE constraint-aware editing and visualization:
  `FixAtoms`, `FixCartesian`, `FixedLine`, `FixedPlane`, `FixScaled`, and
  `Hookean`.
- Hookean constraints are visualized as threshold-aware hook/latch springs.
- Trajectory playback with live frame slider, FPS control, image export, and
  video export.
- Periodic bonds, element-pair cutoff tables, manual bond pairs, supercell
  preview, `make_supercell(P)` cell transform, and wrap atoms into cell.
- Custom extxyz atom type labels such as `H_type5` are preserved for GUI type
  settings even when ASE cannot parse them as real elements.
- Export POSCAR, pickle, PNG image, WebM video, and Blender Python scene script.

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

## Quick Start

Open a structure file:

```bash
v_ase gui POSCAR
v_ase gui structure.vasp
v_ase gui trajectory.extxyz
v_ase gui relaxation.traj
```

The direct file form also works:

```bash
v_ase POSCAR
```

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
v_ase gui POSCAR --output edited.vasp
v_ase gui POSCAR --no-block
```

## Case 1: Selection, FixedLine, and FixedPlane

Selected atoms get yellow Blender-style outlines. Fixed atoms are dimmed, and
selected `FixedLine` / `FixedPlane` atoms show geometric guides so the allowed
movement is visible before committing coordinates.

`FixedLine` is shown as a Li ion moving along a carbon nanotube channel. The ion
can slide parallel to the tube axis, but not leave the channel direction:

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

`FixedPlane` is shown as a Li ion moving over a Cu(111) surface. The motion is
restricted to the surface-parallel XY plane, so it reads as surface diffusion
rather than rotation:

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
the spring becomes active.

![Hookean threshold-aware spring](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/readme_hookean.png)

Example:

```python
from ase.build import molecule
from ase.constraints import Hookean
from v_ase.visualize import view

atoms = molecule("H2O")
atoms.set_constraint(Hookean(1, 2, rt=1.8, k=5.0))
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
- Optional bond-strain guard for rejecting excessive periodic bond distortion.

![Rotate mode](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/readme_rotate.png)

Here a ferrocene molecule is used to show a selected cyclopentadienyl ring
rotating about the X axis while the rest of the molecule remains in place:

![Ferrocene X-axis rotate](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_rotate_x.gif)

For axis-locked rotation, the colored axis guide is drawn through the active
pivot. If the pivot is the origin, the axis passes through the origin; if the
pivot is the selection center of mass, it passes through that COM.

## Case 4: Bonds, Periodicity, and Supercells

Bonding can be automatic, element-pair based, or manually specified.

- Auto cutoff uses covalent radii and respects periodic minimum-image distances.
- Element-pair mode exposes pair-specific `rcut` rows.
- Manual mode accepts pair strings such as `Na-Cl: 3.2` or `0-1, 1-2`.
- Supercell preview shows repeated atoms and repeated unit-cell lines.
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
- export image and export video

## Case 6: Custom Atom Types in extxyz

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
- type-specific color variants are generated.
- Appearance radius controls are grouped by `H_type5`, `O_type2`, etc.
- Bond cutoff pair tables also use the preserved type labels.

## Case 7: Export

From the right panel:

- `Export POSCAR`
- `Export Pickle`
- `Export Blender`
- `Export Image`
- `Export Video`

Blender export downloads `v_ase_blender_scene.py`:

```bash
blender --python v_ase_blender_scene.py
```

The generated scene keeps atoms and constraint graphics as editable Blender
objects where practical.

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
| `G` | Move selected atoms |
| `R` | Rotate selected atoms |
| `X`, `Y`, `Z` | Align view in select mode, lock axis in transform mode |
| Number keys | Numeric transform input |
| `Enter` | Confirm transform |
| `Esc` | Cancel transform |
| `Ctrl+C` / `Ctrl+V` | Copy / paste atoms |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Delete` / `Backspace` | Delete selected atoms |
| `Space` | Play/pause trajectory |

## Notes

- The local editor server binds to `127.0.0.1`.
- Relaxation uses the calculator already attached to the `Atoms` object.
- POSCAR export stores structural data. Pickle export can include the ASE object;
  calculators may not always be pickleable.
- The bundled browser UI is local-first; no Node.js build step is required.
