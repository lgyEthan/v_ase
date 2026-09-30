"""Real multi-file imports and lattice-direction shortcuts across workspace shells."""
import numpy as np
from pathlib import Path
import pytest
from ase import Atoms
from ase.io import write
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port
from v_ase.session import sessions, create_workspace, finalize_workspace

@pytest.fixture(params=['direct', 'workspace'])
def batch_page(request, tmp_path):
    atom = Atoms('H', positions=[[0,0,0]], cell=[[4,1,0],[1,5,1],[1,2,6]])
    editor = view(Atoms() if 'empty_workspace' in request.node.name else atom, notebook=True, block=False, port=find_free_port(), viz_only=False, close_on_disconnect=False)
    ws = create_workspace(sessions[editor.session_id]) if request.param == 'workspace' else None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1440,'height':960})
        page.add_init_script("Object.defineProperty(navigator,'platform',{get:()=> 'Win32'});Object.defineProperty(navigator,'userAgentData',{value:{platform:'Windows'}});")
        page.goto(f'http://127.0.0.1:{editor.port}/workspace?workspace_id={ws.workspace_id}' if ws else editor.url)
        page.wait_for_function("window.__ASE_APP__?.collaborationReady || document.querySelector('iframe')?.contentWindow?.__ASE_APP__?.workspaceRecoveryAcknowledged")
        frame = page.frames[1] if ws else page.main_frame
        files = []
        for number in [10, 2, 1]:
            path = tmp_path / f'step-{number}.vasp'
            a = atom.copy(); a.positions[0,0] = number / 10
            write(path, a, format='vasp'); files.append(str(path))
        yield page, frame, files, editor
        browser.close()
    if ws: finalize_workspace(ws.workspace_id)
    editor.close()


def test_files_open_separate_tabs_without_overwriting(batch_page):
    page, frame, files, editor = batch_page
    original = frame.evaluate('window.__ASE_APP__.sessionId')
    frame.locator('#structure-file').set_input_files(files)
    frame.locator('#open-batch-confirm').wait_for()
    assert frame.locator('#open-batch-files li > span').all_text_contents() == ['step-1.vasp','step-2.vasp','step-10.vasp']
    assert frame.locator('[name=open-batch-mode]:checked').input_value() == 'tabs'
    frame.locator('#open-batch-confirm').click()
    page.wait_for_function('window.__V_ASE_WORKSPACE__?.tabs.size === 4')
    ws = page.evaluate('window.__V_ASE_WORKSPACE__.workspaceId')
    state = page.request.get(f'http://127.0.0.1:{editor.port}/api/workspace/{ws}').json()
    assert len(state['documents']) == 4
    assert original in [d['session_id'] for d in state['documents']]
    assert sessions[original].working_atoms.positions[0,0] == 0
    children = [sessions[d['session_id']] for d in state['documents'] if d['session_id'] != original]
    assert [s.working_atoms.positions[0,0] for s in children] == pytest.approx([.1,.2,1])
    assert len(page.context.pages) == 1

    # Native drag adapter must not swallow a real click on the child button.
    source = (Path(__file__).parents[1] / 'desktop/host-adapter.js').read_text()
    handlers = source[source.index('    // Pointer capture keeps the gesture'):source.index('    native.onCommand')]
    page.evaluate('()=>{const host={detach:async()=>{}};const report=()=>{};const workspace=()=>window.__V_ASE_WORKSPACE__;'+handlers+'}')
    selector = '.document-select, .direct-document-select'
    buttons = page.locator(selector)
    buttons.nth(0).click()
    assert page.evaluate('window.__V_ASE_WORKSPACE__.activeSessionId') == original
    buttons.nth(1).click()
    child = page.evaluate('window.__V_ASE_WORKSPACE__.activeSessionId')
    assert child != original
    page.wait_for_function('''()=>{const w=window.__V_ASE_WORKSPACE__;return w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged;}''')
    # The command family is separate from Alt-only trajectory stepping.
    for key, expected in [('Control+1', original), ('Control+Alt+ArrowRight', child),
                          ('Control+Alt+ArrowLeft', original)]:
        page.keyboard.press(key)
        page.wait_for_function('window.__V_ASE_WORKSPACE__.activeSessionId === '+repr(expected))
    page.keyboard.press('Control+9')
    assert page.evaluate('(()=>{const w=window.__V_ASE_WORKSPACE__;return w.activeSessionId === [...w.tabs.keys()].at(-1);})()')


