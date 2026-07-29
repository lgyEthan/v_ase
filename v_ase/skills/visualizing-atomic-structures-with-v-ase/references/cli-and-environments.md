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
python -m pip install "v_ase-gui==0.0.107"
```

Optional Rhino export:

```bash
python -m pip install "v_ase-gui[rhino]==0.0.107"
```

Runtime dependencies are ASE, FastAPI, Uvicorn, NumPy, imageio-ffmpeg, and
Pillow. No Node.js runtime, API key, or hosted account is required.

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

Agent mode:

```bash
v_ase gui STRUCTURE --for-ai
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
| `--no-browser` | Print the URL without launching a browser |
| `--no-block` | Keep the server alive until interrupted |
| `--stream-frames` | Load trajectory coordinates frame by frame |
| `--show-bonds` / `--hide-bonds` | Override startup bond visibility |
| `--hide-cell` / `--hide-axes` | Hide viewport guides at startup |

`--for-ai` implies a nonblocking, no-browser session and prints one JSON
handshake. Keep the process alive until work is complete.

Python API:

```python
from v_ase.visualize import view

editor = view(atoms_or_frames, notebook=False, block=False)
print(editor.url)
```

## Input Formats

ASE-readable structures and trajectories are supported. Common inputs include:

- POSCAR, CONTCAR, and arbitrary filenames forced with `--format POSCAR`;
- XDATCAR and `vasprun.xml`;
- XYZ and extended XYZ;
- ASE `.traj`;
- LAMMPS dump/`lammpstrj` and LAMMPS data;
- CIF and other formats registered by ASE;
- self-contained `.vase` projects.

Use `--format` when the filename does not identify the reader:

```bash
v_ase gui ABCD --format vasprun.xml
v_ase gui INPUT --format lammps-data
```

The semantic state keeps visual labels separate from ASE chemical symbols.
Custom labels such as `O_bridge` remain labels while the backend element can
remain `O`.

## Output And Lifecycle

The human GUI uses the operating-system save picker before expensive encoding.
The semantic API returns binary exports as data URLs with filename, MIME type,
and byte count.

Main outputs:

- structure: POSCAR or ASE pickle;
- image: PNG by default, or JPEG, PDF, and lossless WebP;
- trajectory movie: MOV/H.264 or AVI/MPEG-4;
- editable scene: Blender Python, Rhino 3DM, or OBJ bundle;
- complete session: `.vase`;
- reusable appearance: visual settings JSON.

The terminal remains occupied while the browser document is active unless
`--no-block` or `--for-ai` is used. Close the document or stop the process after
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

- Claude Code, Codex, and desktop browser agents can launch the local CLI and
  control the live browser API.
- A hosted chat environment without shell or browser access can read this skill
  but cannot operate v_ase directly.
- A sandbox without package installation must already contain v_ase and its
  dependencies.
- Browser-native video capture requires a Chromium-family browser with
  `MediaRecorder`.
- 3DM export requires the optional `rhino3dm` dependency.
- Very large trajectories should use `--stream-frames`; do not preload every
  coordinate into an agent context.
