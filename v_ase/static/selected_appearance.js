// Selected appearance owns label settings, not a second, invisible override layer.
// The initial label split and its first input gesture share one undo entry.
export class SelectedAppearanceEditor {
    constructor(app) {
        this.app = app;
        this.context = null;
        this.transaction = null;
        this.pending = null;
        this.labelPending = null;
        this.scopeRequest = null;
        document.getElementById('selected-frame-scope-value').onchange = event => {
            this.finishGesture();
            this.reset();
            this.app.state.display.selectedAppearanceFrameScope = event.target.value;
            this.app.updateProjectDirtyState();
        };
    }

    get preferredScope() {
        return this.app.state.display.selectedAppearanceFrameScope || 'all';
    }

    syncAssignmentScope() {
        const a = this.app;
        const panel = document.getElementById('selected-frame-scope');
        const field = document.getElementById('selected-frame-scope-value');
        const message = document.getElementById('selected-frame-scope-reason');
        const indices = a.selectedAtomIndices();
        panel.hidden = a.loadedFrameCount() <= 1 || !indices.length;
        if (panel.hidden) { this.scopeRequest = null; return null; }
        const frame = a.currentTrajectoryFrame();
        const overrides = a.viewIdentityOverridesSnapshot();
        const key = JSON.stringify([a.sessionId, a.energySeriesIdentity(), indices, overrides]);
        if (this.scopeRequest?.key !== key) {
            const request = { key, result: null };
            this.scopeRequest = request;
            request.promise = a.api.jsonPost('/api/trajectory/appearance-scope/{session_id}', {
                frame_index: frame, indices, view_identity_overrides: overrides,
            }).then(result => { request.result = result; }, error => {
                request.result = { all_frames: false, reason: error.message };
            }).finally(() => { if (this.scopeRequest === request) this.syncAssignmentScope(); });
        }
        const result = this.scopeRequest.result;
        field.disabled = result === null;
        field.options[0].disabled = !result?.all_frames;
        field.value = result?.all_frames ? this.preferredScope : 'current';
        message.textContent = result ? (result.reason || '') : 'Checking selected indices across the trajectory…';
        message.hidden = !message.textContent;
        return this.scopeRequest;
    }

    async assignmentScope(context) {
        if (this.app.loadedFrameCount() <= 1) return 'current';
        if (context.scopeDecision) return await context.scopeDecision;
        const a = this.app;
        const request = this.syncAssignmentScope();
        context.scopeDecision = (async () => {
            await request?.promise;
            if (this.context !== context || context.key !== this.selectionKey()) return null;
            if (this.scopeRequest !== request) return null;
            if (request?.result?.all_frames && this.preferredScope === 'all') return 'all';
            const confirmed = await a.showConfirmModal({
                title: 'Apply to this frame?',
                intro: '현재 프레임에서 선택한 원자의 라벨을 변경합니다. 이 궤적의 라벨 기반 분석 결과가 초기화되며, 기존 설정으로 다시 계산할 수 있습니다.',
                confirmText: 'Apply to this frame',
                cancelText: 'Cancel',
            });
            return confirmed && this.context === context && context.key === this.selectionKey() ? 'current' : null;
        })();
        try { return await context.scopeDecision; }
        finally { context.scopeDecision = null; }
    }

    selectionChanged() {
        const key = this.selectionKey();
        if (this.context?.key !== key) {
            this.finishGesture();
            this.context = null;
        }
    }

    selectionKey() {
        return `${this.app.state.vizOnly}:${this.app.currentTrajectoryFrame()}:${this.app.selectedAtomIndices().join(',')}`;
    }

    reset() {
        this.context = null;
    }

    valueForRadius(index) {
        this.selectionChanged();
        return this.context?.indices.includes(index) ? this.context.scale : this.app.atomRadiusScaleOverride(index);
    }

    contextForSelection() {
        this.selectionChanged();
        if (this.context) return this.context;
        const a = this.app, indices = a.selectedAtomIndices();
        this.context = { key: this.selectionKey(), indices, owned: false, scale: 1, radii: new Map() };
        return this.context;
    }

