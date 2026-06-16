# ASE Blender-Style HTML Structure Editor - Project Specification & Progress

Last synchronized with implementation: `v_ase-gui 0.0.21`.

## 1. Project Goal
This project implements an interactive HTML-based structure editor for ASE `Atoms` objects.
It is intended to work like an extended version of `ase.visualize.view(atoms)`, but with professional-grade editing capabilities.

Unlike the default ASE viewer, this tool supports:
*   **Interactive Selection**: Click and Rectangle/Box selection.
*   **Blender-Style Transforms**: G (Move), R (Rotate) with X/Y/Z axis locking and numeric input.
*   **Constraint-Aware Editing**: Real-time backend synchronization using `set_positions(..., apply_constraint=True)`.
*   **Structural Modification**: Copy/paste appends atoms through the backend.
*   **Scientific Visualization**: Fixed-atom markers, selection outlines, interactive/manual bonds, unit-cell/axes/grid toggles, POSCAR/pickle/PNG/WebM/Blender export, wrap, and supercell preview.
*   **Trajectory Playback**: Multi-frame `Atoms` inputs and ASE-readable trajectory files expose a movie timeline with live scrubbing, FPS, and frame skip controls.
*   **Live Simulation**: Real-time relaxation visualization using attached ASE calculators or the default v_ase repulsion calculator via WebSockets.

The final interface is usable directly from Python:
```python
from v_ase.visualize import view
edited_atoms = view(atoms)
```

---

## 2. Core Design Principles
1.  **Input/Output Consistency**: Always accepts and returns valid `ase.Atoms` objects.
2.  **Non-Mutating**: The original input object is never modified; a working copy is used.
3.  **Constraint Integrity**: ASE constraints are strictly respected during all coordinate updates via the backend.
4.  **Blender UX**: Mouse and keyboard patterns follow Blender (e.g., Left-drag for selection, G/R for transform).
5.  **Calculator Inheritance**: Calculators are preserved across structural changes (Addition/Deletion/Relaxation).
6.  **Interactive Visualization**: Bonds, selection outlines, fixed-atom markers, and supercell ghosts update dynamically without scene resets.

---

## 3. Required Python API
The main entry point is `view`:
```python
def view(
    atoms,
    *,
    notebook=False,
    block=True,
    port=None,
    show_cell=True,
    show_axes=True,
    show_bonds=False,
    respect_constraints=True,
    allow_relax=True,
    export=True,
    return_mode="atoms",
):
    """
    Open an interactive Blender-style ASE Atoms editor.
    ...
    """
```

---

## 4. Package Structure
```
v_ase/
  __init__.py       # Public package import path
  visualize.py      # from v_ase.visualize import view
  cli.py            # v_ase gui command line entry point
  viewer.py         # Main API and server lifecycle
  server.py         # FastAPI application and session endpoints
  session.py        # EditorSession state model
  serialization.py  # Atoms -> JSON conversion
  repulsion.py      # Default optional-torch/NumPy ASE repulsion calculator
  relax.py          # WebSocket optimization logic
  export.py         # POSCAR, Pickle, Blender, image, and video export handlers
  static/
    index.html      # UI layout
    main.js         # Application orchestration
    renderer.js     # Three.js scene rendering
    selection.js    # Raycast and rectangle selection
    transform.js    # Modal transform state
    style.css       # UI theme
```

---

## 5. Backend and Frontend Stack
*   **Backend**: FastAPI + Uvicorn. Chosen for clean REST endpoints and native WebSocket support for live relaxation.
*   **Frontend**: HTML5 + Three.js (WebGL). Implements a custom modal transform state machine, raycasting for selection, outlines, bonds, and display overlays.

---

## 6. ASE Atoms Serialization
Structures are serialized into a rich JSON format:
```json
{
  "symbols": ["Si", "O"],
  "positions": [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]],
  "cell": [[10,0,0], [0,10,0], [0,0,10]],
  "constraints": { "fixed_indices": [0] },
  "metadata": { "custom_colors": { "1": "#ff0000" }, "has_calculator": true }
}
```

---

## 7. ASE Constraints
The editor currently supports:
1.  **FixAtoms**: Visualized via a translucent atom and lock ring; movement blocked.
2.  **FixCartesian**: Backend-enforced during movement.
3.  **FixedLine / FixedPlane**: Backend-enforced via `set_positions(apply_constraint=True)` and visualized with line/plane guides on selected atoms.
4.  **FixScaled**: Serialized and handled as an ASE constraint in backend coordinate application.
5.  **Hookean**: Visualized as a threshold-aware latch/spring; inactive and active states are shown based on current distance and `rt`.

---

