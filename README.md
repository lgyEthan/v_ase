<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-2f855a.svg)](LICENSE)

**v_ase is a local, ASE-native 3D workspace for structures, trajectories, and
volumetric fields.** Open a file from the terminal or Python, inspect and edit
it in a browser, analyze atomistic data, and export projects, figures, movies,
offline HTML, or reusable 3D scenes.

[Documentation](https://github.com/lgyEthan/v_ase/blob/main/docs/index.md) ·
[PyPI](https://pypi.org/project/v-ase-gui/) ·
[Changelog](CHANGELOG.md) ·
[Issues](https://github.com/lgyEthan/v_ase/issues)

![v_ase structure-editing overview](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_overview.png)

## Quick start

Install from PyPI:

```bash
python -m pip install v_ase-gui
```

Open a file in lightweight **View** mode:

```bash
v_ase gui POSCAR
v_ase gui trajectory.extxyz
v_ase gui CHGCAR
```

Start in **Edit**, or build from an empty editable document:

```bash
v_ase gui structure.vasp --interactive
v_ase gui
```

No Node.js installation or hosted account is required. v_ase runs a
loopback-only local server and opens the interface in a normal browser. Closing
the final v_ase page releases the default blocking process.

### Five-minute tour

1. Middle-drag to orbit, Shift + middle-drag to pan, and use the wheel to zoom.
2. Left-click an atom; Shift-click or Shift-box inverts the current selection.
3. Select two, three, or four atoms in order to measure distance, angle, or
   torsion.
4. Switch to **Edit**, select atoms, press `Esc` to focus the viewport, then use
   `G`, `R`, or physical `S`. Type a value and press `Enter` for an exact edit.
5. Use **Export > Save Project** for a complete `.vase`, or include the
   interactive rendered view to create a restorable offline HTML project.

Continue with [Installation](https://github.com/lgyEthan/v_ase/blob/main/docs/installation.md)
and [First session](https://github.com/lgyEthan/v_ase/blob/main/docs/quickstart.md).

## Why v_ase?

| Area | What it provides |
| --- | --- |
| ASE-native workflow | One `Atoms`, a sequence of frames, or a supported path; caller-owned objects are copied |
| Direct structure editing | Exact move/rotate/scale, copy/paste, atom and molecule insertion, ASE bulk building, constraints, undo/redo |
| Periodic systems | Visual and physical supercells, wrapping, commensurate 2D cells, registry maps, rigid translation |
| Trajectories and analysis | Lazy/indexed playback, displacement, stored forces and arrays, RDF and finite pair distributions |
| Scalar fields | VASP density/potential/ELF, Gaussian Cube and XSF, isosurfaces, planes, and compatible field combinations |
| Figure preparation | Per-label and per-atom styling, custom colormaps, pairwise bonds, flat 2D or shaded 3D, exact Render Area |
| Portable output | Structures, `.vase`, offline HTML, PNG/JPEG/WebP/PDF, MOV/AVI, Blender, OBJ, and optional Rhino 3DM |
| Human–AI collaboration | Exact semantic state, structured operations, shared GUI revisions, and verified rendering/export |

The detailed workflows, scientific meanings, limits, and verification steps are
kept in the versioned documentation instead of duplicated in this README.

## Python and notebooks

```python
from ase.build import molecule
from v_ase import view

atoms = molecule("H2O")
view(atoms)                         # View mode
edited = view(atoms, viz_only=False)  # Edit; returns a detached Atoms
```

For a non-blocking session:

```python
editor = view(atoms, block=False)
print(editor.url)
current = editor.get_atoms()
editor.close()
```

Jupyter automatically uses an inline view. Switch subsequent calls with:

```python
%v_ase inline
%v_ase browser
%v_ase auto
```

See the [Python API](https://github.com/lgyEthan/v_ase/blob/main/docs/python-api.md)
and [notebook guide](https://github.com/lgyEthan/v_ase/blob/main/docs/notebooks-remote.md).

## Remote data

Install the same release locally and remotely, then keep the source data and
backend calculations on the SSH host while rendering in a local browser:

```bash
v_ase gui USER@SERVER:/absolute/path/to/trajectory.extxyz
```

v_ase creates and cleans the private tunnel automatically. Exact remote Python
selection, jump hosts, lazy trajectories, and failure recovery are covered in
[Notebooks and remote systems](https://github.com/lgyEthan/v_ase/blob/main/docs/notebooks-remote.md).

## Work with an external AI agent

![Human and external AI agent working in one live v_ase document](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_collaboration.png)

You describe the scientific result to an external AI Agent; the Agent uses the
Skill and structured CLI/API; the result appears in the same live GUI. A manual
GUI edit becomes the next document revision before another agent mutation.

v_ase does not contain an LLM or interpret natural language. It exposes exact
semantic state and a revisioned loopback bridge:

```bash
v_ase gui STRUCTURE --interactive --cli
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" capabilities
v_ase api "$COMMAND_URL" describe --params '{"includePositions":true}'
```

The first CLI stdout line is a JSON handshake; later lines are collaboration
events, not a stdin command loop. Semantic state can reduce token use and
repeated image interpretation, while decoded renders remain the visual source
of truth.

Read [AI-agent integration](https://github.com/lgyEthan/v_ase/blob/main/docs/ai-agents.md)
and the bundled canonical
[`SKILL.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md)
before automation.

## Save, export, and share

| Goal | Choose |
| --- | --- |
| Resume all scientific and visual work | Compact `.vase` project |
| Resume work and preview in a browser | Save Project with interactive rendered view |
| Share only an offline interactive scene | **Export HTML View** without project embedding |
| Publish a figure | PNG, lossless WebP, JPEG, or rendered PDF |
| Publish a trajectory | H.264 MOV or MPEG-4 AVI |
| Continue in a 3D tool | Blender script, OBJ/MTL ZIP, or optional Rhino 3DM |

Standalone HTML opens from `file://` without v_ase, Python, a server, or a CDN.
The lightweight HTML View is intentionally not editable; embed the project or
keep the `.vase` when full recovery matters.

Rhino export requires one optional extra:

```bash
python -m pip install "v_ase-gui[rhino]"
```

See [Projects, rendering, and export](https://github.com/lgyEthan/v_ase/blob/main/docs/projects-export.md)
and [Supported formats](https://github.com/lgyEthan/v_ase/blob/main/docs/formats.md).

## Documentation map

| Need | Guide |
| --- | --- |
| Install and open the first structure | [Installation](https://github.com/lgyEthan/v_ase/blob/main/docs/installation.md) · [First session](https://github.com/lgyEthan/v_ase/blob/main/docs/quickstart.md) |
| Understand tabs, View/Edit, and state | [Workspace model](https://github.com/lgyEthan/v_ase/blob/main/docs/workspace.md) |
| Select, transform, build, and add atoms/molecules | [Editing structures](https://github.com/lgyEthan/v_ase/blob/main/docs/editing.md) |
| Follow reproducible fixtures | [Worked examples](https://github.com/lgyEthan/v_ase/blob/main/docs/worked-examples.md) |
| Use constraints and relaxation | [Constraints and relaxation](https://github.com/lgyEthan/v_ase/blob/main/docs/constraints-relaxation.md) |
| Analyze trajectories, properties, and RDF | [Trajectories and analysis](https://github.com/lgyEthan/v_ase/blob/main/docs/trajectories-analysis.md) |
| Inspect density, potential, ELF, Cube, or XSF | [Volumetric fields](https://github.com/lgyEthan/v_ase/blob/main/docs/volumetric-guide.md) |
| Match interfaces and registry | [Periodic cells and interfaces](https://github.com/lgyEthan/v_ase/blob/main/docs/periodic-interfaces.md) |
| Look up commands and shortcuts | [CLI](https://github.com/lgyEthan/v_ase/blob/main/docs/cli-reference.md) · [Shortcuts](https://github.com/lgyEthan/v_ase/blob/main/docs/shortcuts.md) |
| Diagnose an error | [Troubleshooting](https://github.com/lgyEthan/v_ase/blob/main/docs/troubleshooting.md) |

The documentation uses Sphinx, MyST Markdown, and the Read the Docs theme. Build
the exact strict site locally:

```bash
python -m pip install -r docs/requirements.txt
make -C docs html
```

Output is written to `docs/_build/html`.

## Development

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e ".[dev]"
python -m playwright install chromium
pytest
```

Documentation and release requirements are in
[Contributing documentation](https://github.com/lgyEthan/v_ase/blob/main/docs/contributing-docs.md)
and the [Release Checklist](https://github.com/lgyEthan/v_ase/blob/main/docs/release_checklist.md).

## Citation

If v_ase supports published work, cite the exact software version. Citation
metadata is provided in [`CITATION.cff`](CITATION.cff).

## License

v_ase is licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE)
(`AGPL-3.0-or-later`). The bundled Three.js module retains its MIT license.
