import { editorIcon } from './editor_interactions.js?v=0.4.7';
// The workbench is a presentation adapter. Route IDs and mounted scientific
// controls belong to the editor; no project state is stored here.
export const WORKBENCH_ROUTES = Object.freeze({
    style: ['appearance', 'bonding', 'cell-replication', 'polyhedra', 'view'],
    build: ['add-atoms', 'transform', 'cell-transform', 'constraints',
        'build-match', 'scientific-tools', 'build-rigid'],
    analyze: ['selection', 'rdf', 'displacement', 'forces', 'volumetric', 'registry-map'],
    render: ['export', 'render-image', 'render-video', 'render-html', 'render-geometry']
});

export const WORKBENCH_LABELS = Object.freeze({
    appearance: 'Atoms', bonding: 'Bonds', 'cell-replication': 'Cell',
    polyhedra: 'Polyhedra', view: 'View & guides',
    'add-atoms': 'Add atoms', transform: 'Transform',
    'cell-transform': 'Cell matrix', constraints: 'Constraints',
    'build-match': 'Match cells', 'scientific-tools': 'Relax',
    'build-rigid': 'Rigid translation', selection: 'Measure',
    rdf: 'Distributions', displacement: 'Displacements', forces: 'Forces',
    volumetric: 'Fields', 'registry-map': 'Registry', export: 'Renderer',
    'render-image': 'Image', 'render-video': 'Video',
    'render-html': 'Interactive HTML', 'render-geometry': 'Geometry'
});

const descriptions = Object.freeze({
    appearance: 'Atom size, color and property mapping',
    bonding: 'Bond topology, cutoffs and appearance',
    'cell-replication': 'Display cell, repeat and materialize a supercell',
    polyhedra: 'Coordination surfaces and edges', view: 'Camera, background and viewport guides',
    'add-atoms': 'Insert atoms, molecules or an ASE-built structure',
    transform: 'Move, rotate and scale a selection',
    'cell-transform': 'Transform the physical cell with an integer matrix',
    constraints: 'Fixed, directional and spring constraints',
    'build-match': 'Match host and guest periodic cells',
    'scientific-tools': 'Optimize atom positions with a calculator',
    'build-rigid': 'Move or optimize a rigid component',
    selection: 'Inspect atom properties and measure ordered selections',
    rdf: 'Pair, bond and angular distributions',
    displacement: 'Compare positions against a reference',
    forces: 'Inspect stored forces and their vectors',
    volumetric: 'Import and process fields, isosurfaces and planes',
    'registry-map': 'Calculate a rigid-translation landscape',
    export: 'Framing, output scale, lighting and quality',
    'render-image': 'Export an image with exact dimensions',
    'render-video': 'Export a trajectory movie',
    'render-html': 'Export an offline interactive HTML project',
    'render-geometry': 'Export Blender, OBJ or Rhino geometry'
});

// Each workbench exposes its tools in place. No hidden select menu is needed
// to discover a scientific operation, and each real control is mounted once.
export function mountWorkbenchTools() {
    const host = document.getElementById('workbench-tools');
    if (!host) return;
    host.replaceChildren(...Object.entries(WORKBENCH_ROUTES).map(([group, routes]) => {
        const nav = document.createElement('div');
        nav.className = 'workbench-tool-list';
        nav.dataset.toolGroup = group;
        nav.setAttribute('role', 'tablist');
        nav.setAttribute('aria-label', `${group[0].toUpperCase()}${group.slice(1)} tools`);
        routes.forEach(route => {
            const button = document.createElement('button');
            button.type = 'button';
            button.id = `workbench-route-${route}`;
            button.dataset.editorRoute = route;
            button.setAttribute('role', 'tab');
            button.setAttribute('aria-controls', 'inspector-content');
            button.setAttribute('aria-selected', 'false');
            button.innerHTML = editorIcon(route);
            button.setAttribute('aria-label', WORKBENCH_LABELS[route]);
            button.dataset.tooltip = WORKBENCH_LABELS[route];
            button.title = `${WORKBENCH_LABELS[route]} — ${descriptions[route]}`;
            button.addEventListener('keydown', event => {
                if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                event.stopPropagation();
                const buttons = [...nav.querySelectorAll('button')];
                const index = buttons.indexOf(button);
                const step = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
                const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                    : (index + step + buttons.length) % buttons.length;
                buttons[next].click();
                buttons[next].focus();
            });
            nav.appendChild(button);
        });
        return nav;
    }));
}

export function workbenchForRoute(route) {
    return Object.keys(WORKBENCH_ROUTES).find(group => WORKBENCH_ROUTES[group].includes(route)) || 'style';
}

export function syncWorkbenchRoute(route, title) {
    const group = workbenchForRoute(route);
    document.body.dataset.workbench = group;
    document.querySelectorAll('[data-workbench]').forEach(tab => {
        const active = tab.dataset.workbench === group;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('#workbench-tools [data-tool-group]').forEach(nav => {
        nav.hidden = nav.dataset.toolGroup !== group;
    });
    document.querySelectorAll('#workbench-tools [data-editor-route]').forEach(tab => {
        const active = tab.dataset.editorRoute === route;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
    });
    const content = document.getElementById('inspector-content');
    if (content) content.setAttribute('aria-labelledby', WORKBENCH_ROUTES[group].includes(route)
        ? `workbench-route-${route}` : 'workbench-context-title');
    const contextual = !WORKBENCH_ROUTES[group].includes(route);
    document.getElementById('workbench-context')?.classList.toggle('hidden', !contextual);
    const contextTitle = document.getElementById('workbench-context-title');
    if (contextTitle) contextTitle.textContent = title;
    document.body.classList.toggle('workbench-contextual', contextual);
}
