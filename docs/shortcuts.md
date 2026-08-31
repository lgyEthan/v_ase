# Visualizer Shortcuts & Controls

The visualizer is designed to be familiar to Blender users.

Use the top-bar **View / Edit** switch to change between lightweight
visualization and ASE-backed structural editing without reopening the file.
View applies materials by label. Edit can apply Standard, Metal, or Rubber to
individual selected atoms and can merge them into an existing label by entering
that exact label.

## Mouse Controls
- **Left Click**: Select an atom or the visible Sun light object.
- **Left Click during G/R/S transform**: Confirm the current transform.
- **Shift + Left Click**: Add/Remove from selection.
- **Left Drag**: Box select; the yellow marquee shows the active selection area.
- **Middle Mouse**: Orbit camera.
- **Shift + Middle Mouse**: Pan camera.
- **Scroll**: Zoom in/out.

Middle mouse orbit is an unrestricted Blender-style tumble; it does not clamp at
the top or bottom pole.

## Transformation Shortcuts
Press these keys to enter transformation mode:

| Key | Action | Description |
|-----|--------|-------------|
| **G** | **Grab** | Move selected atoms or the selected Sun object relative to the view plane. |
| **R** | **Rotate** | Rotate selected atoms around the configured pivot, or rotate the selected Sun direction. |
| **S** | **Scale spacing** | Physically scale selected atom spacing around the configured pivot without changing drawn radii or the unit cell. |
| **X** | **Align / Lock X** | In select mode, restore the canonical +X pose, including screen-up orientation. Press X again only from that exact pose to flip to -X. During G/R/S, lock the transform to X. |
| **Y** | **Align / Lock Y** | In select mode, restore the canonical +Y pose, including screen-up orientation. Press Y again only from that exact pose to flip to -Y. During G/R/S, lock the transform to Y. |
| **Z** | **Align / Lock Z** | In select mode, restore the canonical +Z pose, including screen-up orientation. Press Z again only from that exact pose to flip to -Z. During G/R/S, lock the transform to Z. |
| **Esc** | **Cancel / Inspector** | Revert an active transform or close a modal. Otherwise, open a collapsed control panel; when the panel is open, commit its active field, close it, and return keyboard focus to the viewport. |
| **Enter / Left Click** | **Confirm** | Confirm the current atom or Sun transform. |
| **Ctrl+C** | **Copy** | Copy selected atoms to the editor clipboard. |
| **Ctrl+V** | **Paste** | Paste copied atoms near the selected center. |
| **Ctrl+Z** | **Undo** | Restore the previous structure or visualization-setting action. Camera navigation is intentionally excluded. |
| **Ctrl+Shift+Z** | **Redo** | Reapply the next structure or visualization-setting action after undo. |
| **Delete / Backspace** | **Hide / Delete** | Hide exact visual instances in View; physically delete base atoms and remap supported constraints in Edit. |
| **Space** | **Play/Pause** | Toggle playback for the timeline selected below the viewport. |
| **Left / Right Arrow** | **Previous / Next Frame** | Move one frame in the selected source or relaxation timeline. |
| **Tab** | **Inspector** | Open the control panel while it is collapsed. `Esc` can also open it. Once open, Tab remains normal form navigation and never closes the panel. |

## Sun Direction Controls

Enable `Direction handles` in the lighting card, then select the source or
target in the viewport. Direct dragging selects a handle but does not move it.

| Selection | Shortcut | Result |
|-----------|----------|--------|
| **Sun source** | **G** | Translate source and target together without changing direction. |
| **Sun target** | **G** | Move only the target to aim the directional light. |
| **Either handle** | **R** | Rotate the target around the source pivot. Mouse rotation follows the same on-screen direction as atom rotation. |

Sun transforms support `X`/`Y`/`Z`, numeric input, `Enter`, and `Esc`.

## Visualization-Mode Replica Selection

In the default visualization mode, repeated supercell atoms are selectable by
click, Shift-click, box selection, element checkboxes, and `Ctrl+A`. Replica
identities include their cell offset (for example `12@[1,0,0]`), so center,
distance, and angle measurements use the positions actually shown on screen.
For base-cell atoms, the inspector, viewport overlay, and retained Measure HUD
show both direct-coordinate and minimum-image-convention (MIC) values.
Interactive mode keeps replicas unselectable until `Set Supercell as Cell` is
used, preventing a display-only image from entering an atom edit.

