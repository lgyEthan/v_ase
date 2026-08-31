# CLI And Environments

## Contents

1. Installation
2. Entry Points
3. Input Formats
4. Output And Lifecycle
5. Local, WSL, And Remote Use
6. Runtime Constraints

## Installation

Install the tested release into the active Python environment:

```bash
python -m pip install "v_ase-gui==0.2.35"
```

Optional Rhino export:

```bash
python -m pip install "v_ase-gui[rhino]==0.2.35"
```

Runtime dependencies are ASE, matscipy, FastAPI, Uvicorn, NumPy, SciPy,
scikit-image, Plotly, Matplotlib, imageio-ffmpeg, and Pillow. matscipy provides
the compiled pair-search backend used by RDF, finite pair distributions,
repulsion, and exported bond topology. No Node.js runtime, API key, or hosted
account is required.

Binary dependency markers keep supported interpreters on compatible ABI
families: Python 3.10-3.12 resolves NumPy 1.x with matscipy 1.1.x, while Python
3.13 and newer resolves NumPy 2.x with matscipy 1.2 or newer. A
`numpy.dtype size changed` failure occurs before any structure parsing. Repair
the complete environment with the same interpreter instead of replacing NumPy
alone:

```bash
python -m pip install --upgrade --force-reinstall "v_ase-gui==0.2.35"
```

v_ase uses the `AGPL-3.0-or-later` license. Preserve the license and source
offer when redistributing v_ase or operating a modified version for users over
a network.

Verify the active executable and import:

```bash
v_ase --version
python -c "from v_ase.visualize import view; print(callable(view))"
```

If the command is missing, run `python -m pip show v_ase-gui` and compare that
Python's environment with `which v_ase` on Unix or `where v_ase` on Windows.

## Entry Points

Open an empty workspace:

```bash
v_ase gui
```

This filename-free workspace starts in Edit so a cell and atoms can be created
from scratch. A filename starts in View unless `--interactive` is supplied.
When a human uses **Open File**, each load explicitly offers View or Edit; a
new empty document replaces directly because there is no prior structure to
append or preserve.

Open a structure or all trajectory frames:

```bash
v_ase gui STRUCTURE
```

Terminal-oriented API session for an automation agent to launch itself:

```bash
v_ase gui STRUCTURE --cli
```

Interactive atom editing:

```bash
v_ase gui STRUCTURE --interactive
```

Interactive atom editing controlled through the same live agent bridge:

```bash
v_ase gui STRUCTURE --interactive --cli
```

Use this combined form for structural agent workflows such as batch atom
insertion. The human and agent still share one document; `--interactive`
chooses Edit mode and `--cli` exposes the structured transport.

Useful options:

| Option | Meaning |
| --- | --- |
| `--index :` | Read all frames |
| `--index -1` | Read the last frame |
| `--format FORMAT` | Force a reader for an ambiguous filename |
| `--volumetric-precision fp32|fp64` | Choose scalar-grid import precision; FP64 uses twice the grid memory |
| `--no-browser` | Print the URL without launching a browser |
| `--no-block` | Keep the server alive until interrupted |
| `--stream-frames` | Load trajectory coordinates frame by frame |
| `--remote-python ABSOLUTE_PATH` | For `HOST:/path` input, launch through that exact remote Python instead of remote `PATH` discovery |
| `--show-bonds` / `--hide-bonds` | Override startup bond visibility |
| `--hide-cell` / `--hide-axes` | Hide viewport guides at startup |

`--cli` is not an embedded AI model. It implies a nonblocking, no-browser
session and prints one JSON handshake as the first stdout line. Later stdout
lines are compact revisioned NDJSON events from the live GUI. Keep the process
alive until work is complete.

From an agent shell, launch `v_ase gui ... --cli` as a persistent process.
When the command runner yields output or returns a session/process handle,
parse the first stdout line and move on immediately; never wait for this
server command to finish before calling `v_ase api`. Retain the handle to poll
later NDJSON events and stop it at the end. Use the runner's native
long-running-process mechanism rather than a platform-specific shell trick
when one is available.

After final `describe`, render, and export verification, terminate the
persistent CLI process while the human GUI is still open, then close the GUI.
Closing the GUI first may stop its local server and make the still-running CLI
event poller print a reconnect notice.

`--cli` does not consume natural language or structured commands from stdin.
The first stdout line is the startup handshake, later stdout lines are
`v_ase.collaboration.v1` events, and status goes to stderr. After parsing the
handshake, an external agent opens `human_url` and sends structured HTTP JSON
through the handshake's `command_url`:

```bash
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":false}'
v_ase api "$COMMAND_URL" apply --params-file command.json
v_ase api "$COMMAND_URL" render --params-file render.json --save preview.png
```

