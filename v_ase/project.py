"""Portable v_ase project archives.

The ``.vase`` format is a ZIP container with a JSON manifest and an ASE ULM
trajectory.  It deliberately avoids pickle so opening a project does not
execute Python objects from an untrusted file.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import tempfile
from typing import Any, Iterable
import zipfile

from ase import Atoms
from ase.calculators.calculator import all_properties
from ase.calculators.singlepoint import SinglePointCalculator
from ase.io import read
from ase.io.trajectory import Trajectory
import numpy as np

from .io import atom_type_labels, set_atom_type_labels
from .repulsion import VAseRepulsionCalculator, copy_calculator, is_vase_repulsion_calculator
from .session import EditorSession, copy_atoms_with_calc, replace_session_frames


PROJECT_SCHEMA = "v_ase.project.v1"
SETTINGS_SCHEMA = "v_ase.visual_settings.v2"
PROJECT_MIME = "application/vnd.v-ase.project+zip"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class VaseProject:
    frames: list[Atoms]
    settings: dict[str, Any]
    current_frame: int
    manifest: dict[str, Any]


def package_version() -> str:
    try:
        return version("v_ase-gui")
    except PackageNotFoundError:
        return "0.0.63"


def _json_copy(value: Any) -> Any:
    """Validate JSON compatibility and return a detached value."""
    return json.loads(json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        default=_json_default,
    ))


def normalize_visual_settings(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict):
        raise ValueError("Visual settings must be a JSON object.")
    source = settings.get("settings", settings)
    if not isinstance(source, dict):
        raise ValueError("Visual settings payload must contain an object.")
    clean = _json_copy(source)
    clean["schema"] = SETTINGS_SCHEMA
    return clean


def _copy_without_calculator(atoms: Atoms) -> Atoms:
    copied = atoms.copy()
    copied.calc = None
    return copied


def _copy_with_cached_results(atoms: Atoms) -> Atoms:
    copied = atoms.copy()
    source_calculator = getattr(atoms, "calc", None)
    results = getattr(source_calculator, "results", None)
    if isinstance(results, dict) and results:
        detached = {
            name: np.array(value, copy=True) if np.asarray(value).ndim else np.asarray(value).item()
            for name, value in results.items()
            if name in all_properties and _safe_array(value) is not None
        }
        if detached and is_vase_repulsion_calculator(source_calculator):
            copied.calc = copy_calculator(source_calculator)
            copied.calc.atoms = copied.copy()
            copied.calc.results = detached
        elif detached:
            copied.calc = SinglePointCalculator(copied, **detached)
    elif is_vase_repulsion_calculator(source_calculator):
        copied.calc = copy_calculator(source_calculator)
    return copied


def _apply_current_positions(
    frames: list[Atoms],
    current_frame: int,
    positions: Any | None,
) -> list[Atoms]:
    if positions is None or not frames:
        return frames
    index = max(0, min(int(current_frame), len(frames) - 1))
    coordinates = np.asarray(positions, dtype=float)
    if coordinates.shape != (len(frames[index]), 3) or not np.all(np.isfinite(coordinates)):
        raise ValueError("Project coordinates must be a finite N x 3 array matching the current frame.")
    frames[index].set_positions(coordinates, apply_constraint=False)
    return frames


def session_project_frames(
    session: EditorSession,
    current_positions: Any | None = None,
) -> list[Atoms]:
    """Materialize the complete working trajectory represented by a session."""
    if session.trajectory_source is not None:
        frames = [
            _copy_with_cached_results(session.trajectory_source.read_atoms(index))
            for index in range(session.frame_count)
        ]
        if frames:
            frames[session.current_frame] = _copy_with_cached_results(session.working_atoms)
        return _apply_current_positions(frames, session.current_frame, current_positions)

    session.sync_current_frame()
    source = session.trajectory_frames or [session.working_atoms]
    frames = [_copy_with_cached_results(frame) for frame in source]
    return _apply_current_positions(frames, session.current_frame, current_positions)


def _write_frames(path: Path, frames: Iterable[Atoms]) -> int:
    count = 0
    trajectory = Trajectory(str(path), mode="w")
    try:
        for frame in frames:
            trajectory.write(_copy_without_calculator(frame))
            count += 1
    finally:
        trajectory.close()
    if count == 0:
        raise ValueError("A v_ase project must contain at least one structure frame.")
    return count


def _label_payload(frames: list[Atoms]) -> dict[str, Any]:
    labels = [atom_type_labels(frame) for frame in frames]
    if labels and all(frame_labels == labels[0] for frame_labels in labels[1:]):
        return {"shared": True, "labels": labels[0]}
    return {"shared": False, "frames": labels}


def _restore_labels(frames: list[Atoms], payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    if payload.get("shared") is True:
        labels_by_frame = [payload.get("labels")] * len(frames)
    else:
        labels_by_frame = payload.get("frames") or []
    if len(labels_by_frame) != len(frames):
        raise ValueError("The .vase project label data does not match its frame count.")
    for frame, labels in zip(frames, labels_by_frame):
        if not isinstance(labels, list) or len(labels) != len(frame):
            raise ValueError("The .vase project atom labels do not match the saved structure.")
        set_atom_type_labels(frame, labels)


def _safe_array(array: Any) -> np.ndarray | None:
    value = np.asarray(array)
    if value.dtype.kind in "biufcSU":
        return value
    if value.dtype.kind == "O":
        flat = value.reshape(-1).tolist()
        if all(isinstance(item, (str, bytes, int, float, bool, np.generic)) for item in flat):
            return value.astype("U")
    return None


def _write_array_sidecar(path: Path, frames: list[Atoms]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    stored: dict[str, np.ndarray] = {}
    skipped: list[str] = []
    names = sorted(set().union(*(frame.arrays.keys() for frame in frames)) - {"numbers", "positions"})
    for name in names:
        values = [_safe_array(frame.arrays.get(name)) if name in frame.arrays else None for frame in frames]
        if all(value is not None for value in values) and all(
            values[index].dtype == values[0].dtype
            and values[index].shape == values[0].shape
            and np.array_equal(values[index], values[0])
            for index in range(1, len(values))
        ):
            key = f"array_{len(stored):06d}"
            stored[key] = values[0]
            entries.append({"name": name, "frame": -1, "key": key})
            continue
        wrote_value = False
        for frame_index, value in enumerate(values):
            if value is None:
                continue
            key = f"array_{len(stored):06d}"
            stored[key] = value
            entries.append({"name": name, "frame": frame_index, "key": key})
            wrote_value = True
        if not wrote_value:
            skipped.append(name)
    np.savez_compressed(path, **stored)
    return {"entries": entries, "skipped": skipped}


def _restore_array_sidecar(frames: list[Atoms], path: Path, manifest: Any) -> None:
    if not path.exists() or not isinstance(manifest, dict):
        return
    entries = manifest.get("entries") or []
    with np.load(path, allow_pickle=False) as arrays:
        for entry in entries:
            name = entry.get("name")
            key = entry.get("key")
            frame_index = int(entry.get("frame", -2))
            if not isinstance(name, str) or key not in arrays:
                raise ValueError("Invalid atom-array entry in .vase project.")
            targets = range(len(frames)) if frame_index == -1 else [frame_index]
            for index in targets:
                if index < 0 or index >= len(frames):
                    raise ValueError("Atom-array frame index is out of range in .vase project.")
                value = np.array(arrays[key], copy=True)
                if value.ndim == 0 or len(value) != len(frames[index]):
                    raise ValueError(f"Atom array {name!r} does not match its saved frame.")
                frames[index].set_array(name, value)


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


def _frame_info_payload(frames: list[Atoms]) -> list[dict[str, Any]]:
    payload = []
    for frame in frames:
        try:
            payload.append(json.loads(json.dumps(frame.info, default=_json_default, allow_nan=False)))
        except (TypeError, ValueError):
            payload.append({key: value for key, value in frame.info.items() if isinstance(value, (str, int, float, bool, type(None)))})
    return payload


def _write_calculator_sidecar(path: Path, frames: list[Atoms]) -> dict[str, Any]:
    stored: dict[str, np.ndarray] = {}
    frame_entries: list[dict[str, Any] | None] = []
    for frame in frames:
        calculator = frame.calc
        results = getattr(calculator, "results", None) if calculator is not None else None
        portable_repulsion = is_vase_repulsion_calculator(calculator)
        if (not isinstance(results, dict) or not results) and not portable_repulsion:
            frame_entries.append(None)
            continue
        entry: dict[str, Any] = {
            "calculator": calculator.__class__.__name__,
            "scalars": {},
            "arrays": {},
        }
        if portable_repulsion:
            entry["kind"] = "v_ase_repulsion"
            entry["parameters"] = _json_copy({
                "min_bondinfo": calculator.min_bondinfo,
                "region": list(calculator.region),
                "set_region_as_prohibited": calculator.set_region_as_prohibited,
                "k_boundary": calculator.k_boundary,
                "k_repulsion": calculator.k_repulsion,
                "max_force_norm": calculator.max_force_norm,
                "mic": calculator.mic,
                "work_on_relax_atoms_too": calculator.work_on_relax_atoms_too,
                "device": calculator.device_requested,
                "cpu_threads": calculator.cpu_threads,
                "backend": calculator.backend,
            })
        for name, value in (results or {}).items():
            if name not in all_properties:
                continue
            array = np.asarray(value)
            if array.ndim == 0 and array.dtype.kind in "biufc":
                entry["scalars"][name] = array.item()
                continue
            safe = _safe_array(value)
            if safe is None:
                continue
            key = f"result_{len(stored):06d}"
            stored[key] = safe
            entry["arrays"][name] = key
        frame_entries.append(entry if entry["scalars"] or entry["arrays"] or portable_repulsion else None)
    np.savez_compressed(path, **stored)
    return {"frames": frame_entries, "portable_calculator": "SinglePointCalculator"}


def _restore_calculator_sidecar(frames: list[Atoms], path: Path, manifest: Any) -> None:
    if not path.exists() or not isinstance(manifest, dict):
        return
    frame_entries = manifest.get("frames") or []
    if len(frame_entries) != len(frames):
        raise ValueError("Calculator result metadata does not match the .vase frame count.")
    with np.load(path, allow_pickle=False) as arrays:
        for frame, entry in zip(frames, frame_entries):
            if not entry:
                continue
            results = dict(entry.get("scalars") or {})
            for name, key in (entry.get("arrays") or {}).items():
                if key not in arrays:
                    raise ValueError("Missing calculator result array in .vase project.")
                results[name] = np.array(arrays[key], copy=True)
            if entry.get("kind") == "v_ase_repulsion":
                calculator = VAseRepulsionCalculator(**(entry.get("parameters") or {}))
                calculator.atoms = frame.copy()
                calculator.results = results
                frame.calc = calculator
            elif results:
                frame.calc = SinglePointCalculator(frame, **results)


def write_project_archive(
    path: str | Path,
    session: EditorSession,
    settings: dict[str, Any],
    *,
    current_positions: Any | None = None,
) -> Path:
    destination = Path(path)
    clean_settings = normalize_visual_settings(settings)
    frames = session_project_frames(session, current_positions=current_positions)
    current_frame = max(0, min(int(session.current_frame), len(frames) - 1))
    manifest = {
        "schema": PROJECT_SCHEMA,
        "format_version": 1,
        "created_with": {"application": "v_ase", "version": package_version()},
        "structure": {
            "path": "structure.traj",
            "format": "ase-trajectory",
            "frame_count": len(frames),
            "current_frame": current_frame,
            "calculator_object_included": False,
        },
        "settings": clean_settings,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v_ase_project_") as tmp_dir:
        trajectory_path = Path(tmp_dir) / "structure.traj"
        arrays_path = Path(tmp_dir) / "atom_arrays.npz"
        calculator_path = Path(tmp_dir) / "calculator_results.npz"
        _write_frames(trajectory_path, frames)
        arrays_manifest = _write_array_sidecar(arrays_path, frames)
        calculator_manifest = _write_calculator_sidecar(calculator_path, frames)
        manifest["atom_arrays"] = arrays_manifest
        manifest["calculator_results"] = calculator_manifest
        calculator_entries = [entry for entry in calculator_manifest["frames"] if entry]
        manifest["structure"]["cached_calculator_results_included"] = any(
            entry.get("scalars") or entry.get("arrays") for entry in calculator_entries
        )
        manifest["structure"]["portable_calculator_config_included"] = any(
            entry.get("kind") == "v_ase_repulsion" for entry in calculator_entries
        )
        with zipfile.ZipFile(destination, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8"),
            )
            archive.writestr(
                "labels.json",
                json.dumps(_label_payload(frames), ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
            )
            archive.writestr(
                "frame_info.json",
                json.dumps(_frame_info_payload(frames), ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
            )
            archive.write(trajectory_path, arcname="structure.traj")
            archive.write(arrays_path, arcname="atom_arrays.npz")
            archive.write(calculator_path, arcname="calculator_results.npz")
    return destination


def _validate_archive(archive: zipfile.ZipFile) -> None:
    member_names = archive.namelist()
    names = set(member_names)
    if len(names) != len(member_names):
        raise ValueError("Invalid .vase project: duplicate archive members.")
    required = {"manifest.json", "structure.traj"}
    if not required.issubset(names):
        missing = ", ".join(sorted(required - names))
        raise ValueError(f"Invalid .vase project: missing {missing}.")
    total_size = sum(info.file_size for info in archive.infolist())
    if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ValueError("The .vase project expands beyond the supported size limit.")
    for info in archive.infolist():
        path = Path(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid path inside .vase project.")
        if info.flag_bits & 0x1:
            raise ValueError("Encrypted .vase project members are not supported.")
    bad_member = archive.testzip()
    if bad_member:
        raise ValueError(f"Corrupt .vase project member: {bad_member}.")


def read_project_archive(path: str | Path) -> VaseProject:
    source = Path(path)
    try:
        with zipfile.ZipFile(source, mode="r") as archive:
            _validate_archive(archive)
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise ValueError("The .vase project manifest is too large.")
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            if manifest.get("schema") != PROJECT_SCHEMA:
                raise ValueError(f"Unsupported .vase project schema: {manifest.get('schema')!r}.")
            with tempfile.TemporaryDirectory(prefix="v_ase_project_load_") as tmp_dir:
                trajectory_path = Path(tmp_dir) / "structure.traj"
                arrays_path = Path(tmp_dir) / "atom_arrays.npz"
                calculator_path = Path(tmp_dir) / "calculator_results.npz"
                with archive.open("structure.traj") as incoming, trajectory_path.open("wb") as outgoing:
                    while chunk := incoming.read(1024 * 1024):
                        outgoing.write(chunk)
                if "atom_arrays.npz" in archive.namelist():
                    with archive.open("atom_arrays.npz") as incoming, arrays_path.open("wb") as outgoing:
                        while chunk := incoming.read(1024 * 1024):
                            outgoing.write(chunk)
                if "calculator_results.npz" in archive.namelist():
                    with archive.open("calculator_results.npz") as incoming, calculator_path.open("wb") as outgoing:
                        while chunk := incoming.read(1024 * 1024):
                            outgoing.write(chunk)
                loaded = read(trajectory_path, index=":", format="traj")
                frames = loaded if isinstance(loaded, list) else [loaded]
                _restore_array_sidecar(frames, arrays_path, manifest.get("atom_arrays"))
                _restore_calculator_sidecar(frames, calculator_path, manifest.get("calculator_results"))
            labels_payload = json.loads(archive.read("labels.json").decode("utf-8")) if "labels.json" in archive.namelist() else None
            info_payload = json.loads(archive.read("frame_info.json").decode("utf-8")) if "frame_info.json" in archive.namelist() else None
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid .vase project archive.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid .vase project manifest.") from exc

    if not frames or not all(isinstance(frame, Atoms) for frame in frames):
        raise ValueError("The .vase project contains no readable ASE structures.")
    structure = manifest.get("structure") or {}
    expected_count = int(structure.get("frame_count", len(frames)))
    if expected_count != len(frames):
        raise ValueError("The .vase project frame count does not match its manifest.")
    if labels_payload is not None:
        _restore_labels(frames, labels_payload)
    if info_payload is not None:
        if not isinstance(info_payload, list) or len(info_payload) != len(frames):
            raise ValueError("The .vase project frame metadata does not match its frame count.")
        for frame, info in zip(frames, info_payload):
            if not isinstance(info, dict):
                raise ValueError("Invalid frame metadata in .vase project.")
            frame.info.clear()
            frame.info.update(info)
    current_frame = max(0, min(int(structure.get("current_frame", 0)), len(frames) - 1))
    settings = normalize_visual_settings(manifest.get("settings") or {})
    return VaseProject(
        frames=[_copy_with_cached_results(frame) for frame in frames],
        settings=settings,
        current_frame=current_frame,
        manifest=manifest,
    )


def replace_session_from_project(session: EditorSession, project: VaseProject) -> None:
    replace_session_frames(
        session,
        project.frames,
        current_frame=project.current_frame,
        initial_design_settings=_json_copy(project.settings),
    )
