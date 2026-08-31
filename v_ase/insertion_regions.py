"""Exact Boolean insertion domains for batch atom and molecule placement."""

from __future__ import annotations

import itertools
import math
import re
import uuid
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Any, Iterable, Sequence

import numpy as np
from ase.geometry import find_mic
from scipy.spatial import ConvexHull, QhullError


MAX_INSERTION_REGIONS = 32
MAX_PERIODIC_REGION_IMAGES = 4096
_TOLERANCE = 1e-10
_REGION_ID_PATTERN = re.compile(r"[^A-Za-z0-9_.:-]+")


def finite_cell_or_none(cell: Any) -> np.ndarray | None:
    matrix = np.asarray(cell, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        return None
    if abs(float(np.linalg.det(matrix))) <= _TOLERANCE:
        return None
    return matrix


def normalize_region_role(value: Any) -> str:
    role = str(value or "allow").strip().lower()
    aliases = {
        "allowed": "allow",
        "prohibited": "reject",
        "prohibit": "reject",
        "excluded": "reject",
    }
    role = aliases.get(role, role)
    if role not in {"allow", "reject"}:
        raise ValueError("Region role must be allow or reject.")
    return role


def normalize_cartesian_bounds(bounds: Sequence[Any]) -> tuple[float, ...]:
    if not isinstance(bounds, Sequence) or isinstance(bounds, (str, bytes)) or len(bounds) != 6:
        raise ValueError(
            "Cartesian bounds must contain xmin, xmax, ymin, ymax, zmin, and zmax."
        )
    normalized = tuple(float(value) for value in bounds)
    if not np.all(np.isfinite(normalized)):
        raise ValueError("Cartesian bounds must be finite.")
    for axis in range(3):
        lower, upper = normalized[axis * 2 : axis * 2 + 2]
        if upper <= lower:
            name = "xyz"[axis]
            raise ValueError(f"{name}max must be greater than {name}min.")
    return normalized


def _region_id(value: Any) -> str:
    normalized = _REGION_ID_PATTERN.sub("-", str(value or "").strip()).strip("-")
    return normalized[:96] or str(uuid.uuid4())


@dataclass(frozen=True)
class InsertionRegion:
    id: str
    name: str
    role: str
    bounds: tuple[float, ...]

    def translated(self, vector: Sequence[float]) -> "InsertionRegion":
        delta = np.asarray(vector, dtype=float)
        if delta.shape != (3,) or not np.all(np.isfinite(delta)):
            raise ValueError("Region translation must be a finite xyz vector.")
        values = np.asarray(self.bounds, dtype=float).reshape(3, 2)
        values += delta[:, None]
        return InsertionRegion(self.id, self.name, self.role, tuple(values.reshape(-1)))

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "bounds": list(self.bounds),
        }


def normalize_insertion_regions(
    raw_regions: Any,
    *,
    legacy_mode: str | None = None,
    legacy_bounds: Sequence[Any] | None = None,
    legacy_role: str | None = None,
) -> tuple[InsertionRegion, ...]:
    if raw_regions is None:
        if str(legacy_mode or "cell").strip().lower() != "box":
            return ()
        raw_regions = [{
            "id": "region-1",
            "name": "Region 1",
            "role": normalize_region_role(legacy_role or "allow"),
            "bounds": legacy_bounds,
        }]
    if not isinstance(raw_regions, Sequence) or isinstance(raw_regions, (str, bytes)):
        raise ValueError("regions must be an array of Cartesian region objects.")
    if len(raw_regions) > MAX_INSERTION_REGIONS:
        raise ValueError(f"At most {MAX_INSERTION_REGIONS} insertion regions can be active.")
    normalized: list[InsertionRegion] = []
    used_ids: set[str] = set()
    role_counts = {"allow": 0, "reject": 0}
    for index, raw in enumerate(raw_regions):
        if not isinstance(raw, dict):
            raise ValueError("Each insertion region must be an object.")
        role = normalize_region_role(raw.get("role") or raw.get("region_role"))
        role_counts[role] += 1
        region_id = _region_id(raw.get("id") or f"region-{index + 1}")
        if region_id in used_ids:
            raise ValueError(f"Insertion region id '{region_id}' is duplicated.")
        used_ids.add(region_id)
        default_name = f"{'Allow' if role == 'allow' else 'Reject'} region {role_counts[role]}"
        name = str(raw.get("name") or default_name).strip()[:96] or default_name
        normalized.append(InsertionRegion(
            id=region_id,
            name=name,
            role=role,
            bounds=normalize_cartesian_bounds(raw.get("bounds")),
        ))
    return tuple(normalized)


