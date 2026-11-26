import { editorIcon } from './editor_interactions.js?v=0.5.1&ui=20261111.1';
import { energyPalette, floatingPanelRect, installFloatingPanelHandle, normalizeGraphAxes, graphTypography,
    lineStyles, markerShapes, seriesModes, seriesName } from './trajectory_energy.js?v=0.5.1';
import { createAxisControls } from './graph_axes_ui.js?v=0.5.1';
import { installGraphActivation } from './graph_settings_ui.js?v=0.5.1';
import { rdfSeriesStyles } from './distribution_plot.js?v=0.5.1';

const ANALYSIS_PANEL_MINIMUM = { width: 272, height: 184 };
const number = (value, fallback, least, most) => Number.isFinite(value)
    ? Math.min(most, Math.max(least, value)) : fallback;
const choice = (value, allowed) => allowed.includes(value) ? value : allowed[0];
const color = (value, fallback) => /^#[\da-f]{6}$/i.test(value || '') ? value : fallback;

function normalizePresentation(value) {
    const layout = value?.layout;
    return {
        placement: value?.placement === 'viewport' ? 'viewport' : 'drawer',
        axes: normalizeGraphAxes(value?.axes),
        layout: {
            x: number(layout?.x, .50, 0, 1), y: number(layout?.y, .24, 0, 1),
            width: number(layout?.width, .44, .1, 1), height: number(layout?.height, .47, .1, 1),
        },
    };
}

function normalizeRdfSeries(value) {
    const series = [];
    for (const [key, raw] of Object.entries(value || {})) {
        if (!/^(total|[^|]+\|[^|]+)$/.test(key) || !raw || typeof raw !== 'object') continue;
        const style = {};
        if (seriesName(raw.name, '')) style.name = seriesName(raw.name, '');
        for (const field of ['line', 'marker']) if (color(raw[field], null)) style[field] = raw[field];
        for (const [field, allowed] of [['dataMode', seriesModes], ['lineStyle', lineStyles], ['markerShape', markerShapes]]) {
            if (allowed.includes(raw[field])) style[field] = raw[field];
        }
        if (Number.isFinite(raw.stroke)) style.stroke = number(raw.stroke, 2, .25, 8);
        if (Number.isFinite(raw.markerSize)) style.markerSize = number(raw.markerSize, 5, 2, 16);
        if (Object.keys(style).length) series.push([key, style]);
    }
    return Object.fromEntries(series);
}

export function normalizeAnalysisPlots(value, backgroundDefault = null) {
    const style = { ...backgroundDefault, ...value?.rdf?.style };
    const rdf = {
        ...normalizePresentation(value?.rdf),
        style: {
            ...graphTypography(style, 11),
            series: normalizeRdfSeries(style.series),
            backgroundMode: choice(style?.backgroundMode, ['theme', 'color', 'transparent']),
            background: color(style?.background, '#ffffff'),
            grid: style?.grid !== false,
            legend: style?.legend !== false,
            lineColor: color(style?.lineColor, null),
            lineWidth: number(style?.lineWidth, 2.4, .5, 8),
            lineStyle: choice(style?.lineStyle, ['solid', 'dash', 'dot', 'dashdot']),
            mode: choice(style?.mode, ['lines', 'lines+markers', 'markers']),
            markerSize: number(style?.markerSize, 5, 2, 16),
        },
    };
    return { rdf, registry: normalizePresentation(value?.registry),
        commensurate: { ...normalizePresentation(value?.commensurate),
            projectionAxes: normalizeGraphAxes(value?.commensurate?.projectionAxes) } };
}

