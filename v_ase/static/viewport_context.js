import * as THREE from 'three';
import { editorShortcutLabel } from './editor_commands.js?v=0.5.1';

function atomReference(renderer, index, offset) {
    if (!Number.isInteger(index)) return null;
    return offset?.some(Boolean) ? {
        kind: 'replica', index, cellOffset: offset,
        key: renderer.supercellReferenceKey(index, offset)
    } : { kind: 'atom', index, key: `atom:${index}` };
}

function pickViewportObject(app, event) {
    const renderer = app.renderer;
    if (renderer.pickRenderAreaEye?.(event)) return { kind: 'camera' };
    const sun = renderer.pickSunHandle?.(event);
    if (sun) return { kind: 'sun' };
    const projection = renderer.interactionProjectionContext(event.clientX, event.clientY);
    const ray = new THREE.Raycaster();
    ray.params.Line.threshold = 3 / Math.max(1, renderer.currentPixelsPerAngstrom());
    ray.setFromCamera(renderer.pointerNdc(event, projection), projection.camera);
    const pickables = new Map();
    for (const [group, kind] of [
        [renderer.atomMeshes, 'atom'], [renderer.bondGroup, 'bond'],
        [renderer.supercellGroup, 'replica'], [renderer.cellGroup, 'cell'],
        [renderer.polyhedraGroup, 'polyhedra'], [renderer.volumetricGroup, 'field'],
        [renderer.volumetricPlaneGroup, 'plane'], [renderer.addAtomsRegionGroup, 'region'],
        [renderer.waterLayer?.group, 'water'], [renderer.displacementGroup, 'displacements'],
        [renderer.forceVectorGroup, 'forces'], [renderer.constraintGuideGroup, 'constraints'],
        [renderer.hookeanGroup, 'constraints'], [renderer.constraintMarkGroup, 'constraints']
    ]) {
        group?.traverseVisible(object => {
            if (object.isMesh || object.isLine || object.isLineSegments) pickables.set(object, kind);
        });
    }
    let hitCell = false;
    for (const hit of ray.intersectObjects([...pickables.keys()], false)) {
        const { object, instanceId, faceIndex } = hit;
        const data = object.userData;
        const kind = pickables.get(object);
        const index = data.waterInstanceOrder?.[instanceId] ?? instanceId;
        if (kind === 'atom') {
            const ref = atomReference(renderer, data.atomIndices?.[index] ?? data.index);
            if (ref && renderer.atomGlyphVisible(ref.index)) return { kind, refs: [ref] };
        }
        if (kind === 'replica' && data.supercellInstanced) {
            const reference = renderer.supercellAtomReference(object, instanceId);
            if (reference && renderer.atomGlyphVisible(reference.index, reference.cellOffset)) {
                return { kind: 'atom', refs: [reference] };
            }
        }
        if (kind === 'cell' || data.supercellCellPreview) {
            // A cell edge within the line pick tolerance can cross a sphere.
            // Give the solid target priority where both can be picked.
            hitCell = true;
            continue;
        }
        const instance = data.bondInstances?.[index];
        const segment = instance?.segment ?? data.bondSegments?.[index];
        if (segment?.i !== undefined && segment?.j !== undefined) {
            const start = instance?.cellOffset || [0, 0, 0];
            const image = instance?.imageOffset ?? (renderer.displayOptions.showPeriodicBonds
                ? renderer.minimumImageBondData(segment.i, segment.j).imageOffset : null);
            const end = image ? start.map((value, axis) => value + image[axis]) : start;
            return { kind: 'bond', refs: [
                atomReference(renderer, segment.i, start), atomReference(renderer, segment.j, end)
            ] };
        }
        if (kind === 'polyhedra') {
            const site = data.polyhedraAtomReferences?.[index];
            if (site) return { kind: 'atom', refs: [atomReference(renderer, site.index, site.cellOffset)] };
            const center = data.polyhedraFaces?.[faceIndex];
            return { kind, refs: center ? [atomReference(renderer, center.index, center.cellOffset)] : [] };
        }
        if (kind === 'plane' && data.planeId) return { kind, id: data.planeId };
        if (kind === 'field') return { kind, id: data.volumetricDatasetId ?? data.datasetId };
        if (kind === 'region' && data.regionId) return { kind, id: data.regionId };
        if (['water', 'displacements', 'forces', 'constraints'].includes(kind)) return { kind };
    }
    return { kind: hitCell ? 'cell' : 'background' };
}

