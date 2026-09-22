// File authority is runtime-only. Never include browser handles in a project
// archive or portable visual settings.
export function projectProvenanceFromLoad(data, {
    filename = '', file = null, handle = null
} = {}) {
    if (data?.loaded_file?.kind !== 'project' && !data?.project) return null;
    const name = String(data?.loaded_file?.filename || filename || file?.name || 'project.vase');
    const sourceFormat = String(data?.loaded_file?.format || '').toLowerCase();
    const format = sourceFormat.includes('html') || /\.html?$/i.test(name) ? 'html' : 'vase';
    const settings = data?.project?.settings || data?.metadata?.config?.initial_design_settings || {};
    const serverBinding = data?.loaded_file?.project_file_binding
        || data?.metadata?.project_file_binding || null;
    const contentVersion = handle && Number.isFinite(Number(file?.size))
        && Number.isFinite(Number(file?.lastModified))
        ? { size: Number(file.size), lastModified: Number(file.lastModified) } : null;
    return {
        format,
        filename: name,
        handle,
        serverBinding,
        contentVersion,
        outputProfile: format === 'html'
            ? settings?.projectSave?.html?.exportProfile || settings?.imageExportProfile || null
            : null
    };
}

export function projectProvenanceFromApp(app) {
    const file = app?.projectFile;
    if (!file || !['vase', 'html'].includes(file.format)) return null;
    return {
        format: file.format,
        filename: file.filename || app.workspaceDocumentTitle(),
        handle: file.handle || null,
        serverBinding: file.serverBinding || null,
        contentVersion: file.contentVersion || null,
        outputProfile: file.format === 'html' ? file.outputProfile || null : null
    };
}
