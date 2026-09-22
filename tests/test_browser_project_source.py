"""Opened local projects retain a conflict-safe server write-back target."""

import base64
import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.project import read_project_archive, write_project_archive
from v_ase.session import EditorSession, sessions
from v_ase.viewer import find_free_port, view
from v_ase.export import export_html_response


def test_opened_server_project_saves_exact_source_and_rejects_external_change(tmp_path):
    source = tmp_path / "opened.vase"
    atoms = Atoms("H", positions=[[0, 0, 0]])
    seed = EditorSession("project-seed", atoms.copy(), atoms.copy(),
                         config={"viz_only": True})
    write_project_archive(source, seed, {"display": {"atomRadiusScale": 0.6}})
    editor = view(atoms, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    sessions[editor.session_id].config["launch_directory"] = str(tmp_path)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            result = page.evaluate("""async () => {
                const app=window.__ASE_APP__;
                await app.loadStructureFile({name:'opened.vase'}, '', ':', null,
                    {path:'opened.vase',throwErrors:true});
                app.openEditorRoute('appearance');
                const slider=document.getElementById('atom-radius-scale');
                slider.value='0.8';
                slider.dispatchEvent(new Event('input',{bubbles:true}));
                return {binding:app.projectFile.serverBinding,
                    saved:await app.saveDocument(),kind:app.projectFile.lastSaveKind};
            }""")
            assert result["binding"]["id"]
            assert result["saved"] is True
            assert result["kind"] == "server-source"
            assert read_project_archive(source).settings["display"]["atomRadiusScale"] == pytest.approx(0.8)
            source.write_bytes(b"external")
            assert page.evaluate("window.__ASE_APP__.saveDocument()") is False
            assert source.read_bytes() == b"external"
            assert page.locator('#project-save-status').is_visible()
            assert 'changed outside' in page.locator('#project-save-error-text').inner_text()
            browser.close()
    finally:
        editor.close()


def test_replace_current_requires_save_discard_cancel_for_dirty_document():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.markProjectSavedContent();
                app.state.display.atomRadiusScale=0.8;
                app.renderer.setDisplayOptions({atomRadiusScale:0.8});
                const file=new File(['2\\nnew\\nHe 0 0 0\\nHe 1 0 0\\n'],
                    'new.xyz',{type:'text/plain'});
                window.__replaceResult='pending';
                app.loadStructureFile(file,'xyz',':','view',{throwErrors:true})
                    .then(value=>window.__replaceResult=value);
            }''')
            page.locator('#modal-keep-editing').click()
            page.wait_for_function('window.__replaceResult === false')
            assert page.evaluate('window.__ASE_APP__.state.atoms.positions.length') == 1
            assert page.evaluate('window.__ASE_APP__.projectFile.dirty') is True
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('format_name', ['xyz', 'vase', 'html'])
def test_same_tab_load_establishes_new_clean_baseline_after_request_settles(tmp_path, format_name):
    replacement = Atoms('He', positions=[[0, 0, 0]])
    if format_name == 'xyz':
        raw = b'1\nreplacement\nHe 0 0 0\n'
    else:
        seed = EditorSession('same-tab-seed', replacement.copy(), replacement.copy(),
                             config={'viz_only': True})
        settings = {'display': {'showGrid': False}, 'projectSave': {
            'format': format_name,
            'html': {'exportProfile': {'kind': 'html', 'width': 640, 'height': 480,
                                      'options': {'scaleMode': 'physical',
                                                  'pixelsPerAngstrom': 47}}}
            if format_name == 'html' else None}}
        if format_name == 'vase':
            source = tmp_path / 'replacement.vase'
            write_project_archive(source, seed, settings)
            raw = source.read_bytes()
        else:
            raw = export_html_response(seed, {'settings': settings, 'embed_project': True,
                                              'document_name': 'replacement',
                                              'export_profile': settings['projectSave']['html']['exportProfile']}).body
    encoded = base64.b64encode(raw).decode('ascii')
    editor = view(Atoms('H2', positions=[[0, 0, 0], [2, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            page.evaluate('''async ({encoded,formatName}) => {
                const bytes=Uint8Array.from(atob(encoded),char=>char.charCodeAt(0));
                const file=new File([bytes],`replacement.${formatName}`);
                await window.__ASE_APP__.loadStructureFile(file,'',':','view',
                    {throwErrors:true});
            }''', {'encoded': encoded, 'formatName': format_name})
            page.wait_for_function('window.__ASE_APP__.pendingScientificRequests.size === 0')
            loaded = page.evaluate('''() => {
                const app=window.__ASE_APP__;
                return {format:app.projectFile.format,
                    atoms:app.state.atoms.symbols,
                    current:app.projectScientificSignature(),
                    saved:app.projectFile.savedScientificSignature,
                    dirty:app.updateProjectDirtyState()};
            }''')
            assert loaded['atoms'] == ['He']
            assert loaded['format'] == (None if format_name == 'xyz' else format_name)
            assert loaded['saved'] == loaded['current']
            assert loaded['dirty'] is False
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.openEditorRoute('appearance');
                const slider=document.getElementById('atom-radius-scale');
                slider.value='0.82';
                slider.dispatchEvent(new Event('input',{bubbles:true}));
                slider.dispatchEvent(new Event('change',{bubbles:true}));
            }''')
            page.wait_for_function('window.__ASE_APP__.projectFile.dirty === true')
            page.wait_for_timeout(300)
            assert page.evaluate('window.__ASE_APP__.projectFile.dirty') is True
            browser.close()
    finally:
        editor.close()


