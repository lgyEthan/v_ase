'use strict';

// Native presentation and renderer promises can stop advancing when the host
// sleeps. A smoke failure must produce evidence and terminate, never hang.
async function withDeadline(promise, label, timeout = 20000) {
    let timer;
    try {
        return await Promise.race([
            promise,
            new Promise((_, reject) => {
                timer = setTimeout(() => reject(new Error(`Timed out awaiting ${label} (${timeout} ms).`)), timeout);
            }),
        ]);
    } finally { clearTimeout(timer); }
}

function capturePage(contents, rect, label = 'native compositor capture') {
    return withDeadline(contents.capturePage(rect, { stayAwake: true }), label);
}

async function ensureFocus(win, timeout = 3000) {
    if (win.isDestroyed()) throw new Error('The native input window is closed.');
    if (win.isFocused()) return;
    win.show(); win.focus(); win.webContents.focus();
    const deadline = Date.now() + timeout;
    while (!win.isFocused() && Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 10));
    }
    if (!win.isFocused()) throw new Error('The native input window did not gain focus.');
}

module.exports = { withDeadline, capturePage, ensureFocus };
