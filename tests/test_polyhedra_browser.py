"""Live GUI/native/standalone checks for polyhedra, including style-only edits."""
import io
import base64
import re
import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from PIL import Image
from playwright.sync_api import sync_playwright, expect

from v_ase.ai_tools import FunctionTools
from v_ase.viewer import find_free_port, view
from v_ase.session import sessions
from v_ase.export import export_html_response


def material():
    return Atoms('SrTiO3',scaled_positions=[[0,0,0],[.5,.5,.5],[.5,.5,0],[.5,0,.5],[0,.5,.5]],cell=[3.905]*3,pbc=True)


def open_panel(page):
    if page.locator('body').evaluate("e=>e.classList.contains('inspector-collapsed')"):
        page.click('#btn-inspector-collapse')
    page.click('[data-inspector-group="structure"]')
    page.select_option('#structure-section-select','polyhedra')
    page.locator('#poly-add').scroll_into_view_if_needed()


def test_gui_colors_opacity_native_snapshot_and_exact_render(tmp_path):
    editor=view(material(),notebook=True,block=False,port=find_free_port(),viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1400,'height':1000});errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url) if '/api/analysis/polyhedra/' in r.url else None)
            page.goto(f'http://127.0.0.1:{editor.port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__V_ASE_APP__?.state?.atoms?.positions?.length===5')
            open_panel(page);page.click('#poly-add');page.fill('#poly-centers','Ti');page.fill('#poly-max','2.2');page.click('#poly-apply')
            page.wait_for_function('window.__V_ASE_APP__.renderer.polyhedraRendered?.length===1')
            before=page.evaluate('window.__V_ASE_APP__.state.atoms.positions')
            baseline_requests=len(requests)
            page.uncheck('#poly-inherit')
            page.locator('#poly-color').evaluate("e=>{e.value='#cc3355';e.dispatchEvent(new Event('change',{bubbles:true}));}")
            page.fill('#poly-opacity','0.65');page.locator('#poly-opacity').blur()
            page.wait_for_function("window.__V_ASE_APP__.renderer.polyhedraRendered[0].appearance.color==='#cc3355' && window.__V_ASE_APP__.renderer.polyhedraRendered[0].appearance.opacity===.65")
            assert len(requests)==baseline_requests,'Styling must not query geometry again.'
            np.testing.assert_array_equal(page.evaluate('window.__V_ASE_APP__.state.atoms.positions'),before)
            page.select_option('#poly-atom-mode','none')
            page.wait_for_function("window.__V_ASE_APP__.state.display.polyhedraAtomMode==='none'")
            assert not page.evaluate('window.__V_ASE_APP__.renderer.bondGroup.visible')
            assert page.evaluate('[...window.__V_ASE_APP__.renderer.atomMeshByIndex.values()].every(m=>!m.visible)')
            page.evaluate('async()=>{const a=window.__V_ASE_APP__;a.flushVisualHistoryCommit();await a.flushCollaborationEvents();}')
            tools=FunctionTools(f'http://127.0.0.1:{editor.port}/api/ai/command/session/{editor.session_id}',artifact_dir=tmp_path)
            snapshot=tools.call('vase_scene_snapshot',{'sections':['polyhedra'],'limit':2})
            poly=snapshot['polyhedra']['items'][0]
            assert poly['neighborCount']==6 and poly['appearance']['color']=='#cc3355'
            assert poly['appearance']['opacity']==.65
            assert len(poly['vertices'])==6
            assert poly['hullVertexCount']==6 and poly['duplicateVertexCount']==0
            assert poly['toleranceAngstrom']>0 and snapshot['polyhedra']['units']['volume']=='angstrom^3'
            count=len(requests)
            tools.call('vase_style_polyhedra',{'expected_document_id':editor.session_id,'expected_revision':snapshot['revision'],
                'rule_ids':[poly['ruleId']],'color':'#2288cc','opacity':.3})
            assert len(requests)==count
            styled=tools.call('vase_scene_snapshot',{'sections':['polyhedra'],'limit':1})['polyhedra']['items'][0]
            assert styled['appearance']['color']=='#2288cc' and styled['appearance']['opacity']==.3
            assert styled['vertices']==poly['vertices']
            rendered=tools.call('vase_render',{'width':960,'height':640})
            _,data=tools.read_artifact(rendered['artifact']['uri']);assert Image.open(io.BytesIO(data)).size==(960,640)
            # Select a visible face with atoms hidden. Publication output must
            # remain identical even though the live document gains a highlight.
            page.click('#btn-inspector-collapse')
            point=page.evaluate('''() => {
                const r=window.__V_ASE_APP__.renderer,p=r.polyhedraRendered[0];
                return r.projectWorldToClient(p.center);
            }''')
            page.mouse.click(point['x'],point['y'])
            page.wait_for_function('window.__V_ASE_APP__.renderer.polyhedraSelectionGroup?.visible')
            assert page.evaluate('[...window.__V_ASE_APP__.renderer.polyhedraSelected]')==[1]
            selected=tools.call('vase_render',{'width':960,'height':640})
            _,selected_data=tools.read_artifact(selected['artifact']['uri'])
            np.testing.assert_array_equal(np.array(Image.open(io.BytesIO(data))),np.array(Image.open(io.BytesIO(selected_data))))
            assert page.evaluate('window.__V_ASE_APP__.renderer.polyhedraSelectionGroup.visible')
            page.screenshot(path=str(tmp_path/'polyhedra-controls.png'))
            assert not errors
            browser.close()
    finally:editor.close()


