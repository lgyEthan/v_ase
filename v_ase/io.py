"""Input helpers for structure files that ASE cannot parse directly."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
from ase import Atoms
from ase.data import atomic_masses, atomic_numbers, chemical_symbols
from ase.io.extxyz import key_val_str_to_dict
from ase.io.formats import string2index
from ase.io.lammpsdata import read_lammps_data

ATOM_TYPE_ARRAY = "v_ase_atom_type"


@dataclass
class FastLammpsDumpTrajectory:
    """Offset-indexed LAMMPS dump reader for large viz-only trajectories."""

    path: str
    natoms: int
    columns: list[str]
    atom_offsets: list[int]
    timesteps: list[int]
    cells: np.ndarray
    pbc: np.ndarray
    position_columns: tuple[int, int, int]
    scaled_positions: bool = False
    template_atoms: Atoms | None = None
    id_column: int | None = None
    type_column: int | None = None
    mol_column: int | None = None
    charge_column: int | None = None
    force_columns: tuple[int, int, int] | None = None
    mass_column: int | None = None
    _id_order: np.ndarray | None = field(default=None, repr=False)
    _ids_are_sorted: bool = True

    @property
    def frame_count(self) -> int:
        return len(self.atom_offsets)

    def _read_numeric_table(self, frame_index: int) -> np.ndarray:
        if frame_index < 0 or frame_index >= self.frame_count:
            raise IndexError(f"Frame index {frame_index} is out of range")
        with open(self.path, "rb", buffering=1024 * 1024) as handle:
            handle.seek(self.atom_offsets[frame_index])
            block = b"".join(handle.readline() for _ in range(self.natoms))
        values = np.fromstring(block, sep=" ", dtype=np.float32)
        expected = self.natoms * len(self.columns)
        if values.size != expected:
            raise ValueError(
                f"Fast LAMMPS parser expected {expected} numeric values in frame {frame_index}, "
                f"got {values.size}."
            )
        table = values.reshape(self.natoms, len(self.columns))
        if self.id_column is not None:
            ids = table[:, self.id_column].astype(np.int64, copy=False)
            if self._id_order is None:
                self._ids_are_sorted = bool(np.all(ids[:-1] <= ids[1:]))
                if not self._ids_are_sorted:
                    order = np.argsort(ids, kind="stable")
                    table = table[order]
                    ids = table[:, self.id_column].astype(np.int64, copy=False)
                self._id_order = ids.copy()
            elif not self._ids_are_sorted or not np.array_equal(ids, self._id_order):
                order = np.argsort(ids, kind="stable")
                table = table[order]
                ids = table[:, self.id_column].astype(np.int64, copy=False)
                if not np.array_equal(ids, self._id_order):
                    raise ValueError("LAMMPS dump atom ids changed between frames; virtual trajectory cannot preserve atom identity.")
        return table

    def _positions_from_table(self, table: np.ndarray, frame_index: int) -> np.ndarray:
        raw = table[:, self.position_columns].astype(np.float32, copy=True)
        if self.scaled_positions:
            raw = raw @ self.cells[frame_index].astype(np.float32, copy=False)
        return raw

    def read_positions(self, frame_index: int) -> np.ndarray:
        return self._positions_from_table(self._read_numeric_table(frame_index), frame_index)

    def read_atoms(self, frame_index: int) -> Atoms:
        if self.template_atoms is None:
            raise ValueError("Fast LAMMPS trajectory has no template Atoms object.")
        atoms = self.template_atoms.copy()
        atoms.set_positions(self.read_positions(frame_index), apply_constraint=False)
        atoms.set_cell(self.cells[frame_index])
        atoms.set_pbc(self.pbc[frame_index])
        atoms.info["timestep"] = int(self.timesteps[frame_index])
        return atoms

    def build_template(self, frame_index: int = 0) -> Atoms:
        table = self._read_numeric_table(frame_index)
        labels: list[str]
        symbols: list[str]
        if self.type_column is not None:
            raw_types = [str(int(value)) for value in table[:, self.type_column]]
        else:
            raw_types = ["1"] * self.natoms
        if self.mass_column is not None:
            masses = [float(value) for value in table[:, self.mass_column]]
        else:
            masses = [None] * self.natoms
        labels = [display_label_for_atom_type(raw_type, mass) for raw_type, mass in zip(raw_types, masses)]
        symbols = [base_symbol_for_lammps_type(raw_type, mass) for raw_type, mass in zip(raw_types, masses)]
        positions = self._positions_from_table(table, frame_index)
        atoms = Atoms(symbols=symbols, positions=positions, cell=self.cells[frame_index], pbc=self.pbc[frame_index])
        atoms.info["timestep"] = int(self.timesteps[frame_index])
        set_atom_type_labels(atoms, labels)
        if self.id_column is not None:
            atoms.set_array("lammps_id", table[:, self.id_column].astype(np.int64))
        if self.mol_column is not None:
            atoms.set_array("mol", table[:, self.mol_column].astype(np.int64))
        if self.charge_column is not None:
            atoms.set_initial_charges(table[:, self.charge_column].astype(float))
        if self.force_columns is not None:
            atoms.set_array("forces", table[:, self.force_columns].astype(float))
        if self.mass_column is not None:
            atoms.set_masses(table[:, self.mass_column].astype(float))
        self.template_atoms = atoms.copy()
        return atoms


@dataclass
class FastLammpsDumpResult:
    atoms: Atoms
    trajectory: FastLammpsDumpTrajectory
    initial_frame: int = 0


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
        return suffix
    return text


def display_label_for_atom_type(label: object, mass: object | None = None) -> str:
    """Return a visible v_ase atom type label for raw file metadata."""
    suffix = _integer_type_suffix(label)
    if suffix is not None:
        return suffix
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


def base_symbol_for_lammps_type(label: object, mass: object | None = None) -> str:
    """Return a symbol for LAMMPS type ids, using valid integer ids as Z."""
    guessed = _guess_symbol_from_mass(mass)
    if guessed:
        return guessed
    suffix = _integer_type_suffix(label)
    if suffix is not None:
        number = int(suffix)
        if 1 <= number < len(chemical_symbols) and chemical_symbols[number]:
            return chemical_symbols[number]
    return base_symbol_for_atom_type(label, mass)


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


def _parse_lammps_box_bytes(bounds_header: bytes, lines: list[bytes]) -> tuple[np.ndarray, list[bool]]:
    return _parse_lammps_box(
        bounds_header.decode("utf-8", errors="replace"),
        [line.decode("utf-8", errors="replace") for line in lines],
    )


def _fast_lammps_position_columns(columns: list[str]) -> tuple[tuple[int, int, int], bool]:
    column_map = {name: idx for idx, name in enumerate(columns)}
    for names, scaled in (
        (("x", "y", "z"), False),
        (("xu", "yu", "zu"), False),
        (("xs", "ys", "zs"), True),
        (("xsu", "ysu", "zsu"), True),
    ):
        if all(name in column_map for name in names):
            return (column_map[names[0]], column_map[names[1]], column_map[names[2]]), scaled
    raise ValueError("LAMMPS dump must contain x/y/z, xu/yu/zu, xs/ys/zs, or xsu/ysu/zsu columns.")


def _fast_lammps_selected_initial_frame(index: str | int | slice | None, frame_count: int) -> int:
    parsed = string2index(":") if index is None else string2index(index) if isinstance(index, str) else index
    if isinstance(parsed, int):
        frame = parsed if parsed >= 0 else frame_count + parsed
        if frame < 0 or frame >= frame_count:
            raise IndexError(f"Frame index {parsed} is out of range")
        return frame
    if isinstance(parsed, slice):
        start = 0 if parsed.start is None else parsed.start
        frame = start if start >= 0 else frame_count + start
        return max(0, min(frame_count - 1, frame))
    return 0


def index_lammps_dump(path: str | Path) -> FastLammpsDumpTrajectory:
    """Build a compact frame-offset index for numeric LAMMPS text dumps."""
    path = Path(path)
    atom_offsets: list[int] = []
    timesteps: list[int] = []
    cells: list[np.ndarray] = []
    pbc_values: list[list[bool]] = []
    columns: list[str] | None = None
    natoms: int | None = None

    with path.open("rb", buffering=1024 * 1024) as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            if not line.startswith(b"ITEM: TIMESTEP"):
                continue
            timestep_line = handle.readline()
            if not timestep_line:
                break
            timestep = int(float(timestep_line.strip()))
            if not handle.readline().startswith(b"ITEM: NUMBER OF ATOMS"):
                raise ValueError("LAMMPS dump is missing NUMBER OF ATOMS after TIMESTEP.")
            frame_natoms = int(handle.readline().strip())
            bounds_header = handle.readline()
            if not bounds_header.startswith(b"ITEM: BOX BOUNDS"):
                raise ValueError("LAMMPS dump is missing BOX BOUNDS.")
            bounds_lines = [handle.readline(), handle.readline(), handle.readline()]
            cell, pbc = _parse_lammps_box_bytes(bounds_header, bounds_lines)
            atom_header = handle.readline()
            if not atom_header.startswith(b"ITEM: ATOMS"):
                raise ValueError("LAMMPS dump is missing ATOMS columns.")
            frame_columns = [token.decode("utf-8", errors="replace") for token in atom_header.split()[2:]]
            if "element" in frame_columns:
                raise ValueError("Fast LAMMPS parser supports numeric dump columns; element-string dumps use the safe parser.")
            if natoms is None:
                natoms = frame_natoms
                columns = frame_columns
                _fast_lammps_position_columns(columns)
            elif frame_natoms != natoms:
                raise ValueError("Fast LAMMPS trajectory requires a constant atom count.")
            elif frame_columns != columns:
                raise ValueError("Fast LAMMPS trajectory requires constant ATOMS columns.")

            atom_offsets.append(handle.tell())
            timesteps.append(timestep)
            cells.append(cell)
            pbc_values.append(pbc)
            for _ in range(frame_natoms):
                handle.readline()

    if natoms is None or columns is None or not atom_offsets:
        raise ValueError("No frames found in LAMMPS dump.")

    column_map = {name: idx for idx, name in enumerate(columns)}
    position_columns, scaled = _fast_lammps_position_columns(columns)
    force_columns = None
    if all(name in column_map for name in ("fx", "fy", "fz")):
        force_columns = (column_map["fx"], column_map["fy"], column_map["fz"])
    return FastLammpsDumpTrajectory(
        path=str(path),
        natoms=natoms,
        columns=columns,
        atom_offsets=atom_offsets,
        timesteps=timesteps,
        cells=np.asarray(cells, dtype=float),
        pbc=np.asarray(pbc_values, dtype=bool),
        position_columns=position_columns,
        scaled_positions=scaled,
        id_column=column_map.get("id"),
        type_column=column_map.get("type"),
        mol_column=column_map.get("mol"),
        charge_column=column_map.get("q"),
        force_columns=force_columns,
        mass_column=column_map.get("mass"),
    )


def read_fast_lammps_dump(path: str | Path, index: str | int | slice | None = ":") -> FastLammpsDumpResult:
    """Read a large numeric LAMMPS dump as a first-frame Atoms plus virtual trajectory."""
    trajectory = index_lammps_dump(path)
    initial_frame = _fast_lammps_selected_initial_frame(index, trajectory.frame_count)
    trajectory.build_template(0)
    atoms = trajectory.read_atoms(initial_frame)
    return FastLammpsDumpResult(atoms=atoms, trajectory=trajectory, initial_frame=initial_frame)


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
        symbols = [base_symbol_for_lammps_type(raw_type, mass) for raw_type, mass in zip(raw_types, masses)]
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


def _read_lammps_data_with_style(path: Path, atom_style: str | None) -> Atoms:
    with path.open("r", encoding="utf-8") as handle:
        return read_lammps_data(handle, atom_style=atom_style, sort_by_id=True)


_LAMMPS_DATA_SECTIONS = {
    "masses",
    "atoms",
    "velocities",
    "bonds",
    "angles",
    "dihedrals",
    "impropers",
    "pair coeffs",
    "bond coeffs",
    "angle coeffs",
    "dihedral coeffs",
    "improper coeffs",
}


def _lammps_section_name(line: str) -> str | None:
    head = line.split("#", 1)[0].strip().lower()
    return head if head in _LAMMPS_DATA_SECTIONS else None


def _lammps_data_atom_style(line: str) -> str | None:
    if "#" not in line:
        return None
    style = line.split("#", 1)[1].strip().split()
    return style[0].lower() if style else None


def _is_integer_token(value: str) -> bool:
    return re.fullmatch(r"[+-]?\d+", value.strip()) is not None


def _parse_lammps_data_atom(tokens: list[str], atom_style: str | None) -> dict[str, object]:
    style = (atom_style or "").lower()
    if style == "atomic":
        atom_id, raw_type, xyz = tokens[0], tokens[1], tokens[2:5]
        mol = charge = None
    elif style == "charge":
        atom_id, raw_type, charge, xyz = tokens[0], tokens[1], tokens[2], tokens[3:6]
        mol = None
    elif style == "molecular":
        atom_id, mol, raw_type, xyz = tokens[0], tokens[1], tokens[2], tokens[3:6]
        charge = None
    elif style == "full":
        atom_id, mol, raw_type, charge, xyz = tokens[0], tokens[1], tokens[2], tokens[3], tokens[4:7]
    elif len(tokens) >= 7:
        atom_id = tokens[0]
        if _is_integer_token(tokens[2]) and not _is_integer_token(tokens[3]):
            mol, raw_type, charge, xyz = tokens[1], tokens[2], tokens[3], tokens[4:7]
        elif _is_integer_token(tokens[2]):
            mol, raw_type, charge, xyz = tokens[1], tokens[2], None, tokens[3:6]
        else:
            mol, raw_type, charge, xyz = None, tokens[1], tokens[2], tokens[3:6]
    elif len(tokens) >= 6:
        atom_id = tokens[0]
        if _is_integer_token(tokens[2]):
            mol, raw_type, charge, xyz = tokens[1], tokens[2], None, tokens[3:6]
        else:
            mol, raw_type, charge, xyz = None, tokens[1], tokens[2], tokens[3:6]
    elif len(tokens) >= 5:
        atom_id, raw_type, xyz = tokens[0], tokens[1], tokens[2:5]
        mol = charge = None
    else:
        raise ValueError(f"LAMMPS data atom row has too few fields: {' '.join(tokens)}")
    if len(xyz) < 3:
        raise ValueError(f"LAMMPS data atom row is missing coordinates: {' '.join(tokens)}")
    return {
        "id": int(float(atom_id)),
        "type": raw_type,
        "mol": int(float(mol)) if mol is not None else None,
        "charge": float(charge) if charge is not None else None,
        "position": [float(xyz[0]), float(xyz[1]), float(xyz[2])],
    }


def _read_lammps_data_minimal(path: Path) -> Atoms:
    lines = path.read_text(encoding="utf-8").splitlines()
    bounds: dict[str, tuple[float, float]] = {}
    tilts = [0.0, 0.0, 0.0]
    masses_by_type: dict[str, float] = {}
    atom_rows: list[dict[str, object]] = []
    atom_style: str | None = None

    cursor = 0
    while cursor < len(lines):
        stripped = lines[cursor].strip()
        clean = stripped.split("#", 1)[0].strip()
        tokens = clean.split()
        if len(tokens) >= 4 and tokens[2:4] in (["xlo", "xhi"], ["ylo", "yhi"], ["zlo", "zhi"]):
            bounds[tokens[2][0]] = (float(tokens[0]), float(tokens[1]))
        elif len(tokens) >= 6 and tokens[3:6] == ["xy", "xz", "yz"]:
            tilts = [float(tokens[0]), float(tokens[1]), float(tokens[2])]

        section = _lammps_section_name(stripped)
        if section == "masses":
            cursor += 1
            while cursor < len(lines) and _lammps_section_name(lines[cursor]) is None:
                mass_tokens = lines[cursor].split("#", 1)[0].split()
                if len(mass_tokens) >= 2:
                    masses_by_type[str(int(float(mass_tokens[0])))] = float(mass_tokens[1])
                cursor += 1
            continue
        if section == "atoms":
            atom_style = _lammps_data_atom_style(stripped)
            cursor += 1
            while cursor < len(lines) and _lammps_section_name(lines[cursor]) is None:
                atom_tokens = lines[cursor].split("#", 1)[0].split()
                if atom_tokens:
                    atom_rows.append(_parse_lammps_data_atom(atom_tokens, atom_style))
                cursor += 1
            continue
        cursor += 1

    if not atom_rows:
        raise ValueError("LAMMPS data file does not contain an Atoms section.")

    missing_bounds = [axis for axis in ("x", "y", "z") if axis not in bounds]
    if missing_bounds:
        raise ValueError(f"LAMMPS data file is missing box bounds for: {', '.join(missing_bounds)}")

    atom_rows.sort(key=lambda row: int(row["id"]))
    xy, xz, yz = tilts
    lx = bounds["x"][1] - bounds["x"][0]
    ly = bounds["y"][1] - bounds["y"][0]
    lz = bounds["z"][1] - bounds["z"][0]
    cell = np.asarray([[lx, 0.0, 0.0], [xy, ly, 0.0], [xz, yz, lz]], dtype=float)

    raw_types = [str(row["type"]) for row in atom_rows]
    masses = [masses_by_type.get(str(int(float(raw_type)))) if _integer_type_suffix(raw_type) is not None else None
              for raw_type in raw_types]
    labels = [display_label_for_atom_type(raw_type, mass) for raw_type, mass in zip(raw_types, masses)]
    symbols = [base_symbol_for_lammps_type(label, mass) for label, mass in zip(labels, masses)]
    positions = np.asarray([row["position"] for row in atom_rows], dtype=float)
    atoms = Atoms(symbols=symbols, positions=positions, cell=cell, pbc=[True, True, True])
    set_atom_type_labels(atoms, labels)
    atoms.set_array("lammps_id", np.asarray([row["id"] for row in atom_rows], dtype=int))
    atoms.set_array("type", np.asarray([int(float(raw_type)) if _integer_type_suffix(raw_type) is not None else raw_type
                                        for raw_type in raw_types]))
    if any(mass is not None for mass in masses):
        atoms.set_masses([
            float(mass) if mass is not None else atomic_masses[atomic_numbers[symbol]]
            for mass, symbol in zip(masses, symbols)
        ])
    if any(row["mol"] is not None for row in atom_rows):
        atoms.set_array("mol", np.asarray([row["mol"] or 0 for row in atom_rows], dtype=int))
    if any(row["charge"] is not None for row in atom_rows):
        atoms.set_initial_charges(np.asarray([row["charge"] or 0.0 for row in atom_rows], dtype=float))
    return atoms


def read_custom_lammps_data(
    path: str | Path,
    index: str | int | slice | None = ":",
    atom_style: str | None = None,
) -> list[Atoms]:
    """Read LAMMPS data files while keeping LAMMPS type ids as display labels.

    ASE treats bare integer LAMMPS types as atomic numbers when no Masses block is
    present. v_ase keeps the backend Atoms chemically valid by using mass-based
    symbol guesses when possible and falling back to H, while the visible label
    remains the raw LAMMPS type id such as "1" or "8".
    """
    path = Path(path)
    styles = [atom_style] if atom_style else [None, "full", "atomic", "charge", "molecular"]
    last_error: Exception | None = None
    atoms: Atoms | None = None
    for style in styles:
        try:
            atoms = _read_lammps_data_with_style(path, style)
            break
        except Exception as exc:  # pragma: no cover - exercised through fallback success cases
            last_error = exc
    if atoms is None:
        try:
            atoms = _read_lammps_data_minimal(path)
        except Exception:
            if last_error is not None:
                raise last_error
            raise

    raw_types = atoms.arrays.get("type")
    if raw_types is None or len(raw_types) != len(atoms):
        labels = atom_type_labels(atoms)
        masses = [None] * len(atoms)
    else:
        raw_masses = atoms.arrays.get("masses")
        masses = (
            [float(value) for value in raw_masses]
            if raw_masses is not None and len(raw_masses) == len(atoms)
            else [None] * len(atoms)
        )
        labels = [display_label_for_atom_type(raw_type, mass) for raw_type, mass in zip(raw_types, masses)]

    symbols = [base_symbol_for_lammps_type(label, mass) for label, mass in zip(labels, masses)]
    atoms.set_chemical_symbols(symbols)
    set_atom_type_labels(atoms, labels)
    return _select_frames([atoms], index)


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
