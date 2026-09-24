// Adopt a direct/notebook editor in place. The original app and its opaque
// browser file handle stay alive as the first tab; only later tabs use iframes.
import { projectProvenanceFromLoad } from './project_provenance.js?v=0.4.5';
import { captureDocumentRecovery, restoreDocumentRecovery } from './workspace_recovery.js?v=0.4.5';
import { createWorkspaceAIBridge, handleWorkspaceAICommand } from './workspace_ai.js?v=0.4.5';
import { installShortcutCapture } from './shortcut_capture.js?v=0.4.5';
import { commandIdForEvent, editorAriaShortcut, editorShortcutLabel, resolveShortcutPlatform,
    viewportNavigationForEvent } from './editor_commands.js?v=0.4.5';

export class DirectWorkspace {
    constructor(app) {
        this.app = app;
        this.shortcutPlatform = resolveShortcutPlatform();
        this.workspaceId = null;
        this.hostSessionId = app.sessionId;
        this.tabs = new Map();
        this.activeSessionId = app.sessionId;
        this.pendingClose = new Map();
        this.handledDocumentCommands = new Set();
        this.sequence = 0;
        this.closing = false;
        this.hostClosed = false;
        this.ready = Promise.resolve();
        this.browserClientId = globalThis.crypto?.randomUUID?.()
            || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    }

    async request(path, options = {}) {
        const response = await fetch(path, { credentials: 'same-origin', ...options });
        if (!response.ok) {
            let detail = `${response.status} ${response.statusText}`;
            try { detail = (await response.json()).detail || detail; } catch {}
            throw new Error(detail);
        }
        return await response.json();
    }

    async adopt() {
        if (this.workspaceId) return this;
        const state = await this.request(`/api/workspace/adopt/${encodeURIComponent(this.hostSessionId)}`, {
            method: 'POST'
        });
        this.workspaceId = state.workspace_id;
        this.buildShell();
        this.addTab({
            session_id: this.hostSessionId,
            title: this.app.workspaceDocumentTitle()
        }, { host: true });
        this.updateHost();
        this.connectSocket();
        window.addEventListener('message', event => this.handleMessage(event));
        window.addEventListener('pagehide', () => this.closeBrowser(), { once: true });
        window.addEventListener('beforeunload', event => {
            if (![...this.tabs.values()].some(entry => {
                const app = entry.host ? this.app : entry.pane?.contentWindow?.__ASE_APP__;
                return entry.dirty || app?.projectFile?.dirty
                    || app?.pendingApplyInFlight || app?.pendingScientificRequests?.size;
            })) return;
            event.preventDefault();
            event.returnValue = '';
        });
        this.installAIBridge();
        this.parentShortcutHandler = event => this.dispatchParentShortcut(event);
        window.addEventListener('keydown', this.parentShortcutHandler, true);
        return this;
    }

    buildShell() {
        const bar = document.createElement('div');
        bar.id = 'direct-document-bar';
        bar.setAttribute('role', 'tablist');
        bar.setAttribute('aria-label', 'Open structures');
        const add = document.createElement('button');
        add.id = 'direct-document-new';
        add.type = 'button';
        add.textContent = '+';
        add.setAttribute('aria-label', 'New structure tab');
        add.setAttribute('aria-keyshortcuts', editorAriaShortcut('new', this.shortcutPlatform));
        add.title = `New structure tab (${editorShortcutLabel('new', this.shortcutPlatform)})`;
        add.addEventListener('click', () => {
            this.createDocument().catch(error => this.app.toast(error.message, 'error'));
        });
        bar.appendChild(add);
        const capture = document.getElementById('editor-fullscreen-editing')
            || document.createElement('button');
        capture.id = 'direct-fullscreen-editing';
        capture.type = 'button';
        const captureStatus = document.getElementById('editor-shortcut-status')
            || document.createElement('span');
        captureStatus.id = 'direct-shortcut-status';
        captureStatus.className = 'workspace-shortcut-status';
        captureStatus.setAttribute('role', 'status');
        const captureExit = captureStatus.nextElementSibling?.matches('.shortcut-capture-exit')
            ? captureStatus.nextElementSibling : null;
        const captureOpenFull = captureExit?.nextElementSibling?.matches('.shortcut-capture-open-full')
            ? captureExit.nextElementSibling : null;
        bar.append(capture, captureStatus);
        if (captureExit) bar.appendChild(captureExit);
        if (captureOpenFull) bar.appendChild(captureOpenFull);
        this.disposeShortcutCapture = this.app.disposeShortcutCapture
            || installShortcutCapture(capture, captureStatus);
        this.app.disposeShortcutCapture = null;
        const panes = document.createElement('div');
        panes.id = 'direct-document-panes';
        document.body.append(bar, panes);
        document.body.classList.add('direct-workspace');
        this.bar = bar;
        this.panes = panes;
        this.newButton = add;
        this.app.renderer.onResize();
    }

