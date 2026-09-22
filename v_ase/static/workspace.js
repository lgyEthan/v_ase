import { projectProvenanceFromLoad } from './project_provenance.js?v=0.4.1';
import { captureDocumentRecovery, restoreDocumentRecovery } from './workspace_recovery.js?v=0.4.1';
import { createWorkspaceAIBridge, handleWorkspaceAICommand } from './workspace_ai.js?v=0.4.1';
import { installShortcutCapture } from './shortcut_capture.js?v=0.4.1';
import { commandIdForEvent, editorAriaShortcut, editorShortcutLabel, resolveShortcutPlatform,
    viewportNavigationForEvent } from './editor_commands.js?v=0.4.1';

class VAseWorkspace {
    constructor() {
        const params = new URLSearchParams(window.location.search);
        this.workspaceId = params.get('workspace_id');
        this.shortcutPlatform = resolveShortcutPlatform();
        this.requestedSessionId = params.get('session_id');
        this.tabs = new Map();
        this.pendingCloseRequests = new Map();
        this.handledDocumentCommands = new Set();
        this.closeRequestSequence = 0;
        this.activeSessionId = null;
        this.socket = null;
        this.closing = false;
        this.closeSignalSent = false;
        this.reconnectTimer = null;
        this.browserClientId = globalThis.crypto?.randomUUID?.()
            || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

        this.tabRoot = document.getElementById('document-tabs');
        this.paneRoot = document.getElementById('document-panes');
        this.newButton = document.getElementById('new-document');
        this.newButton.setAttribute('aria-keyshortcuts', editorAriaShortcut('new', this.shortcutPlatform));
        this.newButton.title = `New structure tab (${editorShortcutLabel('new', this.shortcutPlatform)})`;
        this.errorPanel = document.getElementById('workspace-error');
        this.errorMessage = document.getElementById('workspace-error-message');
    }

    async init() {
        if (!this.workspaceId) {
            this.showError('The workspace URL has no workspace identifier.');
            return;
        }
        this.newButton.addEventListener('click', () => this.createDocument());
        this.disposeShortcutCapture = installShortcutCapture(
            document.getElementById('workspace-fullscreen-editing'),
            document.getElementById('workspace-shortcut-status')
        );
        window.addEventListener('message', event => this.handleDocumentMessage(event));
        this.parentShortcutHandler = event => this.dispatchParentShortcut(event);
        window.addEventListener('keydown', this.parentShortcutHandler, true);
        const closeWorkspace = () => {
            if (this.closeSignalSent) return;
            this.closeSignalSent = true;
            this.closing = true;
            if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
            window.removeEventListener('keydown', this.parentShortcutHandler, true);
            this.disposeShortcutCapture?.();
            const closeUrl = `/api/workspace/${encodeURIComponent(this.workspaceId)}`
                + `/browser-close/${encodeURIComponent(this.browserClientId)}`;
            let queued = false;
            try {
                queued = navigator.sendBeacon(closeUrl, '');
            } catch {
                // Fall through to a keepalive request.
            }
            if (!queued) {
                fetch(closeUrl, { method: 'POST', keepalive: true }).catch(() => {});
            }
            try {
                if (this.socket?.readyState <= WebSocket.OPEN) {
                    this.socket.close(1000, 'workspace closing');
                }
            } catch {
                // Browser teardown can race WebSocket state changes.
            }
        };
        window.addEventListener('pagehide', closeWorkspace, { once: true });
        window.addEventListener('beforeunload', event => {
            if (![...this.tabs.values()].some(entry => {
                const app = entry.pane?.contentWindow?.__ASE_APP__;
                return entry.dirty || app?.projectFile?.dirty
                    || app?.pendingApplyInFlight || app?.pendingScientificRequests?.size;
            })) return;
            event.preventDefault();
            event.returnValue = '';
        });
        this.aiBridge = createWorkspaceAIBridge(this);
        this.connectWorkspaceSocket();
        const state = await this.request(`/api/workspace/${encodeURIComponent(this.workspaceId)}`);
        state.documents.forEach(documentState => this.addDocument(documentState));
        const initial = this.tabs.has(this.requestedSessionId)
            ? this.requestedSessionId
            : state.documents[0]?.session_id;
        if (!initial) {
            this.showError('The workspace contains no document sessions.');
            return;
        }
        this.activateDocument(initial);
    }

