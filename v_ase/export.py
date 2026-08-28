from fastapi.responses import FileResponse, Response
from typing import Dict, Any, Callable
from ase.io import write
from ase.calculators.singlepoint import SinglePointCalculator
from ase.geometry import find_mic
import base64
import binascii
import copy
import html
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import pickle
import struct
import zipfile
import zlib
import numpy as np
from ._version import __version__
from .serialization import atoms_to_json


class OptionalExportDependencyError(RuntimeError):
    """Raised when an explicitly optional export backend is unavailable."""


class VideoExportError(RuntimeError):
    """Raised when a recorded browser video cannot be converted."""


VIDEO_EXPORT_FORMATS = {
    "mov": {
        "suffix": ".mov",
        "media_type": "video/quicktime",
        "filename": "v_ase-trajectory.mov",
        "codec_args": [
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "20",
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ],
    },
    "avi": {
        "suffix": ".avi",
        "media_type": "video/x-msvideo",
        "filename": "v_ase-trajectory.avi",
        "codec_args": [
            "-c:v", "mpeg4",
            "-q:v", "3",
            "-pix_fmt", "yuv420p",
        ],
    },
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_DECOMPRESSED_BYTES = 512 * 1024 * 1024
HTML_VIEW_SCHEMA = "v_ase.html-view.v1"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def optimize_png_bytes(source: bytes) -> bytes:
    """Losslessly recompress a browser PNG and keep the smaller byte stream.

    Canvas PNG encoders favor latency. Recompressing only the concatenated IDAT
    stream preserves every decoded pixel, alpha value, dimension, and ancillary
    chunk while avoiding a second lossy image representation.
    """

    if not isinstance(source, (bytes, bytearray)) or not source.startswith(PNG_SIGNATURE):
        raise ValueError("Image export payload is not a PNG file.")
    source = bytes(source)
    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    saw_iend = False
    while offset + 12 <= len(source):
        length = struct.unpack(">I", source[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(source):
            raise ValueError("PNG image is truncated.")
        kind = source[offset + 4 : offset + 8]
        payload = source[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", source[offset + 8 + length : end])[0]
        actual_crc = zlib.crc32(kind)
        actual_crc = zlib.crc32(payload, actual_crc) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValueError("PNG image contains a corrupt chunk.")
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            saw_iend = True
            break
    if not saw_iend or offset != len(source):
        raise ValueError("PNG image has an invalid end marker.")
    if any(kind == b"acTL" for kind, _ in chunks):
        return source

    idat = b"".join(payload for kind, payload in chunks if kind == b"IDAT")
    if not idat:
        raise ValueError("PNG image has no pixel data.")
    try:
        decoder = zlib.decompressobj()
        scanlines = decoder.decompress(idat, MAX_PNG_DECOMPRESSED_BYTES + 1)
        if len(scanlines) > MAX_PNG_DECOMPRESSED_BYTES or decoder.unconsumed_tail:
            raise ValueError("PNG image is too large to optimize safely.")
        remaining = MAX_PNG_DECOMPRESSED_BYTES + 1 - len(scanlines)
        scanlines += decoder.flush(remaining)
    except zlib.error as exc:
        raise ValueError("PNG pixel data cannot be decoded.") from exc
    if len(scanlines) > MAX_PNG_DECOMPRESSED_BYTES:
        raise ValueError("PNG image is too large to optimize safely.")
    if not decoder.eof or decoder.unused_data:
        raise ValueError("PNG image contains an invalid compressed pixel stream.")

    compressor = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=15,
        memLevel=9,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    optimized_idat = compressor.compress(scanlines) + compressor.flush()

    output = bytearray(PNG_SIGNATURE)
    inserted = False
    for kind, payload in chunks:
        if kind == b"IDAT":
            if inserted:
                continue
            payload = optimized_idat
            inserted = True
        output.extend(_png_chunk(kind, payload))
    optimized = bytes(output)
    return optimized if len(optimized) < len(source) else source


def encode_lossless_webp(source_png: bytes) -> bytes:
    """Encode a PNG as lossless WebP at identical decoded RGBA resolution."""
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise OptionalExportDependencyError(
            "Lossless WebP export requires Pillow. Reinstall v_ase-gui to restore it."
        ) from exc

    try:
        with Image.open(io.BytesIO(source_png)) as image:
            rgba = image.convert("RGBA")
            output = io.BytesIO()
            rgba.save(
                output,
                format="WEBP",
                lossless=True,
                quality=100,
                method=6,
                exact=True,
            )
    except (OSError, ValueError) as exc:
        raise ValueError(f"Rendered PNG cannot be encoded as lossless WebP: {exc}") from exc
    return output.getvalue()


def _flatten_png_for_opaque_export(source_png: bytes):
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise OptionalExportDependencyError(
            "JPEG and PDF export require Pillow. Reinstall v_ase-gui to restore it."
        ) from exc

    try:
        image = Image.open(io.BytesIO(source_png)).convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    except (OSError, ValueError) as exc:
        raise ValueError(f"Rendered PNG cannot be decoded: {exc}") from exc


def encode_jpeg(source_png: bytes) -> bytes:
    """Encode an opaque, high-quality JPEG with the exact source dimensions."""
    image = _flatten_png_for_opaque_export(source_png)
    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=95,
        subsampling=0,
        optimize=True,
        progressive=True,
    )
    return output.getvalue()


def encode_pdf(source_png: bytes) -> bytes:
    """Embed the rendered RGB pixels as a single-page 300 dpi PDF."""
    image = _flatten_png_for_opaque_export(source_png)
    output = io.BytesIO()
    image.save(
        output,
        format="PDF",
        resolution=300.0,
        quality=95,
        subsampling=0,
    )
    return output.getvalue()


def encode_export_image(source_png: bytes, output_format: str = "png") -> tuple[bytes, str]:
    normalized = str(output_format or "").strip().lower()
    if normalized == "png":
        return optimize_png_bytes(source_png), "image/png"
    if normalized == "webp":
        return encode_lossless_webp(source_png), "image/webp"
    if normalized in {"jpg", "jpeg"}:
        return encode_jpeg(source_png), "image/jpeg"
    if normalized == "pdf":
        return encode_pdf(source_png), "application/pdf"
    raise ValueError("Image format must be png, jpg, pdf, or webp.")

ATOM_MATERIAL_PRESETS = {
    "standard": {
        "roughness": 0.28,
        "metalness": 0.0,
        "specular": 1.0,
        "clearcoat": 0.04,
        "clearcoat_roughness": 0.22,
    },
    "metal": {
        "roughness": 0.11,
        "metalness": 0.96,
        "specular": 1.0,
        "clearcoat": 0.03,
        "clearcoat_roughness": 0.08,
    },
    "rubber": {
        "roughness": 0.88,
        "metalness": 0.0,
        "specular": 0.16,
        "clearcoat": 0.0,
        "clearcoat_roughness": 0.8,
    },
}

_AUTO_BOND_METALLIC_ELEMENTS = frozenset({
    "Li", "Be", "Na", "Mg", "Al", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn",
    "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Rb", "Sr", "Y", "Zr", "Nb", "Mo",
    "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Cs", "Ba", "La", "Ce",
    "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb",
    "Bi", "Po", "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm",
    "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs",
    "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv",
})


def _atom_material_preset(value) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ATOM_MATERIAL_PRESETS else "standard"


def video_export_format(output_format: str) -> Dict[str, Any]:
    normalized = str(output_format or "").strip().lower()
    if normalized not in VIDEO_EXPORT_FORMATS:
        choices = ", ".join(sorted(VIDEO_EXPORT_FORMATS))
        raise ValueError(f"Unsupported video format '{output_format}'. Choose one of: {choices}.")
    return VIDEO_EXPORT_FORMATS[normalized]


def transcode_video_file(
    source_path: str,
    output_format: str,
    fps: int | None = None,
    frame_count: int | None = None,
    progress_callback: Callable[[float, float | None, int], None] | None = None,
) -> tuple[str, str, str]:
    """Convert a browser-recorded WebM into a portable MOV or AVI file."""
    config = video_export_format(output_format)
    normalized_fps = None if fps is None else max(1, min(60, int(fps)))
    normalized_frame_count = (
        None if frame_count is None else max(1, int(frame_count))
    )
    try:
        import imageio_ffmpeg
    except ModuleNotFoundError as exc:
        raise OptionalExportDependencyError(
            "Video conversion is unavailable because imageio-ffmpeg is not installed. "
            "Reinstall v_ase-gui to restore the runtime dependency."
        ) from exc

    target = tempfile.NamedTemporaryFile(delete=False, suffix=config["suffix"])
    target_path = target.name
    target.close()
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", source_path,
        "-an",
        *(
            [
                "-vf",
                f"setpts=N/({normalized_fps}*TB),fps={normalized_fps}:round=near",
            ]
            if normalized_fps is not None
            else []
        ),
        *(
            ["-frames:v", str(normalized_frame_count)]
            if normalized_frame_count is not None
            else []
        ),
        *config["codec_args"],
        *(["-progress", "pipe:1", "-nostats"] if progress_callback else []),
        target_path,
    ]
    try:
        if progress_callback is None:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30 * 60,
            )
            return_code = completed.returncode
            detail_output = completed.stderr or completed.stdout
        else:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            messages: queue.Queue[tuple[str, str | None]] = queue.Queue()
            stderr_lines: list[str] = []

            def read_stream(name: str, stream) -> None:
                try:
                    for line in iter(stream.readline, ""):
                        messages.put((name, line.rstrip()))
                finally:
                    messages.put((name, None))

            readers = [
                threading.Thread(
                    target=read_stream,
                    args=("stdout", process.stdout),
                    daemon=True,
                ),
                threading.Thread(
                    target=read_stream,
                    args=("stderr", process.stderr),
                    daemon=True,
                ),
            ]
            for reader in readers:
                reader.start()

            started = time.monotonic()
            open_streams = len(readers)
            last_ratio = -1.0
            while open_streams:
                if time.monotonic() - started > 30 * 60:
                    process.kill()
                    raise subprocess.TimeoutExpired(command, 30 * 60)
                try:
                    name, line = messages.get(timeout=0.25)
                except queue.Empty:
                    continue
                if line is None:
                    open_streams -= 1
                    continue
                if name == "stderr":
                    stderr_lines.append(line)
                    continue
                if not line.startswith("frame=") or normalized_frame_count is None:
                    continue
                try:
                    completed_frames = max(0, int(line.split("=", 1)[1].strip()))
                except (TypeError, ValueError):
                    continue
                ratio = min(0.995, completed_frames / normalized_frame_count)
                if ratio <= last_ratio:
                    continue
                elapsed = time.monotonic() - started
                eta = (
                    elapsed * (1.0 - ratio) / ratio
                    if ratio > 0
                    else None
                )
                try:
                    progress_callback(ratio, eta, completed_frames)
                except Exception:
                    pass
                last_ratio = ratio

            return_code = process.wait(timeout=10)
            detail_output = "\n".join(stderr_lines)
            if return_code == 0:
                try:
                    progress_callback(1.0, 0.0, normalized_frame_count or 0)
                except Exception:
                    pass
    except (OSError, subprocess.TimeoutExpired) as exc:
        try:
            os.unlink(target_path)
        except OSError:
            pass
        raise VideoExportError(f"Video conversion could not start: {exc}") from exc
    if return_code != 0 or not os.path.isfile(target_path) or os.path.getsize(target_path) == 0:
        try:
            os.unlink(target_path)
        except OSError:
            pass
        detail = (detail_output or "Unknown FFmpeg error").strip()
        if len(detail) > 1200:
            detail = detail[-1200:]
        raise VideoExportError(f"Video conversion failed: {detail}")
    return target_path, config["filename"], config["media_type"]


def _apply_payload_positions(session, payload: Dict[str, Any]):
    if payload and "positions" in payload and not bool((session.config or {}).get("viz_only", False)):
        session.working_atoms.set_positions(
            np.array(payload["positions"]),
            apply_constraint=bool(payload.get("apply_constraint", True)),
        )
    return session.working_atoms


def _atoms_for_vasp_export(atoms):
    if atoms.cell.rank == 3:
        return atoms

    export_atoms = atoms.copy()
    export_atoms.calc = None
    export_atoms.center(vacuum=8.0)
    export_atoms.set_pbc([False, False, False])
    return export_atoms


def export_poscar_response(session, payload: Dict[str, Any]):
    atoms = _apply_payload_positions(session, payload)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".vasp")
    tmp.close()
    write(tmp.name, _atoms_for_vasp_export(atoms), format="vasp")
    return FileResponse(tmp.name, filename="POSCAR", media_type="application/octet-stream")


def atoms_for_pickle_export(atoms):
    """Return a portable ASE Atoms copy with valid single-point results only."""
    atoms_to_save = atoms.copy()
    atoms_to_save.calc = None
    source_calculator = getattr(atoms, "calc", None)
    if not isinstance(source_calculator, SinglePointCalculator):
        return atoms_to_save
    try:
        if source_calculator.check_state(atoms):
            return atoms_to_save
    except Exception:
        return atoms_to_save
    results = {
        name: copy.deepcopy(value)
        for name, value in source_calculator.results.items()
    }
    if results:
        atoms_to_save.calc = SinglePointCalculator(atoms_to_save, **results)
    return atoms_to_save


def export_pickle_response(session, payload: Dict[str, Any]):
    atoms = _apply_payload_positions(session, payload)
    atoms_to_save = atoms_for_pickle_export(atoms)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
    tmp.close()
    with open(tmp.name, "wb") as handle:
        pickle.dump(atoms_to_save, handle)
    return FileResponse(tmp.name, filename="atoms.pkl", media_type="application/octet-stream")


_HTML_PARTICLE_ID_ARRAY_NAMES = ("lammps_id", "atom_id", "particle_id", "ids", "id")


def _unique_html_particle_ids(atoms):
    for name in _HTML_PARTICLE_ID_ARRAY_NAMES:
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


