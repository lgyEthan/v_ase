'use strict';

const { app, BrowserWindow, Menu, clipboard, dialog, ipcMain, session, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const readline = require('node:readline');
const { FileVault } = require('./file-vault.cjs');
app.setName('v_ase');

const smoke = process.argv.includes('--smoke-test');
if (smoke) {
    app.setPath('userData', path.join(process.env.V_ASE_SMOKE_DIR || path.join(__dirname, 'smoke-output'), 'profile'));
    if (process.env.V_ASE_SOFTWARE_GL === '1') {
        app.commandLine.appendSwitch('use-gl', 'angle');
        app.commandLine.appendSwitch('use-angle', 'swiftshader');
        app.commandLine.appendSwitch('enable-unsafe-swiftshader');
    }
}
const vault = new FileVault();
let win, backend, backendOrigin, handshake, exiting = false;
const windows = new Set();
const closingWindows = new Set();
let quitting = false;
const focusedWindow = () => BrowserWindow.getFocusedWindow() || [...windows].find(w => !w.isDestroyed());
let commands = {};
const pendingFiles = [];

function pythonExecutable() {
    if (!app.isPackaged && process.env.VASE_DEV_PYTHON) return path.resolve(process.env.VASE_DEV_PYTHON);
    const root = app.isPackaged ? process.resourcesPath : path.join(__dirname, 'runtime');
    return path.join(root, 'python', process.platform === 'win32' ? 'python.exe' : 'bin/python3');
}

function localFrame(url) {
    try {
        const parsed = new URL(url);
        return parsed.origin === backendOrigin && (parsed.pathname === '/' || parsed.pathname === '/workspace');
    } catch { return false; }
}

function authorized(event) {
    const ownerWindow = BrowserWindow.fromWebContents(event.sender);
    if (!windows.has(ownerWindow) || event.senderFrame !== event.sender.mainFrame
        || !localFrame(event.senderFrame.url)) throw new Error('This operation is only available to the local v_ase workspace.');
    return event.sender.id;
}

async function describeOpenFile(filename, target = focusedWindow()) {
    const info = await fsp.stat(filename);
    if (!info.isFile()) throw new Error('Choose an atomic structure or v_ase project file.');
    const grant = await vault.authorize(target.webContents.id, filename);
    return { ...grant, ...await vault.stat(target.webContents.id, grant.token) };
}

function sendCommand(id, target = focusedWindow()) {
    if (target && !target.isDestroyed()) target.webContents.send('vase:command', id);
}

function createMenu(registry = {}) {
    const item = (id, label) => ({ id, label, enabled: Boolean(registry[id]),
        accelerator: registry[id] ? `CommandOrControl+${registry[id].shift ? 'Shift+' : ''}${registry[id].code.slice(3)}` : undefined,
        click: () => sendCommand(id) });
    const edit = (label, keyCode, shift = false) => ({ label,
        accelerator: `CommandOrControl+${shift ? 'Shift+' : ''}${keyCode}`,
        click: () => {
            const win = focusedWindow();
            if (!win || win.isDestroyed()) return;
            const modifiers = [process.platform === 'darwin' ? 'meta' : 'control', ...(shift ? ['shift'] : [])];
            win.webContents.sendInputEvent({ type: 'keyDown', keyCode, modifiers });
            win.webContents.sendInputEvent({ type: 'keyUp', keyCode, modifiers });
        } });
    const menu = [
        ...(process.platform === 'darwin' ? [{ label: 'v_ase', submenu: [
            { role: 'about' }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' },
            { role: 'unhide' }, { type: 'separator' }, { label: 'Quit v_ase', accelerator: 'Command+Q', click: () => quitSafely() },
        ] }] : []),
        { label: 'File', submenu: [
            item('new', 'New document'), item('open', 'Open…'),
            { label: 'New window', accelerator: 'CommandOrControl+Shift+N', click: () => sendCommand('new-window') },
            { label: 'Move tab to new window', click: () => sendCommand('detach-tab') },
            { type: 'separator' }, item('save', 'Save'), item('save-as', 'Save As…'),
            { type: 'separator' }, item('close', 'Close document'),
            // Alt+F4 retains the native close-current-window behavior. Explicit
            // Quit checks all windows; it must not take over that OS chord.
            ...(process.platform !== 'darwin' ? [{ type: 'separator' }, { label: 'Quit v_ase', click: () => quitSafely() }] : []),
        ] },
        { label: 'Edit', submenu: [edit('Undo', 'Z'), edit('Redo', 'Z', true), { type: 'separator' },
            edit('Cut', 'X'), edit('Copy', 'C'), edit('Paste', 'V'), edit('Select all', 'A')] },
        { label: 'View', submenu: [item('appearance', 'Atom properties'), item('bonding', 'Bonds'),
            item('supercell', 'Supercell'), item('cell-transform', 'Cell transformation'), item('renderer', 'Renderer'),
            { type: 'separator' }, { role: 'togglefullscreen' }] },
        { label: 'Help', submenu: [{ label: 'Shortcuts', click: () => sendCommand('shortcuts') },
            { label: 'User guide', click: () => shell.openExternal('https://v-ase.readthedocs.io/en/latest/desktop.html') },
            { label: 'Copy agent connection URL', click: () => {
                const target = focusedWindow();
                if (!target) return;
                const id = new URL(target.webContents.getURL()).searchParams.get('workspace_id');
                if (id) clipboard.writeText(`${backendOrigin}/api/ai/command/workspace/${id}`);
            } },
            { label: 'About this runtime', click: () => dialog.showMessageBox(focusedWindow(), { type: 'info',
                title: 'v_ase 0.4.2', message: 'v_ase 0.4.2',
                detail: 'The same v_ase GUI and Python backend, bundled with CPython 3.11.16.\n\nPython/Jupyter installations remain independent.\nSource: github.com/lgyEthan/v_ase\nLicense: AGPL-3.0-or-later' }) }] },
    ];
    Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
}

function registerIPC() {
    ipcMain.handle('vase:open-dropped-file', (event, filename) => {
        authorized(event);
        if (typeof filename !== 'string' || !path.isAbsolute(filename)) throw new Error('Drop a local file from Finder or Explorer.');
        return describeOpenFile(filename, BrowserWindow.fromWebContents(event.sender));
    });
    ipcMain.handle('vase:new-window', async (event, payload) => {
        const owner = authorized(event);
        const validId = id => typeof id === 'string' && /^[0-9a-f-]{36}$/i.test(id);
        if (!validId(payload?.workspace_id) || !validId(payload?.session_id)) throw new Error('Invalid document destination.');
        const response = await fetch(`${backendOrigin}/api/workspace/${payload.workspace_id}`);
        if (!response.ok) throw new Error('The destination workspace is unavailable.');
        const state = await response.json();
        if (!state.documents.some(doc => doc.session_id === payload.session_id)) throw new Error('Unknown destination document.');
        const snapshot = payload.snapshot || null;
        const token = snapshot?.provenance?.desktopToken;
        if (token) vault.handle(owner, token);
        const target = await createEditorWindow(`${backendOrigin}/workspace?workspace_id=${payload.workspace_id}&session_id=${payload.session_id}`, {
            snapshot, sourceOwner: owner,
            position: payload.position,
            contentSize: BrowserWindow.fromWebContents(event.sender).getContentSize(),
        });
        return { windowId: target.id };
    });

    ipcMain.handle('vase:open-dialog', async event => {
        authorized(event);
        const target = BrowserWindow.fromWebContents(event.sender);
        const result = await dialog.showOpenDialog(target, { title: 'Open structure or project', properties: ['openFile'],
            filters: [{ name: 'Structures and projects', extensions: ['vase', 'html', 'htm', 'traj', 'xyz', 'extxyz', 'cif', 'vasp', 'pdb', 'cube', 'xsf', 'xml', 'lammpstrj', 'data'] },
                      { name: 'All files', extensions: ['*'] }] });
        return result.canceled ? null : describeOpenFile(result.filePaths[0], target);
    });
    ipcMain.handle('vase:save-dialog', async (event, options) => {
        const owner = authorized(event);
        const name = typeof options?.suggestedName === 'string' ? path.basename(options.suggestedName).slice(0, 240) : 'Untitled.vase';
        const extension = path.extname(name).slice(1);
        const result = await dialog.showSaveDialog(BrowserWindow.fromWebContents(event.sender), { title: 'Save v_ase file', defaultPath: name,
            filters: /^[a-z0-9]{1,12}$/i.test(extension) ? [{ name: `${extension.toUpperCase()} file`, extensions: [extension] }] : undefined,
            properties: ['showOverwriteConfirmation', 'createDirectory'] });
        return result.canceled || !result.filePath ? null : vault.authorize(owner, result.filePath);
    });
    for (const [channel, operation] of Object.entries({ stat: 'stat', read: 'read', same: 'same', begin: 'begin', chunk: 'chunk', finish: 'finish', abort: 'abort' })) {
        ipcMain.handle(`vase:file-${channel}`, (event, ...args) => vault[operation](authorized(event), ...args));
    }
}

async function launchBackend() {
    const executable = pythonExecutable();
    if (!fs.existsSync(executable)) throw new Error('Bundled Python is missing. Build the runtime with desktop/scripts/prepare_runtime.py.');
    const log = fs.createWriteStream(path.join(app.getPath('userData'), 'backend.log'), { flags: 'a' });
    const environment = { ...process.env, PYTHONUTF8: '1', PYTHONUNBUFFERED: '1' };
    for (const key of ['PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV']) delete environment[key];
    // -I intentionally ignores PYTHON* environment variables; -X is required
    // so Windows reads the GUI's Unicode source in UTF-8 as macOS does.
    // Signed/read-only application resources must never receive import caches.
    const pythonArgs = !app.isPackaged && process.env.VASE_DEV_PYTHON
        ? ['-I', '-B', '-X', 'utf8', '-u', '-c',
           `import sys,runpy;sys.path.insert(0,${JSON.stringify(path.resolve(__dirname, '..'))});runpy.run_module('v_ase.cli',run_name='__main__')`,
           'gui', '--no-browser', '--cli']
        : ['-I', '-B', '-X', 'utf8', '-u', '-m', 'v_ase.cli', 'gui', '--no-browser', '--cli'];
    backend = spawn(executable, pythonArgs, {
        cwd: app.getPath('userData'), env: environment, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    });
    backend.stderr.pipe(log);
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('The Python backend did not start within 60 seconds.')), 60000);
        const lines = readline.createInterface({ input: backend.stdout });
        lines.on('line', line => {
            try {
                const message = JSON.parse(line);
                if (message.protocol !== 'v_ase.ai.v1') return;
                const target = new URL(message.human_url);
                if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || !target.port) {
                    throw new Error('The backend did not provide a loopback workspace.');
                }
                clearTimeout(timer); resolve(message);
            } catch (error) { if (error instanceof SyntaxError) return; clearTimeout(timer); reject(error); }
        });
        backend.once('error', error => { clearTimeout(timer); reject(error); });
        backend.once('exit', code => {
            clearTimeout(timer);
            if (!exiting) {
                const error = new Error(`The Python backend stopped (${code}). See backend.log in the application data directory.`);
                reject(error);
                if (win && !win.isDestroyed()) dialog.showErrorBox('v_ase backend stopped', error.message);
            }
        });
    });
}

