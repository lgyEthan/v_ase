// The two workspace shells share this bridge and the WebSocket command protocol.
export function documentTitle(entry) {
    const value = typeof entry?.name === 'string' ? entry.name
        : typeof entry?.title === 'string' ? entry.title
        : entry?.title?.textContent;
    return String(value || 'Untitled').trim() || 'Untitled';
}

export function createWorkspaceAIBridge(workspace) {
    const active = async () => {
        await workspace.ready;
        return workspace.waitForActiveAIBridge();
    };
    return Object.freeze({
        protocol: 'v_ase.ai.v1',
        ready: async () => (await active()).ready(),
        describe: async options => (await active()).describe(options),
        schema: async options => (await active()).schema(options),
        query: async request => (await active()).query(request),
        capabilities: async options => (await active()).capabilities(options),
        documents: async () => {
            await workspace.ready;
            return {
                activeSessionId: workspace.activeSessionId,
                documents: [...workspace.tabs.values()].map(entry => ({
                    sessionId: entry.sessionId,
                    title: documentTitle(entry),
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
            return (await workspace.waitForActiveAIBridge()).ready();
        },
        newDocument: async () => {
            await workspace.ready;
            await workspace.createDocument();
            return (await workspace.waitForActiveAIBridge()).ready();
        },
        apply: async command => (await active()).apply(command),
        render: async request => (await active()).render(request),
        export: async request => (await active()).export(request)
    });
}

export async function handleWorkspaceAICommand(workspace, message) {
    if (message?.type !== 'ai_command' || !message.command_id
        || !message.method || !message.result_url) return false;
    let payload;
    try {
        await workspace.ready;
        const bridge = workspace.aiBridge;
        const method = String(message.method);
        if (typeof bridge?.[method] !== 'function') {
            throw new Error(`AI method '${method}' is not available on this workspace.`);
        }
        const noArgumentMethods = new Set(['ready', 'documents', 'newDocument']);
        const result = noArgumentMethods.has(method)
            ? await bridge[method]()
            : method === 'activate'
                ? await bridge.activate(message.params && typeof message.params === 'object'
                    ? message.params.sessionId : message.params)
                : await bridge[method](message.params ?? {});
        payload = { ok: true, result };
    } catch (error) {
        payload = { ok: false, error: {
            name: String(error?.name || 'Error'),
            message: String(error?.message || error || 'AI command failed.'),
            ...(error?.code ? {code: error.code, outcome: error.outcome || 'unknown'} : {})
        } };
    }
    try {
        const target = new URL(String(message.result_url), window.location.origin);
        if (target.origin !== window.location.origin) {
            throw new Error('AI command result URL must use the current v_ase origin.');
        }
        const response = await fetch(target.href, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`Could not return AI command result: ${response.status}`);
    } catch (error) {
        console.error(error);
    }
    return true;
}
