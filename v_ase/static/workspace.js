class VAseWorkspace {
    constructor() {
        const params = new URLSearchParams(window.location.search);
        this.workspaceId = params.get('workspace_id');
        this.requestedSessionId = params.get('session_id');
        this.tabs = new Map();
        this.activeSessionId = null;
        this.socket = null;
        this.closing = false;
        this.reconnectTimer = null;

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
        window.addEventListener('pagehide', () => {
            this.closing = true;
            if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
            try {
                if (this.socket?.readyState <= WebSocket.OPEN) {
                    this.socket.close(1000, 'workspace closing');
                }
            } catch {
                // Browser teardown can race WebSocket state changes.
            }
        }, { once: true });
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
        const url = `${protocol}//${window.location.host}/ws/workspace/${encodeURIComponent(this.workspaceId)}`;
        this.socket = new WebSocket(url);
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

        this.tabRoot.appendChild(tab);
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
}

const workspace = new VAseWorkspace();
workspace.init().catch(error => workspace.showError(error.message));