def test_canceled_beforeunload_does_not_dispose_dirty_editor():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            result = page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.markProjectSavedContent();
                app.state.display.atomRadiusScale=0.8;
                app.updateProjectDirtyState();
                const event=new Event('beforeunload',{cancelable:true});
                const accepted=window.dispatchEvent(event);
                return {accepted,dirty:app.projectFile.dirty,disposed:app.disposed};
            }''')
            assert result == {'accepted': False, 'dirty': True, 'disposed': False}
            browser.close()
    finally:
        editor.close()


def test_html_close_save_failure_keeps_dirty_document_open():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.projectFile.format='html';
                app.markProjectSavedContent();
                app.state.display.atomRadiusScale=0.8;
                app.updateProjectDirtyState();
                app.saveHtmlProject=async()=>{throw new Error('simulated HTML write error')};
                window.__closeResult='pending';
                app.confirmDocumentClose().then(value=>window.__closeResult=value);
            }''')
            page.locator('#modal-save-document').click()
            page.wait_for_function('window.__closeResult === false')
            assert page.evaluate('window.__ASE_APP__.projectFile.dirty') is True
            assert 'simulated HTML write error' in page.locator('#project-save-error-text').inner_text()
            browser.close()
    finally:
        editor.close()


def test_save_waits_for_pending_physical_apply_before_serializing():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False,
                  viz_only=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.projectFile.format='vase';
                app.projectFile.filename='pending.vase';
                app.projectFile.serverBinding=null;
                app.projectFile.handle={name:'pending.vase',
                    getFile:async()=>({size:1,lastModified:1}),
                    createWritable:async()=>({write:async()=>{},close:async()=>{}})};
                app.projectFile.contentVersion={size:1,lastModified:1};
                window.__serializedPositions=null;
                window.__saveCalls=[];
                app.api.saveProject=async positions=>{
                    window.__saveCalls.push('blob');
                    window.__serializedPositions=positions;
                    return new Blob(['project']);
                };
                app.api.writeCurrentProject=async payload=>{
                    window.__saveCalls.push('server');
                    window.__serializedPositions=payload.positions;
                    return {version:'new',filename:'pending.vase'};
                };
                app.pendingApply=new Promise(resolve=>{window.__settleApply=resolve});
                window.__saveResult=app.saveCompactProject();
            }''')
            assert page.evaluate('window.__serializedPositions') is None
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.state.atoms.positions=[[1,0,0]];
                app.renderer.updatePositions([[1,0,0]]);
                window.__settleApply();
            }''')
            assert page.evaluate('window.__saveResult') is True
            details = page.evaluate('''() => ({calls:window.__saveCalls,
                positions:window.__serializedPositions,
                binding:window.__ASE_APP__.projectFile.serverBinding,
                kind:window.__ASE_APP__.projectFile.lastSaveKind})''')
            assert details['positions'] is not None, details
            assert details['positions'][0][0] == pytest.approx(1), details
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('reject', [False, True])
def test_confirmed_move_cannot_close_while_real_apply_is_pending_or_failed(reject):
    editor = view(Atoms('H2', positions=[[0, 0, 0], [2, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False,
                  viz_only=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.applyDisplayOptions();
                app.markProjectSavedContent();
                const realApply=app.api.applyPositions.bind(app.api);
                const gate=new Promise(resolve=>{window.__releaseApply=resolve});
                app.api.applyPositions=(positions, constraints)=>gate.then(()=>
                    window.__rejectApply
                        ? Promise.reject(new Error('deferred apply rejected'))
                        : realApply(positions,constraints));
                app.applySelectionAction({references:[1],origin:'semantic'});
                app.enterTransformMode('MOVE');
                app.transform.setAxis('X',app.renderer.camera);
                app.transform.buffer='0.5';
                app.applyTransformPreview();
                app.commitTransform().catch(()=>{});
                window.__closeResult='pending';
                app.confirmDocumentClose().then(value=>window.__closeResult=value);
            }''')
            assert page.evaluate('''() => ({
                close:window.__closeResult,
                dirty:window.__ASE_APP__.updateProjectDirtyState(),
                pending:window.__ASE_APP__.pendingApplyInFlight
            })''') == {'close': 'pending', 'dirty': True, 'pending': True}
            page.evaluate('reject => { window.__rejectApply = reject; window.__releaseApply(); }', reject)
            if reject:
                page.wait_for_function('window.__closeResult === false')
                assert page.evaluate('window.__ASE_APP__.pendingScientificError?.message') == 'deferred apply rejected'
                assert page.evaluate('window.__ASE_APP__.projectFile.dirty') is True
            else:
                page.locator('#modal-keep-editing').click()
                page.wait_for_function('window.__closeResult === false')
                assert page.evaluate('window.__ASE_APP__.projectFile.dirty') is True
            browser.close()
    finally:
        editor.close()


def test_invalid_active_scientific_draft_blocks_save_before_destination_selection():
    editor = view(Atoms('H', positions=[[0, 0, 0]], cell=[5, 5, 5], pbc=True),
                  notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False, viz_only=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.projectFile.format='vase';
                app.markProjectSavedContent();
                window.__destinations=0;
                app.projectSaveDestination=async()=>{
                    window.__destinations+=1;
                    return null;
                };
                app.openEditorRoute('cell-replication');
            }''')
            field = page.locator('#super-x')
            field.fill('0')
            field.press('Tab')
            assert page.evaluate('document.activeElement?.id') == 'super-x'
            field.press('Enter')
            assert page.evaluate('document.activeElement?.id') == 'super-x'
            assert page.evaluate('window.__ASE_APP__.saveCompactProject()') is False
            page.click('#editor-save')
            page.wait_for_function('window.__ASE_APP__.projectFile.error !== null')
            page.evaluate("window.__ASE_APP__.showHtmlExportModal({projectSave:true,saveAs:true})")
            page.click('#html-export-confirm')
            assert page.evaluate('window.__destinations') == 0
            page.evaluate('window.__ASE_APP__.closeModal()')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                app.state.display.atomRadiusScale=0.85;
                app.renderer.setDisplayOptions({atomRadiusScale:0.85});
                app.updateProjectDirtyState();
                window.__invalidClose='pending';
                app.confirmDocumentClose().then(value=>window.__invalidClose=value);
            }''')
            page.locator('#modal-save-document').click()
            page.wait_for_function('window.__invalidClose === false')
            assert page.evaluate('window.__destinations') == 0
            assert field.input_value() == '0'
            assert page.evaluate('window.__ASE_APP__.state.display.supercell[0]') == 1
            browser.close()
    finally:
        editor.close()


def test_html_renderer_undo_restores_visible_and_saved_output_profile():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
            page.evaluate('''() => {
                const app=window.__ASE_APP__;
                const base=app.currentImageExportProfile();
                const imageProfile=app.normalizedImageExportProfile({
                    ...base,width:640,height:480,
                    options:{...base.options,scaleMode:'physical',pixelsPerAngstrom:75}
                });
                const htmlProfile=app.htmlExportProfile({
                    ...imageProfile,
                    options:{...imageProfile.options,pixelsPerAngstrom:100}
                });
                app.setImageExportProfile(imageProfile);
                let size=1, version=1;
                window.__writtenHtml=null;
                const handle={name:'audit.html',
                    queryPermission:async()=> 'granted',
                    getFile:async()=>({size,lastModified:version}),
                    createWritable:async()=>({
                        write:async blob=>{window.__writtenHtml=blob;size=blob.size;},
                        close:async()=>{version+=1;}
                    })};
                app.adoptProjectProvenance({format:'html',filename:'audit.html',
                    handle,contentVersion:{size,lastModified:version},outputProfile:htmlProfile});
                app.openEditorRoute('export');
                const original=app.api.exportHtml.bind(app.api);
                app.api.exportHtml=async (...args)=>{
                    window.__sentHtmlProfile=args[6];
                    window.__sentImageProfile=args[1].imageExportProfile;
                    return await original(...args);
                };
            }''')
            scale = page.locator('#renderer-pixels-per-angstrom')
            scale.fill('200')
            scale.press('Tab')
            page.evaluate('window.__ASE_APP__.flushVisualHistoryCommit()')
            changed = page.evaluate('''() => ({
                image:window.__ASE_APP__.currentImageExportProfile().options.pixelsPerAngstrom,
                html:window.__ASE_APP__.projectFile.outputProfile.options.pixelsPerAngstrom
            })''')
            assert changed == {'image': 200, 'html': 200}
            page.evaluate('window.__ASE_APP__.performUndo()')
            undone = page.evaluate('''() => ({
                image:window.__ASE_APP__.currentImageExportProfile().options.pixelsPerAngstrom,
                html:window.__ASE_APP__.projectFile.outputProfile.options.pixelsPerAngstrom,
                visible:document.getElementById('renderer-pixels-per-angstrom').value
            })''')
            assert undone == {'image': 75, 'html': 100, 'visible': '75.00'}
            page.evaluate('window.__ASE_APP__.performRedo()')
            assert page.evaluate('''() => ({
                image:window.__ASE_APP__.currentImageExportProfile().options.pixelsPerAngstrom,
                html:window.__ASE_APP__.projectFile.outputProfile.options.pixelsPerAngstrom
            })''') == {'image': 200, 'html': 200}
            page.evaluate('window.__ASE_APP__.performUndo()')
            assert page.evaluate('window.__ASE_APP__.saveHtmlProject()') is True
            saved = page.evaluate('''() => ({
                sent:window.__sentHtmlProfile?.options?.pixelsPerAngstrom,
                image:window.__sentImageProfile?.options?.pixelsPerAngstrom,
                size:window.__writtenHtml?.size,
                dirty:window.__ASE_APP__.updateProjectDirtyState()
            })''')
            assert saved['sent'] == 100
            assert saved['image'] == 75
            assert saved['size'] > 1000
            assert saved['dirty'] is False
            browser.close()
    finally:
        editor.close()