@pytest.mark.parametrize('mode',['2d','3d'])
def test_complete_periodic_sites_roles_connectors_and_mcp(mode,tmp_path):
    editor=view(material(),notebook=True,block=False,port=find_free_port(),viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1300,'height':1000})
            page.goto(f'http://127.0.0.1:{editor.port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__V_ASE_APP__?.state?.atoms?.positions?.length===5')
            tools=FunctionTools(f'http://127.0.0.1:{editor.port}/api/ai/command/session/{editor.session_id}',artifact_dir=tmp_path)
            snapshot=tools.call('vase_scene_snapshot',{})
            tools.call('vase_apply_scene',{'expected_document_id':editor.session_id,'expected_revision':snapshot['revision'],
                'patch':{'display':{'atom_display_mode':mode,'show_bonds':False}}})
            snapshot=tools.call('vase_scene_snapshot',{})
            tools.call('vase_configure_polyhedra',{'expected_document_id':editor.session_id,'expected_revision':snapshot['revision'],
                'enabled':True,'complete_ligands':True,'show_center_bonds':True,
                'rules':[{'id':'Ti','centers':{'elements':['Ti']},'ligands':{'elements':['O']},'max_distance':2.2,'color':'#4f9bc9','opacity':.4}]})
            # The public schema gives index/cell_offset, without an internal GUI kind.
            snapshot=tools.call('vase_scene_snapshot',{'sections':['atoms'],'limit':64})
            for offset in ([0,0,1],[0,0,0]):
                tools.call('vase_set_selection',{'expected_document_id':editor.session_id,'expected_revision':snapshot['revision'],
                    'selection':{'references':[{'index':2,'cell_offset':offset}]}})
                snapshot=tools.call('vase_scene_snapshot',{'sections':['atoms'],'limit':64})
                actual=page.evaluate('window.__V_ASE_APP__.selectionEntries()')
                assert len(actual)==1 and actual[0]['index']==2
                assert actual[0]['kind']==('replica' if any(offset) else 'atom')
                if any(offset):assert actual[0]['cellOffset']==offset
            open_panel(page)
            for role,count in [('all',8),('coordination',7),('centers',1),('ligands',6),('none',0)]:
                page.select_option('#poly-atom-mode',role)
                page.wait_for_function('(role)=>window.__V_ASE_APP__.state.display.polyhedraAtomMode===role',arg=role)
                page.evaluate('async()=>{const a=window.__V_ASE_APP__;a.flushVisualHistoryCommit();await a.flushCollaborationEvents();}')
                state=tools.call('vase_scene_snapshot',{'sections':['atoms','bonds','polyhedra'],'visible_only':False,'limit':64})
                visible=[a for a in state['atoms']['items'] if a['enabled']]
                assert len(visible)==count
                assert len({(a['reference']['index'],tuple(a['reference']['cellOffset'])) for a in visible})==count
                connectors=[b for b in state['bonds']['items'] if b.get('source')=='polyhedra-coordination-connector' and b['enabled']]
                assert len(connectors)==6
                if mode=='2d':assert all(s['material']=='unlit' for b in connectors for s in b['segments'])
                assert state['polyhedra']['items'][0]['neighborCount']==6
            page.select_option('#poly-atom-mode','all')
            page.uncheck('#poly-complete')
            page.wait_for_function('window.__V_ASE_APP__.renderer.polyhedraExtraAtoms.length===0')
            page.check('#poly-complete')
            page.wait_for_function('window.__V_ASE_APP__.renderer.polyhedraExtraAtoms.length===3')
            # Supplemental sites must remain selectable by their real image identity.
            selected=page.evaluate('''async()=>{
                const a=window.__V_ASE_APP__,r=a.renderer;
                const {ASESelection}=await import('/static/selection.js');
                a.state.display.translation=[1,2,3];r.setDisplayOptions(a.state.display);
                const selection=new ASESelection(r),site=r.polyhedraExtraAtoms[0];
                const world=site.position.clone().add(r.visualTranslationVector());
                r.camera.position.copy(world).add(r.camera.up.clone().set(8,-15,9));
                r.controls.target.copy(world);r.camera.lookAt(world);r.renderNow();
                const point=r.projectWorldToClient(world);
                return {expected:{index:site.index,cellOffset:site.cellOffset},
                    box:[...selection.boxSelect({left:point.x-2,right:point.x+2,top:point.y-2,bottom:point.y+2},r.atomMeshes,r.camera,r.supercellGroup,true)],
                    hover:selection.pickHover({clientX:point.x,clientY:point.y},r.atomMeshes,r.supercellGroup)};
            }''')
            assert any(isinstance(ref,dict) and ref['index']==selected['expected']['index'] and ref['cellOffset']==selected['expected']['cellOffset'] for ref in selected['box'])
            assert selected['hover']['index']==selected['expected']['index']
            assert selected['hover']['cellOffset']==selected['expected']['cellOffset']
            # A bounded-render failure must restore the prior, usable document.
            rollback=page.evaluate('''async()=>{
                const a=window.__V_ASE_APP__,r=a.renderer,before=JSON.stringify(a.state.display);
                const original=r.createPolyhedraFaceMesh;let injected=false,message='';
                r.createPolyhedraFaceMesh=function(...args){if(!injected){injected=true;throw new Error('Injected face budget error');}return original.apply(this,args);};
                try{await a.configurePolyhedra({atomMode:'none'});}catch(error){message=error.message;}
                finally{r.createPolyhedraFaceMesh=original;}
                return {message,unchanged:before===JSON.stringify(a.state.display),extra:r.polyhedraExtraAtoms.length,count:r.polyhedraRendered.length};
            }''')
            assert rollback=={'message':'Injected face budget error','unchanged':True,'extra':3,'count':1}
            page.uncheck('#poly-center-bonds')
            page.wait_for_function('window.__V_ASE_APP__.renderer.polyhedraConnectors.length===0')
            assert page.evaluate('window.__V_ASE_APP__.state.atoms.positions.length')==5
            browser.close()
    finally:editor.close()


