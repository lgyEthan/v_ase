# ASE Blender-Style HTML Structure Editor - Project Specification & Progress

Last synchronized with implementation: `v_ase-gui 0.0.59`.

## 1. Project Goal
This project implements an interactive HTML-based structure editor for ASE `Atoms` objects.
It is intended to work like an extended version of `ase.visualize.view(atoms)`, but with professional-grade editing capabilities.

Unlike the default ASE viewer, this tool supports:
*   **Interactive Selection**: Click and Rectangle/Box selection.
*   **Blender-Style Transforms**: G (Move), R (Rotate) with X/Y/Z axis locking and numeric input.
*   **Constraint-Aware Editing**: Real-time backend synchronization using `set_positions(..., apply_constraint=True)`.
*   **Structural Modification**: Copy/paste appends atoms through the backend.
*   **Scientific Visualization**: Material-state fixed atoms, selection outlines, selected-constraint guides, cell-local or periodic-image bonds, unit-cell/axes/grid/overlay toggles, opt-in Studio Sun lighting, POSCAR/pickle/PNG/WebM/Blender export, wrap, and supercell preview.
*   **Default Lightweight CLI Viewer**: `v_ase gui FILE` opens in visualization mode by default; `--interactive` enables atom coordinate editing.
*   **Trajectory Playback**: Multi-frame `Atoms` inputs and ASE-readable trajectory files expose a movie timeline with live scrubbing, FPS, and frame skip controls.
*   **Live Simulation**: Real-time relaxation visualization using attached ASE calculators or the default v_ase repulsion calculator via WebSockets. Relaxation frames are collected into an optimization timeline when needed.

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
6.  **Interactive Visualization**: Bonds, selection outlines, selected-constraint guides, and full-material supercell replicas update dynamically without scene resets.

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
  calculators.py    # Public ASE calculator exports
  calculator.py     # Compatibility import module for calculators
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

Packaging hygiene:
*   The PyPI distribution is `v_ase-gui`; the import package and console command are both `v_ase`.
*   `pyproject.toml` owns the console entry point: `v_ase = v_ase.cli:main`.
*   Root-level generated `*.egg-info/` metadata is ignored and must not be committed or left in place before validating `pip install v_ase-gui` from the project root. Otherwise `pip` can treat the source tree as an already installed distribution and skip console-script generation.
*   PyPI install smoke tests should run from outside the repository root, for example under `/private/tmp`.

---

