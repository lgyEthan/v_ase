// Trace IDs are shared by the editor and the offline viewer. Plotly uses them
// in unescaped CSS selectors during image export.
export function rdfTraceUid(key) {
    return 'rdf_' + Array.from(key, char => char.codePointAt(0).toString(16)).join('_');
}

export function rdfTraceKey(uid) {
    if (typeof uid !== 'string' || !/^rdf_(?:[0-9a-f]{1,6}_)*[0-9a-f]{1,6}$/.test(uid)) return null;
    const codes = uid.slice(4).split('_').map(hex => Number.parseInt(hex, 16));
    if (codes.some(code => code > 0x10ffff)) return null;
    return codes.map(code => String.fromCodePoint(code)).join('');
}

export function rdfSeriesStyles(result, style = {}, theme = {}) {
    const palette = [theme.teal || '#58d5bd', theme.amber || '#e58b2a', theme.blue || '#6aa7ff',
        '#e05b78', '#a7d46f', '#c49ae8'];
    const modes = { lines: 'line', 'lines+markers': 'line-markers', markers: 'markers' };
    return ['total', ...Object.keys(result?.partial || {})].map((key, index) => {
        const custom = style.series?.[key] || {};
        const line = custom.line || (index === 0 && style.lineColor) || palette[index % palette.length];
        return {
            key, name: key === 'total' ? 'Total' : key.replace('|', ' - '),
            dataMode: modes[style.mode] || 'line',
            lineStyle: style.lineStyle === 'dashdot' ? 'dash-dot' : style.lineStyle || 'solid',
            stroke: (style.lineWidth || 2.4) * (key === 'total' ? 1 : .625),
            line, marker: line, markerShape: 'circle', markerSize: style.markerSize || 5, ...custom,
        };
    });
}

export function rdfPlotlyTrace(series, x, y) {
    const modes = { line: 'lines', 'line-markers': 'lines+markers', markers: 'markers', hidden: 'lines' };
    return {
        type: 'scatter', uid: rdfTraceUid(series.key), x, y,
        name: series.name, mode: modes[series.dataMode], visible: series.dataMode !== 'hidden',
        line: { color: series.line, width: series.stroke, dash: series.lineStyle.replace('dash-dot', 'dashdot') },
        marker: { color: series.marker, size: series.markerSize, symbol: series.markerShape },
    };
}