def test_trajectory_updates_hulls_and_offline_html_preserves_style_and_frames(tmp_path):
    first=material();second=first.copy();second.positions[2,2]+=.14
    editor=view([first,second],notebook=True,block=False,port=find_free_port(),viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1200,'height':800})
            page.goto(f'http://127.0.0.1:{editor.port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__V_ASE_APP__?.state?.atoms?.positions?.length===5')
            tools=FunctionTools(f'http://127.0.0.1:{editor.port}/api/ai/command/session/{editor.session_id}',artifact_dir=tmp_path)
            snapshot=tools.call('vase_scene_snapshot',{})
            tools.call('vase_configure_polyhedra',{'expected_document_id':editor.session_id,'expected_revision':snapshot['revision'],
                'enabled':True,'rules':[{'id':'TiO6','centers':{'elements':['Ti']},'ligands':{'elements':['O']},
                    'max_distance':2.3,'color':'#1188bb','opacity':.4}]})
            before=tools.call('vase_scene_snapshot',{'sections':['polyhedra'],'limit':1})
            page.evaluate('async()=>await window.__V_ASE_APP__.loadFrame(1)')
            after=tools.call('vase_scene_snapshot',{'sections':['polyhedra'],'limit':1})
            assert after['readiness']['ready'] and after['frame']==1
            assert before['polyhedra']['items'][0]['vertices']!=after['polyhedra']['items'][0]['vertices']
            d=page.evaluate('window.__V_ASE_APP__.state.display')
            response=export_html_response(sessions[editor.session_id],{'settings':{'display':d},'embed_project':False})
            path=tmp_path/'polyhedra.html';path.write_bytes(response.body)
            offline=browser.new_page();network=[];errors=[]
            offline.on('request',lambda r:network.append(r.url) if r.url.startswith(('http://','https://')) else None)
            offline.on('pageerror',lambda e:errors.append(str(e)))
            offline.goto(path.as_uri());expect(offline.locator('html')).to_have_attribute('data-v-ase-atom-count','5')
            assert not network and not errors
            assert offline.locator('canvas').get_attribute('data-polyhedron-count')=='1'
            offline.screenshot(path=str(tmp_path/'polyhedra-offline.png'))
            encoded=re.search(r'<script id="v-ase-scene-data"[^>]*>(.*?)</script>',path.read_text()).group(1)
            scene=json.loads(base64.b64decode(encoded))
            assert len(scene['frames'])==2
            assert scene['frames'][0]['metadata']['polyhedra']['polyhedra'][0]['style']['opacity']==.4
            offline.locator('#frame-slider').focus();offline.keyboard.press('ArrowLeft')
            expect(offline.locator('html')).to_have_attribute('data-v-ase-frame','0')
            browser.close()
    finally:editor.close()


