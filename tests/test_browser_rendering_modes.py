import time

import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


def test_sidebar_sun_renderer_export_and_periodic_bond_contract():
    atoms = Atoms(
        "HH",
        positions=[[0.35, 0.0, 0.0], [9.65, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            initial = page.evaluate("""() => ({
                periodic: window.__ASE_APP__.state.display.showPeriodicBonds,
                bonds: window.__ASE_APP__.renderer.bondPairs.length,
                lighting: window.__ASE_APP__.renderer.lightingOptions.lightingMode,
                shadows: window.__ASE_APP__.renderer.renderer.shadowMap.enabled
            })""")
            assert initial == {
                "periodic": False,
                "bonds": 0,
                "lighting": "modeling",
                "shadows": False,
            }

            page.click('[data-inspector-group="scene"]')
            assert page.locator('[data-panel="view"]').is_visible()
            assert not page.locator('[data-panel="structure-info"]').is_visible()
            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 49")
            assert page.locator('#inspector').evaluate("element => Math.round(element.getBoundingClientRect().width)") == 48
            page.click('#btn-inspector-collapse')

            page.click('[data-panel="bonding"] > summary')
            page.check('#chk-periodic-bonds')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")
            assert page.locator('#app-viewport canvas').get_attribute('data-periodic-bonds') == 'true'

            page.click('#btn-lighting-toggle')
            page.select_option('#lighting-mode', 'studio-shadow')
            page.check('#chk-sun-gizmo')
            page.fill('#sun-position-x', '3')
            page.fill('#sun-position-y', '-3')
            page.fill('#sun-position-z', '4')
            page.wait_for_function("window.__ASE_APP__.renderer.sunGizmoGroup.visible")
            shadow_state = page.evaluate("""() => ({
                mode: window.__ASE_APP__.renderer.lightingOptions.lightingMode,
                shadowMap: window.__ASE_APP__.renderer.renderer.shadowMap.enabled,
                sunShadow: window.__ASE_APP__.renderer.studioSunLight.castShadow,
                modelingLights: window.__ASE_APP__.renderer.modelingLightGroup.visible,
                studioLights: window.__ASE_APP__.renderer.studioLightGroup.visible
            })""")
            assert shadow_state == {
                "mode": "studio-shadow",
                "shadowMap": True,
                "sunShadow": True,
                "modelingLights": False,
                "studioLights": True,
            }

            handle = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const point = app.renderer.sunGizmoGroup.userData.positionHandle.position.clone();
                point.project(app.renderer.camera);
                const rect = app.renderer.domElement.getBoundingClientRect();
                return {
                    x: rect.left + (point.x + 1) * rect.width / 2,
                    y: rect.top + (-point.y + 1) * rect.height / 2
                };
            }""")
            before_drag = page.evaluate("window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice()")
            page.mouse.move(handle["x"], handle["y"])
            page.mouse.down()
            page.mouse.move(handle["x"] + 44, handle["y"] - 28, steps=6)
            page.mouse.up()
            after_drag = page.evaluate("window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice()")
            assert after_drag != before_drag

            exported = page.evaluate("""() => window.__ASE_APP__.renderer.exportPNG(640, 360, {
                renderMode: 'studio-shadow',
                sunIntensity: 2.6,
                sunPosition: [4, -5, 7],
                sunTarget: [0, 0, 0],
                includeGrid: false,
                includeAxes: false
            }).slice(0, 22)""")
            assert exported == "data:image/png;base64,"

            page.select_option('#lighting-mode', 'modeling')
            page.wait_for_function("!window.__ASE_APP__.renderer.renderer.shadowMap.enabled")
            page.wait_for_timeout(100)
            start = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            time.sleep(0.35)
            end = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            assert end == start

            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_interactive_bonds_reinfer_live_and_cutoffs_survive_structure_updates():
    atoms = Atoms(
        "HH",
        positions=[[0.0, 0.0, 0.0], [0.7, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=False,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
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
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            page.click('[data-inspector-group="scene"]')
            page.click('[data-panel="bonding"] > summary')
            page.select_option('#bond-mode', 'element')
            cutoff = page.locator('.element-bond-cutoff[data-pair-key="H-H"]')
            assert cutoff.count() == 1
            cutoff.fill('0.90')
            page.wait_for_function(
                "Math.abs(window.__ASE_APP__.state.display.elementBondCutoffs['H-H'] - 0.9) < 1e-9"
            )

            page.evaluate("""() => {
                document.activeElement?.blur();
                const app = window.__ASE_APP__;
                app.state.selected.clear();
                app.state.selected.add(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('1.0')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'MOVE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )

            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.evaluate("async () => { await window.__ASE_APP__.pendingApply; }")
            persisted = page.evaluate("""() => ({
                mode: window.__ASE_APP__.state.display.bondMode,
                cutoff: window.__ASE_APP__.state.display.elementBondCutoffs['H-H'],
                input: Number(document.querySelector('[data-pair-key="H-H"]').value),
                bonds: window.__ASE_APP__.renderer.bondPairs.length
            })""")
            assert persisted == {
                "mode": "element",
                "cutoff": 0.9,
                "input": 0.9,
                "bonds": 0,
            }

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('-1.0')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'MOVE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 1"
            )
            page.keyboard.press('Escape')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'IDLE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )

            label_cutoffs = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.elementBondCutoffs['H-O'] = 1.23;
                app.transferElementDisplaySettings('H', 'H_custom');
                return {...app.state.display.elementBondCutoffs};
            }""")
            assert label_cutoffs['H-O'] == 1.23
            assert 'H_custom-O' not in label_cutoffs
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_bond_style_thickness_and_color_modes_render_and_persist():
    atoms = Atoms(
        "HO",
        positions=[[0.0, 0.0, 0.0], [0.85, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=False,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
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
            page.wait_for_function("window.__ASE_APP__?.renderer?.bondPairs?.length === 1")

            default_bond = page.evaluate("""() => {
                const mesh = window.__ASE_APP__.renderer.bondGroup.children[0];
                const colors = Array.from(mesh.instanceColor.array);
                return {
                    style: mesh.geometry.type,
                    segments: mesh.userData.bondSegments.length,
                    first: colors.slice(0, 3),
                    second: colors.slice(3, 6)
                };
            }""")
            assert default_bond["style"] == "CylinderGeometry"
            assert default_bond["segments"] == 2
            assert default_bond["first"] != default_bond["second"]

            page.click('[data-inspector-group="scene"]')
            page.click('[data-panel="bonding"] > summary')
            page.select_option('#bond-style', 'flat')
            page.select_option('#bond-color-mode', 'custom')
            page.locator('#bond-thickness').evaluate("""element => {
                element.value = '0.24';
                element.dispatchEvent(new Event('input', { bubbles: true }));
            }""")
            page.locator('#bond-custom-color').evaluate("""element => {
                element.value = '#18a7d8';
                element.dispatchEvent(new Event('input', { bubbles: true }));
            }""")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                return app.state.display.bondStyle === 'flat'
                    && app.state.display.bondColorMode === 'custom'
                    && Math.abs(app.state.display.bondThickness - 0.24) < 1e-9
                    && app.state.display.bondCustomColor === '#18a7d8'
                    && mesh.geometry.type === 'PlaneGeometry'
                    && mesh.userData.bondSegments.length === 1;
            }""")
            flat_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                const matrix = Array.from(mesh.instanceMatrix.array.slice(0, 16));
                return {
                    thickness: Math.hypot(matrix[0], matrix[1], matrix[2]),
                    output: document.getElementById('bond-thickness-value').innerText,
                    customVisible: !document.getElementById('bond-custom-color-row').classList.contains('hidden'),
                    matrix
                };
            }""")
            assert flat_state["thickness"] == pytest.approx(0.24, abs=1e-5)
            assert flat_state["output"] == "0.24 A"
            assert flat_state["customVisible"] is True

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.controls.rotate(42, -27);
                app.renderer.renderNow();
            }""")
            rotated_matrix = page.evaluate(
                "Array.from(window.__ASE_APP__.renderer.bondGroup.children[0].instanceMatrix.array.slice(0, 16))"
            )
            assert rotated_matrix != flat_state["matrix"]

            page.select_option('#bond-color-mode', 'split')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.bondGroup.children[0].userData.bondSegments.length === 2"
            )
            split_colors = page.evaluate(
                "Array.from(window.__ASE_APP__.renderer.bondGroup.children[0].instanceColor.array)"
            )
            assert split_colors[:3] != split_colors[3:6]

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.selected.clear();
                app.state.selected.add(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('0.1')
            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.evaluate("async () => { await window.__ASE_APP__.pendingApply; }")
            persisted = page.evaluate("""() => ({
                style: window.__ASE_APP__.state.display.bondStyle,
                thickness: window.__ASE_APP__.state.display.bondThickness,
                colorMode: window.__ASE_APP__.state.display.bondColorMode,
                customColor: window.__ASE_APP__.state.display.bondCustomColor,
                styleControl: document.getElementById('bond-style').value,
                thicknessControl: Number(document.getElementById('bond-thickness').value),
                colorControl: document.getElementById('bond-color-mode').value
            })""")
            assert persisted == {
                "style": "flat",
                "thickness": 0.24,
                "colorMode": "split",
                "customColor": "#18a7d8",
                "styleControl": "flat",
                "thicknessControl": 0.24,
                "colorControl": "split",
            }
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)
