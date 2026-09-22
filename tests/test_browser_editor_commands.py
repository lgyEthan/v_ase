"""Exact platform document chords must route before viewport letters."""

import os
import numpy as np
import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view
from v_ase.volumetric import VolumetricData


def windows_page(browser):
    page = browser.new_page()
    page.add_init_script("""Object.defineProperty(navigator, 'userAgentData', {
        configurable:true, value:{platform:'Windows'}});
        Object.defineProperty(navigator, 'platform', {
            configurable:true, value:'Win32'});""")
    return page


def test_modified_editor_routes_do_not_change_selection_or_transform():
    editor = view(Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]]),
                  notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.evaluate("window.__ASE_APP__.applySelectionAction({references:[0],origin:'semantic'})")
            cases = [
                ("Control+Shift+b", "structure", "cell-replication"),
                ("Control+Shift+p", "structure", "appearance"),
                ("Control+b", "structure", "bonding"),
                ("Control+Shift+a", "export", "export"),
                ("Control+e", "structure", "cell-transform"),
            ]
            for shortcut, group, section in cases:
                page.keyboard.press(shortcut)
                state = page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    return {group: app.inspectorGroup,
                        section: document.getElementById('structure-section-select').value,
                        selected: [...app.state.selected], transform: app.transform.mode};
                }""")
                assert state == {"group": group, "section": section,
                                 "selected": [0], "transform": "IDLE"}
                if shortcut == 'Control+Shift+a':
                    assert page.locator('#renderer-lighting-mode').is_visible()
                    assert page.locator('#renderer-pixels-per-angstrom').is_visible()
                    page.wait_for_function("document.activeElement?.id === 'renderer-framing-mode'")
            page.wait_for_function("document.activeElement?.id === 'btn-cell-transform-switch-edit'")
            assert page.locator('#btn-cell-transform-switch-edit').is_visible()
            assert page.locator('#matrix-00').is_disabled()
            page.click('#btn-cell-transform-switch-edit')
            page.wait_for_function('window.__ASE_APP__.state.vizOnly === false')
            assert page.locator('#matrix-00').is_enabled()
            browser.close()
    finally:
        editor.close()


def test_mac_command_renderer_and_select_all_remain_distinct():
    editor = view(Atoms('H2', positions=[[0, 0, 0], [2, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.add_init_script("""Object.defineProperty(navigator, 'userAgentData', {
                configurable:true, value:{platform:'macOS'}});
                Object.defineProperty(navigator, 'platform', {
                    configurable:true, value:'MacIntel'});""")
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            page.keyboard.press('Meta+Shift+a')
            page.wait_for_function("window.__ASE_APP__.editorRoute === 'export'")
            assert page.locator('#renderer-pixels-per-angstrom').is_visible()
            page.wait_for_function("document.activeElement?.id === 'renderer-framing-mode'")
            page.evaluate('window.__ASE_APP__.renderer.domElement.focus()')
            page.keyboard.press('Meta+a')
            assert page.evaluate('window.__ASE_APP__.state.selected.size') == 2
            assert page.evaluate('window.__ASE_APP__.editorRoute') == 'export'
            assert page.locator('[data-editor-menu-action="save"] kbd').text_content() == '⌘S'
            assert page.locator('[data-editor-menu-action="save"]').get_attribute('aria-keyshortcuts') == 'Meta+S'
            page.click('#editor-search-toggle')
            page.locator('#editor-command-search').fill('Command Shift P')
            assert page.locator('#editor-navigator [data-editor-route="appearance"]').is_visible()
            page.locator('#editor-command-search').press('Enter')
            page.wait_for_function("document.activeElement?.id === 'atom-radius-scale-number'")
            page.evaluate('window.__ASE_APP__.showShortcutsModal()')
            assert '⌘Shift+P' in page.locator('#modal-container').inner_text()
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('platform', ['mac', 'windows'])
def test_plain_arrows_orbit_and_alt_option_arrows_step_only_the_active_timeline(platform):
    frames = [Atoms('H', positions=[[offset, 0, 0]]) for offset in (0, 0.4, 0.8)]
    editor = view(frames, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            browser_platform = 'macOS' if platform == 'mac' else 'Windows'
            navigator_platform = 'MacIntel' if platform == 'mac' else 'Win32'
            page.add_init_script(f"""Object.defineProperty(navigator, 'userAgentData', {{
                configurable:true, value:{{platform:'{browser_platform}'}}}});
                Object.defineProperty(navigator, 'platform', {{
                    configurable:true, value:'{navigator_platform}'}});""")
            page.goto(editor.url)
            page.wait_for_function('''() => window.__ASE_APP__?.collaborationReady
                && window.__ASE_APP__?.state?.atoms?.metadata?.frame_count===3''')
            page.locator('#app-viewport canvas').focus()
            previous = page.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()')
            structure_before = page.evaluate('window.__ASE_APP__.state.atoms.positions')
            for key in ('ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'):
                page.keyboard.press(key)
                current = page.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()')
                assert current['position'] != pytest.approx(previous['position'], abs=1e-8)
                assert page.evaluate('window.__ASE_APP__.state.atoms.metadata.current_frame') == 0
                assert page.evaluate('window.__ASE_APP__.state.atoms.positions') == structure_before
                previous = current
            page.locator('#tool-select').click()
            button_camera = page.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()')
            page.keyboard.press('ArrowRight')
            assert page.evaluate('''() => window.__ASE_APP__.cameraSettingsSnapshot().position''') \
                != pytest.approx(button_camera['position'], abs=1e-8)
            assert page.evaluate('window.__ASE_APP__.state.atoms.metadata.current_frame') == 0
            page.keyboard.press('Alt+ArrowRight')
            page.wait_for_function('window.__ASE_APP__.state.atoms.metadata.current_frame===1')
            page.keyboard.press('Alt+ArrowLeft')
            page.wait_for_function('window.__ASE_APP__.state.atoms.metadata.current_frame===0')

            page.locator('#movie-fps').focus()
            before_input = page.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()')
            page.keyboard.press('ArrowUp')
            page.keyboard.press('Alt+ArrowRight')
            assert page.evaluate('window.__ASE_APP__.state.atoms.metadata.current_frame') == 0
            assert page.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()') == before_input

            page.evaluate('window.__ASE_APP__.showShortcutsModal()')
            help_text = page.locator('#modal-container').inner_text()
            assert ('Option+← / Option+→' if platform == 'mac'
                    else 'Alt+← / Alt+→') in help_text
            assert 'Orbit or tilt the structure view' in help_text
            browser.close()
    finally:
        editor.close()


def test_renderer_route_controls_committed_physical_scale_without_viewport_zoom_change():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            before = page.evaluate('''() => ({
                zoom:window.__ASE_APP__.renderer.currentPixelsPerAngstrom(),
                radius:window.__ASE_APP__.renderer.atomVisualRadius(0)
            })''')
            page.keyboard.press('Control+Shift+a')
            visible_controls = page.evaluate('''() => {
                const ids = ['renderer-pixels-per-angstrom', 'renderer-lighting-mode'];
                return ids.map(id => {
                    const rect = document.getElementById(id).getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && rect.top >= 0
                        && rect.bottom <= window.innerHeight;
                });
            }''')
            assert visible_controls == [True, True]
            if path := os.environ.get('V_ASE_RENDERER_QA_SCREENSHOT'):
                page.screenshot(path=path, full_page=True)
            page.locator('#renderer-framing-mode').select_option('physical')
            page.locator('#renderer-pixels-per-angstrom').fill('47')
            page.locator('#renderer-pixels-per-angstrom').press('Tab')
            after = page.evaluate('''() => ({
                zoom:window.__ASE_APP__.renderer.currentPixelsPerAngstrom(),
                radius:window.__ASE_APP__.renderer.atomVisualRadius(0),
                mode:window.__ASE_APP__.currentImageExportProfile().options.scaleMode,
                scale:window.__ASE_APP__.currentImageExportProfile().options.pixelsPerAngstrom
            })''')
            assert after['zoom'] == pytest.approx(before['zoom'])
            assert after['radius'] == pytest.approx(before['radius'])
            assert after['mode'] == 'physical'
            assert after['scale'] == 47
            browser.close()
    finally:
        editor.close()


def test_render_format_routes_expose_drafts_without_mutating_project_on_cancel():
    frames = [Atoms('H', positions=[[offset, 0, 0]]) for offset in (0, 0.5, 1.0)]
    editor = view(frames, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 3')
            baseline = page.evaluate('''() => ({
                image:window.__ASE_APP__.currentImageExportProfile().format,
                video:window.__ASE_APP__.state.display.videoFps
            })''')
            page.evaluate("window.__ASE_APP__.openEditorRoute('render-image')")
            assert page.locator('#renderer-image-format').is_visible()
            assert not page.locator('#renderer-video-format').is_visible()
            page.locator('#renderer-image-format').select_option('webp')
            page.click('#btn-export-image')
            assert page.locator('#export-image-format').input_value() == 'webp'
            page.click('#modal-close')

            page.evaluate("window.__ASE_APP__.openEditorRoute('render-video')")
            assert page.locator('#renderer-video-format').is_visible()
            assert not page.locator('#renderer-image-format').is_visible()
            page.locator('#renderer-video-format').select_option('avi')
            page.locator('#renderer-video-fps').fill('24')
            page.locator('#renderer-video-interpolation').fill('3')
            page.locator('#renderer-video-interpolation').press('Tab')
            assert '7 output frames' in page.locator('#renderer-video-estimate').inner_text()
            page.click('#btn-export-video')
            assert page.locator('#video-format').input_value() == 'avi'
            assert page.locator('#video-fps').input_value() == '24'
            assert page.locator('#video-interpolation-multiplier').input_value() == '3'
            page.click('#modal-close')

            page.evaluate("window.__ASE_APP__.openEditorRoute('render-html')")
            assert page.locator('#renderer-html-embed-project').is_visible()
            page.locator('#renderer-html-embed-project').check()
            page.click('#btn-export-html')
            assert page.locator('#html-embed-project').is_checked()
            page.click('#html-export-cancel')
            after = page.evaluate('''() => ({
                image:window.__ASE_APP__.currentImageExportProfile().format,
                video:window.__ASE_APP__.state.display.videoFps
            })''')
            assert after == baseline
            browser.close()
    finally:
        editor.close()


def test_scene_field_objects_expose_real_surface_and_plane_properties():
    atoms = Atoms('H', positions=[[0, 0, 0]], cell=[5, 5, 5], pbc=True)
    field = VolumetricData(name='charge', values=np.ones((4, 4, 4)),
                           cell=atoms.cell.array, pbc=atoms.pbc, quantity='density')
    editor = view(atoms, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False, volumetric_datasets=[field])
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.volumetricDatasets()?.length === 1')
            page.evaluate("window.__ASE_APP__.openEditorRoute('scene-fields')")
            assert page.locator('#volume-tool-surface').evaluate(
                'element => element.parentElement.id') == 'scene-field-surface-properties'
            assert page.locator('#volume-level').is_visible()
            assert page.locator('#volume-surface-mode').is_visible()
            page.evaluate('''() => {
                const app = window.__ASE_APP__;
                app.createVolumetricPlane();
                app.renderSceneContextObjects();
            }''')
            plane = page.locator('#scene-field-list button').filter(has_text='plane').first
            plane.click()
            assert page.locator('#volume-plane-editor').evaluate(
                'element => element.parentElement.id') == 'scene-field-plane-properties'
            assert page.locator('#volume-plane-h').is_visible()
            assert page.locator('#volume-plane-colormap').is_visible()
            page.evaluate("window.__ASE_APP__.openEditorRoute('volumetric')")
            assert page.locator('#volume-plane-editor').evaluate(
                'element => element.parentElement.id') == 'volume-tool-planes'
            browser.close()
    finally:
        editor.close()


def test_command_search_reveals_exact_control_and_empty_state():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.locator('#editor-search-toggle').click()
            search = page.locator('#editor-command-search')
            search.fill('pixels per angstrom')
            assert page.locator('#workbench-tabs [data-workbench="render"]').is_visible()
            search.press('Enter')
            page.wait_for_function("document.activeElement?.id === 'renderer-pixels-per-angstrom'")
            page.locator('#editor-search-toggle').click()
            search.fill('a deliberately nonexistent command')
            assert page.locator('#editor-command-empty').is_visible()
            browser.close()
    finally:
        editor.close()


def test_build_and_analyze_routes_expose_distinct_property_bodies():
    editor = view(Atoms('H2', positions=[[0, 0, 0], [1, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False,
                  viz_only=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            page.evaluate("window.__ASE_APP__.openEditorRoute('transform')")
            assert page.locator('#rotate-pivot').is_visible()
            assert not page.locator('#chk-commensurate-guide').is_visible()
            page.evaluate("window.__ASE_APP__.openEditorRoute('build-match')")
            assert page.locator('#chk-commensurate-guide').is_visible()
            assert not page.locator('#rotate-pivot').is_visible()
            page.evaluate("window.__ASE_APP__.openEditorRoute('build-rigid')")
            assert page.locator('#registry-translation-space').is_visible()
            assert not page.locator('#registry-metric').is_visible()
            page.evaluate("window.__ASE_APP__.openEditorRoute('registry-map')")
            assert page.locator('#registry-metric').is_visible()
            assert not page.locator('#btn-registry-relax-activate').is_visible()
            page.evaluate("window.__ASE_APP__.openEditorRoute('scene-vectors')")
            assert page.locator('#scene-displacement-visible').is_visible()
            assert page.locator('#displacement-style').is_visible()
            assert page.locator('#force-vector-style').is_visible()
            assert page.locator('#displacement-style-controls').evaluate(
                "element => element.parentElement.id") == 'scene-displacement-style'
            page.locator('#scene-displacement-visible').check()
            assert page.locator('#chk-displacement').is_checked()
            page.evaluate("window.__ASE_APP__.openEditorRoute('scene-fields')")
            assert page.locator('#displacement-style-controls').evaluate(
                "element => element.parentElement.dataset.panel") == 'displacement'
            assert 'No field datasets loaded' in page.locator('#scene-field-list').inner_text()
            assert page.locator('#volume-tool-surface').evaluate(
                "element => element.parentElement.id") == 'scene-field-surface-properties'
            assert not page.locator('#volume-level').is_visible()
            page.evaluate("window.__ASE_APP__.openEditorRoute('volumetric')")
            assert page.locator('#volume-tool-surface').evaluate(
                "element => element.parentElement.id") == 'volume-controls'
            browser.close()
    finally:
        editor.close()


def test_required_shortcuts_commit_valid_fields_retain_invalid_drafts_and_block_transforms():
    editor = view(Atoms('H', positions=[[0, 0, 0]], cell=[6, 6, 6], pbc=True),
                  notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False, viz_only=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.keyboard.press('Control+Shift+b')
            repeat = page.locator('#super-x')
            repeat.fill('0')
            repeat.press('Control+Shift+p')
            assert page.evaluate("document.activeElement?.id") == 'super-x'
            assert page.evaluate('window.__ASE_APP__.editorRoute') == 'cell-replication'
            repeat.fill('2')
            repeat.press('Control+Shift+p')
            page.wait_for_function("document.activeElement?.id === 'atom-radius-scale-number'")
            assert page.evaluate('window.__ASE_APP__.state.display.supercell[0]') == 2
            page.evaluate('''() => {
                const element=document.createElement('div');
                element.contentEditable='true';
                element.id='editable-key-test';
                document.body.appendChild(element);
                element.focus();
            }''')
            page.keyboard.press('g')
            assert page.evaluate('window.__ASE_APP__.transform.mode') == 'IDLE'
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.applySelectionAction({references:[0],origin:'semantic'});
                app.enterTransformMode('MOVE');
                window.__saveCalls=0;
                app.saveDocument=async()=>{window.__saveCalls++};
                app.renderer.domElement.focus();
            }''')
            page.keyboard.press('Control+s')
            assert page.evaluate('window.__saveCalls') == 0
            assert page.evaluate('window.__ASE_APP__.transform.mode') == 'MOVE'
            browser.close()
    finally:
        editor.close()


def test_escape_settles_confirmation_instead_of_hiding_pending_dialog():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("""() => {
                window.__confirmResult = 'pending';
                window.__ASE_APP__.showConfirmModal({title:'Close?', intro:'Test', items:[]})
                    .then(value => window.__confirmResult = value);
            }""")
            page.keyboard.press("Escape")
            page.wait_for_function("window.__confirmResult === false")
            assert page.locator('#modal-container').evaluate("node => node.classList.contains('hidden')")
            browser.close()
    finally:
        editor.close()


def test_modal_owns_keyboard_and_blocks_background_edit_and_document_commands():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), viz_only=False,
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.applySelectionAction({references:[0],origin:'semantic'});
                app.markProjectSavedContent();
                app.state.display.atomRadiusScale = 0.8;
                app.renderer.setDisplayOptions({atomRadiusScale:0.8});
                window.__closeResult = 'pending';
                app.showSaveDiscardCancelModal().then(choice => window.__closeResult = choice);
            }""")
            page.locator('#modal-keep-editing').focus()
            for key in ('g', 'r', 's', 'Delete', 'Control+z', 'Control+Shift+s'):
                page.keyboard.press(key)
            state = page.evaluate("""() => ({
                mode:window.__ASE_APP__.transform.mode,
                modalVisible:!document.getElementById('modal-container').classList.contains('hidden'),
                choice:window.__closeResult,
                atomCount:window.__ASE_APP__.state.atoms.positions.length
            })""")
            assert state == {'mode':'IDLE','modalVisible':True,'choice':'pending','atomCount':1}
            page.keyboard.press('Escape')
            page.wait_for_function("window.__closeResult === 'cancel'")
            browser.close()
    finally:
        editor.close()


