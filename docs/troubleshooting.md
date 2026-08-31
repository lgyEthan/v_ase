# Troubleshooting

This guide covers the failure modes most often confused with a structure-file
problem in v_ase 0.2.35. Start with the short environment check, then use the
section matching the visible error.

## Collect the active environment

Run these commands with the same shell and Python used to launch v_ase:

```bash
python --version
python -m pip --version
python -m v_ase.cli --version
python -m pip check
```

`python -m v_ase.cli --version` bypasses a missing console-script entry point.
If it succeeds while `v_ase --version` fails, the package is installed and the
problem is the active environment or its scripts directory.

When reporting a problem, also record the operating system, browser and
version, input format, exact command, full terminal error, whether View or Edit
was active, and the smallest input that reproduces the failure. Do not post a
live workspace URL: it contains session identifiers intended for the local
process.

## The `v_ase` command is not found

Install and invoke the package with the same Python:

```bash
python -m pip install --upgrade v_ase-gui
python -m v_ase.cli --version
```

If the module command works, reactivate the virtual/Conda environment or add
that Python installation's scripts directory to `PATH`. Compare
`python -m pip --version` with `which v_ase` on macOS/Linux or `where v_ase`
on Windows.

See [Installation](installation.md) for a clean-environment setup.

## The browser does not open

The terminal prints the complete loopback URL before attempting automatic
browser launch. Keep the terminal running and open the printed
`http://127.0.0.1:...` address manually.

You can request this workflow explicitly:

```bash
v_ase gui POSCAR --no-browser
```

The server is bound to loopback by design. Opening the URL on another computer
without an SSH tunnel will not work.

### WSL prints `gio: ... Operation not supported`

Copy the already printed loopback URL into a Windows browser. The `gio` error
means the Linux desktop helper could not open a tab; it does not mean the
v_ase server failed. For large data, keep files in the WSL Linux filesystem
rather than `/mnt/c/...`.

## Startup fails before the file is read

### `numpy.dtype size changed`

This indicates a binary ABI mismatch between NumPy and a compiled SciPy or
matscipy module. It occurs during scientific-stack import, before v_ase reads
the requested structure.

Reinstall the stack with the Python that owns v_ase:

```bash
python -m pip install --upgrade --force-reinstall v_ase-gui
```

For v_ase 0.2.35, Python 3.10-3.12 resolve the NumPy 1.x/matscipy 1.1.x family;
Python 3.13 resolves the NumPy 2.x/matscipy 1.2+ family. Avoid upgrading NumPy
alone in a shared Conda base environment. A dedicated environment is the most
reliable repair when unrelated compiled packages require incompatible ABIs.

### matscipy cannot be installed or imported

Update pip and let the v_ase dependency markers choose the compatible build:

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade v_ase-gui
```

v_ase uses matscipy's compiled neighbor search for RDF/pair distributions,
repulsion and bond generation/export. If no wheel exists for the active
Python/platform, use a supported CPython platform or install the compiler
toolchain requested by matscipy's source build.

### `cannot import name 'read_vasp_configuration'`

This came from an ASE compatibility defect in v_ase 0.1.1-0.1.5. Upgrade the
same environment that provides the failing command:

```bash
python -m pip install --upgrade v_ase-gui
v_ase --version
```

Do not repair a current v_ase installation by downgrading only ASE; upgrade
the complete environment so its declared NumPy/matscipy pair stays coherent.

### pip reports an unrelated package version as `None`

That usually identifies a different incomplete or manually installed
distribution in the environment. Run `python -m pip check`, repair the named
distribution, or use a clean environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install v_ase-gui
```

On Windows, activate with `.venv\Scripts\activate`.

## A file uses the wrong reader

Force the intended reader rather than renaming scientific content blindly:

```bash
v_ase gui FILE --format POSCAR
v_ase gui FILE --format vasprun.xml
v_ase gui FILE --format lammpstrj
v_ase gui FILE --format data
```

The original visible filename controls automatic inference, including browser
uploads. Names such as `POSCAR_1`, `CONTCAR-final`, and `XDATCAR.02` are
recognized. See [Supported formats](formats.md) for aliases.

## Open or Add to trajectory reports a reader error

The dialog presents the final useful reader message; the terminal retains the
complete traceback. Check the specific class of failure:

- confirm the path exists and is a file rather than a directory;
- confirm the current user can read it;
- select the Reader explicitly when the format cannot be inferred;
- check that text input is complete rather than truncated; and
- try a single frame if a trajectory may contain one malformed frame.

A failed Replace operation leaves the current document intact. Use
[Data input and documents](data-input.md) for the replacement/append/new-tab
boundaries.

## A remote launch cannot find v_ase

The non-interactive SSH command used by `HOST:/path` may not activate Conda or
read the same shell startup files as an interactive login. Select the exact
remote Python executable:

