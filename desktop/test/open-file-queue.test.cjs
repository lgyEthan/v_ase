'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { OpenFileQueue } = require('../open-file-queue.cjs');
const clock = () => { let call = null; return { setTimer: fn => (call = fn), clearTimer: () => { call = null; }, tick: () => call?.() }; };
test('OS burst waits for one ready window, deduplicates, and retains cold-start files', async () => {
    const time = clock(), received = []; let ready = false;
    const queue = new OpenFileQueue(async files => { if (!ready) return false; received.push(files); return true; }, time);
    queue.add(['/a.vasp']); queue.add(['/b.vasp','/a.vasp']);
    await queue.flush(); assert.deepEqual(received, []);
    ready = true; await queue.flush(); assert.deepEqual(received, [['/a.vasp','/b.vasp']]);
    await queue.flush(); assert.equal(received.length, 1);
});
test('files delivered during asynchronous dispatch remain queued; errors retain grants to retry', async () => {
    let finish; const received = [];
    const queue = new OpenFileQueue(async files => { received.push(files); if (received.length === 1) await new Promise(r => finish=r); return true; }, clock());
    queue.add(['/a']); const pending = queue.flush(); queue.add(['/b']); finish(); await pending;
    await queue.flush(); assert.deepEqual(received,[['/a'],['/b']]);
    const failing = new OpenFileQueue(async () => { throw new Error('Not ready'); }, clock());
    failing.add(['/c']); await assert.rejects(failing.flush(), /Not ready/); assert.deepEqual([...failing.files.values()], ['/c']);
});

test('an elapsed debounce during dispatch schedules the remaining files again', async () => {
    let callback, finish; const received = [];
    const queue = new OpenFileQueue(async files => { received.push(files); if (received.length === 1) await new Promise(r => finish=r); return true; }, {
        setTimer: fn => (callback=fn), clearTimer: () => { callback=null; }
    });
    queue.add(['/a']); const first=queue.flush(); queue.add(['/b']);
    const elapsed=callback; callback=null; elapsed(); finish(); await first;
    assert.equal(typeof callback, 'function'); callback(); await queue.draining;
    assert.deepEqual(received,[['/a'],['/b']]);
});
