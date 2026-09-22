"""Notebook/direct editors adopt tabs without reloading the first document."""

import os
import base64
import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view
from v_ase.session import EditorSession
from v_ase.project import write_project_archive
from v_ase.export import export_html_response


def test_direct_editor_adopts_tabs_in_place_and_preserves_host_file_handle():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.evaluate("""() => {
                window.__hostApp=window.__ASE_APP__;
                window.__hostHandle={name:'retained.vase'};
                window.__hostApp.projectFile.handle=window.__hostHandle;
            }""")
            page.locator('#editor-menu-bar details').first.locator('summary').click()
            page.click('[data-editor-menu-action="new"]')
            page.wait_for_function("""() => window.__V_ASE_WORKSPACE__?.tabs?.size===2
                && window.__V_ASE_WORKSPACE__.activeSessionId!==window.__hostApp.sessionId""")
            page.locator('.direct-document-pane:not([hidden])').wait_for(state='visible')
            page.locator('.direct-document-tab').first.locator('.direct-document-select').click()
            assert page.evaluate("""() => {
                const tools=document.getElementById('viewport-tools').getBoundingClientRect();
                const camera=document.getElementById('viewport-camera-tools').getBoundingClientRect();
                return tools.right<=camera.left || tools.left>=camera.right
                    || tools.bottom<=camera.top || tools.top>=camera.bottom;
            }""") is True
            if path := os.environ.get('V_ASE_DIRECT_QA_SCREENSHOT'):
                page.screenshot(path=path)
            assert page.evaluate("""() => window.__ASE_APP__===window.__hostApp
                && window.__hostApp.projectFile.handle===window.__hostHandle
                && !window.__hostApp.disposed""") is True
            page.locator('.direct-document-tab').first.locator('.direct-document-close').click()
            page.wait_for_function("""() => window.__V_ASE_WORKSPACE__.tabs.size===1
                && window.__hostApp.disposed""")
            assert page.locator('.direct-document-pane:not([hidden])').is_visible()
            page.wait_for_function("""() => {
                const child=document.querySelector('.direct-document-pane')?.contentWindow?.__ASE_APP__;
                return child?.collaborationReady && child.workspaceBaselineSettled
                    && child.workspaceBaselineTimer===null && !child.projectFile.dirty;
            }""")
            previous = page.evaluate("window.__V_ASE_WORKSPACE__.activeSessionId")
            page.locator('.direct-document-tab').first.locator('.direct-document-close').click()
            page.wait_for_function("""previous => window.__V_ASE_WORKSPACE__.tabs.size===1
                && window.__V_ASE_WORKSPACE__.activeSessionId!==previous""", arg=previous)
            assert page.locator('#direct-document-bar').is_visible()
            browser.close()
    finally:
        editor.close()


def test_direct_editor_open_file_in_new_tab_preserves_first_document():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            result = page.evaluate("""async () => {
                const app=window.__ASE_APP__;
                const original=app;
                const handle={name:'original.vase'};
                app.projectFile.handle=handle;
                const file=new File(['2\\nexample\\nH 0 0 0\\nH 1 0 0\\n'],
                    'two-hydrogen.xyz',{type:'text/plain'});
                await app.openStructureFileInNewTab(file,'xyz',':','edit');
                const workspace=window.__V_ASE_WORKSPACE__;
                return {tabs:workspace.tabs.size,hostSame:window.__ASE_APP__===original,
                    handleSame:original.projectFile.handle===handle,
                    active:workspace.activeSessionId!==original.sessionId};
            }""")
            assert result == {"tabs": 2, "hostSame": True, "handleSame": True, "active": True}
            page.wait_for_function("""() => document.querySelector('.direct-document-pane:not([hidden])')
                ?.contentWindow?.__ASE_APP__?.state?.atoms?.positions?.length === 2""")
            browser.close()
    finally:
        editor.close()


