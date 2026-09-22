export const DEFAULT_ATOM_RADIUS_MAPPING = Object.freeze({
    enabled: false,
    field: '',
    valueTransform: 'identity',
    rangeMode: 'current',
    min: 0,
    max: 1,
    minMultiplier: 0.25,
    maxMultiplier: 1.25,
    exponent: 1,
    scope: 'all',
    indices: []
});

const finiteNumber = (value, fallback) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
};

export function normalizeAtomRadiusMapping(value = {}, { strict = false } = {}) {
    const source = value && typeof value === 'object' ? value : {};
    const normalized = {
        enabled: source.enabled === true,
        field: typeof source.field === 'string' ? source.field : '',
        valueTransform: source.valueTransform === 'absolute' ? 'absolute' : 'identity',
        rangeMode: ['current', 'trajectory', 'manual'].includes(source.rangeMode)
            ? source.rangeMode
            : 'current',
        min: finiteNumber(source.min, DEFAULT_ATOM_RADIUS_MAPPING.min),
        max: finiteNumber(source.max, DEFAULT_ATOM_RADIUS_MAPPING.max),
        minMultiplier: finiteNumber(
            source.minMultiplier,
            DEFAULT_ATOM_RADIUS_MAPPING.minMultiplier
        ),
        maxMultiplier: finiteNumber(
            source.maxMultiplier,
            DEFAULT_ATOM_RADIUS_MAPPING.maxMultiplier
        ),
        exponent: finiteNumber(source.exponent, DEFAULT_ATOM_RADIUS_MAPPING.exponent),
        scope: source.scope === 'indices' ? 'indices' : 'all',
        indices: [...new Set((Array.isArray(source.indices) ? source.indices : [])
            .map(Number)
            .filter(index => Number.isInteger(index) && index >= 0))]
            .sort((a, b) => a - b)
    };
    const errors = [];
    if (source.enabled !== undefined && typeof source.enabled !== 'boolean') {
        errors.push('enabled must be a boolean.');
    }
    if (source.field !== undefined && typeof source.field !== 'string') {
        errors.push('field must be a string.');
    }
    if (source.valueTransform !== undefined
        && !['identity', 'absolute'].includes(source.valueTransform)) {
        errors.push('valueTransform must be identity or absolute.');
    }
    if (source.rangeMode !== undefined
        && !['current', 'trajectory', 'manual'].includes(source.rangeMode)) {
        errors.push('rangeMode must be current, trajectory or manual.');
    }
    if (source.scope !== undefined && !['all', 'indices'].includes(source.scope)) {
        errors.push('scope must be all or indices.');
    }
    for (const key of ['min', 'max', 'minMultiplier', 'maxMultiplier', 'exponent']) {
        if (Object.prototype.hasOwnProperty.call(source, key)
            && (source[key] === null || source[key] === '' || typeof source[key] === 'boolean'
                || !Number.isFinite(Number(source[key])))) {
            errors.push(`${key} must be a finite number.`);
        }
    }
    if (source.indices !== undefined && (!Array.isArray(source.indices)
        || source.indices.some(index => !Number.isInteger(index) || index < 0))) {
        errors.push('Frozen radius indices must be nonnegative integers.');
    }
    if (!(normalized.max > normalized.min)) errors.push('Maximum must be greater than minimum.');
    if (normalized.minMultiplier < 0 || normalized.minMultiplier > 4) {
        errors.push('Minimum multiplier must be between 0 and 4.');
    }
    if (normalized.maxMultiplier < 0 || normalized.maxMultiplier > 4) {
        errors.push('Maximum multiplier must be between 0 and 4.');
    }
    if (normalized.maxMultiplier < normalized.minMultiplier) {
        errors.push('Maximum multiplier must not be smaller than minimum multiplier.');
    }
    if (normalized.exponent < 0.1 || normalized.exponent > 5) {
        errors.push('Exponent must be between 0.1 and 5.');
    }
    if (normalized.enabled && !normalized.field) errors.push('Choose a per-atom property.');
    if (strict && errors.length) throw new Error(errors[0]);
    return {
        mapping: errors.length ? { ...DEFAULT_ATOM_RADIUS_MAPPING, indices: [] } : normalized,
        errors
    };
}

