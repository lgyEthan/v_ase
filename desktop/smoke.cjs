'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { Menu, nativeImage, BrowserWindow } = require('electron');

async function runSmoke({ app, win, handshake, vault, sendCommand }) {
    const output = process.env.V_ASE_SMOKE_DIR || path.join(__dirname, 'smoke-output');
    await fs.mkdir(output, { recursive: true });
    const js = async code => {
        try { return await win.webContents.executeJavaScript(code); }
        catch (error) { throw new Error(`${error.message}\nExpression: ${code}`); }
    };
    const active = 'window.__V_ASE_WORKSPACE__.tabs.get(window.__V_ASE_WORKSPACE__.activeSessionId).pane.contentWindow';
    const appRef = `${active}.__ASE_APP__`;
    const modifier = process.platform === 'darwin' ? 'meta' : 'control';
    async function key(keyCode, shift = false) {
        win.show(); win.focus(); win.webContents.focus();
        const modifiers = [modifier, ...(shift ? ['shift'] : [])];
        win.webContents.sendInputEvent({ type: 'keyDown', keyCode, modifiers });
        win.webContents.sendInputEvent({ type: 'keyUp', keyCode, modifiers });
    }
    async function wait(expression, timeoutMs = process.env.V_ASE_SOFTWARE_GL === '1' ? 60000 : 10000) {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            if (await js(`Boolean(${expression})`)) return;
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        const state = await js(`(()=>{const f=${active};return {focus:f.document.activeElement?.id,selection:[...f.__ASE_APP__.state.selected],key:f.__smokeKey,modal:f.document.querySelector('#modal-content')?.textContent};})()`);
        throw new Error(`Timed out: ${expression}\n${JSON.stringify(state)}\n${JSON.stringify(await js('window.__smokePointer || []'))}`);
    }
    async function api(method, params = {}) {
        const response = await fetch(handshake.command_url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ method, params }) });
        if (!response.ok) throw new Error(await response.text());
        return (await response.json()).result;
    }
    async function open(filename, newTab = false) {
        const dialog = require('electron').dialog;
        const original = dialog.showOpenDialog;
        dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [filename] });
        try { await js("window.__vaseDesktopHost.command('open')"); }
        finally { dialog.showOpenDialog = original; }
        if (newTab) {
            const count = await js('window.__V_ASE_WORKSPACE__.tabs.size');
            await js(`${active}.document.querySelector('[name="open-file-mode"][value="new-tab"]').checked=true; ${active}.document.querySelector('#open-file-confirm').click()`);
            await wait(`window.__V_ASE_WORKSPACE__.tabs.size === ${count + 1}`);
            await wait(`${appRef}?.collaborationReady && ${appRef}.projectFile.handle?.desktopToken`);
            return;
        }
        const dirty = await js(`${appRef}.updateProjectDirtyState()`);
        await js(`(()=>{ const a=${appRef}; const original=a.loadStructureFile.bind(a); a.loadStructureFile=(...args)=>{ a.loadStructureFile=original; window.__smokeLoaded=original(...args); return window.__smokeLoaded; }; })()`);
        await js(`${active}.document.querySelector('#open-file-confirm').click()`);
        if (dirty) {
            await wait(`${active}.document.querySelector('#modal-discard-document')`);
            await js(`${active}.document.querySelector('#modal-discard-document').click()`);
        }
        await js('window.__smokeLoaded');
        await wait(`${appRef}.state.atoms.positions.length === 3`);
    }
    await wait(`${appRef}?.collaborationReady`);
    const originalMessageBox = require('electron').dialog.showMessageBox;
    let about;
    require('electron').dialog.showMessageBox = async (_window, options) => {
        about = options;
        return { response: 0 };
    };
    try { await Menu.getApplicationMenu().getMenuItemById('about-runtime').click(); }
    finally { require('electron').dialog.showMessageBox = originalMessageBox; }
    assert.equal(about.message, `v_ase ${app.getVersion()}`);
    assert.equal(about.title, about.message);
    assert.equal(await js('typeof require'), 'undefined');
    assert.equal(await js(`${active}.vaseDesktop`), undefined);
    const fixture = path.join(output, 'desktop-fixture.xyz');
    await fs.writeFile(fixture, '3\nDesktop fixture\nO 0 0 0\nH 0.95 0 0\nH -0.2 0.9 0\n');
    // A real OS-backed File from Chromium, not a renderer-supplied pathname.
    await js(`(()=>{const input=document.createElement('input'); input.type='file'; input.id='smoke-drop-file'; input.hidden=true; document.body.append(input);})()`);
    win.webContents.debugger.attach('1.3');
    try {
        const root = await win.webContents.debugger.sendCommand('DOM.getDocument');
        const node = await win.webContents.debugger.sendCommand('DOM.querySelector', { nodeId: root.root.nodeId, selector:'#smoke-drop-file' });
        await win.webContents.debugger.sendCommand('DOM.setFileInputFiles', { nodeId:node.nodeId, files:[fixture] });
        const dropped = await js("window.vaseDesktop.openDropped(document.getElementById('smoke-drop-file').files[0])");
        assert.equal(dropped.name, 'desktop-fixture.xyz');
        assert.ok(dropped.token && !dropped.path);
        assert.equal(await js("window.vaseDesktop.openDropped(new File(['x'],'fake.xyz'))"), null);
    } finally { win.webContents.debugger.detach(); await js("document.getElementById('smoke-drop-file').remove()"); }
    await open(fixture);
    assert.equal(await js(`${appRef}.state.atoms.positions.length`), 3);
    const routes = { supercell: 'cell-replication', appearance: 'appearance', bonding: 'bonding', renderer: 'export', 'cell-transform': 'cell-transform' };
    for (const [command, route] of Object.entries(routes)) {
        Menu.getApplicationMenu().getMenuItemById(command).click();
        await wait(`${active}.document.body.dataset.currentEditorRoute === ${JSON.stringify(route)}`);
    }
    // Use Chromium's native key-input path as well as explicit menu actions.
    const chords = { supercell: ['B', true], appearance: ['P', true], bonding: ['B', false],
        renderer: ['A', true], 'cell-transform': ['E', false] };
    for (const [command, chord] of Object.entries(chords)) {
        await key(...chord);
        await wait(`${active}.document.body.dataset.currentEditorRoute === ${JSON.stringify(routes[command])}`);
    }
    // Output-camera UI must not let an invalid numeric draft trap native routing.
    await key('A', true);
    await wait(`${active}.document.body.dataset.currentEditorRoute === 'export'`);
    await js(`${active}.document.querySelector('#btn-preview-image').click()`);
    const outputScaleBefore = await js(`${appRef}.currentImageExportProfile().options.pixelsPerAngstrom`);
    await js(`(()=>{const f=${active},x=f.document.querySelector('#renderer-pixels-per-angstrom');
        x.focus();x.value='-2';x.dispatchEvent(new f.Event('input',{bubbles:true}));})()`);
    await key('P', true);
    await wait(`${active}.document.body.dataset.currentEditorRoute === 'appearance'`);
    assert.equal(await js(`${appRef}.currentImageExportProfile().options.pixelsPerAngstrom`), outputScaleBefore);
    await key('A', true);
    await wait(`${active}.document.body.dataset.currentEditorRoute === 'export'`);
    await js(`${active}.document.querySelector('#btn-render-area-from-view').click()`);
    assert.equal(await js(`${appRef}.state.exportPreviewFollowViewport`), false);
    await js(`${active}.document.querySelector('#btn-preview-image').click()`);
    await js(`new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`);
    await js(`${active}.addEventListener('keydown',e=>{${active}.__smokeKey={code:e.code,key:e.key,meta:e.metaKey,ctrl:e.ctrlKey,prevented:e.defaultPrevented,target:e.target.id}}); ${appRef}.renderer.domElement.focus()`);
    await key('A');
    await wait(`${appRef}.state.selected.size === 3`);
    await js(`${active}.document.querySelector('#matrix-00').focus()`);
    await key('A');
    assert.equal(await js(`${appRef}.state.selected.size`), 3);
    for (const command of ['save', 'save-as']) {
        await key('S', command === 'save-as');
        await wait(`!${active}.document.querySelector('#modal-container').classList.contains('hidden')`);
        assert.match(await js(`${active}.document.querySelector('#modal-title').textContent`), /Save/);
        await js(`${appRef}.closeModal()`);
    }
    const source = await api('export', { format: 'project' });
    const saved = path.join(output, 'desktop-source.vase');
    await fs.writeFile(saved, Buffer.from(source.dataUrl.split(',')[1], 'base64'));
    await open(saved);
    await wait(`${appRef}.projectFile.format === 'vase'`);
    assert.equal(await js(`${appRef}.projectFile.format`), 'vase');
    await js(`(()=>{ const frame=${active}; const a=frame.__ASE_APP__; const input=frame.document.querySelector('#atom-radius-scale-number'); input.value='0.8'; input.dispatchEvent(new frame.Event('change',{bubbles:true})); a.updateProjectDirtyState(); })()`);
    assert.equal(await js(`${appRef}.projectFile.dirty`), true);
    await key('S');
    await wait(`!${appRef}.projectFile.dirty && !${appRef}.projectFile.savePromise`);
    assert.equal(await js(`${active}.document.querySelector('#modal-container').classList.contains('hidden')`), true);
    const target = path.join(output, 'desktop-copy.vase');
    const prior = await fs.readFile(saved);
    // Exercise the context-isolated file IPC and streaming handle via the real picker adapter.
    const originalDialog = require('electron').dialog.showSaveDialog;
    require('electron').dialog.showSaveDialog = async () => ({ canceled: false, filePath: target });
    try {
        assert.equal(await js(`${appRef}.saveCompactProject({saveAs:true})`), true);
        assert.equal((await fs.readFile(target)).subarray(0, 2).toString(), 'PK');
        assert.deepEqual(await fs.readFile(saved), prior);
    } finally { require('electron').dialog.showSaveDialog = originalDialog; }
    await open(target, true);
    assert.equal(await js(`${appRef}.state.atoms.positions.length`), 3);
    await key('W');
    await wait('window.__V_ASE_WORKSPACE__.tabs.size === 1');
    await wait(`${appRef}?.collaborationReady`);
    const html = path.join(output, 'desktop-project.html');
    require('electron').dialog.showSaveDialog = async () => ({ canceled: false, filePath: html });
    try {
        assert.equal(await js(`(()=>{ const a=${appRef}; return a.saveHtmlProject({...a.htmlExportProfile(),width:720,height:480},{saveAs:true}); })()`), true);
    } finally { require('electron').dialog.showSaveDialog = originalDialog; }
    await open(html);
    assert.equal(await js(`${appRef}.projectFile.format`), 'html');
    assert.equal(await js(`${appRef}.projectFile.outputProfile.width`), 720);
    await js(`(()=>{const f=${active}; const input=f.document.querySelector('#atom-radius-scale-number'); input.value='0.9'; input.dispatchEvent(new f.Event('change',{bubbles:true})); f.__ASE_APP__.updateProjectDirtyState(); window.__smokeQuit=window.__vaseDesktopHost.confirmQuit(); })()`);
    await wait(`${active}.document.querySelector('#modal-keep-editing')`);
    await js(`${active}.document.querySelector('#modal-keep-editing').click()`);
    assert.equal(await js('window.__smokeQuit'), false);
    assert.equal(win.isDestroyed(), false);
    await key('S');
    await wait(`!${appRef}.projectFile.dirty && !${appRef}.projectFile.savePromise`);
    assert.equal(await js(`${appRef}.projectFile.format`), 'html');
    assert.equal(await js(`${appRef}.projectFile.outputProfile.width`), 720);
    assert.match((await fs.readFile(html, 'utf8')).slice(0, 100), /html/i);
    const render = await api('render', { format: 'png', width: 800, height: 600 });
    assert.equal(render.width, 800); assert.equal(render.height, 600);
    const bitmap = nativeImage.createFromDataURL(render.dataUrl).toBitmap();
    let oxygenPixels = 0;
    for (let i = 0; i < bitmap.length; i += 4) {
        if (bitmap[i + 2] > bitmap[i] + 40 && bitmap[i + 2] > bitmap[i + 1] + 40) oxygenPixels++;
    }
    assert.ok(oxygenPixels > 100, 'The exported image must contain the red oxygen atom, not a blank canvas');
    await fs.writeFile(path.join(output, 'render.png'), Buffer.from(render.dataUrl.split(',')[1], 'base64'));
    await key('N');
    await wait('window.__V_ASE_WORKSPACE__.tabs.size === 2');
    await wait(`${appRef}?.collaborationReady`);
    await key('W');
    await wait('window.__V_ASE_WORKSPACE__.tabs.size === 1');
    assert.equal(win.isDestroyed(), false);
    await wait(`${appRef}?.collaborationReady`);
    let geometryRoutes = 0;
    for (const [width, height] of [[1440,960], [1024,768], [390,844]]) {
        win.setContentSize(width, height);
        const geometry = await js(`(async()=>{
            const f=${active}, d=f.document, issues=[];
            let routes=0;
            const visible=element=>element.getClientRects().length && f.getComputedStyle(element).visibility!=='hidden';
            for (const group of d.querySelectorAll('#workbench-tabs [data-workbench]')) {
                group.click();
                for (const button of d.querySelectorAll('#workbench-tools [data-editor-route]')) {
                    if (!visible(button)) continue;
                    button.click(); routes++;
                    await new Promise(resolve=>f.requestAnimationFrame(()=>f.requestAnimationFrame(resolve)));
                    const inspector=d.getElementById('inspector').getBoundingClientRect();
                    if (d.documentElement.scrollWidth>f.innerWidth+1) issues.push('page overflow');
                    for (const element of d.querySelectorAll('#inspector-content input,#inspector-content select,#inspector-content textarea,#inspector-content button')) {
                        if (!visible(element) || element.type==='hidden') continue;
                        const table=element.closest('#appearance-table');
                        if (table) {
                            const box=table.getBoundingClientRect();
                            if (box.left<inspector.left-1 || box.right>inspector.right+1 || f.getComputedStyle(table).overflowX!=='auto') issues.push('label table overflow');
                            continue;
                        }
                        const r=element.getBoundingClientRect();
                        if (r.width && (r.left<inspector.left-1 || r.right>inspector.right+1)) issues.push(element.id || element.className);
                    }
                    for (const unit of d.querySelectorAll('#inspector .unit-input')) {
                        if (!visible(unit)) continue;
                        const input=unit.querySelector('input'), label=unit.querySelector(':scope > span');
                        if (!input || !label) continue;
                        const a=input.getBoundingClientRect(), b=label.getBoundingClientRect(), box=unit.getBoundingClientRect();
                        if (a.right>b.left+1 || b.right>box.right+1 || a.left<box.left-1 || b.bottom>box.bottom+1) issues.push('unit:'+input.id);
                    }
                }
            }
            f.__ASE_APP__.openEditorRoute('appearance');
            return {routes,issues};
        })()`);
        assert.equal(geometry.routes, 23, `All tools must remain visible at ${width}px`);
        assert.deepEqual(geometry.issues, [], `Clipped controls/units at ${width}px`);
        geometryRoutes += geometry.routes;
        await fs.writeFile(path.join(output, `workspace-${width}.png`), (await win.webContents.capturePage()).toPNG());
    }
    win.setContentSize(1440,960);
    await fs.writeFile(path.join(output, 'workspace.png'), (await win.webContents.capturePage()).toPNG());
    // Real native Ctrl+A (also on macOS) and one-Tab cutoff editing.
    await js(`${appRef}.openEditorRoute('bonding')`);
    await js(`(()=>{const d=${active}.document; const input=d.querySelector('.pairwise-bond-max'); input.focus(); input.value='1.234'; })()`);
    win.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'A', modifiers: ['control'] });
    win.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'A', modifiers: ['control'] });
    win.webContents.insertText('2');
    await wait(`${active}.document.querySelector('.pairwise-bond-max').value === '2'`);
    win.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Tab' });
    win.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Tab' });
    await wait(`${active}.document.activeElement === ${active}.document.querySelectorAll('.pairwise-bond-max')[1]`);
    win.webContents.insertText('2.5');
    await wait(`${active}.document.querySelectorAll('.pairwise-bond-max')[1].value === '2.5'`);
    await js(`${active}.document.activeElement.blur()`);
    // Numeric edits are applied on the next animation frame. Scientific HTTP
    // settlement alone does not drain these display callbacks. Compare history
    // only after the tested edits have actually reached the document model.
    await wait(`${appRef}.state.displayApplyRequest === null && ${appRef}.state.bondApplyRequest === null`);
    await js(`${appRef}.settleScientificMutations().then(()=>${appRef}.flushVisualHistoryCommit())`);
    assert.equal(await js(`${appRef}.state.display.pairwiseBondRanges['H-O'].max`), 2.5);
    const movedId = await js(`${appRef}.sessionId`);
    const documentState = `({format:${appRef}.projectFile.format, filename:${appRef}.projectFile.filename,
        positions:${appRef}.renderer.currentPositions(), camera:${appRef}.cameraSettingsSnapshot(),
        pixelsPerAngstrom:${appRef}.renderer.currentPixelsPerAngstrom(),
        undo:${appRef}.undoTimeline.length, dirty:${appRef}.updateProjectDirtyState()})`;
    const beforeMove = await js(documentState);
    const beforeHistory = await js(`({undo:${appRef}.undoTimeline, pending:${appRef}.visualHistoryPending, displayRAF:${appRef}.state.displayApplyRequest,bondRAF:${appRef}.state.bondApplyRequest})`);
    const tabPoint = await js(`(()=>{const r=window.__V_ASE_WORKSPACE__.tabs.get('${movedId}').select.getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)};})()`);
    await js(`(() => { window.__smokePointer=[]; for (const d of [document,${active}.document]) for(const type of ['pointerdown','pointermove','pointerup','click']) d.addEventListener(type,e=>window.__smokePointer.push({type,target:e.target.className,x:e.clientX,y:e.clientY,top:d===document}),true); })()`);
    win.show(); win.focus(); win.webContents.focus();
    win.webContents.sendInputEvent({ type: 'mouseMove', ...tabPoint });
    win.webContents.sendInputEvent({ type: 'mouseDown', ...tabPoint, button: 'left', clickCount: 1 });
    await js('new Promise(resolve => requestAnimationFrame(resolve))');
    win.webContents.sendInputEvent({ type: 'mouseMove', x:tabPoint.x+70, y:tabPoint.y+140, modifiers:['leftbuttondown'] });
    await js('new Promise(resolve => requestAnimationFrame(resolve))');
    win.webContents.sendInputEvent({ type: 'mouseUp', x:tabPoint.x+70, y:tabPoint.y+140, button:'left', clickCount:1 });
    await wait(`!window.__V_ASE_WORKSPACE__.tabs.has('${movedId}')`, 60000);
    const detached = BrowserWindow.getAllWindows().find(candidate => candidate !== win);
    assert.ok(detached, 'Dragging a tab creates a second native window');
    const detachedJS = code => detached.webContents.executeJavaScript(code);
    const detachedWorkspaceId = new URL(detached.webContents.getURL()).searchParams.get('workspace_id');
    const afterMove = await detachedJS(documentState);
    const afterHistory = await detachedJS(`({undo:${appRef}.undoTimeline, pending:${appRef}.visualHistoryPending})`);
    await fs.writeFile(path.join(output, 'detached-state.json'), JSON.stringify({beforeMove, afterMove, beforeHistory, afterHistory}, null, 2));
    assert.ok(Math.abs(afterMove.pixelsPerAngstrom - beforeMove.pixelsPerAngstrom) < 0.001,
        'Detach preserves physical magnification even when the OS fits the new window to the screen');
    // Raw orthographic zoom/span depend on viewport height. Windows may clamp a
    // newly created window to the work area; compare physical scale above and
    // preserve all remaining camera/scientific/document state exactly.
    const comparable = state => {
        const { pixelsPerAngstrom, ...value } = structuredClone(state);
        if (value.camera.projection === 'orthographic') {
            delete value.camera.zoom;
            delete value.camera.ortho_scale;
        }
        return value;
    };
    assert.deepEqual(comparable(afterMove), comparable(beforeMove), 'Detach preserves visual state, history, dirty state and the save format');
    assert.deepEqual(afterHistory.undo, beforeHistory.undo, 'Detach preserves every committed undo action exactly');
    assert.ok(await detachedJS(`${appRef}.projectFile.handle?.desktopToken`), 'Native file grant moves with the tab');
    await detachedJS(`${appRef}.saveDocument()`);
    assert.equal(await detachedJS(`${appRef}.updateProjectDirtyState()`), false);
    await fs.writeFile(path.join(output, 'detached-window.png'), (await detached.webContents.capturePage()).toPNG());
    const quittingOther = new Promise(resolve => detached.once('closed', resolve));
    detached.close(); await quittingOther;
    assert.equal(win.isDestroyed(), false, 'Closing the detached window leaves the original window running');
    assert.equal((await fetch(`${new URL(handshake.human_url).origin}/api/workspace/${detachedWorkspaceId}`)).status, 400,
        'Closing a native window releases its backend workspace');
    await js(`window.__V_ASE_WORKSPACE__.createDocument()`);
    await wait('window.__V_ASE_WORKSPACE__.tabs.size === 2');
    await wait(`${appRef}?.collaborationReady`);
    // Failure injection must follow native adapter installation; otherwise its
    // document-ready handler can replace the injected function during startup.
    await wait(`${appRef}.workspaceRecoveryAcknowledged && typeof ${appRef}.openWorkspaceWindow === 'function'`);
    const rollbackId = await js(`${appRef}.sessionId`);
    assert.equal(await js(`(async()=>{
        const a=${appRef}, original=a.openWorkspaceWindow;
        a.openWorkspaceWindow=async()=>{throw new Error('smoke-destination-failure')};
        try { await window.__vaseDesktopHost.detach(a.sessionId); return 'unexpected-success'; }
        catch(e){return e.message}
        finally {a.openWorkspaceWindow=original}
    })()`), 'smoke-destination-failure');
    assert.equal(await js(`window.__V_ASE_WORKSPACE__.tabs.has('${rollbackId}') && !${active}.document.body.inert`), true);
    const nativeDialog = require('electron').dialog;
    const previousOpen = nativeDialog.showOpenDialog;
    nativeDialog.showOpenDialog = async()=>({canceled:false,filePaths:[html]});
    try { await js("window.__vaseDesktopHost.command('open')"); }
    finally { nativeDialog.showOpenDialog=previousOpen; }
    await js(`${active}.document.querySelector('[name="open-file-mode"][value="new-window"]').checked=true; ${active}.document.querySelector('#open-file-confirm').click()`);
    let openedWindow, openedState;
    const openDeadline = Date.now() + 60000;
    while (Date.now() < openDeadline) {
        openedWindow=BrowserWindow.getAllWindows().find(candidate=>candidate!==win);
        openedState=openedWindow && await openedWindow.webContents.executeJavaScript(`(()=>{const w=window.__V_ASE_WORKSPACE__,a=w?.tabs.get(w.activeSessionId)?.pane?.contentWindow?.__ASE_APP__;return a?.collaborationReady && a.projectFile.handle?.desktopToken ? {format:a.projectFile.format,width:a.projectFile.outputProfile?.width,count:a.state.atoms.positions.length} : null;})()`).catch(()=>null);
        if(openedState) break;
        await new Promise(resolve=>setTimeout(resolve,50));
    }
    assert.deepEqual(openedState,{format:'html',width:720,count:3},'Open in new window restores the project and native target');
    const openedClosed=new Promise(resolve=>openedWindow.once('closed',resolve));
    openedWindow.close(); await openedClosed;
    assert.equal(win.isDestroyed(),false);
    const result = { version: app.getVersion(), platform: process.platform, architecture: process.arch,
        commands: 10, nativeControlA: true, verticalCutoffTab: true, droppedFileGrant: true, detachedWindow: true, detachedSave: true, transferRollback: true, openNewWindow: true, independentWindowClose: true, nativeKeyInput: true, nativeSave: true, scientificProject: true,
        htmlProfile: [720,480], openNewTab: true, quitCancellation: true, render: [800, 600],
        oxygenPixels, geometryRoutes, nodeIsolation: true };
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
}
module.exports = { runSmoke };
