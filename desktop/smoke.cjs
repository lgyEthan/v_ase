'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { Menu } = require('electron');

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
    async function wait(expression) {
        for (let i = 0; i < 200; i++) {
            if (await js(`Boolean(${expression})`)) return;
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        const state = await js(`(()=>{const f=${active};return {focus:f.document.activeElement?.id,selection:[...f.__ASE_APP__.state.selected],key:f.__smokeKey,modal:f.document.querySelector('#modal-content')?.textContent};})()`);
        throw new Error(`Timed out: ${expression}\n${JSON.stringify(state)}`);
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
    assert.equal(await js('typeof require'), 'undefined');
    assert.equal(await js(`${active}.vaseDesktop`), undefined);
    const fixture = path.join(output, 'desktop-fixture.xyz');
    await fs.writeFile(fixture, '3\nDesktop fixture\nO 0 0 0\nH 0.95 0 0\nH -0.2 0.9 0\n');
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
    await fs.writeFile(path.join(output, 'render.png'), Buffer.from(render.dataUrl.split(',')[1], 'base64'));
    await key('N');
    await wait('window.__V_ASE_WORKSPACE__.tabs.size === 2');
    await wait(`${appRef}?.collaborationReady`);
    await key('W');
    await wait('window.__V_ASE_WORKSPACE__.tabs.size === 1');
    assert.equal(win.isDestroyed(), false);
    await wait(`${appRef}?.collaborationReady`);
    await fs.writeFile(path.join(output, 'workspace.png'), (await win.webContents.capturePage()).toPNG());
    const result = { version: app.getVersion(), platform: process.platform, architecture: process.arch,
        commands: 9, nativeKeyInput: true, nativeSave: true, scientificProject: true,
        htmlProfile: [720,480], openNewTab: true, quitCancellation: true, render: [800, 600], nodeIsolation: true };
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
}
module.exports = { runSmoke };
