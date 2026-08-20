"""Input helpers for structure files that ASE cannot parse directly."""

from __future__ import annotations

import mmap
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

import numpy as np
from ase import Atoms
from ase.data import atomic_masses, atomic_numbers, chemical_symbols
from ase.io import read
from ase.io.extxyz import key_val_str_to_dict
from ase.io.formats import string2index
from ase.io.lammpsdata import read_lammps_data
from ase.io.trajectory import Trajectory

ATOM_LABEL_ARRAY = "v_ase_atom_type"
# Compatibility name for code written against v_ase <= 0.0.77.
ATOM_TYPE_ARRAY = ATOM_LABEL_ARRAY

INPUT_FORMAT_ALIASES = {
    "poscar": "vasp",
    "contcar": "vasp",
    "vasp": "vasp",
    "xdatcar": "vasp-xdatcar",
    "vasp-xdatcar": "vasp-xdatcar",
    "vasp_xdatcar": "vasp-xdatcar",
    "vasprun": "vasp-xml",
    "vasprun.xml": "vasp-xml",
    "vasp-xml": "vasp-xml",
    "vasp_xml": "vasp-xml",
    "lammpstrj": "lammps-dump-text",
    "lammpsdump": "lammps-dump-text",
    "lammps-dump": "lammps-dump-text",
    "lammps_dump": "lammps-dump-text",
    "lammps-dump-text": "lammps-dump-text",
    "lammps_dump_text": "lammps-dump-text",
    "traj": "traj",
    "trajectory": "traj",
    "xyz": "xyz",
    "extxyz": "extxyz",
    "extendedxyz": "extxyz",
    "data": "lammps-data",
    "lammps-data": "lammps-data",
    "lammps_data": "lammps-data",
    "vase": "vase-project",
    "vase-project": "vase-project",
    "html": "vase-html-project",
    "vase-html": "vase-html-project",
    "vase-html-project": "vase-html-project",
    "chg": "vasp-density",
    "chgcar": "vasp-density",
    "parchg": "vasp-partial-density",
    "locpot": "vasp-potential",
    "elfcar": "vasp-elf",
    "cube": "cube",
    "cub": "cube",
    "gaussian-cube": "cube",
    "xsf": "xsf",
    "qe-cube": "cube",
    "qe-xsf": "xsf",
}