def test_direct_editor_dirty_child_close_cancel_then_discard():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            page.locator('#editor-menu-bar details').first.locator('summary').click()
            page.click('[data-editor-menu-action="new"]')
            page.wait_for_function("window.__V_ASE_WORKSPACE__?.tabs?.size === 2")
            child = page.frame_locator('.direct-document-pane:not([hidden])')
            child.locator('#app-viewport').wait_for()
            page.wait_for_function("""() => {
                const app=document.querySelector('.direct-document-pane:not([hidden])')
                    ?.contentWindow?.__ASE_APP__;
                return app?.visualHistoryReady && app.workspaceBaselineSettled;
            }""")
            child.locator('#workbench-tabs [data-workbench="style"]').click()
            child.locator('#atom-radius-scale-number').fill('0.85')
            child.locator('#atom-radius-scale-number').press('Tab')
            page.wait_for_function("document.querySelector('.direct-document-tab.active.dirty')")
            page.locator('.direct-document-tab.active .direct-document-close').click()
            child.locator('#modal-keep-editing').click()
            assert page.locator('.direct-document-tab').count() == 2
            page.locator('.direct-document-tab.active .direct-document-close').click()
            child.locator('#modal-discard-document').click()
            page.wait_for_function("window.__V_ASE_WORKSPACE__.tabs.size === 1")
            assert page.evaluate("window.__V_ASE_WORKSPACE__.activeSessionId === window.__ASE_APP__.sessionId")
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('format_name', ['vase', 'html'])
def test_direct_new_project_tab_adopts_format_profile_and_writable_handle(tmp_path, format_name):
    atoms = Atoms('H', positions=[[0, 0, 0]])
    session = EditorSession('new-tab-source', atoms.copy(), atoms.copy(), config={'viz_only': True})
    profile = {'kind': 'html', 'width': 640, 'height': 480,
               'options': {'scaleMode': 'physical', 'pixelsPerAngstrom': 47}}
    settings = {'projectSave': {'html': {'exportProfile': profile}}}
    if format_name == 'html':
        data = export_html_response(session, {'settings': settings, 'embed_project': True,
                                             'document_name': 'audit', 'export_profile': profile}).body
    else:
        source = tmp_path / 'audit.vase'
        write_project_archive(source, session, settings)
        data = source.read_bytes()
    encoded = base64.b64encode(data).decode('ascii')
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('''async ({encoded,formatName}) => {
                const bytes=Uint8Array.from(atob(encoded), char=>char.charCodeAt(0));
                const file=new File([bytes], `audit.${formatName}`, {
                    type:formatName==='html'?'text/html':'application/vnd.v-ase.project+zip',
                    lastModified:1234
                });
                const handle={name:file.name, getFile:async()=>file,
                    createWritable:async()=>({write:async()=>{},close:async()=>{}})};
                window.__auditHandle=handle;
                await window.__ASE_APP__.openStructureFileInNewTab(file,'',':','view',{handle});
            }''', {'encoded': encoded, 'formatName': format_name})
            page.wait_for_function('''() => {
                const child=document.querySelector('.direct-document-pane:not([hidden])')?.contentWindow?.__ASE_APP__;
                return child?.projectFile?.format;
            }''')
            result = page.evaluate('''() => {
                const child=document.querySelector('.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__;
                return {format:child.projectFile.format,filename:child.projectFile.filename,
                    handle:child.projectFile.handle===window.__auditHandle,
                    width:child.projectFile.outputProfile?.width,
                    pixelsPerAngstrom:child.projectFile.outputProfile?.options?.pixelsPerAngstrom,
                    dirty:child.projectFile.dirty};
            }''')
            assert result['format'] == format_name
            assert result['filename'] == f'audit.{format_name}'
            assert result['handle'] is True
            if format_name == 'html':
                assert result['width'] == 640
                assert result['pixelsPerAngstrom'] == 47
            page.evaluate('''() => {
                const pane=document.querySelector('.direct-document-pane:not([hidden])');
                window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                pane.contentWindow.location.reload();
            }''')
            page.wait_for_function('''formatName => {
                const child=document.querySelector('.direct-document-pane:not([hidden])')
                    ?.contentWindow?.__ASE_APP__;
                const workspace=window.__V_ASE_WORKSPACE__;
                return child && child!==window.__oldProjectChild
                    && child.collaborationReady && child.projectFile.format===formatName
                    && child.workspaceRecoveryAcknowledged
                    && workspace.tabs.get(workspace.activeSessionId)?.appInstance===child;
            }''', arg=format_name)
            reloaded = page.evaluate('''() => {
                const child=document.querySelector('.direct-document-pane:not([hidden])')
                    .contentWindow.__ASE_APP__;
                return {format:child.projectFile.format,filename:child.projectFile.filename,
                    handle:child.projectFile.handle===window.__auditHandle,
                    scale:child.projectFile.outputProfile?.options?.pixelsPerAngstrom,
                    dirty:child.projectFile.dirty};
                }''')
            assert reloaded['format'] == format_name
            assert reloaded['filename'] == f'audit.{format_name}'
            assert reloaded['handle'] is True
            assert reloaded['dirty'] is False
            if format_name == 'html':
                assert reloaded['scale'] == 47
            if format_name == 'vase':
                page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .openEditorRoute('appearance')''')
                radius = page.frame_locator('.direct-document-pane:not([hidden])')
                radius.locator('#atom-radius-scale-number').fill('0.85')
                radius.locator('#atom-radius-scale-number').press('Tab')
                page.wait_for_function('''() => document.querySelector(
                    '.direct-document-tab.active.dirty') !== null''')
                page.wait_for_function('''() => {
                    const workspace=window.__V_ASE_WORKSPACE__;
                    return workspace.tabs.get(workspace.activeSessionId)
                        ?.visualSnapshot?.display?.atomRadiusScale===0.85;
                }''')
                before_reload = page.evaluate('''() => {
                    const workspace=window.__V_ASE_WORKSPACE__;
                    const entry=workspace.tabs.get(workspace.activeSessionId);
                    const child=entry.pane.contentWindow.__ASE_APP__;
                    return {current:child.state.display.atomRadiusScale,
                        retained:entry.visualSnapshot?.display?.atomRadiusScale,
                        dirty:entry.dirty};
                }''')
                assert before_reload == {'current': 0.85, 'retained': 0.85, 'dirty': True}
                page.evaluate('''() => {
                    const pane=document.querySelector('.direct-document-pane:not([hidden])');
                    window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                    pane.contentWindow.location.reload();
                }''')
                page.wait_for_function('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        ?.contentWindow?.__ASE_APP__;
                    const workspace=window.__V_ASE_WORKSPACE__;
                    return child && child!==window.__oldProjectChild
                        && child.collaborationReady && child.projectFile.format==='vase'
                        && workspace.tabs.get(workspace.activeSessionId)?.appInstance===child;
                }''')
                restored = page.evaluate('''() => {
                    const workspace=window.__V_ASE_WORKSPACE__;
                    const entry=workspace.tabs.get(workspace.activeSessionId);
                    const child=entry.pane.contentWindow.__ASE_APP__;
                    return {current:child.state.display.atomRadiusScale,
                        retained:entry.visualSnapshot?.display?.atomRadiusScale,
                        dirty:entry.dirty};
                }''')
                assert restored['current'] == pytest.approx(0.85), restored
                page.wait_for_timeout(350)  # Cross the former delayed baseline timer.
                assert page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .updateProjectDirtyState()''') is True
                page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .openEditorRoute('appearance')''')
                radius = page.frame_locator('.direct-document-pane:not([hidden])')
                for value in ('0.90', '0.95'):
                    radius.locator('#atom-radius-scale-number').fill(value)
                    radius.locator('#atom-radius-scale-number').press('Tab')
                assert page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .state.display.atomRadiusScale''') == pytest.approx(0.95)
                page.evaluate('''() => {
                    const pane=document.querySelector('.direct-document-pane:not([hidden])');
                    window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                    pane.contentWindow.location.reload();
                }''')
                page.wait_for_function('''() => {
                    const pane=document.querySelector('.direct-document-pane:not([hidden])');
                    const child=pane?.contentWindow?.__ASE_APP__;
                    const entry=window.__V_ASE_WORKSPACE__?.tabs
                        .get(window.__V_ASE_WORKSPACE__.activeSessionId);
                    return child && child!==window.__oldProjectChild
                        && entry?.appInstance===child;
                }''')
                assert page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .state.display.atomRadiusScale''') == pytest.approx(0.95)
                saved_as = page.evaluate('''async () => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        .contentWindow.__ASE_APP__;
                    let size=0, version=1;
                    const handle={name:'after-save-as.vase',
                        isSameEntry:async()=>false,
                        getFile:async()=>({size,lastModified:version}),
                        createWritable:async()=>({
                            write:async blob=>{size=blob.size;},
                            close:async()=>{version+=1;}
                        })};
                    window.__afterSaveAsHandle=handle;
                    child.filePickerAdapter={showSaveFilePicker:async()=>handle};
                    return await child.saveCompactProject({saveAs:true});
                }''')
                assert saved_as is True
                page.wait_for_function('''() => {
                    const workspace=window.__V_ASE_WORKSPACE__;
                    return workspace.tabs.get(workspace.activeSessionId)?.provenance
                        ?.filename==='after-save-as.vase';
                }''')
                assert page.evaluate('''async () => {
                    const listing=await window.v_aseAI.documents();
                    return listing.documents.find(item => item.active)?.title;
                }''') == 'after-save-as.vase'
                page.evaluate('''() => {
                    const pane=document.querySelector('.direct-document-pane:not([hidden])');
                    window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                    pane.contentWindow.location.reload();
                }''')
                page.wait_for_function('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        ?.contentWindow?.__ASE_APP__;
                    return child && child!==window.__oldProjectChild
                        && child.projectFile.filename==='after-save-as.vase';
                }''')
                assert page.evaluate('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        .contentWindow.__ASE_APP__;
                    return child.projectFile.handle===window.__afterSaveAsHandle
                        && child.state.display.atomRadiusScale===0.95
                        && child.projectFile.dirty===false;
                }''') is True
            if format_name == 'html':
                page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .openEditorRoute('export')''')
                renderer = page.frame_locator('.direct-document-pane:not([hidden])')
                renderer.locator('#renderer-framing-mode').select_option('physical')
                renderer.locator('#renderer-pixels-per-angstrom').fill('51')
                renderer.locator('#renderer-pixels-per-angstrom').press('Tab')
                page.wait_for_function('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        ?.contentWindow?.__ASE_APP__;
                    return child?.projectFile.outputProfile?.options?.pixelsPerAngstrom===51
                        && child.projectFile.dirty;
                }''')
                page.evaluate('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        .contentWindow.__ASE_APP__;
                    child.rotateCameraView('up', 17);
                    child.completeCameraViewChange('recovery-audit');
                    window.__savedCamera=child.cameraSettingsSnapshot();
                }''')
                saved_as = page.evaluate('''async () => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        .contentWindow.__ASE_APP__;
                    let size=0, version=1;
                    const handle={name:'after-save-as.html',
                        isSameEntry:async()=>false,
                        getFile:async()=>({size,lastModified:version}),
                        createWritable:async()=>({
                            write:async blob=>{size=blob.size;},
                            close:async()=>{version+=1;}
                        })};
                    window.__afterSaveAsHandle=handle;
                    child.filePickerAdapter={showSaveFilePicker:async()=>handle};
                    return await child.saveHtmlProject(child.projectFile.outputProfile,
                        {saveAs:true});
                }''')
                assert saved_as is True
                page.wait_for_function('''() => window.__V_ASE_WORKSPACE__
                    .tabs.get(window.__V_ASE_WORKSPACE__.activeSessionId)
                    ?.provenance?.filename==='after-save-as.html' ''')
                page.evaluate('''() => {
                    const pane=document.querySelector('.direct-document-pane:not([hidden])');
                    window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                    pane.contentWindow.location.reload();
                }''')
                page.wait_for_function('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        ?.contentWindow?.__ASE_APP__;
                    return child && child!==window.__oldProjectChild
                        && child.projectFile.filename==='after-save-as.html';
                }''')
                assert page.evaluate('''() => {
                    const child=document.querySelector('.direct-document-pane:not([hidden])')
                        .contentWindow.__ASE_APP__;
                    return child.projectFile.format==='html'
                        && child.projectFile.outputProfile.options.pixelsPerAngstrom===51
                        && child.projectFile.handle===window.__afterSaveAsHandle
                        && child.projectFile.dirty===false;
                }''') is True
                restored_camera = page.evaluate('''() => document.querySelector(
                    '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                        .cameraSettingsSnapshot()''')
                expected_camera = page.evaluate('window.__savedCamera')
                for key in ('position', 'target', 'up'):
                    assert restored_camera[key] == pytest.approx(expected_camera[key], abs=1e-7)
            browser.close()
    finally:
        editor.close()


