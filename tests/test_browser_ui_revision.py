"""Desktop user-feedback regressions: document navigation, host menus and chrome."""
import json
from pathlib import Path

import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view

ROOT = Path(__file__).resolve().parents[1]
NATIVE_BRIDGE = r'''if (window===top) {
 window.vaseDesktop={platform:'darwin',onCommand:f=>window.__nativeCommand=f,onOpen:f=>window.__nativeOpen=f,
 chooseOpen:async()=>null,chooseSave:async()=>null,closeWindow:async()=>true,newWindow:async()=>{throw Error('Unexpected native window')},
 openDropped:async()=>null,stat:async()=>null,read:async()=>new Uint8Array(),same:async()=>false,
 begin:async()=>1,chunk:async()=>{},finish:async()=>{},abort:async()=>{}};
}'''


@pytest.fixture(params=[False, True], ids=['browser', 'desktop-adapter'])
def revision_workspace(request):
    editor = view(Atoms('CuO', positions=[[0, 0, 0], [1.8, 0, 0]], cell=[7]*3, pbc=True),
                  notebook=False, open_browser=False, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False, document_name='CuO_interface.traj')
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors=[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: errors.append(m.text) if m.type=='error' and 'initialization failed' in m.text else None)
            if request.param:
                page.add_init_script(NATIVE_BRIDGE)
            page.goto(editor.url)
            for _ in range(150):
                assert not errors,errors
                if page.evaluate('Array.from(document.querySelectorAll("iframe")).some(f=>f.contentWindow?.__ASE_APP__?.collaborationReady)'):
                    break
                page.wait_for_timeout(100)
            else:
                pytest.fail('Revised workspace did not become ready')
            frame = next(f for f in page.frames if 'workspace_child=1' in f.url)
            frame.wait_for_function('window.__ASE_APP__.workspaceRecoveryAcknowledged')
            if request.param:
                page.add_script_tag(content=(ROOT/'desktop/host-adapter.js').read_text())
                page.wait_for_function('Boolean(window.__vaseDesktopHost)')
            yield page,frame,request.param,errors
            assert not errors,errors
            browser.close()
    finally:
        editor.close()


def open_global(frame, query):
    frame.locator('#editor-search-toggle').click()
    frame.locator('#editor-command-search').fill(query)


def test_documents_stay_at_top_and_logo_survives_sidebar_collapse(revision_workspace):
    p,f,native,_=revision_workspace
    strip=p.locator('#document-bar');scene=p.locator('#workspace-scene-navigator')
    assert p.locator('#document-tabs').get_attribute('aria-orientation')=='horizontal'
    assert strip.bounding_box()['y']==0
    assert strip.bounding_box()['height']==40
    brand=strip.locator('.document-brand img')
    assert brand.evaluate('e=>e.complete && e.naturalWidth>0')
    for opened in [False,True,False]:
        if (f.locator('#editor-sidebar-toggle').get_attribute('aria-expanded')=='true')!=opened:
            f.locator('#editor-sidebar-toggle').click()
        assert strip.is_visible() and not strip.evaluate('e=>e.inert')
        assert brand.is_visible()
        p.wait_for_function('(opened)=>document.getElementById("workspace-scene-navigator").inert===!opened',arg=opened)
        f.wait_for_function('(opened)=>document.getElementById("editor-sidebar-toggle").getAttribute("aria-expanded")===String(opened)',arg=opened)
        assert scene.evaluate('e=>e.inert') is (not opened)
    p.locator('#new-document').click()
    p.wait_for_function('window.__V_ASE_WORKSPACE__.tabs.size===2')
    boxes=p.locator('.document-tab').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().toJSON())')
    assert boxes[0]['y']==boxes[1]['y'] and boxes[1]['x']>=boxes[0]['right']


def test_global_find_crosses_every_category_and_cmd_f_opens_it(revision_workspace):
    p,f,native,_=revision_workspace
    for group in ['Style','Build','Analyze','Render']:
        f.get_by_role('tab',name=group,exact=True).click()
        before=f.evaluate('window.__ASE_APP__.editorRoute')
        p.keyboard.press('Meta+f')
        assert f.locator('#editor-command-search').evaluate('e=>e===document.activeElement')
        f.locator('#editor-command-search').fill('radius')
        result=f.locator('#editor-navigator [data-editor-route="appearance"]')
        assert result.is_visible() and 'Style' in result.inner_text()
        assert f.evaluate('window.__ASE_APP__.editorRoute')==before
        f.locator('#editor-command-search').press('Enter')
        assert f.locator('body').get_attribute('data-current-editor-route')=='appearance'
    f.locator('#editor-search-toggle').click()
    f.locator('#editor-command-search').fill('image')
    assert f.locator('#editor-navigator [data-editor-route="render-image"]').is_visible()
    f.locator('#editor-command-search').press('Escape')
    assert f.locator('#editor-search-toggle').evaluate('e=>e===document.activeElement')
    if native:
        assert p.evaluate("window.__vaseDesktopHost.commandForInput({code:'KeyF',key:'f',meta:true})")=='search'


