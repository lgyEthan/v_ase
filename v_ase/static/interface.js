// Presentation-only controls. No coordinates, display settings or history live here.
export function updateRangeFill(range) {
    if (!range?.matches?.('input[type="range"]')) return;
    const min = Number(range.min || 0), max = Number(range.max || 100);
    const fraction = max > min ? (Number(range.value) - min) / (max - min) : 0;
    range.style.setProperty('--range-fill', `${Math.max(0, Math.min(1, fraction)) * 100}%`);
}

export function refreshRangeFills(root = document) {
    root.querySelectorAll('input[type="range"]').forEach(updateRangeFill);
}

const isolationSurfaces = new Map();
let isolationBase = null;
let dismissTooltip = null;
export function hideInterfaceTooltip() { dismissTooltip?.(); }
function syncSurfaceIsolation(surface, active, priority) {
    if (!surface) return;
    if (active) isolationSurfaces.set(surface, priority);
    else isolationSurfaces.delete(surface);
    const top = [...isolationSurfaces].sort((a, b) => b[1] - a[1])[0]?.[0];
    if (top) {
        isolationBase ||= new Map();
        for (const sibling of document.body.children) {
            if (sibling.id === 'toolbar-tooltip' || sibling.tagName === 'SCRIPT') continue;
            if (!isolationBase.has(sibling)) isolationBase.set(sibling, sibling.inert);
            sibling.inert = sibling !== top;
        }
    } else if (isolationBase) {
        isolationBase.forEach((value, sibling) => { sibling.inert = value; });
        isolationBase = null;
    }
}
export function syncModalIsolation(modal) {
    syncSurfaceIsolation(modal, Boolean(modal && !modal.classList.contains('hidden')), 1);
}
export function syncBusyIsolation(overlay, active) {
    syncSurfaceIsolation(overlay, active, 2);
}

// The glyph, label and accessibility state describe the same panel state.
export function syncPanelToggle(button, expanded, side = 'left', name = 'Scene sidebar') {
    if (!button) return;
    if (!button.dataset.panelToggleGlyphs) {
        const pane = side === 'left' ? '<path d="M9 4v16"/><rect x="4" y="5" width="4" height="14" fill="currentColor" opacity=".22" stroke="none"/>' : '<path d="M15 4v16"/><rect x="16" y="5" width="4" height="14" fill="currentColor" opacity=".22" stroke="none"/>';
        const close = side === 'left' ? 'm14 8-4 4 4 4' : 'm10 8 4 4-4 4';
        const open = side === 'left' ? 'm12 8 4 4-4 4' : 'm12 8-4 4 4 4';
        const frame = '<rect x="3" y="4" width="18" height="16" rx="3"/>';
        button.innerHTML = `<span class="panel-state-glyph panel-glyph-open"><svg viewBox="0 0 24 24" aria-hidden="true">${frame}${pane}<path d="${close}"/></svg></span><span class="panel-state-glyph panel-glyph-closed"><svg viewBox="0 0 24 24" aria-hidden="true">${frame}<path d="${open}"/></svg></span>`;
        button.dataset.panelToggleGlyphs = 'true';
    }
    button.setAttribute('aria-pressed',String(expanded));
    button.setAttribute('aria-expanded',String(expanded));
    const label = `${expanded ? 'Hide' : 'Show'} ${name}`;
    button.setAttribute('aria-label',label);button.title=label;button.dataset.tooltip=label;
}

