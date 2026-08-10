"""Volumetric data readers and isosurface generation for v_ase.

The module keeps scalar grids separate from ``ase.Atoms``.  This avoids
copying large arrays during ordinary atom edits, trajectory updates, and undo
history operations while retaining an ASE structure for scientific work.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import struct
import threading
from typing import Any, Iterable, Sequence
import uuid

import numpy as np
from ase import Atoms
from ase.io.cube import read_cube
from ase.io import vasp as ase_vasp
from ase.io.xsf import iread_xsf


VOLUMETRIC_FORMAT_ALIASES = {
    "chg": "vasp-density",
    "chgcar": "vasp-density",
    "parchg": "vasp-partial-density",
    "locpot": "vasp-potential",
    "elfcar": "vasp-elf",
    "vasp-density": "vasp-density",
    "vasp-potential": "vasp-potential",
    "vasp-partial-density": "vasp-partial-density",
    "vasp-elf": "vasp-elf",
    "cube": "cube",
    "cub": "cube",
    "gaussian-cube": "cube",
    "xsf": "xsf",
    "qe-cube": "cube",
    "qe-xsf": "xsf",
}

DEFAULT_MAX_GRID_POINTS = 128 * 1024 * 1024
MAX_ISOSURFACE_TRIANGLES = 2_000_000
MAX_VOLUMETRIC_SMEARING_SIGMA = 8.0
MAX_ISOSURFACE_SMOOTHING_ITERATIONS = 30
MAX_ISOSURFACE_CACHE_BYTES = 64 * 1024 * 1024
MAX_ISOSURFACE_CACHE_ITEMS = 4
ISOSURFACE_BINARY_MAGIC = b"VASEISO1"
VOLUMETRIC_HISTOGRAM_BINS = 256
MAX_VOLUMETRIC_PLANE_RESOLUTION = 1024
MAX_VOLUMETRIC_PLANE_PIXELS = 1024 * 1024
MAX_VOLUMETRIC_PLANE_CACHE_BYTES = 48 * 1024 * 1024
MAX_VOLUMETRIC_PLANE_CACHE_ITEMS = 12
VOLUMETRIC_PLANE_BINARY_MAGIC = b"VASEPLN1"
# Cube and XSF writers commonly round cell vectors to six decimal places.
# This accepts that serialization noise without treating distinct cells as equal.
GRID_GEOMETRY_RTOL = 1e-6
GRID_GEOMETRY_ATOL = 1e-6
VOLUMETRIC_PRECISION_DTYPES = {
    "float32": np.dtype(np.float32),
    "float64": np.dtype(np.float64),
}
VOLUMETRIC_PRECISION_ALIASES = {
    "fp32": "float32",
    "float32": "float32",
    "single": "float32",
    "fp64": "float64",
    "float64": "float64",
    "double": "float64",
}


def normalize_volumetric_precision(value: Any = "float32") -> str:
    """Return the portable scalar-grid precision name."""

    key = str(value or "float32").strip().lower()
    try:
        return VOLUMETRIC_PRECISION_ALIASES[key]
    except KeyError as exc:
        raise ValueError(
            "Volumetric precision must be FP32 or FP64."
        ) from exc


def _max_grid_points() -> int:
    raw = os.environ.get(
        "V_ASE_MAX_VOLUMETRIC_POINTS",
        os.environ.get("V_ASE_MAX_VOLUME_POINTS", ""),
    )
    if not raw:
        return DEFAULT_MAX_GRID_POINTS
    try:
        return max(1_000_000, int(raw))
    except ValueError:
        return DEFAULT_MAX_GRID_POINTS


def resolve_volumetric_format(
    path: str | Path,
    fmt: str | None = None,
) -> str | None:
    """Return a canonical volumetric format or ``None`` for structure files."""

    if fmt:
        canonical = VOLUMETRIC_FORMAT_ALIASES.get(fmt.strip().lower())
        if canonical:
            return canonical

    source = Path(path)
    basename = source.name.lower()
    def matches_vasp_stem(stem: str) -> bool:
        return basename == stem or basename.startswith((f"{stem}.", f"{stem}_", f"{stem}-"))

    if matches_vasp_stem("chgcar"):
        return "vasp-density"
    if matches_vasp_stem("chg"):
        return "vasp-density"
    if matches_vasp_stem("locpot"):
        return "vasp-potential"
    if matches_vasp_stem("parchg"):
        return "vasp-partial-density"
    if matches_vasp_stem("elfcar"):
        return "vasp-elf"
    if source.suffix.lower() in {".cube", ".cub"}:
        return "cube"
    if source.suffix.lower() == ".xsf":
        return "xsf"
    return None


def is_volumetric_file(path: str | Path, fmt: str | None = None) -> bool:
    return resolve_volumetric_format(path, fmt) is not None


def _finite_array(
    values: Any,
    *,
    name: str,
    precision: str,
) -> np.ndarray:
    source = np.asarray(values)
    if source.ndim != 3 or min(source.shape) < 2:
        raise ValueError(f"{name} must be a three-dimensional grid with at least two points per axis.")
    if source.size > _max_grid_points():
        raise ValueError(
            f"{name} contains {source.size:,} grid points, exceeding the configured "
            f"limit of {_max_grid_points():,}. Set V_ASE_MAX_VOLUMETRIC_POINTS only "
            "after confirming sufficient memory."
        )
    normalized_precision = normalize_volumetric_precision(precision)
    array = np.asarray(
        source,
        dtype=VOLUMETRIC_PRECISION_DTYPES[normalized_precision],
    )
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains NaN or infinite scalar values.")
    return array


def _cell_array(cell: Any) -> np.ndarray:
    array = np.asarray(cell, dtype=float)
    if array.shape != (3, 3) or not np.all(np.isfinite(array)):
        raise ValueError("Volumetric cell must be a finite 3 x 3 matrix.")
    if abs(float(np.linalg.det(array))) <= 1e-12:
        raise ValueError("Volumetric cell must have non-zero volume.")
    return array


def _scalar_histogram(
    values: np.ndarray,
    minimum: float,
    maximum: float,
    *,
    bins: int = VOLUMETRIC_HISTOGRAM_BINS,
    absolute: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute a bounded-memory histogram without flattening a large grid."""

    count = max(16, min(2048, int(bins)))
    if maximum <= minimum:
        width = max(1.0, abs(minimum)) * 1e-6
        edges = np.linspace(minimum - width, maximum + width, count + 1)
        histogram = np.zeros(count, dtype=np.uint64)
        histogram[count // 2] = int(values.size)
        return histogram, edges

    histogram = np.zeros(count, dtype=np.uint64)
    edges = np.linspace(minimum, maximum, count + 1, dtype=np.float64)
    # A z-slab keeps peak memory independent of the total number of voxels.
    slab_depth = max(1, min(values.shape[0], 16))
    for start in range(0, values.shape[0], slab_depth):
        stop = min(values.shape[0], start + slab_depth)
        samples = values[start:stop]
        if absolute:
            samples = np.abs(samples)
        slab_histogram, _ = np.histogram(samples, bins=edges)
        histogram += slab_histogram.astype(np.uint64, copy=False)
    return histogram, edges


@dataclass
class VolumetricData:
    """One scalar field sampled over a parallelepiped grid."""

    name: str
    values: np.ndarray
    cell: np.ndarray
    origin: np.ndarray = field(default_factory=lambda: np.zeros(3))
    pbc: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=bool))
    quantity: str = "scalar_field"
    units: str = "file_native"
    source_format: str = "unknown"
    component: str = "total"
    endpoint_inclusive: bool = False
    atoms: Atoms | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    precision: str = "float32"
    _smearing_cache_sigma: float | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _smearing_cache_values: np.ndarray | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _smearing_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )
    _minimum: float = field(default=0.0, init=False, repr=False, compare=False)
    _maximum: float = field(default=0.0, init=False, repr=False, compare=False)
    _mean: float = field(default=0.0, init=False, repr=False, compare=False)
    _integral: float = field(default=0.0, init=False, repr=False, compare=False)
    _histogram_counts: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.uint64),
        init=False,
        repr=False,
        compare=False,
    )
    _histogram_edges: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.float64),
        init=False,
        repr=False,
        compare=False,
    )
    _absolute_histogram_counts: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.uint64),
        init=False,
        repr=False,
        compare=False,
    )
    _absolute_histogram_edges: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.float64),
        init=False,
        repr=False,
        compare=False,
    )
    _isosurface_cache: OrderedDict[tuple[Any, ...], "IsosurfaceMesh"] = field(
        default_factory=OrderedDict,
        init=False,
        repr=False,
        compare=False,
    )
    _isosurface_cache_bytes: int = field(default=0, init=False, repr=False, compare=False)
    _isosurface_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )
    _plane_cache: OrderedDict[tuple[Any, ...], "VolumetricPlaneSlice"] = field(
        default_factory=OrderedDict,
        init=False,
        repr=False,
        compare=False,
    )
    _plane_cache_bytes: int = field(default=0, init=False, repr=False, compare=False)
    _plane_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        self.name = str(self.name or "Volumetric data").strip() or "Volumetric data"
        self.precision = normalize_volumetric_precision(self.precision)
        self.values = _finite_array(
            self.values,
            name=self.name,
            precision=self.precision,
        )
        self.cell = _cell_array(self.cell)
        self.origin = np.asarray(self.origin, dtype=float)
        if self.origin.shape != (3,) or not np.all(np.isfinite(self.origin)):
            raise ValueError("Volumetric origin must contain three finite values.")
        self.pbc = np.asarray(self.pbc, dtype=bool)
        if self.pbc.ndim == 0:
            self.pbc = np.repeat(self.pbc, 3)
        if self.pbc.shape != (3,):
            raise ValueError("Volumetric PBC must contain three values.")
        self.quantity = str(self.quantity or "scalar_field")
        self.units = str(self.units or "file_native")
        self.source_format = str(self.source_format or "unknown")
        self.component = str(self.component or "total")
        self.dataset_id = str(self.dataset_id or uuid.uuid4())
        self.metadata = dict(self.metadata or {})
        if self.atoms is not None and not isinstance(self.atoms, Atoms):
            raise TypeError("Volumetric atoms must be an ase.Atoms object or None.")
        self._minimum = float(np.min(self.values))
        self._maximum = float(np.max(self.values))
        self._mean = float(np.mean(self.values, dtype=np.float64))
        self._histogram_counts, self._histogram_edges = _scalar_histogram(
            self.values,
            self._minimum,
            self._maximum,
        )
        absolute_maximum = max(abs(self._minimum), abs(self._maximum))
        self._absolute_histogram_counts, self._absolute_histogram_edges = _scalar_histogram(
            self.values,
            0.0,
            absolute_maximum,
            absolute=True,
        )
        integral_values = self.values
        if self.endpoint_inclusive:
            integral_values = integral_values[:-1, :-1, :-1]
        voxel_volume = abs(float(np.linalg.det(self.cell))) / float(np.prod(integral_values.shape))
        self._integral = float(np.sum(integral_values, dtype=np.float64) * voxel_volume)

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def maximum(self) -> float:
        return self._maximum

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def integral(self) -> float:
        return self._integral

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.dataset_id,
            "name": self.name,
            "shape": [int(value) for value in self.values.shape],
            "cell": self.cell.tolist(),
            "origin": self.origin.tolist(),
            "pbc": self.pbc.tolist(),
            "quantity": self.quantity,
            "units": self.units,
            "source_format": self.source_format,
            "component": self.component,
            "endpoint_inclusive": bool(self.endpoint_inclusive),
            "precision": self.precision,
            "memory_bytes": int(self.values.nbytes),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
            "integral": self.integral,
            "histogram": {
                "counts": [int(value) for value in self._histogram_counts],
                "edges": [float(value) for value in self._histogram_edges],
                "sample_count": int(self.values.size),
                "maximum_count": int(np.max(self._histogram_counts, initial=0)),
            },
            "absolute_histogram": {
                "counts": [int(value) for value in self._absolute_histogram_counts],
                "edges": [float(value) for value in self._absolute_histogram_edges],
                "sample_count": int(self.values.size),
                "maximum_count": int(
                    np.max(self._absolute_histogram_counts, initial=0)
                ),
            },
            "metadata": json.loads(json.dumps(self.metadata, allow_nan=False, default=str)),
        }

    def detached_copy(self) -> "VolumetricData":
        return VolumetricData(
            name=self.name,
            values=self.values.copy(),
            cell=self.cell.copy(),
            origin=self.origin.copy(),
            pbc=self.pbc.copy(),
            quantity=self.quantity,
            units=self.units,
            source_format=self.source_format,
            component=self.component,
            endpoint_inclusive=self.endpoint_inclusive,
            precision=self.precision,
            atoms=self.atoms.copy() if self.atoms is not None else None,
            metadata=dict(self.metadata),
            dataset_id=self.dataset_id,
        )

    def replicated(self, repetitions: Sequence[int]) -> "VolumetricData":
        """Return an exact periodic repetition of this scalar field.

        Endpoint-exclusive grids tile directly. Endpoint-inclusive grids keep
        one closing plane after tiling the non-duplicated samples, preserving
        the source convention without introducing seams or double-counting.
        """

        if len(repetitions) != 3:
            raise ValueError("Volumetric repetitions must contain three integers.")
        try:
            requested_reps = np.asarray(repetitions, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("Volumetric repetitions must be integers.") from exc
        if (
            requested_reps.shape != (3,)
            or not np.all(np.isfinite(requested_reps))
            or not np.all(requested_reps == np.floor(requested_reps))
        ):
            raise ValueError("Volumetric repetitions must be three finite integers.")
        reps = requested_reps.astype(int)
        if np.any(reps < 1):
            raise ValueError("Volumetric repetitions must be positive.")
        for axis, repetition in enumerate(reps):
            if repetition > 1 and not bool(self.pbc[axis]):
                raise ValueError(
                    f"Volumetric axis {axis + 1} cannot repeat because PBC is false."
                )

        source_shape = np.asarray(self.values.shape, dtype=np.int64)
        if self.endpoint_inclusive:
            output_shape = (source_shape - 1) * reps + 1
        else:
            output_shape = source_shape * reps
        output_points = int(np.prod(output_shape, dtype=np.int64))
        if output_points > _max_grid_points():
            raise ValueError(
                f"Repeated volumetric data would contain {output_points:,} grid "
                f"points, exceeding the configured limit of {_max_grid_points():,}."
            )

        values = self.values
        if self.endpoint_inclusive:
            for axis, repetition in enumerate(reps):
                if repetition == 1:
                    continue
                core = np.take(values, range(values.shape[axis] - 1), axis=axis)
                tile_reps = [1, 1, 1]
                tile_reps[axis] = int(repetition)
                values = np.tile(core, tile_reps)
                values = np.concatenate(
                    (values, np.take(values, [0], axis=axis)),
                    axis=axis,
                )
        else:
            values = np.tile(values, tuple(int(value) for value in reps))

        repeated_atoms = None
        if self.atoms is not None:
            repeated_atoms = self.atoms.repeat(tuple(int(value) for value in reps))
        metadata = dict(self.metadata)
        metadata["supercell_repetitions"] = [
            int(value) for value in reps
        ]
        return VolumetricData(
            name=self.name,
            values=values,
            cell=np.diag(reps) @ self.cell,
            origin=self.origin.copy(),
            pbc=self.pbc.copy(),
            quantity=self.quantity,
            units=self.units,
            source_format=self.source_format,
            component=self.component,
            endpoint_inclusive=self.endpoint_inclusive,
            precision=self.precision,
            atoms=repeated_atoms,
            metadata=metadata,
            dataset_id=self.dataset_id,
        )


@dataclass(frozen=True)
class IsosurfaceMesh:
    dataset_id: str
    name: str
    level: float
    vertices: np.ndarray
    faces: np.ndarray
    cell: np.ndarray
    origin: np.ndarray
    metadata: dict[str, Any]

    def binary(self) -> bytes:
        vertices = np.ascontiguousarray(self.vertices, dtype="<f4")
        faces = np.ascontiguousarray(self.faces, dtype="<u4")
        header = json.dumps(
            {
                "schema": "v_ase.isosurface.v1",
                "dataset_id": self.dataset_id,
                "name": self.name,
                "level": float(self.level),
                "vertex_count": int(len(vertices)),
                "face_count": int(len(faces)),
                "cell": np.asarray(self.cell, dtype=float).tolist(),
                "origin": np.asarray(self.origin, dtype=float).tolist(),
                "metadata": self.metadata,
            },
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        # Keep both typed-array sections 4-byte aligned so browsers can view
        # the response buffer directly instead of copying every mesh twice.
        header += b" " * ((-len(header)) % 4)
        return b"".join(
            (
                ISOSURFACE_BINARY_MAGIC,
                struct.pack("<I", len(header)),
                header,
                vertices.tobytes(order="C"),
                faces.tobytes(order="C"),
            )
        )


@dataclass(frozen=True)
class VolumetricPlaneSlice:
    """A scalar-field slice clipped to a crystallographic cell box."""

    dataset_id: str
    hkl: np.ndarray
    offset_angstrom: float
    repetitions: np.ndarray
    polygon_vertices: np.ndarray
    polygon_uv: np.ndarray
    normal: np.ndarray
    centroid: np.ndarray
    width: int
    height: int
    values: np.ndarray
    minimum: float
    maximum: float
    offset_minimum: float
    offset_maximum: float
    metadata: dict[str, Any]

    def binary(self) -> bytes:
        values = np.ascontiguousarray(self.values, dtype="<f4")
        header = json.dumps(
            {
                "schema": "v_ase.volumetric_plane.v1",
                "dataset_id": self.dataset_id,
                "hkl": np.asarray(self.hkl, dtype=float).tolist(),
                "offset_angstrom": float(self.offset_angstrom),
                "offset_minimum": float(self.offset_minimum),
                "offset_maximum": float(self.offset_maximum),
                "repetitions": np.asarray(self.repetitions, dtype=int).tolist(),
                "polygon_vertices": np.asarray(
                    self.polygon_vertices,
                    dtype=float,
                ).tolist(),
                "polygon_uv": np.asarray(self.polygon_uv, dtype=float).tolist(),
                "normal": np.asarray(self.normal, dtype=float).tolist(),
                "centroid": np.asarray(self.centroid, dtype=float).tolist(),
                "width": int(self.width),
                "height": int(self.height),
                "minimum": float(self.minimum),
                "maximum": float(self.maximum),
                "metadata": self.metadata,
            },
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        header += b" " * ((-len(header)) % 4)
        return b"".join(
            (
                VOLUMETRIC_PLANE_BINARY_MAGIC,
                struct.pack("<I", len(header)),
                header,
                values.tobytes(order="C"),
            )
        )


def _validated_plane_repetitions(value: Sequence[int] | None) -> np.ndarray:
    if value is None:
        return np.ones(3, dtype=int)
    try:
        numeric = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Plane repetitions must contain three integers.") from exc
    if (
        numeric.shape != (3,)
        or not np.all(np.isfinite(numeric))
        or not np.all(numeric == np.floor(numeric))
        or np.any(numeric < 1)
        or np.any(numeric > 128)
    ):
        raise ValueError("Plane repetitions must be three integers from 1 to 128.")
    return numeric.astype(int)


def _plane_geometry(
    dataset: VolumetricData,
    hkl: Sequence[float],
    offset_angstrom: float,
    repetitions: Sequence[int] | None,
) -> dict[str, np.ndarray | float]:
    """Intersect one reciprocal-space plane with a repeated cell box."""

    indices = np.asarray(hkl, dtype=float)
    if indices.shape != (3,) or not np.all(np.isfinite(indices)):
        raise ValueError("Plane (h k l) must contain three finite values.")
    if float(np.linalg.norm(indices)) <= 1e-12:
        raise ValueError("Plane (h k l) cannot be (0 0 0).")
    offset = float(offset_angstrom)
    if not np.isfinite(offset):
        raise ValueError("Plane offset must be finite.")
    reps = _validated_plane_repetitions(repetitions)
    if np.any((reps > 1) & ~dataset.pbc):
        raise ValueError("A plane can repeat only along periodic volumetric axes.")

    reciprocal_normal = np.linalg.solve(dataset.cell, indices)
    reciprocal_length = float(np.linalg.norm(reciprocal_normal))
    if reciprocal_length <= 1e-12:
        raise ValueError("Plane (h k l) does not define a finite cell normal.")
    normal = reciprocal_normal / reciprocal_length

    corners_fractional = np.asarray(
        [
            [0, 0, 0],
            [reps[0], 0, 0],
            [0, reps[1], 0],
            [reps[0], reps[1], 0],
            [0, 0, reps[2]],
            [reps[0], 0, reps[2]],
            [0, reps[1], reps[2]],
            [reps[0], reps[1], reps[2]],
        ],
        dtype=float,
    )
    corners = dataset.origin + corners_fractional @ dataset.cell
    projections = (corners - dataset.origin) @ normal
    offset_minimum = float(np.min(projections))
    offset_maximum = float(np.max(projections))
    tolerance = max(1e-8, (offset_maximum - offset_minimum) * 1e-9)
    if offset < offset_minimum - tolerance or offset > offset_maximum + tolerance:
        raise ValueError(
            "Plane offset must lie between "
            f"{offset_minimum:.8g} and {offset_maximum:.8g} angstrom for the "
            "current cell box."
        )
    offset = min(offset_maximum, max(offset_minimum, offset))

    edge_indices = (
        (0, 1), (0, 2), (0, 4),
        (1, 3), (1, 5),
        (2, 3), (2, 6),
        (3, 7),
        (4, 5), (4, 6),
        (5, 7), (6, 7),
    )
    signed = projections - offset
    intersections: list[np.ndarray] = []
    for first, second in edge_indices:
        first_distance = float(signed[first])
        second_distance = float(signed[second])
        if abs(first_distance) <= tolerance:
            intersections.append(corners[first])
        if abs(second_distance) <= tolerance:
            intersections.append(corners[second])
        if first_distance * second_distance < -(tolerance * tolerance):
            ratio = first_distance / (first_distance - second_distance)
            intersections.append(corners[first] + ratio * (corners[second] - corners[first]))

    unique: list[np.ndarray] = []
    cartesian_tolerance = max(1e-7, float(np.max(np.linalg.norm(dataset.cell, axis=1))) * 1e-8)
    for point in intersections:
        if not any(float(np.linalg.norm(point - existing)) <= cartesian_tolerance for existing in unique):
            unique.append(np.asarray(point, dtype=float))
    if len(unique) < 3:
        raise ValueError("The requested plane touches the cell box without a finite visible area.")

    polygon = np.asarray(unique, dtype=float)
    centroid = np.mean(polygon, axis=0)
    reference_axes = np.eye(3)
    reference = reference_axes[int(np.argmin(np.abs(reference_axes @ normal)))]
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    basis_v /= np.linalg.norm(basis_v)
    centered = polygon - centroid
    angles = np.arctan2(centered @ basis_v, centered @ basis_u)
    polygon = polygon[np.argsort(angles)]
    centered = polygon - centroid
    coordinates_u = centered @ basis_u
    coordinates_v = centered @ basis_v
    minimum_u, maximum_u = float(np.min(coordinates_u)), float(np.max(coordinates_u))
    minimum_v, maximum_v = float(np.min(coordinates_v)), float(np.max(coordinates_v))
    span_u = maximum_u - minimum_u
    span_v = maximum_v - minimum_v
    if span_u <= cartesian_tolerance or span_v <= cartesian_tolerance:
        raise ValueError("The requested plane has a numerically degenerate cell intersection.")
    polygon_uv = np.column_stack(
        (
            (coordinates_u - minimum_u) / span_u,
            (coordinates_v - minimum_v) / span_v,
        )
    )
    return {
        "hkl": indices,
        "offset": offset,
        "repetitions": reps,
        "normal": normal,
        "centroid": centroid,
        "polygon": polygon,
        "polygon_uv": polygon_uv,
        "basis_u": basis_u,
        "basis_v": basis_v,
        "minimum_u": minimum_u,
        "maximum_u": maximum_u,
        "minimum_v": minimum_v,
        "maximum_v": maximum_v,
        "offset_minimum": offset_minimum,
        "offset_maximum": offset_maximum,
    }


def generate_volumetric_plane(
    dataset: VolumetricData,
    hkl: Sequence[float],
    offset_angstrom: float,
    *,
    repetitions: Sequence[int] | None = None,
    resolution: int = 256,
) -> VolumetricPlaneSlice:
    """Sample one cell-clipped scalar slice using trilinear interpolation."""

    try:
        numeric_resolution = int(resolution)
    except (TypeError, ValueError) as exc:
        raise ValueError("Plane resolution must be an integer.") from exc
    if numeric_resolution < 16 or numeric_resolution > MAX_VOLUMETRIC_PLANE_RESOLUTION:
        raise ValueError(
            "Plane resolution must be between 16 and "
            f"{MAX_VOLUMETRIC_PLANE_RESOLUTION}."
        )
    geometry = _plane_geometry(dataset, hkl, offset_angstrom, repetitions)
    span_u = float(geometry["maximum_u"]) - float(geometry["minimum_u"])
    span_v = float(geometry["maximum_v"]) - float(geometry["minimum_v"])
    longest = max(span_u, span_v)
    width = max(2, int(round(numeric_resolution * span_u / longest)))
    height = max(2, int(round(numeric_resolution * span_v / longest)))
    if width * height > MAX_VOLUMETRIC_PLANE_PIXELS:
        raise ValueError(
            f"Plane image would contain {width * height:,} pixels, exceeding "
            f"the {MAX_VOLUMETRIC_PLANE_PIXELS:,}-pixel safety limit."
        )

    cache_key = (
        tuple(np.round(np.asarray(geometry["hkl"], dtype=float), 10)),
        round(float(geometry["offset"]), 10),
        tuple(int(value) for value in np.asarray(geometry["repetitions"])),
        width,
        height,
    )
    with dataset._plane_cache_lock:
        cached = dataset._plane_cache.get(cache_key)
        if cached is not None:
            dataset._plane_cache.move_to_end(cache_key)
            return cached

    samples_u = np.linspace(
        float(geometry["minimum_u"]),
        float(geometry["maximum_u"]),
        width,
        dtype=np.float64,
    )
    samples_v = np.linspace(
        float(geometry["minimum_v"]),
        float(geometry["maximum_v"]),
        height,
        dtype=np.float64,
    )
    grid_u, grid_v = np.meshgrid(samples_u, samples_v, indexing="xy")
    points = (
        np.asarray(geometry["centroid"])[None, None, :]
        + grid_u[..., None] * np.asarray(geometry["basis_u"])[None, None, :]
        + grid_v[..., None] * np.asarray(geometry["basis_v"])[None, None, :]
    )
    fractional = (points.reshape(-1, 3) - dataset.origin) @ np.linalg.inv(dataset.cell)
    shape = np.asarray(dataset.values.shape, dtype=float)
    coordinates = np.empty_like(fractional, dtype=np.float64)
    for axis in range(3):
        component = fractional[:, axis]
        if dataset.pbc[axis]:
            component = np.mod(component, 1.0)
        else:
            component = np.clip(component, 0.0, 1.0)
        if dataset.endpoint_inclusive:
            coordinates[:, axis] = component * max(1.0, shape[axis] - 1.0)
        else:
            coordinates[:, axis] = np.minimum(
                component * shape[axis],
                shape[axis] - 1.0,
            )

    try:
        from scipy.ndimage import map_coordinates
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Volumetric plane sampling requires SciPy. Install or repair v_ase "
            "with `python -m pip install -U v_ase-gui`."
        ) from exc
    sampled = map_coordinates(
        dataset.values,
        coordinates.T,
        order=1,
        mode="nearest",
        prefilter=False,
    ).reshape(height, width)
    sampled = np.ascontiguousarray(sampled, dtype=np.float32)
    polygon_uv = np.asarray(geometry["polygon_uv"], dtype=np.float64)
    normalized_u = (grid_u - float(geometry["minimum_u"])) / span_u
    normalized_v = (grid_v - float(geometry["minimum_v"])) / span_v
    visible_mask = np.ones((height, width), dtype=bool)
    signed_area = 0.5 * float(np.sum(
        polygon_uv[:, 0] * np.roll(polygon_uv[:, 1], -1)
        - np.roll(polygon_uv[:, 0], -1) * polygon_uv[:, 1]
    ))
    orientation = 1.0 if signed_area >= 0 else -1.0
    for index, start in enumerate(polygon_uv):
        end = polygon_uv[(index + 1) % len(polygon_uv)]
        cross = (
            (end[0] - start[0]) * (normalized_v - start[1])
            - (end[1] - start[1]) * (normalized_u - start[0])
        )
        visible_mask &= orientation * cross >= -1e-7
    visible_values = sampled[visible_mask]
    if not visible_values.size:
        raise ValueError("The requested plane did not cover any raster samples.")

    vertex_fractional = (
        np.asarray(geometry["polygon"], dtype=float) - dataset.origin
    ) @ np.linalg.inv(dataset.cell)
    vertex_coordinates = np.empty_like(vertex_fractional, dtype=np.float64)
    for axis in range(3):
        component = vertex_fractional[:, axis]
        if dataset.pbc[axis]:
            component = np.mod(component, 1.0)
        else:
            component = np.clip(component, 0.0, 1.0)
        if dataset.endpoint_inclusive:
            vertex_coordinates[:, axis] = component * max(1.0, shape[axis] - 1.0)
        else:
            vertex_coordinates[:, axis] = np.minimum(
                component * shape[axis],
                shape[axis] - 1.0,
            )
    vertex_values = map_coordinates(
        dataset.values,
        vertex_coordinates.T,
        order=1,
        mode="nearest",
        prefilter=False,
    )
    visible_minimum = min(float(np.min(visible_values)), float(np.min(vertex_values)))
    visible_maximum = max(float(np.max(visible_values)), float(np.max(vertex_values)))
    plane = VolumetricPlaneSlice(
        dataset_id=dataset.dataset_id,
        hkl=np.asarray(geometry["hkl"], dtype=float),
        offset_angstrom=float(geometry["offset"]),
        repetitions=np.asarray(geometry["repetitions"], dtype=int),
        polygon_vertices=np.asarray(geometry["polygon"], dtype=np.float32),
        polygon_uv=np.asarray(geometry["polygon_uv"], dtype=np.float32),
        normal=np.asarray(geometry["normal"], dtype=np.float32),
        centroid=np.asarray(geometry["centroid"], dtype=np.float32),
        width=width,
        height=height,
        values=sampled,
        minimum=visible_minimum,
        maximum=visible_maximum,
        offset_minimum=float(geometry["offset_minimum"]),
        offset_maximum=float(geometry["offset_maximum"]),
        metadata={
            "interpolation": "trilinear",
            "requested_resolution": numeric_resolution,
            "source_shape": [int(value) for value in dataset.values.shape],
            "endpoint_inclusive": bool(dataset.endpoint_inclusive),
        },
    )
    plane_bytes = int(plane.values.nbytes)
    with dataset._plane_cache_lock:
        dataset._plane_cache[cache_key] = plane
        dataset._plane_cache.move_to_end(cache_key)
        dataset._plane_cache_bytes += plane_bytes
        while (
            len(dataset._plane_cache) > MAX_VOLUMETRIC_PLANE_CACHE_ITEMS
            or (
                dataset._plane_cache_bytes > MAX_VOLUMETRIC_PLANE_CACHE_BYTES
                and len(dataset._plane_cache) > 1
            )
        ):
            _key, removed = dataset._plane_cache.popitem(last=False)
            dataset._plane_cache_bytes -= int(removed.values.nbytes)
    return plane


def _vasp_quantity(canonical_format: str) -> tuple[str, str, bool]:
    if canonical_format == "vasp-potential":
        return "electrostatic_potential", "eV", True
    if canonical_format == "vasp-partial-density":
        return "partial_charge_density", "1/angstrom^3", False
    if canonical_format == "vasp-elf":
        return "electron_localization", "dimensionless", True
    return "charge_density", "1/angstrom^3", False


def _vasp_grid_dimensions(tokens: Sequence[str]) -> tuple[int, int, int] | None:
    if len(tokens) != 3:
        return None
    try:
        dimensions = tuple(int(token) for token in tokens)
    except ValueError:
        return None
    if any(value < 2 for value in dimensions):
        return None
    return dimensions


def _read_vasp_scalar_block(
    handle,
    dimensions: tuple[int, int, int],
    *,
    divisor: float,
    precision: str,
) -> np.ndarray:
    point_count = int(np.prod(dimensions, dtype=np.int64))
    if point_count > _max_grid_points():
        raise ValueError(
            f"VASP scalar grid contains {point_count:,} points, exceeding the "
            f"configured limit of {_max_grid_points():,}."
        )
    nx, ny, nz = dimensions
    normalized_precision = normalize_volumetric_precision(precision)
    dtype = VOLUMETRIC_PRECISION_DTYPES[normalized_precision]
    flat = np.empty(point_count, dtype=dtype)
    offset = 0
    while offset < point_count:
        line = handle.readline()
        if not line:
            raise ValueError(
                "VASP scalar grid ended before all declared values were read."
            )
        parsed = np.fromstring(line, dtype=dtype, sep=" ")
        if not len(parsed):
            continue
        remaining = point_count - offset
        if len(parsed) > remaining:
            raise ValueError(
                "VASP scalar grid contains more values than its declared dimensions."
            )
        flat[offset:offset + len(parsed)] = parsed
        offset += len(parsed)
    # VASP writes x as the innermost (fastest) index. The transpose is a
    # zero-copy view over the bounded scalar buffer.
    values = flat.reshape((nz, ny, nx)).transpose(2, 1, 0)
    if divisor != 1.0:
        values /= dtype.type(divisor)
    return values


def _vasp_component_details(
    quantity: str,
    component_index: int,
    component_count: int,
) -> tuple[str, str]:
    if component_index == 0:
        return quantity, "total"
    if "density" in quantity:
        if component_count == 2:
            return "magnetization_density", "spin_difference"
        if component_count == 4:
            axis = "xyz"[component_index - 1]
            return "magnetization_density", f"magnetization_{axis}"
        return "magnetization_density", f"magnetization_{component_index}"
    return f"{quantity}_component", f"component_{component_index + 1}"


def _read_vasp_structure_configuration(handle) -> Atoms:
    """Read a POSCAR-style header without consuming the following grid.

    ASE 3.23 and 3.24 expose this operation through ``read_vasp``.  Newer ASE
    releases split the shared POSCAR/CHGCAR parser into
    ``read_vasp_configuration`` because their public ``read_vasp`` reader also
    checks for optional velocity records.  Resolve the capability at call time
    so importing v_ase never depends on that version-specific helper.
    """

    configuration_reader = getattr(
        ase_vasp,
        "read_vasp_configuration",
        None,
    )
    if configuration_reader is not None:
        return configuration_reader(handle)
    return ase_vasp.read_vasp(handle)


def _read_vasp_grids(
    path: Path,
    canonical_format: str,
    precision: str,
) -> list[VolumetricData]:
    """Read VASP grids with ASE structure parsing and bounded scalar blocks.

    The scalar loop follows VASP's documented x-fastest ordering and the
    attached ``Chgcar`` design, while ASE remains authoritative for POSCAR
    scaling, species, Selective Dynamics, coordinates, cell, and constraints.
    This avoids the transient float64 copy made by the legacy all-in-memory
    reader for large grids.
    """

    quantity, units, intensive_values = _vasp_quantity(canonical_format)
    datasets: list[VolumetricData] = []
    frames: list[tuple[Atoms, list[np.ndarray]]] = []
    basename = path.name.lower()
    single_configuration = not (
        basename == "chg" or basename.startswith("chg.")
    )
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        while True:
            try:
                atoms = _read_vasp_structure_configuration(handle)
            except (AssertionError, KeyError, RuntimeError, TypeError, ValueError):
                break

            dimensions_line = handle.readline()
            while dimensions_line and not dimensions_line.split():
                dimensions_line = handle.readline()
            dimensions = _vasp_grid_dimensions(dimensions_line.split())
            if dimensions is None:
                if not frames:
                    raise ValueError(
                        f"{path.name} does not contain valid VASP grid dimensions."
                    )
                break
            divisor = 1.0 if intensive_values else float(atoms.get_volume())
            blocks = [
                _read_vasp_scalar_block(
                    handle,
                    dimensions,
                    divisor=divisor,
                    precision=precision,
                )
            ]

            if single_configuration:
                for line in handle:
                    if _vasp_grid_dimensions(line.split()) == dimensions:
                        blocks.append(
                            _read_vasp_scalar_block(
                                handle,
                                dimensions,
                                divisor=divisor,
                                precision=precision,
                            )
                        )
                frames.append((atoms, blocks))
                break

            next_position = handle.tell()
            next_line = handle.readline()
            if _vasp_grid_dimensions(next_line.split()) == dimensions:
                blocks.append(
                    _read_vasp_scalar_block(
                        handle,
                        dimensions,
                        divisor=divisor,
                        precision=precision,
                    )
                )
            else:
                handle.seek(next_position)
            frames.append((atoms, blocks))

    if not frames:
        raise ValueError(f"{path.name} contains no readable VASP scalar grid.")

    for frame_index, (atoms, blocks) in enumerate(frames):
        frame_suffix = f" frame {frame_index + 1}" if len(frames) > 1 else ""
        for component_index, values in enumerate(blocks):
            component_quantity, component = _vasp_component_details(
                quantity,
                component_index,
                len(blocks),
            )
            component_suffix = (
                ""
                if component_index == 0
                else f" {component.replace('_', ' ')}"
            )
            datasets.append(
                VolumetricData(
                    name=f"{path.name}{frame_suffix}{component_suffix}",
                    values=values,
                    cell=atoms.cell.array,
                    origin=np.zeros(3),
                    pbc=atoms.pbc,
                    quantity=component_quantity,
                    units=units,
                    source_format=canonical_format,
                    component=component,
                    endpoint_inclusive=False,
                    precision=precision,
                    atoms=atoms.copy(),
                    metadata={
                        "source_file": path.name,
                        "source_frame": frame_index,
                        "grid_order": "x-fastest",
                        "scalar_values": (
                            f"bounded {normalize_volumetric_precision(precision)} "
                            "VASP grid parser with ASE "
                            "structure configuration"
                        ),
                    },
                )
            )
    return datasets


def _read_cube_grids(path: Path, precision: str) -> list[VolumetricData]:
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        payload = read_cube(handle, read_data=True)
    atoms = payload["atoms"]
    grids = np.asarray(payload.get("datas", [payload["data"]]))
    datasets = []
    for component_index, values in enumerate(grids):
        component = "total" if len(grids) == 1 else f"component_{component_index + 1}"
        datasets.append(
            VolumetricData(
                name=path.name if len(grids) == 1 else f"{path.name} {component}",
                values=values,
                cell=atoms.cell.array,
                origin=payload.get("origin", np.zeros(3)),
                pbc=atoms.pbc,
                quantity="scalar_field",
                units="file_native",
                source_format="cube",
                component=component,
                endpoint_inclusive=False,
                precision=precision,
                atoms=atoms.copy(),
                metadata={
                    "source_file": path.name,
                    "coordinate_units": "angstrom",
                    "scalar_units": "unchanged from Cube file",
                    "orbital_labels": list(payload.get("labels") or []),
                },
            )
        )
    return datasets


def _read_xsf_grids(path: Path, precision: str) -> list[VolumetricData]:
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        items = list(iread_xsf(handle, read_data=True))
    if not items or not isinstance(items[-1], tuple):
        raise ValueError(f"{path.name} contains no XSF DATAGRID_3D block.")
    data, origin, span_vectors = items[-1]
    frames = [item for item in items[:-1] if isinstance(item, Atoms)]
    atoms = frames[-1].copy() if frames else Atoms(cell=span_vectors, pbc=True)
    return [
        VolumetricData(
            name=path.name,
            values=data,
            cell=span_vectors,
            origin=origin,
            pbc=atoms.pbc,
            quantity="scalar_field",
            units="file_native",
            source_format="xsf",
            component="total",
            endpoint_inclusive=True,
            precision=precision,
            atoms=atoms,
            metadata={
                "source_file": path.name,
                "coordinate_units": "angstrom",
                "scalar_units": "unchanged from XSF file",
            },
        )
    ]


def read_volumetric_file(
    path: str | Path,
    fmt: str | None = None,
    precision: str = "float32",
) -> list[VolumetricData]:
    """Read VASP, Gaussian Cube, or XSF scalar grids.

    Quantum ESPRESSO's ``pp.x`` officially exports both XSF and Gaussian Cube,
    so those two adapters provide the code-independent path for QE and other
    electronic-structure programs.
    """

    source = Path(path)
    normalized_precision = normalize_volumetric_precision(precision)
    canonical = resolve_volumetric_format(source, fmt)
    if canonical is None:
        raise ValueError(
            f"{source.name} is not a supported volumetric file. "
            "Use CHGCAR, CHG, LOCPOT, PARCHG, ELFCAR, XSF, or Cube."
        )
    if canonical.startswith("vasp-"):
        return _read_vasp_grids(source, canonical, normalized_precision)
    if canonical == "cube":
        return _read_cube_grids(source, normalized_precision)
    if canonical == "xsf":
        return _read_xsf_grids(source, normalized_precision)
    raise ValueError(f"Unsupported volumetric format: {canonical}.")


def volumetric_structure(datasets: Sequence[VolumetricData]) -> Atoms:
    for dataset in datasets:
        if dataset.atoms is not None:
            return dataset.atoms.copy()
    if not datasets:
        raise ValueError("No volumetric datasets were loaded.")
    first = datasets[0]
    return Atoms(cell=first.cell, pbc=first.pbc)


def combine_volumetric_datasets(
    datasets: Sequence[VolumetricData],
    coefficients: Sequence[float],
    *,
    name: str = "Charge density difference",
    precision: str | None = None,
) -> VolumetricData:
    """Create a validated linear combination such as ``A - B - C``."""

    if len(datasets) < 2:
        raise ValueError("At least two volumetric datasets are required.")
    if len(datasets) != len(coefficients):
        raise ValueError("Each volumetric dataset requires one coefficient.")
    reference = datasets[0]
    for dataset in datasets[1:]:
        if dataset.values.shape != reference.values.shape:
            raise ValueError("Charge-density difference grids must have identical dimensions.")
        if not np.allclose(
            dataset.cell,
            reference.cell,
            rtol=GRID_GEOMETRY_RTOL,
            atol=GRID_GEOMETRY_ATOL,
        ):
            raise ValueError("Charge-density difference grids must use the same unit cell.")
        if not np.allclose(
            dataset.origin,
            reference.origin,
            rtol=GRID_GEOMETRY_RTOL,
            atol=GRID_GEOMETRY_ATOL,
        ):
            raise ValueError("Charge-density difference grids must use the same origin.")
        if not np.array_equal(dataset.pbc, reference.pbc):
            raise ValueError("Charge-density difference grids must use the same PBC.")
        if dataset.endpoint_inclusive != reference.endpoint_inclusive:
            raise ValueError("Charge-density difference grids use incompatible endpoint conventions.")
        if dataset.units != reference.units:
            raise ValueError("Charge-density difference grids must use the same scalar units.")

    output_precision = normalize_volumetric_precision(
        precision
        or (
            "float64"
            if any(dataset.precision == "float64" for dataset in datasets)
            else "float32"
        )
    )
    output_dtype = VOLUMETRIC_PRECISION_DTYPES[output_precision]
    result = np.zeros(reference.values.shape, dtype=output_dtype)
    clean_coefficients = []
    for coefficient, dataset in zip(coefficients, datasets):
        value = float(coefficient)
        if not np.isfinite(value):
            raise ValueError("Volumetric combination coefficients must be finite.")
        clean_coefficients.append(value)
        # Work in bounded slabs. A full-grid expression temporarily doubles
        # memory for large CHGCAR/PARCHG differences.
        plane_size = int(np.prod(reference.values.shape[1:]))
        slab_depth = max(1, min(reference.values.shape[0], 1_048_576 // max(1, plane_size)))
        coefficient_value = output_dtype.type(value)
        for start in range(0, reference.values.shape[0], slab_depth):
            stop = min(reference.values.shape[0], start + slab_depth)
            result[start:stop] += (
                np.asarray(dataset.values[start:stop], dtype=output_dtype)
                * coefficient_value
            )
    return VolumetricData(
        name=name,
        values=result,
        cell=reference.cell.copy(),
        origin=reference.origin.copy(),
        pbc=reference.pbc.copy(),
        quantity="charge_density_difference",
        units=reference.units,
        source_format="linear-combination",
        component="difference",
        endpoint_inclusive=reference.endpoint_inclusive,
        precision=output_precision,
        atoms=reference.atoms.copy() if reference.atoms is not None else None,
        metadata={
            "sources": [dataset.dataset_id for dataset in datasets],
            "coefficients": clean_coefficients,
            "precision_policy": (
                "explicit" if precision is not None else "highest-input"
            ),
        },
    )


def _periodic_marching_grid(dataset: VolumetricData) -> tuple[np.ndarray, np.ndarray]:
    return _periodic_marching_grid_values(dataset, dataset.values)


def _periodic_marching_grid_values(
    dataset: VolumetricData,
    values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if dataset.endpoint_inclusive:
        denominator = np.maximum(np.asarray(values.shape, dtype=float) - 1.0, 1.0)
        return values, denominator

    denominator = np.asarray(values.shape, dtype=float)
    expanded = values
    for axis, periodic in enumerate(dataset.pbc):
        if periodic:
            expanded = np.concatenate(
                (expanded, np.take(expanded, [0], axis=axis)),
                axis=axis,
            )
    return expanded, denominator


def _validated_smearing_sigma(value: Any) -> float:
    try:
        sigma = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Field smearing sigma must be a finite number.") from exc
    if not np.isfinite(sigma) or sigma < 0 or sigma > MAX_VOLUMETRIC_SMEARING_SIGMA:
        raise ValueError(
            "Field smearing sigma must be between 0 and "
            f"{MAX_VOLUMETRIC_SMEARING_SIGMA:g} grid points."
        )
    return sigma


def _validated_smoothing_iterations(value: Any) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Surface smoothing passes must be an integer.") from exc
    if (
        not np.isfinite(numeric)
        or numeric != np.floor(numeric)
        or numeric < 0
        or numeric > MAX_ISOSURFACE_SMOOTHING_ITERATIONS
    ):
        raise ValueError(
            "Surface smoothing passes must be an integer between 0 and "
            f"{MAX_ISOSURFACE_SMOOTHING_ITERATIONS}."
        )
    return int(numeric)


def _smear_scalar_grid(
    dataset: VolumetricData,
    sigma: float,
) -> np.ndarray:
    """Return an optionally Gaussian-smoothed display grid.

    The source array is never modified. Periodic axes use wrapped convolution.
    Endpoint-inclusive periodic grids are filtered without their redundant
    closing plane and have that plane restored afterwards.
    """

    smear_sigma = _validated_smearing_sigma(sigma)
    if smear_sigma == 0:
        with dataset._smearing_cache_lock:
            dataset._smearing_cache_sigma = None
            dataset._smearing_cache_values = None
        return dataset.values

    with dataset._smearing_cache_lock:
        if (
            dataset._smearing_cache_sigma == smear_sigma
            and dataset._smearing_cache_values is not None
        ):
            return dataset._smearing_cache_values

        try:
            from scipy.ndimage import gaussian_filter
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Volumetric field smearing requires SciPy. "
                "Install or repair v_ase with `python -m pip install -U v_ase-gui`."
            ) from exc

        # Release a prior full-grid cache before allocating the replacement.
        dataset._smearing_cache_sigma = None
        dataset._smearing_cache_values = None

        slices = [slice(None), slice(None), slice(None)]
        closing_axes: list[int] = []
        if dataset.endpoint_inclusive:
            for axis, periodic in enumerate(dataset.pbc):
                if periodic:
                    slices[axis] = slice(0, -1)
                    closing_axes.append(axis)

        core = dataset.values[tuple(slices)]
        modes = tuple("wrap" if periodic else "reflect" for periodic in dataset.pbc)
        smoothed = gaussian_filter(
            core,
            sigma=smear_sigma,
            mode=modes,
            output=dataset.values.dtype,
        )
        for axis in closing_axes:
            smoothed = np.concatenate(
                (smoothed, np.take(smoothed, [0], axis=axis)),
                axis=axis,
            )
        smoothed = np.ascontiguousarray(smoothed, dtype=dataset.values.dtype)
        dataset._smearing_cache_sigma = smear_sigma
        dataset._smearing_cache_values = smoothed
        return smoothed


def _mesh_boundary_mask(
    vertices: np.ndarray,
    denominator: np.ndarray,
) -> np.ndarray:
    """Keep domain-edge vertices fixed so clipped and periodic seams stay closed."""

    boundary = np.zeros(len(vertices), dtype=bool)
    for axis in range(3):
        tolerance = max(1e-6, float(denominator[axis]) * 1e-6)
        boundary |= np.isclose(vertices[:, axis], 0.0, atol=tolerance)
        boundary |= np.isclose(
            vertices[:, axis],
            float(denominator[axis]),
            atol=tolerance,
        )
    return boundary


def _smooth_mesh_vertices(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    iterations: int,
    fixed: np.ndarray | None = None,
) -> np.ndarray:
    """Apply shrinkage-reducing two-pass Laplacian mesh fairing."""

    passes = _validated_smoothing_iterations(iterations)
    source = np.asarray(vertices, dtype=np.float32)
    if passes == 0 or len(source) < 4 or not len(faces):
        return source.copy()

    try:
        from scipy.sparse import coo_matrix
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Isosurface mesh smoothing requires SciPy. "
            "Install or repair v_ase with `python -m pip install -U v_ase-gui`."
        ) from exc

    triangles = np.asarray(faces, dtype=np.uint32)
    edges = np.concatenate(
        (
            triangles[:, (0, 1)],
            triangles[:, (1, 2)],
            triangles[:, (2, 0)],
        ),
        axis=0,
    )
    edges.sort(axis=1)
    edges = np.unique(edges, axis=0)
    rows = np.concatenate((edges[:, 0], edges[:, 1]))
    columns = np.concatenate((edges[:, 1], edges[:, 0]))
    adjacency = coo_matrix(
        (np.ones(len(rows), dtype=np.float32), (rows, columns)),
        shape=(len(source), len(source)),
    ).tocsr()
    degree = np.asarray(adjacency.sum(axis=1), dtype=np.float32).reshape(-1)
    movable = degree > 0
    if fixed is not None:
        fixed_mask = np.asarray(fixed, dtype=bool)
        if fixed_mask.shape != (len(source),):
            raise ValueError("Isosurface fixed-vertex mask has an invalid shape.")
        movable &= ~fixed_mask

    result = source.copy()
    # The negative second pass counters the shrinkage of ordinary Laplacian
    # smoothing while retaining its high-frequency fairing effect.
    for _ in range(passes):
        average = adjacency @ result
        average[movable] /= degree[movable, None]
        result[movable] += 0.5 * (average[movable] - result[movable])

        average = adjacency @ result
        average[movable] /= degree[movable, None]
        result[movable] -= 0.53 * (average[movable] - result[movable])
    return result


def generate_isosurface(
    dataset: VolumetricData,
    level: float,
    *,
    step_size: int = 1,
    smearing_sigma: float = 0.0,
    smoothing_iterations: int = 4,
    max_triangles: int = MAX_ISOSURFACE_TRIANGLES,
) -> IsosurfaceMesh:
    """Generate a cell-aware, optionally refined mesh for one scalar level."""

    try:
        from skimage.measure import marching_cubes
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Isosurface generation requires scikit-image. "
            "Install or repair v_ase with `python -m pip install -U v_ase-gui`."
        ) from exc

    iso_level = float(level)
    if not np.isfinite(iso_level):
        raise ValueError("Isosurface level must be finite.")
    smear_sigma = _validated_smearing_sigma(smearing_sigma)
    smoothing_passes = _validated_smoothing_iterations(smoothing_iterations)
    quality_step = max(1, min(8, int(step_size)))
    cache_key = (
        float(iso_level),
        quality_step,
        float(smear_sigma),
        smoothing_passes,
        int(max_triangles),
    )
    with dataset._isosurface_cache_lock:
        cached = dataset._isosurface_cache.get(cache_key)
        if cached is not None:
            dataset._isosurface_cache.move_to_end(cache_key)
            return cached
    display_values = _smear_scalar_grid(dataset, smear_sigma)
    if smear_sigma == 0:
        minimum, maximum = dataset.minimum, dataset.maximum
    else:
        minimum = float(np.min(display_values))
        maximum = float(np.max(display_values))
    if not minimum < iso_level < maximum:
        raise ValueError(
            "Isosurface level must lie strictly between "
            f"{minimum:.8g} and {maximum:.8g} after field smearing."
        )
    volume, denominator = _periodic_marching_grid_values(dataset, display_values)
    try:
        vertices, faces, _normals, _values = marching_cubes(
            volume,
            level=iso_level,
            step_size=quality_step,
            allow_degenerate=False,
        )
    except (RuntimeError, ValueError) as exc:
        raise ValueError(f"Could not construct the requested isosurface: {exc}") from exc
    if len(faces) > max_triangles:
        raise ValueError(
            f"The isosurface contains {len(faces):,} triangles, exceeding the "
            f"{max_triangles:,} triangle safety limit. Increase the mesh step."
        )

    fixed = _mesh_boundary_mask(vertices, denominator)
    vertices = _smooth_mesh_vertices(
        vertices,
        faces,
        iterations=smoothing_passes,
        fixed=fixed,
    )
    fractional = vertices / np.asarray(denominator, dtype=np.float32)
    cartesian = np.asarray(dataset.origin, dtype=np.float32) + (
        fractional @ np.asarray(dataset.cell, dtype=np.float32)
    )
    mesh = IsosurfaceMesh(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        level=iso_level,
        vertices=np.asarray(cartesian, dtype=np.float32),
        faces=np.asarray(faces, dtype=np.uint32),
        cell=dataset.cell.copy(),
        origin=dataset.origin.copy(),
        metadata={
            "step_size": quality_step,
            "smearing_sigma": smear_sigma,
            "smoothing_iterations": smoothing_passes,
            "display_minimum": minimum,
            "display_maximum": maximum,
            "fixed_boundary_vertices": int(np.count_nonzero(fixed)),
            "periodic_seams": [
                bool(value and not dataset.endpoint_inclusive)
                for value in dataset.pbc
            ],
            "source_shape": [int(value) for value in dataset.values.shape],
        },
    )
    mesh_bytes = int(mesh.vertices.nbytes + mesh.faces.nbytes)
    with dataset._isosurface_cache_lock:
        dataset._isosurface_cache[cache_key] = mesh
        dataset._isosurface_cache.move_to_end(cache_key)
        dataset._isosurface_cache_bytes += mesh_bytes
        while (
            len(dataset._isosurface_cache) > MAX_ISOSURFACE_CACHE_ITEMS
            or (
                dataset._isosurface_cache_bytes > MAX_ISOSURFACE_CACHE_BYTES
                and len(dataset._isosurface_cache) > 1
            )
        ):
            _key, removed = dataset._isosurface_cache.popitem(last=False)
            dataset._isosurface_cache_bytes -= int(
                removed.vertices.nbytes + removed.faces.nbytes
            )
    return mesh


def dataset_by_id(
    datasets: Iterable[VolumetricData],
    dataset_id: str,
) -> VolumetricData:
    target = str(dataset_id)
    for dataset in datasets:
        if dataset.dataset_id == target:
            return dataset
    raise KeyError(f"Volumetric dataset {target!r} was not found.")
