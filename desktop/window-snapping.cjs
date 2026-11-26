'use strict';

const SNAP_DISTANCE = 10;
const RELEASE_DISTANCE = 16;

function snapWindowBounds(bounds, neighbors, previous = {}) {
    const nearest = (axis, size, cross, crossSize) => {
        const start = bounds[axis];
        const end = start + bounds[size];
        const candidates = neighbors.flatMap(other => {
            const gap = Math.max(other[cross] - bounds[cross] - bounds[crossSize],
                bounds[cross] - other[cross] - other[crossSize]);
            if (gap > RELEASE_DISTANCE) return [];
            const far = other[axis] + other[size];
            return [other[axis], far, other[axis] - bounds[size], start + far - end];
        });
        const locked = previous[axis];
        if (locked != null && candidates.includes(locked) && Math.abs(start - locked) <= RELEASE_DISTANCE) return locked;
        let closest = null;
        for (const candidate of candidates) {
            if (Math.abs(candidate - start) <= SNAP_DISTANCE
                && (closest == null || Math.abs(candidate - start) < Math.abs(closest - start))) closest = candidate;
        }
        return closest;
    };
    const x = nearest('x', 'width', 'y', 'height');
    const y = nearest('y', 'height', 'x', 'width');
    return { x: x ?? bounds.x, y: y ?? bounds.y, lock: { x, y } };
}

function attachWindowSnapping(win, windows, screen, platform = process.platform) {
    if (!['darwin', 'win32'].includes(platform)) return;
    const eligible = candidate => !candidate.isDestroyed() && candidate.isVisible()
        && !candidate.isMaximized() && !candidate.isMinimized() && !candidate.isFullScreen()
        && !candidate.isSimpleFullScreen?.();
    let gesture = null, correction = null, lock = {};
    const reset = () => { gesture = correction = null; lock = {}; };

    win.on('will-move', () => {
        if (!eligible(win)) return reset();
        if (platform === 'darwin') {
            // AppKit announces the drag before it updates the origin.
            gesture = { bounds: win.getBounds(), pointer: screen.getCursorScreenPoint() };
            lock = {};
        } else {
            gesture = {};
        }
    });
    for (const event of ['blur', 'will-resize', 'enter-full-screen', 'minimize', 'hide', 'closed']) win.on(event, reset);
    if (platform === 'win32') win.on('moved', reset);

    win.on('move', () => {
        if (correction || !gesture || !eligible(win)) return;
        const bounds = win.getBounds();
        if (platform === 'darwin') {
            const pointer = screen.getCursorScreenPoint();
            const origin = gesture.bounds;
            const dx = pointer.x - gesture.pointer.x, dy = pointer.y - gesture.pointer.y;
            // Ignore programmatic and system moves unrelated to the title-bar drag.
            if (bounds.width !== origin.width || bounds.height !== origin.height
                || Math.abs(bounds.x - origin.x - dx) > RELEASE_DISTANCE * 2
                || Math.abs(bounds.y - origin.y - dy) > RELEASE_DISTANCE * 2) return reset();
        } else {
            gesture = null;
        }
        const display = screen.getDisplayMatching(bounds).id;
        const neighbors = Array.from(windows, candidate => {
            if (candidate === win || !eligible(candidate)) return null;
            const edges = candidate.getBounds();
            return screen.getDisplayMatching(edges).id === display ? edges : null;
        }).filter(Boolean);
        const next = snapWindowBounds(bounds, neighbors, lock);
        lock = next.lock;
        if (next.x === bounds.x && next.y === bounds.y) return;
        // Only correct the window being dragged, without animation or a move event loop.
        correction = next;
        try { win.setPosition(next.x, next.y, false); }
        finally { correction = null; }
    });
}

module.exports = { snapWindowBounds, attachWindowSnapping };
