import os
import threading
import asyncio
from contextlib import asynccontextmanager, suppress
import pickle
import io
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List
from .session import (
    append_session_frames,
    EditorSession,
    create_workspace_session,
    finalize_workspace,
    get_session,
    get_workspace,
    remove_workspace_session,
    replace_session_frames,
    sessions,
    workspaces,
)
from .serialization import atoms_to_json
from .websocket_manager import ws_manager
from .io import atom_labels, base_symbol_for_atom_type, normalize_atom_type_label, set_atom_labels
from .repulsion import (
    copy_calculator,
    ensure_default_calculator,
    is_vase_repulsion_calculator,
    repulsion_metadata,
)
from .commensurate import find_commensurate_angles
from .ai import AI_PROTOCOL, ai_skill_path
from .project import (
    PROJECT_MIME,
    SETTINGS_SCHEMA,
    normalize_visual_settings,
    read_project_archive,
    replace_session_from_project,
    write_project_archive,
)
import numpy as np
from ase import Atom
from ase.build import make_supercell
from ase.build.supercells import lattice_points_in_supercell
from ase.constraints import FixAtoms, FixCartesian, FixedLine, FixedPlane, FixScaled, Hookean
from ase.data import atomic_numbers
from ase.geometry import find_mic
from ase.io.formats import string2index

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
    from starlette.background import BackgroundTask
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FastAPI = None
    WebSocket = Any
    WebSocketDisconnect = Exception
    BackgroundTasks = Any
    BackgroundTask = None
    Request = Any
    StaticFiles = None
    HTMLResponse = None
    FileResponse = None
    JSONResponse = None
    Response = None
    HTTPException = RuntimeError
    FASTAPI_AVAILABLE = False


class _MissingFastAPIApp:
    def mount(self, *args, **kwargs):
        return None

    def on_event(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def get(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def post(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def websocket(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator


@asynccontextmanager
async def app_lifespan(_app):
    broadcaster = asyncio.create_task(ws_manager.broadcaster_task())
    try:
        yield
    finally:
        broadcaster.cancel()
        with suppress(asyncio.CancelledError):
            await broadcaster


app = FastAPI(lifespan=app_lifespan) if FASTAPI_AVAILABLE else _MissingFastAPIApp()
_SESSION_AUTOCLOSE_GRACE_SECONDS = 1.2
_session_autoclose_timers: Dict[str, threading.Timer] = {}
_session_autoclose_lock = threading.Lock()
_workspace_autoclose_timers: Dict[str, threading.Timer] = {}
_workspace_autoclose_lock = threading.Lock()
_workspace_closing_clients: Dict[str, set[str]] = {}


def _remove_temporary_file(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass

if FASTAPI_AVAILABLE:
    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc):
        message = str(exc)
        status = 404 if message.startswith("Session ") else 400
        return JSONResponse(status_code=status, content={"detail": message})

# Ensure static mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if FASTAPI_AVAILABLE:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


MAX_INLINE_TRAJECTORY_CACHE_VALUES = 750_000
MAX_BINARY_TRAJECTORY_CACHE_VALUES = 30_000_000
MAX_UPLOADED_STRUCTURE_BYTES = 64 * 1024 * 1024 * 1024
MAX_UPLOADED_IMAGE_BYTES = 512 * 1024 * 1024
MAX_UPLOADED_VIDEO_BYTES = 2 * 1024 * 1024 * 1024
MAX_LAUNCH_DIRECTORY_ENTRIES = 5000

AI_CONTROL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": (
        "https://github.com/lgyEthan/v_ase/blob/main/v_ase/skills/"
        "visualizing-atomic-structures-with-v-ase/SKILL.md"
    ),
    "title": "v_ase semantic browser control",
    "description": (
        "Commands accepted by window.v_aseAI.apply(). They control the same "
        "live document that a human sees in the v_ase GUI."
    ),
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "frame": {"type": "integer", "minimum": 0},
        "mode": {"enum": ["view", "edit"]},
        "applyConstraints": {"type": "boolean"},
        "quality": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "antiAliasing": {"type": "boolean"},
                "sphereQuality": {
                    "enum": ["auto", "low", "medium", "high", "ultra"],
                },
            },
        },
        "display": {
            "type": "object",
            "description": (
                "Partial visual settings. Common keys include showBonds, "
                "showCell, showAxes, showGrid, viewportBackground, "
                "atomDisplayMode, atomRadiusScale, bondThickness, "
                "supercell, translation, translationMode, lightingMode, "
                "sunIntensity, sunPosition, and sunTarget."
            ),
            "additionalProperties": True,
        },
        "selection": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "clear": {"type": "boolean"},
                "indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "uniqueItems": True,
                },
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["index", "cellOffset"],
                        "properties": {
                            "index": {"type": "integer", "minimum": 0},
                            "cellOffset": {
                                "type": "array",
                                "prefixItems": [
                                    {"type": "integer"},
                                    {"type": "integer"},
                                    {"type": "integer"},
                                ],
                                "minItems": 3,
                                "maxItems": 3,
                            },
                        },
                    },
                },
            },
        },
        "operation": {
            "description": (
                "One semantic structure operation. Supported names are wrap, "
                "translate-all, set-supercell, make-supercell, add-atom, "
                "delete-selection, set-identity, set-constraints, "
                "move-selection, rotate-selection, undo, redo, "
                "reset-coordinates, start-relaxation, stop-relaxation, and "
                "refresh-displacements."
            ),
            "oneOf": [
                {
                    "type": "string",
                    "enum": [
                        "wrap", "undo", "redo", "reset-coordinates",
                        "stop-relaxation", "refresh-displacements",
                    ],
                },
                {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "enum": [
                                "wrap", "translate-all", "set-supercell",
                                "make-supercell", "add-atom",
                                "delete-selection", "set-identity",
                                "set-constraints", "move-selection",
                                "rotate-selection", "undo", "redo",
                                "reset-coordinates", "start-relaxation",
                                "stop-relaxation", "refresh-displacements",
                            ],
                        },
                    },
                    "additionalProperties": True,
                },
            ],
        },
        "camera": {
            "type": "object",
            "description": (
                "Use axis for a deterministic +/-X, +/-Y, or +/-Z view; use "
                "position/target/up for an explicit camera; fit='structure' "
                "frames the complete structure; orbit applies screen-relative "
                "left/right/up/down/roll-cw/roll-ccw rotations."
            ),
            "additionalProperties": True,
            "properties": {
                "axis": {
                    "enum": ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
                },
                "position": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "target": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "up": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "projection": {"enum": ["orthographic", "perspective"]},
                "fit": {"enum": ["structure"]},
                "orbit": {
                    "type": "object",
                    "required": ["direction"],
                    "properties": {
                        "direction": {
                            "enum": [
                                "left", "right", "up", "down",
                                "roll-cw", "roll-ccw",
                            ],
                        },
                        "degrees": {
                            "type": "number",
                            "exclusiveMinimum": 0,
                            "maximum": 360,
                        },
                    },
                },
            },
        },
    },
}


def trajectory_layout_compatible(session: EditorSession) -> bool:
    """Return whether every frame shares atom identity, cell, and PBC."""
    if session._trajectory_layout_compatible is not None:
        return session._trajectory_layout_compatible
    if session.frame_count <= 1:
        session._trajectory_layout_compatible = False
        return False
    if session.trajectory_source is not None:
        source = session.trajectory_source
        if int(getattr(source, "natoms", -1)) != len(session.working_atoms):
            session._trajectory_layout_compatible = False
            return False
        cells = np.asarray(getattr(source, "cells", []), dtype=float)
        pbc = np.asarray(getattr(source, "pbc", []), dtype=bool)
        compatible = bool(
            cells.shape == (session.frame_count, 3, 3)
            and pbc.shape == (session.frame_count, 3)
            and np.allclose(cells, cells[0])
            and np.all(pbc == pbc[0])
        )
        session._trajectory_layout_compatible = compatible
        return compatible
    natoms = len(session.working_atoms)
    base_labels = atom_labels(session.working_atoms)
    base_cell = np.asarray(session.working_atoms.cell.array)
    base_pbc = np.asarray(session.working_atoms.pbc, dtype=bool)
    for frame in session.trajectory_frames:
        if len(frame) != natoms:
            session._trajectory_layout_compatible = False
            return False
        if atom_labels(frame) != base_labels:
            session._trajectory_layout_compatible = False
            return False
        if not np.array_equal(np.asarray(frame.pbc, dtype=bool), base_pbc):
            session._trajectory_layout_compatible = False
            return False
        if not np.allclose(np.asarray(frame.cell.array), base_cell):
            session._trajectory_layout_compatible = False
            return False
    session._trajectory_layout_compatible = True
    return True


def trajectory_position_cache(
    session: EditorSession,
    *,
    layout_compatible: bool | None = None,
):
    if bool((session.config or {}).get("stream_trajectory", False)):
        return None
    natoms = len(session.working_atoms)
    if session.frame_count * natoms * 3 > MAX_INLINE_TRAJECTORY_CACHE_VALUES:
        return None
    if layout_compatible is None:
        layout_compatible = trajectory_layout_compatible(session)
    if not layout_compatible:
        return None
    if session.trajectory_source is not None:
        # Virtual trajectories stay off the initial JSON path. The browser
        # requests their compact float32 cache in the background instead.
        return None
    return [frame.get_positions().tolist() for frame in session.trajectory_frames]


def trajectory_position_array(
    session: EditorSession,
    *,
    layout_compatible: bool | None = None,
):
    if bool((session.config or {}).get("stream_trajectory", False)):
        return None
    natoms = len(session.working_atoms)
    value_count = session.frame_count * natoms * 3
    if value_count > MAX_BINARY_TRAJECTORY_CACHE_VALUES:
        return None
    if layout_compatible is None:
        layout_compatible = trajectory_layout_compatible(session)
    if not layout_compatible:
        return None
    if session.trajectory_source is not None:
        array = np.empty((session.frame_count, natoms, 3), dtype=np.float32)
        for frame_index in range(session.frame_count):
            array[frame_index] = session.trajectory_source.read_positions(frame_index)
        return array
    return np.asarray(
        [frame.get_positions() for frame in session.trajectory_frames],
        dtype=np.float32,
    )


