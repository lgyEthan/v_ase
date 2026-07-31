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
python -m pip install "v_ase-gui==0.1.6"
```

Optional Rhino export:

```bash
python -m pip install "v_ase-gui[rhino]==0.1.6"
```

Runtime dependencies are ASE, FastAPI, Uvicorn, NumPy, SciPy, scikit-image,
Plotly, imageio-ffmpeg, and Pillow. No Node.js runtime, API key, or hosted
account is required.

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
file unless `--force` is explicitly passed. The user may speak natural
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

Volumetric inputs may be opened directly or loaded into an existing document:

- VASP `CHGCAR`/`CHG`, `LOCPOT`, `PARCHG`, and `ELFCAR`;
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

## Output And Lifecycle

The human GUI uses the operating-system save picker before expensive encoding.
The semantic API returns binary exports as data URLs with filename, MIME type,
and byte count. `v_ase api ... --save OUTPUT` decodes them directly.

Main outputs:

- structure: POSCAR or ASE pickle;
- image: PNG by default, or JPEG, PDF, and lossless WebP;
- trajectory movie: MOV/H.264 or AVI/MPEG-4;
- editable scene: Blender Python, Rhino 3DM, or OBJ bundle;
- shareable view: one offline view-only HTML document with optional embedded `.vase` recovery;
- complete session: `.vase`;
- reusable appearance: visual settings JSON.
- analysis table: total and pairwise RDF as CSV.

Use `.vase` as the canonical editable project. Use HTML when the recipient
should inspect the saved 3D scene and trajectory in a browser without
installing v_ase. HTML always includes the renderer and browser scene data.
Set **Embed editable .vase project** when lossless recovery is required; this
adds a Base64 copy of the archive and allows `v_ase gui FILE.html`. Disable it
for a smaller view-only file.

The terminal remains occupied while the browser document is active unless
`--no-block` or `--cli` is used. Close the document or stop the process after
the export has been verified.

## Local, WSL, And Remote Use

Loopback ports are selected automatically when `--port` is omitted.

In WSL or a headless environment, `gio` may report `Operation not supported`.
The server is still valid. Open the printed `http://127.0.0.1:...` URL in the
local browser.

Use `HOST:/absolute/server/path/FILE` to keep parsing and trajectory storage on
an SSH host. For example, with a host configured as `physics`:

```bash
v_ase gui physics:/absolute/server/path/trajectory.extxyz
```

The local browser receives only frame data needed for visualization. The source
file itself is not downloaded.

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
  grid and extracted surface.
- Very large trajectories should use `--stream-frames`; do not preload every
  coordinate into an agent context.
