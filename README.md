<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`v_ase` combines ASE's convenient terminal and Python workflow with the
flexibility of direct 3D structure manipulation. Open structures and
trajectories with one command, inspect or measure them in a local browser,
edit atoms when needed, and export publication or CAD-ready results.

![Phosphorene nanoribbon manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

The example above turns a literature-derived phosphorene nanosheet into a
twisted nanoribbon. Each crystallographic slice is rotated around its own
center of mass in 15 degree steps while bonds remain visible.

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

## Everyday Workflow

| Goal | Action |
| --- | --- |
| Inspect a structure | Middle-drag to orbit, wheel to zoom, left-click to select |
| Edit coordinates | Enter **Edit**, select atoms, press `Esc` to focus the viewport, then use `G` or `R` |
| Measure geometry | Select 2, 3, or 4 atoms in the required order |
| Play a trajectory | Use the bottom timeline or `Space`; FPS and Skip update live |
| Style a figure | Use **Structure > Appearance/Bonding** and **View** |
| Repeat or wrap a cell | Use **Structure > Cell & Replication** |
| Save the whole session | Use **Export > Save Project** to create a self-contained `.vase` |
| Reuse only the visual style | Use **Export > Save Settings** |
| Hand the scene to an AI | Launch with `--for-ai` and provide the bundled agent skill |

> **Viewport tip:** after selecting atoms, press `Esc` to close the control
> panel before using `G` or `R`. The selection is preserved and keyboard focus
> returns to the 3D viewport.

## AI And Agent Use

v_ase exposes atomistic state directly to an AI agent. The agent can read
elements, labels, coordinates, cell, PBC, constraints, trajectory frames,
measurements, camera, bonds, materials, and render settings without repeatedly
interpreting screenshots.

Start a machine-readable session:

```bash
v_ase gui STRUCTURE --for-ai
```

The first output line is a JSON handshake containing:

- the normal GUI URL for human takeover;
- semantic state and command-schema URLs;
- the live `window.v_aseAI` browser API;
- the installed path and HTTP URL for the agent skill.

An agent can configure and verify the structure, camera, lighting, analysis,
and export state, render the final image, then give the same live document back
to the user for manual refinement.

### Teach An Agent v_ase

Use the complete
[v_ase agent skill](https://github.com/lgyEthan/v_ase/tree/main/v_ase/skills/visualizing-atomic-structures-with-v-ase),
not only its first page. The compatibility link
[skills_v_ase.md](https://github.com/lgyEthan/v_ase/blob/main/v_ase/skills_v_ase.md)
resolves to the same canonical skill. The folder contains:

- [SKILL.md](https://github.com/lgyEthan/v_ase/blob/main/v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md):
  triggers, workflow, safety rules, and verification gates;
- `references/semantic-api.md`: supported state, edit, camera, render, and
  export commands;
- `references/workflows-and-examples.md`: complete working recipes;
- `references/safety-and-errors.md`: destructive actions and recovery;
- `references/evaluation.md`: end-to-end tests an agent should run.

For an AI client that supports skill folders, place the entire
`visualizing-atomic-structures-with-v-ase` directory in that client's skills
directory. For example:

```bash
# Codex
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase "$CODEX_HOME/skills/"

# Claude Code, from a project root
mkdir -p .claude/skills
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase .claude/skills/
```

For clients without a skill loader, provide `SKILL.md` and the relevant
one-level `references/` files in the agent context. The contract is
vendor-neutral; it does not require an OpenAI or Anthropic API.

## Structure Manipulation

### Phosphorene Nanoribbon

The main example starts from a puckered black-phosphorene unit cell, repeats it
into a one-layer nanosheet, and rotates each successive crystallographic slice
by 15 degrees around the ribbon axis through that slice's center of mass.

Try the exact assets:

- [flat phosphorene nanosheet](examples/readme_scene_assets/phosphorene_nanosheet.cif)
- [twisted 15 degree nanoribbon](examples/readme_scene_assets/phosphorene_twisted_nanoribbon_15deg.cif)
- [complete manipulation trajectory](examples/readme_scene_assets/phosphorene_twist_15deg.traj)

```bash
v_ase gui examples/readme_scene_assets/phosphorene_nanosheet.cif --interactive
```

To reproduce the operation, select one crystallographic slice, set
**Rotate pivot** to **Selection COM**, press `R`, lock the ribbon axis with
`X`, type `15`, and confirm. Repeat for neighboring slices with the required
signed angle.

The source coordinates are converted directly from the black-phosphorene
cell and positions reported in the
[supporting information of Villegas et al.](https://www.rsc.org/suppdata/c6/cp/c6cp05566d/c6cp05566d1.pdf).
The puckered anisotropic structure is consistent with the black-phosphorus
description in
[Qiao et al., Nature Communications 5, 4475 (2014)](https://www.nature.com/articles/ncomms5475).
This example demonstrates deterministic manipulation; it is not presented as
an energy-minimized nanoribbon.

### Rotation References

Every atom rotation displays three references through the selected pivot:

- **axis line**: the actual rotation axis;
- **neutral start line**: the direction at the moment `R` started;
- **amber current line**: the direction after the current rotation.

For periodic 2D matching, additional cyan candidate lines show low-boundary-
strain commensurate angles. Candidate guides remain visually separate from the
start and current references. Magnetic snapping is optional.

### Graphene/hBN Commensurate Rotation

![Graphene hBN commensurate guide](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate.png)

Open the included stack, select the hBN layer, then use `R`, `Z`. The guide
searches reproducible integer cell matches and labels candidate angle/strain
pairs; enabling **Magnetic angle snap** pulls the current rotation into the
selected tolerance.

```bash
v_ase gui examples/readme_scene_assets/graphene_hbn_commensurate.traj --interactive
```

The normal `R` operation edits selected atoms. **Cell Transform** is a
different operation that applies an integer matrix to the periodic cell and
all trajectory frames. The equations and assumptions are documented in
[unit_cell_aware_rotate.md](docs/unit_cell_aware_rotate.md).

## Measurement And Analysis

![Ordered atom measurement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_measurement.png)

Select atoms in order:

- 1 atom: element, label, position, force, charge, tag, and magnetic moment;
- 2 atoms: direct distance and minimum-image distance;
- 3 atoms: angle `a1-a2-a3`, centered on `a2`;
- 4 atoms: signed torsion `a1-a2-a3-a4`;
- 5 or more atoms: total and per-label selection counts.

The ordered reference labels `a1` through `a4` are separate from atom indices.
Hovered-atom information is also separate, so a saved measurement remains
visible while the pointer moves.

Try the measurement scene:

```bash
v_ase gui examples/readme_scene_assets/ethane_measurement.cif
```

**Analysis** adds displacement vectors for trajectories. Choose the previous
frame or a specific reference frame, toggle minimum-image correction, and
style the vectors as 3D or flat 2D arrows. Displayed supercells repeat the
vectors, and a visual translation moves both endpoints without changing the
physical displacement.

## Constraints

ASE remains authoritative when **Apply constraints** is enabled. Constraint
visualization is local to each atom rather than merged at a group center.

### FixedLine

A compact cyan collar and local axis remain visible without selection. During
`G`, ASE restricts the atom to that line.

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

![Pairwise bond settings](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_bonds.png)

**Structure > Bonding** provides automatic inference, explicit label-pair
cutoffs, and manual index pairs. A pair cutoff of zero disables that pair.
Changes apply immediately. Bonds support:

- cell-local or periodic minimum-image display;
- cylinder or flat 2D geometry;
- custom color or two half-bonds using the atom colors;
- configurable diameter;
- live formation and breaking during Edit transforms.

**View** controls projection, atomic scale, anti-aliasing, sphere smoothness,
background, 2D/3D display, grid, axes, unit cell, overlays, and cell material.
New documents use orthographic projection and a true-white background.

The top-bar renderer switches between fast modeling light and Sun/soft-shadow
rendering. Sun source, target, intensity, and direction can be manipulated in
the viewport and carried into Blender export.

## Export And Save

| Command | Result |
| --- | --- |
| Export POSCAR | Current physical ASE structure in VASP format |
| Export ASE Pickle | ASE `Atoms`, labels, constraints, arrays, and a valid `SinglePointCalculator` |
| Export Image | Lossless WebP or optimized PNG from the exact preview frame |
| Export Video | H.264 MOV or MPEG-4 AVI with optional interpolation |
| Export Blender | Optimized scene script with atoms, bonds, cell, camera, and Sun |
| Export 3DM | Instanced Rhino geometry, metadata, and saved camera views |
| Export OBJ | OBJ/MTL, camera, and metadata in a ZIP |
| Save Project | Self-contained `.vase` with structure/trajectory and visual state |
| Save Settings | Reusable visual settings without coordinates |

The **Preview Area** is the authoritative image/video frame. Its aspect ratio,
camera, crop, lighting, atom scale, and included overlays match the export.
Cell, grid, axes, and background can be included or excluded independently.

The system save picker is opened before expensive rendering or scene
generation when the browser supports it. Canceling the picker cancels the
export.

`.vase` is self-contained and does not reference the original input file.
Opening an ordinary structure in an existing tab keeps the current visual
settings; opening `.vase` restores the saved project.

Rhino export requires the optional dependency:

```bash
python -m pip install "v_ase-gui[rhino]"
```

OBJ export has no optional Python dependency.

## Documents And File Opening

The top-bar **Open** button starts with the operating system file picker. A
selected file can:

1. replace the active document;
2. append structures to its current trajectory;
3. open in a new independent v_ase tab.

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

Return an edited ASE object:

```python
edited = view(atoms, viz_only=False)
print(edited.positions)
```

`view()` accepts one ASE `Atoms`, a sequence of frames, or a supported file
path. `view_edit()` remains a compatibility alias for Edit mode.

## File Formats

Common inputs include POSCAR/CONTCAR, VASP files, XDATCAR, `vasprun.xml`,
XYZ/extxyz, ASE `.traj`, LAMMPS dump/data, CIF, and `.vase`. ASE readers cover
additional formats.

Use `--format` when an ambiguous filename does not identify the reader:

```bash
v_ase gui ABCD --format POSCAR
v_ase gui ABCD --format vasprun.xml
v_ase gui ABCD --format lammpstrj
v_ase gui ABCD --format data
```

Use `--index :` for every frame, `--index -1` for the last frame, or an integer
for one frame.

Repeated POSCAR/CONTCAR species blocks remain separate visual labels. For
example, `O Cu O` with counts `1 14 5` becomes `O1`, `Cu`, and `O2` while all
oxygen atoms remain ASE element `O`.

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
| `Ctrl+Z`, `Ctrl+Shift+Z` | Undo and redo structure or camera changes |
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
between adjacent source frames.

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
