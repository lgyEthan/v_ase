// One physical-key registry for the editor, both workspace parents, UI hints,
// and the optional top-level Keyboard Lock.
export const EDITOR_COMMANDS = Object.freeze({
    supercell: { code: 'KeyB', shift: true, label: 'Open Style → Cell → Supercell', section: 'cell-replication', focus: '#super-x' },
    appearance: { code: 'KeyP', shift: true, label: 'Open Style → Atoms', section: 'appearance', focus: '#atom-radius-scale-number' },
    bonding: { code: 'KeyB', shift: false, label: 'Open Style → Bonds', section: 'bonding', focus: '#bond-mode' },
    renderer: { code: 'KeyA', shift: true, label: 'Open Render → Renderer and output scale', section: 'export', focus: '#renderer-framing-mode' },
    'cell-transform': { code: 'KeyE', shift: false, label: 'Open Build → Cell tools → Transform cell', section: 'cell-transform', focus: '#matrix-00' },
    close: { code: 'KeyW', shift: false, label: 'Close the active document after Save/Discard/Cancel', action: 'close' },
    save: { code: 'KeyS', shift: false, label: 'Save the active document to its current target', action: 'save' },
    'save-as': { code: 'KeyS', shift: true, label: 'Save the active document to a new target', action: 'save-as' },
    new: { code: 'KeyN', shift: false, label: 'Create one new document', action: 'new' }
});

export function resolveShortcutPlatform(injected = null) {
    if (injected === 'mac' || injected === 'windows' || injected === 'linux') return injected;
    const browser = globalThis.navigator;
    const candidates = injected && typeof injected === 'object' ? injected : {
        userAgentDataPlatform: browser?.userAgentData?.platform,
        navigatorPlatform: browser?.platform,
        userAgent: browser?.userAgent
    };
    const platform = String(candidates.userAgentDataPlatform || candidates.navigatorPlatform || '');
    if (/mac|iphone|ipad|ipod/i.test(platform)) return 'mac';
    if (/win/i.test(platform)) return 'windows';
    if (/linux/i.test(platform)) return 'linux';
    return /macintosh|mac os|iphone|ipad|ipod/i.test(String(candidates.userAgent || ''))
        ? 'mac' : 'windows';
}

export function commandIdForEvent(event, platform = resolveShortcutPlatform()) {
    if (!event || event.isComposing || event.keyCode === 229
        || event.altKey || event.getModifierState?.('AltGraph')) return null;
    const apple = resolveShortcutPlatform(platform) === 'mac';
    if (apple ? (!event.metaKey || event.ctrlKey) : (!event.ctrlKey || event.metaKey)) {
        return null;
    }
    const fallback = /^[a-z]$/i.test(String(event.key || ''))
        ? `Key${String(event.key).toUpperCase()}` : '';
    const code = event.code && event.code !== 'Unidentified' ? event.code : fallback;
    return Object.entries(EDITOR_COMMANDS).find(([, command]) => (
        command.code === code && command.shift === Boolean(event.shiftKey)
    ))?.[0] || null;
}

export function editorShortcutLabel(id, platform = resolveShortcutPlatform()) {
    const command = EDITOR_COMMANDS[id];
    if (!command) return '';
    const modifier = resolveShortcutPlatform(platform) === 'mac' ? '⌘' : 'Ctrl+';
    return `${modifier}${command.shift ? 'Shift+' : ''}${command.code.slice(3)}`;
}

export function editorAriaShortcut(id, platform = resolveShortcutPlatform()) {
    const command = EDITOR_COMMANDS[id];
    if (!command) return '';
    const modifier = resolveShortcutPlatform(platform) === 'mac' ? 'Meta' : 'Control';
    return `${modifier}+${command.shift ? 'Shift+' : ''}${command.code.slice(3)}`;
}

export function editorShortcutSearchTerms(id, platform = resolveShortcutPlatform()) {
    const command = EDITOR_COMMANDS[id];
    if (!command) return '';
    const letter = command.code.slice(3);
    const shift = command.shift ? ' Shift' : '';
    const visible = editorShortcutLabel(id, platform);
    const spoken = resolveShortcutPlatform(platform) === 'mac'
        ? `Command${shift} ${letter} Cmd${shift} ${letter}`
        : `Control${shift} ${letter} Ctrl${shift} ${letter}`;
    return `${visible} ${spoken} ${command.label}`;
}

export function editorLockCodes() {
    return [...new Set([
        ...Object.values(EDITOR_COMMANDS).map(command => command.code),
        'ArrowLeft', 'ArrowRight'
    ])];
}

// Plain arrows orbit/tilt the camera; Alt (Option on macOS) plus horizontal
// arrows steps the selected timeline. This matcher is shared by the editor and
// both parent workspace shells; editable controls retain their native arrows.
export function viewportNavigationForEvent(event) {
    if (!event || event.isComposing || event.keyCode === 229
        || event.ctrlKey || event.metaKey || event.shiftKey
        || event.getModifierState?.('AltGraph')) return null;
    const code = event.code && event.code !== 'Unidentified' ? event.code : event.key;
    if (event.altKey) {
        if (code === 'ArrowLeft') return { kind: 'frame', delta: -1 };
        if (code === 'ArrowRight') return { kind: 'frame', delta: 1 };
        return null;
    }
    const directions = {
        ArrowLeft: 'left', ArrowRight: 'right',
        ArrowUp: 'up', ArrowDown: 'down'
    };
    return directions[code] ? { kind: 'camera', direction: directions[code] } : null;
}
