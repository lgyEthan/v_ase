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
from ase.build import bulk, fcc111, graphene, molecule, nanotube
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from ase.io import write
from ase.optimize import FIRE
from ase.units import Bohr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v_ase.repulsion import RepulsionCalculator


DEFAULT_OUT_DIR = ROOT / "examples" / "readme_scene_assets"
PHOSPHORENE_REFERENCE = "https://doi.org/10.1039/C6CP05566D"
PHOSPHORENE_ESI = "https://www.rsc.org/suppdata/c6/cp/c6cp05566d/c6cp05566d1.pdf"


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
        "top_ring": top_c + top_h,
        "bottom_ring": bottom_c + bottom_h,
    }


def make_graphene_hbn_commensurate_scene() -> tuple[Atoms, dict[str, list[int]]]:
    graphene_layer = graphene(formula="C2", a=2.46, size=(6, 6, 1), vacuum=8.0)
    hbn_layer = graphene(formula="BN", a=2.46, size=(6, 6, 1), vacuum=8.0)
    hbn_layer.positions[:, 2] += 3.35
    atoms = graphene_layer + hbn_layer
    atoms.set_cell(graphene_layer.cell)
    atoms.pbc = [True, True, False]
    atoms.info["readme_scene"] = "graphene_hbn_commensurate_rotation"
    return atoms, {
        "graphene": list(range(len(graphene_layer))),
        "hbn": list(range(len(graphene_layer), len(atoms))),
    }


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


def _twist_phosphorene_slices(
    positions: np.ndarray,
    slice_ids: np.ndarray,
    slice_count: int,
    angle_step_degrees: float,
    progress: float,
) -> np.ndarray:
    twisted = np.asarray(positions, dtype=float).copy()
    center_slice = (slice_count - 1) / 2
    for slice_id in range(slice_count):
        indices = np.flatnonzero(slice_ids == slice_id)
        if not len(indices):
            continue
        pivot = positions[indices].mean(axis=0)
        angle = math.radians((slice_id - center_slice) * angle_step_degrees * progress)
        cosine, sine = math.cos(angle), math.sin(angle)
        rotation = np.array([
            [1.0, 0.0, 0.0],
            [0.0, cosine, -sine],
            [0.0, sine, cosine],
        ])
        twisted[indices] = pivot + (positions[indices] - pivot) @ rotation.T
    return twisted


def make_phosphorene_twist_scene(
    repeat: tuple[int, int, int] = (11, 3, 1),
    angle_step_degrees: float = 15.0,
    frame_count: int = 25,
) -> tuple[Atoms, Atoms, list[Atoms], dict[str, object]]:
    """Build a source nanosheet and a uniformly twisted phosphorene ribbon."""

    unit = make_black_phosphorene_unit_cell()
    source = unit.repeat(repeat)
    source.pbc = False
    source_positions = source.get_positions()
    slice_width = float(unit.cell.lengths()[0])
    slice_ids = np.floor((source_positions[:, 0] + 1e-7) / slice_width).astype(int)
    slice_ids = np.clip(slice_ids, 0, repeat[0] - 1)

    raw_frames = [
        _twist_phosphorene_slices(
            source_positions,
            slice_ids,
            repeat[0],
            angle_step_degrees,
            progress,
        )
        for progress in np.linspace(0.0, 1.0, frame_count)
    ]
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
        frame.new_array("readme_slice_id", slice_ids.copy())
        frame.info.update({
            "readme_scene": "phosphorene_twisted_nanoribbon_15deg",
            "twist_step_degrees": angle_step_degrees,
            "twist_progress": frame_index / max(1, frame_count - 1),
            "source_doi": PHOSPHORENE_REFERENCE,
            "source_coordinates": PHOSPHORENE_ESI,
        })
        frames.append(frame)

    source = frames[0].copy()
    source.info["readme_scene"] = "phosphorene_nanosheet_source"
    twisted = frames[-1].copy()
    selected_slice = min(repeat[0] - 1, repeat[0] // 2 + 1)
    selected = np.flatnonzero(slice_ids == selected_slice).tolist()
    return source, twisted, frames, {
        "selected_slice": selected,
        "slice_ids": slice_ids.tolist(),
        "axis": "X",
        "angle_step_degrees": angle_step_degrees,
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
    if name == "fixedline":
        atoms, idx = make_cnt_fixedline_scene()
        info = SceneInfo(
            name=name,
            description="Li ion constrained to a FixedLine inside a carbon nanotube channel.",
            static_file="fixedline.traj",
            selected_indices=(idx["ion"],),
            notes=("Select the Li atom to show the FixedLine guide.",),
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
            description="Idealized ferrocene scene used for X-axis rotate demonstrations.",
            static_file="ferrocene.traj",
            selected_indices=tuple(idx["top_ring"]),
            notes=("Select the top ring and use R X to recreate the rotate interaction.",),
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
    if name == "phosphorene":
        _, atoms, _, idx = make_phosphorene_twist_scene()
        info = SceneInfo(
            name=name,
            description="Literature-derived black-phosphorene sheet twisted by 15 degrees per crystallographic slice.",
            static_file="phosphorene_twisted_nanoribbon_15deg.cif",
            selected_indices=tuple(idx["selected_slice"]),
            notes=(
                "The relaxed cell and coordinates come from Villegas et al. (DOI 10.1039/C6CP05566D).",
                "Use R then X with a slice selected to reproduce the ribbon twist.",
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
    "phosphorene",
    "commensurate",
    "fixedline",
    "fixedplane",
    "hookean",
    "relaxation",
    "measurement",
    "ferrocene",
    "showcase",
)
STALE_MOTION_FILES = (
    "fixedline_motion.traj",
    "fixedplane_motion.traj",
    "hookean_motion.traj",
    "ferrocene_rotate_x_motion.traj",
    "showcase_motion.traj",
    "showcase_first_frame.traj",
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
                description="Literature-derived black-phosphorene sheet twisted by 15 degrees per crystallographic slice.",
                static_file="phosphorene_twisted_nanoribbon_15deg.cif",
                selected_indices=tuple(idx["selected_slice"]),
                notes=(
                    "Source coordinates: DOI 10.1039/C6CP05566D.",
                    "The trajectory records the complete twist from the flat source sheet.",
                ),
            )
            extra_assets = [
                ("phosphorene_nanosheet.cif", source),
                ("phosphorene_twist_15deg.traj", frames),
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
    print(f"  v_ase gui {display_path(out_dir / 'phosphorene_twisted_nanoribbon_15deg.cif')} --show-bonds")
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