## 8. Constraint-Aware Atom Movement
**Constraint Integrity is Mandatory.** 
*   **During Grab (G)**: The frontend sends proposed coordinates to `/api/constrain`.
*   **Backend Application**: `working_atoms.set_positions(positions, apply_constraint=True)` is called.
*   **Dynamic Response**: The backend returns the corrected positions (snapped to line/plane/point).
*   **Display**: The frontend updates the display using these corrected coordinates in near-real-time.

---

## 9. Fixed Atom Visualization
Fixed atoms are rendered as translucent atoms with a lock ring marker.
*   **Visibility**: The marker tracks the atom and remains visible during camera rotation.
*   **Constraint Integrity**: Fixed atoms can be selected, but transform previews and final backend application do not move them.
*   **Planned Upgrade**: A technical hatching shader can be added later, but it is not part of the current verified implementation.

---

## 10. Appearance and Atom-Type Editing
The Appearance panel exposes per-label controls for:
*   **TYPE**: ASE-valid base element dropdown.
*   **VISIBLE**: Hide/show the label group; hidden atoms are not selectable.
*   **SELECT**: Checkbox with all/partial/none selection state.
*   **LABEL**: GUI label editing, including custom labels such as `O_bridge`.
*   **COLOR**: Per-label color picker.
*   **RADIUS / A**: Per-label radius override.

Rows keep the first-seen atom-label order and do not jump to alphabetical order
during label edits. When a label prefix maps to a real element, for example
`O_bridge` or `Si_type3`, the TYPE dropdown follows that element immediately and
the default radius is taken from the corresponding ASE GUI radius. If the base
element changes, old label-specific radius/color overrides are not blindly
copied to the new label.

---

## 11. Mouse Controls
**Selection-First Policy:**
*   **Left Drag**: Rectangle/Box selection (Does NOT rotate camera).
*   **Middle Drag**: Rotate camera.
*   **Shift + Middle Drag**: Pan camera.
*   **Wheel**: Zoom.
*   **Left Click**: Select single atom.

---

## 12. Blender-Style Transform Controls
*   **Move (G)**: View-plane displacement.
*   **Rotate (R)**: View-axis rotation.
*   **Locking (X, Y, Z)**: Restricts movement/rotation to global axes.
*   **Numeric Input**: Type values during transform (e.g., `G X 1.5 <Enter>`).

---

## 13. Visible Transform Axis
When an axis is locked (X/Y/Z), a clear guide line appears:
*   **X Axis**: Red line through pivot.
*   **Y Axis**: Green line through pivot.
*   **Z Axis**: Blue line through pivot.
These guides disappear immediately upon confirmation or cancellation.

---

## 14. Numeric Input
A command buffer is displayed in the UI:
*   **Example**: `MODE: MOVE | Axis: X | Value: 1.5 Å`
*   Supports: Numbers, decimal points, negative signs, Backspace, and Enter.

---

## 15. Transform State Machine
The frontend manages modes: `IDLE`, `MOVE`, `ROTATE`. Transitions are triggered by keydown events, and the state determines how mouse movement and numeric input are processed.

---

## 16. Bond Visualization
*   **Inference**: Initially created based on covalent radii + scale factor.
*   **Interactive**: Once enabled, cylinder bonds **stretch and rotate** to follow atom movement in real time.
*   **Element/Type Pairs**: Element-pair cutoff rows are exposed in the Bonding panel.
*   **Manual Pairs**: Explicit pair lists such as `0-1, 1-2` can be supplied in the Bonding panel.
*   **Recalculation**: Cutoff logic is only reapplied when inference is requested or auto settings change.

---

## 17. Atom Addition
*   **Copy/Paste**: `Ctrl+V` appends copied atoms through `ase.Atoms.append()`.
*   **Calculator**: The existing calculator is preserved after append operations.
*   **Planned Upgrade**: Click-to-place atom insertion can be added as a dedicated mode later.

---

## 18. Atom Deletion
Direct atom deletion is implemented. `Delete` and `Backspace` remove selected
atoms through the backend, remap constraints, preserve calculators where
possible, and update the frontend state. This behavior is covered by
`tests/test_complete_workflow_showcase.py` and frontend regression tests.

---

## 19. Apply, Done, Cancel, Reset
*   **Apply**: Sync current positions and constraints to backend history.
*   **Done**: Finalize and return structure to Python.
*   **Cancel**: Discard all changes.
*   **Reset**: Revert to original input structure (preserving calculator).
*   **Wrap**: Explicitly call `Atoms.wrap()`.

---

## 20. Export
*   **VASP POSCAR**: Exported using `ase.io.write`.
*   **Pickle**: The UI exports a structure-only pickle. The Python handle can export with or without a calculator.
*   **PNG Image**: Export options include transparent background, grid, and axes.
*   **WebM Video**: Available for trajectories.
*   **Blender Script**: Exports atoms, unit cell, bonds, constraints where practical, and the current camera.

---

