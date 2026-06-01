"""Capture README screenshots and GIFs from local v_ase scenes."""

from __future__ import annotations

import math
import os
from io import BytesIO
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import fcc111, nanotube
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from PIL import Image
from playwright.sync_api import sync_playwright

from tests.manual_showcase import make_frames
from v_ase import view_edit


ROOT = Path(__file__).resolve().parents[1]


def parse_media_size(value: str | None, default: tuple[int, int]) -> tuple[int, int]:
    if not value:
        return default
    try:
        width, height = value.lower().split("x", 1)
        return int(width), int(height)
    except ValueError:
        return default


def configured_asset_dir() -> Path:
    value = os.environ.get("V_ASE_README_ASSET_DIR")
    if not value:
        return ROOT / "docs" / "assets"
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


ASSET_DIR = configured_asset_dir()
MEDIA_SIZE = parse_media_size(os.environ.get("V_ASE_README_MEDIA_SIZE"), (1920, 1080))


def open_panels(page, panels):
    page.evaluate(
        """(panels) => {
            const openSet = new Set(panels);
            document.querySelectorAll('#inspector details').forEach((details) => {
                const key = details.dataset.panel || details.id;
                details.open = openSet.has(key);
            });
        }""",
        panels,
    )


def set_display(page, options):
    page.evaluate(
        """(options) => {
            const app = window.__V_ASE_APP__;
            if (app.applyDesignSettings) {
                app.applyDesignSettings({ display: options }, { render: true });
            } else {
                app.state.display = { ...app.state.display, ...options };
                app.renderer.setDisplayOptions(app.state.display);
                app.updateUI();
            }
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }""",
        options,
    )


def set_selection(page, indices):
    page.evaluate(
        """(indices) => {
            const app = window.__V_ASE_APP__;
            app.state.selected = new Set(indices);
            app.updateSelectionVisuals();
            app.renderer.syncConstraintGuides();
            app.updateUI();
        }""",
        indices,
    )


def enter_mode(page, mode, axis=None):
    page.evaluate(
        """({ mode, axis }) => {
            const app = window.__V_ASE_APP__;
            app.enterTransformMode(mode);
            if (axis) app.transform.setAxis(axis, app.renderer.camera);
            app.updateUI();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }""",
        {"mode": mode, "axis": axis},
    )


def set_camera(page, *, target, position, up=(0, 0, 1), fov=38):
    page.evaluate(
        """({ target, position, up, fov }) => {
            const app = window.__V_ASE_APP__;
            const camera = app.renderer.camera;
            camera.fov = fov;
            camera.up.set(up[0], up[1], up[2]);
            camera.position.set(position[0], position[1], position[2]);
            app.renderer.controls.target.set(target[0], target[1], target[2]);
            camera.lookAt(app.renderer.controls.target);
            camera.updateProjectionMatrix();
            app.renderer.syncSelectionOutlines();
            app.renderer.syncConstraintGuides();
            app.renderer.syncLockMarkers();
            app.renderer.updateHookeanPositions();
            app.transform?.updateGuides?.(camera);
            app.renderer.renderer.render(app.renderer.scene, camera);
        }""",
        {"target": target, "position": position, "up": up, "fov": fov},
    )
    page.wait_for_timeout(250)


def settle_view(page, *, target=None, position=None, fov=38):
    page.evaluate(
        """() => {
            const app = window.__V_ASE_APP__;
            app.renderer.fitCameraToStructure();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }"""
    )
    page.wait_for_timeout(400)
    if target is not None and position is not None:
        set_camera(page, target=target, position=position, fov=fov)


def update_positions(page, positions):
    page.evaluate(
        """(positions) => {
            const app = window.__V_ASE_APP__;
            app.state.atoms.positions = positions.map((p) => [...p]);
            app.renderer.updatePositions(positions);
            app.renderer.syncSelectionOutlines();
            app.renderer.syncConstraintGuides();
            app.renderer.updateHookeanPositions();
            app.updateUI();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }""",
        [[float(v) for v in row] for row in positions],
    )


def screenshot_frame(page) -> Image.Image:
    raw = page.screenshot(type="png")
    image = Image.open(BytesIO(raw)).convert("RGB")
    if image.size != MEDIA_SIZE:
        image = image.resize(MEDIA_SIZE, Image.Resampling.LANCZOS)
    return image


def save_gif(frames: list[Image.Image], path: Path, duration=85):
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=False,
        disposal=2,
    )


