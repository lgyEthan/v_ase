'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const test = require('node:test');
const { attachWindowSnapping, snapWindowBounds } = require('../window-snapping.cjs');

const other = { x: 100, y: 200, width: 300, height: 240 };
const bounds = (x, y) => ({ x, y, width: 260, height: 180 });

test('snaps near edges, holds the aligned position, and releases when dragged farther', () => {
    const snapped = snapWindowBounds(bounds(408, 204), [other]);
    assert.deepEqual(snapped, { x: 400, y: 200, lock: { x: 400, y: 200 } });
    const held = snapWindowBounds(bounds(414, 213), [other], snapped.lock);
    assert.deepEqual(held, snapped);
    const released = snapWindowBounds(bounds(418, 221), [other], held.lock);
    assert.deepEqual(released, { x: 418, y: 221, lock: { x: null, y: null } });
    assert.equal(snapWindowBounds(bounds(408, 500), [other]).x, 408);
    assert.equal(snapWindowBounds(bounds(103, 445), [other]).y, 440);
});

test('macOS snaps each native drag move without repositioning a neighbor or recursing', () => {
    class Window extends EventEmitter {
        constructor(rect) { super(); this.bounds = rect; this.positions = []; }
        getBounds() { return this.bounds; }
        isDestroyed() { return false; }
        isVisible() { return true; }
        isMinimized() { return false; }
        isMaximized() { return false; }
        isFullScreen() { return false; }
        setPosition(x, y, animate) {
            this.positions.push([x, y, animate]);
            this.bounds = { ...this.bounds, x, y };
            this.emit('move');
        }
    }
    const moving = new Window(bounds(460, 250));
    const neighbor = new Window(other);
    let pointer = { x: 550, y: 265 };
    const screen = { getCursorScreenPoint: () => pointer, getDisplayMatching: () => ({ id: 1 }) };
    attachWindowSnapping(moving, [moving, neighbor], screen, 'darwin');
    moving.emit('move');
    moving.emit('will-move');
    pointer = { x: 497, y: 219 };
    moving.bounds = bounds(407, 204);
    moving.emit('move');
    assert.deepEqual(moving.positions, [[400, 200, false]]);
    pointer = { x: 504, y: 227 };
    moving.bounds = bounds(414, 212);
    moving.emit('move');
    assert.deepEqual(moving.bounds, bounds(400, 200));
    pointer = { x: 515, y: 240 };
    moving.bounds = bounds(425, 225);
    moving.emit('move');
    assert.deepEqual(moving.bounds, bounds(425, 225));
    assert.deepEqual(neighbor.positions, []);
});
