# Open structures and projects

Choose **File → Open** or drag a file into v_ase. Use the automatic reader for
standard file names, or choose a reader explicitly when needed.

(open-from-the-browser)=

## Open from the app or browser

For a structure or trajectory, choose the reader, frames and View/Edit mode.
If you already have a document open, **Open in new tab** is selected by default.
Choose another destination explicitly when needed:

| Destination | Result |
| --- | --- |
| **Open in new tab** (default) | Keep both documents open independently, each with its own view and undo history. |
| **Add to this trajectory** | Append frames and keep the receiving document's camera and appearance. |
| **Replace this tab** | Replace the current structure. Unsaved work offers Save, Discard or Cancel. |
| **Replace structure only** | Load the selected frames into the current tab while keeping its mode, camera, render settings, visual styles, and project destination. |
| **Open in new window** (desktop) | Open a separate app window. |

An empty document opens the file directly, without a destination choice.
A `.vase` project restores its saved mode, frame and appearance; it uses a new
tab if the current document contains work. [Saving and reopening projects](save-projects.md).

## Open several files

Select multiple files in **File → Open**, drop them together, or open the
selection from Finder/Explorer. One chooser offers:

- **Separate tabs** (default): one new tab per file, each keeping its own frames;
  projects restore their saved mode and appearance. The button shows the number
  of new tabs, such as **Open 15 tabs**.
- **One trajectory**: combine all structures into one new tab. Project files
  contribute structures, not appearance. Scalar-field files use separate tabs.

Files start in natural filename order (`frame-2` before `frame-10`). Check the
list and use its arrows to set the desired tab or trajectory order. Files sent
by the operating system in several events are sorted together until you manually
reorder them; later arrivals then join the end without undoing your order.
Existing tabs are kept.
Opening shows progress. Cancel waits for the current file to finish, then removes
all temporary imports. A failed file is named and the batch creates no partial tabs.
Save the combined trajectory as a new `.vase` project.

## Trajectory tools

In **Edit structure**, use **Duplicate to next frame** from the timeline
or viewport context menu to copy the current structure and activate the copy.
For an existing trajectory this inserts it immediately after the current frame.
Use **Duplicate frame to end** to add the copy to the end instead. On desktop,
the shortcuts are **⌘T / Ctrl+T** and **⌘Shift+T / Ctrl+Shift+T**. Start with a
single structure and duplicate before making the next edit to keep both
geometries. Copying a displayed image from a stopped relaxation keeps the
committed geometry on its source frame and opens the image as a new loaded
frame. A duplication can be undone.

Use **Delete current frame** from the same menu to remove a source image.
Undo restores the image with its stored labels, properties, energy and forces.

