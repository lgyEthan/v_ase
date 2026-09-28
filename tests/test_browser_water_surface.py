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
                                [.5,.5,0],[1.457,.5,0],[.26,1.43,0],[1.4,2,1]],cell=[10,10,10])
    a.new_array('mol',np.array([1,1,1,2,2,2,0]))
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
                        r.updatePositions(positions);await r.prepareSurfaceCapture();r.renderExportCaptureFrame(capture);
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


def test_water_removes_gpu_instances_and_tracks_signed_replicas():
    positions=[]
    for x in range(5):
        for y in range(5):
            for z in range(4):
                p=np.array([x*2.8,y*2.8,z*2.8]);positions.extend([p,p+[.957,0,0],p+[-.24,.93,0]])
    atoms=Atoms('OH2'*100+'Na',positions=[*positions,[7,7,13]],cell=[15,15,15],pbc=True)
    atoms.new_array('mol',np.array([i for i in range(1,101) for _ in range(3)]+[0]))
    editor=view(atoms,notebook=True,block=False,port=find_free_port(),viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page()
            page.goto(editor.url);page.wait_for_function('window.__ASE_APP__?.renderer?.atomInstanceRefs?.size===301')
            result=page.evaluate('''() => {
                const a=window.__ASE_APP__,r=a.renderer;
                const draw=()=>r.renderScientificScene(r.camera);
                const counts=()=>({atoms:[...r.atomInstanceMeshes].reduce((s,m)=>s+m.count,0),
                    replicas:r.supercellGroup.children.filter(m=>m.userData.supercellInstanced).reduce((s,m)=>s+m.count,0),
                    bonds:r.bondGroup.children.filter(m=>m.isInstancedMesh).reduce((s,m)=>s+m.count,0)});
                const cfg={enabled:true};r.setDisplayOptions({waterSurface:cfg});draw();
                const first=counts(),builds=r.waterLayer.builds,initial=r.waterLayer.mesh.geometry.attributes.position.array.slice();
                r.camera.position.x+=1;draw();draw();
                const cameraBuilds=r.waterLayer.builds;
                r.setDisplayOptions({waterSurface:{...cfg,color:'#aaffcc'}});draw();
                const colorBuilds=r.waterLayer.builds;
                r.setDisplayOptions({waterSurface:{...cfg,smoothing:.5,spacing:1.5}});draw();
                const failed={...r.waterLayer.report},restoredAfterError=counts();
                r.setDisplayOptions({waterSurface:cfg});draw();
                const recovered={...r.waterLayer.report};
                r.setDisplayOptions({supercell:[3,1,1]});draw();
                const repeated=counts(),report={...r.waterLayer.report};
                const x=Array.from(r.waterLayer.mesh.geometry.attributes.position.array).filter((_,i)=>i%3===0);
                const mesh=r.supercellGroup.children.find(m=>m.userData.supercellInstanced&&m.count);
                const picked=r.supercellAtomReference(mesh,0);
                const moved=r.currentPositions();for(const p of moved)p[2]+=.2;r.updatePositions(moved);draw();
                const afterMove=counts();
                const flat=moved.flat().map((v,i)=>i%3===2?v+.2:v);
                r.updatePositionsFlat(flat);draw();const afterFlat=counts();
                // Hide only the base O: two visible periodic instances must survive.
                r.setDisplayOptions({hiddenAtomReferences:['atom:0']});draw();
                const hiddenBase={...r.waterLayer.report};
                r.setDisplayOptions({waterSurface:{enabled:false},hiddenAtomReferences:[]});draw();
                return {first,builds,cameraBuilds,colorBuilds,failed,restoredAfterError,recovered,repeated,report,min:Math.min(...x),max:Math.max(...x),picked,afterMove,afterFlat,hiddenBase,restored:counts()};
            }''')
            assert result['first']=={'atoms':1,'replicas':0,'bonds':0}
            assert result['cameraBuilds']==result['builds']==result['colorBuilds']
            assert 'too large' in result['failed']['error']
            assert result['restoredAfterError']['atoms']==301
            assert result['recovered']['molecules']==100 and result['recovered']['triangles']>0
            assert result['repeated']['atoms']==1 and result['repeated']['replicas']==2
            assert result['report']['displayedMolecules']==300
            assert result['min'] < -15 and result['max'] > 26
            assert result['picked']['index']==300
            assert result['afterMove']==result['afterFlat']==result['repeated']
            assert result['hiddenBase']['displayedMolecules']==299
            assert result['restored']['atoms']==301 and result['restored']['replicas']==602
            browser.close()
    finally:
        editor.close()


def test_streaming_molecule_topology_is_current_when_enabling_mid_trajectory():
    frames=water_frames()
    # Same element/label/position layout, different authoritative topology.
    frames[1].arrays['mol'][:6]=1
    class Source:
        natoms=7
        frame_count=2
        cells=np.array([a.cell.array for a in frames])
        pbc=np.array([a.pbc for a in frames])
        def read_atoms(self, index): return frames[index].copy()
        def read_positions(self, index): return frames[index].positions.copy()
    editor=view(frames[0],trajectory_source=Source(),notebook=True,block=False,
                port=find_free_port(),viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page()
            page.goto(editor.url);page.wait_for_function('window.__ASE_APP__?.state?.atoms?.positions?.length===7')
            result=page.evaluate('''async() => {
                const a=window.__ASE_APP__,r=a.renderer;
                await a.loadFrame(1); // Water is off while scrubbing.
                const ids=[...a.state.atoms.molecule_ids];
                r.setDisplayOptions({waterSurface:{enabled:true}});r.renderScientificScene(r.camera);
                const nonwater={...r.waterLayer.report};
                await a.loadFrame(0);r.renderScientificScene(r.camera);
                const water={...r.waterLayer.report};
                return {ids,nonwater,water,binary:a.state.atoms.metadata.trajectory_positions_binary};
            }''')
            assert result['ids']==[1,1,1,1,1,1,0]
            assert result['nonwater']['molecules']==0
            assert result['water']['molecules']==2
            assert result['binary'] is False
            browser.close()
    finally:
        editor.close()


def test_water_new_scene_defaults_and_explicit_legacy_finish_survive_restore():
    editor=view(water_frames(),notebook=True,block=False,port=find_free_port(),
                close_on_disconnect=False,initial_design_settings={'display':{'waterSurface':{'enabled':True}}})
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page()
            page.goto(editor.url);page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            page.evaluate('window.__ASE_APP__.renderer.prepareSurfaceCapture()')
            actual=page.evaluate("()=>{const a=window.__ASE_APP__;return {water:a.state.display.waterSurface,key:a.renderer.waterLayer.mesh._surfaceQuality.key};}")
            assert actual['water']['smoothing']==2 and actual['water']['level']==.63
            assert actual['key']=='1:20'
            # Saved explicit settings, particularly zero, must not inherit defaults.
            page.evaluate("()=>{const a=window.__ASE_APP__,s=a.designSettingsSnapshot();s.display.waterSurface.smoothing=1.45;s.display.waterSurface.level=.65;s.display.waterInterpolation=0;s.display.waterMeshSmoothing=0;a.applyDesignSettings(s);}")
            page.evaluate('window.__ASE_APP__.renderer.prepareSurfaceCapture()')
            actual=page.evaluate("()=>{const a=window.__ASE_APP__;return {water:a.state.display.waterSurface,key:a.renderer.waterLayer.mesh._surfaceQuality.key};}")
            assert actual['water']['smoothing']==1.45 and actual['water']['level']==.65
            assert actual['key']=='0:0'
            browser.close()
    finally:
        editor.close()
