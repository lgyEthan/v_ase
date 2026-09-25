"""Camera lock reference and render area remain coherent on every input frame."""
import pytest
from tests.test_browser_camera_property_persistence import page


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
def test_viewport_locked_grs_keeps_frame_stationary_and_cancel_restores(page, projection):
    result = page.evaluate('''projection => {
      const a=window.__ASE_APP__,r=a.renderer;
      a.applyCameraSettings({...a.currentCameraForExport(),projection});
      a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();a.setRenderCameraNavigation(true);r.renderNow();
      const rect=()=>({...r.lastExportPreview.frameRect});
      const before=rect(),view=a.currentCameraForExport(),camera=structuredClone(a.state.exportPreviewCamera);
      a.viewOutputCamera();const look={follow:a.state.exportPreviewFollowViewport,camera:structuredClone(a.state.exportPreviewCamera)};
      const cases=[];
      for(const [mode,axis,buffer] of [['MOVE','X','2'],['ROTATE','Z','30'],['SCALE',null,'1.5']]) {
        a.setRenderAreaSelected(true);a.enterRenderAreaTransformMode(mode);
        a.transform.axis=axis;a.transform.buffer=buffer;a.applyTransformPreview();r.renderNow();
        cases.push({mode,rect:rect(),view:a.currentCameraForExport(),aligned:r.lastExportPreview.aligned});
        a.cancelRenderAreaTransform();r.renderNow();
      }
      return {before,view,camera,look,cases,restored:a.currentCameraForExport()};
    }''', projection)
    assert result['look']['follow']
    assert result['look']['camera'] == result['camera']
    for case in result['cases']:
        assert case['aligned'], case
        for key in ['left', 'top', 'width', 'height']:
            assert case['rect'][key] == pytest.approx(result['before'][key], abs=.01), case
        assert case['view'] != result['view']
    assert result['restored'] == result['view']


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
def test_axis_immediately_preserves_frame_and_camera_button_state(page, projection):
    page.evaluate('''projection=>{const a=window.__ASE_APP__;a.applyCameraSettings({...a.currentCameraForExport(),projection});
      a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();a.setRenderCameraNavigation(true);}''', projection)
    for axis in ['+X', '+Y', '+Z', '-X', '-Y', '-Z']:
        result = page.evaluate('''axis=>{const a=window.__ASE_APP__;a.setAIAxisView(axis);a.renderer.renderNow();
          return {aligned:a.renderer.lastExportPreview.aligned,hidden:document.getElementById('export-preview-frame').classList.contains('hidden'),
          pressed:document.getElementById('btn-render-area-from-view').getAttribute('aria-pressed')};}''', axis)
        assert result == dict(aligned=True, hidden=False, pressed='true'), (axis, result)
    page.evaluate('''()=>{const a=window.__ASE_APP__;a.setRenderCameraNavigation(false);a.renderer.controls.pan(4,3);
        a.renderer.controls.doZoom(10);}''')
    assert page.get_attribute('#btn-render-area-from-view', 'aria-pressed') == 'true'
    page.evaluate('window.__ASE_APP__.renderer.controls.rotate(80,30)')
    assert page.get_attribute('#btn-render-area-from-view', 'aria-pressed') == 'false'
    page.click('#btn-render-area-from-view')
    assert page.get_attribute('#btn-render-area-from-view', 'aria-pressed') == 'true'
    assert not page.evaluate('window.__ASE_APP__.state.exportPreviewFollowViewport')


def test_real_axis_keys_keep_render_area_and_supercell_selects_input(page):
    page.keyboard.press('Meta+Shift+a')
    page.click('#btn-preview-image')
    page.click('[data-camera-navigation="camera"]')
    page.evaluate('window.__ASE_APP__.renderer.domElement.focus()')
    for key in ['x', 'y', 'z', 'x']:
        page.keyboard.press(key)
        page.wait_for_function("!document.getElementById('export-preview-frame').classList.contains('hidden')")
        assert page.get_attribute('#btn-render-area-from-view', 'aria-pressed') == 'true'
    page.evaluate('''()=>{const a=window.__ASE_APP__;a.setAtomsData({...a.state.atoms, cell:[[8,0,0],[0,8,0],[0,0,8]],pbc:[true,true,true]});a.updateUI();}''')
    page.keyboard.press('Meta+Shift+b')
    assert page.evaluate('document.activeElement.id') == 'super-x'
    page.keyboard.type('2')
    page.keyboard.press('Tab')
    page.keyboard.type('2')
    page.keyboard.press('Tab')
    assert page.input_value('#super-x') == '2'
    assert page.input_value('#super-y') == '2'
