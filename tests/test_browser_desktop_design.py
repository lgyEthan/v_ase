"""Real controls for the native workspace composition and document scene bridge."""
import json

import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view
from tests.ui_navigation import open_editor_route


@pytest.fixture
def desktop_design_page():
    editor = view(Atoms('CuO', positions=[[0, 0, 0], [1.8, 0, 0]], cell=[7, 7, 7], pbc=True),
                  notebook=True, block=False, port=find_free_port(), viz_only=False,
                  close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            yield page
            browser.close()
    finally:
        editor.close()


def test_stage_target_is_centered_and_panel_changes_keep_camera_and_scale(desktop_design_page):
    p = desktop_design_page
    p.emulate_media(reduced_motion='reduce')
    snapshot = '''() => { const a=window.__ASE_APP__, r=a.renderer;
        const rect=r.domElement.getBoundingClientRect();
        const target=a.worldToScreen(r.controls.target);
        return {camera:a.cameraSettingsSnapshot(), scale:r.currentPixelsPerAngstrom(),
            atoms:a.state.atoms.positions, rect:rect.toJSON(),
            target:[target.x,target.y]}; }'''
    before = p.evaluate(snapshot)
    for width, collapsed in [(460, False), (320, True), (320, False)]:
        p.evaluate('([w,c])=>{const a=window.__ASE_APP__; a.setInspectorWidth(w); a.setInspectorCollapsed(c,false);}', [width, collapsed])
        p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        after = p.evaluate(snapshot)
        assert after['atoms'] == before['atoms']
        assert after['camera'] == before['camera']
        assert after['scale'] == pytest.approx(before['scale'], rel=1e-10)
        assert after['target'][0] == pytest.approx(after['rect']['x'] + after['rect']['width'] / 2, abs=.1)
        assert after['target'][1] == pytest.approx(after['rect']['y'] + after['rect']['height'] / 2, abs=.1)
    assert p.locator('#scene-navigator').is_visible()


def test_initial_ready_waits_for_input_availability_even_with_delayed_event():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True, open_browser=False,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            p = browser.new_page(viewport={'width': 1440, 'height': 900})
            p.add_init_script('''{
                const fetchOriginal=window.fetch.bind(window);
                window.fetch=async (input,options={})=>{
                    const url=typeof input==='string'?input:(input.url || String(input));
                    if (url.includes('/api/ai/events/') && typeof options.body==='string'
                        && JSON.parse(options.body).type==='session.ready') {
                        await new Promise(resolve=>window.releaseInitialReady=resolve);
                    }
                    return await fetchOriginal(input,options);
                };
            }''')
            p.goto(editor.url)
            p.wait_for_function('Boolean(window.releaseInitialReady)')
            assert p.evaluate('window.__ASE_APP__.collaborationReady') is False
            assert p.locator('#top-bar').evaluate('e=>e.inert')
            p.keyboard.press('Delete')
            assert p.evaluate('window.__ASE_APP__.state.atoms.positions.length') == 1
            p.evaluate('window.releaseInitialReady()')
            p.wait_for_function('window.__ASE_APP__.collaborationReady && !document.body.dataset.busy')
            shortcut = p.evaluate("window.__ASE_APP__.shortcutPlatform==='mac'?'Meta+Shift+a':'Control+Shift+a'")
            p.keyboard.press(shortcut)
            assert p.locator('body').get_attribute('data-current-editor-route') == 'export'
            assert p.locator('#btn-preview-image svg').is_visible()
            browser.close()
    finally:
        editor.close()


def test_named_tool_search_escape_and_repeated_route_refresh(desktop_design_page):
    p = desktop_design_page
    p.locator('#inspector-tool-trigger').click()
    # A same-route refresh must not close a menu the human is using.
    p.evaluate("window.__ASE_APP__.openEditorRoute('appearance')")
    assert p.locator('#inspector-tool-menu').is_visible()
    p.locator('#workbench-route-bonding').click()
    assert p.locator('body').get_attribute('data-current-editor-route') == 'bonding'
    assert p.locator('#inspector-tool-trigger').inner_text().strip() == 'Bonds'
    p.locator('#inspector-tool-trigger').click()
    p.keyboard.press('Escape')
    assert p.locator('#inspector-tool-menu').is_hidden()
    assert p.locator('#inspector-tool-trigger').evaluate('e=>e===document.activeElement')
    assert 'inspector-collapsed' not in p.locator('body').get_attribute('class')
    shortcut = p.evaluate("window.__ASE_APP__.shortcutPlatform==='mac'?'Meta+f':'Control+f'")
    opener=p.evaluate('document.activeElement.id')
    p.keyboard.press(shortcut)
    assert p.locator('#editor-command-search').evaluate('e=>e===document.activeElement')
    p.locator('#editor-command-search').fill('bonds')
    p.locator('#editor-command-search').press('Escape')
    assert p.evaluate('document.activeElement.id')==opener


def test_view_popup_keeps_controls_inside_its_surface_during_reveal(desktop_design_page):
    p = desktop_design_page
    result = p.evaluate('''async () => {
        const a=window.__ASE_APP__, popup=document.getElementById('camera-more-content');
        const camera=JSON.stringify(a.cameraSettingsSnapshot()), samples=[];
        document.getElementById('camera-rotation-toggle').click();
        const started=performance.now();
        do {
            const r=popup.getBoundingClientRect();
            const outside=[...popup.querySelectorAll('button,input,select')].filter(e=>{
                const b=e.getBoundingClientRect();
                return b.width && b.height && getComputedStyle(e).visibility!=='hidden'
                    && (b.left<r.left-1 || b.right>r.right+1 || b.top<r.top-1 || b.bottom>r.bottom+1);
            }).map(e=>e.id);
            samples.push({height:r.height,outside});
            await new Promise(requestAnimationFrame);
        } while(performance.now()-started<230);
        return {samples,cameraUnchanged:camera===JSON.stringify(a.cameraSettingsSnapshot())};
    }''')
    heights = [s['height'] for s in result['samples']]
    assert min(heights) > 100
    assert max(heights) - min(heights) < 1
    assert not [s for s in result['samples'] if s['outside']]
    assert result['cameraUnchanged']


def test_appearance_disclosure_retains_fields_focus_and_text_draft(desktop_design_page):
    p = desktop_design_page
    row = p.locator('#appearance-table .appearance-row').first
    label = row.locator('.atom-label-input')
    label.click()
    assert row.get_attribute('open') is None
    summary = row.locator(':scope > summary')
    summary.focus(); summary.press('Enter')
    assert row.locator('.label-radius-input').is_visible()
    label.fill('Cu_custom_draft')
    label.evaluate('e=>e.setSelectionRange(3,9)')
    p.evaluate('window.__ASE_APP__.renderAppearanceRows()')
    row = p.locator('#appearance-table .appearance-row').first
    assert row.get_attribute('open') is not None
    assert row.locator('.atom-label-input').input_value() == 'Cu_custom_draft'
    assert row.locator('.atom-label-input').evaluate('e=>e===document.activeElement && e.selectionStart===3 && e.selectionEnd===9')
    assert row.locator('.appearance-material-select').is_visible()
    assert p.locator('#appearance-table').evaluate('e=>e.scrollWidth<=e.clientWidth+1')


def test_image_inspector_edits_the_same_exact_export_profile(desktop_design_page):
    p = desktop_design_page
    open_editor_route(p, 'render-image')
    p.locator('#image-width').fill('640')
    p.locator('#image-height').fill('480')
    p.locator('#renderer-image-transparent').check()
    p.locator('#renderer-image-transparent').press('Tab')
    profile = p.evaluate('window.__ASE_APP__.currentImageExportProfile()')
    assert (profile['width'], profile['height']) == (640, 480)
    assert p.locator('#image-height').evaluate('e=>e.validity.valid')
    assert profile['options']['transparentBackground']
    p.locator('#btn-export-image').click()
    assert p.locator('#export-width').input_value() == '640'
    assert p.locator('#export-height').input_value() == '480'
    p.keyboard.press('Escape')
    open_editor_route(p, 'export')
    assert p.locator('.renderer-output-group #image-width').is_visible()
    assert p.locator('#image-width').input_value() == '640'


def test_busy_export_saves_actual_bytes_and_restores_input(desktop_design_page, tmp_path):
    from PIL import Image
    p = desktop_design_page
    open_editor_route(p, 'render-image')
    p.locator('#image-width').fill('512'); p.locator('#image-height').fill('384')
    p.locator('#renderer-image-format').focus()
    p.locator('#btn-export-image').click()
    with p.expect_download(timeout=30000) as download:
        p.locator('#modal-export-image').click()
    output = tmp_path / 'rendered.png'
    download.value.save_as(output)
    assert Image.open(output).size == (512, 384)
    p.wait_for_function('!document.body.dataset.busy')
    p.locator('#modal-container').wait_for(state='hidden')
    assert not p.locator('#top-bar').evaluate('e=>e.inert')
    p.locator('#image-export-thumbnail:not([hidden])').wait_for()
    with p.expect_download() as copy:
        p.locator('#image-export-copy').click()
    assert open(copy.value.path(), 'rb').read() == output.read_bytes()


def test_framing_preview_fits_actual_stage_at_desktop_sizes(desktop_design_page):
    from tests.ui_navigation import click_view_control
    p = desktop_design_page
    p.emulate_media(reduced_motion='reduce')
    open_editor_route(p, 'render-image')
    p.locator('#image-width').fill('640'); p.locator('#image-height').fill('480')
    positions = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    for width in (1600, 1280, 1024):
        p.set_viewport_size({'width': width, 'height': 900})
        for collapsed in (False, True):
            p.evaluate('(c)=>{const a=window.__ASE_APP__; a.setInspectorCollapsed(c,false); a.setRenderAreaVisible(false);}', collapsed)
            click_view_control(p, '#btn-render-area-from-view')
            p.locator('#camera-rotation-toggle').click()
            geometry = p.evaluate('''() => {
                const stage=document.querySelector('#app-viewport').getBoundingClientRect();
                const frame=document.querySelector('#export-preview-frame').getBoundingClientRect();
                return {stage:stage.toJSON(),frame:frame.toJSON()};
            }''')
            stage, frame = geometry['stage'], geometry['frame']
            assert frame['x'] + frame['width']/2 == pytest.approx(stage['x'] + stage['width']/2, abs=1)
            assert frame['y'] + frame['height']/2 == pytest.approx(stage['y'] + stage['height']/2, abs=1)
            assert frame['width'] <= stage['width'] * .9
            assert frame['height'] <= stage['height'] * .9
            assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == positions


def test_arbitrary_finite_direction_and_position_drafts_are_valid(desktop_design_page):
    p = desktop_design_page
    p.evaluate("window.__ASE_APP__.applySelectionAction({references:[0],origin:'semantic'})")
    open_editor_route(p, 'constraints')
    p.locator('#constraint-kind').select_option('fixed_plane')
    p.locator('#constraint-x').fill('-0.125')
    p.locator('#constraint-y').fill('0')
    p.locator('#constraint-z').fill('1')
    assert p.locator('#constraint-x').evaluate('e=>e.validity.valid')
    assert p.locator('#constraint-x').bounding_box()['width'] >= 80
    vector = p.evaluate('window.__ASE_APP__.readConstraintVector()')
    assert vector[0] < 0 and vector[2] > 0
    open_editor_route(p, 'add-atoms')
    p.locator('#create-atom-x').fill('1.23456789')
    assert p.locator('#create-atom-x').evaluate('e=>e.validity.valid')


def test_busy_edit_blocks_repeated_activation_and_shortcuts_before_reveal(desktop_design_page):
    p = desktop_design_page
    open_editor_route(p, 'cell-replication')
    p.locator('#super-x').fill('2')
    p.evaluate('''() => {
        const a=window.__ASE_APP__, original=a.api.applySupercell.bind(a.api);
        window.supercellCalls=0;
        a.api.applySupercell=async (...args)=>{
            window.supercellCalls++;
            await new Promise(resolve=>window.finishBusyEdit=resolve);
            return await original(...args);
        };
    }''')
    p.locator('#btn-set-supercell').click()
    p.wait_for_function('window.finishBusyEdit && document.body.dataset.busy')
    assert p.locator('#busy-overlay').evaluate('e=>e.classList.contains("busy-pending")')
    for keys in ('Enter', 'Space', 'Delete', 'Escape'):
        p.keyboard.press(keys)
    shortcut = p.evaluate("window.__ASE_APP__.shortcutPlatform==='mac'?'Meta+o':'Control+o'")
    p.keyboard.press(shortcut)
    assert p.locator('#top-bar').evaluate('e=>e.inert')
    assert p.locator('#inspector-pane').evaluate('e=>Boolean(e.closest("[inert]"))')
    assert p.evaluate('window.supercellCalls') == 1
    assert p.evaluate('window.__ASE_APP__.state.atoms.positions.length') == 2
    p.wait_for_function('!document.querySelector("#busy-overlay").classList.contains("busy-pending")')
    p.keyboard.press('Enter')
    assert p.evaluate('window.supercellCalls') == 1
    p.evaluate('window.finishBusyEdit()')
    p.wait_for_function('!document.body.dataset.busy && window.__ASE_APP__.state.atoms.positions.length===4')
    assert not p.locator('#top-bar').evaluate('e=>e.inert')


@pytest.mark.parametrize('finish_newest_first', [False, True])
def test_overlapping_busy_work_preserves_modal_and_focus(desktop_design_page, finish_newest_first):
    p = desktop_design_page
    p.locator('#editor-save').click()
    p.locator('#modal-container').wait_for(state='visible')
    p.locator('#modal-content').focus()
    p.set_viewport_size({'width': 1024, 'height': 900})
    p.wait_for_function('document.body.classList.contains("scene-nav-collapsed")')
    p.evaluate('''() => {
        const a=window.__ASE_APP__;
        window.busyA=a.withBusy('Older work',owner=>new Promise((resolve,reject)=>{
            window.releaseA=resolve; window.rejectA=reject; window.ownerA=owner;
        })).catch(()=>{});
        window.busyB=a.withBusy('Newer work',owner=>new Promise(resolve=>{
            window.releaseB=resolve; window.ownerB=owner;
        }));
    }''')
    p.wait_for_function('Boolean(window.releaseA && window.releaseB)')
    p.evaluate('''() => {
        const a=window.__ASE_APP__;
        a.setBusyProgress(30,{owner:window.ownerB,message:'Newer progress'});
        a.setBusyProgress(90,{owner:window.ownerA,message:'Older progress'});
    }''')
    assert p.locator('#busy-message').inner_text() == 'Newer progress'
    assert p.locator('#busy-progress').get_attribute('aria-valuenow') == '30'
    p.evaluate('window.releaseB()' if finish_newest_first else "window.rejectA(new Error('test failure'))")
    p.wait_for_function('window.__ASE_APP__.busyOperations.size===1')
    assert p.locator('#modal-container').evaluate('e=>e.inert')
    assert p.locator('#top-bar').evaluate('e=>e.inert')
    p.keyboard.press('Escape')
    assert p.locator('#modal-container').is_visible()
    p.evaluate('window.releaseA()' if finish_newest_first else 'window.releaseB()')
    p.wait_for_function('!document.body.dataset.busy')
    assert not p.locator('#modal-container').evaluate('e=>e.inert')
    assert p.locator('#top-bar').evaluate('e=>e.inert')
    assert p.locator('#modal-content').evaluate('e=>e===document.activeElement')
    p.keyboard.press('Escape')
    p.locator('#modal-container').wait_for(state='hidden')
    assert not p.locator('#top-bar').evaluate('e=>e.inert')
    assert p.locator('#scene-navigator').evaluate('e=>e.inert')


def test_modal_created_by_busy_work_restores_its_visible_launcher(desktop_design_page):
    p = desktop_design_page
    p.locator('#editor-search-toggle').focus()
    p.evaluate('''() => {
        const a=window.__ASE_APP__;
        window.modalTask=a.withBusy('Preparing help',async()=>{
            await new Promise(resolve=>window.releaseModalTask=resolve);
            a.showShortcutsModal();
        });
    }''')
    p.wait_for_function('Boolean(window.releaseModalTask)')
    p.evaluate('window.releaseModalTask()')
    p.wait_for_function('!document.body.dataset.busy')
    p.locator('#modal-container').wait_for(state='visible')
    p.keyboard.press('Escape')
    p.locator('#modal-container').wait_for(state='hidden')
    assert p.locator('#editor-search-toggle').evaluate('e=>e===document.activeElement')


def test_busy_interrupts_pointer_transform_without_lost_release(desktop_design_page):
    p = desktop_design_page
    p.evaluate("window.__ASE_APP__.applySelectionAction({references:[0],origin:'semantic'})")
    baseline = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    p.locator('#tool-move').click()
    canvas = p.locator('#app-viewport canvas').first.bounding_box()
    x, y = canvas['x'] + canvas['width']*.6, canvas['y'] + canvas['height']*.6
    p.mouse.move(x, y); p.mouse.down(); p.mouse.move(x+60, y+25, steps=5)
    assert p.evaluate('window.__ASE_APP__.pointerTransformGesture') == 'dragging'
    p.evaluate('''() => {
        window.transformBusy=window.__ASE_APP__.withBusy('Pending work',()=>new Promise(resolve=>window.releaseTransformBusy=resolve));
    }''')
    assert p.evaluate('window.__ASE_APP__.transform.mode') == 'IDLE'
    p.mouse.up()
    p.wait_for_function('Boolean(window.releaseTransformBusy)')
    p.evaluate('window.releaseTransformBusy()')
    p.wait_for_function('!document.body.dataset.busy')
    p.mouse.move(x+120, y+45, steps=4); p.mouse.down(); p.mouse.up()
    assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == baseline
    assert p.evaluate('window.__ASE_APP__.transform.mode') == 'IDLE'


def test_workspace_scene_controls_target_active_generation_and_obey_modal():
    editor = view(Atoms('CuO', positions=[[0, 0, 0], [1.8, 0, 0]], cell=[7, 7, 7], pbc=True),
                  notebook=False, open_browser=False, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            p = browser.new_page(viewport={'width': 1440, 'height': 900})
            p.goto(editor.url)
            p.wait_for_function('()=>window.__V_ASE_WORKSPACE__?.tabs.size===1 && [...window.__V_ASE_WORKSPACE__.tabs.values()][0].pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged')
            frame = next(f for f in p.frames if 'workspace_child=1' in f.url)
            p.set_viewport_size({'width': 1024, 'height': 900})
            p.wait_for_function('document.body.classList.contains("workspace-nav-collapsed")')
            frame.locator('#editor-sidebar-toggle').click()
            p.wait_for_function('!document.body.classList.contains("workspace-nav-collapsed")')
            p.set_viewport_size({'width': 1000, 'height': 900})
            assert frame.locator('#editor-sidebar-toggle').get_attribute('aria-pressed') == 'true'
            p.set_viewport_size({'width': 1440, 'height': 900})
            atoms = frame.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
            box = p.locator('#workspace-scene-list input[data-scene-visibility="grid"]')
            box.uncheck()
            frame.wait_for_function('window.__ASE_APP__.state.display.showGrid===false')
            p.evaluate('''() => {
                const w=window.__V_ASE_WORKSPACE__, e=w.tabs.get(w.activeSessionId);
                e.pane.contentWindow.postMessage({type:'v_ase:workspace-scene-action',sessionId:e.sessionId,
                    generation:'old-generation',id:'grid',action:'visibility',checked:true},location.origin);
            }''')
            p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            assert frame.evaluate('window.__ASE_APP__.state.display.showGrid') is False
            frame.locator('#editor-save').click()
            p.wait_for_function('document.querySelector("#document-bar").inert')
            frame.locator('#modal-container').wait_for(state='visible')
            p.evaluate('''() => {
                const w=window.__V_ASE_WORKSPACE__, e=w.tabs.get(w.activeSessionId);
                e.pane.contentWindow.postMessage({type:'v_ase:workspace-scene-action',sessionId:e.sessionId,
                    generation:e.childGeneration,id:'grid',action:'visibility',checked:true},location.origin);
            }''')
            assert frame.evaluate('window.__ASE_APP__.state.display.showGrid') is False
            frame.locator('#modal-container').press('Escape')
            p.wait_for_function('!document.querySelector("#document-bar").inert')
            assert frame.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == atoms
            p.locator('#new-document').click()
            p.wait_for_function('''() => {
                const w=window.__V_ASE_WORKSPACE__,a=w.tabs.get(w.activeSessionId)?.pane.contentWindow.__ASE_APP__;
                return w.tabs.size===2 && a?.workspaceRecoveryAcknowledged;
            }''')
            p.evaluate('(sid)=>window.__V_ASE_WORKSPACE__.activateDocument(sid)', editor.session_id)
            frame.evaluate('''() => {
                window.workspaceBusy=window.__ASE_APP__.withBusy('Pending work',()=>new Promise(resolve=>window.releaseWorkspaceBusy=resolve));
            }''')
            p.wait_for_function('document.querySelector("#document-bar").inert')
            p.evaluate('()=>{document.body.tabIndex=-1;document.body.focus();}')
            shortcut = frame.evaluate("window.__ASE_APP__.shortcutPlatform==='mac'?'Meta+Alt+ArrowRight':'Control+Alt+ArrowRight'")
            p.keyboard.press(shortcut)
            assert p.evaluate('window.__V_ASE_WORKSPACE__.activeSessionId') == editor.session_id
            assert frame.locator('#busy-overlay').is_visible()
            frame.wait_for_function('Boolean(window.releaseWorkspaceBusy)')
            frame.evaluate('window.releaseWorkspaceBusy()')
            p.wait_for_function('!document.querySelector("#document-bar").inert')
            p.keyboard.press(shortcut)
            p.wait_for_function('(sid)=>window.__V_ASE_WORKSPACE__.activeSessionId!==sid', arg=editor.session_id)
            browser.close()
    finally:
        editor.close()
