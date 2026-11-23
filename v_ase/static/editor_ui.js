import { editorIcon } from './editor_interactions.js?v=0.4.14&ui=20261111.1';
// The workbench is a presentation adapter. Route IDs and mounted scientific
// controls belong to the editor; no project state is stored here.
export const WORKBENCH_ROUTES = Object.freeze({
    style: ['appearance', 'bonding', 'cell-replication', 'polyhedra', 'water', 'isosurfaces', 'forces', 'view'],
    build: ['add-atoms', 'transform', 'cell-transform', 'constraints',
        'build-match', 'scientific-tools', 'build-rigid'],
    analyze: ['selection', 'rdf', 'displacement', 'volumetric', 'registry-map'],
    render: ['export', 'render-image', 'render-video', 'render-html', 'render-geometry']
});

export const WORKBENCH_LABELS = Object.freeze({
    appearance: 'Atoms', bonding: 'Bonds', 'cell-replication': 'Cell',
    isosurfaces: 'Isosurfaces', water: 'Water', polyhedra: 'Polyhedra', view: 'Display & guides',
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
    isosurfaces: 'Create and style scalar-field isosurfaces and sections',
    water: 'Continuous water surface from H₂O coordinates',
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

// The inspector chooses within one workbench. Global Find remains a separate
// toolbar command so the category disclosure never changes its search scope.
export function mountWorkbenchTools() {
    const toolbar=document.getElementById('top-bar');
    // DOM focus order follows the stage-to-inspector composition as well.
    for(const selector of ['#runtime-mode-status','#runtime-mode-switch','#editor-search-toggle','.document-menu-anchor','#editor-quick-actions','.inspector-toolbar']) {
        const element=toolbar?.querySelector(selector);if(element)toolbar.appendChild(element);
    }
    const host = document.getElementById('workbench-tools');
    if (!host) return;
    host.replaceChildren(...Object.entries(WORKBENCH_ROUTES).map(([group, routes]) => {
        const nav = document.createElement('div');
        nav.className = 'workbench-tool-list';
        nav.dataset.toolGroup = group;
        nav.setAttribute('role', 'menu');
        nav.setAttribute('aria-label', `${group[0].toUpperCase()}${group.slice(1)} tools`);
        routes.forEach(route => {
            const button = document.createElement('button');
            button.type = 'button';
            button.id = `workbench-route-${route}`;
            button.dataset.editorRoute = route;
            button.setAttribute('role', 'menuitemradio');
            button.setAttribute('aria-controls', 'inspector-content');
            button.setAttribute('aria-checked', 'false');
            button.innerHTML = editorIcon(route);
            const text = document.createElement('span'); text.className = 'tool-menu-text';
            const label = document.createElement('strong'); label.textContent = WORKBENCH_LABELS[route];
            const detail = document.createElement('span'); detail.textContent = descriptions[route];
            text.append(label, detail); button.appendChild(text);
            button.setAttribute('aria-label', WORKBENCH_LABELS[route]);
            button.dataset.tooltip = WORKBENCH_LABELS[route];
            button.title = `${WORKBENCH_LABELS[route]} — ${descriptions[route]}`;
            button.addEventListener('keydown', event => {
                if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                event.stopPropagation();
                const buttons = [...nav.querySelectorAll('button')].filter(button => !button.hidden);
                const index = buttons.indexOf(button);
                const step = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
                const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                    : (index + step + buttons.length) % buttons.length;
                buttons[next].focus();
            });
            nav.appendChild(button);
        });
        return nav;
    }));
    const trigger = document.getElementById('inspector-tool-trigger');
    const menu = document.getElementById('inspector-tool-menu');
    if (!menu || !trigger) return;
    const setOpen = (open, restoreFocus = false) => {
        menu.hidden = !open;
        menu.inert = !open;
        trigger.setAttribute('aria-expanded', String(open));
        if (open) {
            document.dispatchEvent(new Event('v_ase:category-tools'));
            const group = document.body.dataset.workbench || 'style';
            menu.setAttribute('aria-label', `${group[0].toUpperCase()}${group.slice(1)} tools`);
            const anchor = trigger.getBoundingClientRect();
            const pane = document.getElementById('inspector').getBoundingClientRect();
            menu.style.top = `${anchor.bottom - pane.top + 6}px`;
            menu.style.maxHeight = `${Math.max(60, Math.min(pane.bottom, innerHeight) - anchor.bottom - 18)}px`;
            const current = menu.querySelector('[data-tool-group]:not([hidden]) [aria-checked="true"]');
            (current || menu.querySelector('[data-tool-group]:not([hidden]) button'))?.focus({preventScroll:true});
        } else if (restoreFocus) trigger.focus({preventScroll:true});
    };
    setOpen(false);
    trigger.addEventListener('click', () => setOpen(menu.hidden));
    menu.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        event.preventDefault(); event.stopPropagation(); setOpen(false, true);
    });
    menu.addEventListener('click', event => {
        if (event.target.closest('[data-editor-route]')) setOpen(false, true);
    });
    document.addEventListener('pointerdown', event => {
        if (!menu.hidden && !menu.contains(event.target) && !trigger.contains(event.target)) setOpen(false);
    });
    document.addEventListener('v_ase:tool-route', () => setOpen(false));
    document.addEventListener('v_ase:find-tools', () => setOpen(false));
    document.addEventListener('v_ase:global-tools', () => setOpen(false));
    document.addEventListener('v_ase:close-category-tools', () => setOpen(false));
}