def _html_frame_displacement(frames, current_index, display):
    if len(frames) <= 1:
        return None
    reference_mode = (
        "frame"
        if str(display.get("displacementReferenceMode", "previous")).lower() == "frame"
        else "previous"
    )
    if reference_mode == "previous":
        if current_index <= 0:
            return None
        reference_index = current_index - 1
    else:
        reference_index = max(
            0,
            min(
                len(frames) - 1,
                int(display.get("displacementReferenceFrame", 0) or 0),
            ),
        )

    current = frames[current_index]
    reference = frames[reference_index]
    current_id_name, current_ids = _unique_html_particle_ids(current)
    reference_id_name, reference_ids = _unique_html_particle_ids(reference)
    mapping = "index"
    if (
        current_ids is not None
        and reference_ids is not None
        and current_id_name == reference_id_name
    ):
        mapping = f"particle-id:{current_id_name}"
        lookup = {particle_id: index for index, particle_id in enumerate(reference_ids)}
        current_indices = [
            index
            for index, particle_id in enumerate(current_ids)
            if particle_id in lookup
        ]
        reference_indices = [lookup[current_ids[index]] for index in current_indices]
    elif len(current) == len(reference):
        current_indices = list(range(len(current)))
        reference_indices = list(range(len(reference)))
    else:
        return None
    if not current_indices:
        return None

    current_positions = np.asarray(current.positions, dtype=float)[current_indices]
    reference_positions = np.asarray(reference.positions, dtype=float)[reference_indices]
    vectors = current_positions - reference_positions
    mic_requested = display.get("displacementMic", True) is not False
    mic_applied = False
    if mic_requested and np.asarray(current.pbc, dtype=bool).any():
        cell = np.asarray(current.cell.array, dtype=float)
        if (
            cell.shape == (3, 3)
            and np.isfinite(cell).all()
            and abs(np.linalg.det(cell)) > 1e-12
        ):
            vectors, _ = find_mic(vectors, current.cell, current.pbc)
            vectors = np.asarray(vectors, dtype=float)
            mic_applied = True
    magnitudes = np.linalg.norm(vectors, axis=1)
    return {
        "status": "ok",
        "current_frame": current_index,
        "reference_frame": reference_index,
        "reference_mode": reference_mode,
        "mapping": mapping,
        "mic_requested": mic_requested,
        "mic_applied": mic_applied,
        "indices": [int(index) for index in current_indices],
        "reference_indices": [int(index) for index in reference_indices],
        "starts": current_positions.tolist(),
        "vectors": vectors.tolist(),
        "magnitudes": magnitudes.tolist(),
    }


def _html_view_displacements(frames, settings):
    source = settings.get("settings", settings) if isinstance(settings, dict) else {}
    display = source.get("display", source) if isinstance(source, dict) else {}
    if not isinstance(display, dict) or display.get("showDisplacements") is not True:
        return []
    return [
        _html_frame_displacement(frames, frame_index, display)
        for frame_index in range(len(frames))
    ]


def _base64_text(source: bytes | str) -> str:
    if isinstance(source, str):
        source = source.encode("utf-8")
    return base64.b64encode(source).decode("ascii")


def _validated_html_poster(value: Any) -> str:
    source = str(value or "").strip()
    match = re.fullmatch(
        r"data:image/(png|webp|jpeg);base64,([A-Za-z0-9+/=\s]+)",
        source,
        flags=re.I,
    )
    if not match:
        return ""
    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return ""
    if not decoded or len(decoded) > 24 * 1024 * 1024:
        return ""
    subtype = match.group(1).lower()
    return f"data:image/{subtype};base64,{encoded}"


def _html_export_profile(value: Any, settings: Dict[str, Any]) -> Dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    def dimension(name: str, fallback: int) -> int:
        try:
            parsed = int(source.get(name) or fallback)
        except (TypeError, ValueError):
            parsed = fallback
        return max(256, min(8192, parsed))

    width = dimension("width", 1920)
    height = dimension("height", 1080)
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    normalized_options = dict(options)
    normalized_options.update({
        "includeGrid": options.get("includeGrid") is True,
        "includeAxes": options.get("includeAxes") is not False,
        "includeCell": options.get("includeCell") is not False,
        "transparentBackground": False,
    })
    composition = (
        source.get("composition")
        if isinstance(source.get("composition"), dict)
        else {}
    )
    if not isinstance(composition.get("camera"), dict):
        camera = settings.get("camera") if isinstance(settings, dict) else None
        if isinstance(camera, dict):
            composition = {
                "schema": "v_ase.export-composition.v1",
                "width": width,
                "height": height,
                "aspect": width / height,
                "options": normalized_options,
                "camera": camera,
            }
    return {
        "kind": "html",
        "width": width,
        "height": height,
        "aspect": width / height,
        "options": normalized_options,
        "composition": composition,
    }


def _safe_export_stem(value: Any, fallback: str = "v_ase_view") -> str:
    source = Path(str(value or "")).name
    source = re.sub(r"\.(?:vase|vasp|poscar|contcar|cif|xyz|extxyz|traj|html?)$", "", source, flags=re.I)
    source = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("._-")
    return source or fallback


def _html_atom_color_scale_frames(
    frame_objects,
    settings: Dict[str, Any],
    selection: list[int],
    current_frame: int = 0,
) -> list[dict[str, Any] | None]:
    """Freeze an active browser colorscale into standalone frame metadata.

    The optional Matplotlib import and scalar extraction are deliberately kept
    behind the enabled flag. Ordinary HTML exports therefore retain the same
    cost and dependency path as before atom colorscales were introduced.
    """
    display = settings.get("display") if isinstance(settings.get("display"), dict) else {}
    if display.get("atomColorScaleEnabled") is not True:
        return [None] * len(frame_objects)

    from .atom_scalars import atom_scalar_catalog, atom_scalar_values
    from .colormaps import colormap_lut, custom_colormap_lut

    field_id = str(display.get("atomColorScaleField") or "position:z")
    map_name = str(display.get("atomColorScaleMap") or "viridis")
    reverse = display.get("atomColorScaleReverse") is True
    scope = "selected" if display.get("atomColorScaleScope") == "selected" else "all"
    range_mode = str(display.get("atomColorScaleRangeMode") or "").strip().lower()
    if range_mode not in {"current", "trajectory", "manual"}:
        range_mode = "manual" if display.get("atomColorScaleAutoRange") is False else "current"
    gamma = float(display.get("atomColorScaleGamma", 1.0))
    if not math.isfinite(gamma) or gamma < 0.1 or gamma > 5.0:
        gamma = 1.0
    selected = set(selection)
    custom_map = None
    if map_name == "custom":
        custom_palette = custom_colormap_lut(
            display.get("atomColorScaleCustomMap"),
            samples=256,
            reverse=reverse,
        )
        palette = custom_palette["colors"]
        custom_map = {
            "mode": custom_palette["mode"],
            "stops": custom_palette["stops"],
        }
    else:
        palette = colormap_lut(map_name, samples=256, reverse=reverse)["colors"]
    payloads: list[dict[str, Any] | None] = []
    descriptor: dict[str, Any] = {"id": field_id, "label": field_id, "unit": ""}

    def extract(atoms):
        nonlocal descriptor
        try:
            values = np.asarray(atom_scalar_values(atoms, field_id), dtype=np.float64)
        except ValueError:
            return None
        finite_mask = np.isfinite(values)
        if scope == "selected":
            finite_mask &= np.fromiter(
                (index in selected for index in range(len(atoms))),
                dtype=bool,
                count=len(atoms),
            )
        if descriptor["label"] == field_id:
            descriptor = next(
                (item for item in atom_scalar_catalog(atoms) if item["id"] == field_id),
                descriptor,
            )
        return values, finite_mask

    try:
        minimum = float(display.get("atomColorScaleMin"))
        maximum = float(display.get("atomColorScaleMax"))
    except (TypeError, ValueError):
        minimum = math.nan
        maximum = math.nan
    if not math.isfinite(minimum) or not math.isfinite(maximum) or maximum <= minimum:
        if range_mode == "manual":
            raise ValueError("Manual color scale requires finite vmin and vmax with vmax greater than vmin.")
        indices = (
            range(len(frame_objects))
            if range_mode == "trajectory"
            else [max(0, min(len(frame_objects) - 1, int(current_frame)))]
        )
        minimum = math.inf
        maximum = -math.inf
        finite_count = 0
        for index in indices:
            frame = extract(frame_objects[index])
            if frame is None:
                continue
            values, finite_mask = frame
            finite = values[finite_mask]
            if not finite.size:
                continue
            finite_count += int(finite.size)
            minimum = min(minimum, float(np.min(finite)))
            maximum = max(maximum, float(np.max(finite)))
        if not finite_count:
            return [None] * len(frame_objects)
        if minimum == maximum:
            padding = max(1e-12, abs(minimum) * 1e-6)
            minimum -= padding
            maximum += padding

    for atoms in frame_objects:
        frame = extract(atoms)
        if frame is None:
            payloads.append(None)
            continue
        values, finite_mask = frame
        normalized = np.where(
            np.isfinite(values),
            np.clip((values - minimum) / (maximum - minimum), 0.0, 1.0),
            0.0,
        )
        if gamma != 1.0:
            normalized = normalized ** gamma
        palette_indices = np.rint(normalized * (len(palette) - 1)).astype(np.int64)
        colors = [
            palette[int(palette_indices[index])] if finite_mask[index] else None
            for index in range(len(atoms))
        ]
        payloads.append({
            "field_id": field_id,
            "label": descriptor.get("label", field_id),
            "unit": descriptor.get("unit", ""),
            "map": map_name,
            "custom_map": custom_map,
            "reverse": reverse,
            "gamma": gamma,
            "scope": scope,
            "range_mode": range_mode,
            "minimum": minimum,
            "maximum": maximum,
            "colors": colors,
        })
    return payloads


def _html_view_identity_labels(
    frame_objects,
    settings: Dict[str, Any],
) -> list[list[str] | None]:
    """Return structure-specific View labels without changing ASE elements."""
    source = settings.get("viewIdentityOverrides")
    if not isinstance(source, dict):
        return [None] * len(frame_objects)
    if source.get("scope") == "trajectory" and isinstance(source.get("labels"), list):
        labels = [str(value) for value in source["labels"]]
        return [labels if len(labels) == len(atoms) else None for atoms in frame_objects]
    frames = source.get("frames")
    if source.get("scope") != "frames" or not isinstance(frames, dict):
        return [None] * len(frame_objects)
    result: list[list[str] | None] = []
    for index, atoms in enumerate(frame_objects):
        values = frames.get(str(index))
        labels = [str(value) for value in values] if isinstance(values, list) else None
        result.append(labels if labels is not None and len(labels) == len(atoms) else None)
    return result


