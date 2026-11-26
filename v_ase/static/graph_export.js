import { energyCaptureScale, floatingPanelRect } from './trajectory_energy.js?v=0.5.1';
import { rdfTraceKey } from './distribution_plot.js?v=0.5.1';

const rdfMetadataKeys = [
    'requested_cutoff', 'cutoff', 'unique_mic_cutoff', 'safe_cutoff', 'pair_mode', 'warnings',
    'periodic_image_extent', 'periodic_image_span', 'normalization',
];

const rdfKinds = {
    'g(r)': ['radial-distribution', 'Radial distribution function'],
    'Neighbors per atom / Å': ['periodic-pair-distribution', 'Periodic pair distribution'],
    'Pair probability / Å⁻¹': ['pair-distribution', 'Pair-distribution function'],
};

export function savedRdfGraph(capture, options) {
    const { data, layout } = capture?.chart || {};
    if (!Array.isArray(data) || !data.length) return null;
    const radius = data[0]?.x;
    if (!Array.isArray(radius) || radius.length < 2 || radius.length > 5000
        || !radius.every((value, index) => Number.isFinite(value) && value > (radius[index - 1] ?? 0))) return null;
    const curves = new Map();
    const legendHidden = new Set();
    for (const trace of data) {
        const key = rdfTraceKey(trace?.uid);
        if (!key || (key !== 'total' && !key.includes('|')) || curves.has(key)
            || !Array.isArray(trace.x) || trace.x.length !== radius.length
            || !trace.x.every((value, index) => value === radius[index])
            || !Array.isArray(trace.y) || trace.y.length !== radius.length || !trace.y.every(Number.isFinite)) return null;
        curves.set(key, trace.y);
        if (trace.visible === 'legendonly') legendHidden.add(trace.uid);
    }
    const total = curves.get('total');
    const yLabel = layout?.yaxis?.title?.text;
    if (!total || !Object.hasOwn(rdfKinds, yLabel)) return null;
    curves.delete('total');
    const [analysisKind, title] = rdfKinds[yLabel];
    const metadata = capture.resultMetadata || {};
    const cutoff = Number.isFinite(metadata.cutoff) ? metadata.cutoff : radius.at(-1) + (radius[1] - radius[0]) / 2;
    const result = {
        schema: 'v_ase.rdf.v1', radius, total, partial: Object.fromEntries(curves),
        bins: radius.length, cutoff, frame_index: capture.frame,
        pair_mode: options.pair_mode,
        requested_cutoff: options.cutoff ?? cutoff,
        analysis_kind: analysisKind, title, y_label: yLabel,
    };
    for (const key of rdfMetadataKeys) {
        const value = metadata[key];
        if (key === 'warnings' ? Array.isArray(value) && value.every(item => typeof item === 'string')
            : key.startsWith('periodic_') ? Array.isArray(value) && value.length === 3 && value.every(Number.isInteger)
            : key === 'normalization' || key === 'pair_mode' ? typeof value === 'string'
            : Number.isFinite(value)) result[key] = value;
    }
    const ranges = {};
    for (const axis of ['x', 'y']) {
        const range = layout?.[`${axis}axis`]?.range;
        if (Array.isArray(range) && range.length === 2 && range.every(Number.isFinite) && range[0] < range[1]) {
            ranges[axis] = [...range];
        }
    }
    return { result, ranges, legendHidden };
}

export function graphCapturePlacement(renderer, contract, panel) {
    const { clientWidth: width, clientHeight: height } = renderer.container;
    if (!width || !height || !panel.width || !panel.height) return null;
    let area = { left: 0, top: 0, width, height };
    if (renderer.exportPreview?.enabled) {
        const view = renderer.exportCameraSetup(contract.width, contract.height, contract.options);
        if (view.camera.quaternion.angleTo(renderer.camera.quaternion) < 1e-5) {
            renderer.camera.updateMatrixWorld(true);
            const crop = renderer.exportPreviewRect(contract.width, contract.height, view);
            if ([crop.left, crop.top, crop.width, crop.height].every(Number.isFinite) && crop.width > 0 && crop.height > 0) {
                area = crop;
            }
        }
    }
    const fit = Math.min(1, area.width / panel.width, area.height / panel.height);
    const graphWidth = panel.width * fit / area.width;
    const graphHeight = panel.height * fit / area.height;
    const position = (value, size) => Math.max(0, Math.min(1 - size, value));
    return {
        layout: {
            x: position((panel.left - area.left) / area.width, graphWidth),
            y: position((panel.top - area.top) / area.height, graphHeight),
            width: graphWidth,
            height: graphHeight,
        },
        referenceWidth: area.width / fit,
        referenceHeight: area.height / fit,
    };
}

