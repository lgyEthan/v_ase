# v_ase

View, edit, analyze, and render atomic structures, trajectories, and volumetric
data in an ASE-native workspace.

## Download and install

**[Download for macOS or Windows](https://v-ase.readthedocs.io/en/latest/desktop.html#choose-a-download)**
from the desktop guide. Choose the installer or ZIP for your computer. Python
is included in the desktop app.

For Linux, Jupyter, or an existing Python 3.10+ environment, install from
[PyPI](https://pypi.org/project/v-ase-gui/).

```bash
python -m pip install v_ase-gui
v_ase gui
```

## Open, edit, and save

1. Choose **File → Open** or drop a structure file into the window. v_ase reads
   extended XYZ, ASE trajectories, CIF, VASP files, and [other formats](https://v-ase.readthedocs.io/en/latest/formats.html).
2. Use **View only** to inspect or play a trajectory. Switch to **Edit structure**
   to change atoms, coordinates, or the cell.
3. Save a `.vase` project to keep editing later. Use
   [Export HTML View](https://v-ase.readthedocs.io/en/latest/save-projects.html#html-view)
   to share an interactive view, or **Render → Image** to save a figure.

## User guides

- [Quick start](https://v-ase.readthedocs.io/en/latest/quickstart.html) · [Example files](https://v-ase.readthedocs.io/en/latest/example-inputs.html) · [Keyboard shortcuts](https://v-ase.readthedocs.io/en/latest/shortcuts.html)
- [Build and edit structures](https://v-ase.readthedocs.io/en/latest/worked-examples.html) · [Trajectories and analysis](https://v-ase.readthedocs.io/en/latest/trajectories-analysis.html) · [Render and export](https://v-ase.readthedocs.io/en/latest/render-images.html)
- [Python and Jupyter](https://v-ase.readthedocs.io/en/latest/notebooks-remote.html) · [Connect an AI agent](https://v-ase.readthedocs.io/en/latest/agent-setup.html) · [Troubleshooting](https://v-ase.readthedocs.io/en/latest/troubleshooting.html)

[Release notes](https://github.com/lgyEthan/v_ase/releases) · [AGPL-3.0-or-later](LICENSE)