@pytest.mark.parametrize('palette', ['graphite','slate','stone','moss'])
@pytest.mark.parametrize('appearance', ['light','dark'])
def test_palette_and_appearance_are_atomic_and_preserve_scientific_state(revision_workspace,palette,appearance):
    p,f,_,_=revision_workspace
    snapshot='JSON.stringify({positions:window.__ASE_APP__.state.atoms.positions,display:window.__ASE_APP__.state.display,camera:window.__ASE_APP__.cameraSettingsSnapshot(),profile:window.__ASE_APP__.currentImageExportProfile()})'
    before=f.evaluate(snapshot)
    result=f.evaluate('([palette,appearance])=>window.__ASE_APP__.applyInterfacePresentation({palette,preference:appearance})',[palette,appearance])
    parent=p.evaluate('window.v_aseTheme.info()');child=f.evaluate('window.v_aseTheme.info()')
    assert parent['palette']==child['palette']==result['palette']==palette
    assert parent['resolved']==child['resolved']==appearance
    assert f.evaluate(snapshot)==before
    root_style=p.locator('html').evaluate('e=>getComputedStyle(e).getPropertyValue("--ui-canvas").trim()')
    child_style=f.locator('html').evaluate('e=>getComputedStyle(e).getPropertyValue("--ui-canvas").trim()')
    assert root_style==child_style
    if palette=='graphite' and appearance=='dark':
        assert root_style=='#202226'
    mode=f.locator('#runtime-mode-switch [aria-pressed="true"]')
    assert mode.count()==1
    assert mode.evaluate('e=>getComputedStyle(e).backgroundColor') != f.locator('#runtime-mode-switch').evaluate('e=>getComputedStyle(e).backgroundColor')


def test_browser_menu_has_an_opaque_contained_surface_or_is_absent_in_native_host(revision_workspace):
    p,f,native,_=revision_workspace
    f.evaluate("window.__ASE_APP__.applyThemePreference('dark')")
    if native:
        assert f.locator('#editor-menu-toggle').is_hidden()
        assert f.locator('.document-menu-anchor').is_hidden()
        p.evaluate("window.__vaseDesktopHost.command('preferences')")
        assert f.locator('#ui-palette').evaluate('e=>e===document.activeElement')
        f.locator('#editor-search-toggle').click()
        p.evaluate("window.__vaseDesktopHost.command('preferences')")
        assert f.locator('#editor-navigator').is_hidden()
        assert f.locator('#ui-palette').evaluate('e=>e===document.activeElement')
        return
    f.locator('#editor-menu-toggle').click()
    menu=f.locator('#editor-menu-bar')
    assert menu.evaluate('e=>getComputedStyle(e).opacity')=='1'
    for title in ['File','Edit','View','Preferences','Help','Reset']:
        summary=menu.locator(':scope > details > summary').filter(has_text=title).first
        summary.click()
        result=menu.evaluate('''e=>{
          const box=e.getBoundingClientRect(),outside=[];
          for(const child of e.querySelectorAll('summary,button')) {
            if(!child.checkVisibility())continue;
            const r=child.getBoundingClientRect();
            if(r.left<box.left || r.right>box.right || r.top<box.top || r.bottom>box.bottom)outside.push(child.textContent);
          }
          return {outside,bg:getComputedStyle(e).backgroundColor,height:box.height};
        }''')
        assert not result['outside'],result
        assert result['height']>190
        assert result['bg'].startswith('rgb('),result
    p.keyboard.press('Escape')
    assert menu.is_hidden()