function contextItems(app, target, timeline = false) {
    const item = (label, run, disabled = false, keys = '') => ({ label, run, disabled, keys });
    const open = (route, focus) => app.openEditorRoute(route, { focus });
    const click = id => document.getElementById(id)?.click();
    const select = (refs, mode = 'replace') => app.applySelectionAction({ references: refs, mode, origin: 'context' });
    const use = (refs, existing, action) => () => {
        if (!existing) select(refs);
        return action();
    };
    const canEdit = app.canEditAtoms();
    const canDuplicate = canEdit && app.hasLoadedAtoms() && !app.state.isRelaxing
        && !app.state.atoms?.metadata?.relaxation?.is_relaxing;
    const current = app.selectionEntries();
    const name = ref => `${app.state.atoms?.symbols?.[ref.index] || 'Atom'} #${ref.index}`;
    const isSame = refs => refs?.length === 1 && current.length === 1 && current[0].key === refs[0]?.key;
    const visibility = (id, value) => app.performSceneNavigatorAction(id, 'visibility', value);
    const inspect = id => app.performSceneNavigatorAction(id, 'inspect');
    const atomsActions = (refs, existing) => {
        const selectedFixed = new Set(app.state.atoms?.constraints?.fixed_indices || []);
        const actions = [
            item(refs.length > 1 ? 'Edit labels…' : 'Edit label…', use(refs, existing, () => open('appearance', '#selected-atom-label'))),
            item('Inspect & measure…', use(refs, existing, () => open('selection'))),
            item('Transform…', use(refs, existing, () => open('transform')), !canEdit),
            item('Constraints…', use(refs, existing, () => open('constraints')), !canEdit)
        ];
        if (canEdit && refs.some(ref => !selectedFixed.has(ref.index))) actions.push(
            item('Fix position', use(refs, existing, () => app.updateSelectedConstraints({ fix_atoms: true }))));
        if (canEdit && refs.some(ref => selectedFixed.has(ref.index))) actions.push(
            item('Release fixed position', use(refs, existing, () => app.updateSelectedConstraints({ fix_atoms: false }))));
        actions.push(item(refs.length === 1 ? 'Hide this atom and its bonds' : 'Hide selected atoms and their bonds',
            use(refs, existing, () => app.hideSelectedVisualReferences())));
        return actions;
    };
    const sections = [];
    const group = (scope, label, actions) => sections.push({ scope, label, actions });
    const atomsVisible = app.state.display.showAtoms !== false;
    const refs = target.refs || [];
    switch (target.kind) {
        case 'atom': {
            const ref = refs[0];
            const isSelected = current.some(entry => entry.key === ref.key);
            group('pointer', name(ref) + (ref.kind === 'replica' ? ' · periodic image' : ''), [
                item('Select only this atom', () => select(refs), isSame(refs)),
                item(isSelected ? 'Remove from selection' : 'Add to selection', () => select(refs, 'toggle')),
                ...atomsActions(refs, isSame(refs))
            ]);
            break;
        }
        case 'bond': {
            const selectable = atomsVisible && refs.every(ref => app.isSelectionReferenceVisible(ref)
                && (ref.kind !== 'replica' || app.replicaReferenceIsSelectable(ref)));
            const measurable = selectable
                && app.editableSelectionReference(refs[0]).key !== app.editableSelectionReference(refs[1]).key;
            group('pointer', `${name(refs[0])} – ${name(refs[1])}`, [
                item('Select endpoints', () => select(refs), !selectable),
                item('Inspect distance…', () => {
                    app.applySelectionAction({ references: refs, origin: 'semantic', measurement: 'ordered' });
                    open('selection');
                }, !measurable),
                item('Bond settings…', () => {
                    open('bonding', '#bond-mode');
                    const select = document.getElementById('bond-pair-style-key');
                    const labels = refs.map(ref => app.state.atoms.symbols[ref.index]);
                    select.value = app.labelPairKey(...labels);
                    app.syncBondPairStyleEditor();
                }),
                item('Hide bonds', () => visibility('bonds', false))
            ]);
            break;
        }
        case 'camera':
            group('pointer', 'Render area', [
                item('Camera settings…', () => { open('export', '#renderer-framing-mode'); app.setRenderAreaSelected(true); }),
                item('Align camera to view', () => click('btn-render-area-align-view')),
                item('Hide render area', () => app.setRenderAreaVisible(false))
            ]);
            break;
        case 'sun':
            group('pointer', 'Sun lighting', [item('Lighting settings…', () => open('export', '#renderer-lighting-mode'))]);
            break;
        case 'cell':
            group('pointer', 'Unit cell', [
                item('Cell & supercell…', () => open('cell-replication', '#super-x')),
                item('Transform cell…', () => open('cell-transform', '#matrix-00'), !canEdit),
                item('Hide cell', () => visibility('cell', false))
            ]);
            break;
        case 'polyhedra':
            group('pointer', 'Polyhedra', [
                item('Coordination rules…', () => open('polyhedra')),
                item('Select center', () => select(refs), !atomsVisible || !refs.length),
                item('Hide polyhedra', () => visibility('polyhedra', false))
            ]);
            break;
        case 'plane':
        case 'field': {
            const sceneId = `${target.kind === 'plane' ? 'plane' : 'dataset'}:${target.id}`;
            const available = app.sceneNavigatorEntries?.has(sceneId);
            group('pointer', target.kind === 'plane' ? 'Field plane' : 'Isosurface', [
                item('Field settings…', () => available ? app.performSceneNavigatorAction(sceneId, 'inspect') : open('scene-fields')),
                ...(available ? [item('Hide field', () => visibility(sceneId, false))] : [])
            ]);
            break;
        }
        case 'region': {
            const id = `region:${target.id}`;
            const region = app.sceneNavigatorEntries?.get(id);
            group('pointer', region?.label || 'Insertion region', [
                item('Region settings…', () => region ? inspect(id) : open('add-atoms'))
            ]);
            break;
        }
        case 'water':
        case 'displacements':
        case 'forces':
        case 'constraints': {
            const entry = app.sceneNavigatorEntries?.get(target.kind);
            if (!entry) break;
            group('pointer', entry.label, [
                item('Settings…', () => inspect(entry.id)),
                item(`Hide ${entry.label.toLowerCase()}`, () => visibility(entry.id, false))
            ]);
            break;
        }
        default:
            if (!timeline) group('pointer', 'Viewport', [
                item('Add atoms & molecules…', () => open('add-atoms'), !canEdit),
                item('Fit view', () => app.fitEditorView(), !app.hasLoadedAtoms()),
                item('Display & guides…', () => open('view'))
            ]);
    }
    if (!timeline && current.length && !(target.kind === 'atom' && isSame(refs))) {
        group('selected', `Selected atoms (${current.length})`, atomsActions(current, true));
    }
    if (app.hasLoadedAtoms()) group('trajectory', 'Trajectory', [
        item('Duplicate to next frame', () => app.duplicateTrajectoryFrame('next'), !canDuplicate,
            editorShortcutLabel('duplicate-frame', app.shortcutPlatform)),
        item('Duplicate frame to end', () => app.duplicateTrajectoryFrame('end'), !canDuplicate,
            editorShortcutLabel('append-frame-copy', app.shortcutPlatform)),
        ...(app.loadedFrameCount() > 1 ? [item('Delete current frame',
            () => app.deleteCurrentTrajectoryFrame(), !canDuplicate || app.state.atoms?.metadata?.relaxation?.active)] : [])
    ]);
    return sections;
}