def test_direct_workspace_parent_focus_shortcuts_and_http_agent_bridge():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('window.__ASE_APP__.ensureDirectWorkspace()')
            page.evaluate('window.__V_ASE_WORKSPACE__.createDocument()')
            page.wait_for_function('''() => document.querySelector('.direct-document-pane:not([hidden])')
                ?.contentWindow?.__ASE_APP__?.collaborationReady''')
            page.evaluate('''() => {
                const host=window.__ASE_APP__;
                const child=document.querySelector('.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__;
                window.__saveCalls=[];
                host.saveDocument=async()=>window.__saveCalls.push('host');
                child.saveDocument=async()=>window.__saveCalls.push('child');
            }''')
            page.locator('.direct-document-tab.active .direct-document-select').click()
            before_camera = page.evaluate('''() => document.querySelector(
                '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                    .cameraSettingsSnapshot().position''')
            page.keyboard.press('ArrowLeft')
            after_camera = page.evaluate('''() => document.querySelector(
                '.direct-document-pane:not([hidden])').contentWindow.__ASE_APP__
                    .cameraSettingsSnapshot().position''')
            assert after_camera != pytest.approx(before_camera, abs=1e-8)
            page.keyboard.press('Meta+s')
            assert page.evaluate('window.__saveCalls') == ['child']
            assert page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const entry=workspace.tabs.get(workspace.activeSessionId);
                const child=entry.pane.contentWindow.__ASE_APP__;
                entry.dirty=false;
                child.pendingApplyInFlight=true;
                const event=new Event('beforeunload',{cancelable:true});
                window.dispatchEvent(event);
                child.pendingApplyInFlight=false;
                return event.defaultPrevented;
            }''') is True
            response = page.evaluate('''async () => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const result=await fetch(`/api/ai/command/workspace/${workspace.workspaceId}`, {
                    method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({method:'documents',timeout_seconds:5})
                });
                return {status:result.status,body:await result.json()};
            }''')
            assert response['status'] == 200
            assert len(response['body']['result']['documents']) == 2
            assert all(isinstance(item['title'], str) and item['title']
                       for item in response['body']['result']['documents'])
            assert [item['title'] for item in response['body']['result']['documents']] == page.evaluate('''() =>
                [...window.__V_ASE_WORKSPACE__.tabs.values()].map(entry => entry.name)
            ''')
            page.evaluate('window.__V_ASE_WORKSPACE__.closeDocument(window.__ASE_APP__.sessionId)')
            assert page.evaluate('''async () => {
                const listing=await window.v_aseAI.documents();
                return listing.documents.length===1 && (await window.v_aseAI.describe()).protocol;
            }''')
            browser.close()
    finally:
        editor.close()
