import os
import threading
import asyncio
from contextlib import asynccontextmanager, suppress
import pickle
import io
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from .session import EditorSession, get_session, replace_session_frames, sessions
from .serialization import atoms_to_json
from .websocket_manager import ws_manager
from .io import atom_type_labels, base_symbol_for_atom_type, normalize_atom_type_label, set_atom_type_labels
from .repulsion import copy_calculator, is_vase_repulsion_calculator, repulsion_metadata
from .commensurate import find_commensurate_angles
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
MAX_UPLOADED_VIDEO_BYTES = 2 * 1024 * 1024 * 1024


def trajectory_cacheable(session: EditorSession) -> bool:
    if session.trajectory_source is not None:
        return False
    if session.frame_count <= 1:
        return False
    natoms = len(session.working_atoms)
    base_labels = atom_type_labels(session.working_atoms)
    base_cell = np.asarray(session.working_atoms.cell.array)
    base_pbc = np.asarray(session.working_atoms.pbc, dtype=bool)
    for frame in session.trajectory_frames:
        if len(frame) != natoms:
            return False
        if atom_type_labels(frame) != base_labels:
            return False
        if not np.array_equal(np.asarray(frame.pbc, dtype=bool), base_pbc):
            return False
        if not np.allclose(np.asarray(frame.cell.array), base_cell):
            return False
    return True


def trajectory_position_cache(session: EditorSession):
    natoms = len(session.working_atoms)
    if session.frame_count * natoms * 3 > MAX_INLINE_TRAJECTORY_CACHE_VALUES:
        return None
    if not trajectory_cacheable(session):
        return None
    positions = []
    for frame in session.trajectory_frames:
        positions.append(frame.get_positions().tolist())
    return positions


def trajectory_position_array(session: EditorSession):
    natoms = len(session.working_atoms)
    value_count = session.frame_count * natoms * 3
    if value_count > MAX_BINARY_TRAJECTORY_CACHE_VALUES:
        return None
    if not trajectory_cacheable(session):
        return None
    return np.asarray([frame.get_positions() for frame in session.trajectory_frames], dtype=np.float32)


def session_atoms_to_json(session: EditorSession, include_inline_trajectory: bool = True):
    data = atoms_to_json(session.working_atoms)
    data["metadata"]["config"] = session.config
    data["metadata"]["frame_count"] = session.frame_count
    data["metadata"]["current_frame"] = session.current_frame
    data["metadata"]["virtual_trajectory"] = session.trajectory_source is not None
    data["metadata"]["calculator_details"] = repulsion_metadata(session.working_atoms.calc)
    if is_vase_repulsion_calculator(session.working_atoms.calc):
        data["metadata"]["calculator"] = "Repulsion"
        data["metadata"]["has_calculator"] = True
    trajectory_positions = trajectory_position_cache(session) if include_inline_trajectory else None
    data["metadata"]["trajectory_positions_cached"] = trajectory_positions is not None
    if trajectory_positions is not None:
        data["trajectory_positions"] = trajectory_positions
    data["metadata"]["trajectory_positions_binary"] = (
        trajectory_positions is None
        and session.frame_count > 1
        and session.frame_count * len(session.working_atoms) * 3 <= MAX_BINARY_TRAJECTORY_CACHE_VALUES
        and trajectory_cacheable(session)
    )
    return data


def payload_apply_constraint(payload: Dict[str, Any] | None) -> bool:
    if not payload:
        return True
    return bool(payload.get("apply_constraint", True))


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


def require_editable(session: EditorSession, action: str = "This operation"):
    if is_viz_only(session):
        raise HTTPException(status_code=403, detail=f"{action} is disabled in the default visualization mode. Start v_ase with --interactive to edit atoms.")


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


def set_current_payload_positions(session: EditorSession, payload: Dict[str, Any]):
    if payload and "positions" in payload:
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


def update_atom_type_labels(atoms, indices, label, base_symbol=None):
    indices = sorted({int(i) for i in indices})
    if not indices:
        return atoms.copy()
    if indices[0] < 0 or indices[-1] >= len(atoms):
        raise HTTPException(status_code=400, detail="Atom type indices are out of range.")
    normalized = normalize_atom_type_label(label)
    if not normalized:
        raise HTTPException(status_code=400, detail="Atom type label cannot be empty.")

    updated = atoms.copy()
    symbols = updated.get_chemical_symbols()
    type_labels = atom_type_labels(updated)
    outside_labels = {atom_type for idx, atom_type in enumerate(type_labels) if idx not in indices}
    if normalized in outside_labels:
        suffix = 2
        candidate = f"{normalized}_{suffix}"
        while candidate in outside_labels:
            suffix += 1
            candidate = f"{normalized}_{suffix}"
        normalized = candidate
    base_symbol = base_symbol_for_atom_type(base_symbol) if base_symbol else inferred_base_symbol_for_label(normalized)
    for idx in indices:
        if base_symbol:
            symbols[idx] = base_symbol
        type_labels[idx] = normalized
    updated.set_chemical_symbols(symbols)
    set_atom_type_labels(updated, type_labels)
    if atoms.calc:
        updated.calc = copy_calculator(atoms.calc)
    return updated


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


