'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { dialog, BrowserWindow } = require('electron');
module.exports = async ({ app, win, js, active, appRef, wait, key, output, openQueue }) => {
    const ws = 'window.__V_ASE_WORKSPACE__';
    const originalId = await js(`${ws}.activeSessionId`);
    const originalIds = await js(`[...${ws}.tabs.keys()]`);
    const count = originalIds.length, windows = BrowserWindow.getAllWindows().length;
    const files = [];
    for (const n of [10,2,1]) {
        const filename = path.join(output, `step-${n}.vasp`);
        await fs.writeFile(filename, `batch ${n}\n1\n4 1 0\n1 5 1\n1 2 6\nH\n1\nCartesian\n${n/10} 0 0\n`);
        files.push(filename);
    }
    async function choose() {
        let invoked = false;
        const previous = dialog.showOpenDialog;
        dialog.showOpenDialog = async (_target, options) => {
            invoked = true;
            assert.ok(options.properties.includes('multiSelections'));
            return { canceled: false, filePaths: files };
        };
        try {
            await key('O');
            const deadline = Date.now()+10000;
            while (!invoked && Date.now()<deadline) await new Promise(r=>setTimeout(r,20));
            assert.ok(invoked, 'Native Open shortcut must invoke the multi-file picker');
            await wait(`${active}.document.querySelector('#open-batch-confirm') && !${active}.document.querySelector('#modal-container').classList.contains('hidden')`);
        }
        finally { dialog.showOpenDialog = previous; }
    }
    await choose();
    assert.deepEqual(await js(`[...${active}.document.querySelectorAll('#open-batch-files li > span')].map(n=>n.textContent)`), ['step-1.vasp','step-2.vasp','step-10.vasp']);
    await fs.writeFile(path.join(output, 'multi-file-choice.png'), (await win.webContents.capturePage()).toPNG());
    await js(`${active}.document.querySelector('#open-batch-cancel').click()`);
    await wait('!window.__vaseFileOpenQueue.running');
    assert.equal(await js(`${ws}.tabs.size`), count);
    await choose();
    await js(`${active}.document.querySelector('[name=open-batch-mode][value=trajectory]').click(); ${active}.document.querySelector('#open-batch-confirm').click()`);
    await wait(`${ws}.tabs.size === ${count+1} && ${appRef}?.workspaceRecoveryAcknowledged && ${appRef}.state.atoms.metadata.frame_count === 3`);
    assert.equal(await js(`${appRef}.updateProjectDirtyState() && !${appRef}.projectFile.handle && !${appRef}.projectFile.format`), true);
    assert.ok(Math.abs(await js(`${appRef}.state.atoms.positions[0][0]`) - .1) < 1e-8);
    // Exercise native unmodified keys in a skewed cell, then primary+A selection.
    await js(`${appRef}.renderer.domElement.focus()`);
    for (const [letter, vector] of [['A',[4,1,0]],['B',[1,5,1]],['C',[1,2,6]]]) {
        const expected = vector.map(v=>v/Math.hypot(...vector));
        for (const sign of [1,-1]) {
            win.webContents.sendInputEvent({type:'keyDown',keyCode:letter});
            win.webContents.sendInputEvent({type:'keyUp',keyCode:letter});
            await wait(`${appRef}.cameraViewBasis().offset.normalize().toArray().every((v,i)=>Math.abs(v-(${JSON.stringify(expected)})[i]*${sign})<1e-7)`);
            assert.equal(await js(`${appRef}.state.selected.size`),0);
        }
    }
    await key('A'); await wait(`${appRef}.state.selected.size === 1`);
    // Finder-style bursts and late Explorer processes share one chooser.
    for (const filename of files.slice(0,2)) app.emit('open-file', {preventDefault(){}}, filename);
    await openQueue.flush();
    await wait(`${active}.document.querySelector('#open-batch-confirm')`);
    app.emit('second-instance', {}, [process.execPath, ...(!app.isPackaged ? ['.'] : []), files[2]], process.cwd());
    await openQueue.flush();
    await wait(`${active}.document.querySelectorAll('#open-batch-files li').length === 3`);
    await js(`${active}.document.querySelector('#open-batch-confirm').click()`);
    await wait(`${ws}.tabs.size === ${count+4}`);
    assert.equal(BrowserWindow.getAllWindows().length, windows);
    // Native mouse input exercises the same hit testing and drag capture as a human.
    const orderedIds = await js(`[...${ws}.tabs.keys()]`);
    async function clickTab(id) {
        const point = await js(`(()=>{const n=${ws}.tabs.get('${id}').select;
            n.scrollIntoView({block:'nearest',inline:'nearest'});const r=n.getBoundingClientRect();
            return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)};})()`);
        win.webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...point});
        win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...point});
        await wait(`${ws}.activeSessionId === '${id}' && ${appRef}?.workspaceRecoveryAcknowledged`);
    }
    await clickTab(orderedIds[0]);
    await clickTab(orderedIds[1]);
    await key('1'); await wait(`${ws}.activeSessionId === '${orderedIds[0]}'`);
    await key('Right',false,true); await wait(`${ws}.activeSessionId === '${orderedIds[1]}'`);
    await key('Left',false,true); await wait(`${ws}.activeSessionId === '${orderedIds[0]}'`);
    await key('2'); await wait(`${ws}.activeSessionId === '${orderedIds[1]}'`);
    await key('9'); await wait(`${ws}.activeSessionId === '${orderedIds.at(-1)}'`);
    await wait(`${appRef}?.workspaceRecoveryAcknowledged`);
    await fs.writeFile(path.join(output,'document-navigation.png'),(await win.webContents.capturePage()).toPNG());
    // Dispose only fixtures; preserve the existing workflow's source document.
    const imported = await js(`[...${ws}.tabs.keys()].filter(id=>!${JSON.stringify(originalIds)}.includes(id))`);
    for (const id of imported) {
        await js(`${ws}.activateDocument('${id}')`);
        await wait(`${appRef}?.workspaceRecoveryAcknowledged`);
        await js(`void ${ws}.closeDocument('${id}')`);
        await new Promise(resolve=>setTimeout(resolve,100));
        await js(`(()=>{const d=${ws}.tabs.get('${id}')?.pane?.contentDocument;d?.querySelector('#modal-discard-document')?.click();})()`);
        await wait(`!${ws}.tabs.has('${id}')`);
    }
    await js(`${ws}.activateDocument('${originalId}')`);
    await wait(`${appRef}?.workspaceRecoveryAcknowledged`);
    return { multiFileOpen:true, osOpenBatch:true, cellAxisShortcuts:true,
        nativeTabClicks:true, documentNavigationShortcuts:true };
};