def capture_animation(page, path: Path, position_frames: list[np.ndarray], duration=85):
    frames = []
    for positions in position_frames:
        update_positions(page, positions)
        page.wait_for_timeout(35)
        frames.append(screenshot_frame(page))
    save_gif(frames, path, duration=duration)


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
        [x0 + 0.35, y0 + 0.25, top_z + 1.55],  # mobile ion in the surface plane
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

    # Ethanol-like adsorbate: the Hookean constraint keeps the C-O bond from
    # over-stretching while the hydroxyl group is pulled away from the surface.
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
    ads_positions = (base + rel_positions).tolist()
    atoms = slab + Atoms(ads_symbols, positions=ads_positions)
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
    return atoms, {
        "carbon": carbon,
        "oxygen": oxygen,
        "hydroxyl_h": hydroxyl_h,
        "top_z": top_z,
        "center": [x0, y0, top_z],
    }


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


def open_scene(browser, atoms_or_frames, *, show_bonds=False):
    editor = view_edit(
        atoms_or_frames,
        block=False,
        show_cell=True,
        show_axes=True,
        show_bonds=show_bonds,
        respect_constraints=True,
        allow_relax=False,
    )
    url = f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}"
    page = browser.new_page(
        viewport={"width": MEDIA_SIZE[0], "height": MEDIA_SIZE[1]},
        device_scale_factor=1,
    )
    page.goto(url)
    page.wait_for_function("window.__V_ASE_APP__ && window.__V_ASE_APP__.state.atoms")
    return editor, page


def sinusoidal_frames(base: np.ndarray, index: int, delta_fn, count=34) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        phase = math.sin(2 * math.pi * step / count)
        positions = base.copy()
        positions[index] = base[index] + np.asarray(delta_fn(phase), dtype=float)
        frames.append(positions)
    return frames


def plane_sweep_frames(base: np.ndarray, index: int, count=38) -> list[np.ndarray]:
    offsets = [
        np.array([-1.25, -0.65, 0.0]),
        np.array([1.25, -0.45, 0.0]),
        np.array([0.95, 0.90, 0.0]),
        np.array([-1.10, 0.72, 0.0]),
        np.array([-1.25, -0.65, 0.0]),
    ]
    frames = []
    for step in range(count):
        t = step / max(1, count - 1)
        scaled = t * (len(offsets) - 1)
        seg = min(int(scaled), len(offsets) - 2)
        local = scaled - seg
        smooth = 0.5 - 0.5 * math.cos(math.pi * local)
        positions = base.copy()
        positions[index] = base[index] + offsets[seg] * (1 - smooth) + offsets[seg + 1] * smooth
        frames.append(positions)
    return frames


def hookean_frames(base: np.ndarray, index: int, start: np.ndarray, end: np.ndarray, count=38) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        t = 0.5 - 0.5 * math.cos(2 * math.pi * step / count)
        positions = base.copy()
        positions[index] = start * (1 - t) + end * t
        frames.append(positions)
    return frames


def hookean_group_frames(base: np.ndarray, indices: list[int], delta: np.ndarray, count=42) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        t = 0.5 - 0.5 * math.cos(2 * math.pi * step / count)
        positions = base.copy()
        for idx in indices:
            positions[idx] = base[idx] + delta * t
        frames.append(positions)
    return frames


