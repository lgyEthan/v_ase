import { createAxisControls } from './graph_axes_ui.js?v=0.5.1';
import { energySeriesFields, energySeriesStyle } from './trajectory_energy.js?v=0.5.1';

const element = id => document.getElementById(id);
const seriesControls = {
    'graph-series-name': 'name', 'energy-line-color': 'line', 'energy-marker-color': 'marker',
    'energy-line-width': 'stroke', 'energy-line-style': 'lineStyle', 'energy-data-mode': 'dataMode',
    'energy-marker-shape': 'markerShape', 'energy-marker-size': 'markerSize',
};
const graphControls = {
    'energy-background-mode': 'backgroundMode', 'energy-background-color': 'background', 'energy-grid': 'grid',
    'graph-legend': 'legend', 'graph-font-family': 'fontFamily', 'graph-font-size': 'fontSize',
    'graph-x-tick-labels': 'xTickLabels', 'graph-y-tick-labels': 'yTickLabels',
    'graph-tick-format': 'tickFormat', 'graph-tick-precision': 'tickPrecision',
};

export function installGraphActivation(target, open, keyboard = false) {
    // Plotly may capture the pointer on a temporary drag layer. Observe release
    // on the window, preserving seek, pan, zoom and the floating panel handles.
    target.addEventListener('pointerdown', start => {
        if (start.button !== 0 || !start.isPrimary || start.target.closest('button, a, .legend, .modebar')) return;
        const events = new AbortController();
        const options = { capture: true, signal: events.signal };
        let moved = false;
        const track = event => {
            if (event.pointerId === start.pointerId
                && Math.hypot(event.clientX - start.clientX, event.clientY - start.clientY) > 4) moved = true;
        };
        window.addEventListener('pointermove', track, options);
        window.addEventListener('pointerdown', event => {
            if (event.pointerId !== start.pointerId) events.abort();
        }, options);
        window.addEventListener('pointercancel', event => {
            if (event.pointerId === start.pointerId) events.abort();
        }, options);
        window.addEventListener('pointerup', event => {
            if (event.pointerId !== start.pointerId) return;
            track(event);
            events.abort();
            if (!moved) setTimeout(open, 0);
        }, options);
    }, true);
    if (keyboard) target.addEventListener('keydown', event => {
        if (event.target !== target || !['Enter', ' '].includes(event.key)) return;
        event.preventDefault();
        open();
    });
}

function bindFields(controls, change) {
    for (const [id, key] of Object.entries(controls)) {
        const input = element(id);
        const live = input.type === 'number' || input.type === 'color';
        input.addEventListener(live ? 'input' : 'change', () => {
            if (input.type === 'number' && (!input.validity.valid || !Number.isFinite(input.valueAsNumber))) return;
            const value = input.type === 'checkbox' ? input.checked :
                input.type === 'number' ? input.valueAsNumber : input.value;
            change(key, value);
        });
    }
}

function syncFields(controls, values, force) {
    for (const [id, key] of Object.entries(controls)) {
        const input = element(id);
        if (input.type === 'checkbox') input.checked = values[key];
        else if (force || document.activeElement !== input) input.value = values[key];
    }
}

export class GraphSettingsInspector {
    constructor(app) {
        this.app = app;
        this.kind = 'energy';
        this.selection = { energy: 'samples', rdf: 'total' };
        this.presets = { energy: {}, rdf: {} };
        this.presetSelection = { energy: '', rdf: '' };
        this.root = element('graph-settings');
        this.selector = element('graph-series');
        this.axes = createAxisControls(element('energy-graph-axes'), this.settings.axes, (axes, options) => {
            if (this.kind === 'rdf') app.setAnalysisPlotAxes('rdf', axes, options);
            else app.setEnergyOverlay({ ...this.settings, axes });
        });
        this.selector.onchange = () => {
            this.selection[this.kind] = this.selector.value;
            this.sync(this.kind, true);
        };
        bindFields(seriesControls, (key, value) => {
            const selected = this.selection[this.kind];
            const style = this.settings.style;
            if (this.kind === 'energy') {
                this.setStyle({ ...style, [energySeriesFields[selected][key]]: value });
            } else {
                const series = { ...style.series, [selected]: { ...style.series[selected], [key]: value } };
                this.setStyle({ ...style, series });
            }
            if (key === 'name') this.sync(this.kind, true);
        });
        bindFields(graphControls, (key, value) => this.setStyle({ ...this.settings.style, [key]: value }));
        for (const [format, id] of [['png', 'btn-export-energy-image'], ['csv', 'btn-export-energy-csv']]) {
            element(id).onclick = () => {
                if (this.kind === 'energy') return app.exportEnergyGraph(format);
                app.exportRdfGraph(format).catch(error => app.toast(error.message, 'error'));
            };
        }
        element('btn-energy-default-background').onclick = () => this.saveBackground();
        element('energy-presets').onchange = event => {
            const selected = event.target.value;
            this.presetSelection[this.kind] = selected;
            const style = this.presets[this.kind][selected];
            if (style) {
                this.setStyle(style);
                this.sync(this.kind, true);
            }
            element('btn-delete-energy-preset').disabled = !selected;
        };
        element('btn-save-energy-preset').onclick = () => this.savePresetDialog();
        element('btn-delete-energy-preset').onclick = () => {
            const name = this.presetSelection[this.kind];
            if (name) this.updatePreset(this.kind, name, null).catch(error => app.toast(error.message, 'error'));
        };
    }

