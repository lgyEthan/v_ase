import os
import threading
import asyncio
import uuid
from contextlib import asynccontextmanager, suppress
import pickle
import io
import html
import json
import logging
import tempfile
from collections import Counter
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Dict, Any, List
from ase.io.formats import UnknownFileTypeError
from .session import (
    append_session_frames,
    copy_atoms_with_calc,
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
from .add_atoms import (
    apply_atom_addition_positions,
    atom_addition_domain_preview,
    atom_addition_summary,
    cancel_atom_addition,
    default_pair_cutoffs,
    finish_atom_addition,
    molecule_catalog,
    molecule_entry_elements,
    normalize_molecule_entries,
    start_atom_addition,
    start_atom_addition_relaxation,
    stop_atom_addition_relaxation,
    update_atom_addition_region,
)
from .commensurate import (
    COMMENSURATE_REFERENCES,
    MAX_LATTICE_MATCH_AREA_RATIO,
    commensurate_csv,
    commensurate_supercell_geometry,
    find_commensurate_angles,
    find_lattice_matches,
    host_guest_supercell_geometry,
    row_rotation_matrix,
)
from .analysis import calculate_rdf, rdf_csv
from .atom_scalars import (
    atom_force_vectors,
    atom_property_snapshot,
    atom_scalar_catalog,
    atom_scalar_values,
)
from .builders import (
    BulkBuildError,
    build_bulk_atoms,
    bulk_builder_catalog,
    bulk_preview_payload,
)
from .colormaps import colormap_catalog, colormap_lut
from .registry import calculate_registry_map, registry_map_csv
from .registry_relax import (
    cancel_registry_relaxation_mode,
    finish_registry_relaxation_mode,
    registry_relaxation_summary,
    run_registry_relaxation,
    set_registry_translation,
    start_registry_relaxation_mode,
    stop_registry_relaxation,
)
from .ai import AI_PROTOCOL, COLLABORATION_PROTOCOL, ai_skill_path
from .project import (
    PROJECT_MIME,
    SETTINGS_SCHEMA,
    normalize_visual_settings,
    read_project_archive,
    read_project_html,
    replace_session_from_project,
    write_project_archive,
)
from .preferences import (
    PREFERENCES_SCHEMA,
    clear_visual_defaults,
    load_visual_defaults,
    save_visual_defaults,
)
from .volumetric import (
    GRID_GEOMETRY_ATOL,
    GRID_GEOMETRY_RTOL,
    combine_volumetric_datasets,
    dataset_by_id,
    generate_isosurface,
    generate_volumetric_plane,
    normalize_volumetric_precision,
    read_volumetric_file,
    resolve_volumetric_format,
    volumetric_structure,
)
import numpy as np
from ase import Atom, Atoms
from ase.build import make_supercell
from ase.build.supercells import lattice_points_in_supercell
from ase.calculators.singlepoint import SinglePointCalculator
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

    def delete(self, *args, **kwargs):
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
        for waiter in list(_ai_command_waiters.values()):
            if not waiter.done():
                waiter.cancel()
        _ai_command_waiters.clear()
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
_AI_COMMAND_METHODS = frozenset({
    "ready",
    "schema",
    "describe",
    "capabilities",
    "documents",
    "activate",
    "newDocument",
    "apply",
    "render",
    "export",
})
_AI_COMMAND_DEFAULT_TIMEOUT_SECONDS = 300.0
_AI_COMMAND_MAX_TIMEOUT_SECONDS = 1800.0
_AI_COMMAND_CONNECT_TIMEOUT_SECONDS = 15.0
_ai_command_waiters: Dict[str, asyncio.Future] = {}
LOGGER = logging.getLogger(__name__)


def _remove_temporary_file(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _root_exception_message(exc: BaseException) -> str:
    """Return the final useful exception line without exposing a traceback."""

    root = exc
    visited: set[int] = set()
    while id(root) not in visited:
        visited.add(id(root))
        nested = root.__cause__ or root.__context__
        if nested is None:
            break
        root = nested
    lines = [line.strip() for line in str(root).splitlines() if line.strip()]
    return lines[-1] if lines else root.__class__.__name__


def _exception_chain_contains(exc: BaseException, kind: type[BaseException]) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        if isinstance(current, kind):
            return True
        visited.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _file_read_error_detail(action: str, display_name: str, exc: BaseException) -> str:
    message = _root_exception_message(exc)
    if _exception_chain_contains(exc, UnknownFileTypeError):
        message = (
            "Could not determine the file format. Choose a Reader explicitly "
            "or use a recognized filename extension."
        )
    elif _exception_chain_contains(exc, FileNotFoundError):
        message = "The selected file no longer exists or is not accessible at that path."
    elif _exception_chain_contains(exc, PermissionError):
        message = "Permission was denied while reading the selected file."
    elif _exception_chain_contains(exc, IsADirectoryError):
        message = "The selected path is a directory, not a structure file."
    elif _exception_chain_contains(exc, UnicodeDecodeError):
        message = (
            "The file is not valid text for the selected Reader. "
            "Choose the matching binary Reader or another file."
        )
    elif _exception_chain_contains(exc, EOFError):
        message = "The file ended unexpectedly and may be empty, incomplete, or damaged."
    return f"Could not {action} {display_name}: {message}"


def _file_read_http_error(action: str, display_name: str, exc: BaseException) -> HTTPException:
    LOGGER.exception("Could not %s %s", action, display_name, exc_info=exc)
    return HTTPException(
        status_code=400,
        detail=_file_read_error_detail(action, display_name, exc),
    )

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


def v_ase_license_text() -> str:
    """Return the installed AGPL text in source and wheel installations."""
    source_license = Path(__file__).resolve().parent.parent / "LICENSE"
    if source_license.is_file():
        return source_license.read_text(encoding="utf-8")

    try:
        package = distribution("v_ase-gui")
    except PackageNotFoundError:
        package = None
    if package is not None:
        for record in package.files or ():
            record_path = Path(str(record))
            if record_path.name == "LICENSE" and "licenses" in record_path.parts:
                installed_license = Path(package.locate_file(record))
                if installed_license.is_file():
                    return installed_license.read_text(encoding="utf-8")

    raise FileNotFoundError("The v_ase license text is missing from this installation.")


MAX_INLINE_TRAJECTORY_CACHE_VALUES = 750_000
MAX_BINARY_TRAJECTORY_CACHE_VALUES = 30_000_000
MAX_ATOM_SCALAR_CACHE_VALUES = 20_000_000
MAX_FORCE_VECTOR_CACHE_VALUES = 6_000_000
MAX_UPLOADED_STRUCTURE_BYTES = 64 * 1024 * 1024 * 1024
MAX_UPLOADED_IMAGE_BYTES = 512 * 1024 * 1024
MAX_UPLOADED_VIDEO_BYTES = 2 * 1024 * 1024 * 1024
MAX_LAUNCH_DIRECTORY_ENTRIES = 5000
COLLABORATION_EVENT_CATEGORIES = frozenset({
    "analysis",
    "camera",
    "constraints",
    "display",
    "document",
    "export",
    "frame",
    "mode",
    "selection",
    "state",
    "structure",
    "trajectory",
})


@app.get("/api/vendor/plotly.js", include_in_schema=False)
async def plotly_javascript_bundle():
    """Serve Plotly from the installed Python package without a CDN request."""
    try:
        import plotly
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Interactive RDF plots require the plotly package.",
        ) from exc
    bundle = Path(plotly.__file__).resolve().parent / "package_data" / "plotly.min.js"
    if not bundle.is_file():
        raise HTTPException(status_code=503, detail="The installed Plotly bundle is incomplete.")
    return FileResponse(
        bundle,
        media_type="text/javascript",
        headers={"Cache-Control": "public, max-age=86400"},
    )


_AI_REPULSION_CALCULATOR_SCHEMA = {
    "type": "object",
    "description": (
        "Optional settings for v_ase's built-in repulsion calculator. Pair "
        "distances are independent from visual bonds. In absolute mode each "
        "pair_cutoffs value is its onset distance in Angstrom. In scaled mode "
        "the value is multiplied by cutoff_scale. Zero disables a pair. Pair "
        "energy and force are exactly zero at and beyond the onset distance."
    ),
    "additionalProperties": False,
    "properties": {
        "device": {"enum": ["cpu", "cuda"]},
        "cpu_threads": {"type": "integer", "minimum": 1},
        "cutoff_mode": {"enum": ["absolute", "scaled"]},
        "cutoff_basis": {"enum": ["covalent", "vdw"]},
        "cutoff_distance": {
            "type": "number", "minimum": 0.01, "maximum": 100,
        },
        "cutoff_scale": {
            "type": "number", "minimum": 0.05, "maximum": 3,
        },
        "pair_cutoffs": {
            "type": "object",
            "description": (
                "Independent repulsion reference distances in Angstrom, keyed "
                "by an unordered label pair such as Cu_surface|O_ads. Zero "
                "disables the pair even if a visual bond is shown."
            ),
            "additionalProperties": {
                "type": "number", "minimum": 0, "maximum": 100,
            },
        },
        "k_repulsion": {
            "type": "number", "minimum": 0, "maximum": 1000,
        },
        "k_boundary": {
            "type": "number", "exclusiveMinimum": 0, "maximum": 1000,
        },
    },
}


AI_CONTROL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": (
        "https://github.com/lgyEthan/v_ase/blob/main/v_ase/skills/"
        "visualizing-atomic-structures-with-v-ase/SKILL.md"
    ),
    "title": "v_ase live semantic control",
    "description": (
        "Commands accepted by the HTTP JSON bridge and optional "
        "window.v_aseAI.apply() mirror. They control the same live document "
        "that a human sees in the v_ase GUI."
    ),
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "expectedRevision": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Optional optimistic-concurrency guard. Reject the command "
                "when the live collaboration revision has changed."
            ),
        },
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
                "atomDisplayMode, atomRadiusScale, labelRadii, labelColors, "
                "labelOpacities, labelMaterials, bondThickness, "
                "bondMaterial, bondOpacity, pairwiseBondStyles, supercell, "
                "translation, translationMode, lightingMode, "
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
                "translate-all, set-unit-cell, build-bulk, set-supercell, make-supercell, add-atom, "
                "scatter-atoms, scatter-molecules, update-add-atoms-region, "
                "scale-add-atoms-regions, "
                "relax-added-atoms, stop-added-atoms, "
                "finish-add-atoms, cancel-add-atoms, "
                "delete-selection, set-identity, set-constraints, "
                "move-selection, rotate-selection, scale-selection, rotate-to-commensurate, "
                "load-commensurate-guest, remove-commensurate-guest, "
                "calculate-commensurate, apply-commensurate-cell, "
                "dismiss-commensurate-cell, calculate-registry-map, "
                "start-registry-relaxation, run-registry-relaxation, "
                "set-registry-translation, "
                "stop-registry-relaxation, finish-registry-relaxation, "
                "cancel-registry-relaxation, undo, redo, "
                "reset-coordinates, start-relaxation, stop-relaxation, "
                "clear-relaxation-trajectory, exit-relaxation-mode, and "
                "refresh-displacements, load-volumetric, show-volumetric, "
                "add-volumetric-plane, update-volumetric-planes, "
                "remove-volumetric-planes, combine-volumetric, "
                "remove-volumetric, calculate-rdf, "
                "set-interface-theme, set-personal-visual-default, and "
                "restore-app-visual-defaults, and set-atom-colorscale."
            ),
            "oneOf": [
                {
                    "type": "string",
                    "enum": [
                        "wrap", "undo", "redo", "reset-coordinates",
                        "stop-relaxation", "refresh-displacements",
                        "apply-commensurate-cell", "dismiss-commensurate-cell",
                        "remove-commensurate-guest", "calculate-rdf",
                        "set-personal-visual-default",
                        "stop-added-atoms", "finish-add-atoms", "cancel-add-atoms",
                        "update-add-atoms-region",
                        "stop-registry-relaxation", "finish-registry-relaxation",
                        "cancel-registry-relaxation",
                        "clear-relaxation-trajectory", "exit-relaxation-mode",
                    ],
                },
                {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "enum": [
                                "wrap", "translate-all", "set-unit-cell", "build-bulk", "set-supercell",
                                "make-supercell", "add-atom", "scatter-atoms",
                                "scatter-molecules",
                                "update-add-atoms-region", "scale-add-atoms-regions",
                                "relax-added-atoms", "stop-added-atoms",
                                "finish-add-atoms", "cancel-add-atoms",
                                "delete-selection", "set-identity",
                                "set-constraints", "move-selection",
                                "rotate-selection", "scale-selection", "rotate-to-commensurate",
                                "load-commensurate-guest",
                                "remove-commensurate-guest",
                                "calculate-commensurate",
                                "apply-commensurate-cell",
                                "dismiss-commensurate-cell",
                                "calculate-registry-map",
                                "start-registry-relaxation",
                                "run-registry-relaxation",
                                "set-registry-translation",
                                "stop-registry-relaxation",
                                "finish-registry-relaxation",
                                "cancel-registry-relaxation",
                                "undo", "redo",
                                "reset-coordinates", "start-relaxation",
                                "stop-relaxation", "clear-relaxation-trajectory",
                                "exit-relaxation-mode",
                                "refresh-displacements",
                                "load-volumetric", "show-volumetric",
                                "add-volumetric-plane",
                                "update-volumetric-planes",
                                "remove-volumetric-planes",
                                "combine-volumetric", "remove-volumetric",
                                "calculate-rdf", "set-interface-theme",
                                "set-personal-visual-default",
                                "restore-app-visual-defaults",
                                "set-atom-colorscale",
                            ],
                        },
                    },
                    "allOf": [
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "build-bulk"}},
                            },
                            "then": {
                                "required": ["formula"],
                                "properties": {
                                    "formula": {"type": "string", "minLength": 1},
                                    "crystalStructure": {
                                        "enum": [
                                            "sc", "fcc", "bcc", "bct", "hcp",
                                            "rhombohedral", "orthorhombic", "diamond",
                                            "zincblende", "rocksalt", "cesiumchloride",
                                            "fluorite", "wurtzite",
                                        ],
                                    },
                                    "cellMode": {
                                        "enum": ["primitive", "orthorhombic", "cubic"],
                                    },
                                    "a": {"type": "number", "exclusiveMinimum": 0},
                                    "b": {"type": "number", "exclusiveMinimum": 0},
                                    "c": {"type": "number", "exclusiveMinimum": 0},
                                    "alpha": {
                                        "type": "number",
                                        "exclusiveMinimum": 0,
                                        "exclusiveMaximum": 180,
                                    },
                                    "covera": {"type": "number", "exclusiveMinimum": 0},
                                    "u": {"type": "number", "minimum": 0, "maximum": 1},
                                    "basis": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                            "minItems": 3,
                                            "maxItems": 3,
                                        },
                                    },
                                    "confirmReplace": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "set-unit-cell"}},
                            },
                            "then": {
                                "required": ["cell"],
                                "properties": {
                                    "cell": {
                                        "type": "array",
                                        "minItems": 3,
                                        "maxItems": 3,
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                            "minItems": 3,
                                            "maxItems": 3,
                                        },
                                    },
                                    "pbc": {
                                        "type": "array",
                                        "items": {"type": "boolean"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scatter-atoms"}},
                            },
                            "then": {
                                "anyOf": [
                                    {"required": ["entries"]},
                                    {"required": ["element", "count"]},
                                ],
                                "properties": {
                                    "entries": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "object",
                                            "required": ["element", "count"],
                                            "properties": {
                                                "element": {"type": "string", "minLength": 1},
                                                "label": {"type": "string", "minLength": 1},
                                                "count": {
                                                    "type": "integer", "minimum": 1, "maximum": 100000
                                                },
                                            },
                                        },
                                    },
                                    "element": {"type": "string", "minLength": 1},
                                    "label": {"type": "string", "minLength": 1},
                                    "count": {"type": "integer", "minimum": 1, "maximum": 100000},
                                    "regionMode": {"enum": ["cell", "box", "regions"]},
                                    "regions": {
                                        "type": "array",
                                        "maxItems": 32,
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "role", "bounds"],
                                            "properties": {
                                                "id": {"type": "string", "minLength": 1},
                                                "name": {"type": "string", "minLength": 1},
                                                "role": {"enum": ["allow", "reject"]},
                                                "bounds": {
                                                    "type": "array",
                                                    "items": {"type": "number"},
                                                    "minItems": 6,
                                                    "maxItems": 6,
                                                },
                                            },
                                        },
                                    },
                                    "bounds": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 6,
                                        "maxItems": 6,
                                    },
                                    "regionRole": {
                                        "enum": ["allow", "reject", "allowed", "prohibited"]
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                    "placementMode": {"enum": ["random", "homogeneous", "regular"]},
                                    "regularSpacing": {"type": "number", "exclusiveMinimum": 0},
                                    "coordinateBasis": {"enum": ["cartesian", "fractional"]},
                                    "pbcAware": {"type": "boolean"},
                                    "seed": {"type": ["integer", "null"], "minimum": 0},
                                    "freezeExisting": {"type": "boolean"},
                                    "cutoffBasis": {"enum": ["covalent", "vdw", "pairwise"]},
                                    "cutoffScale": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 3
                                    },
                                    "pairCutoffs": {"type": "object"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scatter-molecules"}},
                            },
                            "then": {
                                "anyOf": [
                                    {"required": ["molecules"]},
                                    {"required": ["molecule", "count"]},
                                ],
                                "properties": {
                                    "molecules": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "object",
                                            "required": ["name", "count"],
                                            "properties": {
                                                "name": {"type": "string", "minLength": 1},
                                                "label": {"type": "string", "minLength": 1},
                                                "count": {
                                                    "type": "integer", "minimum": 1, "maximum": 20000
                                                },
                                            },
                                        },
                                    },
                                    "molecule": {"type": "string", "minLength": 1},
                                    "label": {"type": "string", "minLength": 1},
                                    "count": {"type": "integer", "minimum": 1, "maximum": 20000},
                                    "regionMode": {"enum": ["cell", "box", "regions"]},
                                    "regions": {
                                        "type": "array",
                                        "maxItems": 32,
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "role", "bounds"],
                                            "properties": {
                                                "id": {"type": "string", "minLength": 1},
                                                "name": {"type": "string", "minLength": 1},
                                                "role": {"enum": ["allow", "reject"]},
                                                "bounds": {
                                                    "type": "array",
                                                    "items": {"type": "number"},
                                                    "minItems": 6,
                                                    "maxItems": 6,
                                                },
                                            },
                                        },
                                    },
                                    "bounds": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 6,
                                        "maxItems": 6,
                                    },
                                    "regionRole": {
                                        "enum": ["allow", "reject", "allowed", "prohibited"]
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                    "placementMode": {"enum": ["random", "homogeneous", "regular"]},
                                    "regularSpacing": {"type": "number", "exclusiveMinimum": 0},
                                    "coordinateBasis": {"enum": ["cartesian", "fractional"]},
                                    "pbcAware": {"type": "boolean"},
                                    "randomOrientation": {"type": "boolean"},
                                    "rigidMolecules": {"type": "boolean"},
                                    "quantityMode": {"enum": ["count", "density"]},
                                    "targetDensityGcm3": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 100
                                    },
                                    "seed": {"type": ["integer", "null"], "minimum": 0},
                                    "freezeExisting": {"type": "boolean"},
                                    "cutoffBasis": {"enum": ["covalent", "vdw", "pairwise"]},
                                    "cutoffScale": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 3
                                    },
                                    "pairCutoffs": {"type": "object"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "update-add-atoms-region"}},
                            },
                            "then": {
                                "properties": {
                                    "regions": {
                                        "type": "array",
                                        "maxItems": 32,
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "role", "bounds"],
                                            "properties": {
                                                "id": {"type": "string", "minLength": 1},
                                                "name": {"type": "string", "minLength": 1},
                                                "role": {"enum": ["allow", "reject"]},
                                                "bounds": {
                                                    "type": "array",
                                                    "items": {"type": "number"},
                                                    "minItems": 6,
                                                    "maxItems": 6,
                                                },
                                            },
                                        },
                                    },
                                    "regionId": {"type": "string", "minLength": 1},
                                    "regionName": {"type": "string", "minLength": 1},
                                    "bounds": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 6,
                                        "maxItems": 6,
                                    },
                                    "regionRole": {
                                        "enum": ["allow", "reject", "allowed", "prohibited"]
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scale-add-atoms-regions"}},
                            },
                            "then": {
                                "required": ["regionIds", "factor"],
                                "properties": {
                                    "regionIds": {
                                        "type": "array",
                                        "minItems": 1,
                                        "uniqueItems": True,
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "factor": {"type": "number", "exclusiveMinimum": 0},
                                    "axis": {"enum": ["ALL", "X", "Y", "Z"]},
                                    "pivot": {
                                        "oneOf": [
                                            {"const": "selection"},
                                            {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 3,
                                                "maxItems": 3,
                                            },
                                        ],
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scale-selection"}},
                            },
                            "then": {
                                "required": ["factor"],
                                "properties": {
                                    "factor": {"type": "number", "exclusiveMinimum": 0},
                                    "axis": {"enum": ["ALL", "X", "Y", "Z"]},
                                    "pivot": {
                                        "oneOf": [
                                            {"enum": ["com", "active", "origin", "cell"]},
                                            {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 3,
                                                "maxItems": 3,
                                            },
                                        ],
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "relax-added-atoms"}},
                            },
                            "then": {
                                "properties": {
                                    "pairCutoffs": {"type": "object"},
                                    "hkl": {
                                        "type": "array",
                                        "prefixItems": [
                                            {"type": "integer"},
                                            {"type": "integer"},
                                            {"type": "integer"},
                                        ],
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "freezeExisting": {"type": "boolean"},
                                    "strength": {"type": "number", "minimum": 0, "maximum": 1000},
                                    "boundaryStrength": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 1000
                                    },
                                    "fmax": {"type": "number", "exclusiveMinimum": 0},
                                    "steps": {"type": "integer", "minimum": 1, "maximum": 100000},
                                    "device": {"enum": ["cpu", "cuda"]},
                                    "cpuThreads": {"type": "integer", "minimum": 1},
                                    "mic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "clear-relaxation-trajectory"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "retain": {"enum": ["displayed", "final"]},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "set-atom-colorscale"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "enabled": {"type": "boolean"},
                                    "field": {"type": "string", "minLength": 1},
                                    "map": {"type": "string", "minLength": 1},
                                    "reverse": {"type": "boolean"},
                                    "scope": {"enum": ["all", "selected"]},
                                    "autoRange": {"type": "boolean"},
                                    "rangeMode": {
                                        "enum": ["current", "trajectory", "manual"],
                                    },
                                    "minimum": {"type": "number"},
                                    "maximum": {"type": "number"},
                                    "gamma": {
                                        "type": "number",
                                        "minimum": 0.1,
                                        "maximum": 5.0,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "add-volumetric-plane"},
                                },
                            },
                            "then": {
                                "required": ["datasetId", "hkl"],
                                "properties": {
                                    "datasetId": {"type": "string", "minLength": 1},
                                    "planeName": {"type": "string", "minLength": 1},
                                    "hkl": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "offsetAngstrom": {"type": "number"},
                                    "resolution": {"enum": [128, 256, 512, 1024]},
                                    "colormap": {"type": "string", "minLength": 1},
                                    "reverse": {"type": "boolean"},
                                    "autoRange": {"type": "boolean"},
                                    "vmin": {"type": "number"},
                                    "vmax": {"type": "number"},
                                    "opacity": {
                                        "type": "number", "minimum": 0.05, "maximum": 1
                                    },
                                    "visible": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "update-volumetric-planes"},
                                },
                            },
                            "then": {
                                "required": ["planeIds"],
                                "properties": {
                                    "planeIds": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "datasetId": {"type": "string", "minLength": 1},
                                    "planeName": {"type": "string", "minLength": 1},
                                    "hkl": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "offsetAngstrom": {"type": "number"},
                                    "resolution": {"enum": [128, 256, 512, 1024]},
                                    "colormap": {"type": "string", "minLength": 1},
                                    "reverse": {"type": "boolean"},
                                    "autoRange": {"type": "boolean"},
                                    "vmin": {"type": "number"},
                                    "vmax": {"type": "number"},
                                    "opacity": {
                                        "type": "number", "minimum": 0.05, "maximum": 1
                                    },
                                    "visible": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "remove-volumetric-planes"},
                                },
                            },
                            "then": {
                                "required": ["planeIds"],
                                "properties": {
                                    "planeIds": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "set-interface-theme"},
                                },
                            },
                            "then": {
                                "required": ["theme"],
                                "properties": {
                                    "theme": {"enum": ["system", "light", "dark"]},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "restore-app-visual-defaults"},
                                },
                            },
                            "then": {
                                "required": ["confirm"],
                                "properties": {
                                    "confirm": {"const": True},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "load-commensurate-guest"},
                                },
                            },
                            "then": {
                                "required": ["path"],
                                "properties": {
                                    "path": {"type": "string", "minLength": 1},
                                    "format": {"type": "string"},
                                    "calculate": {"type": "boolean"},
                                    "gap": {
                                        "type": "number", "minimum": 0, "maximum": 20
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "calculate-commensurate"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "axis": {"const": "Z"},
                                    "mode": {"enum": ["same-lattice", "host-guest"]},
                                    "strainTarget": {"enum": ["host", "guest"]},
                                    "strainTolerance": {
                                        "type": "number", "minimum": 0, "maximum": 0.25
                                    },
                                    "maxIndex": {
                                        "type": "integer", "minimum": 2, "maximum": 64
                                    },
                                    "maxAreaRatio": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": MAX_LATTICE_MATCH_AREA_RATIO,
                                    },
                                    "angleDeg": {"type": "number"},
                                    "gap": {
                                        "type": "number", "minimum": 0, "maximum": 20
                                    },
                                    "showAtoms": {"type": "boolean"},
                                    "snap": {"type": "boolean"},
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "uniqueItems": True,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "set-registry-translation"},
                                },
                            },
                            "then": {
                                "required": ["coordinates"],
                                "properties": {
                                    "coordinates": {
                                        "type": "array",
                                        "prefixItems": [
                                            {"type": "number"},
                                            {"type": "number"},
                                        ],
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "calculate-registry-map"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "metric": {"enum": ["short-contact", "bond-strain"]},
                                    "gridX": {
                                        "type": "integer", "minimum": 4, "maximum": 160
                                    },
                                    "gridY": {
                                        "type": "integer", "minimum": 4, "maximum": 160
                                    },
                                    "pairCutoffs": {"type": "object"},
                                    "hkl": {
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
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "start-registry-relaxation"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "hkl": {
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
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {
                                        "enum": [
                                            "run-registry-relaxation",
                                            "start-relaxation",
                                        ],
                                    },
                                },
                            },
                            "then": {
                                "properties": {
                                    "fmax": {"type": "number", "exclusiveMinimum": 0},
                                    "steps": {
                                        "type": "integer", "minimum": 1, "maximum": 100000
                                    },
                                    "calculator": _AI_REPULSION_CALCULATOR_SCHEMA,
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "load-volumetric"},
                                },
                            },
                            "then": {
                                "required": ["path"],
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "format": {"type": "string"},
                                    "precision": {
                                        "enum": [
                                            "fp32", "float32",
                                            "fp64", "float64",
                                        ],
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "show-volumetric"},
                                },
                            },
                            "then": {
                                "required": ["datasetId", "level"],
                                "properties": {
                                    "datasetId": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "level": {"type": "number"},
                                    "surfaceMode": {
                                        "enum": ["single", "signed"],
                                    },
                                    "stepSize": {"enum": [1, 2, 4]},
                                    "smearingSigma": {
                                        "type": "number",
                                        "minimum": 0,
                                        "maximum": 8,
                                    },
                                    "smoothingIterations": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "maximum": 30,
                                    },
                                    "opacity": {
                                        "type": "number",
                                        "minimum": 0.05,
                                        "maximum": 1,
                                    },
                                    "positiveColor": {
                                        "type": "string",
                                        "pattern": "^#[0-9A-Fa-f]{6}$",
                                    },
                                    "negativeColor": {
                                        "type": "string",
                                        "pattern": "^#[0-9A-Fa-f]{6}$",
                                    },
                                },
                                "allOf": [
                                    {
                                        "if": {
                                            "required": ["surfaceMode"],
                                            "properties": {
                                                "surfaceMode": {
                                                    "const": "signed",
                                                },
                                            },
                                        },
                                        "then": {
                                            "properties": {
                                                "level": {
                                                    "not": {"const": 0},
                                                },
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    ],
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
        "renderArea": {
            "type": "object",
            "description": (
                "Persistent image, video, and HTML framing. Enable it to show "
                "the render gate, follow the viewport while composing, or set "
                "an independent camera that remains fixed while the scene changes."
            ),
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
                "followViewport": {"type": "boolean"},
                "fromCurrentView": {"type": "boolean"},
                "camera": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "position": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3,
                        },
                        "target": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3,
                        },
                        "up": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3,
                        },
                        "projection": {"enum": ["orthographic", "perspective"]},
                        "fov": {
                            "type": "number", "exclusiveMinimum": 1,
                            "exclusiveMaximum": 179,
                        },
                        "zoom": {"type": "number", "exclusiveMinimum": 0},
                        "ortho_scale": {"type": "number", "exclusiveMinimum": 0},
                        "near": {"type": "number", "exclusiveMinimum": 0},
                        "far": {"type": "number", "exclusiveMinimum": 0},
                        "aspect": {"type": "number", "exclusiveMinimum": 0},
                    },
                },
            },
        },
    },
}

