"""Inspect saved energies and match atom indices across a trajectory."""

from collections import Counter, deque
import re

import numpy as np
from ase.calculators.calculator import PropertyNotImplementedError
from ase.calculators.singlepoint import SinglePointCalculator
from ase.geometry import find_mic, get_distances
from ase.utils.forcecurve import fit_images
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

from .atom_scalars import atom_force_vectors
from .repulsion import is_vase_repulsion_calculator

MATCH_MODES = ("mic", "cartesian", "soap-translation")
PER_ATOM_RESULTS = {"forces", "charges", "magmoms", "energies", "stresses", "born_effective_charges"}


def trajectory_match_compatible(frames):
    if len(frames) < 2 or not len(frames[0]):
        return False
    composition = Counter(frames[0].numbers)
    return all(Counter(frame.numbers) == composition for frame in frames[1:])


def _species_assignment(groups, costs, size):
    order = np.empty(size, dtype=int)
    for reference, other in groups:
        rows, columns = linear_sum_assignment(costs(reference, other))
        order[reference[rows]] = other[columns]
    return order


def _soap_vectors(descriptor, atoms):
    structure = atoms.copy()
    structure.cell = atoms.cell.complete()
    vectors = descriptor.create(structure)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-15)


def _translation_seeds(reference, moving, descriptor, vectors, groups, mic):
    other = _soap_vectors(descriptor, moving)

    def descriptor_distance(indices, candidates):
        return cdist(vectors[indices], other[candidates], metric="sqeuclidean")

    order = _species_assignment(groups, descriptor_distance, len(reference))
    offsets = mic(reference.positions - moving.positions[order])
    yield offsets.mean(axis=0)
    confidence = np.linalg.norm(vectors - other[order], axis=1)
    for index in np.argsort(confidence, kind="stable")[:16]:
        yield offsets[index]
    # Equivalent local environments can admit several alignments. Include
    # alternative anchors on the rarest species before measuring geometry.
    rare, candidates = min(groups, key=lambda pair: len(pair[0]))
    for anchor in rare[:2]:
        distances = descriptor_distance([anchor], candidates)[0]
        for candidate in candidates[np.argsort(distances, kind="stable")[:16]]:
            yield mic(reference.positions[anchor] - moving.positions[candidate])


def match_trajectory_indices(frames, mode="mic"):
    """Reorder each frame to frame 0, without moving any atom in space."""
    if mode not in MATCH_MODES:
        raise ValueError("Choose minimum image, Cartesian, or SOAP + translation matching.")
    if not trajectory_match_compatible(frames):
        raise ValueError("Matching requires at least two frames with the same element counts.")
    reference = frames[0]
    species = sorted(set(reference.numbers))
    periodic = reference.pbc if mode != "cartesian" else np.zeros(3, dtype=bool)

    def mic(vectors):
        if periodic.any():
            return find_mic(vectors, reference.cell, periodic)[0]
        return vectors

    descriptor = vectors = None
    if mode == "soap-translation":
        try:
            from dscribe.descriptors import SOAP
        except ImportError as exc:
            raise ValueError("SOAP matching requires DScribe. Install v_ase-gui[soap].") from exc
        descriptor = SOAP(species=species, periodic=True, r_cut=5, n_max=4, l_max=4, sigma=0.5)
        vectors = _soap_vectors(descriptor, reference)

    output = [reference]
    for frame in frames[1:]:
        groups = [(np.flatnonzero(reference.numbers == number), np.flatnonzero(frame.numbers == number))
                  for number in species]

        def assign(shift):
            def distances(indices, candidates):
                a = reference.positions[indices]
                b = frame.positions[candidates] + shift
                if periodic.any():
                    distances = get_distances(a, b, cell=reference.cell, pbc=periodic)[1]
                else:
                    distances = cdist(a, b)
                return distances ** 2 if mode == "soap-translation" else distances
            return _species_assignment(groups, distances, len(reference))

        order = assign(np.zeros(3))
        if descriptor is not None:
            def mean_by_species(values):
                return np.mean([values[indices].mean(axis=0) for indices, _ in groups], axis=0)

            def score(residual):
                return mean_by_species(np.sum(residual ** 2, axis=1))

            best_distance = score(mic(reference.positions - frame.positions[order]))
            seen = set()
            for shift in _translation_seeds(reference, frame, descriptor, vectors, groups, mic):
                key = tuple(np.round(shift, decimals=7))
                if key in seen:
                    continue
                seen.add(key)
                for _ in range(3):
                    candidate = assign(shift)
                    residual = mic(reference.positions - frame.positions[candidate] - shift)
                    distance = score(residual)
                    if distance < best_distance - 1e-10:
                        order, best_distance = candidate, distance
                    adjustment = mean_by_species(residual)
                    if np.linalg.norm(adjustment) < 1e-8:
                        break
                    shift = shift + adjustment
        output.append(_reorder_atoms(frame, order))
    return output