async function closeWindowSafely(target) {
    if (!target || target.isDestroyed() || closingWindows.has(target)) return;
    closingWindows.add(target);
    try {
        const allowed = await target.webContents.executeJavaScript('window.__vaseDesktopHost?.confirmQuit() ?? true');
        if (!allowed) return;
        const workspaceId = new URL(target.webContents.getURL()).searchParams.get('workspace_id');
        if (workspaceId) {
            const result = await fetch(`${backendOrigin}/api/workspace/${workspaceId}/close`, { method: 'POST' });
            if (!result.ok && result.status !== 404) throw new Error('The workspace could not close. Try again after pending work finishes.');
        }
        await vault.revoke(target.webContents.id);
        windows.delete(target); target.destroy();
        if (!windows.size) { exiting = true; stopBackend(); app.quit(); }
    } catch (error) {
        dialog.showErrorBox('Unable to finish closing', `The window remains open. ${error.message}`);
    } finally { closingWindows.delete(target); }
}

async function quitSafely() {
    if (quitting) return;
    quitting = true;
    try {
        // Approve all documents first. Cancel in any window keeps every window.
        for (const target of windows) {
            target.show(); target.focus();
            if (!await target.webContents.executeJavaScript('window.__vaseDesktopHost?.confirmQuit() ?? true')) return;
        }
        exiting = true;
        for (const target of [...windows]) {
            await vault.revoke(target.webContents.id); windows.delete(target); target.destroy();
        }
        stopBackend(); app.quit();
    } catch (error) { dialog.showErrorBox('Unable to finish quitting', error.message); }
    finally { quitting = false; }
}