def resolve_input_format(fmt: str | None) -> str | None:
    """Resolve user-facing format aliases to ASE reader names."""
    if not fmt:
        return None
    key = fmt.strip().lower()
    return INPUT_FORMAT_ALIASES.get(key, fmt)


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
    atom_end_offsets: list[int] | None = None
    scaled_positions: bool = False
    template_atoms: Atoms | None = None
    id_column: int | None = None
    type_column: int | None = None
    mol_column: int | None = None
    charge_column: int | None = None
    force_columns: tuple[int, int, int] | None = None
    mass_column: int | None = None
    scalar_columns: dict[str, int] = field(default_factory=dict)
    _id_order: np.ndarray | None = field(default=None, repr=False)
    _ids_are_sorted: bool = True

    @property
    def frame_count(self) -> int:
        return len(self.atom_offsets)

    def __len__(self) -> int:
        return self.frame_count

    def _read_numeric_table(self, frame_index: int) -> np.ndarray:
        if frame_index < 0 or frame_index >= self.frame_count:
            raise IndexError(f"Frame index {frame_index} is out of range")
        with open(self.path, "rb", buffering=1024 * 1024) as handle:
            start = self.atom_offsets[frame_index]
            handle.seek(start)
            if self.atom_end_offsets and frame_index < len(self.atom_end_offsets):
                block = handle.read(self.atom_end_offsets[frame_index] - start)
            else:
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

    def read_scalar_values(self, frame_index: int, field_id: str) -> np.ndarray | None:
        """Read one colorable scalar without constructing an ``Atoms`` object."""

        table = self._read_numeric_table(frame_index)
        if field_id in {"position:x", "position:y", "position:z"}:
            component = {"position:x": 0, "position:y": 1, "position:z": 2}[field_id]
            return self._positions_from_table(table, frame_index)[:, component]
        if field_id == "force:norm" and self.force_columns is not None:
            return np.linalg.norm(table[:, self.force_columns], axis=1).astype(np.float32)

        parts = str(field_id).split("::")
        if len(parts) < 3 or parts[0] != "array":
            return None
        name = unquote(parts[1])
        reduction = parts[2]
        component = int(parts[3]) if len(parts) > 3 and parts[3].lstrip("-").isdigit() else None
        if name == "initial_charges" and self.charge_column is not None:
            values = table[:, self.charge_column]
        elif name == "forces" and self.force_columns is not None:
            values = table[:, self.force_columns]
        elif name == "lammps_id" and self.id_column is not None:
            values = table[:, self.id_column]
        elif name == "lammps_type" and self.type_column is not None:
            values = table[:, self.type_column]
        elif name == "mol" and self.mol_column is not None:
            values = table[:, self.mol_column]
        elif name == "masses" and self.mass_column is not None:
            values = table[:, self.mass_column]
        elif name in self.scalar_columns:
            values = table[:, self.scalar_columns[name]]
        else:
            return None

        flattened = np.asarray(values, dtype=np.float32).reshape(self.natoms, -1)
        if reduction == "scalar" and flattened.shape[1] == 1:
            return flattened[:, 0]
        if reduction == "norm":
            return np.linalg.norm(flattened, axis=1).astype(np.float32)
        if reduction == "component" and component is not None and 0 <= component < flattened.shape[1]:
            return flattened[:, component]
        return None

    def read_force_vectors(self, frame_index: int) -> np.ndarray | None:
        """Read Cartesian forces without constructing an ``Atoms`` object."""

        if self.force_columns is None:
            return None
        table = self._read_numeric_table(frame_index)
        return table[:, self.force_columns].astype(np.float32, copy=True)

    def read_atoms(self, frame_index: int) -> Atoms:
        if self.template_atoms is None:
            raise ValueError("Fast LAMMPS trajectory has no template Atoms object.")
        table = self._read_numeric_table(frame_index)
        atoms = self.template_atoms.copy()
        atoms.set_positions(
            self._positions_from_table(table, frame_index),
            apply_constraint=False,
        )
        atoms.set_cell(self.cells[frame_index])
        atoms.set_pbc(self.pbc[frame_index])
        atoms.info["timestep"] = int(self.timesteps[frame_index])
        self._apply_frame_arrays(atoms, table)
        return atoms

    def _apply_frame_arrays(self, atoms: Atoms, table: np.ndarray) -> None:
        """Update every per-atom numeric field from one dump frame."""

        if self.id_column is not None:
            atoms.set_array("lammps_id", table[:, self.id_column].astype(np.int64))
        if self.type_column is not None:
            atoms.set_array("lammps_type", table[:, self.type_column].astype(np.int32))
        if self.mol_column is not None:
            atoms.set_array("mol", table[:, self.mol_column].astype(np.int64))
        if self.charge_column is not None:
            atoms.set_initial_charges(table[:, self.charge_column].astype(np.float32))
        if self.force_columns is not None:
            atoms.set_array("forces", table[:, self.force_columns].astype(np.float32))
        if self.mass_column is not None:
            atoms.set_masses(table[:, self.mass_column].astype(np.float32))
        for name, column in self.scalar_columns.items():
            atoms.set_array(name, table[:, column].astype(np.float32))

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
        set_atom_labels(atoms, labels)
        self._apply_frame_arrays(atoms, table)
        self.template_atoms = atoms.copy()
        return atoms


@dataclass
class FastLammpsDumpResult:
    atoms: Atoms
    trajectory: FastLammpsDumpTrajectory
    initial_frame: int = 0


@dataclass
class IndexedTrajectoryResult:
    """One immediately available frame plus an on-demand trajectory source."""

    atoms: Atoms
    trajectory: object
    initial_frame: int = 0


def _selected_trajectory_indices(
    index: str | int | slice | None,
    frame_count: int,
) -> list[int]:
    parsed = string2index(":") if index is None else string2index(index) if isinstance(index, str) else index
    available = range(frame_count)
    if isinstance(parsed, slice):
        return list(available[parsed])
    if isinstance(parsed, int):
        try:
            return [available[parsed]]
        except IndexError as exc:
            raise ValueError(f"Frame index {parsed} is out of range") from exc
    return list(available)


def _labels_for_species_blocks(species: list[str], counts: list[int]) -> list[str]:
    totals = Counter(species)
    occurrences: Counter[str] = Counter()
    labels: list[str] = []
    for symbol, count in zip(species, counts):
        occurrences[symbol] += 1
        label = f"{symbol}_{occurrences[symbol]}" if totals[symbol] > 1 else symbol
        labels.extend([label] * count)
    return labels


