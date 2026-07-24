from functools import lru_cache

import numpy as np
from ase.data import chemical_symbols as ase_chemical_symbols, covalent_radii, vdw_radii
from ase.data.colors import jmol_colors
from ase.constraints import FixAtoms, FixCartesian, FixedLine, FixedPlane, FixScaled, Hookean
from v_ase.io import atom_labels

try:
    from ase.gui.defaults import defaults as ase_gui_defaults
except Exception:
    ase_gui_defaults = {}

ASE_GUI_RADIUS_SCALE = float(ase_gui_defaults.get("radii_scale", 0.89))


def _constraint_indices(constraint, natoms):
    if not hasattr(constraint, "index"):
        return []
    index = constraint.index
    if isinstance(index, slice):
        return [int(i) for i in np.arange(natoms)[index]]
    return [int(i) for i in np.atleast_1d(index)]


def _as_float_list(values):
    return [float(v) for v in np.asarray(values, dtype=float).tolist()]


def _nonzero_vector(values, fallback):
    vector = np.asarray(values, dtype=float)
    if vector.shape == (3,) and np.linalg.norm(vector) > 1e-12:
        return vector
    return np.asarray(fallback, dtype=float)


def _fix_scaled_visual_constraint(atoms, constraint):
    """Convert ASE FixScaled masks into Cartesian line/plane display guides.

    FixScaled constrains fractional coordinates. If one fractional coordinate
    is fixed, motion is allowed in the plane spanned by the two remaining cell
    vectors. If two are fixed, motion is allowed along the remaining cell
    vector. If all three are fixed, the atom is visually fixed.
    """
    mask = np.asarray(constraint.mask, dtype=bool)
    if mask.shape != (3,):
        return "fixed", None
    allowed = [axis for axis, fixed in enumerate(mask) if not fixed]
    if len(allowed) == 3:
        return None, None
    if len(allowed) == 0:
        return "fixed", None

    cell = np.asarray(atoms.cell.array, dtype=float)
    fallback_axes = np.eye(3)
    cell_vectors = [
        _nonzero_vector(cell[axis] if cell.shape == (3, 3) else fallback_axes[axis], fallback_axes[axis])
        for axis in range(3)
    ]

    if len(allowed) == 1:
        return "line", _as_float_list(cell_vectors[allowed[0]])

    normal = np.cross(cell_vectors[allowed[0]], cell_vectors[allowed[1]])
    if np.linalg.norm(normal) <= 1e-12:
        fixed_axes = [axis for axis, fixed in enumerate(mask) if fixed]
        normal = fallback_axes[fixed_axes[0]] if fixed_axes else fallback_axes[2]
    return "plane", _as_float_list(normal)


def _ase_gui_jmol_hex(atomic_number):
    number = int(atomic_number)
    if number >= len(jmol_colors):
        return "#CCCCCC"
    rgb = jmol_colors[number]
    channels = [max(0, min(255, int(float(value) * 255))) for value in rgb]
    return "#{:02X}{:02X}{:02X}".format(*channels)


def _ase_gui_radius(atomic_number):
    return float(covalent_radii[int(atomic_number)] * ASE_GUI_RADIUS_SCALE)


def _per_atom_values(atoms, getter, fallback):
    try:
        values = getter()
        if values is not None and len(values) == len(atoms):
            return np.asarray(values).tolist()
    except Exception:
        pass
    return fallback


@lru_cache(maxsize=1)
def _element_visual_defaults():
    colors = {}
    radii = {}
    for number, symbol in enumerate(ase_chemical_symbols):
        if number <= 0 or not symbol:
            continue
        colors[symbol] = _ase_gui_jmol_hex(number)
        radii[symbol] = _ase_gui_radius(number)
    return colors, radii


