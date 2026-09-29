<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

**Build, explore and present atomic structures.** v_ase brings ASE structures,
trajectories and volumetric data into an interactive 3D workspace.
Use the desktop app, a browser or Jupyter.

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Documentation](https://readthedocs.org/projects/v-ase/badge/?version=latest)](https://v-ase.readthedocs.io/en/latest/)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-2f855a.svg)](LICENSE)

[Download the desktop app](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.9) ·
[User guide](https://v-ase.readthedocs.io/en/latest/) ·
[First steps](https://v-ase.readthedocs.io/en/latest/quickstart.html) ·
[Examples](https://v-ase.readthedocs.io/en/latest/example-inputs.html)

![Building a twisted phosphorene ribbon with successive atom selections and rotations](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

## Get v_ase

### Desktop app

Python is included. Download the installer for your computer:

| Computer | Download | Install |
| --- | --- | --- |
| Mac with Apple silicon, macOS 15+ | [Apple silicon DMG](https://github.com/lgyEthan/v_ase/releases/download/v0.4.9/v_ase-0.4.9-mac-arm64.dmg) | Open the DMG and drag **v_ase** into **Applications**. |
| Mac with Intel, macOS 15+ | [Intel DMG](https://github.com/lgyEthan/v_ase/releases/download/v0.4.9/v_ase-0.4.9-mac-x64.dmg) | Open the DMG and drag **v_ase** into **Applications**. |
| Windows 10/11, Intel or AMD 64-bit | [Windows installer](https://github.com/lgyEthan/v_ase/releases/download/v0.4.9/v_ase-0.4.9-win-x64.exe) | Run the installer, then open **v_ase** from Start. |

Open a file with **File → Open**, or drag it into the editor.
[Installation help and updates](https://v-ase.readthedocs.io/en/latest/desktop.html).

### Python and Jupyter

With Python 3.10 or newer:

```bash
python -m pip install v_ase-gui
v_ase gui POSCAR
```

Or open ASE objects directly:

```python
from ase.build import molecule
from v_ase import view

view(molecule("H2O"))
```

[Python installation](https://v-ase.readthedocs.io/en/latest/installation.html) ·
[Jupyter and remote systems](https://v-ase.readthedocs.io/en/latest/notebooks-remote.html) ·
[Supported formats](https://v-ase.readthedocs.io/en/latest/formats.html)

## Explore the workspace

| Task | Tools and guides |
| --- | --- |
| Inspect and style | [Atom colors and materials](https://v-ase.readthedocs.io/en/latest/appearance.html), [property-based radii](https://v-ase.readthedocs.io/en/latest/property-radius.html), [bonds](https://v-ase.readthedocs.io/en/latest/bonds.html), [polyhedra](https://v-ase.readthedocs.io/en/latest/polyhedra.html) |
| Build and edit | [Move](https://v-ase.readthedocs.io/en/latest/move.html), [rotate](https://v-ase.readthedocs.io/en/latest/rotate.html), [add atoms and molecules](https://v-ase.readthedocs.io/en/latest/build-atoms.html), [constraints](https://v-ase.readthedocs.io/en/latest/constraints.html), [relaxation](https://v-ase.readthedocs.io/en/latest/relaxation.html) |
| Work with periodic structures | [Cells and supercells](https://v-ase.readthedocs.io/en/latest/cell-tools.html), [commensurate interfaces](https://v-ase.readthedocs.io/en/latest/commensurate.html), [registry maps](https://v-ase.readthedocs.io/en/latest/registry.html) |
| Explore simulation results | [Trajectories](https://v-ase.readthedocs.io/en/latest/trajectories.html), [scalar colors](https://v-ase.readthedocs.io/en/latest/scalar-colors.html), [RDF](https://v-ase.readthedocs.io/en/latest/rdf.html), [isosurfaces](https://v-ase.readthedocs.io/en/latest/isosurfaces.html) |
| Prepare figures | [Camera and image output](https://v-ase.readthedocs.io/en/latest/render-images.html), [movies and GIFs](https://v-ase.readthedocs.io/en/latest/export-video.html), [Blender and 3D export](https://v-ase.readthedocs.io/en/latest/export-structures.html) |

**View** mode lets you explore data and adjust its appearance. Switch to **Edit**
to change the structure. Select atoms, then press `G` to move, `R` to rotate or
`S` to scale their spacing. [Keyboard and mouse controls](https://v-ase.readthedocs.io/en/latest/shortcuts.html).

## Build and edit

Place atoms or molecules inside a chosen region, remove close contacts, and
keep the parts of your structure that should remain fixed.
[Try molecular insertion](https://v-ase.readthedocs.io/en/latest/molecules.html).

![Water molecules placed around a layered graphene-oxide structure](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_molecules.gif)

## Visualize simulation results

Color atoms by charge, displacement or another stored property, and follow the
changes through a trajectory. [Property colors](https://v-ase.readthedocs.io/en/latest/scalar-colors.html).

![Atoms colored by a per-atom property during trajectory playback](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_atom_colorscale.gif)

Show water as a translucent surface while keeping ions and solids visible.
[Water surfaces](https://v-ase.readthedocs.io/en/latest/water-surface.html).

![Animated water surface around atomistic structures](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/water-surface-experiment.gif)

Explore volumetric data with isosurfaces and cross-sections.
[Isosurfaces](https://v-ase.readthedocs.io/en/latest/isosurfaces.html) ·
[Field planes](https://v-ase.readthedocs.io/en/latest/field-planes.html).

![Positive and negative volumetric isosurfaces around an atomic structure](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric.gif)

## Save and share

| You want to… | Use |
| --- | --- |
| Continue editing later | **Save** a `.vase` project. |
| Share an interactive view that opens in a browser | [Export HTML View](https://v-ase.readthedocs.io/en/latest/save-projects.html#html-view). |
| Share a browser view that can also reopen for editing | In **Project save settings**, enable **Include interactive rendered view** and save as HTML. |
| Publish a figure or animation | Export an image, movie or GIF from **Render**. |

[Saving projects](https://v-ase.readthedocs.io/en/latest/save-projects.html) ·
[Image output](https://v-ase.readthedocs.io/en/latest/render-images.html) ·
[Movies and GIFs](https://v-ase.readthedocs.io/en/latest/export-video.html)

## Work with an AI agent

Connect an MCP-capable agent to the same document you are editing. Ask it to
prepare a structure or figure, inspect the result in v_ase, and refine it by hand.

```bash
python -m pip install "v_ase-gui[mcp]"
v_ase mcp
```

[MCP setup](https://v-ase.readthedocs.io/en/latest/ai-tools.html#install-and-connect-an-mcp-client) ·
[Shared-document workflow](https://v-ase.readthedocs.io/en/latest/ai-agents.html#share-one-document) ·
[ChatGPT connection](https://v-ase.readthedocs.io/en/latest/chatgpt-local.html)

![A user and an AI agent refining the same atomic structure in v_ase](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.gif)

## Help and project information

[User guide](https://v-ase.readthedocs.io/en/latest/) ·
[Troubleshooting](https://v-ase.readthedocs.io/en/latest/troubleshooting.html) ·
[Report a problem](https://github.com/lgyEthan/v_ase/issues) ·
[What's new](https://v-ase.readthedocs.io/en/latest/whats-new.html)

[Scientific methods](https://v-ase.readthedocs.io/en/latest/scientific-validation.html) ·
[Contributing](https://v-ase.readthedocs.io/en/latest/development.html) ·
[Cite v_ase](CITATION.cff) · [AGPL-3.0-or-later](LICENSE) ·
[Third-party license](v_ase/static/vendor/THREE_LICENSE)