def export_html_response(session, payload: Dict[str, Any]):
    """Build one offline, view-only HTML document with optional project recovery."""
    from .project import (
        PROJECT_SCHEMA,
        normalize_visual_settings,
        session_project_frames,
        write_project_archive,
    )

    settings = normalize_visual_settings(payload.get("settings") or {})
    document_name = Path(str(payload.get("document_name") or "v_ase view")).name
    embed_project = payload.get("embed_project") is True
    frame_objects = session_project_frames(
        session,
        current_positions=payload.get("positions"),
    )
    current_frame = max(
        0,
        min(int(getattr(session, "current_frame", 0)), len(frame_objects) - 1),
    )
    project_bytes = b""
    if embed_project:
        project_file = tempfile.NamedTemporaryFile(delete=False, suffix=".vase")
        project_file.close()
        try:
            write_project_archive(
                project_file.name,
                session,
                settings,
                current_positions=payload.get("positions"),
            )
            project_bytes = Path(project_file.name).read_bytes()
        finally:
            try:
                os.unlink(project_file.name)
            except OSError:
                pass

    selection = []
    for value in payload.get("selection") or []:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(frame_objects[current_frame]):
            selection.append(index)
    selection = sorted(set(selection))
    frames = [atoms_to_json(frame) for frame in frame_objects]
    identity_labels = _html_view_identity_labels(frame_objects, settings)
    for frame, labels in zip(frames, identity_labels):
        if labels is not None:
            frame["symbols"] = labels
            frame["atom_types"] = labels
    color_scale_frames = _html_atom_color_scale_frames(
        frame_objects,
        settings,
        selection,
        current_frame=int(session.current_frame),
    )
    for frame, color_scale in zip(frames, color_scale_frames):
        if color_scale is not None:
            frame.setdefault("metadata", {})["atom_color_scale"] = color_scale
    export_profile = _html_export_profile(payload.get("export_profile"), settings)
    poster_data_url = _validated_html_poster(payload.get("poster_data_url"))
    scene = {
        "schema": HTML_VIEW_SCHEMA,
        "createdWith": {"application": "v_ase", "version": __version__},
        "documentName": document_name,
        "hasEmbeddedProject": embed_project,
        "projectFilename": (
            f"{_safe_export_stem(document_name, 'v_ase_project')}.vase"
            if embed_project
            else ""
        ),
        "projectSchema": PROJECT_SCHEMA if embed_project else None,
        "currentFrame": current_frame,
        "settings": settings,
        "exportProfile": export_profile,
        "hasPoster": bool(poster_data_url),
        "selection": selection,
        "frames": frames,
        "displacements": _html_view_displacements(frame_objects, settings),
    }

    static_dir = Path(__file__).with_name("static")
    template = (static_dir / "standalone.html").read_text(encoding="utf-8")
    export_width = int(export_profile["width"])
    export_height = int(export_profile["height"])
    export_aspect = export_width / max(1, export_height)
    export_background = str(
        export_profile.get("options", {}).get("backgroundColor") or "#ffffff"
    ).strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", export_background):
        export_background = "#ffffff"
    replacements = {
        "{{V_ASE_VERSION}}": html.escape(__version__, quote=True),
        "{{DOCUMENT_TITLE}}": html.escape(document_name, quote=True),
        "{{STANDALONE_CSS}}": (static_dir / "standalone.css").read_text(encoding="utf-8"),
        "{{VIEWER_FRAME_STYLE}}": (
            f"aspect-ratio:{export_width}/{export_height};"
            f"width:min(100vw,calc(100vh*{export_aspect:.10f}));"
        ),
        "{{EXPORT_BACKGROUND}}": export_background,
        "{{SCENE_DATA_BASE64}}": _base64_text(
            json.dumps(
                scene,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        ),
        "{{PROJECT_DATA_BASE64}}": _base64_text(project_bytes) if embed_project else "",
        "{{POSTER_DATA_URL}}": poster_data_url,
        "{{POSTER_HIDDEN}}": "" if poster_data_url else "hidden",
        "{{THREE_SOURCE_BASE64}}": _base64_text(
            (static_dir / "vendor" / "three.module.js").read_bytes()
        ),
        "{{RENDERER_SOURCE_BASE64}}": _base64_text(
            (static_dir / "renderer.js").read_bytes()
        ),
        "{{VIEWER_SOURCE_BASE64}}": _base64_text(
            (static_dir / "standalone.js").read_bytes()
        ),
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    if "{{" in template or "}}" in template:
        raise RuntimeError("Standalone HTML template contains an unresolved marker.")

    output = template.encode("utf-8")
    filename = f"{_safe_export_stem(document_name)}.html"
    return Response(
        content=output,
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-V-Ase-View-Schema": HTML_VIEW_SCHEMA,
            "X-V-Ase-Embedded-Project": "true" if embed_project else "false",
            "X-V-Ase-Embedded-Project-Bytes": (
                str(len(project_bytes)) if embed_project else "0"
            ),
            "X-V-Ase-Frame-Count": str(len(frames)),
        },
    )


def _trajectory_frames_json(session):
    frames = getattr(session, "trajectory_frames", []) or []
    if len(frames) <= 1:
        return []
    return [atoms_to_json(frame) for frame in frames]


def _minimum_image_delta(delta, cell, pbc):
    delta = np.asarray(delta, dtype=float)
    clean_pbc = np.asarray(pbc if pbc is not None else [], dtype=bool).reshape(-1)
    matrix = np.asarray(cell if cell is not None else [], dtype=float)
    if clean_pbc.size != 3 or not np.any(clean_pbc) or matrix.size == 0:
        return delta
    if matrix.shape != (3, 3):
        return delta
    try:
        vectors, _ = find_mic(delta.reshape(1, 3), matrix, pbc=clean_pbc)
    except (ValueError, np.linalg.LinAlgError):
        return delta
    return np.asarray(vectors[0], dtype=float)


def _normalized_bond_mode(display: Dict[str, Any]) -> str:
    mode = display.get("bondMode", "auto")
    return "pairwise" if mode == "element" else mode


def _pairwise_bond_cutoffs(display: Dict[str, Any]) -> Dict[str, Any]:
    return (
        display.get("pairwiseBondCutoffs")
        or display.get("elementBondCutoffs")
        or {}
    )


def _pairwise_bond_ranges(display: Dict[str, Any]) -> Dict[str, Any]:
    ranges = display.get("pairwiseBondRanges")
    legacy_cutoffs = _pairwise_bond_cutoffs(display)
    if isinstance(ranges, dict) and not legacy_cutoffs:
        return {
            key: {
                "enabled": value.get("enabled") is not False,
                "min": 0.0,
                "max": value.get("max", 0.0),
            }
            for key, value in ranges.items()
            if isinstance(value, dict)
        }
    result = {}
    for key, value in legacy_cutoffs.items():
        try:
            maximum = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
        source = ranges.get(key) if isinstance(ranges, dict) else None
        if isinstance(source, dict):
            try:
                source_maximum = max(0.0, float(source.get("max", 0.0)))
            except (TypeError, ValueError):
                source_maximum = 0.0
            source_enabled = source.get("enabled") is not False and source_maximum > 0
            legacy_enabled = maximum > 0
            if (
                source_enabled == legacy_enabled
                and (not source_enabled or math.isclose(source_maximum, maximum))
            ):
                result[key] = {
                    "enabled": source_enabled,
                    "min": 0.0,
                    "max": source_maximum,
                }
                continue
        result[key] = {
            "enabled": maximum > 0,
            "min": 0.0,
            "max": maximum,
        }
    return result


def _automatic_bond_cutoff(symbol_a, symbol_b, radius_a, radius_b) -> float:
    first = str(symbol_a)
    second = str(symbol_b)
    first_is_hydrogen = first == "H"
    second_is_hydrogen = second == "H"
    first_is_metal = first in _AUTO_BOND_METALLIC_ELEMENTS
    second_is_metal = second in _AUTO_BOND_METALLIC_ELEMENTS
    if (
        (first_is_hydrogen and second_is_hydrogen)
        or (first_is_metal and second_is_metal)
    ):
        return 0.0
    if first_is_hydrogen or second_is_hydrogen:
        slack = 0.22
    elif first_is_metal or second_is_metal:
        slack = 0.50
    else:
        slack = 0.35
    return max(0.0, float(radius_a) + float(radius_b) + slack)


def _display_bonds(data: Dict[str, Any], display: Dict[str, Any], explicit_pairs=None):
    display = display or {}
    if display.get("showBonds") is False:
        return []

    positions = np.asarray(data.get("positions") or [], dtype=float)
    labels = list(data.get("symbols") or [])
    symbols = list(data.get("chemical_symbols") or labels)
    if len(positions) != len(symbols):
        return []
    if len(labels) != len(symbols):
        labels = symbols

    cell = data.get("cell") or []
    pbc = data.get("pbc") or [False, False, False]
    visual = data.get("visual") or {}
    covalent_source = visual.get("bond_radii") or visual.get("covalent_radii") or []
    covalent = [float(value) if value is not None else 0.75 for value in covalent_source]
    if len(covalent) < len(symbols):
        covalent.extend([0.75] * (len(symbols) - len(covalent)))
    bond_mode = _normalized_bond_mode(display)
    pairwise_ranges = _pairwise_bond_ranges(display) if bond_mode == "pairwise" else {}

    def pair_key(i, j):
        return "-".join(sorted((str(labels[i]), str(labels[j]))))

    def bond_range(i, j):
        if bond_mode == "pairwise":
            key = pair_key(i, j)
            source = pairwise_ranges.get(key)
            if not isinstance(source, dict) or source.get("enabled") is False:
                return 0.0, 0.0
            try:
                maximum = max(0.0, float(source.get("max", 0.0)))
                return 0.0, maximum
            except (TypeError, ValueError):
                return 0.0, 0.0
        scale = float(display.get("bondCutoffScale") or 1.0)
        return 0.0, _automatic_bond_cutoff(
            symbols[i],
            symbols[j],
            covalent[i],
            covalent[j],
        ) * scale

    raw_pairs = explicit_pairs
    if not raw_pairs and bond_mode == "manual":
        raw_pairs = display.get("manualBondPairs") or []

    pairs = []
    include_periodic_images = bool(display.get("showPeriodicBonds"))

    def bond_delta(i, j):
        direct = positions[j] - positions[i]
        if include_periodic_images:
            return _minimum_image_delta(direct, cell, pbc)
        return direct

    if raw_pairs:
        for pair in raw_pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            i, j = int(pair[0]), int(pair[1])
            if 0 <= i < len(symbols) and 0 <= j < len(symbols) and i != j:
                pairs.append((min(i, j), max(i, j)))
    else:
        if bond_mode == "pairwise":
            candidates = []
            for value in pairwise_ranges.values():
                if not isinstance(value, dict) or value.get("enabled") is False:
                    continue
                try:
                    parsed = float(value.get("max", 0.0))
                except (TypeError, ValueError):
                    continue
                if np.isfinite(parsed) and parsed > 0:
                    candidates.append(parsed)
            search_radius = max(candidates, default=0.0)
        else:
            scale = float(display.get("bondCutoffScale") or 1.0)
            search_radius = (2.0 * max(covalent, default=0.75) + 0.50) * scale

        candidate_pairs = []
        if search_radius > 0 and len(symbols) > 1:
            from ase import Atoms

            from .neighbors import neighbour_list

            probe = Atoms(
                numbers=np.ones(len(symbols), dtype=int),
                positions=positions,
                cell=cell,
                pbc=pbc if include_periodic_images else False,
            )
            first, second = neighbour_list(
                "ij",
                probe,
                search_radius,
                self_interaction=False,
            )
            candidate_pairs = sorted({
                (min(int(i), int(j)), max(int(i), int(j)))
                for i, j in zip(first, second)
                if int(i) != int(j)
            })
        for i, j in candidate_pairs:
            i, j = int(i), int(j)
            delta = bond_delta(i, j)
            distance = float(np.linalg.norm(delta))
            minimum, maximum = bond_range(i, j)
            if maximum > 0 and minimum <= distance <= maximum:
                pairs.append((i, j))

    seen = set()
    bonds = []
    for i, j in pairs:
        key = (i, j)
        if key in seen:
            continue
        seen.add(key)
        delta = bond_delta(i, j)
        bonds.append({
            "i": i,
            "j": j,
            "start": positions[i].tolist(),
            "end": (positions[i] + delta).tolist(),
            "length": float(np.linalg.norm(delta)),
        })
    return bonds


def _valid_hex_color(value, fallback="#c8ccd0"):
    if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return value.lower()
    return fallback


def _hex_rgb(value):
    color = _valid_hex_color(value)
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))


def _safe_name(value, fallback="object"):
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_.")
    return cleaned or fallback


def _normalized_supercell(display, data):
    raw = display.get("supercell") or [1, 1, 1]
    repetitions = []
    for axis in range(3):
        try:
            value = int(raw[axis])
        except (IndexError, TypeError, ValueError):
            value = 1
        repetitions.append(max(1, min(128, value)))

    cell = np.asarray(data.get("cell") or [], dtype=float)
    if cell.shape != (3, 3) or abs(float(np.linalg.det(cell))) < 1e-10:
        return [1, 1, 1], np.zeros((3, 3), dtype=float)
    return repetitions, cell