export function fitAtomRadiusRange(values, mapping = DEFAULT_ATOM_RADIUS_MAPPING, indices = null) {
    const selected = indices instanceof Set ? indices : null;
    let minimum = Infinity;
    let maximum = -Infinity;
    let count = 0;
    Array.from(values || []).forEach((rawValue, index) => {
        if (selected && !selected.has(index)) return;
        let value = Number(rawValue);
        if (!Number.isFinite(value)) return;
        if (mapping.valueTransform === 'absolute') value = Math.abs(value);
        minimum = Math.min(minimum, value);
        maximum = Math.max(maximum, value);
        count += 1;
    });
    if (!count) throw new Error('The selected property has no finite values.');
    if (minimum === maximum) {
        const padding = Math.max(1e-12, Math.abs(minimum) * 1e-6);
        minimum -= padding;
        maximum += padding;
    }
    return { minimum, maximum, finiteValues: count };
}

export function atomRadiusFactors(values, mapping, atomCount = values?.length || 0) {
    const { mapping: normalized, errors } = normalizeAtomRadiusMapping(mapping);
    if (errors.length) throw new Error(errors[0]);
    const factors = new Float32Array(Math.max(0, Number(atomCount) || 0));
    factors.fill(1);
    if (!normalized.enabled || !normalized.field) {
        return { factors, missing: 0, applied: 0, mapping: normalized };
    }
    const scope = normalized.scope === 'indices' ? new Set(normalized.indices) : null;
    const span = normalized.max - normalized.min;
    let missing = 0;
    let applied = 0;
    for (let index = 0; index < factors.length; index += 1) {
        if (scope && !scope.has(index)) continue;
        const rawValue = values?.[index];
        let value = rawValue === null || rawValue === undefined ? NaN : Number(rawValue);
        if (!Number.isFinite(value)) {
            missing += 1;
            continue;
        }
        if (normalized.valueTransform === 'absolute') value = Math.abs(value);
        const t = Math.max(0, Math.min(1, (value - normalized.min) / span));
        factors[index] = normalized.minMultiplier
            + (normalized.maxMultiplier - normalized.minMultiplier) * (t ** normalized.exponent);
        applied += 1;
    }
    return { factors, missing, applied, mapping: normalized };
}

export function radiusMappingPreset(name, field, fittedMaximum = 1) {
    const maximum = Number.isFinite(Number(fittedMaximum)) && Number(fittedMaximum) > 0
        ? Number(fittedMaximum)
        : 1;
    if (name === 'fraction') {
        return normalizeAtomRadiusMapping({
            enabled: true, field, rangeMode: 'manual', min: 0, max: 1,
            minMultiplier: 0, maxMultiplier: 1, exponent: 1
        }, { strict: true }).mapping;
    }
    if (name === 'fraction-volume') {
        return normalizeAtomRadiusMapping({
            enabled: true, field, rangeMode: 'manual', min: 0, max: 1,
            minMultiplier: 0, maxMultiplier: 1, exponent: 1 / 3
        }, { strict: true }).mapping;
    }
    if (name === 'charge') {
        return normalizeAtomRadiusMapping({
            enabled: true, field, valueTransform: 'absolute', rangeMode: 'current',
            min: 0, max: maximum, minMultiplier: 0.25, maxMultiplier: 1.5, exponent: 1
        }, { strict: true }).mapping;
    }
    return normalizeAtomRadiusMapping({
        enabled: true, field, rangeMode: 'current', min: 0, max: maximum,
        minMultiplier: 0.25, maxMultiplier: 1.25, exponent: 1
    }, { strict: true }).mapping;
}