AI_OPERATION_PARAMETERS = {
    "set-atom-colorscale": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [
            "enabled", "field", "map", "reverse", "scope", "autoRange",
            "rangeMode", "minimum", "maximum", "gamma",
        ],
        "notes": (
            "Colors atoms by x/y/z, force norm, or a discovered numeric per-atom "
            "ASE array/calculator result. scope is all or selected. rangeMode is "
            "current, trajectory, or manual; every trajectory frame uses the same "
            "resolved minimum and maximum. gamma controls contrast. Disabling it "
            "immediately restores the saved label and element colors."
        ),
    },
    "set-interface-theme": {
        "mode": "view-or-edit",
        "required": ["theme"],
        "optional": [],
        "notes": (
            "theme is system, light, or dark. system follows the browser/OS "
            "color-scheme preference and is the built-in default."
        ),
    },
    "set-personal-visual-default": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [],
        "notes": (
            "Persists the current reusable visual settings for this OS user. "
            "Coordinates, trajectory data, absolute camera placement, and "
            "per-atom appearance overrides are excluded."
        ),
    },
    "restore-app-visual-defaults": {
        "mode": "view-or-edit",
        "required": ["confirm"],
        "optional": [],
        "notes": (
            "Destructively deletes the saved personal visual default and applies "
            "the built-in v_ase visual settings to the active tab. confirm must "
            "be true and an agent must obtain human approval first."
        ),
    },
    "wrap": {
        "mode": "view-or-edit",
        "required": [],
        "optional": ["applyConstraints"],
    },
    "translate-all": {
        "mode": "edit",
        "required": ["vector"],
        "optional": ["coordinateMode", "applyConstraints"],
        "notes": "coordinateMode is cartesian or fractional.",
    },
    "set-unit-cell": {
        "mode": "edit",
        "required": ["cell"],
        "optional": ["pbc"],
        "notes": (
            "Defines the 3 x 3 ASE cell without scaling atom coordinates. pbc defaults "
            "to [true,true,true]. This also creates a usable scratch document when no "
            "atoms have been loaded."
        ),
    },
    "build-bulk": {
        "mode": "edit",
        "required": ["formula"],
        "optional": [
            "crystalStructure", "cellMode", "a", "b", "c", "alpha",
            "covera", "u", "basis", "confirmReplace",
        ],
        "notes": (
            "Builds a periodic crystal with ase.build.bulk. Query "
            "/api/build/bulk/catalog/{session_id} for installed-ASE reference "
            "materials and compatible cell shapes, then preview through "
            "/api/build/bulk/preview/{session_id}. Custom compounds such as CuO "
            "require crystalStructure and a. c and covera are mutually exclusive. "
            "The operation replaces the active structure and trajectory; an existing "
            "document requires explicit human approval and confirmReplace=true."
        ),
    },
    "set-supercell": {
        "mode": "edit",
        "required": ["reps"],
        "optional": ["applyConstraints"],
        "notes": "reps contains three integers from 1 through 64.",
    },
    "make-supercell": {
        "mode": "edit",
        "required": ["matrix"],
        "optional": ["applyConstraints"],
        "notes": "matrix is a 3 x 3 integer transformation matrix.",
    },
    "add-atom": {
        "mode": "edit",
        "required": ["position", "label-or-element"],
        "optional": ["label", "element"],
    },
    "scatter-atoms": {
        "mode": "edit",
        "required": ["entries-or-element-count"],
        "optional": [
            "entries", "element", "label", "count", "regionMode", "regions", "bounds",
            "regionRole", "regionMic", "constrainToDomain", "allowEscape",
            "placementMode", "regularSpacing", "coordinateBasis", "pbcAware",
            "seed", "freezeExisting", "cutoffBasis", "cutoffScale", "pairCutoffs",
        ],
        "notes": (
            "Starts an Add Atoms session or appends one or more element/label populations "
            "to the active session after placement relaxation is inactive. The first "
            "pre-session structure remains the immutable host across every placement. "
            "placementMode is random, homogeneous, or regular. regular uses optional regularSpacing in A. "
            "coordinateBasis=cartesian optimizes "
            "physical nearest-neighbor spacing in angstrom and is the default; fractional "
            "optimizes normalized cell-coordinate spacing. Random sampling remains volume-uniform "
            "under either basis because the cell transform has a constant Jacobian. "
            "regions defines up to 32 stable-id Cartesian Allow/Reject regions. The exact domain is "
            "the unit cell intersected with the Allow union (or the full cell when no Allow exists), "
            "minus the Reject union. Periodic region images are clipped to the triclinic primary cell "
            "without voxel approximation. A structure without a finite cell requires an Allow region. "
            "Legacy regionMode=box remains accepted. constrainToDomain defaults "
            "to false, so the region controls initial sampling without confining relaxation; "
            "allowEscape is the inverse compatibility field. The default "
            "temporarily fixes every pre-session atom. Follow with common start-relaxation "
            "and finish-add-atoms, append another batch, or use cancel-add-atoms to restore "
            "the exact baseline."
        ),
    },
    "scatter-molecules": {
        "mode": "edit",
        "required": ["molecules-or-molecule-count"],
        "optional": [
            "molecules", "molecule", "label", "count", "regionMode", "regions", "bounds",
            "regionRole", "regionMic", "constrainToDomain", "allowEscape",
            "placementMode", "regularSpacing", "coordinateBasis", "pbcAware",
            "randomOrientation", "rigidMolecules", "seed", "freezeExisting",
            "quantityMode", "targetDensityGcm3", "cutoffBasis", "cutoffScale", "pairCutoffs",
        ],
        "notes": (
            "Starts an Add Molecules session or appends molecules to the active Add session "
            "from the installed ASE G2 molecule catalog. "
            "Query /api/add-session/molecules/{session_id} before choosing a name. Molecule "
            "coordinates are placed and rotated about ASE's native coordinate origin without recentering. "
            "randomOrientation uses Haar-uniform SO(3) rotations. rigidMolecules defaults to "
            "true and preserves each molecule's internal distances during atomwise pairwise "
            "repulsion; false permits ordinary atomwise relaxation. quantityMode=density computes "
            "integer molecule counts from exact accessible volume and reports the realized density. "
            "The placement, region, "
            "host-freeze, relaxation, finish, and cancel semantics match scatter-atoms."
        ),
    },
    "update-add-atoms-region": {
        "mode": "edit",
        "required": ["active-cartesian-add-atoms-session"],
        "optional": [
            "regions", "regionId", "regionName", "bounds", "regionRole",
            "regionMic", "constrainToDomain", "allowEscape",
        ],
        "notes": (
            "Replaces all active Allow/Reject regions, or updates one stable regionId, without moving "
            "staged atoms. Regions can translate as a group but cannot be rotated."
        ),
    },
    "relax-added-atoms": {
        "mode": "edit",
        "required": ["active-add-atoms-session"],
        "optional": [
            "pairCutoffs", "freezeExisting", "strength", "boundaryStrength",
            "fmax", "steps", "device", "cpuThreads", "mic",
            "constrainToDomain", "allowEscape",
        ],
        "notes": (
            "Compatibility alias for the same shared placement-relaxation path used by "
            "start-relaxation. It starts asynchronous FIRE with one "
            "AdditionRepulsionCalculator attached to the complete staged structure. "
            "device selects CPU or CUDA and "
            "cpuThreads controls CPU parallelism; CUDA falls back to CPU when unavailable. "
            "Every optimizer step is retained in the Add-mode trajectory. Poll "
            "describe.addAtoms or consume collaboration events until is_relaxing is false."
        ),
    },
    "stop-added-atoms": {
        "mode": "edit",
        "required": ["active-add-atoms-relaxation"],
        "optional": [],
    },
    "finish-add-atoms": {
        "mode": "edit",
        "required": ["inactive-add-atoms-relaxation"],
        "optional": [],
        "notes": "Commits only inserted atoms; every host coordinate, constraint, and array is restored exactly.",
    },
    "cancel-add-atoms": {
        "mode": "edit",
        "required": ["active-add-atoms-session"],
        "optional": [],
        "notes": "Restores the complete pre-session structure and history state.",
    },
    "delete-selection": {
        "mode": "view-or-edit",
        "required": ["selection-or-indices"],
        "optional": ["indices"],
        "notes": (
            "View mode hides the exact selected visual instances without "
            "changing ASE atoms. Edit mode deletes the corresponding base "
            "atom indices from the physical structure."
        ),
    },
    "set-identity": {
        "mode": "edit",
        "required": ["label", "selection-or-indices"],
        "optional": ["indices", "element", "applyConstraints"],
    },
    "set-constraints": {
        "mode": "edit",
        "required": ["selection-or-indices"],
        "optional": [
            "indices", "fixAtoms", "kind", "vector",
            "clearDirectional", "applyConstraints",
        ],
        "notes": "kind is fixed_line or fixed_plane; vector has three components.",
    },
    "move-selection": {
        "mode": "edit",
        "required": ["vector", "selection-or-indices"],
        "optional": ["indices", "applyConstraints"],
    },
    "rotate-selection": {
        "mode": "edit",
        "required": ["angleDeg", "selection-or-indices"],
        "optional": ["indices", "axis", "pivot", "applyConstraints"],
        "notes": (
            "axis defaults to [0,0,1]. pivot is com, active, origin, cell, "
            "or an explicit three-number position."
        ),
    },
    "scale-selection": {
        "mode": "edit",
        "required": ["factor", "selection-or-indices"],
        "optional": ["indices", "axis", "pivot", "applyConstraints"],
        "notes": (
            "Scales physical Cartesian atom coordinates about the pivot without changing "
            "atom or bond radii. axis is X, Y, Z, or ALL and defaults to ALL. pivot is "
            "com, active, origin, cell, or an explicit three-number position."
        ),
    },
    "scale-add-atoms-regions": {
        "mode": "edit",
        "required": ["regionIds", "factor", "active-add-atoms-session"],
        "optional": ["axis", "pivot", "regionMic", "constrainToDomain", "allowEscape"],
        "notes": (
            "Scales Cartesian insertion-region bounds about their shared center, or an "
            "explicit three-number pivot. axis is X, Y, Z, or ALL."
        ),
    },
    "rotate-to-commensurate": {
        "mode": "edit",
        "required": ["angleDeg", "selection-or-indices"],
        "optional": [
            "indices", "axis", "pivot", "maxAngleDifferenceDeg",
            "strainTolerance", "maxIndex", "maxAreaRatio", "showAtoms",
            "applyConstraints",
        ],
        "notes": (
            "Finds the nearest validated periodic 2D lattice match, rotates the "
            "selected layer to that exact angle, and opens the common-cell proposal. "
            "The default is cells-only; showAtoms=true adds the opaque core and muted "
            "one-primitive-cell boundary shell. axis is strictly Z; maxAreaRatio "
            "defaults to 16 and is explicitly limited to 128. No proposal is made "
            "above the requested limit."
        ),
    },
    "load-commensurate-guest": {
        "mode": "view-or-edit",
        "required": ["path"],
        "optional": [
            "format", "calculate", "strainTarget", "strainTolerance",
            "maxAreaRatio", "maxIndex", "angleDeg", "gap", "showAtoms",
        ],
        "notes": (
            "Loads a separate guest structure from inside the GUI launch directory. "
            "gap is guest minimum z minus host maximum z in angstrom and defaults "
            "to 3. Absolute paths and parent-directory traversal are rejected."
        ),
    },
    "remove-commensurate-guest": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [],
    },
    "calculate-commensurate": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [
            "indices", "axis", "mode", "strainTarget", "strainTolerance",
            "maxAreaRatio", "maxIndex", "angleDeg", "gap", "showAtoms", "snap",
        ],
        "notes": (
            "Searches bounded integer common cells about global Z. Same-lattice "
            "mode requires a selected rotating layer before atom preview or "
            "materialization; host-guest mode requires a loaded guest. Cells-only "
            "preview is the default. maxAreaRatio defaults to 16 and accepts 1..128. "
            "Candidate acceptance uses maximum principal strain; the paper projection "
            "reports mean absolute strain and actual host-plus-guest atom counts."
        ),
    },
    "apply-commensurate-cell": {
        "mode": "edit",
        "required": ["active-commensurate-proposal"],
        "optional": [],
        "notes": "Materializes the active validated proposal as the ASE unit cell.",
    },
    "dismiss-commensurate-cell": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [],
        "notes": "Closes the active proposal and restores the pre-preview camera.",
    },
    "calculate-registry-map": {
        "mode": "view-or-edit",
        "required": ["selection-or-indices"],
        "optional": ["indices", "metric", "gridX", "gridY", "pairCutoffs", "hkl"],
        "notes": (
            "Scans one primitive periodic translation cell in the requested (hkl) plane. "
            "metric is short-contact or bond-strain; both are geometry scores, not energies."
        ),
    },
    "start-registry-relaxation": {
        "mode": "edit",
        "required": ["selection-or-indices"],
        "optional": ["indices", "hkl"],
        "notes": (
            "Activates the rigid registry-translation mode for a selected guest or "
            "interface component. Only one common translation in the periodic (hkl) plane "
            "can change; host coordinates, cell vectors, and all selected internal "
            "relative coordinates remain invariant."
        ),
    },
    "set-registry-translation": {
        "mode": "edit",
        "required": ["active-registry-relaxation", "coordinates"],
        "optional": [],
        "notes": (
            "Sets the two unwrapped coefficients of the active primitive plane-lattice "
            "basis without moving the cell or changing selected internal coordinates."
        ),
    },
    "run-registry-relaxation": {
        "mode": "edit",
        "required": ["active-registry-relaxation"],
        "optional": ["fmax", "steps", "calculator"],
        "notes": (
            "Optimizes the two rigid in-plane translation degrees of freedom with the "
            "attached calculator or the default pairwise repulsion calculator. Consume "
            "registry_relax_step events until is_relaxing is false. calculator may "
            "configure absolute pair_cutoffs as independent onset distances in "
            "Angstrom, or cutoff_mode=scaled with reference pair distances and "
            "cutoff_scale; neither cutoff is a hard constraint."
        ),
    },
    "stop-registry-relaxation": {
        "mode": "edit",
        "required": ["active-registry-relaxation"],
        "optional": [],
    },
    "finish-registry-relaxation": {
        "mode": "edit",
        "required": ["inactive-registry-relaxation"],
        "optional": [],
        "notes": "Commits the rigid translation as one undoable structure edit and exits the mode.",
    },
    "cancel-registry-relaxation": {
        "mode": "edit",
        "required": ["active-registry-relaxation"],
        "optional": [],
        "notes": "Restores the exact pre-mode coordinates and exits without a history entry.",
    },
    "undo": {"mode": "view-or-edit", "required": [], "optional": []},
    "redo": {"mode": "view-or-edit", "required": [], "optional": []},
    "reset-coordinates": {
        "mode": "edit",
        "required": [],
        "optional": [],
    },
    "start-relaxation": {
        "mode": "edit",
        "required": ["attached-calculator-or-active-add-atoms-session"],
        "optional": ["fmax", "steps", "calculator", "applyConstraints"],
        "notes": (
            "When Add Atoms is active, this common operation routes the same calculator, "
            "cutoff, device, fmax, and step contract through placement relaxation while "
            "preserving the immutable pre-session host. Otherwise an ASE calculator must "
            "be attached to the structure. "
            "For the built-in repulsion calculator, calculator accepts device, "
            "cpu_threads, k_repulsion, cutoff_basis, and independent label-pair "
            "pair_cutoffs. Absolute mode interprets each enabled pair value directly "
            "in Angstrom; scaled mode multiplies its reference distance by "
            "cutoff_scale. "
            "The cutoff is the zero-force onset distance, not a guaranteed minimum "
            "separation."
        ),
    },
    "stop-relaxation": {
        "mode": "edit",
        "required": [],
        "optional": [],
        "notes": "Stops the active ordinary or Add Atoms placement optimizer.",
    },
    "clear-relaxation-trajectory": {
        "mode": "edit",
        "required": ["available-relaxation-trajectory"],
        "optional": ["retain"],
        "notes": (
            "Removes the dedicated optimization movie while leaving its mode active. "
            "retain is final by default or displayed to keep the frame currently shown."
        ),
    },
    "exit-relaxation-mode": {
        "mode": "edit",
        "required": [],
        "optional": ["keep"],
        "notes": (
            "Stops an active optimizer if needed, closes the dedicated movie timeline, "
            "and either keeps current coordinates (default) or restores the exact "
            "pre-relaxation structure when keep=false."
        ),
    },
    "refresh-displacements": {
        "mode": "view-or-edit",
        "required": [],
        "optional": ["display"],
    },
    "load-volumetric": {
        "mode": "view-or-edit",
        "required": ["path"],
        "optional": ["format", "precision"],
        "notes": (
            "path is resolved inside the GUI launch directory. Supported "
            "formats include CHGCAR, LOCPOT, PARCHG, ELFCAR, Cube, and XSF. "
            "precision is fp32/float32 or fp64/float64 and is applied while reading."
        ),
    },
    "show-volumetric": {
        "mode": "view-or-edit",
        "required": ["datasetId", "level"],
        "optional": [
            "surfaceMode", "stepSize", "opacity",
            "positiveColor", "negativeColor", "smearingSigma",
            "smoothingIterations",
        ],
        "notes": (
            "surfaceMode is single or signed; stepSize is 1, 2, or 4. "
            "Signed mode renders +abs(level) and -abs(level), requires a "
            "non-zero level, and may return only the sign that still crosses "
            "the displayed field range after smearing. opacity is 0.05-1; "
            "colors are six-digit #RRGGBB values. "
            "smearingSigma is 0-8 grid points and filters only the displayed "
            "field. smoothingIterations is an integer from 0-30 and fairs only "
            "the extracted mesh. The default safety limits are 134,217,728 "
            "source grid points and 2,000,000 output triangles per surface."
        ),
    },
    "add-volumetric-plane": {
        "mode": "view-or-edit",
        "required": ["datasetId", "hkl"],
        "optional": [
            "planeName", "offsetAngstrom", "resolution", "colormap",
            "reverse", "autoRange", "vmin", "vmax", "opacity", "visible",
        ],
        "notes": (
            "Creates one cell-clipped scalar-field plane. hkl is a non-zero "
            "three-number reciprocal-space normal; offsetAngstrom is the signed "
            "distance from the origin along its Cartesian unit normal. If the "
            "offset is omitted, the plane is centered in the displayed supercell."
        ),
    },
    "update-volumetric-planes": {
        "mode": "view-or-edit",
        "required": ["planeIds"],
        "optional": [
            "datasetId", "planeName", "hkl", "offsetAngstrom", "resolution",
            "colormap", "reverse", "autoRange", "vmin", "vmax", "opacity",
            "visible",
        ],
        "notes": (
            "Applies every supplied field to all planeIds as one visual edit. "
            "resolution is 128, 256, 512, or 1024. vmin/vmax are used when "
            "autoRange is false. Invalid IDs or values reject the whole edit."
        ),
    },
    "remove-volumetric-planes": {
        "mode": "view-or-edit",
        "required": ["planeIds"],
        "optional": [],
        "notes": "Removes all requested planar sections as one visual edit.",
    },
    "combine-volumetric": {
        "mode": "view-or-edit",
        "required": ["datasetIds", "coefficients"],
        "optional": ["name", "precision"],
        "notes": (
            "All grids must have matching dimensions, cell, origin, PBC, and "
            "units. Output precision defaults to the highest input precision."
        ),
    },
    "remove-volumetric": {
        "mode": "view-or-edit",
        "required": ["datasetId"],
        "optional": [],
    },
    "calculate-rdf": {
        "mode": "view-or-edit",
        "required": [],
        "optional": ["cutoff", "bins", "pairMode", "activePairs"],
        "notes": (
            "pairMode is active, selected, all, or none. selected filters partial "
            "curves to active bonds whose endpoints are both selected in the GUI; "
            "activePairs can provide the same label-pair filter explicitly. Fully "
            "periodic 3D cells use bulk RDF normalization, while finite no-PBC "
            "structures use an unordered-pair probability density. Every periodic "
            "image inside the requested cutoff is counted; the cutoff is not reduced "
            "to a fixed supercell or MIC radius."
        ),
    },
}