    beginAssignments(context, requestedLabel = null, merge = false, scope = 'current') {
        const a = this.app, d = a.state.display;
        a.flushVisualHistoryCommit();
        const transaction = { before: a.visualHistorySnapshot(), atoms: a.clonePlain(a.state.atoms),
            done: false, finish: context.finishRequested };
        this.transaction = transaction;
        const effectiveOverrides = a.viewIdentityOverridesSnapshot();
        context.scope = scope;
        const isolated = scope === 'current' && a.loadedFrameCount() > 1;
        const overrideKeys = ['atomMaterials', 'atomColors', 'atomOpacities', 'atomRadiusScales', 'atomBondStyles'];
        const inheritLabel = [];
        const used = new Set(a.uniqueAtomLabels());
        if (merge) {
            // Pin inherited defaults before changing membership. Otherwise a
            // lower-index atom of another element can become the label's first
            // atom and silently change the old members' fallback color/radius.
            (d.labelColors ||= {})[requestedLabel] = a.labelVisualColor(requestedLabel);
            (d.labelRadii ||= {})[requestedLabel] = Number(d.labelRadii?.[requestedLabel]) || a.labelVisualRadius(requestedLabel);
            (d.labelMaterials ||= {})[requestedLabel] = a.normalizedAtomMaterialPreset(d.labelMaterials?.[requestedLabel]);
            (d.labelOpacities ||= {})[requestedLabel] = d.labelOpacities?.[requestedLabel] ?? 1;
            (d.labelVisible ||= {})[requestedLabel] = d.labelVisible?.[requestedLabel] !== false;
        }
        const assignments = {}, groups = new Map();
        for (const index of context.indices) {
            const source = a.state.atoms.symbols[index];
            const element = a.state.atoms.chemical_symbols?.[index] || source;
            const radius = (Number(d.labelRadii?.[source]) || a.labelVisualRadius(source)) * a.atomRadiusScaleOverride(index);
            const appearance = { color: a.atomManualColor(index), opacity: a.atomManualOpacity(index),
                material: a.atomMaterialPreset(index), radius, visible: d.labelVisible?.[source] !== false,
                bond: a.renderer.bondEndpointOverride(index) };
            const signature = requestedLabel || JSON.stringify([element, source, appearance]);
            let group = groups.get(signature);
            if (!group) {
                used.add(element); // Automatic labels always start at element_2.
                const label = requestedLabel || a.uniqueTransitionLabel(element, used);
                used.add(label);
                group = { label, source, appearance, indices: [] };
                groups.set(signature, group);
                context.radii.set(label, merge ? (Number(d.labelRadii?.[label]) || a.labelVisualRadius(label)) : radius);
            }
            group.indices.push(index);
            assignments[index] = group.label;
        }
        d.retainedLabels = [...new Set([...(d.retainedLabels || []), ...[...groups.values()].map(group => group.source)])];
        for (const { label, source, appearance, indices } of groups.values()) {
            if (!merge) {
                a.transferLabelDisplaySettings(source, label, { removeSource: false });
                for (const [map, value] of Object.entries({ labelColors: appearance.color,
                    labelOpacities: appearance.opacity, labelMaterials: appearance.material,
                    labelRadii: appearance.radius, labelVisible: appearance.visible })) {
                    (d[map] ||= {})[label] = value;
                }
                if (appearance.bond) (d.labelBondStyles ||= {})[label] = { ...appearance.bond };
            }
            for (const index of indices) {
                if (isolated && overrideKeys.some(map => d[map]?.[index] !== undefined)) {
                    a.state.atoms.label_appearance ||= Array(a.state.atoms.symbols.length).fill(false);
                    a.state.atoms.label_appearance[index] = true;
                    inheritLabel.push(index);
                }
                if (!isolated) {
                    for (const map of overrideKeys) if (d[map]) delete d[map][index];
                }
                a.state.atoms.symbols[index] = label;
                if (a.state.atoms.atom_types) a.state.atoms.atom_types[index] = label;
            }
            a.renderer.renameAtomLabel(null, label, indices, d);
        }
        context.owned = !merge;
        context.scale = 1;
        a.rebuildLabelIndexCache(a.state.atoms.symbols);
        a.reconcileLabelOrder(a.state.atoms.symbols);
        this.refresh();
        // Optimistic preview is synchronous. Save/Undo wait for the whole commit,
        // including applying the returned atom data, not merely the HTTP request.
        this.pending = (async () => {
            try {
                const data = await a.api.jsonPost('/api/trajectory/labels/{session_id}', {
                    assignments, frame_index: a.currentTrajectoryFrame(), frame_scope: scope,
                    view_identity_overrides: effectiveOverrides,
                    label_appearance_indices: inheritLabel,
                });
                a.clearViewIdentityOverrides();
                a.invalidateTrajectoryLabelAnalysis();
                a.setAtomsData(data, { preserveDisplay: false, preserveRdf: true });
                transaction.done = true;
                this.refresh();
                if (transaction.finish) this.finishGesture();
            } catch (error) {
                this.transaction = null;
                this.context = null;
                a.setAtomsData(transaction.atoms, { preserveDisplay: false });
                a.applyVisualHistorySnapshot(transaction.before);
                throw error;
            } finally {
                this.pending = null;
            }
        })();
        this.pending.catch(error => a.toast(`Appearance update failed: ${error.message}`, 'error'));
    }