@dataclass
class IndexedXdatcarTrajectory:
    """Byte-offset XDATCAR reader that parses only the requested frame."""

    path: str
    natoms: int
    symbols: list[str]
    labels: list[str]
    coordinate_offsets: list[int]
    coordinate_end_offsets: list[int]
    cells: np.ndarray
    pbc: np.ndarray
    template_atoms: Atoms | None = None

    @property
    def frame_count(self) -> int:
        return len(self.coordinate_offsets)

    def __len__(self) -> int:
        return self.frame_count

    def read_positions(self, frame_index: int) -> np.ndarray:
        if frame_index < 0 or frame_index >= self.frame_count:
            raise IndexError(f"Frame index {frame_index} is out of range")
        start = self.coordinate_offsets[frame_index]
        end = self.coordinate_end_offsets[frame_index]
        with open(self.path, "rb", buffering=1024 * 1024) as handle:
            handle.seek(start)
            block = handle.read(end - start)
        scaled = np.fromstring(block, sep=" ", dtype=np.float64)
        expected = self.natoms * 3
        if scaled.size != expected:
            raise ValueError(
                f"XDATCAR frame {frame_index} contains {scaled.size} coordinate values; "
                f"expected {expected}."
            )
        return scaled.reshape(self.natoms, 3) @ self.cells[frame_index]

    def read_atoms(self, frame_index: int) -> Atoms:
        atoms = Atoms(
            symbols=self.symbols,
            positions=self.read_positions(frame_index),
            cell=self.cells[frame_index],
            pbc=self.pbc[frame_index],
        )
        set_atom_labels(atoms, self.labels)
        atoms.info["configuration"] = int(frame_index + 1)
        return atoms


@dataclass
class IndexedAseTrajectory:
    """Random-access wrapper around ASE's native ``.traj`` container."""

    path: str
    source_indices: list[int]
    natoms: int
    template_atoms: Atoms
    # Unknown cell evolution deliberately disables eager trajectory caches.
    cells: np.ndarray = field(default_factory=lambda: np.empty((0, 3, 3), dtype=float))
    pbc: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=bool))

    @property
    def frame_count(self) -> int:
        return len(self.source_indices)

    def __len__(self) -> int:
        return self.frame_count

    def read_atoms(self, frame_index: int) -> Atoms:
        if frame_index < 0 or frame_index >= self.frame_count:
            raise IndexError(f"Frame index {frame_index} is out of range")
        with Trajectory(self.path, mode="r") as trajectory:
            return trajectory[self.source_indices[frame_index]]

    def read_positions(self, frame_index: int) -> np.ndarray:
        return np.asarray(self.read_atoms(frame_index).positions, dtype=np.float32)


def index_vasp_xdatcar(
    path: str | Path,
    index: str | int | slice | None = ":",
) -> IndexedXdatcarTrajectory:
    """Index XDATCAR frames without parsing every coordinate table."""

    source = Path(path)
    coordinate_offsets: list[int] = []
    coordinate_end_offsets: list[int] = []
    cells: list[np.ndarray] = []
    frame_symbols: list[str] | None = None
    frame_labels: list[str] | None = None
    natoms: int | None = None
    current_cell: np.ndarray | None = None

    with source.open("rb") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            if b"Direct configuration=" not in line:
                scale_line = handle.readline()
                if not scale_line:
                    break
                try:
                    scale_values = scale_line.split()
                    if len(scale_values) != 1:
                        raise ValueError(
                            "XDATCAR vector scaling requires the compatible reader."
                        )
                    scale = float(scale_values[0])
                    if scale <= 0:
                        raise ValueError(
                            "XDATCAR non-positive scaling requires the compatible reader."
                        )
                    cell = np.asarray(
                        [[float(value) for value in handle.readline().split()[:3]] for _ in range(3)],
                        dtype=float,
                    ) * scale
                    species = handle.readline().decode("utf-8", errors="replace").split()
                    counts = [int(value) for value in handle.readline().split()]
                except (TypeError, ValueError) as exc:
                    raise ValueError("XDATCAR header is incomplete or invalid.") from exc
                if cell.shape != (3, 3) or not species or len(species) != len(counts):
                    raise ValueError("XDATCAR species, counts, or cell header is invalid.")
                if any(symbol not in atomic_numbers for symbol in species):
                    raise ValueError("XDATCAR contains an unsupported chemical symbol.")
                expanded = [symbol for symbol, count in zip(species, counts) for _ in range(count)]
                labels = _labels_for_species_blocks(species, counts)
                if frame_symbols is None:
                    frame_symbols = expanded
                    frame_labels = labels
                    natoms = len(expanded)
                elif expanded != frame_symbols or labels != frame_labels:
                    raise ValueError(
                        "XDATCAR atom identities change between frames; use the compatible reader."
                    )
                current_cell = cell
                configuration_line = handle.readline()
                if b"Direct configuration=" not in configuration_line:
                    raise ValueError("XDATCAR frame is missing its Direct configuration marker.")
            elif natoms is None or current_cell is None:
                raise ValueError("XDATCAR starts with coordinates before a structure header.")

            start = handle.tell()
            for _ in range(int(natoms or 0)):
                if not handle.readline():
                    raise ValueError("XDATCAR coordinate block ended before all atoms were read.")
            coordinate_offsets.append(start)
            coordinate_end_offsets.append(handle.tell())
            cells.append(np.asarray(current_cell, dtype=float).copy())

    if natoms is None or frame_symbols is None or frame_labels is None or not coordinate_offsets:
        raise ValueError("No frames found in XDATCAR.")
    selected = _selected_trajectory_indices(index, len(coordinate_offsets))
    if not selected:
        raise ValueError("The requested XDATCAR frame selection is empty.")
    trajectory = IndexedXdatcarTrajectory(
        path=str(source),
        natoms=natoms,
        symbols=frame_symbols,
        labels=frame_labels,
        coordinate_offsets=[coordinate_offsets[i] for i in selected],
        coordinate_end_offsets=[coordinate_end_offsets[i] for i in selected],
        cells=np.asarray([cells[i] for i in selected], dtype=float),
        pbc=np.ones((len(selected), 3), dtype=bool),
    )
    trajectory.template_atoms = trajectory.read_atoms(0)
    return trajectory


