<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`v_ase` combines ASE's convenient terminal and Python workflow with flexible
3D structure manipulation in one local visualizer. It opens atomic structures
and trajectories in a browser, remains lightweight for viewing large systems,
and enables direct atom editing when requested.

![v_ase overview](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_overview.png)

## Install

From PyPI:

```bash
python -m pip install v_ase-gui
```

From GitHub:

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e .
```

No Node.js installation is required.

## Open

Start an empty workspace or open a file directly:

```bash
v_ase gui
v_ase gui FILE
```

Examples:

| Input | Command |
| --- | --- |
| POSCAR | `v_ase gui POSCAR` |
| VASP structure | `v_ase gui structure.vasp` |
| XYZ trajectory | `v_ase gui trajectory.extxyz` |
| ASE trajectory | `v_ase gui relaxation.traj` |
| Saved v_ase project | `v_ase gui project.vase` |

The terminal is released when the v_ase browser document closes.

**Open** immediately displays the operating system file picker. After choosing
a file, select its reader, frame range, and how it should be opened.

The top-bar **Open** command offers three actions:

| Action | Result |
| --- | --- |
| Replace this tab | Replace the current structure or trajectory |
| Add to trajectory | Append the selected frames to the current movie |
| Open in new tab | Open an independent document beside the current tab |

Replacing a tab or opening a new tab with `.vase` restores the complete saved
project. Adding `.vase` to a trajectory imports its structures only and keeps
the active tab's camera, appearance, bonds, lighting, and other visual settings.
New labels and chemical types are added to the existing Appearance and
pairwise-bond controls automatically.

### View And Edit Modes

**View** is the default. It is optimized for visualization, trajectories,
measurements, bonds, supercells, appearance, wrapping, and export:

```bash
v_ase gui trajectory.extxyz
```

Use the **View / Edit** switch in the top bar at any time. **Edit** enables
coordinate transforms, atom creation/deletion, constraints, undo, copy/paste,
and relaxation. To start directly in Edit:

```bash
v_ase gui structure.vasp --interactive
```

The current structure, trajectory frame, camera, labels, appearance, bonds,
and selection remain in place during a mode change. If individual atoms have
different visual materials, switching to View creates numbered labels only for
those visual variants. Position-only edits stay in the same label group.

### Multiple Documents

Use **+** immediately after the document tabs to create an empty independent
tab. Tabs resize as documents are added. Each tab owns its structure or
trajectory, camera, selection, calculator, history, display settings,
relaxation state, and `.vase` project. Inactive tabs pause rendering and movie
playback.

## Controls

| Input | Action |
| --- | --- |
| Left click | Select an atom or confirm a transform |
| Shift + left click | Add or remove selection |
| Left drag | Box selection |
| Middle drag | Orbit |
| Shift + middle drag | Pan |
| Wheel | Zoom |
| `G` | Move selected atoms |
| `R` | Rotate selected atoms |
| `X`, `Y`, `Z` | Lock a transform axis; otherwise align the camera |
| Number keys | Enter an exact distance or angle during `G`/`R` |
| `Enter` / left click | Confirm a transform |
| `Esc` / right click | Cancel a transform |
| `Ctrl+C`, `Ctrl+V` | Copy and paste atoms |
| `Ctrl+Z`, `Ctrl+Shift+Z` | Undo and redo structure or camera changes |
| `Delete` / `Backspace` | Delete selected atoms |
| `Space` | Play or pause the selected timeline |
| `Left Arrow` / `Right Arrow` | Previous or next frame in the selected timeline |
| `Tab` / `Esc` | Open the collapsed control panel |
| `Esc` | Close the open panel and return focus to the viewport |

The **?** button shows the complete shortcut list. The six camera buttons are
ordered as up/down, left/right, and counterclockwise/clockwise roll. The first
four are 3D orbit controls; the last two rotate in the screen plane. They change
only the view by the selected angle, never the atomic coordinates.

## Trajectories

Multi-frame inputs add a timeline below the viewport. Frame scrubbing updates
immediately, FPS changes apply during playback, and **Skip** advances by
`skip + 1` frames per tick. Bond settings, appearance, and supercell display
remain active across all frames.

In interactive mode, relaxation creates a separate optimization timeline.
When source and relaxation trajectories both exist, choose **Source frames** or
**Relaxation · calculator** from the timeline selector. Playback, `Space`, and
the Left/Right Arrow keys control only the selected timeline; the other
timeline remains visible in a separate row.

## Constraints

ASE constraints remain authoritative during interactive transforms while
**Apply constraints** is enabled.

### FixedLine

The atom moves only along its permitted line.

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

```bash
v_ase gui examples/readme_scene_assets/fixedline.traj --show-bonds --interactive
```

### FixedPlane And FixScaled

`FixedPlane` atoms move within their displayed plane. VASP selective dynamics
read as `FixScaled` are displayed from their allowed fractional directions.

![FixedPlane movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

```bash
v_ase gui examples/readme_scene_assets/fixedplane.traj --show-bonds --interactive
```

### FixAtoms

Fixed atoms keep their element color and use a distinct constrained surface
treatment. They remain visible without looking selected.

### Hookean

Hookean constraints show the inactive cutoff, threshold, and active spring
state. The spring engages only after the constrained distance passes `rt`.

![Hookean constraint](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.png)

![Hookean motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

```bash
v_ase gui examples/readme_scene_assets/hookean.traj --show-bonds --interactive
```

## Editing And Measurement

Move and angle increments, transform pivot, constraints, cell transforms,
supercells, and wrapping are available from **Structure**. **Translate atoms**
moves every frame while keeping the cell fixed; enter either Cartesian values
in Angstrom or fractional cell coordinates, then select **Apply Translation**.
Axis-locked rotation can show low-strain commensurate cell-boundary angles and
optionally snap to them.

![Rotate mode](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_rotate.png)

![Ferrocene rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_rotate_x.gif)

One through four ordered selections are marked `a1` through `a4`. The viewport
shows point information, `a1-a2` distance, the `a1-a2-a3` angle centered on
`a2`, or the signed `a1-a2-a3-a4` torsion. Distances report direct and
minimum-image-convention (MIC) values; selecting a displayed supercell image
also reports its unit-cell-mapped distance. Angles and torsions use the
displayed coordinates without an additional MIC value. Larger selections show
the total followed by counts for each atom label. Hovered-atom metadata is
displayed separately.

## Structure, View, And Rendering

The control panel has four workspaces: **Inspect**, **Structure**, **View**, and
**Export**. **Structure** keeps related scientific controls together:
**Atoms**, **Cell**, **Transform**, **Constraints**, **Bonds**, and **Relax**.
Its section bar stays visible while scrolling.

**View** provides:

- orthographic or perspective projection;
- a true-white viewport background by default, with balanced modeling light
  for clear element colors and a dark background option;
- 3D spheres/cylinders or 2D atoms/flat bonds;
- live atomic scale in pixels per Angstrom;
- unit cell, axes, grid, and overlay controls.

**Structure > Atoms** controls per-label TYPE, label, visibility, color, radius,
material, atom smoothness, and anti-aliasing. New documents use a `0.60x` atom
radius. Material presets are **Standard**, **Metal**, and **Rubber**. In View, a
preset applies to a complete label group. In Edit, selected atoms can use
independent materials and can be merged into an existing label by entering that
exact label. Chemical TYPE remains synchronized with ASE while labels control
visual grouping.

The top-bar renderer switches among **Modeling**, **Studio Sun**, and
**Sun + Soft Shadow**. Sun intensity, source, target, and viewport handles are
editable.

**Structure > Bonds** supports automatic element-radius inference, explicit
label-pair specifications, and manual atom-index pairs. Each pair specification
has an enable checkbox plus minimum and maximum distances in Angstrom. Changes
apply immediately; no separate apply step is required. Thickness, cylinder/flat
style, custom color, and midpoint-split atom colors are configurable. New
documents use a `0.25 A` bond diameter. Interactive bonds form and break during
atom transforms.

![Bond pair specifications](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_bonds.png)

## Export And Save

| Option | Contents |
| --- | --- |
| Export POSCAR | Current atomic structure in VASP format |
| Export ASE Pickle | Current ASE `Atoms`, labels, constraints, arrays, and valid `SinglePointCalculator` results |
| Export Image | PNG using the Preview Area camera and crop |
| Export Video | Complete trajectory as MOV or AVI |
| Export Blender | Optimized Python scene with atoms, bonds, camera, Sun, optional cell, and trajectory animation |
| Export 3DM | Instanced Rhino geometry, metadata, and saved views |
| Export OBJ | OBJ/MTL plus camera and metadata JSON in a ZIP |
| Save Project | Self-contained `.vase` structure/trajectory and complete visual state |
| Save Settings | Reusable appearance, bonds, camera, lighting, quality, and supercell JSON |

**Preview Area** uses the exact image/video aspect ratio, camera, crop, display,
and lighting profile used for export. The frame stays fixed while orbit and zoom
change the structure inside it. Unit cell, grid, axes, background, atom
smoothness, and renderer are independently selectable for output.

When the browser supports the system save picker, v_ase asks for the destination
before generating a structure, image, video, Blender, Rhino, OBJ, project, or
settings export. Canceling the picker cancels the export before rendering or
encoding starts.

`.vase` files are self-contained; reopening one does not require the original
structure file. Opening an ordinary structure from an active workspace keeps
the current visual settings. Opening a `.vase` project restores its saved state.

Rhino export requires:

```bash
python -m pip install "v_ase-gui[rhino]"
```

OBJ export has no optional dependency.

## Python

```python
from ase.build import molecule
from v_ase.visualize import view

atoms = molecule("H2O")
view(atoms)  # lightweight visualization mode
```

To edit and return an ASE object:

```python
edited = view(atoms, viz_only=False)
print(edited.positions)
```

`view()` works with one `Atoms`, a sequence of frames, or a supported file path.
`view_edit()` remains as a compatibility alias for interactive mode.

## File Formats

File type is normally detected automatically. Common inputs include POSCAR,
CONTCAR, VASP files, XDATCAR, `vasprun.xml`, XYZ/extxyz, ASE `.traj`, LAMMPS
dump/data files, and `.vase`.

Repeated POSCAR/CONTCAR species blocks remain separate visual groups. For
example, `O Cu O` with counts `1 14 5` appears as `O1`, `Cu`, and `O2`.
The ASE chemical symbols remain unchanged, so calculations and exports continue
to use the correct elements.

For an ambiguous filename, select the reader explicitly:

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
