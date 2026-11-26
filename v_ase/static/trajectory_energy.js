const DEFAULT_STYLE = Object.freeze({
    line: '#3068b3', marker: '#c3472e', stroke: 1.75, reference: 'first',
    dataMode: 'line', lineStyle: 'solid', markerShape: 'circle', markerSize: 5,
    backgroundMode: 'theme', background: '#ffffff', grid: true, cursor: true,
    fitColor: '#7e63c2', fitWidth: 2, fitLineStyle: 'solid',
    tangentColor: '#368375', tangentWidth: 1, tangentScale: 1
});
const DEFAULT_LAYOUT = Object.freeze({ x: .10, y: .05, width: .36, height: .29 });
const ENERGY_PANEL_MINIMUM = { width: 200, height: 116 };
const PANEL_SNAP_DISTANCE = 8;
const PANEL_SNAP_RELEASE_DISTANCE = 14;
const DASH_PATTERNS = { solid: [], dash: [6, 4], dot: [1, 3], 'dash-dot': [7, 3, 1, 3] };
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const finite = (value, fallback) => Number.isFinite(value) ? value : fallback;
const hex = (value, fallback) => /^#[0-9a-f]{6}$/i.test(value || '') ? value : fallback;
const choice = (value, options) => options.includes(value) ? value : options[0];
const numeric = (value, key, low, high) => clamp(finite(value, DEFAULT_STYLE[key]), low, high);
export const graphAxisFields = [['xMin', 'X minimum'], ['xMax', 'X maximum'],
    ['yMin', 'Y minimum'], ['yMax', 'Y maximum']];

export function normalizeGraphAxes(value) {
    const axes = Object.fromEntries(graphAxisFields.map(([key]) => [key, finite(value?.[key], null)]));
    for (const [min, max] of [['xMin', 'xMax'], ['yMin', 'yMax']]) {
        if (axes[min] !== null && axes[max] !== null && axes[min] >= axes[max]) axes[min] = axes[max] = null;
    }
    return axes;
}

export const seriesModes = ['line', 'line-markers', 'markers', 'hidden'];
export const lineStyles = Object.keys(DASH_PATTERNS);
export const markerShapes = ['circle', 'square', 'diamond'];

export function graphTypography(style, defaultSize) {
    return {
        fontFamily: choice(style?.fontFamily, ['system-ui', 'Arial', 'Georgia', 'monospace']),
        fontSize: clamp(Math.round(finite(style?.fontSize, defaultSize)), 8, 24),
        xTickLabels: style?.xTickLabels !== false, yTickLabels: style?.yTickLabels !== false,
        tickFormat: choice(style?.tickFormat, ['auto', 'fixed', 'scientific']),
        tickPrecision: clamp(Math.round(finite(style?.tickPrecision, 2)), 0, 8),
    };
}

export function seriesName(value, fallback) {
    return typeof value === 'string' && value.trim() ? value.trim().slice(0, 64) : fallback;
}

export const energySeriesFields = {
    samples: { name: 'sampleName', line: 'line', marker: 'marker', stroke: 'stroke', dataMode: 'dataMode',
        lineStyle: 'lineStyle', markerShape: 'markerShape', markerSize: 'markerSize' },
    fit: { name: 'fitName', line: 'fitColor', marker: 'fitMarker', stroke: 'fitWidth', dataMode: 'fitMode',
        lineStyle: 'fitLineStyle', markerShape: 'fitMarkerShape', markerSize: 'fitMarkerSize' },
    tangents: { name: 'tangentName', line: 'tangentColor', marker: 'tangentMarker', stroke: 'tangentWidth',
        dataMode: 'tangentMode', lineStyle: 'tangentLineStyle', markerShape: 'tangentMarkerShape', markerSize: 'tangentMarkerSize' },
};

export function energySeriesStyle(style, key) {
    return Object.fromEntries(Object.entries(energySeriesFields[key]).map(([field, stored]) => [field, style[stored]]));
}