def read_indexed_trajectory(
    path: str | Path,
    index: str | int | slice | None = ":",
    fmt: str | None = None,
) -> IndexedTrajectoryResult | None:
    """Return an on-demand source for formats with reliable random access."""

    source = Path(path)
    resolved = resolve_input_format(fmt)
    name = source.name.upper()
    if resolved == "vasp-xdatcar" or (fmt is None and name.startswith("XDATCAR")):
        trajectory = index_vasp_xdatcar(source, index)
        return IndexedTrajectoryResult(
            atoms=trajectory.template_atoms.copy(),
            trajectory=trajectory,
        )
    if resolved == "traj" or (fmt is None and source.suffix.lower() == ".traj"):
        with Trajectory(str(source), mode="r") as reader:
            selected = _selected_trajectory_indices(index, len(reader))
            if not selected:
                raise ValueError("The requested ASE trajectory frame selection is empty.")
            template = reader[selected[0]]
        trajectory = IndexedAseTrajectory(
            path=str(source),
            source_indices=selected,
            natoms=len(template),
            template_atoms=template.copy(),
        )
        return IndexedTrajectoryResult(atoms=template, trajectory=trajectory)
    return None


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


def atom_labels(atoms: Atoms) -> list[str]:
    """Return user-facing labels, distinct from ASE chemical symbols."""
    labels = atoms.arrays.get(ATOM_LABEL_ARRAY)
    if labels is None or len(labels) != len(atoms):
        return atoms.get_chemical_symbols()
    return [normalize_atom_type_label(label) for label in labels]


def set_atom_labels(atoms: Atoms, labels: Iterable[object]) -> None:
    """Store user-facing labels without changing ASE chemical symbols."""
    normalized = [normalize_atom_type_label(label) for label in labels]
    # ASE updates an existing array in place and therefore preserves its old
    # fixed-width Unicode dtype. Recreate the array so longer renamed labels
    # are never silently truncated.
    atoms.set_array(ATOM_LABEL_ARRAY, None)
    atoms.set_array(ATOM_LABEL_ARRAY, np.asarray(normalized, dtype=str))


