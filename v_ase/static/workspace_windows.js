import { projectProvenanceFromApp, projectProvenanceFromLoad } from './project_provenance.js?v=0.4.6';

export async function captureWindowDocument(app) {
    if (app.transform.mode !== 'IDLE' || app.addAtomsSessionActive() || app.state.isRelaxing
        || app.state.atoms?.metadata?.relaxation?.active || app.state.registryRelaxation
        || app.projectFile.saving || app.projectFile.savePromise || app.state.videoExportId) {
        throw new Error('Finish the current transform, job or save before moving this tab.');
    }
    const active = app.renderer.domElement.ownerDocument.activeElement;
    if (app.isCommittableInput(active) && !app.commitInputValue(active)) throw new Error('Correct the highlighted input first.');
    await app.settleScientificMutations();
    app.flushVisualHistoryCommit();
    app.stopPlayback();
    return {
        provenance: projectProvenanceFromApp(app),
        visual: { ...app.visualHistorySnapshot(), camera: app.cameraSettingsSnapshot() },
        saved: { scientific: app.projectFile.savedScientificSignature, visual: app.projectFile.savedVisualSignature },
        undo: app.clonePlain(app.undoTimeline), redo: app.clonePlain(app.redoTimeline),
        selection: app.selectionEntries(), measurement: app.clonePlain(app.state.measurementIntent),
        initialDesignSettings: app.clonePlain(app.initialDesignSettings), route: app.editorRoute,
    };
}

export function restoreWindowDocument(app, snapshot) {
    if (!snapshot) return;
    const win = app.renderer.domElement.ownerDocument.defaultView;
    if (app.workspaceBaselineTimer !== null) win.clearTimeout(app.workspaceBaselineTimer);
    app.workspaceBaselineTimer = null;
    app.workspaceRecoveryRestored = true;
    app.workspaceBaselineSettled = true;
    if (snapshot.provenance) app.adoptProjectProvenance(snapshot.provenance);
    if (snapshot.visual) app.applyVisualHistorySnapshot(snapshot.visual);
    if (snapshot.saved) {
        app.projectFile.savedScientificSignature = snapshot.saved.scientific;
        app.projectFile.savedVisualSignature = snapshot.saved.visual;
    }
    if (snapshot.undo) app.undoTimeline = snapshot.undo;
    if (snapshot.redo) app.redoTimeline = snapshot.redo;
    if (snapshot.initialDesignSettings) app.initialDesignSettings = snapshot.initialDesignSettings;
    if (snapshot.selection) app.applySelectionAction({ references: snapshot.selection, origin: 'semantic' });
    if (snapshot.measurement) app.state.measurementIntent = snapshot.measurement;
    if (snapshot.route) app.openEditorRoute(snapshot.route);
    app.updateSelectionVisuals(); app.updateUI(); app.updateProjectDirtyState();
}

export async function detachWorkspaceDocument(ws, sessionId, openWindow) {
    const entry = ws.tabs.get(sessionId);
    const app = entry?.host ? ws.app : entry?.pane?.contentWindow?.__ASE_APP__;
    if (!app?.collaborationReady || entry.closing) throw new Error('The document is not ready to move.');
    entry.closing = true;
    const doc = app.renderer.domElement.ownerDocument;
    const blockKey = event => { event.preventDefault(); event.stopImmediatePropagation(); };
    let moved;
    try {
        const snapshot = await captureWindowDocument(app);
        app.setBusy('Moving this document to a new window...');
        doc.body.inert = true;
        doc.defaultView.addEventListener('keydown', blockKey, true);
        moved = await ws.request(`/api/workspace/${ws.workspaceId}/sessions/${sessionId}/move`, { method: 'POST' });
        await openWindow({ ...moved, snapshot });
        // The destination acknowledges restored state before destroying the old editor.
        if (entry.host) {
            ws.hostClosed = true; app.dispose(); document.body.classList.add('direct-host-closed');
        } else {
            app.dispose(); entry.pane.remove();
        }
        entry.tab.remove(); ws.tabs.delete(sessionId);
        moved.source_documents.forEach(state => (ws.addDocument || ws.addTab).call(ws, state));
        if (ws.activeSessionId === sessionId) {
            ws.activeSessionId = null;
            (ws.activateDocument || ws.activate).call(ws, moved.source_documents[0].session_id);
        }
        ws.syncCloseButtons?.();
    } catch (error) {
        if (moved) {
            await ws.request(`/api/workspace/${moved.workspace_id}/sessions/${sessionId}/move`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_workspace_id: ws.workspaceId })
            });
            await ws.request(`/api/workspace/${moved.workspace_id}/close`, { method: 'POST' });
        }
        throw error;
    } finally {
        doc.body.inert = false;
        doc.defaultView.removeEventListener('keydown', blockKey, true);
        app.clearBusy();
        entry.closing = false;
    }
}

export async function openFileInWindow(app, file, inputFormat, index, runtimeMode, { handle = null } = {}) {
    // Reserve the browser popup during the trusted click, before file upload.
    const popup = app.openWorkspaceWindow ? null : window.open('about:blank', '_blank', 'popup,width=1440,height=960');
    if (!app.openWorkspaceWindow && !popup) throw new Error('Allow a popup for v_ase to open a separate window.');
    const ws = app.workspaceChild ? window.parent.__V_ASE_WORKSPACE__ : await app.ensureDirectWorkspace();
    let state, moved;
    try {
        state = await ws.request(`/api/workspace/${ws.workspaceId}/sessions`, { method: 'POST' });
        const params = new URLSearchParams({ filename: file.name, index: index || ':',
            input_format: inputFormat || '', runtime_mode: runtimeMode || 'edit',
            volumetric_precision: app.volumetricImportPrecision() });
        const data = await ws.request(`/api/file/load/${state.session_id}?${params}`, {
            method: 'POST', headers: { 'Content-Type': file.type || 'application/octet-stream' }, body: file });
        moved = await ws.request(`/api/workspace/${ws.workspaceId}/sessions/${state.session_id}/move`, { method: 'POST' });
        const snapshot = { provenance: projectProvenanceFromLoad(data, { file, handle }) };
        if (app.openWorkspaceWindow) await app.openWorkspaceWindow({ ...moved, snapshot });
        else {
            const root = window.top;
            root.__vaseWindowTransfers ||= new Map();
            root.__vaseWindowTransfers.set(state.session_id, snapshot);
            // The browser may present a tab instead of a window per its preferences.
            popup.location.href = `/workspace?workspace_id=${moved.workspace_id}&session_id=${state.session_id}&window_transfer=1`;
        }
    } catch (error) {
        popup?.close();
        if (moved) await ws.request(`/api/workspace/${moved.workspace_id}/close`, { method: 'POST' }).catch(() => {});
        else if (state) await ws.request(`/api/workspace/${ws.workspaceId}/sessions/${state.session_id}/close`, { method: 'POST' }).catch(() => {});
        app.toast(`Could not open window: ${error.message}`, 'error');
    }
}