def test_cell_view_does_not_inherit_other_lattice_vector_roll(batch_page):
    page, frame, files, editor = batch_page
    frame.evaluate('''()=>{const a=window.__ASE_APP__;a.state.atoms.cell=[[11.60882634,0,0],[-1.93480439,10.05353852,0],[0,-2.23411967,10.11592505]];
        a.alignViewToCellAxis('a');}''')
    pose = frame.evaluate('window.__ASE_APP__.cameraViewBasis().up.toArray()')
    assert pose == pytest.approx([0, 0, 1], abs=1e-7)
    assert frame.evaluate('window.__ASE_APP__.cameraViewBasis().offset.normalize().toArray()') == pytest.approx([1, 0, 0])
    frame.evaluate("window.__ASE_APP__.alignViewToCellAxis('a')")
    assert frame.evaluate('window.__ASE_APP__.cameraViewBasis().offset.normalize().toArray()') == pytest.approx([-1, 0, 0])
    frame.evaluate('''()=>{const a=window.__ASE_APP__;a.state.atoms.cell=[[4,0,0],[0,5,0],[0,0,6]];a.alignViewToCellAxis('c');}''')
    assert frame.evaluate('window.__ASE_APP__.cameraViewBasis().up.toArray()') == pytest.approx([0, 1, 0], abs=1e-7)


def test_files_form_ordered_unsaved_trajectory_and_cancel_is_safe(batch_page):
    page, frame, files, editor = batch_page
    frame.locator('#structure-file').set_input_files(files)
    frame.locator('#open-batch-cancel').click()
    assert frame.evaluate('window.__ASE_APP__.state.atoms.positions.length') == 1
    frame.locator('#structure-file').set_input_files(files)
    frame.locator('[name=open-batch-mode][value=trajectory]').check()
    frame.locator('#open-batch-files li').nth(1).locator('button').first.click()
    frame.locator('#open-batch-confirm').click()
    page.wait_for_function('window.__V_ASE_WORKSPACE__?.tabs.size === 2')
    page.wait_for_function('''() => {const w=window.__V_ASE_WORKSPACE__;return w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged;}''')
    sid = page.evaluate('window.__V_ASE_WORKSPACE__.activeSessionId')
    assert [a.positions[0,0] for a in sessions[sid].trajectory_frames] == pytest.approx([.2,.1,1])
    state = page.evaluate('''()=>{const w=window.__V_ASE_WORKSPACE__,a=w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__;return {dirty:a.updateProjectDirtyState(),handle:a.projectFile.handle,format:a.projectFile.format};}''')
    assert state == {'dirty':True,'handle':None,'format':None}


def test_invalid_batch_rolls_back_every_staged_document(batch_page, tmp_path):
    page, frame, files, editor = batch_page
    bad = tmp_path/'step-3.vasp'; bad.write_text('invalid cell')
    frame.locator('#structure-file').set_input_files([files[2], str(bad)])
    frame.locator('#open-batch-confirm').click()
    frame.wait_for_function("document.getElementById('toast-container').innerText.includes('step-3.vasp')")
    assert page.evaluate('window.__V_ASE_WORKSPACE__.tabs.size') == 1
    ws = page.evaluate('window.__V_ASE_WORKSPACE__.workspaceId')
    assert len(page.request.get(f'http://127.0.0.1:{editor.port}/api/workspace/{ws}').json()['documents']) == 1


def test_lattice_axes_toggle_without_selecting_and_respect_typing(batch_page):
    page, frame, files, editor = batch_page
    frame.evaluate('document.activeElement?.blur()')
    pose = '(()=>{const a=window.__ASE_APP__,b=a.cameraViewBasis();return {direction:b.offset.normalize().toArray(),up:b.up.toArray(),target:b.target.toArray(),selected:[...a.state.selected]};})()'
    for key, vector in zip('abc', [[4,1,0],[1,5,1],[1,2,6]]):
        direction = np.array(vector)/np.linalg.norm(vector)
        frame.evaluate('document.body.focus();document.activeElement?.blur()')
        page.keyboard.press(key)
        first = frame.evaluate(pose)
        assert first['direction'] == pytest.approx(direction, abs=1e-7)
        assert first['selected'] == []
        page.keyboard.press(key)
        second = frame.evaluate(pose)
        assert second['direction'] == pytest.approx(-direction, abs=1e-7)
        assert second['target'] == first['target']
        assert np.dot(second['direction'], second['up']) == pytest.approx(0, abs=1e-7)
    page.keyboard.press('Control+a')
    assert frame.evaluate('[...window.__ASE_APP__.state.selected]') == [0]
    page.keyboard.press('Alt+a')
    assert frame.evaluate('[...window.__ASE_APP__.state.selected]') == []
    page.keyboard.press('x'); assert frame.evaluate(pose)['direction'] == pytest.approx([1,0,0])
    # No cell: A/B/C have no effect. Ctrl+A is still independent of the cell.
    frame.evaluate('window.__ASE_APP__.state.atoms.cell=[[0,0,0],[0,0,0],[0,0,0]]')
    before = frame.evaluate(pose)
    for key in 'abc': page.keyboard.press(key)
    assert frame.evaluate(pose) == before
    frame.evaluate("const i=document.createElement('input');i.id='axis-typing';document.body.append(i);i.focus()")
    page.keyboard.type('abcxyz')
    assert frame.locator('#axis-typing').input_value() == 'abcxyz'
    assert frame.evaluate(pose) == before


