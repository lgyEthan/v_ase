"""Observable editor interactions: no layout/camera drift, real keys and menus."""
import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port

@pytest.fixture
def editor_page():
    editor = view(Atoms('HHO', positions=[[0,0,0],[0.75,0,0],[0,1,0]], cell=[6,6,6]),
                  notebook=True, block=False, port=find_free_port(), viz_only=False, close_on_disconnect=False)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1440,'height':960})
        page.goto(editor.url)
        page.wait_for_function('window.__ASE_APP__?.collaborationReady')
        yield page
        browser.close()
    editor.close()


def test_bond_defaults_ctrl_a_and_vertical_tab(editor_page):
    p = editor_page
    p.click('#workbench-route-bonding')
    assert p.input_value('#bond-mode') == 'pairwise'
    assert p.locator('#bond-mode option[value="auto"]').count() == 0
    fields = p.locator('.pairwise-bond-max')
    assert fields.count() == 3
    fields.nth(0).click()
    p.keyboard.press('Control+a'); p.keyboard.type('2')
    assert fields.nth(0).input_value() == '2'
    p.keyboard.press('Tab'); p.keyboard.type('2.5')
    assert fields.nth(1).input_value() == '2.5'
    p.keyboard.press('Tab'); p.keyboard.type('3')
    assert fields.nth(2).input_value() == '3'
    p.keyboard.press('Shift+Tab')
    assert fields.nth(1).evaluate('(el) => el === document.activeElement')
    p.wait_for_function('window.__ASE_APP__.state.display.pairwiseBondRanges["H-O"].max === 2.5')


def test_menu_hover_search_exclusion_and_reset(editor_page):
    p = editor_page
    menus=p.locator('#editor-menu-bar > details')
    menus.nth(0).locator('summary').click()
    menus.nth(1).locator('summary').hover()
    assert menus.nth(1).get_attribute('open') is not None
    assert menus.nth(0).get_attribute('open') is None
    p.click('#editor-search-toggle')
    assert p.locator('#editor-navigator').is_visible()
    assert p.locator('#editor-menu-bar > details[open]').count() == 0
    menus.nth(0).locator('summary').click()
    assert p.locator('#editor-navigator').is_hidden()
    p.keyboard.press('ArrowDown'); p.keyboard.press('ArrowRight')
    assert menus.nth(1).get_attribute('open') is not None
    p.keyboard.press('Escape')
    assert p.locator('#editor-menu-bar > details[open]').count() == 0
    p.click('#editor-reset-menu summary')
    assert p.locator('#editor-reset-menu [data-editor-menu-action="reset-coordinates"]').is_visible()
    assert p.locator('#editor-reset-menu [data-editor-menu-action="reset-all"]').is_visible()


def test_floating_panel_keeps_projection_and_can_expand(editor_page):
    p = editor_page
    snapshot='''() => { const app=window.__ASE_APP__; const r=app.renderer;
        return {rect:r.domElement.getBoundingClientRect().toJSON(), camera:app.cameraSettingsSnapshot(),
            point:app.worldToScreen(r.toVisualAtomPosition(app.state.atoms.positions[0])).toArray()}; }'''
    before=p.evaluate(snapshot)
    for width in (324,600,850):
        p.evaluate('(width) => window.__ASE_APP__.setInspectorWidth(width)',width)
        p.evaluate('window.__ASE_APP__.setInspectorCollapsed(true)')
        p.evaluate('window.__ASE_APP__.setInspectorCollapsed(false)')
        assert p.evaluate(snapshot) == before
        assert p.locator('#inspector').bounding_box()['width'] == width
    p.click('#workbench-route-bonding')
    assert p.locator('#pairwise-bond-panel').evaluate('(el)=>el.scrollWidth <= el.clientWidth+1')


def test_tools_exclusive_and_numeric_transform_after_button(editor_page):
    p=editor_page
    p.evaluate('window.__ASE_APP__.applySelectionAction({references:[0],origin:"semantic"})')
    original=p.evaluate('window.__ASE_APP__.renderer.currentPositions()')
    p.click('#tool-orbit')
    assert p.locator('#viewport-tools [aria-pressed="true"]').count()==1
    p.click('#tool-measure')
    assert not p.evaluate('window.__ASE_APP__.orbitToolActive')
    assert p.locator('#viewport-tools [aria-pressed="true"]').count()==1
    p.click('#tool-move')
    p.keyboard.press('x'); p.keyboard.type('2'); p.keyboard.press('Enter')
    p.wait_for_function('window.__ASE_APP__.transform.mode === "IDLE"')
    p.wait_for_function('(x)=>Math.abs(window.__ASE_APP__.renderer.currentPositions()[0][0]-x)<1e-8',arg=original[0][0]+2)
    p.click('#tool-rotate')
    p.keyboard.type('45')
    p.click('#tool-scale') # switching cancels the provisional rotation
    assert p.evaluate('window.__ASE_APP__.transform.mode') == 'SCALE'
    assert p.locator('#viewport-tools [aria-pressed="true"]').count()==1
    p.keyboard.press('Escape')
    assert p.locator('#tool-select').get_attribute('aria-pressed')=='true'
    p.click('#tool-measure'); p.keyboard.press('Escape')
    assert p.locator('#tool-select').get_attribute('aria-pressed')=='true'