export function normalizeEnergyOverlay(value, backgroundDefault = null) {
    const layout = value?.layout;
    const style = { ...backgroundDefault, ...value?.style };
    const neb = value?.neb;
    return {
        visible: value?.visible === true,
        axes: normalizeGraphAxes(value?.axes),
        layout: {
            x: clamp(finite(layout?.x, DEFAULT_LAYOUT.x), 0, 1),
            y: clamp(finite(layout?.y, DEFAULT_LAYOUT.y), 0, 1),
            width: clamp(finite(layout?.width, DEFAULT_LAYOUT.width), .05, 1),
            height: clamp(finite(layout?.height, DEFAULT_LAYOUT.height), .05, 1),
        },
        style: {
            ...graphTypography(style, 10),
            legend: style.legend !== false,
            sampleName: seriesName(style.sampleName, 'Samples'),
            fitName: seriesName(style.fitName, 'ASE fit'),
            tangentName: seriesName(style.tangentName, 'Tangents'),
            fitMode: choice(style.fitMode, seriesModes),
            tangentMode: choice(style.tangentMode, seriesModes),
            fitMarker: hex(style.fitMarker, hex(style.fitColor, DEFAULT_STYLE.fitColor)),
            tangentMarker: hex(style.tangentMarker, hex(style.tangentColor, DEFAULT_STYLE.tangentColor)),
            fitMarkerSize: clamp(finite(style.fitMarkerSize, 5), 2, 16),
            tangentMarkerSize: clamp(finite(style.tangentMarkerSize, 5), 2, 16),
            fitMarkerShape: choice(style.fitMarkerShape, markerShapes),
            tangentMarkerShape: choice(style.tangentMarkerShape, markerShapes),
            tangentLineStyle: choice(style.tangentLineStyle, lineStyles),
            line: hex(style.line, DEFAULT_STYLE.line),
            marker: hex(style.marker, DEFAULT_STYLE.marker),
            stroke: numeric(style.stroke, 'stroke', .75, 5),
            reference: choice(style.reference, ['first', 'absolute']),
            dataMode: choice(style.dataMode, seriesModes),
            lineStyle: choice(style.lineStyle, Object.keys(DASH_PATTERNS)),
            markerShape: choice(style.markerShape, markerShapes),
            markerSize: numeric(style.markerSize, 'markerSize', 2, 16),
            backgroundMode: choice(style.backgroundMode, ['theme', 'color', 'transparent']),
            background: hex(style.background, DEFAULT_STYLE.background),
            grid: style.grid !== false, cursor: style.cursor !== false,
            fitColor: hex(style.fitColor, DEFAULT_STYLE.fitColor),
            fitWidth: numeric(style.fitWidth, 'fitWidth', .5, 8),
            fitLineStyle: choice(style.fitLineStyle, Object.keys(DASH_PATTERNS)),
            tangentColor: hex(style.tangentColor, DEFAULT_STYLE.tangentColor),
            tangentWidth: numeric(style.tangentWidth, 'tangentWidth', .5, 8),
            tangentScale: numeric(style.tangentScale, 'tangentScale', .1, 4),
        },
        neb: {
            fit: neb?.fit === true,
            tangents: neb?.tangents === true,
            images: Number.isInteger(neb?.images) && neb.images >= 2 ? neb.images : null,
            mic: neb?.mic !== false,
        }
    };
}

export function energyPanelRect(layout, width, height, exact = false) {
    return floatingPanelRect(layout, width, height, exact ? 1 : ENERGY_PANEL_MINIMUM.width,
        exact ? 1 : ENERGY_PANEL_MINIMUM.height);
}

export function floatingPanelRect(layout, width, height, minWidth, minHeight) {
    const w = clamp(layout.width * width, Math.min(minWidth, width), width);
    const h = clamp(layout.height * height, Math.min(minHeight, height), height);
    return { left: clamp(layout.x * width, 0, width - w), top: clamp(layout.y * height, 0, height - h),
        width: w, height: h };
}

function otherFloatingPanels(panel, host) {
    return [...host.querySelectorAll('.trajectory-energy-overlay:not([hidden]), .analysis-floating:not([hidden])')]
        .filter(other => other !== panel);
}

function closestSnap(position, edges, previous) {
    if (previous != null && edges.includes(previous)
        && Math.abs(position - previous) <= PANEL_SNAP_RELEASE_DISTANCE) return previous;
    return edges.reduce((best, edge) => {
        const distance = Math.abs(edge - position);
        return distance <= PANEL_SNAP_DISTANCE
            && (best === null || distance < Math.abs(best - position)) ? edge : best;
    }, null);
}

