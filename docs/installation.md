# Install v_ase

Choose the installation that fits how you work:

| Use v_ase with… | Start here |
| --- | --- |
| A Mac or Windows desktop app | [Desktop installation](desktop.md); Python is included. |
| Python, Jupyter or a browser on Linux | Install the Python package below. |
| A remote workstation or cluster | [Remote setup](notebooks-remote.md). |

(pypi-installation)=

## Python installation

Use Python **3.10 or newer**. Install the package and open a structure:

```bash
python -m pip install v_ase-gui
v_ase gui POSCAR
```

`v_ase gui` without a filename opens an empty workspace. Keep the terminal open
while using the browser editor. Required scientific packages, including ASE,
are installed automatically. You do not need Node.js or an online account.

### Use a virtual environment

A separate environment avoids conflicts with other scientific packages.

```bash
python -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

Or on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then install and verify:

```bash
python -m pip install v_ase-gui
v_ase --version
```

## Conda or Mamba

```bash
conda create -n vase python=3.12 -y
conda activate vase
python -m pip install v_ase-gui
```

Use `python -m pip` from the activated environment so v_ase and your scientific
packages use the same Python.

## Optional Rhino export

For Rhino `.3dm` export in a Python installation:

```bash
python -m pip install "v_ase-gui[rhino]"
```

The desktop app already includes this option. Blender and OBJ exports need no
additional v_ase package. [Export guide](export-structures.md).

## Browser and network model

The Python installation opens the editor in your browser and processes data
locally. If the browser does not open automatically:

```bash
v_ase gui POSCAR --no-browser
```

Open the printed local URL on the same computer. For remote work, follow
[Notebooks and remote systems](notebooks-remote.md).

## Platform notes

Use a browser with WebGL enabled. On Linux servers without a desktop, use the
remote workflow. Under WSL, open the printed local URL manually if automatic
browser launching is unavailable. [Troubleshooting](troubleshooting.md).

## Upgrade and uninstall

```bash
python -m pip install --upgrade v_ase-gui
python -m pip uninstall v_ase-gui
```

When using a remote host, update both installations to the same version.
Desktop updates are described in [Update or uninstall](desktop.md#update-or-uninstall).

## Source checkout

To change v_ase itself, see [Contributing](development.md). A source checkout is
not needed for normal use.

## Next step

Open a structure and follow [First steps](quickstart.md).