AI_EXPORT_PARAMETERS = {
    "image": {
        "optional": ["imageFormat", "width", "height", "options"],
        "notes": "imageFormat is png, jpeg, webp, or pdf.",
    },
    "video": {
        "optional": [
            "container", "width", "height", "fps",
            "interpolationMultiplier", "interpolationMic", "options",
        ],
        "notes": "container is mov or avi and requires a trajectory.",
    },
    "poscar": {"optional": []},
    "pickle": {"optional": []},
    "blender": {"optional": ["includeCell"]},
    "3dm": {
        "optional": ["includeCell"],
        "notes": "Requires the optional rhino3dm dependency.",
    },
    "obj": {"optional": ["includeCell"]},
    "html": {
        "optional": ["width", "height", "options", "embedProject"],
        "notes": "embedProject defaults to false for a lightweight view-only file.",
    },
    "project": {"optional": []},
    "settings": {"optional": []},
    "rdf-csv": {
        "optional": ["cutoff", "bins", "pairMode", "activePairs"],
        "notes": (
            "Exports the total RDF and currently requested partial curves. "
            "pairMode accepts active, selected, all, or none; selected requires "
            "the browser-derived selected active label pairs or explicit activePairs."
        ),
    },
    "commensurate-csv": {
        "optional": [
            "mode", "strainTarget", "strainTolerance", "maxAreaRatio", "maxIndex",
        ],
        "notes": (
            "Exports angle, host/guest integer matrices, area ratios, residual "
            "strains, and the scientific references used by the bounded search."
        ),
    },
    "registry-csv": {
        "optional": ["indices", "metric", "gridX", "gridY", "pairCutoffs", "hkl"],
        "notes": (
            "Exports the complete periodic (hkl) translation grid, its exact "
            "lattice basis, Cartesian vectors, and geometry metric values."
        ),
    },
}


def ai_schema_payload() -> Dict[str, Any]:
    """Return the complete live discovery contract for external agents."""
    return {
        "protocol": AI_PROTOCOL,
        "command_transport": "http-json-bridge",
        "accepts_natural_language": False,
        "stdin_commands": False,
        "collaboration": {
            "protocol": COLLABORATION_PROTOCOL,
            "delivery": "ndjson-after-handshake",
            "event_endpoint": "/api/ai/events/{session_id}",
            "workspace_event_endpoint": "/api/ai/workspace-events/{workspace_id}",
            "authoritative_state": (
                "POST method describe to command_endpoint after each event. "
                "Use expectedRevision in apply params to avoid overwriting a newer human edit."
            ),
        },
        "command_endpoint": {
            "workspace": "/api/ai/command/workspace/{workspace_id}",
            "document": "/api/ai/command/session/{session_id}",
            "request": {
                "method": "describe",
                "params": {"includePositions": True},
                "timeout_seconds": _AI_COMMAND_DEFAULT_TIMEOUT_SECONDS,
            },
            "methods": sorted(_AI_COMMAND_METHODS),
        },
        "control_schema": AI_CONTROL_SCHEMA,
        "operation_parameters": AI_OPERATION_PARAMETERS,
        "export_parameters": AI_EXPORT_PARAMETERS,
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


def trajectory_identity_compatible(session: EditorSession) -> bool:
    """Return whether stable atom indices have one element sequence in every frame."""
    if session._trajectory_identity_compatible is not None:
        return session._trajectory_identity_compatible
    if session.frame_count <= 1:
        session._trajectory_identity_compatible = True
        return True
    if session.trajectory_source is not None:
        source = session.trajectory_source
        compatible = int(getattr(source, "natoms", -1)) == len(session.working_atoms)
        session._trajectory_identity_compatible = compatible
        return compatible

    atom_count = len(session.working_atoms)
    elements = session.working_atoms.get_chemical_symbols()
    compatible = all(
        len(frame) == atom_count
        and frame.get_chemical_symbols() == elements
        for frame in session.trajectory_frames
    )
    session._trajectory_identity_compatible = bool(compatible)
    return bool(compatible)


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
    addition = atom_addition_summary(session)
    data["metadata"]["atom_addition"] = addition
    data["metadata"]["registry_relaxation"] = registry_relaxation_summary(session)
    data["metadata"]["relaxation"] = {
        "active": bool(session.relaxation_mode_active),
        "is_relaxing": bool(session.is_relaxing),
    }
    if addition and addition["temporary_fixed_indices"]:
        fixed = set(data["constraints"].get("fixed_indices") or [])
        fixed.update(addition["temporary_fixed_indices"])
        data["constraints"]["fixed_indices"] = sorted(fixed)
    data["metadata"]["volumetric_datasets"] = [
        dataset.summary()
        for dataset in session.volumetric_datasets
    ]
    guest = session.commensurate_guest_atoms
    data["metadata"]["commensurate_guest"] = (
        {
            "name": session.commensurate_guest_name or "Guest structure",
            "natoms": len(guest),
            "cell": np.asarray(guest.cell.array, dtype=float).tolist(),
            "pbc": np.asarray(guest.pbc, dtype=bool).tolist(),
            "labels": atom_labels(guest),
            "chemical_symbols": guest.get_chemical_symbols(),
            "min_z": float(np.min(guest.positions[:, 2])) if len(guest) else 0.0,
            "max_z": float(np.max(guest.positions[:, 2])) if len(guest) else 0.0,
            "default_gap": 3.0,
        }
        if isinstance(guest, Atoms)
        else None
    )
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
    data["metadata"]["trajectory_identity_compatible"] = trajectory_identity_compatible(session)
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


def require_editable(
    session: EditorSession,
    action: str = "This operation",
    *,
    allow_atom_addition: bool = False,
    allow_registry_relaxation: bool = False,
):
    if is_viz_only(session):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{action} is disabled in View mode. "
                "Switch the top-bar mode to Edit before modifying atoms."
            ),
        )
    if not allow_atom_addition:
        require_no_atom_addition(session, action)
    if not allow_registry_relaxation:
        require_no_registry_relaxation(session, action)


def require_no_atom_addition(session: EditorSession, action: str = "This operation"):
    if session.atom_addition is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Finish or cancel Add Atoms before {action.lower()}.",
        )


def require_no_registry_relaxation(session: EditorSession, action: str = "This operation"):
    if session.registry_relaxation is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Apply or cancel planar translation relaxation before {action.lower()}.",
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


def _commensurate_angular_distance(first: float, second: float) -> float:
    return abs((float(first) - float(second) + 180.0) % 360.0 - 180.0)


