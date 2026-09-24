import { projectProvenanceFromApp } from './project_provenance.js?v=0.4.4';

// Parent-owned runtime state. Browser handles never enter the project archive.
export function captureDocumentRecovery(entry, app = entry?.pane?.contentWindow?.__ASE_APP__) {
    if (!entry || !app?.collaborationReady || app !== entry.appInstance) return false;
    entry.provenance = projectProvenanceFromApp(app);
    entry.savedContent = {
        scientific: app.projectFile.savedScientificSignature,
        visual: app.projectFile.savedVisualSignature
    };
    entry.visualSnapshot = {
        ...app.visualHistorySnapshot(), camera: app.cameraSettingsSnapshot()
    };
    entry.recoveryRevision = app.recoveryRevision;
    entry.childGeneration = app.recoveryGeneration;
    return true;
}

export function restoreDocumentRecovery(entry, app) {
    if (!entry || !app) return false;
    const reloaded = entry.provenanceApplied;
    const provenance = entry.pendingProvenance || entry.provenance;
    if (provenance || reloaded) {
        app.adoptProjectProvenance(provenance);
        entry.provenanceApplied = true;
    }
    if (reloaded && entry.visualSnapshot) {
        // Initialization has already created its provisional baseline. A
        // later workspace-activation timer must not make a restored dirty
        // document clean (or replace the saved fingerprints after Save As).
        if (app.workspaceBaselineTimer !== null) {
            entry.pane?.contentWindow?.clearTimeout?.(app.workspaceBaselineTimer);
            app.workspaceBaselineTimer = null;
        }
        app.workspaceRecoveryRestored = true;
        app.workspaceBaselineSettled = true;
        app.applyVisualHistorySnapshot(entry.visualSnapshot);
        if (entry.savedContent?.scientific && entry.savedContent?.visual) {
            app.projectFile.savedScientificSignature = entry.savedContent.scientific;
            app.projectFile.savedVisualSignature = entry.savedContent.visual;
        }
        app.updateProjectDirtyState();
    }
    entry.pendingProvenance = null;
    entry.appInstance = app;
    captureDocumentRecovery(entry, app);
    return true;
}
