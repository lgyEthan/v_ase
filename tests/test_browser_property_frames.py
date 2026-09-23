"""Property mappings, crop guides and deterministic source-range exports."""
import base64
import io

import numpy as np
import pytest
from ase import Atoms
from PIL import Image
from playwright.sync_api import sync_playwright

from tests.ui_navigation import open_editor_route
from v_ase.viewer import find_free_port, view


@pytest.fixture
def property_page():
    frames = []
    for i in range(5):
        atoms = Atoms('H2', positions=[[i, 0, 0], [i + 2, 0, 0]])
        atoms.new_array('fraction', np.array([i / 4, 1 - i / 4]))
        frames.append(atoms)
    editor = view(frames, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=2)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            page.evaluate('''async () => {
                const a=window.__ASE_APP__;
                a.state.display.atomRadiusMapping={enabled:true,field:'array::fraction::scalar',
                  valueTransform:'identity',rangeMode:'manual',min:0,max:1,
                  minMultiplier:0,maxMultiplier:1,exponent:1,scope:'all',indices:[]};
                Object.assign(a.state.display,{atomColorScaleEnabled:true,
                  atomColorScaleField:'array::fraction::scalar',atomColorScaleRangeMode:'manual',
                  atomColorScaleMin:0,atomColorScaleMax:1,atomColorScaleScope:'all'});
                await a.updateAtomColorScale(); await a.updateAtomRadiusMapping();
            }''')
            yield page
            browser.close()
    finally:
        editor.close()


def test_color_targets_are_frozen_until_explicit_reapply(property_page):
    page = property_page
    open_editor_route(page, 'appearance')
    page.evaluate('window.__ASE_APP__.state.selected=new Set([0])')
    page.select_option('#atom-colorscale-scope', 'selected')
    page.wait_for_function('window.__ASE_APP__.renderer.atomColorScaleColors?.[1] === null')
    before = page.evaluate('window.__ASE_APP__.renderer.atomColorScaleColors')
    page.evaluate('''() => {const a=window.__ASE_APP__;a.state.selected=new Set([1]);a.updateSelectionVisuals();}''')
    page.wait_for_timeout(100)
    assert page.evaluate('window.__ASE_APP__.renderer.atomColorScaleColors') == before
    assert page.evaluate('window.__ASE_APP__.designSettingsSnapshot().display.atomColorScaleIndices') == [0]
    page.click('#btn-atom-colorscale-use-selection')
    page.wait_for_function('window.__ASE_APP__.renderer.atomColorScaleColors?.[0] === null')
    assert page.evaluate('window.__ASE_APP__.state.display.atomColorScaleIndices') == [1]
    # One row regardless of panel width, with deliberate horizontal overflow.
    geometry = page.locator('#appearance-table').evaluate('''el => ({width:el.clientWidth,scroll:el.scrollWidth,
        heights:[...el.querySelectorAll('#appearance-table-body .appearance-row')].map(x=>x.getBoundingClientRect().height)})''')
    assert geometry['scroll'] > geometry['width']
    assert all(height <= 42 for height in geometry['heights'])


def test_frame_commit_never_renders_unmapped_radius_during_delayed_scalar_fetch(property_page):
    result = property_page.evaluate('''async () => {
        const a=window.__ASE_APP__, r=a.renderer;
        a.state.trajectoryBinaryCache=null; a.loadTrajectoryCache=async()=>null;
        delete a.state.atoms.trajectory_positions;
        const fetch=a.api.fetchAtomScalarValues.bind(a.api);
        a.api.fetchAtomScalarValues=async(...args)=>{await new Promise(ok=>setTimeout(ok,40));return fetch(...args)};
        const seen=[], original=r.renderFrame.bind(r);
        r.renderFrame=()=>{const count=r.renderCount;original();if(r.renderCount!==count)seen.push({
            frame:a.state.atoms.metadata.current_frame,factors:[...(r.atomRadiusFactors||[])],
            colorFrame:a.atomColorScaleRuntime.renderedFrame});};
        const errors=[];const toast=a.toast.bind(a);a.toast=(message,...rest)=>{errors.push(message);toast(message,...rest)};
        a.queueFrameLoad(1);a.queueFrameLoad(2);a.queueFrameLoad(3);a.queueFrameLoad(4);
        while(a.frameLoadInFlight) await new Promise(ok=>setTimeout(ok,10));
        await new Promise(ok=>requestAnimationFrame(ok));
        r.renderNow();
        return {seen,errors,frame:a.state.atoms.metadata.current_frame};
    }''')
    assert result['frame'] == 4
    assert not any('failed' in message.lower() for message in result['errors'])
    assert result['seen']
    for item in result['seen']:
        assert item['factors'] == pytest.approx([item['frame'] / 4, 1 - item['frame'] / 4])
        assert item['colorFrame'] == item['frame']


