"""Capture README screenshots from the local v_ase showcase scene."""

from __future__ import annotations

import time
from pathlib import Path

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


def settle_view(page):
    page.evaluate(
        """() => {
            const app = window.__V_ASE_APP__;
            app.renderer.fitCameraToStructure();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }"""
    )
    page.wait_for_timeout(1000)


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    editor = view_edit(
        make_frames(),
        block=False,
        port=8790,
        show_cell=True,
        show_axes=True,
        show_bonds=True,
        respect_constraints=True,
        allow_relax=False,
    )
    url = f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}"
    time.sleep(0.8)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(url)
        page.wait_for_function("window.__V_ASE_APP__ && window.__V_ASE_APP__.state.atoms")
        settle_view(page)

        open_panels(page, ["structure-info", "selection", "view", "trajectory-panel"])
        settle_view(page)
        page.screenshot(path=ASSET_DIR / "readme_overview.png")

        set_selection(page, [1, 2])
        open_panels(page, ["structure-info", "selection", "transform", "view"])
        settle_view(page)
        page.screenshot(path=ASSET_DIR / "readme_constraints.png")

        page.evaluate("window.__V_ASE_APP__.loadFrame(2)")
        page.wait_for_timeout(500)
        set_selection(page, [1, 2])
        open_panels(page, ["structure-info", "selection", "trajectory-panel", "view"])
        settle_view(page)
        page.screenshot(path=ASSET_DIR / "readme_hookean.png")

        set_selection(page, [1, 2, 3, 4])
        page.evaluate("window.__V_ASE_APP__.enterTransformMode('ROTATE')")
        open_panels(page, ["structure-info", "selection", "transform", "view"])
        page.wait_for_timeout(500)
        page.screenshot(path=ASSET_DIR / "readme_rotate.png")

        browser.close()

    print(f"Wrote README screenshots to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
