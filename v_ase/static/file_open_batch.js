import { projectProvenanceFromLoad } from './project_provenance.js?v=0.4.11';

const pause = () => new Promise(resolve => setTimeout(resolve, 100));
const nameOf = entry => entry.name || entry.file?.name || entry.handle?.name || 'Untitled';
const ordered = entries => [...entries].sort((a, b) => nameOf(a).localeCompare(nameOf(b), 'en', { numeric: true }));
const getFile = entry => entry.file || entry.getFile?.() || entry.handle?.getFile();

// Stage in new backend sessions, then publish tabs only after every file reads.
// Existing documents and source files are never mutated. Only one file's upload
// buffer is held at a time, including native file grants and large trajectories.
export async function importFileBatch(workspace, app, entries, mode, { cancelled = () => false, progress = () => {} } = {}) {
    const staged = [];
    const sourceSession = app.sessionId;
    const check = () => { if (cancelled()) throw new DOMException('Opening cancelled', 'AbortError'); };
    const create = async () => {
        const state = await workspace.request(`/api/workspace/${workspace.workspaceId}/sessions`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_session_id: sourceSession })
        });
        const record = { state, result: null, provenance: null };
        staged.push(record);
        return record;
    };
    try {
        for (let index = 0; index < entries.length; index++) {
            check();
            const entry = entries[index];
            progress(index, entries.length, nameOf(entry));
            const record = mode === 'trajectory' && staged.length ? staged[0] : await create();
            check();
            const file = await getFile(entry);
            if (!file) throw new Error(`${nameOf(entry)} is unavailable. Choose it again.`);
            check();
            const params = new URLSearchParams({ filename: file.name, index: ':',
                volumetric_precision: app.volumetricImportPrecision() });
            if (mode !== 'trajectory' && !/\.(vase|html?)$/i.test(file.name)) params.set('runtime_mode', app.state.vizOnly ? 'view' : 'edit');
            let result;
            try {
                result = await workspace.request(`/api/file/${mode === 'trajectory' ? 'append' : 'load'}/${record.state.session_id}?${params}`, {
                    method: 'POST', headers: { 'Content-Type': file.type || 'application/octet-stream' }, body: file
                });
            } catch (error) { throw new Error(`${file.name}: ${error.message}`); }
            if (mode === 'trajectory' && result.loaded_file?.source_kind === 'volumetric') {
                throw new Error(`${file.name} contains a scalar field. Open scalar-field files in separate tabs.`);
            }
            record.result = result;
            record.state.title = record.state.title === 'Untitled' ? file.name : record.state.title;
            if (mode !== 'trajectory') record.provenance = projectProvenanceFromLoad(result, { file, handle: entry.handle });
            check();
        }
    } catch (error) {
        // Do not abort an in-flight upload: wait for it before deleting the
        // staging sessions, so the server cannot resurrect a cancelled import.
        const cleanup = await Promise.allSettled(staged.map(record => workspace.request(
            `/api/workspace/${workspace.workspaceId}/sessions/${record.state.session_id}/close`, { method: 'POST' })));
        if (cleanup.some(result => result.status === 'rejected')) {
            throw new Error(`${error.message} Some temporary imports could not close; reopen the workspace to inspect them.`);
        }
        throw error;
    }
    const result = [];
    for (const record of staged) {
        const entry = (workspace.addDocument || workspace.addTab).call(workspace, { ...record.state, empty: false });
        entry.pendingProvenance = entry.provenance = record.provenance;
        entry.pendingUnsaved = mode === 'trajectory';
        result.push(record.state.session_id);
    }
    const discardEmptySource = !app.hasScratchContent() && workspace.tabs.size > 1;
    (workspace.activateDocument || workspace.activate).call(workspace, result[0]);
    if (discardEmptySource) {
        const root = app.workspaceChild ? window.parent : window;
        const close = () => workspace.closeDocument(sourceSession).catch(console.error);
        if (root.__vaseFileOpenQueue?.running) (root.__vaseFileOpenQueue.deferredClose ||= []).push(close);
        else root.setTimeout(close, 0);
    }
    return result;
}