def test_panel_toggles_show_different_states_and_one_resize_per_toggle(revision_workspace):
    p,f,_,_=revision_workspace
    snapshot=f.evaluate('JSON.stringify(window.__ASE_APP__.cameraSettingsSnapshot())')
    result=f.evaluate('''async()=>{
       const a=window.__ASE_APP__,r=a.renderer,old=r.renderer.setSize.bind(r.renderer);let count=0;
       r.renderer.setSize=(...args)=>{count++;return old(...args);};
       const labels=[];
       for(let i=0;i<6;i++){
          document.getElementById('editor-inspector-toggle').click();
          labels.push(document.getElementById('editor-inspector-toggle').getAttribute('aria-label'));
          await new Promise(resolve=>setTimeout(resolve,180));
       }
       r.renderer.setSize=old;return {count,labels};
    }''')
    assert result['count']<=6,result
    assert len(set(result['labels']))==2
    assert f.evaluate('JSON.stringify(window.__ASE_APP__.cameraSettingsSnapshot())')==snapshot
    assert f.locator('#btn-inspector-collapse').is_hidden()
    assert p.locator('#workspace-sidebar-close').is_hidden()
    for selector in ['#editor-sidebar-toggle','#editor-inspector-toggle']:
        button=f.locator(selector)
        def glyph():
            return button.evaluate('e=>[...e.querySelectorAll("svg")].filter(s=>s.checkVisibility()).map(s=>s.outerHTML).join("")')
        first=glyph();before=button.get_attribute('aria-expanded');button.click()
        f.wait_for_function('([selector,before])=>document.querySelector(selector).getAttribute("aria-expanded")!==before',arg=[selector,before])
        second=glyph()
        assert first and second and first!=second
        assert button.get_attribute('aria-expanded')==button.get_attribute('aria-pressed')


def test_access_mode_is_exclusive_without_implicit_search_edits(revision_workspace):
    p,f,_,_=revision_workspace
    positions=f.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    cell=f.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.cell)')
    for mode in ['view','edit','view']:
        f.locator(f'#runtime-mode-switch [data-runtime-mode="{mode}"]').click()
        f.wait_for_function('(view)=>window.__ASE_APP__.state.vizOnly===view',arg=mode=='view')
        assert f.locator('#runtime-mode-switch [aria-pressed="true"]').count()==1
        assert f.locator(f'#runtime-mode-switch [data-runtime-mode="{mode}"]').get_attribute('aria-pressed')=='true'
        assert f.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')==positions
        assert f.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.cell)')==cell
        assert f.locator('#runtime-mode-status').inner_text().startswith('View only.' if mode=='view' else 'Edit structure.')
        assert not f.locator('#toast-container').get_by_text('mode enabled.',exact=False).count()
    open_global(f,'constraints')
    f.locator('#editor-navigator [data-editor-route="constraints"]').click()
    assert f.locator('#workbench-edit-notice').is_visible()
    assert f.evaluate('window.__ASE_APP__.state.vizOnly') is True


def test_search_is_anchored_in_every_desktop_width_and_dismisses_cleanly(revision_workspace):
    p,f,_,_=revision_workspace
    for width,height in [(1440,900),(1280,800),(1024,768),(1024,460)]:
        p.set_viewport_size({'width':width,'height':height})
        for sidebar in [False,True]:
            if (f.locator('#editor-sidebar-toggle').get_attribute('aria-expanded')=='true')!=sidebar:
                f.locator('#editor-sidebar-toggle').click()
            p.wait_for_function('(open)=>!document.body.classList.contains("workspace-nav-collapsed")===open',arg=sidebar)
            open_global(f,'')
            boxes=f.evaluate('''()=>({popup:document.getElementById('editor-navigator').getBoundingClientRect().toJSON(),
                anchor:document.getElementById('editor-search-toggle').getBoundingClientRect().toJSON(),width:innerWidth,height:innerHeight})''')
            box,anchor=boxes['popup'],boxes['anchor']
            assert box['left']==pytest.approx(max(12,min(boxes['width']-box['width']-12,anchor['left'])),abs=1)
            assert box['top']==pytest.approx(anchor['bottom']+8,abs=1)
            assert 12<=box['left']<box['right']<=boxes['width']-11
            assert box['bottom']<=boxes['height']-11
            f.locator('#editor-command-search').fill('radius')
            p.keyboard.press('Meta+f')
            assert f.locator('#editor-command-search').input_value()=='radius'
            p.keyboard.press('Escape')
    f.locator('#inspector-tool-trigger').click()
    assert f.locator('#inspector-tool-trigger').get_attribute('aria-expanded')=='true'
    f.locator('#editor-inspector-toggle').click()
    assert f.locator('#editor-navigator').is_hidden()
    assert f.locator('#inspector-tool-trigger').get_attribute('aria-expanded')=='false'
    assert f.locator('#editor-inspector-toggle').evaluate('e=>e===document.activeElement')