// A separator is usable with a pointer, touch, or keyboard. Interrupted drags
// restore the starting size; values are persisted only after an intentional end.
export function installResizeHandle(handle, {
    axis = 'x', direction = 1, getValue, setValue, bounds, defaultValue,
    step = 8, className = 'ui-resizing', enabled = () => true
}) {
    if (!handle || handle.dataset.uiResizeBound) return;
    handle.dataset.uiResizeBound = 'true';
    handle.tabIndex = 0;
    let drag = null;
    const apply = (value, persist = false) => {
        const [min, max] = bounds();
        const next = Math.max(min, Math.min(max, Math.round(value)));
        setValue(next, persist);
        handle.setAttribute('aria-valuemin', String(Math.round(min)));
        handle.setAttribute('aria-valuemax', String(Math.round(max)));
        handle.setAttribute('aria-valuenow', String(next));
        handle.setAttribute('aria-valuetext', `${next} pixels`);
    };
    const sync = () => {
        const [min, max] = bounds();
        handle.setAttribute('aria-valuemin', String(Math.round(min)));
        handle.setAttribute('aria-valuemax', String(Math.round(max)));
        handle.setAttribute('aria-valuenow', String(Math.round(getValue())));
        handle.setAttribute('aria-valuetext', `${Math.round(getValue())} pixels`);
    };
    const finish = commit => {
        if (!drag) return;
        const previous = drag;
        drag = null;
        apply(commit ? getValue() : previous.value, commit);
        document.body.classList.remove('ui-resizing', className);
        if (handle.hasPointerCapture?.(previous.id)) handle.releasePointerCapture(previous.id);
    };
    handle.addEventListener('pointerdown', event => {
        if (event.button !== 0 || !enabled()) return;
        event.preventDefault(); event.stopPropagation();
        drag = { id: event.pointerId, origin: axis === 'x' ? event.clientX : event.clientY, value: getValue() };
        handle.focus({ preventScroll: true });
        handle.setPointerCapture(event.pointerId);
        document.body.classList.add('ui-resizing', className);
    });
    handle.addEventListener('pointermove', event => {
        if (!drag || event.pointerId !== drag.id) return;
        event.preventDefault();
        apply(drag.value + direction * ((axis === 'x' ? event.clientX : event.clientY) - drag.origin));
    });
    handle.addEventListener('pointerup', event => { if (event.pointerId === drag?.id) finish(true); });
    handle.addEventListener('pointercancel', () => finish(false));
    handle.addEventListener('lostpointercapture', () => finish(false));
    window.addEventListener('blur', () => finish(false));
    window.addEventListener('v_ase:interaction-blocked', () => finish(false));
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || !drag) return;
        event.preventDefault(); event.stopImmediatePropagation(); finish(false);
    }, true);
    handle.addEventListener('keydown', event => {
        if (!enabled() || event.altKey || event.metaKey || event.ctrlKey) return;
        const negative = axis === 'x' ? 'ArrowLeft' : 'ArrowUp';
        const positive = axis === 'x' ? 'ArrowRight' : 'ArrowDown';
        if (![negative, positive, 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation();
        const [min, max] = bounds();
        apply(event.key === 'Home' ? min : event.key === 'End' ? max
            : getValue() + (event.key === negative ? -1 : 1) * direction * step * (event.shiftKey ? 4 : 1), true);
    });
    handle.addEventListener('dblclick', event => {
        if (!enabled() || defaultValue === undefined) return;
        event.preventDefault(); apply(typeof defaultValue === 'function' ? defaultValue() : defaultValue, true);
    });
    window.addEventListener('resize', sync);
    handle.addEventListener('focus', sync);
    sync();
    return sync;
}

export function installInterfaceControls() {
    if (document.documentElement.dataset.interfaceReady) return;
    document.documentElement.dataset.interfaceReady = 'true';
    refreshRangeFills();
    let rangeFrame = null;
    const scheduleRanges = () => {
        if (rangeFrame !== null) return;
        rangeFrame = requestAnimationFrame(() => { rangeFrame = null; refreshRangeFills(); });
    };
    document.addEventListener('input', event => { updateRangeFill(event.target); scheduleRanges(); });
    document.addEventListener('change', () => refreshRangeFills());
    // Dynamic field rows and auto-generated number companions arrive after mount.
    new MutationObserver(records => {
        for (const record of records) for (const node of record.addedNodes) {
            if (node.nodeType !== 1) continue;
            updateRangeFill(node); refreshRangeFills(node);
        }
    }).observe(document.body, { childList: true, subtree: true });

    const tooltip = document.createElement('div');
    tooltip.id = 'toolbar-tooltip'; tooltip.className = 'interface-tooltip';
    tooltip.setAttribute('role', 'tooltip'); tooltip.hidden = true;
    document.body.appendChild(tooltip);
    let target = null, timer = null, oldDescription = null, refreshTooltip = null;
    const titleMessages = new WeakMap();
    const canShowTooltip = element => element?.dataset.tooltip && (!element.disabled || element.dataset.disabledTooltip);
    const messageFor = element => (element.disabled && element.dataset.disabledTooltip)
        || titleMessages.get(element) || element.dataset.tooltip;
    const consumeTitle = element => {
        const nativeTitle = element.getAttribute('title');
        if (nativeTitle === null) return;
        if (nativeTitle) titleMessages.set(element, nativeTitle);
        else titleMessages.delete(element);
        // One tooltip surface, without changing a control's short data label.
        element.removeAttribute('title');
    };
    const hide = () => {
        window.clearTimeout(timer); timer = null; tooltip.hidden = true;
        refreshTooltip = null;
        if (target) {
            if (oldDescription === null) target.removeAttribute('aria-describedby');
            else target.setAttribute('aria-describedby', oldDescription);
        }
        target = null;
    };
    dismissTooltip = hide;
    const show = (element, immediate = false) => {
        hide();
        if (!canShowTooltip(element)) return;
        consumeTitle(element);
        target = element; oldDescription = element.getAttribute('aria-describedby');
        const reveal = () => {
            if (target !== element || !element.isConnected) return;
            tooltip.textContent = messageFor(element);
            tooltip.hidden = false;
            const box = element.getBoundingClientRect(), tip = tooltip.getBoundingClientRect();
            const besideTools = element.closest('.viewport-tools') && box.right + 7 + tip.width <= innerWidth - 8;
            const left = besideTools ? box.right + 7
                : Math.max(8, Math.min(innerWidth - tip.width - 8, box.left + (box.width - tip.width) / 2));
            let top = besideTools
                ? Math.min(innerHeight - tip.height - 8, box.top + (box.height - tip.height) / 2)
                : box.bottom + 7;
            if (!besideTools && top + tip.height > innerHeight - 8) top = box.top - tip.height - 7;
            tooltip.style.left = `${left}px`; tooltip.style.top = `${Math.max(8, top)}px`;
            element.setAttribute('aria-describedby', [oldDescription, tooltip.id].filter(Boolean).join(' '));
        };
        refreshTooltip = reveal;
        if (immediate) reveal(); else timer = window.setTimeout(reveal, 450);
    };
    document.addEventListener('pointerover', event => {
        if (event.pointerType === 'touch') return;
        const element = event.target.closest?.('[data-tooltip]');
        if (element && !element.contains(event.relatedTarget)) show(element);
    });
    document.addEventListener('pointerout', event => {
        if (target && !target.contains(event.relatedTarget)) hide();
    });
    document.addEventListener('focusin', event => {
        if (event.target.matches?.('[data-tooltip]:focus-visible')) show(event.target, true);
    });
    document.addEventListener('focusout', hide);
    document.addEventListener('pointerdown', hide, true);
    document.addEventListener('scroll', hide, true);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); }, true);
    window.addEventListener('blur', hide);

    // Refresh the current hint when its title or disabled reason changes.
    new MutationObserver(records => {
        if (!target || !records.some(record => record.target === target)) return;
        if (!canShowTooltip(target)) { hide(); return; }
        consumeTitle(target);
        if (!tooltip.hidden && tooltip.textContent !== messageFor(target)) refreshTooltip?.();
    }).observe(document.body, {
        attributes: true, subtree: true, attributeFilter: ['title', 'disabled', 'data-disabled-tooltip']
    });

    // Existing dialogs trap Tab. Inert siblings also isolate assistive navigation.
    const modal = document.getElementById('modal-container');
    if (modal) {
        new MutationObserver(() => {
            if (!modal.classList.contains('hidden')) hide();
            syncModalIsolation(modal);
        }).observe(modal, { attributes: true, attributeFilter: ['class'] });
    }
}