Use `--save` for render/export data URLs. It refuses to replace an existing
file unless `--force` is explicitly passed. Without `--save`, the CLI omits
the Base64 payload and returns compact metadata by default; use
`--print-data-url` only when a caller explicitly needs the raw URL. The user may speak natural
language to the external agent and refine the same GUI; v_ase itself receives
file/CLI arguments and semantic API objects only.

Python API:

```python
from v_ase.visualize import view

editor = view(atoms_or_frames, block=False)
print(editor.url)
```

For a scalar-field path, choose import precision explicitly when double
precision is scientifically required:

```python
editor = view(
    "CHGCAR",
    volumetric_precision="fp64",
    block=False,
)
```

In Jupyter Notebook or JupyterLab, use `view(atoms_or_frames)` as the cell's
final expression. It detects the active kernel and renders one view-only
interactive model below the cell without launching an external browser. When
retaining the handle, call `display(editor)` explicitly.

Switch the process-local display target without restarting the kernel:

```python
%v_ase inline
view(atoms_or_frames)

%v_ase browser
editor = view(atoms_or_frames, block=False)

%v_ase auto
```

The magic is registered when `v_ase` or `v_ase.visualize` is imported. Use
`%v_ase auto` restores automatic active-kernel detection: notebook kernels
display inline and ordinary Python opens the external browser. Use
`%load_ext v_ase.notebook` to register the magic explicitly. Per-call
`notebook=True` / `"inline"` or `notebook=False` / `"browser"` overrides the
current magic preference.

## Input Formats

ASE-readable structures and trajectories are supported. Common inputs include:

- POSCAR, CONTCAR, and arbitrary filenames forced with `--format POSCAR`;
- XDATCAR and `vasprun.xml`;
- XYZ and extended XYZ;
- ASE `.traj`;
- LAMMPS dump/`lammpstrj` and LAMMPS data;
- CIF and other formats registered by ASE;
- self-contained `.vase` projects.

CLI paths and **Open File > Auto detect** share one filename resolver. Standard
VASP basenames accept `.`, `_`, or `-` calculation suffixes: for example,
`POSCAR_1`, `CONTCAR-final`, and `XDATCAR_2` select the same readers in both
entry points. This rule also covers browser Replace, Add to trajectory, and
Open in new tab. An explicit `--format` or GUI Reader always takes precedence.

Volumetric inputs may be opened directly or loaded into an existing document:

- VASP `CHGCAR`/`CHG`, `LOCPOT`, `PARCHG`, and `ELFCAR`, including
  calculation suffixes separated by `.`, `_`, or `-`;
- Gaussian Cube;
- XSF `DATAGRID_3D` blocks;
- Quantum ESPRESSO scalar data exported by `pp.x` as Cube or XSF.

Use `--format` when the filename does not identify the reader:

```bash
v_ase gui ABCD --format vasprun.xml
v_ase gui INPUT --format lammps-data
v_ase gui GRID --format CHGCAR
v_ase gui charge.dat --format qe-cube
```

For semantic `load-volumetric`, relative paths are resolved inside the
directory where `v_ase gui` was launched. This keeps an agent inside the same
local or remote working directory as the DFT calculation.

The semantic state keeps visual labels separate from ASE chemical symbols.
Custom labels such as `O_bridge` remain labels while the backend element can
remain `O`.

For VASP 5/6 POSCAR and CONTCAR inputs, repeated entries in the explicit
species header are retained as ordered visual identities. `Cu O O` with counts
`160 15 1` is described as labels `Cu`, `O_1`, and `O_2` in exact file/index
order, while both oxygen blocks keep chemical symbol `O`. Preserve these
labels unless the user explicitly asks to merge them: they may represent
different POTCARs, magnetic groups, or a core-hole target.

## Output And Lifecycle

The human GUI uses the operating-system save picker before expensive encoding.
The semantic API returns binary exports as data URLs with filename, MIME type,
and byte count. `v_ase api ... --save OUTPUT` decodes them directly.

Main outputs:

- structure: POSCAR or ASE pickle;
- image: PNG by default, or JPEG, PDF, and lossless WebP;
- trajectory movie: MOV/H.264 or AVI/MPEG-4;
- editable scene: Blender Python, Rhino 3DM, or OBJ bundle;
- shareable view or save file: one offline HTML document with an optimized
  Quick Look poster and optional embedded `.vase` recovery;
- complete session: `.vase`;
- reusable appearance: visual settings JSON.
- analysis table: total and pairwise RDF as CSV.

Use `.vase` as the canonical editable project. Use HTML when the recipient
should inspect the saved 3D scene and trajectory in a browser without
installing v_ase. HTML always includes the renderer and browser scene data.
Set **Embed editable .vase project** when lossless recovery is required; this
adds a Base64 copy of the archive and allows `v_ase gui FILE.html`. Disable it
for a smaller view-only file. On macOS, Finder/Quick Look displays the embedded
optimized poster without running the browser renderer or requiring v_ase.