def _display_translation(display, cell):
    raw = display.get("translation") if isinstance(display, dict) else None
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        return np.zeros(3, dtype=float)
    try:
        vector = np.asarray(raw[:3], dtype=float)
    except (TypeError, ValueError):
        return np.zeros(3, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        return np.zeros(3, dtype=float)
    if display.get("translationMode") != "fractional":
        return vector
    matrix = np.asarray(cell if cell is not None else [], dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        return np.zeros(3, dtype=float)
    return vector @ matrix


def _translate_visual_frame(data, display):
    """Apply the visual-only atom offset while leaving the unit cell fixed."""
    translation = _display_translation(display, data.get("cell"))
    if not np.any(np.abs(translation) > 1e-15):
        return translation
    positions = np.asarray(data.get("positions") or [], dtype=float)
    if positions.ndim == 2 and positions.shape[1:] == (3,):
        data["positions"] = (positions + translation).tolist()
    constraints = data.get("constraints")
    if isinstance(constraints, dict):
        for item in constraints.get("hookean") or []:
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "point":
                origin = np.asarray(item.get("origin") or [], dtype=float)
                if origin.shape == (3,) and np.all(np.isfinite(origin)):
                    item["origin"] = (origin + translation).tolist()
            elif item.get("kind") == "plane":
                plane = np.asarray(item.get("plane") or [], dtype=float)
                if plane.shape == (4,) and np.all(np.isfinite(plane)):
                    plane[3] -= float(np.dot(plane[:3], translation))
                    item["plane"] = plane.tolist()
    data["visual_translation"] = translation.tolist()
    return translation


def _cell_offsets(repetitions):
    return [
        (ix, iy, iz)
        for ix in range(repetitions[0])
        for iy in range(repetitions[1])
        for iz in range(repetitions[2])
    ]


def _offset_vector(offset, cell):
    return np.asarray(offset, dtype=float) @ cell


def _scene_cell_edges(cell, repetitions):
    if not np.any(cell):
        return []
    edge_axes = ((1, 2), (0, 2), (0, 1))
    edges = []
    seen = set()
    for offset in _cell_offsets(repetitions):
        origin = _offset_vector(offset, cell)
        for axis, (other_a, other_b) in enumerate(edge_axes):
            for bit_a in (0, 1):
                for bit_b in (0, 1):
                    start = origin + bit_a * cell[other_a] + bit_b * cell[other_b]
                    end = start + cell[axis]
                    key = tuple(sorted((
                        tuple(np.round(start, 8)),
                        tuple(np.round(end, 8)),
                    )))
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append({"start": start.tolist(), "end": end.tolist()})
    return edges


def _cad_scene_data(session, payload: Dict[str, Any]):
    """Normalize the current viewport into editable 3D geometry primitives."""
    payload = payload or {}
    atoms = _apply_payload_positions(session, payload)
    if getattr(session, "trajectory_frames", None):
        session.sync_current_frame()
    data = atoms_to_json(atoms)
    display = payload.get("display") or {}
    repetitions, cell = _normalized_supercell(display, data)
    visual_translation = _display_translation(display, data.get("cell"))
    offsets = _cell_offsets(repetitions)
    total_atoms = len(data.get("positions") or []) * len(offsets)
    if total_atoms > 1_000_000:
        raise ValueError(
            f"3D export would create {total_atoms:,} atom objects; reduce the supercell below 1,000,000 atoms."
        )

    labels = list(data.get("symbols") or [])
    symbols = list(data.get("chemical_symbols") or labels)
    positions = np.asarray(data.get("positions") or [], dtype=float)
    visual = data.get("visual") or {}
    base_colors = list(visual.get("colors") or [])
    base_radii = list(visual.get("radii") or [])
    visible_map = display.get("labelVisible") or display.get("elementVisible") or {}
    color_map = display.get("labelColors") or display.get("elementColors") or {}
    radius_map = display.get("labelRadii") or display.get("elementRadii") or {}
    opacity_map = display.get("labelOpacities") or {}
    label_materials = display.get("labelMaterials") or {}
    atom_radius_scales = display.get("atomRadiusScales") or {}
    atom_colors = display.get("atomColors") or {}
    atom_opacities = display.get("atomOpacities") or {}
    atom_materials = display.get("atomMaterials") or {}
    scale_colors = (
        display.get("atomColorScaleColors")
        if display.get("atomColorScaleEnabled") is True
        and isinstance(display.get("atomColorScaleColors"), list)
        else []
    )
    try:
        radius_scale = float(display.get("atomRadiusScale", 0.6))
    except (TypeError, ValueError):
        radius_scale = 0.6
    if not np.isfinite(radius_scale) or radius_scale <= 0:
        radius_scale = 0.6

    def atom_color(index, label):
        fallback = base_colors[index] if index < len(base_colors) else "#c8ccd0"
        established = _valid_hex_color(color_map.get(label), _valid_hex_color(fallback))
        if index < len(scale_colors):
            return _valid_hex_color(scale_colors[index], established)
        override = atom_colors.get(str(index), atom_colors.get(index))
        if override is not None:
            return _valid_hex_color(override, established)
        return established

    def atom_opacity(index, label):
        try:
            value = float(atom_opacities.get(
                str(index), atom_opacities.get(index, opacity_map.get(label, 1.0))
            ))
        except (TypeError, ValueError):
            value = 1.0
        if not np.isfinite(value):
            value = 1.0
        return max(0.0, min(1.0, value))

    atom_specs = []
    visible_indices = set()
    for index, position in enumerate(positions):
        label = labels[index] if index < len(labels) else symbols[index]
        if visible_map.get(label, True) is False:
            continue
        visible_indices.add(index)
        color = atom_color(index, label)
        try:
            source_radius = float(radius_map.get(label, base_radii[index]))
        except (IndexError, TypeError, ValueError):
            source_radius = 0.5
        radius = source_radius * radius_scale
        try:
            radius *= float(atom_radius_scales.get(str(index), atom_radius_scales.get(index, 1.0)))
        except (TypeError, ValueError):
            pass
        if not np.isfinite(radius) or radius <= 0:
            radius = 0.5 * radius_scale
        material_preset = _atom_material_preset(
            atom_materials.get(str(index), atom_materials.get(index, label_materials.get(label)))
        )
        for offset in offsets:
            shifted = position + _offset_vector(offset, cell) + visual_translation
            atom_specs.append({
                "index": index,
                "label": str(label),
                "symbol": str(symbols[index] if index < len(symbols) else label),
                "position": shifted.tolist(),
                "radius": float(radius),
                "color": color,
                "opacity": atom_opacity(index, label),
                "material": material_preset,
                "cell_offset": list(offset),
            })

    color_mode = display.get("bondColorMode", "split")
    custom_bond_color = _valid_hex_color(display.get("bondCustomColor"), "#c8ccd0")
    pair_bond_styles = display.get("pairwiseBondStyles") or {}
    atom_bond_styles = display.get("atomBondStyles") or {}
    try:
        bond_diameter = float(display.get("bondThickness", 0.25))
    except (TypeError, ValueError):
        bond_diameter = 0.25
    bond_diameter = max(0.02, min(0.6, bond_diameter))
    bond_radius = bond_diameter * 0.5
    bond_style = "flat" if display.get("bondStyle") == "flat" else "cylinder"
    bond_material = _atom_material_preset(display.get("bondMaterial"))
    try:
        bond_opacity = max(0.0, min(1.0, float(display.get("bondOpacity", 1.0))))
    except (TypeError, ValueError):
        bond_opacity = 1.0

    def bond_atom_color(index):
        label = labels[index] if index < len(labels) else symbols[index]
        return atom_color(index, label)

    def bond_appearance(i, j, endpoint=None):
        left = labels[i] if i < len(labels) else symbols[i]
        right = labels[j] if j < len(labels) else symbols[j]
        pair_key = "-".join(sorted((str(left), str(right))))
        pair = pair_bond_styles.get(pair_key)
        pair = pair if isinstance(pair, dict) else {}
        endpoint_style = atom_bond_styles.get(str(endpoint), atom_bond_styles.get(endpoint, {})) \
            if endpoint is not None else {}
        endpoint_style = endpoint_style if isinstance(endpoint_style, dict) else {}
        try:
            diameter = max(0.02, min(0.6, float(pair.get("thickness", bond_diameter))))
        except (TypeError, ValueError):
            diameter = bond_diameter
        try:
            opacity = max(0.0, min(1.0, float(endpoint_style.get(
                "opacity", pair.get("opacity", bond_opacity)
            ))))
        except (TypeError, ValueError):
            opacity = bond_opacity
        requested_color = endpoint_style.get("color", pair.get("color", custom_bond_color))
        return {
            "style": "flat" if pair.get("style", bond_style) == "flat" else "cylinder",
            "material": _atom_material_preset(endpoint_style.get(
                "material", pair.get("material", bond_material)
            )),
            "diameter": diameter,
            "radius": diameter * 0.5,
            "color_mode": "custom" if pair.get("colorMode", color_mode) == "custom" else "split",
            "custom_color": _valid_hex_color(requested_color, custom_bond_color),
            "opacity": opacity,
            "endpoint_override": bool(endpoint_style),
        }

    bond_specs = []

    def add_bond(i, j, start, end, suffix):
        start = np.asarray(start, dtype=float)
        end = np.asarray(end, dtype=float)
        if float(np.linalg.norm(end - start)) < 1e-9:
            return
        base_appearance = bond_appearance(i, j)
        left_appearance = bond_appearance(i, j, i)
        right_appearance = bond_appearance(i, j, j)
        if (
            base_appearance["color_mode"] == "custom"
            and not left_appearance["endpoint_override"]
            and not right_appearance["endpoint_override"]
        ):
            segments = ((0.0, 1.0, base_appearance["custom_color"], "full", base_appearance),)
        else:
            segments = (
                (
                    0.0, 0.5,
                    left_appearance["custom_color"]
                    if base_appearance["color_mode"] == "custom" else bond_atom_color(i),
                    "a", left_appearance,
                ),
                (
                    0.5, 1.0,
                    right_appearance["custom_color"]
                    if base_appearance["color_mode"] == "custom" else bond_atom_color(j),
                    "b", right_appearance,
                ),
            )
        delta = end - start
        logical_name = f"bond_{i}_{j}_{suffix}"
        for t0, t1, color, half, appearance in segments:
            bond_specs.append({
                "i": int(i),
                "j": int(j),
                "start": (start + delta * t0).tolist(),
                "end": (start + delta * t1).tolist(),
                "radius": appearance["radius"],
                "diameter": appearance["diameter"],
                "style": appearance["style"],
                "color": color,
                "material": appearance["material"],
                "opacity": appearance["opacity"],
                "name": f"{logical_name}_{half}",
                "logical_name": logical_name,
                "segment": half,
                "full_start": start.tolist(),
                "full_end": end.tolist(),
            })

    base_bonds = _display_bonds(data, display, payload.get("bond_pairs"))
    for bond in base_bonds:
        i, j = int(bond["i"]), int(bond["j"])
        if i not in visible_indices or j not in visible_indices:
            continue
        for offset in offsets:
            shift = _offset_vector(offset, cell)
            add_bond(
                i,
                j,
                np.asarray(bond["start"]) + shift + visual_translation,
                np.asarray(bond["end"]) + shift + visual_translation,
                "_".join(map(str, offset)),
            )

    for record in payload.get("bond_bridges") or []:
        try:
            i, j = int(record["i"]), int(record["j"])
            image_offset = tuple(int(value) for value in record["imageOffset"])
        except (KeyError, TypeError, ValueError):
            continue
        if len(image_offset) != 3 or i not in visible_indices or j not in visible_indices:
            continue
        for offset in offsets:
            end_offset = tuple(offset[axis] + image_offset[axis] for axis in range(3))
            if not all(0 <= end_offset[axis] < repetitions[axis] for axis in range(3)):
                continue
            start = positions[i] + _offset_vector(offset, cell) + visual_translation
            end = positions[j] + _offset_vector(end_offset, cell) + visual_translation
            add_bond(i, j, start, end, "bridge_" + "_".join(map(str, offset)))

    include_cell = payload.get("include_cell")
    if include_cell is None:
        include_cell = display.get("showCell", True)
    try:
        cell_thickness = max(0.01, min(0.30, float(display.get("cellThickness", 0.04))))
    except (TypeError, ValueError):
        cell_thickness = 0.04
    cell_material = str(display.get("cellMaterial", "unlit"))
    if cell_material not in {"unlit", "standard", "metal"}:
        cell_material = "unlit"
    return {
        "atoms": atom_specs,
        "bonds": bond_specs,
        "cell_edges": _scene_cell_edges(cell, repetitions) if include_cell else [],
        "cell_color": _valid_hex_color(display.get("cellColor"), "#d6bd67"),
        "cell_thickness": cell_thickness,
        "cell_material": cell_material,
        "camera": copy.deepcopy(payload.get("camera") or {}),
        "include_cell": bool(include_cell),
        "repetitions": repetitions,
        "translation": visual_translation.tolist(),
        "units": "angstrom",
    }


def _cad_object_attributes(rhino3dm, name, layer_index, material_index, color, metadata=None):
    attributes = rhino3dm.ObjectAttributes()
    attributes.Name = _safe_name(name)
    attributes.LayerIndex = layer_index
    attributes.MaterialIndex = material_index
    attributes.MaterialSource = rhino3dm.ObjectMaterialSource.MaterialFromObject
    rgba = (*_hex_rgb(color), 255)
    attributes.ObjectColor = rgba
    attributes.ColorSource = rhino3dm.ObjectColorSource.ColorFromObject
    for key, value in (metadata or {}).items():
        attributes.SetUserString(str(key), str(value))
    return attributes


def _perpendicular_basis(direction):
    axis = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(axis))
    if length < 1e-12:
        return None
    axis /= length
    reference = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    side = np.cross(axis, reference)
    side /= max(float(np.linalg.norm(side)), 1e-12)
    normal = np.cross(axis, side)
    return axis, side, normal, length


def _rhino_parent_attributes(rhino3dm, layer_index):
    attributes = rhino3dm.ObjectAttributes()
    attributes.LayerIndex = layer_index
    attributes.MaterialSource = rhino3dm.ObjectMaterialSource.MaterialFromParent
    attributes.ColorSource = rhino3dm.ObjectColorSource.ColorFromParent
    return attributes


def _rhino_instance_transform(rhino3dm, x_axis, y_axis, z_axis, origin):
    """Create an affine transform from local basis columns and an origin."""
    x_axis = np.asarray(x_axis, dtype=float)
    y_axis = np.asarray(y_axis, dtype=float)
    z_axis = np.asarray(z_axis, dtype=float)
    origin = np.asarray(origin, dtype=float)
    transform = rhino3dm.Transform.Identity()
    transform.M00, transform.M10, transform.M20 = x_axis.tolist()
    transform.M01, transform.M11, transform.M21 = y_axis.tolist()
    transform.M02, transform.M12, transform.M22 = z_axis.tolist()
    transform.M03, transform.M13, transform.M23 = origin.tolist()
    return transform


def _add_rhino_definition(model, rhino3dm, name, geometry, layer_index):
    attributes = _rhino_parent_attributes(rhino3dm, layer_index)
    index = model.InstanceDefinitions.Add(
        name,
        "Reusable v_ase export primitive",
        "",
        "",
        rhino3dm.Point3d(0.0, 0.0, 0.0),
        (geometry,),
        (attributes,),
    )
    if index < 0:
        raise RuntimeError(f"rhino3dm could not create the {name!r} instance definition.")
    return model.InstanceDefinitions.FindIndex(index).Id


def _normalized_camera_payload(camera):
    camera = camera if isinstance(camera, dict) else {}

    def vector(name, fallback):
        value = camera.get(name)
        if isinstance(value, (list, tuple)) and len(value) == 3:
            parsed = np.asarray(value, dtype=float)
            if np.all(np.isfinite(parsed)):
                return parsed
        return np.asarray(fallback, dtype=float)

    position = vector("position", [8.0, -9.0, 6.0])
    target = vector("target", [0.0, 0.0, 0.0])
    up = vector("up", [0.0, 0.0, 1.0])
    direction = target - position
    distance = float(np.linalg.norm(direction))
    if distance < 1e-8:
        position = target + np.array([8.0, -9.0, 6.0])
        direction = target - position
        distance = float(np.linalg.norm(direction))
    if float(np.linalg.norm(up)) < 1e-8:
        up = np.array([0.0, 0.0, 1.0])
    up /= float(np.linalg.norm(up))

    def finite_float(name, fallback, minimum=None):
        try:
            value = float(camera.get(name, fallback))
        except (TypeError, ValueError):
            value = float(fallback)
        if not np.isfinite(value):
            value = float(fallback)
        return max(minimum, value) if minimum is not None else value

    near = finite_float("near", max(0.001, distance / 1000.0), 1e-6)
    far = finite_float("far", max(1000.0, distance * 10.0), near + 1e-3)
    aspect = finite_float("aspect", 16.0 / 9.0, 1e-3)
    return {
        "position": position,
        "target": target,
        "up": up,
        "direction": direction,
        "distance": distance,
        "projection": "perspective" if camera.get("projection") == "perspective" else "orthographic",
        "fov": min(179.0, finite_float("fov", 50.0, 1e-3)),
        "ortho_scale": finite_float("ortho_scale", max(1.0, distance * 0.75), 1e-6),
        "near": near,
        "far": far,
        "aspect": aspect,
    }


def _rhino_view_info(rhino3dm, camera, name="v_ase View"):
    normalized = _normalized_camera_payload(camera)
    view = rhino3dm.ViewInfo()
    view.Name = name
    viewport = view.Viewport
    viewport.SetCameraLocation(rhino3dm.Point3d(*normalized["position"].tolist()))
    viewport.SetCameraDirection(rhino3dm.Vector3d(*normalized["direction"].tolist()))
    viewport.SetCameraUp(rhino3dm.Vector3d(*normalized["up"].tolist()))
    viewport.TargetPoint = rhino3dm.Point3d(*normalized["target"].tolist())
    if normalized["projection"] == "perspective":
        viewport.ChangeToPerspectiveProjection(normalized["distance"], True, 50.0)
        half_height = normalized["near"] * math.tan(math.radians(normalized["fov"]) * 0.5)
    else:
        viewport.ChangeToParallelProjection(True)
        half_height = normalized["ortho_scale"] * 0.5
    half_width = half_height * normalized["aspect"]
    viewport.SetFrustum(
        -half_width,
        half_width,
        -half_height,
        half_height,
        normalized["near"],
        normalized["far"],
    )
    return view


def export_3dm_response(session, payload: Dict[str, Any]):
    try:
        import rhino3dm
    except ImportError as exc:
        raise OptionalExportDependencyError(
            '3DM export requires the optional "rhino3dm" package. Install it with '
            'python -m pip install "v_ase-gui[rhino]".'
        ) from exc

    scene = _cad_scene_data(session, payload)
    model = rhino3dm.File3dm()
    model.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Angstroms
    model.ApplicationName = "v_ase"
    model.ApplicationDetails = "Editable atomistic scene exported by v_ase"

    layer_indices = {}
    for name, color in (
        ("Atoms", "#d7dce1"),
        ("Bonds", "#aeb6bf"),
        ("Unit Cell", scene["cell_color"]),
    ):
        layer = rhino3dm.Layer()
        layer.Name = name
        layer.Color = (*_hex_rgb(color), 255)
        layer_indices[name] = model.Layers.Add(layer)

    material_indices = {}

    def material_index(color, preset="standard", opacity=1.0):
        color = _valid_hex_color(color)
        preset = _atom_material_preset(preset)
        try:
            opacity = max(0.0, min(1.0, float(opacity)))
        except (TypeError, ValueError):
            opacity = 1.0
        key = (color, preset, round(opacity, 6))
        if key in material_indices:
            return material_indices[key]
        material = rhino3dm.Material()
        material.Name = f"v_ase_{preset}_{color[1:]}_a{round(opacity * 10000):04d}"
        material.DiffuseColor = (*_hex_rgb(color), 255)
        if hasattr(material, "Transparency"):
            material.Transparency = 1.0 - opacity
        if preset == "metal":
            material.Shine = 246.0
            material.Reflectivity = 0.92
            material.ReflectionGlossiness = 0.96
            material.FresnelReflections = True
        elif preset == "rubber":
            material.Shine = 18.0
            material.Reflectivity = 0.01
            material.ReflectionGlossiness = 0.12
            material.SpecularColor = (36, 36, 36, 255)
        else:
            material.Shine = 176.0
            material.Reflectivity = 0.03
            material.ReflectionGlossiness = 0.74
        material_indices[key] = model.Materials.Add(material)
        return material_indices[key]

    definition_ids = {}
    if scene["atoms"]:
        sphere = rhino3dm.Sphere(rhino3dm.Point3d(0.0, 0.0, 0.0), 1.0).ToNurbsSurface()
        definition_ids["atom"] = _add_rhino_definition(
            model, rhino3dm, "v_ase_atom_unit_sphere", sphere, layer_indices["Atoms"]
        )
    bond_definition_ids = {}

    def bond_definition(style, segment_materials):
        key = (style, tuple(segment_materials))
        if key in bond_definition_ids:
            return bond_definition_ids[key]
        fractions = [(0.0, 1.0)] if len(segment_materials) == 1 else [(0.0, 0.5), (0.5, 1.0)]
        geometry = []
        attributes = []
        for index, ((start_fraction, end_fraction), specification) in enumerate(
            zip(fractions, segment_materials)
        ):
            color, preset, opacity = specification
            if style == "flat":
                primitive = rhino3dm.Mesh()
                for point in (
                    (-0.5, 0.0, start_fraction),
                    (0.5, 0.0, start_fraction),
                    (0.5, 0.0, end_fraction),
                    (-0.5, 0.0, end_fraction),
                ):
                    primitive.Vertices.Add(*point)
                primitive.Faces.AddFace(0, 1, 2, 3)
            else:
                plane = rhino3dm.Plane(
                    rhino3dm.Point3d(0.0, 0.0, start_fraction),
                    rhino3dm.Vector3d(0.0, 0.0, 1.0),
                )
                circle = rhino3dm.Circle(0.5)
                circle.Plane = plane
                primitive = rhino3dm.Cylinder(circle, end_fraction - start_fraction).ToBrep(True, True)
            geometry.append(primitive)
            attributes.append(_cad_object_attributes(
                rhino3dm,
                f"bond_segment_{index}",
                layer_indices["Bonds"],
                material_index(color, preset, opacity),
                color,
            ))
        definition_name = _safe_name(
            f"v_ase_bond_{style}_{'_'.join(color.lstrip('#') for color, _, _ in segment_materials)}"
        )
        definition_index = model.InstanceDefinitions.Add(
            definition_name,
            "Reusable v_ase bond primitive; parent scale stores diameter and length",
            "",
            "",
            rhino3dm.Point3d(0.0, 0.0, 0.0),
            tuple(geometry),
            tuple(attributes),
        )
        if definition_index < 0:
            raise RuntimeError("rhino3dm could not create a bond instance definition.")
        identifier = model.InstanceDefinitions.FindIndex(definition_index).Id
        bond_definition_ids[key] = identifier
        return identifier

    for atom in scene["atoms"]:
        offset = ",".join(map(str, atom["cell_offset"]))
        attributes = _cad_object_attributes(
            rhino3dm,
            f"atom_{atom['index']}_{atom['label']}_cell_{offset}",
            layer_indices["Atoms"],
            material_index(atom["color"], atom["material"], atom["opacity"]),
            atom["color"],
            {
                "v_ase.kind": "atom",
                "v_ase.index": atom["index"],
                "v_ase.label": atom["label"],
                "v_ase.element": atom["symbol"],
                "v_ase.material": atom["material"],
                "v_ase.opacity": atom["opacity"],
                "v_ase.cell_offset": offset,
                "v_ase.units": "angstrom",
            },
        )
        radius = float(atom["radius"])
        transform = _rhino_instance_transform(
            rhino3dm,
            [radius, 0.0, 0.0],
            [0.0, radius, 0.0],
            [0.0, 0.0, radius],
            atom["position"],
        )
        reference = rhino3dm.InstanceReference(definition_ids["atom"], transform)
        model.Objects.AddInstanceObject(reference, attributes)

    grouped_bonds = {}
    for bond in scene["bonds"]:
        grouped_bonds.setdefault(bond["logical_name"], []).append(bond)

    for logical_name, segments in grouped_bonds.items():
        bond = segments[0]
        start = np.asarray(bond["full_start"], dtype=float)
        end = np.asarray(bond["full_end"], dtype=float)
        basis = _perpendicular_basis(end - start)
        if basis is None:
            continue
        axis, side, normal, length = basis
        colors = tuple(segment["color"] for segment in segments)
        segment_materials = tuple((
            segment["color"],
            _atom_material_preset(segment.get("material")),
            round(float(segment.get("opacity", 1.0)), 6),
        ) for segment in segments)
        attributes = _cad_object_attributes(
            rhino3dm,
            logical_name,
            layer_indices["Bonds"],
            material_index(*segment_materials[0]),
            colors[0],
            {
                "v_ase.kind": "bond",
                "v_ase.atom_i": bond["i"],
                "v_ase.atom_j": bond["j"],
                "v_ase.style": bond["style"],
                "v_ase.materials": ",".join(specification[1] for specification in segment_materials),
                "v_ase.opacities": ",".join(str(specification[2]) for specification in segment_materials),
                "v_ase.colors": ",".join(colors),
                "v_ase.units": "angstrom",
            },
        )
        diameter = float(bond.get("diameter", float(bond["radius"]) * 2.0))
        transform = _rhino_instance_transform(
            rhino3dm,
            side * diameter,
            normal * diameter,
            axis * length,
            start,
        )
        reference = rhino3dm.InstanceReference(
            bond_definition(bond["style"], segment_materials), transform
        )
        model.Objects.AddInstanceObject(reference, attributes)

    cell_color = scene["cell_color"]
    cell_preset = "metal" if scene["cell_material"] == "metal" else "standard"
    cell_material = material_index(cell_color, cell_preset)
    cell_definition_id = None
    if scene["cell_edges"]:
        plane = rhino3dm.Plane(
            rhino3dm.Point3d(0.0, 0.0, 0.0),
            rhino3dm.Vector3d(0.0, 0.0, 1.0),
        )
        circle = rhino3dm.Circle(0.5)
        circle.Plane = plane
        primitive = rhino3dm.Cylinder(circle, 1.0).ToBrep(True, True)
        cell_definition_index = model.InstanceDefinitions.Add(
            "v_ase_unit_cell_edge",
            "Reusable v_ase unit-cell edge; parent scale stores diameter and length",
            "",
            "",
            rhino3dm.Point3d(0.0, 0.0, 0.0),
            (primitive,),
            (_cad_object_attributes(
                rhino3dm,
                "cell_edge_primitive",
                layer_indices["Unit Cell"],
                cell_material,
                cell_color,
            ),),
        )
        if cell_definition_index < 0:
            raise RuntimeError("rhino3dm could not create a unit-cell edge definition.")
        cell_definition_id = model.InstanceDefinitions.FindIndex(cell_definition_index).Id
    for index, edge in enumerate(scene["cell_edges"]):
        start = np.asarray(edge["start"], dtype=float)
        end = np.asarray(edge["end"], dtype=float)
        basis = _perpendicular_basis(end - start)
        if basis is None:
            continue
        axis, side, normal, length = basis
        attributes = _cad_object_attributes(
            rhino3dm,
            f"cell_edge_{index}",
            layer_indices["Unit Cell"],
            cell_material,
            cell_color,
            {
                "v_ase.kind": "unit_cell",
                "v_ase.units": "angstrom",
                "v_ase.thickness": scene["cell_thickness"],
                "v_ase.material": scene["cell_material"],
            },
        )
        diameter = float(scene["cell_thickness"])
        transform = _rhino_instance_transform(
            rhino3dm,
            side * diameter,
            normal * diameter,
            axis * length,
            start,
        )
        model.Objects.AddInstanceObject(
            rhino3dm.InstanceReference(cell_definition_id, transform),
            attributes,
        )

    model.Views.Add(_rhino_view_info(rhino3dm, scene.get("camera"), "v_ase View"))
    model.NamedViews.Add(_rhino_view_info(rhino3dm, scene.get("camera"), "v_ase Saved View"))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".3dm")
    tmp.close()
    if not model.Write(tmp.name, 7):
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise RuntimeError("rhino3dm could not write the 3DM scene.")
    return FileResponse(tmp.name, filename="v_ase_scene.3dm", media_type="model/vnd.3dm")