The bottom `MEASURE` HUD is tied to the retained selection, not the mouse
pointer. Ordered selections are labeled `a1` through `a4`: two atoms measure
`a1-a2`, three measure the `a1-a2-a3` angle at `a2`, and four measure the
signed `a1-a2-a3-a4` torsion. Direct and MIC results are displayed together.
Five or more atoms show the selected total followed by stable per-label
counts.
Box selection uses a deterministic visible order. The separate Hover HUD
continues to update atom metadata as the pointer moves.

Move and rotate snapping can be set in the right-side Transform section. A zero
increment keeps motion continuous; non-zero increments make mouse transforms step
in Angstrom or degree units.

During every atom rotation, the viewport shows the active pivot axis, a fixed
neutral start reference, and an amber reference that follows the current
rotation. Commensurate or magnetic candidates use separate cyan guides.

For a specific-atom pivot, select the moving atoms first, Shift-select the
pivot atom last, and choose **Active atom (last selected)** under
**Structure > Transform**. The active atom remains at the pivot while the
selected geometry rotates around it.

## Saving

The Export workspace keeps structure-independent settings separate from project
state:

- **Export ASE Pickle** writes the current ASE structure for Python use,
  including labels, cell/PBC, constraints, portable arrays, and valid
  `SinglePointCalculator` results. It does not include visualization settings.
- **Export Preset** writes JSON containing bonds, appearance, camera, lighting,
  quality, overlays, display supercell, and visual translation, but no atomic
  coordinates.
- **Set Current as Default** stores reusable visual choices for new structures
  and tabs under the current OS user. **Restore App Defaults** warns before
  deleting that preference and leaves structure data untouched.
- **Save Project** writes the complete structure or trajectory, current frame,
  edited coordinates, cell/PBC, constraints, labels, cached standard calculator
  results, and visual setup. The default compact output is `.vase`; enable the
  interactive rendered view to change the output to a restorable `.html`.
- **Export HTML View** writes one offline view-only browser document with the
  exact Preview Area camera crop, scene, and trajectory controls. Grid
  defaults off; axes and unit cell default on. The default file is a smaller
  view-only handoff, with optional complete `.vase` embedding.
- The **Save Project** dialog clearly reports `.vase` or `.html` before writing;
  HTML project output always includes complete `.vase` recovery.

Start with `v_ase gui` to open an empty workspace, then use the top-bar **Open**
command to launch the operating system file picker and load a structure,
trajectory, `.vase`, or project-embedded HTML. Choose **Replace this tab**, **Add to
trajectory**, or **Open in new tab** after selecting the file. Appending
`.vase` imports structures only; replacing or opening it in a new tab restores
the complete saved project.

## Constraint Behavior

- Confirmed transforms are committed through ASE with constraints enabled.
- `FixAtoms` remains immobile.
- `FixedLine` moves only along its direction.
- `FixedPlane` moves only within its plane.
- `FixScaled` follows its allowed fractional cell directions.
- Disable **Apply constraints** for unrestricted editing without removing the
  saved constraints.

`FixedLine` and `FixedPlane` guides remain visible without selecting the atom.
They stay local to each constrained atom and scale with its displayed radius.
Starting `G` on a FixedLine atom shows a longer direction guide through its
original position. Starting `G` on a FixedPlane atom shows a larger
translucent permitted-plane guide at its original position. Both clear when
the move is confirmed or canceled.

## Calculator Controls
- Repulsion controls live under **Structure > Relaxation** and appear only in
  Edit mode with the built-in v_ase calculator.
- `CPU` is the default device. `CUDA` is enabled only when torch and CUDA are
  available in the Python environment.
- Pair distances in Å are the default cutoff definition; strength defaults to
  `1.0`. Each label pair has an independent on/off switch and repulsion onset,
  initialized from covalent radii without reading the visible-bond table.
- **Scaled reference radii** is the optional alternative. Its
  contact-distance multiplier scales covalent or van der Waals reference
  radii together; a disabled pair or `0 Å` distance remains inactive.
- Torch is optional; NumPy fallback is used when torch is not installed.
