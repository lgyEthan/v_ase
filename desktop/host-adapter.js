/* Runs only in the trusted local workspace. Reuses the published GUI handlers. */
(async () => {
    if (window.__vaseDesktopHost || !window.vaseDesktop) return;
    const native = window.vaseDesktop;
    const { EDITOR_COMMANDS, commandIdForEvent } = await import('/static/editor_commands.js?v=0.4.7');
    const installed = new WeakSet();
    const { detachWorkspaceDocument, restoreWindowDocument } = await import('/static/workspace_windows.js?v=0.4.7');
    let transfer = null;
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const workspace = () => window.__V_ASE_WORKSPACE__;
    const activeApp = () => {
        const ws = workspace();
        const entry = ws?.tabs.get(ws.activeSessionId);
        return entry?.host ? ws.app : entry?.pane?.contentWindow?.__ASE_APP__ || window.__ASE_APP__;
    };
    const report = error => activeApp()?.toast(error.message || String(error), 'error');

    function fileHandle(description) {
        const { token, name } = description;
        return {
            kind: 'file', name, desktopToken: token,
            getFile: () => native.stat(token),
            queryPermission: async () => 'granted',
            requestPermission: async () => 'granted',
            isSameEntry: other => other?.desktopToken ? native.same(token, other.desktopToken) : false,
            createWritable: async () => {
                const id = await native.begin(token);
                let closed = false;
                return {
                    write: async blob => {
                        if (closed) throw new Error('Save transaction is closed.');
                        for (let start = 0; start < blob.size; start += 4 * 1024 * 1024) {
                            const bytes = new Uint8Array(await blob.slice(start, start + 4 * 1024 * 1024).arrayBuffer());
                            await native.chunk(id, bytes);
                        }
                    },
                    close: async () => { await native.finish(id); closed = true; },
                    abort: async () => { if (!closed) await native.abort(id); closed = true; },
                };
            },
        };
    }

    async function waitForApp() {
        for (let attempt = 0; attempt < 600; attempt++) {
            const app = activeApp();
            if (app?.collaborationReady && (!app.workspaceChild || app.workspaceRecoveryAcknowledged)) { install(app); return app; }
            await sleep(50);
        }
        throw new Error('The document is still loading. Try again when it is ready.');
    }

    async function open(selected) {
        if (!selected) return;
        if (transfer) throw new Error('Wait until the tab finishes moving before opening another file.');
        const app = await waitForApp();
        const parts = [];
        let offset = 0;
        while (offset < selected.size) {
            const bytes = await native.read(selected.token, offset);
            if (!bytes.byteLength) throw new Error('The file changed while opening. Choose it again.');
            parts.push(bytes); offset += bytes.byteLength;
        }
        const file = new File(parts, selected.name, { lastModified: selected.lastModified });
        app.showOpenFileModal(file, { handle: fileHandle(selected) });
    }

    function install(app) {
        if (!app || installed.has(app)) return;
        installed.add(app);
        const ws = workspace();
        if (ws) ws.closeLastDocument = () => native.closeWindow();
        app.droppedFileHandle = async file => {
            const selected = await native.openDropped(file);
            return selected ? fileHandle(selected) : null;
        };
        app.openWorkspaceWindow = async payload => {
            const provenance = payload.snapshot?.provenance;
            const serialized = { ...payload, snapshot: payload.snapshot ? { ...payload.snapshot,
                provenance: provenance ? { ...provenance, handle: null,
                    desktopToken: provenance.handle?.desktopToken || null } : null } : null };
            return native.newWindow(serialized);
        };
        app.filePickerAdapter = { showSaveFilePicker: async options => {
            const selected = await native.chooseSave(options);
            if (!selected) throw new DOMException('Save cancelled', 'AbortError');
            return fileHandle(selected);
        } };
        app.chooseSystemStructureFile = async () => {
            try { await open(await native.chooseOpen()); } catch (error) { report(error); }
        };
        const originalNew = app.openStructureFileInNewTab.bind(app);
        app.openStructureFileInNewTab = async (file, inputFormat = '', index = ':', runtimeMode = null, options = {}) => {
            if (!options.handle?.desktopToken) return originalNew(file, inputFormat, index, runtimeMode, options);
            const ws = workspace();
            if (ws.openFileInNewTab) return ws.openFileInNewTab(file, inputFormat, index, runtimeMode,
                { handle: options.handle, volumetricPrecision: app.volumetricImportPrecision() });
            const requestId = `desktop:${app.sessionId}:${crypto.randomUUID()}`;
            try {
                await new Promise((resolve, reject) => {
                    app.workspaceOpenRequests.set(requestId, { resolve, reject });
                    void ws.openDocumentFromFile(ws.tabs.get(app.sessionId), {
                        type: 'v_ase:document-open-new', sessionId: app.sessionId, requestId,
                        file, handle: options.handle, fileName: file.name, inputFormat, index,
                        volumetricPrecision: app.volumetricImportPrecision(),
                        runtimeMode,
                    });
                });
            } catch (error) { app.workspaceOpenRequests.delete(requestId); report(error); }
        };
        const doc = app.renderer.domElement.ownerDocument;
        const showShortcuts = app.showShortcutsModal.bind(app);
        app.showShortcutsModal = () => {
            showShortcuts();
            for (const note of doc.querySelectorAll('#modal-content .panel-note')) {
                if (note.textContent.includes('Browser or operating-system reserved')) {
                    note.textContent = 'Desktop commands work in ordinary and fullscreen windows. Command on macOS; Ctrl on Windows. Closing the last tab closes its window; closing the last window quits after checking unsaved work.';
                }
            }
        };
    }

    const observer = new MutationObserver(() => {
        for (const frame of document.querySelectorAll('iframe')) {
            if (frame.dataset.desktopObserved) continue;
            frame.dataset.desktopObserved = 'true';
            frame.addEventListener('load', () => {
                try { install(frame.contentWindow.__ASE_APP__); } catch {}
            });
        }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    // Document-ready messages occur after asynchronous app initialization.
    window.addEventListener('message', event => {
        if (event.origin !== location.origin || event.data?.type !== 'v_ase:document-ready') return;
        try { install(event.source.__ASE_APP__); } catch {}
    });
    const host = {
        commands: EDITOR_COMMANDS,
        commandForInput: input => commandIdForEvent({
            code: input.code, key: input.key, shiftKey: input.shift, ctrlKey: input.control,
            metaKey: input.meta, altKey: input.alt, isComposing: input.isComposing,
        }, native.platform === 'darwin' ? 'mac' : 'windows'),
        async command(id) {
            if (transfer) throw new Error('Wait until the tab finishes moving to its new window.');
            const app = await waitForApp();
            if (id === 'open') return app.chooseSystemStructureFile();
            if (id === 'detach-tab') return host.detach(workspace().activeSessionId);
            if (id === 'new-window') {
                const ws = workspace();
                const state = await ws.createDocument({ activate: true });
                if (!state) return;
                await waitForApp();
                return host.detach(state.session_id);
            }
            if (id === 'shortcuts') return app.showShortcutsModal();
            return app.executeEditorCommand(id);
        },
        async confirmQuit() {
            if (transfer) { report(new Error('Wait until the tab finishes moving to its new window.')); return false; }
            const ws = workspace();
            if (!ws?.tabs) return activeApp() ? activeApp().confirmDocumentClose() : true;
            const previous = ws.activeSessionId;
            for (const [id, entry] of ws.tabs) {
                if (entry.pane?.dataset.loaded !== 'true' && !entry.dirty) continue;
                (ws.activateDocument || ws.activate).call(ws, id);
                const app = await waitForApp();
                if (!await app.confirmDocumentClose()) return false;
            }
            if (ws.tabs.has(previous)) (ws.activateDocument || ws.activate).call(ws, previous);
            return true;
        },
        async restore(snapshot) {
            const app = await waitForApp();
            if (snapshot?.provenance?.desktopToken) {
                snapshot.provenance.handle = fileHandle({ token: snapshot.provenance.desktopToken,
                    name: snapshot.provenance.filename });
                delete snapshot.provenance.desktopToken;
            }
            restoreWindowDocument(app, snapshot);
            const entry = workspace()?.tabs.get(app.sessionId);
            workspace()?.captureDocumentProvenance?.(entry, app);
            return true;
        },
        async detach(sessionId, position = null) {
            if (transfer) return transfer;
            const ws = workspace();
            (ws.activateDocument || ws.activate).call(ws, sessionId);
            const app = await waitForApp();
            transfer = detachWorkspaceDocument(ws, sessionId, payload => app.openWorkspaceWindow({ ...payload, position }));
            try { return await transfer; } finally { transfer = null; }
        },
        open,
    };
    window.__vaseDesktopHost = host;
    // Pointer capture keeps the gesture alive outside the tab strip/window.
    let tabDrag = null;
    let suppressDragClick = false;
    const tabSelector = '.document-tab, .direct-document-tab';
    document.addEventListener('pointerdown', event => {
        const tab = event.target.closest(tabSelector);
        if (!tab || event.button !== 0 || event.target.closest('.document-close, .direct-document-close')) return;
        tabDrag = { tab, id: tab.dataset.sessionId, x: event.clientX, y: event.clientY,
            pointer: event.pointerId, moved: false, title: tab.title };
        suppressDragClick = false;
        tab.setPointerCapture(event.pointerId);
    });
    document.addEventListener('pointermove', event => {
        if (!tabDrag || event.pointerId !== tabDrag.pointer) return;
        if (Math.hypot(event.clientX-tabDrag.x, event.clientY-tabDrag.y) < 8) return;
        tabDrag.moved = true;
        tabDrag.tab.style.opacity = '0.5';
        tabDrag.tab.title = 'Release below the tab strip to move this document into a new window';
        event.preventDefault();
    });
    const finishTabDrag = event => {
        const drag = tabDrag; tabDrag = null;
        if (!drag) return;
        drag.tab.style.opacity = '';
        drag.tab.title = drag.title;
        if (drag.tab.hasPointerCapture?.(drag.pointer)) drag.tab.releasePointerCapture(drag.pointer);
        if (!drag.moved || event.type === 'pointercancel') return;
        suppressDragClick = true;
        const bar = document.querySelector('#document-bar, #direct-document-bar').getBoundingClientRect();
        if (event.clientY > bar.bottom + 56 || event.clientY < -24 || event.clientX < -24 || event.clientX > innerWidth + 24) {
            event.preventDefault();
            host.detach(drag.id, { x: Math.max(0, event.screenX-150), y: Math.max(0,event.screenY-24) }).catch(report);
        } else {
            const target = [...document.querySelectorAll(tabSelector)].find(tab => {
                const rect = tab.getBoundingClientRect(); return event.clientX >= rect.left && event.clientX <= rect.right;
            });
            if (target && target !== drag.tab) {
                const before = event.clientX < target.getBoundingClientRect().left + target.clientWidth/2;
                target.parentNode.insertBefore(drag.tab, before ? target : target.nextSibling);
                const ws = workspace();
                ws.tabs = new Map([...document.querySelectorAll(tabSelector)]
                    .map(tab => [tab.dataset.sessionId, ws.tabs.get(tab.dataset.sessionId)]));
            }
        }
    };
    document.addEventListener('pointerup', finishTabDrag);
    document.addEventListener('pointercancel', finishTabDrag);
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || !tabDrag) return;
        event.preventDefault(); event.stopPropagation();
        finishTabDrag({ type: 'pointercancel' });
    }, true);
    document.addEventListener('click', event => {
        if (!suppressDragClick) return;
        suppressDragClick = false;
        event.preventDefault(); event.stopImmediatePropagation();
    }, true);

    native.onCommand(id => host.command(id).catch(report));
    native.onOpen(file => open(file).catch(report));
    for (const entry of workspace()?.tabs.values() || []) {
        try { install(entry.host ? workspace().app : entry.pane?.contentWindow?.__ASE_APP__); } catch {}
    }
    await waitForApp();
    const capture = document.getElementById('workspace-fullscreen-editing');
    const status = document.getElementById('workspace-shortcut-status');
    if (capture) capture.hidden = true;
    if (status) status.textContent = 'Desktop shortcuts';
})();
