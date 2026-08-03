"""Phonopy-backed finite-displacement and frozen-mode workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from ase import Atoms

from .io import atom_labels, set_atom_labels


class PhononDependencyError(RuntimeError):
    """Raised when phonopy is not installed."""


def _phonopy_api():
    try:
        import phonopy
        from phonopy import Phonopy
        from phonopy.structure.atoms import PhonopyAtoms
    except ModuleNotFoundError as exc:
        raise PhononDependencyError(
            "Phonon workflows require phonopy. Install with "
            '`python -m pip install -e ".[phonon]"`.'
        ) from exc
    return phonopy, Phonopy, PhonopyAtoms


def _seekpath_api():
    try:
        import seekpath
    except ModuleNotFoundError as exc:
        raise PhononDependencyError(
            "Automatic phonon band paths require seekpath. Install with "
            '`python -m pip install -e ".[phonon]"`.'
        ) from exc
    return seekpath


def _integer_matrix(value: Sequence[int] | Sequence[Sequence[int]]) -> np.ndarray:
    try:
        numeric = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("The phonon supercell matrix must contain integers.") from exc
    if not np.isfinite(numeric).all() or not np.allclose(
        numeric,
        np.rint(numeric),
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("The phonon supercell matrix must contain finite integers.")
    array = np.rint(numeric).astype(np.int64)
    if array.shape == (3,):
        if np.any(array < 1):
            raise ValueError("Supercell repeats must be positive integers.")
        array = np.diag(array)
    if array.shape != (3, 3):
        raise ValueError("The phonon supercell matrix must be length 3 or shape 3 x 3.")
    determinant = int(round(float(np.linalg.det(array))))
    if determinant == 0:
        raise ValueError("The phonon supercell matrix must be invertible.")
    return array


def _validate_unitcell(atoms: Atoms) -> None:
    if len(atoms) == 0:
        raise ValueError("Phonon workflows require at least one atom.")
    lattice = np.asarray(atoms.cell.array, dtype=float)
    if lattice.shape != (3, 3) or abs(float(np.linalg.det(lattice))) < 1e-12:
        raise ValueError("Phonon workflows require an invertible 3D unit cell.")
    if not np.asarray(atoms.pbc, dtype=bool).all():
        raise ValueError(
            "Phonopy mode construction requires PBC=True along all three cell axes."
        )


def ase_to_phonopy(atoms: Atoms):
    """Convert ASE Atoms without carrying executable calculator state."""
    _, _, PhonopyAtoms = _phonopy_api()
    _validate_unitcell(atoms)
    kwargs = {
        "symbols": atoms.get_chemical_symbols(),
        "cell": np.asarray(atoms.cell.array, dtype=float),
        "scaled_positions": np.mod(
            np.asarray(atoms.get_scaled_positions(wrap=False), dtype=float), 1.0
        ),
        "masses": np.asarray(atoms.get_masses(), dtype=float),
    }
    magnetic_moments = np.asarray(atoms.get_initial_magnetic_moments(), dtype=float)
    if magnetic_moments.size and np.any(np.abs(magnetic_moments) > 1e-12):
        kwargs["magnetic_moments"] = magnetic_moments
    return PhonopyAtoms(
        **kwargs,
    )


def _supercell_unit_indices(phonon: Any) -> list[int] | None:
    supercell = phonon.supercell
    s2u = getattr(supercell, "s2u_map", None)
    u2s = getattr(supercell, "u2s_map", None)
    if s2u is None or u2s is None:
        return None
    representative_to_unit = {
        int(representative): index
        for index, representative in enumerate(np.asarray(u2s, dtype=int))
    }
    try:
        return [
            representative_to_unit[int(representative)]
            for representative in np.asarray(s2u, dtype=int)
        ]
    except KeyError:
        return None


def phonopy_to_ase(
    structure: Any,
    *,
    labels: Sequence[str] | None = None,
    unit_indices: Sequence[int] | None = None,
    cartesian_transform: Sequence[Sequence[float]] | None = None,
    cartesian_shift: Sequence[float] | None = None,
    reference_scaled_positions: Sequence[Sequence[float]] | None = None,
) -> Atoms:
    """Convert PhonopyAtoms to ASE and preserve labels when a map is available."""
    masses = getattr(structure, "masses", None)
    cell = np.asarray(structure.cell, dtype=float)
    if cartesian_transform is not None:
        transform = np.asarray(cartesian_transform, dtype=float)
        if transform.shape != (3, 3) or not np.isfinite(transform).all():
            raise ValueError("Cartesian phonon alignment must be a finite 3 x 3 matrix.")
        cell = cell @ transform
    scaled_positions = np.asarray(structure.scaled_positions, dtype=float)
    if reference_scaled_positions is None:
        scaled_positions = np.mod(scaled_positions, 1.0)
    else:
        reference = np.asarray(reference_scaled_positions, dtype=float)
        if reference.shape != scaled_positions.shape or not np.isfinite(reference).all():
            raise ValueError(
                "Reference phonon positions must match the generated supercell."
            )
        periodic_delta = scaled_positions - reference
        periodic_delta -= np.rint(periodic_delta)
        scaled_positions = reference + periodic_delta
    atoms = Atoms(
        symbols=list(structure.symbols),
        scaled_positions=scaled_positions,
        cell=cell,
        pbc=True,
        masses=(np.asarray(masses, dtype=float) if masses is not None else None),
    )
    if cartesian_shift is not None:
        shift = np.asarray(cartesian_shift, dtype=float)
        if shift.shape != (3,) or not np.isfinite(shift).all():
            raise ValueError("Cartesian phonon origin shift must contain three values.")
        atoms.translate(shift)
    if labels is not None:
        if unit_indices is None and len(labels) == len(atoms):
            set_atom_labels(atoms, list(labels))
        elif unit_indices is not None and len(unit_indices) == len(atoms):
            set_atom_labels(atoms, [str(labels[index]) for index in unit_indices])
    return atoms


@dataclass
class PhononModel:
    """A loaded or generated phonopy model held by one editor session."""

    phonon: Any
    source: str
    unit_labels: list[str]
    cartesian_transform: np.ndarray = field(default_factory=lambda: np.eye(3))
    cartesian_shift: np.ndarray = field(default_factory=lambda: np.zeros(3))

    @property
    def has_force_constants(self) -> bool:
        return self.phonon.force_constants is not None

    def summary(self) -> dict[str, Any]:
        primitive = self.phonon.primitive
        supercell = self.phonon.supercell
        return {
            "status": "ok",
            "source": self.source,
            "unit_atoms": len(self.phonon.unitcell),
            "primitive_atoms": len(primitive),
            "supercell_atoms": len(supercell),
            "supercell_matrix": np.asarray(
                self.phonon.supercell_matrix, dtype=int
            ).tolist(),
            "has_force_constants": self.has_force_constants,
            "has_nac": self.phonon.nac_params is not None,
            "frequency_unit": "THz",
            "aligned_to_active_structure": bool(
                not np.allclose(self.cartesian_transform, np.eye(3), atol=1e-12)
                or not np.allclose(self.cartesian_shift, 0.0, atol=1e-12)
            ),
        }


def validate_phonon_model_for_atoms(
    model: PhononModel,
    atoms: Atoms,
    *,
    tolerance: float = 1e-5,
) -> None:
    """Reject a phonopy project that does not describe the active structure."""
    _validate_unitcell(atoms)
    unitcell = model.phonon.unitcell
    if len(unitcell) != len(atoms):
        raise ValueError(
            "The phonopy project has "
            f"{len(unitcell)} unit-cell atoms, but the current structure has {len(atoms)}."
        )
    project_symbols = list(unitcell.symbols)
    current_symbols = atoms.get_chemical_symbols()
    if project_symbols != current_symbols:
        raise ValueError(
            "The phonopy project atom order or chemical elements do not match "
            "the current structure."
        )
    project_cell = np.asarray(unitcell.cell, dtype=float)
    current_cell = np.asarray(atoms.cell.array, dtype=float)
    metric_tolerance = float(tolerance) * max(
        1.0,
        2.0 * float(np.max(np.linalg.norm(current_cell, axis=1))),
    )
    if not np.allclose(
        project_cell @ project_cell.T,
        current_cell @ current_cell.T,
        rtol=0.0,
        atol=metric_tolerance,
    ):
        raise ValueError(
            "The phonopy project lattice metric does not match the current structure."
        )
    cartesian_transform = np.linalg.solve(project_cell, current_cell)
    orthogonality_error = float(
        np.max(np.abs(cartesian_transform.T @ cartesian_transform - np.eye(3)))
    )
    determinant = float(np.linalg.det(cartesian_transform))
    if orthogonality_error > 1e-7 or not np.isclose(
        determinant,
        1.0,
        rtol=0.0,
        atol=1e-7,
    ):
        raise ValueError(
            "The phonopy project requires a non-rigid lattice-basis change; "
            "only a Cartesian rotation of the same basis is accepted."
        )
    project_scaled = np.asarray(unitcell.scaled_positions, dtype=float)
    current_scaled = np.asarray(atoms.get_scaled_positions(wrap=False), dtype=float)
    fractional_shift = current_scaled - project_scaled
    fractional_shift -= np.rint(fractional_shift)
    common_shift = fractional_shift[0]
    relative_shift = fractional_shift - common_shift
    relative_shift -= np.rint(relative_shift)
    cartesian_delta = relative_shift @ current_cell
    maximum_position = float(
        np.max(np.linalg.norm(cartesian_delta, axis=1), initial=0.0)
    )
    if maximum_position > float(tolerance):
        raise ValueError(
            "The phonopy project fractional positions or atom order do not match "
            "the current structure "
            f"(maximum non-rigid periodic displacement {maximum_position:.6g} A)."
        )
    model.cartesian_transform = cartesian_transform
    model.cartesian_shift = common_shift @ current_cell


def create_phonon_model(
    atoms: Atoms,
    *,
    supercell_matrix: Sequence[int] | Sequence[Sequence[int]] = (2, 2, 2),
    primitive_matrix: Any = "auto",
    symprec: float = 1e-5,
) -> PhononModel:
    """Create an empty phonopy model suitable for displacement generation."""
    _, Phonopy, _ = _phonopy_api()
    phonon = Phonopy(
        ase_to_phonopy(atoms),
        _integer_matrix(supercell_matrix),
        primitive_matrix=primitive_matrix,
        symprec=float(symprec),
    )
    return PhononModel(
        phonon=phonon,
        source="generated from current v_ase structure",
        unit_labels=atom_labels(atoms),
    )


def load_phonon_model(
    path: str | Path,
    *,
    force_constants_path: str | Path | None = None,
    symprec: float = 1e-5,
) -> PhononModel:
    """Load a phonopy YAML project, optionally with a separate force-constants file."""
    phonopy, _, _ = _phonopy_api()
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Phonopy project not found: {source}")
    kwargs: dict[str, Any] = {
        "phonopy_yaml": source,
        "symprec": float(symprec),
        "produce_fc": True,
    }
    if force_constants_path is not None:
        force_source = Path(force_constants_path).expanduser().resolve()
        if not force_source.is_file():
            raise FileNotFoundError(f"Force constants not found: {force_source}")
        kwargs["force_constants_filename"] = force_source
    try:
        model = phonopy.load(**kwargs)
    except Exception as exc:
        raise ValueError(
            f"Could not load the phonopy project '{source.name}': {exc}"
        ) from exc
    labels = list(model.unitcell.symbols)
    return PhononModel(model, str(source), labels)


def generate_finite_displacements(
    atoms: Atoms,
    *,
    supercell_matrix: Sequence[int] | Sequence[Sequence[int]] = (2, 2, 2),
    distance: float = 0.01,
    plusminus: bool | str = "auto",
    diagonal: bool = True,
    symprec: float = 1e-5,
) -> tuple[PhononModel, list[Atoms], dict[str, Any]]:
    """Generate symmetry-reduced finite-displacement supercells without forces."""
    if not np.isfinite(distance) or distance <= 0:
        raise ValueError("Finite-displacement distance must be positive in Angstrom.")
    model = create_phonon_model(
        atoms,
        supercell_matrix=supercell_matrix,
        symprec=symprec,
    )
    model.phonon.generate_displacements(
        distance=float(distance),
        is_plusminus=plusminus,
        is_diagonal=bool(diagonal),
    )
    displaced = model.phonon.supercells_with_displacements
    if not displaced:
        raise ValueError("phonopy generated no finite-displacement structures.")
    mapping = _supercell_unit_indices(model.phonon)
    frames = [
        phonopy_to_ase(
            structure,
            labels=model.unit_labels,
            unit_indices=mapping,
        )
        for structure in displaced
    ]
    for index, frame in enumerate(frames):
        frame.info["v_ase_phonon_displacement"] = {
            "index": index,
            "count": len(frames),
            "distance_angstrom": float(distance),
            "supercell_matrix": np.asarray(
                model.phonon.supercell_matrix, dtype=int
            ).tolist(),
            "forces_required": True,
        }
    return model, frames, {
        **model.summary(),
        "displacement_count": len(frames),
        "distance_angstrom": float(distance),
        "forces_required": True,
        "message": (
            "These structures are calculation inputs. Compute forces for every "
            "frame before producing force constants or physical phonon modes."
        ),
    }


def qpoint_commensurability(
    qpoint: Sequence[float],
    dimension: Sequence[int] | Sequence[Sequence[int]],
    *,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    """Check the Phonopy condition P.T @ q being integer."""
    q = np.asarray(qpoint, dtype=float)
    if q.shape != (3,) or not np.isfinite(q).all():
        raise ValueError("qpoint must contain three finite reciprocal coordinates.")
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Commensurability tolerance must be positive and finite.")
    matrix = _integer_matrix(dimension)
    transformed = matrix.T @ q
    nearest = np.rint(transformed)
    residual = transformed - nearest
    return {
        "commensurate": bool(np.all(np.abs(residual) <= float(tolerance))),
        "qpoint": q.tolist(),
        "dimension": matrix.tolist(),
        "transformed": transformed.tolist(),
        "nearest_integer": nearest.astype(int).tolist(),
        "residual": residual.tolist(),
        "tolerance": float(tolerance),
    }


def _suggest_diagonal_supercell(
    qpoint: Sequence[float],
    *,
    max_repeat: int = 50,
    tolerance: float = 1e-8,
) -> list[int] | None:
    """Return small diagonal repeats satisfying diag(n).T @ q = integer."""
    q = np.asarray(qpoint, dtype=float)
    if q.shape != (3,) or not np.isfinite(q).all():
        raise ValueError("qpoint must contain three finite reciprocal coordinates.")
    if max_repeat < 1:
        raise ValueError("max_repeat must be a positive integer.")
    repeats: list[int] = []
    for value in q:
        reduced = float(value - np.rint(value))
        if abs(reduced) <= tolerance:
            repeats.append(1)
            continue
        fraction = Fraction(reduced).limit_denominator(int(max_repeat))
        if abs(float(fraction) - reduced) > tolerance:
            return None
        repeats.append(int(fraction.denominator))
    if not qpoint_commensurability(q, repeats, tolerance=tolerance)["commensurate"]:
        return None
    return repeats


def _gamma_nac_directions(qpoints: np.ndarray, tolerance: float = 1e-10):
    """Return an adjacent path direction for each reciprocal-lattice Gamma point."""
    directions: list[list[float] | None] = [None] * len(qpoints)
    for index, qpoint in enumerate(qpoints):
        reduced = qpoint - np.rint(qpoint)
        if float(np.linalg.norm(reduced)) > tolerance:
            continue
        direction = None
        if index + 1 < len(qpoints):
            candidate = qpoints[index + 1] - qpoint
            if float(np.linalg.norm(candidate)) > tolerance:
                direction = candidate
        if direction is None and index > 0:
            candidate = qpoint - qpoints[index - 1]
            if float(np.linalg.norm(candidate)) > tolerance:
                direction = candidate
        if direction is not None:
            directions[index] = np.asarray(direction, dtype=float).tolist()
    return directions


def phonon_band_structure(
    model: PhononModel,
    *,
    reference_distance: float = 0.08,
    symprec: float = 1e-5,
    angle_tolerance: float = -1.0,
    with_time_reversal: bool = True,
    max_frequency_values: int = 500_000,
) -> dict[str, Any]:
    """Calculate an HPKOT phonon dispersion in the model primitive basis."""
    if not model.has_force_constants:
        raise ValueError(
            "A phonon band structure requires loaded force constants. Generate "
            "finite-displacement forces and load the completed phonopy project first."
        )
    if not np.isfinite(reference_distance) or not 0.005 <= reference_distance <= 1.0:
        raise ValueError("reference_distance must be between 0.005 and 1.0 1/Angstrom.")
    if not np.isfinite(symprec) or symprec <= 0:
        raise ValueError("symprec must be a positive finite length in Angstrom.")
    if int(max_frequency_values) < 1:
        raise ValueError("max_frequency_values must be positive.")

    seekpath = _seekpath_api()
    primitive = model.phonon.primitive
    primitive_cell = np.asarray(primitive.cell, dtype=float)
    structure = (
        primitive_cell,
        np.asarray(primitive.scaled_positions, dtype=float),
        np.asarray(primitive.numbers, dtype=int),
    )

    spacing = float(reference_distance)
    explicit = None
    band_count = 3 * len(primitive)
    for _ in range(4):
        explicit = seekpath.get_explicit_k_path(
            structure,
            with_time_reversal=bool(with_time_reversal),
            reference_distance=spacing,
            symprec=float(symprec),
            angle_tolerance=float(angle_tolerance),
        )
        qpoint_count = len(explicit["explicit_kpoints_abs"])
        value_count = qpoint_count * band_count
        if value_count <= int(max_frequency_values):
            break
        spacing = min(1.0, spacing * value_count / int(max_frequency_values))
    else:  # pragma: no cover - defensive; the final explicit path is checked below
        explicit = None
    if explicit is None:
        raise ValueError("SeeK-path could not construct an explicit reciprocal path.")
    if len(explicit["explicit_kpoints_abs"]) * band_count > int(max_frequency_values):
        raise ValueError(
            "The requested band plot is too large for an interactive response. "
            "Increase reference_distance or use a smaller primitive cell."
        )

    reciprocal_model = 2.0 * np.pi * np.linalg.inv(primitive_cell).T
    qpoints_absolute = np.asarray(explicit["explicit_kpoints_abs"], dtype=float)
    qpoints_model = qpoints_absolute @ np.linalg.inv(reciprocal_model)
    qpoints_model[np.abs(qpoints_model) < 1e-13] = 0.0
    linear_coordinates = np.asarray(
        explicit["explicit_kpoints_linearcoord"], dtype=float
    )
    labels = [str(value) for value in explicit["explicit_kpoints_labels"]]
    explicit_segments = [
        (int(start), int(stop))
        for start, stop in explicit["explicit_segments"]
    ]
    paths = [qpoints_model[start:stop] for start, stop in explicit_segments]
    band_structure = model.phonon.run_band_structure(
        paths,
        with_eigenvectors=False,
        is_band_connection=False,
    )

    segments = []
    all_frequencies = []
    for segment_index, ((start, stop), frequencies) in enumerate(
        zip(explicit_segments, band_structure.frequencies, strict=True)
    ):
        segment_qpoints = qpoints_model[start:stop]
        segment_frequencies = np.asarray(frequencies, dtype=float)
        if segment_frequencies.shape != (len(segment_qpoints), band_count):
            raise RuntimeError("Phonopy returned an inconsistent band-structure shape.")
        all_frequencies.append(segment_frequencies)
        segments.append(
            {
                "index": segment_index,
                "start_label": labels[start],
                "end_label": labels[stop - 1],
                "distances": linear_coordinates[start:stop].tolist(),
                "qpoints": segment_qpoints.tolist(),
                "frequencies": segment_frequencies.tolist(),
                "nac_directions": _gamma_nac_directions(segment_qpoints),
                "suggested_dimensions": [
                    _suggest_diagonal_supercell(qpoint)
                    for qpoint in segment_qpoints
                ],
            }
        )

    ticks: list[dict[str, Any]] = []
    for segment in segments:
        for distance, label in (
            (segment["distances"][0], segment["start_label"]),
            (segment["distances"][-1], segment["end_label"]),
        ):
            if ticks and abs(float(ticks[-1]["distance"]) - float(distance)) <= 1e-10:
                current = str(ticks[-1]["label"])
                if label and label not in current.split("|"):
                    ticks[-1]["label"] = f"{current}|{label}" if current else label
            else:
                ticks.append({"distance": float(distance), "label": str(label)})

    frequency_array = np.concatenate(all_frequencies, axis=0)
    return {
        "status": "ok",
        "convention": "HPKOT",
        "path_source": "SeeK-path",
        "spacegroup_number": int(explicit["spacegroup_number"]),
        "spacegroup_international": str(explicit["spacegroup_international"]),
        "bravais_lattice": str(explicit["bravais_lattice"]),
        "reference_distance": spacing,
        "distance_unit": "1/Angstrom",
        "frequency_unit": "THz",
        "band_count": band_count,
        "qpoint_count": int(sum(len(segment["qpoints"]) for segment in segments)),
        "frequency_min": float(np.min(frequency_array)),
        "frequency_max": float(np.max(frequency_array)),
        "has_imaginary": bool(np.any(frequency_array < -1e-8)),
        "ticks": ticks,
        "segments": segments,
    }


def phonon_modes_at_q(
    model: PhononModel,
    qpoint: Sequence[float],
    *,
    nac_direction: Sequence[float] | None = None,
    projection_direction: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Calculate frequencies, eigenvectors, and polarization summaries at q."""
    if not model.has_force_constants:
        raise ValueError(
            "Physical phonon modes require force constants. Generate displacement "
            "structures, calculate their forces, and load the completed phonopy project."
        )
    q = np.asarray(qpoint, dtype=float)
    if q.shape != (3,) or not np.isfinite(q).all():
        raise ValueError("qpoint must contain three finite reciprocal coordinates.")
    result = model.phonon.run_qpoints(
        [q],
        with_eigenvectors=True,
        nac_q_direction=nac_direction,
    )
    frequencies = np.asarray(result.frequencies[0], dtype=float)
    eigenvectors = np.asarray(result.eigenvectors[0], dtype=complex)
    primitive = model.phonon.primitive
    reciprocal = 2 * np.pi * np.linalg.inv(np.asarray(primitive.cell, dtype=float)).T
    q_cart = q @ reciprocal
    alignment = np.asarray(model.cartesian_transform, dtype=float)
    q_cart = q_cart @ alignment
    q_norm = float(np.linalg.norm(q_cart))
    projection = None
    if projection_direction is not None:
        projection = np.asarray(projection_direction, dtype=float)
        if projection.shape != (3,) or not np.isfinite(projection).all():
            raise ValueError("projection_direction must contain three finite values.")
        projection_norm = float(np.linalg.norm(projection))
        if projection_norm <= 1e-12:
            raise ValueError("projection_direction must be non-zero.")
        projection = projection / projection_norm
    bands = []
    atom_count = len(primitive)
    for band_index, frequency in enumerate(frequencies):
        vector = eigenvectors[:, band_index].reshape(atom_count, 3) @ alignment
        weights = np.sum(np.abs(vector) ** 2, axis=1)
        cartesian_weight = np.sum(np.abs(vector) ** 2, axis=0)
        dominant_axis = "xyz"[int(np.argmax(cartesian_weight))]
        longitudinal_fraction = None
        if q_norm > 1e-12:
            direction = q_cart / q_norm
            longitudinal = np.sum(np.abs(vector @ direction) ** 2)
            total = np.sum(np.abs(vector) ** 2)
            longitudinal_fraction = float(longitudinal / total) if total else 0.0
        directional_fraction = None
        if projection is not None:
            directional = np.sum(np.abs(vector @ projection) ** 2)
            total = np.sum(np.abs(vector) ** 2)
            directional_fraction = float(directional / total) if total else 0.0
        bands.append(
            {
                "band": band_index + 1,
                "frequency_thz": float(frequency),
                "imaginary": bool(frequency < 0),
                "dominant_axis": dominant_axis,
                "longitudinal_fraction": longitudinal_fraction,
                "directional_fraction": directional_fraction,
                "dominant_atom": int(np.argmax(weights)),
                "participation": weights.real.tolist(),
                "eigenvector_real": vector.real.tolist(),
                "eigenvector_imag": vector.imag.tolist(),
            }
        )
    return {
        "status": "ok",
        "qpoint": q.tolist(),
        "band_count": len(bands),
        "frequency_unit": "THz",
        "projection_direction": (
            projection.tolist()
            if projection is not None
            else None
        ),
        "bands": bands,
    }


