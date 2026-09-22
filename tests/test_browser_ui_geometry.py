"""Every scientific tool remains discoverable and fits the real workbench."""

import json
import os
from pathlib import Path

import numpy as np
from ase import Atoms
from playwright.sync_api import sync_playwright

from tests.ui_navigation import ROUTE_GROUPS, open_editor_route
from v_ase.viewer import find_free_port, view


def test_all_tools_and_unit_fields_fit_desktop_narrow_and_mobile():
    atoms = Atoms('CuO', positions=[[0, 0, 0], [1.8, 0, 0]], cell=[8, 8, 8], pbc=True)
    atoms.new_array('v_ase_atom_type', np.array(['Cu_substrate_layer_123456789', 'O_surface_oxide']))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    violations = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 960})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            for width, height in [(1440, 960), (1024, 768), (390, 844)]:
                page.set_viewport_size({'width': width, 'height': height})
                for group, routes in ROUTE_GROUPS.items():
                    page.locator(f'#workbench-tabs [data-workbench="{group}"]').click()
                    for route in routes:
                        button = page.locator(f'#workbench-tools [data-editor-route="{route}"]')
                        assert button.is_visible(), (width, group, route)
                        button.click()
                        assert page.locator('body').get_attribute('data-current-editor-route') == route
                        if route == 'appearance':
                            page.locator('#chk-atom-radius-mapping').check()
                            page.locator('#chk-atom-colorscale').check()
                        elif route == 'add-atoms':
                            page.locator('#add-atoms-tab-batch').click()
                            page.locator('#add-atoms-content-molecules').click()
                            page.locator('#add-molecules-quantity-density').click()
                            page.locator('#add-atoms-placement-regular').click()
                        issues = page.evaluate("""() => {
                            const issues = [];
                            const inspector = document.getElementById('inspector').getBoundingClientRect();
                            const legend = document.getElementById('atom-colorscale-legend');
                            if (!legend.classList.contains('hidden')) {
                                const l=legend.getBoundingClientRect();
                                for (const id of ['btn-objects', 'viewport-camera-tools', 'orientation-widget', 'viewport-tools']) {
                                    const r=document.getElementById(id).getBoundingClientRect();
                                    if (l.left < r.right && l.right > r.left && l.top < r.bottom && l.bottom > r.top) {
                                        issues.push({legendOverlaps:id});
                                    }
                                }
                            }

                            const visible = element => element.getClientRects().length
                                && getComputedStyle(element).visibility !== 'hidden';
                            if (document.documentElement.scrollWidth > innerWidth + 1) issues.push('page overflow');
                            document.querySelectorAll('#inspector-content input, #inspector-content select, #inspector-content textarea, #inspector-content button').forEach(element => {
                                if (!visible(element) || element.type === 'hidden') return;
                                const r = element.getBoundingClientRect();
                                if (!r.width || !r.height) return;
                                if (r.left < inspector.left - 1 || r.right > inspector.right + 1) {
                                    issues.push({id:element.id || element.className, left:r.left-inspector.left, right:r.right-inspector.right});
                                }
                            });
                            document.querySelectorAll('#inspector .unit-input').forEach(group => {
                                if (!visible(group)) return;
                                const input = group.querySelector('input');
                                const unit = group.querySelector(':scope > span');
                                if (!input || !unit) return;
                                const box=group.getBoundingClientRect(), a=input.getBoundingClientRect(), b=unit.getBoundingClientRect();
                                if (a.right > b.left + 1 || b.right > box.right + 1 || a.left < box.left - 1
                                    || b.bottom > box.bottom + 1 || a.bottom > box.bottom + 1) {
                                    issues.push({unit:input.id, overlap:a.right-b.left});
                                }
                            });
                            return issues;
                        }""")
                        violations.extend({'width': width, 'route': route, 'issue': issue} for issue in issues)
                    if directory := os.environ.get('V_ASE_UI_QA_DIR'):
                        Path(directory).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(directory) / f'workbench-{group}-{width}.png'), full_page=True)
            assert not errors
            assert not violations, json.dumps(violations, indent=2)
            browser.close()
    finally:
        editor.close()


def test_tool_keyboard_navigation_does_not_move_camera_and_view_mode_explains_editing():
    editor = view(Atoms('CuO', positions=[[0, 0, 0], [1.8, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), viz_only=True, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            camera = page.evaluate('window.__ASE_APP__.renderer.camera.position.toArray()')
            page.locator('#workbench-route-appearance').focus()
            page.keyboard.press('ArrowRight')
            assert page.locator('body').get_attribute('data-current-editor-route') == 'bonding'
            assert page.evaluate('window.__ASE_APP__.renderer.camera.position.toArray()') == camera
            page.locator('#workbench-tabs [data-workbench="build"]').click()
            assert page.locator('#workbench-edit-notice').is_visible()
            assert page.evaluate('window.__ASE_APP__.state.vizOnly') is True
            page.locator('#workbench-switch-edit').click()
            page.wait_for_function('!window.__ASE_APP__.state.vizOnly')
            assert not page.locator('#workbench-edit-notice').is_visible()
            assert page.locator('#btn-create-atom-add').is_enabled()
            browser.close()
    finally:
        editor.close()


def test_export_dialog_units_and_controls_fit_narrow_windows():
    frames = [Atoms('H2', positions=[[0, 0, 0], [1 + frame / 10, 0, 0]]) for frame in (0, 1)]
    editor = view(frames, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            for width, height in [(1440, 960), (1024, 768), (390, 844), (640, 360)]:
                page.set_viewport_size({'width': width, 'height': height})
                for route, trigger, prefix in [('render-image', '#btn-export-image', 'export'),
                                               ('render-video', '#btn-export-video', 'video')]:
                    open_editor_route(page, route)
                    page.locator(trigger).click()
                    field = page.locator(f'#{prefix}-pixels-per-angstrom')
                    field.fill('123.45')
                    assert field.evaluate('''input => {
                        const group=input.closest('.unit-input');
                        if (!group) return false;
                        const unit=group.querySelector(':scope > span');
                        const r=group.getBoundingClientRect(), a=input.getBoundingClientRect(), b=unit.getBoundingClientRect();
                        return a.right <= b.left+1 && b.right <= r.right+1
                            && a.left >= r.left-1 && b.bottom <= r.bottom+1;
                    }'''), (width, route)
                    assert page.locator('#modal-container .modal').evaluate('''modal => {
                        const bounds=modal.getBoundingClientRect();
                        return [...modal.querySelectorAll('input,select,button')].every(element => {
                            if (!element.getClientRects().length) return true;
                            const r=element.getBoundingClientRect();
                            return r.left >= bounds.left-1 && r.right <= bounds.right+1;
                        });
                    }'''), (width, route)
                    page.locator('#modal-close').click()
            browser.close()
    finally:
        editor.close()
