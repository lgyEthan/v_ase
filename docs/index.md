# v_ase documentation

Inspect atomic structures, edit coordinates and create scientific figures.
Choose a feature below; the guides are independent, not a sequence of required steps.

[Install v_ase](installation.md) · [Open your first structure](quickstart.md) ·
[Download example inputs](example-inputs.md) · [Connect ChatGPT](chatgpt-local.md)

```{vase-demo} logo
:alt: Interactive v_ase atom logo
:fallback: assets/v_ase-logo.png
:height: 300
:caption: Drag to orbit this atomic scene. The feature guides below use downloadable example structures.
```

## Find a feature

| I want to… | Open this guide |
| --- | --- |
| Move an adsorbate along one axis | [Move atoms](move.md) |
| Rotate a ring around a metal atom | [Rotate atoms](rotate.md) |
| Show colored coordination polyhedra | [Polyhedra](polyhedra.md) |
| Color substrate and surface atoms differently | [Atom appearance](appearance.md) |
| Show fixed layers, allowed lines or planes | [Constraints](constraints.md) |
| Add atoms or fill a pore with molecules | [Distributions](atomic-distributions.md) · [Molecules](molecules.md) |
| Build a common periodic interface cell | [Commensurate cells](commensurate.md) |
| Plot RDF or color stored atom properties | [RDF](rdf.md) · [Scalar colors](scalar-colors.md) |
| Show field lobes or a cross-section | [Isosurfaces](isosurfaces.md) · [Planes](field-planes.md) |
| Save a figure, video or interactive project | [Images](render-images.md) · [Videos](export-video.md) · [Projects](save-projects.md) |

Each feature guide explains the controls first, then walks through a real example
with its input file, settings and expected result. **View** changes presentation;
**Edit** enables physical edits. [Workspace and modes](workspace.md).

This manual describes **v_ase 0.3.7**.
The [scientific source audit](scientific-source-audit.md) and
[ChatGPT tunnel helper](chatgpt-local.md) describe the numerical fixes and personal connection setup in this release.

```{toctree}
:caption: Get started
:maxdepth: 1
:hidden:

installation
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
bonds
polyhedra
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
vectors
scalar-colors
rdf
field-processing
isosurfaces
field-planes
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
development
whats-new
```
