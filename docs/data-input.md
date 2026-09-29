# Open structures and projects

Choose **File → Open** or drag a file into v_ase. Use the automatic reader for
standard file names, or choose a reader explicitly when needed.

(open-from-the-browser)=

## Open from the app or browser

For a structure or trajectory, choose the reader, frames and View/Edit mode.
If you already have a document open, choose where the new data should go:

| Destination | Result |
| --- | --- |
| **Replace current** | Replace the current structure. Unsaved work offers Save, Discard or Cancel. |
| **Add to trajectory** | Append frames and keep the receiving document's camera and appearance. |
| **Open in new tab** | Keep both documents open independently. |
| **Open in new window** (desktop) | Open a separate app window. |

An empty document opens the file directly, without a destination choice.
A `.vase` project restores its saved mode, frame and appearance; it uses a new
tab if the current document contains work. [Saving and reopening projects](save-projects.md).

## Open several files

Select multiple files in **File → Open**, drop them together, or open the
selection from Finder/Explorer. One chooser offers:

- **Separate tabs** (default): each file keeps its own frames; projects restore
  their saved mode and appearance.
- **One trajectory**: combine all structures into one new tab. Project files
  contribute structures, not appearance. Scalar-field files use separate tabs.

Files start in natural filename order (`frame-2` before `frame-10`). Check the
list and use its arrows to set the desired frame order. Existing tabs are kept.
Opening shows progress. Cancel waits for the current file to finish, then removes
all temporary imports. A failed file is named and the batch creates no partial tabs.
Save the combined trajectory as a new `.vase` project.

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

Reader diagnostics distinguish unknown formats, missing files, directories,
permissions, malformed data, and incomplete text. A failed replacement leaves
the active document intact. If inference chose the wrong reader, retry with an
explicit `--format` or browser Reader selection rather than renaming scientific
content blindly.

See [Supported formats](formats.md) for the format and export matrix.