def _commensurate_search_signature(session: EditorSession, payload: Dict[str, Any]) -> str:
    guest = session.commensurate_guest_atoms
    mode = "host-guest" if payload.get("mode") == "host-guest" and guest is not None else "same-lattice"
    signature = {
        "mode": mode,
        "axis": str(payload.get("axis", "Z")).upper(),
        "max_index": int(payload.get("max_index", 32)),
        "max_area_ratio": int(payload.get("max_area_ratio", 16)),
        "strain_tolerance": round(float(payload.get("strain_tolerance", 0.01)), 12),
        "strain_target": str(payload.get("strain_target", "guest")).lower(),
        "selected_indices": sorted(
            int(index)
            for index in payload.get("selected_indices", payload.get("indices", []))
            if isinstance(index, (int, np.integer))
        ),
        "host_cell": np.round(np.asarray(session.working_atoms.cell.array, dtype=float), 10).tolist(),
        "host_pbc": np.asarray(session.working_atoms.pbc, dtype=bool).tolist(),
        "guest_cell": (
            np.round(np.asarray(guest.cell.array, dtype=float), 10).tolist()
            if mode == "host-guest"
            else None
        ),
        "guest_pbc": (
            np.asarray(guest.pbc, dtype=bool).tolist()
            if mode == "host-guest"
            else None
        ),
    }
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def _run_commensurate_search(
    session: EditorSession,
    payload: Dict[str, Any],
    progress_callback=None,
) -> Dict[str, Any]:
    axis = str(payload.get("axis", "Z")).upper()
    if axis != "Z":
        raise ValueError(
            "Commensurate atoms is restricted to in-plane rotation about global Z."
        )
    max_index = int(payload.get("max_index", 32))
    strain_tolerance = float(payload.get("strain_tolerance", 0.01))
    max_area_ratio = int(payload.get("max_area_ratio", 16))
    if max_area_ratio < 1 or max_area_ratio > MAX_LATTICE_MATCH_AREA_RATIO:
        raise ValueError(
            "Maximum commensurate area ratio must be between 1 and "
            f"{MAX_LATTICE_MATCH_AREA_RATIO}."
        )
    mode = "host-guest" if payload.get("mode") == "host-guest" else "same-lattice"
    atoms = session.working_atoms
    if mode == "host-guest":
        guest = session.commensurate_guest_atoms
        if guest is None:
            raise ValueError("Load a guest structure before host/guest lattice matching.")
        result = find_lattice_matches(
            atoms.cell.array,
            atoms.pbc,
            guest.cell.array,
            guest.pbc,
            max_area_ratio=max_area_ratio,
            strain_tolerance=strain_tolerance,
            strain_target=payload.get("strain_target", "guest"),
            progress_callback=progress_callback,
        )
        for candidate in result["candidates"]:
            candidate["host_atom_count"] = (
                len(atoms) * int(candidate.get("host_area_ratio", 0))
            )
            candidate["guest_atom_count"] = (
                len(guest) * int(candidate.get("guest_area_ratio", 0))
            )
            candidate["total_atom_count"] = (
                candidate["host_atom_count"] + candidate["guest_atom_count"]
            )
    else:
        if progress_callback:
            progress_callback(0.08, "Projecting the periodic host cell")
        result = find_commensurate_angles(
            atoms.cell.array,
            atoms.pbc,
            axis,
            max_index=max_index,
            strain_tolerance=strain_tolerance,
            chemical_symbols=atoms.get_chemical_symbols(),
        )
        result["max_area_ratio"] = max_area_ratio
        selected = {
            int(index)
            for index in payload.get("selected_indices", payload.get("indices", []))
            if isinstance(index, (int, np.integer)) and 0 <= int(index) < len(atoms)
        }
        for candidate in result["candidates"]:
            area = int(candidate.get("area_ratio", 0))
            candidate["host_atom_count"] = (len(atoms) - len(selected)) * area
            candidate["guest_atom_count"] = len(selected) * area
            candidate["total_atom_count"] = len(atoms) * area
        result["suggestion_count"] = sum(
            1
            for candidate in result["candidates"]
            if candidate.get("supercell_supported")
            and int(candidate.get("area_ratio", 0)) <= max_area_ratio
        )
        if progress_callback:
            progress_callback(1.0, "Ranking valid commensurate matches")
    return result


