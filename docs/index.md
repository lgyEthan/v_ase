:::{image} assets/v_ase-logo.png
:alt: v_ase
:width: 720px
:align: center
:::

# v_ase documentation

v_ase is a local, browser-based viewer, editor, and analysis workspace for
[Atomic Simulation Environment (ASE)](https://ase-lib.org/) structures,
trajectories, and volumetric fields. It combines terminal and Python entry
points with a direct 3D editor, scientific analysis, reproducible rendering,
portable projects, and an exact semantic interface for external AI agents.

:::{admonition} Current release
:class: note
This manual describes **v_ase 0.2.35a1+symmetry**. This experimental build is
synchronized from main 0.2.35, distributed only from the `symmetry` branch,
and not published to PyPI.
:::

## Start here

Install and open a structure:

```bash
git clone --branch symmetry https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e ".[symmetry,phonon]"
v_ase gui POSCAR
```

Or launch from Python:

```python
from ase.build import molecule
from v_ase import view

view(molecule("H2O"))
```

The default file workflow starts in lightweight **View** mode. Switch to
**Edit** when coordinates, topology, constraints, or relaxation must change.
Running `v_ase gui` without a file opens an empty editable document.

## What v_ase covers

| Area | Included workflows |
| --- | --- |
| Inspect | Large structures, lazy trajectories, labels and ASE arrays, ordered measurements, supercell replicas |
| Edit | Exact move/rotate/scale, add atoms and molecules, ASE bulk building, copy/paste, constraints, undo/redo |
| Analyze | Displacement, stored forces, periodic RDF, finite pair distributions, registry maps, space groups, standard cells, reciprocal paths, and phonon modes |
| Fields | VASP density/potential/ELF, Gaussian Cube and XSF, combinations, slices, isosurfaces, repetition |
| Interfaces | Local CLI, Python API, Jupyter display, one-command SSH remote use, multi-document workspaces |
| Output | Structures, `.vase`, project HTML, view-only HTML, images, video, Blender, OBJ, and optional Rhino 3DM |
| Collaboration | Revisioned semantic state and commands shared by the live GUI, terminal automation, and external AI agents |

![v_ase structure-editing overview](assets/readme_overview.png)

## Choose a path

- New users should follow [Installation](installation.md),
  [First session](quickstart.md), and [Workspace model](workspace.md).
- Users preparing figures should read [Visualization and styling](visualization.md)
  and [Projects, rendering, and export](projects-export.md).
- Atomistic workflow users can jump to [Editing structures](editing.md),
  [Constraints and relaxation](constraints-relaxation.md), or
  [Trajectories and analysis](trajectories-analysis.md).
- Symmetry and lattice-dynamics users should read
  [Symmetry and phonon methodology](symmetry_and_phonons.md).
- Python and automation users should start with the [Python API](python-api.md),
  [CLI reference](cli-reference.md), or [AI-agent integration](ai-agents.md).
- Maintainers can use the implementation contracts and release checklist under
  **Developer documentation** in the navigation.

```{toctree}
:maxdepth: 2
:caption: Getting started
:hidden:

installation
quickstart
workspace
whats-new
```

```{toctree}
:maxdepth: 2
:caption: User guide
:hidden:

data-input
visualization
editing
worked-examples
constraints-relaxation
trajectories-analysis
symmetry_and_phonons
volumetric-guide
periodic-interfaces
projects-export
```

```{toctree}
:maxdepth: 2
:caption: Interfaces and automation
:hidden:

python-api
cli-reference
notebooks-remote
ai-agents
```

```{toctree}
:maxdepth: 2
:caption: Reference
:hidden:

formats
shortcuts
api
troubleshooting
```

```{toctree}
:maxdepth: 2
:caption: Developer documentation
:hidden:

features
current_progress
performance
unit_cell_aware_rotate
commensurate_validation
contributing-docs
release_checklist
```

## Project links

- [Source repository](https://github.com/lgyEthan/v_ase)
- [Production PyPI package (main only)](https://pypi.org/project/v-ase-gui/)
- [Issue tracker](https://github.com/lgyEthan/v_ase/issues)
- [License](https://github.com/lgyEthan/v_ase/blob/symmetry/LICENSE)
