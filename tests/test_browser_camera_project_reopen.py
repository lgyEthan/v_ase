"""Regressions for saved project presentation and an independently editable camera."""
import base64
import io

import numpy as np
import pytest
from PIL import Image
from tests.test_browser_camera_property_persistence import page  # noqa: F401


@pytest.mark.parametrize('saved_view', [False, True])
def test_replacement_project_load_adopts_saved_mode_before_display(page, saved_view):
    state = page.evaluate('''async savedView => {
        const a=window.__ASE_APP__;
        await a.switchRuntimeMode(savedView);
        a.applySelectionAction({references:[2],origin:'semantic'});
        const exported=await a.aiExport({format:'project'});
        const blob=await (await fetch(exported.dataUrl)).blob();
        await a.switchRuntimeMode(!savedView);
        await a.loadStructureFile(new File([blob],'mode.vase'),'vase',':',null,{confirmedIntent:true,throwErrors:true});
        return {mode:a.state.vizOnly,display:a.state.display.vizOnly,backend:a.state.atoms.metadata.config.viz_only,
            selection:[...a.state.selected],
            pressed:document.querySelector('[data-runtime-mode="view"]').getAttribute('aria-pressed')};
    }''', saved_view)
    assert state == dict(mode=saved_view, display=saved_view, backend=saved_view, selection=[2], pressed=str(saved_view).lower())