class _ObjWriter:
    def __init__(self, handle):
        self.handle = handle
        self.vertex_index = 1

    def _vertices_with_normals(self, vertices, normals):
        start = self.vertex_index
        for vertex in vertices:
            self.handle.write("v {:.9g} {:.9g} {:.9g}\n".format(*vertex))
        for normal in normals:
            self.handle.write("vn {:.9g} {:.9g} {:.9g}\n".format(*normal))
        self.vertex_index += len(vertices)
        return start

    def sphere(self, name, center, radius, material, segments, stacks):
        center = np.asarray(center, dtype=float)
        vertices = [center + np.array([0.0, 0.0, radius])]
        normals = [np.array([0.0, 0.0, 1.0])]
        for stack in range(1, stacks):
            phi = math.pi * stack / stacks
            for segment in range(segments):
                theta = 2.0 * math.pi * segment / segments
                normal = np.array([
                    math.sin(phi) * math.cos(theta),
                    math.sin(phi) * math.sin(theta),
                    math.cos(phi),
                ])
                vertices.append(center + radius * normal)
                normals.append(normal)
        vertices.append(center + np.array([0.0, 0.0, -radius]))
        normals.append(np.array([0.0, 0.0, -1.0]))
        start = self._vertices_with_normals(vertices, normals)
        bottom = start + len(vertices) - 1
        self.handle.write(f"o {_safe_name(name)}\nusemtl {material}\ns 1\n")

        def ref(local):
            index = start + local
            return f"{index}//{index}"

        for segment in range(segments):
            first = 1 + segment
            second = 1 + (segment + 1) % segments
            self.handle.write(f"f {ref(0)} {ref(first)} {ref(second)}\n")
        for stack in range(stacks - 2):
            ring_a = 1 + stack * segments
            ring_b = ring_a + segments
            for segment in range(segments):
                a = ring_a + segment
                b = ring_a + (segment + 1) % segments
                c = ring_b + (segment + 1) % segments
                d = ring_b + segment
                self.handle.write(f"f {ref(a)} {ref(d)} {ref(c)} {ref(b)}\n")
        last_ring = 1 + (stacks - 2) * segments
        for segment in range(segments):
            first = last_ring + segment
            second = last_ring + (segment + 1) % segments
            self.handle.write(f"f {ref(first)} {ref(bottom - start)} {ref(second)}\n")

    def cylinder(self, name, start_point, end_point, radius, material, segments=12):
        start_point = np.asarray(start_point, dtype=float)
        end_point = np.asarray(end_point, dtype=float)
        basis = _perpendicular_basis(end_point - start_point)
        if basis is None:
            return
        _, side, normal, _ = basis
        vertices = []
        normals = []
        for point in (start_point, end_point):
            for segment in range(segments):
                theta = 2.0 * math.pi * segment / segments
                radial = math.cos(theta) * side + math.sin(theta) * normal
                vertices.append(point + radius * radial)
                normals.append(radial)
        start = self._vertices_with_normals(vertices, normals)
        self.handle.write(f"o {_safe_name(name)}\nusemtl {material}\ns 1\n")

        def ref(local):
            index = start + local
            return f"{index}//{index}"

        for segment in range(segments):
            next_segment = (segment + 1) % segments
            self.handle.write(
                f"f {ref(segment)} {ref(segment + segments)} "
                f"{ref(next_segment + segments)} {ref(next_segment)}\n"
            )

    def ribbon(self, name, start_point, end_point, half_width, material):
        start_point = np.asarray(start_point, dtype=float)
        end_point = np.asarray(end_point, dtype=float)
        basis = _perpendicular_basis(end_point - start_point)
        if basis is None:
            return
        _, side, normal, _ = basis
        vertices = [
            start_point - side * half_width,
            start_point + side * half_width,
            end_point + side * half_width,
            end_point - side * half_width,
        ]
        normals = [normal] * 4
        start = self._vertices_with_normals(vertices, normals)
        refs = [f"{start + index}//{start + index}" for index in range(4)]
        self.handle.write(f"o {_safe_name(name)}\nusemtl {material}\ns off\n")
        self.handle.write(f"f {' '.join(refs)}\n")
        self.handle.write(f"f {' '.join(reversed(refs))}\n")

    def line(self, name, start_point, end_point, material):
        start = self.vertex_index
        for point in (start_point, end_point):
            self.handle.write("v {:.9g} {:.9g} {:.9g}\n".format(*point))
        self.vertex_index += 2
        self.handle.write(
            f"o {_safe_name(name)}\nusemtl {material}\nl {start} {start + 1}\n"
        )


def _obj_sphere_resolution(scene, display):
    count = max(1, len(scene["atoms"]))
    quality = str(display.get("imageSphereQuality") or "viewport").lower()
    requested = {
        "low": (10, 6),
        "medium": (16, 10),
        "high": (24, 14),
        "ultra": (32, 18),
    }.get(quality, (16, 10))
    if count > 20_000:
        return 8, 5
    if count > 5_000:
        return min(requested[0], 10), min(requested[1], 6)
    if count > 1_000:
        return min(requested[0], 12), min(requested[1], 8)
    return requested


