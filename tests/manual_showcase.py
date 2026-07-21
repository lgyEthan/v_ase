"""Manual end-to-end v_ase showcase.

Run this when you want to test the app by hand instead of reading pytest
success output:

    conda run -n python311 python tests/manual_showcase.py

Useful variants:

    conda run -n python311 python tests/manual_showcase.py --no-block
    conda run -n python311 python tests/manual_showcase.py --write-assets
    conda run -n python311 python tests/manual_showcase.py --print-checklist

This single scene intentionally contains:
- A NaCl solid-state supercell with one intentionally displaced atom.
- FixAtoms on atom 0.
- FixedLine on atom 1, movable only along X.
- FixedPlane on atom 2, movable only in the XY plane.
- Hookean between atoms 1 and 2 with rt=4.80 Angstrom.
- A boundary pair across the periodic cell edge for minimum-image bond testing.
- Three trajectory frames: Hookean inactive, threshold, active/far.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from ase import Atoms
from ase.build import bulk
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from ase.io import write

from v_ase import view_edit


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "tests" / "manual_showcase_assets"

CHECKLIST = """\
v_ase manual showcase checklist
===============================

Launch:
  conda run -n python311 python tests/manual_showcase.py

Scene:
  Structure : 2 x 2 x 1 cubic NaCl solid-state supercell.
  Atom 0    : FixAtoms, should not move when apply_constraint is on.
  Atom 1    : FixedLine([1, 0, 0]), can move only along X when constraints are on.
  Atom 2    : FixedPlane([0, 0, 1]), can move only in XY when constraints are on.
  Atoms 1-2: Hookean(rt=4.80 A, k=5.0).
  Atoms 3-4: Boundary pair across periodic X; auto bond should appear by minimum image.
  Atom 5    : Starts outside the unit cell so Wrap Atoms Into Cell is visibly testable.

Manual checks:
  1. Selection feedback
     - Click atoms. Selected atoms should have clear yellow outlines.
     - Select atom 1: FixedLine guide should appear.
     - Select atom 2: FixedPlane guide should appear.

  2. apply_constraint=True transform behavior
     - Keep apply_constraint checked.
     - Press A, then R, then Z, type 90, press Enter.
     - Atom 0 must stay fixed.
     - Atom 1 should only slide along the FixedLine X direction.
     - Atom 2 should stay in the FixedPlane, so Z must not change.

  3. apply_constraint=False free Blender-like editing
     - Uncheck apply_constraint in the right panel.
     - Press A, then R, then Z, type 90, press Enter.
     - Fixed atom and constrained atoms should now move freely.
     - Re-check apply_constraint for the remaining checks.

  4. Hookean visual state
     - Use trajectory controls at the bottom/right panel.
     - Frame 1: Hookean should be inactive with an open latch and blue slack gap.
     - Frame 2: Hookean should be near threshold.
     - Frame 3: Hookean should be active with a closed green latch and continuous spring.
     - The spring must not visually break when atom 2 is far from atom 1.

  5. PBC bond
     - Ensure Show Bonds is checked and Mode is Auto cutoff.
     - Atoms 3 and 4 sit on opposite sides of the periodic X boundary.
     - They should still be bonded through the periodic boundary.
     - Switch Mode to Pairwise cutoff.
     - Confirm Na-Na, Na-Cl, and Cl-Cl rcut rows appear and changing Na-Cl updates bonds.

  6. Supercell
     - Set Supercell to 2 x 1 x 1.
     - First it appears as translucent preview atoms plus repeated unit-cell lines.
     - Click Set Supercell as Cell.
     - The scene should become a larger real editable solid-state cell.

  7. Delete and wrap
     - Select any non-critical atom and press Delete or Backspace.
     - The selected atom should disappear and indices/constraints should update.
     - Click Wrap Atoms Into Cell.
     - Atom 5 should be brought back inside the displayed unit cell.

  8. Export
     - Click Export POSCAR.
     - Click Export ASE Pickle.
     - Click Export Blender.
     - Blender export should download v_ase_blender_scene.py.
     - The script should contain Hookean threshold/gap/marker objects.

  9. Camera
     - Middle mouse drag should rotate without polar angle limits.
     - Shift + middle mouse drag should pan.
     - Mouse wheel should zoom.

  10. Visual quality and modal layering
     - Change Atom smoothness from Auto to Ultra.
     - Toggle Anti-aliasing and confirm viewport quality updates without losing selection.
     - Open Export Image and drag inside the modal; atoms behind it should not be selected.
