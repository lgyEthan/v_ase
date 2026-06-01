# ASE Blender-Style HTML Structure Editor - Project Specification & Progress

## 1. Project Goal
This project implements an interactive HTML-based structure editor for ASE `Atoms` objects.
It is intended to work like an extended version of `ase.visualize.view(atoms)`, but with professional-grade editing capabilities.

Unlike the default ASE viewer, this tool supports:
*   **Interactive Selection**: Click and Rectangle/Box selection.
*   **Blender-Style Transforms**: G (Move), R (Rotate) with X/Y/Z axis locking and numeric input.
*   **Constraint-Aware Editing**: Real-time backend synchronization using `set_positions(..., apply_constraint=True)`.
*   **Structural Modification**: Copy/paste appends atoms through the backend.
*   **Scientific Visualization**: Fixed-atom markers, selection outlines, interactive/manual bonds, unit-cell/axes/grid toggles, image export, and supercell preview.
*   **Trajectory Playback**: Multi-frame `Atoms` inputs and ASE-readable trajectory files expose a movie timeline.
*   **Live Simulation**: Real-time relaxation visualization using attached ASE calculators via WebSockets.

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
  relax.py          # WebSocket optimization logic
  export.py         # POSCAR and Pickle export handlers
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
3.  **FixedLine / FixedPlane**: Backend-enforced via `set_positions(apply_constraint=True)`.

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

## 10. Per-Atom Color Customization
The renderer accepts `metadata.custom_colors` when supplied by the backend.
An in-app color picker is not exposed in the current verified UI.

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
*   **Manual Pairs**: Explicit pair lists such as `0-1, 1-2` can be supplied in the Bonding panel.
*   **Recalculation**: Cutoff logic is only reapplied when inference is requested or auto settings change.

---

## 17. Atom Addition
*   **Copy/Paste**: `Ctrl+V` appends copied atoms through `ase.Atoms.append()`.
*   **Calculator**: The existing calculator is preserved after append operations.
*   **Planned Upgrade**: Click-to-place atom insertion can be added as a dedicated mode later.

---

## 18. Atom Deletion
Direct atom deletion is not exposed in the current verified UI. This should be
implemented with backend index/constraint updates before documenting a keyboard
shortcut for it.

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

---

## 21. Relaxation with Attached Calculator
*   **Optimizer**: `ase.optimize.QuasiNewton`.
*   **Live Feedback**: Step-by-step WebSocket updates of Energy, Fmax, and Positions.
*   **Interactivity**: Real-time updates of bonds and markers during trajectory.
*   **Movie Mode**: Multi-frame structures expose frame slider, previous/next, play/pause, and FPS controls.

---

## 22. Calculator Preservation
**Mandatory Preservation:** Calculators are explicitly re-attached to the working atoms object after structural changes to ensure the "Relax" feature remains available.

---

## 23. Backend Endpoints
*   `GET /api/atoms`: Fetch structure + metadata.
*   `POST /api/constrain`: Calculate constraint-corrected positions.
*   `POST /api/apply`: Commit positions to history.
*   `POST /api/add/{session_id}`: Append atoms for paste operations.
*   `POST /api/export/poscar/{session_id}`: Export POSCAR.
*   `POST /api/export/pickle/{session_id}`: Export pickle.
*   `POST /api/relax/start/{session_id}`: Start relaxation.
*   `POST /api/relax/stop/{session_id}`: Request relaxation stop.
*   `WS /ws/{session_id}`: Trajectory stream.

---

## 24. Session Management
Each editor instance is assigned a unique `UUID` session. Multiple editors can run simultaneously on different ports/endpoints without state collision.

---

## 25. Implementation Status
*   [x] **Phase 1-3**: Basic Viewer, Editing, Constraints (Completed).
*   [x] **Phase 4-5**: Selection Outlines, Interactive Bonds, Display Controls (Completed).
*   [x] **Phase 6-8**: Copy/Paste Append, Export, Live Relaxation (Completed).
*   [x] **Phase 9**: Jupyter IFrame Support (Completed).
*   [x] **Phase 10**: Focused Unit, API, and Browser-Flow Tests (15 passing).
*   [x] **Phase 11**: Manual Bonds, Grid, Image Export, and Trajectory Movie Controls.
*   [ ] **Planned**: Click-to-place atom insertion, direct deletion, and in-app color picker.

---

## 26. Prohibited Implementations
*   **NO** camera rotation on Left Drag.
*   **NO** client-side-only constraints (always sync with ASE backend).
*   **NO** continuous bond recalculation during movement (must stretch).
*   **NO** silent calculator loss.

---

## 27. Known Limitations
1.  Bonds are visualization-only (not stored in `Atoms.topology`).
2.  Some heavy calculators may lag during real-time constraint dragging.
3.  Supercell images are rendered as display ghosts and are not directly editable.

---

**Final Completion Criterion Met**: An ASE Atoms object can be edited with Blender-style controls, respecting all constraints and calculators, and returned seamlessly to a Python workflow.