def test_late_single_open_promotes_to_one_batch_and_cancel_during_read_rolls_back(batch_page):
    page, frame, files, editor = batch_page
    frame.locator('#structure-file').set_input_files(files[0])
    frame.locator('#open-file-confirm').wait_for()
    frame.locator('#structure-file').set_input_files(files[1:])
    frame.locator('#open-batch-confirm').wait_for()
    assert frame.locator('#open-batch-files li').count() == 3
    frame.locator('#open-batch-cancel').click()
    # A deliberately held second file read lets cancellation exercise staging
    # cleanup after the first file uploaded, with no partially published tabs.
    frame.evaluate("""() => {
        const a=window.__ASE_APP__,file=new File(['1\\nseed\\nH 0 0 0\\n'],'one.xyz');
        a.showOpenFilesModal([{file},{name:'two.xyz',getFile:()=>new Promise(resolve=>{window.__finishBatchRead=()=>resolve(file);})}]);
    }""")
    frame.locator('#open-batch-confirm').click()
    frame.wait_for_function('Boolean(window.__finishBatchRead)')
    frame.locator('#open-batch-stop').click()
    frame.evaluate('window.__finishBatchRead()')
    page.wait_for_function('!window.__vaseFileOpenQueue.running')
    assert page.evaluate('window.__V_ASE_WORKSPACE__.tabs.size') == 1
    ws=page.evaluate('window.__V_ASE_WORKSPACE__.workspaceId')
    assert len(page.request.get(f'http://127.0.0.1:{editor.port}/api/workspace/{ws}').json()['documents']) == 1


def test_project_batch_preserves_saved_modes_profiles_and_file_handles(batch_page, tmp_path):
    import base64
    from v_ase.project import write_project_archive
    from v_ase.session import EditorSession
    from v_ase.export import export_html_response
    page,frame,files,editor=batch_page
    atoms=Atoms('He',positions=[[0,0,0]])
    payload=[]
    for mode,fmt in [('view','vase'),('edit','html')]:
        seed=EditorSession('seed',atoms.copy(),atoms.copy(),config={'viz_only':mode=='view'})
        settings={'display':{'atomRadiusScale':.75},'projectSave':{'format':fmt,
            'html':{'exportProfile':{'kind':'html','width':640,'height':480,'options':{'scaleMode':'physical','pixelsPerAngstrom':47}}} if fmt=='html' else None}}
        if fmt=='vase':
            path=write_project_archive(tmp_path/'saved.vase',seed,settings); raw=path.read_bytes()
        else:
            raw=export_html_response(seed,{'settings':settings,'embed_project':True,'document_name':'saved','export_profile':settings['projectSave']['html']['exportProfile']}).body
        payload.append({'name':f'{mode}.{fmt}','raw':base64.b64encode(raw).decode()})
    frame.evaluate("""entries=>{window.__ASE_APP__.showOpenFilesModal(entries.map(e=>({file:new File([Uint8Array.from(atob(e.raw),c=>c.charCodeAt(0))],e.name),handle:{kind:'file',name:e.name,testHandle:true}})));}""",payload)
    frame.locator('#open-batch-confirm').click()
    page.wait_for_function('window.__V_ASE_WORKSPACE__?.tabs.size===3')
    ids=page.evaluate('[...window.__V_ASE_WORKSPACE__.tabs.keys()].slice(1)')
    found={}
    for sid in ids:
        page.evaluate('sid=>{const w=window.__V_ASE_WORKSPACE__; (w.activateDocument||w.activate).call(w,sid);}',sid)
        page.wait_for_function("""()=>{const w=window.__V_ASE_WORKSPACE__;return w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged;}""")
        info=page.evaluate("""()=>{const w=window.__V_ASE_WORKSPACE__,a=w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__;return {mode:a.state.vizOnly?'view':'edit',format:a.projectFile.format,handle:a.projectFile.handle?.testHandle,radius:a.state.display.atomRadiusScale,profile:a.projectFile.outputProfile};}""")
        found[info['format']]=info
    assert found['vase']['mode']=='view' and found['html']['mode']=='edit'
    assert all(i['handle'] and i['radius']==.75 for i in found.values())
    assert found['html']['profile']['width']==640
    assert found['html']['profile']['options']['pixelsPerAngstrom']==47


def test_empty_workspace_batch_removes_only_placeholder(batch_page):
    page,frame,files,editor=batch_page
    assert not frame.evaluate('window.__ASE_APP__.hasScratchContent()')
    frame.locator('#structure-file').set_input_files(files[:2])
    frame.locator('#open-batch-confirm').click()
    page.wait_for_function('window.__V_ASE_WORKSPACE__?.tabs.size===2 && !window.__vaseFileOpenQueue.running')
    page.wait_for_function("""()=>{const w=window.__V_ASE_WORKSPACE__;return w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged;}""")
    assert page.evaluate('window.__V_ASE_WORKSPACE__.tabs.size')==2
