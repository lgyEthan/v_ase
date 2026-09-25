"""Status bar, scene visibility and flat-mode controls share the rendered state."""
from tests.test_browser_camera_property_persistence import page
from tests.ui_navigation import open_editor_route


def test_single_atom_properties_live_in_footer(page):
    page.evaluate('''()=>{const a=window.__ASE_APP__;a.state.selected=new Set([0]);a.updateSelectionVisuals();a.updateUI();}''')
    page.wait_for_function("document.getElementById('hover-readout').textContent.includes('existence = 0.2')")
    text=page.locator('#hover-readout').inner_text()
    assert 'H' in text and 'X:' in text and 'Y:' in text and 'Z:' in text
    for unwanted in ['mass =', 'Element:', 'fractional', 'Position (Cartesian)']:
        assert unwanted not in text
    assert not page.locator('#selection-measure-readout').is_visible()
    assert not page.locator('#workbench-selection').is_visible()


def test_constraint_visibility_and_flat_controls(page):
    page.evaluate('''async()=>{const a=window.__ASE_APP__;await a.aiApply({mode:'edit'});
        const data=await a.api.updateConstraints([0],{fix_atoms:true});a.setAtomsData(data);a.updateUI();}''')
    page.click('#btn-objects')
    page.get_by_role('checkbox', name='Show Constraints', exact=True).uncheck()
    assert not page.evaluate('window.__ASE_APP__.renderer.fixedAtomDisplayEnabled()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.constraints.fixed_indices') == [0]
    page.get_by_role('checkbox', name='Show Constraints', exact=True).check()
    assert page.evaluate('window.__ASE_APP__.renderer.fixedAtomDisplayEnabled()')
    page.click('#btn-objects')
    open_editor_route(page, 'export')
    page.select_option('#renderer-atom-display-mode','2d')
    assert page.locator('#renderer-lighting-mode').is_disabled()
    open_editor_route(page, 'appearance')
    assert page.locator('[data-appearance-field="material"]').first.is_disabled()
    open_editor_route(page,'export')
    page.select_option('#renderer-atom-display-mode','3d')
    assert page.locator('#renderer-lighting-mode').is_enabled()


def test_delayed_property_catalog_has_nonblocking_activity_indicator(page):
    open_editor_route(page, 'appearance')
    page.evaluate('''()=>{const a=window.__ASE_APP__;const original=a.ensureAtomScalarCatalog.bind(a);
      a.ensureAtomScalarCatalog=async(...args)=>{await new Promise(r=>window.finishCatalog=r);return original(...args)};
      window.catalogJob=a.ensureAtomColorScaleCatalog();}''')
    assert page.locator('.atom-colorscale-card > .section-activity').is_visible()
    assert page.get_attribute('.atom-colorscale-card','aria-busy') == 'true'
    page.evaluate('async()=>{window.finishCatalog();await window.catalogJob;}')
    assert not page.locator('.atom-colorscale-card > .section-activity').is_visible()


def test_flat_constraints_and_object_visibility_match_png_and_gif(page):
    import base64
    import io
    import numpy as np
    from PIL import Image
    result=page.evaluate('''async()=>{
        const a=window.__ASE_APP__,r=a.renderer;
        await a.aiApply({mode:'edit'});
        a.setAtomsData(await a.api.updateConstraints([0],{fix_atoms:true}));
        a.applyDesignSettings({display:{atomDisplayMode:'2d',showGrid:false,showAxes:false,showCell:false}});
        a.applyCameraSettings({position:[2,0,10],target:[2,0,0],up:[0,1,0],projection:'orthographic',ortho_scale:4});
        a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();a.setRenderCameraNavigation(false);
        const visible=await a.aiRender({format:'png',width:320,height:180});
        a.state.display.showConstraints=false;r.setDisplayOptions(a.state.display);
        const hidden=await a.aiRender({format:'png',width:320,height:180});
        r.controls.rotate(120,60);
        const video=await a.aiExport({format:'video',container:'gif',width:320,height:180,fps:5,loop:false});
        return {visible,hidden,video,profile:a.currentImageExportProfile().options,
          constraints:a.state.atoms.constraints.fixed_indices};
    }''')
    def decode(artifact):
        return Image.open(io.BytesIO(base64.b64decode(artifact['dataUrl'].split(',')[1])))
    visible=decode(result['visible']).convert('RGB')
    visible.save('/tmp/vase-046-flat-constraint.png')
    hidden=decode(result['hidden']).convert('RGB')
    assert np.abs(np.asarray(visible,dtype=float)-np.asarray(hidden,dtype=float)).sum()>1000
    with decode(result['video']) as video:
        assert video.n_frames==3
        assert video.size==(320,180)
        assert np.abs(np.asarray(video.convert('RGB'),dtype=float)-np.asarray(hidden,dtype=float)).mean()<3
    assert result['constraints']==[0]
    assert all(result['profile'][key] is False for key in ['includeGrid','includeAxes','includeCell'])
