"""Generate and open the v_ase README/demo scenes.

These are the structures used for the README screenshots and GIFs. The default
output format is ASE ``.traj`` because it preserves constraints such as
FixedLine, FixedPlane, and Hookean. Literature-derived structure examples also
include portable CIF files.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import (
    bulk,
    fcc111,
    graphene,
    graphene_nanoribbon,
    molecule,
    nanotube,
    surface,
)
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from ase.calculators.singlepoint import SinglePointCalculator
from ase.io import read, write
from ase.optimize import FIRE
from ase.spacegroup import crystal
from ase.units import Bohr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v_ase.repulsion import RepulsionCalculator
from v_ase.io import atom_labels, set_atom_labels
from v_ase.add_atoms import resolve_molecule_density
from v_ase.insertion_regions import build_insertion_domain


DEFAULT_OUT_DIR = ROOT / "examples" / "readme_scene_assets"
PHOSPHORENE_REFERENCE = "https://doi.org/10.1039/C6CP05566D"
PHOSPHORENE_ESI = "https://www.rsc.org/suppdata/c6/cp/c6cp05566d/c6cp05566d1.pdf"
PHOSPHORENE_TWIST_REFERENCE = "https://doi.org/10.1039/C6NR04354B"
PHOSPHORENE_TWIST_ESI = "https://www.rsc.org/suppdata/c6/nr/c6nr04354b/c6nr04354b1.pdf"
PHOSPHORENE_COLOR_REFERENCE = "https://doi.org/10.1038/srep13927"
CU2O_111_REFERENCE = "https://doi.org/10.1039/C8CP06023A"
CU2O_CU_EPITAXY_REFERENCE = "https://doi.org/10.1016/0022-0248(78)90299-3"
CU2O_CU_INTERFACE_REFERENCE = "https://doi.org/10.1021/acs.jpcc.0c04453"
O_CU111_REFERENCE = "https://doi.org/10.1016/S0039-6028(01)01464-9"
PHOSPHORENE_TWIST_DEGREES = 13.85
PHOSPHORENE_SUBLAYER_COLORS = {
    "P_upper": "#6faf68",
    "P_lower": "#8064a2",
}


@dataclass(frozen=True)
class SceneInfo:
    name: str
    description: str
    static_file: str
    selected_indices: tuple[int, ...]
    notes: tuple[str, ...] = ()


def make_cnt_fixedline_scene() -> tuple[Atoms, dict[str, int]]:
    tube = nanotube(8, 0, length=4, bond=1.42)
    tube.positions[:, 0] += 7.0
    tube.positions[:, 1] += 7.0
    z_length = float(tube.cell.lengths()[2])
    tube.cell = [14.0, 14.0, z_length]
    tube.pbc = [False, False, True]
    ion = Atoms("Li", positions=[[7.0, 7.0, z_length * 0.5]])
    atoms = tube + ion
    ion_idx = len(tube)
    atoms.set_constraint(FixedLine(ion_idx, [0, 0, 1]))
    atoms.info["readme_scene"] = "li_in_cnt_fixed_line"
    return atoms, {"ion": ion_idx, "z_length": z_length}


def make_surface_fixedplane_scene() -> tuple[Atoms, dict[str, int]]:
    slab = fcc111("Cu", size=(4, 4, 2), vacuum=7.0, orthogonal=True)
    positions = slab.get_positions()
    top_z = float(np.max(positions[:, 2]))
    center = np.mean(positions, axis=0)
    x0, y0 = float(center[0]), float(center[1])

    ads_symbols = ["Li", "O", "H"]
    ads_positions = [
        [x0 + 0.35, y0 + 0.25, top_z + 1.55],
        [x0 - 1.45, y0 - 0.35, top_z + 1.60],
        [x0 - 2.05, y0 + 0.25, top_z + 2.00],
    ]
    atoms = slab + Atoms(ads_symbols, positions=ads_positions)
    atoms.pbc = [True, True, False]

    ion_idx = len(slab)
    bottom = [i for i, p in enumerate(positions) if p[2] < top_z - 0.5]
    atoms.set_constraint([
        FixAtoms(indices=bottom),
        FixedPlane(ion_idx, [0, 0, 1]),
    ])
    atoms.info["readme_scene"] = "li_on_cu111_fixed_plane"
    return atoms, {"ion": ion_idx}


def make_hookean_surface_scene() -> tuple[Atoms, dict[str, int]]:
    slab = fcc111("Cu", size=(4, 4, 2), vacuum=7.0, orthogonal=True)
    positions = slab.get_positions()
    top_z = float(np.max(positions[:, 2]))
    center = np.mean(positions, axis=0)
    x0, y0 = float(center[0]), float(center[1])

    ads_symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    base = np.array([x0 - 2.25, y0 - 0.25, top_z + 3.15])
    rel_positions = np.array([
        [0.00, 0.00, 0.00],
        [1.52, 0.08, 0.05],
        [2.93, 0.16, 0.08],
        [3.50, 0.88, 0.15],
        [-0.52, 0.93, 0.18],
        [-0.57, -0.50, 0.78],
        [-0.54, -0.42, -0.78],
        [1.63, 0.86, 0.85],
        [1.66, -0.88, -0.70],
    ])
    atoms = slab + Atoms(ads_symbols, positions=(base + rel_positions).tolist())
    atoms.pbc = [True, True, False]
    carbon = len(slab) + 1
    oxygen = len(slab) + 2
    hydroxyl_h = len(slab) + 3
    bottom = [i for i, p in enumerate(positions) if p[2] < top_z - 0.5]
    atoms.set_constraint([
        FixAtoms(indices=bottom),
        Hookean(carbon, oxygen, rt=1.50, k=12.0),
    ])
    atoms.info["readme_scene"] = "cu111_hookean_ethanol_co_bond"
    return atoms, {"carbon": carbon, "oxygen": oxygen, "hydroxyl_h": hydroxyl_h}


def make_ferrocene_scene() -> tuple[Atoms, dict[str, list[int]]]:
    symbols = ["Fe"]
    positions = [[0.0, 0.0, 0.0]]
    carbon_radius = 1.22
    hydrogen_radius = 2.28
    z_ring = 1.65
    top_c, bottom_c, top_h, bottom_h = [], [], [], []

    for ring, z, phase in [("top", z_ring, 0.0), ("bottom", -z_ring, math.pi / 5)]:
        c_indices = []
        h_indices = []
        for i in range(5):
            angle = phase + i * 2 * math.pi / 5
            c_indices.append(len(symbols))
            symbols.append("C")
            positions.append([carbon_radius * math.cos(angle), carbon_radius * math.sin(angle), z])
        for i in range(5):
            angle = phase + i * 2 * math.pi / 5
            h_indices.append(len(symbols))
            symbols.append("H")
            positions.append([hydrogen_radius * math.cos(angle), hydrogen_radius * math.sin(angle), z])
        if ring == "top":
            top_c, top_h = c_indices, h_indices
        else:
            bottom_c, bottom_h = c_indices, h_indices

    atoms = Atoms(symbols=symbols, positions=positions, cell=[7.0, 7.0, 7.0], pbc=False)
    atoms.info["readme_scene"] = "idealized_ferrocene"
    return atoms, {
        "iron": [0],
        "top_ring": top_c + top_h,
        "bottom_ring": bottom_c + bottom_h,
    }


def make_graphene_hbn_commensurate_scene() -> tuple[Atoms, dict[str, list[int]]]:
    # The commensurate search operates on primitive periodic cells.  Keeping
    # the README fixture primitive makes every displayed repetition a result
    # of the proposed integer common cell rather than a pre-repeated input.
    graphene_layer = graphene(formula="C2", a=2.46, size=(1, 1, 1), vacuum=8.0)
    hbn_layer = graphene(formula="BN", a=2.46, size=(1, 1, 1), vacuum=8.0)
    hbn_layer.positions[:, 2] += 3.35
    atoms = graphene_layer + hbn_layer
    atoms.set_cell(graphene_layer.cell)
    atoms.pbc = [True, True, False]
    atoms.info["readme_scene"] = "graphene_hbn_commensurate_rotation"
    return atoms, {
        "graphene": list(range(len(graphene_layer))),
        "hbn": list(range(len(graphene_layer), len(atoms))),
    }


def make_ai_pyridinic_graphene_scene() -> tuple[Atoms, Atoms, dict[str, object]]:
    """Return a deterministic graphene-to-N3-vacancy Li-site editing example."""

    source = graphene(formula="C2", a=2.46, size=(6, 6, 1), vacuum=8.0)
    source.pbc = [True, True, False]
    source.info["readme_scene"] = "ai_graphene_source"

    center = 0.5 * (np.asarray(source.cell[0]) + np.asarray(source.cell[1]))
    center[2] = float(np.mean(source.positions[:, 2]))
    vacancy_index = int(np.argmin(np.linalg.norm(source.positions - center, axis=1)))
    vacancy_position = source.positions[vacancy_index].copy()
    distances = source.get_distances(
        vacancy_index,
        np.arange(len(source)),
        mic=True,
    )
    neighbor_indices_before = [
        int(index)
        for index in np.argsort(distances)
        if int(index) != vacancy_index
    ][:3]

    intermediate = source.copy()
    del intermediate[vacancy_index]
    neighbor_indices_after = [
        index - (1 if index > vacancy_index else 0)
        for index in neighbor_indices_before
    ]
    symbols = intermediate.get_chemical_symbols()
    labels = ["C"] * len(intermediate)
    for index in neighbor_indices_after:
        symbols[index] = "N"
        labels[index] = "N_pyridinic"
    intermediate.set_chemical_symbols(symbols)
    set_atom_labels(intermediate, labels)
    intermediate.info.update({
        "readme_scene": "ai_pyridinic_n3_graphene",
        "generated_from": "ase.build.graphene(formula='C2', a=2.46, size=(6, 6, 1))",
        "edit_summary": "central carbon vacancy with three pyridinic nitrogen neighbors",
    })

    adsorption_height = 2.15
    li_position = vacancy_position + np.array([0.0, 0.0, adsorption_height])
    final = intermediate + Atoms("Li", positions=[li_position])
    set_atom_labels(final, atom_labels(intermediate) + ["Li_site"])
    final.info.update({
        "readme_scene": "ai_pyridinic_n3_li_graphene",
        "generated_from": "ase.build.graphene(formula='C2', a=2.46, size=(6, 6, 1))",
        "edit_summary": (
            "central carbon vacancy with three pyridinic nitrogen neighbors "
            "and a Li atom 2.15 Angstrom above the vacancy"
        ),
    })
    return source, final, {
        "vacancy_index": vacancy_index,
        "vacancy_position": vacancy_position.tolist(),
        "neighbors_before": neighbor_indices_before,
        "neighbors_after": neighbor_indices_after,
        "intermediate": intermediate,
        "li_index": len(intermediate),
        "li_position": li_position.tolist(),
        "adsorption_height_angstrom": adsorption_height,
    }


def make_graphene_pi_volumetric_scene(
    shape: tuple[int, int, int] = (104, 104, 104),
) -> tuple[Atoms, np.ndarray]:
    """Return a graphene flake and a signed, orbital-like pi scalar field.

    The field is generated analytically from alternating carbon-centered pz
    Gaussians. It is a deterministic visualization example rather than a DFT
    wavefunction, and its multi-center variation makes moving plane slices
    visually testable without redistributing electronic-structure data.
    """

    atoms = graphene(formula="C2", a=2.46, size=(4, 3, 1), vacuum=0.0)
    # Decimal cell lengths survive the text precision of the portable Cube
    # writer exactly enough to match the live structure geometry.
    cell = np.diag([17.5, 11.5, 13.0])
    center = 0.5 * np.diag(cell)
    atoms.positions += center - np.mean(atoms.positions, axis=0)
    atoms.set_cell(cell)
    atoms.pbc = True
    set_atom_labels(atoms, [
        "C_pi_A" if index % 2 == 0 else "C_pi_B"
        for index in range(len(atoms))
    ])

    axes = [np.arange(size, dtype=float) / size for size in shape]
    fractional = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)
    values = np.zeros(shape, dtype=np.float32)
    for atom_index, (position, symbol) in enumerate(zip(
        atoms.get_scaled_positions(wrap=True),
        atoms.get_chemical_symbols(),
    )):
        if symbol != "C":
            continue
        delta = fractional - position
        delta -= np.rint(delta)
        cartesian = np.einsum("...i,ij->...j", delta, cell)
        radius_squared = np.einsum(
            "...i,...i->...",
            cartesian,
            cartesian,
        )
        phase = 1.0 if atom_index % 2 == 0 else -1.0
        values += phase * (
            cartesian[..., 2]
            * np.exp(-radius_squared / (2.0 * 0.68**2))
        ).astype(np.float32)

    atoms.info.update({
        "readme_scene": "graphene_signed_pi_isosurface",
        "volumetric_model": "alternating carbon-centered analytic pz Gaussian field",
    })
    return atoms, values


def make_amorphous_cuzr_rdf_scene(
    *,
    seed: int = 20260731,
    count: int = 900,
    cell_length: float = 28.0,
) -> Atoms:
    """Return a deterministic periodic Cu-Zr hard-core amorphous model.

    Random sequential insertion enforces species-dependent short-range
    exclusion while leaving long-range correlations uniform. The resulting
    RDF has a broad first-neighbor peak and approaches the bulk limit g(r)=1.
    """

    rng = np.random.default_rng(seed)
    positions: list[np.ndarray] = []
    symbols: list[str] = []
    minimum_distance = {
        ("Cu", "Cu"): 2.15,
        ("Cu", "Zr"): 2.30,
        ("Zr", "Cu"): 2.30,
        ("Zr", "Zr"): 2.45,
    }
    maximum_trials = max(100_000, count * 5_000)
    trials = 0
    while len(positions) < count and trials < maximum_trials:
        trials += 1
        symbol = "Cu" if rng.random() < 0.64 else "Zr"
        candidate = rng.random(3) * cell_length
        if positions:
            delta = np.asarray(positions) - candidate
            delta -= cell_length * np.rint(delta / cell_length)
            distances = np.linalg.norm(delta, axis=1)
            cutoffs = np.asarray([
                minimum_distance[(symbol, other)]
                for other in symbols
            ])
            if np.any(distances < cutoffs):
                continue
        positions.append(candidate)
        symbols.append(symbol)

    if len(positions) != count:
        raise RuntimeError(
            f"Could not place {count} amorphous atoms after {maximum_trials} trials."
        )

    atoms = Atoms(
        symbols,
        positions=positions,
        cell=[cell_length] * 3,
        pbc=True,
    )
    set_atom_labels(
        atoms,
        ["Cu_glass" if symbol == "Cu" else "Zr_glass" for symbol in symbols],
    )
    atoms.info.update({
        "readme_scene": "amorphous_cuzr_rdf_plateau",
        "model": "deterministic periodic binary hard-core amorphous configuration",
        "random_seed": seed,
    })
    return atoms


def make_copper_oxide_bond_scene() -> tuple[Atoms, dict[str, list[int]]]:
    """Return a top-registered Cu2O(111)/Cu(111) coincidence interface.

    ASE's Cu2O(111) surface cell spans two primitive surface translations.
    Repeating it 3 x 3 therefore produces the 6 x 6 primitive oxide mesh used
    with 7 x 7 Cu(111). The unrelaxed lateral origin is fixed by placing one
    interfacial oxygen directly above a top-layer substrate copper atom.
    """

    copper_lattice = 3.615
    cuprite_lattice = 4.2696
    substrate = fcc111(
        "Cu",
        size=(7, 7, 4),
        a=copper_lattice,
        vacuum=0.0,
        orthogonal=False,
    )
    cuprite = crystal(
        ["Cu", "O"],
        basis=[(0.25, 0.25, 0.25), (0.0, 0.0, 0.0)],
        spacegroup=224,
        cellpar=[
            cuprite_lattice,
            cuprite_lattice,
            cuprite_lattice,
            90.0,
            90.0,
            90.0,
        ],
    )
    oxide = surface(
        cuprite,
        (1, 1, 1),
        layers=2,
        vacuum=0.0,
        periodic=True,
    ).repeat((3, 3, 1))

    oxide_cell = oxide.cell.array.copy()
    unstrained_length = float(np.linalg.norm(oxide_cell[0]))
    oxide_cell[0] = substrate.cell[0]
    oxide_cell[1] = substrate.cell[1]
    oxide.set_cell(oxide_cell, scale_atoms=True)
    in_plane_strain = (
        float(np.linalg.norm(oxide.cell[0])) / unstrained_length - 1.0
    )

    substrate_top = np.flatnonzero(
        np.isclose(
            substrate.positions[:, 2],
            np.max(substrate.positions[:, 2]),
            atol=1e-8,
        )
    )
    oxide_oxygen = np.flatnonzero(
        np.asarray(oxide.get_chemical_symbols()) == "O"
    )
    interfacial_oxygen = oxide_oxygen[
        np.isclose(
            oxide.positions[oxide_oxygen, 2],
            np.min(oxide.positions[oxide_oxygen, 2]),
            atol=1e-8,
        )
    ]
    substrate_anchor = int(
        substrate_top[
            np.argmin(np.linalg.norm(substrate.positions[substrate_top, :2], axis=1))
        ]
    )
    oxide_anchor = int(
        interfacial_oxygen[
            np.argmin(np.linalg.norm(oxide.positions[interfacial_oxygen, :2], axis=1))
        ]
    )
    registry_shift = (
        substrate.positions[substrate_anchor, :2]
        - oxide.positions[oxide_anchor, :2]
    )
    oxide.positions[:, :2] += registry_shift

    interface_gap = 1.85
    oxide.positions[:, 2] += (
        float(np.max(substrate.positions[:, 2]))
        + interface_gap
        - float(np.min(oxide.positions[:, 2]))
    )
    atoms = substrate + oxide
    atoms.positions[:, 2] += 4.0
    cell = substrate.cell.array.copy()
    cell[2] = [0.0, 0.0, float(np.max(atoms.positions[:, 2])) + 7.0]
    atoms.set_cell(cell)
    atoms.pbc = [True, True, False]

    substrate_count = len(substrate)
    labels = ["Cu_substrate"] * substrate_count
    labels.extend(
        "Cu_oxide" if symbol == "Cu" else "O_oxide"
        for symbol in oxide.get_chemical_symbols()
    )
    set_atom_labels(atoms, labels)
    atoms.info.update({
        "readme_scene": "cu2o111_on_cu111_pairwise_bonds",
        "model": (
            "unrelaxed top-registered 6x6 primitive Cu2O(111) mesh "
            "on 7x7 Cu(111)"
        ),
        "ase_surface_repeat": [3, 3, 1],
        "interface_registry": "interfacial O top-anchored coincidence origin",
        "interface_site_context": (
            "DFT relaxation reports unsaturated interfacial O bonded to "
            "substrate Cu at top, bridge, and hollow sites"
        ),
        "interface_anchor_lateral_distance_angstrom": float(
            np.linalg.norm(
                atoms.positions[substrate_count + oxide_anchor, :2]
                - atoms.positions[substrate_anchor, :2]
            )
        ),
        "in_plane_oxide_strain_percent": 100.0 * in_plane_strain,
        "references": [
            CU2O_111_REFERENCE,
            CU2O_CU_EPITAXY_REFERENCE,
            CU2O_CU_INTERFACE_REFERENCE,
        ],
        "bond_display": (
            "Cu_oxide-O_oxide and Cu_substrate-O_oxide enabled; "
            "all Cu-Cu and O-O pairs disabled"
        ),
    })
    return atoms, {
        "substrate_copper": [
            index for index, label in enumerate(labels)
            if label == "Cu_substrate"
        ],
        "oxide_copper": [
            index for index, label in enumerate(labels)
            if label == "Cu_oxide"
        ],
        "oxide_oxygen": [
            index for index, label in enumerate(labels)
            if label == "O_oxide"
        ],
        "interfacial_oxygen": [
            substrate_count + int(index)
            for index in interfacial_oxygen
        ],
        "registry_anchor": [
            substrate_anchor,
            substrate_count + oxide_anchor,
        ],
    }


def make_material_preset_scene() -> tuple[Atoms, dict[str, list[int]]]:
    """Return three identical Cu clusters with distinct material labels."""

    from ase.cluster.icosahedron import Icosahedron

    clusters = []
    groups: dict[str, list[int]] = {}
    labels: list[str] = []
    offset = 0
    for label, x_position in (
        ("Cu_standard", -7.2),
        ("Cu_metal", 0.0),
        ("Cu_rubber", 7.2),
    ):
        cluster = Icosahedron("Cu", 2)
        cluster.positions += np.array([x_position, 0.0, 0.0])
        clusters.append(cluster)
        groups[label] = list(range(offset, offset + len(cluster)))
        labels.extend([label] * len(cluster))
        offset += len(cluster)
    atoms = clusters[0] + clusters[1] + clusters[2]
    atoms.set_cell([24.0, 10.0, 10.0])
    atoms.pbc = False
    set_atom_labels(atoms, labels)
    atoms.info["readme_scene"] = "material_preset_comparison"
    return atoms, groups


def make_cu5o4_appearance_scene() -> tuple[Atoms, dict[str, list[int]]]:
    """Return the supplied Cu surface-oxide model with stable layer groups."""

    source = DEFAULT_OUT_DIR / "cu5o4_surface_appearance.vasp"
    atoms = read(source)
    chemical_symbols = atoms.get_chemical_symbols()
    substrate = [
        index
        for index, (symbol, position) in enumerate(zip(chemical_symbols, atoms.positions))
        if symbol == "Cu" and float(position[2]) < 7.0
    ]
    oxide_copper = [
        index
        for index, (symbol, position) in enumerate(zip(chemical_symbols, atoms.positions))
        if symbol == "Cu" and float(position[2]) >= 7.0
    ]
    oxide_oxygen = [
        index for index, symbol in enumerate(chemical_symbols) if symbol == "O"
    ]
    if len(substrate) != 32 or len(oxide_copper) != 5 or len(oxide_oxygen) != 4:
        raise AssertionError("Unexpected Cu5O4 surface-layer partition.")
    set_atom_labels(
        atoms,
        ["Cu" if symbol == "Cu" else "O_surface_oxide" for symbol in chemical_symbols],
    )
    atoms.info.update({
        "readme_scene": "cu5o4_view_appearance",
        "purpose": "View-mode index label split and nonstructural appearance editing",
    })
    return atoms, {
        "substrate_copper": substrate,
        "oxide_copper": oxide_copper,
        "oxide_oxygen": oxide_oxygen,
    }


def make_random_addition_scene() -> tuple[Atoms, dict[str, object]]:
    """Return a Cu(111) slab with a finite bulk-like O insertion volume."""

    host = fcc111(
        "Cu",
        size=(7, 6, 5),
        a=3.615,
        vacuum=7.0,
        orthogonal=True,
    )
    host.pbc = [True, True, False]
    set_atom_labels(host, ["Cu_surface"] * len(host))
    cell_lengths = host.cell.lengths()
    z_layers = np.unique(np.round(host.positions[:, 2], decimals=6))
    top_z = float(z_layers[-1])
    allow_bounds = [
        0.10 * cell_lengths[0],
        0.90 * cell_lengths[0],
        0.08 * cell_lengths[1],
        0.92 * cell_lengths[1],
        0.5 * (float(z_layers[0]) + float(z_layers[1])),
        0.5 * (float(z_layers[-2]) + top_z),
    ]
    host.info.update({
        "readme_scene": "cu111_bulk_like_oxygen_addition",
        "purpose": "random O insertion through the interior Cu layers followed by pairwise repulsion",
        "coverage_monolayer": 18 / 42,
        "surface_reference": O_CU111_REFERENCE,
    })
    return host, {
        "entries": [{"element": "O", "label": "O_subsurface", "count": 18}],
        "seed": 2021,
        "coverage_monolayer": 18 / 42,
        "allow_region": {
            "id": "bulk-like-insertion-zone",
            "name": "Bulk-like insertion zone",
            "role": "allow",
            "bounds": allow_bounds,
        },
        "surface_reference": O_CU111_REFERENCE,
    }


def make_layered_water_channel_scene() -> tuple[Atoms, dict[str, object]]:
    """Return periodic edge/basal-hydroxylated GO layers and solvent chambers."""

    source = graphene_nanoribbon(7, 3, type="zigzag", sheet=False, vacuum=0.0)
    carbon_x = np.asarray(source.positions[:, 0], dtype=float)
    carbon_y = np.asarray(source.positions[:, 2], dtype=float)
    ribbon_min_x = float(np.min(carbon_x))
    ribbon_max_x = float(np.max(carbon_x))
    chamber_padding = 7.0
    shifted_x = carbon_x - ribbon_min_x + chamber_padding
    length_y = float(source.cell.lengths()[2])
    length_x = float(ribbon_max_x - ribbon_min_x + 2.0 * chamber_padding)
    cell = np.diag([length_x, length_y, 12.0])
    carbon_xy = np.column_stack((shifted_x, carbon_y))
    edge_tolerance = 1e-7
    left_edge = np.flatnonzero(np.isclose(carbon_x, ribbon_min_x, atol=edge_tolerance))
    right_edge = np.flatnonzero(np.isclose(carbon_x, ribbon_max_x, atol=edge_tolerance))
    edge_indices = np.concatenate((left_edge, right_edge))
    edge_index_set = set(edge_indices.tolist())
    left_edge_set = set(left_edge.tolist())
    interior_indices = np.asarray(
        [index for index in range(len(source)) if index not in edge_index_set],
        dtype=int,
    )

    def graphene_oxide_layer(
        z: float,
        layer: str,
        seed: int,
    ) -> tuple[Atoms, list[str], dict[str, object]]:
        carbon = Atoms(
            "C" * len(source),
            positions=np.column_stack((carbon_xy, np.full(len(source), z))),
            cell=cell,
            pbc=True,
        )
        rng = np.random.default_rng(seed)
        basal_indices = np.sort(rng.choice(interior_indices, size=6, replace=False))
        ligand_symbols: list[str] = []
        ligand_positions: list[list[float]] = []

        # Every finite-ribbon edge carbon is hydroxyl-passivated.  The O-H
        # direction is tilted around the C-O bond, rather than drawn collinear.
        for edge_order, index in enumerate(edge_indices):
            carbon_position = carbon.positions[int(index)]
            outward = -1.0 if int(index) in left_edge_set else 1.0
            oxygen = carbon_position + np.array([1.36 * outward, 0.0, 0.0])
            azimuth = 2.0 * math.pi * ((edge_order + 0.37 * seed) % 7) / 7.0
            perpendicular = np.array([0.0, math.cos(azimuth), math.sin(azimuth)])
            oh_direction = (
                0.32 * np.array([outward, 0.0, 0.0])
                + math.sqrt(1.0 - 0.32**2) * perpendicular
            )
            hydrogen = oxygen + 0.97 * oh_direction
            ligand_symbols.extend(["O", "H"])
            ligand_positions.extend([oxygen.tolist(), hydrogen.tolist()])

        # Basal hydroxyls use deterministic random sites and azimuths, so they
        # cover both faces without collapsing into a single crystallographic row.
        for order, index in enumerate(basal_indices):
            direction = 1.0 if rng.random() >= 0.5 else -1.0
            carbon_position = carbon.positions[int(index)]
            oxygen = carbon_position + np.array([0.0, 0.0, 1.42 * direction])
            azimuth = float(rng.uniform(0.0, 2.0 * math.pi))
            lateral = np.array([math.cos(azimuth), math.sin(azimuth), 0.0])
            oh_direction = (
                math.sqrt(1.0 - 0.32**2) * lateral
                + 0.32 * np.array([0.0, 0.0, direction])
            )
            hydrogen = oxygen + 0.97 * oh_direction
            ligand_symbols.extend(["O", "H"])
            ligand_positions.extend([oxygen.tolist(), hydrogen.tolist()])
        ligands = Atoms(ligand_symbols, positions=ligand_positions, cell=cell, pbc=True)
        layer_atoms = carbon + ligands
        labels = (
            [f"C_GO_{layer}"] * len(carbon)
            + [
                value
                for _ in range(len(edge_indices) + len(basal_indices))
                for value in (f"O_GO_{layer}", f"H_GO_{layer}")
            ]
        )
        return layer_atoms, labels, {
            "edge_indices": edge_indices.tolist(),
            "basal_indices": basal_indices.tolist(),
            "basal_xy": carbon_xy[basal_indices].tolist(),
            "hydroxyl_carbon_indices": np.concatenate(
                (edge_indices, basal_indices)
            ).tolist(),
        }

    lower, lower_labels, lower_ligands = graphene_oxide_layer(3.0, "lower", 1207)
    upper, upper_labels, upper_ligands = graphene_oxide_layer(9.0, "upper", 2710)
    channel = lower + upper
    channel.cell = cell
    channel.pbc = True
    set_atom_labels(channel, lower_labels + upper_labels)
    channel.wrap(eps=1e-10)
    channel.info.update({
        "readme_scene": "periodic_graphene_oxide_water",
        "purpose": "exact solvent density outside ligand-wrapped reject regions",
    })
    reject_min_x = float(np.min(shifted_x) - 1.85)
    reject_max_x = float(np.max(shifted_x) + 1.85)
    regions = [
        {
            "id": "lower-go-exclusion",
            "name": "Lower GO exclusion",
            "role": "reject",
            "bounds": [reject_min_x, reject_max_x, 0.0, length_y, 2.0, 4.0],
        },
        {
            "id": "upper-go-exclusion",
            "name": "Upper GO exclusion",
            "role": "reject",
            "bounds": [reject_min_x, reject_max_x, 0.0, length_y, 8.0, 10.0],
        },
    ]
    domain = build_insertion_domain(
        cell=channel.cell.array,
        pbc=channel.pbc,
        regions=regions,
        pbc_aware=True,
    )
    target_density = 1.0
    _, density = resolve_molecule_density(
        [{"name": "H2O", "label": "water", "count": 1, "atom_count": 3}],
        target_density_g_cm3=target_density,
        accessible_volume_angstrom3=domain.volume,
    )
    return channel, {
        "molecules": [{"name": "H2O", "label": "water", "count": 1}],
        "target_density_g_cm3": target_density,
        "expected_molecule_count": density["molecule_count"],
        "actual_density_g_cm3": density["actual_g_cm3"],
        "regions": regions,
        "accessible_volume_angstrom3": domain.volume,
        "interlayer_spacing_angstrom": 6.0,
        "reject_region_thickness_angstrom": 2.0,
        "left_chamber_width_angstrom": reject_min_x,
        "right_chamber_width_angstrom": length_x - reject_max_x,
        "edge_hydroxyls_per_layer": len(edge_indices),
        "basal_hydroxyls_per_layer": len(lower_ligands["basal_indices"]),
        "basal_hydroxyl_sites": {
            "lower": lower_ligands["basal_xy"],
            "upper": upper_ligands["basal_xy"],
        },
        "hydroxyl_carbon_indices": {
            "lower": lower_ligands["hydroxyl_carbon_indices"],
            "upper": upper_ligands["hydroxyl_carbon_indices"],
        },
        "seed": 1207,
        "placement_mode": "random",
        "coordinate_basis": "cartesian",
        "random_orientation": True,
        "rigid_molecules": True,
    }


def make_atom_colorscale_trajectory() -> list[Atoms]:
    """Return a smooth screened-probe force field above a Cu(111) slab.

    The fixed O marker represents an external probe. Its Gaussian-screened
    field acts on every Cu atom, so the stored Cartesian response resolves the
    first, second, and third lateral neighbour shells without one oversized
    reaction-force arrow dominating the visual scale.
    """

    surface = fcc111("Cu", size=(8, 8, 3), vacuum=7.0, orthogonal=True)
    surface_center = np.mean(surface.positions, axis=0)
    top_z = float(np.max(surface.positions[:, 2]))
    frames: list[Atoms] = []
    phases = np.linspace(0.0, 2.0 * math.pi, 14, endpoint=False)
    for frame_index, phase in enumerate(phases):
        probe_position = surface_center + np.array([
            2.35 * math.cos(phase),
            1.85 * math.sin(phase),
            top_z - surface_center[2] + 2.45 + 0.08 * math.sin(2.0 * phase),
        ])
        atoms = surface.copy()
        atoms += Atoms("O", positions=[probe_position])
        set_atom_labels(atoms, ["Cu_surface"] * len(surface) + ["O_probe"])

        probe_index = len(atoms) - 1
        delta = surface.positions - probe_position
        distance = np.linalg.norm(delta, axis=1)
        lateral_distance = np.linalg.norm(delta[:, :2], axis=1)
        depth = top_z - surface.positions[:, 2]
        magnitude = (
            0.22
            * np.exp(-np.square(lateral_distance / 5.2))
            * np.exp(-depth / 5.0)
        )
        directions = delta / np.maximum(distance[:, None], 1e-12)
        surface_forces = directions * magnitude[:, None]
        forces = np.vstack([surface_forces, np.zeros((1, 3), dtype=float)])
        energy = float(np.sum(0.22 * np.exp(-np.square(lateral_distance / 5.2))))
        if np.count_nonzero(np.linalg.norm(surface_forces, axis=1) > 0.01) < 36:
            raise AssertionError("README probe field must visibly resolve multiple neighbour shells.")
        atoms.new_array("forces", forces.copy())
        atoms.calc = SinglePointCalculator(
            atoms,
            energy=energy,
            forces=forces,
        )
        atoms.info["readme_scene"] = "force_consistent_atom_colorscale"
        atoms.info["force_model"] = "Gaussian-screened external probe field"
        atoms.info["force_calculator"] = "analytic external field stored in SinglePointCalculator"
        atoms.info["probe_index"] = probe_index
        atoms.info["frame_index"] = frame_index
        frames.append(atoms)
    return frames


def make_black_phosphorene_unit_cell() -> Atoms:
    """Return the relaxed black-phosphorene cell reported by Villegas et al.

    The supporting information publishes the cell and Cartesian coordinates
    in Bohr. They are converted here without refitting or idealization.
    """

    cell_bohr = np.array([
        [8.628, 0.000, 0.000],
        [0.000, 6.243, 0.000],
        [0.000, 0.000, 51.930],
    ])
    positions_bohr = np.array([
        [0.0010552522, 0.0000356586, 29.9470289674],
        [2.8030439932, 3.1217420556, 29.9470395784],
        [4.3153452296, 3.1217421076, 25.9662853800],
        [7.1173323694, 0.0000357105, 25.96627772033],
    ])
    atoms = Atoms(
        "P4",
        positions=positions_bohr * Bohr,
        cell=cell_bohr * Bohr,
        pbc=[True, True, False],
    )
    atoms.info.update({
        "readme_scene": "black_phosphorene_unit_cell",
        "source_doi": PHOSPHORENE_REFERENCE,
        "source_coordinates": PHOSPHORENE_ESI,
    })
    return atoms


def _rotate_about_x(
    positions: np.ndarray,
    indices: np.ndarray,
    pivot: np.ndarray,
    angle_degrees: float,
) -> np.ndarray:
    rotated = np.asarray(positions, dtype=float).copy()
    angle = math.radians(float(angle_degrees))
    cosine, sine = math.cos(angle), math.sin(angle)
    rotation = np.array([
        [1.0, 0.0, 0.0],
        [0.0, cosine, -sine],
        [0.0, sine, cosine],
    ])
    rotated[indices] = pivot + (rotated[indices] - pivot) @ rotation.T
    return rotated


def _cumulative_phosphorene_twist(
    positions: np.ndarray,
    ridge_ids: np.ndarray,
    ridge_count: int,
    target_twist_degrees: float,
    frame_count: int,
) -> tuple[list[np.ndarray], list[dict[str, object]], list[dict[str, object]]]:
    """Distribute a literature angle over successive puckered ribbon ridges."""

    operations: list[dict[str, object]] = []
    completed = [np.asarray(positions, dtype=float).copy()]
    current = completed[0]
    interval_count = max(0, ridge_count - 1)
    angle_increment = (
        float(target_twist_degrees) / interval_count
        if interval_count
        else 0.0
    )

    # Ridge zero is the fixed reference. Starting at ridge one avoids adding a
    # rigid-body rotation before the actual torsional deformation.
    for ridge_start in range(1, ridge_count):
        selected = np.flatnonzero(ridge_ids >= ridge_start)
        pivot = current[selected].mean(axis=0)
        operations.append({
            "ridge_start": ridge_start,
            "selected_indices": selected.tolist(),
            "pivot": pivot.tolist(),
            "angle_degrees": angle_increment,
            "cumulative_twist_degrees": angle_increment * ridge_start,
        })
        current = _rotate_about_x(
            current,
            selected,
            pivot,
            angle_increment,
        )
        completed.append(current)

    if not operations:
        return [completed[0]], [], []

    frame_positions: list[np.ndarray] = []
    frame_operations: list[dict[str, object]] = []
    progress_values = np.linspace(0.0, float(len(operations)), max(2, int(frame_count)))
    for progress in progress_values:
        if progress >= len(operations):
            operation_index = len(operations) - 1
            fraction = 1.0
            frame = completed[-1].copy()
        else:
            operation_index = min(int(math.floor(progress)), len(operations) - 1)
            fraction = progress - operation_index
            operation = operations[operation_index]
            selected = np.asarray(operation["selected_indices"], dtype=int)
            pivot = np.asarray(operation["pivot"], dtype=float)
            frame = _rotate_about_x(
                completed[operation_index],
                selected,
                pivot,
                angle_increment * fraction,
            )

        operation = operations[operation_index]
        frame_positions.append(frame)
        frame_operations.append({
            "operation_index": operation_index,
            "operation_count": len(operations),
            "ridge_start": operation["ridge_start"],
            "selected_indices": operation["selected_indices"],
            "pivot": operation["pivot"],
            "angle_degrees": float(angle_increment * fraction),
            "angle_increment_degrees": angle_increment,
            "cumulative_twist_degrees": (
                angle_increment * operation_index
                + angle_increment * fraction
            ),
            "target_twist_degrees": float(target_twist_degrees),
        })
    return frame_positions, frame_operations, operations


def make_phosphorene_twist_scene(
    repeat: tuple[int, int, int] = (5, 6, 1),
    target_twist_degrees: float = PHOSPHORENE_TWIST_DEGREES,
    frame_count: int = 19,
) -> tuple[Atoms, Atoms, list[Atoms], dict[str, object]]:
    """Build a compact literature-angle model one puckered ridge at a time."""

    unit = make_black_phosphorene_unit_cell()
    source = unit.repeat(repeat)
    source.pbc = False
    source_positions = source.get_positions()
    ridge_width = float(unit.cell.lengths()[0]) / 2.0
    ridge_count = repeat[0] * 2
    ridge_ids = np.floor((source_positions[:, 0] + 1e-7) / ridge_width).astype(int)
    ridge_ids = np.clip(ridge_ids, 0, ridge_count - 1)
    z_midpoint = float(np.mean(unit.positions[:, 2]))
    sublayer_ids = (source_positions[:, 2] >= z_midpoint).astype(int)
    labels = np.where(sublayer_ids == 1, "P_upper", "P_lower").tolist()
    set_atom_labels(source, labels)

    raw_frames, frame_operations, operations = _cumulative_phosphorene_twist(
        source_positions,
        ridge_ids,
        ridge_count,
        target_twist_degrees,
        frame_count,
    )
    all_positions = np.concatenate([source_positions, raw_frames[-1]], axis=0)
    lower = np.min(all_positions, axis=0)
    upper = np.max(all_positions, axis=0)
    padding = np.array([4.0, 4.5, 4.5])
    shift = padding - lower
    cell_lengths = upper - lower + 2 * padding

    frames: list[Atoms] = []
    for frame_index, positions in enumerate(raw_frames):
        frame = source.copy()
        frame.positions = positions + shift
        frame.cell = np.diag(cell_lengths)
        frame.pbc = False
        frame.new_array("readme_ridge_id", ridge_ids.copy())
        frame.new_array("readme_sublayer_id", sublayer_ids.copy())
        frame.info.update({
            "readme_scene": "phosphorene_cumulative_nanoribbon_manipulation",
            "twist_target_degrees": target_twist_degrees,
            "twist_increment_degrees": (
                target_twist_degrees / max(1, ridge_count - 1)
            ),
            "twist_progress": frame_index / max(1, frame_count - 1),
            "twist_operation": int(frame_operations[frame_index]["operation_index"]) + 1,
            "twist_ridge_start": int(frame_operations[frame_index]["ridge_start"]),
            "source_doi": PHOSPHORENE_REFERENCE,
            "source_coordinates": PHOSPHORENE_ESI,
            "twist_source_doi": PHOSPHORENE_TWIST_REFERENCE,
            "twist_source_data": PHOSPHORENE_TWIST_ESI,
            "color_source_doi": PHOSPHORENE_COLOR_REFERENCE,
        })
        frames.append(frame)

    source = frames[0].copy()
    source.info["readme_scene"] = "phosphorene_nanosheet_source"
    twisted = frames[-1].copy()
    showcase_operation = operations[min(len(operations) - 1, len(operations) // 2)]
    return source, twisted, frames, {
        "selected_ridge": np.flatnonzero(
            ridge_ids == int(showcase_operation["ridge_start"])
        ).tolist(),
        "selected_range": showcase_operation["selected_indices"],
        "ridge_ids": ridge_ids.tolist(),
        "ridge_count": ridge_count,
        "ridge_width_angstrom": ridge_width,
        "sublayer_ids": sublayer_ids.tolist(),
        "sublayer_colors": dict(PHOSPHORENE_SUBLAYER_COLORS),
        "axis": "X",
        "target_twist_degrees": target_twist_degrees,
        "angle_increment_degrees": target_twist_degrees / max(1, ridge_count - 1),
        "ribbon_direction": "armchair",
        "row_definition": "one puckered sublayer ridge per half armchair cell",
        "twist_source_doi": PHOSPHORENE_TWIST_REFERENCE,
        "operations": operations,
        "frame_operations": frame_operations,
    }


def make_crowded_c60_relaxation_scene(
    frame_interval: int = 1,
) -> tuple[Atoms, Atoms, list[Atoms], dict[str, float]]:
    """Run a real repulsive FIRE relaxation from a compressed C60 geometry."""

    atoms = molecule("C60")
    atoms.positions -= atoms.get_center_of_mass()
    atoms.positions *= 0.45
    atoms.cell = [18.0, 18.0, 18.0]
    atoms.center()
    atoms.pbc = False
    atoms.calc = RepulsionCalculator(cutoff_scale=0.7, k_repulsion=4.0)
    frames: list[Atoms] = []

    def snapshot() -> None:
        forces = atoms.get_forces()
        frame = atoms.copy()
        frame.calc = None
        frame.info.update({
            "readme_scene": "crowded_c60_repulsive_relaxation",
            "energy": float(atoms.get_potential_energy()),
            "fmax": float(np.linalg.norm(forces, axis=1).max()),
            "calculator": "v_ase.RepulsionCalculator",
            "cutoff_scale": 0.7,
            "k_repulsion": 4.0,
        })
        frames.append(frame)

    snapshot()
    optimizer = FIRE(atoms, logfile=None)
    optimizer.attach(snapshot, interval=max(1, int(frame_interval)))
    optimizer.run(fmax=0.05, steps=150)
    if not np.allclose(frames[-1].positions, atoms.positions):
        snapshot()

    initial = frames[0].copy()
    initial.info["readme_scene"] = "crowded_c60_initial"
    relaxed = frames[-1].copy()
    relaxed.info["readme_scene"] = "crowded_c60_relaxed"
    return initial, relaxed, frames, {
        "initial_energy": float(frames[0].info["energy"]),
        "final_energy": float(frames[-1].info["energy"]),
        "initial_fmax": float(frames[0].info["fmax"]),
        "final_fmax": float(frames[-1].info["fmax"]),
    }


def make_ethane_measurement_scene() -> tuple[Atoms, dict[str, list[int]]]:
    atoms = molecule("C2H6")
    atoms.cell = [10.0, 10.0, 10.0]
    atoms.center()
    atoms.pbc = False
    atoms.info["readme_scene"] = "ordered_ethane_measurement"
    return atoms, {"ordered_selection": [3, 0, 1, 6]}


def make_showcase_scene() -> tuple[Atoms, dict[str, int]]:
    def constraints():
        return [
            FixAtoms(indices=[0]),
            FixedLine(1, [1, 0, 0]),
            FixedPlane(2, [0, 0, 1]),
            Hookean(1, 2, rt=4.80, k=5.0),
        ]

    def frame(hookean_x: float) -> Atoms:
        atoms = bulk("NaCl", "rocksalt", a=5.64, cubic=True).repeat((2, 2, 1))
        cell_x, cell_y, _ = atoms.cell.lengths()
        atoms.positions[0] = [1.20, 1.20, 1.20]
        atoms.positions[1] = [1.20, 3.20, 2.40]
        atoms.positions[2] = [hookean_x, 3.20, 2.40]
        atoms.positions[3] = [0.12, cell_y - 1.35, 2.40]
        atoms.positions[4] = [cell_x - 0.12, cell_y - 1.35, 2.40]
        atoms.positions[5] = [cell_x + 0.85, 0.65, 1.40]
        atoms.set_constraint(constraints())
        atoms.info["readme_scene"] = "solid_state_all_in_one_showcase"
        atoms.info["hookean_rt_angstrom"] = 4.80
        return atoms

    return frame(6.45), {"fixed_line": 1, "fixed_plane": 2}


def build_scene(name: str) -> tuple[Atoms, SceneInfo]:
    if name == "add-atoms":
        atoms, metadata = make_random_addition_scene()
        entries = metadata["entries"]
        info = SceneInfo(
            name=name,
            description=(
                "Five-layer Cu(111) slab for random O insertion across its bulk-like interior."
            ),
            static_file="cu111_oxygen_add_atoms.traj",
            selected_indices=(),
            notes=(
                (
                    f"Scatter {entries[0]['count']} O_subsurface atoms with random seed 2021 "
                    f"({metadata['coverage_monolayer']:.3f} per top-layer Cu atom)."
                ),
                "The finite Allow region spans the three interior Cu(111) layers.",
                "All Cu coordinates remain unchanged while only inserted O follows pairwise repulsion.",
                f"Surface context: {metadata['surface_reference']}",
            ),
        )
        return atoms, info
    if name == "add-molecules":
        atoms, metadata = make_layered_water_channel_scene()
        info = SceneInfo(
            name=name,
            description=(
                "Periodic edge/basal-hydroxylated graphene oxide with left and right water chambers."
            ),
            static_file="layered_water_channel.traj",
            selected_indices=(),
            notes=(
                (
                    f"Target {metadata['target_density_g_cm3']:.2f} g/cm^3 in the exact "
                    f"{metadata['accessible_volume_angstrom3']:.3f} A^3 solvent domain; "
                    f"{metadata['expected_molecule_count']} H2O molecules are realizable."
                ),
                "Random orientation is Haar-uniform and rigid placement preserves each molecular geometry.",
                "Two 2 A Reject regions cover only the GO planes in a 6 A periodic layered cell.",
                "The expanded x cell leaves distinct left and right solvent chambers.",
            ),
        )
        return atoms, info
    if name == "fixedline":
        atoms, idx = make_cnt_fixedline_scene()
        info = SceneInfo(
            name=name,
            description="Li ion constrained to a FixedLine inside a carbon nanotube channel.",
            static_file="fixedline.traj",
            selected_indices=(idx["ion"],),
            notes=(
                "The short center axis remains visible without selection.",
                "Starting G shows the longer original-position direction guide.",
            ),
        )
        return atoms, info
    if name == "fixedplane":
        atoms, idx = make_surface_fixedplane_scene()
        info = SceneInfo(
            name=name,
            description="Li ion constrained to a FixedPlane over a Cu(111) surface.",
            static_file="fixedplane.traj",
            selected_indices=(idx["ion"],),
            notes=("Select the Li atom to show the FixedPlane guide.",),
        )
        return atoms, info
    if name == "hookean":
        atoms, idx = make_hookean_surface_scene()
        info = SceneInfo(
            name=name,
            description="Ethanol-like adsorbate on Cu(111) with a Hookean C-O bond constraint.",
            static_file="hookean.traj",
            selected_indices=(idx["carbon"], idx["oxygen"], idx["hydroxyl_h"]),
            notes=("Move the O/H group away from the carbon to engage the Hookean spring.",),
        )
        return atoms, info
    if name == "ferrocene":
        atoms, idx = make_ferrocene_scene()
        info = SceneInfo(
            name=name,
            description="Idealized ferrocene scene for rotations around an active Fe atom pivot.",
            static_file="ferrocene.traj",
            selected_indices=tuple(idx["top_ring"] + idx["iron"]),
            notes=(
                "Select the top ring, Shift-select Fe last, choose Active atom, and use R Z or R X.",
            ),
        )
        return atoms, info
    if name == "showcase":
        atoms, idx = make_showcase_scene()
        info = SceneInfo(
            name=name,
            description="Solid-state all-in-one NaCl showcase with FixAtoms, FixedLine, FixedPlane, Hookean, PBC bonds, and wrap test.",
            static_file="showcase.traj",
            selected_indices=(idx["fixed_line"], idx["fixed_plane"]),
            notes=("Use this when you want one compact scene with all major constraint types.",),
        )
        return atoms, info
    if name == "commensurate":
        atoms, idx = make_graphene_hbn_commensurate_scene()
        info = SceneInfo(
            name=name,
            description="Graphene/hBN stack for the periodic commensurate rotation guide.",
            static_file="graphene_hbn_commensurate.traj",
            selected_indices=tuple(idx["hbn"]),
            notes=("Select the hBN layer, press R then Z, and rotate toward a displayed cell match.",),
        )
        return atoms, info
    if name == "ai-edit":
        _, atoms, idx = make_ai_pyridinic_graphene_scene()
        info = SceneInfo(
            name=name,
            description="AI-generated Li site over a pyridinic N3 vacancy in a 6 x 6 ASE graphene sheet.",
            static_file="ai_pyridinic_n3_li_graphene.cif",
            selected_indices=tuple([*idx["neighbors_after"], idx["li_index"]]),
            notes=(
                "The source lattice is generated by ase.build.graphene; no external coordinates are copied.",
                "The AI deletes the central C, converts its three nearest neighbors to N, and adds Li 2.15 Angstrom above the vacancy.",
            ),
        )
        return atoms, info
    if name == "bonding":
        atoms, groups = make_copper_oxide_bond_scene()
        info = SceneInfo(
            name=name,
            description="Coherent Cu2O(111)/Cu(111) interface used to demonstrate label-pair bond control.",
            static_file="cu2o111_on_cu111_pairwise_bonds.traj",
            selected_indices=(),
            notes=(
                "A 3x3 ASE conventional surface repeat gives a 6x6 primitive Cu2O(111) mesh matched to 7x7 Cu(111) with about 1.22 percent in-plane compression.",
                "One interfacial O is registered directly above a top-layer substrate Cu atom before relaxation.",
                "Cu_oxide-O_oxide and Cu_substrate-O_oxide are enabled; Cu-Cu and O-O pairs are disabled.",
                f"The scene contains {len(groups['substrate_copper'])} substrate Cu, "
                f"{len(groups['oxide_copper'])} oxide Cu, and "
                f"{len(groups['oxide_oxygen'])} oxide O atoms.",
            ),
        )
        return atoms, info
    if name == "materials":
        atoms, groups = make_material_preset_scene()
        info = SceneInfo(
            name=name,
            description="Identical Cu13 clusters for Standard, Metal, and Rubber material comparison.",
            static_file="material_presets.traj",
            selected_indices=(),
            notes=(
                "Labels map left-to-right to Standard, Metal, and Rubber.",
                f"Each material group contains {len(next(iter(groups.values())))} Cu atoms.",
            ),
        )
        return atoms, info
    if name == "phosphorene":
        _, atoms, _, idx = make_phosphorene_twist_scene()
        info = SceneInfo(
            name=name,
            description="Short, wide 5 x 6 armchair black-phosphorene ribbon twisted to the paper-reported 13.85 degree model in 9 ridge edits.",
            static_file="phosphorene_twisted_nanoribbon_13p85deg.cif",
            selected_indices=tuple(idx["selected_range"]),
            notes=(
                "The relaxed cell and coordinates come from Villegas et al. (DOI 10.1039/C6CP05566D).",
                "The 13.85 degree H-APNR target comes from Jang et al. (DOI 10.1039/C6NR04354B).",
                "Each selected row is one puckered sublayer ridge, not a full two-ridge unit cell.",
            ),
        )
        return atoms, info
    if name == "relaxation":
        _, atoms, _, _ = make_crowded_c60_relaxation_scene()
        info = SceneInfo(
            name=name,
            description="Compressed C60 relaxed with the built-in repulsive fallback calculator and ASE FIRE.",
            static_file="crowded_c60_relaxed.cif",
            selected_indices=(),
            notes=(
                "This demonstrates clash removal, not a chemically predictive energy model.",
                "Open the trajectory to inspect every optimization step.",
            ),
        )
        return atoms, info
    if name == "measurement":
        atoms, idx = make_ethane_measurement_scene()
        info = SceneInfo(
            name=name,
            description="Ethane with an H-C-C-H ordered selection for distance, angle, and torsion measurement.",
            static_file="ethane_measurement.cif",
            selected_indices=tuple(idx["ordered_selection"]),
            notes=("Select the listed atoms in order to display a1 through a4.",),
        )
        return atoms, info
    raise KeyError(name)


SCENE_NAMES = (
    "add-atoms",
    "add-molecules",
    "phosphorene",
    "commensurate",
    "ai-edit",
    "bonding",
    "materials",
    "fixedline",
    "fixedplane",
    "hookean",
    "relaxation",
    "measurement",
    "ferrocene",
    "showcase",
)
STALE_MOTION_FILES = (
    "amorphous_ga_h_add_atoms.traj",
    "fixedline_motion.traj",
    "fixedplane_motion.traj",
    "hookean_motion.traj",
    "ferrocene_rotate_x_motion.traj",
    "showcase_motion.traj",
    "showcase_first_frame.traj",
    "phosphorene_twisted_nanoribbon_15deg.cif",
    "phosphorene_twist_15deg.traj",
    "phosphorene_twisted_nanoribbon_36deg.cif",
    "phosphorene_twist_36deg.traj",
    "ai_pyridinic_n3_graphene.traj",
    "cu111_oxygen_pairwise_bonds.traj",
)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_scene_assets(out_dir: Path, scene_names: tuple[str, ...] = SCENE_NAMES) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename in STALE_MOTION_FILES:
        stale = out_dir / filename
        if stale.exists():
            stale.unlink()
    written: list[Path] = []
    summary_lines = ["# v_ase README Scene Assets", ""]

    for name in scene_names:
        extra_assets: list[tuple[str, Atoms | list[Atoms]]] = []
        if name == "phosphorene":
            source, static_atoms, frames, idx = make_phosphorene_twist_scene()
            info = SceneInfo(
                name=name,
                description="Short, wide 5 x 6 armchair black-phosphorene ribbon twisted to the paper-reported 13.85 degree model in 9 ridge edits.",
                static_file="phosphorene_twisted_nanoribbon_13p85deg.cif",
                selected_indices=tuple(idx["selected_range"]),
                notes=(
                    "Source coordinates: DOI 10.1039/C6CP05566D.",
                    "Twist model: DOI 10.1039/C6NR04354B, H-APNR theta = 13.85 degrees.",
                    "Each of the 9 trajectory edits starts from the previously committed coordinates and advances by one puckered ridge.",
                ),
            )
            extra_assets = [
                ("phosphorene_nanosheet.cif", source),
                ("phosphorene_twist_13p85deg.traj", frames),
            ]
        elif name == "relaxation":
            initial, static_atoms, frames, metrics = make_crowded_c60_relaxation_scene()
            info = SceneInfo(
                name=name,
                description="Compressed C60 relaxed with the built-in repulsive fallback calculator and ASE FIRE.",
                static_file="crowded_c60_relaxed.cif",
                selected_indices=(),
                notes=(
                    "This is a clash-removal demonstration, not a predictive chemical potential.",
                    f"Energy: {metrics['initial_energy']:.3f} -> {metrics['final_energy']:.3f} eV.",
                ),
            )
            extra_assets = [
                ("crowded_c60_initial.cif", initial),
                ("crowded_c60_relaxation.traj", frames),
            ]
        elif name == "ai-edit":
            source, static_atoms, idx = make_ai_pyridinic_graphene_scene()
            info = SceneInfo(
                name=name,
                description="AI-generated Li site over a pyridinic N3 vacancy in a 6 x 6 ASE graphene sheet.",
                static_file="ai_pyridinic_n3_li_graphene.cif",
                selected_indices=tuple([*idx["neighbors_after"], idx["li_index"]]),
                notes=(
                    "Source generated with ase.build.graphene; no external coordinates are copied.",
                    "The central C is deleted, its three nearest neighbors become N_pyridinic, and Li is added above the vacancy.",
                ),
            )
            extra_assets = [
                ("ai_graphene_source.cif", source),
                ("ai_pyridinic_n3_graphene.cif", idx["intermediate"]),
                ("ai_pyridinic_n3_li_graphene.traj", static_atoms),
            ]
        else:
            static_atoms, info = build_scene(name)
        static_path = out_dir / info.static_file
        write(static_path, static_atoms)
        written.append(static_path)
        for filename, payload in extra_assets:
            extra_path = out_dir / filename
            write(extra_path, payload)
            written.append(extra_path)

        summary_lines.extend([
            f"## {name}",
            "",
            info.description,
            "",
            f"- Static: `{static_path.name}`",
            f"- Suggested selected indices: `{', '.join(map(str, info.selected_indices))}`",
        ])
        if info.notes:
            summary_lines.extend(f"- {note}" for note in info.notes)
        if extra_assets:
            summary_lines.extend(f"- Additional: `{filename}`" for filename, _ in extra_assets)

        summary_lines.extend([
            "",
            "Open command:",
            "",
            f"```bash\nv_ase gui {display_path(static_path)} --show-bonds\n```",
            "",
        ])

    summary = out_dir / "README.md"
    summary.write_text("\n".join(summary_lines), encoding="utf-8")
    written.append(summary)
    return written


def print_written_assets(paths: list[Path], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    print("Wrote v_ase scene assets:")
    for path in paths:
        print(f"  {path}")
    print()
    print("Open them with normal user-facing v_ase commands:")
    print(f"  v_ase gui {display_path(out_dir / 'phosphorene_twisted_nanoribbon_13p85deg.cif')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'crowded_c60_relaxation.traj')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'graphene_hbn_commensurate.traj')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'fixedline.traj')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'fixedplane.traj')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'hookean.traj')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'ferrocene.traj')} --show-bonds")
    print(f"  v_ase gui {display_path(out_dir / 'showcase.traj')} --show-bonds")


def main() -> int:
    paths = write_scene_assets(DEFAULT_OUT_DIR)
    print_written_assets(paths, DEFAULT_OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
