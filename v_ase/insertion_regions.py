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
from scipy.spatial import ConvexHull, QhullError

from .neighbors import find_mic


MAX_INSERTION_REGIONS = 32
MAX_PERIODIC_REGION_IMAGES = 4096
MAX_PROJECTION_COMPONENT_IMAGES = 2_000_000
MAX_INSERTION_PARTITION_CELLS = 250_000
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
    region_lower, region_upper = _bounds_arrays(region.bounds)
    base_lower, base_upper = _bounds_arrays(base_bounds)
    if np.all(region_lower <= base_lower) and np.all(region_upper >= base_upper):
        # A Cartesian box containing every cell vertex contains the complete
        # convex cell. Its translated images add nothing to the region union
        # within that cell, even for very large boxes and highly skew cells.
        return [PeriodicRegionImage(
            region.id,
            region.role,
            (0, 0, 0),
            (0.0, 0.0, 0.0),
            region.bounds,
        )]
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
    # Periodic translations cannot repair a disjoint finite fractional axis.
    # Reject this before constructing a potentially enormous periodic range.
    finite_axes = ~pbc
    if np.any(finite_axes & (
        (np.max(fractional, axis=0) <= 0.0)
        | (np.min(fractional, axis=0) >= 1.0)
    )):
        return []
    ranges: list[range] = []
    for axis in range(3):
        if not pbc[axis]:
            ranges.append(range(0, 1))
            continue
        lower = int(math.ceil(-float(fractional[:, axis].max()) - 1e-9))
        upper = int(math.floor(1.0 - float(fractional[:, axis].min()) + 1e-9))
        ranges.append(range(lower, upper + 1))
    # Bound candidates, not only retained intersections. Otherwise a long box
    # outside the Cartesian cell can enumerate trillions of rejected shifts.
    # Subtract endpoints rather than len(range), which can itself overflow.
    if math.prod(max(0, values.stop - values.start) for values in ranges) > MAX_PERIODIC_REGION_IMAGES:
        raise ValueError(
            "An insertion region requires too many candidate periodic images. "
            "Reduce its size or disable periodic region wrapping."
        )
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

    def _minimum_image_displacements(self, vectors: np.ndarray) -> np.ndarray:
        values = np.asarray(vectors, dtype=float)
        if self.cell is None or not self.pbc_aware or not np.any(self.pbc):
            return values
        return np.asarray(find_mic(values, self.cell, pbc=self.pbc)[0], dtype=float)

    @cached_property
    def _projection_planes(self):
        normals, _ = _box_halfspaces([0, 1] * 3)
        if self.cell is not None:
            normals = np.concatenate((normals, _cell_halfspaces(self.cell)[0]))
        scales = np.linalg.norm(normals, axis=1)
        normals = normals / scales[:, None]
        groups = []
        for size in (1, 2, 3):
            indices = np.asarray([
                subset for subset in itertools.combinations(range(len(normals)), size)
                if np.linalg.matrix_rank(normals[list(subset)], tol=1e-12) == size
            ])
            active = normals[indices]
            groups.append((indices, active, np.linalg.pinv(active, rcond=1e-12)))
        return normals, scales, groups

    def _project_component(self, point: np.ndarray, index: int):
        lower, upper, box_inside = self._projection_components
        if box_inside[index]:
            return np.clip(point, lower[index], upper[index]), 0.5 * (lower[index] + upper[index])
        normals, scales, groups = self._projection_planes
        limits = np.column_stack((upper[index], -lower[index])).reshape(-1)
        limits = np.concatenate((limits, np.tile([1.0, 0.0], 3))) / scales
        candidates = [point[None, :]]
        for indices, active, inverse in groups:
            rhs = np.einsum("nij,j->ni", active, point) - limits[indices]
            candidates.append(point - np.einsum("nij,nj->ni", inverse, rhs))
        candidates = np.concatenate(candidates)
        candidates = candidates[np.all(candidates @ normals.T <= limits + 2e-10, axis=1)]
        if not len(candidates):
            raise ValueError("The insertion domain has an ill-conditioned boundary intersection.")
        squared = np.sum((candidates - point) ** 2, axis=1)
        # All feasible vertices occur among these active sets, so their mean
        # lies inside this positive-volume component, including clipped boxes.
        return candidates[int(np.argmin(squared))], np.mean(candidates, axis=0)

    def _project_closure(self, point: np.ndarray):
        """Nearest Euclidean point in the finite union, including cell images."""
        lower, upper, _ = self._projection_components
        box_delta = np.clip(point, lower, upper) - point
        lower_bound = np.sum(box_delta * box_delta, axis=1)
        initial_index = int(np.argmin(lower_bound))
        best, center = self._project_component(point, initial_index)
        periodic_search = self.cell is not None and self.pbc_aware and np.any(self.pbc)
        if len(lower) == 1 and not periodic_search:
            return best, center
        best_delta = self._minimum_image_displacements((best - point)[None, :])[0]
        best_squared = float(best_delta @ best_delta)
        best_translation = point + best_delta - best
        best = best + best_translation
        center = center + best_translation

        translations = np.zeros((1, 3))
        if periodic_search:
            inverse = np.linalg.inv(self.cell)
            fractional = point @ inverse
            margin = math.sqrt(best_squared) * np.linalg.norm(inverse, axis=0)
            ranges = [
                range(math.ceil(fractional[axis] - 1.0 - margin[axis] - 1e-9),
                      math.floor(fractional[axis] + margin[axis] + 1e-9) + 1)
                if self.pbc[axis] else range(1)
                for axis in range(3)
            ]
            if math.prod(map(len, ranges)) > MAX_PERIODIC_REGION_IMAGES:
                raise ValueError("Domain confinement requires too many periodic images; reduce cell skew or region complexity.")
            translations = np.asarray(list(itertools.product(*ranges))) @ self.cell
        if len(translations) * len(lower) > MAX_PROJECTION_COMPONENT_IMAGES:
            raise ValueError("Domain confinement exceeds the bounded region-image search; reduce region complexity.")
        # Box-distance lower bounds prune exact polytope solves. Search closest
        # bounds first, then stop as soon as all remaining bounds are worse.
        candidates = []
        for translation in translations:
            local = point - translation
            delta = np.clip(local, lower, upper) - local
            distances = np.sum(delta * delta, axis=1)
            for index in np.flatnonzero(distances <= best_squared + 1e-12):
                candidates.append((float(distances[index]), int(index), translation))
        candidates.sort(key=lambda item: item[0])
        for distance, index, translation in candidates:
            if distance > best_squared + 1e-12:
                break
            if index == initial_index and not np.any(translation):
                continue  # This component/query was solved for the initial bound.
            projected, interior = self._project_component(point - translation, index)
            projected = projected + translation
            squared = float(np.sum((projected - point) ** 2))
            if squared < best_squared:
                best, center, best_squared = projected, interior + translation, squared
        return best, center

    def project_points(self, points: Sequence[Sequence[float]]) -> np.ndarray:
        """Project to the nearest feasible domain component in Cartesian space.

        Reject faces belong to the closure used by the conservative penalty.
        Hard publication nudges those boundary points into the chosen component
        so that the returned positions also satisfy the strict rejection rule.
        """
        values = np.asarray(points, dtype=float)
        if values.ndim != 2 or values.shape[1] != 3 or not np.all(np.isfinite(values)):
            raise ValueError("Insertion-domain points must be a finite N x 3 array.")
        output = self.canonicalize_points(values)
        valid = self.contains(output)
        for index in np.flatnonzero(~valid):
            point = output[index]
            projected, interior = self._project_closure(point)
            canonical = self.canonicalize_points(projected[None, :])[0]
            if not self.contains(canonical[None, :])[0]:
                direction = interior - projected
                fraction = min(0.5, 1e-8 / max(float(np.linalg.norm(direction)), 1e-20))
                for _ in range(10):
                    canonical = self.canonicalize_points((projected + fraction * direction)[None, :])[0]
                    if self.contains(canonical[None, :])[0]:
                        break
                    fraction = min(0.5, fraction * 10)
                else:
                    raise ValueError("The insertion domain could not project a confined position.")
            output[index] = canonical
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
        delta = np.zeros_like(canonical)
        for index in np.flatnonzero(~self.contains(canonical)):
            projected, _ = self._project_closure(canonical[index])
            delta[index] = projected - canonical[index]
        return delta

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
        # Use Python integers: a NumPy int64 product can wrap before a shape
        # or work bound is checked. This precedes both the Boolean masks and
        # the much larger per-component Cartesian/fractional corner arrays.
        shape = tuple(len(values) - 1 for values in axes)
        if math.prod(shape) > MAX_INSERTION_PARTITION_CELLS:
            raise ValueError(
                "Insertion regions create more than 250,000 Boolean partition cells. "
                "Reduce region complexity or disable periodic region wrapping."
            )
        centers = [0.5 * (values[:-1] + values[1:]) for values in axes]
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
        lower = np.column_stack([
            axes[axis][active[:, axis]] for axis in range(3)
        ])
        upper = np.column_stack([
            axes[axis][active[:, axis] + 1] for axis in range(3)
        ])
        cell_volumes = np.prod(upper - lower, axis=1)
        if self.cell is None:
            self._projection_components = (lower, upper, np.ones(len(active), dtype=bool))
            return float(np.sum(cell_volumes))
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
        nonempty = wholly_inside.copy()
        cell_values = tuple(float(value) for value in self.cell.reshape(-1))
        for row in boundary:
            i, j, k = active[row]
            bounds = (
                float(axes[0][i]), float(axes[0][i + 1]),
                float(axes[1][j]), float(axes[1][j + 1]),
                float(axes[2][k]), float(axes[2][k + 1]),
            )
            component_volume = _box_cell_intersection_volume_cached(bounds, cell_values)
            volume += component_volume
            nonempty[row] = component_volume > 0.0
        self._projection_components = (lower[nonempty], upper[nonempty], wholly_inside[nonempty])
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
