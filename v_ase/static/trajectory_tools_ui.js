import { energyCaptureScale, energyCsv, energyPalette, energyPanelRect, energyPlot, normalizeEnergyOverlay,
    paintEnergyPanel, TrajectoryEnergyOverlay } from './trajectory_energy.js?v=0.5.1';
import { graphCapturePlacement } from './graph_export.js?v=0.5.1';
import { GraphSettingsInspector, installGraphActivation } from './graph_settings_ui.js?v=0.5.1';
import { editorIcon } from './editor_interactions.js?v=0.5.1&ui=20261111.1';

const energyPath = '/api/trajectory/energy/{session_id}';
const controlStyleFields = {
    'energy-reference': 'reference', 'energy-cursor': 'cursor', 'energy-tangent-scale': 'tangentScale',
};
const controlNebFields = {
    'energy-neb-fit': 'fit', 'energy-neb-tangents': 'tangents', 'energy-neb-images': 'images', 'energy-neb-mic': 'mic'
};
const nebImages = neb => neb?.fit || neb?.tangents ? neb.images ?? 0 : null;
const backdrop = app => app.state.display.viewportBackground === 'dark' ? '#30373a' : '#ffffff';

function canvasBlob(canvas) {
    return new Promise((resolve, reject) => canvas.toBlob(blob => {
        if (blob) resolve(blob);
        else reject(new Error('Could not encode the energy graph as PNG.'));
    }, 'image/png'));
}

