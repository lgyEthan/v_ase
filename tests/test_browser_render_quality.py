import numpy as np
from ase import Atoms
from playwright.sync_api import sync_playwright, expect
from v_ase.viewer import view, find_free_port
from v_ase.session import sessions
from v_ase.export import export_html_response


def test_numeric_quality_surface_cancel_capture_and_restore(tmp_path):
    positions=[]
    for x in range(6):
        for y in range(6):
            for z in range(3):
                p=np.array([x*2.7,y*2.7,z*2.7]);positions.extend([p,p+[.95,0,0],p+[-.24,.93,0]])
    atoms=Atoms('OH2'*108,positions=positions,cell=[20,20,15])
    atoms.new_array('mol',np.repeat(np.arange(1,109),3))
    port=find_free_port();editor=view(atoms,notebook=True,block=False,port=port,viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.state?.atoms?.positions?.length===324')
            quality=page.evaluate('async()=> (await window.v_aseAI.capabilities()).rendererQuality')
            assert quality['subdivisionRange']==[0,8] and quality['smoothingPasses']==[0,100]
            assert quality['isovalueRoute']=='Style → Isosurfaces'
            assert quality['inactiveSurfaceControls']=='disabled'
            page.evaluate("window.__ASE_APP__.openEditorRoute('export')")
            expect(page.locator('#renderer-isosurface-interpolation')).to_be_disabled()
            expect(page.locator('#renderer-isosurface-smoothing')).to_be_disabled()
            expect(page.locator('#renderer-water-smoothing')).to_be_disabled()
            page.get_by_role('button',name='Style → Isosurfaces',exact=True).click()
            expect(page.locator('#btn-volume-add')).to_be_visible()
            expect(page.locator('#volume-empty')).to_be_visible()
            assert page.locator('#volume-level').count()==1
            expect(page.locator('#workbench-tabs [data-workbench="style"]')).to_have_attribute('aria-selected','true')
            # Stored data visualization is under Style; physical calculations stay in Build.
            expect(page.locator('#workbench-tools [data-editor-route="forces"]')).to_be_visible()
            page.locator('#workbench-tools [data-editor-route="forces"]').click()
            expect(page.locator('#chk-force-vectors')).to_be_visible()
            expect(page.locator('#force-vector-scale')).to_be_visible()
            page.locator('#workbench-tabs [data-workbench="analyze"]').click()
            expect(page.locator('#workbench-tools [data-editor-route="forces"]')).to_be_hidden()
            page.evaluate("window.__ASE_APP__.openEditorRoute('export')")
            page.evaluate("()=>{const a=window.__ASE_APP__,p=a.currentImageExportProfile();p.options.sphereQuality='ultra';p.options.sphereQualityScale=1.5;a.setImageExportProfile(p);}")
            field=page.locator('#renderer-sphere-quality');field.fill('64');field.dispatch_event('change')
            page.wait_for_function('window.__ASE_APP__.state.display.atomSmoothness===64')
            result=page.evaluate('''()=>{const a=window.__ASE_APP__,r=a.renderer;r.renderNow();
                return {sphere:r.atomMeshes.children[0].geometry.parameters.widthSegments,
                    bond:r.bondCylinderGeometry.parameters.radialSegments,
                    drawn:Number(r.domElement.dataset.qualityDrawn),profile:a.currentImageExportProfile().options.sphereQuality,
                    actual:r.renderer.info.render.triangles,settings:a.designSettingsSnapshot()};}''')
            assert result['sphere']==result['bond']==64
            assert result['drawn']>0 and result['profile']=='viewport'
            assert result['actual']<324*64*80
            page.locator('#renderer-quality-revert').click()
            assert page.evaluate('window.__ASE_APP__.state.display.atomSmoothness')==0
            assert page.evaluate('window.__ASE_APP__.currentImageExportProfile().options.sphereQuality')=='ultra'
            assert page.evaluate('window.__ASE_APP__.currentImageExportProfile().options.sphereQualityScale')==1.5
            # Source geometry remains valid while an asynchronously refined mesh is prepared.
            page.evaluate("window.__ASE_APP__.state.display.waterSurface={enabled:true};window.__ASE_APP__.renderer.setDisplayOptions({waterSurface:{enabled:true}})")
            page.wait_for_function('window.__ASE_APP__.renderer.waterLayer.report.molecules===108')
            base=page.evaluate('window.__ASE_APP__.renderer.waterLayer.mesh.geometry.index.count')
            field=page.locator('#renderer-water-interpolation');field.fill('1');field.dispatch_event('change')
            # UI has a single source of truth, so keep water enabled in the app state too.
            page.evaluate('window.__ASE_APP__.state.display.waterSurface={enabled:true};window.__ASE_APP__.renderer.setDisplayOptions({waterSurface:{enabled:true}})')
            page.evaluate('window.__ASE_APP__.renderer.prepareSurfaceCapture()')
            assert page.evaluate('window.__ASE_APP__.renderer.waterLayer.mesh.geometry.index.count')==base*4
            expect(page.locator('#renderer-water-smoothing')).to_be_enabled()
            field=page.locator('#renderer-water-smoothing');field.fill('20');field.dispatch_event('change')
            page.evaluate('window.__ASE_APP__.renderer.prepareSurfaceCapture()')
            mesh=page.evaluate("()=>{const q=window.__ASE_APP__.renderer.waterLayer.mesh._surfaceQuality;return {key:q.key,moved:q.base.attributes.position.array.some((v,i)=>Math.abs(v-q.applied.attributes.position.array[i])>1e-5)};}")
            assert mesh=={'key':'1:20','moved':True}
            cancelled=page.evaluate('''()=>{const field=document.getElementById('renderer-water-interpolation');field.value='3';field.dispatchEvent(new Event('change',{bubbles:true}));const jobs=[...window.__ASE_APP__.renderer.surfaceQualityJobs.values()];document.getElementById('renderer-quality-cancel').click();return {jobs:jobs.length,requested:jobs.map(j=>j.level),aborted:jobs.every(j=>j.controller.signal.aborted)};}''')
            assert cancelled['jobs'] and cancelled['aborted'] and 3 in cancelled['requested']
            page.evaluate('window.__ASE_APP__.renderer.prepareSurfaceCapture()')
            assert page.evaluate('window.__ASE_APP__.state.display.waterInterpolation')==1
            assert page.evaluate('window.__ASE_APP__.renderer.waterLayer.mesh.geometry.index.count')==base*4
            # Faster frame requests must not replace a refined view with coarse geometry.
            frames=page.evaluate('''async()=>{const r=window.__ASE_APP__.renderer,old=r.waterLayer.mesh.geometry;
                const positions=r.atomsData.positions.map(p=>[...p]);positions[0][0]+=.15;r.updatePositions(positions);r.renderNow();
                const keptFirst=r.waterLayer.mesh.geometry===old;
                positions[0][0]+=.1;r.updatePositions(positions);r.renderNow();const keptLatest=r.waterLayer.mesh.geometry===old;
                await r.prepareSurfaceCapture();return {keptFirst,keptLatest,updated:r.waterLayer.mesh.geometry!==old,ratio:r.waterLayer.mesh.geometry.index.count/r.waterLayer.mesh._surfaceQuality.base.index.count};}''')
            assert frames=={'keptFirst':True,'keptLatest':True,'updated':True,'ratio':4}
            # Identical quality is awaited by asynchronous PNG/video entry points.
            page.evaluate('''async()=>{const r=window.__ASE_APP__.renderer;await r.exportPNGBlob(400,300,{antiAliasing:'off'});}''')
            page.evaluate('''()=>{const a=window.__ASE_APP__;a.state.display.showVolumetric=true;a.renderer.setDisplayOptions({showVolumetric:true});a.renderer.setVolumetricSurfaces([{vertices:[0,0,0,1,0,0,0,1,0,0,0,1],faces:[0,2,1,0,1,3,0,3,2,1,2,3]}]);}''')
            field=page.locator('#renderer-isosurface-interpolation');field.fill('2');field.dispatch_event('change')
            page.evaluate('window.__ASE_APP__.renderer.prepareSurfaceCapture()')
            assert page.evaluate('window.__ASE_APP__.renderer.volumetricSurfaces[0].geometry.index.count')==12*16
            expect(page.locator('#renderer-isosurface-smoothing')).to_be_enabled()
            page.evaluate("window.__ASE_APP__.renderer.setDisplayOptions({showVolumetric:false})")
            expect(page.locator('#renderer-isosurface-smoothing')).to_be_disabled()
            page.evaluate("window.__ASE_APP__.renderer.setDisplayOptions({showVolumetric:true})")
            expect(page.locator('#renderer-isosurface-smoothing')).to_be_enabled()
            # An over-budget mesh rejects capture, but removing it clears only its own failure.
            rejected=page.evaluate('''async()=>{const r=window.__ASE_APP__.renderer;
                r.setVolumetricSurfaces([{vertices:[0,0,0,1,0,0,0,1,0],faces:Array.from({length:500001},()=>[0,1,2]).flat()}]);
                let message='';try{await r.prepareSurfaceCapture();}catch(e){message=e.message;}
                r.clearVolumetricSurfaces();await r.prepareSurfaceCapture();
                return {message,failed:r.surfaceQualityFailed};}''')
            assert '8,000,000' in rejected['message'] and not rejected['failed']
            page.evaluate('''window.__ASE_APP__.renderer.setVolumetricSurfaces([{vertices:[0,0,0,1,0,0,0,1,0,0,0,1],faces:[0,2,1,0,1,3,0,3,2,1,2,3]}])''')
            page.locator('#renderer-quality-safe').click()
            assert page.evaluate('window.__ASE_APP__.renderer.volumetricSurfaces[0].geometry.index.count')==12
            assert page.evaluate('window.__ASE_APP__.renderer.bondCylinderGeometry.parameters.radialSegments')==12
            page.evaluate('window.v_aseAI.apply({display:{atomSmoothness:64,waterInterpolation:1,waterMeshSmoothing:20}})')
            settings=page.evaluate('window.__ASE_APP__.designSettingsSnapshot()')
            html=export_html_response(sessions[editor.session_id],{'settings':settings,'width':400,'height':300}).body
            path=tmp_path/'quality.html';path.write_bytes(html)
            offline=browser.new_page();offline.on('pageerror',lambda e:errors.append(str(e)))
            external=[];offline.on('request',lambda req: external.append(req.url) if req.url.startswith(('http:','https:')) else None)
            offline.goto(path.as_uri())
            expect(offline.locator('canvas')).to_have_attribute('data-surface-quality-busy','false')
            assert offline.locator('canvas').get_attribute('data-quality-drawn') is not None
            assert int(offline.locator('canvas').get_attribute('data-water-rendered-triangles'))==base*4//3
            assert not external
            assert not errors
            browser.close()
    finally:
        sessions.pop(editor.session_id,None)


def test_extreme_closeup_quality_is_rejected_before_gpu_submission():
    atoms=Atoms('Ar'*1800,positions=np.zeros((1800,3)))
    port=find_free_port();editor=view(atoms,notebook=True,block=False,port=port,viz_only=True,close_on_disconnect=False,
        initial_design_settings={'display':{'showBonds':False}})
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page()
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.state?.atoms?.positions?.length===1800')
            result=page.evaluate('''()=>{const a=window.__ASE_APP__,r=a.renderer,positions=JSON.stringify(r.atomsData.positions);
                r.setProjectionMode('orthographic');r.setPixelsPerAngstrom(2500,{requestRender:false});
                a.state.display.atomSmoothness=128;r.setDisplayOptions(a.state.display);r.renderNow();
                return {app:a.state.display.atomSmoothness,renderer:r.displayOptions.atomSmoothness,
                    unchanged:positions===JSON.stringify(r.atomsData.positions),triangles:r.renderer.info.render.triangles,warning:r.domElement.dataset.qualityWarning};}''')
            assert result['app']==result['renderer']==12
            assert result['unchanged'] and result['triangles']<1000000
            assert '20 million' in result['warning']
            browser.close()
    finally:
        sessions.pop(editor.session_id,None)
