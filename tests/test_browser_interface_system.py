"""Interaction contracts for the shared editor chrome, using real controls."""
from tests.ui_navigation import open_editor_route
import json

import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view


@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('viewport,panel', [(1440, 352), (1024, 300), (390, 352)])
def test_disclosure_glyphs_and_controls_do_not_overlap_in_expanded_tools(interface_page, theme, viewport, panel):
    p = interface_page
    p.set_viewport_size({'width': viewport, 'height': 844})
    p.emulate_media(reduced_motion='reduce')
    p.evaluate('(x)=>window.v_aseTheme.apply(x)', theme)
    p.evaluate('(x)=>window.__ASE_APP__.setInspectorWidth(x)', panel)
    p.evaluate('''()=>{const a=window.__ASE_APP__;a.state.selected=new Set([0]);
        a.updateSelectionVisuals();a.updateUI();}''')
    positions = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    routes = p.locator('#workbench-tools [data-editor-route], [data-editor-menu-route]').evaluate_all(
        '(es)=>[...new Set(es.map(e=>e.dataset.editorRoute || e.dataset.editorMenuRoute))]')
    issues, checked = [], 0
    for route in routes:
        p.evaluate('(r)=>window.__ASE_APP__.openEditorRoute(r)', route)
        p.evaluate('''()=>{for(const d of document.querySelectorAll('#inspector-content .editor-route-current details')) d.open=true;}''')
        if route == 'appearance':
            p.locator('#chk-atom-radius-mapping').check()
            p.locator('#chk-atom-colorscale').check()
        p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        result = p.evaluate(r'''() => {
            const issues=[], visible=e=>e.checkVisibility({visibilityProperty:true})
                && e.getAttribute('aria-hidden')!=='true' && e.getBoundingClientRect().width>0;
            const controls=[...document.querySelectorAll('#inspector-content :is(button,input,select,summary)')].filter(visible);
            const id=e=>e.id || e.textContent.trim().slice(0,70) || e.className;
            const selects=[...document.querySelectorAll('#inspector select,#top-bar select,#command-bar select')].filter(visible);
            for(const e of selects){
                if(e.multiple || e.size>1)continue;
                const s=getComputedStyle(e), r=e.getBoundingClientRect();
                // A single glyph sits in a reserved area, even in compact cells;
                // long values must truncate before it, rather than paint below it.
                if(parseFloat(s.paddingRight)<24 || s.appearance!=='none'
                    || s.backgroundImage==='none' || s.textOverflow!=='ellipsis'
                    || r.width<parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+12){
                    issues.push({select:id(e),padding:s.paddingRight,appearance:s.appearance,width:r.width});
                }
            }
            for(const e of controls.filter(e=>e.tagName==='SUMMARY')){
                const s=getComputedStyle(e), glyph=getComputedStyle(e,'::after'), r=e.getBoundingClientRect();
                const range=document.createRange();range.selectNodeContents(e);
                const text=range.getBoundingClientRect();
                if(glyph.content==='none' || glyph.position==='absolute'
                    || text.right>r.right-16 || text.left<r.left-1){
                    issues.push({summary:id(e),textRight:text.right-r.right,glyphPosition:glyph.position});
                }
            }
            for(let i=0;i<controls.length;i++)for(let j=i+1;j<controls.length;j++){
                const a=controls[i],b=controls[j];
                if(a.contains(b)||b.contains(a)||a.closest('#appearance-table')||b.closest('#appearance-table'))continue;
                const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();
                const w=Math.min(x.right,y.right)-Math.max(x.left,y.left),h=Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top);
                if(w>2 && h>2)issues.push({overlap:[id(a),id(b)],width:w,height:h});
            }
            const trigger=document.getElementById('atom-colormap-trigger');
            if(visible(trigger)){
                const r=trigger.getBoundingClientRect(), label=trigger.querySelector('.atom-colormap-trigger-name').getBoundingClientRect(),
                    glyph=trigger.querySelector('.atom-colormap-chevron').getBoundingClientRect();
                if(label.right>glyph.left-4 || glyph.right>r.right-5 || glyph.top<r.top || glyph.bottom>r.bottom){
                    issues.push({picker:'colormap',labelGap:glyph.left-label.right,glyphInset:r.right-glyph.right});
                }
            }
            return {issues,checked:selects.length};
        }''')
        checked += result['checked']
        issues.extend({'route': route, **issue} for issue in result['issues'])
    assert checked >= 35
    assert not issues, json.dumps(issues, indent=2)
    assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == positions


