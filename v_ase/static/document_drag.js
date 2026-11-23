// Pure geometry shared by native document gestures and their headless checks.
export function documentDropDestination(point, bar, tabs, vertical, viewport) {
    const outsideWindow = point.x < -24 || point.y < -24
        || point.x > viewport.width + 24 || point.y > viewport.height + 24;
    const detach = outsideWindow || (vertical ? point.x > bar.right + 56 : point.y > bar.bottom + 56);
    if (detach) return { action: 'detach' };
    const target = tabs.find(tab => point.x >= tab.left && point.x <= tab.right
        && point.y >= tab.top && point.y <= tab.bottom);
    if (!target) return { action: 'none' };
    return { action: 'reorder', id: target.id,
        before: vertical ? point.y < (target.top + target.bottom) / 2
            : point.x < (target.left + target.right) / 2 };
}
