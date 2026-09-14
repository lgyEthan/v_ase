"""Pointer-level coverage for the toolbar lighting popover (not just DOM visibility)."""
import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port

@pytest.mark.parametrize('width,height', [(2308,1190), (1280,800), (390,844), (640,300)])
def test_lighting_popover_is_clickable_outside_scrolling_toolbar(width, height):
    port=find_free_port()
    editor=view(Atoms('CuO',positions=[[0,0,0],[2,0,0]],cell=[8,8,8]),notebook=True,block=False,port=port,viz_only=False,close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':width,'height':height})
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            trigger=page.locator('#btn-lighting-toggle')
            trigger.click()
            assert trigger.get_attribute('aria-expanded')=='true'
            mode=page.locator('#lighting-mode')
            # is_visible()/bounding_box() and select_option() alone do not catch
            # an ancestor clipping an otherwise laid-out element.
            assert mode.evaluate('''el => {
                const r=el.getBoundingClientRect();
                return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));
            }'''), 'Lighting options are clipped or covered after opening'
            mode.click(timeout=2000)
            mode.select_option('studio')
            page.wait_for_function("window.__ASE_APP__.state.display.lightingMode === 'studio'")
            assert page.locator('#lighting-card').is_visible()
            page.locator('#btn-lighting-close').click(timeout=2000)
            assert trigger.get_attribute('aria-expanded')=='false'
            trigger.click()
            page.set_viewport_size({'width': max(340,width-100), 'height':height})
            page.wait_for_function('''() => {
                const card=document.getElementById('lighting-card').getBoundingClientRect();
                return card.left >= 0 && card.right <= innerWidth && card.bottom <= innerHeight;
            }''')
            page.keyboard.press('Escape')
            assert trigger.get_attribute('aria-expanded')=='false'
            assert trigger.evaluate('el => el === document.activeElement')
            trigger.click()
            page.mouse.click(8,height-12)
            assert trigger.get_attribute('aria-expanded')=='false'
            browser.close()
    finally:
        editor.close()
