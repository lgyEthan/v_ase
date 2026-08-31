# Data input and documents

The CLI, Python path API, and browser file picker use the same canonical input
resolver. Explicit reader choices take priority over filename inference.

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

## Open from the browser

The top-bar **Open** action invokes the operating-system picker immediately.
After selecting a file, choose the reader, frame range, mode, and destination:

| Destination | Structure/trajectory | `.vase` or project HTML |
| --- | --- | --- |
| Replace current | Replaces scientific content and reconciles existing visual settings | Restores the complete project state |
| Add to trajectory | Appends selected frames and keeps current frame/camera/settings | Appends only selected embedded structures |
| Open in new tab | Creates an independent document | Restores the project in an independent document |

When the current document is empty, the file replaces it directly and the
destination chooser is skipped.

## Filename inference

Standard VASP stems can carry `.`, `_`, or `-` suffixes. Examples such as
`POSCAR_1`, `CONTCAR-final`, `XDATCAR.02`, `CHGCAR_spin`, and `LOCPOT-test`
retain their intended reader. The same rule applies to local CLI files and
temporary browser uploads because inference uses the original visible name.

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

In View mode, compatible XDATCAR and ASE `.traj` inputs use indexed random
access. Large numeric LAMMPS dumps use a byte-offset/memory-mapped trajectory
path when their layout is supported. Frame changes load only the requested
frame and keep stable identity checks.

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
