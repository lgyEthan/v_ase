"""Camera visibility, responsive controls and uninterrupted viewport presentation."""
import pytest

from tests.test_browser_camera_property_persistence import page


def test_camera_icons_and_objects_share_visibility_and_unlock_when_hidden(page):
    page.keyboard.press('Meta+Shift+a')
    assert not page.evaluate('window.__ASE_APP__.state.exportPreviewFollowViewport')
    assert page.locator('#btn-preview-image svg').is_visible()
    assert page.locator('#btn-preview-image').inner_text() == ''
    page.click('#btn-preview-image')
    original = page.evaluate('structuredClone(window.__ASE_APP__.state.exportPreviewCamera)')
    page.click('#btn-camera-lock-viewport')
    assert page.get_attribute('#btn-camera-lock-viewport', 'aria-pressed') == 'true'
    page.click('#btn-render-area-from-view')
    for selector in ['#btn-preview-image', '#btn-render-area-from-view', '#btn-camera-lock-viewport']:
        assert page.get_attribute(selector, 'aria-pressed') == 'false'
    assert page.locator('#export-preview-frame').is_hidden()
    page.click('#btn-objects')
    checkbox = page.get_by_role('checkbox', name='Show Camera / render area', exact=True)
    assert not checkbox.is_checked()
    checkbox.check()
    assert page.get_attribute('#btn-preview-image', 'aria-pressed') == 'true'
    page.click('#btn-camera-lock-viewport')
    checkbox.uncheck()
    assert not page.evaluate('window.__ASE_APP__.state.exportPreviewFollowViewport')
    assert page.evaluate('window.__ASE_APP__.state.exportPreviewCamera') == original
    page.evaluate('''async()=>{const a=window.__ASE_APP__;
      await a.aiApply({renderArea:{enabled:true,followViewport:true}});
      a.setRenderAreaSelected(true);
      await a.aiApply({renderArea:{enabled:false}});
    }''')
    assert not page.evaluate('window.__ASE_APP__.state.exportPreviewFollowViewport')
    assert not page.evaluate('window.__ASE_APP__.state.renderAreaSelected')
    # Saving/restoring an old hidden + follow combination must never leave an
    # invisible camera attached to future viewport navigation.
    page.evaluate('window.__ASE_APP__.applyDesignSettings({renderArea:{visible:false,followViewport:true}})')
    assert not page.evaluate('window.__ASE_APP__.state.exportPreviewFollowViewport')


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
@pytest.mark.parametrize('collapsed', [True, False])
def test_enter_camera_view_fits_open_panel_work_area_without_changing_output(page, projection, collapsed):
    result = page.evaluate('''({projection,collapsed})=>{
      const a=window.__ASE_APP__,r=a.renderer;
      a.applyCameraSettings({...a.currentCameraForExport(),projection});a.captureRenderAreaCamera();
      const before=structuredClone(a.state.exportPreviewCamera);
      a.setInspectorCollapsed(collapsed);a.setRenderAreaVisible(true,{enterView:true});r.renderNow();
      const area={...r.lastExportPreview.frameRect}, pose=a.currentCameraForExport();
      a.setInspectorCollapsed(!collapsed);r.renderNow();
      return {before,after:a.state.exportPreviewCamera,area,pose,afterPanel:a.currentCameraForExport(),
        panel:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--inspector-width')),
        width:r.containerSize().width};
    }''', dict(projection=projection, collapsed=collapsed))
    area = result['area']
    assert area['left'] + area['width'] / 2 == pytest.approx((result['width'] - result['panel']) / 2, abs=.1)
    assert area['left'] > 0
    assert area['left'] + area['width'] < result['width'] - result['panel']
    assert result['before'] == result['after']
    assert result['pose'] == result['afterPanel']