def cell_cartesian_corners(cell: Any) -> np.ndarray:
    matrix = finite_cell_or_none(cell)
    if matrix is None:
        raise ValueError("A finite, non-degenerate 3D cell is required.")
    fractional = np.asarray(list(itertools.product((0.0, 1.0), repeat=3)), dtype=float)
    return fractional @ matrix


def cell_cartesian_bounds(cell: Any) -> tuple[float, ...]:
    corners = cell_cartesian_corners(cell)
    return tuple(
        value
        for axis in range(3)
        for value in (float(corners[:, axis].min()), float(corners[:, axis].max()))
    )


def _bounds_arrays(bounds: Sequence[Any]) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(normalize_cartesian_bounds(bounds), dtype=float)
    return values[::2], values[1::2]


def _bounds_corners(bounds: Sequence[Any]) -> np.ndarray:
    lower, upper = _bounds_arrays(bounds)
    return np.asarray(list(itertools.product(*zip(lower, upper))), dtype=float)


def _bounds_intersection(
    first: Sequence[Any],
    second: Sequence[Any],
) -> tuple[float, ...] | None:
    first_lower, first_upper = _bounds_arrays(first)
    second_lower, second_upper = _bounds_arrays(second)
    lower = np.maximum(first_lower, second_lower)
    upper = np.minimum(first_upper, second_upper)
    if np.any(upper - lower <= _TOLERANCE):
        return None
    return tuple(np.column_stack((lower, upper)).reshape(-1))


def _translated_bounds(bounds: Sequence[Any], translation: np.ndarray) -> tuple[float, ...]:
    values = np.asarray(bounds, dtype=float).reshape(3, 2) + translation[:, None]
    return tuple(values.reshape(-1))


@dataclass(frozen=True)
class PeriodicRegionImage:
    region_id: str
    role: str
    shift: tuple[int, int, int]
    translation: tuple[float, float, float]
    bounds: tuple[float, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "role": self.role,
            "shift": list(self.shift),
            "translation": list(self.translation),
            "bounds": list(self.bounds),
        }


def _periodic_region_images(
    region: InsertionRegion,
    cell: np.ndarray | None,
    pbc: np.ndarray,
    pbc_aware: bool,
) -> list[PeriodicRegionImage]:
    if cell is None:
        return [PeriodicRegionImage(
            region.id,
            region.role,
            (0, 0, 0),
            (0.0, 0.0, 0.0),
            region.bounds,
        )]
    base_bounds = cell_cartesian_bounds(cell)
    if not pbc_aware or not np.any(pbc):
        clipped = _bounds_intersection(region.bounds, base_bounds)
        if clipped is None:
            return []
        return [PeriodicRegionImage(
            region.id,
            region.role,
            (0, 0, 0),
            (0.0, 0.0, 0.0),
            region.bounds,
        )]

    fractional = _bounds_corners(region.bounds) @ np.linalg.inv(cell)
    ranges: list[range] = []
    for axis in range(3):
        if not pbc[axis]:
            ranges.append(range(0, 1))
            continue
        lower = int(math.ceil(-float(fractional[:, axis].max()) - 1e-9))
        upper = int(math.floor(1.0 - float(fractional[:, axis].min()) + 1e-9))
        ranges.append(range(lower, upper + 1))
    images: list[PeriodicRegionImage] = []
    for shift_values in itertools.product(*ranges):
        shift = np.asarray(shift_values, dtype=int)
        translation = shift @ cell
        bounds = _translated_bounds(region.bounds, translation)
        if _bounds_intersection(bounds, base_bounds) is None:
            continue
        images.append(PeriodicRegionImage(
            region.id,
            region.role,
            tuple(int(value) for value in shift),
            tuple(float(value) for value in translation),
            bounds,
        ))
        if len(images) > MAX_PERIODIC_REGION_IMAGES:
            raise ValueError(
                "An insertion region generates too many periodic images. "
                "Reduce its size or disable periodic region wrapping."
            )
    return images