The terminal remains occupied while the browser document is active unless
`--no-block` or `--cli` is used. Close the document or stop the process after
the export has been verified.

## Local, WSL, And Remote Use

Loopback ports are selected automatically when `--port` is omitted.

In WSL or a headless environment, `gio` may report `Operation not supported`.
The server is still valid. v_ase always prints the complete
`http://127.0.0.1:...` URL before waiting, including when a WSL browser command
reports success but no tab appears. Ctrl+click it or paste it into the local
browser; keep the terminal process running.

Use `HOST:/absolute/server/path/FILE` to keep parsing and trajectory storage on
an SSH host. For example, with a host configured as `physics`:

```bash
v_ase gui physics:/absolute/server/path/trajectory.extxyz
```

No explicit port is needed. The local launcher starts the remote backend and
the local forward on one SSH connection, which pins both ends to the same login
node even when a cluster alias is load balanced. The source file itself is
never downloaded.

The remote process owns source-file I/O, ASE parsing, trajectory caching,
volumetric sampling/isosurface generation, and backend calculations. The local
browser owns UI interaction and WebGL rendering. Only requested frame or
derived rendering payloads cross the encrypted tunnel. v_ase must therefore be
installed remotely so that the Python backend and ASE dependencies execute
next to the data.

Current View-mode XDATCAR files are indexed by coordinate byte offset and
native ASE `.traj` files use their random-access container. Startup reads only
the first selected frame; later frames are parsed remotely on demand. Do not
download a remote trajectory as a performance workaround. An uncommon
XDATCAR header that the fast path cannot prove safe is sent to ASE's compatible
reader automatically. Edit mode may materialize the trajectory because
physical topology operations require editable ASE frame objects.

If the remote `v_ase` entry point is not available to a non-interactive SSH
shell, select its Python executable directly for one launch:

```bash
v_ase gui physics:/absolute/server/path/trajectory.extxyz \
  --remote-python /home/user/miniconda3/envs/vase/bin/python
```

For a stable host environment, persist the same exact executable locally:

```bash
v_ase remote configure physics \
  --python /home/user/miniconda3/envs/vase/bin/python
v_ase remote show physics
v_ase gui physics:/absolute/server/path/trajectory.extxyz
```

Precedence is transient `--remote-python`, saved exact-host mapping, then the
remote `PATH` entry point. Remove a mapping with `v_ase remote remove physics`.
These commands never source `.bashrc`, activate Conda, copy the remote source,
or store SSH credentials. Configure the exact `USER@HOST`/alias string used to
the left of `:`; differently written hosts are intentionally separate.

The launcher reads remote `v_ase gui --help` and passes only supported options.
Treat an upgrade warning as a request to update before opening large
trajectories or using a newly added backend feature:

```bash
ssh physics 'python -m pip install --upgrade v_ase-gui'
```

`ERR_CONNECTION_RESET` immediately after remote startup indicates a local
launcher older than 0.2.17 on a load-balanced cluster. Upgrade the local
installation; do not copy the source file locally as a workaround.

An explicit feature that cannot be preserved is never silently removed. For
example, requesting FP64 volumetric data from a remote CLI without
`--volumetric-precision` stops with an upgrade instruction.

Manual tunnel fallback:

```bash
ssh -L 8765:127.0.0.1:REMOTE_PORT physics
```

Then open the forwarded local URL. Do not expose the Uvicorn listener directly
to an untrusted network.

## Runtime Constraints

- Codex, Claude Code, ChatGPT desktop agents, Gemini-based agents, agentic
  IDEs, and other local models can control the same live browser API when they
  have local shell and browser access. Follow `agent-setup.md`; do not assume a
  vendor-specific skill directory when one is not documented.
- A hosted chat environment without shell or browser access can read this skill
  but cannot operate v_ase directly.
- A sandbox without package installation must already contain v_ase and its
  dependencies.
- Browser-native video capture requires a Chromium-family browser with
  `MediaRecorder`.
- 3DM export requires the optional `rhino3dm` dependency.
- Volumetric input is bounded by `V_ASE_MAX_VOLUMETRIC_POINTS`. Keep the
  default safety limit unless the machine has enough memory for the complete
  grid and extracted surface. The backend keeps the scalar grid and sends only
  an aligned binary mesh to the browser; identical mesh requests use a bounded
  cache.
- Very large trajectories should use `--stream-frames`; do not preload every
  coordinate into an agent context.
- Per-atom colorscale catalogs include finite numeric LAMMPS atom columns.
  Full-trajectory range fitting uses one bounded scalar cache when eligible
  and otherwise computes extrema in the backend.
