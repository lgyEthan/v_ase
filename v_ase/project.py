"""Portable v_ase project archives.

The ``.vase`` format is a ZIP container with a JSON manifest and an ASE ULM
trajectory.  It deliberately avoids pickle so opening a project does not
execute Python objects from an untrusted file.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
import json
import mmap
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

from ._version import __version__
from .io import atom_labels, set_atom_labels
from .repulsion import VAseRepulsionCalculator, copy_calculator, is_vase_repulsion_calculator
from .session import EditorSession, copy_atoms_with_calc, replace_session_frames
from .volumetric import DEFAULT_MAX_GRID_POINTS, VolumetricData


PROJECT_SCHEMA = "v_ase.project.v1"
SETTINGS_SCHEMA = "v_ase.visual_settings.v3"
PROJECT_MIME = "application/vnd.v-ase.project+zip"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
MAX_NPZ_MEMBERS = 100_000
MAX_VOLUMETRIC_MEMBER_BYTES = (
    DEFAULT_MAX_GRID_POINTS * np.dtype(np.float64).itemsize
    + 16 * 1024 * 1024
)
MAX_SIDECAR_NPZ_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024
HTML_PROJECT_SCRIPT_ID = "v-ase-project-data"
HTML_PROJECT_FORMAT = "vase-html-project"
_HTML_PROJECT_ID_MARKER = f'id="{HTML_PROJECT_SCRIPT_ID}"'.encode("ascii")
_HTML_SCRIPT_END_MARKER = b"</script>"
_BASE64_WHITESPACE = b" \t\r\n"
_BASE64_DECODE_CHUNK_BYTES = 4 * 1024 * 1024
LEGACY_PAIRWISE_CUTOFF_KEY = "elementBondCutoffs"
LEGACY_LABEL_DISPLAY_KEYS = {
    "elementRadii": "labelRadii",
    "elementColors": "labelColors",
    "elementVisible": "labelVisible",
}


@dataclass(frozen=True)
class VaseProject:
    frames: list[Atoms]
    settings: dict[str, Any]
    current_frame: int
    manifest: dict[str, Any]
    volumetric_datasets: list[VolumetricData] = field(default_factory=list)
    commensurate_guest_atoms: Atoms | None = None
    commensurate_guest_name: str | None = None


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
    display = clean.get("display") if isinstance(clean.get("display"), dict) else clean
    if (
        "pairwiseBondCutoffs" not in display
        and LEGACY_PAIRWISE_CUTOFF_KEY in display
    ):
        display["pairwiseBondCutoffs"] = display[LEGACY_PAIRWISE_CUTOFF_KEY]
    if (
        "pairwiseBondRanges" not in display
        and isinstance(display.get("pairwiseBondCutoffs"), dict)
    ):
        ranges = {}
        for key, value in display["pairwiseBondCutoffs"].items():
            try:
                maximum = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
            ranges[key] = {
                "enabled": maximum > 0,
                "min": 0.0,
                "max": maximum,
            }
        display["pairwiseBondRanges"] = ranges
    elif isinstance(display.get("pairwiseBondRanges"), dict):
        for value in display["pairwiseBondRanges"].values():
            if isinstance(value, dict):
                value["min"] = 0.0
    display.pop(LEGACY_PAIRWISE_CUTOFF_KEY, None)
    for legacy_key, current_key in LEGACY_LABEL_DISPLAY_KEYS.items():
        if current_key not in display and legacy_key in display:
            display[current_key] = display[legacy_key]
        display.pop(legacy_key, None)
    if display.get("bondMode") == "element":
        display["bondMode"] = "pairwise"
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
    labels = [atom_labels(frame) for frame in frames]
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
        set_atom_labels(frame, labels)


def _safe_array(array: Any) -> np.ndarray | None:
    value = np.asarray(array)
    if value.dtype.kind in "biufcSU":
        return value
    if value.dtype.kind == "O":
        flat = value.reshape(-1).tolist()
        if all(isinstance(item, (str, bytes, int, float, bool, np.generic)) for item in flat):
            return value.astype("U")
    return None


def _validate_npz_container(
    path: Path,
    *,
    max_uncompressed_bytes: int,
    required_names: set[str] | None = None,
) -> None:
    """Reject nested ZIP bombs and non-array members before ``numpy.load``."""

    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_NPZ_MEMBERS:
                raise ValueError("An NPZ sidecar contains too many array members.")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ValueError("Invalid NPZ sidecar: duplicate members.")
            if any(
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or Path(name).parent != Path(".")
                or not name.endswith(".npy")
                for name in names
            ):
                raise ValueError("Invalid NPZ sidecar member name.")
            array_names = {name[:-4] for name in names}
            if required_names is not None and array_names != required_names:
                raise ValueError("A .vase volumetric dataset contains unexpected arrays.")
            total_size = sum(info.file_size for info in infos)
            if total_size > max_uncompressed_bytes:
                raise ValueError("An NPZ sidecar expands beyond the supported size limit.")
            if any(info.flag_bits & 0x1 for info in infos):
                raise ValueError("Encrypted NPZ sidecars are not supported.")
            bad_member = archive.testzip()
            if bad_member:
                raise ValueError(f"Corrupt NPZ sidecar member: {bad_member}.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid NPZ sidecar in .vase project.") from exc


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
    _validate_npz_container(
        path,
        max_uncompressed_bytes=MAX_SIDECAR_NPZ_UNCOMPRESSED_BYTES,
    )
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
                "cutoff_mode": calculator.cutoff_mode,
                "cutoff_distance": calculator.cutoff_distance,
                "cutoff_scale": calculator.cutoff_scale,
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
    _validate_npz_container(
        path,
        max_uncompressed_bytes=MAX_SIDECAR_NPZ_UNCOMPRESSED_BYTES,
    )
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
                parameters = dict(entry.get("parameters") or {})
                # Projects written before cutoff_scale was persisted used the
                # unscaled radius threshold. Preserve that behavior on load.
                parameters.setdefault("cutoff_scale", 1.0)
                parameters.setdefault("cutoff_mode", "scaled")
                parameters.setdefault("cutoff_distance", 2.0)
                calculator = VAseRepulsionCalculator(**parameters)
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
        "created_with": {"application": "v_ase", "version": __version__},
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
        volumetric_paths: list[tuple[Path, str]] = []
        guest_path: Path | None = None
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
        volumetric_manifest = []
        for dataset_index, dataset in enumerate(session.volumetric_datasets):
            if not isinstance(dataset, VolumetricData):
                raise ValueError("Project volumetric datasets contain an invalid object.")
            archive_name = f"volumetric/{dataset_index:04d}.npz"
            dataset_path = Path(tmp_dir) / f"volumetric_{dataset_index:04d}.npz"
            np.savez(
                dataset_path,
                values=dataset.values,
                cell=dataset.cell,
                origin=dataset.origin,
                pbc=dataset.pbc,
            )
            entry = dataset.summary()
            entry["path"] = archive_name
            volumetric_manifest.append(entry)
            volumetric_paths.append((dataset_path, archive_name))
        manifest["volumetric_datasets"] = volumetric_manifest
        if session.commensurate_guest_atoms is not None:
            guest_path = Path(tmp_dir) / "commensurate_guest.traj"
            _write_frames(guest_path, [session.commensurate_guest_atoms])
            manifest["commensurate_guest"] = {
                "path": "commensurate_guest.traj",
                "labels_path": "commensurate_guest_labels.json",
                "name": session.commensurate_guest_name or "Guest structure",
            }
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
            if guest_path is not None:
                archive.write(guest_path, arcname="commensurate_guest.traj")
                archive.writestr(
                    "commensurate_guest_labels.json",
                    json.dumps(
                        _label_payload([session.commensurate_guest_atoms]),
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                )
            for dataset_path, archive_name in volumetric_paths:
                archive.write(dataset_path, arcname=archive_name)
    return destination


def _validate_archive(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("The .vase project contains too many archive members.")
    member_names = [info.filename for info in infos]
    names = set(member_names)
    if len(names) != len(member_names):
        raise ValueError("Invalid .vase project: duplicate archive members.")
    required = {"manifest.json", "structure.traj"}
    if not required.issubset(names):
        missing = ", ".join(sorted(required - names))
        raise ValueError(f"Invalid .vase project: missing {missing}.")
    total_size = sum(info.file_size for info in infos)
    if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ValueError("The .vase project expands beyond the supported size limit.")
    for info in infos:
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
    guest_atoms: Atoms | None = None
    guest_name: str | None = None
    try:
        with zipfile.ZipFile(source, mode="r") as archive:
            _validate_archive(archive)
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise ValueError("The .vase project manifest is too large.")
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            if manifest.get("schema") != PROJECT_SCHEMA:
                raise ValueError(f"Unsupported .vase project schema: {manifest.get('schema')!r}.")
            volumetric_manifest = manifest.get("volumetric_datasets") or []
            if not isinstance(volumetric_manifest, list) or len(volumetric_manifest) > 256:
                raise ValueError("Invalid .vase project volumetric dataset manifest.")
            dataset_ids = [str(entry.get("id") or "") for entry in volumetric_manifest if isinstance(entry, dict)]
            if len(dataset_ids) != len(volumetric_manifest) or any(not value for value in dataset_ids):
                raise ValueError("Every .vase volumetric dataset requires a non-empty id.")
            if len(dataset_ids) != len(set(dataset_ids)):
                raise ValueError("A .vase project contains duplicate volumetric dataset ids.")
            guest_manifest = manifest.get("commensurate_guest")
            if guest_manifest is not None and not isinstance(guest_manifest, dict):
                raise ValueError("Invalid .vase commensurate guest manifest.")
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
                volumetric_datasets = []
                for dataset_index, entry in enumerate(volumetric_manifest):
                    if not isinstance(entry, dict):
                        raise ValueError("Invalid volumetric dataset metadata in .vase project.")
                    archive_name = str(entry.get("path") or "")
                    if archive_name not in archive.namelist():
                        raise ValueError(
                            f"Invalid .vase project: missing volumetric dataset {dataset_index + 1}."
                        )
                    member = archive.getinfo(archive_name)
                    if member.file_size > MAX_VOLUMETRIC_MEMBER_BYTES:
                        raise ValueError(
                            f"Volumetric dataset {dataset_index + 1} exceeds the configured grid limit."
                        )
                    dataset_path = Path(tmp_dir) / f"volumetric_{dataset_index:04d}.npz"
                    with archive.open(archive_name) as incoming, dataset_path.open("wb") as outgoing:
                        while chunk := incoming.read(1024 * 1024):
                            outgoing.write(chunk)
                    _validate_npz_container(
                        dataset_path,
                        max_uncompressed_bytes=MAX_VOLUMETRIC_MEMBER_BYTES,
                        required_names={"values", "cell", "origin", "pbc"},
                    )
                    with np.load(dataset_path, allow_pickle=False) as arrays:
                        required_arrays = {"values", "cell", "origin", "pbc"}
                        if not required_arrays.issubset(arrays.files):
                            raise ValueError("A .vase volumetric dataset is incomplete.")
                        values = arrays["values"]
                        declared_shape = tuple(int(value) for value in entry.get("shape") or ())
                        if declared_shape and values.shape != declared_shape:
                            raise ValueError(
                                "A .vase volumetric grid shape does not match its manifest."
                            )
                        if values.dtype not in {
                            np.dtype(np.float32),
                            np.dtype(np.float64),
                        }:
                            raise ValueError(
                                "A .vase volumetric grid must use portable float32 "
                                "or float64 encoding."
                            )
                        declared_precision = str(
                            entry.get("precision") or values.dtype.name
                        )
                        if declared_precision != values.dtype.name:
                            raise ValueError(
                                "A .vase volumetric grid precision does not match "
                                "its manifest."
                            )
                        source_frame = int((entry.get("metadata") or {}).get("source_frame", 0))
                        source_atoms = (
                            frames[source_frame].copy()
                            if 0 <= source_frame < len(frames)
                            else frames[0].copy()
                        )
                        volumetric_datasets.append(
                            VolumetricData(
                                name=str(entry.get("name") or f"Volumetric data {dataset_index + 1}"),
                                values=values,
                                cell=arrays["cell"],
                                origin=arrays["origin"],
                                pbc=arrays["pbc"],
                                quantity=str(entry.get("quantity") or "scalar_field"),
                                units=str(entry.get("units") or "file_native"),
                                source_format=str(entry.get("source_format") or "unknown"),
                                component=str(entry.get("component") or "total"),
                                endpoint_inclusive=bool(entry.get("endpoint_inclusive", False)),
                                precision=declared_precision,
                                atoms=source_atoms,
                                metadata=dict(entry.get("metadata") or {}),
                                dataset_id=str(entry.get("id") or ""),
                            )
                        )
                if guest_manifest:
                    guest_archive_name = str(guest_manifest.get("path") or "")
                    if guest_archive_name != "commensurate_guest.traj":
                        raise ValueError("Invalid .vase commensurate guest path.")
                    if guest_archive_name not in archive.namelist():
                        raise ValueError("Invalid .vase project: missing commensurate guest structure.")
                    guest_path = Path(tmp_dir) / "commensurate_guest.traj"
                    with archive.open(guest_archive_name) as incoming, guest_path.open("wb") as outgoing:
                        while chunk := incoming.read(1024 * 1024):
                            outgoing.write(chunk)
                    loaded_guest = read(guest_path, index=0, format="traj")
                    if not isinstance(loaded_guest, Atoms) or len(loaded_guest) < 1:
                        raise ValueError("The .vase commensurate guest structure is empty.")
                    guest_labels_path = str(
                        guest_manifest.get("labels_path")
                        or "commensurate_guest_labels.json"
                    )
                    if guest_labels_path in archive.namelist():
                        guest_labels = json.loads(archive.read(guest_labels_path).decode("utf-8"))
                        _restore_labels([loaded_guest], guest_labels)
                    guest_atoms = loaded_guest
                    guest_name = str(guest_manifest.get("name") or "Guest structure")
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
        volumetric_datasets=volumetric_datasets,
        commensurate_guest_atoms=(
            _copy_with_cached_results(guest_atoms)
            if guest_atoms is not None
            else None
        ),
        commensurate_guest_name=guest_name,
    )


def extract_project_archive_from_html(
    html_path: str | Path,
    destination: str | Path,
) -> Path:
    """Extract a generated HTML view's optional embedded .vase archive.

    The Base64 payload is decoded in bounded chunks so reopening a large
    project does not require copying the complete HTML document into memory.
    """

    source = Path(html_path)
    output = Path(destination)
    try:
        source_size = source.stat().st_size
    except OSError as exc:
        raise ValueError(f"Could not read v_ase HTML project: {exc}") from exc
    if source_size <= 0:
        raise ValueError("The selected HTML file is empty.")

    output.parent.mkdir(parents=True, exist_ok=True)
    decoded_bytes = 0
    try:
        with source.open("rb") as handle, mmap.mmap(
            handle.fileno(),
            length=0,
            access=mmap.ACCESS_READ,
        ) as document:
            identifier = document.find(_HTML_PROJECT_ID_MARKER)
            if identifier < 0:
                raise ValueError(
                    "This HTML view has no embedded .vase project. "
                    "Re-export it with 'Embed editable .vase project' enabled."
                )
            tag_start = document.rfind(b"<script", 0, identifier)
            tag_end = document.find(b">", identifier)
            payload_end = document.find(_HTML_SCRIPT_END_MARKER, tag_end + 1)
            if tag_start < 0 or tag_end < 0 or payload_end < 0:
                raise ValueError("The embedded v_ase project marker is malformed.")
            start_tag = bytes(document[tag_start:tag_end + 1])
            if b'data-encoding="base64"' not in start_tag:
                raise ValueError("The embedded v_ase project encoding is unsupported.")

            payload_start = tag_end + 1
            remainder = b""
            with output.open("wb") as archive:
                cursor = payload_start
                while cursor < payload_end:
                    stop = min(payload_end, cursor + _BASE64_DECODE_CHUNK_BYTES)
                    block = bytes(document[cursor:stop]).translate(
                        None,
                        _BASE64_WHITESPACE,
                    )
                    cursor = stop
                    if not block:
                        continue
                    block = remainder + block
                    usable = len(block) - (len(block) % 4)
                    if usable:
                        try:
                            decoded = base64.b64decode(
                                block[:usable],
                                validate=True,
                            )
                        except (binascii.Error, ValueError) as exc:
                            raise ValueError(
                                "The embedded .vase project is not valid Base64 data."
                            ) from exc
                        archive.write(decoded)
                        decoded_bytes += len(decoded)
                    remainder = block[usable:]
                if remainder:
                    try:
                        decoded = base64.b64decode(remainder, validate=True)
                    except (binascii.Error, ValueError) as exc:
                        raise ValueError(
                            "The embedded .vase project is not valid Base64 data."
                        ) from exc
                    archive.write(decoded)
                    decoded_bytes += len(decoded)
    except (OSError, ValueError):
        try:
            output.unlink()
        except OSError:
            pass
        raise

    if decoded_bytes <= 0:
        try:
            output.unlink()
        except OSError:
            pass
        raise ValueError(
            "This HTML view has no embedded .vase project. "
            "Re-export it with 'Embed editable .vase project' enabled."
        )
    return output


def read_project_html(path: str | Path) -> VaseProject:
    """Read a lossless project embedded in a generated standalone HTML view."""

    temporary = tempfile.NamedTemporaryFile(delete=False, suffix=".vase")
    temporary.close()
    try:
        extract_project_archive_from_html(path, temporary.name)
        return read_project_archive(temporary.name)
    finally:
        try:
            Path(temporary.name).unlink()
        except OSError:
            pass


def read_project_document(path: str | Path) -> VaseProject:
    """Read either a canonical .vase archive or an HTML-embedded project."""

    source = Path(path)
    if source.suffix.lower() in {".html", ".htm"}:
        return read_project_html(source)
    return read_project_archive(source)


def replace_session_from_project(session: EditorSession, project: VaseProject) -> None:
    replace_session_frames(
        session,
        project.frames,
        current_frame=project.current_frame,
        initial_design_settings=_json_copy(project.settings),
        volumetric_datasets=project.volumetric_datasets,
    )
    session.commensurate_guest_atoms = (
        copy_atoms_with_calc(project.commensurate_guest_atoms, attach_default=False)
        if project.commensurate_guest_atoms is not None
        else None
    )
    session.commensurate_guest_name = project.commensurate_guest_name
    session.commensurate_search_cache = None