function snapFloatingPanel(panel, host, candidate, previous) {
    const nearby = otherFloatingPanels(panel, host);
    const nearest = (position, size, crossPosition, crossSize, origin, extent, old) => {
        const neighbors = nearby.flatMap(other => {
            const start = other[origin], end = start + other[extent];
            const crossOrigin = origin === 'offsetLeft' ? 'offsetTop' : 'offsetLeft';
            const crossExtent = extent === 'offsetWidth' ? 'offsetHeight' : 'offsetWidth';
            const gap = Math.max(other[crossOrigin] - crossPosition - crossSize,
                crossPosition - other[crossOrigin] - other[crossExtent]);
            return gap > PANEL_SNAP_RELEASE_DISTANCE ? [] : [start, end, start - size, end - size];
        });
        return closestSnap(position, neighbors, old);
    };
    const { clientWidth: width, clientHeight: height } = host;
    const { x, y, width: w, height: h } = candidate;
    const left = x * width, top = y * height;
    return {
        x: nearest(left, w * width, top, h * height, 'offsetLeft', 'offsetWidth', previous.x),
        y: nearest(top, h * height, left, w * width, 'offsetTop', 'offsetHeight', previous.y),
    };
}

function snapFloatingPanelSize(panel, host, candidate, minimum, previous, dx, dy) {
    const { clientWidth: width, clientHeight: height } = host;
    const hostRect = host.getBoundingClientRect();
    const neighbors = otherFloatingPanels(panel, host).map(other => other.getBoundingClientRect());
    const left = candidate.x * width, top = candidate.y * height;
    const axis = (position, origin, min, max, start, end, old) => {
        // Match parallel edges across a gap, such as one graph above another.
        const edges = neighbors.flatMap(other => [other[start] - origin, other[end] - origin])
            .filter(edge => edge >= min && edge <= max);
        return closestSnap(position, edges, old);
    };
    return {
        x: dx ? axis(left + candidate.width * width, hostRect.left + host.clientLeft,
            Math.min(left + minimum.width, width), width, 'left', 'right', previous.x) : null,
        y: dy ? axis(top + candidate.height * height, hostRect.top + host.clientTop,
            Math.min(top + minimum.height, height), height, 'top', 'bottom', previous.y) : null,
    };
}

export function installFloatingPanelHandle(element, host, { panel, resize, minimum, current, preview, commit }) {
    let drag = null;
    const adjust = (start, dx, dy) => {
        const x = dx / host.clientWidth, y = dy / host.clientHeight;
        if (resize) {
            const candidate = { ...start, width: Math.min(1 - start.x, start.width + x),
                height: Math.min(1 - start.y, start.height + y) };
            if (panel && drag) {
                drag.snap = snapFloatingPanelSize(panel, host, candidate, minimum, drag.snap, dx, dy);
                if (drag.snap.x !== null) candidate.width = drag.snap.x / host.clientWidth - start.x;
                if (drag.snap.y !== null) candidate.height = drag.snap.y / host.clientHeight - start.y;
            }
            return preview(candidate);
        }
        const candidate = { ...start, x: start.x + x, y: start.y + y };
        if (panel && drag) {
            drag.snap = snapFloatingPanel(panel, host, candidate, drag.snap);
            if (drag.snap.x !== null) candidate.x = drag.snap.x / host.clientWidth;
            if (drag.snap.y !== null) candidate.y = drag.snap.y / host.clientHeight;
        }
        return preview(candidate);
    };
    element.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        const start = current();
        if (!start) return;
        drag = { id: event.pointerId, x: event.clientX, y: event.clientY, start, next: start, snap: {} };
        element.setPointerCapture(event.pointerId);
    });
    element.addEventListener('pointermove', event => {
        if (drag?.id !== event.pointerId) return;
        drag.next = adjust(drag.start, event.clientX - drag.x, event.clientY - drag.y);
    });
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
        element.addEventListener(type, event => {
            if (drag?.id !== event.pointerId) return;
            const completed = event.type === 'pointerup';
            const next = completed ? drag.next : drag.start;
            drag = null;
            preview(next);
            if (completed && next) commit(next);
        });
    }
    element.addEventListener('keydown', event => {
        const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
        if (!delta) return;
        const start = current();
        if (!start) return;
        event.preventDefault();
        event.stopPropagation();
        const step = event.shiftKey ? 20 : 4;
        const next = adjust(start, step * delta[0], step * delta[1]);
        if (next) commit(next);
    });
}

export function energyCaptureScale(capture, width, height) {
    return capture ? Math.min(width / capture.referenceWidth, height / capture.referenceHeight) : 1;
}

