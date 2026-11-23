'use strict';
const assert = require('node:assert/strict');

function codeFor(key) {
    if (/^[a-z]$/i.test(key)) return `Key${key.toUpperCase()}`;
    if (/^[0-9]$/.test(key)) return `Digit${key}`;
    return { Left: 'ArrowLeft', Right: 'ArrowRight', Up: 'ArrowUp', Down: 'ArrowDown',
        Space: 'Space', Return: 'Enter' }[key] || key;
}

// Disposable test windows take OS focus to exercise Electron's native input
// path. Human typing in another app must not become an unplanned scientific
// edit when that focus changes. Every test key still traverses before-input-
// event and the normal desktop/editor handlers; unmatched input is recorded.
// A lost or incorrectly matched test key leaves a pending expectation and fails.
module.exports = function isolateSmokeKeyboard(contents, {platform = process.platform} = {}) {
    const pending = [], optionalReleases = [], pendingMouse = [], received = [], sent = [];
    const original = contents.sendInputEvent.bind(contents);
    contents.sendInputEvent = input => {
        if (input.type === 'keyDown' || input.type === 'keyUp') {
            const modifiers = input.modifiers || [];
            const expected = { type: input.type, code: codeFor(input.keyCode),
                meta: modifiers.includes('meta'), control: modifiers.includes('control'),
                alt: modifiers.includes('alt'), shift: modifiers.includes('shift') };
            // AppKit consumes Command shortcut releases before Electron's
            // before-input-event. The command keyDown remains mandatory; plain
            // keys (including Delete/Backspace/Tab) require both events.
            if(platform === 'darwin' && expected.meta && input.type === 'keyUp') optionalReleases.push(expected);
            else pending.push(expected);
            sent.push({ at: Date.now(), ...input });
        } else if (input.type.startsWith('mouse')) {
            pendingMouse.push({ type: input.type, x: input.x, y: input.y,
                ...(input.type !== 'mouseMove' ? { button: input.button } : {}) });
        }
        return original(input);
    };
    contents.on('before-input-event', (event, input) => {
        const matches = expected => expected && Object.entries(expected).every(([key, value]) =>
            key === 'type' || key === 'code' ? input[key] === value : Boolean(input[key]) === value);
        const required = matches(pending[0]);
        const release = optionalReleases.findIndex(matches);
        const allowed = Boolean(required || release >= 0);
        if (required) pending.shift();
        else if(release >= 0)optionalReleases.splice(release,1);
        else event.preventDefault();
        const safe = /^(Delete|Backspace|Escape|Tab|Enter|Arrow\w+|Space)$/.test(input.code || '');
        received.push({ at: Date.now(), allowed, type: input.type,
            code: safe ? input.code : '[text]', meta: input.meta, control: input.control });
    });
    contents.on('before-mouse-event', (event, input) => {
        // Chromium may coalesce consecutive moves. Presses and releases must
        // still be delivered in order, at the tested coordinates.
        let index = 0;
        while (index < pendingMouse.length - 1 && pendingMouse[index].type === 'mouseMove'
            && (input.type !== 'mouseMove' || pendingMouse[index].x !== input.x || pendingMouse[index].y !== input.y)) index++;
        const expected = pendingMouse[index];
        const allowed = Boolean(expected && Object.entries(expected).every(([key, value]) => input[key] === value));
        if (allowed) pendingMouse.splice(0, index + 1);
        else event.preventDefault();
        if (input.type !== 'mouseMove' || !allowed) received.push({at:Date.now(),allowed,
            type:input.type,x:input.x,y:input.y,button:input.button});
    });
    return {
        snapshot: () => ({ sent, received, pending, pendingMouse }),
        assertDrained: () => {
            assert.deepEqual(pending, [], 'Every test key must reach the native input handler');
            assert.deepEqual(pendingMouse.filter(input=>input.type !== 'mouseMove'), [], 'Every test mouse press/release must reach the native input handler');
        },
    };
};
