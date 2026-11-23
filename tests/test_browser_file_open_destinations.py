"""Open destinations preserve work and handle an actual fifteen-file selection."""
import numpy as np
import pytest
from ase import Atoms
from ase.io import write

from tests.test_batch_and_cell import batch_page  # noqa: F401
from tests.test_browser_ui_revision import revision_workspace  # noqa: F401
from v_ase.session import sessions


SOURCE_STATE = '''() => {
    const a=window.__ASE_APP__;
    return {scientific:a.projectScientificSignature(),radius:a.state.display.atomRadiusScale,
        selection:[...a.state.selected],dirty:a.updateProjectDirtyState(),
        sameHandle:a.projectFile.handle===window.__sourceHandle};
}'''


def preserve_dirty_source(frame):
    frame.evaluate('''() => {
        const a=window.__ASE_APP__;
        a.markProjectSavedContent();
        window.__sourceHandle={kind:'file',name:'source.vase'};
        a.projectFile.handle=window.__sourceHandle;
        a.state.display.atomRadiusScale=1.17;
        a.applySelectionAction({references:[0],origin:'semantic'});
    }''')
    state=frame.evaluate(SOURCE_STATE)
    assert state['dirty'] and state['sameHandle']
    return state


@pytest.mark.parametrize('entry',['picker','drop'])
def test_single_file_defaults_to_new_tab_without_touching_dirty_source(batch_page,entry):
    page,frame,files,editor=batch_page
    source=frame.evaluate('window.__ASE_APP__.sessionId')
    before=preserve_dirty_source(frame)
    positions=sessions[source].working_atoms.positions.copy()
    if entry=='picker':
        frame.locator('#structure-file').set_input_files(files[0])
    else:
        from pathlib import Path
        frame.evaluate('''text => {
            const dt=new DataTransfer();dt.items.add(new File([text],'step-10.vasp'));
            document.body.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));
        }''',Path(files[0]).read_text())
    confirm=frame.locator('#open-file-confirm')
    confirm.wait_for()
    assert frame.locator('[name="open-file-mode"]:checked').input_value()=='new-tab'
    assert frame.locator('[name="open-file-mode"]').first.input_value()=='new-tab'
    assert confirm.inner_text()=='Open New Tab'
    assert frame.locator('.open-file-modes').bounding_box()['y'] < frame.locator('#open-file-format').bounding_box()['y']
    confirm.click()
    page.wait_for_function('window.__V_ASE_WORKSPACE__?.tabs.size===2 && !window.__vaseFileOpenQueue.running')
    imported=page.evaluate('window.__V_ASE_WORKSPACE__.activeSessionId')
    assert imported!=source
    assert sessions[imported].working_atoms.positions[0,0]==pytest.approx(1)
    assert frame.evaluate(SOURCE_STATE)==before
    np.testing.assert_array_equal(sessions[source].working_atoms.positions,positions)