function stopBackend() {
    if (!backend || backend.exitCode !== null) return;
    if (process.platform === 'win32') spawn('taskkill', ['/pid', String(backend.pid), '/T', '/F'], { windowsHide: true });
    else backend.kill('SIGTERM');
}

async function openQueued() {
    const target = focusedWindow();
    if (!target) return;
    for (const file of pendingFiles.splice(0)) target.webContents.send('vase:open-file', await describeOpenFile(file, target));
}

function inputCommand(input) {
    if (input.type !== 'keyDown' || input.isComposing || input.alt) return null;
    if (process.platform === 'darwin' ? (!input.meta || input.control) : (!input.control || input.meta)) return null;
    return Object.entries(commands).find(([, command]) => command.code === input.code && command.shift === Boolean(input.shift))?.[0];
}

async function start() {
    await fsp.mkdir(app.getPath('userData'), { recursive: true });
    createMenu(); registerIPC();
    handshake = await launchBackend();
    backendOrigin = new URL(handshake.human_url).origin;
    const isolated = session.fromPartition('persist:v_ase-desktop');
    isolated.webRequest.onBeforeRequest((details, callback) => {
        const url = new URL(details.url);
        const local = url.origin === backendOrigin
            || (url.protocol === 'ws:' && url.host === new URL(backendOrigin).host);
        callback({ cancel: !local && !['data:', 'blob:', 'about:'].includes(url.protocol) });
    });
    isolated.setPermissionRequestHandler((_contents, permission, callback, details) => {
        callback(['clipboard-sanitized-write', 'fullscreen'].includes(permission) && localFrame(details.requestingUrl));
    });
    isolated.setPermissionCheckHandler((_contents, permission, requestingOrigin) =>
        ['clipboard-sanitized-write', 'fullscreen'].includes(permission) && requestingOrigin === backendOrigin);
    win = await createEditorWindow(handshake.human_url, { initial: true });
}

