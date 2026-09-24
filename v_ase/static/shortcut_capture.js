import { editorLockCodes, editorShortcutLabel, resolveShortcutPlatform } from './editor_commands.js?v=0.4.5';

// A top-level document owns fullscreen/Keyboard Lock. The OS may still reserve
// an accelerator even after lock() resolves.
export function installShortcutCapture(button, status) {
    if (!button || !status) return () => {};
    const doc = button.ownerDocument;
    const win = doc.defaultView;
    const nav = win.navigator;
    const platform = resolveShortcutPlatform();
    const topLevel = win.top === win;
    let state = 'normal';
    let disposed = false;
    let locked = false;
    let attempt = 0;
    let detail = '';

    const secondary = doc.createElement('button');
    secondary.type = 'button';
    secondary.textContent = 'Exit fullscreen';
    secondary.hidden = true;
    secondary.className = 'shortcut-capture-exit';
    status.after(secondary);

    const openFull = doc.createElement('a');
    const fullUrl = new URL(win.location.href);
    fullUrl.searchParams.delete('workspace_child');
    openFull.href = fullUrl.href;
    openFull.target = '_blank';
    openFull.rel = 'noopener noreferrer';
    openFull.textContent = 'Open full editor';
    openFull.className = 'shortcut-capture-open-full';
    openFull.hidden = true;
    secondary.after(openFull);

    function show() {
        if (disposed) return;
        const fullscreen = Boolean(doc.fullscreenElement);
        button.hidden = !topLevel;
        openFull.hidden = topLevel;
        secondary.hidden = !topLevel || !fullscreen || state !== 'fullscreen-without-lock';
        button.disabled = state === 'requesting-fullscreen' || state === 'requesting-lock';
        button.textContent = state === 'fullscreen-without-lock' && nav.keyboard?.lock
            ? 'Retry capture' : fullscreen ? 'Exit fullscreen' : 'Fullscreen editing';
        button.setAttribute('aria-pressed', fullscreen ? 'true' : 'false');
        status.dataset.captureState = state;
        if (!topLevel) {
            status.textContent = 'Keyboard capture requires a top-level editor. Use File actions here or open the same session.';
        } else if (state === 'requesting-fullscreen') {
            status.textContent = 'Entering application fullscreen…';
        } else if (state === 'requesting-lock') {
            status.textContent = 'Requesting keyboard capture…';
        } else if (state === 'locked' && fullscreen) {
            status.textContent = `Keyboard capture active for supported keys (for example ${editorShortcutLabel('save', platform)} and ${editorShortcutLabel('new', platform)}); the OS may still reserve shortcuts.`;
        } else if (state === 'fullscreen-without-lock') {
            status.textContent = `${detail || 'Keyboard Lock is unavailable.'} Fullscreen remains on; use File actions if the browser retains a shortcut.`;
        } else if (state === 'unavailable' || state === 'error') {
            status.textContent = `${detail} Use File actions for browser-reserved shortcuts.`;
        } else {
            status.textContent = 'Some browser shortcuts may remain reserved. Use Fullscreen editing or File actions.';
        }
    }

    function unlock() {
        if (!locked) return;
        try { nav.keyboard?.unlock?.(); } catch {}
        locked = false;
    }

    function onFullscreenChange() {
        if (disposed) return;
        if (!doc.fullscreenElement) {
            attempt += 1;
            unlock();
            state = 'normal';
            detail = '';
        } else if (state !== 'requesting-lock' && state !== 'locked') {
            state = 'fullscreen-without-lock';
            detail = nav.keyboard?.lock ? 'Capture is not active.' : 'Keyboard Lock is unavailable.';
        }
        show();
    }

    async function requestLock(token) {
        if (!doc.fullscreenElement || disposed || token !== attempt) return;
        if (!nav.keyboard?.lock) {
            state = 'fullscreen-without-lock';
            detail = 'Keyboard Lock is unavailable in this browser.';
            show();
            return;
        }
        state = 'requesting-lock';
        show();
        try {
            await nav.keyboard.lock(editorLockCodes());
            if (disposed || token !== attempt || !doc.fullscreenElement) {
                try { nav.keyboard?.unlock?.(); } catch {}
                return;
            }
            locked = true;
            state = 'locked';
            detail = '';
        } catch (error) {
            if (disposed || token !== attempt) return;
            locked = false;
            state = 'fullscreen-without-lock';
            detail = `Keyboard Lock was denied${error?.message ? `: ${error.message}` : '.'}`;
        }
        show();
    }

    async function activate() {
        if (disposed || !topLevel || button.disabled) return;
        if (doc.fullscreenElement) {
            if (state === 'fullscreen-without-lock' && nav.keyboard?.lock) {
                await requestLock(++attempt);
            } else {
                await doc.exitFullscreen?.();
                onFullscreenChange();
            }
            return;
        }
        if (!win.isSecureContext) {
            state = 'unavailable';
            detail = 'Keyboard capture requires a secure context.';
            show();
            return;
        }
        if (!doc.documentElement.requestFullscreen) {
            state = 'unavailable';
            detail = 'Application fullscreen is unavailable in this browser.';
            show();
            return;
        }
        const token = ++attempt;
        state = 'requesting-fullscreen';
        show();
        try {
            await doc.documentElement.requestFullscreen();
        } catch (error) {
            if (disposed || token !== attempt) return;
            state = 'error';
            detail = `Fullscreen was not permitted${error?.message ? `: ${error.message}` : '.'}`;
            show();
            return;
        }
        await requestLock(token);
    }

    const click = () => { void activate(); };
    const exit = () => { void doc.exitFullscreen?.(); };
    const leave = () => {
        attempt += 1;
        unlock();
        state = 'normal';
    };
    button.addEventListener('click', click);
    secondary.addEventListener('click', exit);
    doc.addEventListener('fullscreenchange', onFullscreenChange);
    win.addEventListener('pagehide', leave);
    win.addEventListener('pageshow', onFullscreenChange);
    show();
    return () => {
        if (disposed) return;
        disposed = true;
        attempt += 1;
        button.removeEventListener('click', click);
        secondary.removeEventListener('click', exit);
        doc.removeEventListener('fullscreenchange', onFullscreenChange);
        win.removeEventListener('pagehide', leave);
        win.removeEventListener('pageshow', onFullscreenChange);
        unlock();
        secondary.remove();
        openFull.remove();
        status.dataset.captureState = 'normal';
        status.textContent = '';
    };
}