def atoms_to_json(atoms):
    """
    Rich serialization of ASE Atoms for professional visualization.
    """
    atomic_numbers = atoms.get_atomic_numbers()
    chemical_symbols = atoms.get_chemical_symbols()
    display_symbols = atom_labels(atoms)
    base_colors = [_ase_gui_jmol_hex(number) for number in atomic_numbers]
    cached_element_colors, cached_element_radii = _element_visual_defaults()
    element_colors = dict(cached_element_colors)
    element_radii = dict(cached_element_radii)
    data = {
        "labels": display_symbols,
        # Kept for compatibility with the pre-0.0.78 browser payload.
        "symbols": display_symbols,
        "atom_types": display_symbols,
        "chemical_symbols": chemical_symbols,
        "atomic_numbers": atomic_numbers.tolist(),
        "positions": atoms.get_positions().tolist(),
        "cell": atoms.get_cell().tolist(),
        "pbc": atoms.get_pbc().tolist(),
        "tags": atoms.get_tags().tolist(),
        "charges": _per_atom_values(atoms, atoms.get_initial_charges, [0.0] * len(atoms)),
        "magmoms": _per_atom_values(atoms, atoms.get_initial_magnetic_moments, [0.0] * len(atoms)),
        "forces": [None] * len(atoms),
        "visual": {
            "color_source": "ase.gui.view.View.colors using ase.data.colors.jmol_colors",
            "radius_source": "ase.gui.images.Images.get_radii: ase.data.covalent_radii * 0.89",
            "colors": base_colors,
            "base_colors": base_colors,
            "element_colors": element_colors,
            "element_radii": element_radii,
            "radii": [_ase_gui_radius(number) for number in atomic_numbers],
            "covalent_radii": [_ase_gui_radius(number) for number in atomic_numbers],
            "bond_radii": [float(covalent_radii[int(number)]) for number in atomic_numbers],
            "vdw_radii": [
                None if not np.isfinite(float(vdw_radii[int(number)])) else float(vdw_radii[int(number)])
                for number in atomic_numbers
            ],
            "radius_scale": ASE_GUI_RADIUS_SCALE,
        },
        "constraints": {
            "fixed_indices": [],
            "fixed_cartesian": {},
            "fixed_line": {},
            "fixed_plane": {},
            "hookean": [],
        },
        "metadata": {
            "natoms": len(atoms),
            "units": "angstrom",
            "has_calculator": atoms.calc is not None,
            "calculator": atoms.calc.__class__.__name__ if atoms.calc else None,
        }
    }

    # Extract constraints
    for c in atoms.constraints:
        indices = _constraint_indices(c, len(atoms))
            
        if isinstance(c, FixAtoms):
            data["constraints"]["fixed_indices"].extend([int(i) for i in indices])
        elif isinstance(c, FixCartesian):
            for idx in indices:
                data["constraints"]["fixed_cartesian"][str(idx)] = [bool(v) for v in c.mask.tolist()]
        elif isinstance(c, FixedLine):
            for idx in indices:
                data["constraints"]["fixed_line"][str(idx)] = _as_float_list(c.dir)
        elif isinstance(c, FixedPlane):
            for idx in indices:
                normal = getattr(c, "plane_normal", getattr(c, "dir", None))
                data["constraints"]["fixed_plane"][str(idx)] = _as_float_list(normal)
        elif isinstance(c, FixScaled):
            kind, vector = _fix_scaled_visual_constraint(atoms, c)
            if kind == "fixed":
                data["constraints"]["fixed_indices"].extend([int(i) for i in indices])
            elif kind == "line":
                for idx in indices:
                    data["constraints"]["fixed_line"][str(idx)] = vector
            elif kind == "plane":
                for idx in indices:
                    data["constraints"]["fixed_plane"][str(idx)] = vector
        elif isinstance(c, Hookean):
            item = {
                "spring": float(c.spring),
                "threshold": None if c.threshold is None else float(c.threshold),
                "kind": getattr(c, "_type", "unknown"),
            }
            if c._type == "two atoms":
                item["indices"] = [int(i) for i in c.indices]
            elif c._type == "point":
                item["index"] = int(c.index)
                item["origin"] = _as_float_list(c.origin)
            elif c._type == "plane":
                item["index"] = int(c.index)
                item["plane"] = _as_float_list(c.plane)
            data["constraints"]["hookean"].append(item)

    data["constraints"]["fixed_indices"] = list(set(data["constraints"]["fixed_indices"]))
    
    # Calculator results if converged/available
    if atoms.calc is not None:
        try:
            data["metadata"]["energy"] = float(atoms.get_potential_energy())
        except:
            pass
        try:
            data["forces"] = atoms.get_forces().tolist()
        except:
            pass
    elif "forces" in atoms.arrays:
        data["forces"] = np.asarray(atoms.arrays["forces"], dtype=float).tolist()

    return data
