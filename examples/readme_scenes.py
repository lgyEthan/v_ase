"""Generate and open the v_ase README/demo scenes.

These are the structures used for the README screenshots and GIFs. The default
output format is ASE ``.traj`` because it preserves constraints such as
FixedLine, FixedPlane, and Hookean.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import bulk, fcc111, nanotube
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from ase.io import write


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "examples" / "readme_scene_assets"


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
    raise KeyError(name)


SCENE_NAMES = ("fixedline", "fixedplane", "hookean", "ferrocene", "showcase")
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
        static_atoms, info = build_scene(name)
        static_path = out_dir / info.static_file
        write(static_path, static_atoms)
        written.append(static_path)

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