def resolve_commensurate_candidate(session: EditorSession, payload: Dict[str, Any]):
    """Validate a client-selected common-cell candidate against backend search."""

    max_area_ratio = int(payload.get("max_area_ratio", 16))
    requested = payload.get("candidate") or {}
    try:
        requested_guest = np.asarray(
            requested.get("guest_matrix", requested.get("source_matrix")),
            dtype=int,
        )
        requested_host = np.asarray(
            requested.get("host_matrix", requested.get("target_matrix")),
            dtype=int,
        )
        requested_angle = float(requested.get("angle_deg"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid commensurate candidate payload.") from exc
    if requested_guest.shape != (2, 2) or requested_host.shape != (2, 2):
        raise HTTPException(status_code=400, detail="Commensurate candidate needs two 2 x 2 integer matrices.")

    signature = _commensurate_search_signature(session, payload)
    cached = session.commensurate_search_cache or {}
    if cached.get("signature") == signature and isinstance(cached.get("result"), dict):
        result = cached["result"]
    else:
        try:
            result = _run_commensurate_search(session, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.commensurate_search_cache = {"signature": signature, "result": result}
    matches = [
        candidate
        for candidate in result["candidates"]
        if np.array_equal(
            np.asarray(candidate.get("guest_matrix", candidate.get("source_matrix")), dtype=int),
            requested_guest,
        )
        and np.array_equal(
            np.asarray(candidate.get("host_matrix", candidate.get("target_matrix")), dtype=int),
            requested_host,
        )
        and _commensurate_angular_distance(candidate["angle_deg"], requested_angle) <= 2e-5
    ]
    if not matches:
        raise HTTPException(
            status_code=400,
            detail="The proposed commensurate cell is not a current low-strain lattice match.",
        )
    candidate = matches[0]
    if int(candidate["area_ratio"]) > max_area_ratio:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The smallest matching cell has area ratio {candidate['area_ratio']}, "
                f"above the configured maximum of {max_area_ratio}."
            ),
        )
    if not candidate.get("supercell_supported", False):
        raise HTTPException(
            status_code=400,
            detail=candidate.get("supercell_reason") or "This match cannot be materialized as a common cell.",
        )
    return candidate, result


def _commensurate_constraint_indices(constraint, natoms: int) -> list[int]:
    return [int(index) for index in _constraint_indices(constraint, natoms)]


def materialize_commensurate_atoms(
    atoms: Atoms,
    geometry: Dict[str, Any],
    candidate: Dict[str, Any],
    selected_indices: List[int],
    pivot,
) -> Atoms:
    """Create one editable common cell while preserving supported constraints."""

    core_rows = [index for index, core in enumerate(geometry["core_mask"]) if core]
    source_indices = [int(geometry["atom_indices"][row]) for row in core_rows]
    source = atoms.copy()
    source.set_constraint()
    transformed = source[source_indices]
    transformed.set_positions(np.asarray([geometry["positions"][row] for row in core_rows], dtype=float))
    transformed.set_cell(np.asarray(geometry["cell"], dtype=float), scale_atoms=False)
    transformed.set_pbc(atoms.pbc)
    transformed.wrap(eps=1e-9)

    row_metadata = [
        (
            int(geometry["atom_indices"][row]),
            tuple(int(value) for value in geometry["lattice_indices"][row]),
            str(geometry["components"][row]),
        )
        for row in core_rows
    ]
    index_map: Dict[tuple[int, tuple[int, int, int], str], int] = {
        metadata: new_index for new_index, metadata in enumerate(row_metadata)
    }
    by_atom_component: Dict[tuple[int, str], List[int]] = {}
    for new_index, (old_index, _, component) in enumerate(row_metadata):
        by_atom_component.setdefault((old_index, component), []).append(new_index)

    selected = set(int(index) for index in selected_indices)
    rotation = row_rotation_matrix(
        [1.0 if str(candidate.get("axis", "Z")).upper() == "X" else 0.0,
         1.0 if str(candidate.get("axis", "Z")).upper() == "Y" else 0.0,
         1.0 if str(candidate.get("axis", "Z")).upper() == "Z" else 0.0],
        float(candidate["angle_deg"]),
    )
    deformation = np.asarray(candidate["deformation_matrix"], dtype=float)

    def transformed_direction(values, component: str, *, plane_normal: bool = False):
        direction = np.asarray(values, dtype=float)
        if component == "rotating":
            affine = rotation @ deformation
            direction = (
                np.linalg.solve(affine, direction)
                if plane_normal
                else direction @ affine
            )
        length = float(np.linalg.norm(direction))
        if length <= 1e-12:
            raise HTTPException(status_code=400, detail="A directional constraint became singular.")
        return (direction / length).tolist()

    constraints = []
    for constraint in atoms.constraints or []:
        old_indices = _commensurate_constraint_indices(constraint, len(atoms))
        if isinstance(constraint, FixAtoms):
            mapped = [
                new_index
                for old_index in old_indices
                for component in (("rotating",) if old_index in selected else ("reference",))
                for new_index in by_atom_component.get((old_index, component), [])
            ]
            if mapped:
                constraints.append(FixAtoms(indices=mapped))
        elif isinstance(constraint, FixCartesian):
            for component in ("reference", "rotating"):
                mapped = [
                    new_index
                    for old_index in old_indices
                    for new_index in by_atom_component.get((old_index, component), [])
                ]
                if mapped:
                    constraints.append(FixCartesian(mapped, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixScaled):
            for component in ("reference", "rotating"):
                mapped = [
                    new_index
                    for old_index in old_indices
                    for new_index in by_atom_component.get((old_index, component), [])
                ]
                if mapped:
                    constraints.append(FixScaled(mapped, mask=constraint.mask.tolist()))
        elif isinstance(constraint, (FixedLine, FixedPlane)):
            constraint_type = FixedLine if isinstance(constraint, FixedLine) else FixedPlane
            for component in ("reference", "rotating"):
                mapped = [
                    new_index
                    for old_index in old_indices
                    for new_index in by_atom_component.get((old_index, component), [])
                ]
                if mapped:
                    constraints.append(constraint_type(
                        mapped,
                        transformed_direction(
                            constraint.dir,
                            component,
                            plane_normal=isinstance(constraint, FixedPlane),
                        ),
                    ))
        elif isinstance(constraint, Hookean):
            if constraint._type != "two atoms":
                raise HTTPException(
                    status_code=400,
                    detail="Hookean point/plane constraints must be removed before applying a commensurate cell.",
                )
            first, second = [int(value) for value in constraint.indices]
            first_component = "rotating" if first in selected else "reference"
            second_component = "rotating" if second in selected else "reference"
            if first_component != second_component:
                raise HTTPException(
                    status_code=400,
                    detail="A Hookean constraint crossing the two commensurate layers cannot be replicated unambiguously.",
                )
            component = first_component
            lattice_points = sorted({
                lattice
                for old_index, lattice, row_component in row_metadata
                if old_index == first and row_component == component
            })
            for lattice in lattice_points:
                first_new = index_map.get((first, lattice, component))
                second_new = index_map.get((second, lattice, component))
                if first_new is not None and second_new is not None:
                    constraints.append(Hookean(
                        first_new,
                        second_new,
                        rt=constraint.threshold,
                        k=constraint.spring,
                    ))
    if constraints:
        transformed.set_constraint(constraints)
    if atoms.calc:
        transformed.calc = copy_calculator(atoms.calc)
    return transformed


def _normalized_affine_line_direction(values, affine: np.ndarray) -> list[float]:
    direction = np.asarray(values, dtype=float) @ affine
    length = float(np.linalg.norm(direction))
    if length <= 1e-12:
        raise HTTPException(
            status_code=400,
            detail="A directional constraint became singular in the common cell.",
        )
    return (direction / length).tolist()


def _normalized_affine_plane_normal(values, affine: np.ndarray) -> list[float]:
    try:
        normal = np.linalg.solve(np.asarray(affine, dtype=float), np.asarray(values, dtype=float))
    except np.linalg.LinAlgError as exc:
        raise HTTPException(
            status_code=400,
            detail="A fixed-plane normal became singular in the common cell.",
        ) from exc
    length = float(np.linalg.norm(normal))
    if length <= 1e-12:
        raise HTTPException(
            status_code=400,
            detail="A fixed-plane normal became singular in the common cell.",
        )
    return (normal / length).tolist()


def _transform_commensurate_constraints(
    atoms: Atoms,
    affine: np.ndarray,
    translation: np.ndarray,
) -> list[Any]:
    transformed: list[Any] = []
    for constraint in atoms.constraints or []:
        indices = _commensurate_constraint_indices(constraint, len(atoms))
        if isinstance(constraint, FixAtoms):
            transformed.append(FixAtoms(indices=indices))
        elif isinstance(constraint, FixCartesian):
            transformed.append(FixCartesian(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixScaled):
            transformed.append(FixScaled(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixedLine):
            transformed.append(FixedLine(
                indices,
                _normalized_affine_line_direction(constraint.dir, affine),
            ))
        elif isinstance(constraint, FixedPlane):
            transformed.append(FixedPlane(
                indices,
                _normalized_affine_plane_normal(constraint.dir, affine),
            ))
        elif isinstance(constraint, Hookean) and constraint._type == "two atoms":
            transformed.append(Hookean(
                int(constraint.indices[0]),
                int(constraint.indices[1]),
                rt=constraint.threshold,
                k=constraint.spring,
            ))
        elif isinstance(constraint, Hookean) and constraint._type == "point":
            origin = np.asarray(constraint.origin, dtype=float) @ affine + translation
            transformed.append(Hookean(
                int(constraint.index),
                origin,
                rt=constraint.threshold,
                k=constraint.spring,
            ))
        elif isinstance(constraint, Hookean) and constraint._type == "plane":
            coefficients = np.asarray(constraint.plane[:3], dtype=float)
            try:
                normal = np.linalg.solve(affine, coefficients)
            except np.linalg.LinAlgError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="A Hookean plane became singular in the common cell.",
                ) from exc
            offset = float(constraint.plane[3]) - float(np.dot(translation, normal))
            norm = float(np.linalg.norm(normal))
            if norm <= 1e-12:
                raise HTTPException(status_code=400, detail="A Hookean plane became singular.")
            transformed.append(Hookean(
                int(constraint.index),
                [*(normal / norm), offset / norm],
                rt=constraint.threshold,
                k=constraint.spring,
            ))
    return transformed


def _offset_constraints(constraints: List[Any], offset: int) -> list[Any]:
    shifted: list[Any] = []
    for constraint in constraints:
        if isinstance(constraint, FixAtoms):
            shifted.append(FixAtoms(indices=[int(value) + offset for value in constraint.index]))
        elif isinstance(constraint, FixCartesian):
            shifted.append(FixCartesian(
                [int(value) + offset for value in constraint.index],
                mask=constraint.mask.tolist(),
            ))
        elif isinstance(constraint, FixScaled):
            shifted.append(FixScaled(
                [int(value) + offset for value in constraint.index],
                mask=constraint.mask.tolist(),
            ))
        elif isinstance(constraint, FixedLine):
            shifted.append(FixedLine(
                [int(value) + offset for value in constraint.index],
                constraint.dir,
            ))
        elif isinstance(constraint, FixedPlane):
            shifted.append(FixedPlane(
                [int(value) + offset for value in constraint.index],
                constraint.dir,
            ))
        elif isinstance(constraint, Hookean) and constraint._type == "two atoms":
            shifted.append(Hookean(
                int(constraint.indices[0]) + offset,
                int(constraint.indices[1]) + offset,
                rt=constraint.threshold,
                k=constraint.spring,
            ))
        elif isinstance(constraint, Hookean) and constraint._type == "point":
            shifted.append(Hookean(
                int(constraint.index) + offset,
                constraint.origin,
                rt=constraint.threshold,
                k=constraint.spring,
            ))
        elif isinstance(constraint, Hookean) and constraint._type == "plane":
            shifted.append(Hookean(
                int(constraint.index) + offset,
                constraint.plane,
                rt=constraint.threshold,
                k=constraint.spring,
            ))
    return shifted


def materialize_host_guest_atoms(
    host: Atoms,
    guest: Atoms,
    candidate: Dict[str, Any],
    guest_offset,
) -> Atoms:
    """Materialize a validated host/guest candidate as one ASE structure."""

    host_matrix = np.asarray(candidate["host_matrix_3d"], dtype=int)
    guest_matrix = np.asarray(candidate["guest_matrix_3d"], dtype=int)
    host_super = make_supercell_atoms(host, host_matrix)
    guest_super = make_supercell_atoms(guest, guest_matrix)
    rotation = row_rotation_matrix([0.0, 0.0, 1.0], float(candidate["angle_deg"]))
    host_affine = np.asarray(candidate["host_deformation_matrix"], dtype=float)
    guest_affine = rotation @ np.asarray(candidate["guest_deformation_matrix"], dtype=float)
    offset = np.asarray(guest_offset, dtype=float)
    common_cell = np.asarray(candidate["suggested_cell"], dtype=float)

    host_super.set_positions(host_super.get_positions() @ host_affine, apply_constraint=False)
    guest_super.set_positions(
        guest_super.get_positions() @ guest_affine + offset,
        apply_constraint=False,
    )
    host_constraints = _transform_commensurate_constraints(
        host_super,
        host_affine,
        np.zeros(3),
    )
    guest_constraints = _transform_commensurate_constraints(
        guest_super,
        guest_affine,
        offset,
    )
    host_labels = atom_labels(host_super)
    guest_labels = atom_labels(guest_super)
    host_super.set_constraint()
    guest_super.set_constraint()
    combined = host_super.copy()
    combined.extend(guest_super)
    combined.set_cell(common_cell, scale_atoms=False)
    combined.set_pbc(host.pbc)
    set_atom_labels(combined, [*host_labels, *guest_labels])
    combined.set_constraint([
        *host_constraints,
        *_offset_constraints(guest_constraints, len(host_super)),
    ])
    if host.calc:
        combined.calc = copy_calculator(host.calc)
    else:
        ensure_default_calculator(combined)
    return combined


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


def constraints_for_duplicated_atoms(atoms: Atoms, source_indices: List[int]):
    """Copy constraints whose complete physical subject is duplicated."""

    selected = sorted({int(index) for index in source_indices})
    index_map = {
        old_index: len(atoms) + new_offset
        for new_offset, old_index in enumerate(selected)
    }
    duplicated = []
    for constraint in atoms.constraints or []:
        if isinstance(constraint, FixAtoms):
            indices = [index_map[index] for index in _constraint_indices(constraint, len(atoms)) if index in index_map]
            if indices:
                duplicated.append(FixAtoms(indices=indices))
        elif isinstance(constraint, FixCartesian):
            indices = [index_map[index] for index in _constraint_indices(constraint, len(atoms)) if index in index_map]
            if indices:
                duplicated.append(FixCartesian(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, FixedLine):
            indices = [index_map[index] for index in _constraint_indices(constraint, len(atoms)) if index in index_map]
            if indices:
                duplicated.append(FixedLine(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixedPlane):
            indices = [index_map[index] for index in _constraint_indices(constraint, len(atoms)) if index in index_map]
            if indices:
                duplicated.append(FixedPlane(indices, constraint.dir.tolist()))
        elif isinstance(constraint, FixScaled):
            indices = [index_map[index] for index in _constraint_indices(constraint, len(atoms)) if index in index_map]
            if indices:
                duplicated.append(FixScaled(indices, mask=constraint.mask.tolist()))
        elif isinstance(constraint, Hookean) and constraint._type == "two atoms":
            first, second = [int(value) for value in constraint.indices]
            if first in index_map and second in index_map:
                duplicated.append(Hookean(
                    index_map[first],
                    index_map[second],
                    rt=constraint.threshold,
                    k=constraint.spring,
                ))
        elif isinstance(constraint, Hookean) and constraint._type == "point":
            index = int(constraint.index)
            if index in index_map:
                duplicated.append(Hookean(
                    index_map[index],
                    np.asarray(constraint.origin, dtype=float),
                    rt=constraint.threshold,
                    k=constraint.spring,
                ))
        elif isinstance(constraint, Hookean) and constraint._type == "plane":
            index = int(constraint.index)
            if index in index_map:
                duplicated.append(Hookean(
                    index_map[index],
                    constraint.plane,
                    rt=constraint.threshold,
                    k=constraint.spring,
                ))
    return duplicated


def duplicate_indices_in_atoms(atoms: Atoms, source_indices: List[int]) -> tuple[Atoms, list[int]]:
    """Duplicate atoms in place, retaining every per-atom ASE array and constraint."""

    indices = sorted({int(index) for index in source_indices})
    if not indices:
        return atoms.copy(), []
    if indices[0] < 0 or indices[-1] >= len(atoms):
        raise HTTPException(status_code=400, detail="Duplicate indices are out of range.")

    duplicated_constraints = constraints_for_duplicated_atoms(atoms, indices)
    duplicate = atoms[indices]
    duplicate.set_constraint()
    result = atoms.copy()
    original_constraints = list(result.constraints or [])
    result.set_constraint()
    result.extend(duplicate)
    result.set_constraint([*original_constraints, *duplicated_constraints])
    if isinstance(atoms.calc, SinglePointCalculator):
        copied_results = {}
        for name, value in atoms.calc.results.items():
            if isinstance(value, np.ndarray):
                copied = np.asarray(value).copy()
                if copied.ndim >= 1 and copied.shape[0] == len(atoms):
                    copied = np.concatenate([copied, copied[indices]], axis=0)
                    copied_results[name] = copied
        if copied_results:
            result.calc = SinglePointCalculator(result, **copied_results)
    elif atoms.calc:
        result.calc = copy_calculator(atoms.calc)
    return result, list(range(len(atoms), len(result)))


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
    cutoff_mode=None,
    cutoff_basis=None,
    cutoff_distance=None,
    cutoff_scale=None,
    pair_cutoffs=None,
    k_repulsion=None,
):
    configured = False
    frames = [session.working_atoms, *session.trajectory_frames, *session.original_frames]
    for atoms in frames:
        if is_vase_repulsion_calculator(atoms.calc):
            atoms.calc.configure(
                device=device,
                cpu_threads=cpu_threads,
                cutoff_mode=cutoff_mode,
                cutoff_basis=cutoff_basis,
                cutoff_distance=cutoff_distance,
                cutoff_scale=cutoff_scale,
                pair_cutoffs=pair_cutoffs,
                k_repulsion=k_repulsion,
            )
            configured = True
    return configured

@app.get("/")
async def get_index():
    with open(os.path.join(static_dir, "index.html"), "r") as f:
        return HTMLResponse(f.read())


@app.get("/license", include_in_schema=False)
async def get_license():
    try:
        content = v_ase_license_text()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return HTMLResponse(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v_ase license</title>
  <style>
    body { max-width: 920px; margin: 0 auto; padding: 40px 24px; color: #202523; background: #fff; font: 16px/1.55 system-ui, sans-serif; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { margin: 0 0 28px; color: #4f5955; }
    a { color: #167c6b; }
    pre { overflow: auto; white-space: pre-wrap; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
  </style>
</head>
<body>
  <h1>v_ase</h1>
  <p>Licensed under AGPL-3.0-or-later. <a href="https://github.com/lgyEthan/v_ase">Get the corresponding source.</a></p>
  <pre>"""
        + html.escape(content)
        + """</pre>
</body>
</html>"""
    )


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


def normalize_ai_command(payload: Dict[str, Any]) -> tuple[str, Any, float]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="AI command must be a JSON object.")
    method = str(payload.get("method") or "").strip()
    if method not in _AI_COMMAND_METHODS:
        supported = ", ".join(sorted(_AI_COMMAND_METHODS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported AI command method '{method}'. Supported methods: {supported}.",
        )
    params = payload.get("params", {})
    try:
        timeout = float(
            payload.get("timeout_seconds", _AI_COMMAND_DEFAULT_TIMEOUT_SECONDS)
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="timeout_seconds must be a finite positive number.",
        )
    if not np.isfinite(timeout) or timeout <= 0:
        raise HTTPException(
            status_code=400,
            detail="timeout_seconds must be a finite positive number.",
        )
    return method, params, min(timeout, _AI_COMMAND_MAX_TIMEOUT_SECONDS)


async def wait_for_ai_browser_connection(
    *,
    session_id: str | None = None,
    session_prefix: str | None = None,
) -> None:
    deadline = asyncio.get_running_loop().time() + _AI_COMMAND_CONNECT_TIMEOUT_SECONDS
    while True:
        connected = (
            ws_manager.has_session_connection(session_id)
            if session_id is not None
            else ws_manager.has_connection_prefix(str(session_prefix))
        )
        if connected:
            return
        if asyncio.get_running_loop().time() >= deadline:
            scope = session_id or session_prefix or "requested session"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"No live v_ase browser is connected for {scope}. "
                    "Open human_url and wait for the viewport to load before sending commands."
                ),
            )
        await asyncio.sleep(0.05)


async def dispatch_ai_browser_command(
    payload: Dict[str, Any],
    *,
    session_id: str | None = None,
    session_prefix: str | None = None,
) -> Dict[str, Any]:
    method, params, timeout = normalize_ai_command(payload)
    if method == "schema":
        return {
            "protocol": AI_PROTOCOL,
            "method": method,
            "result": ai_schema_payload(),
        }
    await wait_for_ai_browser_connection(
        session_id=session_id,
        session_prefix=session_prefix,
    )
    command_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    waiter = loop.create_future()
    _ai_command_waiters[command_id] = waiter
    result_url = f"/api/ai/command-result/{command_id}"
    ws_manager.broadcast_sync(
        {
            "type": "ai_command",
            "protocol": AI_PROTOCOL,
            "command_id": command_id,
            "method": method,
            "params": params,
            "result_url": result_url,
        },
        session_id=session_id,
        session_prefix=session_prefix,
    )
    try:
        browser_result = await asyncio.wait_for(waiter, timeout=timeout)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=(
                f"The live browser did not complete AI method '{method}' "
                f"within {timeout:g} seconds."
            ),
        )
    finally:
        _ai_command_waiters.pop(command_id, None)

    if not isinstance(browser_result, dict):
        raise HTTPException(status_code=502, detail="The browser returned an invalid command result.")
    if not browser_result.get("ok"):
        error = browser_result.get("error") or {}
        message = str(
            error.get("message")
            if isinstance(error, dict)
            else error
        ).strip() or f"AI method '{method}' failed in the live browser."
        raise HTTPException(status_code=422, detail=message)
    return {
        "protocol": AI_PROTOCOL,
        "command_id": command_id,
        "method": method,
        "result": browser_result.get("result"),
    }


@app.get("/api/ai/schema")
async def ai_control_schema():
    return ai_schema_payload()


@app.post("/api/ai/command/session/{session_id}")
async def command_ai_document(
    session_id: str,
    payload: Dict[str, Any],
):
    get_session(session_id)
    return await dispatch_ai_browser_command(payload, session_id=session_id)


@app.post("/api/ai/command/workspace/{workspace_id}")
async def command_ai_workspace(
    workspace_id: str,
    payload: Dict[str, Any],
):
    get_workspace(workspace_id)
    return await dispatch_ai_browser_command(
        payload,
        session_prefix=f"workspace:{workspace_id}",
    )


@app.post("/api/ai/command-result/{command_id}")
async def complete_ai_browser_command(
    command_id: str,
    payload: Dict[str, Any],
):
    waiter = _ai_command_waiters.get(str(command_id))
    if waiter is None:
        raise HTTPException(
            status_code=404,
            detail="This AI command is unknown or no longer waiting for a result.",
        )
    if waiter.done():
        raise HTTPException(status_code=409, detail="This AI command already has a result.")
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        raise HTTPException(
            status_code=400,
            detail="AI command result must contain a boolean ok field.",
        )
    waiter.set_result(payload)
    return {"status": "accepted", "command_id": command_id}


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
    workspace_revision = None
    workspace_id = str((session.config or {}).get("workspace_id") or "").strip()
    if workspace_id:
        try:
            workspace_revision = get_workspace(workspace_id).collaboration_revision
        except ValueError:
            workspace_revision = None
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
        "collaboration_revision": int(session.collaboration_revision),
        "workspace_collaboration_revision": workspace_revision,
    }
    return data


def normalize_collaboration_event(
    session: EditorSession,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate a compact browser-originated collaboration notification."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Collaboration event must be an object.")

    source = str(payload.get("source") or "human").strip().lower()
    if source not in {"human", "agent", "system"}:
        raise HTTPException(status_code=400, detail="Event source must be human, agent, or system.")
    event_type = str(payload.get("type") or "state.changed").strip()
    if event_type not in {"state.changed", "session.ready"}:
        raise HTTPException(status_code=400, detail="Unsupported collaboration event type.")

    raw_categories = payload.get("categories") or []
    if not isinstance(raw_categories, list):
        raise HTTPException(status_code=400, detail="Event categories must be an array.")
    categories = []
    for value in raw_categories[:16]:
        category = str(value).strip().lower()
        if category not in COLLABORATION_EVENT_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported collaboration category: {category}",
            )
        if category not in categories:
            categories.append(category)
    if not categories:
        categories = ["state"]

    raw_paths = payload.get("changed_paths") or payload.get("changedPaths") or []
    if not isinstance(raw_paths, list):
        raise HTTPException(status_code=400, detail="changed_paths must be an array.")
    changed_paths = []
    for value in raw_paths[:64]:
        path = str(value).strip()[:160]
        if path and path not in changed_paths:
            changed_paths.append(path)

    summary = str(payload.get("summary") or "Session state changed.").strip()
    summary = summary[:320] or "Session state changed."

    def bounded_int(key: str, fallback: int = 0) -> int:
        try:
            return max(0, int(payload.get(key, fallback)))
        except (TypeError, ValueError):
            return fallback

    return {
        "type": event_type,
        "source": source,
        "categories": categories,
        "changed_paths": changed_paths,
        "summary": summary,
        "document": str(
            payload.get("document")
            or (session.config or {}).get("document_name")
            or "Untitled"
        )[:240],
        "frame": bounded_int("frame", session.current_frame),
        "atom_count": bounded_int("atom_count", len(session.working_atoms)),
        "selection_count": bounded_int("selection_count"),
    }


@app.post("/api/ai/events/{session_id}")
async def publish_ai_collaboration_event(
    session_id: str,
    payload: Dict[str, Any],
):
    session = get_session(session_id)
    event = normalize_collaboration_event(session, payload)
    document_event = session.publish_collaboration_event(event)
    workspace_id = str((session.config or {}).get("workspace_id") or "").strip()
    if workspace_id:
        try:
            get_workspace(workspace_id).publish_collaboration_event(document_event)
        except ValueError:
            pass
    return document_event


@app.get("/api/ai/events/{session_id}")
async def poll_ai_collaboration_events(
    session_id: str,
    after: int = 0,
    timeout: float = 20.0,
):
    session = get_session(session_id)
    normalized_after = max(0, int(after))
    normalized_timeout = max(0.0, min(float(timeout), 30.0))
    return await poll_collaboration_source(
        session,
        normalized_after,
        normalized_timeout,
    )


async def poll_collaboration_source(
    source: Any,
    after_revision: int,
    timeout: float,
) -> Dict[str, Any]:
    """Wait without leaving a blocking worker behind during server shutdown."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while source.collaboration_revision <= after_revision:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        await asyncio.sleep(min(0.1, remaining))
    return source.collaboration_events_after(after_revision, timeout=0)


@app.get("/api/ai/workspace-events/{workspace_id}")
async def poll_ai_workspace_collaboration_events(
    workspace_id: str,
    after: int = 0,
    timeout: float = 20.0,
):
    workspace = get_workspace(workspace_id)
    normalized_after = max(0, int(after))
    normalized_timeout = max(0.0, min(float(timeout), 30.0))
    return await poll_collaboration_source(
        workspace,
        normalized_after,
        normalized_timeout,
    )


@app.post("/api/mode/{session_id}")
async def update_session_mode(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_no_atom_addition(session, "changing View/Edit mode")
    require_no_registry_relaxation(session, "changing View/Edit mode")
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
        frame_atoms = await asyncio.to_thread(session.set_frame, frame_index)
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    positions = frame_atoms.get_positions()
    cell = np.asarray(frame_atoms.cell.array, dtype=float)
    pbc = np.asarray(frame_atoms.pbc, dtype=bool)
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
    if lower_name in {"chg", "chgcar"} or lower_name.startswith(("chg.", "chg_", "chg-", "chgcar.", "chgcar_", "chgcar-")):
        return "vasp-density"
    if lower_name == "locpot" or lower_name.startswith(("locpot.", "locpot_", "locpot-")):
        return "vasp-potential"
    if lower_name == "parchg" or lower_name.startswith(("parchg.", "parchg_", "parchg-")):
        return "vasp-partial-density"
    if lower_name == "elfcar" or lower_name.startswith(("elfcar.", "elfcar_", "elfcar-")):
        return "vasp-elf"
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
    volumetric_precision: str = "float32",
    runtime_mode: str | None = None,
) -> tuple[Dict[str, Any], bool]:
    from .io import (
        read_fast_lammps_dump,
        read_indexed_trajectory,
        read_structure_frames,
        resolve_input_format,
    )

    requested_mode = None
    if runtime_mode is not None and str(runtime_mode).strip():
        requested_mode = str(runtime_mode).strip().lower()
        if requested_mode not in {"view", "edit"}:
            raise HTTPException(
                status_code=400,
                detail="runtime_mode must be 'view' or 'edit'.",
            )
        # Select the reader before parsing.  In particular, View mode must use
        # the virtual LAMMPS trajectory path instead of materializing every
        # frame as editable ASE Atoms first.
        session.config["viz_only"] = requested_mode == "view"

    suffix = Path(display_name).suffix
    format_hint = _uploaded_format_hint(display_name, input_format)
    resolved_format = resolve_input_format(format_hint)
    volumetric_format = resolve_volumetric_format(
        Path(display_name),
        format_hint or resolved_format,
    )
    is_vase_project = (
        suffix.lower() == ".vase"
        or resolved_format == "vase-project"
    )
    is_html_project = (
        suffix.lower() in {".html", ".htm"}
        or resolved_format == "vase-html-project"
    )
    is_project = is_vase_project or is_html_project
    is_lammps_dump = (
        resolved_format == "lammps-dump-text"
        or (format_hint is None and suffix.lower() in {".lammpstrj", ".dump"})
    )
    project = None
    keep_source = False

    if is_project:
        project_reader = read_project_html if is_html_project else read_project_archive
        project = await asyncio.to_thread(project_reader, source_path)
        session.cleanup_temporary_files()
        replace_session_from_project(session, project)
        loaded_kind = "project"
    elif volumetric_format:
        datasets = await asyncio.to_thread(
            read_volumetric_file,
            source_path,
            volumetric_format,
            normalize_volumetric_precision(volumetric_precision),
        )
        structure = volumetric_structure(datasets)
        session.cleanup_temporary_files()
        replace_session_frames(
            session,
            [structure],
            volumetric_datasets=datasets,
        )
        loaded_kind = "volumetric"
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
    elif is_viz_only(session):
        try:
            indexed = await asyncio.to_thread(
                read_indexed_trajectory,
                source_path,
                index,
                format_hint,
            )
        except ValueError as exc:
            LOGGER.info(
                "Indexed trajectory loading is unavailable for %s; "
                "falling back to the general ASE reader: %s",
                display_name,
                exc,
            )
            indexed = None
        if indexed is None:
            frames = await asyncio.to_thread(
                read_structure_frames, source_path, index, format_hint
            )
            session.cleanup_temporary_files()
            replace_session_frames(session, frames)
        else:
            session.cleanup_temporary_files()
            replace_session_frames(
                session,
                [indexed.atoms],
                trajectory_source=indexed.trajectory,
                current_frame=indexed.initial_frame,
            )
            if source_is_temporary:
                source_text = str(source_path)
                session.temporary_files.add(source_text)
                keep_source = True
        loaded_kind = "trajectory" if session.frame_count > 1 else "structure"
    else:
        frames = await asyncio.to_thread(
            read_structure_frames, source_path, index, format_hint
        )
        session.cleanup_temporary_files()
        replace_session_frames(session, frames)
        loaded_kind = "trajectory" if session.frame_count > 1 else "structure"

    if requested_mode is not None:
        switch_session_mode(session, viz_only=requested_mode == "view")
    session.config["empty_workspace"] = False
    session.config["document_name"] = display_name
    data = session_atoms_to_json(session)
    data["loaded_file"] = {
        "filename": display_name,
        "kind": loaded_kind,
        "format": volumetric_format or resolved_format or (
            "vase-html-project" if is_html_project
            else "vase-project" if is_vase_project
            else "auto"
        ),
    }
    if project is not None:
        data["project"] = {
            "schema": project.manifest.get("schema"),
            "settings": project.settings,
        }
    return data, keep_source


def _volumetric_matches_original_structure(
    session: EditorSession,
    dataset,
) -> bool:
    original_cell = np.asarray(session.original_atoms.cell.array, dtype=float)
    original_pbc = np.asarray(session.original_atoms.pbc, dtype=bool)
    return (
        abs(float(np.linalg.det(original_cell))) > 1e-12
        and np.allclose(
            dataset.cell,
            original_cell,
            rtol=GRID_GEOMETRY_RTOL,
            atol=GRID_GEOMETRY_ATOL,
        )
        and np.array_equal(dataset.pbc, original_pbc)
    )


async def _append_session_from_file(
    session: EditorSession,
    source_path: Path,
    display_name: str,
    input_format: str | None,
    index: str,
    volumetric_precision: str = "float32",
) -> Dict[str, Any]:
    from .io import read_fast_lammps_dump, read_structure_frames, resolve_input_format

    suffix = Path(display_name).suffix
    was_empty = bool((session.config or {}).get("empty_workspace", False)) and len(session.working_atoms) == 0
    format_hint = _uploaded_format_hint(display_name, input_format)
    resolved_format = resolve_input_format(format_hint)
    volumetric_format = resolve_volumetric_format(
        Path(display_name),
        format_hint or resolved_format,
    )
    is_vase_project = (
        suffix.lower() == ".vase"
        or resolved_format == "vase-project"
    )
    is_html_project = (
        suffix.lower() in {".html", ".htm"}
        or resolved_format == "vase-html-project"
    )
    is_project = is_vase_project or is_html_project
    is_lammps_dump = (
        resolved_format == "lammps-dump-text"
        or (format_hint is None and suffix.lower() in {".lammpstrj", ".dump"})
    )

    if is_project:
        project_reader = read_project_html if is_html_project else read_project_archive
        project = await asyncio.to_thread(project_reader, source_path)
        selected_indices = _selected_frame_indices(index, len(project.frames))
        frames = [project.frames[frame_index] for frame_index in selected_indices]
        source_kind = "project"
    elif volumetric_format:
        datasets = await asyncio.to_thread(
            read_volumetric_file,
            source_path,
            volumetric_format,
            normalize_volumetric_precision(volumetric_precision),
        )
        with session.mode_transition_lock:
            if was_empty:
                replace_session_frames(
                    session,
                    [volumetric_structure(datasets)],
                    volumetric_datasets=datasets,
                )
                session.config["document_name"] = display_name
                session.config["empty_workspace"] = False
            else:
                reference_cell = np.asarray(session.working_atoms.cell.array, dtype=float)
                reference_pbc = np.asarray(session.working_atoms.pbc, dtype=bool)
                if (
                    abs(float(np.linalg.det(reference_cell))) <= 1e-12
                    or any(
                        not np.allclose(
                            dataset.cell,
                            reference_cell,
                            rtol=GRID_GEOMETRY_RTOL,
                            atol=GRID_GEOMETRY_ATOL,
                        )
                        or not np.array_equal(dataset.pbc, reference_pbc)
                        for dataset in datasets
                    )
                ):
                    raise ValueError(
                        "Added volumetric data must use the current structure's "
                        "unit cell and periodic boundary conditions."
                    )
                if session.frame_count > 1:
                    for dataset in datasets:
                        local_frame = int(dataset.metadata.get("source_frame", 0))
                        dataset.metadata["trajectory_frame"] = min(
                            session.frame_count - 1,
                            session.current_frame + max(0, local_frame),
                        )
                session.volumetric_datasets.extend(datasets)
                session.original_volumetric_datasets.extend(
                    dataset
                    for dataset in datasets
                    if _volumetric_matches_original_structure(session, dataset)
                )
        data = session_atoms_to_json(session)
        data["loaded_file"] = {
            "filename": display_name,
            "kind": "append",
            "source_kind": "volumetric",
            "format": volumetric_format,
            "appended_frames": 0,
            "appended_volumetric_datasets": len(datasets),
            "project_settings_ignored": False,
        }
        return data
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
        "format": resolved_format or (
            "vase-html-project" if is_html_project
            else "vase-project" if is_vase_project
            else "auto"
        ),
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
    volumetric_precision: str = "float32",
    runtime_mode: str | None = None,
):
    """Stream a browser-selected structure, trajectory, or project into a session."""
    session = get_session(session_id)
    require_no_atom_addition(session, "Loading another file")
    require_no_registry_relaxation(session, "Loading another file")
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
            volumetric_precision=volumetric_precision,
            runtime_mode=runtime_mode,
        )
        return data
    except HTTPException:
        raise
    except Exception as exc:
        raise _file_read_http_error("load", display_name, exc) from exc
    finally:
        if not keep_temporary_file:
            _remove_temporary_file(tmp_path)


@app.post("/api/file/load-path/{session_id}")
async def load_structure_path(session_id: str, payload: Dict[str, Any]):
    """Load a file selected from the terminal launch directory."""
    session = get_session(session_id)
    require_no_atom_addition(session, "Loading another file")
    require_no_registry_relaxation(session, "Loading another file")
    source_path = _resolve_launch_path(
        session,
        str(payload.get("path") or ""),
        require_file=True,
    )
    _validate_launch_file_size(source_path)
    display_name = _validated_uploaded_filename(source_path.name)
    input_format = payload.get("input_format") or None
    index = str(payload.get("index") or ":")
    volumetric_precision = str(payload.get("volumetric_precision") or "float32")
    runtime_mode = payload.get("runtime_mode")
    try:
        data, _ = await _replace_session_from_file(
            session,
            source_path,
            display_name,
            str(input_format) if input_format else None,
            index,
            source_is_temporary=False,
            volumetric_precision=volumetric_precision,
            runtime_mode=str(runtime_mode) if runtime_mode is not None else None,
        )
        return data
    except HTTPException:
        raise
    except Exception as exc:
        raise _file_read_http_error("load", display_name, exc) from exc


@app.post("/api/file/append/{session_id}")
async def append_structure_file(
    session_id: str,
    request: Request,
    filename: str,
    input_format: str | None = None,
    index: str = ":",
    volumetric_precision: str = "float32",
):
    """Append uploaded structures as movie frames without replacing visual settings."""
    session = get_session(session_id)
    require_no_atom_addition(session, "Appending trajectory frames")
    require_no_registry_relaxation(session, "Appending trajectory frames")
    display_name = _validated_uploaded_filename(filename)
    tmp_path = await _stream_uploaded_file(request, display_name)
    try:
        return await _append_session_from_file(
            session,
            Path(tmp_path),
            display_name,
            input_format,
            index,
            volumetric_precision,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _file_read_http_error("append", display_name, exc) from exc
    finally:
        _remove_temporary_file(tmp_path)


@app.post("/api/file/append-path/{session_id}")
async def append_structure_path(session_id: str, payload: Dict[str, Any]):
    """Append a file selected from the terminal launch directory."""
    session = get_session(session_id)
    require_no_atom_addition(session, "Appending trajectory frames")
    require_no_registry_relaxation(session, "Appending trajectory frames")
    source_path = _resolve_launch_path(
        session,
        str(payload.get("path") or ""),
        require_file=True,
    )
    _validate_launch_file_size(source_path)
    display_name = _validated_uploaded_filename(source_path.name)
    input_format = payload.get("input_format") or None
    index = str(payload.get("index") or ":")
    volumetric_precision = str(payload.get("volumetric_precision") or "float32")
    try:
        return await _append_session_from_file(
            session,
            source_path,
            display_name,
            str(input_format) if input_format else None,
            index,
            volumetric_precision,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _file_read_http_error("append", display_name, exc) from exc


@app.post("/api/volumetric/difference/{session_id}")
async def create_volumetric_difference(session_id: str, payload: Dict[str, Any]):
    """Create a validated linear combination of loaded scalar fields."""
    session = get_session(session_id)
    dataset_ids = payload.get("dataset_ids") or []
    coefficients = payload.get("coefficients") or []
    if not isinstance(dataset_ids, list) or not isinstance(coefficients, list):
        raise HTTPException(
            status_code=400,
            detail="Volumetric dataset ids and coefficients must be arrays.",
        )
    try:
        with session.mode_transition_lock:
            datasets = [
                dataset_by_id(session.volumetric_datasets, str(dataset_id))
                for dataset_id in dataset_ids
            ]
            combined = combine_volumetric_datasets(
                datasets,
                coefficients,
                name=str(payload.get("name") or "Charge density difference"),
                precision=(
                    normalize_volumetric_precision(payload["precision"])
                    if payload.get("precision")
                    else None
                ),
            )
            session.volumetric_datasets.append(combined)
            if _volumetric_matches_original_structure(session, combined):
                session.original_volumetric_datasets.append(combined)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "ok",
        "dataset": combined.summary(),
        "volumetric_datasets": [
            dataset.summary()
            for dataset in session.volumetric_datasets
        ],
    }


@app.post("/api/volumetric/isosurface/{session_id}")
async def volumetric_isosurface(session_id: str, payload: Dict[str, Any]):
    """Return a compact binary mesh without transferring the source grid."""
    session = get_session(session_id)
    try:
        dataset = dataset_by_id(
            session.volumetric_datasets,
            str(payload.get("dataset_id") or ""),
        )
        mesh = await asyncio.to_thread(
            generate_isosurface,
            dataset,
            float(payload.get("level")),
            step_size=int(payload.get("step_size", 1)),
            smearing_sigma=float(payload.get("smearing_sigma", 0.0)),
            smoothing_iterations=payload.get("smoothing_iterations", 4),
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=mesh.binary(),
        media_type="application/vnd.v-ase.isosurface",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/volumetric/plane/{session_id}")
async def volumetric_plane(session_id: str, payload: Dict[str, Any]):
    """Return one compact, cell-clipped scalar plane without the source grid."""
    session = get_session(session_id)
    try:
        dataset = dataset_by_id(
            session.volumetric_datasets,
            str(payload.get("dataset_id") or ""),
        )
        plane = await asyncio.to_thread(
            generate_volumetric_plane,
            dataset,
            payload.get("hkl") or [0, 0, 1],
            float(payload.get("offset_angstrom", 0.0)),
            repetitions=payload.get("repetitions") or [1, 1, 1],
            resolution=int(payload.get("resolution", 256)),
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=plane.binary(),
        media_type="application/vnd.v-ase.volumetric-plane",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/volumetric/delete/{session_id}")
async def delete_volumetric_dataset(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    dataset_id = str(payload.get("dataset_id") or "")
    with session.mode_transition_lock:
        retained = [
            dataset
            for dataset in session.volumetric_datasets
            if dataset.dataset_id != dataset_id
        ]
        if len(retained) == len(session.volumetric_datasets):
            raise HTTPException(status_code=404, detail="Volumetric dataset was not found.")
        session.volumetric_datasets = retained
        session.original_volumetric_datasets = [
            dataset
            for dataset in session.original_volumetric_datasets
            if dataset.dataset_id != dataset_id
        ]
    return {
        "status": "ok",
        "volumetric_datasets": [
            dataset.summary()
            for dataset in retained
        ],
    }


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


def _suggested_guest_offset(
    host: Atoms,
    guest: Atoms,
    separation: float = 3.0,
) -> list[float]:
    if not len(host) or not len(guest):
        return [0.0, 0.0, 0.0]
    separation = max(0.0, float(separation))
    return [
        0.0,
        0.0,
        float(np.max(host.positions[:, 2]) - np.min(guest.positions[:, 2]) + separation),
    ]


def _read_commensurate_guest_structure(
    source_path: Path,
    display_name: str,
    input_format: str | None = None,
) -> Atoms:
    """Read and validate one independent in-plane guest structure."""

    from .commensurate import project_periodic_lattice
    from .io import read_structure_frames, resolve_input_format

    format_hint = _uploaded_format_hint(display_name, input_format or None)
    resolved = resolve_input_format(format_hint)
    if resolved in {"vase-project", "vase-html-project"}:
        raise ValueError("Load a structure file, not a v_ase project, as the guest lattice.")
    frames = read_structure_frames(source_path, "0", resolved)
    if not frames:
        raise ValueError("The guest file contains no readable structure.")
    guest = frames[0]
    if len(guest) < 1:
        raise ValueError("The guest structure contains no atoms.")
    projected = project_periodic_lattice(guest.cell.array, guest.pbc, "Z")
    if projected.axis_alignment < 0.985:
        raise ValueError(
            "Guest matching requires two periodic cell vectors in the global XY plane."
        )
    return guest


def _set_commensurate_guest(
    session: EditorSession,
    guest: Atoms,
    display_name: str,
) -> Dict[str, Any]:
    session.commensurate_guest_atoms = copy_atoms_with_calc(guest, attach_default=False)
    session.commensurate_guest_name = display_name
    session.commensurate_search_cache = None
    return {
        "status": "ok",
        "guest": {
            "name": display_name,
            "atoms": atoms_to_json(session.commensurate_guest_atoms),
            "min_z": float(np.min(session.commensurate_guest_atoms.positions[:, 2])),
            "max_z": float(np.max(session.commensurate_guest_atoms.positions[:, 2])),
            "default_gap": 3.0,
            "suggested_offset": _suggested_guest_offset(
                session.working_atoms,
                session.commensurate_guest_atoms,
            ),
        },
    }


def _enrich_commensurate_preview_visuals(
    geometry: Dict[str, Any],
    host: Atoms,
    guest: Atoms | None = None,
) -> Dict[str, Any]:
    if not geometry.get("positions"):
        return geometry
    serialized = {"host": atoms_to_json(host), "reference": atoms_to_json(host), "rotating": atoms_to_json(host)}
    if guest is not None:
        serialized["guest"] = atoms_to_json(guest)
    labels: list[str] = []
    chemical_symbols: list[str] = []
    colors: list[str] = []
    radii: list[float] = []
    bond_radii: list[float] = []
    for atom_index, component in zip(geometry["atom_indices"], geometry["components"]):
        source = serialized.get(str(component), serialized["host"])
        index = int(atom_index)
        labels.append(str(source["symbols"][index]))
        chemical_symbols.append(str(source["chemical_symbols"][index]))
        colors.append(str(source["visual"]["colors"][index]))
        radii.append(float(source["visual"]["radii"][index]))
        bond_radii.append(float(source["visual"]["bond_radii"][index]))
    return {
        **geometry,
        "labels": labels,
        "chemical_symbols": chemical_symbols,
        "colors": colors,
        "radii": radii,
        "bond_radii": bond_radii,
    }


@app.post("/api/commensurate/guest/{session_id}")
async def load_commensurate_guest(
    session_id: str,
    request: Request,
    filename: str = "guest.xyz",
    input_format: str = "",
):
    """Load one independent guest structure for interface-cell matching."""

    session = get_session(session_id)
    display_name = _validated_uploaded_filename(filename)
    temporary = await _stream_uploaded_file(request, display_name)
    try:
        guest = await asyncio.to_thread(
            _read_commensurate_guest_structure,
            temporary,
            display_name,
            input_format or None,
        )
        return _set_commensurate_guest(session, guest, display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        _remove_temporary_file(temporary)


@app.post("/api/commensurate/guest-path/{session_id}")
async def load_commensurate_guest_path(session_id: str, payload: Dict[str, Any]):
    """Load a guest structure from the terminal launch directory for agents."""

    session = get_session(session_id)
    source_path = _resolve_launch_path(
        session,
        str(payload.get("path") or ""),
        require_file=True,
    )
    _validate_launch_file_size(source_path)
    display_name = _validated_uploaded_filename(source_path.name)
    try:
        guest = await asyncio.to_thread(
            _read_commensurate_guest_structure,
            source_path,
            display_name,
            str(payload.get("input_format") or "") or None,
        )
        return _set_commensurate_guest(session, guest, display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/commensurate/guest/remove/{session_id}")
async def remove_commensurate_guest(session_id: str):
    session = get_session(session_id)
    session.commensurate_guest_atoms = None
    session.commensurate_guest_name = None
    session.commensurate_search_cache = None
    return {"status": "ok", "guest": None}


@app.post("/api/commensurate/{session_id}")
async def commensurate_rotation_candidates(session_id: str, payload: Dict[str, Any]):
    """Return bounded same-lattice or host/guest periodic-cell matches."""
    session = get_session(session_id)
    sync_session_frame_from_payload(session, payload)
    job_id = str(payload.get("job_id") or uuid.uuid4())

    def progress(value: float, stage: str) -> None:
        ws_manager.broadcast_sync({
            "type": "analysis_progress",
            "analysis": "commensurate",
            "job_id": job_id,
            "progress": float(value),
            "stage": str(stage),
        }, session_id=session_id)

    try:
        result = await asyncio.to_thread(
            _run_commensurate_search,
            session,
            payload,
            progress,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["job_id"] = job_id
    result["guest"] = (
        {
            "name": session.commensurate_guest_name or "Guest structure",
            "natoms": len(session.commensurate_guest_atoms),
            "min_z": float(np.min(session.commensurate_guest_atoms.positions[:, 2])),
            "max_z": float(np.max(session.commensurate_guest_atoms.positions[:, 2])),
            "default_gap": 3.0,
            "suggested_offset": _suggested_guest_offset(
                session.working_atoms,
                session.commensurate_guest_atoms,
            ),
        }
        if session.commensurate_guest_atoms is not None
        else None
    )
    session.commensurate_search_cache = {
        "signature": _commensurate_search_signature(session, payload),
        "result": result,
    }
    return result


@app.post("/api/commensurate/preview/{session_id}")
async def preview_commensurate_supercell(session_id: str, payload: Dict[str, Any]):
    """Build a separate common-cell preview without mutating ASE state."""

    session = get_session(session_id)
    sync_session_frame_from_payload(session, payload)
    atoms = session.working_atoms.copy()
    if payload.get("positions") is not None:
        positions = np.asarray(payload["positions"], dtype=float)
        if positions.shape != (len(atoms), 3) or not np.all(np.isfinite(positions)):
            raise HTTPException(status_code=400, detail="Preview positions must match the current atom count.")
        atoms.set_positions(positions, apply_constraint=False)
    candidate, search = resolve_commensurate_candidate(session, payload)
    mode = str(search.get("mode") or "same-lattice")
    selected = [int(value) for value in payload.get("selected_indices", [])]
    pivot = payload.get("pivot", [0.0, 0.0, 0.0])
    try:
        if mode == "host-guest":
            guest = session.commensurate_guest_atoms
            if guest is None:
                raise ValueError("The guest structure is no longer loaded.")
            geometry = await asyncio.to_thread(
                host_guest_supercell_geometry,
                host_cell=atoms.cell.array,
                host_positions=atoms.get_positions(),
                guest_cell=guest.cell.array,
                guest_positions=guest.get_positions(),
                candidate=candidate,
                guest_offset=payload.get(
                    "guest_offset",
                    _suggested_guest_offset(atoms, guest),
                ),
                padding_cells=1,
                include_atoms=bool(payload.get("show_atoms", False)),
                display_angle_deg=payload.get("display_angle_deg"),
                parent_lattice_preview=True,
                parent_grid_radius=max(2, min(64, int(payload.get("parent_grid_radius", 4)))),
            )
            geometry = _enrich_commensurate_preview_visuals(geometry, atoms, guest)
        else:
            geometry = await asyncio.to_thread(
                commensurate_supercell_geometry,
                cell=atoms.cell.array,
                positions=atoms.get_positions(),
                selected_indices=selected,
                candidate=candidate,
                pivot=pivot,
                padding_cells=1,
                include_atoms=bool(payload.get("show_atoms", False)),
                display_angle_deg=payload.get("display_angle_deg"),
                positions_include_display_rotation=bool(
                    payload.get("positions_include_display_rotation", True)
                ),
                parent_lattice_preview=True,
                parent_grid_radius=max(2, min(64, int(payload.get("parent_grid_radius", 4)))),
            )
            geometry = _enrich_commensurate_preview_visuals(geometry, atoms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    materialization_reason = None
    if session.frame_count > 1 or session.trajectory_source is not None:
        materialization_reason = (
            "Preview is available, but materialization is disabled for trajectories because "
            "each frame may require an independently validated layer mapping."
        )
    elif session.volumetric_datasets:
        materialization_reason = (
            "Remove volumetric datasets before materializing a layer-specific commensurate cell."
        )
    return {
        "status": "ok",
        "candidate": candidate,
        "search": {
            "axis": search["axis"],
            "mode": mode,
            "lattice_family": search["lattice_family"],
            "strain_tolerance": search["strain_tolerance"],
            "max_area_ratio": int(payload.get("max_area_ratio", 16)),
        },
        "preview": geometry,
        "materialization_supported": materialization_reason is None,
        "materialization_reason": materialization_reason,
    }


@app.post("/api/commensurate/apply/{session_id}")
async def apply_commensurate_supercell(session_id: str, payload: Dict[str, Any]):
    """Materialize a validated two-component common cell as editable ASE atoms."""

    session = get_session(session_id)
    require_editable(session, "Applying a commensurate common cell")
    if session.frame_count > 1 or session.trajectory_source is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Commensurate cell materialization currently requires a single structure; "
                "the opaque preview remains available for trajectories."
            ),
        )
    if session.volumetric_datasets:
        raise HTTPException(
            status_code=400,
            detail="Remove volumetric datasets before applying a layer-specific commensurate cell.",
        )
    sync_session_frame_from_payload(session, payload)
    set_current_payload_positions(session, payload)
    atoms = session.working_atoms
    candidate, search = resolve_commensurate_candidate(session, payload)
    selected = [int(value) for value in payload.get("selected_indices", [])]
    pivot = payload.get("pivot", [0.0, 0.0, 0.0])
    mode = str(search.get("mode") or "same-lattice")
    session.push_history(include_trajectory=True)
    if mode == "host-guest":
        guest = session.commensurate_guest_atoms
        if guest is None:
            raise HTTPException(status_code=400, detail="The guest structure is no longer loaded.")
        transformed = materialize_host_guest_atoms(
            atoms,
            guest,
            candidate,
            payload.get("guest_offset", _suggested_guest_offset(atoms, guest)),
        )
        session.commensurate_guest_atoms = None
        session.commensurate_guest_name = None
    else:
        try:
            geometry = await asyncio.to_thread(
                commensurate_supercell_geometry,
                cell=atoms.cell.array,
                positions=atoms.get_positions(),
                selected_indices=selected,
                candidate=candidate,
                pivot=pivot,
                padding_cells=0,
                include_atoms=True,
                display_angle_deg=payload.get("display_angle_deg"),
                positions_include_display_rotation=bool(
                    payload.get("positions_include_display_rotation", True)
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        transformed = materialize_commensurate_atoms(atoms, geometry, candidate, selected, pivot)
    session.working_atoms = transformed
    session.commensurate_search_cache = None
    session.sync_current_frame()
    session.invalidate_trajectory_layout()
    session.refresh_trajectory_identity()
    return session_update_to_json(session)

@app.post("/api/apply/{session_id}")
async def apply_positions(session_id: str, payload: Dict[str, Any]):
    """COMMIT: Backend state update with authoritative constraints."""
    session = get_session(session_id)
    require_editable(session, "Atom coordinate editing", allow_atom_addition=True)
    sync_session_frame_from_payload(session, payload)
    positions = np.array(payload["positions"])
    if session.atom_addition is not None:
        try:
            apply_atom_addition_positions(session, positions)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return session_update_to_json(session)

    session.push_history()
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
    session.push_history(
        include_trajectory=True,
        include_volumetric=bool(session.volumetric_datasets),
    )
    session.reset_all_frames()
    return session_update_to_json(session)


@app.post("/api/reset-coordinates/{session_id}")
async def reset_coordinates(session_id: str, payload: Dict[str, Any] | None = None):
    session = get_session(session_id)
    require_editable(session, "Coordinate reset")
    sync_session_frame_from_payload(session, payload)
    session.push_history(
        include_trajectory=True,
        include_volumetric=bool(session.volumetric_datasets),
    )
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
    if len(raw) > 512 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Visual settings file is too large.")
    stripped = raw.lstrip()
    if stripped.startswith((b"<!doctype html", b"<html")) or b'v-ase-project-data' in raw[:2 * 1024 * 1024]:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temporary:
                temporary.write(raw)
                temporary_path = temporary.name
            project = read_project_html(temporary_path)
            return {
                "schema": SETTINGS_SCHEMA,
                "settings": normalize_visual_settings(project.settings),
            }
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"This HTML file does not contain an importable v_ase project preset: {exc}",
            ) from exc
        finally:
            if temporary_path:
                with suppress(OSError):
                    Path(temporary_path).unlink()
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


@app.get("/api/preferences/visual-defaults/{session_id}")
async def get_user_visual_defaults(session_id: str):
    get_session(session_id)
    settings = load_visual_defaults()
    return {
        "schema": PREFERENCES_SCHEMA,
        "configured": settings is not None,
        "settings": settings,
    }


@app.post("/api/preferences/visual-defaults/{session_id}")
async def set_user_visual_defaults(session_id: str, payload: Dict[str, Any]):
    get_session(session_id)
    try:
        settings = normalize_visual_settings(payload.get("settings", payload))
        saved = save_visual_defaults(settings)
    except (OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "schema": PREFERENCES_SCHEMA,
        "configured": True,
        "settings": saved,
    }


@app.delete("/api/preferences/visual-defaults/{session_id}")
async def delete_user_visual_defaults(session_id: str):
    get_session(session_id)
    try:
        removed = clear_visual_defaults()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not clear user defaults: {exc}") from exc
    return {
        "schema": PREFERENCES_SCHEMA,
        "configured": False,
        "removed": removed,
        "settings": None,
    }


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
    require_no_atom_addition(session, "Loading a project")
    require_no_registry_relaxation(session, "Loading a project")
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
    require_editable(session, "Undo", allow_atom_addition=True)
    atoms = session.undo()
    if atoms is not None:
        session.sync_current_frame()
    return session_update_to_json(session)


@app.post("/api/redo/{session_id}")
async def redo(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Redo", allow_atom_addition=True)
    atoms = session.redo()
    if atoms is not None:
        session.sync_current_frame()
    return session_update_to_json(session)


@app.get("/api/add-session/molecules/{session_id}")
async def atom_addition_molecule_catalog(session_id: str):
    get_session(session_id)
    return {"molecules": [dict(entry) for entry in molecule_catalog()]}


@app.post("/api/add-session/pairs/{session_id}")
async def atom_addition_pair_cutoffs(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Random atom insertion", allow_atom_addition=True)
    elements = list(session.working_atoms.get_chemical_symbols())
    elements.extend(payload.get("elements") or [])
    if payload.get("molecules"):
        try:
            entries = normalize_molecule_entries({"molecules": payload.get("molecules")})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        elements.extend(molecule_entry_elements(entries))
    if not elements:
        elements = ["H"]
    return {
        "basis": str(payload.get("basis") or "covalent").lower(),
        "scale": float(payload.get("scale", 1.0)),
        "pair_cutoffs": default_pair_cutoffs(
            elements,
            basis=payload.get("basis") or "covalent",
            scale=payload.get("scale", 1.0),
        ),
    }


@app.post("/api/add-session/domain/{session_id}")
async def atom_addition_domain(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Insertion-domain preview", allow_atom_addition=True)
    try:
        return await asyncio.to_thread(
            atom_addition_domain_preview,
            session.working_atoms,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/add-session/start/{session_id}")
async def start_random_atom_addition(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Random atom insertion", allow_atom_addition=True)
    sync_session_frame_from_payload(session, payload)
    try:
        addition = await asyncio.to_thread(start_atom_addition, session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = session_update_to_json(session)
    data["metadata"]["atom_addition"].update({
        "sampling": addition.get("sampling") or {},
    })
    return data


@app.post("/api/add-session/relax/{session_id}")
async def relax_random_atom_addition(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Random atom insertion", allow_atom_addition=True)
    try:
        return start_atom_addition_relaxation(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/add-session/region/{session_id}")
async def update_random_atom_addition_region(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Random atom insertion", allow_atom_addition=True)
    try:
        summary = update_atom_addition_region(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    data = session_update_to_json(session)
    data["metadata"]["atom_addition"] = summary
    return data


@app.post("/api/add-session/stop/{session_id}")
async def stop_random_atom_addition(session_id: str):
    session = get_session(session_id)
    return {"status": "stopping" if stop_atom_addition_relaxation(session) else "idle"}


@app.post("/api/add-session/finish/{session_id}")
async def finish_random_atom_addition(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Random atom insertion", allow_atom_addition=True)
    try:
        result = finish_atom_addition(session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    data = session_update_to_json(session)
    data["metadata"]["atom_addition_result"] = result
    return data


@app.post("/api/add-session/cancel/{session_id}")
async def cancel_random_atom_addition(session_id: str):
    session = get_session(session_id)
    require_editable(session, "Random atom insertion", allow_atom_addition=True)
    cancel_atom_addition(session)
    return session_update_to_json(session)


@app.post("/api/add/{session_id}")
async def add_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Adding atoms")
    require_no_atom_addition(session, "adding a separate atom")
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
    session.config["empty_workspace"] = False
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


@app.post("/api/duplicate/{session_id}")
async def duplicate_atoms(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Duplicating atoms")
    require_no_atom_addition(session, "duplicating atoms")
    sync_session_frame_from_payload(session, payload)
    indices = payload.get("indices", [])
    if not indices:
        return session_update_to_json(session)

    session.push_history()
    session.working_atoms, new_indices = duplicate_indices_in_atoms(
        session.working_atoms,
        indices,
    )
    session.config["empty_workspace"] = False
    session.invalidate_trajectory_layout()
    session.sync_current_frame()
    session.refresh_trajectory_identity()
    data = session_update_to_json(session)
    data["duplicated_indices"] = new_indices
    return data


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
    require_editable(session, "Repulsion calculator settings")
    sync_session_frame_from_payload(session, payload)
    if not is_vase_repulsion_calculator(session.working_atoms.calc):
        raise HTTPException(
            status_code=400,
            detail="These settings are only available for the default repulsion calculator.",
        )
    configure_repulsion_calculators(
        session,
        device=payload.get("device"),
        cpu_threads=payload.get("cpu_threads"),
        cutoff_mode=payload.get("cutoff_mode"),
        cutoff_basis=payload.get("cutoff_basis"),
        cutoff_distance=payload.get("cutoff_distance"),
        cutoff_scale=payload.get("cutoff_scale"),
        pair_cutoffs=payload.get("pair_cutoffs"),
        k_repulsion=payload.get("k_repulsion"),
    )
    session.sync_current_frame()
    return session_update_to_json(session)


@app.post("/api/frame/{session_id}")
async def set_frame(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_no_atom_addition(session, "changing trajectory frames")
    require_no_registry_relaxation(session, "changing trajectory frames")
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


def _atom_scalar_frame_atoms(session: EditorSession, frame_index: int):
    if frame_index == session.current_frame:
        return session.working_atoms.copy()
    return _analysis_frame_atoms(session, frame_index)


def _stored_atom_property_frame_atoms(session: EditorSession, frame_index: int):
    """Return a lock-protected frame without dropping its stored calculator."""

    if frame_index < 0 or frame_index >= session.frame_count:
        raise IndexError(
            f"Frame index {frame_index} is out of range for {session.frame_count} frames."
        )
    if frame_index == session.current_frame:
        return session.working_atoms
    if session.trajectory_source is not None:
        return session.trajectory_source.read_atoms(frame_index)
    if session.trajectory_frames:
        return session.trajectory_frames[frame_index]
    if frame_index == 0:
        return session.working_atoms
    raise IndexError("The requested trajectory frame is unavailable.")


def _fast_trajectory_scalar_values(
    session: EditorSession,
    frame_index: int,
    field_id: str,
):
    reader = getattr(session.trajectory_source, "read_scalar_values", None)
    if not callable(reader):
        return None
    return reader(frame_index, field_id)


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


@app.get("/api/analysis/atom-scalars/catalog/{session_id}")
async def per_atom_scalar_catalog(session_id: str, frame_index: int | None = None):
    session = get_session(session_id)

    def discover():
        with session.mode_transition_lock:
            index = session.current_frame if frame_index is None else int(frame_index)
            atoms = _atom_scalar_frame_atoms(session, index)
            return {
                "frame_index": index,
                "atom_count": len(atoms),
                "fields": atom_scalar_catalog(atoms),
            }

    try:
        return await asyncio.to_thread(discover)
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analysis/atom-properties/{session_id}/{atom_index}")
async def per_atom_properties(
    session_id: str,
    atom_index: int,
    frame_index: int | None = None,
):
    """Return one atom's stored ASE arrays and calculator results lazily."""

    session = get_session(session_id)

    def inspect():
        with session.mode_transition_lock:
            index = session.current_frame if frame_index is None else int(frame_index)
            atoms = _stored_atom_property_frame_atoms(session, index)
            if atom_index < 0 or atom_index >= len(atoms):
                raise IndexError(
                    f"Atom index {atom_index} is out of range for frame {index} "
                    f"with {len(atoms)} atoms."
                )
            return {
                "frame_index": index,
                "atom_index": int(atom_index),
                "atom_count": len(atoms),
                "properties": atom_property_snapshot(atoms, atom_index),
            }

    try:
        return await asyncio.to_thread(inspect)
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _session_atom_scalar_values(session: EditorSession, payload: Dict[str, Any]):
    field_id = str(payload.get("field_id") or "").strip()
    if not field_id:
        raise ValueError("field_id is required.")
    requested_frame = int(payload.get("frame_index", session.current_frame))
    requested_all_frames = bool(payload.get("all_frames", False))

    with session.mode_transition_lock:
        current_atoms = None
        atom_count = (
            int(session.trajectory_source.natoms)
            if session.trajectory_source is not None
            and hasattr(session.trajectory_source, "natoms")
            else len(_atom_scalar_frame_atoms(session, requested_frame))
        )
        can_cache_trajectory = (
            requested_all_frames
            and session.frame_count > 1
            and trajectory_layout_compatible(session)
            and session.frame_count * atom_count <= MAX_ATOM_SCALAR_CACHE_VALUES
        )
        if not can_cache_trajectory:
            fast_values = _fast_trajectory_scalar_values(session, requested_frame, field_id)
            if fast_values is not None:
                return requested_frame, np.asarray(fast_values, dtype=np.float32).reshape(1, atom_count)
            current_atoms = _atom_scalar_frame_atoms(session, requested_frame)
            try:
                values = atom_scalar_values(current_atoms, field_id).reshape(1, atom_count)
            except ValueError:
                # A field may be absent from one trajectory frame. Keep its
                # identity/range stable and render that frame as uncolored.
                values = np.full((1, atom_count), np.nan, dtype=np.float32)
            return requested_frame, values

        values = np.full((session.frame_count, atom_count), np.nan, dtype=np.float32)
        for index in range(session.frame_count):
            fast_values = _fast_trajectory_scalar_values(session, index, field_id)
            if fast_values is not None:
                values[index] = fast_values
                continue
            atoms = _atom_scalar_frame_atoms(session, index)
            if len(atoms) != atom_count:
                raise ValueError("Trajectory atom counts differ; this field cannot be cached across frames.")
            try:
                values[index] = atom_scalar_values(atoms, field_id)
            except ValueError:
                # Calculator and custom arrays may be absent from individual frames.
                # NaN keeps those frames explicit instead of substituting misleading data.
                continue
        return 0, values


@app.post("/api/analysis/atom-scalars/values/{session_id}")
async def per_atom_scalar_values(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    try:
        start_frame, values = await asyncio.to_thread(_session_atom_scalar_values, session, payload)
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    packed = np.asarray(values, dtype=np.float32, order="C")
    return Response(
        content=packed.tobytes(order="C"),
        media_type="application/octet-stream",
        headers={
            "X-V-Ase-Frames": str(packed.shape[0]),
            "X-V-Ase-Atoms": str(packed.shape[1]),
            "X-V-Ase-Start-Frame": str(start_frame),
            "X-V-Ase-Dtype": "float32",
            "X-V-Ase-Cache": "trajectory" if packed.shape[0] > 1 else "frame",
        },
    )


def _session_force_vector_values(session: EditorSession, payload: Dict[str, Any]):
    requested_frame = int(payload.get("frame_index", session.current_frame))
    requested_all_frames = bool(payload.get("all_frames", False))

    with session.mode_transition_lock:
        current_atoms = _atom_scalar_frame_atoms(session, requested_frame)
        atom_count = len(current_atoms)
        can_cache_trajectory = (
            requested_all_frames
            and session.frame_count > 1
            and trajectory_layout_compatible(session)
            and session.frame_count * atom_count * 3 <= MAX_FORCE_VECTOR_CACHE_VALUES
        )
        frame_indices = range(session.frame_count) if can_cache_trajectory else (requested_frame,)
        start_frame = 0 if can_cache_trajectory else requested_frame
        values = np.full((len(frame_indices), atom_count, 3), np.nan, dtype=np.float32)
        for output_index, frame_index in enumerate(frame_indices):
            fast_reader = getattr(session.trajectory_source, "read_force_vectors", None)
            vectors = None
            if callable(fast_reader) and frame_index != session.current_frame:
                vectors = fast_reader(frame_index)
            if vectors is None:
                atoms = current_atoms if frame_index == requested_frame else _atom_scalar_frame_atoms(
                    session, frame_index
                )
                if len(atoms) != atom_count:
                    raise ValueError(
                        "Trajectory atom counts differ; force vectors cannot be cached across frames."
                    )
                vectors = atom_force_vectors(atoms)
            if vectors is not None:
                values[output_index] = vectors
        return start_frame, values


@app.post("/api/analysis/force-vectors/{session_id}")
async def per_atom_force_vectors(session_id: str, payload: Dict[str, Any]):
    """Return stored frame forces as compact float32 Cartesian vectors."""

    session = get_session(session_id)
    try:
        start_frame, values = await asyncio.to_thread(
            _session_force_vector_values, session, payload
        )
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    packed = np.asarray(values, dtype=np.float32, order="C")
    return Response(
        content=packed.tobytes(order="C"),
        media_type="application/octet-stream",
        headers={
            "X-V-Ase-Frames": str(packed.shape[0]),
            "X-V-Ase-Atoms": str(packed.shape[1]),
            "X-V-Ase-Start-Frame": str(start_frame),
            "X-V-Ase-Dtype": "float32",
            "X-V-Ase-Cache": "trajectory" if packed.shape[0] > 1 else "frame",
        },
    )


def _session_atom_scalar_range(session: EditorSession, payload: Dict[str, Any]):
    field_id = str(payload.get("field_id") or "").strip()
    if not field_id:
        raise ValueError("field_id is required.")
    requested_frame = int(payload.get("frame_index", session.current_frame))
    requested_all_frames = bool(payload.get("all_frames", False))
    requested_indices = payload.get("indices")

    with session.mode_transition_lock:
        current_atoms = _atom_scalar_frame_atoms(session, requested_frame)
        if requested_indices is None:
            selected = None
        else:
            if not isinstance(requested_indices, list):
                raise ValueError("indices must be a list when a selected-atom range is requested.")
            selected = np.asarray(sorted({int(index) for index in requested_indices}), dtype=np.int64)
            if selected.size == 0:
                raise ValueError("Select at least one atom before fitting a selected-atom color range.")
            if selected[0] < 0 or selected[-1] >= len(current_atoms):
                raise ValueError("A selected atom index is outside the current structure.")

        frame_indices = (
            range(session.frame_count)
            if requested_all_frames and session.frame_count > 1
            else (requested_frame,)
        )
        minimum = np.inf
        maximum = -np.inf
        finite_count = 0
        frames_with_values = 0
        missing_frames = 0

        for index in frame_indices:
            fast_values = _fast_trajectory_scalar_values(session, index, field_id)
            if fast_values is not None:
                values = np.asarray(fast_values, dtype=np.float64)
            else:
                atoms = _atom_scalar_frame_atoms(session, index)
                try:
                    values = np.asarray(atom_scalar_values(atoms, field_id), dtype=np.float64)
                except ValueError:
                    missing_frames += 1
                    continue
            if selected is not None:
                valid = selected[selected < values.shape[0]]
                if valid.size == 0:
                    missing_frames += 1
                    continue
                values = values[valid]
            finite = values[np.isfinite(values)]
            if finite.size == 0:
                missing_frames += 1
                continue
            frames_with_values += 1
            finite_count += int(finite.size)
            minimum = min(minimum, float(np.min(finite)))
            maximum = max(maximum, float(np.max(finite)))

        if finite_count == 0:
            target = "trajectory" if requested_all_frames else "current frame"
            raise ValueError(f"The selected per-atom property has no finite values in the {target}.")
        if minimum == maximum:
            padding = max(1e-12, abs(minimum) * 1e-6)
            minimum -= padding
            maximum += padding
        return {
            "field_id": field_id,
            "scope": "selected" if selected is not None else "all",
            "range_mode": "trajectory" if requested_all_frames and session.frame_count > 1 else "current",
            "minimum": minimum,
            "maximum": maximum,
            "finite_values": finite_count,
            "frames_scanned": len(frame_indices),
            "frames_with_values": frames_with_values,
            "missing_frames": missing_frames,
        }


@app.post("/api/analysis/atom-scalars/range/{session_id}")
async def per_atom_scalar_range(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    try:
        return await asyncio.to_thread(_session_atom_scalar_range, session, payload)
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analysis/colormaps/{session_id}")
async def registered_colormaps(session_id: str):
    get_session(session_id)
    return await asyncio.to_thread(colormap_catalog)


@app.post("/api/analysis/colormaps/{session_id}")
async def sampled_colormap(session_id: str, payload: Dict[str, Any]):
    get_session(session_id)
    try:
        return await asyncio.to_thread(
            colormap_lut,
            str(payload.get("name") or "viridis"),
            int(payload.get("samples", 256)),
            bool(payload.get("reverse", False)),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _calculate_session_rdf(session: EditorSession, payload: Dict[str, Any]):
    with session.mode_transition_lock:
        frame_index = int(payload.get("frame_index", session.current_frame))
        # Analysis requests must not move the live editor session. This also
        # permits trajectory RDF frames to be prefetched safely while the GUI
        # remains on the frame chosen by the user.
        atoms = _atom_scalar_frame_atoms(session, frame_index)
    supplied_positions = payload.get("positions")
    if supplied_positions is not None:
        positions = np.asarray(supplied_positions, dtype=float)
        if positions.shape != (len(atoms), 3) or not np.all(np.isfinite(positions)):
            raise ValueError("Displayed RDF positions must contain one finite xyz row per atom.")
        atoms.set_positions(positions, apply_constraint=False)
    requested_cutoff = payload.get("cutoff")
    cutoff = (
        None
        if requested_cutoff is None or requested_cutoff == ""
        else float(requested_cutoff)
    )
    return calculate_rdf(
        atoms,
        cutoff=cutoff,
        bins=int(payload.get("bins", 200)),
        pair_mode=str(payload.get("pair_mode") or "active"),
        active_pairs=payload.get("active_pairs") or [],
        frame_index=frame_index,
    )


@app.post("/api/analysis/rdf/{session_id}")
async def radial_distribution_analysis(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    try:
        result = await asyncio.to_thread(_calculate_session_rdf, session, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.payload()


@app.post("/api/analysis/rdf-csv/{session_id}")
async def radial_distribution_csv(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    try:
        result = await asyncio.to_thread(_calculate_session_rdf, session, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=rdf_csv(result),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="v_ase_rdf.csv"'},
    )


@app.post("/api/analysis/commensurate-csv/{session_id}")
async def commensurate_candidate_csv(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    try:
        signature = _commensurate_search_signature(session, payload)
        cached = session.commensurate_search_cache or {}
        result = (
            cached["result"]
            if cached.get("signature") == signature and isinstance(cached.get("result"), dict)
            else await asyncio.to_thread(_run_commensurate_search, session, payload)
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=commensurate_csv(result),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="v_ase_commensurate.csv"'},
    )


def _calculate_session_registry(
    session: EditorSession,
    payload: Dict[str, Any],
    progress_callback=None,
):
    with session.mode_transition_lock:
        sync_session_frame_from_payload(session, payload)
        active_mode = session.registry_relaxation
        atoms = (
            copy_atoms_with_calc(active_mode.baseline_atoms)
            if active_mode is not None
            else session.working_atoms.copy()
        )
        positions = payload.get("positions")
        if positions is not None and active_mode is None:
            coordinates = np.asarray(positions, dtype=float)
            if coordinates.shape != (len(atoms), 3) or not np.all(np.isfinite(coordinates)):
                raise ValueError("Registry-map positions must match the current atom count.")
            atoms.set_positions(coordinates, apply_constraint=False)
    return calculate_registry_map(
        atoms,
        payload.get("selected_indices") or [],
        grid_x=int(payload.get("grid_x", 32)),
        grid_y=int(payload.get("grid_y", 32)),
        metric=str(payload.get("metric") or "short-contact"),
        pair_cutoffs=payload.get("pair_cutoffs") or {},
        hkl=payload.get("hkl") or [0, 0, 1],
        progress_callback=progress_callback,
    )


@app.post("/api/analysis/registry/{session_id}")
async def registry_analysis(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    job_id = str(payload.get("job_id") or uuid.uuid4())

    def progress(value: float, stage: str) -> None:
        ws_manager.broadcast_sync({
            "type": "analysis_progress",
            "analysis": "registry",
            "job_id": job_id,
            "progress": float(value),
            "stage": str(stage),
        }, session_id=session_id)

    try:
        result = await asyncio.to_thread(
            _calculate_session_registry,
            session,
            payload,
            progress,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = result.payload()
    response["job_id"] = job_id
    return response


@app.post("/api/analysis/registry-csv/{session_id}")
async def registry_analysis_csv(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    try:
        result = await asyncio.to_thread(_calculate_session_registry, session, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=registry_map_csv(result),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="v_ase_registry_map.csv"'},
    )


@app.post("/api/registry-relax/start/{session_id}")
async def start_registry_relaxation(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "planar translation relaxation")
    sync_session_frame_from_payload(session, payload)
    positions = payload.get("positions")
    if positions is not None:
        coordinates = np.asarray(positions, dtype=float)
        if coordinates.shape != (len(session.working_atoms), 3) or not np.all(np.isfinite(coordinates)):
            raise HTTPException(status_code=400, detail="Registry positions must match the current atom count.")
        session.working_atoms.set_positions(coordinates, apply_constraint=False)
        session.sync_current_frame()
    try:
        summary = start_registry_relaxation_mode(
            session,
            payload.get("selected_indices") or [],
            payload.get("hkl") or [0, 0, 1],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = session_update_to_json(session)
    data["metadata"]["registry_relaxation"] = summary
    return data


@app.post("/api/registry-relax/run/{session_id}")
async def run_registry_relaxation_endpoint(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(
        session,
        "planar translation relaxation",
        allow_registry_relaxation=True,
    )
    calculator = payload.get("calculator") or {}
    if is_vase_repulsion_calculator(session.working_atoms.calc):
        configure_repulsion_calculators(
            session,
            device=calculator.get("device"),
            cpu_threads=calculator.get("cpu_threads"),
            cutoff_mode=calculator.get("cutoff_mode"),
            cutoff_distance=calculator.get("cutoff_distance"),
            cutoff_scale=calculator.get("cutoff_scale"),
            pair_cutoffs=calculator.get("pair_cutoffs"),
            k_repulsion=calculator.get("k_repulsion"),
        )
        mode = session.registry_relaxation
        if mode is not None and is_vase_repulsion_calculator(mode.baseline_atoms.calc):
            mode.baseline_atoms.calc.configure(
                device=calculator.get("device"),
                cpu_threads=calculator.get("cpu_threads"),
                cutoff_mode=calculator.get("cutoff_mode"),
                cutoff_distance=calculator.get("cutoff_distance"),
                cutoff_scale=calculator.get("cutoff_scale"),
                pair_cutoffs=calculator.get("pair_cutoffs"),
                k_repulsion=calculator.get("k_repulsion"),
            )
    try:
        return run_registry_relaxation(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/registry-relax/stop/{session_id}")
async def stop_registry_relaxation_endpoint(session_id: str):
    session = get_session(session_id)
    return {"status": "stopping" if stop_registry_relaxation(session) else "idle"}


@app.post("/api/registry-relax/translate/{session_id}")
async def translate_registry_relaxation_endpoint(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(
        session,
        "planar translation",
        allow_registry_relaxation=True,
    )
    try:
        summary = set_registry_translation(session, payload.get("coordinates") or [])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    data = session_update_to_json(session)
    data["metadata"]["registry_relaxation"] = summary
    return data


@app.post("/api/registry-relax/finish/{session_id}")
async def finish_registry_relaxation_endpoint(session_id: str):
    session = get_session(session_id)
    require_editable(
        session,
        "planar translation relaxation",
        allow_registry_relaxation=True,
    )
    try:
        result = finish_registry_relaxation_mode(session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    data = session_update_to_json(session)
    data["metadata"]["registry_relaxation_result"] = result
    return data


@app.post("/api/registry-relax/cancel/{session_id}")
async def cancel_registry_relaxation_endpoint(session_id: str):
    session = get_session(session_id)
    require_editable(
        session,
        "planar translation relaxation",
        allow_registry_relaxation=True,
    )
    cancel_registry_relaxation_mode(session)
    return session_update_to_json(session)


@app.post("/api/done/{session_id}")
async def done(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_no_atom_addition(session, "closing the editor")
    require_no_registry_relaxation(session, "closing the editor")
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
    repeated_volumes = [
        dataset.replicated(reps)
        for dataset in session.volumetric_datasets
    ]
    session.push_history(
        include_trajectory=True,
        include_volumetric=bool(session.volumetric_datasets),
    )
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: repeat_atoms_as_supercell(atoms, reps))
    session.volumetric_datasets = repeated_volumes
    session.invalidate_trajectory_layout()
    return session_update_to_json(session)


@app.get("/api/build/bulk/catalog/{session_id}")
async def ase_bulk_catalog(session_id: str):
    """Describe the installed ASE bulk builder without mutating the session."""
    get_session(session_id)
    return bulk_builder_catalog()


@app.post("/api/build/bulk/preview/{session_id}")
async def preview_ase_bulk(session_id: str, payload: Dict[str, Any]):
    """Validate one bulk request and return its exact generated geometry summary."""
    get_session(session_id)
    try:
        return bulk_preview_payload(payload)
    except BulkBuildError as exc:
        return exc.as_dict()


def _session_has_replaceable_content(session: EditorSession) -> bool:
    if len(session.working_atoms):
        return True
    cell = np.asarray(session.working_atoms.cell.array, dtype=float)
    return bool(cell.shape == (3, 3) and abs(float(np.linalg.det(cell))) > 1e-12)


def _replace_session_with_built_atoms(session: EditorSession, atoms: Atoms) -> None:
    """Install a generated single frame while keeping the replacement undoable."""
    attach_default = not is_viz_only(session)
    session.push_history(include_trajectory=True, include_original=True)
    original = copy_atoms_with_calc(atoms, attach_default=attach_default)
    working = copy_atoms_with_calc(atoms, attach_default=attach_default)
    session.original_atoms = copy_atoms_with_calc(
        original,
        attach_default=attach_default,
    )
    session.working_atoms = working
    session.original_frames = [copy_atoms_with_calc(
        original,
        attach_default=attach_default,
    )]
    session.trajectory_frames = [copy_atoms_with_calc(
        working,
        attach_default=attach_default,
    )]
    session.trajectory_source = None
    session.current_frame = 0
    session.result_atoms = None
    session.commensurate_search_cache = None
    session.stop_relax = False
    session.is_relaxing = False
    session.relax_restart_requested = False
    session.relax_run_id += 1
    session.relax_params.clear()
    session.relaxation_baseline = None
    session.relaxation_mode_active = False
    session.config["empty_workspace"] = False
    session.invalidate_trajectory_layout()
    session.refresh_trajectory_identity()


@app.post("/api/build/bulk/apply/{session_id}")
async def apply_ase_bulk(session_id: str, payload: Dict[str, Any]):
    """Replace the active Edit document with a validated ASE bulk structure."""
    session = get_session(session_id)
    require_editable(session, "Building an ASE bulk structure")
    if session.volumetric_datasets:
        raise HTTPException(
            status_code=409,
            detail="Remove loaded volumetric data before replacing the structure.",
        )
    if session.commensurate_guest_atoms is not None:
        raise HTTPException(
            status_code=409,
            detail="Remove the commensurate guest structure before replacing the document.",
        )
    if session.is_relaxing or session.relaxation_mode_active:
        raise HTTPException(
            status_code=409,
            detail="Exit the active Relaxation mode before replacing the structure.",
        )
    if _session_has_replaceable_content(session) and payload.get("replace_existing") is not True:
        raise HTTPException(
            status_code=409,
            detail=(
                "This build replaces the current structure and trajectory. "
                "Confirm the replacement and retry with replace_existing=true."
            ),
        )
    try:
        atoms, normalized = build_bulk_atoms(payload)
    except BulkBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _replace_session_with_built_atoms(session, atoms)
    data = session_update_to_json(session)
    data["generated_structure"] = {
        "generator": "ase.build.bulk",
        "formula": normalized["formula"],
        "crystalstructure": normalized["effective_crystalstructure"],
        "cell_mode": normalized["cell_mode"],
    }
    return data


@app.post("/api/cell/{session_id}")
async def set_unit_cell(session_id: str, payload: Dict[str, Any]):
    """Set one explicit Cartesian 3 x 3 cell on every editable frame."""
    session = get_session(session_id)
    require_editable(session, "Setting the unit cell")
    if session.volumetric_datasets:
        raise HTTPException(
            status_code=409,
            detail="Remove loaded volumetric data before replacing its unit cell.",
        )
    try:
        cell = np.asarray(payload.get("cell"), dtype=float)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Cell entries must be numeric.") from exc
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise HTTPException(
            status_code=400,
            detail="Cell must be a 3 x 3 matrix of finite Cartesian values in angstrom.",
        )
    determinant = float(np.linalg.det(cell))
    if abs(determinant) <= 1e-12:
        raise HTTPException(status_code=400, detail="Cell vectors must span a non-zero volume.")
    raw_pbc = payload.get("pbc", [True, True, True])
    if not isinstance(raw_pbc, (list, tuple)) or len(raw_pbc) != 3:
        raise HTTPException(status_code=400, detail="PBC must contain three boolean values.")
    pbc = np.asarray([bool(value) for value in raw_pbc], dtype=bool)
    scale_atoms = bool(payload.get("scale_atoms", False))

    def transform(atoms):
        updated = atoms.copy()
        updated.set_cell(cell, scale_atoms=scale_atoms)
        updated.set_pbc(pbc)
        if atoms.calc:
            updated.calc = copy_calculator(atoms.calc)
        return updated

    session.push_history(include_trajectory=True)
    apply_all_frames(session, transform)
    session.config["empty_workspace"] = False
    session.invalidate_trajectory_layout()
    return session_update_to_json(session)


@app.post("/api/supercell/matrix/{session_id}")
async def apply_supercell_matrix(session_id: str, payload: Dict[str, Any]):
    session = get_session(session_id)
    require_editable(session, "Applying a cell transformation")
    sync_session_frame_from_payload(session, payload)
    matrix = payload.get("matrix")
    P = validate_supercell_matrix_request(session, matrix)
    repeated_volumes = None
    if session.volumetric_datasets:
        diagonal = np.diag(np.diag(P))
        if not np.array_equal(P, diagonal) or np.any(np.diag(P) < 1):
            raise HTTPException(
                status_code=400,
                detail=(
                    "A non-diagonal cell transform cannot preserve the loaded "
                    "volumetric grid exactly. Remove the volumetric dataset or "
                    "use diagonal supercell repetitions."
                ),
            )
        repeated_volumes = [
            dataset.replicated(np.diag(P).tolist())
            for dataset in session.volumetric_datasets
        ]
    session.push_history(
        include_trajectory=True,
        include_volumetric=bool(session.volumetric_datasets),
    )
    set_current_payload_positions(session, payload)
    apply_all_frames(session, lambda atoms: make_supercell_atoms(atoms, P))
    if repeated_volumes is not None:
        session.volumetric_datasets = repeated_volumes
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
    from .relax import (
        clear_relaxation_trajectory,
        exit_relaxation,
        start_relaxation,
        stop_relaxation,
    )
    from .export import (
        OptionalExportDependencyError,
        VideoExportError,
        export_3dm_response,
        export_blender_response,
        export_html_response,
        export_obj_response,
        export_pickle_response,
        export_poscar_response,
        encode_export_image,
        transcode_video_file,
    )

    @app.get("/api/notebook/view/{session_id}")
    async def api_notebook_view(session_id: str):
        """Return a standalone view-only document for an inline notebook frame."""
        session = get_session(session_id)
        config = session.config or {}
        settings = config.get("initial_design_settings") or {
            "schema": "v_ase.visual_settings.v3",
            "display": {
                "showBonds": config.get("show_bonds", True) is not False,
                "showCell": config.get("show_cell", True) is not False,
                "showAxes": config.get("show_axes", True) is not False,
                "showGrid": False,
                "showOverlays": True,
                "projectionMode": "orthographic",
                "viewportBackground": "white",
                "atomRadiusScale": 0.6,
                "bondThickness": 0.25,
            },
            "applyConstraints": config.get("apply_constraint", True) is not False,
            "antiAliasing": True,
            "sphereQuality": "auto",
        }
        response = await asyncio.to_thread(
            export_html_response,
            session,
            {
                "positions": None,
                "settings": settings,
                "selection": [],
                "document_name": config.get("document_name") or "v_ase notebook view",
                "embed_project": False,
                "export_profile": {
                    "kind": "html",
                    "width": 1280,
                    "height": 720,
                    "options": {
                        "includeGrid": False,
                        "includeAxes": config.get("show_axes", True) is not False,
                        "includeCell": config.get("show_cell", True) is not False,
                        "transparentBackground": False,
                        "backgroundColor": "#ffffff",
                    },
                },
            },
        )
        response.headers["Content-Disposition"] = 'inline; filename="v_ase-notebook-view.html"'
        response.headers["Cache-Control"] = "no-store"
        return response

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

    @app.post("/api/export/html/{session_id}")
    async def api_export_html(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        sync_session_frame_from_payload(session, payload)
        try:
            return await asyncio.to_thread(export_html_response, session, payload)
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
        require_no_atom_addition(session, "starting structure relaxation")
        require_no_registry_relaxation(session, "starting structure relaxation")
        sync_session_frame_from_payload(session, payload)
        return await start_relaxation(session, payload, bt)

    @app.post("/api/relax/stop/{session_id}")
    async def api_relax_stop(session_id: str):
        session = get_session(session_id)
        return await stop_relaxation(session)

    @app.post("/api/relax/trajectory/clear/{session_id}")
    async def api_relax_trajectory_clear(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        try:
            result = clear_relaxation_trajectory(session, payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        data = session_update_to_json(session)
        data["relaxation_trajectory"] = result
        return data

    @app.post("/api/relax/exit/{session_id}")
    async def api_relax_exit(session_id: str, payload: Dict[str, Any]):
        session = get_session(session_id)
        result = await exit_relaxation(session, keep=bool(payload.get("keep", True)))
        data = session_update_to_json(session)
        data["relaxation_exit"] = result
        return data
