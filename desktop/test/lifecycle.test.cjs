'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');

// Exercise the production handlers with Electron's synchronous last-window
// event ordering. In particular, a cancelled will-quit must remain cancelled.
function fixture(decisions) {
    const app = new EventEmitter();
    let quitRequests = 0;
    const revoked = [];
    Object.assign(app, {
        setName() {}, requestSingleInstanceLock: () => true,
        whenReady: () => ({ then: () => ({ catch() {} }) }),
        quit() {
            quitRequests++;
            app.emit('will-quit', { preventDefault() {} });
        },
    });
    const electron = { app, dialog: { showErrorBox: (...args) => assert.fail(args.join(': ')) } };
    const context = vm.createContext({
        require: name => name === 'electron' ? electron
            : name === './file-vault.cjs' ? { FileVault: class { async revoke(id) { revoked.push(id); } } }
                : require(name),
        process: { argv: ['electron', '.'], platform: process.platform, env: {} },
        __dirname: path.join(__dirname, '..'), console, URL, setTimeout, clearTimeout,
        fetch: async () => ({ ok: true }),
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../main.cjs'), 'utf8'), context);
    const targets = decisions.map((allowed, id) => ({
        destroyed: false, show() {}, focus() {}, isDestroyed() { return this.destroyed; },
        webContents: { id, executeJavaScript: async () => allowed,
            getURL: () => `http://localhost/workspace?workspace_id=fixture-${id}` },
        destroy() {
            this.destroyed = true;
            if (targets.every(target => target.destroyed)) app.emit('window-all-closed');
        },
    }));
    context.targets = targets;
    vm.runInContext('targets.forEach(target => windows.add(target))', context);
    return { app, targets, revoked, quitRequests: () => quitRequests,
        close: index => vm.runInContext(`closeWindowSafely(targets[${index}])`, context),
        quit: () => vm.runInContext('quitSafely()', context) };
}

test('closing the last window requests quit exactly once, preserving cancellation', async () => {
    const f = fixture([true]);
    let willQuit = 0;
    f.app.on('will-quit', event => { willQuit++; event.preventDefault(); });
    assert.equal(await f.close(0), true);
    assert.equal(f.quitRequests(), 1);
    assert.equal(willQuit, 1);
    assert.deepEqual(f.revoked, [0]);
});

test('closing one of several windows leaves the application running', async () => {
    const f = fixture([true, true]);
    assert.equal(await f.close(0), true);
    assert.equal(f.quitRequests(), 0);
    assert.equal(f.targets[1].destroyed, false);
    assert.equal(await f.close(1), true);
    assert.equal(f.quitRequests(), 1);
});

test('explicit Quit releases every window and requests quit exactly once', async () => {
    const f = fixture([true, true]);
    await f.quit();
    assert.deepEqual(f.revoked, [0, 1]);
    assert.equal(f.quitRequests(), 1);
    // Electron can deliver window lifecycle events after the initiating call.
    f.app.emit('window-all-closed');
    await f.quit();
    assert.equal(f.quitRequests(), 1);
});

test('cancelled close or Quit preserves windows and file grants', async () => {
    const close = fixture([false]);
    assert.equal(await close.close(0), false);
    assert.equal(close.targets[0].destroyed, false);
    assert.equal(close.quitRequests(), 0);
    assert.deepEqual(close.revoked, []);
    const quit = fixture([true, false]);
    await quit.quit();
    assert.equal(quit.targets.some(target => target.destroyed), false);
    assert.equal(quit.quitRequests(), 0);
    assert.deepEqual(quit.revoked, []);
});
