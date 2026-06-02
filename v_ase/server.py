import os
import threading
import asyncio
import pickle
from typing import Dict, Any, List
from .session import EditorSession, get_session, sessions
from .serialization import atoms_to_json
from .websocket_manager import ws_manager
from .io import atom_type_labels, base_symbol_for_atom_type, set_atom_type_labels
import numpy as np
from ase import Atom
from ase.build import make_supercell
from ase.build.supercells import lattice_points_in_supercell
from ase.constraints import FixAtoms, FixCartesian, FixedLine, FixedPlane, FixScaled, Hookean

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FastAPI = None
    WebSocket = Any
    WebSocketDisconnect = Exception
    BackgroundTasks = Any
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


app = FastAPI() if FASTAPI_AVAILABLE else _MissingFastAPIApp()

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


def session_atoms_to_json(session: EditorSession):
    data = atoms_to_json(session.working_atoms)
    data["metadata"]["config"] = session.config
    data["metadata"]["frame_count"] = session.frame_count
    data["metadata"]["current_frame"] = session.current_frame
    return data


def payload_apply_constraint(payload: Dict[str, Any] | None) -> bool:
    if not payload:
        return True
    return bool(payload.get("apply_constraint", True))


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
        repeated.calc = atoms.calc
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
        transformed.calc = atoms.calc
    return transformed


def set_current_payload_positions(session: EditorSession, payload: Dict[str, Any]):
    if payload and "positions" in payload:
        session.working_atoms.set_positions(
            np.array(payload["positions"]),
            apply_constraint=payload_apply_constraint(payload),
        )
        session.sync_current_frame()


def refresh_working_frame(session: EditorSession):
    session.working_atoms = session.trajectory_frames[session.current_frame].copy()
    if session.trajectory_frames[session.current_frame].calc:
        session.working_atoms.calc = session.trajectory_frames[session.current_frame].calc


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
        new_atoms.calc = atoms.calc
    return new_atoms


def update_atom_type_labels(atoms, indices, label):
    indices = sorted({int(i) for i in indices})
    if not indices:
        return atoms.copy()
    if indices[0] < 0 or indices[-1] >= len(atoms):
        raise HTTPException(status_code=400, detail="Atom type indices are out of range.")
    normalized = str(label).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Atom type label cannot be empty.")

    updated = atoms.copy()
    symbols = updated.get_chemical_symbols()
    type_labels = atom_type_labels(updated)
    base_symbol = base_symbol_for_atom_type(normalized)
    for idx in indices:
        symbols[idx] = base_symbol
        type_labels[idx] = normalized
    updated.set_chemical_symbols(symbols)
    set_atom_type_labels(updated, type_labels)
    if atoms.calc:
        updated.calc = atoms.calc
    return updated

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(ws_manager.broadcaster_task())

@app.get("/")
async def get_index():
    with open(os.path.join(static_dir, "index.html"), "r") as f:
        return HTMLResponse(f.read())

@app.get("/api/atoms/{session_id}")
async def get_atoms(session_id: str):
    session = get_session(session_id)
    return session_atoms_to_json(session)


@app.get("/api/session/active")
async def active_session():
    if len(sessions) != 1:
        return {"session_id": None, "count": len(sessions)}
    return {"session_id": next(iter(sessions.keys())), "count": 1}

@app.post("/api/constrain/{session_id}")
async def constrain_positions(session_id: str, payload: Dict[str, Any]):
    """AUTHORITATIVE: Backend correction of proposed positions."""
    session = get_session(session_id)
    positions = np.array(payload["positions"])
    
    # Validation step: Apply constraints on a copy
    temp_atoms = session.working_atoms.copy()
    temp_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    
    return {"positions": temp_atoms.get_positions().tolist()}

@app.post("/api/apply/{session_id}")
async def apply_positions(session_id: str, payload: Dict[str, Any]):
    """COMMIT: Backend state update with authoritative constraints."""
    session = get_session(session_id)
    session.push_history()
    
    positions = np.array(payload["positions"])
    # Enforcement: Final coordinates MUST respect ASE constraints
    session.working_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    session.sync_current_frame()
    
    return session_atoms_to_json(session)


@app.post("/api/reset/{session_id}")
async def reset(session_id: str):
    session = get_session(session_id)
    session.push_history()
    session.reset_all_frames()
    session.selection.clear()
    return session_atoms_to_json(session)