export function workbenchForRoute(route) {
    return Object.keys(WORKBENCH_ROUTES).find(group => WORKBENCH_ROUTES[group].includes(route))
        || (['project','settings','save-guide'].includes(route) ? 'render' : 'style');
}

let routeAnimations = [];
let lastRouteChange = -Infinity;

export function syncWorkbenchRoute(route, title, previousRoute) {
    const group = workbenchForRoute(route);
    document.body.dataset.workbench = group;
    document.querySelectorAll('#workbench-tabs [data-workbench]').forEach(tab => {
        const active = tab.dataset.workbench === group;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('#workbench-tools [data-tool-group]').forEach(nav => {
        nav.hidden = nav.dataset.toolGroup !== group;
    });
    document.querySelectorAll('#workbench-tools [data-editor-route]').forEach(tab => {
        const active = tab.dataset.editorRoute === route;
        tab.setAttribute('aria-checked', String(active));
        tab.tabIndex = -1;
    });
    const heading = document.getElementById('inspector-context');
    if (heading && !heading.parentElement.classList.contains('inspector-title-group')) {
        const group = document.createElement('div'); group.className = 'inspector-title-group';
        heading.replaceWith(group); group.appendChild(heading);
        const description = document.createElement('p');
        description.className = 'inspector-description'; description.id = 'inspector-description';
        group.appendChild(description);
    }
    const description = document.getElementById('inspector-description');
    const toolLabel = document.getElementById('inspector-tool-label');
    if (toolLabel) toolLabel.textContent = WORKBENCH_LABELS[route] || title;
    const toolIcon = document.getElementById('inspector-tool-icon');
    if (toolIcon) toolIcon.innerHTML = editorIcon(route);
    // updateUI also refreshes the current route without a previous route.
    // Only a real navigation may dismiss a chooser the human is using.
    if (previousRoute && previousRoute !== route) document.dispatchEvent(new Event('v_ase:tool-route'));
    if (description) {
        description.textContent = descriptions[route] || '';
        description.hidden = !description.textContent;
    }
    if (previousRoute && previousRoute !== route) {
        routeAnimations.forEach(animation => animation.cancel());
        routeAnimations = [];
        const now = performance.now();
        // Keep repeated route changes immediate. Heading and values transition
        // together on deliberate changes and the canvas stays in place.
        const immediate = matchMedia(
            '(prefers-reduced-motion: reduce), (max-width: 760px) and (max-height: 480px)'
        ).matches;
        if (now - lastRouteChange >= 130 && !immediate) {
            const groupChanged = previousRoute && workbenchForRoute(previousRoute) !== group;
            const order = Object.keys(WORKBENCH_ROUTES);
            const direction = groupChanged && order.indexOf(group) < order.indexOf(workbenchForRoute(previousRoute)) ? -1 : 1;
            routeAnimations = Array.from(document.querySelectorAll(
                '#inspector .inspector-head, #inspector-content > .editor-route-current'
            ), element => element.animate([
                { opacity: .35, transform: `translate(${groupChanged ? direction * 8 : 0}px, ${groupChanged ? 0 : 3}px)` },
                { opacity: 1, transform: 'translate(0, 0)' }
            ], {
                duration: 120, easing: 'cubic-bezier(.2,.8,.2,1)'
            }));
        }
        lastRouteChange = now;
    }
    const content = document.getElementById('inspector-content');
    if (content) content.setAttribute('aria-labelledby','inspector-tool-label');
    const contextual = !WORKBENCH_ROUTES[group].includes(route);
    document.getElementById('workbench-context')?.classList.toggle('hidden', !contextual);
    const contextTitle = document.getElementById('workbench-context-title');
    if (contextTitle) contextTitle.textContent = title;
    document.body.classList.toggle('workbench-contextual', contextual);
}