def _vasp_species_block_labels(path: Path, atoms: Atoms) -> list[str] | None:
    """Preserve repeated POSCAR species blocks as distinct display labels.

    ASE remains authoritative for the physical structure.  Labels are applied
    only after the explicit VASP 5/6 species header expands to the exact ASE
    chemical-symbol sequence, so no coordinates, elements, or constraints are
    inferred or reordered here.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            header = [handle.readline() for _ in range(7)]
    except OSError:
        return None
    if len(header) < 7 or any(line == "" for line in header):
        return None

    try:
        scale_values = [float(value) for value in header[1].split()]
        lattice_rows = [
            [float(value) for value in header[row].split()[:3]]
            for row in range(2, 5)
        ]
    except (TypeError, ValueError):
        return None
    if len(scale_values) not in {1, 3} or any(len(row) != 3 for row in lattice_rows):
        return None

    species = header[5].split()
    count_tokens = header[6].split()
    if not species or len(species) != len(count_tokens):
        return None
    if any(symbol not in atomic_numbers for symbol in species):
        return None
    try:
        counts = [int(value) for value in count_tokens]
    except ValueError:
        return None
    if any(count < 0 for count in counts) or sum(counts) != len(atoms):
        return None

    expanded_symbols = [
        symbol
        for symbol, count in zip(species, counts)
        for _ in range(count)
    ]
    if expanded_symbols != atoms.get_chemical_symbols():
        return None

    block_totals = Counter(species)
    if all(total == 1 for total in block_totals.values()):
        return None
    block_occurrences: Counter[str] = Counter()
    labels: list[str] = []
    for symbol, count in zip(species, counts):
        block_occurrences[symbol] += 1
        label = (
            f"{symbol}_{block_occurrences[symbol]}"
            if block_totals[symbol] > 1
            else symbol
        )
        labels.extend([label] * count)
    return labels


def _apply_vasp_species_block_labels(
    path: Path,
    frames: list[Atoms],
    resolved_format: str | None,
    requested_format: str | None,
) -> None:
    name = path.name.upper()
    is_vasp_structure = resolved_format == "vasp" or (
        requested_format is None
        and (
            path.suffix.lower() == ".vasp"
            or name.startswith("POSCAR")
            or name.startswith("CONTCAR")
        )
    )
    if not is_vasp_structure:
        return
    for atoms in frames:
        labels = _vasp_species_block_labels(path, atoms)
        if labels is not None:
            set_atom_labels(atoms, labels)


# Compatibility aliases for code written against v_ase <= 0.0.77.
atom_type_labels = atom_labels
set_atom_type_labels = set_atom_labels


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
    if path.stat().st_size == 0:
        raise ValueError("No frames found in LAMMPS dump.")
    atom_offsets: list[int] = []
    atom_end_offsets: list[int] = []
    timesteps: list[int] = []
    cells: list[np.ndarray] = []
    pbc_values: list[list[bool]] = []
    columns: list[str] | None = None
    natoms: int | None = None

    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            size = len(mapped)

            def read_line(position: int) -> tuple[bytes, int]:
                if position >= size:
                    return b"", size
                end = mapped.find(b"\n", position)
                if end < 0:
                    return mapped[position:size].rstrip(b"\r"), size
                return mapped[position:end].rstrip(b"\r"), end + 1

            cursor = 0
            while cursor < size:
                marker = mapped.find(b"ITEM: TIMESTEP", cursor)
                if marker < 0:
                    break
                if marker > 0 and mapped[marker - 1:marker] not in {b"\n", b"\r"}:
                    cursor = marker + 1
                    continue

                line, cursor = read_line(marker)
                if line != b"ITEM: TIMESTEP":
                    cursor = marker + 1
                    continue
                timestep_line, cursor = read_line(cursor)
                number_header, cursor = read_line(cursor)
                if number_header != b"ITEM: NUMBER OF ATOMS":
                    raise ValueError("LAMMPS dump is missing NUMBER OF ATOMS after TIMESTEP.")
                natoms_line, cursor = read_line(cursor)
                bounds_header, cursor = read_line(cursor)
                if not bounds_header.startswith(b"ITEM: BOX BOUNDS"):
                    raise ValueError("LAMMPS dump is missing BOX BOUNDS.")
                bounds_lines = []
                for _ in range(3):
                    bounds_line, cursor = read_line(cursor)
                    bounds_lines.append(bounds_line)
                atom_header, cursor = read_line(cursor)
                if not atom_header.startswith(b"ITEM: ATOMS"):
                    raise ValueError("LAMMPS dump is missing ATOMS columns.")

                timestep = int(float(timestep_line.strip()))
                frame_natoms = int(natoms_line.strip())
                cell, pbc = _parse_lammps_box_bytes(bounds_header, bounds_lines)
                frame_columns = [
                    token.decode("utf-8", errors="replace")
                    for token in atom_header.split()[2:]
                ]
                if "element" in frame_columns:
                    raise ValueError(
                        "Fast LAMMPS parser supports numeric dump columns; "
                        "element-string dumps use the safe parser."
                    )
                if natoms is None:
                    natoms = frame_natoms
                    columns = frame_columns
                    _fast_lammps_position_columns(columns)
                elif frame_natoms != natoms:
                    raise ValueError("Fast LAMMPS trajectory requires a constant atom count.")
                elif frame_columns != columns:
                    raise ValueError("Fast LAMMPS trajectory requires constant ATOMS columns.")

                atom_start = cursor
                next_marker = mapped.find(b"\nITEM: TIMESTEP", atom_start)
                atom_end = size if next_marker < 0 else next_marker + 1
                atom_offsets.append(atom_start)
                atom_end_offsets.append(atom_end)
                timesteps.append(timestep)
                cells.append(cell)
                pbc_values.append(pbc)
                cursor = size if next_marker < 0 else next_marker + 1

    if natoms is None or columns is None or not atom_offsets:
        raise ValueError("No frames found in LAMMPS dump.")

    column_map = {name: idx for idx, name in enumerate(columns)}
    position_columns, scaled = _fast_lammps_position_columns(columns)
    force_columns = None
    if all(name in column_map for name in ("fx", "fy", "fz")):
        force_columns = (column_map["fx"], column_map["fy"], column_map["fz"])
    known_columns = {
        "id", "type", "mol", "q", "mass",
        "x", "y", "z", "xu", "yu", "zu", "xs", "ys", "zs",
        "xsu", "ysu", "zsu", "fx", "fy", "fz",
    }
    scalar_columns = {
        name: column
        for name, column in column_map.items()
        if name not in known_columns
    }
    return FastLammpsDumpTrajectory(
        path=str(path),
        natoms=natoms,
        columns=columns,
        atom_offsets=atom_offsets,
        timesteps=timesteps,
        cells=np.asarray(cells, dtype=float),
        pbc=np.asarray(pbc_values, dtype=bool),
        position_columns=position_columns,
        atom_end_offsets=atom_end_offsets,
        scaled_positions=scaled,
        id_column=column_map.get("id"),
        type_column=column_map.get("type"),
        mol_column=column_map.get("mol"),
        charge_column=column_map.get("q"),
        force_columns=force_columns,
        mass_column=column_map.get("mass"),
        scalar_columns=scalar_columns,
    )


def read_fast_lammps_dump(path: str | Path, index: str | int | slice | None = ":") -> FastLammpsDumpResult:
    """Read a large numeric LAMMPS dump as a first-frame Atoms plus virtual trajectory."""
    trajectory = index_lammps_dump(path)
    initial_frame = _fast_lammps_selected_initial_frame(index, trajectory.frame_count)
    template = trajectory.build_template(0)
    atoms = template.copy() if initial_frame == 0 else trajectory.read_atoms(initial_frame)
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
        set_atom_labels(atoms, labels)
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
    set_atom_labels(atoms, labels)
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
        labels = atom_labels(atoms)
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
    set_atom_labels(atoms, labels)
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
                set_atom_labels(atoms, labels)

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


def read_structure_frames(
    path: str | Path,
    index: str | int | slice | None = ":",
    fmt: str | None = None,
) -> list[Atoms]:
    """Read one or more frames through the canonical v_ase input pipeline."""
    source = Path(path)
    resolved_format = resolve_input_format(fmt)
    suffix = source.suffix.lower()

    if resolved_format == "lammps-dump-text" or (
        fmt is None and suffix in {".lammpstrj", ".dump"}
    ):
        return read_custom_lammps_dump(source, index)
    if resolved_format == "lammps-data" or (fmt is None and suffix == ".data"):
        return read_custom_lammps_data(source, index)

    read_kwargs = {"index": index}
    if resolved_format:
        read_kwargs["format"] = resolved_format

    custom_extxyz_allowed = (
        resolved_format in {None, "extxyz", "xyz"}
        and suffix in {".xyz", ".extxyz"}
    )

    def needs_custom_extxyz(frames: list[Atoms]) -> bool:
        if not custom_extxyz_allowed:
            return False
        return any(
            "atom_type" in atoms.arrays
            and any(symbol == "X" for symbol in atoms.get_chemical_symbols())
            for atoms in frames
        )

    try:
        loaded = read(source, **read_kwargs)
    except (KeyError, TypeError, ValueError):
        if not custom_extxyz_allowed:
            raise
        return read_custom_extxyz(source, index)

    frames = loaded if isinstance(loaded, list) else [loaded]
    if needs_custom_extxyz(frames):
        return read_custom_extxyz(source, index)
    _apply_vasp_species_block_labels(source, frames, resolved_format, fmt)
    return frames