async function createEditorWindow(url, { snapshot = null, sourceOwner = null, position = null, contentSize = [1440, 960], initial = false } = {}) {
    const isolated = session.fromPartition('persist:v_ase-desktop');
    // Smoke windows must be visible too: hidden destination windows throttle
    // animation frames and cannot exercise the real restore/readiness lifecycle.
    const win = new BrowserWindow({ width: contentSize[0], height: contentSize[1], useContentSize: true, minWidth: 390, minHeight: 480, title: 'v_ase', show: true,
        backgroundColor: '#f8f9fa', webPreferences: { preload: path.join(__dirname, 'preload.cjs'),
            contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, session: isolated } });
    windows.add(win);
    if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) win.setPosition(Math.round(position.x), Math.round(position.y));
    win.on('close', event => { if (!exiting) { event.preventDefault(); closeWindowSafely(win); } });
    win.on('closed', () => { windows.delete(win); });
    win.webContents.on('will-navigate', event => { if (!localFrame(event.url)) event.preventDefault(); });
    win.webContents.on('will-frame-navigate', event => {
        if (!localFrame(event.url) && event.url !== 'about:blank') event.preventDefault();
    });
    win.webContents.setWindowOpenHandler(({ url }) => {
        try {
            const target = new URL(url);
            if (target.protocol === 'https:' && ['v-ase.readthedocs.io', 'github.com', 'pypi.org'].includes(target.hostname)) shell.openExternal(url);
        } catch {}
        return { action: 'deny' };
    });
    win.webContents.on('before-input-event', (event, input) => {
        // Let the shared editor choose structural editing versus text editing.
        // Avoid recursively invoking our Edit menu when its click sends a key.
        const editing = ['KeyZ', 'KeyX', 'KeyC', 'KeyV', 'KeyA'].includes(input.code)
            && (input.meta || input.control) && !input.alt;
        win.webContents.setIgnoreMenuShortcuts(editing);
        const id = inputCommand(input);
        if (id) { event.preventDefault(); if (!input.isAutoRepeat) sendCommand(id, win); }
    });
    if (smoke) win.webContents.on('console-message', event => {
        if (event.level === 'error' || event.level >= 2) console.error('Renderer:', event.message);
    });
    let readyResolve, readyReject;
    const ready = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
    ready.catch(() => {}); // loadURL and ready share the same cleanup below.
    const readyTimeout = setTimeout(() => readyReject(new Error('The destination window did not become ready.')), 60000);
    win.webContents.on('did-finish-load', async () => {
        if (!localFrame(win.webContents.getURL())) return;
        try {
            await win.webContents.executeJavaScript(await fsp.readFile(path.join(__dirname, 'host-adapter.js'), 'utf8'));
            commands = await win.webContents.executeJavaScript('window.__vaseDesktopHost.commands');
            createMenu(commands);
            if (snapshot) {
                if (snapshot.provenance?.desktopToken) {
                    const grant = vault.fork(sourceOwner, snapshot.provenance.desktopToken, win.webContents.id);
                    snapshot.provenance.desktopToken = grant.token;
                }
                await win.webContents.executeJavaScript(`window.__vaseDesktopHost.restore(${JSON.stringify(snapshot)})`);
                snapshot = null;
            }
            clearTimeout(readyTimeout); readyResolve(win);
            if (initial) await openQueued();
            if (smoke && initial) {
                const { runSmoke } = require('./smoke.cjs');
                await runSmoke({ app, win, handshake, vault, sendCommand });
                exiting = true; win.destroy(); stopBackend(); app.exit(0);
            }
        } catch (error) {
            console.error(error); clearTimeout(readyTimeout);
            if (smoke && initial) {
                const output = process.env.V_ASE_SMOKE_DIR || path.join(__dirname, 'smoke-output');
                await fsp.mkdir(output, { recursive: true });
                await fsp.writeFile(path.join(output, 'failure.png'), (await win.webContents.capturePage()).toPNG()).catch(() => {});
                const visible = await win.webContents.executeJavaScript(`document.body.innerText + '\\n' + [...document.querySelectorAll('iframe')].map(f=>f.contentDocument?.body?.innerText || '').join('\\n')`).catch(() => '');
                console.error('Workspace at failure:', visible.slice(-12000));
                exiting = true; stopBackend(); app.exit(1);
            }
            else { readyReject(error); }
        }
    });
    try {
        await win.loadURL(url);
        await ready;
        if (!smoke) { win.show(); win.focus(); }
        return win;
    } catch (error) {
        clearTimeout(readyTimeout); windows.delete(win);
        await vault.revoke(win.webContents.id); win.destroy(); throw error;
    }
}

app.on('open-file', (event, filename) => { event.preventDefault(); pendingFiles.push(filename); if (commands.new) openQueued().catch(console.error); });
if (!app.requestSingleInstanceLock()) app.quit();
else {
    app.on('second-instance', (_event, argv) => {
        for (const value of argv.slice(app.isPackaged ? 1 : 2)) if (!value.startsWith('-') && fs.existsSync(value) && fs.statSync(value).isFile()) pendingFiles.push(value);
        focusedWindow()?.show(); focusedWindow()?.focus(); if (commands.new) openQueued().catch(console.error);
    });
    for (const value of process.argv.slice(app.isPackaged ? 1 : 2)) if (!value.startsWith('-') && fs.existsSync(value) && fs.statSync(value).isFile()) pendingFiles.push(value);
    app.on('before-quit', event => { if (!exiting && windows.size) { event.preventDefault(); quitSafely(); } });
    app.on('window-all-closed', () => { stopBackend(); app.quit(); });
    app.on('will-quit', stopBackend);
    app.whenReady().then(start).catch(error => {
        console.error(error); exiting = true; stopBackend();
        if (!smoke) dialog.showErrorBox('Could not start v_ase', error.message);
        app.exit(1);
    });
}