def test_native_select_disclosure_keys_and_colormap_still_work(interface_page):
    p = interface_page
    positions = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    p.evaluate("window.__ASE_APP__.openEditorRoute('view')")
    projection = p.locator('#projection-mode')
    # Native macOS popup menus do not select via synthetic Arrow/Enter in
    # headless Chromium, including on a plain HTML page. Use its select adapter;
    # exercise disclosure keys below and verify the real menu in visual QA.
    projection.select_option('perspective')
    assert projection.input_value() == 'perspective'
    projection.select_option('orthographic')
    assert projection.input_value() == 'orthographic'
    p.evaluate("window.__ASE_APP__.openEditorRoute('build-rigid')")
    details = p.locator('#rigid-translation-optional')
    summary = details.locator(':scope > summary')
    summary.focus(); summary.press('Enter')
    assert details.evaluate('e=>e.open')
    summary.press('Space')
    assert not details.evaluate('e=>e.open')
    assert p.evaluate('!window.__ASE_APP__.state.trajectoryTimer && !window.__ASE_APP__.state.trajectoryPlaybackTask')
    p.evaluate("window.__ASE_APP__.openEditorRoute('appearance')")
    p.locator('#chk-atom-colorscale').check()
    p.locator('#atom-colormap-trigger').click()
    p.locator('#atom-colormap-menu-search').fill('cividis')
    p.locator('.atom-colormap-option[data-map="cividis"]').click()
    assert p.locator('#atom-colorscale-map').input_value() == 'cividis'
    assert p.locator('#atom-colormap-trigger').get_attribute('aria-expanded') == 'false'
    p.click('#editor-save')
    assert p.locator('#modal-container').is_visible()
    for select in p.locator('#modal-container select:visible').all():
        assert select.evaluate('e=>parseFloat(getComputedStyle(e).paddingRight)') >= 24
    assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == positions


def test_selects_keep_system_disclosure_in_forced_colors(interface_page):
    p = interface_page
    p.emulate_media(forced_colors='active')
    p.evaluate("window.__ASE_APP__.openEditorRoute('view')")
    select = p.locator('#projection-mode')
    assert select.evaluate('e=>getComputedStyle(e).appearance') == 'auto'
    assert select.evaluate('e=>getComputedStyle(e).backgroundImage') == 'none'
    select.select_option('perspective')
    assert select.input_value() == 'perspective'


@pytest.fixture
def interface_page():
    atoms = Atoms('HHO', positions=[[0, 0, 0], [.76, 0, 0], [0, 1, 0]], cell=[6, 6, 6])
    frames = [atoms.copy() for _ in range(3)]
    for index, frame in enumerate(frames):
        frame.positions[0, 2] = index * .1
    editor = view(frames,
                  notebook=True, block=False, port=find_free_port(), viz_only=False,
                  close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 960})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady && document.documentElement.dataset.interfaceReady')
            yield page
            browser.close()
    finally:
        editor.close()


