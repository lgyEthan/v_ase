<p align="center">
  <img src="https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/v_ase-logo.png" width="720" alt="v_ase logo">
</p>

# v_ase

[![PyPI version](https://img.shields.io/pypi/v/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![Python versions](https://img.shields.io/pypi/pyversions/v_ase-gui.svg)](https://pypi.org/project/v-ase-gui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`v_ase` brings ASE's convenient terminal and Python workflow together with
direct, Blender-style 3D structure editing. Open a structure or trajectory
with one command, inspect and measure it in a local browser, edit it manually
or let an external AI agent translate a natural-language request into verified
structure operations, then export publication images, videos, and reusable 3D
scenes.

![Phosphorene nanoribbon manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

The animation builds a phosphorene nanoribbon twist one ridge at a time. Each
amber box selects the remaining ridges, the Transform controls apply an exact
X-axis rotation, and the sequence reaches a 13.85 degree twist before the
completed structure is inspected from above and below.

| Work directly in v_ase | Included |
| --- | --- |
| Structures and trajectories | ASE-supported formats, live timeline, per-frame bonds |
| Geometry editing | Ordered selection, `G` move, `R` rotate, axis locks, numeric input |
| Scientific inspection | Distances, angles, torsions, displacement vectors, constraints |
| Figure preparation | Appearance, bonds, lighting, exact preview, image/video export |
| Reproducible sessions | Self-contained `.vase` projects and reusable visual settings |
| Agent workflows | Semantic state/command API and a vendor-neutral AI skill |

## Quick Start

Install from PyPI:

```bash
python -m pip install v_ase-gui
```

Or install the current GitHub source:

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e .
```

Start an empty workspace or open a file:

```bash
v_ase gui
v_ase gui FILE
```

Examples:

```bash
v_ase gui POSCAR
v_ase gui trajectory.extxyz
v_ase gui relaxation.traj
v_ase gui project.vase
```

The default **View** mode is optimized for visualization, trajectories,
measurement, appearance, bonds, supercells, and export. Use the top-bar mode
switch or start directly in **Edit** when atomic coordinates must change:

```bash
v_ase gui structure.vasp --interactive
```

No Node.js installation or hosted account is required. Closing the v_ase
browser document releases the blocking terminal process.

## Everyday Workflow

| Goal | Action |
| --- | --- |
| Inspect a structure | Middle-drag to orbit, wheel to zoom, left-click to select |
| Edit coordinates | Enter **Edit**, select atoms, press `Esc` to focus the viewport, then use `G` or `R` |
| Measure geometry | Select 2, 3, or 4 atoms in the required order |
| Play a trajectory | Use the bottom timeline or `Space`; FPS and Skip update live |
| Style a figure | Use **Structure > Appearance/Bonding** and **View** |
| Repeat or wrap a cell | Use **Structure > Cell & Replication** |
| Save the whole session | Use **Export > v_ase Project** and choose compact `.vase` or browser-ready HTML |
| Reuse only the visual style | Use **Export > Save Settings** |
| Share an offline 3D view | Use **Export HTML View**, then choose whether to embed the editable `.vase` |
| Hand the scene to an AI | Provide the bundled agent skill; the agent starts the CLI/API session itself |

> **Viewport tip:** after selecting atoms, press `Esc` to close the control
> panel before using `G` or `R`. The selection is preserved and keyboard focus
> returns to the 3D viewport.

## Use v_ase Through An External AI Agent

v_ase does not contain an LLM and does not accept natural language itself.
Give an external AI agent the bundled [v_ase agent skill](#ai-and-agent-use),
then describe the scientific result to that agent rather than a sequence of
mouse actions:

> From this pristine 6 x 6 graphene sheet, remove the carbon nearest the cell
> center, convert its three nearest neighbors to pyridinic nitrogen, add a
> `Li_site` atom 2.15 A above the vacancy, preserve PBC and bonds, use a clean
> oblique studio-shadow view, and render a 4K image.

![Natural-language pyridinic N3 graphene edit](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ai_edit.gif)

The external agent starts `v_ase gui STRUCTURE --cli`, parses the JSON
handshake printed by v_ase, and controls the live document with structured
`window.v_aseAI` commands. It reads atom identities, coordinates, cell, PBC,
selection, constraints, and camera directly from semantic state. In this
example it finds the central site, remaps neighbor indices after deletion,
changes three ASE elements and labels, creates Li at a measured height,
verifies the 72-atom result, and renders the same document a human can continue
editing. No screenshot OCR or coordinate guessing is required. Final
validation confirms three `N_pyridinic` labels and one `Li_site` label against
the corresponding ASE elements.

This example is generated entirely from `ase.build.graphene`, so it contains
no copied structure or private data:

- [source graphene CIF](examples/readme_scene_assets/ai_graphene_source.cif)
- [intermediate pyridinic N3 CIF](examples/readme_scene_assets/ai_pyridinic_n3_graphene.cif)
- [final N3/Li-site CIF](examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.cif)
- [ASE trajectory preserving labels](examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.traj)

## Structure Manipulation

Use **Edit** when atom coordinates must change. Selection, measurement,
appearance, bonds, replication, wrapping, visual translation, and export
remain available in the default **View** mode.

### Select

- Left-click selects one atom; `Shift` + click extends or removes selection.
- Left-drag draws a visible selection box.
- Appearance rows select complete label groups without merging distinct labels.
- Ordered single-atom selections are retained for geometry measurement.

### Move

Press `G` after selecting atoms. Lock the move with `X`, `Y`, or `Z`, type an
exact displacement in angstrom, then confirm with left-click or `Enter`.
Configured ASE constraints remain authoritative when **Apply constraints** is
enabled.

### Rotate

Press `R` after selecting atoms. Choose **Selection COM**, **Active atom (last
selected)**, **Origin**, or **Unit-cell center** as the pivot, lock an axis if
needed, and enter an exact angle. To rotate around a particular atom, select
the moving atoms first and Shift-select the pivot atom last. For a panel-driven
edit, use **Structure > Transform > Exact selection rotation** to choose the
axis and angle, then click **Rotate Selection**. Both methods honor the current
constraint and undo settings. Every active rotation shows:

- the rotation axis through the chosen pivot;
- a neutral line fixed at the direction where the operation started;
- an amber line that follows the current structure;
- cyan candidate lines only when the commensurate guide is enabled.

#### Ferrocene: Use Fe As The Active Pivot

![Ferrocene pivot rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_ferrocene_pivot.gif)

Select the upper cyclopentadienyl ring first, then Shift-select Fe last. With
**Active atom (last selected)** enabled, Fe remains fixed at the exact rotation
pivot:

1. `R`, `Z` rotates the ring around the axis through Fe.
2. `R`, `X` folds the same ring around an X axis through Fe.

The active atom can be any selected atom; it does not need to coincide with the
global origin or the selection center.

#### Phosphorene: Build The Twist One Edit At A Time

![Cumulative phosphorene manipulation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_phosphorene_twist.gif)

The animation records a sequence of normal v_ase edits:

1. Keep the first puckered ridge fixed. Left-drag the visible amber box from
   the **second ridge through the end** of the ribbon, then release to commit
   the yellow outlined selection.
2. Open **Structure > Transform**, keep **Selection COM**, choose axis `X`,
   enter `1.538889` degrees, and click **Rotate Selection**.
3. Close the panel, left-drag a new box from the **third ridge through the
   end**, enter the same exact angle, and rotate again from the edited
   coordinates.
4. Continue advancing the box-selection boundary by one 12-atom ridge. After
   9 rotations, the final ridge is rotated by exactly 13.85 degrees.
5. Orbit the completed structure from above to below to inspect the full
   three-dimensional twist.

The amber box shows the current selection area, the yellow outline identifies
the atoms affected by the next edit, and bonds update after each rotation.

Black phosphorene has two puckered sublayers in one armchair unit cell. The
`5 x 6` model contains 10 puckered ridges with 12 atoms per ridge. Green and
purple distinguish the upper and lower P sublayers; both remain phosphorus in
the ASE structure.

The relaxed source coordinates come from the
[supporting information of Villegas et al.](https://www.rsc.org/suppdata/c6/cp/c6cp05566d/c6cp05566d1.pdf).
The 13.85 degree target is one of the H-APNR angles tabulated by
[Jang et al.](https://www.rsc.org/suppdata/c6/nr/c6nr04354b/c6nr04354b1.pdf),
and the green/purple sublayer convention follows published phosphorene
structure diagrams such as
[Zhang et al.](https://doi.org/10.1038/srep13927). The example demonstrates
geometry editing and is not an energy-minimized final structure.

#### Graphene/hBN: Find A Commensurate Rotation

![Graphene hBN commensurate rotation](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_commensurate.gif)

Select the hBN layer, enable **Commensurate guide**, then use `R`, `Z`. The
top view intentionally hides the world X/Y/Z axes so the neutral start line,
amber current line, and labeled cyan cell-match candidates remain distinct.
**Magnetic angle snap** can pull the active rotation to a candidate within the
configured tolerance.

Normal `R` rotates selected atoms. **Cell Transform** is a separate periodic
operation that applies an integer matrix to the cell and every trajectory
frame. Its equations and assumptions are documented in
[unit_cell_aware_rotate.md](docs/unit_cell_aware_rotate.md).

## Measurement And Analysis

![Ordered distance angle and torsion measurement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_measurement.gif)

The numbered `a1` to `a4` markers record selection order and are deliberately
different from atom indices.

| Ordered selection | Reported result |
| --- | --- |
| 1 atom | Label, element, position, force, charge, tag, magnetic moment |
| 2 atoms | Direct distance and minimum-image distance |
| 3 atoms | Angle `a1-a2-a3`, centered on `a2` |
| 4 atoms | Signed torsion `a1-a2-a3-a4` |
| 5 or more | Total count and per-label counts |

The connector, angle arc, torsion axis, and compact value badge stay attached
to the selected atoms. Hover information is independent, so moving the pointer
does not replace a saved measurement.

![Trajectory displacement analysis](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_displacement.png)

For trajectories, **Analysis > Displacement** compares the current frame with
the previous frame or a chosen reference. Minimum-image correction, vector
scale, thickness, color, and 2D/3D style are configurable. Displayed
supercells repeat the vectors, and visual translation moves both endpoints
without changing the physical displacement.

## Constraints

ASE remains authoritative when **Apply constraints** is enabled. Constraint
visualization is local to each atom rather than merged at a group center.

### FixedLine

A short cyan line passes through each constrained atom and remains visible
without selection. Starting `G` displays a longer guide through the atom's
original position while ASE restricts movement to that direction. FixedLine
does not use a ring or plane disc.

![FixedLine movement](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedline.gif)

```bash
v_ase gui examples/readme_scene_assets/fixedline.traj --interactive
```

### FixedPlane And FixScaled

Each constrained atom keeps its own local ring, crosshair, and normal marker.
When `G` starts, a larger translucent guide plane appears at that atom's
original position so the permitted surface remains visible while the atom
moves. Multiple selected atoms retain independent planes; no center-of-mass
plane is substituted.

VASP selective dynamics read as `FixScaled` are displayed from their allowed
fractional directions.

![FixedPlane movement and guide plane](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_fixedplane.gif)

```bash
v_ase gui examples/readme_scene_assets/fixedplane.traj --interactive
```

### FixAtoms

Fixed atoms keep their element color but use a distinct constrained surface
treatment. They remain identifiable without looking selected.

### Hookean

Hookean constraints show their inactive cutoff and engaged state separately.
After the constrained distance passes `rt`, a shaded 3D helical spring appears
between the constrained atoms.

![Hookean constraint](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.png)

![Hookean motion](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_hookean.gif)

```bash
v_ase gui examples/readme_scene_assets/hookean.traj --interactive
```

## Relaxation

![Repulsive relaxation trajectory](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_relaxation.gif)

**Structure > Relaxation** places every optimization step on a dedicated
timeline. A single loaded structure gains a relaxation movie after the first
run. If a source trajectory is already open, source and relaxation timelines
remain separate and the active timeline is clearly selected.

The included example starts from a deliberately compressed C60 geometry and
runs ASE FIRE with v_ase's repulsive fallback calculator:

- [crowded initial C60](examples/readme_scene_assets/crowded_c60_initial.cif)
- [relaxed C60](examples/readme_scene_assets/crowded_c60_relaxed.cif)
- [optimization trajectory](examples/readme_scene_assets/crowded_c60_relaxation.traj)

```bash
v_ase gui examples/readme_scene_assets/crowded_c60_initial.cif --interactive
```

The fallback calculator is intended for removing obvious close contacts, not
for predictive chemistry. Its cutoff scale and strength are editable. Attach a
scientific ASE calculator when the optimized energy or forces will be used as
physical results.

## Trajectories

Multi-frame inputs add a timeline below the viewport. Scrubbing updates the
frame continuously, selected atom indices persist when topology permits, FPS
changes apply during playback, and **Skip** advances by `skip + 1` source
frames per tick.

Bond topology is evaluated for each frame, so bonds form or break when a
pair crosses its cutoff. Appearance, pair settings, supercell display, camera,
and analysis settings remain active across the movie.

Video export uses FPS as playback speed. Optional `N x` interpolation creates
`(source_frames - 1) * N + 1` output frames. Minimum-image interpolation uses
periodic cells to avoid jumps across a boundary. Interpolation takes longer
because more frames are rendered.

## Appearance, Bonds, And Rendering

**Structure > Appearance** controls each stable atom label:

- ASE chemical TYPE and independent visual label;
- visibility and selection availability;
- color and radius;
- Standard, Metal, or Rubber material;
- all/partial/none selection checkbox.

View mode applies appearance by label. Edit mode can keep per-atom material
overrides. Relabeling does not reorder the table or merge otherwise distinct
atom types accidentally.

![Standard Metal and Rubber atom materials](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_materials.png)

The comparison uses three identical Cu13 clusters with the same element color
and radius, so only the optical material changes:

| Material | Visual response | Typical use |
| --- | --- | --- |
| Standard | Balanced diffuse color and compact highlight | General structures and chemically neutral figures |
| Metal | Strong environment reflection and bright metallic highlight | Metals, electrodes, and reflective surfaces |
| Rubber | High roughness with broad, muted highlights | Soft visual grouping and low-glare nonmetal regions |

Materials affect rendering only. ASE elements, coordinates, calculators, and
constraints are unchanged.

![Pairwise Cu O bonds in a Cu2O(111) film on Cu(111)](https://raw.githubusercontent.com/lgyEthan/v_ase/main/docs/assets/github/readme_bonds.png)

**Structure > Bonding** provides automatic inference, explicit label-pair
cutoffs, and manual index pairs. A pair cutoff of zero disables that pair.
Changes apply immediately. Bonds support:

- cell-local or periodic minimum-image display;
- cylinder or flat 2D geometry;
- custom color or two half-bonds using the atom colors;
- configurable diameter;
- live formation and breaking during Edit transforms.

The top view shows a `6 x 6 Cu2O(111)` film on `7 x 7 Cu(111)`, with one
interfacial oxygen positioned over a substrate Cu top site.
The Cu(111) substrate uses a nearest-neighbor touching-sphere radius.
`Cu_oxide-O_oxide` and `Cu_substrate-O_oxide` bonds are enabled, while
`Cu_substrate-Cu_substrate`, `Cu_oxide-Cu_oxide`, cross-region Cu-Cu, and
O-O pairs are disabled. Dark metallic substrate Cu, bright standard-material
oxide Cu, and matte red oxide O separate the phases without changing ASE
elements. Each bond is split into the colors of its two endpoint atoms, so the
Cu-O connectivity remains readable without an unrelated custom bond color.
Separate oxide and substrate labels let each interaction be enabled or
assigned its own cutoff independently.

```bash
v_ase gui examples/readme_scene_assets/cu2o111_on_cu111_pairwise_bonds.traj
```

**View** controls projection, atomic scale, anti-aliasing, sphere smoothness,
background, 2D/3D display, grid, axes, unit cell, overlays, and cell material.
The **Axes** and **Unit Cell** switches update the working viewport
immediately; they are not export-only settings. Hiding world axes does not
remove the compact orientation gizmo. New documents use orthographic
projection and a true-white background.

The top-bar renderer switches between fast modeling light and Sun/soft-shadow
rendering. Sun source, target, intensity, and direction can be manipulated in
the viewport and carried into Blender export.

## Export And Save

| Command | Result |
| --- | --- |
| Export POSCAR | Current physical ASE structure in VASP format |
| Export ASE Pickle | ASE `Atoms`, labels, constraints, arrays, and a valid `SinglePointCalculator` |
| Export Image | PNG by default; JPEG, PDF, and lossless WebP from the exact preview frame |
| Export Video | Constant-frame-rate H.264 MOV or MPEG-4 AVI with optional interpolation |
| Export Blender | Optimized scene script with atoms, bonds, cell, camera, and Sun |
| Export 3DM | Instanced Rhino geometry, metadata, and saved camera views |
| Export OBJ | OBJ/MTL, camera, and metadata in a ZIP |
| Export HTML View | Offline, view-only 3D document; optionally embed `.vase` recovery |
| Save `.vase` | Compact project with structure/trajectory and complete visual state |
| Save HTML | Browser-ready project with optional embedded `.vase` recovery |
| Save Settings | Reusable visual settings without coordinates |

The **Preview Area** is the authoritative image/video frame. Its aspect ratio,
camera, crop, lighting, atom scale, and included overlays match the export.
Cell, grid, axes, and background can be included or excluded independently.

The system save picker is opened before expensive rendering or scene
generation when the browser supports it. Canceling the picker cancels the
export. Chrome may then show **This site can view changes you make to this
file**. That message is Chrome's File System Access permission notice: v_ase
can write only to the destination selected in that picker. Browser code cannot
hide the notice while retaining destination selection before rendering.

Image export uses one determinate progress bar for rendering, pixel capture,
upload, encoding, download, and the final file write. It reports estimated
remaining time and reaches 100% once, only after the destination is complete.
Video export follows the same monotonic rule across all frames and encoding.
Every source frame is retained exactly once at `1x`; interpolation adds
in-between frames. Visible displacement vectors and other selected scene
overlays are recalculated for each rendered frame.

### Project Or Shareable HTML

Under **Export > v_ase Project**, use **Save .vase** for the smallest complete
project. It contains every loaded frame, coordinates, cells, PBC, labels,
constraints, safe calculator results, camera, appearance, bonds, lighting,
analysis, and export settings. It is self-contained and never references the
original input file.

Use **Save HTML** or **Export HTML View** when the result should open directly
in a browser. Before saving, choose whether to enable **Embed editable .vase
project**. The save dialog previews the rendered structure that will initialize
the standalone viewer. Every generated HTML:

- opens offline without v_ase, Python, a server, or a CDN;
- restores the saved camera, viewport styling, bonds, constraint overlays,
  displacement vectors, supercell, visual translation, and trajectory;
- allows orbit, pan, zoom, frame stepping, and movie playback;
- exposes no atom, structure, appearance, or project editing controls.

With project embedding enabled, the HTML also includes the complete `.vase`.
The viewer exposes **Download .vase**, and either command restores the full
editable project:

```bash
v_ase gui project.vase
v_ase gui project.html
```

With project embedding disabled, the file is smaller and remains a portable
view-only document. It cannot be restored as an editable v_ase project. v_ase
reports this explicitly if that lightweight HTML is opened as input.

HTML is larger than `.vase` because it contains the browser renderer and
immediately readable scene data. Embedding adds a Base64 copy of `.vase` on
top of that. Keep `.vase` as the compact editable source of truth.

Opening an ordinary structure in an existing tab keeps the current visual
settings; opening `.vase` or project-embedded HTML restores the saved project.

Rhino export requires the optional dependency:

```bash
python -m pip install "v_ase-gui[rhino]"
```

OBJ export has no optional Python dependency.

## AI And Agent Use

The natural-language interface belongs to an external AI agent, not to v_ase.
The complete path is:

```text
natural-language request
  -> external AI agent + v_ase Skill
  -> v_ase CLI startup and JSON handshake
  -> structured window.v_aseAI commands
  -> ASE-backed state, render, and export results
  -> agent verification or human takeover
```

Install v_ase normally and give the external agent the bundled skill. The
agent starts the machine-readable session itself when the task requires it:

```bash
v_ase gui STRUCTURE --cli
```

### What `--cli` Actually Does

`--cli` is a launcher and discovery mode. It suppresses automatic browser
launch, starts the same local FastAPI/browser application used by the GUI,
prints one compact JSON handshake to stdout, and keeps the process alive.
It does not read natural-language or structured commands from stdin, call
an AI service, or provide an embedded model.

The first stdout line has this form:

```json
{
  "protocol": "v_ase.ai.v1",
  "status": "ready",
  "human_url": "http://127.0.0.1:xxxxx/workspace?...",
  "state_url": "http://127.0.0.1:xxxxx/api/ai/state/xxxx",
  "schema_url": "http://127.0.0.1:xxxxx/api/ai/schema",
  "skill_url": "http://127.0.0.1:xxxxx/api/ai/skill",
  "browser_api": "window.v_aseAI",
  "command_transport": "browser-javascript",
  "accepts_natural_language": false,
  "stdin_commands": false
}
```

Status text is written to stderr. The process remains alive until the agent or
user stops it. `human_url` opens the same live document for manual takeover.

### Structured Input And Output

After opening `human_url`, the external agent uses the browser API. These are
structured `window.v_aseAI` commands, not natural-language prompts.

```javascript
const ai = window.v_aseAI;
await ai.ready();
const capabilities = await ai.capabilities();
const state = await ai.describe({includePositions: true});

const updated = await ai.apply({
  mode: "edit",
  selection: {clear: true, indices: [0, 4, 9]},
  operation: {
    name: "rotate-selection",
    axis: [0, 0, 1],
    angleDeg: 30,
    pivot: "active"
  }
});
```

| Interface | Input | Output |
| --- | --- | --- |
| CLI startup | File path and CLI options | One JSON handshake on stdout; lifecycle status on stderr |
| `state_url` | HTTP GET | Read-only JSON structure/session state |
| `capabilities()` | No payload | Supported state fields, operations, and exports |
| `describe()` | Optional detail flags | Labels, ASE elements, positions, cell, PBC, constraints, trajectory, selection, measurements, display, camera, and export profile |
| `apply(command)` | Structured object for frame, mode, display, camera, selection, or operation | Updated semantic state after the change |
| `render(request)` | Dimensions, format, and exact render options | Image data URL plus dimensions, MIME type, filename, and byte count |
| `export(request)` | Export format and options | Export data URL plus filename, MIME type, and byte count |

The Skill teaches the external agent which fields and operations are valid,
how to preserve ASE semantics, when confirmation is required, and how to
verify each result. It is documentation and an operating contract, not an AI
runtime. Reading compact semantic state instead of repeatedly analyzing full
screenshots can reduce token use; final rendered images are still inspected
when visual quality matters.

Use the complete
[v_ase agent skill](https://github.com/lgyEthan/v_ase/tree/main/v_ase/skills/visualizing-atomic-structures-with-v-ase).
It is vendor-neutral and can be used by Codex, Claude Code, ChatGPT desktop
agents, Gemini-based agents, agentic IDEs, or another model that can run local
commands or control a browser. The
[agent setup reference](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/agent-setup.md)
explains each integration path.

### What To Give The AI

Prefer the complete skill directory. If the client accepts only individual
files, provide the following:

| Always provide | Add when the task needs it |
| --- | --- |
| [`SKILL.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md) | [`semantic-api.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/semantic-api.md) for live state, edits, camera, render, or export |
| [`agent-setup.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/agent-setup.md) | [`workflows-and-examples.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/workflows-and-examples.md) for multi-step scientific workflows |
|  | [`cli-and-environments.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/cli-and-environments.md) for installation, server, WSL, or process handling |
|  | [`safety-and-errors.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/safety-and-errors.md) before destructive edits, relaxation, or file output |
|  | [`evaluation.md`](v_ase/skills/visualizing-atomic-structures-with-v-ase/references/evaluation.md) when changing or releasing v_ase itself |

The external agent launches the document and parses the first JSON line itself:

```bash
v_ase gui STRUCTURE --cli
```

That line discovers the live GUI, read-only state, current command schema,
browser control object, and installed Skill. It is not a prompt endpoint.
Do not paste screenshots or manually transcribe coordinates when semantic
state is available.

This bootstrap instruction works for clients without a native skill loader:

```text
Read SKILL.md and agent-setup.md first. Load only the reference files needed
for this task. Start v_ase with --cli, inspect capabilities() and describe()
before editing, execute semantic operations one at a time, verify state after
each physical change, inspect the decoded final render, and give me human_url
for manual takeover.
```

The compatibility document
[`skills_v_ase.md`](v_ase/skills_v_ase.md) points existing integrations to the
same canonical skill and reference set.

### Installing The Skill

Clients with skill-folder support should install the complete directory:

```bash
# Codex
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase "$CODEX_HOME/skills/"

# Claude Code, from a project root
mkdir -p .claude/skills
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase .claude/skills/
```

For another AI, use its documented local skill directory if it supports the
same `SKILL.md` convention. Otherwise attach the files listed above or make
them readable in the project and include the bootstrap instruction. The live
semantic protocol is the same regardless of model vendor.

## Documents And File Opening

The top-bar **Open** button starts with the operating system file picker. A
selected file can:

1. replace the active document;
2. append structures to its current trajectory;
3. open in a new independent v_ase tab.

If the active document is empty, the selected file opens there immediately;
the destination chooser is shown only when a document already contains a
structure or trajectory.

The **+** beside the document tabs creates an empty independent document. Each
tab owns its structure, trajectory, camera, selection, history, settings,
calculator, and `.vase` output.

Adding `.vase` to an existing trajectory imports only its structures and keeps
the current tab's visual state. Replacing a tab or opening a new one restores
the complete `.vase` project.

## Python

```python
from ase.build import molecule
from v_ase.visualize import view

atoms = molecule("H2O")
view(atoms)  # View mode
```

Return an edited ASE object:

```python
edited = view(atoms, viz_only=False)
print(edited.positions)
```

`view()` accepts one ASE `Atoms`, a sequence of frames, or a supported file
path. `view_edit()` remains a compatibility alias for Edit mode.

## File Formats

Common inputs include POSCAR/CONTCAR, VASP files, XDATCAR, `vasprun.xml`,
XYZ/extxyz, ASE `.traj`, LAMMPS dump/data, CIF, and `.vase`. ASE readers cover
additional formats.

Use `--format` when an ambiguous filename does not identify the reader:

```bash
v_ase gui ABCD --format POSCAR
v_ase gui ABCD --format vasprun.xml
v_ase gui ABCD --format lammpstrj
v_ase gui ABCD --format data
```

Use `--index :` for every frame, `--index -1` for the last frame, or an integer
for one frame.

Repeated POSCAR/CONTCAR species blocks remain separate visual labels. For
example, `O Cu O` with counts `1 14 5` becomes `O1`, `Cu`, and `O2` while all
oxygen atoms remain ASE element `O`.

## Controls

| Input | Action |
| --- | --- |
| Left click / Shift + click | Select / extend selection |
| Left drag | Box select |
| Middle drag | Orbit without inertia |
| Shift + middle drag | Pan |
| Wheel | Zoom |
| `G` / `R` | Move / rotate selected atoms |
| `X`, `Y`, `Z` during `G`/`R` | Lock transform axis |
| `X`, `Y`, `Z` otherwise | Align camera to an axis |
| Number keys | Exact move distance or rotation angle |
| `Enter` or left click | Confirm transform |
| `Esc` or right click | Cancel transform |
| `Ctrl+C`, `Ctrl+V` | Copy and paste atoms |
| `Ctrl+Z`, `Ctrl+Shift+Z` | Undo and redo structure and visualization-setting changes; camera navigation is excluded |
| `Delete` / `Backspace` | Delete selected atoms |
| `Space` | Play or pause the active timeline |
| Left / Right Arrow | Previous / next frame in the active timeline |
| `Tab` or `Esc` | Open a collapsed control panel |
| `Esc` with the panel open | Close it and return focus to the viewport |

The **?** button contains the complete shortcut table.

## Remote Servers

Install v_ase on both the local computer and remote host, then run one command
locally:

```bash
v_ase gui USER@SERVER:/absolute/path/to/STRUCTURE
```

An SSH config alias works:

```bash
v_ase gui physics:/absolute/path/to/trajectory.extxyz
```

v_ase selects private ports automatically, starts the backend beside the
remote file, creates the SSH tunnel, and opens the local browser. The source
file and full trajectory cache remain on the server; only the current frame
data required for local Three.js rendering crosses the tunnel. Use `ProxyJump`
in `~/.ssh/config` when a login node is required.

## Troubleshooting

<details>
<summary><code>v_ase</code> command is not found</summary>

Install and run with the same Python environment:

```bash
python -m pip install --upgrade v_ase-gui
python -m v_ase.cli --version
```

If the module command works but the console command does not, reactivate the
environment or add its Python scripts directory to `PATH`.

</details>

<details>
<summary>The browser does not open, or WSL prints <code>gio: ... Operation not supported</code></summary>

The terminal also prints the complete local URL. Ctrl+click it or copy the text
beginning with `http://` into Chrome, Edge, Firefox, or another browser. Keep
the terminal process running.

Example with sensitive session identifiers masked:

```text
(base) giyeok@DESKTOP-XXXX:~$ v_ase gui
gio: http://127.0.0.1:58039/workspace?workspace_id=xxxx&session_id=xxxx: Operation not supported
```

For better WSL performance, keep trajectories under the Linux filesystem
rather than `/mnt/c/...`.

</details>

<details>
<summary>A file is detected with the wrong format</summary>

Force the reader:

```bash
v_ase gui FILE --format POSCAR
v_ase gui FILE --format vasprun.xml
v_ase gui FILE --format lammpstrj
v_ase gui FILE --format data
```

</details>

<details>
<summary>Replicated supercell atoms cannot be selected</summary>

In **Edit**, displayed replicas are noneditable previews. Use
**Set Supercell as Cell** to create real ASE atoms and an editable larger cell.
In **View**, displayed replicas are selectable and participate in center,
distance, and other measurements.

</details>

<details>
<summary>Video export is unavailable or slow</summary>

Video export requires at least two frames and browser `MediaRecorder` support.
MOV/AVI conversion uses the bundled `imageio-ffmpeg`. Interpolation renders
additional frames and requires stable atom count, element, label, and ordering
between adjacent source frames. The selected FPS controls playback time:
72 frames at 30 FPS produce 2.40 seconds. The progress indicator reaches 100%
only after encoding and the destination write both finish.

</details>

<details>
<summary>Chrome says this site can view changes made to the saved file</summary>

This is a Chrome security notice for the File System Access API. v_ase opens
the system save picker before a costly image, video, Blender, or 3D scene export so
canceling does not waste time. It receives write access only to the file you
choose. Chrome does not allow a page to suppress this notice; using an ordinary
browser download would remove advance destination selection.

</details>

<details>
<summary>A large trajectory opens or plays slowly</summary>

- Keep the default View mode unless editing is required.
- Use `--stream-frames` when frame data should be loaded on demand.
- Keep browser hardware acceleration enabled.
- Close unused v_ase tabs; inactive tabs pause rendering but retain document
  state in memory.
- In WSL, keep data in the Linux filesystem.

</details>

<details>
<summary>Installation fails while pip checks an unrelated package version</summary>

A package version reported as `None` usually belongs to a different incomplete
or manually installed distribution in that environment. Run
`python -m pip check`, repair that distribution, or use a clean environment:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install v_ase-gui
```

</details>

Run `v_ase --help` or `v_ase gui --help` for all CLI options. Report
reproducible problems at
[GitHub Issues](https://github.com/lgyEthan/v_ase/issues).