def export_obj_response(session, payload: Dict[str, Any]):
    scene = _cad_scene_data(session, payload)
    display = payload.get("display") or {}
    material_specs = {
        (
            atom["color"],
            _atom_material_preset(atom.get("material")),
            round(float(atom.get("opacity", 1.0)), 6),
        )
        for atom in scene["atoms"]
    }
    material_specs.update((
        bond["color"],
        _atom_material_preset(bond.get("material")),
        round(float(bond.get("opacity", 1.0)), 6),
    ) for bond in scene["bonds"])
    if scene["cell_edges"]:
        cell_preset = "metal" if scene["cell_material"] == "metal" else "standard"
        material_specs.add((scene["cell_color"], cell_preset, 1.0))
    material_specs = sorted(material_specs)
    materials = {
        spec: (
            f"v_ase_{spec[1]}_{spec[0][1:]}"
            + ("" if spec[2] >= 0.999999 else f"_a{round(spec[2] * 10000):04d}")
        )
        for spec in material_specs
    }
    segments, stacks = _obj_sphere_resolution(scene, display)

    workdir = tempfile.mkdtemp(prefix="v_ase_obj_")
    obj_path = os.path.join(workdir, "v_ase_scene.obj")
    mtl_path = os.path.join(workdir, "v_ase_scene.mtl")
    metadata_path = os.path.join(workdir, "v_ase_scene.json")
    with open(mtl_path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("# v_ase material library\n")
        for color, preset, opacity in material_specs:
            red, green, blue = (channel / 255.0 for channel in _hex_rgb(color))
            if preset == "metal":
                specular, shine, illumination = 0.98, 246.0, 3
            elif preset == "rubber":
                specular, shine, illumination = 0.06, 12.0, 2
            else:
                specular, shine, illumination = 0.52, 144.0, 2
            handle.write(
                f"newmtl {materials[(color, preset, opacity)]}\n"
                f"Ka {red * 0.18:.6f} {green * 0.18:.6f} {blue * 0.18:.6f}\n"
                f"Kd {red:.6f} {green:.6f} {blue:.6f}\n"
                f"Ks {specular:.6f} {specular:.6f} {specular:.6f}\n"
                f"Ns {shine:.6f}\nd {opacity:.6f}\nillum {illumination}\n\n"
            )

    with open(obj_path, "w", encoding="ascii", newline="\n") as handle:
        handle.write(
            "# v_ase editable atomistic scene\n"
            "# Coordinates and radii are in angstrom\n"
            "# Bond thickness is stored as a diameter in angstrom\n"
            f"# v_ase.camera {json.dumps(scene.get('camera') or {}, separators=(',', ':'))}\n"
            "mtllib v_ase_scene.mtl\n"
        )
        writer = _ObjWriter(handle)
        for atom in scene["atoms"]:
            offset = "_".join(map(str, atom["cell_offset"]))
            writer.sphere(
                f"atom_{atom['index']}_{atom['label']}_cell_{offset}",
                atom["position"],
                atom["radius"],
                materials[(
                    atom["color"],
                    atom["material"],
                    round(float(atom.get("opacity", 1.0)), 6),
                )],
                segments,
                stacks,
            )
        for bond in scene["bonds"]:
            bond_material_key = (
                bond["color"],
                _atom_material_preset(bond.get("material")),
                round(float(bond.get("opacity", 1.0)), 6),
            )
            if bond["style"] == "flat":
                writer.ribbon(
                    bond["name"], bond["start"], bond["end"], bond["radius"],
                    materials[bond_material_key]
                )
            else:
                writer.cylinder(
                    bond["name"], bond["start"], bond["end"], bond["radius"],
                    materials[bond_material_key]
                )
        for index, edge in enumerate(scene["cell_edges"]):
            cell_preset = "metal" if scene["cell_material"] == "metal" else "standard"
            writer.cylinder(
                f"cell_edge_{index}",
                edge["start"],
                edge["end"],
                float(scene["cell_thickness"]) * 0.5,
                materials[(scene["cell_color"], cell_preset, 1.0)],
            )

    with open(metadata_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            {
                "schema": "v_ase.obj_scene.v1",
                "units": scene["units"],
                "camera": scene.get("camera") or {},
                "include_cell": scene["include_cell"],
                "repetitions": scene["repetitions"],
                "translation": scene["translation"],
                "atoms": scene["atoms"],
                "bonds": scene["bonds"],
                "cell_edges": scene["cell_edges"],
                "cell_color": scene["cell_color"],
                "cell_thickness": scene["cell_thickness"],
                "cell_material": scene["cell_material"],
                "bond_thickness_semantics": "diameter",
            },
            handle,
            ensure_ascii=True,
            separators=(",", ":"),
        )

    archive = tempfile.NamedTemporaryFile(delete=False, suffix="_v_ase_obj.zip")
    archive.close()
    with zipfile.ZipFile(archive.name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        bundle.write(obj_path, arcname="v_ase_scene.obj")
        bundle.write(mtl_path, arcname="v_ase_scene.mtl")
        bundle.write(metadata_path, arcname="v_ase_scene.json")
    try:
        os.unlink(obj_path)
        os.unlink(mtl_path)
        os.unlink(metadata_path)
        os.rmdir(workdir)
    except OSError:
        pass
    return FileResponse(archive.name, filename="v_ase_obj_scene.zip", media_type="application/zip")


def _blender_script(data: Dict[str, Any]) -> str:
    return f'''# Generated by v_ase. Run in Blender with: blender --python this_file.py
import math
import bpy
from mathutils import Vector

DATA = {repr(data)}
FRAMES = DATA.get("frames", [])
CAMERA = DATA.get("camera", {{}})
BONDS = DATA.get("bonds", [])
CELL = DATA.get("cell", [])
INCLUDE_CELL = bool(DATA.get("include_cell", True))
DISPLAY = DATA.get("display", {{}})
LIGHTING = DATA.get("lighting", {{}})
BOND_STYLE = DISPLAY.get("bondStyle", "cylinder")
BOND_COLOR_MODE = DISPLAY.get("bondColorMode", "split")
BOND_CUSTOM_COLOR = DISPLAY.get("bondCustomColor", "#c8ccd0")
BOND_MATERIAL = DISPLAY.get("bondMaterial", "standard")
DISPLAY_PAIR_BOND_STYLES = DISPLAY.get("pairwiseBondStyles", {{}})
DISPLAY_ATOM_BOND_STYLES = DISPLAY.get("atomBondStyles", {{}})
BLENDER_OBJECT_MODE = DISPLAY.get("blenderExportMode", "instanced")
CELL_COLOR = DISPLAY.get("cellColor", "#d6bd67")
CELL_MATERIAL = DISPLAY.get("cellMaterial", "unlit")
try:
    BOND_THICKNESS = max(0.02, min(0.6, float(DISPLAY.get("bondThickness", 0.25))))
except (TypeError, ValueError):
    BOND_THICKNESS = 0.25
try:
    BOND_OPACITY = max(0.0, min(1.0, float(DISPLAY.get("bondOpacity", 1.0))))
except (TypeError, ValueError):
    BOND_OPACITY = 1.0
try:
    CELL_THICKNESS = max(0.01, min(0.30, float(DISPLAY.get("cellThickness", 0.04))))
except (TypeError, ValueError):
    CELL_THICKNESS = 0.04

VISUAL = DATA.get("visual", {{}})
ATOM_COLORS = VISUAL.get("colors", [])
ATOM_RADII = VISUAL.get("radii", VISUAL.get("covalent_radii", []))
ATOM_LABELS = DATA.get("symbols", [])
DISPLAY_LABEL_COLORS = DISPLAY.get("labelColors", DISPLAY.get("elementColors", {{}}))
DISPLAY_LABEL_RADII = DISPLAY.get("labelRadii", DISPLAY.get("elementRadii", {{}}))
DISPLAY_LABEL_OPACITIES = DISPLAY.get("labelOpacities", {{}})
DISPLAY_LABEL_VISIBLE = DISPLAY.get("labelVisible", DISPLAY.get("elementVisible", {{}}))
DISPLAY_LABEL_MATERIALS = DISPLAY.get("labelMaterials", {{}})
DISPLAY_ATOM_RADIUS_SCALES = DISPLAY.get("atomRadiusScales", {{}})
DISPLAY_ATOM_COLORS = DISPLAY.get("atomColors", {{}})
DISPLAY_ATOM_OPACITIES = DISPLAY.get("atomOpacities", {{}})
DISPLAY_ATOM_MATERIALS = DISPLAY.get("atomMaterials", {{}})
DISPLAY_ATOM_COLOR_SCALE_COLORS = DISPLAY.get("atomColorScaleColors", []) \
    if DISPLAY.get("atomColorScaleEnabled") else []
MATERIAL_PRESETS = {{
    "standard": {{"roughness": 0.28, "metalness": 0.0, "specular": 1.0, "clearcoat": 0.04, "clearcoat_roughness": 0.22}},
    "metal": {{"roughness": 0.11, "metalness": 0.96, "specular": 1.0, "clearcoat": 0.03, "clearcoat_roughness": 0.08}},
    "rubber": {{"roughness": 0.88, "metalness": 0.0, "specular": 0.16, "clearcoat": 0.0, "clearcoat_roughness": 0.8}},
    "unlit": {{"roughness": 1.0, "metalness": 0.0, "specular": 0.0, "clearcoat": 0.0, "clearcoat_roughness": 1.0}},
}}
try:
    ATOM_RADIUS_SCALE = max(0.01, float(DISPLAY.get("atomRadiusScale", 0.6)))
except (TypeError, ValueError):
    ATOM_RADIUS_SCALE = 0.6
FALLBACK_COLOR = (0.8, 0.8, 0.8, 1.0)
FALLBACK_RADIUS = 0.7

def clamp01(value):
    return max(0.0, min(1.0, float(value)))

def hex_to_rgba(value):
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 6:
            try:
                return (
                    int(text[0:2], 16) / 255.0,
                    int(text[2:4], 16) / 255.0,
                    int(text[4:6], 16) / 255.0,
                    1.0,
                )
            except ValueError:
                pass
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (clamp01(value[0]), clamp01(value[1]), clamp01(value[2]), clamp01(value[3]) if len(value) > 3 else 1.0)
    return FALLBACK_COLOR

def get_atom_color(index):
    if 0 <= index < len(DISPLAY_ATOM_COLOR_SCALE_COLORS):
        color = DISPLAY_ATOM_COLOR_SCALE_COLORS[index]
        if color:
            return hex_to_rgba(color)
    atom_color = DISPLAY_ATOM_COLORS.get(str(index), DISPLAY_ATOM_COLORS.get(index))
    if atom_color:
        return hex_to_rgba(atom_color)
    if 0 <= index < len(ATOM_LABELS):
        display_color = DISPLAY_LABEL_COLORS.get(ATOM_LABELS[index])
        if display_color:
            return hex_to_rgba(display_color)
    if 0 <= index < len(ATOM_COLORS):
        return hex_to_rgba(ATOM_COLORS[index])
    return FALLBACK_COLOR

def get_atom_radius(index, fallback=FALLBACK_RADIUS):
    try:
        atom_scale = max(0.01, float(DISPLAY_ATOM_RADIUS_SCALES.get(
            str(index), DISPLAY_ATOM_RADIUS_SCALES.get(index, 1.0)
        )))
    except (TypeError, ValueError):
        atom_scale = 1.0
    if 0 <= index < len(ATOM_LABELS):
        try:
            display_radius = float(DISPLAY_LABEL_RADII.get(ATOM_LABELS[index], 0.0))
            if display_radius > 0:
                return display_radius * ATOM_RADIUS_SCALE * atom_scale
        except (TypeError, ValueError):
            pass
    if 0 <= index < len(ATOM_RADII):
        try:
            radius = float(ATOM_RADII[index])
            if radius > 0:
                return radius * ATOM_RADIUS_SCALE * atom_scale
        except (TypeError, ValueError):
            pass
    return fallback * ATOM_RADIUS_SCALE * atom_scale

def get_atom_opacity(index):
    try:
        override = DISPLAY_ATOM_OPACITIES.get(str(index), DISPLAY_ATOM_OPACITIES.get(index))
        if override is not None:
            return clamp01(override)
    except (TypeError, ValueError):
        pass
    if 0 <= index < len(ATOM_LABELS):
        try:
            return clamp01(DISPLAY_LABEL_OPACITIES.get(ATOM_LABELS[index], 1.0))
        except (TypeError, ValueError):
            pass
    return 1.0

def get_atom_material_preset(index):
    value = DISPLAY_ATOM_MATERIALS.get(str(index), DISPLAY_ATOM_MATERIALS.get(index))
    if value not in MATERIAL_PRESETS and 0 <= index < len(ATOM_LABELS):
        value = DISPLAY_LABEL_MATERIALS.get(ATOM_LABELS[index])
    return value if value in MATERIAL_PRESETS else "standard"

def material(name, color, alpha=1.0, preset="standard"):
    mat = bpy.data.materials.new(name)
    rgba = (clamp01(color[0]), clamp01(color[1]), clamp01(color[2]), clamp01(alpha))
    preset = preset if preset in MATERIAL_PRESETS else "standard"
    surface = MATERIAL_PRESETS[preset]
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        base_color = bsdf.inputs.get("Base Color")
        if base_color is not None:
            base_color.default_value = rgba
        alpha_input = bsdf.inputs.get("Alpha")
        if alpha_input is not None:
            alpha_input.default_value = rgba[3]
        roughness = bsdf.inputs.get("Roughness")
        if roughness is not None:
            roughness.default_value = surface["roughness"]
        metallic = bsdf.inputs.get("Metallic")
        if metallic is not None:
            metallic.default_value = surface["metalness"]
        specular = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
        if specular is not None:
            specular.default_value = min(1.0, surface["specular"] * 0.5)
        clearcoat = bsdf.inputs.get("Coat Weight") or bsdf.inputs.get("Clearcoat")
        if clearcoat is not None:
            clearcoat.default_value = surface["clearcoat"]
        clearcoat_roughness = (
            bsdf.inputs.get("Coat Roughness")
            or bsdf.inputs.get("Clearcoat Roughness")
        )
        if clearcoat_roughness is not None:
            clearcoat_roughness.default_value = surface["clearcoat_roughness"]
    if alpha < 1.0:
        try:
            mat.surface_render_method = "DITHERED"
        except (AttributeError, TypeError, ValueError):
            try:
                mat.blend_method = "BLEND"
            except (AttributeError, TypeError, ValueError):
                pass
        if hasattr(mat, "show_transparent_back"):
            mat.show_transparent_back = True
    return mat

ATOM_MATS = {{}}
ATOM_MESHES = {{}}
BOND_MATS = {{}}
MAT_LINE = material("v_ase fixed line", (0.3, 0.8, 1.0, 0.55), 0.55)
MAT_PLANE = material("v_ase fixed plane", (0.25, 1.0, 0.78, 0.22), 0.22)
MAT_HOOKEAN = material("v_ase Hookean active spring", (1.0, 0.58, 0.18, 1.0), 1.0)
MAT_HOOKEAN_INACTIVE = material("v_ase Hookean inactive spring", (0.56, 0.72, 1.0, 0.48), 0.48)
MAT_HOOKEAN_GUIDE = material("v_ase Hookean threshold guide", (0.68, 0.76, 0.85, 0.42), 0.42)
MAT_HOOKEAN_HOOK = material("v_ase Hookean hook latch", (0.48, 0.72, 1.0, 0.86), 0.86)
MAT_HOOKEAN_SLACK = material("v_ase Hookean inactive gap", (0.72, 0.76, 0.85, 0.38), 0.38)
MAT_HOOKEAN_ACTIVE_MARKER = material("v_ase Hookean active marker", (0.22, 0.85, 0.59, 0.92), 0.92)
MAT_HOOKEAN_INACTIVE_MARKER = material("v_ase Hookean inactive marker", (0.46, 0.66, 1.0, 0.78), 0.78)
MAT_HOOKEAN_THRESHOLD_MARKER = material("v_ase Hookean threshold marker", (1.0, 0.82, 0.35, 0.9), 0.9)
MAT_BOND = material("v_ase custom bond", hex_to_rgba(BOND_CUSTOM_COLOR), 1.0)
MAT_CELL = material(
    "v_ase unit cell",
    hex_to_rgba(CELL_COLOR),
    0.88,
    "metal" if CELL_MATERIAL == "metal" else "standard",
)

def get_bond_mat(color, preset="standard", opacity=1.0):
    color = hex_to_rgba(color) if isinstance(color, str) else color
    preset = preset if preset in MATERIAL_PRESETS else "standard"
    opacity = clamp01(opacity)
    key = f"{{preset}}_{{color[0]:.4f}}_{{color[1]:.4f}}_{{color[2]:.4f}}_a{{opacity:.4f}}"
    if key not in BOND_MATS:
        BOND_MATS[key] = material(f"v_ase bond {{key}}", color, opacity, preset)
    return BOND_MATS[key]

def get_bond_appearance(i, j, endpoint=None):
    left = ATOM_LABELS[i] if 0 <= i < len(ATOM_LABELS) else str(i)
    right = ATOM_LABELS[j] if 0 <= j < len(ATOM_LABELS) else str(j)
    pair = DISPLAY_PAIR_BOND_STYLES.get("-".join(sorted((left, right))), {{}})
    pair = pair if isinstance(pair, dict) else {{}}
    endpoint_style = DISPLAY_ATOM_BOND_STYLES.get(
        str(endpoint), DISPLAY_ATOM_BOND_STYLES.get(endpoint, {{}})
    ) if endpoint is not None else {{}}
    endpoint_style = endpoint_style if isinstance(endpoint_style, dict) else {{}}
    try:
        thickness = max(0.02, min(0.6, float(pair.get("thickness", BOND_THICKNESS))))
    except (TypeError, ValueError):
        thickness = BOND_THICKNESS
    try:
        opacity = clamp01(endpoint_style.get("opacity", pair.get("opacity", BOND_OPACITY)))
    except (TypeError, ValueError):
        opacity = BOND_OPACITY
    preset = endpoint_style.get("material", pair.get("material", BOND_MATERIAL))
    preset = preset if preset in MATERIAL_PRESETS else "standard"
    color_mode = "custom" if pair.get("colorMode", BOND_COLOR_MODE) == "custom" else "split"
    color = endpoint_style.get("color", pair.get("color", BOND_CUSTOM_COLOR))
    return {{
        "style": "flat" if pair.get("style", BOND_STYLE) == "flat" else "cylinder",
        "thickness": thickness,
        "material": preset,
        "opacity": opacity,
        "color_mode": color_mode,
        "custom_color": color,
        "endpoint_override": bool(endpoint_style),
    }}

def bond_pieces(i, j, start, end):
    base = get_bond_appearance(i, j)
    left = get_bond_appearance(i, j, i)
    right = get_bond_appearance(i, j, j)
    if base["color_mode"] == "custom" and not left["endpoint_override"] and not right["endpoint_override"]:
        return [(start, end, get_bond_mat(base["custom_color"], base["material"], base["opacity"]), base)]
    midpoint = (start + end) * 0.5
    pieces = []
    for endpoint, appearance, piece_start, piece_end in (
        (i, left, start, midpoint),
        (j, right, midpoint, end),
    ):
        color = appearance["custom_color"] if base["color_mode"] == "custom" else get_atom_color(endpoint)
        pieces.append((
            piece_start,
            piece_end,
            get_bond_mat(color, appearance["material"], appearance["opacity"]),
            appearance,
        ))
    return pieces

def get_atom_mat(index, symbol):
    color = get_atom_color(index)
    preset = get_atom_material_preset(index)
    opacity = get_atom_opacity(index)
    key = f"{{symbol}}_{{preset}}_{{color[0]:.4f}}_{{color[1]:.4f}}_{{color[2]:.4f}}_a{{opacity:.4f}}"
    if key not in ATOM_MATS:
        ATOM_MATS[key] = material(
            f"atom {{symbol}} {{preset}} alpha {{opacity:.4f}}",
            color,
            opacity,
            preset,
        )
    return ATOM_MATS[key]

def get_atom_mesh(index, symbol):
    color = get_atom_color(index)
    radius = get_atom_radius(index)
    preset = get_atom_material_preset(index)
    opacity = get_atom_opacity(index)
    material_key = f"{{symbol}}_{{preset}}_{{color[0]:.4f}}_{{color[1]:.4f}}_{{color[2]:.4f}}_a{{opacity:.4f}}"
    mesh_key = f"r{{radius:.4f}}_{{material_key}}"
    if mesh_key not in ATOM_MESHES:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius, location=(0, 0, 0))
        source = bpy.context.object
        source.name = f"v_ase_atom_mesh_source_{{mesh_key}}"
        mesh = source.data
        mesh.name = f"v_ase_atom_mesh_{{mesh_key}}"
        mesh.materials.append(get_atom_mat(index, symbol))
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        bpy.data.objects.remove(source, do_unlink=True)
        ATOM_MESHES[mesh_key] = mesh
    return ATOM_MESHES[mesh_key]

def safe_name(value):
    text = "".join(char if char.isalnum() or char in "_-" else "_" for char in str(value))
    return text[:48] or "type"

def geometry_node_group(name):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    if hasattr(group, "interface"):
        group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    else:
        group.inputs.new("NodeSocketGeometry", "Geometry")
        group.outputs.new("NodeSocketGeometry", "Geometry")
    return group

def add_instanced_atom_group(symbol, indices, positions):
    name = f"atoms_{{safe_name(symbol)}}"
    mesh = bpy.data.meshes.new(name + "_points")
    mesh.from_pydata([positions[index] for index in indices], [], [])
    mesh.update()
    atom_index = mesh.attributes.new("atom_index", "INT", "POINT")
    atom_index.data.foreach_set("value", indices)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj["v_ase_atom_group"] = True
    obj["v_ase_label"] = str(symbol)
    obj["v_ase_atom_count"] = len(indices)
    if DISPLAY_LABEL_VISIBLE.get(symbol) is False:
        obj.hide_viewport = True
        obj.hide_render = True

    group = geometry_node_group(name + "_instances")
    nodes = group.nodes
    links = group.links
    node_in = nodes.new("NodeGroupInput")
    node_out = nodes.new("NodeGroupOutput")
    sphere = nodes.new("GeometryNodeMeshIcoSphere")
    set_material = nodes.new("GeometryNodeSetMaterial")
    shade_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    instances = nodes.new("GeometryNodeInstanceOnPoints")
    quality = str(DISPLAY.get("sphereQuality", "auto"))
    subdivisions = {{"low": 1, "medium": 2, "high": 3, "ultra": 4, "auto": 3}}.get(quality, 3)
    sphere.inputs["Radius"].default_value = get_atom_radius(indices[0])
    sphere.inputs["Subdivisions"].default_value = subdivisions
    set_material.inputs["Material"].default_value = get_atom_mat(indices[0], symbol)
    if "Shade Smooth" in shade_smooth.inputs:
        shade_smooth.inputs["Shade Smooth"].default_value = True
    links.new(node_in.outputs["Geometry"], instances.inputs["Points"])
    links.new(sphere.outputs["Mesh"], set_material.inputs["Geometry"])
    links.new(set_material.outputs["Geometry"], shade_smooth.inputs["Geometry"])
    links.new(shade_smooth.outputs["Geometry"], instances.inputs["Instance"])
    links.new(instances.outputs["Instances"], node_out.inputs["Geometry"])
    modifier = obj.modifiers.new("v_ase atom instances", "NODES")
    modifier.node_group = group
    return obj, list(indices)

def add_instanced_atoms(positions, symbols):
    grouped = {{}}
    for index, symbol in enumerate(symbols):
        color = get_atom_color(index)
        radius = get_atom_radius(index)
        preset = get_atom_material_preset(index)
        key = (str(symbol), preset, round(radius, 6), tuple(round(value, 6) for value in color[:3]))
        grouped.setdefault(key, []).append(index)
    groups = []
    for (symbol, _preset, _radius, _color), indices in grouped.items():
        groups.append(add_instanced_atom_group(symbol, indices, positions))
    return groups

def animation_fcurves(animated_data):
    animation_data = getattr(animated_data, "animation_data", None)
    action = getattr(animation_data, "action", None)
    if action is None:
        return []
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    slot = getattr(animation_data, "action_slot", None)
    curves = []
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            channelbag = None
            for method_name in ("channelbag", "channelbag_for_slot"):
                method = getattr(strip, method_name, None)
                if method is None or slot is None:
                    continue
                try:
                    channelbag = method(slot)
                    break
                except (RuntimeError, TypeError, ValueError):
                    continue
            if channelbag is not None:
                curves.extend(list(getattr(channelbag, "fcurves", [])))
    return curves

def add_group_trajectory_shape_keys(groups, frames):
    if len(frames) <= 1:
        return
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = len(frames)
    for obj, indices in groups:
        obj.shape_key_add(name="Basis")
        for frame_number, frame_data in enumerate(frames, start=1):
            key = obj.shape_key_add(name=f"frame_{{frame_number:05d}}")
            coordinates = []
            for atom_index in indices:
                coordinates.extend(frame_data["positions"][atom_index])
            key.data.foreach_set("co", coordinates)
            if frame_number > 1:
                key.value = 0.0
                key.keyframe_insert(data_path="value", frame=frame_number - 1)
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=frame_number)
            if frame_number < len(frames):
                key.value = 0.0
                key.keyframe_insert(data_path="value", frame=frame_number + 1)
            key.value = 0.0
        if obj.data.shape_keys:
            for fcurve in animation_fcurves(obj.data.shape_keys):
                for point in fcurve.keyframe_points:
                    point.interpolation = "LINEAR"

def look_at_axis(obj, direction):
    direction = Vector(direction)
    if direction.length == 0:
        return
    quat = direction.to_track_quat("Z", "Y")
    obj.rotation_euler = quat.to_euler()

def look_at_camera(obj, target):
    direction = Vector(target) - obj.location
    if direction.length == 0:
        return
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def add_scene_camera():
    position = CAMERA.get("position")
    target = CAMERA.get("target")
    if isinstance(position, (list, tuple)) and len(position) == 3 and isinstance(target, (list, tuple)) and len(target) == 3:
        bpy.ops.object.camera_add(location=position)
        obj = bpy.context.object
        obj.name = "v_ase_view_camera"
        look_at_camera(obj, target)
        try:
            if CAMERA.get("projection") == "orthographic":
                obj.data.type = "ORTHO"
                obj.data.ortho_scale = max(0.1, float(CAMERA.get("ortho_scale") or 10.0))
            else:
                obj.data.angle = math.radians(float(CAMERA.get("fov", 50.0)))
        except (TypeError, ValueError):
            pass
        try:
            obj.data.clip_start = max(0.001, float(CAMERA.get("near", obj.data.clip_start)))
            obj.data.clip_end = max(obj.data.clip_start + 1.0, float(CAMERA.get("far", obj.data.clip_end)))
        except (TypeError, ValueError):
            pass
        bpy.context.scene.camera = obj
        return obj

    bpy.ops.object.camera_add(location=(8, -9, 6), rotation=(math.radians(60), 0, math.radians(42)))
    obj = bpy.context.object
    obj.name = "v_ase_view_camera"
    bpy.context.scene.camera = obj
    return obj

def add_scene_lighting():
    mode = LIGHTING.get("mode", DISPLAY.get("lightingMode", "modeling"))
    if mode in ("studio", "studio-shadow"):
        position = LIGHTING.get("position", DISPLAY.get("sunPosition", (8, -10, 14)))
        target = LIGHTING.get("target", DISPLAY.get("sunTarget", (0, 0, 0)))
        color = LIGHTING.get("color", (1.0, 0.960784, 0.87451))
        try:
            intensity = max(0.0, float(LIGHTING.get("intensity", DISPLAY.get("sunIntensity", 2.2))))
        except (TypeError, ValueError):
            intensity = 2.2
        try:
            position = Vector(position)
            target = Vector(target)
        except Exception:
            position = Vector((8, -10, 14))
            target = Vector((0, 0, 0))

        source = bpy.data.objects.new("v_ase_sun_source", None)
        source.empty_display_type = "CIRCLE"
        source.empty_display_size = 0.45
        source.location = position
        source["v_ase_role"] = "sun_source"
        bpy.context.collection.objects.link(source)

        target_handle = bpy.data.objects.new("v_ase_sun_target", None)
        target_handle.empty_display_type = "SPHERE"
        target_handle.empty_display_size = 0.32
        target_handle.location = target
        target_handle["v_ase_role"] = "sun_target"
        bpy.context.collection.objects.link(target_handle)

        light_data = bpy.data.lights.new("v_ase_studio_sun_data", type="SUN")
        obj = bpy.data.objects.new("v_ase_studio_sun", light_data)
        bpy.context.collection.objects.link(obj)
        obj.parent = source
        obj.location = (0, 0, 0)
        obj.data.energy = intensity
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            obj.data.color = tuple(clamp01(value) for value in color[:3])
        direction = target - position
        if direction.length <= 1e-10:
            direction = Vector((0, 0, -1))
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        track = obj.constraints.new(type="TRACK_TO")
        track.name = "Aim at v_ase target"
        track.target = target_handle
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        obj["v_ase_mode"] = mode
        obj["v_ase_target"] = target[:]
        obj["v_ase_direction"] = direction.normalized()[:]
        obj["v_ase_intensity"] = intensity
        if hasattr(obj.data, "angle"):
            obj.data.angle = math.radians(2.0 if mode == "studio-shadow" else 0.5)

        world = bpy.context.scene.world
        if world is not None:
            world.use_nodes = True
            background = world.node_tree.nodes.get("Background")
            if background is not None:
                background.inputs["Color"].default_value = (0.075, 0.085, 0.095, 1.0)
                background.inputs["Strength"].default_value = 0.24
        return obj

    bpy.ops.object.light_add(type="AREA", location=(5, -6, 8))
    obj = bpy.context.object
    obj.name = "v_ase_area_light"
    obj.data.energy = 450
    obj.data.size = 5
    return obj

def add_cylinder_between(name, start, end, radius, mat):
    start = Vector(start); end = Vector(end)
    mid = (start + end) * 0.5
    length = (end - start).length
    if length <= 1e-8:
        return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=length, location=mid)
    obj = bpy.context.object
    obj.name = name
    look_at_axis(obj, end - start)
    obj.data.materials.append(mat)
    return obj

def add_flat_between(name, start, end, width, mat):
    start = Vector(start); end = Vector(end)
    axis = end - start
    length = axis.length
    if length <= 1e-8:
        return None
    direction = axis.normalized()
    camera_position = CAMERA.get("position", (8, -9, 6))
    camera_target = CAMERA.get("target", (0, 0, 0))
    view = Vector(camera_target) - Vector(camera_position)
    side = direction.cross(view)
    if side.length <= 1e-8:
        side = direction.cross(Vector((0, 0, 1)))
    if side.length <= 1e-8:
        side = direction.cross(Vector((0, 1, 0)))
    side.normalize()
    half = side * (width * 0.5)
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([start - half, end - half, end + half, start + half], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_bond_piece(name, start, end, mat, appearance):
    if appearance["style"] == "flat":
        return add_flat_between(name, start, end, appearance["thickness"], mat)
    return add_cylinder_between(name, start, end, appearance["thickness"] * 0.5, mat)

def add_curve_segments(name, segments, radius, mat):
    if not segments:
        return None
    curve = bpy.data.curves.new(name + "_curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    curve.resolution_v = 0
    curve.fill_mode = "FULL"
    for start, end in segments:
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (*Vector(start), 1.0)
        spline.points[1].co = (*Vector(end), 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_flat_segments(name, segments, width, mat):
    if not segments:
        return None
    vertices = []
    faces = []
    camera_position = Vector(CAMERA.get("position", (8, -9, 6)))
    camera_target = Vector(CAMERA.get("target", (0, 0, 0)))
    view = camera_target - camera_position
    for start_value, end_value in segments:
        start = Vector(start_value); end = Vector(end_value)
        axis = end - start
        if axis.length <= 1e-8:
            continue
        direction = axis.normalized()
        side = direction.cross(view)
        if side.length <= 1e-8:
            side = direction.cross(Vector((0, 0, 1)))
        if side.length <= 1e-8:
            side = direction.cross(Vector((0, 1, 0)))
        side.normalize()
        half = side * (width * 0.5)
        offset = len(vertices)
        vertices.extend([start - half, end - half, end + half, start + half])
        faces.append((offset, offset + 1, offset + 2, offset + 3))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_bond_groups(bonds):
    grouped = {{}}
    for bond_index, bond in enumerate(bonds):
        i = int(bond.get("i", 0)); j = int(bond.get("j", 0))
        start = Vector(bond.get("start")); end = Vector(bond.get("end"))
        for piece_start, piece_end, mat, appearance in bond_pieces(i, j, start, end):
            key = (mat.name, appearance["style"], round(appearance["thickness"], 6))
            grouped.setdefault(key, {{
                "material": mat,
                "segments": [],
                "style": appearance["style"],
                "thickness": appearance["thickness"],
            }})["segments"].append((piece_start, piece_end))
    for group_index, item in enumerate(grouped.values()):
        name = f"bond_group_{{group_index:03d}}"
        if item["style"] == "flat":
            add_flat_segments(name, item["segments"], item["thickness"], item["material"])
        else:
            add_curve_segments(name, item["segments"], item["thickness"] * 0.5, item["material"])

def add_unit_cell(cell):
    if not isinstance(cell, (list, tuple)) or len(cell) != 3:
        return
    try:
        a, b, c = [Vector(v) for v in cell]
    except Exception:
        return
    corners = [
        Vector((0, 0, 0)),
        a,
        b,
        c,
        a + b,
        a + c,
        b + c,
        a + b + c,
    ]
    edges = [
        (0, 1), (0, 2), (0, 3),
        (1, 4), (1, 5),
        (2, 4), (2, 6),
        (3, 5), (3, 6),
        (4, 7), (5, 7), (6, 7),
    ]
    add_curve_segments(
        "unit_cell_edges",
        [(corners[i], corners[j]) for i, j in edges],
        CELL_THICKNESS * 0.5,
        MAT_CELL,
    )

def add_plane_disc(name, center, normal, radius, mat):
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius, fill_type="TRIFAN", location=center)
    obj = bpy.context.object
    obj.name = name
    look_at_axis(obj, normal)
    obj.data.materials.append(mat)
    return obj

def add_poly_curve(name, points, mat, bevel=0.025):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = bevel
    poly = curve.splines.new("POLY")
    poly.points.add(len(points) - 1)
    for idx, p in enumerate(points):
        poly.points[idx].co = (p.x, p.y, p.z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_ring(name, center, direction, radius, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=radius * 0.12, major_segments=48, minor_segments=8, location=center)
    obj = bpy.context.object
    obj.name = name
    look_at_axis(obj, direction)
    obj.data.materials.append(mat)
    return obj

def hookean_state(length, threshold):
    if threshold is None or threshold <= 0:
        return "active"
    if abs(length - threshold) <= max(0.035, threshold * 0.025):
        return "threshold"
    return "inactive" if length < threshold else "active"

def hookean_marker_material(state):
    if state == "active":
        return MAT_HOOKEAN_ACTIVE_MARKER
    if state == "threshold":
        return MAT_HOOKEAN_THRESHOLD_MARKER
    return MAT_HOOKEAN_INACTIVE_MARKER

def add_hookean_spring(name, start, end, threshold=None, radius_start=0.7, radius_end=0.7):
    start = Vector(start); end = Vector(end)
    axis = end - start
    length = axis.length
    if length <= 1e-8:
        return None
    direction = axis.normalized()
    helper = direction.cross(Vector((0, 0, 1)))
    if helper.length < 1e-6:
        helper = direction.cross(Vector((0, 1, 0)))
    u = helper.normalized()
    v = direction.cross(u).normalized()
    center = (start + end) * 0.5

    def to_world(x, y, z=0.0):
        return center + direction * y + u * x + v * z

    left_center = -length / 2
    right_center = length / 2
    left = left_center + min(radius_start * 0.55 + 0.04, length * 0.24)
    right = right_center - min(radius_end * 0.55 + 0.04, length * 0.24)
    span = max(0.12, abs(right - left))
    state = hookean_state(length, threshold)
    gate_width = max(0.12, min(span * 0.09, 0.28))
    lock_half = max(0.08, min(span * 0.045, 0.18))
    threshold_y = left_center + threshold if threshold and threshold > 0 else left + span * 0.52
    spring_start = threshold_y
    spring_end = right
    spring_len = max(0.001, spring_end - spring_start)
    coil_radius = min(
        max(min(radius_start, radius_end) * 0.38, 0.20),
        0.32,
        span * 0.14,
    )
    coils = max(3, min(14, round(spring_len / 0.18)))
    steps = max(72, coils * 18)

    add_poly_curve(name + "_dead_zone_rail", [
        to_world(0, left, 0),
        to_world(0, threshold_y, 0),
    ], MAT_HOOKEAN_GUIDE, bevel=0.018)

    add_poly_curve(name + "_cutoff_gate", [
        to_world(-gate_width, threshold_y, 0),
        to_world(gate_width, threshold_y, 0),
    ], hookean_marker_material(state), bevel=0.024 if state == "inactive" else 0.034)

    if state != "inactive":
        add_poly_curve(name + "_lock_pin", [
            to_world(0, threshold_y - lock_half, 0),
            to_world(0, threshold_y + lock_half, 0),
        ], hookean_marker_material(state), bevel=0.034)

    if state != "inactive" and spring_end > spring_start:
        spring_points = [to_world(0, spring_start, 0)]
        lead = min(0.14, spring_len * 0.12)
        coil_start = spring_start + lead
        coil_end = spring_end - lead
        for step in range(steps + 1):
            t = step / steps
            angle = t * math.tau * coils
            ramp = min(1.0, t * 8.0, (1.0 - t) * 8.0)
            radius = coil_radius * max(0.0, ramp)
            spring_points.append(to_world(
                math.cos(angle) * radius,
                coil_start + (coil_end - coil_start) * t,
                math.sin(angle) * radius,
            ))
        spring_points.append(to_world(0, spring_end, 0))
        add_poly_curve(name + "_spring", spring_points, MAT_HOOKEAN, bevel=0.022)

    if state == "inactive" and threshold_y > right:
        add_poly_curve(name + "_inactive_gap", [to_world(0, right, 0), to_world(0, threshold_y, 0)], MAT_HOOKEAN_SLACK, bevel=0.015)
    return None

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

scene = bpy.context.scene
for render_engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = render_engine
        break
    except (TypeError, ValueError):
        continue
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except (TypeError, ValueError):
    pass

positions = DATA["positions"]
symbols = DATA["symbols"]
atoms = []
atom_groups = []
if BLENDER_OBJECT_MODE == "objects":
    for idx, (symbol, pos) in enumerate(zip(symbols, positions)):
        obj = bpy.data.objects.new(f"atom_{{idx:04d}}_{{symbol}}", get_atom_mesh(idx, symbol))
        obj.name = f"atom_{{idx:04d}}_{{symbol}}"
        obj.location = pos
        obj["v_ase_atom_index"] = idx
        if DISPLAY_LABEL_VISIBLE.get(symbol) is False:
            obj.hide_viewport = True
            obj.hide_render = True
        bpy.context.collection.objects.link(obj)
        atoms.append(obj)
else:
    atom_groups = add_instanced_atoms(positions, symbols)

if INCLUDE_CELL:
    add_unit_cell(CELL)

if BLENDER_OBJECT_MODE == "objects":
    for bond_index, bond in enumerate(BONDS):
        i = int(bond.get("i", 0)); j = int(bond.get("j", 0))
        start = Vector(bond.get("start")); end = Vector(bond.get("end"))
        name = f"bond_{{i}}_{{j}}_{{bond_index:04d}}"
        pieces = bond_pieces(i, j, start, end)
        for piece_index, (piece_start, piece_end, mat, appearance) in enumerate(pieces):
            suffix = "" if len(pieces) == 1 else ("_start" if piece_index == 0 else "_end")
            add_bond_piece(name + suffix, piece_start, piece_end, mat, appearance)
else:
    add_bond_groups(BONDS)

def frame_topology_matches(frame_data):
    return (
        frame_data.get("symbols") == symbols
        and len(frame_data.get("positions", [])) == len(symbols)
    )

if len(FRAMES) > 1 and all(frame_topology_matches(frame) for frame in FRAMES):
    if BLENDER_OBJECT_MODE == "objects":
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = len(FRAMES)
        for frame_number, frame_data in enumerate(FRAMES, start=1):
            for idx, obj in enumerate(atoms):
                obj.location = frame_data["positions"][idx]
                obj.keyframe_insert(data_path="location", frame=frame_number)
        for obj in atoms:
            for fcurve in animation_fcurves(obj):
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = "LINEAR"
    else:
        add_group_trajectory_shape_keys(atom_groups, FRAMES)

constraints = DATA.get("constraints", {{}})
for idx_text, direction in constraints.get("fixed_line", {{}}).items():
    idx = int(idx_text)
    start = Vector(positions[idx]) - Vector(direction).normalized() * 2.2
    end = Vector(positions[idx]) + Vector(direction).normalized() * 2.2
    add_cylinder_between(f"fixed_line_{{idx}}", start, end, 0.035, MAT_LINE)

for idx_text, normal in constraints.get("fixed_plane", {{}}).items():
    idx = int(idx_text)
    add_plane_disc(f"fixed_plane_{{idx}}", positions[idx], normal, 1.6, MAT_PLANE)

for item in constraints.get("hookean", []):
    if item.get("kind") == "two atoms":
        i, j = item["indices"]
        add_hookean_spring(
            f"hookean_{{i}}_{{j}}",
            positions[i],
            positions[j],
            threshold=item.get("threshold"),
            radius_start=get_atom_radius(i),
            radius_end=get_atom_radius(j),
        )
    elif item.get("kind") == "point":
        idx = item["index"]
        add_hookean_spring(
            f"hookean_{{idx}}_point",
            positions[idx],
            item["origin"],
            threshold=item.get("threshold"),
            radius_start=get_atom_radius(idx),
            radius_end=0.18,
        )
    elif item.get("kind") == "plane":
        idx = item["index"]
        A, B, C, D = item["plane"]
        normal = Vector((A, B, C))
        pos = Vector(positions[idx])
        signed = (A * pos.x + B * pos.y + C * pos.z + D) / max(normal.length, 1e-9)
        center = pos - normal.normalized() * signed
        add_plane_disc(f"hookean_plane_{{idx}}", center, normal, 1.25, MAT_PLANE)
        add_hookean_spring(
            f"hookean_{{idx}}_plane_spring",
            pos,
            center,
            threshold=None,
            radius_start=get_atom_radius(idx),
            radius_end=0.18,
        )

add_scene_lighting()
add_scene_camera()
'''


def export_blender_response(session, payload: Dict[str, Any]):
    atoms = _apply_payload_positions(session, payload)
    if getattr(session, "trajectory_frames", None):
        session.sync_current_frame()
    data = atoms_to_json(atoms)
    frames = _trajectory_frames_json(session)
    if frames:
        data["frames"] = frames
    display = payload.get("display") or {}
    if display:
        data["display"] = display
    _translate_visual_frame(data, display)
    for frame in frames:
        _translate_visual_frame(frame, display)
    lighting = payload.get("lighting") or {
        "mode": display.get("lightingMode", "modeling"),
        "intensity": display.get("sunIntensity", 2.2),
        "position": display.get("sunPosition", [8, -10, 14]),
        "target": display.get("sunTarget", [0, 0, 0]),
        "color": [1.0, 0.960784, 0.87451],
    }
    data["lighting"] = lighting
    data["bonds"] = _display_bonds(data, display, payload.get("bond_pairs"))
    data["include_cell"] = bool(payload.get("include_cell", True))
    if payload.get("camera"):
        data["camera"] = payload["camera"]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_v_ase_blender.py", mode="w", encoding="utf-8")
    tmp.write(_blender_script(data))
    tmp.close()
    return FileResponse(tmp.name, filename="v_ase_blender_scene.py", media_type="text/x-python")
