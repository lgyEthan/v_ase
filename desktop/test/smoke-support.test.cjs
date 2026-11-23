'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { withDeadline, capturePage, ensureFocus } = require('../smoke-support.cjs');

test('a compositor that never responds fails within the capture deadline', async () => {
    await assert.rejects(withDeadline(new Promise(() => {}), 'native frame', 10), /native frame.*10 ms/);
});
test('deadline preserves the original result and rejection', async () => {
    assert.equal(await withDeadline(Promise.resolve('frame'), 'frame', 1000), 'frame');
    const error = new Error('renderer failure');
    await assert.rejects(withDeadline(Promise.reject(error), 'frame', 1000), value => value === error);
});
test('native capture keeps the host awake without changing the image', async () => {
    const image = { bitmap: 'exact' }, calls = [];
    const contents = { capturePage: async (...args) => { calls.push(args); return image; } };
    const rect = { x: 1, y: 2, width: 30, height: 40 };
    assert.equal(await capturePage(contents, rect), image);
    assert.deepEqual(calls, [[rect, { stayAwake: true }]]);
});
test('native input waits for focus acknowledgement', async () => {
    let focused=false, shown=false;
    const win={isDestroyed:()=>false,isFocused:()=>focused,show:()=>{shown=true;},
        focus:()=>setTimeout(()=>{focused=true;},5),webContents:{focus:()=>{}}};
    await ensureFocus(win,100);
    assert.ok(shown && focused);
});
test('an already focused native control keeps its current DOM focus', async () => {
    const win={isDestroyed:()=>false,isFocused:()=>true,
        show:()=>assert.fail('unnecessary show'),focus:()=>assert.fail('unnecessary focus'),
        webContents:{focus:()=>assert.fail('must not reset the focused checkbox')}};
    await ensureFocus(win);
});