def configure_repulsion_calculators(session: EditorSession, *, device=None, cpu_threads=None):
    configured = False
    frames = [session.working_atoms, *session.trajectory_frames, *session.original_frames]
    for atoms in frames:
        if is_vase_repulsion_calculator(atoms.calc):
            atoms.calc.configure(device=device, cpu_threads=cpu_threads)
            configured = True
    return configured

@app.get("/")
async def get_index():
    with open(os.path.join(static_dir, "index.html"), "r") as f:
        return HTMLResponse(f.read())

@app.get("/api/atoms/{session_id}")
async def get_atoms(session_id: str):
    session = get_session(session_id)
    return session_atoms_to_json(session)


@app.get("/api/trajectory/positions/{session_id}")
async def get_trajectory_positions(session_id: str):
    session = get_session(session_id)
    array = trajectory_position_array(session)
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
        positions = session.trajectory_source.read_positions(frame_index)
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
    display_name = Path(filename).name.strip()
    if not display_name or display_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="The selected file has no valid filename.")
    try:
        content_length = int(request.headers.get("content-length", "0") or 0)
    except ValueError:
        content_length = 0
    if content_length > MAX_UPLOADED_STRUCTURE_BYTES:
        raise HTTPException(status_code=413, detail="The selected structure file is too large.")

    suffix = Path(display_name).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    total = 0
    keep_temporary_file = False
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

        from .cli import _read_frames, resolve_input_format
        from .io import read_fast_lammps_dump

        format_hint = _uploaded_format_hint(display_name, input_format)
        resolved_format = resolve_input_format(format_hint)
        is_project = suffix.lower() == ".vase" or resolved_format == "vase-project"
        is_lammps_dump = (
            resolved_format == "lammps-dump-text"
            or (format_hint is None and suffix.lower() in {".lammpstrj", ".dump"})
        )

        if is_project:
            project = await asyncio.to_thread(read_project_archive, tmp_path)
            session.cleanup_temporary_files()
            replace_session_from_project(session, project)
            loaded_kind = "project"
        elif is_viz_only(session) and is_lammps_dump:
            try:
                fast = await asyncio.to_thread(read_fast_lammps_dump, Path(tmp_path), index)
                session.cleanup_temporary_files()
                replace_session_frames(
                    session,
                    [fast.atoms],
                    trajectory_source=fast.trajectory,
                    current_frame=fast.initial_frame,
                )
                session.temporary_files.add(tmp_path)
                keep_temporary_file = True
            except ValueError:
                frames = await asyncio.to_thread(_read_frames, Path(tmp_path), index, format_hint)
                session.cleanup_temporary_files()
                replace_session_frames(session, frames)
            loaded_kind = "trajectory" if session.frame_count > 1 else "structure"
        else:
            frames = await asyncio.to_thread(_read_frames, Path(tmp_path), index, format_hint)
            session.cleanup_temporary_files()
            replace_session_frames(session, frames)
            loaded_kind = "trajectory" if session.frame_count > 1 else "structure"

        session.config["empty_workspace"] = False
        data = session_atoms_to_json(session)
        data["loaded_file"] = {
            "filename": display_name,
            "kind": loaded_kind,
            "format": resolved_format or "auto",
        }
        if is_project:
            data["project"] = {
                "schema": project.manifest.get("schema"),
                "settings": project.settings,
            }
        return data
    except HTTPException:
        raise
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not load {display_name}: {exc}") from exc
    finally:
        if not tmp.closed:
            tmp.close()
        if not keep_temporary_file:
            _remove_temporary_file(tmp_path)

@app.post("/api/constrain/{session_id}")
async def constrain_positions(session_id: str, payload: Dict[str, Any]):
    """AUTHORITATIVE: Backend correction of proposed positions."""
    session = get_session(session_id)
    positions = np.array(payload["positions"])
    
    # Validation step: Apply constraints on a copy
    temp_atoms = session.working_atoms.copy()
    temp_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    
    return {"positions": temp_atoms.get_positions().tolist()}


@app.post("/api/commensurate/{session_id}")
async def commensurate_rotation_candidates(session_id: str, payload: Dict[str, Any]):
    """Return periodic 2D cell-boundary matches for an axis-locked rotate."""
    session = get_session(session_id)
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
    session.push_history()
    
    positions = np.array(payload["positions"])
    # Enforcement: Final coordinates MUST respect ASE constraints
    session.working_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    session.sync_current_frame()
    if session.is_relaxing:
        from .relax import request_relax_restart
        request_relax_restart(session)
    
    return session_atoms_to_json(session)


