# v_ase user guide

Build, explore and present atomic structures, trajectories and volumetric data.
Start with the desktop app or use v_ase from Python and Jupyter.

[Install v_ase](installation.md) · [First steps](quickstart.md) ·
[Example files](example-inputs.md) · [Keyboard shortcuts](shortcuts.md)

```{vase-demo} logo
:alt: Interactive v_ase atom logo
:fallback: assets/v_ase-logo.png
:height: 300
:caption: Drag to rotate the atomic logo.
```

(find-a-feature)=

## Choose your task

| I want to… | Guide |
| --- | --- |
| Open a structure or trajectory | [Open files](data-input.md) · [Supported formats](formats.md) |
| Find a control or understand View/Edit | [Workspace](workspace.md) |
| Change atom colors, size or materials | [Atom appearance](appearance.md) · [Property colors](scalar-colors.md) · [Property radii](property-radius.md) |
| Set bonds, show polyhedra or display water | [Bonds](bonds.md) · [Polyhedra](polyhedra.md) · [Water](water-surface.md) |
| Move, rotate or add atoms | [Move](move.md) · [Rotate](rotate.md) · [Build](build-atoms.md) |
| Hold atoms fixed and relax a structure | [Constraints](constraints.md) · [Relaxation](relaxation.md) |
| Work with periodic cells and interfaces | [Cell tools](cell-tools.md) · [Commensurate cells](commensurate.md) · [Registry maps](registry.md) |
| Inspect simulation results | [Trajectories](trajectories.md) · [RDF](rdf.md) · [Force vectors](vectors.md) |
| Explore volumetric data | [Isosurfaces](isosurfaces.md) · [Cross-sections](field-planes.md) |
| Save a project or share a figure | [Projects and HTML](save-projects.md) · [Images](render-images.md) · [Movies and GIFs](export-video.md) |
| Continue a scene in Blender | [3D export](export-structures.md#blender) |
| Connect an AI agent | [MCP setup](ai-tools.md) · [ChatGPT](chatgpt-local.md) |

Each guide includes the controls and examples for that task. If something does
not work, start with [Troubleshooting](troubleshooting.md).

This manual describes **v_ase 0.4.13**. [What's new](whats-new.md).

```{toctree}
:caption: Get started
:maxdepth: 1
:hidden:

installation
desktop
quickstart
workspace
data-input
example-inputs
worked-examples
```

```{toctree}
:caption: Appearance
:maxdepth: 1
:hidden:

appearance
property-radius
scalar-colors
vectors
bonds
polyhedra
water-surface
isosurfaces
field-planes
camera
```

```{toctree}
:caption: Edit structures
:maxdepth: 1
:hidden:

selection
move
rotate
scale
build-atoms
atomic-distributions
insertion-regions
molecules
constraints
relaxation
```

```{toctree}
:caption: Cells and interfaces
:maxdepth: 1
:hidden:

cell-tools
commensurate
registry
```

```{toctree}
:caption: Analysis and fields
:maxdepth: 1
:hidden:

trajectories
rdf
field-processing
```

```{toctree}
:caption: Save and export
:maxdepth: 1
:hidden:

render-images
save-projects
export-video
export-structures
```

```{toctree}
:caption: AI and scripting
:maxdepth: 1
:hidden:

chatgpt-local
ai-agents
ai-scene
python-api
cli-reference
notebooks-remote
```

```{toctree}
:caption: Reference
:maxdepth: 1
:hidden:

shortcuts
formats
troubleshooting
scientific-validation
agent-material-evaluation
api
whats-new
```

```{toctree}
:caption: Contributing
:maxdepth: 1
:hidden:

development
```
