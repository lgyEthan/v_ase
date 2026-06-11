"""Input helpers for structure files that ASE cannot parse directly."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
from ase import Atoms
from ase.data import atomic_masses, atomic_numbers, chemical_symbols
from ase.io.extxyz import key_val_str_to_dict
from ase.io.formats import string2index

ATOM_TYPE_ARRAY = "v_ase_atom_type"


def _integer_type_suffix(label: object) -> str | None:
    text = str(label).strip()
    if re.fullmatch(r"[+-]?\d+", text):
        return str(int(text))
    if isinstance(label, (float, np.floating)) and float(label).is_integer():
        return str(int(label))
    return None


def _guess_symbol_from_mass(mass: object | None) -> str | None:
    if mass is None:
        return None
    try:
        value = float(mass)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value) or value <= 0:
        return None
    candidates = []
    for number in range(1, len(chemical_symbols)):
        symbol = chemical_symbols[number]
        reference = float(atomic_masses[number])
        if not symbol or not np.isfinite(reference) or reference <= 0:
            continue
        candidates.append((abs(reference - value), symbol, reference))
    if not candidates:
        return None
    delta, symbol, reference = min(candidates, key=lambda item: item[0])
    tolerance = max(0.35, reference * 0.04)
    return symbol if delta <= tolerance else None


def normalize_atom_type_label(label: object) -> str:
    text = str(label).strip()
    suffix = _integer_type_suffix(label)
    if suffix is not None:
        return f"H_{suffix}"
    return text


def display_label_for_atom_type(label: object, mass: object | None = None) -> str:
    """Return a visible v_ase atom type label for raw file metadata."""
    suffix = _integer_type_suffix(label)
    if suffix is not None:
        return f"{_guess_symbol_from_mass(mass) or 'H'}_{suffix}"
    return normalize_atom_type_label(label)


def base_symbol_for_atom_type(label: object, mass: object | None = None) -> str:
    """Return an ASE-valid symbol for a possibly custom atom type label."""
    text = normalize_atom_type_label(label)
    if text in atomic_numbers:
        return text
    prefix = text.split("_", 1)[0]
    if prefix in atomic_numbers:
        return prefix
    match = re.match(r"^([A-Z][a-z]?)", text)
    if match and match.group(1) in atomic_numbers:
        return match.group(1)
    return _guess_symbol_from_mass(mass) or "H"


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


def _lammps_position(row: dict[str, str], cell: np.ndarray) -> list[float]:
    if all(key in row for key in ("x", "y", "z")):
        return [float(row["x"]), float(row["y"]), float(row["z"])]
    if all(key in row for key in ("xu", "yu", "zu")):
        return [float(row["xu"]), float(row["yu"]), float(row["zu"])]
    if all(key in row for key in ("xs", "ys", "zs")):
        scaled = np.asarray([float(row["xs"]), float(row["ys"]), float(row["zs"])], dtype=float)
        return (scaled @ cell).tolist()
    if all(key in row for key in ("xsu", "ysu", "zsu")):
        scaled = np.asarray([float(row["xsu"]), float(row["ysu"]), float(row["zsu"])], dtype=float)
        return (scaled @ cell).tolist()
    raise ValueError("LAMMPS dump must contain x/y/z, xu/yu/zu, xs/ys/zs, or xsu/ysu/zsu columns.")


def _parse_lammps_box(bounds_header: str, lines: list[str]) -> tuple[np.ndarray, list[bool]]:
    tokens = bounds_header.split()[3:]
    pbc = [token.startswith("p") for token in tokens[:3]]
    bounds = [[float(v) for v in line.split()[:2]] for line in lines[:3]]
    lengths = [hi - lo for lo, hi in bounds]
    cell = np.diag(lengths)
    return cell, pbc if len(pbc) == 3 else [True, True, True]


def read_custom_lammps_dump(path: str | Path, index: str | int | slice | None = ":") -> list[Atoms]:
    """Read LAMMPS text dumps while preserving integer atom types as v_ase labels."""
    frames: list[Atoms] = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    cursor = 0
    while cursor < len(lines):
        if not lines[cursor].startswith("ITEM: TIMESTEP"):
            cursor += 1
            continue
        cursor += 1
        timestep = int(float(lines[cursor].strip()))
        cursor += 1
        if cursor >= len(lines) or not lines[cursor].startswith("ITEM: NUMBER OF ATOMS"):
            raise ValueError("LAMMPS dump is missing NUMBER OF ATOMS after TIMESTEP.")
        cursor += 1
        natoms = int(lines[cursor].strip())
        cursor += 1
        if cursor >= len(lines) or not lines[cursor].startswith("ITEM: BOX BOUNDS"):
            raise ValueError("LAMMPS dump is missing BOX BOUNDS.")
        bounds_header = lines[cursor]
        cursor += 1
        cell, pbc = _parse_lammps_box(bounds_header, lines[cursor:cursor + 3])
        cursor += 3
        if cursor >= len(lines) or not lines[cursor].startswith("ITEM: ATOMS"):
            raise ValueError("LAMMPS dump is missing ATOMS columns.")
        columns = lines[cursor].split()[2:]
        cursor += 1

        rows = []
        for _ in range(natoms):
            values = lines[cursor].split()
            cursor += 1
            rows.append(dict(zip(columns, values)))
        if "id" in columns:
            rows.sort(key=lambda row: int(float(row["id"])))

        raw_types = [row.get("type") or row.get("element") or row.get("mol") or "1" for row in rows]
        raw_masses = [row.get("mass") for row in rows]
        masses = raw_masses if any(value is not None for value in raw_masses) else [None] * len(rows)
        labels = [display_label_for_atom_type(raw_type, mass) for raw_type, mass in zip(raw_types, masses)]
        symbols = [base_symbol_for_atom_type(label, mass) for label, mass in zip(labels, masses)]
        positions = [_lammps_position(row, cell) for row in rows]
        atoms = Atoms(symbols=symbols, positions=np.asarray(positions, dtype=float), cell=cell, pbc=pbc)
        atoms.info["timestep"] = timestep
        set_atom_type_labels(atoms, labels)
        if any(value is not None for value in raw_masses):
            atoms.set_masses([float(value) if value is not None else atomic_masses[atomic_numbers[symbol]]
                              for value, symbol in zip(raw_masses, symbols)])
        if "id" in columns:
            atoms.set_array("lammps_id", np.asarray([int(float(row["id"])) for row in rows], dtype=int))
        if "mol" in columns:
            atoms.set_array("mol", np.asarray([int(float(row["mol"])) for row in rows], dtype=int))
        if "q" in columns:
            atoms.set_initial_charges(np.asarray([float(row["q"]) for row in rows], dtype=float))
        if all(key in columns for key in ("fx", "fy", "fz")):
            atoms.set_array("forces", np.asarray([[float(row["fx"]), float(row["fy"]), float(row["fz"])] for row in rows], dtype=float))
        frames.append(atoms)
    if not frames:
        raise ValueError("No frames found in LAMMPS dump.")
    return _select_frames(frames, index)


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

            positions = columns.get("pos", columns.get("positions"))
            raw_labels = (
                columns.get("species")
                or columns.get("symbols")
                or columns.get("atom_type")
                or columns.get("type")
                or columns.get("element")
                or []
            )
            if not raw_labels and positions is not None:
                raw_labels = ["H"] * len(positions)
            raw_masses = columns.get("mass") or columns.get("masses") or []
            masses = raw_masses if len(raw_masses) == len(raw_labels) else [None] * len(raw_labels)
            labels = [display_label_for_atom_type(value, mass) for value, mass in zip(raw_labels, masses)]
            symbols = [base_symbol_for_atom_type(label, mass) for label, mass in zip(labels, masses)]
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
                if name in {"species", "symbols", "atom_type", "type", "element", "pos", "positions"}:
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