## 5. Backend and Frontend Stack
*   **Backend**: FastAPI + Uvicorn. Chosen for clean REST endpoints and native WebSocket support for live relaxation.
*   **Frontend**: HTML5 + Three.js (stable WebGL2 path). Implements a custom modal transform state machine, raycasting for selection, outlines, bonds, display overlays, and an opt-in directional-light/shadow renderer.

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
1.  **FixAtoms**: Visualized by changing the atom material itself to a micro-etched shader texture; movement blocked.
2.  **FixCartesian**: Backend-enforced during movement.
3.  **FixedLine / FixedPlane**: Backend-enforced via `set_positions(apply_constraint=True)`. These constraints keep the viewport clean until selected, then show minimal CAD-style line/plane guides. FixedPlane uses a soft transparent plane plus perimeter, crosshair, and normal tick. Multiple selected FixedPlane atoms use compact local plane markers per atom so the visual anchor never shifts to the selection COM.
4.  **FixScaled**: Backend-enforced by ASE and serialized into cell-aware `FixedPlane`, `FixedLine`, or fixed-atom visual guides according to the fractional-coordinate mask.
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
Fixed atoms use the atom mesh itself as the visual carrier; no separate hatch,
ring, or always-on overlay geometry is drawn.
*   **Material State**: Fixed atoms keep their radius and base hue, but use a micro-etched shader pattern with increased roughness. This reads as a material/constraint state without looking like selection.
*   **Depth Behavior**: The fixed-atom state is not a see-through overlay and is occluded normally by other atoms.
*   **Constraint Integrity**: Fixed atoms can be selected, but transform previews and final backend application do not move them.
*   **Selected Guides Only**: FixedLine and FixedPlane guides are drawn only for selected atoms. FixedLine uses a thin fading axis; FixedPlane uses a translucent soft-edge plane, thin bounding perimeter, central crosshair, and short normal marker. Multi-atom FixedPlane selections switch to compact per-atom circular markers to avoid both overlay stacking and false COM anchoring.
*   **Global Overlay Toggle**: `Show Overlays` hides selection outlines, selected constraint guides, Hookean overlays, and fixed-atom material marking for clean structure inspection or figure capture.

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
*   **Cell Boundary Default**: Direct current-cell distances are used by default, so cylinders do not point toward invisible neighboring-cell atoms.
*   **Periodic Images**: `Periodic image bonds` explicitly enables minimum-image vectors and image-crossing cylinders, following VESTA's separate inside-boundary / outside-boundary search policy.
*   **Interactive**: Auto and pairwise-cutoff bonds are re-inferred from the current preview coordinates during G/R transforms, so cylinders form and disappear before the transform is committed. Manual pairs keep their explicit topology and update cylinder geometry only.
*   **Label Pairs**: `Pairwise cutoff` rows are keyed by editable display labels, allowing chemically identical types such as `Cu_surface` and `Cu_bulk` to use different cutoffs. `0` explicitly disables a pair.
*   **Manual Pairs**: Explicit pair lists such as `0-1, 1-2` can be supplied in the Bonding panel.
*   **Recalculation**: Auto and pairwise-cutoff modes are re-inferred during interactive previews and whenever the trajectory frame changes. A cell-list search is used above the small-scene threshold, and bond meshes are rebuilt only when the inferred pair list changes.
*   **Persistent Settings**: Bond mode, global cutoff scale, label-pair `rcut` values, MIC policy, and manual pairs survive structure refreshes, transform commits, trajectory changes, and display-label edits. Relabeling copies matching pair settings before the renderer rebuilds.
*   **Supercell Preview**: Atom and bond instances are repeated for every positive supercell shift. Replicas use the original atom material at full opacity and participate in hover readout. Visualization mode gives every image a stable base-index/cell-offset identity for click, box, element, and `Ctrl+A` selection plus displayed-coordinate measurements. Interactive mode leaves display images unselectable until the supercell is committed as the cell.
*   **Appearance**: Bond thickness is the cylinder diameter or flat-ribbon width. Bonds can use a lit 3D cylinder or a camera-facing 2D ribbon, with either one custom color or two midpoint-split segments colored from their endpoint atoms. Viewport bonds retain GPU instancing but are grouped by final material color so custom and split colors are rendered exactly instead of relying on fragile per-instance shader colors. Viewport, PNG/WebM, visual-settings JSON, and Blender export share these values.

---

## 17. Atom Addition
*   **Copy/Paste**: `Ctrl+V` appends copied atoms through `ase.Atoms.append()`.
*   **Calculator**: The existing calculator is preserved after append operations.
*   **Create Atom Widget**: Interactive mode exposes a compact draggable viewport widget for adding an ASE-valid element or custom label at exact Cartesian coordinates.

---

## 18. Atom Deletion
Direct atom deletion is implemented. `Delete` and `Backspace` remove selected
atoms through the backend, remap constraints, preserve calculators where
possible, and update the frontend state. This behavior is covered by
`tests/test_complete_workflow_showcase.py` and frontend regression tests.

---

## 19. Top Bar, Reset, and Constraint Editing
*   **Apply / Done / Cancel buttons**: Removed from the visible top bar to avoid accidental session shutdown. Coordinate commits happen directly from viewport transform confirmation; backend finalization endpoints still exist for API-driven blocking workflows.
*   **Reset**: Revert to original input structure (preserving calculator).
*   **Wrap**: Explicitly call `Atoms.wrap()`.
*   **Constraint Panel**: Interactive mode can apply or clear `FixAtoms`, `FixedLine`, and `FixedPlane` on selected atoms. FixAtoms uses tri-state selection semantics; partial selections clear first, then can be applied to all selected atoms.
*   **Inspector Sections**: Inspect, Structure, Display, and Output tabs replace the single long inspector. Cell & Replication belongs to Structure; camera, appearance, and bonding belong to Display; exports and both save formats belong to Output. The panel starts fully collapsed and opens from a compact edge tab backed by a larger transparent hit area. Its active section, explicit collapsed state, and width persist locally.