@pytest.mark.parametrize('mode',['2d','3d'])
def test_interpolated_movie_keeps_polyhedra_in_every_encoded_frame(mode,tmp_path):
    import imageio_ffmpeg
    first=material();second=first.copy();second.positions[2,2]+=.14
    editor=view([first,second],notebook=True,block=False,port=find_free_port(),viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1000,'height':800})
            page.goto(f'http://127.0.0.1:{editor.port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__V_ASE_APP__?.state?.atoms?.positions?.length===5')
            result=page.evaluate('''async mode=>{
                const a=window.__V_ASE_APP__,r=a.renderer;
                Object.assign(a.state.display,{atomDisplayMode:mode,showGrid:false,showAxes:false,showCell:false,
                    showBonds:false,atomRadiusScale:.2,labelColors:{Sr:'#888888',Ti:'#888888',O:'#ff0000'}});
                r.setDisplayOptions(a.state.display);
                await a.configurePolyhedra({enabled:true,atomMode:'coordination',completeLigands:true,
                    rules:[{id:'Ti',centers:{elements:['Ti']},ligands:{elements:['O']},maxDistance:2.3,color:'#124cdd',opacity:.8}]});
                r.fitCameraToStructure();const samples=[],original=a.captureCurrentVideoFrame;
                a.captureCurrentVideoFrame=async function(...args){await original.apply(this,args);samples.push({
                    count:r.polyhedraRendered.length,extra:r.polyhedraExtraAtoms.length,positions:[...r.polyhedraData.polyhedra[0].vertices].sort((a,b)=>a.index-b.index||a.cellOffset[0]-b.cellOffset[0]||a.cellOffset[1]-b.cellOffset[1]||a.cellOffset[2]-b.cellOffset[2]).map(v=>v.position)});};
                const blob=await a.exportTrajectoryVideo({width:320,height:320,fps:6,format:'mov',interpolationMultiplier:2,
                    includeAxes:false,includeGrid:false,includeCell:false},null,{returnBlob:true});
                const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);
                return {samples,data:btoa(binary)};
            }''',mode)
            assert len(result['samples'])==3
            assert all(s['count']==1 and s['extra']==3 for s in result['samples'])
            vertices=[np.array(s['positions']) for s in result['samples']]
            # Align by site-image identity; distance ordering can change between frames.
            np.testing.assert_allclose(vertices[1],(vertices[0]+vertices[2])/2,atol=1e-9)
            path=tmp_path/f'polyhedra-{mode}.mov';path.write_bytes(base64.b64decode(result['data']))
            reader=imageio_ffmpeg.read_frames(str(path),pix_fmt='rgb24');metadata=next(reader)
            assert tuple(metadata['size'])==(320,320)
            frames=[np.frombuffer(frame,np.uint8).reshape(320,320,3).astype(int) for frame in reader]
            assert len(frames)==3
            for frame in frames:
                blue=(frame[:,:,2]>frame[:,:,0]+30)&(frame[:,:,2]>frame[:,:,1]+20)
                assert np.count_nonzero(blue)>100,'Encoded frame lost its blue polyhedron faces.'
            browser.close()
    finally:editor.close()
