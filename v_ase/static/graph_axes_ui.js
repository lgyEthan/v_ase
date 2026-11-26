import { graphAxisFields } from './trajectory_energy.js?v=0.5.1';

export function createAxisControls(container, axes, onChange) {
    let applied = axes;
    const inputs = graphAxisFields.map(([key, label]) => {
        const row = document.createElement('label');
        row.className = 'prop-row';
        const input = document.createElement('input');
        input.type = 'number';
        input.step = 'any';
        input.placeholder = 'Auto';
        row.append(label, input);
        container.append(row);
        return [key, input];
    });
    const status = document.createElement('p');
    status.className = 'panel-note graph-axis-warning';
    status.setAttribute('role', 'status');
    status.hidden = true;
    container.append(status);
    const sync = (axes, force = false) => {
        applied = axes;
        if (force) { status.hidden = true; status.textContent = ''; }
        for (const [key, input] of inputs) {
            if (force || input !== document.activeElement) input.value = axes[key] ?? '';
        }
    };
    const read = () => {
        const next = Object.fromEntries(inputs.map(([key, input]) => [key,
            Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : null]));
        const invalid = inputs.some(([, input]) => !input.validity.valid)
            || [['xMin', 'xMax'], ['yMin', 'yMax']].some(([min, max]) =>
                next[min] !== null && next[max] !== null && next[min] >= next[max]);
        status.hidden = !invalid;
        status.textContent = invalid ? 'Enter a number or leave it blank. Each minimum must be less than its maximum.' : '';
        return invalid ? null : next;
    };
    if (onChange) {
        const apply = (force = false) => {
            const next = read();
            if (!next || (!force && inputs.every(([key]) => next[key] === applied[key]))) return;
            applied = next;
            onChange(next, { force });
        };
        container.addEventListener('input', () => apply());
        container.addEventListener('change', () => apply());
        for (const [, input] of inputs) input.addEventListener('keydown', event => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            event.stopPropagation();
            apply(true);
        });
    }
    sync(axes, true);
    return { sync, read, focus: () => inputs[0][1].focus() };
}

function dataExtent(traces, key) {
    let low = Infinity, high = -Infinity;
    for (const trace of traces) {
        if (trace.visible === false) continue;
        for (const value of trace[key] || []) {
            if (!Number.isFinite(value)) continue;
            low = Math.min(low, value);
            high = Math.max(high, value);
        }
    }
    return Number.isFinite(low) ? [low, high] : [0, 1];
}

export function plotlyAxisBounds(axes, key, defaults = null, traces = null) {
    const min = axes[`${key}Min`], max = axes[`${key}Max`];
    if (min === null && max === null) return defaults ? { range: defaults } : {};
    if (!defaults && traces && (min === null || max === null)) {
        const extent = dataExtent(traces, key);
        // Partial autorange in Plotly can reset the pinned end on a new trace.
        // Resolve the other end from this result, including breathing room for markers.
        const span = extent[1] - extent[0] || Math.max(1e-6, Math.abs(extent[0]) * .05);
        defaults = [extent[0] - .04 * span, extent[1] + .04 * span];
    }
    if (defaults) {
        const extent = defaults[1] - defaults[0];
        const span = extent > 0 ? extent : Math.max(Math.abs(defaults[0]) * .05, 1e-6);
        const low = min ?? (max > defaults[0] ? defaults[0] : max - span);
        const high = max ?? (low < defaults[1] ? defaults[1] : low + span);
        return { range: [low, high], autorange: false };
    }
    return { range: [min, max], autorange: min === null ? 'min' : max === null ? 'max' : false };
}
