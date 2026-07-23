<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`v_ase` is a local 3D viewer and editor for atomic structures and trajectories.
Open ASE-compatible files from the terminal or Python, inspect large systems,
edit atoms when needed, and export publication-ready images, movies, and 3D
scenes.

![v_ase overview](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_overview.png)

## Install

### From PyPI

```bash
python -m pip install v_ase-gui
```

### From GitHub

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e .
```

No Node.js installation is required.

## Start

There are two command forms:

```bash
v_ase gui
v_ase gui [structure-filename]
```

| What you want to open | Command |
| --- | --- |
| Empty workspace with an **Open** button | `v_ase gui` |
| POSCAR or another static structure | `v_ase gui POSCAR` |
| VASP structure | `v_ase gui structure.vasp` |
| XYZ or extended XYZ trajectory | `v_ase gui trajectory.extxyz` |
| ASE trajectory | `v_ase gui relaxation.traj` |
| Saved v_ase project | `v_ase gui project.vase` |

The terminal waits while the viewer is open and becomes available again when
the browser tab is closed.

### View And Interactive Modes

The default mode is optimized for viewing, trajectory playback, measurements,
bonds, appearance, supercells, wrapping, and export:

```bash
v_ase gui trajectory.extxyz
```

Use interactive mode to move, rotate, create, delete, copy, paste, or relax
atoms:

```bash
v_ase gui structure.vasp --interactive
```

## Controls

| Input | Action |
| --- | --- |
| Left click | Select an atom or confirm a transform |
| Shift + left click | Add or remove atoms from the selection |
| Left drag | Box selection |
| Middle drag | Orbit the view |
| Shift + middle drag | Pan |
| Wheel | Zoom |
| `G` | Move selected atoms |
| `R` | Rotate selected atoms |
| `X`, `Y`, `Z` | Lock a transform axis; outside a transform, align the view |
| Number keys | Enter an exact distance or angle during `G` or `R` |
| `Enter` / left click | Confirm a transform |
| `Esc` / right click | Cancel a transform |
| `Ctrl+C`, `Ctrl+V`, `Ctrl+Z` | Copy, paste, undo |
| `Delete` / `Backspace` | Delete selected atoms |
| `Space` | Play or pause a trajectory |
| `Tab` | Open the control panel when it is collapsed |
| `Esc` | Close the open control panel and return focus to the viewport |

The **?** button in the top bar shows the same shortcut reference inside the
app.

## Trajectories

Multi-frame files receive a timeline at the bottom of the viewport. You can:

- drag the frame slider for immediate frame updates;
- play or pause with `Space`;
- set playback FPS and frame skip;
- keep bond cutoffs and appearance settings across every frame;
- run relaxation in interactive mode and inspect its optimization path;
- export the complete loaded trajectory as a movie.

### Export Video

Open **Export & Save**, select **Export Video**, then choose:

- `MOV` with H.264 video or `AVI` with MPEG-4 video;
- output width, height, and FPS;
- current viewport framing or a fixed atomic scale in px/Å;
- atom smoothness;
- grid and axes visibility;
- renderer, Sun brightness, position, and target.

Every trajectory frame is rendered. The movie uses the exact camera, crop,
lighting, and atom styling shown by **Preview Area**. Movie backgrounds are
white; transparent video export is not used.

## Constraints

Constraints remain active during interactive transforms when **Apply
constraints** is enabled. Disable that switch when unrestricted editing is
required.

### FixedLine

A constrained atom moves only along its permitted direction. The guide remains
visible in the viewport and becomes more prominent when the atom is selected.

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

Example:

```bash
v_ase gui examples/readme_scene_assets/fixedline.traj --show-bonds --interactive
```

### FixedPlane And FixScaled

`FixedPlane` movement is limited to the displayed plane. VASP selective
dynamics read as `FixScaled` are shown according to their allowed fractional
directions.

![FixedPlane movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

Example:

```bash
v_ase gui examples/readme_scene_assets/fixedplane.traj --show-bonds --interactive
```

### FixAtoms

Fixed atoms use a distinct surface treatment while keeping their element
color. They remain recognizable without being confused with the yellow
selection outline.

### Hookean

Hookean constraints show their threshold and active spring state. The spring
engages only after the constrained distance passes its cutoff.

![Hookean constraint close-up](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.png)

![Hookean constraint motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

Example:

```bash
v_ase gui examples/readme_scene_assets/hookean.traj --show-bonds --interactive
```

## Atom Editing

Interactive mode supports direct selection, move, and rotate operations. Move
and angle increments can be set in the control panel, and the live transform
readout reports the displacement or rotation applied so far.

![Rotate mode](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_rotate.png)

![Ferrocene rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_rotate_x.gif)

Example:

```bash
v_ase gui examples/readme_scene_assets/ferrocene.traj --show-bonds --interactive
```

## Display And Measurement

The control panel provides:

- orthographic or perspective projection;
- live atomic scale in px/Å;
- Modeling, Studio Sun, and Sun + Soft Shadow rendering;
- editable Sun brightness, source, and target;
- per-label element type, name, visibility, color, and radius;
- selectable sphere smoothness and anti-aliasing;
- atom-index, element, center, distance, and angle measurements;
- unit-cell display, wrapping, and periodic supercell replication.

## Bonds

Enable **Show bonds** and choose automatic, pairwise-cutoff, or manual bonds.
Pairwise cutoffs use atom labels, so chemically distinct labels can have
different cutoffs even when they share one element type. A cutoff of `0`
disables that pair.

Bond thickness, cylinder or flat style, one custom color, or split endpoint
colors can be selected. In interactive mode, automatic and pairwise bonds form
and break while atoms move. Supercell bonds are repeated across the displayed
supercell.

## Export And Save

| Option | Result |
| --- | --- |
| Export POSCAR | Current atomic structure in VASP format |
| Export ASE Pickle | ASE `Atoms` data, labels, constraints, and valid `SinglePointCalculator` results |
| Export Image | PNG using the requested dimensions and Preview Area crop |
| Export Video | Complete trajectory as MOV or AVI |
| Export Blender | Python scene script with atoms, cell, bonds, camera, and Sun settings |
| Export 3DM | Editable Rhino geometry with atom and bond metadata |
| Export OBJ | OBJ/MTL scene bundle in a ZIP file |
| Save Project | Complete structure, trajectory, edits, labels, and visual state in `.vase` |
| Save Settings | Reusable appearance, bonds, camera, lighting, quality, and supercell settings in JSON |

Use **Preview Area** before image or video export. Its fixed frame has the exact
output aspect ratio; orbiting or zooming changes the structure inside the frame
without moving the frame itself. Image-dialog changes to dimensions, framing,
grid, axes, transparency, atom smoothness, renderer, and Sun settings update the
preview immediately; PNG export uses that same profile without recomputing it.

Rhino 3DM export needs one optional package:

```bash
python -m pip install "v_ase-gui[rhino]"
```

OBJ export needs no optional dependency.

## Python

```python
from ase.build import molecule
from v_ase.visualize import view

atoms = molecule("H2O")
view(atoms)
```

Interactive mode can return the edited ASE object:

```python
edited = view(atoms, viz_only=False)
print(edited.positions)
```

## Input Formats

File type is normally detected automatically. Common inputs include POSCAR,
CONTCAR, VASP files, XDATCAR, `vasprun.xml`, XYZ, extended XYZ, ASE `.traj`,
LAMMPS dump files, LAMMPS data files, and `.vase` projects.

For a filename without a useful extension, specify the reader:

```bash
v_ase gui ABCD --format POSCAR
v_ase gui ABCD --format XDATCAR
v_ase gui ABCD --format vasprun.xml
v_ase gui ABCD --format lammpstrj
v_ase gui ABCD --format extxyz
v_ase gui ABCD --format data
```

Use `--index :` for all frames, `--index -1` for the last frame, or an integer
for one frame.

## Help

```bash
v_ase --help
v_ase gui --help
```

Report reproducible problems at
[GitHub Issues](https://github.com/lgyEthan/v_ase/issues).