def test_inspector_drag_cancel_keyboard_reset_and_projection(interface_page):
    p = interface_page
    before = p.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()')
    handle = p.locator('#inspector-resizer')
    box = handle.bounding_box()
    x, y = box['x'] + box['width'] / 2, box['y'] + 50
    initial = p.locator('#inspector').bounding_box()['width']
    p.mouse.move(x, y); p.mouse.down(); p.mouse.move(x - 100, y, steps=5)
    assert p.locator('#inspector').bounding_box()['width'] == initial + 100
    p.keyboard.press('Escape'); p.mouse.up()
    assert p.locator('#inspector').bounding_box()['width'] == initial
    assert p.evaluate('localStorage.getItem("v_ase.workbench.v1.width")') is None
    assert not p.locator('body').evaluate('e=>e.classList.contains("ui-resizing")')
    handle.focus(); p.keyboard.press('ArrowLeft')
    assert int(handle.get_attribute('aria-valuenow')) == initial + 8
    p.keyboard.press('Shift+ArrowLeft')
    assert int(handle.get_attribute('aria-valuenow')) == initial + 40
    handle.dblclick()
    assert int(handle.get_attribute('aria-valuenow')) == initial
    handle.press('ArrowRight')
    narrowed = max(320, int(initial) - 8)
    assert p.evaluate('localStorage.getItem("v_ase.workbench.v1.width")') == str(narrowed)
    p.keyboard.press('Escape')
    assert p.locator('body').evaluate('e=>e.classList.contains("inspector-collapsed")')
    p.click('#editor-inspector-toggle')
    assert p.locator('#inspector').bounding_box()['width'] == narrowed
    assert p.evaluate('window.__ASE_APP__.cameraSettingsSnapshot()') == before


def test_interrupted_resize_restores_size_and_ignores_secondary_button(interface_page):
    p = interface_page
    handle = p.locator('#inspector-resizer')
    initial = int(handle.get_attribute('aria-valuenow'))
    box = handle.bounding_box(); x, y = box['x'] + 4, box['y'] + 50
    p.mouse.move(x, y); p.mouse.down(button='right'); p.mouse.move(x - 80, y); p.mouse.up(button='right')
    assert int(handle.get_attribute('aria-valuenow')) == initial
    p.mouse.move(x, y); p.mouse.down(); p.mouse.move(x - 80, y)
    handle.dispatch_event('pointercancel', {'pointerId': 1})
    p.mouse.up()
    assert int(handle.get_attribute('aria-valuenow')) == initial
    assert 'ui-resizing' not in p.locator('body').get_attribute('class')


def test_pair_column_cancel_and_keyboard_are_presentation_only(interface_page):
    p = interface_page
    open_editor_route(p, 'bonding')
    p.evaluate('window.__ASE_APP__.setInspectorWidth(650)')
    initial_atoms = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
    handle = p.locator('#pairwise-label-column-resizer')
    initial = int(handle.get_attribute('aria-valuenow'))
    box = handle.bounding_box(); x, y = box['x'] + box['width'] / 2, box['y'] + 8
    p.mouse.move(x, y); p.mouse.down(); p.mouse.move(x + 40, y)
    p.keyboard.press('Escape'); p.mouse.up()
    assert int(handle.get_attribute('aria-valuenow')) == initial
    handle.focus(); p.keyboard.press('ArrowRight')
    assert int(handle.get_attribute('aria-valuenow')) == initial + 12
    assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)') == initial_atoms


