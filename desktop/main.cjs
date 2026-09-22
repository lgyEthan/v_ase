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
let win, backend, backendOrigin, handshake, closing = false, exiting = false;
let commands = {};
const pendingFiles = [];

function pythonExecutable() {
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
    if (!win || event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame
        || !localFrame(event.senderFrame.url)) throw new Error('This operation is only available to the local v_ase workspace.');
    return event.sender.id;
}

async function describeOpenFile(filename) {
    const info = await fsp.stat(filename);
    if (!info.isFile()) throw new Error('Choose an atomic structure or v_ase project file.');
    const grant = await vault.authorize(win.webContents.id, filename);
    return { ...grant, ...await vault.stat(win.webContents.id, grant.token) };
}

function sendCommand(id) {
    if (win && !win.isDestroyed()) win.webContents.send('vase:command', id);
}

function createMenu(registry = {}) {
    const item = (id, label) => ({ id, label, enabled: Boolean(registry[id]),
        accelerator: registry[id] ? `CommandOrControl+${registry[id].shift ? 'Shift+' : ''}${registry[id].code.slice(3)}` : undefined,
        click: () => sendCommand(id) });
    const edit = (label, keyCode, shift = false) => ({ label,
        accelerator: `CommandOrControl+${shift ? 'Shift+' : ''}${keyCode}`,
        click: () => {
            if (!win || win.isDestroyed()) return;
            const modifiers = [process.platform === 'darwin' ? 'meta' : 'control', ...(shift ? ['shift'] : [])];
            win.webContents.sendInputEvent({ type: 'keyDown', keyCode, modifiers });
            win.webContents.sendInputEvent({ type: 'keyUp', keyCode, modifiers });
        } });
    const menu = [
        ...(process.platform === 'darwin' ? [{ label: 'v_ase', submenu: [
            { role: 'about' }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' },
            { role: 'unhide' }, { type: 'separator' }, { label: 'Quit v_ase', accelerator: 'Command+Q', click: () => win?.close() },
        ] }] : []),
        { label: 'File', submenu: [
            item('new', 'New document'), { label: 'Open…', accelerator: 'CommandOrControl+O', click: () => sendCommand('open') },
            { type: 'separator' }, item('save', 'Save'), item('save-as', 'Save As…'),
            { type: 'separator' }, item('close', 'Close document'),
            ...(process.platform !== 'darwin' ? [{ type: 'separator' }, { label: 'Quit v_ase', accelerator: 'Alt+F4', click: () => win?.close() }] : []),
        ] },
        { label: 'Edit', submenu: [edit('Undo', 'Z'), edit('Redo', 'Z', true), { type: 'separator' },
            edit('Cut', 'X'), edit('Copy', 'C'), edit('Paste', 'V'), edit('Select all', 'A')] },
        { label: 'View', submenu: [item('appearance', 'Atom properties'), item('bonding', 'Bonds'),
            item('supercell', 'Supercell'), item('cell-transform', 'Cell transformation'), item('renderer', 'Renderer'),
            { type: 'separator' }, { role: 'togglefullscreen' }] },
        { label: 'Help', submenu: [{ label: 'Shortcuts', click: () => sendCommand('shortcuts') },
            { label: 'User guide', click: () => shell.openExternal('https://v-ase.readthedocs.io/en/latest/desktop.html') },
            { label: 'Copy agent connection URL', click: () => handshake && clipboard.writeText(handshake.command_url) },
            { label: 'About this runtime', click: () => dialog.showMessageBox(win, { type: 'info',
                title: 'v_ase 0.4.1', message: 'v_ase 0.4.1',
                detail: 'The same v_ase GUI and Python backend, bundled with CPython 3.11.16.\n\nPython/Jupyter installations remain independent.\nSource: github.com/lgyEthan/v_ase\nLicense: AGPL-3.0-or-later' }) }] },
    ];
    Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
}