---

## 20. Export
*   **VASP POSCAR**: Exported using `ase.io.write`.
*   **Pickle**: The UI exports a structure-only pickle. The Python handle can export with or without a calculator.
*   **PNG Image**: Export options include resolution, transparent background,
    grid, axes, and an independent Modeling, Studio Sun, or Sun + Soft Shadow
    setup with brightness, source, and direction target. Studio Sun uses
    parallel directional rays; its shadow camera is centered and fitted to the
    complete visible structure so large and off-origin models do not cross a
    finite shadow-frustum boundary.
*   **WebM Video**: Available for trajectories.
*   **Blender Script**: Optimized mode groups atoms into editable point meshes
    by label and uses Geometry Nodes for smooth sphere instancing. Trajectories
    use point-mesh shape keys, bonds are grouped by material, and the unit cell
    is one multi-spline curve. Individual atom objects remain an opt-in mode.
    The current camera and a Blender Sun rig preserve source, target-derived
    direction, color, and numeric energy. Blender can run the script and save a
    native `.blend`; OBJ loses camera, trajectory, lighting, instancing, and
    richer materials.

### Save Formats
*   **Visual Settings JSON**: Reusable bond topology/appearance, label
    appearance and visibility, quality, overlays, camera/projection, Sun, and
    supercell preview without structure coordinates. Loading intersects saved
    labels with current labels and gives newly encountered labels/pairs defaults.
*   **`.vase` Project**: Validated ZIP archive containing all trajectory frames,
    current frame, edited or locally wrapped coordinates, cells/PBC,
    constraints, labels, safe arrays, JSON-compatible info, cached standard ASE
    results, and visual settings. Executable calculator objects and undo history
    are deliberately excluded; cached results restore through
    `SinglePointCalculator`. The built-in repulsion calculator is reconstructed
    from validated primitive configuration so relaxation remains available.

---

## 21. Calculator Handling and Default Repulsion
*   **Preserve Existing Calculators**: `SinglePointCalculator` and other user-attached ASE calculators are kept and used as-is.
*   **Visualization Mode**: The default lightweight viewer preserves an existing calculator but does not attach a fallback calculator or show repulsion device controls.
*   **Interactive Default Calculator**: In `--interactive`, if an `Atoms` object has no calculator, v_ase attaches a default soft pair-repulsion ASE calculator.
*   **Model**: The default model uses harmonic repulsion below covalent-radius contact thresholds, with optional region penalties available in the calculator implementation.
*   **Torch Optional**: `torch` is not a package dependency. When present, the repulsion calculator can use torch CPU or CUDA; otherwise it falls back to NumPy.
*   **Device Controls**: Top-right `DEVICE` and `CPU` controls are visible only in interactive mode and enabled only for the default repulsion calculator. CPU defaults to 4 threads, capped by host CPU count.
*   **Public Calculator API**: The default model can be used directly with `from v_ase.calculators import RepulsionCalculator`. `Conditioner`, `DefaultRepulsionCalculator`, `from v_ase import RepulsionCalculator`, `v_ase.calculator`, and `v_ase.repulsion` are supported aliases for the same ASE calculator class.
*   **Future Calculators**: Device/thread controls do not modify user-defined calculators; those calculators must manage their own backend settings.

---

