"""Reference-derived interactions must remain usable in the actual viewport."""
import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view,find_free_port

from tests.test_browser_interface_system import interface_page


@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('size', [(1440, 960), (1024, 768), (390, 844), (320, 568), (700, 420)])
def test_viewport_tools_are_fully_reachable_without_clipped_first_button(interface_page, theme, size):
    p = interface_page
    p.set_viewport_size({'width':size[0], 'height':size[1]})
    p.emulate_media(reduced_motion='reduce')
    p.evaluate('(x)=>window.v_aseTheme.apply(x)', theme)
    p.evaluate('''()=>{const a=window.__ASE_APP__;a.state.selected=new Set([0]);
        a.updateSelectionVisuals();a.updateUI();a.openEditorRoute('add-atoms');}''')
    p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    before = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    camera = p.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()')
    # Centering overflowing flex content made the first button unreachable even
    # at scrollTop=0. Check the whole glyph/hit target, not only panel bounds.
    p.locator('#viewport-tools').evaluate('e=>{e.scrollTop=0;e.scrollLeft=0;}')
    issues = p.locator('#tool-select').evaluate('''e=>{
        const r=e.getBoundingClientRect(),t=e.closest('#viewport-tools').getBoundingClientRect();
        return r.top<t.top || r.left<t.left || r.bottom>t.bottom || r.right>t.right;}''')
    assert not issues, 'The first Select button is clipped at the scroll origin'
    for tool in ['select','measure','move','rotate','scale','orbit','add']:
        target = p.locator('#tool-'+tool)
        target.evaluate("e=>e.scrollIntoView({block:'nearest',inline:'nearest'})")
        result = target.evaluate('''e=>{const r=e.getBoundingClientRect(),t=e.closest('#viewport-tools').getBoundingClientRect();
            const probes=[[r.left+4,r.top+4],[r.right-4,r.top+4],[r.right-4,r.bottom-4],[r.left+4,r.bottom-4],[r.left+r.width/2,r.top+r.height/2]];
            return {inside:r.top>=t.top && r.left>=t.left && r.bottom<=t.bottom && r.right<=t.right,
                hittable:probes.every(([x,y])=>e.contains(document.elementFromPoint(x,y)))};}''')
        assert result == {'inside':True,'hittable':True}, (size,tool,result)
    # The compact rail and Fit view must not obscure each other's targets.
    assert p.locator('#btn-fit-view').evaluate('''e=>{const r=e.getBoundingClientRect();
        return e.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2));}''')
    floating_issues=p.evaluate('''()=>{
        const viewport=document.querySelector('#app-viewport').getBoundingClientRect();
        return [...document.querySelectorAll('#viewport-camera-tools button,#btn-fit-view,#btn-objects')]
            .filter(e=>!e.disabled && !e.closest('.hidden,[inert]') && e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0)
            .flatMap(e=>{const r=e.getBoundingClientRect();
                const inside=r.left>=viewport.left && r.top>=viewport.top && r.right<=viewport.right && r.bottom<=viewport.bottom;
                const hit=[[r.left+4,r.top+4],[r.right-4,r.bottom-4],[r.left+r.width/2,r.top+r.height/2]]
                    .every(([x,y])=>e.contains(document.elementFromPoint(x,y)));
                return inside && hit ? [] : [{id:e.id,label:e.ariaLabel,inside,hit}];});}''')
    assert not floating_issues, floating_issues
    disclosure=p.locator('#camera-rotation-toggle')
    if disclosure.is_visible():
        disclosure.click()
        assert disclosure.get_attribute('aria-expanded')=='true'
        assert not p.locator('#camera-more-content').evaluate('e=>e.inert')
        for button in p.locator('#camera-more-content .camera-presets button,#view-toolbar button').all():
            result=button.evaluate('''e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
                return {inside:r.left>=0 && r.top>=0 && r.right<=innerWidth && r.bottom<=innerHeight,
                    hit:e.contains(hit),rect:r.toJSON(),blockedBy:hit?.id || hit?.tagName,label:e.ariaLabel};}''')
            assert result['inside'] and result['hit'],result
        disclosure.press('Escape')
        assert disclosure.get_attribute('aria-expanded')=='false'
        assert p.locator('#camera-more-content').evaluate('e=>e.inert')
    p.locator('#tool-select').click()
    assert p.locator('#tool-select').get_attribute('aria-pressed') == 'true'
    assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == before
    assert p.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()') == camera


