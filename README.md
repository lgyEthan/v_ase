<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Documentation Status](https://readthedocs.org/projects/v-ase/badge/?version=latest)](https://v-ase.readthedocs.io/en/latest/?badge=latest)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-2f855a.svg)](LICENSE)

[Documentation](https://v-ase.readthedocs.io/en/latest/) ·
[PyPI](https://pypi.org/project/v-ase-gui/) ·
[Changelog](https://v-ase.readthedocs.io/en/latest/whats-new.html) ·
[Issues](https://github.com/lgyEthan/v_ase/issues) ·
[Software paper and LaTeX source](paper/joss/README.md)

**0.3.5 · Coordination polyhedra** · [Changes](https://v-ase.readthedocs.io/en/latest/whats-new.html)

An ASE-native workspace for building, editing and visualizing atomic structures,
trajectories and volumetric data.

![Phosphorene nanoribbon manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

## Installation And Launch

```bash
python -m pip install v_ase-gui
v_ase gui POSCAR
```

Use `v_ase gui` for an empty workspace or `--interactive` to edit a file.
[Installation](https://v-ase.readthedocs.io/en/latest/installation.html) · [First session](https://v-ase.readthedocs.io/en/latest/quickstart.html) ·
[Supported formats](https://v-ase.readthedocs.io/en/latest/formats.html) · [Troubleshooting](https://v-ase.readthedocs.io/en/latest/troubleshooting.html)

## Explore

| Work with | Guide |
| --- | --- |
| Atoms and molecules | [Move](https://v-ase.readthedocs.io/en/latest/move.html) · [Rotate](https://v-ase.readthedocs.io/en/latest/rotate.html) · [Build](https://v-ase.readthedocs.io/en/latest/build-atoms.html) |
| Periodic interfaces | [Cells, matching, registry](https://v-ase.readthedocs.io/en/latest/cell-tools.html) |
| Trajectories and fields | [Analysis](https://v-ase.readthedocs.io/en/latest/trajectories.html) · [Volumetric data](https://v-ase.readthedocs.io/en/latest/field-processing.html) |
| Figures and projects | [Appearance](https://v-ase.readthedocs.io/en/latest/appearance.html) · [Export](https://v-ase.readthedocs.io/en/latest/save-projects.html) |
| AI agents | [MCP setup](https://v-ase.readthedocs.io/en/latest/ai-tools.html) · [GUI/MCP comparison](https://v-ase.readthedocs.io/en/latest/agent-material-evaluation.html) |
| Numerical methods | [Validation](https://v-ase.readthedocs.io/en/latest/scientific-validation.html) · [Source audit](docs/scientific-source-audit.md) |

## Save And Share

One HTML file for offline viewing and project recovery.
[Project HTML](https://v-ase.readthedocs.io/en/latest/save-projects.html#project-html) · [Export HTML View](https://v-ase.readthedocs.io/en/latest/save-projects.html#html-view)

![A self-contained v_ase HTML project with a static preview and offline 3D interaction](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_html_quicklook.gif)

## Work With An AI Agent

You and an external agent edit the same live document.
[Connect MCP](https://v-ase.readthedocs.io/en/latest/ai-tools.html#install-and-connect-an-mcp-client) ·
[Scene workflow](https://v-ase.readthedocs.io/en/latest/ai-scene.html) · [CLI compatibility](https://v-ase.readthedocs.io/en/latest/ai-cli.html)

[ChatGPT Chat setup](https://v-ase.readthedocs.io/en/latest/chatgpt-local.html) · personal connection.

![Human and external AI agent working in one live v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.png)

```bash
python -m pip install "v_ase-gui[mcp]"
v_ase mcp
```

**60-run comparison:** MCP completed 30/30 strict targets; GUI completed 24/30.
[Images, token usage and success criteria](https://v-ase.readthedocs.io/en/latest/agent-material-evaluation.html)

![A natural-language request passing through an external AI Agent into the same live revisioned v_ase GUI](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.gif)

Exact atom edits from a natural-language request.
[Agent workflow](https://v-ase.readthedocs.io/en/latest/ai-agents.html#share-one-document) ·
[Bundled Skill](v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md)

![Natural-language pyridinic N3 graphene edit in the shared GUI](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_edit.gif)

## Edit Structures

Select atoms, then use `G` to move, `R` to rotate and `S` to scale coordinates.
[Editing guide](https://v-ase.readthedocs.io/en/latest/editing.html#move-rotate-and-scale-coordinates) · [Controls](https://v-ase.readthedocs.io/en/latest/shortcuts.html)

### Build From Scratch

Define a cell and distribute atoms; refine overlaps with repulsion.
[Atomic distributions](https://v-ase.readthedocs.io/en/latest/atomic-distributions.html) · [ASE crystal builder](https://v-ase.readthedocs.io/en/latest/build-atoms.html#build-a-periodic-bulk-crystal-with-ase)

![Building an amorphous structure from an empty v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_scratch_amorphous.gif)

### Add Atoms

Set composition, density, placement and allowed regions.
[Insertion workflow](https://v-ase.readthedocs.io/en/latest/insertion-regions.html)

![Oxygen distributed through a bulk-like Cu(111) insertion region](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_atoms_allowed.gif)

### Add Molecules

Place rigid molecules around an existing structure.
[Molecular insertion](https://v-ase.readthedocs.io/en/latest/atomic-distributions.html#insert-rigid-molecules)

![Rigid water molecules placed around edge- and basal-hydroxylated graphene-oxide layers](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_molecules.gif)

### Rotate Selected Atoms

Rotate around an active atom, center of mass or explicit pivot.
[Pivot controls](https://v-ase.readthedocs.io/en/latest/rotate.html)

![Ferrocene pivot rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_pivot.gif)

Build a phosphorene twist through successive selections and rotations.
[Worked examples](https://v-ase.readthedocs.io/en/latest/worked-examples.html)

![Cumulative phosphorene manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

## Periodic Cells And Interfaces

### Commensurate Cells

Find compatible 2D cells within declared strain and search limits.
[Same-lattice matching](https://v-ase.readthedocs.io/en/latest/commensurate.html#commensurate-same-lattice-rotation)

![Graphene hBN commensurate rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate.gif)

Match separate host and guest lattices.
[Host/guest workflow](https://v-ase.readthedocs.io/en/latest/commensurate.html)

![Graphene and MoS2 host/guest common-cell search with a live angle plane](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate_host_guest.gif)

### Rigid Translation

Map registry or relax a selected rigid component.
[Registry maps](https://v-ase.readthedocs.io/en/latest/registry.html#registry-maps) · [Rigid relaxation](https://v-ase.readthedocs.io/en/latest/registry.html#rigid-registry-relaxation)

![Periodic planar translation scan with current and optimum translations](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_registry_map.png)

![Rigid planar translation trials without a precomputed colorscale map](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_registry_relax.gif)

## Analyze Structures And Fields

### Ordered Geometry

Select 2, 3 or 4 atoms for distance, angle or torsion.
[Measurements](https://v-ase.readthedocs.io/en/latest/selection.html#ordered-geometry-through-a-trajectory)

![Ordered distance angle and torsion measurement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_measurement.gif)

### Trajectories And Displacement

Scrub frames and inspect displacement against a reference.
[Trajectory analysis](https://v-ase.readthedocs.io/en/latest/vectors.html#displacement-analysis)

![Trajectory displacement analysis](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_displacement.png)

### Map Per-Atom Data

Color atoms by stored properties and display force vectors.
[Colorscales](https://v-ase.readthedocs.io/en/latest/scalar-colors.html#map-numeric-per-atom-data) · [Forces](https://v-ase.readthedocs.io/en/latest/vectors.html#stored-force-vectors)

![Trajectory-wide force-magnitude colorscale with locked limits and matching Cartesian force vectors](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_atom_colorscale.gif)

### Volumetric Fields

Inspect charge, potential and orbital grids as isosurfaces or planar sections.
[Isosurfaces](https://v-ase.readthedocs.io/en/latest/isosurfaces.html#create-an-isosurface) · [Planes](https://v-ase.readthedocs.io/en/latest/field-planes.html#add-planar-sections) ·
[Combine fields](https://v-ase.readthedocs.io/en/latest/field-processing.html#combine-compatible-datasets)

![Signed isosurface threshold moving across a fixed volumetric distribution](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric.gif)

![Interactive hkl scalar-field plane clipped to the displayed cell](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric_plane.gif)

### Radial And Pair-distribution Functions

Plot periodic RDFs or finite pair distributions with the appropriate normalization.
[RDF guide](https://v-ase.readthedocs.io/en/latest/rdf.html)

![Pairwise amorphous Cu-Zr RDF curves approaching the bulk limit](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_rdf.png)

## Constraints And Relaxation

Constrain physical motion using ASE constraints.
[Constraint guide](https://v-ase.readthedocs.io/en/latest/constraints.html#supported-constraint-state)

### FixedLine

Restrict motion to a line. [Details](https://v-ase.readthedocs.io/en/latest/constraints.html#fixedline)

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

### FixedPlane And FixScaled

Restrict motion in Cartesian or fractional directions.
[FixedPlane](https://v-ase.readthedocs.io/en/latest/constraints.html#fixedplane) · [FixScaled](https://v-ase.readthedocs.io/en/latest/constraints.html#fixscaled-and-fixcartesian)

![FixedPlane movement and guide plane](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

### Hookean

Apply spring-like restraints. [Details](https://v-ase.readthedocs.io/en/latest/constraints.html#hookean)

![Hookean constraint](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.png)

![Hookean motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

### Relaxation

Reduce overlaps or optimize with a configured calculator.
[Repulsion](https://v-ase.readthedocs.io/en/latest/relaxation.html#built-in-repulsion-calculator) · [Run relaxation](https://v-ase.readthedocs.io/en/latest/relaxation.html#run-an-ordinary-relaxation)

![Repulsive relaxation trajectory](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_relaxation.gif)

## Coordination Polyhedra

Color coordination cages and adjust opacity by element, label, or atom group.
[Polyhedra guide](https://v-ase.readthedocs.io/en/latest/polyhedra.html)

![IrO2 coordination polyhedra with independent colors and face opacity](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_polyhedra.gif)

## Style Atoms, Bonds, And Rendering

Control colors, radii and visibility by label or atom index.
[Appearance](https://v-ase.readthedocs.io/en/latest/appearance.html#per-atom-overrides)

![View-mode label and appearance editing on Cu5O4](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_cu5o4_view_appearance.gif)

Choose Standard, Metal, Rubber or flat 2D rendering.
[Materials and rendering](https://v-ase.readthedocs.io/en/latest/appearance.html#d-and-flat-2d-rendering)

![Standard Metal and Rubber atom materials](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_materials.png)

Set bond topology and appearance by pair or exact atom indices.
[Bond controls](https://v-ase.readthedocs.io/en/latest/bonds.html)

![Pairwise Cu O bonds in a Cu2O(111) film on Cu(111)](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_bonds.png)

## Export And Save

[Images and video](https://v-ase.readthedocs.io/en/latest/render-images.html#image-output) ·
[Render Area](https://v-ase.readthedocs.io/en/latest/render-images.html#render-area) ·
[Blender / OBJ / Rhino](https://v-ase.readthedocs.io/en/latest/export-structures.html#d-scene-output) ·
[Projects and presets](https://v-ase.readthedocs.io/en/latest/save-projects.html#save-project)

## Python And Remote Systems

```python
from ase.build import molecule
from v_ase import view

view(molecule("H2O"))
```

[Python API](https://v-ase.readthedocs.io/en/latest/python-api.html) · [Jupyter](https://v-ase.readthedocs.io/en/latest/notebooks-remote.html#jupyter-auto-detection) ·
[SSH / remote files](https://v-ase.readthedocs.io/en/latest/notebooks-remote.html#one-command-remote-files)

## License And Citation

[AGPL-3.0-or-later](LICENSE) · [Three.js MIT license](v_ase/static/vendor/THREE_LICENSE) · [Cite v_ase](CITATION.cff)
