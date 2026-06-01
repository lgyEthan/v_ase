"""Capture README screenshots and GIFs from local v_ase scenes."""

from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import fcc111
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from PIL import Image
from playwright.sync_api import sync_playwright

from tests.manual_showcase import make_frames
from v_ase import view_edit


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"
GIF_SIZE = (960, 600)


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
            app.state.display = { ...app.state.display, ...options };
            app.renderer.setDisplayOptions(app.state.display);
            app.updateUI();
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
    return image.resize(GIF_SIZE, Image.Resampling.LANCZOS)


def save_gif(frames: list[Image.Image], path: Path, duration=85):
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )


def capture_animation(page, path: Path, position_frames: list[np.ndarray], duration=85):
    frames = []
    for positions in position_frames:
        update_positions(page, positions)
        page.wait_for_timeout(35)
        frames.append(screenshot_frame(page))
    save_gif(frames, path, duration=duration)


def make_surface_constraint_scene() -> tuple[Atoms, dict[str, int]]:
    slab = fcc111("Cu", size=(4, 4, 2), vacuum=7.0, orthogonal=True)
    positions = slab.get_positions()
    top_z = float(np.max(positions[:, 2]))
    center = np.mean(positions, axis=0)
    x0, y0 = float(center[0]), float(center[1])

    ads_symbols = ["C", "O", "N", "H"]
    ads_positions = [
        [x0 - 2.0, y0 - 0.2, top_z + 1.55],  # CO carbon, constrained to a line
        [x0 - 0.9, y0 - 0.2, top_z + 1.95],  # CO oxygen
        [x0 + 1.4, y0 + 0.45, top_z + 1.45],  # adsorbate N, constrained to a plane
        [x0 + 2.2, y0 + 0.95, top_z + 1.90],
    ]
    atoms = slab + Atoms(ads_symbols, positions=ads_positions)
    atoms.pbc = [True, True, False]

    line_idx = len(slab)
    oxygen_idx = len(slab) + 1
    plane_idx = len(slab) + 2
    hydrogen_idx = len(slab) + 3
    bottom = [i for i, p in enumerate(positions) if p[2] < top_z - 0.5]
    atoms.set_constraint([
        FixAtoms(indices=bottom),
        FixedLine(line_idx, [1, 0, 0]),
        FixedPlane(plane_idx, [0, 0, 1]),
    ])
    atoms.info["readme_scene"] = "cu111_fixed_line_fixed_plane"
    return atoms, {
        "line": line_idx,
        "oxygen": oxygen_idx,
        "plane": plane_idx,
        "hydrogen": hydrogen_idx,
    }


def make_hookean_surface_scene() -> tuple[Atoms, dict[str, int]]:
    slab = fcc111("Cu", size=(4, 4, 2), vacuum=7.0, orthogonal=True)
    positions = slab.get_positions()
    top_z = float(np.max(positions[:, 2]))
    center = np.mean(positions, axis=0)
    x0, y0 = float(center[0]), float(center[1])

    ads_symbols = ["O", "H", "H", "O", "H"]
    ads_positions = [
        [x0 - 1.55, y0, top_z + 1.65],
        [x0 - 2.20, y0 + 0.45, top_z + 2.10],
        [x0 - 1.15, y0 - 0.65, top_z + 2.05],
        [x0 + 2.05, y0, top_z + 1.70],
        [x0 + 2.65, y0 + 0.55, top_z + 2.15],
    ]
    atoms = slab + Atoms(ads_symbols, positions=ads_positions)
    atoms.pbc = [True, True, False]
    left_o = len(slab)
    right_o = len(slab) + 3
    bottom = [i for i, p in enumerate(positions) if p[2] < top_z - 0.5]
    atoms.set_constraint([
        FixAtoms(indices=bottom),
        Hookean(left_o, right_o, rt=3.15, k=5.0),
    ])
    atoms.info["readme_scene"] = "cu111_hookean_water_pair"
    return atoms, {"left_o": left_o, "right_o": right_o}


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
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
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


def plane_orbit_frames(base: np.ndarray, index: int, count=38) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        angle = 2 * math.pi * step / count
        positions = base.copy()
        positions[index] = base[index] + np.array([0.95 * math.cos(angle), 0.55 * math.sin(angle), 0.0])
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

            constraint_atoms, cidx = make_surface_constraint_scene()
            editor, page = open_scene(browser, constraint_atoms, show_bonds=True)
            set_display(page, {"atomRadiusScale": 0.62, "showBonds": True, "showGrid": True})
            set_selection(page, [cidx["line"], cidx["plane"]])
            open_panels(page, ["structure-info", "selection", "view", "transform"])
            settle_view(page, target=[5.2, 4.6, 12.1], position=[11.5, -5.0, 17.4], fov=39)
            page.screenshot(path=ASSET_DIR / "readme_constraints.png")

            base = constraint_atoms.get_positions()
            set_selection(page, [cidx["line"]])
            enter_mode(page, "MOVE", "X")
            capture_animation(
                page,
                ASSET_DIR / "readme_fixedline.gif",
                sinusoidal_frames(base, cidx["line"], lambda phase: [1.25 * phase, 0, 0]),
            )
            set_selection(page, [cidx["plane"]])
            enter_mode(page, "MOVE", None)
            capture_animation(
                page,
                ASSET_DIR / "readme_fixedplane.gif",
                plane_orbit_frames(base, cidx["plane"]),
            )
            page.close()
            editor.close()

            hookean_atoms, hidx = make_hookean_surface_scene()
            editor, page = open_scene(browser, hookean_atoms, show_bonds=True)
            set_display(page, {"atomRadiusScale": 0.58, "showBonds": True, "showGrid": True})
            set_selection(page, [hidx["left_o"], hidx["right_o"]])
            open_panels(page, ["structure-info", "selection", "view"])
            settle_view(page, target=[5.0, 4.5, 12.1], position=[11.4, -5.3, 17.6], fov=39)
            page.screenshot(path=ASSET_DIR / "readme_hookean.png")
            base = hookean_atoms.get_positions()
            start = base[hidx["right_o"]].copy()
            end = start + np.array([1.35, 0.0, 0.0])
            enter_mode(page, "MOVE", "X")
            capture_animation(
                page,
                ASSET_DIR / "readme_hookean.gif",
                hookean_frames(base, hidx["right_o"], start, end),
            )
            page.close()
            editor.close()

            ferrocene, fidx = make_ferrocene_scene()
            editor, page = open_scene(browser, ferrocene, show_bonds=True)
            set_display(page, {"atomRadiusScale": 0.72, "showBonds": True, "showGrid": True})
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
