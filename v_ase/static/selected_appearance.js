// Selected appearance owns label settings, not a second, invisible override layer.
// The initial label split and its first input gesture share one undo entry.
export class SelectedAppearanceEditor {
    constructor(app) {
        this.app = app;
        this.context = null;
        this.transaction = null;
        this.pending = null;
        this.labelPending = null;
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

    beginAssignments(context, requestedLabel = null, merge = false) {
        const a = this.app, d = a.state.display;
        a.flushVisualHistoryCommit();
        const transaction = { before: a.visualHistorySnapshot(), atoms: a.clonePlain(a.state.atoms), done: false };
        this.transaction = transaction;
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
                material: a.atomMaterialPreset(index), radius, visible: d.labelVisible?.[source] !== false };
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
        for (const { label, source, appearance, indices } of groups.values()) {
            if (!merge) {
                a.transferLabelDisplaySettings(source, label, { removeSource: false });
                for (const [map, value] of Object.entries({ labelColors: appearance.color,
                    labelOpacities: appearance.opacity, labelMaterials: appearance.material,
                    labelRadii: appearance.radius, labelVisible: appearance.visible })) {
                    (d[map] ||= {})[label] = value;
                }
            }
            for (const index of indices) {
                for (const map of ['atomMaterials', 'atomColors', 'atomOpacities', 'atomRadiusScales', 'atomBondStyles']) {
                    if (d[map]) delete d[map][index];
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
        a.recordViewIdentityOverride();
        this.refresh();
        // Optimistic preview is synchronous. Save/Undo wait for the whole commit,
        // including applying the returned atom data, not merely the HTTP request.
        this.pending = (async () => {
            try {
                if (a.canEditAtoms()) {
                    const data = await a.api.assignAtomLabels(assignments, a.backendPositionsPayload(), a.state.applyConstraints);
                    a.setAtomsData(data, { preserveDisplay: false });
                }
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

    change(field, value) {
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
        if (!context.owned) this.beginAssignments(context);
        const d = a.state.display;
        const map = { color: 'labelColors', material: 'labelMaterials', opacity: 'labelOpacities', radiusScale: 'labelRadii' }[field];
        const labels = new Set(context.indices.map(index => a.state.atoms.symbols[index]));
        if (field === 'radiusScale') context.scale = value;
        for (const label of labels) (d[map] ||= {})[label] = field === 'radiusScale' ? context.radii.get(label) * value : value;
        if (d.selectedAppearanceAffectsBonds !== false && ['material', 'opacity'].includes(field)) {
            for (const index of context.indices) {
                const style = (d.atomBondStyles ||= {})[index] ||= {};
                style[field] = value;
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
        this.beginAssignments(context, label, merge);
        this.finishGesture();
        await this.pending;
        return true;
    }

    finishGesture() {
        const t = this.transaction, a = this.app;
        if (!t) { a.flushVisualHistoryCommit(); return; }
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