@pytest.mark.parametrize('mode', ['edit', 'view'])
def test_vase_restores_mode_frame_view_and_opens_without_import_dialog(page, mode):
    result = page.evaluate('''async mode => {
        const a=window.__ASE_APP__;
        await a.switchRuntimeMode(mode==='view');
        await a.loadFrame(2);
        a.renderer.controls.rotate(.2,.1);
        Object.assign(a.state.display,{atomColorScaleEnabled:true,atomColorScaleField:'array::existence::scalar',
            atomColorScaleScope:'selected',atomColorScaleIndices:[1],atomColorScaleRangeMode:'manual',
            atomColorScaleMin:0,atomColorScaleMax:1,
            atomRadiusMapping:{enabled:true,field:'array::existence::scalar',valueTransform:'identity',
                rangeMode:'manual',min:0,max:1,minMultiplier:.2,maxMultiplier:1,exponent:1,scope:'all',indices:[]}});
        await a.updateAtomColorScale();await a.updateAtomRadiusMapping();
        a.applySelectionAction({references:[1],origin:'semantic'});
        a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();a.viewOutputCamera();
        a.openEditorRoute('export');
        a.setInspectorWidth(480);
        const settings=a.projectSettingsSnapshot('vase');
        const image=a.renderer.exportPNG(400,300,{...a.currentImageExportProfile().options,includeGrid:false,includeAxes:false});
        const blob=await a.api.saveProject(a.backendPositionsPayload(),settings,a.state.applyConstraints);
        const file=new File([blob],'saved.vase');
        a.markProjectSavedContent();
        await a.switchRuntimeMode(mode!=='view');
        await a.loadFrame(0);
        await a.showOpenFileModal(file);
        return {settings, image, original:a.sessionId};
    }''', mode)
    # Direct/notebook mode is adopted without replacing its original document.
    page.wait_for_function('''() => [...document.querySelectorAll('iframe')].some(f=>
        f.contentWindow?.__ASE_APP__?.collaborationReady)''')
    restored = page.evaluate('''async () => {
        const a=[...document.querySelectorAll('iframe')].map(f=>f.contentWindow?.__ASE_APP__).find(a=>a?.collaborationReady);
        await a.updateAtomColorScale();await a.updateAtomRadiusMapping();
        return {mode:a.state.vizOnly, frame:a.state.atoms.metadata.current_frame,
            image:a.renderer.exportPNG(400,300,{...a.currentImageExportProfile().options,includeGrid:false,includeAxes:false}),
            settings:a.projectSettingsSnapshot('vase'), modal:!a.renderer.domElement.ownerDocument
                .getElementById('modal-container').classList.contains('hidden')};
    }''')
    assert restored['mode'] == (mode == 'view')
    assert restored['frame'] == 2
    assert not restored['modal']
    for key in ['position', 'target', 'up', 'projection']:
        assert restored['settings']['camera'][key] == result['settings']['camera'][key]
    assert restored['settings']['renderArea'] == result['settings']['renderArea']
    assert restored['settings']['presentation']['route'] == 'export'
    assert restored['settings']['presentation']['selection'][0]['index'] == 1
    assert restored['settings']['presentation']['inspectorWidth'] == 480
    def pixels(data):
        return np.array(Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB'), dtype=float)
    assert np.abs(pixels(result['image']) - pixels(restored['image'])).mean() < 0.1


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
def test_navigation_target_switch_preserves_composition_and_camera_grs(page, projection):
    result = page.evaluate('''projection => {
        const a=window.__ASE_APP__, r=a.renderer;
        a.applyCameraSettings({...a.currentCameraForExport(),projection});
        a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();a.viewOutputCamera();
        const before=structuredClone(a.currentImageExportProfile());
        a.setRenderCameraNavigation(true);
        const switched=structuredClone(a.currentImageExportProfile());
        r.controls.rotate(80,50);
        const followed=structuredClone(a.state.exportPreviewCamera);
        a.setRenderCameraNavigation(false);
        r.controls.rotate(120,80);
        const fixed=structuredClone(a.state.exportPreviewCamera);
        a.setRenderAreaSelected(true);
        a.enterRenderAreaTransformMode('SCALE');a.transform.buffer='2';a.applyTransformPreview();
        const scaled=a.currentImageExportProfile();a.cancelRenderAreaTransform();
        const canceled=a.currentImageExportProfile();
        a.enterRenderAreaTransformMode('ROTATE');a.transform.axis='Z';a.transform.buffer='90';a.applyTransformPreview();
        const rotated=structuredClone(a.state.exportPreviewCamera);a.commitRenderAreaTransform();
        a.enterRenderAreaTransformMode('MOVE');a.transform.axis='X';a.transform.buffer='2';a.applyTransformPreview();
        const moved=structuredClone(a.state.exportPreviewCamera);a.commitRenderAreaTransform();
        return {before,switched,followed,fixed,scaled,canceled,rotated,moved};
    }''', projection)
    assert result['before'] == result['switched']
    assert result['followed'] != result['before']['options']['camera']
    assert result['followed'] == result['fixed']
    assert result['canceled']['options']['camera'] == result['fixed']
    assert result['scaled']['options']['camera']['ortho_scale'] == pytest.approx(result['fixed']['ortho_scale'] * 2)
    assert result['rotated']['target'] == result['fixed']['target']
    assert result['rotated']['position'] != result['fixed']['position']
    assert result['moved']['position'][0] == pytest.approx(result['rotated']['position'][0] + 2)
    assert result['moved']['target'][0] == pytest.approx(result['rotated']['target'][0] + 2)


def test_stale_near_plane_cannot_slice_atoms_and_camera_overlay_does_not_mask(page):
    result = page.evaluate('''() => {
        const a=window.__ASE_APP__,r=a.renderer;
        a.applyCameraSettings({position:[2,0,10],target:[2,0,0],up:[0,1,0],projection:'orthographic',ortho_scale:8,near:.01,far:1000});
        const image=near=>r.exportPNG(400,400,{camera:{...a.currentCameraForExport(),near},includeGrid:false,includeAxes:false,includeCell:false});
        const before=image(.01), sliced=image(10.2);
        a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();a.setRenderCameraNavigation(false);
        r.controls.rotate(160,90);r.renderNow();
        return {before,sliced,gridDepthWrite:r.gridGroup.children[0].material.depthWrite,
            overlayTypes:r.renderAreaGizmoGroup.children.map(o=>o.type)};
    }''')
    def pixels(data):
        return np.array(Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB'), dtype=float)
    assert np.abs(pixels(result['before']) - pixels(result['sliced'])).mean() < 0.05
    assert not result['gridDepthWrite']
    assert result['overlayTypes'] == ['LineSegments']
    page.screenshot(path='/tmp/vase-045-camera-wireframe.png')


def test_renderer_flat_toggle_and_idle_no_redraw_loop(page):
    page.keyboard.press('Meta+Shift+a')
    page.select_option('#renderer-atom-display-mode', '2d')
    assert page.evaluate('window.__ASE_APP__.renderer.atomDisplayMode()') == '2d'
    page.select_option('#renderer-atom-display-mode', '3d')
    page.click('#btn-preview-image')
    page.click('[data-camera-navigation="scene"]')
    page.wait_for_timeout(500)
    start=page.evaluate('window.__ASE_APP__.renderer.renderCount')
    page.wait_for_timeout(500)
    assert page.evaluate('window.__ASE_APP__.renderer.renderCount') - start < 3


def test_grid_stays_behind_atoms_and_display_edits_preserve_output_profile(page):
    images = page.evaluate('''() => {
        const a=window.__ASE_APP__,r=a.renderer;
        a.applyCameraSettings({position:[8,8,10],target:[2,0,0],up:[0,0,1],projection:'orthographic',ortho_scale:8});
        a.state.exportPreviewEnabled=true;a.captureRenderAreaCamera();
        const profile=structuredClone(a.currentImageExportProfile());
        a.applyDesignSettings({display:{atomDisplayMode:'3d'}});
        const after=structuredClone(a.currentImageExportProfile());
        const options={camera:a.currentCameraForExport(),includeAxes:false,includeCell:false};
        return {profile,after,without:r.exportPNG(600,600,{...options,includeGrid:false}),
            withGrid:r.exportPNG(600,600,{...options,includeGrid:true})};
    }''')
    assert images['profile'] == images['after']
    def pixels(data):
        return np.array(Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB'), dtype=float)
    plain, grid = pixels(images['without']), pixels(images['withGrid'])
    oxygen = (plain[:,:,0] > plain[:,:,1]*1.7) & (plain[:,:,0] > plain[:,:,2]*1.7) & (plain[:,:,0] > 80)
    assert oxygen.sum() > 500
    assert np.abs(plain[oxygen] - grid[oxygen]).mean() < 0.5
    assert np.abs(plain - grid).sum() > 1000  # guide actually rendered
    page.screenshot(path='/tmp/vase-045-grid-oblique.png')


def test_empty_color_target_does_not_block_trajectory_export(page):
    result = page.evaluate('''async () => {
        const a=window.__ASE_APP__;
        await a.aiApply({operation:{name:'set-atom-colorscale',enabled:true,field:'array::existence::scalar',
            scope:'selected',indices:[],rangeMode:'trajectory'}});
        a.applySelectionAction({references:[2],origin:'semantic'});
        a.flushVisualHistoryCommit();await a.flushCollaborationEvents();
        const revision=a.collaborationRevision;
        const gif=await a.aiExport({format:'video',container:'gif',width:256,height:144,fps:5,loop:false});
        await a.flushCollaborationEvents();
        return {gif,indices:a.state.display.atomColorScaleIndices,colors:a.renderer.atomColorScaleColors,
            selection:[...a.state.selected],revision,after:a.collaborationRevision};
    }''')
    assert result['indices'] == []
    assert not any(result['colors'] or [])
    assert result['selection'] == [2]
    assert result['after'] == result['revision']
    with Image.open(io.BytesIO(base64.b64decode(result['gif']['dataUrl'].split(',')[1]))) as gif:
        assert gif.size == (256, 144)
        assert gif.n_frames == 3


def test_grid_fades_at_grazing_angles_instead_of_dense_stripes(page):
    images = page.evaluate('''() => {
        const a=window.__ASE_APP__,r=a.renderer;
        a.applyCameraSettings({position:[2,10,.1],target:[2,0,0],up:[0,0,1],projection:'orthographic',ortho_scale:8});
        const options={camera:a.currentCameraForExport(),includeAxes:false,includeCell:false};
        return [false,true].map(includeGrid=>r.exportPNG(400,300,{...options,includeGrid}));
    }''')
    pixels = [np.array(Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB'), dtype=float)
              for data in images]
    assert np.abs(pixels[0] - pixels[1]).mean() < 0.05


def test_collaboration_flush_waits_for_an_already_publishing_event(page):
    result = page.evaluate('''async () => {
        const a=window.__ASE_APP__;
        a.flushVisualHistoryCommit();await a.flushCollaborationEvents();
        const publish=a.api.publishCollaborationEvent.bind(a.api);
        let release,started;
        const gate=new Promise(resolve=>release=resolve),began=new Promise(resolve=>started=resolve);
        a.api.publishCollaborationEvent=async event=>{started();await gate;return publish(event);};
        a.scheduleCollaborationEvent({source:'human',categories:['selection'],changedPaths:['selection.references']});
        const first=a.flushCollaborationEvents();await began;
        let returned=false;
        const second=a.flushCollaborationEvents().then(revision=>{returned=true;return revision;});
        await new Promise(resolve=>setTimeout(resolve,50));const premature=returned;
        release();const revisions=await Promise.all([first,second]);
        a.api.publishCollaborationEvent=publish;
        return {premature,revisions,current:a.collaborationRevision};
    }''')
    assert not result['premature']
    assert result['revisions'] == [result['current'], result['current']]
