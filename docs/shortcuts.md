# Visualizer Shortcuts & Controls

The visualizer is designed to be familiar to Blender users.

## Mouse Controls
- **Left Click**: Select an atom.
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
| **G** | **Grab** | Move selected atoms relative to the view plane. |
| **R** | **Rotate** | Rotate selected atoms around their collective center. |
| **X** | **Align / Lock X** | In select mode, align the viewport to the X-axis. During G/R, lock movement/rotation to X. |
| **Y** | **Align / Lock Y** | In select mode, align the viewport to the Y-axis. During G/R, lock movement/rotation to Y. |
| **Z** | **Align / Lock Z** | In select mode, align the viewport to the Z-axis. During G/R, lock movement/rotation to Z. |
| **Esc** | **Cancel** | Revert atoms to their original positions. |
| **Enter / Left Click** | **Confirm** | Save new positions to the ASE Atoms object. |
| **Ctrl+C** | **Copy** | Copy selected atoms to the editor clipboard. |
| **Ctrl+V** | **Paste** | Paste copied atoms near the selected center. |
| **Ctrl+Z** | **Undo** | Restore the previous structure state. |
| **Ctrl+Shift+Z** | **Redo** | Restore the next structure state after undo. |
| **Delete / Backspace** | **Delete** | Delete selected atoms through the backend and remap supported constraints. |
| **Space** | **Play/Pause** | Toggle trajectory playback when a multi-frame structure is loaded. |

Move and rotate snapping can be set in the right-side Transform section. A zero
increment keeps motion continuous; non-zero increments make mouse transforms step
in Angstrom or degree units.

## Constraint Behavior
- Atoms constrained with `FixAtoms` in ASE will appear as "Fixed" in the UI.
- Even if selected, these atoms will not move when transformations are applied.

## Calculator Controls
- The top-right `DEVICE` and `CPU` controls are active only for the default
  v_ase repulsion calculator.
- `CPU` is the default device. `CUDA` is enabled only when torch and CUDA are
  available in the Python environment.
- Torch is optional; NumPy fallback is used when torch is not installed.