**Match** appears on the timeline in Edit structure when two or more frames
have the same element counts. It assigns atoms separately by element using
frame 1 as the reference. **Minimum image** uses the reference cell and
periodic directions. **Cartesian distance** uses the stored coordinates.
**SOAP + translation** proposes translations from DScribe local environments
and selects the assignment with the lowest species-balanced minimum-image RMS.
It applies the resulting index order. Each frame keeps its coordinates, cell,
constraints and stored results. One Undo restores the original ordering.
The desktop includes DScribe. In a Python installation, install
`v_ase-gui[soap]` to enable SOAP matching.
[DScribe SOAP reference](https://singroup.github.io/dscribe/latest/tutorials/descriptors/soap.html).

Turn on **Overlays → Energy graph** with its eye icon. NEB data with a saved
`path_length_A` uses that coordinate. Other trajectories use frame number.
The graph reads stored energies in eV and shows gaps for unavailable values.
It follows timeline playback. Click, drag, or use the arrow keys on the graph
to seek a frame. Drag the header to move the graph and drag its lower-right
corner to resize it. Select the Energy graph row to change the line color,
width, pattern, marker shape and size, or show only sample markers. Set a
custom or transparent background, control the graph grid, and choose whether
to display the current-frame cursor. **Set background as default** uses the
current background for new documents. Named presets save the rest of the
appearance independently.

### NEB fits and force tangents

Open **NEB** in the Energy graph inspector to enable **Force-based fit**,
**Force tangents**, or both. Supply **Last images** to select a recent band
from a trajectory of successive NEB iterations. Leave the field blank when
the loaded frames already form one band. The fit uses
`ase.utils.forcecurve.fit_images` with saved energies and per-atom forces.
It requires the same atom order across the band. With **Minimum image
(PBC)** enabled by default, the fit uses the file's periodic axes and checks
that the periodic cell vectors are consistent. Turn it off to fit the stored
Cartesian displacements, for example after using minimum image to match atom
indices. The setting changes the curve's path axis and the tangent positions
and spans. ASE projects the forces using the stored Cartesian directions in
both modes. The tangent length multiplier scales each segment about its
image while keeping the force slope.
[ASE NEB reference](https://docs.ase-lib.org/ase/neb.html).

Choose **Markers** for the raw images and adjust the fit line independently.
The graph seeks to the corresponding source frames, including when it shows
only a band at the end of the trajectory. A band missing saved results shows a
diagnostic and keeps the available raw energies.

**Export image** saves a graph-only PNG at twice its display size and supports
transparent backgrounds. **Export CSV** writes sample energies with one-based
frame numbers. Enabled NEB layers add ASE fit samples and the two endpoints
and slope of each displayed tangent. Path coordinates use Å and energies use
eV. Missing absolute energies remain blank.

## Open from the terminal

```bash
v_ase gui FILE
v_ase gui FILE --index :
v_ase gui FILE --index -1
v_ase gui FILE --index 12
v_ase gui AMBIGUOUS --format POSCAR
```

`--index :` loads or exposes all frames, `-1` selects the last frame, and an
integer selects one frame. The default is all frames.

## Filename inference

Standard VASP stems can carry `.`, `_`, or `-` suffixes. Examples such as
`POSCAR_1`, `CONTCAR-final`, `XDATCAR.02`, `CHGCAR_spin`, and `LOCPOT-test`
retain their intended reader. You can keep these file names when opening them from either the app or terminal.

Use an explicit reader when a name is genuinely ambiguous:

```bash
v_ase gui calculation.out --format extxyz
v_ase gui density.dat --format cube
v_ase gui dump.custom --format lammpstrj
```

## Labels and chemical types

Some source formats contain identities that are not valid ASE chemical symbols.
v_ase preserves this distinction with an internal per-atom label array:

- repeated POSCAR/CONTCAR blocks become ordered labels such as `O_1`, `O_2`;
- custom extxyz labels retain their text while mapping to a valid ASE TYPE;
- LAMMPS integer types remain visible raw labels;
- LAMMPS masses can infer a chemical TYPE when unambiguous.

Appearance and pair tables key on LABEL. Element radii, ASE builders, and
scientific calculations key on TYPE.

## Large and remote trajectories

Use View mode to inspect large trajectories. Supported XDATCAR, ASE `.traj`
and LAMMPS inputs can load frames on demand, reducing startup time and memory.

Remote `HOST:/path` sessions always stream frames. The source file, ASE objects,
trajectory cache, volumetric processing, and backend calculations stay on the
remote host; the local browser receives active-frame or derived rendering data
through the SSH tunnel.

## Volumetric input

CHG/CHGCAR, PARCHG, LOCPOT, ELFCAR, Gaussian Cube, and XSF open as a structure
plus one or more scalar datasets. Choose memory precision at launch:

```bash
v_ase gui CHGCAR --volumetric-precision fp32
v_ase gui LOCPOT --volumetric-precision fp64
```

FP32 is the lower-memory default. FP64 preserves double-precision input values
and uses twice the scalar-grid memory. See [Volumetric fields](volumetric-guide.md).

## Open failures

When opening in a new tab in the desktop app, a zero-byte file is reported by
name. If the selection is unavailable, choose the file again.

Reader diagnostics distinguish unknown formats, missing files, directories,
permissions, malformed data, and incomplete text. A failed replacement leaves
the active document intact. If inference chose the wrong reader, retry with an
explicit `--format` or browser Reader selection rather than renaming scientific
content blindly.

See [Supported formats](formats.md) for the format and export matrix.