def test_shortcut_help_matches_the_editor_command_registry_without_old_inversion():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("window.__ASE_APP__.showShortcutsModal()")
            shortcuts = page.locator('#modal-container .shortcut-grid > span').all_inner_texts()
            for chord in ("Ctrl+Shift+B", "Ctrl+Shift+P", "Ctrl+B", "Ctrl+Shift+A",
                          "Ctrl+E", "Ctrl+W", "Ctrl+S", "Ctrl+Shift+S", "Ctrl+N"):
                assert shortcuts.count(chord) == 1
            assert "Shift+Ctrl+A" not in shortcuts
            assert shortcuts.count("Shift+A") == 1
            assert "Hide the exact visual selection in View" in page.locator('#modal-container').inner_text()
            browser.close()
    finally:
        editor.close()


def test_output_pixels_per_angstrom_is_independent_of_live_viewport_scale():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            result = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const viewport = app.renderer.currentPixelsPerAngstrom();
                const saved = app.currentImageExportProfile().options.pixelsPerAngstrom;
                app.showExportImageModal();
                document.getElementById('export-framing-mode').value = 'physical';
                document.getElementById('export-framing-mode').dispatchEvent(new Event('change', {bubbles:true}));
                const input = document.getElementById('export-pixels-per-angstrom');
                input.value = '123.4';
                input.dispatchEvent(new Event('input', {bubbles:true}));
                const output = app.state.exportPreviewProfile.options.pixelsPerAngstrom;
                const live = app.renderer.currentPixelsPerAngstrom();
                app.closeModal();
                return {viewport, output, live, saved,
                    afterCancel: app.currentImageExportProfile().options.pixelsPerAngstrom};
            }""")
            assert result["output"] == pytest.approx(123.4)
            assert result["live"] == pytest.approx(result["viewport"])
            assert result["afterCancel"] == pytest.approx(result["saved"])
            browser.close()
    finally:
        editor.close()


def test_save_reuses_writable_target_and_save_as_adopts_new_target():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            result = page.evaluate("""async () => {
                    const app = window.__ASE_APP__;
                    const writes = [];
                    const fileVersions = new Map();
                    const handle = name => ({name,
                        queryPermission: async () => 'granted',
                        getFile: async () => fileVersions.get(name) || {size:0,lastModified:0},
                        createWritable: async () => ({
                            write: async blob => {
                                writes.push([name, blob.size]);
                                fileVersions.set(name, {size:blob.size,lastModified:writes.length});
                            },
                        close: async () => {}
                    })
                });
                const choices = [handle('first.vase'), handle('second.vase')];
                let pickers = 0;
                app.filePickerAdapter = {showSaveFilePicker: async () => {
                    pickers += 1;
                    return choices.shift();
                }};
                const first = await app.saveCompactProject();
                const second = await app.saveDocument();
                const as = await app.saveCompactProject({saveAs:true});
                return {first, second, as, pickers, writes,
                    filename: app.projectFile.filename,
                    kind: app.projectFile.lastSaveKind};
            }""")
            assert result["first"] is True
            assert result["second"] is True
            assert result["as"] is True
            assert result["pickers"] == 2
            assert [name for name, _ in result["writes"]] == ["first.vase", "first.vase", "second.vase"]
            assert all(size > 100 for _, size in result["writes"])
            assert result["filename"] == "second.vase"
            assert result["kind"] == "writable-file"
            browser.close()
    finally:
        editor.close()


def test_reused_browser_handle_rechecks_external_version_after_deferred_build():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = windows_page(browser)
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            result = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.markProjectSavedContent();
                app.state.display.atomRadiusScale = 0.8;
                app.renderer.setDisplayOptions({atomRadiusScale: 0.8});
                const outcomes = [];
                for (const format of ['vase', 'html']) {
                    let version = 1;
                    let size = 10;
                    let reads = 0;
                    let writes = 0;
                    const handle = {
                        name: `current.${format}`,
                        queryPermission: async () => 'granted',
                        getFile: async () => { reads += 1; return {size, lastModified: version}; },
                        createWritable: async () => {
                            writes += 1;
                            return {write: async () => {}, close: async () => {}};
                        }
                    };
                    Object.assign(app.projectFile, {
                        format, filename: handle.name, handle,
                        contentVersion: {size, lastModified: version}, serverBinding: null
                    });
                    let error = '';
                    try {
                        await app.writeProjectFile(format, handle.name, async () => {
                            version = 2;
                            size = 12;
                            return new Blob(['prepared']);
                        });
                    } catch (caught) { error = caught.message; }
                    outcomes.push({format, error, reads, writes, dirty:app.updateProjectDirtyState()});
                }
                return outcomes;
            }""")
            assert len(result) == 2
            assert all("changed outside" in item["error"] for item in result)
            assert all(item["reads"] >= 2 and item["writes"] == 0 for item in result)
            assert all(item["dirty"] is True for item in result)
            browser.close()
    finally:
        editor.close()


def test_semantic_camera_scale_only_and_fit_then_explicit_scale():
    editor = view(Atoms('H2', positions=[[0, 0, 0], [3.37, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1200, 'height': 800})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            for camera, expected in [
                ({'axis': '+Z', 'projection': 'orthographic', 'fit': 'structure', 'ortho_scale': 4}, {'ortho_scale': 4}),
                ({'ortho_scale': 3.5}, {'ortho_scale': 3.5}),
                ({'projection': 'perspective', 'fov': 42, 'zoom': 1.4, 'near': 0.2, 'far': 1234},
                 {'fov': 42, 'zoom': 1.4, 'near': 0.2, 'far': 1234}),
            ]:
                actual = page.evaluate('''async camera => {
                    await window.v_aseAI.apply({camera});
                    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                    return window.__ASE_APP__.currentCameraForExport();
                }''', camera)
                for key, value in expected.items():
                    assert actual[key] == pytest.approx(value, abs=1e-9)
            browser.close()
    finally:
        editor.close()
