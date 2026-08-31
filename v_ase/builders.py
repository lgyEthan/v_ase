"""Validated, cached structure generators backed by :mod:`ase.build`.

The GUI consumes the compact catalog in this module instead of probing ASE on
every control change.  ASE itself remains the final authority when a structure
is previewed or built, so a v_ase update does not silently diverge from the
installed ASE implementation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, Mapping, Sequence

import ase
import numpy as np
from ase import Atoms
from ase.build import bulk
from ase.data import chemical_symbols, reference_states
from ase.symbols import string2symbols


BULK_CATALOG_SCHEMA = "v_ase.ase-build.bulk.v1"
BULK_CELL_MODES = ("primitive", "orthorhombic", "cubic")


# These are the construction paths implemented by ase.build.bulk.  ASE also
# accepts a few names in its initial parser that have no downstream builder in
# current releases; exposing those as usable GUI choices would be misleading.
BULK_STRUCTURE_SPECS: Dict[str, Dict[str, Any]] = {
    "sc": {
        "label": "Simple cubic",
        "formula_atoms": 1,
        "formula_hint": "one element, for example Cu",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "fcc": {
        "label": "Face-centered cubic",
        "formula_atoms": 1,
        "formula_hint": "one element, for example Cu",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "bcc": {
        "label": "Body-centered cubic",
        "formula_atoms": 1,
        "formula_hint": "one element, for example Fe",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "bct": {
        "label": "Body-centered tetragonal",
        "formula_atoms": 1,
        "formula_hint": "one element, for example In",
        "cell_modes": ["primitive"],
        "parameters": ["a", "c", "basis"],
    },
    "hcp": {
        "label": "Hexagonal close-packed",
        "formula_atoms": 1,
        "formula_hint": "one element, for example Mg",
        "cell_modes": ["primitive", "orthorhombic"],
        "parameters": ["a", "c", "covera"],
    },
    "rhombohedral": {
        "label": "Rhombohedral",
        "formula_atoms": 1,
        "formula_hint": "one element, for example As",
        "cell_modes": ["primitive"],
        "parameters": ["a", "alpha", "basis"],
    },
    "orthorhombic": {
        "label": "Orthorhombic",
        "formula_atoms": 1,
        "formula_hint": "one element, for example U",
        "cell_modes": ["primitive"],
        "parameters": ["a", "b", "c"],
    },
    "diamond": {
        "label": "Diamond",
        "formula_atoms": 1,
        "formula_hint": "one element, for example C",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "zincblende": {
        "label": "Zincblende",
        "formula_atoms": 2,
        "formula_hint": "1:1 binary formula, for example GaAs",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "rocksalt": {
        "label": "Rocksalt",
        "formula_atoms": 2,
        "formula_hint": "1:1 binary formula, for example CuO",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "cesiumchloride": {
        "label": "Cesium chloride",
        "formula_atoms": 2,
        "formula_hint": "1:1 binary formula, for example CsCl",
        "cell_modes": ["primitive", "orthorhombic", "cubic"],
        "parameters": ["a"],
    },
    "fluorite": {
        "label": "Fluorite",
        "formula_atoms": 3,
        "formula_hint": "1:2 formula, for example CaF2",
        "cell_modes": ["primitive", "cubic"],
        "parameters": ["a"],
    },
    "wurtzite": {
        "label": "Wurtzite",
        "formula_atoms": 2,
        "formula_hint": "1:1 binary formula, for example ZnO",
        "cell_modes": ["primitive", "orthorhombic"],
        "parameters": ["a", "c", "covera", "u"],
    },
}


BULK_EXAMPLES = (
    {"formula": "Cu", "crystalstructure": None, "cell_mode": "cubic"},
    {"formula": "Fe", "crystalstructure": None, "cell_mode": "cubic"},
    {"formula": "Mg", "crystalstructure": None, "cell_mode": "orthorhombic"},
    {"formula": "CuO", "crystalstructure": "rocksalt", "cell_mode": "cubic", "a": 4.27},
    {"formula": "GaAs", "crystalstructure": "zincblende", "cell_mode": "cubic", "a": 5.65},
    {"formula": "ZnO", "crystalstructure": "wurtzite", "cell_mode": "primitive", "a": 3.25},
    {"formula": "CaF2", "crystalstructure": "fluorite", "cell_mode": "cubic", "a": 5.46},
)


@dataclass(frozen=True)
class BulkBuildError(ValueError):
    """Actionable validation error returned to both GUI and AI clients."""

    message: str
    missing_fields: tuple[str, ...] = ()
    field: str | None = None
    code: str = "invalid-bulk-request"

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> Dict[str, Any]:
        return {
            "valid": False,
            "code": self.code,
            "message": self.message,
            "missing_fields": list(self.missing_fields),
            "field": self.field,
        }


def _reference_for_symbol(symbol: str) -> Mapping[str, Any]:
    try:
        index = chemical_symbols.index(symbol)
    except ValueError:
        return {}
    reference = reference_states[index]
    return reference or {}


def _finite_optional_float(payload: Mapping[str, Any], key: str) -> float | None:
    raw = payload.get(key)
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raise BulkBuildError(f"{key} must be a finite number.", field=key)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise BulkBuildError(f"{key} must be a finite number.", field=key) from exc
    if not math.isfinite(value):
        raise BulkBuildError(f"{key} must be a finite number.", field=key)
    return value


def _normalize_basis(raw: Any) -> list[list[float]] | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BulkBuildError(
                "basis must be JSON fractional coordinates such as [[0, 0, 0]].",
                field="basis",
            ) from exc
    try:
        basis = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise BulkBuildError(
            "basis must be an N x 3 array of fractional coordinates.",
            field="basis",
        ) from exc
    if basis.ndim != 2 or basis.shape[0] < 1 or basis.shape[1] != 3:
        raise BulkBuildError(
            "basis must be a non-empty N x 3 array of fractional coordinates.",
            field="basis",
        )
    if not np.all(np.isfinite(basis)):
        raise BulkBuildError("basis entries must be finite numbers.", field="basis")
    return basis.tolist()


def _formula_symbols(formula: str) -> list[str]:
    try:
        symbols = list(string2symbols(formula))
    except (KeyError, TypeError, ValueError) as exc:
        raise BulkBuildError(
            f"'{formula}' is not a valid chemical formula.",
            field="formula",
            code="invalid-formula",
        ) from exc
    if not symbols:
        raise BulkBuildError("Enter a chemical formula.", missing_fields=("formula",))
    return symbols


def _same_reference_structure(formula: str, structure: str) -> bool:
    symbols = _formula_symbols(formula)
    if len(symbols) != 1 or symbols[0] != formula:
        return False
    return _reference_for_symbol(formula).get("symmetry") == structure


def _missing_explicit_parameters(
    formula: str,
    structure: str,
    values: Mapping[str, Any],
) -> list[str]:
    reference = _reference_for_symbol(formula)
    same_reference = _same_reference_structure(formula, structure)
    missing: list[str] = []

    if values.get("a") is None and not (
        same_reference and reference.get("a") is not None
    ):
        missing.append("a")

    if structure == "bct":
        has_reference_c = same_reference and (
            reference.get("c/a") is not None or reference.get("c") is not None
        )
        if values.get("c") is None and not has_reference_c:
            missing.append("c")
    elif structure == "orthorhombic":
        has_reference_b = same_reference and (
            reference.get("b/a") is not None or reference.get("b") is not None
        )
        has_reference_c = same_reference and (
            reference.get("c/a") is not None or reference.get("c") is not None
        )
        if values.get("b") is None and not has_reference_b:
            missing.append("b")
        if values.get("c") is None and not has_reference_c:
            missing.append("c")
    elif structure == "rhombohedral":
        if values.get("alpha") is None and not (
            same_reference and reference.get("alpha") is not None
        ):
            missing.append("alpha")
        if values.get("basis") is None and not (
            same_reference and reference.get("basis_x") is not None
        ):
            missing.append("basis")
    return missing


def _missing_message(fields: Iterable[str], *, formula: str) -> str:
    ordered = list(dict.fromkeys(fields))
    readable = {
        "formula": "chemical formula",
        "crystalstructure": "crystal structure",
        "a": "lattice parameter a",
        "b": "lattice parameter b",
        "c": "lattice parameter c",
        "alpha": "rhombohedral angle alpha",
        "basis": "fractional atomic basis",
    }
    names = [readable.get(field, field) for field in ordered]
    if len(names) == 1:
        joined = names[0]
    else:
        joined = ", ".join(names[:-1]) + f" and {names[-1]}"
    return f"{formula or 'This material'} requires {joined}."


def normalize_bulk_request(payload: Mapping[str, Any]) -> Dict[str, Any]:
    formula = str(payload.get("formula") or payload.get("name") or "").strip()
    if not formula:
        raise BulkBuildError("Enter a chemical formula.", missing_fields=("formula",))
    formula_symbols = _formula_symbols(formula)

    raw_structure = payload.get("crystalstructure", payload.get("crystalStructure"))
    structure = str(raw_structure or "").strip().lower() or None
    if structure == "auto":
        structure = None
    if structure is not None and structure not in BULK_STRUCTURE_SPECS:
        choices = ", ".join(BULK_STRUCTURE_SPECS)
        raise BulkBuildError(
            f"Unknown crystal structure '{structure}'. Choose one of: {choices}.",
            field="crystalstructure",
            code="unknown-crystal-structure",
        )

    raw_mode = payload.get("cell_mode", payload.get("cellMode"))
    if raw_mode is None:
        cubic = bool(payload.get("cubic", False))
        orthorhombic = bool(payload.get("orthorhombic", False))
        if cubic and orthorhombic:
            raise BulkBuildError(
                "Choose either cubic or orthorhombic output, not both.",
                field="cell_mode",
            )
        cell_mode = "cubic" if cubic else "orthorhombic" if orthorhombic else "primitive"
    else:
        cell_mode = str(raw_mode).strip().lower()
    if cell_mode not in BULK_CELL_MODES:
        raise BulkBuildError(
            "cell_mode must be primitive, orthorhombic, or cubic.",
            field="cell_mode",
        )

    values = {
        key: _finite_optional_float(payload, key)
        for key in ("a", "b", "c", "alpha", "covera", "u")
    }
    values["basis"] = _normalize_basis(payload.get("basis"))
    for key in ("a", "b", "c", "covera"):
        value = values.get(key)
        if value is not None and value <= 0:
            raise BulkBuildError(f"{key} must be greater than zero.", field=key)
    alpha = values.get("alpha")
    if alpha is not None and not 0 < alpha < 180:
        raise BulkBuildError("alpha must be between 0 and 180 degrees.", field="alpha")
    u = values.get("u")
    if u is not None and not 0 <= u <= 1:
        raise BulkBuildError("u must be between 0 and 1.", field="u")
    if values.get("c") is not None and values.get("covera") is not None:
        raise BulkBuildError(
            "Specify either c or c/a, not both.",
            field="covera",
            code="conflicting-parameters",
        )

    if structure is None:
        if len(formula_symbols) != 1 or formula_symbols[0] != formula:
            missing = ("crystalstructure", "a")
            raise BulkBuildError(
                _missing_message(missing, formula=formula),
                missing_fields=missing,
                code="missing-reference-data",
            )
        reference = _reference_for_symbol(formula)
        structure = str(reference.get("symmetry") or "") or None
        if structure not in BULK_STRUCTURE_SPECS:
            missing = ("crystalstructure", "a")
            raise BulkBuildError(
                _missing_message(missing, formula=formula),
                missing_fields=missing,
                code="missing-reference-data",
            )
        effective_structure = structure
        requested_structure = None
    else:
        effective_structure = structure
        requested_structure = structure

    spec = BULK_STRUCTURE_SPECS[effective_structure]
    expected_atoms = int(spec["formula_atoms"])
    if len(formula_symbols) != expected_atoms:
        raise BulkBuildError(
            f"{effective_structure} expects {spec['formula_hint']}; "
            f"'{formula}' expands to {len(formula_symbols)} atom symbol(s).",
            field="formula",
            code="formula-prototype-mismatch",
        )
    if cell_mode not in spec["cell_modes"]:
        supported = ", ".join(spec["cell_modes"])
        raise BulkBuildError(
            f"ASE cannot construct a {cell_mode} cell for {effective_structure}. "
            f"Available cell shapes: {supported}.",
            field="cell_mode",
            code="incompatible-cell-shape",
        )

    missing = _missing_explicit_parameters(
        formula,
        effective_structure,
        values,
    )
    if missing:
        raise BulkBuildError(
            _missing_message(missing, formula=formula),
            missing_fields=tuple(missing),
            code="missing-bulk-parameters",
        )

    return {
        "formula": formula,
        "crystalstructure": requested_structure,
        "effective_crystalstructure": effective_structure,
        "cell_mode": cell_mode,
        **values,
    }


def build_bulk_atoms(payload: Mapping[str, Any]) -> tuple[Atoms, Dict[str, Any]]:
    """Validate a request and construct one periodic ASE ``Atoms`` object."""

    normalized = normalize_bulk_request(payload)
    kwargs = {
        key: normalized.get(key)
        for key in ("a", "b", "c", "alpha", "covera", "u", "basis")
        if normalized.get(key) is not None
    }
    if normalized["crystalstructure"] is not None:
        kwargs["crystalstructure"] = normalized["crystalstructure"]
    kwargs["orthorhombic"] = normalized["cell_mode"] == "orthorhombic"
    kwargs["cubic"] = normalized["cell_mode"] == "cubic"
    try:
        atoms = bulk(normalized["formula"], **kwargs)
    except (AssertionError, KeyError, RuntimeError, TypeError, ValueError) as exc:
        message = str(exc).strip() or type(exc).__name__
        raise BulkBuildError(
            f"ASE could not build this crystal: {message}",
            code="ase-build-failed",
        ) from exc

    cell = np.asarray(atoms.cell.array, dtype=float)
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise BulkBuildError(
            "ASE returned a non-finite unit cell. Check all required lattice parameters.",
            code="invalid-generated-cell",
        )
    if abs(float(np.linalg.det(cell))) <= 1e-12:
        raise BulkBuildError(
            "ASE returned a zero-volume unit cell. Check all required lattice parameters.",
            code="invalid-generated-cell",
        )
    atoms.set_pbc(True)
    return atoms, normalized


def bulk_preview_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    atoms, normalized = build_bulk_atoms(payload)
    lengths_angles = np.asarray(atoms.cell.cellpar(), dtype=float)
    return {
        "valid": True,
        "schema": BULK_CATALOG_SCHEMA,
        "generator": "ase.build.bulk",
        "formula": normalized["formula"],
        "crystalstructure": normalized["effective_crystalstructure"],
        "cell_mode": normalized["cell_mode"],
        "atom_count": len(atoms),
        "chemical_formula": atoms.get_chemical_formula(),
        "chemical_symbols": atoms.get_chemical_symbols(),
        "cell": np.asarray(atoms.cell.array, dtype=float).tolist(),
        "cell_parameters": {
            "a": float(lengths_angles[0]),
            "b": float(lengths_angles[1]),
            "c": float(lengths_angles[2]),
            "alpha": float(lengths_angles[3]),
            "beta": float(lengths_angles[4]),
            "gamma": float(lengths_angles[5]),
        },
        "pbc": [True, True, True],
        "arguments": {
            key: normalized.get(key)
            for key in (
                "formula", "crystalstructure", "cell_mode", "a", "b", "c",
                "alpha", "covera", "u", "basis",
            )
        },
    }


def _is_cubic_cell(atoms: Atoms) -> bool:
    parameters = np.asarray(atoms.cell.cellpar(), dtype=float)
    return bool(
        np.allclose(parameters[:3], parameters[0], rtol=1e-10, atol=1e-10)
        and np.allclose(parameters[3:], 90.0, rtol=0, atol=1e-8)
    )


@lru_cache(maxsize=1)
def bulk_builder_catalog() -> Dict[str, Any]:
    """Return the small immutable compatibility catalog used by the GUI."""

    references = []
    for symbol in chemical_symbols[1:]:
        reference = _reference_for_symbol(symbol)
        structure = str(reference.get("symmetry") or "")
        if structure not in BULK_STRUCTURE_SPECS:
            continue
        compatible_modes = []
        atom_counts: Dict[str, int] = {}
        for mode in BULK_STRUCTURE_SPECS[structure]["cell_modes"]:
            try:
                atoms, _ = build_bulk_atoms({
                    "formula": symbol,
                    "cell_mode": mode,
                })
            except BulkBuildError:
                continue
            if mode == "cubic" and not _is_cubic_cell(atoms):
                continue
            compatible_modes.append(mode)
            atom_counts[mode] = len(atoms)
        if not compatible_modes:
            continue
        references.append({
            "formula": symbol,
            "element": symbol,
            "crystalstructure": structure,
            "a": (
                float(reference["a"])
                if reference.get("a") is not None
                else None
            ),
            "compatible_cell_modes": compatible_modes,
            "atom_counts": atom_counts,
        })

    structures = []
    for identifier, spec in BULK_STRUCTURE_SPECS.items():
        structures.append({"id": identifier, **spec})
    return {
        "schema": BULK_CATALOG_SCHEMA,
        "generator": "ase.build.bulk",
        "ase_version": ase.__version__,
        "cell_modes": [
            {
                "id": "primitive",
                "label": "Native / primitive",
                "argument": "orthorhombic=False, cubic=False",
            },
            {
                "id": "orthorhombic",
                "label": "Orthorhombic",
                "argument": "orthorhombic=True",
            },
            {
                "id": "cubic",
                "label": "Cubic",
                "argument": "cubic=True",
            },
        ],
        "arguments": [
            {"id": "formula", "label": "Formula", "type": "chemical-formula", "required": True},
            {"id": "crystalstructure", "label": "Crystal structure", "type": "enum", "required": False},
            {"id": "a", "label": "a / Å", "type": "positive-number", "required": "conditional"},
            {"id": "b", "label": "b / Å", "type": "positive-number", "required": "conditional"},
            {"id": "c", "label": "c / Å", "type": "positive-number", "required": "conditional"},
            {"id": "alpha", "label": "alpha / degree", "type": "number", "required": "conditional"},
            {"id": "covera", "label": "c/a", "type": "positive-number", "required": False},
            {"id": "u", "label": "u", "type": "number", "required": False},
            {"id": "orthorhombic", "label": "Orthorhombic cell", "type": "boolean", "required": False},
            {"id": "cubic", "label": "Cubic cell", "type": "boolean", "required": False},
            {"id": "basis", "label": "Fractional basis", "type": "Nx3-array", "required": "conditional"},
        ],
        "structures": structures,
        "reference_materials": references,
        "elements": list(chemical_symbols[1:]),
        "examples": [dict(item) for item in BULK_EXAMPLES],
        "notes": [
            "Reference materials use ASE lattice defaults only when available.",
            "Custom compounds require an explicit prototype and lattice parameter a.",
            "c and c/a are mutually exclusive.",
        ],
    }
