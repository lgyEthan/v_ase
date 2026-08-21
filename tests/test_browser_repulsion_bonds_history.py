"""Focused browser regressions for repulsion, bond appearance, and history."""

from __future__ import annotations

import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.io import set_atom_labels
from v_ase.viewer import find_free_port, view


def _expand_inspector(page):
    if page.locator("body").evaluate(
        "element => element.classList.contains('inspector-collapsed')"
    ):
        page.click("#btn-inspector-collapse")
        page.wait_for_function(
            "!document.body.classList.contains('inspector-collapsed')"
        )


def _select_structure_section(page, section):
    page.click('[data-inspector-group="structure"]')
    page.select_option("#structure-section-select", section)
    page.wait_for_function(
        """section => document.querySelector(`[data-panel="${section}"]`)?.open === true""",
        arg=section,
    )


def test_repulsion_bond_theme_toolbar_and_add_atoms_history_are_independent():
    atoms = Atoms(
        "OHH",
        positions=[[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=True,
    )
    set_atom_labels(atoms, ["O_water", "H_water", "H_water"])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3"
            )

            _expand_inspector(page)
            _select_structure_section(page, "bonding")
            page.select_option("#bond-mode", "pairwise")
            visual_hh = page.locator(
                '.pairwise-bond-row[data-pair-key="H_water-H_water"] '
                '.pairwise-bond-enabled'
            )
            visual_hh.uncheck()
            page.wait_for_function(
                "window.__ASE_APP__.state.display.pairwiseBondRanges"
                '["H_water-H_water"].enabled === false'
            )
            _select_structure_section(page, "scientific-tools")
            page.wait_for_function(
                "document.querySelectorAll('#repulsion-pair-list .repulsion-pair-row').length === 3"
            )
            repulsion_hh = page.locator(
                '.repulsion-pair-row[data-pair-key="H_water|H_water"]'
            )
            assert repulsion_hh.count() == 1
            assert repulsion_hh.locator(".repulsion-pair-enabled").is_checked()
            assert float(repulsion_hh.locator(".repulsion-pair-distance").input_value()) > 0

            _select_structure_section(page, "bonding")
            page.select_option("#bond-pair-style-key", "H_water-O_water")
            page.check("#bond-pair-style-enabled")
            page.select_option("#bond-pair-style", "flat")
            page.select_option("#bond-pair-material", "metal")
            page.select_option("#bond-pair-color-mode", "custom")
            page.fill("#bond-pair-custom-color", "#27a6d1")
            page.fill("#bond-pair-opacity", "0.35")
            page.click("#btn-bond-pair-apply")
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas')?.dataset.bondStyle === 'mixed'"
            )
            appearance = page.evaluate(
                "window.__ASE_APP__.renderer.bondAppearance(0, 1)"
            )
            assert appearance == {
                "style": "flat",
                "material": "metal",
                "colorMode": "custom",
                "customColor": "#27a6d1",
                "opacity": pytest.approx(0.35),
            }
            assert page.locator("#bond-style").input_value() == "cylinder"

            page.click('[data-inspector-group="view"]')
            page.select_option("#ui-theme", "dark")
            page.wait_for_function(
                "document.documentElement.dataset.uiTheme === 'dark'"
                " && document.body.dataset.viewportBackground === 'dark'"
                " && document.querySelector('#app-viewport canvas')?.dataset.viewportBackground === 'dark'"
            )
            page.select_option("#ui-theme", "system")
            page.wait_for_function(
                "document.documentElement.dataset.themePreference === 'system'"
                " && document.body.dataset.viewportBackground === 'white'"
            )

            grid_before = page.get_attribute("#btn-grid-toggle", "aria-pressed")
            page.click("#btn-grid-toggle")
            assert page.get_attribute("#btn-grid-toggle", "aria-pressed") != grid_before
            page.click("#btn-lighting-toggle")
            assert page.get_attribute("#btn-lighting-toggle", "aria-expanded") == "true"
            assert "hidden" not in (page.get_attribute("#lighting-card", "class") or "")
            page.hover("#btn-grid-toggle")
            page.wait_for_timeout(650)
            assert page.locator("#toolbar-tooltip").is_visible()
            assert "viewport grid" in page.locator("#toolbar-tooltip").inner_text().lower()

            page.click("#btn-create-atom-toggle")
            page.click("#add-atoms-tab-batch")
            page.fill(".add-atoms-entry-count", "2")
            page.click("#btn-add-atoms-scatter")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 5"
                " && window.__ASE_APP__.addAtomsUI.active?.placement_count === 1"
            )
            page.click("#btn-add-atoms-scatter")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 7"
                " && window.__ASE_APP__.addAtomsUI.active?.placement_count === 2"
            )
            assert page.evaluate("window.__ASE_APP__.undoTimeline.length") >= 2
            page.evaluate("() => window.__ASE_APP__.performUndo()")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 5"
                " && window.__ASE_APP__.addAtomsUI.active?.placement_count === 1"
            )
            page.evaluate("() => window.__ASE_APP__.performRedo()")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 7"
                " && window.__ASE_APP__.addAtomsUI.active?.placement_count === 2"
            )
            page.click("#btn-add-atoms-cancel")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 3"
                " && window.__ASE_APP__.addAtomsUI.active === null"
                " && !window.__ASE_APP__.undoTimeline.some(action => action.scope?.startsWith('add-atoms:'))"
            )
            browser.close()
    finally:
        editor.close()
