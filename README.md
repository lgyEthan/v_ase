<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

**Build structures. Explore simulations. Make figures.**
v_ase is an ASE-native workspace for atomic structures, trajectories and volumetric
data, available as a desktop app, in your browser and in Jupyter.

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Documentation](https://readthedocs.org/projects/v-ase/badge/?version=latest)](https://v-ase.readthedocs.io/en/latest/)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-2f855a.svg)](LICENSE)

[Download for Mac or Windows](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.11) ·
[Install with Python](#get-v_ase) ·
[User guide](https://v-ase.readthedocs.io/en/latest/) ·
[Example files](https://v-ase.readthedocs.io/en/latest/example-inputs.html)

**Shape a structure directly in the viewport.** Select successive parts of a
phosphorene ribbon and rotate them into a twist. These are coordinate edits,
with the camera kept in place.

![Successive atom selections and rotations turn a flat phosphorene ribbon into a twist](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

[Build and edit](#build-and-edit) · [Water and fields](#water-and-volumetric-fields) ·
[Periodic interfaces](#periodic-cells-and-interfaces) · [Appearance](#atoms-bonds-and-coordination) ·
[Trajectories and analysis](#trajectories-and-analysis) · [Constraints and relaxation](#constraints-and-relaxation) ·
[AI collaboration](#work-with-an-ai-agent) · [Rendering](#render-and-export) · [Save and share](#save-and-share)

## Build and edit

### Start from an empty cell

Create a cell, choose a composition and populate it with atoms. Build a crystal
with ASE, or prepare a disordered starting structure and remove close contacts.

![An empty workspace becomes a populated cell, followed by overlap relaxation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_scratch_amorphous.gif)

[Atomic distributions](https://v-ase.readthedocs.io/en/latest/atomic-distributions.html) ·
[Crystal and atom builders](https://v-ase.readthedocs.io/en/latest/build-atoms.html)

### Add atoms where you need them

Define an insertion region and control composition, density and allowed space.
Here, oxygen is added around an existing copper structure while the host remains in place.

![Oxygen atoms placed within a chosen region around copper, then relaxed](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_atoms_allowed.gif)

[Insertion regions and placement](https://v-ase.readthedocs.io/en/latest/insertion-regions.html)

### Fill pores and surround surfaces with molecules

Insert rigid molecules into a selected region, set their number or density,
and relax close contacts before keeping the result. This example places water
around hydroxylated graphene-oxide layers.

![Water molecules inserted and relaxed around a layered graphene-oxide structure](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_add_molecules.gif)

[Molecular insertion](https://v-ase.readthedocs.io/en/latest/molecules.html)

### Move, rotate and scale selected atoms

Use `G`, `R` and `S` for direct manipulation, or enter exact values. Rotate a
fragment about its center, an active atom or a chosen pivot; undo an edit when
trying another arrangement.

![A selected ferrocene ring rotates about an explicit pivot and axis](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_pivot.gif)

[Move](https://v-ase.readthedocs.io/en/latest/move.html) ·
[Rotate and choose a pivot](https://v-ase.readthedocs.io/en/latest/rotate.html) ·
[Scale](https://v-ase.readthedocs.io/en/latest/scale.html) ·
[Keyboard controls](https://v-ase.readthedocs.io/en/latest/shortcuts.html)

## Water and volumetric fields

### Show water as a continuous surface

Turn H₂O coordinates into a translucent water envelope while keeping ions and
solids visible. Adjust color, opacity, smoothing and lighting, and follow the
surface through a trajectory. This visualizes supplied coordinates; it does not run a fluid simulation.

![An animated translucent water surface surrounds ions and an atomistic membrane](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/water-surface-experiment.gif)

[Water surfaces](https://v-ase.readthedocs.io/en/latest/water-surface.html)

### Explore charge, potential and orbital fields

Display positive and negative isosurfaces, change the threshold, and control
color and transparency. The example below changes the isovalue of a fixed
signed field around a carbon structure.

![Positive and negative isosurfaces expand and contract as the isovalue changes](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric.gif)

[Isosurfaces](https://v-ase.readthedocs.io/en/latest/isosurfaces.html) ·
[Import and combine fields](https://v-ase.readthedocs.io/en/latest/field-processing.html)

### Slice through a scalar field

Move a colored section through the data to inspect what lies inside. Choose
Cartesian or crystallographic planes and keep the atomic structure in view.

![A colored scalar-field plane sweeps through an atomic structure](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_volumetric_plane.gif)

[Field planes and cross-sections](https://v-ase.readthedocs.io/en/latest/field-planes.html)

## Periodic cells and interfaces

### Find a common cell for rotated layers

Explore relative rotations and compatible periodic cells within your strain
and size limits. Preview candidates before creating the matched structure.
Cell tools also provide supercells, wrapping and cell transformations.

![Rotating a graphene and hBN bilayer reveals a compatible periodic cell](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate.gif)

[Commensurate rotation](https://v-ase.readthedocs.io/en/latest/commensurate.html#commensurate-same-lattice-rotation) ·
[Cells and supercells](https://v-ase.readthedocs.io/en/latest/cell-tools.html)

### Match different host and guest lattices

Load a second material, search possible common cells and compare the required
strain. Here, graphene and MoS₂ are matched as separate host and guest structures.

![Graphene and MoS2 host and guest lattices are searched for a common periodic cell](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate_host_guest.gif)

Rigid translation relaxation keeps its progress and completion state synchronized.

[Host/guest matching](https://v-ase.readthedocs.io/en/latest/commensurate.html)

### Explore interfacial registry

Scan lateral alignments or relax a whole selected fragment as one rigid body.
Registry maps compare geometric contact or bond-strain scores while preserving
the fragment's internal structure; they are not potential-energy maps.

![A selected layer translates rigidly over its host without deforming its internal structure](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_registry_relax.gif)

[Registry maps and rigid translation](https://v-ase.readthedocs.io/en/latest/registry.html)

## Atoms, bonds and coordination

### Give scientific groups their own appearance

Separate substrate, surface and adsorbate atoms with labels—even when they
share an element. Set each group's color, radius, opacity and material, and
choose which atom pairs form visible bonds.

![Substrate copper is separated into a label and styled independently of the surface oxide](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_cu5o4_view_appearance.gif)

[Atom appearance](https://v-ase.readthedocs.io/en/latest/appearance.html) ·
[Pair-specific bonds](https://v-ase.readthedocs.io/en/latest/bonds.html)

### Reveal coordination polyhedra

Show local coordination as faces, edges and ligand connectors. Give different
center groups their own colors and transparency, in both 3D and flat 2D views.

![Two groups of IrO2 coordination polyhedra receive independent colors and face opacity](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_polyhedra.gif)

[Coordination polyhedra](https://v-ase.readthedocs.io/en/latest/polyhedra.html)

## Trajectories and analysis

### Follow motion and map per-atom properties

Scrub or play a trajectory, color atoms by stored scalar data, and display force
or displacement vectors. Keep a shared colorscale across frames for comparison.
Atom radii can also follow a scalar such as charge or fractional existence.

![Trajectory playback combines a force-magnitude colorscale with force vectors](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_atom_colorscale.gif)

[Trajectories](https://v-ase.readthedocs.io/en/latest/trajectories.html) ·
[Colorscales](https://v-ase.readthedocs.io/en/latest/scalar-colors.html) ·
[Property-based radii](https://v-ase.readthedocs.io/en/latest/property-radius.html) ·
[Forces and displacement](https://v-ase.readthedocs.io/en/latest/vectors.html)

### Measure distances, angles and torsions

Pick atoms in order to inspect their geometry. Drag selections remain useful
for editing groups without creating unintended measurements.

![Ordered atom picks reveal a distance, angle and torsion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_measurement.gif)

[Selection and measurements](https://v-ase.readthedocs.io/en/latest/selection.html)

### Compare local structure with pair distributions

Plot total and label-resolved radial distributions for periodic systems, or
pair-distance distributions for finite structures. Export the curves as CSV.

![Total and label-resolved Cu-Zr radial distribution curves beside the atomic structure](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_rdf.png)

[Radial and pair distributions](https://v-ase.readthedocs.io/en/latest/rdf.html)

## Constraints and relaxation

### Control which directions atoms can move

Keep atoms fixed, restrict motion to a line or plane, or constrain selected
Cartesian or fractional directions. Visible guides make the allowed motion clear.

**Along a line:** the selected atoms move only in their permitted direction.

![FixedLine keeps selected atom motion on a visible guide line](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

**Within a plane:** move an adsorbate while holding its height above a surface.
A translucent pale cyan face fills each allowed plane, framed by narrow, darker inner and outer rims.
Selecting or hovering reveals the blocked normal with a dashed line and X ends.
Selection expands the ring around the yellow outline while preserving its face width.
The ring and atom occlude one another at their actual 3D depth.
Use the Orbit tool and drag to inspect the plane from any angle; Shift-drag pans.

![FixedPlane lets a lithium adsorbate move within a plane above copper](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

[Fixed atoms, lines, planes and fractional constraints](https://v-ase.readthedocs.io/en/latest/constraints.html)

### Add spring-like restraints

Use Hookean restraints between atoms or relative to a point or plane. The
spring guide shows the relationship as the structure changes.

![A Hookean restraint stretches as the selected atom is moved](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

[Hookean restraints](https://v-ase.readthedocs.io/en/latest/constraints.html#hookean)

### Relax and inspect the path

Remove close contacts with built-in repulsion, or optimize using a configured
ASE calculator. Play the relaxation trajectory, keep a chosen frame, or restore
the starting structure. The example shows repulsive overlap removal.

![A crowded atomic cluster separates during repulsive relaxation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_relaxation.gif)

[Relaxation and calculators](https://v-ase.readthedocs.io/en/latest/relaxation.html)

## Work with an AI agent

Ask an MCP-capable agent to prepare a structure or figure in the same document
you have open. Watch its edits, inspect the result, and continue refining it by hand.

![A user and an AI agent exchange requests and refine one shared live v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.gif)

For example, turn a selected graphene site into a pyridinic N₃ vacancy and place
a Li atom above it. The resulting atoms remain editable in the GUI.

![An agent creates a pyridinic N3 vacancy in graphene and places a lithium atom above it](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_edit.gif)

Commensurate rotation tools use global Z and keep the guest layer selected,
so its preview remains available while adjusting appearance or the camera.

[MCP setup](https://v-ase.readthedocs.io/en/latest/ai-tools.html#install-and-connect-an-mcp-client) ·
[Shared-document workflow](https://v-ase.readthedocs.io/en/latest/ai-agents.html#share-one-document) ·
[ChatGPT connection](https://v-ase.readthedocs.io/en/latest/chatgpt-local.html)

## Render and export

Stored force vectors stay synchronized after edits and trajectory frame changes.
Missing displacement comparisons do not block image rendering.

Choose flat 2D with crisp, uniformly colored bonds or shaded 3D, tune materials
and lighting, and compose a render
area independently of your editing view. Set output resolution and physical
scale for figures, or export a selected trajectory range as a movie or GIF.

![Standard, Metal and Rubber materials compared on identical copper clusters](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_materials.png)

Continue working in **Blender** with editable atoms, bonds and water-surface
meshes, including trajectory animation. **OBJ/MTL** and **Rhino 3DM** provide
additional geometry exports; ASE structure formats keep the scientific data usable elsewhere.

[Camera and image output](https://v-ase.readthedocs.io/en/latest/render-images.html) ·
[Movies and GIFs](https://v-ase.readthedocs.io/en/latest/export-video.html) ·
[Blender and geometry export](https://v-ase.readthedocs.io/en/latest/export-structures.html)

## Save and share

| You want to… | Use |
| --- | --- |
| Continue editing later | **Save** a `.vase` project. |
| Share an interactive view that opens in a browser | [Export HTML View](https://v-ase.readthedocs.io/en/latest/save-projects.html#html-view). |
| Share a browser view that can also reopen for editing | In **Project save settings**, enable **Include interactive rendered view** and save as HTML. |
| Publish a figure or animation | Export an image, movie or GIF from **Render**. |

[Saving projects](https://v-ase.readthedocs.io/en/latest/save-projects.html)

## Get v_ase

### Desktop app

Python is included. Download the installer for your computer:

| Computer | Download | Install |
| --- | --- | --- |
| Mac with Apple silicon, macOS 15+ | [Apple silicon DMG](https://github.com/lgyEthan/v_ase/releases/download/v0.4.11/v_ase-0.4.11-mac-arm64.dmg) | Open the DMG and drag **v_ase** into **Applications**. |
| Mac with Intel, macOS 15+ | [Intel DMG](https://github.com/lgyEthan/v_ase/releases/download/v0.4.11/v_ase-0.4.11-mac-x64.dmg) | Open the DMG and drag **v_ase** into **Applications**. |
| Windows 10/11, Intel or AMD 64-bit | [Windows installer](https://github.com/lgyEthan/v_ase/releases/download/v0.4.11/v_ase-0.4.11-win-x64.exe) | Run the installer, then open **v_ase** from Start. |

Open files with **File → Open**, Finder/Explorer, or drag-and-drop. Select
several files to open **separate tabs** or **one trajectory** in the same window.
Use **A/B/C** to view along the unit-cell vectors (press again to reverse);
**X/Y/Z** uses Cartesian axes. [Opening files](https://v-ase.readthedocs.io/en/latest/data-input.html) ·
[Shortcuts](https://v-ase.readthedocs.io/en/latest/shortcuts.html).
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

## Help and project information

[User guide](https://v-ase.readthedocs.io/en/latest/) ·
[Troubleshooting](https://v-ase.readthedocs.io/en/latest/troubleshooting.html) ·
[Report a problem](https://github.com/lgyEthan/v_ase/issues) ·
[What's new](https://v-ase.readthedocs.io/en/latest/whats-new.html)

[Scientific methods](https://v-ase.readthedocs.io/en/latest/scientific-validation.html) ·
[Contributing](https://v-ase.readthedocs.io/en/latest/development.html) ·
[Cite v_ase](CITATION.cff) · [AGPL-3.0-or-later](LICENSE) ·
[Third-party license](v_ase/static/vendor/THREE_LICENSE)
