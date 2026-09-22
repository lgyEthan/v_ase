# v_ase 0.4.1 implementation and validation record

Date: 22 September 2026. This is a delivery record, not a future implementation
plan. The superseded remaining-implementation instructions have been removed.
The editable `v_ase_ui_toy_model.html` and its two reference images are retained
as design history; production behavior is implemented in `v_ase/static/`.

## Delivered workspace

The atomic viewport occupies the main workspace. A single right workbench
contains four persistent primary tabs and visible, labelled tool buttons:

| Area | Directly available tools |
| --- | --- |
| Style | Atoms, Bonds, Cell, Polyhedra, View & guides |
| Build | Add atoms, Transform, Cell matrix, Constraints, Match cells, Relax, Rigid translation |
| Analyze | Measure, Distributions, Displacements, Forces, Fields, Registry |
| Render | Renderer, Image, Video, Interactive HTML, Geometry |

Objects uses a contextual viewport drawer. Analysis results occupy a dock below
the viewport. File, Edit, View, Preferences and Help retain project, history,
presets and guidance workflows. All seven viewport tools are visible: Select,
Move, Orbit, Rotate, Scale, Measure and Add atoms. Camera presets, grid and
lighting remain beside the viewport. Tools requiring Edit explain that state
and provide an explicit switch. View-only cell matching previews remain usable.

At narrow widths the workbench stacks below the viewport. Numeric fields use
bounded layouts; suffixes share the input's container. Atom-type appearance uses
labelled vertical forms instead of a horizontally scrolling table. The color
legend, orientation widget, camera controls and viewport toolbar occupy separate
regions. Collapsing the workbench also disables hit targets in its hidden body.

Primary ownership: `static/editor_ui.js`, `static/editor.css`, `static/index.html`
and `static/main.js`. Scientific state and existing backend operations remain
authoritative; navigation does not create a second document model.

## Functional requirements

- Bulk/box selection records its intent and does not accidentally create an
  ordered distance, angle or torsion. Individual ordered picks and explicit
  measurement retain those workflows.
- Global, type and selected atom size coexist with scalar-property radius
  mapping. Mapping supports fitted/fixed ranges, frozen selection scope,
  trajectory properties, missing values and persistence. Browser rendering,
  image/video, standalone HTML, Blender and CAD exports share the effective
  radius representation. See `docs/property-radius.md`.
- Rendering scale is px/Å, independent of atom radius and viewport zoom.
- Save reuses a writable destination, original HTML/VASE format and stored
  output profile. Save As chooses a new destination. Browser limitations use an
  explicit fallback instead of pretending a download overwrites its source.
- Internal documents have independent dirty state, close decisions and reload
  recovery. Direct and notebook editors can adopt internal tabs in place.
- Scientific coordinates use double-precision trajectory transport. GPU display
  buffers may use floats, but visiting a frame cannot reduce precision in saved
  ASE Pickle or VASE data. Optical camera settings apply after fit and can be
  changed without supplying a new camera pose.

## Required commands

Use Command on macOS and Ctrl on Windows/Linux. The registry in
`static/editor_commands.js` is shared by menus, shortcut labels, search and
execution. Modifier aliases are not silently substituted.

| Command | macOS | Windows/Linux |
| --- | --- | --- |
| Supercell | Command+Shift+B | Ctrl+Shift+B |
| Atom properties | Command+Shift+P | Ctrl+Shift+P |
| Bonds | Command+B | Ctrl+B |
| Renderer | Command+Shift+A | Ctrl+Shift+A |
| Cell matrix | Command+E | Ctrl+E |
| Close internal document | Command+W | Ctrl+W |
| Save | Command+S | Ctrl+S |
| Save As | Command+Shift+S | Ctrl+Shift+S |
| New internal document | Command+N | Ctrl+N |

The browser application intercepts events it receives. Browser/OS-reserved
accelerators are not universally delivered to a web page. App fullscreen
Keyboard Lock is capability- and permission-dependent and reports its state;
ordinary browser fullscreen does not guarantee capture. Menus always provide
the same operations. See `docs/shortcuts.md` for input focus, Escape, G/R/S,
camera arrows and Option/Alt+trajectory navigation. Native application keyboard
capture belongs to the separately requested desktop delivery.

## Verification

- Full Python/Chromium suite: **1,019 passed, 2 skipped**, 508.66 seconds.
  The two optional-environment cases were then executed with the installed
  Sphinx/Jupyter runtime: **2 passed**. These cover shared HTML/LaTeX image
  fallback and a real kernel exercising `%v_ase inline`, `browser` and `auto`.
- `tests/test_browser_ui_geometry.py` checks all 23 tools at 1440, 1024 and
  390 px widths, long atom labels, expanded property mapping, bulk molecular
  fields and legend/control separation. Image/video dialogs are also checked
  at 640×360. Roving tool keyboard navigation preserves the camera.
- Browser regressions cover structure editing, ordered versus bulk selection,
  appearance, bonds, cells, constraints, relaxation, trajectories, fields,
  analysis, project formats, save conflicts, dirty close, tabs, reload and
  platform command dispatch. Blender/runtime and optional Rhino dependencies
  were available in the full-suite environment.
- Scientific identity regressions compare coordinates exactly across cached
  and streamed trajectories, including 260 atoms, edits and project/export
  round trips. No tolerance hides float32 truncation.
- A fresh agent using only the canonical Skill independently exercised guarded
  physical edits, constraints, properties, trajectory changes, axis cameras,
  exact-sized images, scientific exports, GUI/CLI collaboration and stale
  revision rejection. Its fresh-session recheck confirmed all three exported
  frames exactly, with maximum coordinate error 0 Å; camera scales 4 and 3.5
  were confirmed in state and visually inspected images. The bounded recheck
  made 17 successful semantic CLI calls. Provider token usage was unavailable.
- Typed tool reference generation, first-party JavaScript syntax and whitespace
  checks pass. Strict Sphinx HTML builds pass. Documentation was inspected at
  desktop and narrow widths, including the live logo, workflow, API/CLI,
  troubleshooting and developer navigation.
- All README image/animation capture groups were regenerated, synchronized to
  `docs/assets/github/`, and representative geometry/constraint frames inspected.

The full suite is the regression evidence; the independent agent check is
intentionally narrower. Native OS shortcut delivery was not falsely inferred
from synthetic browser events. PyPI/GitHub publication and clean published-wheel
verification follow `docs/release_checklist.md`; their external records identify
the actual released commit and artifacts.
