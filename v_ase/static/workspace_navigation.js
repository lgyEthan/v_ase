// Shared by notebook, browser workspace and native desktop document commands.
export function navigateWorkspaceDocument(workspace, commandId) {
    const ids = [...(workspace?.tabs?.keys() || [])];
    if (!ids.length) return false;
    const current = Math.max(0, ids.indexOf(workspace.activeSessionId));
    let index;
    if (commandId === 'previous-tab') index = (current - 1 + ids.length) % ids.length;
    else if (commandId === 'next-tab') index = (current + 1) % ids.length;
    else if (/^tab-[1-9]$/.test(commandId)) {
        const number = Number(commandId.slice(4));
        index = number === 9 ? ids.length - 1 : number - 1;
    } else return false;
    if (index >= ids.length || ids[index] === workspace.activeSessionId) return true;
    const entry = workspace.tabs.get(workspace.activeSessionId);
    const app = entry?.host ? workspace.app : entry?.pane?.contentWindow?.__ASE_APP__;
    const doc = app?.renderer?.domElement?.ownerDocument;
    if (doc?.getElementById('modal-container')?.classList.contains('hidden') === false) return true;
    if (app?.transform?.mode && app.transform.mode !== 'IDLE') {
        app.toast('Finish or cancel the transform before switching documents.', 'warning');
        return true;
    }
    workspace.activateDocument(ids[index]);
    const next = workspace.tabs.get(ids[index]);
    const nextApp = next?.host ? workspace.app : next?.pane?.contentWindow?.__ASE_APP__;
    nextApp?.renderer?.domElement?.focus({ preventScroll: true });
    return true;
}
