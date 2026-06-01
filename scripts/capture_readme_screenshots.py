"""Capture README screenshots from the local v_ase showcase scene."""

from __future__ import annotations

from pathlib import Path

from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from playwright.sync_api import sync_playwright

from tests.manual_showcase import make_frames
from v_ase import view_edit


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"


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
            app.renderer.renderer.render(app.renderer.scene, camera);
        }""",
        {"target": target, "position": position, "up": up, "fov": fov},
    )
    page.wait_for_timeout(300)


def settle_view(page, *, target=None, position=None, fov=38):
    page.evaluate(
        """() => {
            const app = window.__V_ASE_APP__;
            app.renderer.fitCameraToStructure();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }"""
    )
    page.wait_for_timeout(500)
    if target is not None and position is not None:
        set_camera(page, target=target, position=position, fov=fov)


def make_constraint_scene() -> Atoms:
    atoms = Atoms(
        symbols=["C", "Cl", "O"],
        positions=[
            [0.9, 4.4, 1.2],
            [2.2, 2.6, 1.8],
            [5.1, 2.6, 1.8],
        ],
        cell=[7.2, 5.2, 3.8],
        pbc=[True, True, False],
    )
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
    ])
    atoms.info["readme_scene"] = "fixed_line_fixed_plane"
    return atoms


def make_hookean_scene() -> Atoms:
    atoms = Atoms(
        symbols=["C", "O"],
        positions=[
            [1.0, 2.0, 1.8],
            [5.8, 2.0, 1.8],
        ],
        cell=[7.5, 4.0, 3.6],
        pbc=[False, False, False],
    )
    atoms.set_constraint(Hookean(0, 1, rt=3.2, k=5.0))
    atoms.info["readme_scene"] = "hookean_active"
    return atoms


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

            editor, page = open_scene(browser, make_constraint_scene(), show_bonds=False)
            set_display(page, {"atomRadiusScale": 0.52, "showBonds": False, "showGrid": True})
            set_selection(page, [1, 2])
            open_panels(page, ["structure-info", "selection", "view", "transform"])
            settle_view(page, target=[3.5, 2.55, 1.75], position=[3.5, -6.2, 4.7], fov=41)
            page.screenshot(path=ASSET_DIR / "readme_constraints.png")
            page.close()
            editor.close()

            editor, page = open_scene(browser, make_hookean_scene(), show_bonds=False)
            set_display(page, {"atomRadiusScale": 0.56, "showBonds": False, "showGrid": True})
            set_selection(page, [0, 1])
            open_panels(page, ["structure-info", "selection", "view"])
            settle_view(page, target=[4.15, 2.0, 1.8], position=[4.15, -6.4, 4.3], fov=46)
            page.screenshot(path=ASSET_DIR / "readme_hookean.png")
            page.close()
            editor.close()

            editor, page = open_scene(browser, make_frames(), show_bonds=True)
            set_selection(page, [1, 2, 3, 4])
            page.evaluate("window.__V_ASE_APP__.enterTransformMode('ROTATE')")
            open_panels(page, ["structure-info", "selection", "transform", "view"])
            settle_view(page, target=[5.3, 5.4, 2.3], position=[15.0, -10.0, 8.6], fov=39)
            page.wait_for_timeout(500)
            page.screenshot(path=ASSET_DIR / "readme_rotate.png")
            page.close()
            editor.close()
        finally:
            browser.close()
            webbrowser.open = original_open

    print(f"Wrote README screenshots to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