export function energyPalette(style, host, backdrop = '#ffffff') {
    if (style.backgroundMode === 'theme') {
        const css = host.ownerDocument.defaultView.getComputedStyle(host);
        const token = (name, fallback) => hex(css.getPropertyValue(name).trim(), fallback);
        return { background: token('--ui-surface', '#f7f8fa'), ink: token('--ui-ink', '#242a31'),
            secondary: token('--ui-secondary', '#535863'), border: token('--ui-border', '#cad0d8'),
            grid: token('--ui-line', '#cbd1d9') };
    }
    const background = style.backgroundMode === 'color' ? style.background : 'transparent';
    const reference = hex(background, hex(backdrop, '#ffffff'));
    const channels = [1, 3, 5].map(offset => parseInt(reference.slice(offset, offset + 2), 16));
    const light = .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2] > 140;
    return light
        ? { background, ink: '#20242b', secondary: '#46505d', border: '#8b94a1', grid: '#a9b0ba' }
        : { background, ink: '#f2f4f7', secondary: '#d0d7e0', border: '#748093', grid: '#667185' };
}

export function energyPlot(data, settings) {
    const { style, neb: layers } = settings;
    const neb = layers.fit || layers.tangents ? data?.neb : null;
    const values = neb?.values || data?.values || [];
    const first = values.find(Number.isFinite);
    if (values.length < 2 || first === undefined) return null;
    const relativeOnly = neb?.relativeOnly ?? data.relativeOnly;
    const relative = relativeOnly || style.reference === 'first';
    const offset = style.reference === 'first' ? first : 0;
    const path = neb?.path || data.path;
    const start = neb?.start || 0;
    const xAt = index => path ? path[index] : index + start + 1;
    const sampleY = value => value - offset;
    const fit = layers.fit && neb ? neb.fitPath.map((x, i) => [x, neb.fitEnergies[i] + (first - offset)]) : [];
    const tangents = layers.tangents && neb ? neb.tangents.map(({ halfWidth, slope }, index) => {
        const half = halfWidth * style.tangentScale;
        const x = xAt(index), y = sampleY(values[index]);
        return { frame: index + start, slope, points: [[x - half, y - half * slope], [x + half, y + half * slope]] };
    }) : [];
    let xmin = xAt(0), xmax = xAt(values.length - 1);
    let low = Infinity, high = -Infinity;
    const include = value => { low = Math.min(low, value); high = Math.max(high, value); };
    for (const value of values) if (Number.isFinite(value)) include(sampleY(value));
    for (const [, y] of fit) include(y);
    for (const {points} of tangents) for (const [x, y] of points) {
        xmin = Math.min(xmin, x);
        xmax = Math.max(xmax, x);
        include(y);
    }
    const padding = high === low ? Math.max(.01, Math.abs(low) * .005) : (high - low) * .08;
    const { xMin, xMax, yMin, yMax } = normalizeGraphAxes(settings.axes);
    const range = (min, max, autoMin, autoMax) => {
        const span = autoMax > autoMin ? autoMax - autoMin : 1;
        const lower = min ?? (max !== null && max <= autoMin ? max - span : autoMin);
        const upper = max ?? (lower >= autoMax ? lower + span : autoMax);
        return [lower, upper];
    };
    [xmin, xmax] = range(xMin, xMax, xmin, xmax);
    [low, high] = range(yMin, yMax, low - padding, high + padding);
    return { values, start, path, xAt, relative, relativeOnly, offset, first, fit, tangents,
        count: data.values.length, xmin, xmax, low, high, customX: xMin !== null || xMax !== null,
        customRange: [xMin, xMax, yMin, yMax].some(bound => bound !== null) };
}

function paintLine(context, points, geometry, color, width, pattern = 'solid') {
    context.strokeStyle = color;
    context.lineWidth = width;
    context.lineJoin = 'round';
    context.lineCap = 'round';
    context.setLineDash(DASH_PATTERNS[pattern].map(value => value * Math.max(.75, width / 1.75)));
    context.beginPath();
    let previous = false;
    for (const [x, y] of points) {
        if (!Number.isFinite(y)) { previous = false; continue; }
        const method = previous ? 'lineTo' : 'moveTo';
        context[method](geometry.toX(x), geometry.toY(y));
        previous = true;
    }
    context.stroke();
    context.setLineDash([]);
}

function paintMarker(context, x, y, radius, shape = 'circle') {
    context.beginPath();
    if (shape === 'square') {
        context.rect(x - radius, y - radius, radius * 2, radius * 2);
    } else if (shape === 'diamond') {
        context.moveTo(x, y - radius);
        context.lineTo(x + radius, y);
        context.lineTo(x, y + radius);
        context.lineTo(x - radius, y);
        context.closePath();
    } else {
        context.arc(x, y, radius, 0, Math.PI * 2);
    }
    context.fill();
}

