"""The approved single-workbench editor shares one resize-aware canvas grid."""

import os
from pathlib import Path

import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view
from tests.ui_navigation import ROUTE_GROUPS, open_editor_route


def test_editor_shell_docks_viewport_and_reveals_one_scoped_route():
    editor = view(Atoms("CuO", positions=[[0, 0, 0], [2, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            if path := os.environ.get("V_ASE_UI_QA_SCREENSHOT"):
                page.screenshot(path=path.replace('.png', '-before.png'), full_page=True)
            assert page.locator('#workbench-tabs [data-workbench="style"]').get_attribute('aria-selected') == 'true'
            assert page.locator('#editor-navigator').is_hidden()
            assert page.locator('#objects-drawer').is_hidden()
            page.get_by_role('tab', name='Analyze').click()
            assert page.locator('body').get_attribute('data-current-editor-route') == 'selection'
            page.get_by_role('tab', name='Style').click()
            assert page.locator('body').get_attribute('data-current-editor-route') == 'appearance'
            state = page.evaluate("""() => {
                const box = id => {
                    const rect = document.getElementById(id).getBoundingClientRect();
                    return {x:rect.x,y:rect.y,width:rect.width,height:rect.height};
                };
                return {navigator:box('editor-navigator'), viewport:box('app-viewport'),
                    inspector:box('inspector'), footer:box('command-bar'),
                    route: document.body.dataset.currentEditorRoute,
                    visiblePanels: [...document.querySelectorAll('#inspector-content [data-panel]')]
                        .filter(node => getComputedStyle(node).display !== 'none')
                        .map(node => node.dataset.panel)};
            }""")
            assert state["route"] == "appearance"
            assert state["visiblePanels"] == ["appearance"]
            assert state["navigator"]["width"] == 0
            assert state["viewport"]["x"] == pytest.approx(0, abs=2)
            assert state["inspector"]["width"] == pytest.approx(352, abs=2)
            assert state["viewport"]["x"] + state["viewport"]["width"] == pytest.approx(
                1440, abs=2)
            assert state["viewport"]["y"] + state["viewport"]["height"] <= state["footer"]["y"] + 2
            route_inventory = page.evaluate("""() => {
                const app=window.__ASE_APP__;
                return [...document.querySelectorAll('#editor-navigator [data-editor-route]')]
                    .map(button => {
                        const route=button.dataset.editorRoute;
                        const opened=app.openEditorRoute(route);
                        const visible=[...document.querySelectorAll('#inspector-content [data-panel]')]
                            .filter(node => getComputedStyle(node).display !== 'none')
                            .map(node => node.dataset.panel);
                        return {route,opened,visible};
                    });
            }""")
            assert all(item['opened'] and len(item['visible']) == 1 for item in route_inventory)
            page.get_by_role('tab', name='Style').click()
            page.click('#btn-objects')
            assert page.locator('#objects-list .objects-row').count() >= 1
            page.click('#btn-objects-close')
            if path := os.environ.get("V_ASE_UI_QA_SCREENSHOT"):
                page.screenshot(path=path, full_page=True)
            browser.close()
    finally:
        editor.close()


def test_workbench_responsive_routes_objects_and_theme():
    editor = view(Atoms("CuO", positions=[[0, 0, 0], [2, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            shots = os.environ.get('V_ASE_UI_QA_DIR')
            for width, height in [(1440, 960), (1024, 768), (390, 844)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(120)
                metrics = page.evaluate("""() => ({
                    scroll:document.documentElement.scrollWidth,
                    width:document.documentElement.clientWidth,
                    viewport:document.getElementById('app-viewport').getBoundingClientRect().toJSON(),
                    inspector:document.getElementById('inspector').getBoundingClientRect().toJSON()
                })""")
                assert metrics['scroll'] <= metrics['width'] + 1
                assert metrics['viewport']['width'] >= (320 if width == 390 else 500)
                if width > 760:
                    assert metrics['inspector']['width'] == pytest.approx(324 if width == 1024 else 352, abs=2)
                else:
                    assert metrics['inspector']['y'] >= metrics['viewport']['bottom'] - 1
                if shots:
                    Path(shots).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(shots) / f'editor-{width}.png'), full_page=True)
            page.get_by_role('tab', name='Build').click()
            assert page.locator('#workbench-route-add-atoms').get_attribute('aria-selected') == 'true'
            page.locator('#workbench-route-cell-transform').click()
            assert page.locator('#matrix-00').is_visible()
            if shots:
                page.screenshot(path=str(Path(shots) / 'editor-build-390.png'), full_page=True)
            page.get_by_role('tab', name='Analyze').click()
            page.locator('#workbench-route-rdf').click()
            assert page.locator('[data-panel="rdf"]').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.get_by_role('tab', name='Render').click()
            assert page.locator('#renderer-pixels-per-angstrom').is_visible()
            page.click('#btn-objects')
            assert page.locator('#objects-list [data-object-id="atoms"]').count() == 1
            page.locator('#objects-list [data-object-id="atoms"]').click()
            assert page.locator('[data-panel="structure-info"]').is_visible()
            page.locator('#workbench-context-back').click()
            assert page.locator('body').get_attribute('data-current-editor-route') == 'export'
            page.evaluate("window.v_aseTheme.apply('dark')")
            if shots:
                page.screenshot(path=str(Path(shots) / 'editor-dark-390.png'), full_page=True)
            assert not errors
            browser.close()
    finally:
        editor.close()


def test_objects_visibility_and_fit_use_live_state_without_changing_atoms():
    editor = view(Atoms('CuO', positions=[[0, 0, 0], [1.5, 0, 0]],
                        cell=[8, 8, 8], pbc=True),
                  notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            assert page.evaluate('window.__ASE_APP__.renderer.bondPairs?.length') > 0
            initial = page.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
            page.click('#btn-objects')
            page.get_by_role('checkbox', name='Show Bonds').uncheck()
            assert page.locator('#chk-bonds').is_checked() is False
            assert page.locator('body').get_attribute('data-current-editor-route') == 'appearance'
            page.locator('#objects-list [data-object-id="cell"]').click()
            assert page.locator('body').get_attribute('data-current-editor-route') == 'cell-replication'
            page.locator('#app-viewport canvas').first.focus()
            page.keyboard.press('f')
            assert page.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == initial
            page.get_by_role('button', name='Top', exact=True).click()
            assert page.evaluate("""() => {
                const app=window.__ASE_APP__,delta=app.renderer.camera.position.clone().sub(app.renderer.controls.target);
                return delta.z > 0 && Math.abs(delta.x) < 1e-6 && Math.abs(delta.y) < 1e-6;
            }""")
            browser.close()
    finally:
        editor.close()


def test_initial_narrow_editor_has_visible_scene_and_stacked_controls():
    editor = view(Atoms('CuO', positions=[[0, 0, 0], [2, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            if directory := os.environ.get('V_ASE_UI_QA_DIR'):
                page.screenshot(path=str(Path(directory) / 'editor-initial-390.png'), full_page=True)
            bounds = page.evaluate("""() => {
                const app = window.__ASE_APP__, viewport=document.getElementById('app-viewport').getBoundingClientRect();
                const atoms=[0,1].map(i => {
                    const mesh=app.renderer.atomMeshByIndex.get(i);
                    const p=mesh.getWorldPosition(mesh.position.clone());
                    p.project(app.renderer.camera);
                    return [viewport.left+(p.x+1)*viewport.width/2,viewport.top+(1-p.y)*viewport.height/2];
                });
                return {viewport:viewport.toJSON(),atoms};
            }""")
            assert all(0 <= x <= 390 and 49 <= y <= 514 for x, y in bounds['atoms'])
            assert page.locator('#inspector').is_visible()
            browser.close()
    finally:
        editor.close()


def test_every_primary_workbench_route_reaches_one_real_form():
    editor = view(Atoms('H2', positions=[[0, 0, 0], [1, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 960})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            for routes in ROUTE_GROUPS.values():
                for route in routes:
                    open_editor_route(page, route)
                    assert page.locator('body').get_attribute('data-current-editor-route') == route
                    assert page.locator('#inspector-content .editor-route-current').count() == 1
                    assert page.locator('#inspector-content .editor-route-current').is_visible()
            duplicates = page.evaluate("""() => {
                const seen=new Set();
                return [...document.querySelectorAll('[id]')]
                    .map(node=>node.id).filter(id=>seen.has(id)||!seen.add(id));
            }""")
            assert duplicates == []
            assert not errors
            browser.close()
    finally:
        editor.close()


def test_style_scope_reuses_real_global_label_and_selected_radius_controls():
    editor = view(Atoms('HO', positions=[[0, 0, 0], [1.1, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            assert page.locator('#appearance-scope-select option[value="selected"]').get_attribute('disabled') is not None
            page.locator('#appearance-scope-select').select_option('H')
            assert page.locator('#appearance-scope-select').input_value() == 'H'
            page.select_option('#appearance-material', 'metal')
            page.fill('#appearance-opacity', '0.7')
            page.locator('#appearance-opacity').press('Tab')
            assert page.evaluate('window.__ASE_APP__.atomMaterialPreset(0)') == 'metal'
            assert page.evaluate('window.__ASE_APP__.atomMaterialPreset(1)') == 'standard'
            assert page.evaluate('window.__ASE_APP__.atomManualOpacity(0)') == pytest.approx(0.7)
            assert page.evaluate('window.__ASE_APP__.atomManualOpacity(1)') == pytest.approx(1)
            page.evaluate("window.__ASE_APP__.applySelectionAction({references:[0],origin:'semantic'})")
            page.locator('#appearance-scope-select').select_option('selected')
            assert page.evaluate('document.activeElement?.id') == 'selected-atom-radius-scale-number'
            assert page.locator('#workbench-selection-label').inner_text().startswith('H · H')
            page.locator('#selected-atom-radius-scale-number').fill('1.2')
            page.locator('#selected-atom-radius-scale-number').press('Tab')
            assert page.evaluate('window.__ASE_APP__.state.display.atomRadiusScales[0]') == pytest.approx(1.2)
            assert page.locator('#atom-radius-scale-number').input_value() == '0.6'
            browser.close()
    finally:
        editor.close()


def test_selected_radius_is_live_without_committing_pending_label_edit():
    editor = view(Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.get_by_role('tab', name='Atoms').click()
            page.evaluate("window.__ASE_APP__.applySelectionAction({references:[0],origin:'semantic'})")
            before = page.evaluate("window.__ASE_APP__.renderer.atomVisualRadius(0)")
            page.fill('#selected-atom-label', 'O')
            page.locator('#selected-atom-radius-scale-number').fill('1.5')
            page.locator('#selected-atom-radius-scale-number').press('Tab')
            after = page.evaluate("""() => {
                const app=window.__ASE_APP__;
                return {radius:app.renderer.atomVisualRadius(0),
                    symbol:app.state.atoms.symbols[0],
                    labelDraft:document.getElementById('selected-atom-label').value,
                    scale:app.state.display.atomRadiusScales[0]};
            }""")
            assert after['radius'] == pytest.approx(before * 1.5)
            assert after['symbol'] == 'H'
            assert after['labelDraft'] == 'O'
            assert after['scale'] == pytest.approx(1.5)
            browser.close()
    finally:
        editor.close()


def test_global_radius_number_and_slider_keep_exact_hundredth_value():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.get_by_role('tab', name='Atoms').click()
            page.fill('#atom-radius-scale-number', '0.62')
            page.locator('#atom-radius-scale-number').press('Tab')
            assert page.locator('#atom-radius-scale').input_value() == '0.62'
            assert page.locator('#atom-radius-scale-number').input_value() == '0.62'
            assert page.locator('#atom-radius-scale-value').inner_text() == '0.62x'
            assert page.evaluate('window.__ASE_APP__.state.display.atomRadiusScale') == pytest.approx(0.62)
            browser.close()
    finally:
        editor.close()


def test_continuous_scientific_sliders_have_editable_number_controls():
    editor = view(Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            controls = page.evaluate("""() => [...document.querySelectorAll('input[type=range][id]')]
                .filter(input => !['frame-slider','secondary-frame-slider',
                    'volume-level-slider','volume-plane-offset-slider'].includes(input.id))
                .map(input => ({id:input.id,
                    number:document.getElementById(input.id+'-number')?.type}))""")
            assert controls and all(item['number'] == 'number' for item in controls)
            page.get_by_role('tab', name='Bonds').click()
            page.fill('#bond-thickness-number', '0.31')
            page.locator('#bond-thickness-number').press('Tab')
            assert page.locator('#bond-thickness').input_value() == '0.31'
            assert page.evaluate('window.__ASE_APP__.state.display.bondThickness') == pytest.approx(0.31)
            page.fill('#bond-thickness-number', '')
            page.locator('#bond-thickness-number').press('Tab')
            assert page.locator('#bond-thickness-number').input_value() == ''
            assert page.evaluate('window.__ASE_APP__.state.display.bondThickness') == pytest.approx(0.31)
            browser.close()
    finally:
        editor.close()


def test_narrow_search_popover_keeps_workbench_visible():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 780, "height": 700})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.click('#editor-search-toggle')
            assert page.locator('body').evaluate("node => node.classList.contains('editor-search-open')")
            assert page.locator('#inspector').is_visible()
            page.locator('#editor-command-search').fill('atom radius')
            page.locator('#editor-command-search').press('Enter')
            assert page.locator('body').get_attribute('data-current-editor-route') == 'appearance'
            assert not page.locator('body').evaluate("node => node.classList.contains('editor-search-open')")
            assert page.locator('body').get_attribute('data-current-editor-route') == 'appearance'
            browser.close()
    finally:
        editor.close()


def test_panel_resize_is_not_dirty_and_restoring_saved_content_cleans_tab():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("window.__ASE_APP__.markProjectSavedContent()")
            page.get_by_role('tab', name='Atoms').click()
            assert page.evaluate("window.__ASE_APP__.updateProjectDirtyState()") is False
            saved = page.locator('#atom-radius-scale').input_value()
            page.locator('#atom-radius-scale').evaluate("element => {element.value='0.8';element.dispatchEvent(new Event('input',{bubbles:true}));}")
            assert page.evaluate("window.__ASE_APP__.updateProjectDirtyState()") is True
            page.locator('#atom-radius-scale').evaluate("(element,value) => {element.value=value;element.dispatchEvent(new Event('input',{bubbles:true}));}", saved)
            assert page.evaluate("window.__ASE_APP__.updateProjectDirtyState()") is False
            browser.close()
    finally:
        editor.close()


def test_selected_radius_slow_drag_is_one_undo_action():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            result = page.evaluate("""async () => {
                const app=window.__ASE_APP__;
                app.openEditorRoute('appearance');
                app.applySelectionAction({references:[0],origin:'semantic'});
                const slider=document.getElementById('selected-atom-radius-scale');
                slider.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
                slider.value='1.2';slider.dispatchEvent(new Event('input',{bubbles:true}));
                await new Promise(resolve=>setTimeout(resolve,240));
                slider.value='1.5';slider.dispatchEvent(new Event('input',{bubbles:true}));
                slider.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));
                slider.dispatchEvent(new Event('change',{bubbles:true}));
                return {actions:app.undoTimeline.filter(item=>item.source==='selected-radius-scale').length,
                    radius:app.renderer.atomVisualRadius(0)};
            }""")
            assert result['actions'] == 1
            assert result['radius'] > 0
            browser.close()
    finally:
        editor.close()


def test_short_window_switches_results_to_full_work_area_with_back_action():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 720, "height": 430})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("window.__ASE_APP__.showAnalysisDrawer('rdf','Pair distribution')")
            drawer = page.locator('#analysis-drawer').bounding_box()
            assert drawer is not None
            assert drawer['y'] == pytest.approx(49, abs=1)
            assert drawer['height'] >= 380
            page.click('#btn-results-back')
            assert page.locator('#analysis-drawer').is_hidden()
            browser.close()
    finally:
        editor.close()


def test_desktop_results_dock_resizes_its_grid_track_without_changing_camera_scale():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("window.__ASE_APP__.markProjectSavedContent()")
            page.evaluate("window.__ASE_APP__.showAnalysisDrawer('rdf','Distribution')")
            page.wait_for_function("document.getElementById('analysis-drawer').getBoundingClientRect().height >= 225")
            before = page.evaluate("window.__ASE_APP__.renderer.currentPixelsPerAngstrom()")
            before_height = page.locator('#analysis-drawer').bounding_box()['height']
            resizer = page.locator('#analysis-drawer-resizer').bounding_box()
            assert resizer is not None
            x = resizer['x'] + resizer['width'] / 2
            y = resizer['y'] + resizer['height'] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x, y - 120, steps=4)
            page.mouse.up()
            page.wait_for_function("height => document.getElementById('analysis-drawer').getBoundingClientRect().height >= height + 115", arg=before_height)
            drawer = page.locator('#analysis-drawer').bounding_box()
            viewport = page.locator('#app-viewport').bounding_box()
            assert drawer['height'] == pytest.approx(before_height + 120, abs=3)
            assert viewport['y'] + viewport['height'] == pytest.approx(drawer['y'], abs=2)
            assert page.evaluate('window.__ASE_APP__.renderer.currentPixelsPerAngstrom()') == pytest.approx(before, rel=1e-4)
            assert page.evaluate('window.__ASE_APP__.updateProjectDirtyState()') is False
            browser.close()
    finally:
        editor.close()