    addTab(documentState, { host = false } = {}) {
        const sessionId = documentState.session_id;
        if (!sessionId || this.tabs.has(sessionId)) return this.tabs.get(sessionId);
        const tab = document.createElement('div');
        tab.className = 'direct-document-tab';
        tab.setAttribute('role', 'tab');
        tab.dataset.sessionId = sessionId;
        const select = document.createElement('button');
        select.type = 'button';
        select.className = 'direct-document-select';
        select.addEventListener('click', () => this.activate(sessionId));
        const indicator = document.createElement('span');
        indicator.className = 'direct-document-indicator';
        const title = document.createElement('span');
        title.className = 'direct-document-title';
        select.append(indicator, title);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'direct-document-close';
        close.textContent = '×';
        close.addEventListener('click', () => {
            this.closeDocument(sessionId).catch(error => this.app.toast(error.message, 'error'));
        });
        tab.append(select, close);
        this.bar.insertBefore(tab, this.newButton);
        const pane = host ? null : document.createElement('iframe');
        if (pane) {
            pane.className = 'direct-document-pane';
            pane.title = `${documentState.title || 'Untitled'} editor`;
            pane.dataset.editorUrl = `/?${new URLSearchParams({
                session_id: sessionId, workspace_id: this.workspaceId, workspace_child: '1'
            })}`;
            pane.dataset.loaded = 'false';
            pane.hidden = true;
            pane.setAttribute('allow', 'clipboard-read; clipboard-write');
            this.panes.appendChild(pane);
        }
        const entry = { sessionId, host, tab, select, title, close, pane,
            name: documentState.title || 'Untitled', dirty: false, saving: false,
            error: null, closing: false, provenance: null,
            savedContent: null, provenanceApplied: false, appInstance: null,
            visualSnapshot: null, recoveryRevision: 0, childGeneration: null };
        this.tabs.set(sessionId, entry);
        this.updateTab(entry);
        this.activate(this.activeSessionId);
        return entry;
    }

    updateTab(entry) {
        entry.title.textContent = entry.name;
        entry.select.title = entry.name;
        entry.select.setAttribute('aria-label', `${entry.name}${entry.error
            ? `, save error: ${entry.error}`
            : entry.saving ? ', saving' : entry.dirty ? ', unsaved changes' : ''}`);
        entry.close.setAttribute('aria-label', `Close ${entry.name}`);
        entry.tab.classList.toggle('dirty', entry.dirty);
        entry.tab.classList.toggle('saving', entry.saving);
        entry.tab.classList.toggle('error', Boolean(entry.error));
        entry.tab.classList.toggle('active', this.activeSessionId === entry.sessionId);
        entry.tab.setAttribute('aria-selected', this.activeSessionId === entry.sessionId ? 'true' : 'false');
    }

    updateHost() {
        const entry = this.tabs.get(this.hostSessionId);
        if (!entry) return;
        entry.name = this.app.workspaceDocumentTitle();
        entry.dirty = Boolean(this.app.projectFile?.dirty);
        entry.saving = Boolean(this.app.projectFile?.saving);
        entry.error = this.app.projectFile?.error || null;
        this.updateTab(entry);
    }

