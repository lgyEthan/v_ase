"""Open the actual problematic CIF through the GUI, then inspect both layers."""
from pathlib import Path

import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import view,find_free_port
from tests.ui_navigation import open_editor_route

FIXTURE=Path(__file__).parent/'fixtures/vermiculite.cif'


@pytest.mark.parametrize('reader',['','cif'],ids=['auto-detect','explicit-cif'])
def test_cif_open_and_first_use_polyhedra_show_both_layers_without_bond_lines(reader,tmp_path):
    editor=view(Atoms(),notebook=True,open_browser=False,block=False,port=find_free_port(),viz_only=False,close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            p=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
            p.on('pageerror',lambda e:errors.append(str(e)))
            p.goto(editor.url);p.wait_for_function('window.__ASE_APP__?.collaborationReady')
            p.evaluate('''text=>{const dt=new DataTransfer();dt.items.add(new File([text],'vermiculite.cif',{type:'chemical/x-cif'}));document.body.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));}''',FIXTURE.read_text())
            assert p.locator('#open-file-format option[value="cif"]').count()==1
            p.select_option('#open-file-format',reader);p.click('#open-file-confirm')
            p.wait_for_function('window.__ASE_APP__.state.atoms.positions.length===76')
            before=p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')
            open_editor_route(p,'bonding');p.uncheck('#chk-bonds')
            open_editor_route(p,'polyhedra')
            assert not p.is_checked('#poly-bonded-only')
            p.check('#poly-enabled')
            p.wait_for_function('window.__ASE_APP__.renderer.polyhedraData?.polyhedronCount===28')
            counts=p.evaluate('''()=>{const a=window.__ASE_APP__,out={};for(const item of a.renderer.polyhedraData.polyhedra){const key=`${item.centerLabel}:${item.neighborCount}`;out[key]=(out[key]||0)+1;}return out;}''')
            assert counts=={'Mg:6':12,'Si:4':16}
            assert not p.evaluate('window.__ASE_APP__.state.display.showBonds')
            assert p.evaluate('window.__ASE_APP__.renderer.polyhedraRendered.length')==28
            assert 'CN 4' in p.locator('#poly-breakdown').inner_text()
            assert 'CN 6' in p.locator('#poly-breakdown').inner_text()
            p.click('#poly-help-toggle')
            assert '1.25' in p.locator('#poly-help').inner_text()
            assert 'Periodic images' in p.locator('#poly-help').inner_text()
            p.locator('#poly-help-toggle').press('Escape');assert p.locator('#poly-help').is_hidden()
            p.check('#poly-bonded-only')
            p.wait_for_function('window.__ASE_APP__.renderer.polyhedraData?.bondedOnly===true')
            assert p.evaluate('window.__ASE_APP__.renderer.polyhedraData.polyhedronCount')==28
            assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms.positions)')==before
            # The same workflow must be reachable through the typed agent tool,
            # with the real document/revision guard and no private route calls.
            from v_ase.ai_tools import FunctionTools
            with FunctionTools(f'http://127.0.0.1:{editor.port}/api/ai/command/session/{editor.session_id}',artifact_dir=tmp_path) as tools:
                snapshot=tools.call('vase_scene_snapshot',{'sections':['polyhedra'],'limit':1})
                tools.call('vase_configure_polyhedra',{'expected_document_id':editor.session_id,
                    'expected_revision':snapshot['revision'],'automatic':True,'enabled':True,'bonded_only':False})
                checked=tools.call('vase_scene_snapshot',{'sections':['polyhedra'],'limit':1})
                assert checked['polyhedra']['items'][0]['neighborCount'] in (4,6)
                assert p.evaluate('window.__ASE_APP__.renderer.polyhedraData.polyhedronCount')==28
                assert not p.evaluate('window.__ASE_APP__.state.display.polyhedraBondedOnly')
            p.screenshot(path=str(tmp_path/f'vermiculite-{reader or "auto"}.png'))
            assert not errors,errors
            browser.close()
    finally:editor.close()