"""


def _constraints():
    return [
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
        Hookean(1, 2, rt=4.80, k=5.0),
    ]


def make_frame(hookean_x: float) -> Atoms:
    atoms = bulk("NaCl", "rocksalt", a=5.64, cubic=True).repeat((2, 2, 1))
    cell_x, cell_y, _ = atoms.cell.lengths()
    atoms.positions[0] = [1.20, 1.20, 1.20]
    atoms.positions[1] = [1.20, 3.20, 2.40]
    atoms.positions[2] = [hookean_x, 3.20, 2.40]
    atoms.positions[3] = [0.12, cell_y - 1.35, 2.40]
    atoms.positions[4] = [cell_x - 0.12, cell_y - 1.35, 2.40]
    atoms.positions[5] = [cell_x + 0.85, 0.65, 1.40]
    atoms.set_constraint(_constraints())
    atoms.info["v_ase_manual_showcase"] = True
    atoms.info["solid_state_showcase"] = "NaCl_2x2x1"
    atoms.info["hookean_rt_angstrom"] = 4.80
    return atoms


def make_frames() -> list[Atoms]:
    return [
        make_frame(4.40),  # distance 3.20 A, inactive
        make_frame(6.00),  # distance 4.80 A, threshold
        make_frame(6.45),  # distance 5.25 A, active
    ]


def write_assets(frames: list[Atoms]) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    write(ASSET_DIR / "v_ase_manual_showcase.traj", frames)
    write(ASSET_DIR / "v_ase_manual_showcase.extxyz", frames)
    write(ASSET_DIR / "v_ase_manual_showcase_first_frame.vasp", frames[0], format="vasp")
    (ASSET_DIR / "CHECKLIST.md").write_text(CHECKLIST, encoding="utf-8")
    print(f"Wrote manual showcase assets to: {ASSET_DIR}")
    print()
    print("Open the full trajectory from this source tree with:")
    print(f"  conda run -n python311 python -m v_ase.cli gui {ASSET_DIR / 'v_ase_manual_showcase.traj'} --show-bonds")
    print()
    print("After `python -m pip install -e .`, the installed entry point is:")
    print(f"  conda run -n python311 v_ase gui {ASSET_DIR / 'v_ase_manual_showcase.traj'} --show-bonds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open the manual v_ase all-in-one showcase.")
    parser.add_argument("--no-block", action="store_true", help="open the GUI without waiting for session finalization; keep the server alive until Ctrl+C")
    parser.add_argument("--write-assets", action="store_true", help="write .traj/.extxyz/.vasp assets and checklist")
    parser.add_argument("--print-checklist", action="store_true", help="print the manual checklist and exit")
    parser.add_argument("--no-open", action="store_true", help="prepare assets/checklist without opening the GUI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frames = make_frames()

    if args.print_checklist:
        print(CHECKLIST)
        return 0

    if args.write_assets or args.no_open:
        write_assets(frames)

    if args.no_open:
        return 0

    print(CHECKLIST)
    print("Opening v_ase manual showcase...")

    view_kwargs = dict(
        show_cell=True,
        show_axes=True,
        show_bonds=True,
        respect_constraints=True,
        allow_relax=False,
    )

    if args.no_block:
        editor = view_edit(frames, block=False, **view_kwargs)
        print(f"Viewer URL: http://127.0.0.1:{editor.port}/?session_id={editor.session_id}")
        print("Server is kept alive for manual testing. Press Ctrl+C here to stop it.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            editor.close()
        return 0

    view_edit(frames, block=True, **view_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