function axisTicks(value, span, style) {
    if (style.tickFormat === 'fixed') return value.toFixed(style.tickPrecision);
    if (style.tickFormat === 'scientific') return value.toExponential(style.tickPrecision);
    const decimals = clamp(1 - Math.floor(Math.log10(span)), 0, 8);
    return value !== 0 && (Math.abs(value) >= 1e8 || Math.abs(value) < 1e-7)
        ? value.toExponential(1) : value.toFixed(decimals);
}

function drawSeries(context, series, segments, geometry) {
    if (series.dataMode === 'hidden') return;
    if (series.dataMode !== 'markers') {
        for (const points of segments) paintLine(context, points, geometry, series.line, series.stroke, series.lineStyle);
    }
    if (series.dataMode !== 'line') {
        context.fillStyle = series.marker;
        for (const points of segments) for (const [x, y] of points) {
            if (Number.isFinite(y)) paintMarker(context, geometry.toX(x), geometry.toY(y), series.markerSize / 2, series.markerShape);
        }
    }
}

function drawLegend(context, visible, width, size, palette) {
    const scale = { toX: x => x, toY: y => y };
    context.textAlign = 'left';
    context.textBaseline = 'middle';
    let x = 8;
    const y = size / 2 + 5;
    for (const [index, { style }] of visible.entries()) {
        const end = x + (width - 4 - x) / (visible.length - index);
        if (style.dataMode !== 'markers') paintLine(context, [[x, y], [x + 12, y]], scale, style.line, style.stroke, style.lineStyle);
        if (style.dataMode !== 'line') {
            context.fillStyle = style.marker;
            paintMarker(context, x + 6, y, Math.min(style.markerSize / 2, size / 2), style.markerShape);
        }
        context.fillStyle = palette.secondary;
        const labelWidth = Math.max(1, end - x - 24);
        let label = style.name;
        while (label.length > 1 && context.measureText(label).width > labelWidth) label = label.slice(0, -2) + '…';
        context.fillText(label, x + 16, y, labelWidth);
        x += context.measureText(label).width + 24;
    }
}

function paintPlot(context, plot, style, palette, width, height) {
    if (!plot || width < 80 || height < 50) return null;
    const data = plot.values.map((value, i) => [plot.xAt(i), Number.isFinite(value) ? value - plot.offset : null]);
    const visible = [
        { style: energySeriesStyle(style, 'samples'), segments: [data] },
        { style: energySeriesStyle(style, 'fit'), segments: plot.fit.length ? [plot.fit] : [] },
        { style: energySeriesStyle(style, 'tangents'), segments: plot.tangents.map(tangent => tangent.points) },
    ].filter(series => series.segments.length && series.style.dataMode !== 'hidden');
    const size = style.fontSize;
    context.font = `${size}px ${style.fontFamily}`;
    const left = style.yTickLabels ? Math.min(7.2 * size, width * .35) : size + 10;
    const right = width - Math.min(width * .12, Math.max(12, size * 1.4));
    const legend = style.legend && visible.length > 0 && height > size * 4.8;
    const top = legend ? size * 1.8 + 8 : size / 2 + 6;
    const bottom = Math.max(top + 8, height - size * (style.xTickLabels ? 2.5 : 1.25) - 7);
    const toX = value => left + (right - left) * (value - plot.xmin) / (plot.xmax - plot.xmin);
    const toY = value => bottom - (bottom - top) * (value - plot.low) / (plot.high - plot.low);
    const geometry = { left, right, top, bottom, toX, toY };
    if (legend) drawLegend(context, visible, width, size, palette);
    context.fillStyle = palette.secondary;
    context.strokeStyle = palette.grid;
    context.lineWidth = 1;
    context.textAlign = 'right';
    context.textBaseline = 'middle';
    const yTicks = clamp(Math.floor((bottom - top) / (size * 1.4)), 1, 3);
    for (let tick = 0; tick <= yTicks; tick++) {
        const value = plot.low + (plot.high - plot.low) * tick / yTicks;
        const y = toY(value);
        if (style.grid) {
            context.beginPath();
            context.moveTo(left, y);
            context.lineTo(right, y);
            context.stroke();
        }
        if (style.yTickLabels) context.fillText(axisTicks(value, plot.high - plot.low, style), left - 5, y, Math.max(1, left - size - 7));
    }
    context.strokeStyle = palette.border;
    context.beginPath();
    context.moveTo(left, top);
    context.lineTo(left, bottom);
    context.lineTo(right, bottom);
    context.stroke();
    context.textAlign = 'center';
    const ticks = Math.min(4, plot.values.length - 1, Math.max(1, Math.floor((right - left) / (size * 4))));
    for (let tick = 0; style.xTickLabels && tick <= ticks; tick++) {
        const frame = Math.round((plot.values.length - 1) * tick / ticks);
        const useRange = plot.path || plot.customX;
        const value = useRange ? plot.xmin + (plot.xmax - plot.xmin) * tick / ticks : plot.xAt(frame);
        const tickLabel = useRange || style.tickFormat !== 'auto' ? axisTicks(value, plot.xmax - plot.xmin, style) : String(value);
        const maxWidth = (right - left) / ticks - 3;
        const halfWidth = Math.min(maxWidth, context.measureText(tickLabel).width) / 2;
        const x = clamp(toX(value), halfWidth + 2, width - halfWidth - 2);
        context.fillText(tickLabel, x, bottom + size * .7 + 3, maxWidth);
    }
    context.fillText(plot.path ? 'NEB path (Å)' : 'Frame', (left + right) / 2, height - size / 2 - 2);
    if (height >= 86) {
        context.save();
        context.translate(size / 2 + 4, (top + bottom) / 2);
        context.rotate(-Math.PI / 2);
        context.fillText(plot.relative ? 'ΔE (eV)' : 'Energy (eV)', 0, 0, bottom - top);
        context.restore();
    }
    context.save();
    context.beginPath();
    const pad = plot.customRange ? 0 : 8;
    context.rect(left - pad, top - pad, right - left + 2 * pad, bottom - top + 2 * pad);
    context.clip();
    for (const series of visible) drawSeries(context, series.style, series.segments, geometry);
    context.restore();
    return geometry;
}

