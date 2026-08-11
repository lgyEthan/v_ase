"""Lazy discovery and extraction of numeric per-atom scalar fields."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from urllib.parse import quote, unquote

import numpy as np


_EXCLUDED_ARRAYS = {"numbers", "positions", "forces", "v_ase_atom_type"}
_EXCLUDED_RESULTS = {"forces"}
_VECTOR_LABELS = ("x", "y", "z")


@dataclass(frozen=True)
class AtomScalarField:
    id: str
    label: str
    group: str
    source: str
    name: str
    reduction: str
    component: int | None = None
    unit: str = ""

    def payload(self) -> dict:
        return asdict(self)


def _encoded_field_id(source: str, name: str, reduction: str, component: int | None = None) -> str:
    parts = [source, quote(str(name), safe=""), reduction]
    if component is not None:
        parts.append(str(int(component)))
    return "::".join(parts)


def _field_unit(name: str, source: str) -> str:
    normalized = str(name).strip().lower()
    if source == "position":
        return "A"
    if normalized in {"forces", "force"}:
        return "eV/A"
    if normalized in {"charges", "charge", "initial_charges"}:
        return "e"
    if normalized in {
        "magmoms",
        "magmom",
        "magnetic_moments",
        "initial_magmoms",
    }:
        return "mu_B"
    if "energy" in normalized or normalized in {"energies", "free_energies"}:
        return "eV"
    if normalized in {"momenta", "momentum"}:
        return "amu A/fs"
    if normalized in {"masses", "mass"}:
        return "amu"
    return ""


def _numeric_per_atom_array(value, natoms: int) -> np.ndarray | None:
    try:
        array = np.asarray(value)
    except Exception:
        return None
    if array.ndim < 1 or array.shape[0] != natoms:
        return None
    if not (np.issubdtype(array.dtype, np.number) or np.issubdtype(array.dtype, np.bool_)):
        return None
    if np.iscomplexobj(array):
        return None
    return array


def _calculator_results(atoms) -> Mapping:
    results = getattr(getattr(atoms, "calc", None), "results", None)
    return results if isinstance(results, Mapping) else {}


def _force_array(atoms) -> np.ndarray | None:
    natoms = len(atoms)
    array = _numeric_per_atom_array(atoms.arrays.get("forces"), natoms)
    if array is None:
        array = _numeric_per_atom_array(_calculator_results(atoms).get("forces"), natoms)
    if array is None:
        return None
    flattened = np.asarray(array, dtype=np.float64).reshape(natoms, -1)
    return flattened if flattened.shape[1] else None


def atom_force_vectors(atoms) -> np.ndarray | None:
    """Return stored Cartesian per-atom forces without evaluating a calculator."""

    array = _force_array(atoms)
    if array is None or array.shape[1] < 3:
        return None
    return np.asarray(array[:, :3], dtype=np.float64)


def _array_field_descriptors(source: str, name: str, value, natoms: int) -> list[AtomScalarField]:
    array = _numeric_per_atom_array(value, natoms)
    if array is None:
        return []
    flattened = array.reshape(natoms, -1)
    width = int(flattened.shape[1])
    if width <= 0:
        return []

    group = "ASE arrays" if source == "array" else "Calculator results"
    source_label = "ASE array" if source == "array" else "Calculator"
    unit = _field_unit(name, source)
    if width == 1:
        return [
            AtomScalarField(
                id=_encoded_field_id(source, name, "scalar"),
                label=f"{name}",
                group=group,
                source=source,
                name=str(name),
                reduction="scalar",
                unit=unit,
            )
        ]

    fields = [
        AtomScalarField(
            id=_encoded_field_id(source, name, "norm"),
            label=f"{name} |norm|",
            group=group,
            source=source,
            name=str(name),
            reduction="norm",
            unit=unit,
        )
    ]
    if width <= 9:
        for component in range(width):
            suffix = _VECTOR_LABELS[component] if width == 3 else str(component)
            fields.append(
                AtomScalarField(
                    id=_encoded_field_id(source, name, "component", component),
                    label=f"{name} [{suffix}]",
                    group=group,
                    source=source,
                    name=str(name),
                    reduction="component",
                    component=component,
                    unit=unit,
                )
            )
    return fields


def atom_scalar_catalog(atoms) -> list[dict]:
    """Return colorable per-atom fields without evaluating a calculator."""
    fields = [
        AtomScalarField("position:x", "x coordinate", "Position", "position", "positions", "component", 0, "A"),
        AtomScalarField("position:y", "y coordinate", "Position", "position", "positions", "component", 1, "A"),
        AtomScalarField("position:z", "z coordinate", "Position", "position", "positions", "component", 2, "A"),
    ]
    if atom_force_vectors(atoms) is not None:
        fields.append(
            AtomScalarField("force:norm", "Force |norm|", "Calculator results", "force", "forces", "norm", None, "eV/A")
        )

    natoms = len(atoms)
    for name in sorted(atoms.arrays, key=str.casefold):
        if str(name) in _EXCLUDED_ARRAYS:
            continue
        fields.extend(_array_field_descriptors("array", str(name), atoms.arrays[name], natoms))
    for name in sorted(_calculator_results(atoms), key=str.casefold):
        if str(name) in _EXCLUDED_RESULTS:
            continue
        fields.extend(
            _array_field_descriptors("result", str(name), _calculator_results(atoms)[name], natoms)
        )
    return [field.payload() for field in fields]


def _parse_encoded_field(field_id: str) -> tuple[str, str, str, int | None]:
    parts = str(field_id).split("::")
    if len(parts) not in {3, 4} or parts[0] not in {"array", "result"}:
        raise ValueError(f"Unknown per-atom scalar field: {field_id}")
    component = None
    if len(parts) == 4:
        try:
            component = int(parts[3])
        except ValueError as exc:
            raise ValueError(f"Invalid component in per-atom scalar field: {field_id}") from exc
    return parts[0], unquote(parts[1]), parts[2], component


def atom_scalar_values(atoms, field_id: str) -> np.ndarray:
    """Extract one scalar per atom without triggering calculator evaluation."""
    natoms = len(atoms)
    if field_id in {"position:x", "position:y", "position:z"}:
        component = {"position:x": 0, "position:y": 1, "position:z": 2}[field_id]
        return np.asarray(atoms.positions[:, component], dtype=np.float64)
    if field_id == "force:norm":
        array = _force_array(atoms)
        if array is None:
            raise ValueError("Force values are not available for this frame.")
        return np.linalg.norm(array, axis=1)

    source, name, reduction, component = _parse_encoded_field(field_id)
    values = atoms.arrays.get(name) if source == "array" else _calculator_results(atoms).get(name)
    array = _numeric_per_atom_array(values, natoms)
    if array is None:
        raise ValueError(f"Per-atom field '{name}' is not available for this frame.")
    flattened = np.asarray(array, dtype=np.float64).reshape(natoms, -1)
    if reduction == "scalar":
        if flattened.shape[1] != 1:
            raise ValueError(f"Per-atom field '{name}' is not scalar.")
        result = flattened[:, 0]
    elif reduction == "norm":
        result = np.linalg.norm(flattened, axis=1)
    elif reduction == "component":
        if component is None or component < 0 or component >= flattened.shape[1]:
            raise ValueError(f"Component is out of range for per-atom field '{name}'.")
        result = flattened[:, component]
    else:
        raise ValueError(f"Unknown reduction '{reduction}' for per-atom field '{name}'.")
    return np.asarray(result, dtype=np.float64)
