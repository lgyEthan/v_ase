"""Output camera navigation and index-scoped properties across topology changes."""
import numpy as np
import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port
from tests.ui_navigation import open_editor_route


@pytest.fixture
def page():
    frames = []
    for symbols, values in [('HOC', [.2, .4, .6]), ('He', [.7]), ('COH', [.3, .5, .9])]:
        atoms = Atoms(symbols, positions=[[i * 2, 0, 0] for i in range(len(values))])
        atoms.new_array('existence', np.array(values))
        frames.append(atoms)
    editor = view(frames, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.add_init_script("Object.defineProperty(navigator,'userAgentData',{value:{platform:'macOS'},configurable:true})")
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            yield page
            browser.close()
    finally:
        editor.close()


def test_index_targets_survive_short_and_changed_element_frames_and_settings(page):
    result = page.evaluate('''async () => {
        const a=window.__ASE_APP__;
        Object.assign(a.state.display,{atomColorScaleEnabled:true,atomColorScaleField:'array::existence::scalar',
          atomColorScaleScope:'selected',atomColorScaleIndices:[2],atomColorScaleRangeMode:'manual',
          atomColorScaleMin:0,atomColorScaleMax:1});
        a.state.display.atomRadiusMapping={enabled:true,field:'array::existence::scalar',
          valueTransform:'identity',rangeMode:'manual',min:0,max:1,minMultiplier:0,maxMultiplier:1,
          exponent:1,scope:'indices',indices:[2]};
        await a.updateAtomColorScale(); await a.updateAtomRadiusMapping();
        await a.loadFrame(1);
        const settings=a.designSettingsSnapshot();
        a.applyDesignSettings(settings);
        await a.aiApply({mode:'edit'});
        await a.aiApply({operation:{name:'move-selection',indices:[0],vector:[.25,0,0]}});
        const short={color:a.state.display.atomColorScaleIndices,radius:a.state.display.atomRadiusMapping};
        await a.loadFrame(2);
        const last={color:[...a.renderer.atomColorScaleColors],radius:[...a.renderer.atomRadiusFactors],
          symbols:a.state.atoms.chemical_symbols};
        await a.loadFrame(0);
        return {short,last,back:{color:[...a.renderer.atomColorScaleColors],radius:[...a.renderer.atomRadiusFactors]}};
    }''')
    assert result['short']['color'] == [2]
    assert result['short']['radius']['indices'] == [2]
    assert result['short']['radius']['enabled']
    assert result['last']['color'][:2] == [None, None]
    assert result['last']['color'][2]
    assert result['last']['radius'] == pytest.approx([1, 1, .9])
    assert result['back']['radius'] == pytest.approx([1, 1, .6])


def test_label_target_and_bottom_atom_properties(page):
    open_editor_route(page, 'appearance')
    page.check('#chk-atom-colorscale')
    page.select_option('#atom-colorscale-field', 'array::existence::scalar')
    page.fill('#atom-colorscale-min', '0')
    page.locator('#atom-colorscale-min').press('Enter')
    page.fill('#atom-colorscale-max', '1')
    page.locator('#atom-colorscale-max').press('Enter')
    page.select_option('#atom-colorscale-scope', 'label:C')
    page.wait_for_function('window.__ASE_APP__.renderer.atomColorScaleColors?.[2] != null')
    assert page.evaluate('window.__ASE_APP__.state.display.atomColorScaleIndices') == [2]
    assert page.evaluate('''() => {const d=window.__ASE_APP__.state.display;
      return [d.atomColorScaleRangeMode,d.atomColorScaleMin,d.atomColorScaleMax];}''') == ['manual', 0, 1]
    page.evaluate('''() => {const a=window.__ASE_APP__;a.state.selected=new Set([0]);a.updateSelectionVisuals();a.updateUI();}''')
    page.wait_for_function("document.getElementById('selection-measure-value').textContent.includes('existence = 0.2')")
    assert page.locator('#selection-measure-readout').is_visible()
    page.click('#btn-atom-colorscale-use-selection')
    assert page.input_value('#atom-colorscale-scope') == 'selected'
    assert page.evaluate('window.__ASE_APP__.state.display.atomColorScaleIndices') == [0]
    assert page.evaluate('''() => {const d=window.__ASE_APP__.state.display;
      return [d.atomColorScaleRangeMode,d.atomColorScaleMin,d.atomColorScaleMax];}''') == ['manual', 0, 1]
    assert 'Fixed' not in page.locator('#atom-colorscale-scope').inner_text()


def test_cached_property_dropdown_keeps_option_nodes(page):
    page.wait_for_function("document.querySelector('#atom-colorscale-field option[value=\"array::existence::scalar\"]')")
    assert page.evaluate('''async () => {
      const a=window.__ASE_APP__, el=document.getElementById('atom-colorscale-field');
      const option=el.options[0]; await a.ensureAtomColorScaleCatalog();
      return option===el.options[0];
    }''')


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
def test_fixed_camera_zoom_and_axis_views_do_not_change_output(page, projection):
    result = page.evaluate('''async projection => {
      const a=window.__ASE_APP__,r=a.renderer;
      a.applyCameraSettings({...a.currentCameraForExport(),projection});
      a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();
      const p=a.currentImageExportProfile();p.width=1920;p.height=1080;
      p.options.scaleMode='physical';p.options.pixelsPerAngstrom=10;a.setImageExportProfile(p);
      a.viewOutputCamera();r.renderNow();
      const composition=()=>r.exportCompositionSnapshot(p.width,p.height,a.currentImageExportProfile().options);
      const before=composition(), rect={...r.lastExportPreview.frameRect};
      const image=r.exportPNG(256,144,a.currentImageExportProfile().options);
      r.controls.doZoom(120);r.renderNow();
      const zoomed={...r.lastExportPreview.frameRect};
      r.controls.rotate(.3,.4);r.renderNow();
      const unchanged=image===r.exportPNG(256,144,a.currentImageExportProfile().options);
      const after=composition(),saved=structuredClone(a.state.exportPreviewCamera);
      a.viewOutputCamera();r.renderNow();
      return {before,after,rect,zoomed,saved,unchanged,restored:a.state.exportPreviewCamera,
        aligned:r.lastExportPreview.aligned,fit:r.lastExportPreview.frameRect};
    }''', projection)
    assert result['before'] == result['after']
    assert result['unchanged']
    assert result['saved'] == result['restored']
    assert result['zoomed']['width'] < result['rect']['width']
    assert result['aligned']
    assert 0 < result['fit']['width'] < result['fit']['canvasWidth']
    assert 0 < result['fit']['height'] < result['fit']['canvasHeight']
    # Real keyboard axis navigation cannot move the fixed camera either.
    page.evaluate('window.__ASE_APP__.renderer.domElement.focus()')
    before = page.evaluate('window.__ASE_APP__.state.exportPreviewCamera')
    for key in ['x', 'y', 'z']:
        page.keyboard.press(key)
        assert page.evaluate('window.__ASE_APP__.state.exportPreviewCamera') == before


def test_output_shortcuts_recover_invalid_draft_without_applying_it(page):
    page.keyboard.press('Meta+Shift+a')
    page.click('#btn-preview-image')
    scale = page.locator('#renderer-pixels-per-angstrom')
    previous = page.evaluate('window.__ASE_APP__.currentImageExportProfile().options.pixelsPerAngstrom')
    scale.fill('-2')
    page.keyboard.press('Meta+Shift+p')
    page.wait_for_function("window.__ASE_APP__.editorRoute==='appearance'")
    assert page.evaluate('window.__ASE_APP__.currentImageExportProfile().options.pixelsPerAngstrom') == previous
    page.keyboard.press('Meta+Shift+a')
    page.wait_for_function("window.__ASE_APP__.editorRoute==='export'")
    assert page.evaluate('window.__ASE_APP__.invalidDraftInput') is None
    assert page.locator('.renderer-output-group #btn-preview-image').is_visible()


def test_default_gif_uses_saved_camera_after_editor_zoom(page):
    import base64
    import io
    from PIL import Image
    result = page.evaluate('''async () => {
      const a=window.__ASE_APP__,r=a.renderer;
      a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();
      a.viewOutputCamera();r.controls.doZoom(-150);r.controls.rotate(.2,.1);
      const viewport=a.currentCameraForExport();
      const gif=await a.aiExport({format:'video',container:'gif',width:256,height:144,fps:5,loop:false});
      await a.loadFrame(2);
      const png=await a.aiRender({format:'png',width:256,height:144});
      return {gif,png,viewport,after:a.currentCameraForExport()};
    }''')
    assert result['gif']['effectiveRender']['source'] == 'render-area'
    assert result['gif']['camera'] == result['png']['camera']
    # Resize/capture may rebase orthographic frustum/zoom without changing its physical span.
    for key in result['viewport']:
        if key != 'zoom' or result['viewport']['projection'] == 'perspective':
            assert result['after'][key] == result['viewport'][key]
    with Image.open(io.BytesIO(base64.b64decode(result['gif']['dataUrl'].split(',')[1]))) as gif:
        assert gif.n_frames == 3
        gif.seek(2)
        final = np.array(gif.convert('RGB'), dtype=float)
    with Image.open(io.BytesIO(base64.b64decode(result['png']['dataUrl'].split(',')[1]))) as png:
        reference = np.array(png.convert('RGB'), dtype=float)
    assert np.abs(final - reference).mean() < 3  # GIF palette quantization only.