    async request(path, options = {}) {
        const response = await fetch(path, options);
        if (!response.ok) {
            let message = `${response.status} ${response.statusText}`;
            try {
                const payload = await response.json();
                message = payload.detail || message;
            } catch {
                // Keep the HTTP status when the response has no JSON detail.
            }
            throw new Error(message);
        }
        return await response.json();
    }

    connectWorkspaceSocket() {
        if (this.closing) return;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const query = new URLSearchParams({ client_id: this.browserClientId });
        const url = `${protocol}//${window.location.host}/ws/workspace/`
            + `${encodeURIComponent(this.workspaceId)}?${query.toString()}`;
        this.socket = new WebSocket(url);
        this.socket.onmessage = event => {
            let message;
            try {
                message = JSON.parse(event.data);
            } catch {
                return;
            }
            if (message.type === 'ai_command') {
                void handleWorkspaceAICommand(this, message);
            }
        };
        this.socket.onclose = () => {
            if (this.closing || this.reconnectTimer !== null) return;
            this.reconnectTimer = window.setTimeout(() => {
                this.reconnectTimer = null;
                this.connectWorkspaceSocket();
            }, 250);
        };
    }

    editorUrl(sessionId) {
        const params = new URLSearchParams({
            session_id: sessionId,
            workspace_id: this.workspaceId,
            workspace_child: '1',
        });
        return `/?${params.toString()}`;
    }

    addDocument(documentState) {
        const sessionId = documentState.session_id;
        if (!sessionId) return null;
        if (this.tabs.has(sessionId)) return this.tabs.get(sessionId);

        const tab = document.createElement('div');
        tab.className = 'document-tab';
        tab.dataset.sessionId = sessionId;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-selected', 'false');

        const select = document.createElement('button');
        select.className = 'document-select';
        select.type = 'button';
        select.title = documentState.title || 'Untitled';
        select.innerHTML = `
            <span class="document-symbol" aria-hidden="true"></span>
            <span class="document-title"></span>
        `;
        select.querySelector('.document-title').textContent = documentState.title || 'Untitled';
        select.addEventListener('click', () => this.activateDocument(sessionId));

        const close = document.createElement('button');
        close.className = 'document-close';
        close.type = 'button';
        close.setAttribute('aria-label', `Close ${documentState.title || 'Untitled'}`);
        close.title = 'Close tab';
        close.innerHTML = `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 7l10 10M17 7 7 17"></path>
            </svg>
        `;
        close.addEventListener('click', event => {
            event.stopPropagation();
            this.closeDocument(sessionId);
        });
        tab.append(select, close);

        const pane = document.createElement('iframe');
        pane.className = 'document-pane';
        pane.dataset.sessionId = sessionId;
        pane.title = `${documentState.title || 'Untitled'} editor`;
        pane.src = 'about:blank';
        pane.dataset.editorUrl = this.editorUrl(sessionId);
        pane.dataset.loaded = 'false';
        pane.hidden = true;
        pane.setAttribute('allow', 'clipboard-read; clipboard-write');

        this.tabRoot.insertBefore(tab, this.newButton);
        this.paneRoot.appendChild(pane);
        const entry = {
            sessionId,
            title: documentState.title || 'Untitled',
            tab,
            select,
            close,
            pane,
            dirty: false,
            saving: false,
            provenance: null,
            savedContent: null,
            provenanceApplied: false,
            appInstance: null,
            visualSnapshot: null,
            recoveryRevision: 0,
            childGeneration: null,
        };
        this.tabs.set(sessionId, entry);
        this.syncCloseButtons();
        return entry;
    }