def generate_mode_trajectory(
    model: PhononModel,
    *,
    qpoint: Sequence[float],
    band: int,
    amplitude: float,
    phase_degrees: float = 0.0,
    dimension: Sequence[int] | Sequence[Sequence[int]] = (1, 1, 1),
    frames: int = 24,
    oscillation: bool = True,
    nac_direction: Sequence[float] | None = None,
) -> tuple[list[Atoms], dict[str, Any]]:
    """Generate frozen-mode structure(s) using phonopy's modulation convention."""
    if not model.has_force_constants:
        raise ValueError(
            "Frozen-phonon mode deformation requires force constants and eigenvectors."
        )
    if not np.isfinite(amplitude) or amplitude < 0:
        raise ValueError("Mode amplitude must be a non-negative finite value.")
    q = np.asarray(qpoint, dtype=float)
    matrix = _integer_matrix(dimension)
    commensurability = qpoint_commensurability(q, matrix)
    if not commensurability["commensurate"]:
        raise ValueError(
            "The selected q-point is not commensurate with the requested supercell: "
            f"P.T @ q residual is {commensurability['residual']}."
        )
    mode_data = phonon_modes_at_q(model, q, nac_direction=nac_direction)
    band_index = int(band) - 1
    if band_index < 0 or band_index >= mode_data["band_count"]:
        raise ValueError(f"band must be between 1 and {mode_data['band_count']}.")
    image_count = max(1, min(240, int(frames)))
    phases = (
        float(phase_degrees) + np.linspace(0.0, 360.0, image_count, endpoint=False)
        if oscillation and image_count > 1
        else np.asarray([float(phase_degrees)])
    )
    output = []
    for phase in phases:
        modulation = model.phonon.run_modulations(
            dimension=matrix,
            phonon_modes=[[q.tolist(), band_index, float(amplitude), float(phase)]],
            nac_q_direction=nac_direction,
        )
        structure = modulation.modulated_supercells[0]
        reference_scaled_positions = np.asarray(
            modulation.supercell.scaled_positions,
            dtype=float,
        )
        frame = phonopy_to_ase(
            structure,
            labels=model.unit_labels,
            unit_indices=_supercell_unit_indices(modulation),
            cartesian_transform=model.cartesian_transform,
            cartesian_shift=model.cartesian_shift,
            reference_scaled_positions=reference_scaled_positions,
        )
        frame.info["v_ase_phonon_mode"] = {
            "qpoint": q.tolist(),
            "band": band_index + 1,
            "frequency_thz": mode_data["bands"][band_index]["frequency_thz"],
            "amplitude": float(amplitude),
            "phase_degrees": float(phase),
            "dimension": matrix.tolist(),
            "coordinates_unwrapped": True,
        }
        output.append(frame)
    return output, {
        "status": "ok",
        "qpoint": q.tolist(),
        "band": band_index + 1,
        "frequency_thz": mode_data["bands"][band_index]["frequency_thz"],
        "imaginary": mode_data["bands"][band_index]["imaginary"],
        "amplitude": float(amplitude),
        "phase_degrees": [float(value) for value in phases],
        "frame_count": len(output),
        "dimension": matrix.tolist(),
        "commensurability": commensurability,
        "normalization": "phonopy modulation convention",
        "coordinates_unwrapped": True,
    }


__all__ = [
    "PhononDependencyError",
    "PhononModel",
    "ase_to_phonopy",
    "create_phonon_model",
    "generate_finite_displacements",
    "generate_mode_trajectory",
    "load_phonon_model",
    "phonon_band_structure",
    "phonon_modes_at_q",
    "phonopy_to_ase",
    "qpoint_commensurability",
    "validate_phonon_model_for_atoms",
]