## 22. Relaxation
*   **Optimizer**: `ase.optimize.QuasiNewton`.
*   **Live Feedback**: Step-by-step WebSocket updates of Energy, Fmax, and Positions.
*   **Interactivity**: Real-time updates of bonds and markers during trajectory.
*   **Movie Mode**: Multi-frame structures expose frame slider, previous/next, play/pause, FPS, and frame skip controls.
*   **Interactive Restart**: In interactive mode, coordinate edits during relaxation stop the active optimizer and restart from the edited coordinates.
*   **Visualization Tracking**: In the default CLI visualization mode, atom editing remains disabled, but relaxation can be watched as streamed structure updates. Use `--interactive` for coordinate edits.

---

## 23. Calculator Preservation
**Mandatory Preservation:** Existing calculators are explicitly re-attached to the working atoms object after structural changes. In interactive mode, structures without a calculator receive the default repulsion fallback so "Relax" remains available. In visualization mode, no fallback calculator is attached unless the input already had one.

---

## 24. Large Visualization-Mode Trajectories
For default visualization-mode LAMMPS text dumps (`.lammpstrj` / `.dump`), v_ase does not build an ASE `Atoms` object for every frame during startup. The optimized path:
*   Builds a compact byte-offset index for all frames.
*   Parses the first visible frame into a normal ASE `Atoms` object.
*   Keeps the remaining frames as a virtual trajectory source.
*   Serves frame changes through a binary float32 position endpoint instead of JSON arrays.

This preserves the ASE bridge for the current frame while avoiding the startup and memory cost of materializing thousands of full ASE frames. The benchmark case
`side_project/bigger_atoms/efield_all.lammpstrj` (15,333 atoms, 1,051 frames, 1.1 GB) opens in under 5 seconds on the local test machine.

### 24.1 Frontend Rendering Pipeline
The 0.0.46 renderer removes the permanent animation loop. Camera movement,
trajectory playback, transforms, and state changes schedule a frame, while an
idle viewport schedules none. Large structures use shared unit-sphere geometry
and GPU instancing for atoms, bonds, selection outlines, and visualization-mode
supercell copies. Visibility changes update only indices belonging to changed
labels, and the device pixel ratio is capped progressively at 1,000, 5,000, and
15,000 atoms.

A fresh-browser validation on the local test machine loaded a synthetic
15,000-atom, 16-frame LAMMPS trajectory to a fully rendered 1280 x 720 canvas in
4.06 seconds. After completion, a 0.9-second idle sample produced zero additional
render frames. Studio Sun activated in 79 ms on the same scene. The complete
method is recorded in `docs/performance.md`.

---

## 25. Backend Endpoints
*   `GET /api/atoms/{session_id}`: Fetch structure + metadata.
*   `GET /api/frame/positions/{session_id}/{frame_index}`: Fetch one virtual trajectory frame as binary float32 positions.
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
*   `POST /api/settings/save/{session_id}`: Export reusable visual settings JSON.
*   `POST /api/settings/load/{session_id}`: Load validated JSON or restricted legacy settings.
*   `POST /api/project/save/{session_id}`: Export the complete session as `.vase`.
*   `POST /api/project/load/{session_id}`: Replace the active session from `.vase`.
*   `POST /api/relax/start/{session_id}`: Start relaxation.
*   `POST /api/relax/stop/{session_id}`: Request relaxation stop.
*   `WS /ws/{session_id}`: Trajectory stream.

---

## 26. Session Management
Each editor instance is assigned a unique `UUID` session. Multiple editors can run simultaneously on different ports/endpoints without state collision.

---

