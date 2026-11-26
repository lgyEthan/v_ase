import { editorIcon } from './editor_interactions.js?v=0.5.1&ui=20261111.1';

// A presentation of the editor's actual scene entries. Both the standalone
// navigator and workspace parent use the same rows; actions stay in the editor.
// Keep rows keyed so background updates never replace a focused visibility box.
export function renderSceneNavigator(root, entries, onAction) {
    if (!root) return;
    root.sceneAction = onAction;
    if (!root.dataset.sceneMounted) {
        root.dataset.sceneMounted = 'true';
        root.addEventListener('click', event => {
            const button = event.target.closest('button[data-object-id]');
            if (button && root.contains(button)) root.sceneAction?.(button.dataset.objectId, 'inspect');
        });
        root.addEventListener('change', event => {
            const input = event.target.closest('input[data-scene-visibility]');
            if (input && root.contains(input)) root.sceneAction?.(input.dataset.sceneVisibility, 'visibility', input.checked);
        });
        root.addEventListener('keydown', event => {
            if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)
                || !event.target.matches('button[data-object-id]')) return;
            const buttons = [...root.querySelectorAll('button[data-object-id]')];
            const index = buttons.indexOf(event.target);
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                : Math.max(0, Math.min(buttons.length - 1, index + (event.key === 'ArrowUp' ? -1 : 1)));
            event.preventDefault(); event.stopPropagation();
            buttons[next]?.focus();
        });
    }
    if (!root.querySelector('.scene-object-group')) {
        root.replaceChildren();
        const objects = document.createElement('div'); objects.className = 'scene-object-group'; objects.dataset.sceneGroup = 'objects';
        const guides = document.createElement('section'); guides.className = 'scene-object-group'; guides.dataset.sceneGroup = 'guides';
        guides.innerHTML = '<h3 class="scene-group-heading">Guides</h3>';
        const overlays = document.createElement('details'); overlays.className = 'scene-object-group scene-overlays'; overlays.dataset.sceneGroup = 'overlays';
        overlays.open = true;
        overlays.innerHTML = '<summary class="scene-group-heading">Overlays</summary>';
        root.append(objects, guides, overlays);
    }
    const existing = new Map([...root.querySelectorAll('[data-scene-id]')].map(row => [row.dataset.sceneId, row]));
    const ids = new Set();
    entries.forEach(entry => {
        ids.add(entry.id);
        let row = existing.get(entry.id);
        if (!row) {
            row = document.createElement('div');
            row.className = 'objects-row scene-row';
            row.dataset.sceneId = entry.id;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'scene-select';
            const icon = document.createElement('span'); icon.className = 'scene-symbol';
            const label = document.createElement('span'); label.className = 'scene-label';
            const count = document.createElement('span'); count.className = 'scene-count';
            button.append(icon, label, count);
            const visibility = document.createElement('label');
            visibility.className = 'scene-visibility';
            const input = document.createElement('input'); input.type = 'checkbox';
            visibility.appendChild(input);
            const eye = document.createElement('span'); eye.className = 'scene-eye';
            eye.innerHTML = editorIcon('view'); eye.setAttribute('aria-hidden', 'true');
            visibility.appendChild(eye);
            row.append(button, visibility);
            const group = root.querySelector(`[data-scene-group="${entry.group || 'objects'}"]`);
            group.appendChild(row);
        }
        const button = row.querySelector('button');
        button.dataset.objectId = entry.id;
        button.dataset.editorRoute = entry.route;
        button.setAttribute('aria-current', entry.active ? 'true' : 'false');
        button.title = entry.label;
        const icon = button.querySelector('.scene-symbol');
        if (icon.dataset.icon !== (entry.icon || entry.route)) {
            icon.dataset.icon = entry.icon || entry.route;
            icon.innerHTML = editorIcon(entry.icon || entry.route);
        }
        const counted = entry.label.match(/^(Atoms|Bonds) · (\d+)$/);
        button.querySelector('.scene-label').textContent = counted?.[1] || entry.label;
        button.querySelector('.scene-count').textContent = counted?.[2] || '';
        const visibility = row.querySelector('.scene-visibility');
        visibility.hidden = entry.visible === null || entry.visible === undefined;
        const input = visibility.querySelector('input');
        input.dataset.sceneVisibility = entry.id;
        input.checked = Boolean(entry.visible);
        input.setAttribute('aria-label', `Show ${entry.label}`);
    });
    existing.forEach((row, id) => { if (!ids.has(id)) row.remove(); });
}
