# Installation

v_ase requires CPython 3.10 or newer. This experimental symmetry build and its
validation matrix cover Python 3.10 through 3.13. Install the distribution
named `v_ase-gui`; it provides the Python package and terminal command both
named `v_ase`.

## Symmetry branch installation

Using a dedicated virtual environment avoids binary conflicts with an older
NumPy/SciPy stack:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
git clone --branch symmetry https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e ".[symmetry,phonon]"
```

Verify the executable and Python import:

```bash
v_ase --version
python -c "import v_ase; print(v_ase.__version__)"
```

The installed runtime includes ASE, FastAPI/Uvicorn, NumPy, SciPy,
scikit-image, Plotly, Matplotlib, Pillow, imageio-ffmpeg, and a Python-version
appropriate matscipy build. Node.js and a hosted account are not required.

## Conda or Mamba

Create the environment first, then use that environment's Python to install
the isolated branch checkout:

```bash
conda create -n vase python=3.12 -y
conda activate vase
git clone --branch symmetry https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e ".[symmetry,phonon]"
```

Use `python -m pip`, not a bare `pip`, when more than one Python installation
is present. Both `python -m pip --version` and `which v_ase` (Windows:
`where v_ase`) should point into the same environment.

## Source checkout

For a fresh or development checkout:

```bash
git clone --branch symmetry https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e ".[symmetry,phonon]"
```

Install development dependencies to run the complete test and packaging suite:

```bash
python -m pip install -e ".[dev,symmetry,phonon]"
python -m playwright install chromium
```

## Optional Rhino export

OBJ/MTL export uses the standard library. Rhino `.3dm` export requires the
optional dependency:

```bash
python -m pip install -e ".[symmetry,phonon,rhino]"
```

The option only changes 3DM availability; normal viewing, editing, analysis,
image, video, HTML, OBJ, and Blender export do not require `rhino3dm`.

## Browser and network model

v_ase starts a loopback-only HTTP/WebSocket server and opens a normal browser
tab. The scientific Python objects and source files stay in the Python process;
the browser receives the data needed for the active document and renders with
WebGL. The application does not require an external web service.

If a browser cannot be launched automatically:

```bash
v_ase gui POSCAR --no-browser
```

Open the printed `http://127.0.0.1:...` URL on the same computer. Closing the
last v_ase browser page normally finalizes a blocking CLI/Python session.

## Platform notes

### Linux

Use any recent Chromium-, Firefox-, or WebKit-based browser with WebGL enabled.
On a headless node, use `--no-browser`, an SSH tunnel, or the one-command remote
workflow in [Notebooks and remote systems](notebooks-remote.md).

### macOS

The default browser is opened with the operating-system launcher. A project
HTML file can also include an optimized poster used by Finder/Quick Look.

### Windows and WSL

Native Windows Python uses the configured default browser. Under WSL, v_ase
tries Windows-aware launchers before Linux desktop helpers. If interop is not
available, use `--no-browser` and open the printed loopback URL manually.

## Update and uninstall

```bash
git pull --ff-only origin symmetry
python -m pip install -e ".[symmetry,phonon]"
python -m pip uninstall v_ase-gui
```

The PyPI package follows production `main`; it does not contain this
experimental branch.

For a remote `HOST:/path` workflow, keep the local and remote installations on
the same release so their browser, backend, and semantic schemas agree.

## Next step

Continue with [First session](quickstart.md). If installation succeeds but the
application does not open or import, use [Troubleshooting](troubleshooting.md).
