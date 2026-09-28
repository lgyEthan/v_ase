"""Actual shared renderer checks: UI, frame/capture parity and offline HTML."""
import base64
import io
import re
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from ase import Atoms
from v_ase.session import sessions
from v_ase.viewer import find_free_port, view
from v_ase.export import export_html_response


def water_frames():
    a=Atoms('OH2OH2Na',positions=[[0,0,0],[.957,0,0],[-.24,.93,0],
                                [2.8,0,0],[3.757,0,0],[2.56,.93,0],[1.4,2,1]],cell=[10,10,10])
    b=a.copy();b.positions[3:6,1]+=.9
    return [a,b]


def test_water_ui_movie_capture_settings_and_offline_html(tmp_path):
    frames=water_frames();port=find_free_port()
    editor=view(frames,notebook=True,block=False,port=port,viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1200,'height':850},device_scale_factor=2)
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.state?.atoms?.positions?.length===7')
            page.evaluate("window.__ASE_APP__.openEditorRoute('water')")
            assert page.locator('[data-panel=water] input[type=number]').evaluate_all('(fields)=>fields.every(f=>f.checkValidity())')
            page.locator('#water-enabled').check()
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.report.molecules===2')
            assert page.evaluate('window.__ASE_APP__.renderer.atomMeshByIndex.get(6).visible')
            assert not page.evaluate('window.__ASE_APP__.renderer.atomMeshByIndex.get(0).visible')
            # A live appearance change is one reversible visual edit.
            page.evaluate('window.__ASE_APP__.performUndo()')
            page.wait_for_function('!window.__ASE_APP__.renderer.waterLayer.group.visible')
            assert not page.locator('#water-enabled').is_checked()
            page.evaluate('window.__ASE_APP__.performRedo()')
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.report.molecules===2')
            # Capture oxygen indices; future selection must not change the scope.
            page.locator('#water-source').select_option('selected')
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.report.molecules===0')
            page.evaluate('window.__ASE_APP__.applySelectionAction({references:[0],origin:"semantic"})')
            page.locator('#water-selected').click()
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.report.molecules===1')
            page.evaluate('window.__ASE_APP__.applySelectionAction({references:[3],origin:"semantic"})')
            assert page.evaluate('window.__ASE_APP__.state.display.waterSurface.indices') == [0]
            assert page.evaluate('window.__ASE_APP__.renderer.waterLayer.hidden.has(3)') is False
            page.locator('#water-source').select_option('auto')
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.report.molecules===2')
            # Toggling the layer must restore exact scientific source + glyphs.
            page.locator('#water-enabled').uncheck()
            page.wait_for_function('!window.__ASE_APP__.renderer.waterLayer.group.visible')
            assert page.evaluate('window.__ASE_APP__.renderer.atomMeshByIndex.get(0).visible')
            page.locator('#water-enabled').check()
            page.locator('#water-lighting').uncheck()
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.mesh.material.isMeshBasicMaterial')
            page.locator('#water-color').fill('#317cbd')
            page.locator('#water-color').dispatch_event('input')
            page.wait_for_function("window.__ASE_APP__.renderer.waterLayer.mesh.material.color.getHexString()==='317cbd'")
            capability=page.evaluate('window.v_aseAI.capabilities()')
            assert capability['waterSurface']['control']=='display.waterSurface'
            schema=page.request.get(capability['schemaUrl']).json()
            assert 'waterSurface' in str(schema)
            settings=page.evaluate('window.__ASE_APP__.designSettingsSnapshot()')
            assert settings['display']['waterSurface']['lighting'] is False
            page.evaluate('(s)=>window.__ASE_APP__.applyDesignSettings(s)',settings)
            assert page.evaluate('window.__ASE_APP__.state.display.waterSurface.enabled')
            result=page.evaluate("""async() => {
                const a=window.__ASE_APP__,r=a.renderer;
                const original=JSON.stringify(a.state.atoms.positions);
                const capture=r.beginExportCapture(640,360,{antiAliasing:'off'});
                const shots=[],hashes=[];
                try {
                    for(const delta of [0,.9]) {
                        const positions=a.state.atoms.positions.map(p=>[...p]);
                        for(const i of [3,4,5])positions[i][1]+=delta;
                        r.updatePositions(positions);r.renderExportCaptureFrame(capture);
                        shots.push(r.domElement.toDataURL('image/png'));
                        hashes.push(Array.from(r.waterLayer.mesh.geometry.attributes.position.array).reduce((s,x)=>s+x,0));
                    }
                }finally{r.endExportCapture(capture);}
                return {shots,hashes,source:original,actual:JSON.stringify(a.state.atoms.positions)};
            }""")
            assert result['hashes'][0]!=result['hashes'][1]
            # Renderer-owned data may be the current view copy; server originals stay untouched.
            for i,data in enumerate(result['shots']):
                pixels=base64.b64decode(data.split(',')[1]);image=Image.open(io.BytesIO(pixels))
                assert image.size==(640,360)
                image.save(tmp_path/f'water-frame-{i}.png')
                assert np.asarray(image.convert('RGB')).std()>5
            assert result['shots'][0]!=result['shots'][1]
            np.testing.assert_array_equal(sessions[editor.session_id].original_atoms.positions,frames[0].positions)
            html=export_html_response(sessions[editor.session_id],{'settings':settings,'embed_project':True,'width':640,'height':360}).body
            path=tmp_path/'water.html';path.write_bytes(html)
            offline=browser.new_page();offline_errors=[]
            offline.on('pageerror',lambda error:offline_errors.append(str(error)))
            offline.goto(path.as_uri())
            expect(offline.locator('canvas')).to_have_attribute('data-water-triangles', re.compile(r'[1-9][0-9]*'))
            assert offline.locator('canvas').get_attribute('data-water-molecules')=='2'
            assert not offline_errors
            assert not errors
            browser.close()
    finally:
        sessions.pop(editor.session_id,None)