def test_analysis_separator_reports_visible_size_and_cancels_vertical_drag(interface_page):
    p = interface_page
    p.get_by_role('tab', name='Analyze', exact=True).click()
    open_editor_route(p, 'rdf')
    p.click('#btn-rdf-calculate')
    drawer = p.locator('#analysis-drawer')
    drawer.wait_for(state='visible')
    handle = p.locator('#analysis-drawer-resizer')
    handle.focus()
    initial = drawer.bounding_box()['height']
    assert int(handle.get_attribute('aria-valuenow')) == pytest.approx(initial, abs=1)
    p.keyboard.press('ArrowUp')
    assert drawer.bounding_box()['height'] == pytest.approx(initial + 8, abs=1)
    box = handle.bounding_box(); x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    p.mouse.move(x, y); p.mouse.down(); p.mouse.move(x, y - 60, steps=4)
    assert drawer.bounding_box()['height'] == pytest.approx(initial + 68, abs=1)
    p.keyboard.press('Escape'); p.mouse.up()
    assert drawer.bounding_box()['height'] == pytest.approx(initial + 8, abs=1)
    assert p.locator('#analysis-drawer').is_visible()


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_range_hit_target_fill_exact_number_and_keyboard(interface_page, theme):
    p = interface_page
    p.evaluate('(theme)=>window.v_aseTheme.apply(theme)', theme)
    slider = p.locator('#atom-radius-scale')
    number = p.locator('#atom-radius-scale-number')
    assert slider.bounding_box()['height'] >= 24
    number.fill('1.17'); number.press('Enter')
    p.wait_for_function('window.__ASE_APP__.state.display.atomRadiusScale === 1.17')
    p.wait_for_function('document.getElementById("atom-radius-scale").style.getPropertyValue("--range-fill") !== ""')
    value, minimum, maximum, fill = slider.evaluate('e=>[+e.value,+e.min,+e.max,parseFloat(e.style.getPropertyValue("--range-fill"))]')
    assert fill == pytest.approx(100 * (value - minimum) / (maximum - minimum))
    slider.focus(); slider.press('ArrowRight')
    assert float(number.input_value()) == pytest.approx(1.18)
    assert p.evaluate('window.__ASE_APP__.state.display.atomRadiusScale') == pytest.approx(1.18)


def test_keyboard_tooltip_is_bounded_and_dismisses(interface_page):
    p = interface_page
    button = p.locator('#tool-orbit')
    initial_title = button.get_attribute('title')
    label = button.get_attribute('data-tooltip')
    assert initial_title
    button.focus()
    tooltip = p.locator('#toolbar-tooltip')
    tooltip.wait_for(state='visible')
    assert tooltip.inner_text() == initial_title
    assert button.get_attribute('title') is None
    assert button.get_attribute('data-tooltip') == label
    p.locator('#editor-search-toggle').focus()
    button.focus()
    assert tooltip.inner_text() == initial_title
    button.evaluate("e=>{e.title='Updated view hint'}")
    p.wait_for_function("document.getElementById('toolbar-tooltip').textContent === 'Updated view hint'", timeout=2000)
    assert tooltip.inner_text() == 'Updated view hint'
    assert button.get_attribute('title') is None
    assert button.get_attribute('data-tooltip') == label
    rect = tooltip.bounding_box()
    assert 0 <= rect['x'] < rect['x'] + rect['width'] <= 1440
    assert 0 <= rect['y'] < rect['y'] + rect['height'] <= 960
    assert button.get_attribute('aria-describedby') == 'toolbar-tooltip'
    p.keyboard.press('Escape')
    assert tooltip.is_hidden()
    assert button.get_attribute('aria-describedby') is None


def test_frame_steps_update_track_without_a_pointer_event(interface_page):
    p = interface_page
    p.click('#btn-frame-next')
    p.wait_for_function('window.__ASE_APP__.timelineFrameIndex("loaded") === 1')
    slider = p.locator('#frame-slider')
    assert slider.input_value() == '1'
    assert float(slider.evaluate('e=>parseFloat(e.style.getPropertyValue("--range-fill"))')) == pytest.approx(50)
    p.click('#btn-frame-next')
    p.wait_for_function('window.__ASE_APP__.timelineFrameIndex("loaded") === 2')
    assert float(slider.evaluate('e=>parseFloat(e.style.getPropertyValue("--range-fill"))')) == pytest.approx(100)