function energyFrameText(plot, frame) {
    if (!plot) return '';
    if (frame < plot.start || frame >= plot.start + plot.values.length) return `Frame ${frame + 1} · outside NEB band`;
    const value = plot.values[frame - plot.start];
    const number = Number.isFinite(value)
        ? `${plot.relative ? 'ΔE ' : ''}${(value - plot.offset).toFixed(4)} eV` : 'No energy';
    return `${number} · ${frame + 1}/${plot.count}`;
}

export function paintEnergyPanel(context, rect, data, settings, frame, palette, scale = 1) {
    const plot = energyPlot(data, settings);
    if (!plot) return;
    const width = rect.width / scale, height = rect.height / scale;
    context.save();
    context.translate(rect.left, rect.top);
    context.scale(scale, scale);
    context.beginPath();
    context.roundRect(.5, .5, width - 1, height - 1, 8);
    if (palette.background !== 'transparent') {
        context.fillStyle = palette.background;
        context.fill();
    }
    context.strokeStyle = palette.border;
    context.lineWidth = 1;
    context.stroke();
    context.textAlign = 'left';
    context.textBaseline = 'middle';
    context.font = '600 12px system-ui';
    context.fillStyle = palette.ink;
    context.fillText('Energy', 9, 13, width * .25);
    context.font = '11px system-ui';
    context.fillStyle = palette.secondary;
    context.textAlign = 'right';
    context.fillText(energyFrameText(plot, frame), width - 9, 13, width * .7);
    context.strokeStyle = palette.grid;
    context.beginPath();
    context.moveTo(0, 26);
    context.lineTo(width, 26);
    context.stroke();
    context.translate(0, 26);
    const geometry = paintPlot(context, plot, settings.style, palette, width, height - 26);
    const index = frame - plot.start;
    const position = plot.xAt(index);
    if (geometry && settings.style.cursor && index >= 0 && index < plot.values.length
        && position >= plot.xmin && position <= plot.xmax) {
        const x = geometry.toX(position);
        context.globalAlpha = .48;
        context.strokeStyle = palette.secondary;
        context.beginPath();
        context.moveTo(x, geometry.top);
        context.lineTo(x, geometry.bottom);
        context.stroke();
        context.globalAlpha = 1;
        const value = plot.values[index] - plot.offset;
        if (Number.isFinite(plot.values[index]) && value >= plot.low && value <= plot.high) {
            context.fillStyle = settings.style.marker;
            paintMarker(context, x, geometry.toY(value), 4);
            context.strokeStyle = palette.background === 'transparent' ? palette.ink : palette.background;
            context.stroke();
        }
    }
    context.restore();
}

