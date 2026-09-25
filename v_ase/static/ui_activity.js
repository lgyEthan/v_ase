// A counter per section keeps concurrent/nested requests from hiding each
// other's feedback. Indicators do not capture focus or block navigation.
export function installActivityIndicators(App) {
    const activities = {
        ensureAtomColorScaleCatalog: ['[data-panel="appearance"] .atom-colorscale-card', 'Loading properties…'],
        updateAtomColorScale: ['[data-panel="appearance"] .atom-colorscale-card', 'Updating colors…'],
        fitAtomColorScaleRange: ['[data-panel="appearance"] .atom-colorscale-card', 'Finding color range…'],
        ensureAtomRadiusCatalog: ['.atom-radius-mapping-card', 'Loading properties…'],
        updateAtomRadiusMapping: ['.atom-radius-mapping-card', 'Updating radii…'],
        fitAtomRadiusMappingRange: ['.atom-radius-mapping-card', 'Finding radius range…'],
        calculateRdf: ['[data-panel="rdf"]', 'Calculating distribution…'],
        calculateRegistryMap: ['[data-panel="registry-map"]', 'Calculating translation map…'],
        refreshDisplacementAnalysis: ['[data-panel="displacement"]', 'Calculating displacements…'],
        updateForceVectorsForCurrentFrame: ['[data-panel="forces"]', 'Loading forces…'],
        updateVolumetricSurface: ['#volume-tool-surface', 'Building isosurface…'],
        renderAllVolumetricPlanes: ['#volume-plane-editor', 'Rendering planes…']
    };
    const counters = new WeakMap();
    for (const [method, [selector, label]] of Object.entries(activities)) {
        const original = App.prototype[method];
        if (!original) continue;
        App.prototype[method] = async function (...args) {
            const root = document.querySelector(selector);
            let indicator;
            if (root) {
                const count = counters.get(root) || 0;
                counters.set(root, count + 1);
                root.setAttribute('aria-busy', 'true');
                indicator = root.querySelector(':scope > .section-activity');
                if (!indicator) {
                    indicator = document.createElement('div');
                    indicator.className = 'section-activity';
                    indicator.setAttribute('role', 'status');
                    root.appendChild(indicator);
                }
                indicator.textContent = label;
                indicator.hidden = false;
            }
            try { return await original.apply(this, args); }
            finally {
                if (root) {
                    const count = Math.max(0, (counters.get(root) || 1) - 1);
                    counters.set(root, count);
                    if (!count) { root.setAttribute('aria-busy', 'false'); indicator.hidden = true; }
                }
            }
        };
    }
}