def test_open_chord_and_file_drop_offer_destinations(editor_page):
    p=editor_page
    p.evaluate('() => { window.openCommandCount=0; window.__ASE_APP__.chooseSystemStructureFile=()=>{ window.openCommandCount++; }; }')
    p.keyboard.press(('Meta' if p.evaluate('/Mac/i.test(navigator.platform)') else 'Control')+'+o')
    assert p.evaluate('window.openCommandCount') == 1
    p.evaluate('''() => { const dt = new DataTransfer();
        dt.items.add(new File(['1\\nDropped\\nHe 0 0 0\\n'],'drop.xyz',{type:'text/plain'}));
        document.body.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt})); }''')
    p.locator('#open-file-name').wait_for()
    assert p.locator('#open-file-name').inner_text()=='drop.xyz'
    assert p.locator('[name="open-file-mode"][value="new-tab"]').is_checked()
    assert p.locator('[name="open-file-mode"][value="new-window"]').is_visible()
    p.check('[name="open-file-mode"][value="append"]')
    p.click('#open-file-confirm')
    p.wait_for_function('window.__ASE_APP__.timelineFrameCount("loaded") === 2')


def test_bookmarks_have_unique_icons_labels_and_precede_section_title(editor_page):
    p=editor_page
    nav=p.locator('#workbench-tools')
    assert nav.bounding_box()['y'] < p.locator('.inspector-head').bounding_box()['y']
    icons=p.locator('#workbench-tools [data-editor-route] svg').evaluate_all('(els)=>els.map(el=>el.innerHTML)')
    assert len(icons)==23 and len(set(icons))==23
    for button in p.locator('#workbench-tools [data-editor-route]').all():
        assert button.get_attribute('aria-label')
        assert button.inner_text()==''
    p.locator('#workbench-route-bonding').hover()
    assert p.locator('#workbench-route-bonding').get_attribute('data-tooltip')=='Bonds'
    p.locator('#workbench-route-bonding').click()
    assert p.locator('#inspector-context').inner_text()=='Bonds'
    p.evaluate('window.__ASE_APP__.clearAtomSelection(); window.__ASE_APP__.updateSelectionVisuals()')
    assert p.locator('#tool-move').is_disabled()
    assert p.locator('#tool-rotate').is_disabled()
    assert p.locator('#tool-scale').is_disabled()


def test_toolbar_transforms_wait_for_drag_and_commit_on_release(editor_page):
    p=editor_page
    for tool in ('move', 'rotate', 'scale'):
        p.evaluate('window.__ASE_APP__.applySelectionAction({references:[0,1],origin:"semantic"})')
        original=p.evaluate('window.__ASE_APP__.renderer.currentPositions()')
        p.click('#tool-'+tool)
        p.mouse.move(650,430)
        assert p.evaluate('window.__ASE_APP__.renderer.currentPositions()') == original
        p.mouse.down()
        p.mouse.move(730,475,steps=8)
        p.mouse.up()
        p.wait_for_function('window.__ASE_APP__.transform.mode === "IDLE"')
        p.wait_for_function('(before)=>JSON.stringify(window.__ASE_APP__.renderer.currentPositions())!==JSON.stringify(before)',arg=original)
        assert p.locator('#tool-select').get_attribute('aria-pressed') == 'true'
        p.evaluate('window.__ASE_APP__.performUndo()')
        p.wait_for_function('(before)=>window.__ASE_APP__.renderer.currentPositions().every((v,i)=>v.every((n,j)=>Math.abs(n-before[i][j])<1e-8))',arg=original)


def test_browser_drop_can_open_a_separate_window_without_replacing_source(editor_page):
    p=editor_page
    p.evaluate('''() => { const dt = new DataTransfer();
        dt.items.add(new File(['1\\nSeparate\\nHe 0 0 0\\n'],'helium.xyz',{type:'text/plain'}));
        document.body.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt})); }''')
    p.check('[name="open-file-mode"][value="new-window"]')
    with p.expect_popup() as opened:
        p.click('#open-file-confirm')
    popup=opened.value
    popup.wait_for_function('''() => { const w=window.__V_ASE_WORKSPACE__;
        const a=w?.tabs.get(w.activeSessionId)?.pane?.contentWindow?.__ASE_APP__;
        return a?.collaborationReady && a.state.atoms.positions.length===1; }''')
    assert p.evaluate('window.__ASE_APP__.state.atoms.positions.length') == 3
    assert popup.evaluate('window.__V_ASE_WORKSPACE__.tabs.size') == 1
    # Explicit cleanup: browsers may retain independently opened workspaces.
    workspace_id=popup.evaluate('window.__V_ASE_WORKSPACE__.workspaceId')
    popup.close()
    p.request.post(f'{p.url.split("/?")[0]}/api/workspace/{workspace_id}/close')