def _reorder_atoms(atoms, order):
    if np.array_equal(order, np.arange(len(atoms))):
        return atoms
    reordered = atoms[order]
    if len(reordered.constraints) != len(atoms.constraints):
        raise ValueError("An atom constraint does not support index remapping. The trajectory was preserved.")
    calculator = atoms.calc
    if isinstance(calculator, SinglePointCalculator):
        # Stale single-point values must stay stale after index matching.
        if calculator.check_state(atoms):
            return reordered
        results = {
            key: np.asarray(value)[order] if key in PER_ATOM_RESULTS else value
            for key, value in calculator.results.items()
        }
        calculator = SinglePointCalculator(reordered, **results)
    reordered.calc = calculator
    return reordered


def _finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if np.isfinite(result) else None


def stored_frame_energy(atoms):
    """Read a stored value without evaluating a scientific calculator."""
    if isinstance(atoms.calc, SinglePointCalculator) and atoms.calc.check_state(atoms):
        return None
    if (atoms.calc is not None and not is_vase_repulsion_calculator(atoms.calc)
            and "energy" in getattr(atoms.calc, "results", {})):
        try:
            return _finite(atoms.calc.get_property("energy", atoms, allow_calculation=False))
        except PropertyNotImplementedError:
            return None
    for key in ("energy", "potential_energy", "energy_eV", "potential_energy_eV"):
        if key in atoms.info:
            value = _finite(atoms.info[key])
            if value is not None:
                return value
    return None


def stored_relative_frame_energy(atoms):
    if isinstance(atoms.calc, SinglePointCalculator) and atoms.calc.check_state(atoms):
        return None
    return _finite(atoms.info.get("delta_energy_eV"))


def trajectory_overlay_availability(frames):
    """Find available trajectory properties without building graph or vector arrays."""
    energy = forces = False
    for frame in frames:
        if not energy:
            energy = stored_frame_energy(frame) is not None or stored_relative_frame_energy(frame) is not None
        if not forces and len(frame):
            stale = isinstance(frame.calc, SinglePointCalculator) and frame.calc.check_state(frame)
            if not stale or "forces" in frame.arrays:
                vectors = atom_force_vectors(frame)
                forces = vectors is not None and bool(np.isfinite(vectors).all(axis=1).any())
        if energy and forces:
            break
    return {"energy": energy, "forces": forces}


def _fit_neb_band(frames, values, relative, start, *, mic):
    """Fit a single saved band with ASE, using only cached energy and forces."""
    if len(frames) < 2:
        raise ValueError("An NEB band needs at least two images.")
    if all(value is not None for value in values):
        energies, relative_only = values, False
    elif all(value is not None for value in relative):
        energies, relative_only = relative, True
    else:
        missing = next(index for index, value in enumerate(values) if value is None)
        raise ValueError(f"Frame {start + missing + 1} has no saved energy for the NEB fit.")

    reference = frames[0]
    periodic = np.asarray(reference.pbc)
    images = []
    for index, (frame, energy) in enumerate(zip(frames, energies), start + 1):
        if not np.array_equal(frame.numbers, reference.numbers):
            raise ValueError(f"Frame {index} has a different atom count or element order.")
        if mic and (not np.array_equal(frame.pbc, periodic) or not np.allclose(
            frame.cell.array[periodic], reference.cell.array[periodic], rtol=0, atol=1e-8
        )):
            raise ValueError(f"Frame {index} has different periodic cell vectors.")
        calc = frame.calc
        forces = None
        if calc and not is_vase_repulsion_calculator(calc) and not calc.check_state(frame):
            forces = getattr(calc, "results", {}).get("forces")
        stale = isinstance(calc, SinglePointCalculator) and calc.check_state(frame)
        if forces is None and not stale:
            forces = frame.arrays.get("forces")
        try:
            forces = np.asarray(forces, dtype=float)
        except (TypeError, ValueError):
            forces = np.empty(0)
        if forces.shape != frame.positions.shape or not np.isfinite(forces).all():
            raise ValueError(f"Frame {index} has no valid saved per-atom forces for the NEB fit.")
        image = frame.copy()
        if not mic:
            image.pbc = False
        image.calc = SinglePointCalculator(image, energy=energy, forces=np.asarray(forces))
        images.append(image)

    try:
        with np.errstate(divide="raise", invalid="raise", over="raise"):
            fit = fit_images(images)
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise ValueError("ASE could not fit this band. Check for overlapping or repeated images.") from exc
    if not np.isfinite(fit.fit_energies).all() or not np.isfinite(fit.fit_path).all():
        raise ValueError("ASE could not produce a finite energy curve for this band.")
    tangents = []
    for coordinates, tangent in fit.lines:
        half = float(coordinates[-1] - coordinates[0]) / 2
        if half <= 0 or not np.isfinite(tangent).all():
            raise ValueError("ASE could not produce finite force tangents for this band.")
        tangents.append({"halfWidth": half, "slope": float(tangent[-1] - tangent[0]) / (2 * half)})
    return {
        "start": start,
        "path": list(map(float, fit.path)),
        "fitPath": fit.fit_path.tolist(),
        "fitEnergies": fit.fit_energies.tolist(),
        "values": (np.asarray(fit.energies) + images[0].get_potential_energy()).tolist(),
        "relativeOnly": relative_only,
        "tangents": tangents,
    }