    activate(sessionId) {
        const entry = this.tabs.get(sessionId);
        if (!entry) return false;
        const previous = this.tabs.get(this.activeSessionId);
        if (previous?.pane && previous !== entry) {
            previous.pane.hidden = true;
            previous.pane.contentWindow?.postMessage({ type: 'v_ase:workspace-active', active: false }, location.origin);
        }
        this.activeSessionId = sessionId;
        const hostActive = entry.host && !this.hostClosed;
        document.body.classList.toggle('direct-child-active', !hostActive);
        if (!this.hostClosed) {
            this.app.setWorkspaceActive(hostActive).catch(error => console.error(error));
        }
        if (entry.pane) {
            entry.pane.hidden = false;
            if (entry.pane.dataset.loaded !== 'true') {
                entry.pane.dataset.loaded = 'true';
                entry.pane.src = entry.pane.dataset.editorUrl;
            } else {
                entry.pane.contentWindow?.postMessage({ type: 'v_ase:workspace-active', active: true }, location.origin);
            }
        }
        this.tabs.forEach(item => this.updateTab(item));
        document.title = `${entry.name} - v_ase`;
        return true;
    }

    activateDocument(sessionId) { return this.activate(sessionId); }

    dispatchParentShortcut(event) {
        if (this.activeSessionId === this.hostSessionId) return;
        const commandId = commandIdForEvent(event, this.shortcutPlatform);
        const navigation = commandId ? null : viewportNavigationForEvent(event);
        if (!commandId && !navigation) return;
        const entry = this.tabs.get(this.activeSessionId);
        const child = entry?.pane?.contentWindow;
        const app = child?.__ASE_APP__;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (commandId && event.repeat) return;
        if (!entry || child?.document?.getElementById('modal-container')
            ?.classList.contains('hidden') === false) return;
        if (app?.collaborationReady && app.workspaceRecoveryAcknowledged
            && app.sessionId === this.activeSessionId) {
            if (commandId) app.executeEditorCommand(commandId);
            else app.executeViewportNavigation(navigation);
        } else {
            this.app.toast('The active document is still loading. Try the shortcut again when it is ready.', 'warning');
        }
    }