def ferrocene_rotate_frames(base: np.ndarray, indices: list[int], count=46) -> list[np.ndarray]:
    frames = []
    pivot = np.array([0.0, 0.0, 0.0])
    for step in range(count):
        angle = math.radians(95) * math.sin(2 * math.pi * step / count)
        ca, sa = math.cos(angle), math.sin(angle)
        rot = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]], dtype=float)
        positions = base.copy()
        for idx in indices:
            positions[idx] = pivot + rot @ (base[idx] - pivot)
        frames.append(positions)
    return frames


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    import webbrowser

    original_open = webbrowser.open
    webbrowser.open = lambda *args, **kwargs: True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            editor, page = open_scene(browser, make_frames(), show_bonds=True)
            settle_view(page, target=[5.6, 5.0, 2.2], position=[17.0, -12.5, 10.0], fov=40)
            open_panels(page, ["structure-info", "selection", "view", "trajectory-panel"])
            page.screenshot(path=ASSET_DIR / "readme_overview.png")
            page.close()
            editor.close()

            fixedline_atoms, line_idx = make_cnt_fixedline_scene()
            editor, page = open_scene(browser, fixedline_atoms, show_bonds=True)
            set_display(page, {"atomRadiusScale": 0.54, "showBonds": True, "showGrid": True})
            set_selection(page, [line_idx["ion"]])
            open_panels(page, ["structure-info", "selection", "view", "transform"])
            settle_view(
                page,
                target=[7.0, 7.0, line_idx["z_length"] * 0.52],
                position=[16.5, -6.2, line_idx["z_length"] * 0.72],
                fov=38,
            )
            page.screenshot(path=ASSET_DIR / "readme_constraints.png")

            base = fixedline_atoms.get_positions()
            set_selection(page, [line_idx["ion"]])
            enter_mode(page, "MOVE", "Z")
            capture_animation(
                page,
                ASSET_DIR / "readme_fixedline.gif",
                sinusoidal_frames(base, line_idx["ion"], lambda phase: [0, 0, 2.2 * phase]),
            )
            page.close()
            editor.close()

            fixedplane_atoms, plane_idx = make_surface_fixedplane_scene()
            editor, page = open_scene(browser, fixedplane_atoms, show_bonds=True)
            set_display(page, {"atomRadiusScale": 0.60, "showBonds": True, "showGrid": True})
            set_selection(page, [plane_idx["ion"]])
            open_panels(page, ["structure-info", "selection", "view", "transform"])
            settle_view(page, target=[5.1, 4.5, 11.6], position=[11.6, -5.5, 17.2], fov=39)
            base = fixedplane_atoms.get_positions()
            set_selection(page, [plane_idx["ion"]])
            enter_mode(page, "MOVE", None)
            capture_animation(
                page,
                ASSET_DIR / "readme_fixedplane.gif",
                plane_sweep_frames(base, plane_idx["ion"]),
            )
            page.close()
            editor.close()

            hookean_atoms, hidx = make_hookean_surface_scene()
            editor, page = open_scene(browser, hookean_atoms, show_bonds=True)
            set_display(page, {
                "atomRadiusScale": 0.54,
                "elementRadii": {"Cu": 0.42, "C": 0.56, "O": 0.60, "H": 0.28},
                "showBonds": True,
                "showGrid": True
            })
            set_selection(page, [])
            open_panels(page, ["structure-info", "selection", "view"])
            base = hookean_atoms.get_positions()
            carbon_pos = base[hidx["carbon"]].copy()
            oxygen_pos = base[hidx["oxygen"]].copy()
            direction = oxygen_pos - carbon_pos
            direction /= np.linalg.norm(direction)
            target = (carbon_pos + oxygen_pos) * 0.5 + np.array([0.15, 0.05, 0.12])
            camera = target + np.array([3.90, -4.70, 2.90])
            settle_view(page, target=target.tolist(), position=camera.tolist(), fov=33)
            active_preview = base.copy()
            preview_delta = direction * 0.62
            active_preview[hidx["oxygen"]] = base[hidx["oxygen"]] + preview_delta
            active_preview[hidx["hydroxyl_h"]] = base[hidx["hydroxyl_h"]] + preview_delta
            update_positions(page, active_preview)
            page.screenshot(path=ASSET_DIR / "readme_hookean.png")
            end = carbon_pos + direction * 2.18
            delta = end - oxygen_pos
            capture_animation(
                page,
                ASSET_DIR / "readme_hookean.gif",
                hookean_group_frames(base, [hidx["oxygen"], hidx["hydroxyl_h"]], delta),
            )
            page.close()
            editor.close()

            ferrocene, fidx = make_ferrocene_scene()
            editor, page = open_scene(browser, ferrocene, show_bonds=True)
            set_display(page, {
                "atomRadiusScale": 0.72,
                "showBonds": True,
                "showGrid": True,
                "rotatePivot": "origin"
            })
            set_selection(page, fidx["top_ring"])
            open_panels(page, ["structure-info", "selection", "transform", "view"])
            settle_view(page, target=[0, 0, 0], position=[6.2, -7.8, 4.6], fov=36)
            enter_mode(page, "ROTATE", "X")
            page.screenshot(path=ASSET_DIR / "readme_rotate.png")
            capture_animation(
                page,
                ASSET_DIR / "readme_ferrocene_rotate_x.gif",
                ferrocene_rotate_frames(ferrocene.get_positions(), fidx["top_ring"]),
                duration=75,
            )
            page.close()
            editor.close()
        finally:
            browser.close()
            webbrowser.open = original_open

    print(f"Wrote README media to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
