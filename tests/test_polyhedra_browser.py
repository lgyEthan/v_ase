"""Live GUI/native/standalone checks for polyhedra, including style-only edits."""
import io
import base64
import re
import json
from pathlib import Path

import numpy as np
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