def test_modal_isolation_focus_restore_and_reduced_motion(interface_page):
    p = interface_page
    p.emulate_media(reduced_motion='reduce')
    p.click('#editor-search-toggle')
    search = p.locator('#editor-command-search')
    search.fill('shortcuts')
    # Use the same command exposed in Help; its dialog returns to the opener.
    p.keyboard.press('Escape')
    p.evaluate('window.__ASE_APP__.showShortcutsModal()')
    p.locator('#modal-container:not(.hidden)').wait_for()
    assert p.locator('#top-bar').evaluate('e=>e.inert')
    p.locator('#modal-close').focus()
    p.keyboard.press('Tab')
    assert p.evaluate('document.getElementById("modal-container").contains(document.activeElement)')
    p.keyboard.press('Escape')
    assert not p.locator('#top-bar').evaluate('e=>e.inert')
    assert p.locator('#editor-search-toggle').evaluate('e=>e===document.activeElement')
    open_editor_route(p, 'bonding')
    durations = p.locator('#inspector-content > .editor-route-current').evaluate('e=>[getComputedStyle(e).animationDuration,getComputedStyle(e).transitionDuration]')
    assert float(durations[0].rstrip('s')) <= .00001
    assert durations[1] == '0s'


def test_chrome_palette_and_route_transitions_do_not_modify_the_scene(interface_page):
    p = interface_page
    snapshot = 'JSON.stringify({positions:window.__ASE_APP__.state.atoms.positions,camera:window.__ASE_APP__.cameraSettingsSnapshot(),display:window.__ASE_APP__.state.display})'
    before = json.loads(p.evaluate(snapshot))
    for theme in ('dark', 'light'):
        p.evaluate('(theme)=>window.v_aseTheme.apply(theme)', theme)
        for group in ('Build', 'Analyze', 'Render', 'Style'):
            p.get_by_role('tab', name=group, exact=True).click()
        assert json.loads(p.evaluate(snapshot)) == before
    assert p.locator('#inspector-description').inner_text() == 'Atom size, color and property mapping'
    assert p.locator('body').get_attribute('aria-selected') is None
    assert p.locator('body').get_attribute('tabindex') is None


def test_route_starts_at_top_and_explicit_search_focus_reveals_target(interface_page):
    p = interface_page
    p.get_by_role('tab', name='Render', exact=True).click()
    open_editor_route(p, 'render-image')
    p.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    assert p.locator('#inspector-content').evaluate('e=>e.scrollTop') == 0
    assert p.locator('#renderer-image-format').is_visible()
    assert p.locator('#renderer-pixels-per-angstrom').is_visible()
    assert not p.locator('#render-shared-settings').evaluate('e=>e.open')
    p.evaluate('window.__ASE_APP__.openEditorRoute("render-image", {focus:"#btn-export-image"})')
    assert p.locator('#btn-export-image').evaluate('e=>e===document.activeElement')
    assert p.locator('#inspector-content').evaluate('e=>e.scrollTop') == 0
    p.evaluate('window.__ASE_APP__.openEditorRoute("render-image", {focus:"#renderer-pixels-per-angstrom"})')
    assert p.locator('#renderer-pixels-per-angstrom').evaluate('e=>e===document.activeElement')


@pytest.mark.parametrize('defer_entry_frame', [False, True])
def test_dialog_from_help_returns_to_a_visible_menu_opener(interface_page, defer_entry_frame):
    p = interface_page
    p.locator('#editor-menu-toggle').click()
    p.get_by_text('Help', exact=True).click()
    if defer_entry_frame:
        # A fast Escape must work before the dialog's first animation frame.
        # Defer application RAF callbacks, while Playwright's isolated world
        # can still drive the actual menu item and keyboard event.
        p.evaluate('''()=>{
            window.__entryFrame = window.requestAnimationFrame;
            window.requestAnimationFrame = () => 0;
        }''')
    p.locator('[data-editor-menu-action="shortcuts"]').click()
    p.locator('#modal-container:not(.hidden)').wait_for()
    assert p.locator('#modal-container').evaluate('e=>e.contains(document.activeElement)')
    p.keyboard.press('Escape')
    assert p.locator('#modal-container').evaluate('e=>e.classList.contains("hidden")')
    assert p.locator('#editor-menu-toggle').evaluate('e=>e===document.activeElement')
    assert p.locator('#modal-container').evaluate('e=>e.inert')
    if defer_entry_frame:
        p.evaluate('()=>{window.requestAnimationFrame = window.__entryFrame;}')


