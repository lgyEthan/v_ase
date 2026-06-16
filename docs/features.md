# Features & Architecture

## Core Features
### Interactive Editing
Users can select atoms and transform them in 3D space. The positions are synchronized back to the Python ASE `Atoms` object in real-time.

### Blender-Style Workflow
The visualizer adopts the modal operator pattern from Blender:
1. Select atoms.
2. Press `G` or `R`.
3. (Optional) Press `X`, `Y`, or `Z` to lock axis.
4. Move mouse to transform.
5. Click or press `Enter` to confirm, or `Esc` to cancel.

### Editor Actions
The current editor supports copy/paste, undo/redo, Delete/Backspace deletion,
reset, wrap, Done/Cancel, POSCAR export, pickle export, viewport PNG image
export, WebM video export, Blender scene export, and calculator-backed
relaxation controls.

### Calculator Handling
Existing ASE calculators are preserved, including `SinglePointCalculator`.
When no calculator is attached, v_ase installs a default soft repulsion
calculator so Relax can still remove close contacts. The default calculator uses
NumPy when torch is unavailable. If torch is installed, it can run on CPU or
CUDA; torch is optional and is not a package dependency.

The top-right `DEVICE` and `CPU` controls apply only to this default repulsion
calculator. User-provided calculators are expected to manage their own execution
backend and are not modified by these controls.

### Display Tools
Bonds are rendered as live cylinder objects and update during transform previews,
relaxation updates, and trajectory frame changes. Bonding can use covalent-radius
inference, element-pair cutoff rows, or an explicit pair list such as `0-1, 1-2`. Unit cell, axes, grid, and
supercell preview controls are exposed in the inspector. Supercell preview is
only enabled when a valid unit cell exists and PBC is true in the requested
direction; otherwise the UI shows a warning and resets the invalid multiplier.

### Trajectory/Movie Playback
`view()` and `view_edit()` accept an `Atoms` object, a sequence of `Atoms`
frames, or an ASE-readable trajectory path. Multi-frame inputs expose an
OVITO-style timeline panel with previous/next, play/pause, frame slider, FPS,
and frame skip controls. Skip advances by `skip + 1` frames per playback tick,
so `0` means no skipped frames.

### File Type and Label Handling
The CLI accepts ASE-readable formats plus v_ase-specific helpers for custom
labels. extxyz labels such as `H_type5` are preserved as GUI labels while being
mapped to ASE-valid base elements. LAMMPS dump/data integer types are preserved
as raw GUI labels; valid integer ids are also interpreted as atomic numbers for
default color/radius distinction, while out-of-range ids fall back to internal
`H`.

### Appearance Editing
The Appearance table is label-oriented and stable under edits. Changing a label
does not reorder rows. If a label prefix names a real element, for example
`O_bridge`, the TYPE dropdown and default radius follow that element. When the
base element changes, stale radius/color overrides from the old label are not
blindly copied.

### ASE Constraint Compatibility
The visualizer respects ASE constraints:
- **FixAtoms**: Atoms marked as fixed cannot be moved or rotated.
- **Set Positions**: The backend uses `atoms.set_positions(..., apply_constraint=True)`, ensuring that even if the UI sends a move, ASE will enforce the physical constraints.

## Architecture
- **Backend**: FastAPI running through Uvicorn in a daemon thread. It serves static assets and provides REST endpoints for state updates, export, wrap/reset, and relaxation control.
- **Frontend**: A single-page application built with **Three.js**. It uses `Raycaster` for selection and a state-machine for transformations.
- **Communication**: JSON-over-HTTP for editing/export plus WebSockets for live relaxation updates.
    - `GET /api/atoms/{session_id}`: Fetches the current atoms state.
    - `POST /api/apply/{session_id}`: Applies new coordinates through ASE constraint logic.
    - `POST /api/add/{session_id}`: Appends atoms for paste operations.
    - `POST /api/delete/{session_id}`: Deletes selected atoms and remaps constraints.
    - `POST /api/calculator/{session_id}`: Updates default repulsion calculator CPU/CUDA settings.
    - `POST /api/frame/{session_id}`: Switches the active trajectory frame.
    - `POST /api/wrap/{session_id}`: Wraps atoms into the unit cell.
    - `POST /api/export/poscar/{session_id}`: Exports the current structure as POSCAR.
    - `POST /api/export/pickle/{session_id}`: Exports the current structure as a pickle.
    - `POST /api/export/blender/{session_id}`: Exports a Blender Python scene.
    - `POST /api/relax/start/{session_id}`: Starts geometry optimization.
    - `POST /api/relax/stop/{session_id}`: Requests geometry optimization stop.
    - `WS /ws/{session_id}`: Streams relaxation positions, energy, and fmax.
