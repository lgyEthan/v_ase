"""Canvas axis guides use their own depth extent in orthographic views."""
import base64
import io

import numpy as np
import pytest
from PIL import Image
from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view


CELL = [[11.60882634, 0, 0], [-1.93480439, 10.05353852, 0],
        [0, -2.2341196707915394, 10.115925053333333]]


@pytest.fixture
def page():
    editor = view(Atoms('C', positions=[[0, 0, 0]], cell=CELL), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 960})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            yield page
            browser.close()
    finally:
        editor.close()


def pixels(page):
    return np.array(Image.open(io.BytesIO(
        page.locator('#app-viewport canvas').first.screenshot())).convert('RGB'), dtype=int)


@pytest.mark.parametrize('mode', ['2d', '3d'])
@pytest.mark.parametrize('background', ['white', 'dark'])
def test_c_view_draws_z_shaft_behind_nominal_eye_and_preserves_saved_optics(page, mode, background):
    result = page.evaluate('''({mode,background})=>{
        const a=window.__ASE_APP__,r=a.renderer;
        a.applyDesignSettings({display:{showAxes:true,showGrid:false,showCell:false,
            atomDisplayMode:mode,viewportBackground:background}});
        a.setInspectorCollapsed(true);
        const direction=r.camera.position.clone().fromArray(a.state.atoms.cell[2]).normalize();
        a.applyCameraSettings({position:[30,0,0],
            target:[0,0,0],up:[0,0,1],projection:'orthographic',ortho_scale:40,near:1,far:1000});
        a.alignViewToCellAxis('c');
        // This positive-Z point is inside the displayed view, but behind the
        // nominal eye. The old atom-only clipping range removed its shaft.
        const point=direction.clone().set(0,0,60),camera=r.camera;
        const snapshot=a.currentCameraForExport();
        let drawing=null;
        const original=r.renderer.render.bind(r.renderer);
        r.renderer.render=(scene,c)=>{drawing={near:c.near,far:c.far};return original(scene,c);};
        r.renderNow();r.renderer.render=original;
        const rect=r.domElement.getBoundingClientRect(),projected=r.projectWorldToClient(point);
        return {snapshot,after:a.currentCameraForExport(),drawing,
            sample:{x:projected.x-rect.left,y:projected.y-rect.top},
            direction:a.cameraViewBasis().offset.normalize().toArray()};
    }''', dict(mode=mode, background=background))
    assert result['snapshot'] == result['after']
    assert result['drawing']['near'] < -60
    expected = np.array(CELL[2]); expected /= np.linalg.norm(expected)
    assert result['direction'] == pytest.approx(expected, abs=1e-8)
    shown = pixels(page)
    x, y = round(result['sample']['x']), round(result['sample']['y'])
    assert 5 < x < shown.shape[1] - 5 and 5 < y < shown.shape[0] - 5
    page.evaluate('''()=>{const r=window.__ASE_APP__.renderer;
        r.axesHelper.children[2].visible=false;r.renderNow();}''')
    hidden = pixels(page)
    assert np.abs(shown[y-2:y+3, x-2:x+3] - hidden[y-2:y+3, x-2:x+3]).sum() > 80
    # The blue line must really appear, not merely change internal clip values.
    patch = shown[y-2:y+3, x-2:x+3]
    # Y and Z project onto the same line in this cell view. Their translucent
    # colors may blend, but adding Z must contribute actual blue shaft pixels.
    blue_gain = patch[:, :, 2] - hidden[y-2:y+3, x-2:x+3, 2]
    assert ((patch[:, :, 2] > patch[:, :, 0] + 20) & (blue_gain > 15)).sum() >= 3


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
def test_axis_depth_fit_preserves_atom_occlusion_and_perspective_near_plane(page, projection):
    point = page.evaluate('''projection=>{
        const a=window.__ASE_APP__,r=a.renderer;
        a.setInspectorCollapsed(true);
        a.applyDesignSettings({display:{showAxes:true,showGrid:false,showCell:false}});
        a.applyCameraSettings({position:[30,0,0],target:[0,0,0],up:[0,0,1],
            projection,ortho_scale:40,near:1,far:1000});
        a.alignViewToCellAxis('c');
        let near=null;const original=r.renderer.render.bind(r.renderer);
        r.renderer.render=(scene,c)=>{near=c.near;return original(scene,c);};
        r.renderNow();r.renderer.render=original;
        const p=r.projectWorldToClient(r.atomMeshByIndex.get(0).position);
        const rect=r.domElement.getBoundingClientRect();
        return {x:p.x-rect.left,y:p.y-rect.top,near};
    }''', projection)
    if projection == 'perspective':
        assert point['near'] > 0
    shown = pixels(page)
    page.evaluate('()=>{const r=window.__ASE_APP__.renderer;r.axesHelper.visible=false;r.renderNow();}')
    hidden = pixels(page)
    x, y = round(point['x']), round(point['y'])
    assert np.abs(shown[y-2:y+3, x-2:x+3] - hidden[y-2:y+3, x-2:x+3]).max() <= 2


def test_hidden_axes_do_not_expand_depth_and_true_end_on_z_stays_a_point(page):
    result = page.evaluate('''()=>{
        const a=window.__ASE_APP__,r=a.renderer;
        a.applyDesignSettings({display:{showAxes:false,showGrid:false}});
        a.alignViewToAxis('Z');
        const before=a.currentCameraForExport();
        let drawing=null;const original=r.renderer.render.bind(r.renderer);
        r.renderer.render=(scene,c)=>{drawing={near:c.near,far:c.far};return original(scene,c);};
        r.renderNow();r.renderer.render=original;
        const z=r.axesHelper.children[2],positions=z.geometry.attributes.position;
        const endpoints=[0,1].map(i=>r.camera.position.clone().fromBufferAttribute(positions,i).project(r.camera));
        return {before,after:a.currentCameraForExport(),drawing,
            xy:endpoints.map(p=>[p.x,p.y])};
    }''')
    assert result['before'] == result['after']
    assert result['drawing']['near'] > -60
    assert result['xy'][0] == pytest.approx(result['xy'][1], abs=1e-8)


def test_exact_png_includes_unclipped_axes_and_respects_include_axes_false(page):
    images = page.evaluate('''()=>{
        const a=window.__ASE_APP__,r=a.renderer;
        a.applyDesignSettings({display:{showGrid:false,showAxes:true}});
        a.applyCameraSettings({position:[30,0,0],target:[0,0,0],
            up:[0,0,1],projection:'orthographic',ortho_scale:40,near:1,far:1000});
        a.alignViewToCellAxis('c');
        const options={includeGrid:false,antiAliasing:'off'},before=a.currentCameraForExport();
        return {with:r.exportPNG(640,480,{...options,includeAxes:true}),
            without:r.exportPNG(640,480,{...options,includeAxes:false}),before,
            after:a.currentCameraForExport(),visible:r.axesHelper.visible};
    }''')
    assert images['before'] == images['after']
    assert images['visible']
    def decode(value):
        return np.array(Image.open(io.BytesIO(base64.b64decode(value.split(',')[1]))).convert('RGB'), dtype=int)
    shown, hidden = decode(images['with']), decode(images['without'])
    assert shown.shape == (480, 640, 3)
    # Check the positive half well away from atoms and the origin, where the
    # previous implementation clipped Z even though that location is visible.
    assert (np.abs(shown[60:140] - hidden[60:140]).sum(axis=2) > 20).sum() > 60