def test_first_cell_controls_match_structure_and_survive_reload(interface_page):
    p = interface_page
    for attempt in range(2):
        if attempt:
            p.reload()
            p.wait_for_function('window.__ASE_APP__?.collaborationReady')
        open_editor_route(p, 'cell-replication')
        assert [float(p.input_value(f'#cell-{i}{i}')) for i in range(3)] == [6, 6, 6]
        assert [float(p.input_value(f'#cell-{i}{j}')) for i, j in ((0, 1), (1, 2), (2, 0))] == [0, 0, 0]
        assert not any(p.locator(f'#cell-pbc-{axis}').is_checked() for axis in 'xyz')


def test_colormap_escape_closes_only_the_menu_and_restores_focus(interface_page):
    p = interface_page
    p.locator('#chk-atom-colorscale').check()
    trigger = p.locator('#atom-colormap-trigger')
    menu = p.locator('#atom-colormap-menu')
    for _ in range(3):
        trigger.click()
        p.wait_for_function("document.activeElement.id === 'atom-colormap-menu-search'")
        p.keyboard.press('Escape')
        assert trigger.get_attribute('aria-expanded') == 'false'
        assert menu.evaluate('e=>e.inert')
        assert trigger.evaluate('e=>e === document.activeElement')
        assert not p.locator('body').evaluate('e=>e.classList.contains("inspector-collapsed")')
        menu.wait_for(state='hidden')


def test_inspector_commits_canvas_once_and_animates_only_the_panel(interface_page):
    p = interface_page
    capture = """() => ({
        canvas: window.__ASE_APP__.renderer.domElement.getBoundingClientRect().toJSON(),
        camera: window.__ASE_APP__.cameraSettingsSnapshot()
    })"""
    before = p.evaluate(capture)
    transition = p.evaluate("""async () => {
        const pane=document.getElementById('inspector'),r=window.__ASE_APP__.renderer;
        const initial=pane.getBoundingClientRect(),original=r.renderer.setSize.bind(r.renderer);let allocations=0;
        r.renderer.setSize=(...args)=>{allocations++;return original(...args);};
        document.getElementById('editor-inspector-toggle').click();
        const animation=pane.getAnimations().find(a=>a.transitionProperty==='translate');
        if(!animation)throw Error('Panel reveal transition missing');
        animation.pause();animation.currentTime=70;
        const middle=pane.getBoundingClientRect(),canvasMiddle=r.domElement.getBoundingClientRect().toJSON();
        animation.finish();await new Promise(resolve=>setTimeout(resolve,180));
        const end=pane.getBoundingClientRect(),canvasEnd=r.domElement.getBoundingClientRect().toJSON();
        r.renderer.setSize=original;
        return {initial:initial.x,middle:middle.x,end:end.x,width:middle.width,originalWidth:initial.width,
            canvasMiddle,canvasEnd,allocations,inert:document.getElementById('inspector-pane').inert};
    }""")
    assert transition['initial'] < transition['middle'] < transition['end']
    assert transition['width'] == transition['originalWidth']
    assert transition['canvasMiddle'] == transition['canvasEnd']
    assert transition['allocations'] == 1
    assert transition['inert']
    p.locator('#editor-inspector-toggle').click()
    p.wait_for_function("!document.getElementById('inspector-pane').inert")
    p.wait_for_function('(width)=>Math.abs(window.__ASE_APP__.renderer.domElement.getBoundingClientRect().width-width)<.1',arg=before['canvas']['width'])
    assert p.evaluate(capture) == before