export function floatingRdfGraphPresent(app) {
    return app.state.activeAnalysisPlot === 'rdf' && Boolean(app.state.rdfResult)
        && app.state.display.analysisPlots.rdf.placement === 'viewport'
        && !document.getElementById('analysis-floating').hidden;
}

export async function captureFloatingRdf(app, contract) {
    if (!floatingRdfGraphPresent(app)) return null;
    const panel = document.getElementById('analysis-floating');
    const title = document.getElementById('analysis-floating-title');
    const plot = app.analysisPlotElement('rdf');
    if (!plot?._fullLayout || !plot.clientWidth || !plot.clientHeight) return null;
    const placement = graphCapturePlacement(app.renderer, contract, {
        left: panel.offsetLeft, top: panel.offsetTop,
        width: panel.offsetWidth, height: panel.offsetHeight,
    });
    if (!placement) return null;
    const chartLayout = structuredClone(plot.layout);
    for (const axis of ['xaxis', 'yaxis']) {
        chartLayout[axis].range = [...plot._fullLayout[axis].range];
        chartLayout[axis].autorange = false;
    }
    delete chartLayout.width;
    delete chartLayout.height;
    const result = app.state.rdfResult;
    const capture = {
        ...placement,
        title: title.textContent,
        headerHeight: title.parentElement.offsetHeight,
        frame: result.source_frame_index ?? result.frame_index ?? 0,
        source: result.display_source || 'loaded',
        resultMetadata: Object.fromEntries(rdfMetadataKeys.filter(key => result[key] !== undefined)
            .map(key => [key, result[key]])),
        palette: app.distributionPalette(app.state.display.analysisPlots.rdf.style),
        chart: { data: structuredClone(plot.data), layout: chartLayout },
    };
    if (contract.kind === 'html') {
        const { cutoff, use_pbc, active_pairs } = app.rdfOptions({ includePositions: false });
        const { teal, amber, blue } = app.plotTheme();
        capture.analysisOptions = {
            cutoff, use_pbc, active_pairs,
            bins: result.bins, pair_mode: result.pair_mode,
        };
        capture.seriesTheme = { teal, amber, blue };
    }
    const image = new Image();
    image.src = await window.Plotly.toImage(plot, {
        format: 'png', width: plot.clientWidth, height: plot.clientHeight, scale: 2,
    });
    await image.decode();
    return { capture, image };
}

export async function composeFloatingRdf(blob, width, height, { capture, image }) {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    const bitmap = await createImageBitmap(blob);
    try { context.drawImage(bitmap, 0, 0, width, height); }
    finally { bitmap.close(); }
    const panel = floatingPanelRect(capture.layout, width, height, 1, 1);
    const scale = energyCaptureScale(capture, width, height);
    const header = Math.min(panel.height, capture.headerHeight * scale);
    const { left, top } = panel;
    context.beginPath();
    context.roundRect(left, top, panel.width, panel.height, 8 * scale);
    context.clip();
    context.fillStyle = capture.palette.background;
    context.fill();
    context.drawImage(image, left + scale, top + header, Math.max(0, panel.width - 2 * scale),
        Math.max(0, panel.height - header - scale));
    context.strokeStyle = capture.palette.border;
    context.lineWidth = 2 * scale;
    context.stroke();
    context.fillStyle = capture.palette.border;
    context.fillRect(left, top + header - scale, panel.width, scale);
    context.fillStyle = capture.palette.ink;
    context.textBaseline = 'middle';
    context.font = `600 ${12 * scale}px system-ui`;
    context.fillText(capture.title, left + 9 * scale, top + header / 2, Math.max(0, panel.width - 18 * scale));
    return new Promise((resolve, reject) => canvas.toBlob(result => {
        if (result) resolve(result);
        else reject(new Error('Could not composite the distribution graph.'));
    }, 'image/png'));
}