export function installTrajectoryTools(App) {
    Object.assign(App.prototype, {
        setupTrajectoryTools() {
            document.getElementById('btn-match-trajectory').onclick = () => this.showTrajectoryMatching();
            this.graphSettings = new GraphSettingsInspector(this);
            if (this.editorRoute === 'rdf' || this.editorRoute === 'trajectory-energy') {
                this.graphSettings.show(this.editorRoute === 'rdf' ? 'rdf' : 'energy');
            }
            for (const [group, fields] of [['style', controlStyleFields], ['neb', controlNebFields]]) {
                for (const [id, key] of Object.entries(fields)) {
                    const control = document.getElementById(id);
                    const event = control.type === 'color' || control.type === 'number' && group === 'style' ? 'input' : 'change';
                    control.addEventListener(event, () => {
                        if (control.type === 'number' && control.value && !control.validity.valid) return;
                        const value = control.type === 'checkbox' ? control.checked
                            : control.type === 'number' ? (Number.isFinite(control.valueAsNumber) ? control.valueAsNumber : null)
                                : control.value;
                        if (group === 'style' && value === null) return;
                        const settings = this.energyOverlaySettings();
                        this.setEnergyOverlay({ ...settings, [group]: { ...settings[group], [key]: value } });
                    });
                }
            }
        },

        energyOverlaySettings() {
            return normalizeEnergyOverlay(this.state.display.energyOverlay, this.personalEnergyBackground);
        },

        setEnergyOverlay(value) {
            this.state.display.energyOverlay = normalizeEnergyOverlay(value, this.personalEnergyBackground);
            this.syncTrajectoryTools();
            this.syncEnergyInspector();
            this.scheduleVisualHistoryCommit('trajectory-energy');
        },

        async seekEnergyFrame(index) {
            await this.stopPlayback();
            if (this.primaryTimelineSource() !== 'loaded') await this.setTimelineSource('loaded');
            this.queueFrameLoad(index, 'loaded');
        },

        energyForStatus(meta) {
            const request = this.trajectoryEnergyRequest;
            if (this.state.displayedTimelineSource === 'relax'
                || !request?.data || request.key !== meta.scientific_content_identity) return meta.energy;
            return request.data.relativeOnly ? null : request.data.values[meta.current_frame || 0];
        },

        syncTrajectoryEnergyStatus() {
            const energy = this.energyForStatus(this.state.atoms?.metadata || {});
            const status = document.getElementById('val-energy');
            const value = Number.isFinite(energy) ? energy.toFixed(4) : '-';
            if (status && status.textContent !== value) status.textContent = value;
        },

        availableTrajectoryOverlays() {
            if (this.loadedFrameCount() < 2) return {};
            const key = this.energySeriesIdentity();
            if (this.trajectoryOverlayRequest?.key !== key) {
                const request = { key };
                this.trajectoryOverlayRequest = request;
                this.api.request('/api/trajectory/overlay-availability/{session_id}').then(data => {
                    if (this.trajectoryOverlayRequest !== request || this.disposed) return;
                    request.data = data;
                    this.renderSceneNavigatorObjects();
                }).catch(error => console.warn('Could not check saved trajectory overlays.', error.message));
            }
            return this.trajectoryOverlayRequest.data || {};
        },

        energySeriesIdentity() {
            const meta = this.state.atoms?.metadata || {};
            return meta.scientific_content_identity || `${this.structureGeneration}:${this.loadedFrameCount()}`;
        },

        energySeriesRequest(images = null, mic = true) {
            const identity = this.energySeriesIdentity();
            const field = images === null ? 'trajectoryEnergyRequest' : 'trajectoryNebRequest';
            const key = images === null ? identity : `${identity}:${images}:${mic}`;
            if (this[field]?.key === key) return this[field];
            const request = { key };
            this[field] = request;
            const path = images === null ? energyPath : `${energyPath}?neb_images=${images}&neb_mic=${mic}`;
            request.promise = this.api.request(path).then(data => {
                request.data = data;
            }).catch(error => {
                request.error = error;
            }).finally(() => {
                if (this[field] === request && !this.disposed) this.syncTrajectoryTools();
            });
            return request;
        },

        async energyDataFor(settings) {
            const images = nebImages(settings.neb);
            const basic = this.energySeriesRequest();
            if (images === null) {
                await basic.promise;
                if (basic.error) throw basic.error;
                return basic.data;
            }
            const fitting = this.energySeriesRequest(images, settings.neb.mic);
            await Promise.all([basic.promise, fitting.promise]);
            if (fitting.data) return fitting.data;
            if (basic.error) throw basic.error;
            return basic.data;
        },

        syncTrajectoryTools() {
            const meta = this.state.atoms?.metadata || {};
            const count = meta.frame_count || 1;
            const match = document.getElementById('btn-match-trajectory');
            match.hidden = count <= 1;
            match.disabled = !meta.config?.trajectory_match_compatible
                || this.state.vizOnly || this.state.isRelaxing || meta.relaxation?.active;
            match.title = this.state.vizOnly ? 'Switch to Edit structure to match atom indices.'
                : !meta.config?.trajectory_match_compatible ? 'All frames must have the same element counts.'
                    : 'Match atom indices to the first frame';

            const settings = this.state.display.energyOverlay;
            this.syncTrajectoryEnergyStatus();
            const inspectorOpen = this.editorRoute === 'trajectory-energy';
            if (count < 2) this.syncEnergyNebStatus(null, count, settings.neb);
            if (count > 1 && (settings?.visible === true || inspectorOpen)) {
                const raw = this.energySeriesRequest();
                const images = nebImages(settings.neb);
                const fitting = images === null ? null : this.energySeriesRequest(images, settings.neb.mic);
                this.syncEnergyNebStatus(fitting, count, settings.neb);
                this.refreshEnergyOverlay(settings, raw, fitting);
            }
            if (count <= 1 || settings?.visible !== true) {
                if (this.trajectoryEnergyOverlay) this.trajectoryEnergyOverlay.root.hidden = true;
            }
        },

        refreshEnergyOverlay(settings, raw, fitting) {
            if (!settings.visible) return;
            if (raw.data && !raw.data.values.some(Number.isFinite) && !fitting?.data?.neb) {
                if (this.trajectoryEnergyOverlay) this.trajectoryEnergyOverlay.root.hidden = true;
                return;
            }
            if (!this.trajectoryEnergyOverlay) {
                this.trajectoryEnergyOverlay = new TrajectoryEnergyOverlay(this.renderer.container, {
                    seek: index => this.seekEnergyFrame(index).catch(error => this.toast(error.message, 'error')),
                    onLayout: layout => this.setEnergyOverlay({ ...this.energyOverlaySettings(), layout }),
                    backdrop: () => backdrop(this),
                });
                const graph = this.trajectoryEnergyOverlay;
                const open = () => this.openEditorRoute('trajectory-energy');
                const settingsButton = document.createElement('button');
                settingsButton.type = 'button';
                settingsButton.id = 'btn-energy-graph-settings';
                settingsButton.title = 'Graph settings';
                settingsButton.setAttribute('aria-label', settingsButton.title);
                settingsButton.innerHTML = editorIcon('properties');
                settingsButton.onpointerdown = event => event.stopPropagation();
                settingsButton.onclick = () => this.openEditorRoute('trajectory-energy', { focus: '#graph-series' });
                graph.header.append(settingsButton);
                graph.header.title = 'Click for graph settings. Drag or use arrow keys to move.';
                installGraphActivation(graph.header, open, true);
                installGraphActivation(graph.canvas, open);
                this.cleanupCallbacks.push(() => this.trajectoryEnergyOverlay.destroy());
            }
            const graph = this.trajectoryEnergyOverlay;
            if (graph.root.hidden || this.appliedGraphSettings !== settings) {
                graph.setSettings(settings);
                this.appliedGraphSettings = settings;
            }
            const data = fitting?.data || raw.data;
            const message = data ? '' : raw.error?.message || 'Reading saved energies…';
            if (graph.data !== data || graph.message !== message) graph.setData(data, message);
            graph.updateFrame(this.timelineFrameIndex('loaded'));
        },

        syncEnergyInspector({ open = false, force = false } = {}) {
            const {style, neb} = this.energyOverlaySettings();
            this.graphSettings?.sync('energy', force);
            for (const [fields, values] of [[controlStyleFields, style], [controlNebFields, neb]]) {
                for (const [id, key] of Object.entries(fields)) {
                    const input = document.getElementById(id);
                    if (!force && document.activeElement === input) continue;
                    if (input.type === 'checkbox') input.checked = values[key];
                    else input.value = values[key] ?? '';
                }
            }
            document.getElementById('energy-tangent-properties').hidden = !neb.tangents;
            document.getElementById('energy-neb-images').max = this.loadedFrameCount();
            if (open) {
                document.getElementById('energy-neb-settings').open = neb.fit || neb.tangents;
                this.syncTrajectoryTools();
            }

        },

        syncEnergyNebStatus(request, count, neb) {
            const status = document.getElementById('energy-neb-status');
            const enabled = neb?.fit || neb?.tangents;
            const error = request?.data?.nebError || request?.error?.message;
            const band = request?.data?.neb;
            const message = count < 2 ? 'Load a trajectory to fit an NEB band.' : error
                || (band ? `ASE fit · frames ${band.start + 1}–${band.start + band.path.length}` : 'Reading and fitting saved forces…');
            status.hidden = !enabled;
            status.dataset.error = String(Boolean(error));
            if (enabled && status.textContent !== message) status.textContent = message;
        },

        async exportEnergyGraph(format) {
            const settings = this.energyOverlaySettings();
            const stem = this.workspaceDocumentTitle().replace(/\.[^.]+$/, '').replace(/[\\/:*?"<>|]/g, '_');
            const mime = format === 'csv' ? 'text/csv' : 'image/png';
            try {
                const saved = await this.saveBlobFromAction(async () => {
                    const data = await this.energyDataFor(settings);
                    if (!energyPlot(data, settings)) throw new Error('No saved trajectory energies to export.');
                    if (format === 'csv') return new Blob([energyCsv(data, settings)], { type: mime });
                    const { clientWidth, clientHeight } = this.renderer.container;
                    const panel = energyPanelRect(settings.layout, clientWidth, clientHeight);
                    const width = Math.max(200, Math.round(panel.width));
                    const height = Math.max(116, Math.round(panel.height));
                    const canvas = document.createElement('canvas');
                    canvas.width = width * 2;
                    canvas.height = height * 2;
                    paintEnergyPanel(canvas.getContext('2d'), {left: 0, top: 0, width: canvas.width, height: canvas.height},
                        data, settings, this.timelineFrameIndex('loaded'), energyPalette(settings.style, this.renderer.container, backdrop(this)), 2);
                    return await canvasBlob(canvas);
                }, `${stem || 'v_ase'}-energy.${format}`, mime, 'Preparing energy graph…');
                if (saved) this.toast(format === 'csv' ? 'Energy data exported.' : 'Energy graph exported.', 'success');
            } catch (error) { this.toast(error.message, 'error'); }
        },

        async captureHtmlEnergyGraph(contract) {
            if (!contract.options.includeGraph || this.loadedFrameCount() < 2) return null;
            const settings = this.energyOverlaySettings();
            const frame = this.timelineFrameIndex('loaded');
            const renderer = this.renderer;
            const { clientWidth: width, clientHeight: height } = renderer.container;
            if (!width || !height) return null;
            const panel = energyPanelRect(settings.layout, width, height);
            const placement = graphCapturePlacement(renderer, contract, panel);
            if (!placement) return null;
            const capture = {
                ...placement,
                palette: energyPalette(settings.style, renderer.container, contract.options.backgroundColor)
            };
            let data;
            try { data = await this.energyDataFor(settings); }
            catch { return null; }
            return energyPlot(data, settings) ? { capture, settings, data, frame } : null;
        },

        async compositeHtmlEnergyGraph(blob, width, height, graph) {
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const context = canvas.getContext('2d');
            const bitmap = await createImageBitmap(blob);
            try { context.drawImage(bitmap, 0, 0, width, height); }
            finally { bitmap.close(); }
            const { capture, settings, data, frame } = graph;
            const rect = energyPanelRect(capture.layout, width, height, true);
            paintEnergyPanel(context, rect, data, settings, frame, capture.palette, energyCaptureScale(capture, width, height));
            return await canvasBlob(canvas);
        },

        showTrajectoryMatching() {
            this.showModal(`<h2>Match atom indices</h2>
                <p class="modal-intro">Use the first source frame as the reference. Each element is matched separately. Coordinates stay in their original positions.</p>
                <fieldset class="open-file-modes">
                    <legend>Matching method</legend>
                    <label class="open-file-mode"><input type="radio" name="trajectory-match" value="mic" checked>
                        <span><strong>Minimum image</strong><small>Match current positions across periodic boundaries.</small></span></label>
                    <label class="open-file-mode"><input type="radio" name="trajectory-match" value="cartesian">
                        <span><strong>Cartesian distance</strong><small>Match the coordinates as stored.</small></span></label>
                    <label class="open-file-mode"><input type="radio" name="trajectory-match" value="soap-translation">
                        <span><strong>SOAP + translation</strong><small>Use local environments to estimate translation, then match with minimum-image distances.</small></span></label>
                </fieldset>`,
            '<button id="modal-close" class="btn">Cancel</button><button id="trajectory-match-apply" class="btn primary">Match indices</button>');
            document.getElementById('trajectory-match-apply').onclick = async () => {
                const mode = document.querySelector('[name="trajectory-match"]:checked').value;
                this.closeModal();
                try {
                    await this.stopPlayback();
                    if (this.primaryTimelineSource() !== 'loaded') await this.setTimelineSource('loaded');
                    await this.settleScientificMutations();
                    const data = await this.withBusy('Matching atom indices…',
                        () => this.api.jsonPost('/api/trajectory/match/{session_id}', { mode }));
                    this.setAtomsData(data, { clearSelection: true });
                    this.toast(`Matched ${data.metadata.frame_count} frames to frame 1.`, 'success');
                } catch (error) { this.toast(error.message, 'error'); }
            };
        },

        async deleteCurrentTrajectoryFrame() {
            if (!this.canEditAtoms() || this.loadedFrameCount() < 2 || this.state.atoms?.metadata?.relaxation?.active) return;
            try {
                await this.stopPlayback();
                await this.frameCommitTask;
                await this.settleScientificMutations();
                const index = this.currentTrajectoryFrame();
                const confirmed = await this.showConfirmModal({
                    title: `Delete frame ${index + 1}?`,
                    intro: 'Undo restores the removed frame and its data.',
                    confirmText: 'Delete frame', cancelText: 'Cancel', danger: true,
                });
                if (!confirmed) return;
                const retainedLabels = this.uniqueAtomLabels();
                const data = await this.withBusy('Deleting frame…', () =>
                    this.api.jsonPost('/api/trajectory/delete-frame/{session_id}', { frame_index: index }));
                this.state.display.retainedLabels = retainedLabels;
                this.clearViewIdentityOverrides();
                this.state.timelineSource = 'loaded';
                this.state.displayedTimelineSource = 'loaded';
                this.setAtomsData(data, { preserveDisplay: false });
                this.toast(`Deleted frame ${index + 1}.`, 'success');
            } catch (error) { this.toast(error.message, 'error'); }
        },

        async duplicateTrajectoryFrame(placement = 'next') {
            if (!this.canEditAtoms() || !this.hasLoadedAtoms()) {
                this.toast('Switch to Edit structure and load or build a structure first.', 'warning');
                return;
            }
            try {
                await this.stopPlayback();
                await this.frameCommitTask;
                await this.settleScientificMutations();
                const displayed = this.rdfFrameContext({ source: this.state.displayedTimelineSource });
                const payload = { placement, frame_index: displayed.backendFrameIndex };
                if (displayed.source === 'relax') payload.positions = displayed.positions;
                const data = await this.withBusy('Duplicating frame…', () =>
                    this.api.jsonPost('/api/trajectory/duplicate/{session_id}', payload));
                this.state.timelineSource = 'loaded';
                this.state.displayedTimelineSource = 'loaded';
                this.setAtomsData(data);
                this.toast(`Created frame ${data.metadata.current_frame + 1} of ${data.metadata.frame_count}.`, 'success');
            } catch (error) { this.toast(error.message, 'error'); }
        }
    });
}