    get settings() {
        return this.kind === 'rdf' ? this.app.state.display.analysisPlots.rdf : this.app.energyOverlaySettings();
    }

    show(kind) {
        this.kind = kind;
        const host = element(`${kind}-graph-settings-host`);
        if (this.root.parentElement !== host) host.append(this.root);
        this.root.dataset.graph = kind;
        for (const section of this.root.querySelectorAll('[data-energy-only]')) section.hidden = kind !== 'energy';
        this.sync(kind, true);
        this.syncPresets(kind);
        const request = {};
        this.presetRequest = request;
        this.app.api.request(this.presetPath(kind)).then(presets => {
            if (this.presetRequest !== request) return;
            this.presets[kind] = presets;
            this.syncPresets(kind);
        }).catch(error => this.app.toast(error.message, 'error'));
    }

    sync(kind, force = false) {
        if (kind !== this.kind) return;
        const settings = this.settings;
        const { style } = settings;
        const series = kind === 'rdf' ? this.app.rdfSeriesStyles() : [
            'samples', ...(settings.neb.fit ? ['fit'] : []), ...(settings.neb.tangents ? ['tangents'] : []),
        ].map(key => ({ key, ...energySeriesStyle(style, key) }));
        const selected = series.find(s => s.key === this.selection[kind]) || series[0];
        if (selected.key !== this.selection[kind]) force = true;
        this.selection[kind] = selected.key;
        if (series.length !== this.selector.length || series.some(({ key, name }, i) => {
            const option = this.selector.options[i];
            return option.value !== key || option.text !== name;
        })) this.selector.replaceChildren(...series.map(({ key, name }) => new Option(name, key)));
        this.selector.value = selected.key;
        const width = element('energy-line-width');
        const samples = kind === 'energy' && selected.key === 'samples';
        width.min = samples ? '.75' : kind === 'rdf' ? '.25' : '.5';
        width.max = samples ? '5' : '8';
        width.step = 'any';
        syncFields(seriesControls, selected, force);
        syncFields(graphControls, style, force);
        this.axes.sync(settings.axes, force);
        const lines = ['line', 'line-markers'].includes(selected.dataMode);
        const markers = ['markers', 'line-markers'].includes(selected.dataMode);
        for (const id of ['energy-line-style', 'energy-line-color', 'energy-line-width']) element(id).disabled = !lines;
        for (const id of ['energy-marker-shape', 'energy-marker-size']) element(id).disabled = !markers;
        element('energy-marker-color').disabled = !markers && !(samples && style.cursor);
        element('energy-background-color-row').hidden = style.backgroundMode !== 'color';
        element('graph-tick-precision').disabled = style.tickFormat === 'auto';
        for (const id of ['btn-export-energy-image', 'btn-export-energy-csv']) {
            element(id).disabled = kind === 'energy' ? this.app.loadedFrameCount() < 2 : !this.app.state.rdfResult;
        }
    }

    setStyle(style) {
        if (this.kind === 'rdf') this.app.setRdfGraphStyle(style);
        else this.app.setEnergyOverlay({ ...this.settings, style });
    }

    async saveBackground() {
        const kind = this.kind;
        const { backgroundMode, background } = this.settings.style;
        try {
            const stored = await this.app.api.jsonPost(`/api/preferences/${kind}-background/{session_id}`,
                { backgroundMode, background });
            if (kind === 'energy') this.app.personalEnergyBackground = stored;
            else this.app.personalRdfBackground = stored;
            this.app.toast('Graph background saved for new documents.', 'success');
        } catch (error) { this.app.toast(error.message, 'error'); }
    }

    presetPath(kind) {
        return `/api/preferences/${kind}-presets/{session_id}`;
    }

    syncPresets(kind) {
        if (kind !== this.kind) return;
        const control = element('energy-presets');
        const names = Object.keys(this.presets[kind]).sort((a, b) => a.localeCompare(b));
        control.replaceChildren(new Option('Choose preset', ''), ...names.map(name => new Option(name, name)));
        const selected = this.presetSelection[kind];
        control.value = names.includes(selected) ? selected : '';
        element('btn-delete-energy-preset').disabled = !control.value;
    }

    async updatePreset(kind, name, style) {
        this.presetRequest = null;
        this.presets[kind] = await this.app.api.jsonPost(this.presetPath(kind), { name, style });
        this.presetSelection[kind] = style ? name : '';
        this.syncPresets(kind);
    }

    savePresetDialog() {
        const kind = this.kind;
        const style = this.settings.style;
        this.app.showModal(`<h2>Save graph style preset</h2>
            <div class="prop-row"><label for="energy-preset-name">Name</label>
            <input id="energy-preset-name" type="text" maxlength="64" autocomplete="off"></div>`,
        '<button id="modal-close" class="btn">Cancel</button><button id="energy-preset-save" class="btn primary">Save</button>');
        const name = element('energy-preset-name');
        const save = element('energy-preset-save');
        name.focus();
        save.onclick = async () => {
            if (!name.value.trim()) { name.focus(); return; }
            save.disabled = true;
            try {
                await this.updatePreset(kind, name.value.trim(), style);
                this.app.closeModal();
            } catch (error) {
                save.disabled = false;
                this.app.toast(error.message, 'error');
            }
        };
    }
}