export function energyCsv(data, settings) {
    const plot = energyPlot(data, settings);
    if (!plot) return null;
    const lines = ['series,frame,path_A,energy_eV,delta_energy_eV,slope_eV_per_A'];
    const row = (series, frame, x, value, slope = '') => {
        const available = Number.isFinite(value);
        const absolute = available && !plot.relativeOnly ? value : '';
        const relative = available ? value - plot.first : '';
        lines.push([series, frame, plot.path ? x : '', absolute, relative, slope].join(','));
    };
    plot.values.forEach((value, index) => row('sample', index + plot.start + 1, plot.xAt(index), value));
    plot.fit.forEach(([x, y]) => row('ase_fit', '', x, y + plot.offset));
    for (const {frame, slope, points} of plot.tangents) {
        for (const [x, y] of points) row('force_tangent', frame + 1, x, y + plot.offset, slope);
    }
    return lines.join('\r\n') + '\r\n';
}

export class TrajectoryEnergyOverlay {
    constructor(host, { seek, onLayout, capture, backdrop } = {}) {
        this.host = host;
        this.seek = seek;
        this.onLayout = onLayout;
        this.capture = capture;
        this.backdrop = backdrop;
        this.settings = normalizeEnergyOverlay(null);
        this.data = null;
        this.frame = 0;
        this.root = host.ownerDocument.createElement('section');
        this.root.className = 'trajectory-energy-overlay';
        this.root.hidden = true;
        this.root.setAttribute('aria-label', 'Trajectory energy');
        this.root.innerHTML = `
            <div class="energy-overlay-header">
                <span>Energy</span><output></output>
            </div>
            <div class="energy-chart">
                <canvas role="slider" tabindex="0" aria-label="Energy graph frame"></canvas>
                <span class="energy-chart-guide" hidden></span>
                <span class="energy-chart-marker" hidden></span>
                <span class="energy-chart-empty" role="status" hidden></span>
            </div>`;
        host.append(this.root);
        this.header = this.root.querySelector('.energy-overlay-header');
        this.subtitle = this.root.querySelector('output');
        this.canvas = this.root.querySelector('canvas');
        this.guide = this.root.querySelector('.energy-chart-guide');
        this.marker = this.root.querySelector('.energy-chart-marker');
        this.empty = this.root.querySelector('.energy-chart-empty');
        if (onLayout) {
            const grip = host.ownerDocument.createElement('button');
            grip.className = 'energy-overlay-resize';
            grip.type = 'button';
            grip.title = 'Resize energy graph';
            grip.setAttribute('aria-label', grip.title);
            this.root.append(grip);
            this.header.tabIndex = 0;
            this.header.title = 'Drag to move the energy graph';
            this.root.classList.add('is-editable');
            this.installLayoutHandle(this.header, false);
            this.installLayoutHandle(grip, true);
        }
        this.installSeek();
        for (const type of ['pointerdown', 'pointermove', 'pointerup', 'click', 'dblclick', 'wheel']) {
            this.root.addEventListener(type, event => event.stopPropagation());
        }
        this.observer = new ResizeObserver(() => this.layout(this.settings.layout));
        this.observer.observe(host);
    }

    destroy() {
        this.observer.disconnect();
        this.root.remove();
    }

    setSettings(value) {
        this.settings = normalizeEnergyOverlay(value);
        this.plot = energyPlot(this.data, this.settings);
        this.root.hidden = !this.settings.visible;
        if (!this.root.hidden) this.layout(this.settings.layout);
    }

    setData(data, message = '') {
        this.data = data;
        this.message = message;
        this.plot = energyPlot(data, this.settings);
        if (!this.root.hidden) this.draw();
    }