@pytest.mark.parametrize('width', [1440,390])
def test_command_search_arrows_open_and_escape_work_as_one_flow(interface_page, width):
    p=interface_page
    p.set_viewport_size({'width':width,'height':844})
    p.emulate_media(reduced_motion='reduce')
    p.locator('#editor-search-toggle').click()
    search=p.locator('#editor-command-search')
    search.fill('render')
    search.press('ArrowDown')
    assert p.evaluate('document.activeElement.matches("#editor-navigator [data-editor-route]")')
    p.keyboard.press('End')
    last=p.evaluate('document.activeElement.dataset.editorRoute')
    p.keyboard.press('Home')
    first=p.evaluate('document.activeElement.dataset.editorRoute')
    assert first != last
    p.keyboard.press('ArrowUp')
    assert search.evaluate('e=>e===document.activeElement')
    search.press('ArrowDown')
    p.keyboard.press('Escape')
    assert not p.locator('body').evaluate('e=>e.classList.contains("editor-search-open")')
    assert p.locator('#editor-search-toggle').evaluate('e=>e===document.activeElement')
    p.locator('#editor-search-toggle').click()
    search.fill('bond')
    search.press('ArrowDown')
    p.keyboard.press('Enter')
    assert p.locator('body').get_attribute('data-current-editor-route') == 'bonding'
    assert not p.locator('body').evaluate('e=>e.classList.contains("editor-search-open")')
    p.locator('#editor-search-toggle').click()
    search.fill('no-matching-control-zzzz')
    search.press('ArrowDown')
    assert search.evaluate('e=>e===document.activeElement')
    assert p.locator('#editor-command-empty').is_visible()


@pytest.mark.parametrize('theme',['light','dark'])
def test_primary_button_has_distinct_press_feedback_without_moving_target(interface_page, theme):
    p=interface_page
    p.emulate_media(reduced_motion='reduce')
    p.evaluate('(x)=>window.v_aseTheme.apply(x)',theme)
    button=p.locator('#editor-render')
    p.mouse.move(500,600)
    normal=button.evaluate('e=>getComputedStyle(e).backgroundColor')
    box=button.bounding_box()
    button.hover()
    hover=button.evaluate('e=>getComputedStyle(e).backgroundColor')
    p.mouse.down()
    pressed=button.evaluate('e=>getComputedStyle(e).backgroundColor')
    assert len({normal,hover,pressed}) == 3
    assert button.bounding_box() == box
    p.mouse.move(500,600);p.mouse.up()


@pytest.fixture
def single_structure_page():
    editor=view(Atoms('HHO',positions=[[0,0,0],[.76,0,0],[0,1,0]],cell=[6,6,6]),
                notebook=True,block=False,open_browser=False,viz_only=False,
                port=find_free_port(),close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':960})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            yield page
            browser.close()
    finally: editor.close()


def test_mounted_add_atom_inspector_has_one_title_and_keeps_active_session_controls(single_structure_page):
    p=single_structure_page
    p.evaluate("window.__ASE_APP__.openEditorRoute('add-atoms')")
    assert p.locator('#inspector-context').inner_text() == 'Add atoms & molecules'
    assert not p.locator('#create-atom-drag').is_visible()
    assert p.locator('#add-atoms-tab-single').is_visible()
    # Exercise a real insertion session so its status/exit controls cannot be
    # hidden with the redundant inactive heading.
    p.locator('#add-atoms-tab-batch').click()
    p.locator('.add-atoms-entry-count').fill('1')
    p.locator('#btn-add-atoms-scatter').click()
    p.wait_for_function('window.__ASE_APP__.addAtomsUI.active?.active',timeout=10000)
    assert p.locator('#add-atoms-mode-badge').is_visible()
    assert p.locator('#btn-create-atom-close').is_visible()
    p.locator('#btn-add-atoms-cancel').click()
    p.wait_for_function('!window.__ASE_APP__.addAtomsUI.active?.active')
    assert not p.locator('#create-atom-drag').is_visible()


@pytest.mark.parametrize('width',[320,390])
def test_touch_tool_strip_keeps_44px_targets_and_both_ends_accessible(interface_page,width):
    context=interface_page.context.browser.new_context(viewport={'width':width,'height':844},
        is_mobile=True,has_touch=True,device_scale_factor=1)
    try:
        p=context.new_page();p.goto(interface_page.url)
        p.wait_for_function('window.__ASE_APP__?.collaborationReady')
        for tool in ['select','measure','orbit','add']:
            target=p.locator('#tool-'+tool)
            target.evaluate("e=>e.scrollIntoView({block:'nearest',inline:'nearest'})")
            box=target.bounding_box()
            assert box['width']>=44 and box['height']>=44
            assert target.evaluate('''e=>{const r=e.getBoundingClientRect();
                return e.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2));}''')
        p.locator('#tool-select').tap()
        assert p.locator('#tool-select').get_attribute('aria-pressed')=='true'
    finally: context.close()