def test_rotation_controls_inline_when_spacious_and_animated_disclosure_when_narrow(page):
    page.set_viewport_size(dict(width=1800, height=960))
    page.wait_for_function("!document.getElementById('camera-more').classList.contains('compact')")
    assert not page.locator('#camera-rotation-toggle').is_visible()
    assert page.locator('[data-view-rotate="left"]').is_visible()
    page.fill('#view-rotate-step', '30')
    page.locator('#view-rotate-step').press('Enter')
    page.set_viewport_size(dict(width=1000, height=800))
    page.wait_for_function("document.getElementById('camera-more').classList.contains('compact')")
    assert page.get_attribute('#camera-rotation-toggle', 'aria-expanded') == 'false'
    assert page.evaluate("document.getElementById('camera-more-content').inert")
    page.click('#camera-rotation-toggle')
    page.locator('[data-view-rotate="left"]').click()
    bounds = page.evaluate('''()=>{
      const content=document.getElementById('camera-more-content').getBoundingClientRect();
      const toolbar=document.getElementById('view-toolbar').getBoundingClientRect();
      return {left:content.left,right:content.right,width:content.width,toolbar:toolbar.width,viewport:innerWidth};
    }''')
    assert bounds['left'] >= 0 and bounds['right'] <= bounds['viewport']
    assert bounds['width'] >= bounds['toolbar']
    assert page.input_value('#view-rotate-step') == '30'
    assert page.get_attribute('#camera-rotation-toggle', 'aria-expanded') == 'true'
    page.locator('#camera-rotation-toggle').press('Escape')
    assert page.get_attribute('#camera-rotation-toggle', 'aria-expanded') == 'false'
    assert page.evaluate("document.activeElement.id") == 'camera-rotation-toggle'
    page.set_viewport_size(dict(width=1800, height=960))
    page.wait_for_function("!document.getElementById('camera-more').classList.contains('compact')")
    assert not page.evaluate("document.getElementById('camera-more-content').inert")
    assert page.input_value('#view-rotate-step') == '30'
    page.locator('#view-rotate-step').focus()
    page.set_viewport_size(dict(width=1000, height=800))
    page.wait_for_function("document.getElementById('camera-more').classList.contains('compact')")
    assert page.evaluate('document.activeElement.id') == 'view-rotate-step'
    assert page.get_attribute('#camera-rotation-toggle', 'aria-expanded') == 'true'


def test_locking_a_hidden_camera_restores_its_view_without_overwriting_its_projection(page):
    result = page.evaluate('''()=>{
      const a=window.__ASE_APP__,r=a.renderer;
      a.captureRenderAreaCamera();const before=structuredClone(a.state.exportPreviewCamera);
      a.setRenderAreaVisible(false);r.controls.rotate(80,50);r.controls.pan(200,100);
      a.applyCameraSettings({...a.currentCameraForExport(),projection:'perspective'});
      a.setRenderCameraNavigation(true);r.renderNow();
      return {before,after:a.state.exportPreviewCamera,aligned:r.lastExportPreview.aligned,
        visible:a.state.exportPreviewEnabled,follow:a.state.exportPreviewFollowViewport};
    }''')
    assert result['before'] == result['after']
    assert result['aligned'] and result['visible'] and result['follow']


def test_deselect_does_not_clear_canvas_and_resize_paints_before_returning(page):
    page.evaluate('''()=>{
      const a=window.__ASE_APP__,r=a.renderer;
      a.applySelectionAction({references:[0,1,2]});
      window.canvasSizeWrites=[];
      new MutationObserver(records=>canvasSizeWrites.push(...records.map(r=>r.attributeName)))
        .observe(r.domElement,{attributes:true,attributeFilter:['width','height']});
    }''')
    page.locator('#app-viewport canvas').focus()
    page.keyboard.press('Alt+a')
    page.wait_for_function('window.__ASE_APP__.selectionCount() === 0')
    result = page.evaluate('''async()=>{
      const a=window.__ASE_APP__,r=a.renderer;
      r.onResize();r.onResize();
      await new Promise(resolve=>requestAnimationFrame(resolve));
      const redundantWrites=[...canvasSizeWrites], paints=[];
      const resize=r.onResize.bind(r);
      r.onResize=()=>{const count=r.renderCount;resize();paints.push(r.renderCount-count)};
      // Reproduce a status-row layout change during selection/hover. An RO
      // callback must render synchronously, before the newly cleared canvas
      // can be composited as a blank frame.
      document.getElementById('command-bar').style.minHeight='170px';
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      return {redundantWrites,paints};
    }''')
    assert result['redundantWrites'] == []
    assert result['paints'] and all(count >= 1 for count in result['paints'])