def test_retina_gif_source_range_interpolates_colors_and_radius(property_page):
    data = property_page.evaluate('''async () => {
        const a=window.__ASE_APP__, samples=[];
        const original=a.captureCurrentVideoFrame.bind(a);
        a.captureCurrentVideoFrame=async(...args)=>{
            a.renderer.updateRenderQuality(); // Rebuild/quality change during capture must not resize output.
            samples.push({radius:[...a.renderer.atomRadiusFactors],colors:[...a.renderer.atomColorScaleColors]});
            return original(...args);
        };
        const result=await a.aiExport({format:'video',container:'gif',width:320,height:240,
            fps:10,startFrame:1,endFrame:3,loop:false,interpolationMultiplier:2});
        return {result,samples,frame:a.state.atoms.metadata.current_frame};
    }''')
    assert data['frame'] == 0
    assert data['result']['sourceFrameCount'] == 3
    assert data['result']['frameCount'] == 5
    assert data['result']['mimeType'] == 'image/gif'
    assert [s['radius'][0] for s in data['samples']] == pytest.approx([.25, .375, .5, .625, .75])
    assert len({tuple(s['colors']) for s in data['samples']}) == 5
    with Image.open(io.BytesIO(base64.b64decode(data['result']['dataUrl'].split(',')[1]))) as image:
        assert image.size == (320, 240)
        assert image.n_frames == 5
        assert 'loop' not in image.info
        assert image.info['duration'] == 100


def test_output_guide_does_not_render_or_pick_a_second_view(property_page):
    result = property_page.evaluate('''() => {
        const a=window.__ASE_APP__,r=a.renderer;
        a.state.exportPreviewEnabled=true;a.syncImageExportPreview();
        let renders=0;const original=r.renderer.render.bind(r.renderer);
        r.renderer.render=(...args)=>{renders++;return original(...args)};
        r.renderNow();
        const rect=r.lastExportPreview.frameRect;
        const box=r.domElement.getBoundingClientRect();
        const context=r.interactionProjectionContext(box.left+box.width/2,box.top+box.height/2);
        const before={...rect};document.body.classList.toggle('inspector-collapsed');
        r.renderNow();
        return {renders,context:context.kind,guide:r.lastExportPreview.guideOnly,before,after:r.lastExportPreview.frameRect};
    }''')
    assert result['renders'] == 2
    assert result['context'] == 'viewport'
    assert result['guide'] is True
    assert result['before'] == result['after']