@app.post("/api/reset/{session_id}")
async def reset(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Full reset")
    session.push_history()
    session.reset_all_frames()
    session.selection.clear()
    return session_atoms_to_json(session)


@app.post("/api/reset-coordinates/{session_id}")
async def reset_coordinates(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Coordinate reset")
    session.push_history()
    session.reset_all_frames()
    session.selection.clear()
    return session_atoms_to_json(session)


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
    session.push_history()
    set_current_payload_positions(session, payload or {})

    def wrap_frame(atoms):
        wrapped = atoms.copy()
        wrapped.wrap()
        if atoms.calc:
            wrapped.calc = copy_calculator(atoms.calc)
        return wrapped

    apply_all_frames(session, wrap_frame)
    return session_atoms_to_json(session)


@app.post("/api/undo/{session_id}")
async def undo(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Undo")
    atoms = session.undo()
    if atoms is not None:
        session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/redo/{session_id}")
async def redo(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Redo")
    atoms = session.redo()
    if atoms is not None:
        session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/add/{session_id}")
async def add_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Adding atoms")
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
    type_labels = atom_type_labels(session.working_atoms)
    for symbol, position, base_symbol in zip(symbols, positions, base_symbols):
        label = normalize_atom_type_label(symbol)
        if not label:
            raise HTTPException(status_code=400, detail="Atom type label cannot be empty.")
        type_labels.append(label)
        atom_symbol = base_symbol_for_atom_type(base_symbol) if base_symbol else base_symbol_for_atom_type(label)
        session.working_atoms.append(Atom(atom_symbol, position=position))
    set_atom_type_labels(session.working_atoms, type_labels)
    session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/delete/{session_id}")
async def delete_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Deleting atoms")
    indices = payload.get("indices", [])
    if not indices:
        return session_atoms_to_json(session)

    session.push_history()
    session.working_atoms = delete_indices_from_atoms(session.working_atoms, indices)
    session.selection.clear()
    session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/atom-types/{session_id}")
async def update_atom_types(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Atom type editing")
    indices = payload.get("indices", [])
    label = payload.get("label", "")
    if not indices:
        return session_atoms_to_json(session)

    session.push_history()
    set_current_payload_positions(session, payload)
    base_symbol = payload.get("base_symbol")
    apply_all_frames(session, lambda atoms: update_atom_type_labels(atoms, indices, label, base_symbol))
    return session_atoms_to_json(session)


@app.post("/api/constraints/{session_id}")
async def update_constraints(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Constraint editing")
    indices = payload.get("indices", [])
    if not indices:
        return session_atoms_to_json(session)

    session.push_history()
    set_current_payload_positions(session, payload)
    fix_atoms = payload.get("fix_atoms", None)
    directional_kind = payload.get("directional_kind", None)
    vector = payload.get("vector", None)
    apply_all_frames(
        session,
        lambda atoms: update_atom_constraints(
            atoms,
            indices,
            fix_atoms=fix_atoms,
            directional_kind=directional_kind,
            vector=vector,
        )
    )
    return session_atoms_to_json(session)


@app.post("/api/calculator/{session_id}")
async def update_calculator(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Calculator device settings")
    if not is_vase_repulsion_calculator(session.working_atoms.calc):
        raise HTTPException(status_code=400, detail="Calculator device settings are only available for the default repulsion calculator.")
    configure_repulsion_calculators(
        session,
        device=payload.get("device"),
        cpu_threads=payload.get("cpu_threads"),
    )
    session.sync_current_frame()
    return session_atoms_to_json(session)


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

@app.post("/api/done/{session_id}")
async def done(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
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
    reps = [int(v) for v in payload.get("reps", [1, 1, 1])]
    validate_supercell_request(session, reps)
    session.push_history()
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: repeat_atoms_as_supercell(atoms, reps))
    return session_atoms_to_json(session)


@app.post("/api/supercell/matrix/{session_id}")
async def apply_supercell_matrix(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    matrix = payload.get("matrix")
    P = validate_supercell_matrix_request(session, matrix)
    session.push_history()
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: make_supercell_atoms(atoms, P))
    return session_atoms_to_json(session)

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
        transcode_video_file,
    )

    @app.post("/api/export/poscar/{session_id}")
    async def api_export_poscar(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        return export_poscar_response(session, payload)

    @app.post("/api/export/pickle/{session_id}")
    async def api_export_pickle(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        return export_pickle_response(session, payload)

    @app.post("/api/export/blender/{session_id}")
    async def api_export_blender(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        return export_blender_response(session, payload)

    @app.post("/api/export/3dm/{session_id}")
    async def api_export_3dm(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        try:
            return export_3dm_response(session, payload)
        except OptionalExportDependencyError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/export/obj/{session_id}")
    async def api_export_obj(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        try:
            return export_obj_response(session, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/export/video/{session_id}")
    async def api_export_video(session_id: str, request: Request, format: str = "mov"):
        get_session(session_id)
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
        try:
            async for chunk in request.stream():
                total += len(chunk)
                if total > MAX_UPLOADED_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Recorded video exceeds the 2 GB export limit.")
                source.write(chunk)
            source.close()
            if total == 0:
                raise HTTPException(status_code=400, detail="Recorded video is empty.")
            target_path, filename, media_type = await asyncio.to_thread(
                transcode_video_file,
                source_path,
                format,
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
        return await start_relaxation(session, payload, bt)

    @app.post("/api/relax/stop/{session_id}")
    async def api_relax_stop(session_id: str):
        session = get_session(session_id)
        return await stop_relaxation(session)