def _cell_halfspaces(cell: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    inverse = np.linalg.inv(cell)
    normals: list[np.ndarray] = []
    limits: list[float] = []
    for axis in range(3):
        normal = inverse[:, axis]
        normals.extend((normal, -normal))
        limits.extend((1.0, 0.0))
    return np.asarray(normals, dtype=float), np.asarray(limits, dtype=float)


def _box_halfspaces(bounds: Sequence[Any]) -> tuple[np.ndarray, np.ndarray]:
    lower, upper = _bounds_arrays(bounds)
    normals = np.asarray([
        [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0], [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0], [0.0, 0.0, -1.0],
    ])
    limits = np.asarray([
        upper[0], -lower[0], upper[1], -lower[1], upper[2], -lower[2]
    ])
    return normals, limits


_CUBE_EDGE_PAIRS = tuple(
    (first, second)
    for first in range(8)
    for second in range(first + 1, 8)
    if (first ^ second).bit_count() == 1
)


def _edge_plane_intersections(
    corners: np.ndarray,
    plane_normals: np.ndarray,
    plane_limits: np.ndarray,
    clip_normals: np.ndarray,
    clip_limits: np.ndarray,
) -> np.ndarray:
    edges = np.asarray(_CUBE_EDGE_PAIRS, dtype=int)
    starts = corners[edges[:, 0]]
    deltas = corners[edges[:, 1]] - starts
    denominator = deltas @ plane_normals.T
    numerator = plane_limits[None, :] - starts @ plane_normals.T
    valid = np.abs(denominator) > 1e-13
    parameter = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=valid,
    )
    valid &= (parameter >= -2e-10) & (parameter <= 1.0 + 2e-10)
    if not np.any(valid):
        return np.empty((0, 3), dtype=float)
    candidates = starts[:, None, :] + parameter[:, :, None] * deltas[:, None, :]
    candidates = candidates[valid]
    inside = np.all(
        candidates @ clip_normals.T <= clip_limits[None, :] + 2e-9,
        axis=1,
    )
    return candidates[inside]


@lru_cache(maxsize=32768)
def _box_cell_intersection_volume_cached(
    bounds: tuple[float, ...],
    cell_values: tuple[float, ...],
) -> float:
    cell = np.asarray(cell_values, dtype=float).reshape(3, 3)
    cell_bounds = cell_cartesian_bounds(cell)
    clipped = _bounds_intersection(bounds, cell_bounds)
    if clipped is None:
        return 0.0
    corners = _bounds_corners(bounds)
    fractional = corners @ np.linalg.inv(cell)
    if np.all((fractional >= -1e-10) & (fractional <= 1.0 + 1e-10)):
        lower, upper = _bounds_arrays(bounds)
        return float(np.prod(upper - lower))
    cell_corners = cell_cartesian_corners(cell)
    lower, upper = _bounds_arrays(bounds)
    if np.all((cell_corners >= lower - 1e-10) & (cell_corners <= upper + 1e-10)):
        return abs(float(np.linalg.det(cell)))

    box_normals, box_limits = _box_halfspaces(bounds)
    cell_normals, cell_limits = _cell_halfspaces(cell)
    normals = np.concatenate((box_normals, cell_normals), axis=0)
    limits = np.concatenate((box_limits, cell_limits), axis=0)
    box_inside = corners[
        np.all(corners @ cell_normals.T <= cell_limits[None, :] + 2e-9, axis=1)
    ]
    cell_inside = cell_corners[
        np.all(cell_corners @ box_normals.T <= box_limits[None, :] + 2e-9, axis=1)
    ]
    box_edge_hits = _edge_plane_intersections(
        corners,
        cell_normals,
        cell_limits,
        normals,
        limits,
    )
    cell_edge_hits = _edge_plane_intersections(
        cell_corners,
        box_normals,
        box_limits,
        normals,
        limits,
    )
    vertices = np.concatenate(
        (box_inside, cell_inside, box_edge_hits, cell_edge_hits),
        axis=0,
    )
    if len(vertices) < 4:
        return 0.0
    unique = np.unique(np.round(vertices, decimals=11), axis=0)
    if len(unique) < 4:
        return 0.0
    try:
        return float(ConvexHull(unique).volume)
    except QhullError:
        return 0.0