    layout(layout) {
        if (this.root.hidden || !this.host.clientWidth || !this.host.clientHeight) return;
        const w = this.host.clientWidth;
        const h = this.host.clientHeight;
        const { left, top, width, height } = energyPanelRect(this.capture?.layout || layout, w, h, Boolean(this.capture));
        this.scale = energyCaptureScale(this.capture, w, h);
        this.root.style.setProperty('--energy-scale', String(this.scale));
        Object.assign(this.root.style, {
            left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px`
        });
        this.draw();
        return { x: left / w, y: top / h, width: width / w, height: height / h };
    }

    installLayoutHandle(element, resize) {
        installFloatingPanelHandle(element, this.host, {
            panel: this.root,
            resize,
            minimum: ENERGY_PANEL_MINIMUM,
            current: () => this.layout(this.settings.layout),
            preview: layout => layout && this.layout(layout),
            commit: layout => {
                this.settings.layout = layout;
                this.onLayout(layout);
            },
        });
    }

    installSeek() {
        let pointer = null;
        const seek = event => {
            if (!this.geometry || !this.plot) return;
            const { left, right } = this.geometry;
            const { path, values, start, xmin, xmax } = this.plot;
            const x = (event.clientX - this.canvas.getBoundingClientRect().left) / this.scale;
            const ratio = clamp((x - left) / (right - left), 0, 1);
            const position = xmin + ratio * (xmax - xmin);
            let index = clamp(Math.round(position - start - 1), 0, values.length - 1);
            if (path) {
                let lo = 0, hi = path.length - 1;
                while (lo < hi) {
                    const middle = Math.floor((lo + hi) / 2);
                    if (path[middle] < position) lo = middle + 1;
                    else hi = middle;
                }
                index = lo > 0 && position - path[lo - 1] < path[lo] - position ? lo - 1 : lo;
            }
            this.seek?.(index + start);
        };
        this.canvas.addEventListener('pointerdown', event => {
            if (event.button !== 0 || !this.geometry) return;
            pointer = event.pointerId;
            this.canvas.setPointerCapture(pointer);
            seek(event);
        });
        this.canvas.addEventListener('pointermove', event => {
            if (event.pointerId === pointer) seek(event);
        });
        this.canvas.addEventListener('lostpointercapture', () => { pointer = null; });
        this.canvas.addEventListener('keydown', event => {
            if (!this.geometry || !this.plot) return;
            const first = this.plot.start;
            const last = first + this.plot.values.length - 1;
            const index = { ArrowLeft: this.frame - 1, ArrowRight: this.frame + 1,
                ArrowDown: this.frame - 1, ArrowUp: this.frame + 1, Home: 0, End: this.plot.count - 1 }[event.key];
            if (index === undefined) return;
            event.preventDefault();
            event.stopPropagation();
            this.seek?.(event.key === 'Home' || event.key === 'End' ? index : clamp(index, first, last));
        });
    }

    draw() {
        if (this.root.hidden) return;
        const style = this.settings.style;
        const palette = this.capture?.palette || energyPalette(style, this.root, this.backdrop?.());
        this.root.dataset.background = style.backgroundMode;
        for (const [key, color] of Object.entries(palette)) this.root.style.setProperty(`--energy-${key}`, color);
        const { clientWidth: width, clientHeight: height } = this.canvas;
        if (!width || !height) return;
        const scale = this.scale || 1;
        const dpr = Math.min(2, this.host.ownerDocument.defaultView.devicePixelRatio || 1);
        this.canvas.width = Math.round(width * dpr);
        this.canvas.height = Math.round(height * dpr);
        const context = this.canvas.getContext('2d');
        context.scale(dpr * scale, dpr * scale);
        this.geometry = paintPlot(context, this.plot, style, palette, width / scale, height / scale);
        this.empty.hidden = Boolean(this.plot);
        this.empty.textContent = this.message || 'No saved trajectory energy';
        this.canvas.tabIndex = this.geometry ? 0 : -1;
        this.updateFrame(this.frame);
    }

    updateFrame(index) {
        this.frame = index;
        this.root.dataset.frame = String(index);
        if (!this.geometry || !this.plot) {
            this.guide.hidden = this.marker.hidden = true;
            this.subtitle.textContent = '';
            return;
        }
        const { toX, toY, top, bottom } = this.geometry;
        const { start, values, xAt, offset, xmin, xmax, low, high } = this.plot;
        const local = index - start;
        this.subtitle.textContent = energyFrameText(this.plot, index);
        this.canvas.setAttribute('aria-valuemin', String(start + 1));
        this.canvas.setAttribute('aria-valuemax', String(start + values.length));
        this.canvas.setAttribute('aria-valuenow', String(clamp(index + 1, start + 1, start + values.length)));
        this.canvas.setAttribute('aria-valuetext', this.subtitle.textContent);
        const xValue = xAt(local);
        const yValue = values[local] - offset;
        this.guide.hidden = !this.settings.style.cursor || local < 0 || local >= values.length || xValue < xmin || xValue > xmax;
        this.marker.hidden = this.guide.hidden || !Number.isFinite(values[local]) || yValue < low || yValue > high;
        if (this.guide.hidden) return;
        const x = toX(xValue) * this.scale;
        Object.assign(this.guide.style, { left: `${x}px`, top: `${top * this.scale}px`, height: `${(bottom - top) * this.scale}px` });
        if (!this.marker.hidden) Object.assign(this.marker.style, {
            left: `${x}px`, top: `${toY(values[local] - offset) * this.scale}px`, backgroundColor: this.settings.style.marker
        });
    }
}