    activateDocument(sessionId) {
        if (!this.tabs.has(sessionId) || this.activeSessionId === sessionId) return;
        const previous = this.tabs.get(this.activeSessionId);
        if (previous) {
            previous.tab.classList.remove('active');
            previous.tab.setAttribute('aria-selected', 'false');
            previous.pane.hidden = true;
            previous.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-active',
                active: false,
            }, window.location.origin);
        }

        const next = this.tabs.get(sessionId);
        this.activeSessionId = sessionId;
        next.tab.classList.add('active');
        next.tab.setAttribute('aria-selected', 'true');
        next.pane.hidden = false;
        this.loadDocument(next);
        next.select.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        next.pane.contentWindow?.postMessage({
            type: 'v_ase:workspace-active',
            active: true,
        }, window.location.origin);
        document.title = `${next.title} - v_ase`;
    }

    dispatchParentShortcut(event) {
        const commandId = commandIdForEvent(event, this.shortcutPlatform);
        const navigation = commandId ? null : viewportNavigationForEvent(event);
        if (!commandId && !navigation) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (commandId && event.repeat) return;
        const entry = this.tabs.get(this.activeSessionId);
        const child = entry?.pane?.contentWindow;
        if (child?.document?.getElementById('modal-container')
            ?.classList.contains('hidden') === false) return;
        const app = child?.__ASE_APP__;
        if (app?.collaborationReady && app.workspaceRecoveryAcknowledged
            && app.sessionId === this.activeSessionId) {
            if (commandId) app.executeEditorCommand(commandId);
            else app.executeViewportNavigation(navigation);
        } else {
            this.showError('The active document is still loading. Try the shortcut again when it is ready.');
        }
    }

    loadDocument(entry) {
        if (!entry || entry.pane.dataset.loaded === 'true') return;
        entry.pane.dataset.loaded = 'true';
        entry.pane.src = entry.pane.dataset.editorUrl;
    }

    async createDocument({ activate = true } = {}) {
        this.newButton.disabled = true;
        try {
            const documentState = await this.request(
                `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_session_id: this.activeSessionId }),
                }
            );
            this.addDocument(documentState);
            if (activate) this.activateDocument(documentState.session_id);
            return documentState;
        } catch (error) {
            this.showError(`Could not create a new document: ${error.message}`);
            return null;
        } finally {
            this.newButton.disabled = false;
        }
    }

    async uploadFileToSession(
        sessionId,
        file,
        inputFormat = '',
        index = ':',
        volumetricPrecision = 'float32',
        runtimeMode = null
    ) {
        const params = new URLSearchParams({
            filename: file?.name || 'structure',
            index: index || ':',
            volumetric_precision: volumetricPrecision || 'float32',
        });
        if (inputFormat) params.set('input_format', inputFormat);
        if (runtimeMode === 'view' || runtimeMode === 'edit') {
            params.set('runtime_mode', runtimeMode);
        }
        return await this.request(
            `/api/file/load/${encodeURIComponent(sessionId)}?${params.toString()}`,
            {
                method: 'POST',
                headers: {'Content-Type': file?.type || 'application/octet-stream'},
                body: file,
            }
        );
    }

    async loadPathToSession(
        sessionId,
        path,
        inputFormat = '',
        index = ':',
        volumetricPrecision = 'float32',
        runtimeMode = null
    ) {
        return await this.request(
            `/api/file/load-path/${encodeURIComponent(sessionId)}`,
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    path,
                    input_format: inputFormat || '',
                    index: index || ':',
                    volumetric_precision: volumetricPrecision || 'float32',
                    runtime_mode: runtimeMode === 'view' || runtimeMode === 'edit'
                        ? runtimeMode
                        : null,
                }),
            }
        );
    }

    async openDocumentFromFile(sourceEntry, message) {
        let documentState = null;
        const respond = payload => {
            sourceEntry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-open-result',
                requestId: message.requestId,
                ...payload,
            }, window.location.origin);
        };
        try {
            const hasServerPath = typeof message.serverPath === 'string' && message.serverPath.length > 0;
            const hasUpload = message.file instanceof Blob && message.file.size > 0;
            if (!hasServerPath && !hasUpload) {
                throw new Error('The selected file is empty or unavailable.');
            }
            documentState = await this.request(
                `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions`,
                {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({source_session_id: sourceEntry.sessionId}),
                }
            );
            const requestedMode = message.runtimeMode === 'edit' ? 'edit' : 'view';
            const data = hasServerPath
                ? await this.loadPathToSession(
                    documentState.session_id,
                    message.serverPath,
                    message.inputFormat || '',
                    message.index || ':',
                    message.volumetricPrecision || 'float32',
                    requestedMode
                )
                : await this.uploadFileToSession(
                    documentState.session_id,
                    message.file,
                    message.inputFormat || '',
                    message.index || ':',
                    message.volumetricPrecision || 'float32',
                    requestedMode
                );
            documentState.title = data.loaded_file?.filename || message.fileName || message.file?.name || 'Untitled';
            documentState.empty = false;
            const newEntry = this.addDocument(documentState);
            newEntry.pendingProvenance = projectProvenanceFromLoad(data, {
                filename: message.fileName || message.file?.name || documentState.title,
                file: message.file,
                handle: message.handle,
            });
            newEntry.provenance = newEntry.pendingProvenance;
            this.activateDocument(documentState.session_id);
            respond({
                ok: true,
                sessionId: documentState.session_id,
                title: documentState.title,
            });
        } catch (error) {
            if (documentState?.session_id) {
                try {
                    await this.request(
                        `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions/`
                        + `${encodeURIComponent(documentState.session_id)}/close`,
                        {method: 'POST'}
                    );
                } catch {
                    // Preserve the original upload error for the requesting document.
                }
                const failedEntry = this.tabs.get(documentState.session_id);
                if (failedEntry) {
                    failedEntry.tab.remove();
                    failedEntry.pane.remove();
                    this.tabs.delete(documentState.session_id);
                    this.syncCloseButtons();
                    if (this.activeSessionId === documentState.session_id) {
                        this.activeSessionId = null;
                        this.activateDocument(sourceEntry.sessionId);
                    }
                }
            }
            respond({ok: false, error: error.message});
        }
    }

    async closeDocument(sessionId) {
        if (!this.tabs.has(sessionId)) return;
        const ordered = [...this.tabs.keys()];
        const index = ordered.indexOf(sessionId);
        const fallback = ordered[index + 1] || ordered[index - 1];
        const entry = this.tabs.get(sessionId);
        if (entry.closing) return;
        entry.closing = true;
        entry.close.disabled = true;
        try {
            const allowed = await this.requestDocumentCloseApproval(entry);
            if (!allowed) return;
            let replacement = fallback;
            if (!replacement) {
                const created = await this.createDocument({ activate: false });
                if (!created) return;
                replacement = created.session_id;
            }
            await this.request(
                `/api/workspace/${encodeURIComponent(this.workspaceId)}/sessions/${encodeURIComponent(sessionId)}/close`,
                { method: 'POST' }
            );
            entry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-dispose',
            }, window.location.origin);
            entry.tab.remove();
            entry.pane.remove();
            this.tabs.delete(sessionId);
            this.syncCloseButtons();
            if (this.activeSessionId === sessionId) {
                this.activeSessionId = null;
                this.activateDocument(replacement);
            }
        } catch (error) {
            this.showError(`Could not close the document: ${error.message}`);
        } finally {
            entry.closing = false;
            if (this.tabs.has(sessionId)) entry.close.disabled = false;
        }
    }

    requestDocumentCloseApproval(entry) {
        if (entry.pane.dataset.loaded !== 'true') return Promise.resolve(true);
        if (!entry.pane.contentWindow) return Promise.resolve(false);
        const requestId = `${entry.sessionId}:${++this.closeRequestSequence}`;
        return new Promise(resolve => {
            this.pendingCloseRequests.set(requestId, {
                sessionId: entry.sessionId,
                source: entry.pane.contentWindow,
                resolve
            });
            entry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-request-close', requestId
            }, window.location.origin);
        });
    }

    syncCloseButtons() {
        this.tabs.forEach(entry => {
            entry.close.disabled = Boolean(entry.closing);
            entry.close.title = 'Close document';
        });
    }

    applyWorkspaceTheme(preference, { persist = true } = {}) {
        const result = window.v_aseTheme?.apply?.(preference, { persist })
            || { preference };
        this.tabs.forEach(entry => {
            entry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-theme',
                preference: result.preference
            }, window.location.origin);
        });
    }

    broadcastVisualDefaults(message) {
        this.tabs.forEach(entry => {
            entry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-visual-defaults',
                configured: message.configured === true,
                settings: message.settings || null
            }, window.location.origin);
        });
    }

    captureDocumentProvenance(entry, app = entry?.pane?.contentWindow?.__ASE_APP__) {
        return captureDocumentRecovery(entry, app);
    }

    handleDocumentMessage(event) {
        if (event.origin !== window.location.origin) return;
        const message = event.data || {};
        if (!message.type?.startsWith('v_ase:document-')) return;
        const entry = this.tabs.get(message.sessionId);
        if (!entry || entry.pane.contentWindow !== event.source) return;
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
            const pending = this.pendingCloseRequests.get(message.requestId);
            if (pending?.sessionId === message.sessionId && pending.source === event.source) {
                this.pendingCloseRequests.delete(message.requestId);
                pending.resolve(message.allowed === true);
            }
            return;
        }
        if (message.type === 'v_ase:document-theme') {
            this.applyWorkspaceTheme(message.preference, { persist: message.persist !== false });
            return;
        }
        if (message.type === 'v_ase:document-visual-defaults') {
            this.broadcastVisualDefaults(message);
            return;
        }
        if (message.type === 'v_ase:document-open-new') {
            this.openDocumentFromFile(entry, message);
            return;
        }
        if (message.type === 'v_ase:document-command') {
            if (message.sessionId !== this.activeSessionId) return;
            if (message.requestId) {
                if (this.handledDocumentCommands.has(message.requestId)) return;
                this.handledDocumentCommands.add(message.requestId);
                if (this.handledDocumentCommands.size > 256) {
                    this.handledDocumentCommands.delete(this.handledDocumentCommands.values().next().value);
                }
            }
            if (message.command === 'new') this.createDocument();
            else if (message.command === 'close') this.closeDocument(message.sessionId);
            return;
        }
        if (['v_ase:document-title', 'v_ase:document-ready', 'v_ase:document-dirty', 'v_ase:document-state']
            .includes(message.type)) {
            this.updateDocumentTitle(message.sessionId, message.title);
            entry.dirty = message.dirty === true;
            entry.saving = message.saving === true;
            entry.error = message.error || null;
            entry.tab.classList.toggle('dirty', entry.dirty);
            entry.tab.classList.toggle('saving', entry.saving);
            entry.tab.classList.toggle('error', Boolean(entry.error));
            entry.select.setAttribute('aria-label',
                `${entry.title}${entry.error ? `, save error: ${entry.error}`
                    : entry.saving ? ', saving' : entry.dirty ? ', unsaved changes' : ''}`);
            if (message.type !== 'v_ase:document-ready') this.captureDocumentProvenance(entry);
        }
        if (message.type === 'v_ase:document-ready') {
            const app = entry.pane.contentWindow?.__ASE_APP__;
            restoreDocumentRecovery(entry, app);
            if (app) entry.dirty = Boolean(app.projectFile.dirty);
            entry.tab.classList.toggle('dirty', entry.dirty);
            entry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-active',
                active: this.activeSessionId === message.sessionId,
                recoveryReady: true,
            }, window.location.origin);
        }
    }

    updateDocumentTitle(sessionId, title) {
        const entry = this.tabs.get(sessionId);
        if (!entry) return;
        const normalized = String(title || 'Untitled').trim() || 'Untitled';
        entry.title = normalized;
        entry.select.title = normalized;
        entry.select.querySelector('.document-title').textContent = normalized;
        entry.close.setAttribute('aria-label', `Close ${normalized}`);
        entry.pane.title = `${normalized} editor`;
        if (this.activeSessionId === sessionId) document.title = `${normalized} - v_ase`;
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorPanel.hidden = false;
    }

    activeAIBridge() {
        const entry = this.tabs.get(this.activeSessionId);
        return entry?.pane?.contentWindow?.v_aseAI || null;
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

    createAIBridge() { return this.aiBridge || createWorkspaceAIBridge(this); }

    async postAICommandResult(message, payload) {
        const target = new URL(String(message.result_url || ''), window.location.origin);
        if (target.origin !== window.location.origin) {
            throw new Error('AI command result URL must use the current v_ase origin.');
        }
        const response = await fetch(target.href, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            let detail = `${response.status} ${response.statusText}`;
            try {
                const data = await response.json();
                detail = data.detail || detail;
            } catch {
                // Keep the HTTP status when the server returned no JSON detail.
            }
            throw new Error(`Could not return AI command result: ${detail}`);
        }
    }

    async handleAICommandMessage(message) { return handleWorkspaceAICommand(this, message); }
}

const workspace = new VAseWorkspace();
workspace.ready = workspace.init().catch(error => {
    workspace.showError(error.message);
    throw error;
});
window.__V_ASE_WORKSPACE__ = workspace;
window.v_aseAI = workspace.createAIBridge();
window.__V_ASE_AI__ = window.v_aseAI;