## 27. Implementation Status
*   [x] **Phase 1-3**: Basic Viewer, Editing, Constraints (Completed).
*   [x] **Phase 4-5**: Selection Outlines, Interactive Bonds, Display Controls (Completed).
*   [x] **Phase 6-8**: Copy/Paste Append, Export, Live Relaxation (Completed).
*   [x] **Phase 9**: Jupyter IFrame Support (Completed).
*   [x] **Phase 10**: Focused Unit, API, Browser-Flow, and Packaging Tests (kept current through 0.0.59).
*   [x] **Phase 11**: Manual Bonds, Grid, Image Export, and Trajectory Movie Controls.
*   [x] **Phase 12**: LAMMPS dump/data parsing, custom atom-type labels, default visualization mode, Appearance panel editing, frame skip, and PyPI packaging.
*   [x] **Phase 13**: Default repulsion calculator, optional torch/CUDA controls, CPU thread selection, and relaxation restart on interactive edits.
*   [x] **Phase 14**: Public ASE calculator import API for the default repulsion model.
*   [x] **Phase 15**: Top-bar cleanup and interactive selected-atom constraint editing.
*   [x] **Phase 16**: Micro-etched FixAtoms material, bounded FixedPlane guide, and fast virtual LAMMPS trajectory loading for default visualization mode.
*   [x] **Phase 17**: `--interactive` edit-mode opt-in, bounded/copyable selection fields, orientation widget, visualization-mode wrap, and instanced full-opacity supercell repeats.
*   [x] **Phase 18**: Repulsion calculator device controls relabeled in the top bar, and visualization-mode supercell repeats use same color material grouping as original atoms.
*   [x] **Phase 19**: Visualization mode no longer attaches or displays the default repulsion calculator; Blender export reuses shared sphere meshes per radius/color material to reduce import cost for large structures.
*   [x] **Phase 20**: Orthographic projection is the default view, viewport lighting uses symmetric fill plus camera-follow fill, Appearance row order remains the initial file order after relabeling, and trajectory auto/element bonds are re-inferred per frame.
*   [x] **Phase 21**: FixAtoms remain visible in default visualization mode using faceted, micro-etched materials, and viewport lighting adds a camera-follow directional fill so +Y/-Y axis views stay balanced.
*   [x] **Phase 22**: Blocking CLI sessions finalize when the browser tab/window closes by using WebSocket disconnect detection with a short reconnect grace period.
*   [x] **Phase 23**: Number fields keep browser-native spin buttons, while native spin-button presses are intercepted so each press produces exactly one step and cannot continue repeating after pointer release outside the field.
*   [x] **Phase 24**: Appearance atom-type rows preserve the initial natural label order, and element/type changes cannot merge distinct atom-type labels when multiple labels share one chemical element.
*   [x] **Phase 25**: Appearance `TYPE` changes update chemical element, default radius, and color while preserving existing labels; automatic bond inference uses covalent-radius tolerance (`1.2 * (r_i + r_j)`) to avoid water intermolecular false bonds.
*   [x] **Phase 26**: Middle-button viewport tumble/pan keeps window-level pointer and mouseup fallback listeners active, so transient browser pointer-capture loss does not stop rotation while the physical button is still held.
*   [x] **Phase 27**: Interactive mode includes a compact floating Create Atom widget outside the inspector, and Python API sessions explicitly close their WebSocket on browser pagehide so browser-window close finalizes sessions like the CLI path.
*   [x] **Phase 28**: ASE `FixScaled` constraints from VASP selective dynamics are visualized as cell-aware FixedPlane/FixedLine guides instead of being collapsed into FixAtoms.
*   [x] **Phase 29**: Multi-atom FixedPlane selections use compact per-atom local markers instead of COM-centered or heavily overlapping planes, and quick or long relaxation runs populate an optimization timeline without showing a useless single-frame bar for plain static structures.
*   [x] **Phase 30**: Added a standalone HTML design preview with five FixedLine and five FixedPlane persistent-marker candidates, plus fixed-atom reference styling.
*   [x] **Phase 31**: Consolidated the desktop UI into one responsive style system, integrated the atomistic v_ase logo in the app/package/README, added demand rendering and adaptive DPR, and instanced atoms, bonds, selection outlines, and visualization-mode supercells for large-scene performance.
*   [x] **Phase 32**: Added collapsible inspector navigation, opt-in Studio Sun and soft-shadow rendering with viewport light controls and independent image-export settings, plus a VESTA-style cell-local bond default with explicit periodic-image MIC mode.
*   [x] **Phase 33**: Auto and pairwise-cutoff bonds now form and break live during interactive G/R previews, while all user bond settings persist across backend structure refreshes, trajectory changes, and label edits.
*   [x] **Phase 34**: Added persistent bond thickness, custom or midpoint-split atom colors, 3D cylinder and camera-facing flat-ribbon styles, GPU-instanced rendering, and matching Blender export.
*   [x] **Phase 35**: Replaced the ambiguous inspector chevron construction with explicit action glyphs, removed the redundant Workspace header label, and introduced an illuminated-object vector icon for render lighting.
*   [x] **Phase 36**: Replaced direct Sun-handle dragging with selectable Blender-style `G`/`R` light transforms, including axis locks, numeric input, confirm/cancel, robust viewport focus, and exact Sun transform/intensity export to Blender.
*   [x] **Phase 37**: The inspector now starts collapsed behind a small geometric panel-edge handle with a robust invisible hit area; render lighting is centered above the orientation gizmo and uses a clearly illuminated, two-tone sphere icon whose control card opens away from the gizmo.
*   [x] **Phase 38**: The inspector handle is centered vertically and slightly enlarged without sacrificing its compact edge-tab form; render lighting now sits to the gizmo's right and uses an explicit Sun-to-sphere illumination icon with a ground shadow.
*   [x] **Phase 39**: Made custom and midpoint-split bond colors use color-grouped instanced materials for reliable final rendering, and unified number/text/color input commits across Enter, Tab, and focus changes.
*   [x] **Phase 40**: Reworked Studio Sun as a structure-fitted directional light, eliminating finite shadow-map seams while preserving planar illumination. Source and target are independently selectable for Blender-style `G`/`R` transforms; the render-lighting control lives beside the calculator in the top toolbar, and browser tests cover both handles, shadow bounds, export settings, and responsive placement.
*   [x] **Phase 41**: Supercell previews now instance full-opacity unselectable-but-hoverable atoms and repeated live bonds in every cell; pairwise cutoffs are label-keyed with explicit zero-disable semantics; `Tab` toggles the inspector and all category panels default open; Blender export writes opaque colors to Principled BSDF and is runtime-render tested in Blender 5.
*   [x] **Phase 42**: Studio Sun now behaves as a coherent light rig: moving the source translates source and target together, moving the target changes aim only, and rotating either selected handle always orbits the target around the source pivot.
*   [x] **Phase 43**: Appearance relabeling now commits atomically across Enter/change/focus events; visualization-mode supercell images are independently selectable and measurable by cell offset; Selection center fractional coordinates use a dedicated second line; the bottom HUD exposes live selection measurements; and Sun mouse rotation follows atom rotation direction.
*   [x] **Phase 44**: Split persistent selection measurements from pointer-dependent hover metadata, reduced the viewport summary to distance/angle essentials, replaced the bulb-like lighting glyph with a directional studio spotlight, and regenerated the logo plus README media with the current Sun + Soft Shadow renderer.
*   [x] **Phase 45**: Added portable JSON visual presets and validated full-state `.vase` projects, reorganized the inspector into Inspect/Structure/Display/Output, optimized Blender export with Geometry Nodes point groups and trajectory shape keys, and runtime-tested a 15,000-atom Blender 5 scene at 0.700 seconds.

---

## 28. Prohibited Implementations
*   **NO** camera rotation on Left Drag.
*   **NO** client-side-only constraints (always sync with ASE backend).
*   **NO** stale auto/element bond topology during movement; re-infer it from preview coordinates. Manual pair topology remains explicit and only its geometry may stretch.
*   **NO** silent calculator loss.
*   **NO** mandatory torch dependency for the default repulsion model.
*   **NO** device/thread controls applied to user-provided calculators.

---

## 28. Known Limitations
1.  Bonds are visualization-only (not stored in `Atoms.topology`).
2.  Some heavy calculators may lag during real-time constraint dragging.
3.  Supercell images are display-only repeats. Visualization mode can select and measure them, but interactive editing requires `Set Supercell as Cell`.

---

**Final Completion Criterion Met**: An ASE Atoms object can be edited with Blender-style controls, respecting all constraints and calculators, and returned seamlessly to a Python workflow.