def box_cell_intersection_volume(bounds: Sequence[Any], cell: Any) -> float:
    normalized = normalize_cartesian_bounds(bounds)
    matrix = finite_cell_or_none(cell)
    if matrix is None:
        raise ValueError("A finite, non-degenerate 3D cell is required.")
    return _box_cell_intersection_volume_cached(
        normalized,
        tuple(float(value) for value in matrix.reshape(-1)),
    )


class InsertionDomain:
    """Finite Boolean domain built from allow and reject Cartesian regions."""

    def __init__(
        self,
        *,
        cell: Any,
        pbc: Sequence[bool],
        regions: Sequence[InsertionRegion],
        pbc_aware: bool = True,
    ):
        self.cell = finite_cell_or_none(cell)
        self.pbc = np.asarray(pbc, dtype=bool)
        if self.pbc.shape != (3,):
            raise ValueError("pbc must contain exactly three boolean values.")
        if np.any(self.pbc) and self.cell is None:
            raise ValueError("Periodic insertion requires a finite, non-degenerate 3D cell.")
        self.regions = tuple(regions)
        self.pbc_aware = bool(pbc_aware)
        self.allow_regions = tuple(region for region in self.regions if region.role == "allow")
        self.reject_regions = tuple(region for region in self.regions if region.role == "reject")
        if self.cell is None and not self.allow_regions:
            raise ValueError(
                "A structure without a finite unit cell requires at least one Allow region; "
                "Reject regions alone do not define a finite insertion volume."
            )
        images: list[PeriodicRegionImage] = []
        for region in self.regions:
            images.extend(_periodic_region_images(
                region,
                self.cell,
                self.pbc,
                self.pbc_aware,
            ))
        self.images = tuple(images)
        self.allow_images = tuple(image for image in self.images if image.role == "allow")
        self.reject_images = tuple(image for image in self.images if image.role == "reject")
        if self.allow_regions and not self.allow_images:
            raise ValueError("The Allow regions do not overlap the insertion domain.")
        if self.volume <= _TOLERANCE:
            raise ValueError("Allow and Reject regions leave no accessible insertion volume.")

    @cached_property
    def base_bounds(self) -> tuple[float, ...]:
        if self.cell is not None:
            return cell_cartesian_bounds(self.cell)
        lower = np.min([_bounds_arrays(region.bounds)[0] for region in self.allow_regions], axis=0)
        upper = np.max([_bounds_arrays(region.bounds)[1] for region in self.allow_regions], axis=0)
        return tuple(np.column_stack((lower, upper)).reshape(-1))

    def _inside_images(
        self,
        points: np.ndarray,
        images: Sequence[PeriodicRegionImage],
    ) -> np.ndarray:
        result = np.zeros(len(points), dtype=bool)
        for image in images:
            lower, upper = _bounds_arrays(image.bounds)
            result |= np.all((points >= lower - _TOLERANCE) & (points <= upper + _TOLERANCE), axis=1)
        return result

    def contains(self, points: Sequence[Sequence[float]]) -> np.ndarray:
        values = np.asarray(points, dtype=float)
        if values.ndim != 2 or values.shape[1] != 3 or not np.all(np.isfinite(values)):
            raise ValueError("Insertion-domain points must be a finite N x 3 array.")
        if self.cell is not None:
            fractional = values @ np.linalg.inv(self.cell)
            base = np.all(
                (fractional >= -_TOLERANCE) & (fractional <= 1.0 + _TOLERANCE),
                axis=1,
            )
        else:
            base = np.ones(len(values), dtype=bool)
        allowed = (
            self._inside_images(values, self.allow_images)
            if self.allow_regions
            else np.ones(len(values), dtype=bool)
        )
        rejected = self._inside_images(values, self.reject_images)
        return base & allowed & ~rejected

    def canonicalize_points(self, points: np.ndarray) -> np.ndarray:
        values = np.asarray(points, dtype=float).copy()
        if self.cell is None or not self.pbc_aware or not np.any(self.pbc):
            return values
        fractional = values @ np.linalg.inv(self.cell)
        fractional[:, self.pbc] %= 1.0
        return fractional @ self.cell

    def _project_to_base(self, point: np.ndarray) -> np.ndarray:
        value = np.asarray(point, dtype=float).copy()
        if self.cell is None:
            return value
        inverse = np.linalg.inv(self.cell)
        fractional = value @ inverse
        for axis in range(3):
            if self.pbc_aware and self.pbc[axis]:
                fractional[axis] %= 1.0
            else:
                fractional[axis] = float(np.clip(fractional[axis], 1e-9, 1.0 - 1e-9))
        return fractional @ self.cell

    def _candidate_points(self, point: np.ndarray) -> list[np.ndarray]:
        epsilon = 1e-8
        base = self._project_to_base(point)
        if self.cell is not None and self.pbc_aware and np.any(self.pbc):
            ranges = [(-1, 0, 1) if periodic else (0,) for periodic in self.pbc]
            point_images = [
                base + np.asarray(shift, dtype=float) @ self.cell
                for shift in itertools.product(*ranges)
            ]
        else:
            point_images = [base]
        candidates: list[np.ndarray] = [base]
        for source in point_images:
            for image in self.allow_images:
                lower, upper = _bounds_arrays(image.bounds)
                candidates.append(self._project_to_base(
                    np.clip(source, lower + epsilon, upper - epsilon)
                ))
            for image in self.reject_images:
                lower, upper = _bounds_arrays(image.bounds)
                if not np.all((source >= lower) & (source <= upper)):
                    continue
                for axis in range(3):
                    lower_face = source.copy()
                    lower_face[axis] = lower[axis] - epsilon
                    candidates.append(self._project_to_base(lower_face))
                    upper_face = source.copy()
                    upper_face[axis] = upper[axis] + epsilon
                    candidates.append(self._project_to_base(upper_face))
        unique = np.unique(np.round(np.asarray(candidates), decimals=12), axis=0)
        return [candidate for candidate in unique]

    def _minimum_image_displacements(self, vectors: np.ndarray) -> np.ndarray:
        values = np.asarray(vectors, dtype=float)
        if self.cell is None or not self.pbc_aware or not np.any(self.pbc):
            return values
        return np.asarray(find_mic(values, self.cell, pbc=self.pbc)[0], dtype=float)

    def project_points(self, points: Sequence[Sequence[float]]) -> np.ndarray:
        """Project points to the nearest generated feasible boundary candidate.

        Region volume and sampling are exact. This projection is used only by
        the optional confinement force during relaxation; it searches all
        relevant allow clamps and reject faces, then chooses the nearest valid
        candidate in Cartesian distance.
        """
        values = np.asarray(points, dtype=float)
        if values.ndim != 2 or values.shape[1] != 3 or not np.all(np.isfinite(values)):
            raise ValueError("Insertion-domain points must be a finite N x 3 array.")
        output = self.canonicalize_points(values)
        valid = self.contains(output)
        for index in np.flatnonzero(~valid):
            point = output[index]
            candidates = self._candidate_points(point)
            feasible = [
                candidate
                for candidate in candidates
                if bool(self.contains(np.asarray([candidate]))[0])
            ]
            if not feasible:
                # Resolve combinations of overlapping reject regions without
                # replacing exact domain semantics by a voxel approximation.
                frontier = candidates
                for _ in range(max(1, len(self.reject_regions))):
                    next_frontier: list[np.ndarray] = []
                    for candidate in frontier:
                        next_frontier.extend(self._candidate_points(candidate))
                    feasible = [
                        candidate
                        for candidate in next_frontier
                        if bool(self.contains(np.asarray([candidate]))[0])
                    ]
                    if feasible:
                        break
                    frontier = next_frontier
            if not feasible:
                raise ValueError("The insertion domain could not project a confined position.")
            deltas = self._minimum_image_displacements(
                np.asarray(feasible, dtype=float) - point
            )
            distances = np.einsum("ij,ij->i", deltas, deltas)
            output[index] = feasible[int(np.argmin(distances))]
        return output

    def displacements_to_domain(
        self,
        points: Sequence[Sequence[float]],
    ) -> np.ndarray:
        """Return shortest physical displacements into the Boolean domain.

        Periodic components use ASE's triclinic minimum-image solution. The
        returned vectors can therefore cross a periodic face without applying
        a cell-length Cartesian penalty.
        """
        values = np.asarray(points, dtype=float)
        if values.ndim != 2 or values.shape[1] != 3 or not np.all(np.isfinite(values)):
            raise ValueError("Insertion-domain points must be a finite N x 3 array.")
        canonical = self.canonicalize_points(values)
        projected = self.project_points(values)
        return self._minimum_image_displacements(projected - canonical)

    @cached_property
    def volume(self) -> float:
        base_lower, base_upper = _bounds_arrays(self.base_bounds)
        coordinates: list[list[float]] = [
            [float(base_lower[axis]), float(base_upper[axis])] for axis in range(3)
        ]
        for image in self.images:
            lower, upper = _bounds_arrays(image.bounds)
            for axis in range(3):
                if lower[axis] > base_lower[axis] + _TOLERANCE and lower[axis] < base_upper[axis] - _TOLERANCE:
                    coordinates[axis].append(float(lower[axis]))
                if upper[axis] > base_lower[axis] + _TOLERANCE and upper[axis] < base_upper[axis] - _TOLERANCE:
                    coordinates[axis].append(float(upper[axis]))
        axes = [np.unique(np.asarray(values, dtype=float)) for values in coordinates]
        centers = [0.5 * (values[:-1] + values[1:]) for values in axes]
        shape = tuple(len(values) for values in centers)
        allowed = np.zeros(shape, dtype=bool) if self.allow_regions else np.ones(shape, dtype=bool)
        rejected = np.zeros(shape, dtype=bool)

        def mark(target: np.ndarray, images: Iterable[PeriodicRegionImage]) -> None:
            for image in images:
                lower, upper = _bounds_arrays(image.bounds)
                masks = [
                    (centers[axis] >= lower[axis] - _TOLERANCE)
                    & (centers[axis] <= upper[axis] + _TOLERANCE)
                    for axis in range(3)
                ]
                target |= masks[0][:, None, None] & masks[1][None, :, None] & masks[2][None, None, :]

        if self.allow_regions:
            mark(allowed, self.allow_images)
        mark(rejected, self.reject_images)
        active = np.argwhere(allowed & ~rejected)
        if not len(active):
            return 0.0
        widths = [values[1:] - values[:-1] for values in axes]
        if self.cell is None:
            return float(np.sum(
                widths[0][active[:, 0]]
                * widths[1][active[:, 1]]
                * widths[2][active[:, 2]]
            ))

        lower = np.column_stack([
            axes[axis][active[:, axis]] for axis in range(3)
        ])
        upper = np.column_stack([
            axes[axis][active[:, axis] + 1] for axis in range(3)
        ])
        cell_volumes = np.prod(upper - lower, axis=1)
        corner_selectors = np.asarray(
            list(itertools.product((0, 1), repeat=3)), dtype=bool
        )
        corners = np.where(
            corner_selectors[None, :, :],
            upper[:, None, :],
            lower[:, None, :],
        )
        fractional = corners @ np.linalg.inv(self.cell)
        wholly_inside = np.all(
            (fractional >= -2e-10) & (fractional <= 1.0 + 2e-10),
            axis=(1, 2),
        )
        volume = float(np.sum(cell_volumes[wholly_inside]))

        # An AABB is certainly outside the cell if every point lies beyond at
        # least one defining cell halfspace. This exact rejection leaves only
        # boundary-crossing cells for the convex-polyhedron calculation.
        normals, limits = _cell_halfspaces(self.cell)
        minimum_dot = np.zeros((len(active), len(normals)), dtype=float)
        for plane_index, normal in enumerate(normals):
            support = np.where(normal[None, :] >= 0.0, lower, upper)
            minimum_dot[:, plane_index] = support @ normal
        wholly_outside = np.any(minimum_dot > limits[None, :] + 2e-10, axis=1)
        boundary = np.flatnonzero(~wholly_inside & ~wholly_outside)
        cell_values = tuple(float(value) for value in self.cell.reshape(-1))
        for row in boundary:
            i, j, k = active[row]
            bounds = (
                float(axes[0][i]), float(axes[0][i + 1]),
                float(axes[1][j]), float(axes[1][j + 1]),
                float(axes[2][k]), float(axes[2][k + 1]),
            )
            volume += _box_cell_intersection_volume_cached(bounds, cell_values)
        return float(volume)

    def random_points(
        self,
        count: int,
        *,
        seed: int | None = None,
        max_batches: int = 512,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        requested = int(count)
        if requested < 1:
            raise ValueError("Insertion count must be positive.")
        generator = np.random.default_rng(seed)
        accepted: list[np.ndarray] = []
        accepted_count = 0
        eligible_count = 0
        attempted = 0
        lower, upper = _bounds_arrays(self.base_bounds)
        for _ in range(max(1, int(max_batches))):
            remaining = requested - accepted_count
            if remaining <= 0:
                break
            batch_size = min(1_000_000, max(4096, remaining * 8))
            if self.cell is not None:
                candidates = generator.random((batch_size, 3), dtype=np.float64) @ self.cell
            else:
                candidates = generator.uniform(lower, upper, size=(batch_size, 3))
            attempted += batch_size
            eligible = candidates[self.contains(candidates)]
            eligible_count += len(eligible)
            if len(eligible):
                chunk = eligible[:remaining]
                accepted.append(chunk)
                accepted_count += len(chunk)
        if accepted_count < requested:
            raise ValueError(
                "The insertion domain has too little accessible volume for sampling. "
                "Resize the Allow or Reject regions."
            )
        return np.concatenate(accepted, axis=0)[:requested], {
            "attempted": int(attempted),
            "accepted": int(requested),
            "acceptance_fraction": float(eligible_count / max(1, attempted)),
        }

    def sobol_points(
        self,
        count: int,
        *,
        coordinate_basis: str,
        seed: int | None,
        max_batches: int = 96,
    ) -> tuple[np.ndarray, int]:
        from scipy.stats import qmc

        target = max(1, int(count))
        basis = str(coordinate_basis or "cartesian").lower()
        if basis == "fractional" and self.cell is None:
            raise ValueError("Fractional homogeneous spacing requires a finite unit cell.")
        lower, upper = _bounds_arrays(self.base_bounds)
        engine = qmc.Sobol(d=3, scramble=True, seed=seed)
        chunks: list[np.ndarray] = []
        accepted_count = 0
        attempted = 0
        batch_size = 1 << int(math.ceil(math.log2(max(2048, min(131072, target * 4)))))
        for _ in range(max_batches):
            raw = engine.random(batch_size)
            attempted += batch_size
            candidates = (
                raw @ self.cell
                if basis == "fractional" and self.cell is not None
                else lower + raw * (upper - lower)
            )
            eligible = candidates[self.contains(candidates)]
            if len(eligible):
                chunk = eligible[: target - accepted_count]
                chunks.append(chunk)
                accepted_count += len(chunk)
            if accepted_count >= target:
                break
        if accepted_count < target:
            raise ValueError("The insertion domain is too small for homogeneous placement.")
        return np.concatenate(chunks, axis=0)[:target], attempted

    def to_json(self) -> dict[str, Any]:
        return {
            "base": "unit-cell" if self.cell is not None else "allow-regions",
            "has_unit_cell": self.cell is not None,
            "pbc_aware": self.pbc_aware,
            "volume_angstrom3": self.volume,
            "regions": [region.to_json() for region in self.regions],
            "images": [image.to_json() for image in self.images],
        }


def build_insertion_domain(
    *,
    cell: Any,
    pbc: Sequence[bool],
    regions: Sequence[InsertionRegion] | Sequence[dict[str, Any]],
    pbc_aware: bool = True,
) -> InsertionDomain:
    normalized = (
        tuple(regions)
        if all(isinstance(region, InsertionRegion) for region in regions)
        else normalize_insertion_regions(regions)
    )
    return InsertionDomain(
        cell=cell,
        pbc=pbc,
        regions=normalized,
        pbc_aware=pbc_aware,
    )