def session_atoms_to_json(session: EditorSession, include_inline_trajectory: bool = True):
    data = atoms_to_json(session.working_atoms)
    data["metadata"]["config"] = session.config
    data["metadata"]["frame_count"] = session.frame_count
    data["metadata"]["current_frame"] = session.current_frame
    data["metadata"]["virtual_trajectory"] = session.trajectory_source is not None
    data["metadata"]["trajectory_streaming"] = bool(
        (session.config or {}).get("stream_trajectory", False)
    )
    data["metadata"]["calculator_details"] = repulsion_metadata(session.working_atoms.calc)
    if is_vase_repulsion_calculator(session.working_atoms.calc):
        data["metadata"]["calculator"] = "Repulsion"
        data["metadata"]["has_calculator"] = True
    layout_compatible = trajectory_layout_compatible(session)
    trajectory_positions = (
        trajectory_position_cache(session, layout_compatible=layout_compatible)
        if include_inline_trajectory
        else None
    )
    data["metadata"]["trajectory_positions_cached"] = trajectory_positions is not None
    if trajectory_positions is not None:
        data["trajectory_positions"] = trajectory_positions
    data["metadata"]["trajectory_positions_binary"] = (
        not data["metadata"]["trajectory_streaming"]
        and trajectory_positions is None
        and session.frame_count > 1
        and session.frame_count * len(session.working_atoms) * 3 <= MAX_BINARY_TRAJECTORY_CACHE_VALUES
        and layout_compatible
    )
    return data


def session_update_to_json(session: EditorSession):
    """Serialize an update without retransmitting inline trajectory frames."""
    return session_atoms_to_json(session, include_inline_trajectory=False)


def payload_apply_constraint(payload: Dict[str, Any] | None) -> bool:
    if not payload:
        return True
    return bool(payload.get("apply_constraint", True))


def sync_session_frame_from_payload(
    session: EditorSession,
    payload: Dict[str, Any] | None,
) -> int:
    """Synchronize backend state with the frame currently shown in the browser."""
    if not payload or payload.get("frame_index") is None:
        return int(session.current_frame)
    try:
        frame_index = int(payload["frame_index"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="frame_index must be an integer.") from exc
    if frame_index < 0 or frame_index >= session.frame_count:
        raise HTTPException(
            status_code=400,
            detail=f"Frame index {frame_index} is out of range for {session.frame_count} frames.",
        )
    if frame_index != session.current_frame:
        session.set_frame(frame_index)
    return frame_index


def is_viz_only(session: EditorSession) -> bool:
    return bool((session.config or {}).get("viz_only", False))


def session_allows_disconnect_autoclose(session: EditorSession) -> bool:
    return bool((session.config or {}).get("auto_close_on_disconnect", False))


def finalize_session_from_browser_close(session_id: str) -> None:
    session = sessions.get(session_id)
    if session is None or session.done_event.is_set():
        return
    if not session_allows_disconnect_autoclose(session):
        return
    if ws_manager.has_session_connection(session_id):
        return
    session.result_atoms = session.working_atoms.copy()
    if session.working_atoms.calc:
        session.result_atoms.calc = copy_calculator(session.working_atoms.calc)
    session.done_event.set()


def cancel_session_autoclose(session_id: str) -> None:
    with _session_autoclose_lock:
        timer = _session_autoclose_timers.pop(session_id, None)
    if timer is not None:
        timer.cancel()


def schedule_session_autoclose(session_id: str, delay: float = _SESSION_AUTOCLOSE_GRACE_SECONDS) -> None:
    session = sessions.get(session_id)
    if session is None or not session_allows_disconnect_autoclose(session):
        return
    cancel_session_autoclose(session_id)

    def close_if_still_disconnected() -> None:
        try:
            finalize_session_from_browser_close(session_id)
        finally:
            with _session_autoclose_lock:
                _session_autoclose_timers.pop(session_id, None)

    timer = threading.Timer(delay, close_if_still_disconnected)
    timer.daemon = True
    with _session_autoclose_lock:
        _session_autoclose_timers[session_id] = timer
    timer.start()


def _workspace_connection_client_ids(workspace_id: str) -> set[str]:
    prefix = f"workspace:{workspace_id}:"
    legacy = f"workspace:{workspace_id}"
    client_ids: set[str] = set()
    for connection_id in list(ws_manager.active_connections.values()):
        if connection_id == legacy:
            client_ids.add("__legacy__")
        elif isinstance(connection_id, str) and connection_id.startswith(prefix):
            client_ids.add(connection_id[len(prefix):])
    return client_ids


def cancel_workspace_autoclose(
    workspace_id: str,
    *,
    connected_client_id: str | None = None,
) -> None:
    with _workspace_autoclose_lock:
        timer = _workspace_autoclose_timers.pop(workspace_id, None)
        if connected_client_id:
            closing = _workspace_closing_clients.get(workspace_id)
            if closing is not None:
                closing.discard(connected_client_id)
                if not closing:
                    _workspace_closing_clients.pop(workspace_id, None)
    if timer is not None:
        timer.cancel()


def schedule_workspace_autoclose(
    workspace_id: str,
    delay: float = _SESSION_AUTOCLOSE_GRACE_SECONDS,
    *,
    closing_client_id: str | None = None,
) -> None:
    workspace = workspaces.get(workspace_id)
    if workspace is None or not bool(
        (workspace.host_session.config or {}).get(
            "workspace_auto_close_on_disconnect",
            True,
        )
    ):
        return

    def close_if_still_disconnected() -> None:
        should_finalize = False
        try:
            with _workspace_autoclose_lock:
                if _workspace_autoclose_timers.get(workspace_id) is not timer:
                    return
                closing_clients = set(
                    _workspace_closing_clients.get(workspace_id, set())
                )
            active_clients = _workspace_connection_client_ids(workspace_id)
            with _workspace_autoclose_lock:
                if _workspace_autoclose_timers.get(workspace_id) is not timer:
                    return
                _workspace_autoclose_timers.pop(workspace_id, None)
                should_finalize = not (active_clients - closing_clients)
            if should_finalize:
                finalize_workspace(workspace_id)
        finally:
            with _workspace_autoclose_lock:
                if _workspace_autoclose_timers.get(workspace_id) is timer:
                    _workspace_autoclose_timers.pop(workspace_id, None)
                if workspace_id not in workspaces:
                    _workspace_closing_clients.pop(workspace_id, None)

    timer = threading.Timer(delay, close_if_still_disconnected)
    timer.daemon = True
    with _workspace_autoclose_lock:
        previous_timer = _workspace_autoclose_timers.pop(workspace_id, None)
        if closing_client_id:
            _workspace_closing_clients.setdefault(workspace_id, set()).add(
                closing_client_id
            )
        _workspace_autoclose_timers[workspace_id] = timer
    if previous_timer is not None:
        previous_timer.cancel()
    timer.start()


def require_editable(session: EditorSession, action: str = "This operation"):
    if is_viz_only(session):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{action} is disabled in View mode. "
                "Switch the top-bar mode to Edit before modifying atoms."
            ),
        )


def validate_supercell_atoms(atoms, reps: List[int]):
    if len(reps) != 3 or any(v < 1 for v in reps):
        raise HTTPException(status_code=400, detail="Supercell repetitions must be three positive integers.")
    if atoms.cell.rank == 0:
        raise HTTPException(status_code=400, detail="Set Supercell as Cell requires a defined unit cell.")
    pbc = atoms.pbc
    for axis, value in enumerate(reps):
        if value > 1 and not bool(pbc[axis]):
            raise HTTPException(
                status_code=400,
                detail=f"Supercell axis {axis + 1} requires PBC=True in that direction."
            )


def validate_supercell_request(session: EditorSession, reps: List[int]):
    validate_supercell_atoms(session.working_atoms, reps)


def repeat_atoms_as_supercell(atoms, reps: List[int]):
    validate_supercell_atoms(atoms, reps)
    new_constraints = repeat_supported_constraints(atoms, reps)
    source = atoms.copy()
    source.set_constraint()
    repeated = source.repeat(tuple(reps))
    if new_constraints:
        repeated.set_constraint(new_constraints)
    if atoms.calc:
        repeated.calc = copy_calculator(atoms.calc)
    return repeated


def validate_supercell_matrix_atoms(atoms, matrix):
    try:
        raw = np.array(matrix, dtype=float)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="make_supercell matrix must be numeric.") from exc
    if raw.shape != (3, 3):
        raise HTTPException(status_code=400, detail="make_supercell matrix must be a 3 x 3 integer matrix.")
    if not np.all(np.isfinite(raw)) or not np.allclose(raw, np.round(raw), atol=1e-9):
        raise HTTPException(status_code=400, detail="make_supercell matrix entries must be integers.")
    P = np.array(np.round(raw), dtype=int)
    if atoms.cell.rank == 0:
        raise HTTPException(status_code=400, detail="make_supercell requires a defined unit cell.")
    det = int(round(np.linalg.det(P)))
    if det <= 0:
        raise HTTPException(status_code=400, detail="make_supercell matrix must have a positive non-zero determinant.")
    if det * len(atoms) > 20000:
        raise HTTPException(status_code=400, detail="make_supercell result is too large for interactive editing.")
    identity = np.eye(3, dtype=int)
    for axis, periodic in enumerate(atoms.pbc):
        if not bool(periodic) and (
            not np.array_equal(P[:, axis], identity[:, axis])
            or not np.array_equal(P[axis, :], identity[axis, :])
        ):
            raise HTTPException(
                status_code=400,
                detail=f"make_supercell cannot mix, tilt, or repeat non-periodic axis {axis + 1}."
            )
    return P


def validate_supercell_matrix_request(session: EditorSession, matrix):
    return validate_supercell_matrix_atoms(session.working_atoms, matrix)


def supercell_matrix_offsets(atoms, matrix):
    P = np.array(matrix, dtype=int)
    supercell = np.dot(P, np.array(atoms.cell))
    lattice_points_frac = lattice_points_in_supercell(P)
    lattice_points = np.dot(lattice_points_frac, supercell)
    natoms = len(atoms)
    for image, shift in enumerate(lattice_points):
        yield image * natoms, np.array(shift, dtype=float)