export function installViewportContextMenu(app) {
    const canvas = app.renderer.domElement;
    const timeline = document.getElementById('trajectory-panel');
    const controls = app.renderer.controls;
    const menu = document.createElement('div');
    menu.id = 'viewport-context-menu';
    menu.className = 'viewport-context-menu';
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', 'Viewport commands');
    menu.hidden = true;
    document.body.append(menu);
    let previousFocus = canvas;
    const close = (restore = false) => {
        if (menu.hidden) return;
        menu.hidden = true;
        menu.replaceChildren();
        if (restore && previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
    const allowed = () => app.collaborationReady && app.transform.mode === 'IDLE'
        && !document.body.dataset.busy && document.getElementById('modal-container').classList.contains('hidden');
    const show = (event, onTimeline = false) => {
        if (!allowed()) return;
        close();
        const target = onTimeline ? { kind: 'background' } : pickViewportObject(app, event);
        const sections = contextItems(app, target, onTimeline);
        if (!sections.length) return;
        previousFocus = onTimeline ? document.activeElement : canvas;
        const frame = app.timelineFrameIndex(app.primaryTimelineSource());
        const generation = app.structureGeneration;
        for (const section of sections) {
            const group = document.createElement('div');
            group.className = 'viewport-context-group';
            group.dataset.contextScope = section.scope;
            group.setAttribute('role', 'group');
            group.setAttribute('aria-label', section.label);
            const title = document.createElement('div');
            title.className = 'viewport-context-title';
            title.textContent = section.label;
            group.append(title);
            for (const action of section.actions) {
                const button = document.createElement('button');
                button.type = 'button';
                button.setAttribute('role', 'menuitem');
                button.tabIndex = -1;
                button.disabled = action.disabled;
                const label = document.createElement('span');
                label.textContent = action.label;
                button.append(label);
                if (action.keys) {
                    const keys = document.createElement('kbd');
                    keys.textContent = action.keys;
                    button.append(keys);
                }
                button.onclick = async () => {
                    close(true);
                    if (!allowed() || generation !== app.structureGeneration
                        || frame !== app.timelineFrameIndex(app.primaryTimelineSource())) {
                        app.toast('The scene changed. Open the menu again.', 'warning');
                        return;
                    }
                    try { await action.run(); }
                    catch (error) { app.toast(error.message, 'error'); }
                };
                group.append(button);
            }
            menu.append(group);
        }
        menu.hidden = false;
        const margin = 8;
        const pane = canvas.getBoundingClientRect();
        const boundRight = onTimeline ? innerWidth : Math.min(innerWidth, pane.right);
        const boundBottom = onTimeline ? innerHeight : Math.min(innerHeight, pane.bottom);
        const boundLeft = onTimeline ? 0 : Math.max(0, pane.left);
        const boundTop = onTimeline ? 0 : Math.max(0, pane.top);
        menu.style.maxWidth = `${Math.max(0, boundRight - boundLeft - 2 * margin)}px`;
        menu.style.maxHeight = `${Math.max(0, boundBottom - boundTop - 2 * margin)}px`;
        const left = Math.max(boundLeft + margin, Math.min(boundRight - menu.offsetWidth - margin, event.clientX + 3));
        const top = Math.max(boundTop + margin, Math.min(boundBottom - menu.offsetHeight - margin, event.clientY + 3));
        Object.assign(menu.style, { left: `${left}px`, top: `${top}px` });
        menu.querySelector('button:not(:disabled)')?.focus({ preventScroll: true });
    };
    controls.isContextModifier = event => app.shortcutPlatform === 'mac' && event.button === 0 && event.ctrlKey;
    controls.onContextClick = show;

    const outside = event => { if (!menu.contains(event.target)) close(); };
    const closeOnBlur = () => close();
    const timelineMenu = event => {
        event.preventDefault();
        show(event, true);
    };
    const keys = event => {
        if (menu.hidden) {
            if (event.target !== canvas || !(event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10'))) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            const { left, top, width, height } = canvas.getBoundingClientRect();
            const hovered = app.state.lastPointer;
            const inViewport = hovered.x >= left && hovered.x <= left + width
                && hovered.y >= top && hovered.y <= top + height;
            show({ clientX: inViewport ? hovered.x : left + width / 2,
                clientY: inViewport ? hovered.y : top + height / 2 });
            return;
        }
        if (event.key === 'Escape' || event.key === 'Tab') {
            close(true);
            if (event.key === 'Escape') event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        const buttons = [...menu.querySelectorAll('button:not(:disabled)')];
        const current = buttons.indexOf(document.activeElement);
        const index = { ArrowDown: (current + 1) % buttons.length,
            ArrowUp: (current + buttons.length - 1) % buttons.length, Home: 0, End: buttons.length - 1 }[event.key];
        if (index !== undefined) {
            event.preventDefault();
            event.stopImmediatePropagation();
            buttons[index]?.focus();
        }
    };
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', keys, true);
    window.addEventListener('blur', closeOnBlur);
    window.addEventListener('resize', closeOnBlur);
    timeline?.addEventListener('contextmenu', timelineMenu);
    return () => {
        document.removeEventListener('pointerdown', outside, true);
        document.removeEventListener('keydown', keys, true);
        window.removeEventListener('blur', closeOnBlur);
        window.removeEventListener('resize', closeOnBlur);
        timeline?.removeEventListener('contextmenu', timelineMenu);
        delete controls.onContextClick;
        delete controls.isContextModifier;
        menu.remove();
    };
}