def trajectory_energy_series(frames, *, neb_images=None, neb_mic=True):
    """Use a saved NEB path coordinate when present, otherwise frame number."""
    band = deque(maxlen=neb_images or None) if neb_images is not None else None
    values, path, relative = [], [], []
    for frame in frames:
        values.append(stored_frame_energy(frame))
        path.append(_finite(frame.info.get("path_length_A")))
        relative.append(stored_relative_frame_energy(frame))
        if band is not None:
            band.append(frame)
    has_path = (
        len(path) > 1 and all(value is not None for value in path)
        and path[-1] > path[0] and all(a <= b for a, b in zip(path, path[1:]))
    )
    relative_only = not any(value is not None for value in values)
    result = {
        "values": relative if relative_only else values,
        "path": path if has_path else None,
        "relativeOnly": relative_only,
    }
    if band is not None:
        try:
            if neb_images and neb_images > len(values):
                raise ValueError(f"Only {len(values)} frames are loaded for this NEB band.")
            start = len(values) - len(band)
            result["neb"] = _fit_neb_band(band, values[start:], relative[start:], start, mic=neb_mic)
        except ValueError as exc:
            result["nebError"] = str(exc)
    return result


def normalize_energy_style(style):
    from jsonschema import Draft202012Validator

    from .ai_display_schema import ENERGY_GRAPH_EXTRA_STYLE

    if not isinstance(style, dict):
        raise ValueError("Energy graph style must be an object.")
    result = {}
    for key, fallback in (
        ("line", "#3068b3"), ("marker", "#c3472e"), ("background", "#ffffff"),
        ("fitColor", "#7e63c2"), ("tangentColor", "#368375"),
    ):
        color = style.get(key, fallback)
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError(f"Choose a valid color for {key}.")
        result[key] = color.lower()
    for key, fallback, low, high in (
        ("stroke", 1.75, .75, 5), ("markerSize", 5, 2, 16), ("fitWidth", 2, .5, 8),
        ("tangentWidth", 1, .5, 8), ("tangentScale", 1, .1, 4),
    ):
        value = _finite(style.get(key, fallback))
        if value is None or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        result[key] = value
    patterns = ("solid", "dash", "dot", "dash-dot")
    for key, choices in (
        ("reference", ("first", "absolute")), ("backgroundMode", ("theme", "color", "transparent")),
        ("dataMode", ("line", "line-markers", "markers", "hidden")),
        ("lineStyle", patterns), ("fitLineStyle", patterns),
        ("markerShape", ("circle", "square", "diamond")),
    ):
        value = style.get(key, choices[0])
        if value not in choices:
            raise ValueError(f"Choose one of the available settings for {key}.")
        result[key] = value
    for key in ("grid", "cursor"):
        result[key] = style.get(key, True) is not False
    extra = {key: style[key] for key in ENERGY_GRAPH_EXTRA_STYLE if key in style}
    error = next(Draft202012Validator({"properties": ENERGY_GRAPH_EXTRA_STYLE}).iter_errors(extra), None)
    if error is not None:
        raise ValueError(f"{error.path[0]}: {error.message}")
    result.update(extra)
    return result


def energy_neb_options(overlay):
    """Use the overlay's band length and distance mode for HTML export."""
    neb = overlay.get("neb") if isinstance(overlay, dict) else None
    if not isinstance(neb, dict) or not (neb.get("fit") is True or neb.get("tangents") is True):
        return {}
    images = neb.get("images")
    return {
        "neb_images": images if type(images) is int and images >= 2 else 0,
        "neb_mic": neb.get("mic") is not False,
    }