## 21. Calculator Handling and Default Repulsion
*   **Preserve Existing Calculators**: `SinglePointCalculator` and other user-attached ASE calculators are kept and used as-is.
*   **Default Calculator**: If an `Atoms` object has no calculator, v_ase attaches a default soft pair-repulsion ASE calculator.
*   **Model**: The default model uses harmonic repulsion below covalent-radius contact thresholds, with optional region penalties available in the calculator implementation.
*   **Torch Optional**: `torch` is not a package dependency. When present, the repulsion calculator can use torch CPU or CUDA; otherwise it falls back to NumPy.
*   **Device Controls**: Top-right `DEVICE` and `CPU` controls are enabled only for the default repulsion calculator. CPU defaults to 4 threads, capped by host CPU count.
*   **Future Calculators**: Device/thread controls do not modify user-defined calculators; those calculators must manage their own backend settings.

---

## 22. Relaxation
*   **Optimizer**: `ase.optimize.QuasiNewton`.
*   **Live Feedback**: Step-by-step WebSocket updates of Energy, Fmax, and Positions.
*   **Interactivity**: Real-time updates of bonds and markers during trajectory.
*   **Movie Mode**: Multi-frame structures expose frame slider, previous/next, play/pause, FPS, and frame skip controls.
*   **Interactive Restart**: In interactive mode, coordinate edits during relaxation stop the active optimizer and restart from the edited coordinates.
*   **Viz-Only Tracking**: In `--viz-only`, atom editing remains disabled, but relaxation can be watched as streamed structure updates.

---

## 23. Calculator Preservation
**Mandatory Preservation:** Calculators are explicitly re-attached to the working atoms object after structural changes to ensure the "Relax" feature remains available.

---

## 24. Backend Endpoints
*   `GET /api/atoms/{session_id}`: Fetch structure + metadata.
*   `POST /api/constrain/{session_id}`: Calculate constraint-corrected positions.
*   `POST /api/apply/{session_id}`: Commit positions to history.
*   `POST /api/add/{session_id}`: Append atoms for paste operations.
*   `POST /api/delete/{session_id}`: Delete selected atoms with constraint remapping.
*   `POST /api/calculator/{session_id}`: Update default repulsion calculator device/thread settings.
*   `POST /api/frame/{session_id}`: Switch the active trajectory frame.
*   `POST /api/wrap/{session_id}`: Wrap atoms into the current unit cell.
*   `POST /api/export/poscar/{session_id}`: Export POSCAR.
*   `POST /api/export/pickle/{session_id}`: Export pickle.
*   `POST /api/export/blender/{session_id}`: Export a Blender Python scene.
*   `POST /api/relax/start/{session_id}`: Start relaxation.
*   `POST /api/relax/stop/{session_id}`: Request relaxation stop.
*   `WS /ws/{session_id}`: Trajectory stream.

---

## 25. Session Management
Each editor instance is assigned a unique `UUID` session. Multiple editors can run simultaneously on different ports/endpoints without state collision.

---

## 26. Implementation Status
*   [x] **Phase 1-3**: Basic Viewer, Editing, Constraints (Completed).
*   [x] **Phase 4-5**: Selection Outlines, Interactive Bonds, Display Controls (Completed).
*   [x] **Phase 6-8**: Copy/Paste Append, Export, Live Relaxation (Completed).
*   [x] **Phase 9**: Jupyter IFrame Support (Completed).
*   [x] **Phase 10**: Focused Unit, API, and Browser-Flow Tests (70 collected as of 0.0.21).
*   [x] **Phase 11**: Manual Bonds, Grid, Image Export, and Trajectory Movie Controls.
*   [x] **Phase 12**: LAMMPS dump/data parsing, custom atom-type labels, `--viz-only`, Appearance panel editing, frame skip, and PyPI packaging.
*   [x] **Phase 13**: Default repulsion calculator, optional torch/CUDA controls, CPU thread selection, and relaxation restart on interactive edits.
*   [ ] **Planned**: Click-to-place atom insertion and optional technical hatching shader for fixed atoms.

---

## 27. Prohibited Implementations
*   **NO** camera rotation on Left Drag.
*   **NO** client-side-only constraints (always sync with ASE backend).
*   **NO** continuous bond recalculation during movement (must stretch).
*   **NO** silent calculator loss.
*   **NO** mandatory torch dependency for the default repulsion model.
*   **NO** device/thread controls applied to user-provided calculators.

---

## 28. Known Limitations
1.  Bonds are visualization-only (not stored in `Atoms.topology`).
2.  Some heavy calculators may lag during real-time constraint dragging.
3.  Supercell images are rendered as display ghosts and are not directly editable.

---

**Final Completion Criterion Met**: An ASE Atoms object can be edited with Blender-style controls, respecting all constraints and calculators, and returned seamlessly to a Python workflow.
