"""Input helpers for structure files that ASE cannot parse directly."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
from ase import Atoms
from ase.data import atomic_numbers
from ase.io.extxyz import key_val_str_to_dict
from ase.io.formats import string2index

ATOM_TYPE_ARRAY = "v_ase_atom_type"


def normalize_atom_type_label(label: object) -> str:
    return str(label).strip()


def base_symbol_for_atom_type(label: object) -> str:
    """Return an ASE-valid symbol for a possibly custom atom type label."""
    text = normalize_atom_type_label(label)
    if text in atomic_numbers:
        return text
    match = re.match(r"^([A-Z][a-z]?)", text)
    if match and match.group(1) in atomic_numbers:
        return match.group(1)
    return "X"


def atom_type_labels(atoms: Atoms) -> list[str]:
    labels = atoms.arrays.get(ATOM_TYPE_ARRAY)
    if labels is None or len(labels) != len(atoms):
        return atoms.get_chemical_symbols()
    return [normalize_atom_type_label(label) for label in labels]


def set_atom_type_labels(atoms: Atoms, labels: Iterable[object]) -> None:
    normalized = [normalize_atom_type_label(label) for label in labels]
    atoms.set_array(ATOM_TYPE_ARRAY, np.asarray(normalized, dtype="U64"))


def _parse_properties(properties: str) -> list[tuple[str, str, int]]:
    tokens = properties.split(":")
    parsed = []
    i = 0
    while i + 2 < len(tokens):
        name = tokens[i]
        kind = tokens[i + 1]
        cols = int(tokens[i + 2])
        parsed.append((name, kind, cols))
        i += 3
    return parsed


def _convert_values(values: list[str], kind: str, cols: int):
    if kind == "R":
        converted = [float(v) for v in values]
    elif kind == "I":
        converted = [int(v) for v in values]
    elif kind == "L":
        converted = [v.lower() in {"t", "true", "1"} for v in values]
    else:
        converted = values
    return converted[0] if cols == 1 else converted


def _select_frames(frames: list[Atoms], index: str | int | slice | None) -> list[Atoms]:
    parsed = string2index(":") if index is None else string2index(index) if isinstance(index, str) else index
    if isinstance(parsed, slice):
        return frames[parsed]
    if isinstance(parsed, int):
        return [frames[parsed]]
    return frames


def read_custom_extxyz(path: str | Path, index: str | int | slice | None = ":") -> list[Atoms]:
    """Read extended XYZ files with non-ASE atom type labels such as H_type5."""
    frames: list[Atoms] = []
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        while True:
            first = handle.readline()
            if not first:
                break
            if not first.strip():
                continue
            natoms = int(first.strip())
            comment = handle.readline()
            if not comment:
                break
            info = key_val_str_to_dict(comment.strip())
            properties = _parse_properties(info.get("Properties", "species:S:1:pos:R:3"))
            rows = [handle.readline().split() for _ in range(natoms)]

            columns: dict[str, list[object]] = {name: [] for name, _, _ in properties}
            for row in rows:
                cursor = 0
                for name, kind, cols in properties:
                    raw_values = row[cursor:cursor + cols]
                    cursor += cols
                    columns[name].append(_convert_values(raw_values, kind, cols))

            labels = [normalize_atom_type_label(v) for v in columns.get("species", columns.get("symbols", []))]
            symbols = [base_symbol_for_atom_type(label) for label in labels]
            positions = columns.get("pos", columns.get("positions"))
            atoms = Atoms(symbols=symbols, positions=np.asarray(positions, dtype=float))
            if labels:
                set_atom_type_labels(atoms, labels)

            lattice = info.get("Lattice")
            if lattice is not None:
                atoms.set_cell(np.asarray(lattice, dtype=float).reshape(3, 3))
                atoms.set_pbc(info.get("pbc", [True, True, True]))
            elif "pbc" in info:
                atoms.set_pbc(info["pbc"])

            for key, value in info.items():
                if key not in {"Properties", "Lattice", "pbc"}:
                    atoms.info[key] = value

            for name, values in columns.items():
                if name in {"species", "symbols", "pos", "positions"}:
                    continue
                array = np.asarray(values)
                if name in {"force", "forces"}:
                    atoms.set_array("forces", np.asarray(values, dtype=float))
                elif name in {"charge", "charges"}:
                    atoms.set_initial_charges(np.asarray(values, dtype=float))
                elif name in {"magmom", "magmoms"}:
                    atoms.set_initial_magnetic_moments(np.asarray(values, dtype=float))
                elif name in {"tag", "tags"}:
                    atoms.set_tags(np.asarray(values, dtype=int))
                else:
                    atoms.set_array(name, array)
            frames.append(atoms)
    return _select_frames(frames, index)