    refresh() {
        const a = this.app;
        a.renderer.setDisplayOptions(a.state.display);
        a.renderAppearanceRows();
        a.renderPairwiseBondControls({ capture: false });
        a.updateSelectedAppearanceControls();
        a.updateSelectionVisuals();
        a.updateProjectDirtyState();
    }

    async change(field, value) {
        const a = this.app, context = this.contextForSelection();
        if (!context.indices.length) return;
        if (this.labelPending) {
            this.labelPending.then(() => this.change(field, value));
            return;
        }
        if (field === 'material' && a.state.display.atomDisplayMode === '2d') return;
        if (field === 'color' && !a.validHexColor(value)) return;
        if (['opacity', 'radiusScale'].includes(field)) {
            if (value === '') return;
            value = Number(value);
            const [min, max] = field === 'opacity' ? [0, 1] : [0.25, 2.5];
            if (!Number.isFinite(value) || value < min || value > max) return;
        }
        if (!context.owned) {
            const scope = a.loadedFrameCount() <= 1 ? 'current' : await this.assignmentScope(context);
            if (!scope || this.context !== context) { this.refresh(); return; }
            if (!context.owned) this.beginAssignments(context, null, false, scope);
        }
        const d = a.state.display;
        const map = { color: 'labelColors', material: 'labelMaterials', opacity: 'labelOpacities', radiusScale: 'labelRadii' }[field];
        const labels = new Set(context.indices.map(index => a.state.atoms.symbols[index]));
        if (field === 'radiusScale') context.scale = value;
        for (const label of labels) (d[map] ||= {})[label] = field === 'radiusScale' ? context.radii.get(label) * value : value;
        if (d.selectedAppearanceAffectsBonds !== false && ['material', 'opacity'].includes(field)) {
            if (a.loadedFrameCount() > 1) {
                for (const label of labels) ((d.labelBondStyles ||= {})[label] ||= {})[field] = value;
            } else {
                for (const index of context.indices) ((d.atomBondStyles ||= {})[index] ||= {})[field] = value;
            }
        }
        this.refresh();
        if (!this.transaction) a.scheduleVisualHistoryCommit('selected-appearance');
    }

    async commitLabel(value) {
        const a = this.app, label = a.normalizedTypeLabel(value);
        if (!label) { this.refresh(); return false; }
        await this.settle();
        const context = this.contextForSelection();
        if (!context.indices.length || context.indices.every(index => a.state.atoms.symbols[index] === label)) return true;
        const scope = await this.assignmentScope(context);
        if (!scope) { this.refresh(); return false; }
        const merge = a.uniqueAtomLabels().includes(label);
        if (merge) {
            const escaped = label.replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
            const yes = await a.showConfirmModal({ title: `Merge into ${escaped}?`,
                intro: 'The selected atoms will inherit this label’s appearance.',
                items: ['Color, radius, opacity, material, visibility and bond settings use the existing label.',
                    'Chemical elements and coordinates stay unchanged. Undo restores the previous labels and appearance.'],
                confirmText: 'Yes, merge' });
            if (!yes || context.key !== this.selectionKey()) { this.refresh(); return false; }
        }
        context.radii.clear();
        this.beginAssignments(context, label, merge, scope);
        this.finishGesture();
        await this.pending;
        return true;
    }

    finishGesture() {
        const t = this.transaction, a = this.app;
        if (!t) {
            if (this.context?.scopeDecision) this.context.finishRequested = true;
            a.flushVisualHistoryCommit();
            return;
        }
        t.finish = true;
        if (!t.done) return;
        const after = a.visualHistorySnapshot();
        if (t.action) t.action.visualAfter = after;
        else a.recordHistoryAction({ kind: 'visual', source: 'selected-label-appearance', before: t.before, after });
        this.transaction = null;
        a.resetVisualHistoryBaseline();
        a.updateProjectDirtyState();
        a.scheduleCollaborationEvent({ source: a.currentCollaborationActor(), categories: ['display', 'structure'],
            changedPaths: ['display', 'structure.labels'], summary: 'Selected atom labels and appearance changed.' });
    }

    async settle() {
        await this.pending;
        this.finishGesture();
    }
}