@app.post("/api/reset-coordinates/{session_id}")
async def reset_coordinates(session_id: str):
    session = get_session(session_id)
    session.push_history()
    session.reset_all_frames()
    session.selection.clear()
    return session_atoms_to_json(session)


@app.post("/api/settings/save/{session_id}")
async def save_visual_settings(session_id: str, payload: Dict[str, Any]):
    get_session(session_id)
    settings = payload.get("settings", payload)
    data = {
        "schema": "v_ase.visual_settings.v1",
        "settings": settings,
    }
    blob = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="v_ase_visual_settings.pkl"'},
    )


@app.post("/api/settings/load/{session_id}")
async def load_visual_settings(session_id: str, request: Request):
    get_session(session_id)
    raw = await request.body()
    try:
        data = pickle.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid v_ase settings pickle: {exc}") from exc
    if isinstance(data, dict) and "settings" in data:
        return {
            "schema": data.get("schema", "v_ase.visual_settings.v1"),
            "settings": data["settings"],
        }
    if isinstance(data, dict):
        return {"schema": "v_ase.visual_settings.v1", "settings": data}
    raise HTTPException(status_code=400, detail="Settings pickle must contain a dictionary.")


@app.post("/api/wrap/{session_id}")
async def wrap(session_id: str, payload: Dict[str, Any] | None = None):
    session = get_session(session_id)
    session.push_history()
    set_current_payload_positions(session, payload or {})

    def wrap_frame(atoms):
        wrapped = atoms.copy()
        wrapped.wrap()
        if atoms.calc:
            wrapped.calc = atoms.calc
        return wrapped

    apply_all_frames(session, wrap_frame)
    return session_atoms_to_json(session)


@app.post("/api/undo/{session_id}")
async def undo(session_id: str):
    session = get_session(session_id)
    atoms = session.undo()
    if atoms is not None:
        session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/redo/{session_id}")
async def redo(session_id: str):
    session = get_session(session_id)
    atoms = session.redo()
    if atoms is not None:
        session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/add/{session_id}")
async def add_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    symbols = payload.get("symbols")
    positions = payload.get("positions")
    if symbols is None and "symbol" in payload:
        symbols = [payload["symbol"]]
        positions = [payload["position"]]
    if not symbols or not positions or len(symbols) != len(positions):
        raise HTTPException(status_code=400, detail="symbols and positions must have the same non-zero length")

    session.push_history()
    type_labels = atom_type_labels(session.working_atoms)
    for symbol, position in zip(symbols, positions):
        type_labels.append(str(symbol))
        session.working_atoms.append(Atom(base_symbol_for_atom_type(symbol), position=position))
    set_atom_type_labels(session.working_atoms, type_labels)
    session.sync_current_frame()
    return session_atoms_to_json(session)


@app.post("/api/delete/{session_id}")
async def delete_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
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
    indices = payload.get("indices", [])
    label = payload.get("label", "")
    if not indices:
        return session_atoms_to_json(session)

    session.push_history()
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: update_atom_type_labels(atoms, indices, label))
    return session_atoms_to_json(session)


@app.post("/api/frame/{session_id}")
async def set_frame(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    frame_index = int(payload.get("index", 0))
    try:
        session.set_frame(frame_index)
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session_atoms_to_json(session)

@app.post("/api/done/{session_id}")
async def done(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    positions = np.array(payload["positions"])
    
    # Final enforcement
    session.working_atoms.set_positions(positions, apply_constraint=payload_apply_constraint(payload))
    session.sync_current_frame()
    session.result_atoms = session.working_atoms.copy()
    if session.working_atoms.calc:
        session.result_atoms.calc = session.working_atoms.calc
        
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
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# Modular endpoints for scientific features
if FASTAPI_AVAILABLE:
    from .relax import start_relaxation, stop_relaxation
    from .export import export_blender_response, export_poscar_response, export_pickle_response

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

    @app.post("/api/relax/start/{session_id}")
    async def api_relax_start(session_id: str, payload: Dict[str, Any], bt: BackgroundTasks):
        session = get_session(session_id)
        return await start_relaxation(session, payload, bt)

    @app.post("/api/relax/stop/{session_id}")
    async def api_relax_stop(session_id: str):
        session = get_session(session_id)
        return await stop_relaxation(session)