def repeat_supported_constraints_for_matrix(atoms, matrix):
    constraints = list(atoms.constraints or [])
    if not constraints:
        return []
    natoms = len(atoms)
    repeated = []
    offsets = list(supercell_matrix_offsets(atoms, matrix))
    for constraint in constraints:
        if isinstance(constraint, FixAtoms):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in offsets:
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixAtoms(indices=indices))
        elif isinstance(constraint, FixCartesian):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in offsets:
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixCartesian(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixedLine):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in offsets:
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixedLine(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixedPlane):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in offsets:
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixedPlane(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixScaled):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in offsets:
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixScaled(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, Hookean):
            for offset, shift in offsets:
                if constraint._type == "two atoms":
                    repeated.append(Hookean(
                        constraint.indices[0] + offset,
                        constraint.indices[1] + offset,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
                elif constraint._type == "point":
                    repeated.append(Hookean(
                        constraint.index + offset,
                        np.array(constraint.origin) + shift,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
                elif constraint._type == "plane":
                    A, B, C, D = constraint.plane
                    shifted_plane = [A, B, C, D - float(np.dot([A, B, C], shift))]
                    repeated.append(Hookean(
                        constraint.index + offset,
                        shifted_plane,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
    return repeated


def make_supercell_atoms(atoms, matrix):
    P = validate_supercell_matrix_atoms(atoms, matrix)
    new_constraints = repeat_supported_constraints_for_matrix(atoms, P)
    source = atoms.copy()
    source.set_constraint()
    transformed = make_supercell(source, P, wrap=True, order="cell-major")
    if new_constraints:
        transformed.set_constraint(new_constraints)
    if atoms.calc:
        transformed.calc = copy_calculator(atoms.calc)
    return transformed


def translate_atoms(atoms, vector, coordinate_mode="cartesian"):
    shift = np.asarray(vector, dtype=float)
    if shift.shape != (3,) or not np.isfinite(shift).all():
        raise HTTPException(status_code=400, detail="Translation must contain three finite numeric components.")
    mode = str(coordinate_mode or "cartesian").strip().lower()
    if mode == "fractional":
        cell = np.asarray(atoms.cell.array, dtype=float)
        if cell.shape != (3, 3) or not np.isfinite(cell).all() or np.linalg.norm(cell) < 1e-12:
            raise HTTPException(
                status_code=400,
                detail="Fractional translation requires a defined unit cell.",
            )
        shift = np.dot(shift, cell)
    elif mode != "cartesian":
        raise HTTPException(
            status_code=400,
            detail="Translation coordinate mode must be 'cartesian' or 'fractional'.",
        )

    translated = atoms.copy()
    translated.translate(shift)
    if atoms.calc:
        translated.calc = copy_calculator(atoms.calc)
    return translated


def set_current_payload_positions(session: EditorSession, payload: Dict[str, Any]):
    sync_session_frame_from_payload(session, payload)
    if payload and payload.get("positions") is not None:
        session.working_atoms.set_positions(
            np.array(payload["positions"]),
            apply_constraint=payload_apply_constraint(payload),
        )
        session.sync_current_frame()


def refresh_working_frame(session: EditorSession):
    if session.trajectory_source is not None:
        session.set_frame(session.current_frame)
        return
    session.working_atoms = session.trajectory_frames[session.current_frame].copy()
    if session.trajectory_frames[session.current_frame].calc:
        session.working_atoms.calc = copy_calculator(session.trajectory_frames[session.current_frame].calc)


def apply_all_frames(session: EditorSession, transform):
    if not session.trajectory_frames:
        session.working_atoms = transform(session.working_atoms)
        session.sync_current_frame()
        return

    session.trajectory_frames = [transform(frame) for frame in session.trajectory_frames]
    refresh_working_frame(session)


def supercell_image_offsets(natoms: int, reps: List[int]):
    image = 0
    cell = None
    # The shift vector is computed by the caller because it depends on the
    # original cell.  Keep the index order identical to ASE Atoms.repeat().
    for ix in range(reps[0]):
        for iy in range(reps[1]):
            for iz in range(reps[2]):
                yield image * natoms, (ix, iy, iz)
                image += 1


def repeat_supported_constraints(atoms, reps: List[int]):
    constraints = list(atoms.constraints or [])
    if not constraints:
        return []
    natoms = len(atoms)
    cell = np.array(atoms.cell)
    repeated = []
    for constraint in constraints:
        if isinstance(constraint, FixAtoms):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in supercell_image_offsets(natoms, reps):
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixAtoms(indices=indices))
        elif isinstance(constraint, FixCartesian):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in supercell_image_offsets(natoms, reps):
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixCartesian(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixedLine):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in supercell_image_offsets(natoms, reps):
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixedLine(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixedPlane):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in supercell_image_offsets(natoms, reps):
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixedPlane(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixScaled):
            indices = []
            base_indices = [int(i) for i in constraint.index]
            for offset, _ in supercell_image_offsets(natoms, reps):
                indices.extend([i + offset for i in base_indices])
            repeated.append(FixScaled(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, Hookean):
            for offset, image in supercell_image_offsets(natoms, reps):
                shift = np.dot(image, cell)
                if constraint._type == "two atoms":
                    repeated.append(Hookean(
                        constraint.indices[0] + offset,
                        constraint.indices[1] + offset,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
                elif constraint._type == "point":
                    repeated.append(Hookean(
                        constraint.index + offset,
                        np.array(constraint.origin) + shift,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
                elif constraint._type == "plane":
                    A, B, C, D = constraint.plane
                    shifted_plane = [A, B, C, D - float(np.dot([A, B, C], shift))]
                    repeated.append(Hookean(
                        constraint.index + offset,
                        shifted_plane,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
    return repeated


def _constraint_indices(constraint, natoms: int):
    if not hasattr(constraint, "index"):
        return []
    index = constraint.index
    if isinstance(index, slice):
        return [int(i) for i in np.arange(natoms)[index]]
    return [int(i) for i in np.atleast_1d(index)]


def constraints_after_delete(atoms, delete_indices):
    deleted = {int(i) for i in delete_indices}
    index_map = {
        old_index: new_index
        for new_index, old_index in enumerate(i for i in range(len(atoms)) if i not in deleted)
    }
    remapped = []
    for constraint in atoms.constraints or []:
        if isinstance(constraint, FixAtoms):
            indices = [index_map[i] for i in _constraint_indices(constraint, len(atoms)) if i in index_map]
            if indices:
                remapped.append(FixAtoms(indices=indices))
        elif isinstance(constraint, FixCartesian):
            indices = [index_map[i] for i in _constraint_indices(constraint, len(atoms)) if i in index_map]
            if indices:
                remapped.append(FixCartesian(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixedLine):
            indices = [index_map[i] for i in _constraint_indices(constraint, len(atoms)) if i in index_map]
            if indices:
                remapped.append(FixedLine(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixedPlane):
            indices = [index_map[i] for i in _constraint_indices(constraint, len(atoms)) if i in index_map]
            if indices:
                remapped.append(FixedPlane(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixScaled):
            indices = [index_map[i] for i in _constraint_indices(constraint, len(atoms)) if i in index_map]
            if indices:
                remapped.append(FixScaled(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, Hookean):
            if constraint._type == "two atoms":
                i, j = [int(v) for v in constraint.indices]
                if i in index_map and j in index_map:
                    remapped.append(Hookean(index_map[i], index_map[j], rt=constraint.threshold, k=constraint.spring))
            elif constraint._type == "point":
                i = int(constraint.index)
                if i in index_map:
                    remapped.append(Hookean(index_map[i], np.array(constraint.origin), rt=constraint.threshold, k=constraint.spring))
            elif constraint._type == "plane":
                i = int(constraint.index)
                if i in index_map:
                    remapped.append(Hookean(index_map[i], constraint.plane, rt=constraint.threshold, k=constraint.spring))
    return remapped


def delete_indices_from_atoms(atoms, delete_indices):
    indices = sorted({int(i) for i in delete_indices})
    if not indices:
        return atoms.copy()
    if indices[0] < 0 or indices[-1] >= len(atoms):
        raise HTTPException(status_code=400, detail="Delete indices are out of range.")
    new_constraints = constraints_after_delete(atoms, indices)
    new_atoms = atoms.copy()
    new_atoms.set_constraint()
    del new_atoms[indices]
    if new_constraints:
        new_atoms.set_constraint(new_constraints)
    if atoms.calc:
        new_atoms.calc = copy_calculator(atoms.calc)
    return new_atoms


def inferred_base_symbol_for_label(label) -> str | None:
    normalized = normalize_atom_type_label(label)
    if normalized in atomic_numbers:
        return normalized
    prefix = normalized.split("_", 1)[0]
    if prefix in atomic_numbers:
        return prefix
    import re
    match = re.match(r"^([A-Z][a-z]?)", normalized)
    if match and match.group(1) in atomic_numbers:
        return match.group(1)
    return None


def update_atom_identity_on_atoms(atoms, indices, label, base_symbol=None):
    indices = sorted({int(i) for i in indices})
    if not indices:
        return atoms.copy()
    if indices[0] < 0 or indices[-1] >= len(atoms):
        raise HTTPException(status_code=400, detail="Atom indices are out of range.")
    normalized = normalize_atom_type_label(label)
    if not normalized:
        raise HTTPException(status_code=400, detail="Atom label cannot be empty.")

    updated = atoms.copy()
    symbols = updated.get_chemical_symbols()
    type_labels = atom_labels(updated)
    base_symbol = base_symbol_for_atom_type(base_symbol) if base_symbol else inferred_base_symbol_for_label(normalized)
    for idx in indices:
        if base_symbol:
            symbols[idx] = base_symbol
        type_labels[idx] = normalized
    updated.set_chemical_symbols(symbols)
    set_atom_labels(updated, type_labels)
    if atoms.calc:
        updated.calc = copy_calculator(atoms.calc)
    return updated


def indices_present_in_atoms(atoms, indices):
    """Return stable atom indices that exist in this trajectory frame."""
    return sorted({
        int(index)
        for index in indices
        if 0 <= int(index) < len(atoms)
    })


def update_atom_identity_where_present(atoms, indices, label, base_symbol=None):
    valid = indices_present_in_atoms(atoms, indices)
    if not valid:
        return atoms.copy()
    return update_atom_identity_on_atoms(
        atoms,
        valid,
        label,
        base_symbol,
    )


def set_atom_identity_arrays_on_atoms(atoms, labels, base_symbols=None):
    """Apply an exact client identity snapshot without changing coordinates."""
    normalized_labels = [normalize_atom_type_label(label) for label in labels]
    if len(normalized_labels) != len(atoms) or any(not label for label in normalized_labels):
        raise HTTPException(
            status_code=400,
            detail="Atom labels must be non-empty and match the current atom count.",
        )
    if base_symbols is None:
        symbols = atoms.get_chemical_symbols()
    else:
        if len(base_symbols) != len(atoms):
            raise HTTPException(
                status_code=400,
                detail="Chemical symbols must match the current atom count.",
            )
        try:
            symbols = [base_symbol_for_atom_type(symbol) for symbol in base_symbols]
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chemical symbol in mode transition: {exc}",
            ) from exc

    updated = atoms.copy()
    updated.set_chemical_symbols(symbols)
    set_atom_labels(updated, normalized_labels)
    if atoms.calc:
        updated.calc = copy_calculator(atoms.calc)
    return updated


def normalized_identity_snapshot_for_atoms(atoms, labels, base_symbols=None):
    """Return an exact identity snapshot, preserving unmatched atoms by index."""
    existing_labels = atom_labels(atoms)
    existing_symbols = atoms.get_chemical_symbols()
    incoming_labels = list(labels or [])
    incoming_symbols = list(base_symbols or [])
    warnings = []

    if len(incoming_labels) != len(atoms):
        warnings.append(
            f"Identity snapshot had {len(incoming_labels)} labels for {len(atoms)} atoms; "
            "matched indices were applied and unmatched atoms were preserved."
        )
    if base_symbols is not None and len(incoming_symbols) != len(incoming_labels):
        warnings.append(
            "Chemical-symbol snapshot length did not match the label snapshot; "
            "existing ASE element types were preserved where needed."
        )

    merged_labels = []
    merged_symbols = []
    for index in range(len(atoms)):
        incoming_label = (
            normalize_atom_type_label(incoming_labels[index])
            if index < len(incoming_labels)
            else ""
        )
        fallback_label = normalize_atom_type_label(existing_labels[index])
        label = incoming_label or fallback_label or existing_symbols[index]
        if not incoming_label and index < len(incoming_labels):
            warnings.append(
                f"Empty atom label at index {index} was replaced with the existing label."
            )
        merged_labels.append(label)

        if base_symbols is None or index >= len(incoming_symbols):
            merged_symbols.append(existing_symbols[index])
            continue
        try:
            merged_symbols.append(base_symbol_for_atom_type(incoming_symbols[index]))
        except (KeyError, TypeError, ValueError):
            merged_symbols.append(existing_symbols[index])
            warnings.append(
                f"Invalid chemical symbol at index {index} was replaced with "
                f"{existing_symbols[index]}."
            )

    return merged_labels, merged_symbols, warnings


def merge_identity_snapshot_on_atoms(atoms, labels, base_symbols=None):
    merged_labels, merged_symbols, warnings = normalized_identity_snapshot_for_atoms(
        atoms,
        labels,
        base_symbols,
    )
    updated = atoms.copy()
    updated.set_chemical_symbols(merged_symbols)
    set_atom_labels(updated, merged_labels)
    if atoms.calc:
        updated.calc = copy_calculator(atoms.calc)
    return updated, warnings


def materialize_virtual_trajectory(session: EditorSession) -> None:
    """Convert the fast read-only trajectory into editable ASE frames."""
    source = session.trajectory_source
    if source is None:
        return
    frames = [source.read_atoms(index) for index in range(session.frame_count)]
    current_frame = session.current_frame
    initial_design_settings = (session.config or {}).get("initial_design_settings")
    session.config["viz_only"] = False
    replace_session_frames(
        session,
        frames,
        current_frame=current_frame,
        initial_design_settings=initial_design_settings,
    )
    session.cleanup_temporary_files()


def apply_identity_snapshot_to_session(session: EditorSession, labels, base_symbols=None) -> List[str]:
    """Merge a browser identity snapshot into every frame by stable atom index."""
    warnings = []

    def transform(atoms):
        updated, frame_warnings = merge_identity_snapshot_on_atoms(
            atoms,
            labels,
            base_symbols,
        )
        warnings.extend(frame_warnings)
        return updated

    session.working_atoms = transform(session.working_atoms)
    session.original_atoms = transform(session.original_atoms)
    session.trajectory_frames = [transform(frame) for frame in session.trajectory_frames]
    session.original_frames = [transform(frame) for frame in session.original_frames]
    source_template = getattr(session.trajectory_source, "template_atoms", None)
    if source_template is not None:
        session.trajectory_source.template_atoms = transform(source_template)
    session.invalidate_trajectory_layout()
    session.refresh_trajectory_identity()
    return list(dict.fromkeys(warnings))


def switch_session_mode(
    session: EditorSession,
    *,
    viz_only: bool,
    labels=None,
    base_symbols=None,
    positions=None,
) -> List[str]:
    """Switch runtime capability while preserving the complete working state."""
    if session.is_relaxing:
        raise HTTPException(
            status_code=409,
            detail="Stop the active relaxation before changing View/Edit mode.",
        )

    if not viz_only and session.trajectory_source is not None:
        materialize_virtual_trajectory(session)

    warnings = []
    if labels is not None:
        warnings.extend(
            apply_identity_snapshot_to_session(session, labels, base_symbols)
        )

    if positions is not None:
        coordinates = np.asarray(positions, dtype=float)
        if coordinates.shape == (len(session.working_atoms), 3) and np.all(np.isfinite(coordinates)):
            session.working_atoms.set_positions(coordinates, apply_constraint=False)
            session.sync_current_frame()
        else:
            warnings.append(
                "Displayed coordinates did not match the active frame topology; "
                "the backend frame coordinates were preserved."
            )

    session.config["viz_only"] = bool(viz_only)
    if not viz_only:
        ensure_default_calculator(session.working_atoms)
        ensure_default_calculator(session.original_atoms)
        for frame in session.trajectory_frames:
            ensure_default_calculator(frame)
        for frame in session.original_frames:
            ensure_default_calculator(frame)
    return list(dict.fromkeys(warnings))


def validate_constraint_vector(values, name="Constraint vector"):
    try:
        vector = np.array(values, dtype=float)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{name} must be three numeric values.") from exc
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise HTTPException(status_code=400, detail=f"{name} must be three finite numeric values.")
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise HTTPException(status_code=400, detail=f"{name} cannot be zero.")
    return (vector / norm).tolist()


def update_atom_constraints(atoms, indices, *, fix_atoms=None, directional_kind=None, vector=None):
    selected = sorted({int(i) for i in indices})
    if not selected:
        return atoms.copy()
    if selected[0] < 0 or selected[-1] >= len(atoms):
        raise HTTPException(status_code=400, detail="Constraint indices are out of range.")

    selected_set = set(selected)
    edit_directional = directional_kind is not None
    directional_kind = (directional_kind or "none").lower()
    if edit_directional and directional_kind not in {"none", "fixed_line", "fixed_plane"}:
        raise HTTPException(status_code=400, detail="Directional constraint must be none, fixed_line, or fixed_plane.")
    direction = validate_constraint_vector(vector, "FixedLine direction" if directional_kind == "fixed_line" else "FixedPlane normal") \
        if directional_kind in {"fixed_line", "fixed_plane"} else None

    remapped = []
    for constraint in atoms.constraints or []:
        indices_for_constraint = _constraint_indices(constraint, len(atoms))
        if isinstance(constraint, FixAtoms):
            remaining = [idx for idx in indices_for_constraint if idx not in selected_set] if fix_atoms is not None else indices_for_constraint
            if remaining:
                remapped.append(FixAtoms(indices=remaining))
        elif isinstance(constraint, FixedLine):
            remaining = [idx for idx in indices_for_constraint if idx not in selected_set] if edit_directional else indices_for_constraint
            if remaining:
                remapped.append(FixedLine(remaining, constraint.dir.tolist()))
        elif isinstance(constraint, FixedPlane):
            remaining = [idx for idx in indices_for_constraint if idx not in selected_set] if edit_directional else indices_for_constraint
            if remaining:
                remapped.append(FixedPlane(remaining, constraint.dir.tolist()))
        else:
            remapped.append(constraint)

    if fix_atoms is True:
        remapped.append(FixAtoms(indices=selected))
    if directional_kind == "fixed_line":
        remapped.append(FixedLine(selected, direction))
    elif directional_kind == "fixed_plane":
        remapped.append(FixedPlane(selected, direction))

    updated = atoms.copy()
    updated.set_constraint(remapped)
    if atoms.calc:
        updated.calc = copy_calculator(atoms.calc)
    return updated


def update_atom_constraints_where_present(
    atoms,
    indices,
    *,
    fix_atoms=None,
    directional_kind=None,
    vector=None,
):
    valid = indices_present_in_atoms(atoms, indices)
    if not valid:
        return atoms.copy()
    return update_atom_constraints(
        atoms,
        valid,
        fix_atoms=fix_atoms,
        directional_kind=directional_kind,
        vector=vector,
    )


def configure_repulsion_calculators(
    session: EditorSession,
    *,
    device=None,
    cpu_threads=None,
    cutoff_scale=None,
    k_repulsion=None,
):
    configured = False
    frames = [session.working_atoms, *session.trajectory_frames, *session.original_frames]
    for atoms in frames:
        if is_vase_repulsion_calculator(atoms.calc):
            atoms.calc.configure(
                device=device,
                cpu_threads=cpu_threads,
                cutoff_scale=cutoff_scale,
                k_repulsion=k_repulsion,
            )
            configured = True
    return configured

@app.get("/")
async def get_index():
    with open(os.path.join(static_dir, "index.html"), "r") as f:
        return HTMLResponse(f.read())


@app.get("/workspace")
async def get_workspace_index():
    with open(os.path.join(static_dir, "workspace.html"), "r") as f:
        return HTMLResponse(f.read())


def workspace_session_payload(session: EditorSession) -> Dict[str, Any]:
    return {
        "session_id": session.session_id,
        "title": str((session.config or {}).get("document_name") or "Untitled"),
        "empty": bool((session.config or {}).get("empty_workspace", False)),
        "viz_only": is_viz_only(session),
    }


@app.get("/api/workspace/{workspace_id}")
async def workspace_state(workspace_id: str):
    workspace = get_workspace(workspace_id)
    with workspace.lock:
        documents = [
            workspace_session_payload(sessions[session_id])
            for session_id in workspace.session_ids
            if session_id in sessions
        ]
    return {
        "workspace_id": workspace.workspace_id,
        "host_session_id": workspace.host_session_id,
        "documents": documents,
    }


@app.post("/api/workspace/{workspace_id}/sessions")
async def create_workspace_document(workspace_id: str, payload: Dict[str, Any] | None = None):
    workspace = get_workspace(workspace_id)
    source_session_id = (payload or {}).get("source_session_id")
    session = create_workspace_session(
        workspace,
        source_session_id=str(source_session_id) if source_session_id else None,
    )
    return workspace_session_payload(session)


@app.post("/api/workspace/{workspace_id}/sessions/{session_id}/close")
async def close_workspace_document(workspace_id: str, session_id: str):
    workspace = get_workspace(workspace_id)
    with workspace.lock:
        if len(workspace.session_ids) <= 1:
            raise HTTPException(status_code=409, detail="A workspace must keep at least one document tab.")
        remove_workspace_session(workspace, session_id)
    return {"status": "closed", "session_id": session_id}


@app.post("/api/workspace/{workspace_id}/browser-close/{client_id}")
async def close_workspace_browser(workspace_id: str, client_id: str):
    get_workspace(workspace_id)
    normalized = str(client_id or "").strip()
    if not normalized or len(normalized) > 128:
        raise HTTPException(status_code=400, detail="Invalid workspace browser client identifier.")
    schedule_workspace_autoclose(
        workspace_id,
        closing_client_id=normalized,
    )
    return {"status": "scheduled"}


@app.get("/api/atoms/{session_id}")
async def get_atoms(session_id: str):
    session = get_session(session_id)
    return session_atoms_to_json(session)


@app.get("/api/ai/schema")
async def ai_control_schema():
    return {
        "protocol": AI_PROTOCOL,
        "control_schema": AI_CONTROL_SCHEMA,
        "browser_api": {
            "object": "window.v_aseAI",
            "methods": [
                "ready()",
                "describe()",
                "capabilities()",
                "documents() [workspace page]",
                "activate(sessionId) [workspace page]",
                "newDocument() [workspace page]",
                "apply(command)",
                "render({width, height, options})",
                "export({format, ...options})",
            ],
        },
    }


@app.get("/api/ai/skill")
async def ai_skill():
    path = Path(ai_skill_path())
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


@app.get("/api/ai/state/{session_id}")
async def ai_semantic_state(session_id: str):
    session = get_session(session_id)
    data = session_update_to_json(session)
    labels = [str(value) for value in data.get("labels", data.get("symbols", []))]
    elements = [str(value) for value in data.get("chemical_symbols", [])]
    data["ai"] = {
        "protocol": AI_PROTOCOL,
        "units": {"length": "angstrom", "angle": "degree"},
        "document_name": str((session.config or {}).get("document_name") or "Untitled"),
        "mode": "view" if is_viz_only(session) else "edit",
        "frame": int(session.current_frame),
        "frame_count": int(session.frame_count),
        "label_counts": dict(Counter(labels)),
        "element_counts": dict(Counter(elements)),
        "browser_control": "window.v_aseAI",
    }
    return data


@app.post("/api/mode/{session_id}")
async def update_session_mode(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    requested = payload.get("viz_only")
    if not isinstance(requested, bool):
        raise HTTPException(status_code=400, detail="viz_only must be true or false.")

    sync_session_frame_from_payload(session, payload)
    labels = payload.get("labels")
    base_symbols = payload.get("chemical_symbols")
    positions = payload.get("positions")
    if labels is not None:
        # Normalize before materialization. Different-topology trajectories are
        # merged by stable atom index instead of rejecting the mode transition.
        normalized_identity_snapshot_for_atoms(
            session.working_atoms,
            labels,
            base_symbols,
        )
    if positions is not None:
        coordinates = np.asarray(positions, dtype=float)
        if coordinates.ndim != 2 or coordinates.shape[1:] != (3,) or not np.all(np.isfinite(coordinates)):
            positions = None

    def switch():
        with session.mode_transition_lock:
            warnings = switch_session_mode(
                session,
                viz_only=requested,
                labels=labels,
                base_symbols=base_symbols,
                positions=positions,
            )
            data = session_update_to_json(session)
            if warnings:
                data["mode_transition_warnings"] = warnings
            return data

    return await asyncio.to_thread(switch)


@app.get("/api/trajectory/positions/{session_id}")
async def get_trajectory_positions(session_id: str):
    session = get_session(session_id)
    array = await asyncio.to_thread(trajectory_position_array, session)
    if array is None:
        raise HTTPException(status_code=404, detail="Trajectory position cache is not available for this session.")
    return Response(
        content=array.tobytes(order="C"),
        media_type="application/octet-stream",
        headers={
            "X-V-Ase-Frames": str(array.shape[0]),
            "X-V-Ase-Atoms": str(array.shape[1]),
            "X-V-Ase-Dtype": "float32",
        },
    )


@app.get("/api/frame/positions/{session_id}/{frame_index}")
async def get_frame_positions(session_id: str, frame_index: int):
    session = get_session(session_id)
    if session.trajectory_source is None:
        raise HTTPException(status_code=404, detail="Virtual trajectory positions are not available for this session.")
    try:
        positions = await asyncio.to_thread(
            session.trajectory_source.read_positions,
            frame_index,
        )
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.current_frame = int(frame_index)
    session.working_atoms.set_positions(positions, apply_constraint=False)
    cell = np.asarray(session.trajectory_source.cells[frame_index], dtype=float)
    pbc = np.asarray(session.trajectory_source.pbc[frame_index], dtype=bool)
    session.working_atoms.set_cell(cell)
    session.working_atoms.set_pbc(pbc)
    return Response(
        content=np.asarray(positions, dtype=np.float32).tobytes(order="C"),
        media_type="application/octet-stream",
        headers={
            "X-V-Ase-Frame": str(frame_index),
            "X-V-Ase-Frames": str(session.frame_count),
            "X-V-Ase-Atoms": str(len(session.working_atoms)),
            "X-V-Ase-Dtype": "float32",
            "X-V-Ase-Cell": json.dumps(cell.tolist(), separators=(",", ":")),
            "X-V-Ase-Pbc": json.dumps(pbc.tolist(), separators=(",", ":")),
        },
    )


@app.get("/api/session/active")
async def active_session():
    if len(sessions) != 1:
        return {"session_id": None, "count": len(sessions)}
    return {"session_id": next(iter(sessions.keys())), "count": 1}


def _uploaded_format_hint(filename: str, explicit_format: str | None) -> str | None:
    if explicit_format:
        return explicit_format
    lower_name = filename.lower()
    if lower_name in {"poscar", "contcar"}:
        return "vasp"
    if lower_name == "xdatcar":
        return "vasp-xdatcar"
    if lower_name == "vasprun.xml":
        return "vasp-xml"
    return None


def _selected_frame_indices(index: str | int | slice | None, frame_count: int) -> list[int]:
    parsed = string2index(":") if index is None else string2index(index) if isinstance(index, str) else index
    available = range(frame_count)
    if isinstance(parsed, slice):
        return list(available[parsed])
    if isinstance(parsed, int):
        try:
            return [available[parsed]]
        except IndexError as exc:
            raise ValueError(f"Frame index {parsed} is out of range") from exc
    return list(available)


def _validated_uploaded_filename(filename: str) -> str:
    display_name = Path(filename).name.strip()
    if not display_name or display_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="The selected file has no valid filename.")
    return display_name


def _session_launch_directory(session: EditorSession) -> Path:
    configured = (session.config or {}).get("launch_directory") or os.getcwd()
    try:
        root = Path(configured).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The terminal launch directory is no longer available.",
        ) from exc
    if not root.is_dir():
        raise HTTPException(
            status_code=400,
            detail="The terminal launch location is not a directory.",
        )
    return root


def _resolve_launch_path(
    session: EditorSession,
    relative_path: str,
    *,
    require_file: bool = False,
    require_directory: bool = False,
) -> Path:
    root = _session_launch_directory(session)
    raw_path = str(relative_path or "")
    candidate_path = Path(raw_path)
    if candidate_path.is_absolute() or "\x00" in raw_path:
        raise HTTPException(
            status_code=403,
            detail="Only paths inside the terminal launch directory are allowed.",
        )
    try:
        candidate = (root / candidate_path).resolve(strict=True)
        candidate.relative_to(root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=403,
            detail="The requested path is unavailable or outside the terminal launch directory.",
        ) from exc
    if require_file and not candidate.is_file():
        raise HTTPException(status_code=400, detail="The selected path is not a file.")
    if require_directory and not candidate.is_dir():
        raise HTTPException(status_code=400, detail="The selected path is not a directory.")
    return candidate


def _validate_launch_file_size(source_path: Path) -> None:
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail="The selected file is no longer available.",
        ) from exc
    if size > MAX_UPLOADED_STRUCTURE_BYTES:
        raise HTTPException(status_code=413, detail="The selected structure file is too large.")
    if size == 0:
        raise HTTPException(status_code=400, detail="The selected structure file is empty.")


@app.get("/api/files/{session_id}")
async def browse_launch_directory(session_id: str, directory: str = ""):
    """List files below the directory where v_ase was launched."""
    session = get_session(session_id)
    root = _session_launch_directory(session)
    current = _resolve_launch_path(session, directory, require_directory=True)
    relative_current = current.relative_to(root)
    entries = []
    truncated = False
    try:
        children = sorted(
            current.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.casefold()),
        )
    except OSError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Could not read {current.name or current}: {exc}",
        ) from exc

    for child in children:
        if child.name.startswith("."):
            continue
        try:
            resolved = child.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError):
            continue
        if not (resolved.is_dir() or resolved.is_file()):
            continue
        if len(entries) >= MAX_LAUNCH_DIRECTORY_ENTRIES:
            truncated = True
            break
        relative = child.relative_to(root).as_posix()
        item = {
            "name": child.name,
            "path": relative,
            "kind": "directory" if resolved.is_dir() else "file",
        }
        if resolved.is_file():
            try:
                item["size"] = resolved.stat().st_size
            except OSError:
                item["size"] = 0
        entries.append(item)

    relative_text = "" if relative_current == Path(".") else relative_current.as_posix()
    if not relative_text:
        parent = None
    else:
        parent_path = relative_current.parent
        parent = "" if parent_path == Path(".") else parent_path.as_posix()
    return {
        "root": str(root),
        "directory": relative_text,
        "parent": parent,
        "entries": entries,
        "truncated": truncated,
    }


async def _stream_uploaded_file(request: Request, display_name: str) -> str:
    try:
        content_length = int(request.headers.get("content-length", "0") or 0)
    except ValueError:
        content_length = 0
    if content_length > MAX_UPLOADED_STRUCTURE_BYTES:
        raise HTTPException(status_code=413, detail="The selected structure file is too large.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(display_name).suffix)
    tmp_path = tmp.name
    total = 0
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_UPLOADED_STRUCTURE_BYTES:
                raise HTTPException(status_code=413, detail="The selected structure file is too large.")
            tmp.write(chunk)
        tmp.close()
        if total == 0:
            raise HTTPException(status_code=400, detail="The selected structure file is empty.")
        return tmp_path
    except Exception:
        if not tmp.closed:
            tmp.close()
        _remove_temporary_file(tmp_path)
        raise


async def _replace_session_from_file(
    session: EditorSession,
    source_path: Path,
    display_name: str,
    input_format: str | None,
    index: str,
    *,
    source_is_temporary: bool,
) -> tuple[Dict[str, Any], bool]:
    from .io import read_fast_lammps_dump, read_structure_frames, resolve_input_format

    suffix = Path(display_name).suffix
    format_hint = _uploaded_format_hint(display_name, input_format)
    resolved_format = resolve_input_format(format_hint)
    is_project = suffix.lower() == ".vase" or resolved_format == "vase-project"
    is_lammps_dump = (
        resolved_format == "lammps-dump-text"
        or (format_hint is None and suffix.lower() in {".lammpstrj", ".dump"})
    )
    project = None
    keep_source = False

    if is_project:
        project = await asyncio.to_thread(read_project_archive, source_path)
        session.cleanup_temporary_files()
        replace_session_from_project(session, project)
        loaded_kind = "project"
    elif is_viz_only(session) and is_lammps_dump:
        try:
            fast = await asyncio.to_thread(read_fast_lammps_dump, source_path, index)
            session.cleanup_temporary_files()
            replace_session_frames(
                session,
                [fast.atoms],
                trajectory_source=fast.trajectory,
                current_frame=fast.initial_frame,
            )
            if source_is_temporary:
                source_text = str(source_path)
                session.temporary_files.add(source_text)
                keep_source = True
        except ValueError:
            frames = await asyncio.to_thread(
                read_structure_frames, source_path, index, format_hint
            )
            session.cleanup_temporary_files()
            replace_session_frames(session, frames)
        loaded_kind = "trajectory" if session.frame_count > 1 else "structure"
    else:
        frames = await asyncio.to_thread(
            read_structure_frames, source_path, index, format_hint
        )
        session.cleanup_temporary_files()
        replace_session_frames(session, frames)
        loaded_kind = "trajectory" if session.frame_count > 1 else "structure"

    session.config["empty_workspace"] = False
    session.config["document_name"] = display_name
    data = session_atoms_to_json(session)
    data["loaded_file"] = {
        "filename": display_name,
        "kind": loaded_kind,
        "format": resolved_format or "auto",
    }
    if project is not None:
        data["project"] = {
            "schema": project.manifest.get("schema"),
            "settings": project.settings,
        }
    return data, keep_source


async def _append_session_from_file(
    session: EditorSession,
    source_path: Path,
    display_name: str,
    input_format: str | None,
    index: str,
) -> Dict[str, Any]:
    from .io import read_fast_lammps_dump, read_structure_frames, resolve_input_format

    suffix = Path(display_name).suffix
    was_empty = bool((session.config or {}).get("empty_workspace", False)) and len(session.working_atoms) == 0
    format_hint = _uploaded_format_hint(display_name, input_format)
    resolved_format = resolve_input_format(format_hint)
    is_project = suffix.lower() == ".vase" or resolved_format == "vase-project"
    is_lammps_dump = (
        resolved_format == "lammps-dump-text"
        or (format_hint is None and suffix.lower() in {".lammpstrj", ".dump"})
    )

    if is_project:
        project = await asyncio.to_thread(read_project_archive, source_path)
        selected_indices = _selected_frame_indices(index, len(project.frames))
        frames = [project.frames[frame_index] for frame_index in selected_indices]
        source_kind = "project"
    elif is_lammps_dump:
        try:
            fast = await asyncio.to_thread(read_fast_lammps_dump, source_path, index)
            selected_indices = _selected_frame_indices(index, fast.trajectory.frame_count)
            frames = await asyncio.to_thread(
                lambda: [
                    fast.trajectory.read_atoms(frame_index)
                    for frame_index in selected_indices
                ]
            )
        except ValueError:
            frames = await asyncio.to_thread(
                read_structure_frames, source_path, index, format_hint
            )
        source_kind = "trajectory" if len(frames) > 1 else "structure"
    else:
        frames = await asyncio.to_thread(
            read_structure_frames, source_path, index, format_hint
        )
        source_kind = "trajectory" if len(frames) > 1 else "structure"

    with session.mode_transition_lock:
        appended_count = append_session_frames(session, frames)
        if was_empty:
            session.config["document_name"] = display_name
        session.config["empty_workspace"] = False

    data = session_atoms_to_json(session)
    data["loaded_file"] = {
        "filename": display_name,
        "kind": "append",
        "source_kind": source_kind,
        "format": resolved_format or "auto",
        "appended_frames": appended_count,
        "project_settings_ignored": bool(is_project),
    }
    return data


@app.post("/api/file/load/{session_id}")
async def load_structure_file(
    session_id: str,
    request: Request,
    filename: str,
    input_format: str | None = None,
    index: str = ":",
):
    """Stream a browser-selected structure, trajectory, or project into a session."""
    session = get_session(session_id)
    display_name = _validated_uploaded_filename(filename)
    tmp_path = await _stream_uploaded_file(request, display_name)
    keep_temporary_file = False
    try:
        data, keep_temporary_file = await _replace_session_from_file(
            session,
            Path(tmp_path),
            display_name,
            input_format,
            index,
            source_is_temporary=True,
        )
        return data
    except HTTPException:
        raise
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not load {display_name}: {exc}") from exc
    finally:
        if not keep_temporary_file:
            _remove_temporary_file(tmp_path)


@app.post("/api/file/load-path/{session_id}")
async def load_structure_path(session_id: str, payload: Dict[str, Any]):
    """Load a file selected from the terminal launch directory."""
    session = get_session(session_id)
    source_path = _resolve_launch_path(
        session,
        str(payload.get("path") or ""),
        require_file=True,
    )
    _validate_launch_file_size(source_path)
    display_name = _validated_uploaded_filename(source_path.name)
    input_format = payload.get("input_format") or None
    index = str(payload.get("index") or ":")
    try:
        data, _ = await _replace_session_from_file(
            session,
            source_path,
            display_name,
            str(input_format) if input_format else None,
            index,
            source_is_temporary=False,
        )
        return data
    except HTTPException:
        raise
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not load {display_name}: {exc}") from exc


@app.post("/api/file/append/{session_id}")
async def append_structure_file(
    session_id: str,
    request: Request,
    filename: str,
    input_format: str | None = None,
    index: str = ":",
):
    """Append uploaded structures as movie frames without replacing visual settings."""
    session = get_session(session_id)
    display_name = _validated_uploaded_filename(filename)
    tmp_path = await _stream_uploaded_file(request, display_name)
    try:
        return await _append_session_from_file(
            session,
            Path(tmp_path),
            display_name,
            input_format,
            index,
        )
    except HTTPException:
        raise
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not append {display_name}: {exc}") from exc
    finally:
        _remove_temporary_file(tmp_path)


@app.post("/api/file/append-path/{session_id}")
async def append_structure_path(session_id: str, payload: Dict[str, Any]):
    """Append a file selected from the terminal launch directory."""
    session = get_session(session_id)
    source_path = _resolve_launch_path(
        session,
        str(payload.get("path") or ""),
        require_file=True,
    )
    _validate_launch_file_size(source_path)
    display_name = _validated_uploaded_filename(source_path.name)
    input_format = payload.get("input_format") or None
    index = str(payload.get("index") or ":")
    try:
        return await _append_session_from_file(
            session,
            source_path,
            display_name,
            str(input_format) if input_format else None,
            index,
        )
    except HTTPException:
        raise
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not append {display_name}: {exc}") from exc


@app.post("/api/constrain/{session_id}")
async def constrain_positions(session_id: str, payload: Dict[str, Any]):
    """AUTHORITATIVE: Backend correction of proposed positions."""
    session = get_session(session_id)
    sync_session_frame_from_payload(session, payload)
    positions = np.array(payload["positions"])
    
    # Validation step: Apply constraints on a copy
    temp_atoms = session.working_atoms.copy()
    temp_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    
    return {"positions": temp_atoms.get_positions().tolist()}


@app.post("/api/commensurate/{session_id}")
async def commensurate_rotation_candidates(session_id: str, payload: Dict[str, Any]):
    """Return periodic 2D cell-boundary matches for an axis-locked rotate."""
    session = get_session(session_id)
    sync_session_frame_from_payload(session, payload)
    atoms = session.working_atoms
    return await asyncio.to_thread(
        find_commensurate_angles,
        atoms.cell.array,
        atoms.pbc,
        payload.get("axis", "Z"),
        max_index=payload.get("max_index", 32),
        strain_tolerance=payload.get("strain_tolerance", 0.01),
        chemical_symbols=atoms.get_chemical_symbols(),
    )

@app.post("/api/apply/{session_id}")
async def apply_positions(session_id: str, payload: Dict[str, Any]):
    """COMMIT: Backend state update with authoritative constraints."""
    session = get_session(session_id)
    require_editable(session, "Atom coordinate editing")
    sync_session_frame_from_payload(session, payload)
    session.push_history()
    
    positions = np.array(payload["positions"])
    # Enforcement: Final coordinates MUST respect ASE constraints
    session.working_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    session.sync_current_frame()
    if session.is_relaxing:
        from .relax import request_relax_restart
        request_relax_restart(session)
    
    return session_update_to_json(session)


@app.post("/api/reset/{session_id}")
async def reset(session_id: str, payload: Dict[str, Any] | None = None):
    session = get_session(session_id)
    require_editable(session, "Full reset")
    sync_session_frame_from_payload(session, payload)
    session.push_history(include_trajectory=True)
    session.reset_all_frames()
    return session_update_to_json(session)


@app.post("/api/reset-coordinates/{session_id}")
async def reset_coordinates(session_id: str, payload: Dict[str, Any] | None = None):
    session = get_session(session_id)
    require_editable(session, "Coordinate reset")
    sync_session_frame_from_payload(session, payload)
    session.push_history(include_trajectory=True)
    session.reset_all_frames()
    return session_update_to_json(session)


@app.post("/api/settings/save/{session_id}")
async def save_visual_settings(session_id: str, payload: Dict[str, Any]):
    get_session(session_id)
    try:
        settings = normalize_visual_settings(payload.get("settings", payload))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = {
        "schema": SETTINGS_SCHEMA,
        "settings": settings,
    }
    blob = json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
    return Response(
        content=blob,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="v_ase_visual_settings.json"'},
    )


@app.post("/api/settings/load/{session_id}")
async def load_visual_settings(session_id: str, request: Request):
    get_session(session_id)
    raw = await request.body()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Visual settings file is too large.")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        class SettingsUnpickler(pickle.Unpickler):
            def find_class(self, module, name):
                raise pickle.UnpicklingError("global objects are not allowed in settings files")

        try:
            data = SettingsUnpickler(io.BytesIO(raw)).load()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid v_ase visual settings file: {exc}") from exc
    if isinstance(data, dict) and "settings" in data:
        settings = data["settings"]
    if isinstance(data, dict):
        settings = settings if "settings" in data else data
        try:
            settings = normalize_visual_settings(settings)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"schema": SETTINGS_SCHEMA, "settings": settings}
    raise HTTPException(status_code=400, detail="Visual settings file must contain a JSON object.")


@app.post("/api/project/save/{session_id}")
async def save_project(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    sync_session_frame_from_payload(session, payload)
    viz_only = is_viz_only(session)
    if not viz_only:
        set_current_payload_positions(session, payload)
    settings = payload.get("settings") or {}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".vase")
    tmp.close()
    try:
        write_project_archive(
            tmp.name,
            session,
            settings,
            current_positions=payload.get("positions") if viz_only else None,
        )
    except (TypeError, ValueError, OSError) as exc:
        _remove_temporary_file(tmp.name)
        raise HTTPException(status_code=400, detail=f"Could not save .vase project: {exc}") from exc
    return FileResponse(
        tmp.name,
        filename="v_ase_project.vase",
        media_type=PROJECT_MIME,
        background=BackgroundTask(_remove_temporary_file, tmp.name),
    )


@app.post("/api/project/load/{session_id}")
async def load_project(session_id: str, request: Request):
    session = get_session(session_id)
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="The .vase project is empty.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".vase")
    try:
        tmp.write(raw)
        tmp.close()
        project = read_project_archive(tmp.name)
        session.cleanup_temporary_files()
        replace_session_from_project(session, project)
        session.config["empty_workspace"] = False
    except (TypeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not load .vase project: {exc}") from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    data = session_atoms_to_json(session)
    data["project"] = {
        "schema": project.manifest.get("schema"),
        "settings": project.settings,
    }
    return data


@app.post("/api/wrap/{session_id}")
async def wrap(session_id: str, payload: Dict[str, Any] | None = None):
    session = get_session(session_id)
    require_editable(session, "Wrap atoms")
    sync_session_frame_from_payload(session, payload)
    session.push_history(include_trajectory=True)
    set_current_payload_positions(session, payload or {})

    def wrap_frame(atoms):
        wrapped = atoms.copy()
        wrapped.wrap()
        if atoms.calc:
            wrapped.calc = copy_calculator(atoms.calc)
        return wrapped

    apply_all_frames(session, wrap_frame)
    return session_update_to_json(session)


@app.post("/api/undo/{session_id}")
async def undo(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Undo")
    atoms = session.undo()
    if atoms is not None:
        session.sync_current_frame()
    return session_update_to_json(session)


@app.post("/api/redo/{session_id}")
async def redo(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Redo")
    atoms = session.redo()
    if atoms is not None:
        session.sync_current_frame()
    return session_update_to_json(session)


@app.post("/api/add/{session_id}")
async def add_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Adding atoms")
    sync_session_frame_from_payload(session, payload)
    symbols = payload.get("symbols")
    positions = payload.get("positions")
    base_symbols = payload.get("base_symbols")
    if symbols is None and "symbol" in payload:
        symbols = [payload["symbol"]]
        positions = [payload["position"]]
        base_symbols = [payload.get("base_symbol")]
    if not symbols or not positions or len(symbols) != len(positions):
        raise HTTPException(status_code=400, detail="symbols and positions must have the same non-zero length")
    if base_symbols is None:
        base_symbols = [None] * len(symbols)
    if len(base_symbols) != len(symbols):
        raise HTTPException(status_code=400, detail="base_symbols must match symbols when provided")

    session.push_history()
    labels = atom_labels(session.working_atoms)
    for symbol, position, base_symbol in zip(symbols, positions, base_symbols):
        label = normalize_atom_type_label(symbol)
        if not label:
            raise HTTPException(status_code=400, detail="Atom type label cannot be empty.")
        labels.append(label)
        atom_symbol = (
            base_symbol_for_atom_type(base_symbol)
            if base_symbol
            else base_symbol_for_atom_type(label)
        )
        session.working_atoms.append(Atom(atom_symbol, position=position))
    set_atom_labels(session.working_atoms, labels)
    session.invalidate_trajectory_layout()
    session.sync_current_frame()
    session.refresh_trajectory_identity()
    return session_update_to_json(session)


@app.post("/api/delete/{session_id}")
async def delete_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Deleting atoms")
    sync_session_frame_from_payload(session, payload)
    indices = payload.get("indices", [])
    if not indices:
        return session_update_to_json(session)

    session.push_history()
    session.working_atoms = delete_indices_from_atoms(session.working_atoms, indices)
    session.invalidate_trajectory_layout()
    session.sync_current_frame()
    session.refresh_trajectory_identity()
    return session_update_to_json(session)


@app.post("/api/atom-identity/{session_id}")
@app.post("/api/atom-types/{session_id}", include_in_schema=False)
async def update_atom_identity(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Atom identity editing")
    try:
        indices = sorted({int(index) for index in payload.get("indices", [])})
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Atom indices must be integers.") from exc
    label = payload.get("label", "")
    if not indices:
        return session_update_to_json(session)

    sync_session_frame_from_payload(session, payload)
    session.push_history(include_trajectory=True, include_original=True)
    set_current_payload_positions(session, payload)
    base_symbol = payload.get("base_symbol")
    apply_all_frames(
        session,
        lambda atoms: update_atom_identity_where_present(
            atoms,
            indices,
            label,
            base_symbol,
        ),
    )
    session.original_frames = [
        update_atom_identity_where_present(frame, indices, label, base_symbol)
        for frame in session.original_frames
    ]
    session.original_atoms = update_atom_identity_where_present(
        session.original_atoms,
        indices,
        label,
        base_symbol,
    )
    session.invalidate_trajectory_layout()
    session.refresh_trajectory_identity()
    return session_update_to_json(session)


# Compatibility name for direct imports used before 0.0.78.
update_atom_types = update_atom_identity


@app.post("/api/constraints/{session_id}")
async def update_constraints(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Constraint editing")
    indices = payload.get("indices", [])
    if not indices:
        return session_update_to_json(session)

    sync_session_frame_from_payload(session, payload)
    session.push_history(include_trajectory=True)
    set_current_payload_positions(session, payload)
    fix_atoms = payload.get("fix_atoms", None)
    directional_kind = payload.get("directional_kind", None)
    vector = payload.get("vector", None)
    apply_all_frames(
        session,
        lambda atoms: update_atom_constraints_where_present(
            atoms,
            indices,
            fix_atoms=fix_atoms,
            directional_kind=directional_kind,
            vector=vector,
        )
    )
    return session_update_to_json(session)


@app.post("/api/calculator/{session_id}")
async def update_calculator(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Calculator device settings")
    sync_session_frame_from_payload(session, payload)
    if not is_vase_repulsion_calculator(session.working_atoms.calc):
        raise HTTPException(status_code=400, detail="Calculator device settings are only available for the default repulsion calculator.")
    configure_repulsion_calculators(
        session,
        device=payload.get("device"),
        cpu_threads=payload.get("cpu_threads"),
        cutoff_scale=payload.get("cutoff_scale"),
        k_repulsion=payload.get("k_repulsion"),
    )
    session.sync_current_frame()
    return session_update_to_json(session)


@app.post("/api/frame/{session_id}")
async def set_frame(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    frame_index = int(payload.get("index", 0))
    try:
        session.set_frame(frame_index)
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if session.trajectory_source is not None:
        return {
            "positions": session.working_atoms.get_positions().astype(float).tolist(),
            "cell": np.asarray(session.working_atoms.cell.array, dtype=float).tolist(),
            "pbc": np.asarray(session.working_atoms.pbc, dtype=bool).tolist(),
            "metadata": {
                "positions_only": True,
                "frame_count": session.frame_count,
                "current_frame": session.current_frame,
                "virtual_trajectory": True,
            },
        }
    return session_atoms_to_json(session, include_inline_trajectory=False)


_PARTICLE_ID_ARRAY_NAMES = ("lammps_id", "atom_id", "particle_id", "ids", "id")


def _analysis_frame_atoms(session: EditorSession, frame_index: int):
    if frame_index < 0 or frame_index >= session.frame_count:
        raise HTTPException(
            status_code=400,
            detail=f"Frame index {frame_index} is out of range for {session.frame_count} frames.",
        )
    if session.trajectory_source is not None:
        return session.trajectory_source.read_atoms(frame_index)
    if session.trajectory_frames:
        return session.trajectory_frames[frame_index].copy()
    if frame_index == 0:
        return session.working_atoms.copy()
    raise HTTPException(status_code=400, detail="The requested trajectory frame is unavailable.")


def _unique_particle_ids(atoms):
    for name in _PARTICLE_ID_ARRAY_NAMES:
        values = atoms.arrays.get(name)
        if values is None or len(values) != len(atoms):
            continue
        normalized = []
        for value in np.asarray(values).tolist():
            if isinstance(value, list):
                value = tuple(value)
            normalized.append(value)
        try:
            if len(set(normalized)) == len(normalized):
                return name, normalized
        except TypeError:
            continue
    return None, None


def calculate_displacements(session: EditorSession, payload: Dict[str, Any]):
    frame_count = session.frame_count
    if frame_count <= 1:
        return {
            "status": "unavailable",
            "message": "Displacement analysis requires at least two trajectory frames.",
            "frame_count": frame_count,
        }

    current_index = int(payload.get("frame_index", session.current_frame))
    reference_mode = str(payload.get("reference_mode", "previous")).strip().lower()
    if reference_mode == "previous":
        if current_index <= 0:
            return {
                "status": "unavailable",
                "message": "The first frame has no previous-frame displacement.",
                "frame_count": frame_count,
                "current_frame": current_index,
            }
        reference_index = current_index - 1
    elif reference_mode == "frame":
        reference_index = int(payload.get("reference_frame", 0))
    else:
        raise HTTPException(
            status_code=400,
            detail="reference_mode must be 'previous' or 'frame'.",
        )

    current = _analysis_frame_atoms(session, current_index)
    reference = _analysis_frame_atoms(session, reference_index)
    current_positions = np.asarray(current.get_positions(), dtype=float)
    supplied_positions = payload.get("positions")
    if supplied_positions is not None:
        supplied = np.asarray(supplied_positions, dtype=float)
        if supplied.shape == current_positions.shape and np.all(np.isfinite(supplied)):
            current_positions = supplied

    current_id_name, current_ids = _unique_particle_ids(current)
    reference_id_name, reference_ids = _unique_particle_ids(reference)
    mapping = "index"
    warnings = []
    if (
        current_ids is not None
        and reference_ids is not None
        and current_id_name == reference_id_name
    ):
        mapping = f"particle-id:{current_id_name}"
        reference_lookup = {
            particle_id: index
            for index, particle_id in enumerate(reference_ids)
        }
        current_indices = [
            index
            for index, particle_id in enumerate(current_ids)
            if particle_id in reference_lookup
        ]
        reference_indices = [
            reference_lookup[current_ids[index]]
            for index in current_indices
        ]
        unmatched_current = len(current) - len(current_indices)
        unmatched_reference = len(reference) - len(current_indices)
        if unmatched_current or unmatched_reference:
            warnings.append(
                f"Matched {len(current_indices)} particles by {current_id_name}; "
                f"{unmatched_current} current and {unmatched_reference} reference particles were unmatched."
            )
    elif len(current) == len(reference):
        current_indices = list(range(len(current)))
        reference_indices = list(range(len(reference)))
        unmatched_current = 0
        unmatched_reference = 0
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Trajectory frames have different atom counts and no common unique "
                "particle-ID array. Displacement mapping is not physically defined."
            ),
        )

    if not current_indices:
        raise HTTPException(
            status_code=400,
            detail="No particles could be mapped between the selected frames.",
        )

    current_mapped = current_positions[np.asarray(current_indices, dtype=int)]
    reference_mapped = np.asarray(reference.get_positions(), dtype=float)[
        np.asarray(reference_indices, dtype=int)
    ]
    vectors = current_mapped - reference_mapped
    use_mic = bool(payload.get("mic", True))
    mic_applied = False
    if use_mic and np.asarray(current.pbc, dtype=bool).any():
        cell = np.asarray(current.cell.array, dtype=float)
        if cell.shape == (3, 3) and np.isfinite(cell).all() and abs(np.linalg.det(cell)) > 1e-12:
            vectors, _ = find_mic(vectors, current.cell, current.pbc)
            vectors = np.asarray(vectors, dtype=float)
            mic_applied = True
        else:
            warnings.append("MIC was requested but the current frame has no invertible unit cell.")

    # Vectors describe the physical current-reference displacement, while the
    # glyph anchor is the atom's current position. The renderer may add a
    # visual-only translation or displayed supercell offset to both endpoints.
    starts = current_mapped
    magnitudes = np.linalg.norm(vectors, axis=1)
    return {
        "status": "ok",
        "frame_count": frame_count,
        "current_frame": current_index,
        "reference_frame": reference_index,
        "reference_mode": reference_mode,
        "mapping": mapping,
        "mic_requested": use_mic,
        "mic_applied": mic_applied,
        "indices": [int(index) for index in current_indices],
        "reference_indices": [int(index) for index in reference_indices],
        "starts": starts.tolist(),
        "vectors": vectors.tolist(),
        "magnitudes": magnitudes.tolist(),
        "matched": len(current_indices),
        "unmatched_current": unmatched_current,
        "unmatched_reference": unmatched_reference,
        "stats": {
            "mean": float(np.mean(magnitudes)),
            "rms": float(np.sqrt(np.mean(magnitudes ** 2))),
            "max": float(np.max(magnitudes)),
        },
        "warnings": warnings,
    }


@app.post("/api/analysis/displacement/{session_id}")
async def displacement_analysis(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    def calculate():
        with session.mode_transition_lock:
            return calculate_displacements(session, payload)

    return await asyncio.to_thread(calculate)

@app.post("/api/done/{session_id}")
async def done(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    sync_session_frame_from_payload(session, payload)
    if not is_viz_only(session):
        positions = np.array(payload["positions"])
        session.working_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
        session.sync_current_frame()
    session.result_atoms = session.working_atoms.copy()
    if session.working_atoms.calc:
        session.result_atoms.calc = copy_calculator(session.working_atoms.calc)
        
    session.done_event.set()
    return {"status": "ok"}


@app.post("/api/supercell/apply/{session_id}")
async def apply_supercell(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Setting a supercell as the editable cell")
    sync_session_frame_from_payload(session, payload)
    reps = [int(v) for v in payload.get("reps", [1, 1, 1])]
    validate_supercell_request(session, reps)
    session.push_history(include_trajectory=True)
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: repeat_atoms_as_supercell(atoms, reps))
    session.invalidate_trajectory_layout()
    return session_update_to_json(session)


@app.post("/api/supercell/matrix/{session_id}")
async def apply_supercell_matrix(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Applying a cell transformation")
    sync_session_frame_from_payload(session, payload)
    matrix = payload.get("matrix")
    P = validate_supercell_matrix_request(session, matrix)
    session.push_history(include_trajectory=True)
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: make_supercell_atoms(atoms, P))
    session.invalidate_trajectory_layout()
    return session_update_to_json(session)


@app.post("/api/translate/{session_id}")
async def apply_translation(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Atom translation")
    sync_session_frame_from_payload(session, payload)
    vector = payload.get("vector", [0, 0, 0])
    coordinate_mode = payload.get("coordinate_mode", "cartesian")
    # Validate before creating a history entry.
    translate_atoms(session.working_atoms, vector, coordinate_mode)
    session.push_history(include_trajectory=True)
    set_current_payload_positions(session, payload)
    apply_all_frames(
        session,
        lambda atoms: translate_atoms(atoms, vector, coordinate_mode),
    )
    return session_update_to_json(session)


@app.post("/api/cancel/{session_id}")
async def cancel(session_id: str):
    session = get_session(session_id)
    session.cancelled = True
    session.done_event.set()
    return {"status": "ok"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await ws_manager.connect(websocket, session_id)
    cancel_session_autoclose(session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        schedule_session_autoclose(session_id)


@app.websocket("/ws/workspace/{workspace_id}")
async def workspace_websocket_endpoint(websocket: WebSocket, workspace_id: str):
    get_workspace(workspace_id)
    client_id = str(websocket.query_params.get("client_id") or "").strip()
    connection_id = (
        f"workspace:{workspace_id}:{client_id}"
        if client_id
        else f"workspace:{workspace_id}"
    )
    cancel_workspace_autoclose(
        workspace_id,
        connected_client_id=client_id or None,
    )
    try:
        await ws_manager.connect(websocket, connection_id)
    except Exception:
        schedule_workspace_autoclose(workspace_id)
        raise
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)
        schedule_workspace_autoclose(workspace_id)

# Modular endpoints for scientific features
if FASTAPI_AVAILABLE:
    from .relax import start_relaxation, stop_relaxation
    from .export import (
        OptionalExportDependencyError,
        VideoExportError,
        export_3dm_response,
        export_blender_response,
        export_obj_response,
        export_pickle_response,
        export_poscar_response,
        encode_export_image,
        transcode_video_file,
    )

    @app.post("/api/export/poscar/{session_id}")
    async def api_export_poscar(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        return export_poscar_response(session, payload)

    @app.post("/api/export/pickle/{session_id}")
    async def api_export_pickle(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        return export_pickle_response(session, payload)

    @app.post("/api/export/blender/{session_id}")
    async def api_export_blender(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        return export_blender_response(session, payload)

    @app.post("/api/export/3dm/{session_id}")
    async def api_export_3dm(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        try:
            return export_3dm_response(session, payload)
        except OptionalExportDependencyError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/export/obj/{session_id}")
    async def api_export_obj(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        try:
            return export_obj_response(session, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/export/image/{session_id}")
    async def api_export_image(
        session_id: str,
        request: Request,
        format: str = "png",
    ):
        """Encode a rendered PNG without changing its dimensions or RGBA pixels."""
        get_session(session_id)
        declared_size = request.headers.get("content-length")
        if declared_size:
            try:
                if int(declared_size) > MAX_UPLOADED_IMAGE_BYTES:
                    raise HTTPException(status_code=413, detail="Rendered PNG exceeds the 512 MB optimization limit.")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid PNG content length.")

        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > MAX_UPLOADED_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Rendered PNG exceeds the 512 MB optimization limit.")
        if not payload:
            raise HTTPException(status_code=400, detail="Rendered PNG is empty.")
        try:
            encoded, media_type = await asyncio.to_thread(
                encode_export_image,
                bytes(payload),
                format,
            )
        except OptionalExportDependencyError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=encoded,
            media_type=media_type,
            headers={
                "X-V-Ase-Source-Bytes": str(len(payload)),
                "X-V-Ase-Encoded-Bytes": str(len(encoded)),
                "X-V-Ase-Image-Format": str(format).lower(),
            },
        )

    @app.post("/api/export/video/{session_id}")
    async def api_export_video(
        session_id: str,
        request: Request,
        format: str = "mov",
        fps: int = 12,
        frames: int | None = None,
        export_id: str = "",
    ):
        get_session(session_id)
        if fps < 1 or fps > 60:
            raise HTTPException(status_code=400, detail="Video FPS must be between 1 and 60.")
        if frames is not None and (frames < 1 or frames > 10_000_000):
            raise HTTPException(status_code=400, detail="Invalid expected video frame count.")
        declared_size = request.headers.get("content-length")
        if declared_size:
            try:
                if int(declared_size) > MAX_UPLOADED_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Recorded video exceeds the 2 GB export limit.")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid video content length.")

        source = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
        source_path = source.name
        total = 0
        normalized_export_id = str(export_id or "").strip()[:128]

        def report_progress(ratio: float, eta_seconds: float | None, frame: int) -> None:
            if not normalized_export_id:
                return
            ws_manager.broadcast_sync(
                {
                    "type": "video_export_progress",
                    "export_id": normalized_export_id,
                    "phase": "encoding",
                    "progress": max(0.0, min(1.0, float(ratio))),
                    "eta_seconds": (
                        None
                        if eta_seconds is None
                        else max(0.0, float(eta_seconds))
                    ),
                    "frame": max(0, int(frame)),
                    "frame_count": frames,
                },
                session_id,
            )

        try:
            async for chunk in request.stream():
                total += len(chunk)
                if total > MAX_UPLOADED_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Recorded video exceeds the 2 GB export limit.")
                source.write(chunk)
            source.close()
            if total == 0:
                raise HTTPException(status_code=400, detail="Recorded video is empty.")
            report_progress(0.0, None, 0)
            target_path, filename, media_type = await asyncio.to_thread(
                transcode_video_file,
                source_path,
                format,
                fps,
                frames,
                report_progress if normalized_export_id else None,
            )
        except HTTPException:
            source.close()
            raise
        except OptionalExportDependencyError as exc:
            source.close()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            source.close()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except VideoExportError as exc:
            source.close()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            source.close()
            _remove_temporary_file(source_path)

        return FileResponse(
            target_path,
            filename=filename,
            media_type=media_type,
            background=BackgroundTask(_remove_temporary_file, target_path),
        )

    @app.post("/api/relax/start/{session_id}")
    async def api_relax_start(session_id: str, payload: Dict[str, Any], bt: BackgroundTasks):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        return await start_relaxation(session, payload, bt)

    @app.post("/api/relax/stop/{session_id}")
    async def api_relax_stop(session_id: str):
        session = get_session(session_id)
        return await stop_relaxation(session)