export function installAnalysisPlots(App) {
    Object.assign(App.prototype, {
        setupAnalysisPlots() {
            const panel = document.getElementById('analysis-floating');
            const host = this.renderer.container;
            for (const [id, icon] of [
                ['btn-analysis-float', 'plot-float'], ['btn-analysis-settings', 'properties'],
                ['btn-analysis-dock', 'plot-dock'], ['btn-analysis-appearance', 'properties'],
                ['btn-analysis-floating-export', 'save-data'], ['btn-analysis-floating-close', 'close'],
            ]) document.getElementById(id).innerHTML = editorIcon(icon);
            const move = (type, placement) => {
                if (!type || type !== this.state.activeAnalysisPlot) return;
                const plots = this.state.display.analysisPlots;
                plots[type] = { ...plots[type], placement };
                this.syncDistributionPlotControls();
                this.scheduleVisualHistoryCommit('analysis-plot-placement');
                const title = document.getElementById('analysis-drawer-title').textContent;
                this.showAnalysisDrawer(type, title);
                this.resizeActiveAnalysisPlot();
                const focus = placement === 'viewport' ? 'analysis-floating-title' : 'btn-analysis-float';
                document.getElementById(focus).focus({ preventScroll: true });
            };
            document.getElementById('btn-analysis-float').onclick = () => move(this.state.activeAnalysisPlot, 'viewport');
            document.getElementById('btn-analysis-dock').onclick = () => move(this.state.activeAnalysisPlot, 'drawer');
            document.getElementById('btn-analysis-floating-close').onclick = () => {
                this.closeAnalysisDrawer();
                this.renderer.domElement.focus({ preventScroll: true });
            };
            for (const id of ['btn-analysis-settings', 'btn-analysis-appearance']) {
                document.getElementById(id).onclick = () => this.openAnalysisGraphSettings();
            }
            document.getElementById('btn-analysis-floating-export').onclick = () => {
                this.exportActiveAnalysisData().catch(error => this.toast(`Analysis export failed: ${error.message}`, 'error'));
            };
            const openRdf = () => {
                if (this.state.activeAnalysisPlot === 'rdf') this.openAnalysisGraphSettings(false);
            };
            installGraphActivation(document.getElementById('rdf-plot'), openRdf);
            installGraphActivation(document.getElementById('analysis-floating-title'), openRdf, true);
            for (const [id, resize] of [['analysis-floating-title', false], ['analysis-floating-resize', true]]) {
                installFloatingPanelHandle(document.getElementById(id), host, {
                    panel,
                    resize,
                    minimum: ANALYSIS_PANEL_MINIMUM,
                    current: () => this.layoutAnalysisPlot(),
                    preview: layout => layout && this.layoutAnalysisPlot(layout),
                    commit: layout => {
                        const plots = this.state.display.analysisPlots;
                        const type = this.state.activeAnalysisPlot;
                        plots[type] = { ...plots[type], layout };
                        this.scheduleVisualHistoryCommit('analysis-plot-layout');
                    },
                });
            }
            for (const event of ['pointerdown', 'pointermove', 'pointerup', 'click', 'dblclick', 'contextmenu', 'wheel']) {
                panel.addEventListener(event, e => e.stopPropagation());
            }
            const observer = new ResizeObserver(entries => {
                if (panel.hidden) return;
                if (entries.some(entry => entry.target === host)) this.layoutAnalysisPlot();
                this.resizeActiveAnalysisPlot();
            });
            observer.observe(host);
            observer.observe(panel.querySelector('.analysis-floating-content'));
            this.cleanupCallbacks.push(() => observer.disconnect());
            this.syncDistributionPlotControls();
        },

        syncDistributionPlotControls() {
            this.graphSettings?.sync('rdf');
        },

        setRdfGraphStyle(style) {
            const plots = this.state.display.analysisPlots;
            this.state.display.analysisPlots = normalizeAnalysisPlots({
                ...plots, rdf: { ...plots.rdf, style },
            }, this.personalRdfBackground);
            this.syncDistributionPlotControls();
            this.scheduleVisualHistoryCommit('distribution-appearance');
            if (this.state.activeAnalysisPlot === 'rdf' && this.state.rdfResult) {
                this.plotRdf(this.state.rdfResult).catch(error => this.toast(error.message, 'error'));
            }
        },

        rdfSeriesStyles(result = this.state.rdfResult) {
            return rdfSeriesStyles(result, this.state.display.analysisPlots.rdf.style, this.plotTheme());
        },

        async exportRdfGraph(format) {
            if (!this.state.rdfResult) throw new Error('Calculate the distribution before exporting.');
            const mime = format === 'png' ? 'image/png' : 'text/csv';
            await this.saveBlobFromAction(async () => {
                if (format === 'csv') return this.api.exportRdfCsv(this.rdfOptions());
                if (this.state.activeAnalysisPlot !== 'rdf') await this.plotRdf(this.state.rdfResult);
                const plot = this.analysisPlotElement('rdf');
                const data = await window.Plotly.toImage(plot, { format: 'png', scale: 2,
                    width: plot.clientWidth, height: plot.clientHeight });
                return (await fetch(data)).blob();
            }, `v_ase_rdf.${format}`, mime, 'Preparing distribution graph…');
        },

        analysisPlotAxisKey(type) {
            return type === 'commensurate' && document.getElementById('commensurate-plot-view').value === 'stradi-2d'
                ? 'projectionAxes' : 'axes';
        },

        analysisPlotAxes(type) {
            return this.state.display.analysisPlots[type][this.analysisPlotAxisKey(type)];
        },

        setAnalysisPlotAxes(type, axes, { force = false } = {}) {
            this.state.display.analysisPlots[type][this.analysisPlotAxisKey(type)] = normalizeGraphAxes(axes);
            if (type === 'rdf' && force) this.rdfAxisApplyRevision = (this.rdfAxisApplyRevision || 0) + 1;
            if (this.state.activeAnalysisPlot === type) this.refreshActiveAnalysisTheme();
            this.scheduleVisualHistoryCommit('graph-axis-limits');
        },

        openAnalysisGraphSettings(focus = true) {
            const type = this.state.activeAnalysisPlot;
            if (!type) return;
            if (type === 'rdf') {
                const section = document.getElementById('rdf-graph-appearance');
                section.open = true;
                if (this.openEditorRoute('rdf', { focus: focus ? '#graph-series' : null })) {
                    section.scrollIntoView({ block: 'start' });
                }
                return;
            }
            this.showModal('<h2>Axis limits</h2><div id="analysis-axis-controls"></div>',
                '<button id="modal-close" class="btn">Cancel</button><button id="apply-graph-axes" class="btn primary">Apply</button>');
            const controls = createAxisControls(document.getElementById('analysis-axis-controls'), this.analysisPlotAxes(type));
            document.getElementById('apply-graph-axes').onclick = () => {
                const axes = controls.read();
                if (!axes) return;
                this.setAnalysisPlotAxes(type, axes);
                this.closeModal();
            };
            controls.focus();
        },

        layoutAnalysisPlot(layout = this.state.display.analysisPlots[this.state.activeAnalysisPlot]?.layout) {
            const panel = document.getElementById('analysis-floating');
            const { clientWidth: width, clientHeight: height } = this.renderer.container;
            if (panel.hidden || !layout || !width || !height) return null;
            const rect = floatingPanelRect(layout, width, height, ANALYSIS_PANEL_MINIMUM.width,
                ANALYSIS_PANEL_MINIMUM.height);
            for (const [key, value] of Object.entries(rect)) panel.style[key] = `${value}px`;
            return { x: rect.left / width, y: rect.top / height, width: rect.width / width, height: rect.height / height };
        },

        resizeActiveAnalysisPlot() {
            if (this.analysisPlotResizeRequest) return;
            this.analysisPlotResizeRequest = requestAnimationFrame(() => {
                this.analysisPlotResizeRequest = null;
                const plot = this.analysisPlotElement();
                if (plot?._fullLayout && plot.clientWidth && plot.clientHeight) {
                    window.Plotly?.Plots.resize(plot)?.catch(() => {});
                }
            });
        },

        presentAnalysisPlot(type, title) {
            const panel = document.getElementById('analysis-floating');
            const drawer = document.getElementById('analysis-drawer');
            const plot = this.analysisPlotElement(type);
            const windowSettings = this.state.display.analysisPlots[type];
            const floating = windowSettings?.placement === 'viewport';
            const content = panel.querySelector('.analysis-floating-content');
            if (content.firstElementChild && (!floating || content.firstElementChild !== plot)) {
                drawer.append(content.firstElementChild);
            }
            if (floating && plot.parentElement !== content) content.append(plot);
            const selector = document.getElementById('commensurate-plot-view');
            const floatingSelector = floating && type === 'commensurate';
            const toolbar = document.getElementById('analysis-floating-options');
            const holder = floatingSelector ? toolbar : document.querySelector('.analysis-drawer-actions');
            if (selector.parentElement !== holder) holder.prepend(selector);
            toolbar.hidden = !floatingSelector;
            panel.hidden = !floating;
            document.getElementById('btn-analysis-float').hidden = !type || floating;
            if (!floating) return false;
            const heading = document.getElementById('analysis-floating-title');
            heading.textContent = title;
            heading.title = type === 'rdf' ? 'Click for graph settings. Drag or use arrow keys to move.'
                : 'Drag or use arrow keys to move the graph';
            const style = windowSettings.style || { backgroundMode: 'theme' };
            const palette = this.distributionPalette(style);
            panel.style.setProperty('--analysis-plot-background', palette.background);
            panel.style.setProperty('--analysis-plot-ink', palette.ink);
            panel.style.setProperty('--analysis-plot-border', palette.border);
            panel.dataset.background = style.backgroundMode;
            this.layoutAnalysisPlot();
            return true;
        },

        restoreAnalysisPlot(previousPlots, usePbcChanged) {
            const type = this.state.activeAnalysisPlot;
            if (!type) return;
            const previous = previousPlots[type];
            const current = this.state.display.analysisPlots[type];
            if (current.placement !== previous.placement
                || JSON.stringify(current.layout) !== JSON.stringify(previous.layout)) {
                const title = document.getElementById('analysis-drawer-title').textContent;
                this.showAnalysisDrawer(type, title);
                this.resizeActiveAnalysisPlot();
            }
            const axisKey = this.analysisPlotAxisKey(type);
            const axesChanged = JSON.stringify(current[axisKey]) !== JSON.stringify(previous[axisKey]);
            if (type !== 'rdf' || !this.state.rdfResult) {
                if (axesChanged) this.refreshActiveAnalysisTheme();
            } else if (usePbcChanged) {
                this.calculateRdf({ quiet: true }).catch(error => {
                    this.setRdfStatus('warning', 'Distribution unavailable', error.message);
                    this.toast(error.message, 'error');
                });
            } else if (axesChanged || JSON.stringify(current.style) !== JSON.stringify(previous.style)) {
                this.plotRdf(this.state.rdfResult).catch(error => this.toast(error.message, 'error'));
            }
        },

        distributionPalette(style) {
            const backdrop = this.state.display.viewportBackground === 'dark' ? '#30373a' : '#ffffff';
            return energyPalette(style, this.renderer.container, backdrop);
        },
    });
}