@pytest.mark.parametrize('late_old_cache', [False, True])
def test_physical_edit_survives_cached_frame_switch_video_and_project(property_page, tmp_path, late_old_cache):
    """A cache completed before or after a commit must not restore old coordinates."""
    result = property_page.evaluate('''async late => {
        const a=window.__ASE_APP__;
        await a.aiApply({mode:'edit',frame:3});
        delete a.state.atoms.trajectory_positions;
        a.state.atoms.metadata.trajectory_positions_binary=true;
        await a.loadTrajectoryCache();
        let release, oldTask;
        if(late){
            const stale=a.state.trajectoryBinaryCache;
            const original=a.api.fetchTrajectoryPositions.bind(a.api);
            a.state.trajectoryBinaryCache=null;
            a.api.fetchTrajectoryPositions=()=>{
                a.api.fetchTrajectoryPositions=original;
                return new Promise(resolve=>{release=()=>resolve(stale)});
            };
            oldTask=a.loadTrajectoryCache({background:true});
        }
        await a.aiApply({operation:{name:'move-selection',indices:[0],vector:[0.25,0,0]}});
        const edited=a.state.atoms.positions[0][0];
        if(late){release();await oldTask;}
        await a.loadFrame(4);await a.loadFrame(3);
        const roundtrip=a.state.atoms.positions[0][0];
        await a.aiExport({format:'video',container:'gif',width:128,height:96,fps:5,
          startFrame:2,endFrame:4,loop:false});
        return {edited,roundtrip,afterVideo:a.state.atoms.positions[0][0],
          project:await a.aiExport({format:'project'})};
    }''', late_old_cache)
    assert result['edited'] == pytest.approx(3.25)
    assert result['roundtrip'] == pytest.approx(3.25)
    assert result['afterVideo'] == pytest.approx(3.25)
    import zipfile
    from ase.io import read
    data = base64.b64decode(result['project']['dataUrl'].split(',')[1])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        trajectory = tmp_path / 'structure.traj'
        trajectory.write_bytes(archive.read('structure.traj'))
    frames = read(trajectory, index=':')
    assert frames[3].positions[0, 0] == pytest.approx(3.25)
    assert frames[4].positions[0, 0] == pytest.approx(4)


def test_retina_1080p_video_keeps_exact_png_size_through_frame_rebuild(property_page, tmp_path):
    result = property_page.evaluate('''async () => {
        const a=window.__ASE_APP__, sizes=[];
        // Force server-loaded frames to exercise rebuildAtoms and quality changes.
        delete a.state.atoms.trajectory_positions;
        a.state.trajectoryBinaryCache=null; a.loadTrajectoryCache=async()=>null;
        const original=a.api.appendVideoFrame.bind(a.api);
        a.api.appendVideoFrame=async(id,index,png)=>{
            const image=await createImageBitmap(png);sizes.push([image.width,image.height]);image.close();
            return original(id,index,png);
        };
        return {video:await a.aiExport({format:'video',container:'mov',width:1920,height:1080,
            fps:5,startFrame:1,endFrame:2}),sizes};
    }''')
    assert result['sizes'] == [[1920, 1080], [1920, 1080]]
    movie = tmp_path / 'retina.mov'
    movie.write_bytes(base64.b64decode(result['video']['dataUrl'].split(',')[1]))
    import imageio_ffmpeg
    decoded = imageio_ffmpeg.read_frames(str(movie), pix_fmt='rgb24')
    metadata = next(decoded)
    assert metadata['size'] == (1920, 1080)
    assert metadata['fps'] == pytest.approx(5)
    assert sum(1 for _ in decoded) == 2


def test_reopened_project_restores_video_range_and_loop_instead_of_previous_draft(property_page):
    property_page.evaluate('''async () => {
        const a=window.__ASE_APP__;
        Object.assign(a.state.display,{videoFormat:'gif',videoFps:5,
            videoStartFrame:1,videoEndFrame:3,videoLoop:false});
        const saved=await a.aiExport({format:'project'});
        a.videoExportDraft={format:'mov',fps:24,interpolationMultiplier:1,
            interpolationMic:true,startFrame:0,endFrame:4,loop:true};
        const bytes=Uint8Array.from(atob(saved.dataUrl.split(',')[1]),c=>c.charCodeAt(0));
        window.__reopenRangeProject=a.loadStructureFile(new File([bytes],'range.vase'));
    }''')
    property_page.click('#modal-discard-document')
    result = property_page.evaluate('''async () => {
        await window.__reopenRangeProject;
        const a=window.__ASE_APP__;
        a.syncRendererFormatProperties();
        return ['renderer-video-format','renderer-video-fps','renderer-video-start',
            'renderer-video-end','renderer-video-loop'].map(id=>document.getElementById(id).value);
    }''')
    assert result == ['gif', '5', '2', '4', 'once']
