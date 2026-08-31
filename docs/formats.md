# Supported formats

v_ase 0.2.35 uses one input pipeline for the terminal, Python path API, and
browser file picker. It adds project, volumetric, indexed-trajectory, and
LAMMPS handling around ASE's readers. An explicit reader always takes priority
over filename inference.

## Input overview

| Family | Common names and extensions | What v_ase loads | Important behavior |
| --- | --- | --- | --- |
| VASP structures | `POSCAR`, `CONTCAR`, `.vasp` | Structure, cell, PBC, constraints and compatible arrays | Numbered or descriptive suffixes such as `POSCAR_1` and `CONTCAR-final` are recognized |
| VASP trajectories | `XDATCAR` | All or selected trajectory frames | View mode uses indexed random access when the header is compatible |
| VASP calculation XML | `vasprun.xml` | ASE-readable structures and frames | Use `--format vasprun.xml` when the visible filename is ambiguous |
| XYZ | `.xyz` | One or more structures | Standard XYZ has limited metadata |
| Extended XYZ | `.extxyz` | Frames, cells/PBC, arrays and compatible calculator results | Preferred text interchange when ASE metadata must survive |
| ASE trajectory | `.traj` | Native ASE frames and metadata | View mode uses the trajectory container's random access |
| LAMMPS dump | `.lammpstrj`, `.dump` | Frames, box/PBC, ids, types, positions and supported numeric columns | Compatible numeric dumps use a byte-indexed, memory-mapped View path |
| LAMMPS data | `.data` | Structure, box, atom ids/types, masses and supported topology fields | Atom style is detected when possible; `--format data` removes ambiguity |
| CIF | `.cif` | ASE-readable crystallographic structures | CIF interpretation follows the installed ASE release |
| v_ase project | `.vase` | Complete editable document | Restores frames, scientific metadata, visual state, analysis and export settings |
| v_ase project HTML | `.html`, `.htm` | Embedded `.vase`, when present | A lightweight view-only HTML has no editable project to restore |
| VASP scalar fields | `CHG`, `CHGCAR`, `PARCHG`, `LOCPOT`, `ELFCAR` | Structure plus scalar datasets | Standard stems may use `.`, `_`, or `-` suffixes |
| Gaussian Cube | `.cube`, `.cub` | Structure and scalar grid | `cube`, `gaussian-cube`, and `qe-cube` are accepted reader aliases |
| XSF | `.xsf` | Structure and supported scalar grids | `xsf` and `qe-xsf` are accepted aliases |
| Other ASE formats | Format-dependent | Structures or trajectories accepted by `ase.io.read` | Pass the raw ASE format name when automatic detection is insufficient |

:::{note}
"Supported by ASE" does not imply that every format can preserve every ASE
array, constraint, calculator result, label, or trajectory feature. Use
extended XYZ, ASE trajectory, ASE Pickle, or `.vase` when those distinctions
matter.
:::

## Automatic detection and reader aliases

The resolver examines the original user-visible filename, including browser
uploads that are stored temporarily under a different server-side name. The
following standard VASP stems are recognized with an optional `.`, `_`, or
`-` suffix:

- `POSCAR` and `CONTCAR`;
- `XDATCAR`;
- `CHG` and `CHGCAR`;
- `PARCHG`;
- `LOCPOT`; and
- `ELFCAR`.

For example, `POSCAR.relaxed`, `XDATCAR_2`, and `LOCPOT-spin` retain the
intended reader. `vasprun.xml` is recognized by its complete basename.

Use `--format` to override inference:

```bash
v_ase gui INPUT --format POSCAR
v_ase gui INPUT --format XDATCAR
v_ase gui INPUT --format vasprun.xml
v_ase gui INPUT --format lammpstrj
v_ase gui INPUT --format data
v_ase gui INPUT --format CHGCAR
v_ase gui INPUT --format qe-cube
v_ase gui INPUT --format qe-xsf
```

Common aliases are case-insensitive:

| Requested family | Accepted examples |
| --- | --- |
| VASP structure | `poscar`, `contcar`, `vasp` |
| XDATCAR | `xdatcar`, `vasp-xdatcar`, `vasp_xdatcar` |
| vasprun.xml | `vasprun`, `vasprun.xml`, `vasp-xml`, `vasp_xml` |
| LAMMPS dump | `lammpstrj`, `lammpsdump`, `lammps-dump`, `lammps-dump-text` |
| LAMMPS data | `data`, `lammps-data`, `lammps_data` |
| ASE trajectory | `traj`, `trajectory` |
| Extended XYZ | `extxyz`, `extendedxyz` |
| Project | `vase`, `vase-project`, `html`, `vase-html-project` |
| Scalar field | `chg`, `chgcar`, `parchg`, `locpot`, `elfcar`, `cube`, `cub`, `xsf` |

Raw ASE format names are also forwarded to ASE. See
[Data input and documents](data-input.md) for browser destinations and failure
semantics.

## Frame selection

The terminal accepts ASE-style frame selection:

```bash
v_ase gui trajectory.extxyz --index :
v_ase gui trajectory.traj --index -1
v_ase gui XDATCAR --index 25
```

`:` means all frames, `-1` means the final frame, and an integer selects one
frame. The default is all frames. Indexed sources can expose the requested
frame immediately in View mode; switching to Edit can materialize the complete
selected trajectory because physical topology operations require editable ASE
objects.

## Labels, types, and per-atom data

v_ase keeps ASE chemical **TYPE** separate from the visual **LABEL** used by
appearance, selection, and label-pair rules.

