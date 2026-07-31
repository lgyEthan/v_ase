"""Volumetric data readers and isosurface generation for v_ase.

The module keeps scalar grids separate from ``ase.Atoms``.  This avoids
copying large arrays during ordinary atom edits, trajectory updates, and undo
history operations while retaining an ASE structure for scientific work.
"""

from __future__ import annotations

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
ISOSURFACE_BINARY_MAGIC = b"VASEISO1"
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
    if basename == "chgcar" or basename.startswith("chgcar."):
        return "vasp-density"
    if basename == "chg" or basename.startswith("chg."):
        return "vasp-density"
    if basename == "locpot" or basename.startswith("locpot."):
        return "vasp-potential"
    if basename == "parchg" or basename.startswith("parchg."):
        return "vasp-partial-density"
    if basename == "elfcar" or basename.startswith("elfcar."):
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

    @property
    def minimum(self) -> float:
        return float(np.min(self.values))

    @property
    def maximum(self) -> float:
        return float(np.max(self.values))

    @property
    def mean(self) -> float:
        return float(np.mean(self.values, dtype=np.float64))

    @property
    def integral(self) -> float:
        values = self.values
        if self.endpoint_inclusive:
            values = values[:-1, :-1, :-1]
        voxel_volume = abs(float(np.linalg.det(self.cell))) / float(np.prod(values.shape))
        return float(np.sum(values, dtype=np.float64) * voxel_volume)

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
        return b"".join(
            (
                ISOSURFACE_BINARY_MAGIC,
                struct.pack("<I", len(header)),
                header,
                vertices.tobytes(order="C"),
                faces.tobytes(order="C"),
            )
        )


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
    result = np.zeros(reference.values.shape, dtype=np.float64)
    clean_coefficients = []
    for coefficient, dataset in zip(coefficients, datasets):
        value = float(coefficient)
        if not np.isfinite(value):
            raise ValueError("Volumetric combination coefficients must be finite.")
        clean_coefficients.append(value)
        result += value * dataset.values
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
    source = np.asarray(vertices, dtype=np.float64)
    if passes == 0 or len(source) < 4 or not len(faces):
        return source.copy()

    try:
        from scipy.sparse import coo_matrix
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Isosurface mesh smoothing requires SciPy. "
            "Install or repair v_ase with `python -m pip install -U v_ase-gui`."
        ) from exc

    triangles = np.asarray(faces, dtype=np.int64)
    edges = np.concatenate(
        (
            triangles[:, (0, 1)],
            triangles[:, (1, 2)],
            triangles[:, (2, 0)],
        ),
        axis=0,
    )
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    rows = np.concatenate((edges[:, 0], edges[:, 1]))
    columns = np.concatenate((edges[:, 1], edges[:, 0]))
    adjacency = coo_matrix(
        (np.ones(len(rows), dtype=np.float64), (rows, columns)),
        shape=(len(source), len(source)),
    ).tocsr()
    degree = np.asarray(adjacency.sum(axis=1)).reshape(-1)
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
    display_values = _smear_scalar_grid(dataset, smear_sigma)
    minimum = float(np.min(display_values))
    maximum = float(np.max(display_values))
    if not minimum < iso_level < maximum:
        raise ValueError(
            "Isosurface level must lie strictly between "
            f"{minimum:.8g} and {maximum:.8g} after field smearing."
        )
    quality_step = max(1, min(8, int(step_size)))
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
    fractional = vertices / denominator
    cartesian = dataset.origin + fractional @ dataset.cell
    return IsosurfaceMesh(
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


def dataset_by_id(
    datasets: Iterable[VolumetricData],
    dataset_id: str,
) -> VolumetricData:
    target = str(dataset_id)
    for dataset in datasets:
        if dataset.dataset_id == target:
            return dataset
    raise KeyError(f"Volumetric dataset {target!r} was not found.")
