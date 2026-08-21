"""Fast, validated pair searches backed by matscipy."""

from __future__ import annotations

from typing import Any

import numpy as np
from ase import Atoms
from ase.cell import Cell
from matscipy.neighbours import neighbour_list as _matscipy_neighbour_list


_CELL_EPS = 1e-12


def _normalized_cutoff(cutoff: Any):
    if isinstance(cutoff, dict):
        return {
            key: float(value)
            for key, value in cutoff.items()
        }
    values = np.asarray(cutoff, dtype=float)
    if values.ndim == 0:
        return float(values)
    return np.ascontiguousarray(values, dtype=float)


def _maximum_cutoff(cutoff: Any) -> float:
    if isinstance(cutoff, dict):
        values = [float(value) for value in cutoff.values()]
        return max(values, default=0.0)
    values = np.asarray(cutoff, dtype=float)
    if values.ndim == 0:
        return float(values)
    if values.size == 0:
        return 0.0
    maximum = float(np.nanmax(values))
    # A one-dimensional matscipy cutoff contains one sphere radius per atom;
    # two atoms interact when their spheres overlap.
    return 2.0 * maximum if values.ndim == 1 else maximum


def _nonperiodic_search_geometry(
    positions: np.ndarray,
    cutoff: Any,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a finite orthorhombic search box without changing distances."""

    margin = max(_maximum_cutoff(cutoff), 1.0)
    if len(positions):
        lower = np.min(positions, axis=0) - margin
        upper = np.max(positions, axis=0) + margin
    else:
        lower = np.full(3, -margin, dtype=float)
        upper = np.full(3, margin, dtype=float)
    lengths = np.maximum(upper - lower, 2.0 * margin)
    return np.diag(lengths), lower


def _partial_periodic_search_geometry(
    cell: np.ndarray,
    positions: np.ndarray,
    pbc: np.ndarray,
    cutoff: Any,
) -> tuple[np.ndarray, np.ndarray]:
    """Enclose finite axes without changing any periodic lattice vector.

    matscipy bins atoms through the complete cell matrix.  With partial PBC,
    coordinates outside a finite cell direction can otherwise acquire a shift
    in that nonperiodic direction.  Complete missing finite vectors, then
    enlarge every nonperiodic basis direction to contain the atoms plus one
    search-cutoff margin.  Returned shifts therefore use periodic rows only.
    """

    missing = np.linalg.norm(cell, axis=1) <= _CELL_EPS
    if np.any(missing & pbc):
        raise ValueError("A periodic direction requires a finite cell vector.")
    completed = (
        np.asarray(Cell(cell).complete(), dtype=float)
        if np.any(missing)
        else np.array(cell, dtype=float, copy=True)
    )
    inverse = np.linalg.inv(completed)
    fractional = positions @ inverse if len(positions) else np.empty((0, 3), dtype=float)
    origin = np.zeros(3, dtype=float)
    margin = max(_maximum_cutoff(cutoff), 1.0)
    for axis in np.flatnonzero(~pbc):
        # f = r @ inv(cell), so this reciprocal column bounds the largest
        # fractional displacement made by any Cartesian vector of length
        # ``margin`` through Cauchy-Schwarz.
        fractional_margin = margin * float(np.linalg.norm(inverse[:, axis]))
        fractional_margin = max(fractional_margin, _CELL_EPS)
        if len(fractional):
            lower = float(np.min(fractional[:, axis]) - fractional_margin)
            upper = float(np.max(fractional[:, axis]) + fractional_margin)
        else:
            lower = -fractional_margin
            upper = fractional_margin
        span = max(upper - lower, 2.0 * fractional_margin)
        basis = completed[axis].copy()
        origin += lower * basis
        completed[axis] = span * basis
    return completed, origin


def _empty_result(quantities: str):
    values = []
    for quantity in quantities:
        if quantity in {"i", "j"}:
            values.append(np.empty(0, dtype=np.int32))
        elif quantity == "d":
            values.append(np.empty(0, dtype=float))
        elif quantity == "D":
            values.append(np.empty((0, 3), dtype=float))
        elif quantity == "S":
            values.append(np.empty((0, 3), dtype=np.int32))
        else:
            raise ValueError(f"Unsupported neighbor-list quantity: {quantity}")
    return values[0] if len(values) == 1 else tuple(values)


def primitive_neighbour_list(
    quantities: str,
    *,
    pbc,
    cell,
    positions,
    cutoff,
    numbers=None,
    self_interaction: bool = False,
    use_scaled_positions: bool = False,
):
    """Matscipy equivalent of the ASE primitive pair-search interface.

    v_ase only requests distinct Cartesian pairs. Rank-zero finite structures
    receive a temporary nonperiodic search box so they keep their exact
    coordinates while avoiding the previous quadratic Python scan.
    """

    if self_interaction:
        raise ValueError("v_ase pair searches do not include zero-shift self interactions.")
    if use_scaled_positions:
        raise ValueError("v_ase matscipy searches require Cartesian positions.")

    clean_positions = np.ascontiguousarray(np.asarray(positions, dtype=float))
    if clean_positions.ndim != 2 or clean_positions.shape[1] != 3:
        raise ValueError("Neighbor-search positions must contain one xyz row per atom.")
    clean_pbc = np.asarray(pbc, dtype=bool).reshape(-1)
    if clean_pbc.size == 1:
        clean_pbc = np.repeat(clean_pbc, 3)
    if clean_pbc.size != 3:
        raise ValueError("Neighbor-search periodicity must contain three values.")
    clean_cell = np.asarray(cell, dtype=float).reshape(3, 3)
    clean_numbers = (
        np.ones(len(clean_positions), dtype=np.int32)
        if numbers is None
        else np.ascontiguousarray(np.asarray(numbers, dtype=np.int32))
    )
    if clean_numbers.shape != (len(clean_positions),):
        raise ValueError("Neighbor-search atomic numbers must match the atom count.")
    if not len(clean_positions):
        return _empty_result(quantities)

    clean_cutoff = _normalized_cutoff(cutoff)

    if not np.any(clean_pbc):
        search_cell, cell_origin = _nonperiodic_search_geometry(
            clean_positions,
            clean_cutoff,
        )
    elif not np.all(clean_pbc):
        search_cell, cell_origin = _partial_periodic_search_geometry(
            clean_cell,
            clean_positions,
            clean_pbc,
            clean_cutoff,
        )
    else:
        if np.linalg.matrix_rank(clean_cell, tol=_CELL_EPS) < 3:
            raise ValueError("Three periodic directions require a full-rank cell.")
        search_cell = clean_cell
        cell_origin = np.zeros(3, dtype=float)

    return _matscipy_neighbour_list(
        quantities,
        positions=clean_positions,
        cell=np.ascontiguousarray(search_cell, dtype=float),
        pbc=clean_pbc,
        numbers=clean_numbers,
        cell_origin=np.asarray(cell_origin, dtype=float),
        cutoff=clean_cutoff,
    )


def neighbour_list(
    quantities: str,
    atoms: Atoms,
    cutoff,
    *,
    self_interaction: bool = False,
):
    """Return matscipy neighbors with v_ase's validated pair semantics."""

    if not len(atoms):
        return _empty_result(quantities)
    clean_cutoff = _normalized_cutoff(cutoff)
    if atoms.cell.rank == 3 and np.all(np.asarray(atoms.pbc, dtype=bool)):
        if self_interaction:
            raise ValueError("v_ase pair searches do not include zero-shift self interactions.")
        return _matscipy_neighbour_list(
            quantities,
            atoms=atoms,
            cutoff=clean_cutoff,
        )
    return primitive_neighbour_list(
        quantities,
        pbc=atoms.pbc,
        cell=atoms.cell.array,
        positions=atoms.positions,
        cutoff=clean_cutoff,
        numbers=atoms.numbers,
        self_interaction=self_interaction,
        use_scaled_positions=False,
    )
