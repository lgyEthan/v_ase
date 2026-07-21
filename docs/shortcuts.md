# Visualizer Shortcuts & Controls

The visualizer is designed to be familiar to Blender users.

## Mouse Controls
- **Left Click**: Select an atom or the visible Sun light object.
- **Left Click during G/R transform**: Confirm the current transform.
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
| **R** | **Rotate** | Rotate selected atoms around their collective center, or rotate the selected Sun direction. |
| **X** | **Align / Lock X** | In select mode, align the viewport to +X. Press X again only from exact +X alignment to flip to -X. During G/R, lock movement/rotation to X. |
| **Y** | **Align / Lock Y** | In select mode, align the viewport to +Y. Press Y again only from exact +Y alignment to flip to -Y. During G/R, lock movement/rotation to Y. |
| **Z** | **Align / Lock Z** | In select mode, align the viewport to +Z. Press Z again only from exact +Z alignment to flip to -Z. During G/R, lock movement/rotation to Z. |
| **Esc** | **Cancel / Return** | Revert an active transform. Otherwise, commit the active inspector field, close the open control panel, and return keyboard focus to the viewport. |
| **Enter / Left Click** | **Confirm** | Confirm the current atom or Sun transform. |
| **Ctrl+C** | **Copy** | Copy selected atoms to the editor clipboard. |
| **Ctrl+V** | **Paste** | Paste copied atoms near the selected center. |
| **Ctrl+Z** | **Undo** | Restore the previous structure state. |
| **Ctrl+Shift+Z** | **Redo** | Restore the next structure state after undo. |
| **Delete / Backspace** | **Delete** | Delete selected atoms through the backend and remap supported constraints. |
| **Space** | **Play/Pause** | Toggle trajectory playback when a multi-frame structure is loaded. |
| **Tab** | **Inspector** | Open the control panel while it is collapsed. Once open, Tab remains normal form navigation and never closes the panel. |

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
Interactive mode keeps replicas unselectable until `Set Supercell as Cell` is
used, preventing a display-only image from entering an atom edit.

The bottom `MEASURE` HUD is tied to the retained selection, not the mouse
pointer: two atoms show one distance, three show the angle plus its two adjacent
distances, and larger selections show only the atom count. The separate Hover
HUD continues to update atom metadata as the pointer moves.

Move and rotate snapping can be set in the right-side Transform section. A zero
increment keeps motion continuous; non-zero increments make mouse transforms step
in Angstrom or degree units.

## Saving

The Output workspace keeps structure-independent settings separate from project
state:

- **Export ASE Pickle** writes the current ASE structure for Python use,
  including labels, cell/PBC, constraints, portable arrays, and valid
  `SinglePointCalculator` results. It does not include visualization settings.
- **Save Settings** writes JSON containing bonds, appearance, camera, lighting,
  quality, overlays, and supercell preview, but no atomic coordinates.
- **Save .vase** writes the complete structure or trajectory, current frame,
  edited coordinates, cell/PBC, constraints, labels, cached standard calculator
  results, and visual setup. Reopen it with `v_ase gui FILE.vase`.

Start with `v_ase gui` to open an empty workspace, then use the top-bar **Open**
command to load a structure, trajectory, or `.vase` project.

## Constraint Behavior
- Atoms constrained with `FixAtoms` in ASE will appear as "Fixed" in the UI.
- Even if selected, these atoms will not move when transformations are applied.

## Calculator Controls
- The top-right `DEVICE` and `CPU` controls are active only for the default
  v_ase repulsion calculator.
- `CPU` is the default device. `CUDA` is enabled only when torch and CUDA are
  available in the Python environment.
- Torch is optional; NumPy fallback is used when torch is not installed.
