'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const waitForVisualFrame = require('../visual-frame.cjs');

test('presentation can trail selection state by several native bitmaps', async () => {
    let reads = 0;
    const bitmap = await waitForVisualFrame(async () => ++reads >= 3 ? 'selected' : 'old',
        value => value === 'selected', { timeout: 100, interval: 1 });
    assert.equal(bitmap, 'selected');
    assert.equal(reads, 3);
});

test('missing selection remains a failure after the bounded presentation wait', async () => {
    let reads = 0;
    const bitmap = await waitForVisualFrame(async () => { reads++; return 'old'; },
        value => value === 'selected', { timeout: 15, interval: 1 });
    assert.equal(bitmap, 'old');
    assert.ok(reads > 1 && reads < 50);
});