```bash
v_ase gui USER@SERVER:/absolute/path/to/STRUCTURE \
  --remote-python /home/user/miniconda3/envs/vase/bin/python
```

Verify it independently:

```bash
ssh USER@SERVER '/home/user/miniconda3/envs/vase/bin/python -m v_ase.cli --version'
```

Save a reusable mapping with:

```bash
v_ase remote configure USER@SERVER \
  --python /home/user/miniconda3/envs/vase/bin/python
v_ase remote show USER@SERVER
```

The one-launch `--remote-python` value overrides the saved mapping. Keep local
and remote v_ase installations on the same current release so their browser,
backend and semantic schemas agree.

### Remote reports unknown `--no-browser` or `--stream-frames`

The remote installation is older than the local launcher. Upgrade both ends.
Current local launchers can fall back to a compatible remote command, but
on-demand frame transfer and newer volumetric or semantic features still
require a current remote backend.

### The remote page opens and then shows `ERR_CONNECTION_RESET`

Upgrade the local launcher. Old releases could create the remote backend and
port forward on separate SSH connections; a load-balanced cluster alias could
send those connections to different login nodes. Current releases keep both
operations on one SSH connection.

## A large trajectory opens or plays slowly

- Stay in **View** unless physical editing is required. Switching to Edit can
  materialize lazy frames.
- XDATCAR and native ASE `.traj` inputs use indexed access automatically in
  View. Compatible numeric LAMMPS dumps use a byte-offset path.
- Use `--stream-frames` for another supported virtual source when launching a
  backend manually.
- Keep browser hardware acceleration and WebGL enabled.
- Close unused documents when memory is constrained. Inactive tabs suspend
  rendering and playback but retain their document state.
- Reduce displayed supercell replication, bonds, volumetric refinement, and
  simultaneous overlays before reducing scientific input data.

See [Rendering performance](performance.md) for validated boundaries and
benchmark methods.

## Replicated atoms behave unexpectedly

In **View**, each displayed periodic replica is a separate visual reference.
It can be selected, measured, styled or hidden without changing the ASE unit
cell. Hidden atoms still exist in backend analysis.

In **Edit**, every replica resolves to its unique base atom. Selection is
deduplicated across images and physical deletion removes that base atom. Use
**Set Supercell as Cell** only when the displayed copies should become real
ASE atoms in a larger physical cell.

## A transform ignores or changes the preview

The browser shows an unconstrained interaction preview, then commits through
the backend. With **Apply constraints** enabled, ASE constraints remain
authoritative and can project the confirmed coordinates back to an allowed
line, plane, scaled direction, or fixed position.

Press `Esc` once to close an open panel and return keyboard focus to the
viewport without clearing selection. Press `Esc` during an active transform to
cancel that transform.

## Pair statistics reject the boundary conditions

v_ase chooses between two different definitions:

- finite structures with all PBC axes off use the finite pair-distribution
  function; and
- fully periodic three-dimensional structures use bulk RDF `g(r)`.

Partial-PBC slabs and wires are not silently normalized as either definition.
Use a method with a boundary correction appropriate to that geometry.

## Volumetric datasets cannot be combined

Difference and combination operations require identical grid dimensions,
cell vectors, origin, PBC, endpoint convention, and units. Generate component
fields on the same FFT mesh or resample them deliberately before opening them.
v_ase does not interpolate incompatible scientific grids implicitly.

## Video export is unavailable or slow

Video requires at least two frames and browser `MediaRecorder` support.
MOV/AVI conversion uses bundled `imageio-ffmpeg`. Interpolation renders extra
frames and requires stable atom count, element, label and ordering between
adjacent source frames.

At `1x`, every source frame appears once. For example, 72 output frames at
30 FPS produce 2.40 seconds. Export progress reaches 100% only after rendering,
encoding, download and the destination write are complete.

## Chrome says the site can change the saved file

This is Chrome's File System Access permission notice. v_ase opens the system
save picker before expensive rendering so cancellation does not waste the
render. The page receives write access only to the destination selected in
that picker. Chrome does not let a page suppress the notice while retaining
advance destination selection.

## An HTML file cannot be restored as a project

The lightweight **HTML View** defaults to view-only and contains no editable
project. It remains an offline interactive presentation, but v_ase cannot
recover scientific project state that was never embedded.

Use either:

- **Save Project** with **Include interactive rendered view** enabled; or
- **HTML View** with **Embed editable .vase project** enabled.

For the smallest editable source of truth, save `.vase` directly.

## Before opening an issue

Confirm the problem on v_ase 0.2.35, reduce it to the smallest safe input, and
record the exact steps and expected result. Include terminal output as text,
not only a screenshot. For rendering defects, include the viewport and exported
file dimensions and say whether the issue affects the live viewport, Render
Area preview, or final file.

Report reproducible problems through
[GitHub Issues](https://github.com/lgyEthan/v_ase/issues). Run
`v_ase --help` and `v_ase gui --help` for the complete CLI option list.