@pytest.mark.parametrize('destination',['tabs','trajectory'])
def test_fifteen_files_offer_both_destinations_and_keep_every_frame(revision_workspace,tmp_path,destination):
    page,frame,native,errors=revision_workspace
    source=frame.evaluate('window.__ASE_APP__.sessionId')
    before=preserve_dirty_source(frame)
    positions=sessions[source].working_atoms.positions.copy()
    files=[]
    # One file contains two frames: fifteen files must not be called fifteen frames.
    for number in range(15,0,-1):
        path=tmp_path/f'step-{number}.xyz'
        structures=[Atoms('H',positions=[[number/10,0,0]])]
        if number==1:structures.append(Atoms('H',positions=[[.15,0,0]]))
        write(path,structures,format='extxyz');files.append(path)
    if native:
        # Exercise the real desktop adapter with opaque grants, without an OS dialog.
        page.evaluate('''async entries => {
            const grants=new Map(entries.map((e,i)=>{
                const bytes=new TextEncoder().encode(e.text);
                return [String(i),{token:String(i),name:e.name,size:bytes.length,lastModified:1,bytes}];
            }));
            const native=window.vaseDesktop;
            native.chooseOpen=async()=>[...grants.values()].map(({bytes,...description})=>description);
            native.stat=async token=>{const {bytes,...description}=grants.get(token);return description;};
            native.read=async(token,offset)=>grants.get(token).bytes.slice(offset,offset+4096);
            await window.__vaseDesktopHost.command('open');
        }''',[{'name':path.name,'text':path.read_text()} for path in files])
    else:
        frame.locator('#structure-file').set_input_files([str(path) for path in files])
    confirm=frame.locator('#open-batch-confirm');confirm.wait_for()
    assert confirm.inner_text()=='Open 15 tabs'
    assert frame.locator('#open-batch-files li > span').all_text_contents()==[f'step-{n}.xyz' for n in range(1,16)]
    assert frame.locator('#open-batch-files').evaluate('e=>e.scrollHeight>e.clientHeight')
    frame.locator(f'[name="open-batch-mode"][value="{destination}"]').check()
    assert confirm.inner_text()==('Open 15 tabs' if destination=='tabs' else 'Open trajectory')
    page.screenshot(path=str(tmp_path/f'fifteen-{native}-{destination}-choice.png'),animations='disabled')
    confirm.click()
    size=16 if destination=='tabs' else 2
    page.wait_for_function('(size)=>window.__V_ASE_WORKSPACE__.tabs.size===size && !window.__vaseFileOpenQueue.running',arg=size)
    ids=page.evaluate('[...window.__V_ASE_WORKSPACE__.tabs.keys()]')
    assert ids[0]==source
    if destination=='tabs':
        assert len(sessions[ids[1]].trajectory_frames)==2
        assert [sessions[sid].working_atoms.positions[0,0] for sid in ids[1:]]==pytest.approx([n/10 for n in range(1,16)])
        page.locator('.document-tab').last.locator('.document-select').click()
        page.wait_for_function('''sid=>{const w=window.__V_ASE_WORKSPACE__;return w.activeSessionId===sid &&
            w.tabs.get(sid).pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged;}''',arg=ids[-1])
        last=next(f for f in page.frames if f.evaluate('window.__ASE_APP__?.sessionId')==ids[-1])
        assert last.evaluate('window.__ASE_APP__.state.atoms.positions[0][0]')==pytest.approx(1.5)
    else:
        movie=sessions[ids[1]]
        assert [a.positions[0,0] for a in movie.trajectory_frames]==pytest.approx([.1,.15,*[n/10 for n in range(2,16)]])
        page.wait_for_function('''()=>{const w=window.__V_ASE_WORKSPACE__;return w.tabs.get(w.activeSessionId).pane.contentWindow.__ASE_APP__?.workspaceRecoveryAcknowledged;}''')
        movie_frame=next(f for f in page.frames if f.evaluate('window.__ASE_APP__?.sessionId')==ids[1])
        assert movie_frame.evaluate('window.__ASE_APP__.updateProjectDirtyState()')
        assert movie_frame.evaluate('window.__ASE_APP__.projectFile.handle') is None
        movie_frame.evaluate('window.__ASE_APP__.loadFrame(15)')
        assert movie_frame.locator('#frame-label').inner_text()=='16 / 16'
        movie_frame.evaluate('window.__ASE_APP__.loadFrame(0)')
        movie_frame.locator('#btn-play').click()
        movie_frame.wait_for_function('window.__ASE_APP__.state.atoms.metadata.current_frame>0')
        movie_frame.evaluate('window.__ASE_APP__.stopPlayback()')
    assert frame.evaluate(SOURCE_STATE)==before
    np.testing.assert_array_equal(sessions[source].working_atoms.positions,positions)
    assert len(page.context.pages)==1 and not errors


def test_late_os_files_sort_together_and_manual_order_keeps_keyboard_focus(batch_page):
    page,frame,files,editor=batch_page
    frame.locator('#structure-file').set_input_files(files[0])  # step-10 arrives first.
    frame.locator('#open-file-confirm').wait_for()
    frame.locator('#structure-file').set_input_files(files[1:])
    frame.locator('#open-batch-confirm').wait_for()
    names=frame.locator('#open-batch-files li > span')
    assert names.all_text_contents()==['step-1.vasp','step-2.vasp','step-10.vasp']
    # Move to the boundary using Enter; the opposite enabled arrow retains focus.
    up=frame.locator('#open-batch-files li').nth(1).locator('button').first
    up.focus();up.press('Enter')
    assert names.all_text_contents()==['step-2.vasp','step-1.vasp','step-10.vasp']
    assert frame.evaluate('document.activeElement.title')=='Move down: step-2.vasp'
    assert frame.locator('#open-batch-announcement').inner_text()=='step-2.vasp, position 1 of 3'
    frame.evaluate("window.__ASE_APP__.showOpenFilesModal([new File(['1\\nnew\\nH 0 0 0\\n'],'step-0.xyz')]);undefined")
    # showOpenFilesModal first awaits its module import; wait for this arrival,
    # not the whole modal promise (which completes only after user confirmation).
    frame.wait_for_function('document.querySelectorAll("#open-batch-files li").length===4')
    assert names.all_text_contents()==['step-2.vasp','step-1.vasp','step-10.vasp','step-0.xyz']
    assert frame.locator('#open-batch-confirm').inner_text()=='Open 4 tabs'
    assert frame.evaluate('document.activeElement.title')=='Move down: step-2.vasp'
    down=frame.locator('#open-batch-files li').nth(2).locator('button').last
    down.focus();down.press('Enter')
    assert frame.evaluate('document.activeElement.title')=='Move up: step-10.vasp'
    frame.locator('[name="open-batch-mode"][value="trajectory"]').check()
    assert frame.locator('#open-batch-files').get_attribute('aria-label')=='Files in trajectory order'
    frame.locator('#open-batch-cancel').click()
    page.wait_for_function('!window.__vaseFileOpenQueue.running')
    assert page.evaluate('window.__V_ASE_WORKSPACE__?.tabs.size||1')==1
    assert sessions[editor.session_id].working_atoms.positions[0,0]==0
