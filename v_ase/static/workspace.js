class VAseWorkspace {
    constructor() {
        const params = new URLSearchParams(window.location.search);
        this.workspaceId = params.get('workspace_id');
        this.requestedSessionId = params.get('session_id');
        this.tabs = new Map();
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
        this.errorPanel = document.getElementById('workspace-error');
        this.errorMessage = document.getElementById('workspace-error-message');
    }

    async init() {
        if (!this.workspaceId) {
            this.showError('The workspace URL has no workspace identifier.');
            return;
        }
        this.newButton.addEventListener('click', () => this.createDocument());
        window.addEventListener('message', event => this.handleDocumentMessage(event));
        const closeWorkspace = () => {
            if (this.closeSignalSent) return;
            this.closeSignalSent = true;
            this.closing = true;
            if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
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
        window.addEventListener('beforeunload', closeWorkspace, { once: true });
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
                void this.handleAICommandMessage(message);
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
        if (!sessionId || this.tabs.has(sessionId)) return;

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
        this.tabs.set(sessionId, {
            sessionId,
            title: documentState.title || 'Untitled',
            tab,
            select,
            close,
            pane,
        });
        this.syncCloseButtons();
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

    loadDocument(entry) {
        if (!entry || entry.pane.dataset.loaded === 'true') return;
        entry.pane.dataset.loaded = 'true';
        entry.pane.src = entry.pane.dataset.editorUrl;
    }

    async createDocument() {
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
            this.activateDocument(documentState.session_id);
        } catch (error) {
            this.showError(`Could not create a new document: ${error.message}`);
        } finally {
            this.newButton.disabled = false;
        }
    }

    async uploadFileToSession(sessionId, file, inputFormat = '', index = ':') {
        const params = new URLSearchParams({
            filename: file?.name || 'structure',
            index: index || ':',
        });
        if (inputFormat) params.set('input_format', inputFormat);
        return await this.request(
            `/api/file/load/${encodeURIComponent(sessionId)}?${params.toString()}`,
            {
                method: 'POST',
                headers: {'Content-Type': file?.type || 'application/octet-stream'},
                body: file,
            }
        );
    }

    async loadPathToSession(sessionId, path, inputFormat = '', index = ':') {
        return await this.request(
            `/api/file/load-path/${encodeURIComponent(sessionId)}`,
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    path,
                    input_format: inputFormat || '',
                    index: index || ':',
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
            const data = hasServerPath
                ? await this.loadPathToSession(
                    documentState.session_id,
                    message.serverPath,
                    message.inputFormat || '',
                    message.index || ':'
                )
                : await this.uploadFileToSession(
                    documentState.session_id,
                    message.file,
                    message.inputFormat || '',
                    message.index || ':'
                );
            documentState.title = data.loaded_file?.filename || message.fileName || message.file?.name || 'Untitled';
            documentState.empty = false;
            this.addDocument(documentState);
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
            }
            respond({ok: false, error: error.message});
        }
    }

    async closeDocument(sessionId) {
        if (!this.tabs.has(sessionId) || this.tabs.size <= 1) return;
        const ordered = [...this.tabs.keys()];
        const index = ordered.indexOf(sessionId);
        const fallback = ordered[index + 1] || ordered[index - 1];
        const entry = this.tabs.get(sessionId);
        entry.close.disabled = true;
        try {
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
                this.activateDocument(fallback);
            }
        } catch (error) {
            entry.close.disabled = false;
            this.showError(`Could not close the document: ${error.message}`);
        }
    }

    syncCloseButtons() {
        const onlyDocument = this.tabs.size <= 1;
        this.tabs.forEach(entry => {
            entry.close.disabled = onlyDocument;
            entry.close.title = onlyDocument
                ? 'Keep at least one structure tab open'
                : 'Close tab';
        });
    }

    handleDocumentMessage(event) {
        if (event.origin !== window.location.origin) return;
        const message = event.data || {};
        if (!message.type?.startsWith('v_ase:document-')) return;
        const entry = this.tabs.get(message.sessionId);
        if (!entry || entry.pane.contentWindow !== event.source) return;
        if (message.type === 'v_ase:document-open-new') {
            this.openDocumentFromFile(entry, message);
            return;
        }
        if (message.type === 'v_ase:document-title' || message.type === 'v_ase:document-ready') {
            this.updateDocumentTitle(message.sessionId, message.title);
        }
        if (message.type === 'v_ase:document-ready') {
            entry.pane.contentWindow?.postMessage({
                type: 'v_ase:workspace-active',
                active: this.activeSessionId === message.sessionId,
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

    createAIBridge() {
        const workspace = this;
        return Object.freeze({
            protocol: 'v_ase.ai.v1',
            ready: async () => {
                await workspace.ready;
                const bridge = await workspace.waitForActiveAIBridge();
                return await bridge.ready();
            },
            describe: async options => {
                await workspace.ready;
                return await (await workspace.waitForActiveAIBridge()).describe(options);
            },
            capabilities: async () => {
                await workspace.ready;
                return await (await workspace.waitForActiveAIBridge()).capabilities();
            },
            documents: async () => {
                await workspace.ready;
                return {
                    activeSessionId: workspace.activeSessionId,
                    documents: [...workspace.tabs.values()].map(entry => ({
                        sessionId: entry.sessionId,
                        title: entry.title,
                        active: entry.sessionId === workspace.activeSessionId
                    }))
                };
            },
            activate: async sessionId => {
                await workspace.ready;
                if (!workspace.tabs.has(sessionId)) {
                    throw new Error(`Unknown v_ase document session '${sessionId}'.`);
                }
                workspace.activateDocument(sessionId);
                return await (await workspace.waitForActiveAIBridge()).ready();
            },
            newDocument: async () => {
                await workspace.ready;
                await workspace.createDocument();
                return await (await workspace.waitForActiveAIBridge()).ready();
            },
            apply: async command => {
                await workspace.ready;
                return await (await workspace.waitForActiveAIBridge()).apply(command);
            },
            render: async request => {
                await workspace.ready;
                return await (await workspace.waitForActiveAIBridge()).render(request);
            },
            export: async request => {
                await workspace.ready;
                return await (await workspace.waitForActiveAIBridge()).export(request);
            }
        });
    }

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

    async handleAICommandMessage(message) {
        if (
            message?.type !== 'ai_command'
            || !message.command_id
            || !message.method
            || !message.result_url
        ) {
            return false;
        }
        let payload;
        try {
            await this.ready;
            const bridge = window.v_aseAI || this.createAIBridge();
            const method = String(message.method);
            if (typeof bridge[method] !== 'function') {
                throw new Error(`AI method '${method}' is not available on this workspace.`);
            }
            const noArgumentMethods = new Set([
                'ready', 'capabilities', 'documents', 'newDocument'
            ]);
            let result;
            if (noArgumentMethods.has(method)) {
                result = await bridge[method]();
            } else if (method === 'activate') {
                const sessionId = (
                    message.params && typeof message.params === 'object'
                    ? message.params.sessionId
                    : message.params
                );
                result = await bridge.activate(sessionId);
            } else {
                result = await bridge[method](message.params ?? {});
            }
            payload = { ok: true, result };
        } catch (error) {
            payload = {
                ok: false,
                error: {
                    name: String(error?.name || 'Error'),
                    message: String(error?.message || error || 'AI command failed.')
                }
            };
        }
        try {
            await this.postAICommandResult(message, payload);
        } catch (error) {
            console.error(error);
        }
        return true;
    }
}

const workspace = new VAseWorkspace();
workspace.ready = workspace.init().catch(error => {
    workspace.showError(error.message);
    throw error;
});
window.__V_ASE_WORKSPACE__ = workspace;
window.v_aseAI = workspace.createAIBridge();
window.__V_ASE_AI__ = window.v_aseAI;