- Repeated POSCAR/CONTCAR species blocks remain distinct. A header `Cu O O`
  can become labels `Cu`, `O_1`, and `O_2` while both oxygen groups retain ASE
  element `O`.
- Extended XYZ arrays and valid labels are retained when ASE exposes them.
- LAMMPS integer types remain visible as labels. A mass can infer a chemical
  element when the match is unambiguous.
- Compatible LAMMPS dump columns such as id, molecule, charge, force, mass,
  and scalar values are exposed as ASE arrays or colorable properties.

Plain XYZ and many crystallographic formats cannot encode all of these fields.
Choose an interchange format according to the preservation table below.

## Volumetric data

VASP density, potential, partial-density, and ELF files, Gaussian Cube, and
XSF can open as a structure plus scalar datasets. Select the in-memory scalar
precision at launch:

```bash
v_ase gui CHGCAR --volumetric-precision fp32
v_ase gui LOCPOT --volumetric-precision fp64
```

FP32 is the lower-memory default. FP64 preserves double-precision grid values
and uses approximately twice the grid memory. Combining datasets requires
identical dimensions, cell vectors, origin, PBC, endpoint convention, and
units; v_ase does not silently resample incompatible grids.

## Structure and scientific-state output

| Output | Contents | Does not preserve |
| --- | --- | --- |
| POSCAR | Current physical ASE structure and full-rank cell | Trajectory, visual settings, analysis, arbitrary arrays unsupported by VASP |
| CLI `-o PATH` | Final blocking-session ASE object through the writer inferred from `PATH` | Anything unsupported by the chosen ASE writer |
| ASE Pickle (`.pkl`) | Current frame, symbols, positions, cell/PBC, labels, constraints, portable arrays, valid `SinglePointCalculator` results | Other frames, visual settings, arbitrary executable calculator implementations |
| `.vase` | Complete editable project archive | Original source-file dependency; the archive is self-contained |
| Project HTML | Offline rendered document plus complete embedded `.vase` | Editing in the browser view itself; reopen it in v_ase to edit |
| Visual Settings JSON | Reusable presentation, bonds, camera/projection, lighting, display replication and visual translation | Coordinates and trajectory frames |

For a normal blocking terminal workflow, `-o` writes the returned structure
with ASE after the session closes:

```bash
v_ase gui input.cif -o edited.extxyz
v_ase gui input.cif -o edited.data --output-format lammps-data
```

The GUI POSCAR exporter centers a cell-free or rank-deficient finite structure
in a nonperiodic box with 8 Å vacuum so that ASE's VASP writer can produce a
valid file.

ASE Pickle is Python-specific and uses pickle; load only files from a trusted
source. In contrast, `.vase` is a validated ZIP-based project format and does
not unpickle executable Python objects.

## Project and HTML choices

Use **Export > Save Project** for editable continuity:

- the default `.vase` is the smallest complete project;
- enabling **Include interactive rendered view** produces a larger `.html`
  containing the same complete `.vase`, an optimized poster, and an offline
  interactive scene.

Use **HTML View** for a presentation handoff. Its default is the smaller
view-only document without an embedded project. Enabling project embedding
adds **Download .vase** and makes the file reopenable through:

```bash
v_ase gui project.html
```

All standalone HTML output opens from `file://` without Python, a local
server, a CDN, or another network request. It supports camera navigation and
trajectory playback but intentionally exposes no atom or style editing tools.

## Rendered media and 3D scenes

| Export | File | Notes |
| --- | --- | --- |
| Image | `.png`, `.webp`, `.jpg`, `.pdf` | Uses the exact Render Area dimensions and camera |
| Video | `.mov`, `.avi` | Constant-frame-rate output; interpolation inserts in-between frames |
| Blender | `v_ase_blender_scene.py` | Reconstructs optimized atoms, bonds, cell, camera and Sun in Blender |
| OBJ | `v_ase_obj_scene.zip` | Contains OBJ/MTL scene data plus camera and metadata; no optional dependency |
| Rhino | `v_ase_scene.3dm` | Instanced geometry, metadata and saved views; requires the `rhino` extra |

PNG is the default. PNG recompression and WebP are lossless. JPEG and PDF
flatten transparency onto white; all four retain the requested pixel
dimensions. PDF is a rendered-image export, not editable vector atom geometry.

Video export requires at least two compatible frames. Every source frame is
kept exactly once at `1x`; interpolation adds frames between sources and
requires stable atom count, ordering, element, and label identity across each
interpolated pair. MOV uses H.264 and AVI uses MPEG-4 through the bundled
`imageio-ffmpeg` runtime.

Install the optional Rhino writer with:

```bash
python -m pip install "v_ase-gui[rhino]"
```

## Which format should I choose?

| Goal | Recommended choice |
| --- | --- |
| Resume all scientific and visual work | `.vase` |
| Resume work and preview/share in a browser | Save Project HTML |
| Share only an offline interactive view | HTML View without project embedding |
| Exchange ASE arrays and multiple frames as text | Extended XYZ |
| Preserve native ASE trajectory access | `.traj` |
| Pass one current ASE object between trusted Python processes | ASE Pickle |
| Continue a VASP calculation workflow | POSCAR/CONTCAR as appropriate |
| Publish a raster figure | PNG or lossless WebP |
| Move geometry into a general 3D tool | OBJ ZIP, Blender script, or optional 3DM |

When exact project restoration matters, validate by reopening the saved file
with v_ase rather than assuming a visually similar interchange format retained
the document state.
