"""Validated scalar-to-radius mapping shared by project and export paths."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
from typing import Any

import numpy as np

from .atom_scalars import atom_scalar_values


DEFAULT_ATOM_RADIUS_MAPPING: dict[str, Any] = {
    "enabled": False,
    "field": "",
    "valueTransform": "identity",
    "rangeMode": "current",
    "min": 0.0,
    "max": 1.0,
    "minMultiplier": 0.25,
    "maxMultiplier": 1.25,
    "exponent": 1.0,
    "scope": "all",
    "indices": [],
}


def _finite(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def normalize_atom_radius_mapping(value: Any, *, strict: bool = False) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    indices: list[int] = []
    for raw_index in source.get("indices", []) if isinstance(source.get("indices"), list) else []:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if index >= 0 and index not in indices:
            indices.append(index)
    normalized = {
        "enabled": source.get("enabled") is True,
        "field": str(source.get("field", "")) if isinstance(source.get("field", ""), str) else "",
        "valueTransform": "absolute" if source.get("valueTransform") == "absolute" else "identity",
        "rangeMode": source.get("rangeMode")
        if isinstance(source.get("rangeMode"), str)
        and source.get("rangeMode") in {"current", "trajectory", "manual"}
        else "current",
        "min": _finite(source.get("min"), 0.0),
        "max": _finite(source.get("max"), 1.0),
        "minMultiplier": _finite(source.get("minMultiplier"), 0.25),
        "maxMultiplier": _finite(source.get("maxMultiplier"), 1.25),
        "exponent": _finite(source.get("exponent"), 1.0),
        "scope": "indices" if source.get("scope") == "indices" else "all",
        "indices": sorted(indices),
    }
    errors = []
    if "enabled" in source and not isinstance(source["enabled"], bool):
        errors.append("enabled must be a boolean.")
    if "field" in source and not isinstance(source["field"], str):
        errors.append("field must be a string.")
    if "valueTransform" in source and (
        not isinstance(source["valueTransform"], str)
        or source["valueTransform"] not in {"identity", "absolute"}
    ):
        errors.append("valueTransform must be identity or absolute.")
    if "rangeMode" in source and (
        not isinstance(source["rangeMode"], str)
        or source["rangeMode"] not in {"current", "trajectory", "manual"}
    ):
        errors.append("rangeMode must be current, trajectory or manual.")
    if "scope" in source and (
        not isinstance(source["scope"], str)
        or source["scope"] not in {"all", "indices"}
    ):
        errors.append("scope must be all or indices.")
    for key in ("min", "max", "minMultiplier", "maxMultiplier", "exponent"):
        if key in source and (source[key] is None or source[key] == "" or
                             isinstance(source[key], bool) or
                             not math.isfinite(_finite(source[key], math.nan))):
            errors.append(f"{key} must be a finite number.")
    if "indices" in source and (not isinstance(source["indices"], list) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in source["indices"]
    )):
        errors.append("Frozen radius indices must be nonnegative integers.")
    if normalized["max"] <= normalized["min"]:
        errors.append("Maximum must be greater than minimum.")
    if not 0 <= normalized["minMultiplier"] <= 4:
        errors.append("Minimum multiplier must be between 0 and 4.")
    if not 0 <= normalized["maxMultiplier"] <= 4:
        errors.append("Maximum multiplier must be between 0 and 4.")
    if normalized["maxMultiplier"] < normalized["minMultiplier"]:
        errors.append("Maximum multiplier must not be smaller than minimum multiplier.")
    if not 0.1 <= normalized["exponent"] <= 5:
        errors.append("Exponent must be between 0.1 and 5.")
    if normalized["enabled"] and not normalized["field"]:
        errors.append("Choose a per-atom property.")
    if strict and errors:
        raise ValueError(errors[0])
    if errors:
        return dict(DEFAULT_ATOM_RADIUS_MAPPING)
    return normalized


def fit_atom_radius_range(
    values: Iterable[float],
    mapping: Mapping[str, Any],
    indices: Iterable[int] | None = None,
) -> dict[str, float | int]:
    array = np.asarray(list(values), dtype=np.float64)
    selected = np.ones(len(array), dtype=bool)
    if indices is not None:
        selected[:] = False
        for raw_index in indices:
            index = int(raw_index)
            if 0 <= index < len(array):
                selected[index] = True
    transformed = np.abs(array) if mapping.get("valueTransform") == "absolute" else array
    finite = transformed[selected & np.isfinite(transformed)]
    if not finite.size:
        raise ValueError("The selected property has no finite values.")
    minimum = float(np.min(finite))
    maximum = float(np.max(finite))
    if minimum == maximum:
        padding = max(1e-12, abs(minimum) * 1e-6)
        minimum -= padding
        maximum += padding
    return {"minimum": minimum, "maximum": maximum, "finiteValues": int(finite.size)}


def atom_radius_factors(values: Iterable[float], mapping: Mapping[str, Any]) -> np.ndarray:
    normalized = normalize_atom_radius_mapping(mapping, strict=True)
    array = np.asarray(list(values), dtype=np.float64)
    factors = np.ones(len(array), dtype=np.float64)
    if not normalized["enabled"] or not normalized["field"]:
        return factors
    selected = np.ones(len(array), dtype=bool)
    if normalized["scope"] == "indices":
        selected[:] = False
        for index in normalized["indices"]:
            if 0 <= index < len(array):
                selected[index] = True
    transformed = np.abs(array) if normalized["valueTransform"] == "absolute" else array
    finite = selected & np.isfinite(transformed)
    t = np.clip(
        (transformed[finite] - normalized["min"]) / (normalized["max"] - normalized["min"]),
        0.0,
        1.0,
    )
    factors[finite] = normalized["minMultiplier"] + (
        normalized["maxMultiplier"] - normalized["minMultiplier"]
    ) * np.power(t, normalized["exponent"])
    return factors


def atom_radius_factors_for_atoms(atoms, mapping: Mapping[str, Any]) -> np.ndarray:
    normalized = normalize_atom_radius_mapping(mapping, strict=True)
    if not normalized["enabled"] or not normalized["field"]:
        return np.ones(len(atoms), dtype=np.float64)
    try:
        values = atom_scalar_values(atoms, normalized["field"])
    except ValueError:
        return np.ones(len(atoms), dtype=np.float64)
    return atom_radius_factors(values, normalized)