function registerIPC() {
    ipcMain.handle('vase:open-dialog', async event => {
        authorized(event);
        const result = await dialog.showOpenDialog(win, { title: 'Open structure or project', properties: ['openFile'],
            filters: [{ name: 'Structures and projects', extensions: ['vase', 'html', 'htm', 'traj', 'xyz', 'extxyz', 'cif', 'vasp', 'pdb', 'cube', 'xsf', 'xml', 'lammpstrj', 'data'] },
                      { name: 'All files', extensions: ['*'] }] });
        return result.canceled ? null : describeOpenFile(result.filePaths[0]);
    });
    ipcMain.handle('vase:save-dialog', async (event, options) => {
        const owner = authorized(event);
        const name = typeof options?.suggestedName === 'string' ? path.basename(options.suggestedName).slice(0, 240) : 'Untitled.vase';
        const extension = path.extname(name).slice(1);
        const result = await dialog.showSaveDialog(win, { title: 'Save v_ase file', defaultPath: name,
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
    backend = spawn(executable, ['-I', '-B', '-X', 'utf8', '-u', '-m', 'v_ase.cli', 'gui', '--no-browser', '--cli'], {
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

async function quitSafely() {
    if (closing || !win) return;
    closing = true;
    try {
        const allowed = await win.webContents.executeJavaScript('window.__vaseDesktopHost?.confirmQuit() ?? true');
        if (!allowed) return;
        exiting = true;
        await vault.revoke(win.webContents.id);
        win.destroy();
        stopBackend();
        app.quit();
    } catch (error) {
        const choice = await dialog.showMessageBox(win, { type: 'warning', title: 'Unable to finish closing',
            message: 'v_ase could not confirm every document.', detail: error.message,
            buttons: ['Keep open', 'Quit without saving'], defaultId: 0, cancelId: 0 });
        if (choice.response === 1) { exiting = true; win.destroy(); stopBackend(); app.quit(); }
    } finally { closing = false; }
}

function stopBackend() {
    if (!backend || backend.exitCode !== null) return;
    if (process.platform === 'win32') spawn('taskkill', ['/pid', String(backend.pid), '/T', '/F'], { windowsHide: true });
    else backend.kill('SIGTERM');
}

async function openQueued() {
    for (const file of pendingFiles.splice(0)) win.webContents.send('vase:open-file', await describeOpenFile(file));
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
    win = new BrowserWindow({ width: 1440, height: 960, minWidth: 390, minHeight: 480, title: 'v_ase', show: !smoke,
        backgroundColor: '#f8f9fa', webPreferences: { preload: path.join(__dirname, 'preload.cjs'),
            contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, session: isolated } });
    win.on('close', event => { if (!exiting) { event.preventDefault(); quitSafely(); } });
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
        if (id) { event.preventDefault(); if (!input.isAutoRepeat) sendCommand(id); }
    });
    if (smoke) win.webContents.on('console-message', event => {
        if (event.level === 'error' || event.level >= 2) console.error('Renderer:', event.message);
    });
    win.webContents.on('did-finish-load', async () => {
        if (!localFrame(win.webContents.getURL())) return;
        try {
            await win.webContents.executeJavaScript(await fsp.readFile(path.join(__dirname, 'host-adapter.js'), 'utf8'));
            commands = await win.webContents.executeJavaScript('window.__vaseDesktopHost.commands');
            createMenu(commands);
            await openQueued();
            if (smoke) {
                const { runSmoke } = require('./smoke.cjs');
                await runSmoke({ app, win, handshake, vault, sendCommand });
                exiting = true; win.destroy(); stopBackend(); app.exit(0);
            }
        } catch (error) {
            console.error(error);
            if (smoke) {
                const output = process.env.V_ASE_SMOKE_DIR || path.join(__dirname, 'smoke-output');
                await fsp.mkdir(output, { recursive: true });
                await fsp.writeFile(path.join(output, 'failure.png'), (await win.webContents.capturePage()).toPNG()).catch(() => {});
                const visible = await win.webContents.executeJavaScript(`document.body.innerText + '\\n' + [...document.querySelectorAll('iframe')].map(f=>f.contentDocument?.body?.innerText || '').join('\\n')`).catch(() => '');
                console.error('Workspace at failure:', visible.slice(-12000));
                exiting = true; stopBackend(); app.exit(1);
            }
            else dialog.showErrorBox('v_ase desktop could not initialize', error.message);
        }
    });
    await win.loadURL(handshake.human_url);
}

app.on('open-file', (event, filename) => { event.preventDefault(); pendingFiles.push(filename); if (commands.new) openQueued().catch(console.error); });
if (!app.requestSingleInstanceLock()) app.quit();
else {
    app.on('second-instance', (_event, argv) => {
        for (const value of argv.slice(app.isPackaged ? 1 : 2)) if (!value.startsWith('-') && fs.existsSync(value) && fs.statSync(value).isFile()) pendingFiles.push(value);
        win?.show(); win?.focus(); if (commands.new) openQueued().catch(console.error);
    });
    for (const value of process.argv.slice(app.isPackaged ? 1 : 2)) if (!value.startsWith('-') && fs.existsSync(value) && fs.statSync(value).isFile()) pendingFiles.push(value);
    app.on('before-quit', event => { if (!exiting && win && !win.isDestroyed()) { event.preventDefault(); quitSafely(); } });
    app.on('window-all-closed', () => { stopBackend(); app.quit(); });
    app.on('will-quit', stopBackend);
    app.whenReady().then(start).catch(error => {
        console.error(error); exiting = true; stopBackend();
        if (!smoke) dialog.showErrorBox('Could not start v_ase', error.message);
        app.exit(1);
    });
}