def test_semantic_palette_matches_schema_and_preserves_rendered_image_bytes(revision_workspace):
    p,f,_,_=revision_workspace
    baseline=f.evaluate('window.__ASE_APP__.renderer.exportPNG(320,240)')
    profile=f.evaluate('JSON.stringify(window.__ASE_APP__.currentImageExportProfile())')
    for palette,appearance in [('graphite','dark'),('slate','light'),('stone','dark'),('moss','light')]:
        f.evaluate('async ([palette,theme])=>await window.v_aseAI.apply({operation:{name:"set-interface-theme",theme,palette}})',[palette,appearance])
        assert p.evaluate('window.v_aseTheme.info().palette')==palette
        assert f.evaluate('window.__ASE_APP__.renderer.exportPNG(320,240)')==baseline
        assert f.evaluate('JSON.stringify(window.__ASE_APP__.currentImageExportProfile())')==profile


@pytest.mark.parametrize('revision_workspace',[True],indirect=True,ids=['desktop-adapter'])
def test_native_horizontal_tab_drag_previews_reorders_and_cancels(revision_workspace):
    p,f,native,_=revision_workspace
    assert native
    for count in [2,3]:
        p.locator('#new-document').click()
        p.wait_for_function('(count)=>{const w=window.__V_ASE_WORKSPACE__,a=w.tabs.get(w.activeSessionId)?.pane.contentWindow.__ASE_APP__;return w.tabs.size===count && a?.collaborationReady && a.workspaceRecoveryAcknowledged && !document.getElementById("document-bar").inert;}',arg=count)
    order=lambda:p.locator('.document-tab').evaluate_all('es=>es.map(e=>e.dataset.sessionId)')
    initial=order();boxes=p.locator('.document-tab').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().toJSON())')
    p.mouse.move(boxes[0]['x']+40,20);p.mouse.down();p.mouse.move(boxes[-1]['right']-3,20,steps=5)
    assert p.locator('#document-drag-preview').inner_text()=='Reorder document'
    p.mouse.up();assert order()==initial[1:]+initial[:1]
    current=order();box=p.locator('.document-tab').first.bounding_box()
    p.evaluate('()=>{window.__vaseDesktopHost.detach=async(...args)=>{window.__detachRequest=args;};}')
    p.mouse.move(box['x']+40,20);p.mouse.down();p.mouse.move(box['x']+40,130,steps=5)
    assert p.locator('#document-drag-preview').inner_text()=='Move to a new window'
    p.evaluate('()=>{const w=window.__V_ASE_WORKSPACE__;w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__.renderer.domElement.focus();}')
    p.keyboard.press('Escape');p.mouse.up()
    assert order()==current and p.evaluate('window.__detachRequest===undefined')
    assert p.locator('#document-drag-preview').is_hidden()
    p.mouse.move(box['x']+40,20);p.mouse.down();p.mouse.move(box['x']+40,130,steps=5);p.mouse.up()
    assert p.evaluate('window.__detachRequest[0]')==current[0]


def test_deferred_busy_blocks_tabs_without_flashing_parent_scrim(revision_workspace):
    p,f,_,_=revision_workspace
    f.evaluate('''()=>{const a=window.__ASE_APP__;
        window.pendingOwner=a.setBusy('Pending',{revealAfter:10000});}''')
    p.wait_for_function('document.getElementById("document-bar").inert')
    assert not p.locator('body').evaluate('e=>e.classList.contains("workspace-scrim-visible")')
    f.evaluate('''()=>{window.visibleOwner=window.__ASE_APP__.setBusy('Visible',{revealAfter:0});}''')
    p.wait_for_function('document.body.classList.contains("workspace-scrim-visible")')
    f.evaluate('window.__ASE_APP__.clearBusy(window.visibleOwner)')
    p.wait_for_function('!document.body.classList.contains("workspace-scrim-visible")')
    assert p.locator('#document-bar').evaluate('e=>e.inert')
    f.evaluate('window.__ASE_APP__.clearBusy(window.pendingOwner)')
    p.wait_for_function('!document.getElementById("document-bar").inert')
    assert not p.locator('body').evaluate('e=>e.classList.contains("workspace-scrim-visible")')
