"""Inspect actual flat bond pixels, not just shader source or material flags."""
import base64
from io import BytesIO
import numpy as np
import pytest
from PIL import Image
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port

@pytest.mark.parametrize('scale', [1,2])
def test_flat_bond_has_solid_fill_crisp_sides_and_no_midpoint_cap(tmp_path, scale):
    atoms = Atoms('HO', positions=[[-2,0,0],[2,0,0]])
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width':1000,'height':750}, device_scale_factor=scale)
            page.goto(editor.url); page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            result = page.evaluate('''()=>{
                const a=window.__ASE_APP__,r=a.renderer;
                Object.assign(a.state.display,{atomDisplayMode:'2d',viewportBackground:'white',showGrid:false,showAxes:false,showCell:false,
                    bondMode:'manual',manualBondPairs:[[0,1]],bondThickness:.5,showBonds:true,bondColorMode:'element',bondMaterial:'metal'});
                r.customColors={0:'#8844cc',1:'#cc8888'};
                r.setDisplayOptions(a.state.display);a.setAIAxisView('+Z');
                const c=r.camera;c.position.set(0,0,15);r.controls.target.set(0,0,0);c.lookAt(0,0,0);c.updateMatrixWorld(true);
                return {png:r.exportPNG(1000,750,{framing:'structure',backgroundColor:'#ffffff',includeCell:false,includeAxes:false,includeGrid:false}),
                    materials:r.bondGroup.children.map(m=>m.material.type)};
            }''')
            assert set(result['materials']) == {'MeshBasicMaterial'}
            image = Image.open(BytesIO(base64.b64decode(result['png'].split(',')[1]))).convert('RGB')
            image.save(tmp_path/f'flat-bond-{scale}.png')
            pixels = np.array(image)
            # At the bond center, both color halves must remain solid with no
            # black joint. Its full-width exterior has at most ~1px transition.
            center = pixels[375, 450:550]
            assert np.min(center.max(axis=1)) > 100, center.tolist()
            vertical = pixels[:,450]
            colored = (vertical.max(axis=1)-vertical.min(axis=1) > 25)
            ys = np.where(colored)[0]
            assert len(ys) > 8
            low, high = ys.min(),ys.max()
            core = vertical[low+2:high-1]
            assert np.max(np.ptp(core.astype(int),axis=0)) <= 2
            # Bound the antialias transition width at both interior boundaries.
            reference = core[len(core)//2]
            errors = np.max(np.abs(vertical[low:high+1].astype(int)-reference.astype(int)),axis=1)
            assert np.count_nonzero(errors > 3) <= 4
            browser.close()
    finally: editor.close()
