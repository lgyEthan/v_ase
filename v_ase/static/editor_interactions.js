// Shared editor chrome. Scientific state and mutations remain in ASEApp.
const paths = {
    select: '<path d="m5 3 14 9-7 1-3 7z"/>',
    move: '<path d="M12 3v18M3 12h18m-12-6 3-3 3 3m-6 12 3 3 3-3M6 9l-3 3 3 3m12-6 3 3-3 3"/>',
    orbit: '<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(-30 12 12)"/><circle cx="12" cy="12" r="4"/>',
    rotate: '<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
    scale: '<path d="M14 3h7v7m0-7-9 9M3 10v11h11V10z"/>',
    measure: '<path d="m3 16 13-13 5 5L8 21zM7 12l3 3m1-7 3 3m1-7 3 3"/>',
    add: '<circle cx="9" cy="9" r="5"/><path d="M17 12v10m-5-5h10M4 15v5h5"/>',
    appearance: '<circle cx="8" cy="9" r="5"/><circle cx="17" cy="16" r="4"/><path d="m11 13 3 1"/>',
    bonding: '<circle cx="5" cy="6" r="3"/><circle cx="19" cy="18" r="3"/><path d="m8 7 9 8m-11-5 9 8"/>',
    'cell-replication': '<path d="m12 2 9 5v10l-9 5-9-5V7zm0 10 9-5M12 12 3 7m9 5v10"/>',
    polyhedra: '<path d="m12 2 9 7-4 12H7L3 9zm0 0L7 21m5-19 5 19M3 9h18"/>',
    view: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    transform: '<path d="M3 3h7v7H3zm11 11h7v7h-7zM14 3h7v7m0-7-7 7M3 14v7h7"/>',
    constraints: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v3"/>',
    export: '<path d="M4 4h16v12H4zm4 16h8m-4-4v4"/><circle cx="12" cy="10" r="3"/>',
    'render-image': '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
    'render-video': '<rect x="2" y="5" width="14" height="14" rx="2"/><path d="m16 10 6-4v12l-6-4z"/>',
    'render-html': '<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
    volumetric: '<path d="m2 8 10-5 10 5-10 5zm0 5 10 5 10-5M2 18l10 5 10-5"/>',
    rdf: '<path d="M3 3v18h18M6 17l3-8 4 5 4-9 4 4"/>',
    forces: '<path d="M4 20 20 4m-8 0h8v8M4 13v7h7"/>',
    reset: '<path d="M4 8a8 8 0 1 1 0 8M4 3v5h5"/>',
    search: '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
    'add-atoms': '<circle cx="6" cy="15" r="3"/><circle cx="13" cy="8" r="3"/><path d="m8 13 3-3m7 4v8m-4-4h8"/>',
    selection: '<path d="M3 20h18M3 20 16 3M10 20a7 7 0 0 0-2.8-5.6"/><circle cx="3" cy="20" r="1.5"/>',
    'cell-transform': '<path d="M6 2H3v20h3M18 2h3v20h-3M8 6h1m6 0h1M8 12h1m6 0h1M8 18h1m6 0h1"/>',
    'build-match': '<path d="M2 3h8v8H2zm12 10h8v8h-8zM4 11v7h7m-3-3 3 3-3 3M20 13V6h-7m3-3-3 3 3 3"/>',
    'scientific-tools': '<path d="M3 3v18h18M5 5c2 0 2 13 7 13s5-13 7-13"/><circle cx="12" cy="15" r="2"/>',
    'build-rigid': '<circle cx="5" cy="7" r="2"/><circle cx="5" cy="17" r="2"/><circle cx="12" cy="12" r="2"/><path d="m7 8 3 3m-3 5 3-3M5 9v6m10-3h7m-3-3 3 3-3 3"/>',
    displacement: '<circle cx="5" cy="18" r="3" stroke-dasharray="2 2"/><circle cx="19" cy="5" r="3"/><path d="m8 15 7-7m-5 0h5v5"/>',
    'registry-map': '<path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/><circle cx="12" cy="12" r="2" fill="currentColor"/>',
    'render-geometry': '<path d="m3 10 6-4 6 4v8l-6 4-6-4zm0 0 6 4 6-4m-6 4v8M14 3h7v7m0-7-5 5"/>',
};
export function editorIcon(name) {
    return `<svg class="editor-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name] || paths.view}</svg>`;
}

