import time

import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.session import sessions
from v_ase.io import set_atom_type_labels
from v_ase.viewer import find_free_port, view


def _expand_inspector(page):
    if page.locator('body').evaluate("element => element.classList.contains('inspector-collapsed')"):
        page.click('#btn-inspector-collapse')
        page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
        page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 336")


def _open_panel(page, panel):
    details = page.locator(f'[data-panel="{panel}"]')
    if not details.evaluate("element => element.open"):
        details.locator('summary').click()


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

            assert page.locator('body').evaluate("element => element.classList.contains('inspector-collapsed')")
            assert page.locator('#btn-inspector-collapse').get_attribute('aria-expanded') == 'false'
            assert page.locator('#btn-inspector-collapse').get_attribute('title') == 'Expand control panel'
            assert page.locator('#btn-inspector-collapse .inspector-edge-chevron').count() == 1
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            assert page.locator('#inspector').evaluate("element => Math.round(element.getBoundingClientRect().width)") == 0

            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 336")
            assert page.locator('#btn-inspector-collapse').get_attribute('aria-expanded') == 'true'
            assert page.locator('#btn-inspector-collapse').get_attribute('title') == 'Collapse control panel'
            edge_geometry = page.evaluate("""() => {
                const button = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                return {
                    buttonRight: button.right,
                    panelLeft: panel.left,
                    verticalCenterDelta: Math.abs(
                        (button.top + button.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert edge_geometry['buttonRight'] == pytest.approx(edge_geometry['panelLeft'], abs=1.5)
            assert edge_geometry['verticalCenterDelta'] <= 1.5

            page.click('[data-inspector-group="scene"]')
            assert page.locator('[data-panel="view"]').is_visible()
            assert not page.locator('[data-panel="structure-info"]').is_visible()
            for panel in ('view', 'appearance', 'bonding'):
                assert page.locator(f'[data-panel="{panel}"]').evaluate("element => element.open")
            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Tab')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")

            _open_panel(page, 'bonding')
            page.check('#chk-periodic-bonds')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")
            assert page.locator('#app-viewport canvas').get_attribute('data-periodic-bonds') == 'true'

            lighting_icon = page.locator('#btn-lighting-toggle .render-light-icon')
            assert lighting_icon.is_visible()
            icon_box = lighting_icon.bounding_box()
            assert icon_box is not None
            assert icon_box['width'] == pytest.approx(27, abs=1)
            assert icon_box['height'] == pytest.approx(27, abs=1)
            viewport_tools = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const calculator = document.getElementById('calc-controls').getBoundingClientRect();
                const actionGroup = document.querySelector('.action-group').getBoundingClientRect();
                return {
                    triggerLeft: trigger.left,
                    calculatorRight: calculator.right,
                    contained: trigger.left >= actionGroup.left && trigger.right <= actionGroup.right,
                    headerCenterDelta: Math.abs(
                        (trigger.top + trigger.height / 2) -
                        (actionGroup.top + actionGroup.height / 2)
                    )
                };
            }""")
            assert viewport_tools['triggerLeft'] >= viewport_tools['calculatorRight'] + 5
            assert viewport_tools['contained'] is True
            assert viewport_tools['headerCenterDelta'] <= 2
            page.click('#btn-lighting-toggle')
            lighting_panel_geometry = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const card = document.getElementById('lighting-card').getBoundingClientRect();
                const header = document.getElementById('top-bar').getBoundingClientRect();
                return {
                    triggerRight: trigger.right,
                    cardRight: card.right,
                    cardTop: card.top,
                    headerBottom: header.bottom
                };
            }""")
            assert lighting_panel_geometry['cardRight'] == pytest.approx(lighting_panel_geometry['triggerRight'], abs=1.5)
            assert lighting_panel_geometry['cardTop'] >= lighting_panel_geometry['headerBottom'] + 5
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
            page.click('#btn-lighting-close')

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
            before_drag = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            page.mouse.move(handle["x"], handle["y"])
            page.mouse.down()
            page.mouse.move(handle["x"] + 44, handle["y"] - 28, steps=6)
            page.mouse.up()
            after_direct_drag = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice(),
                selected: window.__ASE_APP__.state.sunSelected,
                rendererSelected: window.__ASE_APP__.renderer.sunGizmoSelected
            })""")
            assert after_direct_drag["position"] == pytest.approx(before_drag["position"])
            assert after_direct_drag["target"] == pytest.approx(before_drag["target"])
            assert after_direct_drag["selected"] == "source"
            assert after_direct_drag["rendererSelected"] == "source"

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('2')
            page.keyboard.press('Enter')
            after_move = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice(),
                mode: window.__ASE_APP__.transform.mode
            })""")
            assert after_move["position"] == pytest.approx([
                before_drag["position"][0] + 2,
                before_drag["position"][1],
                before_drag["position"][2],
            ])
            assert after_move["target"] == pytest.approx([
                before_drag["target"][0] + 2,
                before_drag["target"][1],
                before_drag["target"][2],
            ])
            assert after_move["mode"] == 'IDLE'

            direction_before_rotate = [
                after_move["target"][axis] - after_move["position"][axis]
                for axis in range(3)
            ]
            page.keyboard.press('r')
            page.keyboard.press('z')
            page.keyboard.type('90')
            page.keyboard.press('Enter')
            after_rotate = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            direction_after_rotate = [
                after_rotate["target"][axis] - after_rotate["position"][axis]
                for axis in range(3)
            ]
            assert after_rotate["position"] == pytest.approx(after_move["position"])
            assert direction_after_rotate == pytest.approx([
                -direction_before_rotate[1],
                direction_before_rotate[0],
                direction_before_rotate[2],
            ])

            page.evaluate("window.__ASE_APP__.setSunSelected('target')")
            target_selection = page.evaluate("""() => ({
                selected: window.__ASE_APP__.state.sunSelected,
                rendererSelected: window.__ASE_APP__.renderer.sunGizmoSelected
            })""")
            assert target_selection == {"selected": "target", "rendererSelected": "target"}

            page.keyboard.press('g')
            page.keyboard.press('y')
            page.keyboard.type('3')
            page.keyboard.press('Enter')
            after_target_move = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            assert after_target_move["position"] == pytest.approx(after_rotate["position"])
            assert after_target_move["target"] == pytest.approx([
                after_rotate["target"][0],
                after_rotate["target"][1] + 3,
                after_rotate["target"][2],
            ])

            direction_before_target_rotate = [
                after_target_move["target"][axis] - after_target_move["position"][axis]
                for axis in range(3)
            ]
            page.keyboard.press('r')
            target_rotate_pivot = page.evaluate("window.__ASE_APP__.transform.pivot.toArray()")
            assert target_rotate_pivot == pytest.approx(after_target_move["position"])
            page.keyboard.press('z')
            page.keyboard.type('90')
            page.keyboard.press('Enter')
            after_target_rotate = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            direction_after_target_rotate = [
                after_target_rotate["target"][axis] - after_target_rotate["position"][axis]
                for axis in range(3)
            ]
            assert after_target_rotate["position"] == pytest.approx(after_target_move["position"])
            assert direction_after_target_rotate == pytest.approx([
                -direction_before_target_rotate[1],
                direction_before_target_rotate[0],
                direction_before_target_rotate[2],
            ])

            page.keyboard.press('g')
            page.keyboard.press('z')
            page.keyboard.type('2')
            page.keyboard.press('Escape')
            after_cancel = page.evaluate("window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()")
            assert after_cancel == pytest.approx(after_target_rotate["target"])

            directional_shadow = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const originalPositions = window.__ASE_APP__.state.atoms.positions.map(position => position.slice());
                const shiftedPositions = originalPositions.map(([x, y, z]) => [x + 120, y - 80, z + 45]);
                renderer.updatePositions(shiftedPositions);
                renderer.fitSunShadowCamera();
                const bounds = renderer.lightingStructureBounds();
                const center = bounds.getCenter(renderer.studioSunTarget.position.clone());
                const semanticDirection = renderer.studioSunTarget.position.clone()
                    .fromArray(renderer.lightingOptions.sunTarget)
                    .sub(renderer.studioSunLight.position.clone().fromArray(renderer.lightingOptions.sunPosition))
                    .normalize();
                const effectiveDirection = renderer.studioSunTarget.position.clone()
                    .sub(renderer.studioSunLight.position).normalize();
                const camera = renderer.studioSunLight.shadow.camera;
                camera.updateMatrixWorld(true);
                const inside = renderer.boxCorners(bounds).every(corner => {
                    const point = corner.clone().applyMatrix4(camera.matrixWorldInverse);
                    return point.x >= camera.left && point.x <= camera.right &&
                        point.y >= camera.bottom && point.y <= camera.top &&
                        -point.z >= camera.near && -point.z <= camera.far;
                });
                const result = {
                    directional: renderer.studioSunLight.isDirectionalLight,
                    center: center.toArray(),
                    effectiveTarget: renderer.studioSunTarget.position.toArray(),
                    semanticDirection: semanticDirection.toArray(),
                    effectiveDirection: effectiveDirection.toArray(),
                    inside
                };
                renderer.updatePositions(originalPositions);
                return result;
            }""")
            assert directional_shadow["directional"] is True
            assert max(abs(value) for value in directional_shadow["center"]) > 40
            assert directional_shadow["effectiveTarget"] == pytest.approx(directional_shadow["center"])
            assert directional_shadow["effectiveDirection"] == pytest.approx(
                directional_shadow["semanticDirection"]
            )
            assert directional_shadow["inside"] is True
            lighting_export = page.evaluate("window.__ASE_APP__.currentLightingForExport()")
            assert lighting_export["mode"] == "studio-shadow"
            assert lighting_export["intensity"] == pytest.approx(2.2)
            assert lighting_export["position"] == pytest.approx(after_target_rotate["position"])
            assert lighting_export["target"] == pytest.approx(after_target_rotate["target"])
            assert lighting_export["color"] == pytest.approx([1.0, 0.960784, 0.87451])

            exported = page.evaluate("""() => window.__ASE_APP__.renderer.exportPNG(640, 360, {
                renderMode: 'studio-shadow',
                sunIntensity: 2.6,
                sunPosition: [4, -5, 7],
                sunTarget: [0, 0, 0],
                includeGrid: false,
                includeAxes: false
            }).slice(0, 22)""")
            assert exported == "data:image/png;base64,"

            page.click('#btn-lighting-toggle')
            page.select_option('#lighting-mode', 'modeling')
            page.wait_for_function("!window.__ASE_APP__.renderer.renderer.shadowMap.enabled")
            page.wait_for_timeout(100)
            start = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            time.sleep(0.35)
            end = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            assert end == start

            page.click('#btn-lighting-close')
            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            mobile_collapsed = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const handle = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                const actionGroup = document.querySelector('.action-group').getBoundingClientRect();
                return {
                    panelWidth: panel.width,
                    handleRight: handle.right,
                    viewportWidth: window.innerWidth,
                    triggerRight: trigger.right,
                    handleLeft: handle.left,
                    handleOverlap: !(
                        trigger.right <= handle.left ||
                        trigger.left >= handle.right ||
                        trigger.bottom <= handle.top ||
                        trigger.top >= handle.bottom
                    ),
                    triggerContained: trigger.left >= actionGroup.left && trigger.right <= actionGroup.right,
                    headerCenterDelta: Math.abs(
                        (trigger.top + trigger.height / 2) -
                        (actionGroup.top + actionGroup.height / 2)
                    ),
                    handleVerticalCenterDelta: Math.abs(
                        (handle.top + handle.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert mobile_collapsed['panelWidth'] == pytest.approx(0, abs=1)
            assert mobile_collapsed['handleRight'] == pytest.approx(mobile_collapsed['viewportWidth'], abs=1)
            assert mobile_collapsed['handleOverlap'] is False
            assert mobile_collapsed['triggerContained'] is True
            assert mobile_collapsed['headerCenterDelta'] <= 2
            assert mobile_collapsed['handleVerticalCenterDelta'] <= 1.5

            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 345.5")
            mobile_expanded = page.evaluate("""() => {
                const handle = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                return {
                    handleRight: handle.right,
                    panelLeft: panel.left,
                    panelWidth: panel.width,
                    verticalCenterDelta: Math.abs(
                        (handle.top + handle.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert mobile_expanded['panelWidth'] == pytest.approx(346, abs=1)
            assert mobile_expanded['handleRight'] == pytest.approx(mobile_expanded['panelLeft'], abs=1)
            assert mobile_expanded['verticalCenterDelta'] <= 1.5

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
    set_atom_type_labels(atoms, ["H_left", "H_right"])
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

            _expand_inspector(page)
            page.click('[data-inspector-group="scene"]')
            _open_panel(page, 'bonding')
            page.select_option('#bond-mode', 'element')
            cutoff = page.locator('.element-bond-cutoff[data-pair-key="H_left-H_right"]')
            assert cutoff.count() == 1
            cutoff.fill('0.90')
            page.wait_for_function(
                "Math.abs(window.__ASE_APP__.state.display.elementBondCutoffs['H_left-H_right'] - 0.9) < 1e-9"
            )
            cutoff.fill('0')
            page.wait_for_function(
                "window.__ASE_APP__.state.display.elementBondCutoffs['H_left-H_right'] === 0 && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )
            cutoff.fill('0.90')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

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
                cutoff: window.__ASE_APP__.state.display.elementBondCutoffs['H_left-H_right'],
                input: Number(document.querySelector('[data-pair-key="H_left-H_right"]').value),
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

            relabeled = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.elementBondCutoffs['H_left-H_right'] = 1.23;
                app.renameElementTypeForVisualization('H_left', 'H_custom', [0], 'H', {preserveAppearance: true});
                return {
                    labels: [...app.state.atoms.symbols],
                    order: [...app.state.typeOrder],
                    cutoff: app.state.display.elementBondCutoffs['H_custom-H_right'],
                    rendererCutoff: app.renderer.bondCutoffForPair(0, 1),
                    input: Number(document.querySelector('[data-pair-key="H_custom-H_right"]')?.value),
                };
            }""")
            assert relabeled == {
                "labels": ["H_custom", "H_right"],
                "order": ["H_custom", "H_right"],
                "cutoff": 1.23,
                "rendererCutoff": 1.23,
                "input": 1.23,
            }
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_bond_style_thickness_and_color_modes_render_and_persist():
    atoms = Atoms(
        "HO",
        positions=[[0.0, 0.0, 0.0], [2.4, 0.0, 0.0]],
        cell=[[8.0, 0.0, 0.0], [1.2, 8.0, 0.0], [0.3, 0.5, 8.0]],
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
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            _expand_inspector(page)
            page.click('[data-inspector-group="scene"]')
            _open_panel(page, 'bonding')
            page.select_option('#bond-mode', 'manual')
            page.fill('#bond-pairs', '0-1')
            page.click('#btn-bond-apply')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            default_bond = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.bondGroup.children;
                return {
                    styles: meshes.map(mesh => mesh.geometry.type),
                    segments: meshes.reduce((sum, mesh) => sum + mesh.userData.bondSegments.length, 0),
                    colors: meshes.map(mesh => `#${mesh.material.color.getHexString()}`).sort(),
                    expected: [renderer.atomVisualColor(0), renderer.atomVisualColor(1)]
                        .map(color => color.toLowerCase()).sort()
                };
            }""")
            assert default_bond["styles"] == ["CylinderGeometry", "CylinderGeometry"]
            assert default_bond["segments"] == 2
            assert default_bond["colors"] == default_bond["expected"]

            page.select_option('#bond-style', 'flat')
            page.select_option('#bond-color-mode', 'custom')
            page.fill('#bond-thickness', '0.24')
            page.fill('#bond-custom-color', '#18a7d8')
            page.locator('#bond-pairs').click()
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                return app.state.display.bondStyle === 'flat'
                    && app.state.display.bondColorMode === 'custom'
                    && Math.abs(app.state.display.bondThickness - 0.24) < 1e-9
                    && app.state.display.bondCustomColor === '#18a7d8'
                    && mesh.geometry.type === 'PlaneGeometry'
                    && mesh.userData.bondSegments.length === 1
                    && mesh.userData.bondColor === '#18a7d8'
                    && mesh.material.color.getHexString() === '18a7d8';
            }""")
            flat_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                const matrix = Array.from(mesh.instanceMatrix.array.slice(0, 16));
                return {
                    thickness: Math.hypot(matrix[0], matrix[1], matrix[2]),
                    output: document.getElementById('bond-thickness-value').innerText,
                    customVisible: !document.getElementById('bond-custom-color-row').classList.contains('hidden'),
                    color: `#${mesh.material.color.getHexString()}`,
                    matrix
                };
            }""")
            assert flat_state["thickness"] == pytest.approx(0.24, abs=1e-5)
            assert flat_state["output"] == "0.24 A"
            assert flat_state["customVisible"] is True
            assert flat_state["color"] == "#18a7d8"

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
            page.wait_for_function("""() => {
                const meshes = window.__ASE_APP__.renderer.bondGroup.children;
                return meshes.length === 2
                    && meshes.reduce((sum, mesh) => sum + mesh.userData.bondSegments.length, 0) === 2;
            }""")
            split_colors = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    actual: renderer.bondGroup.children
                        .map(mesh => `#${mesh.material.color.getHexString()}`).sort(),
                    expected: [renderer.atomVisualColor(0), renderer.atomVisualColor(1)]
                        .map(color => color.toLowerCase()).sort()
                };
            }""")
            assert split_colors["actual"] == split_colors["expected"]

            page.fill('#super-x', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[0] === 2")
            page.fill('#super-y', '2')
            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[1] === 2")
            page.fill('#super-z', '2')
            page.locator('#bond-pairs').click()
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[2] === 2")
            assert page.evaluate("window.__ASE_APP__.state.display.supercell") == [2, 2, 2]
            repeated = page.evaluate("""() => {
                const children = window.__ASE_APP__.renderer.supercellGroup.children;
                const atoms = children.filter(child => child.userData.supercellInstanced);
                const bonds = children.filter(child => child.userData.supercellBonds);
                return {
                    atomInstances: atoms.reduce((sum, mesh) => sum + mesh.count, 0),
                    bondInstances: bonds.reduce((sum, mesh) => sum + mesh.count, 0),
                    atomMeshes: atoms.length,
                    bondMeshes: bonds.length,
                    atomTransparent: atoms.some(mesh => mesh.material.transparent),
                    atomOpacity: atoms.map(mesh => mesh.material.opacity),
                    selectableChildren: window.__ASE_APP__.renderer.atomMeshes.children.length,
                };
            }""")
            assert repeated["atomInstances"] == 14
            assert repeated["bondInstances"] == 14
            assert repeated["atomMeshes"] >= 1
            assert repeated["bondMeshes"] == 2
            assert repeated["atomTransparent"] is False
            assert repeated["atomOpacity"] == [1]
            assert repeated["selectableChildren"] == 2
            repeated_hover = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const Vector3 = renderer.camera.position.constructor;
                const target = new Vector3(8, 0, 0);
                renderer.camera.position.set(13, -20, 7);
                renderer.camera.up.set(0, 0, 1);
                renderer.controls.target.copy(target);
                renderer.camera.lookAt(target);
                renderer.camera.updateMatrixWorld(true);
                renderer.scene.updateMatrixWorld(true);
                const screen = target.clone().project(renderer.camera);
                const pointer = {
                    clientX: (screen.x + 1) * 0.5 * window.innerWidth,
                    clientY: (1 - screen.y) * 0.5 * window.innerHeight,
                };
                return {
                    hover: app.selection.pickHover(pointer, renderer.atomMeshes, renderer.supercellGroup),
                    selectable: app.selection.pick(pointer, renderer.atomMeshes),
                    clientX: pointer.clientX,
                    clientY: pointer.clientY,
                };
            }""")
            assert repeated_hover["hover"] == 0
            assert repeated_hover["selectable"] is None
            page.mouse.move(repeated_hover["clientX"], repeated_hover["clientY"])
            page.wait_for_function("window.__ASE_APP__.state.hoveredIndex === 0")
            assert "#0 H" in page.locator('#hover-readout').inner_text()
            for control in ('#super-x', '#super-y', '#super-z'):
                page.fill(control, '1')
                page.keyboard.press('Tab')
            page.wait_for_function(
                "window.__ASE_APP__.state.display.supercell.every(value => value === 1)"
            )

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