    async createDocument({ activate = true } = {}) {
        if (!this.workspaceId) await this.adopt();
        this.newButton.disabled = true;
        try {
            const documentState = await this.request(
                `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions`,
                { method: 'POST', headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ source_session_id: this.activeSessionId }) }
            );
            this.addTab(documentState);
            if (activate) this.activate(documentState.session_id);
            return documentState;
        } finally {
            this.newButton.disabled = false;
        }
    }

    async openFileInNewTab(file, inputFormat = '', index = ':', runtimeMode = null,
        { handle = null, volumetricPrecision = 'float32', serverPath = null } = {}) {
        const created = await this.createDocument({ activate: false });
        const sessionId = created.session_id;
        try {
            const params = new URLSearchParams({ filename: file?.name || serverPath || 'Untitled', index });
            if (inputFormat) params.set('input_format', inputFormat);
            if (runtimeMode) params.set('runtime_mode', runtimeMode);
            params.set('volumetric_precision', volumetricPrecision);
            const result = serverPath
                ? await this.request(`/api/file/load-path/${encodeURIComponent(sessionId)}`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({path:serverPath,input_format:inputFormat || null,index,
                        volumetric_precision:volumetricPrecision,runtime_mode:runtimeMode})
                })
                : await this.request(
                    `/api/file/load/${encodeURIComponent(sessionId)}?${params}`,
                    { method: 'POST', headers: { 'Content-Type': file.type || 'application/octet-stream' }, body: file }
                );
            const entry = this.tabs.get(sessionId);
            entry.name = result.loaded_file?.filename || file?.name || serverPath;
            entry.pendingProvenance = projectProvenanceFromLoad(result, {
                filename: file?.name || serverPath, file, handle
            });
            entry.provenance = entry.pendingProvenance;
            this.updateTab(entry);
            this.activate(sessionId);
            return { title: entry.name, sessionId };
        } catch (error) {
            await this.request(
                `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions/${encodeURIComponent(sessionId)}/close`,
                { method: 'POST' }
            ).catch(() => {});
            const entry = this.tabs.get(sessionId);
            entry?.tab.remove();
            entry?.pane.remove();
            this.tabs.delete(sessionId);
            throw error;
        }
    }

    requestCloseApproval(entry) {
        if (entry.host) return this.app.confirmDocumentClose();
        if (!entry.pane?.contentWindow || entry.pane.dataset.loaded !== 'true') return Promise.resolve(true);
        const requestId = `${entry.sessionId}:${++this.sequence}`;
        return new Promise(resolve => {
            const timer = setTimeout(() => {
                this.pendingClose.delete(requestId);
                resolve(false);
            }, 30000);
            this.pendingClose.set(requestId, { source: entry.pane.contentWindow, resolve, timer });
            entry.pane.contentWindow.postMessage({ type: 'v_ase:workspace-request-close', requestId }, location.origin);
        });
    }

    async closeDocument(sessionId) {
        const entry = this.tabs.get(sessionId);
        if (!entry || entry.closing) return false;
        if (this.tabs.size === 1 && this.closeLastDocument) return this.closeLastDocument();
        entry.closing = true;
        entry.close.disabled = true;
        try {
            if (!await this.requestCloseApproval(entry)) return false;
            const others = [...this.tabs.keys()].filter(id => id !== sessionId);
            let replacement = others[0];
            if (!replacement) replacement = (await this.createDocument({ activate: false })).session_id;
            await this.request(
                `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions/${encodeURIComponent(sessionId)}/close`,
                { method: 'POST' }
            );
            if (entry.host) {
                this.hostClosed = true;
                this.app.dispose();
                document.body.classList.add('direct-host-closed');
            } else {
                entry.pane.contentWindow?.postMessage({ type: 'v_ase:workspace-dispose' }, location.origin);
                entry.pane.remove();
            }
            entry.tab.remove();
            this.tabs.delete(sessionId);
            this.activate(replacement);
            return true;
        } finally {
            entry.closing = false;
            if (this.tabs.has(sessionId)) entry.close.disabled = false;
        }
    }

    captureDocumentProvenance(entry, app = entry?.pane?.contentWindow?.__ASE_APP__) {
        return captureDocumentRecovery(entry, app);
    }

    handleMessage(event) {
        if (event.origin !== location.origin) return;
        const message = event.data || {};
        const entry = this.tabs.get(message.sessionId);
        if (!entry?.pane || entry.pane.contentWindow !== event.source) return;
        const currentApp = entry.pane.contentWindow?.__ASE_APP__;
        if (message.type === 'v_ase:document-ready'
            && (!currentApp || message.generation !== currentApp.recoveryGeneration)) return;
        if (message.type !== 'v_ase:document-ready' && entry.appInstance
            && currentApp && currentApp !== entry.appInstance) return;
        const recoveryMessage = ['v_ase:document-title', 'v_ase:document-dirty',
            'v_ase:document-state'].includes(message.type);
        if (recoveryMessage && entry.childGeneration
            && message.generation !== entry.childGeneration) return;
        if (recoveryMessage && entry.childGeneration
            && Number(message.recoveryRevision) < entry.recoveryRevision) return;
        if (message.type === 'v_ase:document-close-result') {
            const pending = this.pendingClose.get(message.requestId);
            if (!pending || pending.source !== event.source) return;
            clearTimeout(pending.timer);
            this.pendingClose.delete(message.requestId);
            pending.resolve(message.allowed === true);
        } else if (['v_ase:document-title', 'v_ase:document-dirty', 'v_ase:document-ready',
            'v_ase:document-state'].includes(message.type)) {
            entry.name = message.title || entry.name;
            entry.dirty = message.dirty === true;
            entry.saving = message.saving === true;
            entry.error = message.error || null;
            this.updateTab(entry);
            if (message.type !== 'v_ase:document-ready') this.captureDocumentProvenance(entry);
            if (message.type === 'v_ase:document-ready') {
                const app = entry.pane.contentWindow?.__ASE_APP__;
                restoreDocumentRecovery(entry, app);
                if (app) entry.dirty = Boolean(app.projectFile.dirty);
                this.updateTab(entry);
                entry.pane.contentWindow?.postMessage({
                    type: 'v_ase:workspace-active', active: this.activeSessionId === entry.sessionId,
                    recoveryReady: true
                }, location.origin);
            }
        } else if (message.type === 'v_ase:document-command' && this.activeSessionId === entry.sessionId) {
            if (message.requestId) {
                if (this.handledDocumentCommands.has(message.requestId)) return;
                this.handledDocumentCommands.add(message.requestId);
                if (this.handledDocumentCommands.size > 256) {
                    this.handledDocumentCommands.delete(this.handledDocumentCommands.values().next().value);
                }
            }
            if (message.command === 'new') this.createDocument().catch(error => this.app.toast(error.message, 'error'));
            if (message.command === 'close') this.closeDocument(entry.sessionId).catch(error => this.app.toast(error.message, 'error'));
        } else if (message.type === 'v_ase:document-open-new') {
            this.openFileInNewTab(message.file, message.inputFormat, message.index, message.runtimeMode, {
                handle: message.handle,
                volumetricPrecision: message.volumetricPrecision || 'float32',
                serverPath: message.serverPath || null
            })
                .then(result => entry.pane.contentWindow?.postMessage({
                    type: 'v_ase:workspace-open-result', requestId: message.requestId,
                    ok: true, title: result.title
                }, location.origin))
                .catch(error => entry.pane.contentWindow?.postMessage({
                    type: 'v_ase:workspace-open-result', requestId: message.requestId,
                    ok: false, error: error.message
                }, location.origin));
        }
    }

    connectSocket() {
        if (this.closing || !this.workspaceId) return;
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws/workspace/${encodeURIComponent(this.workspaceId)}`
            + `?client_id=${encodeURIComponent(this.browserClientId)}`;
        const socket = new WebSocket(url);
        this.socket = socket;
        socket.onmessage = event => {
            let message;
            try { message = JSON.parse(event.data); } catch { return; }
            if (message.type === 'ai_command') void handleWorkspaceAICommand(this, message);
        };
        socket.onclose = () => {
            if (!this.closing) setTimeout(() => this.connectSocket(), 250);
        };
    }

    closeBrowser() {
        if (this.closing || !this.workspaceId) return;
        this.closing = true;
        this.disposeShortcutCapture?.();
        window.removeEventListener('keydown', this.parentShortcutHandler, true);
        const url = `/api/workspace/${encodeURIComponent(this.workspaceId)}/browser-close/`
            + encodeURIComponent(this.browserClientId);
        navigator.sendBeacon?.(url, new Blob([], { type: 'application/octet-stream' }));
        this.socket?.close(1000, 'page closing');
    }

    installAIBridge() {
        const hostBridge = window.v_aseAI;
        this.hostAIBridge = hostBridge;
        this.aiBridge = createWorkspaceAIBridge(this);
        window.v_aseAI = this.aiBridge;
        window.__V_ASE_AI__ = this.aiBridge;
        window.__V_ASE_WORKSPACE__ = this;
    }

    activeAIBridge() {
        const entry = this.tabs.get(this.activeSessionId);
        return entry?.host ? (this.hostClosed ? null : this.hostAIBridge)
            : entry?.pane?.contentWindow?.v_aseAI || null;
    }

    async waitForActiveAIBridge(timeoutMs = 15000) {
        const deadline = performance.now() + Math.max(100, Number(timeoutMs) || 15000);
        while (performance.now() < deadline) {
            const bridge = this.activeAIBridge();
            if (bridge) {
                await bridge.ready();
                return bridge;
            }
            await new Promise(resolve => window.setTimeout(resolve, 25));
        }
        throw new Error('The active v_ase document did not become ready for AI control.');
    }
}