function showBatchChoice(group) {
    const { app } = group;
    const doc = app.renderer.domElement.ownerDocument;
    return new Promise(resolve => {
        app.showModal(`<h2>Open files</h2>
            <p class="modal-intro">Keep files in separate tabs, or combine their structures into a new trajectory. Your current documents stay open.</p>
            <fieldset class="open-file-modes">
                <legend>Open as</legend>
                <label class="open-file-mode"><input type="radio" name="open-batch-mode" value="tabs" checked>
                    <span><strong>Separate tabs</strong><small>One tab per file. Projects keep their saved mode and appearance.</small></span></label>
                <label class="open-file-mode"><input type="radio" name="open-batch-mode" value="trajectory">
                    <span><strong>One trajectory</strong><small>All frames, in the order below, in one new tab. Imports structures only; save as a new project.</small></span></label>
            </fieldset>
            <div class="open-batch-heading"><strong id="open-batch-count"></strong><span>Use arrows to change frame order</span></div>
            <ol id="open-batch-files" class="open-batch-files" aria-label="Files in frame order"></ol>`,
            '<button id="open-batch-cancel" class="btn">Cancel</button><button id="open-batch-confirm" class="btn primary">Open separate tabs</button>');
        const confirm = doc.getElementById('open-batch-confirm');
        group.refresh = () => {
            doc.getElementById('open-batch-count').textContent = `${group.entries.length} files`;
            const list = doc.getElementById('open-batch-files');
            list.replaceChildren();
            group.entries.forEach((entry, index) => {
                const row = doc.createElement('li');
                const name = doc.createElement('span'); name.textContent = nameOf(entry); name.title = name.textContent;
                row.append(name);
                for (const [direction, label, symbol] of [[-1, 'Move up', '↑'], [1, 'Move down', '↓']]) {
                    const button = doc.createElement('button'); button.type = 'button'; button.className = 'btn';
                    button.textContent = symbol; button.title = `${label}: ${nameOf(entry)}`;
                    button.setAttribute('aria-label', button.title);
                    button.disabled = index + direction < 0 || index + direction >= group.entries.length;
                    button.onclick = () => {
                        const next = index + direction;
                        [group.entries[index], group.entries[next]] = [group.entries[next], group.entries[index]];
                        group.refresh();
                        list.children[next]?.querySelector(`button:nth-of-type(${direction < 0 ? 1 : 2})`)?.focus();
                    };
                    row.append(button);
                }
                list.append(row);
            });
        };
        group.refresh();
        app.modalDismiss = () => { group.mergeable = false; group.refresh = null; resolve(null); };
        doc.getElementById('open-batch-cancel').onclick = () => app.closeModal();
        doc.querySelectorAll('[name="open-batch-mode"]').forEach(input => input.onchange = () => {
            confirm.textContent = input.value === 'trajectory' ? 'Open trajectory' : 'Open separate tabs';
        });
        confirm.onclick = () => {
            const mode = doc.querySelector('[name="open-batch-mode"]:checked').value;
            app.modalDismiss = null; group.mergeable = false; group.refresh = null; app.closeModal(); resolve(mode);
        };
    });
}

async function runGroup(group) {
    const { app } = group;
    const doc = app.renderer.domElement.ownerDocument;
    // An OS open event must not replace a pending save/discard or edit dialog.
    while (!doc.getElementById('modal-container')?.classList.contains('hidden')) await pause();
    if (group.entries.length === 1) {
        const entry = group.entries[0];
        const file = await getFile(entry);
        if (group.entries.length === 1) {
            // An additional OS event can promote an unconfirmed single-file
            // reader into the same batch chooser, even after the debounce.
            group.mergeable = !/\.vase$/i.test(file.name);
            group.refresh = group.mergeable ? () => app.closeModal() : null;
            await app.showOpenFileModal(file, { ...group.options, handle: entry.handle || null,
                onCommit: () => { group.mergeable = false; group.refresh = null; } });
            group.refresh = null;
            if (group.entries.length === 1 || !group.mergeable) return;
        }
    }
    const mode = await showBatchChoice(group);
    if (!mode) return;
    let cancelled = false;
    app.showModal('<h2>Opening files</h2><p id="open-batch-progress" role="status" aria-live="polite"></p><progress id="open-batch-progress-bar" max="1" value="0"></progress>',
        '<button id="open-batch-stop" class="btn">Cancel</button>');
    const progress = doc.getElementById('open-batch-progress');
    const bar = doc.getElementById('open-batch-progress-bar');
    const stop = doc.getElementById('open-batch-stop');
    const cancel = () => { cancelled = true; progress.textContent = 'Cancelling after the current file finishes…'; stop.disabled = true; };
    app.modalDismiss = cancel;
    stop.onclick = cancel;
    try {
        const workspace = app.workspaceChild ? window.parent.__V_ASE_WORKSPACE__ : await app.ensureDirectWorkspace();
        await importFileBatch(workspace, app, group.entries, mode, { cancelled: () => cancelled,
            progress: (index, total, name) => { progress.textContent = `Reading ${index + 1} of ${total}: ${name}`; bar.max = total; bar.value = index; } });
    } finally { app.modalDismiss = null; app.closeModal(); }
}

export function queueFileOpen(app, input, options = {}) {
    const entries = ordered(input.map(entry => entry instanceof Blob ? { file: entry } : entry));
    if (!entries.length) return Promise.resolve();
    const root = app.workspaceChild ? window.parent : window;
    const queue = root.__vaseFileOpenQueue ||= { pending: [], active: null, running: false };
    return new Promise(resolve => {
        if (queue.active?.mergeable) {
            // Explorer may deliver late processes after the first burst. Extend
            // the unconfirmed chooser, never overwrite it or lose those files.
            queue.active.entries.push(...entries); queue.active.resolvers.push(resolve);
            queue.active.refresh?.(); return;
        }
        const group = { app, entries, options, resolvers: [resolve], refresh: null, mergeable: true };
        queue.pending.push(group);
        if (queue.running) return;
        queue.running = true;
        void (async () => {
            try {
                while (queue.pending.length) {
                    const current = queue.active = queue.pending.shift();
                    const workspace = root.__V_ASE_WORKSPACE__;
                    const active = workspace?.tabs.get(workspace.activeSessionId);
                    current.app = active?.pane?.contentWindow?.__ASE_APP__ || current.app;
                    try { await runGroup(current); }
                    catch (error) { if (error.name !== 'AbortError') current.app.toast(`Open files failed: ${error.message}`, 'error'); }
                    finally { current.resolvers.forEach(done => done()); queue.active = null; }
                }
            } finally {
                queue.running = false;
                const closes = queue.deferredClose || []; queue.deferredClose = [];
                closes.forEach(close => root.setTimeout(close, 0));
            }
        })();
    });
}