export function installEditorInteractions(app) {
    // Ctrl+A is also a supported text-editing chord on Mac. Native number
    // controls select only a numeric segment on some Chromium/macOS versions.
    document.addEventListener('keydown', event => {
        if (event.isComposing || event.altKey || event.shiftKey || !(event.ctrlKey || event.metaKey)
            || !((event.code === 'KeyA') || event.key?.toLowerCase() === 'a')) return;
        const field = event.target;
        if (field.matches?.('input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="color"]), textarea')) {
            event.preventDefault(); event.stopImmediatePropagation(); field.select();
        } else if (field.isContentEditable) {
            event.preventDefault(); event.stopImmediatePropagation();
            const range = document.createRange(); range.selectNodeContents(field);
            const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        }
    }, true);
    // Spreadsheet-style vertical editing, while checkboxes remain keyboard
    // reachable by ordinary Tab from outside the cutoff column.
    document.getElementById('pairwise-bond-list')?.addEventListener('keydown', event => {
        if (event.key !== 'Tab' || event.altKey || event.metaKey || event.ctrlKey
            || !event.target.matches('.pairwise-bond-max')) return;
        const fields = [...document.querySelectorAll('.pairwise-bond-max:not(:disabled)')];
        const next = fields[fields.indexOf(event.target) + (event.shiftKey ? -1 : 1)];
        if (next) { event.preventDefault(); next.focus(); next.select(); }
    });
    document.querySelectorAll('#viewport-tools > button').forEach(button => {
        button.innerHTML = editorIcon(button.id.slice(5));
        button.setAttribute('aria-pressed', 'false');
    });
    const toolbar = document.getElementById('viewport-tools');
    for (const [label, tools] of [
        ['Selection and measurement', ['select', 'measure']],
        ['Transform selected objects', ['move', 'rotate', 'scale']],
        ['Camera navigation', ['orbit']],
        ['Create objects', ['add']],
    ]) {
        const group = document.createElement('div'); group.className = 'viewport-tool-group';
        group.setAttribute('role', 'group'); group.setAttribute('aria-label', label);
        tools.forEach(tool => group.appendChild(document.getElementById(`tool-${tool}`)));
        toolbar.appendChild(group);
    }
    document.getElementById('tool-add').removeAttribute('aria-pressed');
    document.getElementById('viewport-transform-apply')?.addEventListener('click', () => app.commitTransform());
    document.getElementById('viewport-transform-cancel')?.addEventListener('click', () => app.cancelTransform());
    document.getElementById('editor-search-toggle').innerHTML = editorIcon('search');
    const menus = [...document.querySelectorAll('#editor-menu-bar > details')];
    const closeSearch = () => {
        document.body.classList.remove('editor-search-open');
        document.getElementById('editor-search-toggle')?.setAttribute('aria-expanded', 'false');
    };
    const closeMenus = () => menus.forEach(menu => { menu.open = false; });
    const showMenu = (menu, focus = false) => {
        closeSearch(); menus.forEach(other => { other.open = other === menu; });
        if (focus) menu.querySelector('button:not(:disabled)')?.focus();
    };
    menus.forEach((menu, index) => {
        const summary = menu.querySelector('summary');
        summary.setAttribute('aria-haspopup', 'menu');
        menu.querySelector('.editor-menu-popover')?.setAttribute('role', 'menu');
        menu.querySelectorAll('button').forEach(item => item.setAttribute('role', 'menuitem'));
        summary.addEventListener('click', event => {
            event.preventDefault();
            if (menu.open) closeMenus(); else showMenu(menu);
        });
        summary.addEventListener('pointerenter', event => {
            if (event.pointerType !== 'touch' && menus.some(other => other.open)) showMenu(menu);
        });
        menu.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Tab'].includes(event.key)) return;
            if (event.key === 'Tab') { closeMenus(); return; }
            event.preventDefault(); event.stopPropagation();
            if (['Home', 'End'].includes(event.key)) {
                const items = [...menu.querySelectorAll('button:not(:disabled)')];
                (event.key === 'Home' ? items[0] : items.at(-1))?.focus();
            } else showMenu(menus[(index + (event.key === 'ArrowRight' ? 1 : menus.length - 1)) % menus.length], true);
        });
    });
    document.getElementById('editor-search-toggle')?.addEventListener('click', closeMenus);
    document.addEventListener('pointerdown', event => {
        if (!event.target.closest?.('#editor-navigator, #editor-search-toggle')) closeSearch();
    });
    // A dropped document always goes through the same explicit destination UI.
    let dragDepth = 0;
    const isFileDrag = event => [...(event.dataTransfer?.types || [])].includes('Files');
    document.addEventListener('dragenter', event => {
        if (!isFileDrag(event)) return;
        event.preventDefault(); dragDepth++; document.body.classList.add('file-drag-over');
    });
    document.addEventListener('dragover', event => {
        if (!isFileDrag(event)) return;
        event.preventDefault(); event.dataTransfer.dropEffect = 'copy';
    });
    document.addEventListener('dragleave', () => {
        if (--dragDepth <= 0) { dragDepth = 0; document.body.classList.remove('file-drag-over'); }
    });
    document.addEventListener('drop', async event => {
        if (!isFileDrag(event)) return;
        event.preventDefault(); event.stopPropagation(); dragDepth = 0;
        document.body.classList.remove('file-drag-over');
        const files = [...event.dataTransfer.files];
        if (!files.length) return;
        if (files.length > 1) { app.toast('Drop one structure or trajectory file at a time.', 'warning'); return; }
        // Obtain browser handles within the trusted drop gesture, before awaiting.
        const handlePromise = app.droppedFileHandle
            ? app.droppedFileHandle(files[0])
            : event.dataTransfer.items[0]?.getAsFileSystemHandle?.();
        const handle = await handlePromise?.catch(() => null);
        app.showOpenFileModal(files[0], { handle: handle || null, dropped: true });
    });
}
