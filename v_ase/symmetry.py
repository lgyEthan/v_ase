"""Crystallographic symmetry analysis and cell transformations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Literal

import numpy as np
from ase import Atoms
from ase.data import chemical_symbols

from .io import atom_labels, set_atom_labels


TypeBasis = Literal["element", "label"]
TransformMode = Literal["primitive", "conventional", "refine"]


class SymmetryDependencyError(RuntimeError):
    """Raised when an optional crystallography dependency is unavailable."""


def _require_spglib():
    try:
        import spglib
    except ModuleNotFoundError as exc:
        raise SymmetryDependencyError(
            "Symmetry analysis requires spglib. Install with "
            '`python -m pip install -e ".[symmetry]"`.'
        ) from exc
    return spglib


def _require_seekpath():
    try:
        import seekpath
    except ModuleNotFoundError as exc:
        raise SymmetryDependencyError(
            "High-symmetry paths require SeeK-path. Install with "
            '`python -m pip install -e ".[symmetry]"`.'
        ) from exc
    return seekpath


def _validated_cell(atoms: Atoms) -> np.ndarray:
    lattice = np.asarray(atoms.cell.array, dtype=float)
    if lattice.shape != (3, 3) or not np.isfinite(lattice).all():
        raise ValueError("Symmetry analysis requires a finite 3 x 3 unit cell.")
    if abs(float(np.linalg.det(lattice))) < 1e-12:
        raise ValueError("Symmetry analysis requires an invertible 3D unit cell.")
    if len(atoms) == 0:
        raise ValueError("Symmetry analysis requires at least one atom.")
    return lattice


@dataclass(frozen=True)
class _TypeEncoding:
    values: np.ndarray
    symbols: dict[int, str]
    labels: dict[int, str]


def _encode_types(atoms: Atoms, basis: TypeBasis) -> _TypeEncoding:
    if basis not in {"element", "label"}:
        raise ValueError("type_basis must be 'element' or 'label'.")
    labels = atom_labels(atoms)
    if basis == "element":
        values = np.asarray(atoms.numbers, dtype=np.int32)
        unique = sorted(set(int(value) for value in values))
        return _TypeEncoding(
            values=values,
            symbols={number: chemical_symbols[number] for number in unique},
            labels={number: chemical_symbols[number] for number in unique},
        )

    key_to_type: dict[tuple[int, str], int] = {}
    symbols: dict[int, str] = {}
    encoded_labels: dict[int, str] = {}
    values = np.empty(len(atoms), dtype=np.int32)
    for index, (number, label) in enumerate(zip(atoms.numbers, labels)):
        key = (int(number), str(label))
        type_id = key_to_type.setdefault(key, len(key_to_type) + 1)
        values[index] = type_id
        symbols[type_id] = chemical_symbols[int(number)]
        encoded_labels[type_id] = str(label)
    return _TypeEncoding(values=values, symbols=symbols, labels=encoded_labels)


def _spglib_cell(
    atoms: Atoms,
    *,
    type_basis: TypeBasis = "element",
    magnetic: bool = False,
) -> tuple[tuple[Any, ...], _TypeEncoding]:
    lattice = _validated_cell(atoms)
    encoding = _encode_types(atoms, type_basis)
    base: tuple[Any, ...] = (
        lattice,
        np.mod(np.asarray(atoms.get_scaled_positions(wrap=False), dtype=float), 1.0),
        encoding.values,
    )
    if not magnetic:
        return base, encoding

    magmoms = np.asarray(atoms.get_initial_magnetic_moments(), dtype=float)
    if magmoms.shape not in {(len(atoms),), (len(atoms), 3)}:
        raise ValueError(
            "Magnetic symmetry requires one scalar or 3-vector magnetic moment per atom."
        )
    return (*base, magmoms), encoding


def _crystal_system(number: int) -> str:
    if number <= 2:
        return "triclinic"
    if number <= 15:
        return "monoclinic"
    if number <= 74:
        return "orthorhombic"
    if number <= 142:
        return "tetragonal"
    if number <= 167:
        return "trigonal"
    if number <= 194:
        return "hexagonal"
    return "cubic"


def _analysis_warnings(atoms: Atoms, type_basis: TypeBasis) -> list[str]:
    warnings: list[str] = []
    pbc = np.asarray(atoms.pbc, dtype=bool)
    if not pbc.all():
        warnings.append(
            "spglib applies three-dimensional periodic symmetry. Partial-PBC "
            "or slab results depend on the supplied vacuum cell."
        )
    labels = atom_labels(atoms)
    if type_basis == "element" and any(
        label != chemical_symbols[int(number)]
        for label, number in zip(labels, atoms.numbers)
    ):
        warnings.append(
            "Custom labels were ignored for symmetry equivalence; chemical "
            "elements define crystallographic types."
        )
    return warnings


def _orbits(atoms: Atoms, dataset: Any) -> list[dict[str, Any]]:
    labels = atom_labels(atoms)
    equivalents = np.asarray(dataset.equivalent_atoms, dtype=int)
    scaled = np.mod(np.asarray(atoms.get_scaled_positions(wrap=False), dtype=float), 1.0)
    ordered_representatives = list(dict.fromkeys(int(value) for value in equivalents))
    result = []
    for orbit_number, representative in enumerate(ordered_representatives, start=1):
        indices = np.flatnonzero(equivalents == representative).astype(int).tolist()
        first = indices[0]
        result.append(
            {
                "orbit": orbit_number,
                "representative": int(representative),
                "indices": indices,
                "multiplicity": len(indices),
                "wyckoff": str(dataset.wyckoffs[first]),
                "site_symmetry": str(dataset.site_symmetry_symbols[first]).strip(),
                "element": chemical_symbols[int(atoms.numbers[first])],
                "labels": list(dict.fromkeys(str(labels[index]) for index in indices)),
                "fractional_position": scaled[first].tolist(),
            }
        )
    return result


def analyze_symmetry(
    atoms: Atoms,
    *,
    symprec: float = 1e-5,
    angle_tolerance: float = -1.0,
    type_basis: TypeBasis = "element",
    magnetic: bool = False,
    mag_symprec: float = -1.0,
) -> dict[str, Any]:
    """Return a JSON-safe crystallographic dataset for an ASE structure."""
    spglib = _require_spglib()
    if not np.isfinite(symprec) or symprec <= 0:
        raise ValueError("symprec must be a positive finite length in Angstrom.")
    cell, _ = _spglib_cell(atoms, type_basis=type_basis, magnetic=magnetic)
    warnings = _analysis_warnings(atoms, type_basis)

    if magnetic:
        dataset = spglib.get_magnetic_symmetry_dataset(
            cell,
            symprec=float(symprec),
            angle_tolerance=float(angle_tolerance),
            mag_symprec=float(mag_symprec),
        )
        if dataset is None:
            raise ValueError(f"spglib could not find magnetic symmetry at symprec={symprec:g} A.")
        return {
            "status": "ok",
            "kind": "magnetic",
            "symprec": float(symprec),
            "angle_tolerance": float(angle_tolerance),
            "type_basis": type_basis,
            "uni_number": int(dataset.uni_number),
            "magnetic_spacegroup_type": int(dataset.msg_type),
            "hall_number": int(dataset.hall_number),
            "operation_count": len(dataset.rotations),
            "rotations": np.asarray(dataset.rotations, dtype=int).tolist(),
            "translations": np.asarray(dataset.translations, dtype=float).tolist(),
            "time_reversals": np.asarray(dataset.time_reversals, dtype=int).tolist(),
            "equivalent_atoms": np.asarray(dataset.equivalent_atoms, dtype=int).tolist(),
            "warnings": warnings,
        }

    dataset = spglib.get_symmetry_dataset(
        cell,
        symprec=float(symprec),
        angle_tolerance=float(angle_tolerance),
    )
    if dataset is None:
        raise ValueError(f"spglib could not find symmetry at symprec={symprec:g} A.")
    return {
        "status": "ok",
        "kind": "space-group",
        "symprec": float(symprec),
        "angle_tolerance": float(angle_tolerance),
        "type_basis": type_basis,
        "international": str(dataset.international).strip(),
        "number": int(dataset.number),
        "hall": str(dataset.hall).strip(),
        "hall_number": int(dataset.hall_number),
        "choice": str(dataset.choice).strip(),
        "pointgroup": str(dataset.pointgroup).strip(),
        "crystal_system": _crystal_system(int(dataset.number)),
        "operation_count": len(dataset.rotations),
        "primitive_atom_count": len(set(np.asarray(dataset.mapping_to_primitive, dtype=int))),
        "standard_atom_count": len(dataset.std_types),
        "equivalent_atoms": np.asarray(dataset.equivalent_atoms, dtype=int).tolist(),
        "crystallographic_orbits": np.asarray(
            dataset.crystallographic_orbits, dtype=int
        ).tolist(),
        "wyckoffs": [str(value) for value in dataset.wyckoffs],
        "site_symmetry_symbols": [
            str(value).strip() for value in dataset.site_symmetry_symbols
        ],
        "orbits": _orbits(atoms, dataset),
        "rotations": np.asarray(dataset.rotations, dtype=int).tolist(),
        "translations": np.asarray(dataset.translations, dtype=float).tolist(),
        "transformation_matrix": np.asarray(
            dataset.transformation_matrix, dtype=float
        ).tolist(),
        "origin_shift": np.asarray(dataset.origin_shift, dtype=float).tolist(),
        "warnings": warnings,
    }


def symmetry_tolerance_scan(
    atoms: Atoms,
    *,
    tolerances: Iterable[float] = (1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2),
    angle_tolerance: float = -1.0,
    type_basis: TypeBasis = "element",
) -> list[dict[str, Any]]:
    """Report how the detected space group changes with positional tolerance."""
    result = []
    for tolerance in tolerances:
        value = float(tolerance)
        try:
            analysis = analyze_symmetry(
                atoms,
                symprec=value,
                angle_tolerance=angle_tolerance,
                type_basis=type_basis,
            )
            result.append(
                {
                    "symprec": value,
                    "number": analysis["number"],
                    "international": analysis["international"],
                    "operation_count": analysis["operation_count"],
                }
            )
        except ValueError as exc:
            result.append({"symprec": value, "error": str(exc)})
    return result


def transform_by_symmetry(
    atoms: Atoms,
    mode: TransformMode,
    *,
    symprec: float = 1e-5,
    angle_tolerance: float = -1.0,
    type_basis: TypeBasis = "element",
    idealize: bool = True,
) -> tuple[Atoms, dict[str, Any]]:
    """Create a primitive, conventional, or refined cell with explicit data loss."""
    spglib = _require_spglib()
    cell, encoding = _spglib_cell(atoms, type_basis=type_basis)
    if mode == "primitive":
        transformed = spglib.standardize_cell(
            cell,
            to_primitive=True,
            no_idealize=not idealize,
            symprec=float(symprec),
            angle_tolerance=float(angle_tolerance),
        )
    elif mode == "conventional":
        transformed = spglib.standardize_cell(
            cell,
            to_primitive=False,
            no_idealize=not idealize,
            symprec=float(symprec),
            angle_tolerance=float(angle_tolerance),
        )
    elif mode == "refine":
        transformed = spglib.refine_cell(
            cell,
            symprec=float(symprec),
            angle_tolerance=float(angle_tolerance),
        )
    else:
        raise ValueError("mode must be primitive, conventional, or refine.")
    if transformed is None:
        raise ValueError(
            f"spglib could not create the {mode} structure at symprec={symprec:g} A."
        )

    lattice, scaled_positions, type_values = transformed
    type_values = np.asarray(type_values, dtype=int)
    try:
        symbols = [encoding.symbols[int(value)] for value in type_values]
        labels = [encoding.labels[int(value)] for value in type_values]
    except KeyError as exc:
        raise ValueError("spglib returned an unknown crystallographic type.") from exc
    result = Atoms(
        symbols=symbols,
        scaled_positions=np.mod(np.asarray(scaled_positions, dtype=float), 1.0),
        cell=np.asarray(lattice, dtype=float),
        pbc=np.asarray(atoms.pbc, dtype=bool),
        info=deepcopy(atoms.info),
    )
    set_atom_labels(result, labels)
    result.info["v_ase_symmetry_transform"] = {
        "mode": mode,
        "symprec": float(symprec),
        "angle_tolerance": float(angle_tolerance),
        "type_basis": type_basis,
        "idealize": bool(idealize),
        "source_atom_count": len(atoms),
    }
    warnings = []
    if atoms.constraints:
        warnings.append(
            "Constraints were removed because atom ordering and multiplicity changed."
        )
    if atoms.calc is not None:
        warnings.append(
            "The calculator was removed because cached results do not describe the transformed cell."
        )
    if any(name not in {"numbers", "positions", "atom_labels"} for name in atoms.arrays):
        warnings.append(
            "Per-atom arrays other than atom_labels were removed because no exact "
            "source mapping is defined for standardized atoms."
        )
    return result, {
        "mode": mode,
        "source_atom_count": len(atoms),
        "result_atom_count": len(result),
        "warnings": warnings,
    }


def high_symmetry_path(
    atoms: Atoms,
    *,
    symprec: float = 1e-5,
    angle_tolerance: float = -1.0,
    type_basis: TypeBasis = "element",
    with_time_reversal: bool = True,
) -> dict[str, Any]:
    """Return a SeeK-path HPKOT reciprocal-space path."""
    seekpath = _require_seekpath()
    cell, _ = _spglib_cell(atoms, type_basis=type_basis)
    result = seekpath.get_path(
        cell,
        with_time_reversal=bool(with_time_reversal),
        symprec=float(symprec),
        angle_tolerance=float(angle_tolerance),
    )
    return {
        "status": "ok",
        "spacegroup_number": int(result["spacegroup_number"]),
        "spacegroup_international": str(result["spacegroup_international"]),
        "bravais_lattice": str(result["bravais_lattice"]),
        "has_inversion_symmetry": bool(result["has_inversion_symmetry"]),
        "augmented_path": bool(result["augmented_path"]),
        "point_coords": {
            str(name): np.asarray(value, dtype=float).tolist()
            for name, value in result["point_coords"].items()
        },
        "path": [[str(start), str(end)] for start, end in result["path"]],
        "primitive_lattice": np.asarray(
            result["primitive_lattice"], dtype=float
        ).tolist(),
        "reciprocal_primitive_lattice": np.asarray(
            result["reciprocal_primitive_lattice"], dtype=float
        ).tolist(),
        "primitive_positions": np.asarray(
            result["primitive_positions"], dtype=float
        ).tolist(),
        "primitive_types": np.asarray(result["primitive_types"], dtype=int).tolist(),
        "volume_original_wrt_prim": float(result["volume_original_wrt_prim"]),
    }


__all__ = [
    "SymmetryDependencyError",
    "analyze_symmetry",
    "high_symmetry_path",
    "symmetry_tolerance_scan",
    "transform_by_symmetry",
]
