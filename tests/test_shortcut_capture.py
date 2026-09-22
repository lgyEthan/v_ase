"""The fullscreen controller reports actual capability and releases its lock."""

from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view


def test_capture_controller_granted_denied_retry_and_exit():
    editor = view(Atoms('H'), notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            result = page.evaluate('''async () => {
                const {installShortcutCapture} = await import('/static/shortcut_capture.js');
                const button = document.createElement('button');
                const status = document.createElement('span');
                document.body.append(button, status);
                let fullscreen = null, denied = false, unlocks = 0;
                const requests = [];
                Object.defineProperty(document, 'fullscreenElement', {
                    configurable:true, get:()=>fullscreen});
                document.documentElement.requestFullscreen = async () => {
                    fullscreen = document.documentElement;
                    document.dispatchEvent(new Event('fullscreenchange'));
                };
                document.exitFullscreen = async () => {
                    fullscreen = null;
                    document.dispatchEvent(new Event('fullscreenchange'));
                };
                Object.defineProperty(navigator, 'keyboard', {configurable:true,
                    value:{lock:async codes => {
                        requests.push(codes);
                        if (denied) throw new Error('permission denied');
                    }, unlock:()=>{unlocks += 1;}}});
                const dispose = installShortcutCapture(button, status);
                const initial = status.dataset.captureState;
                button.click();
                await new Promise(resolve => setTimeout(resolve, 0));
                const locked = {state:status.dataset.captureState,
                    message:status.textContent, codes:requests[0], button:button.textContent};
                button.click();
                await new Promise(resolve => setTimeout(resolve, 0));
                const exited = {state:status.dataset.captureState, unlocks};
                denied = true;
                button.click();
                await new Promise(resolve => setTimeout(resolve, 0));
                const deniedState = {state:status.dataset.captureState,
                    message:status.textContent, retry:button.textContent,
                    exitVisible:!status.nextElementSibling.hidden};
                denied = false;
                button.click();
                await new Promise(resolve => setTimeout(resolve, 0));
                const retried = status.dataset.captureState;
                dispose();
                const disposed = {state:status.dataset.captureState, unlocks};
                await document.exitFullscreen();
                Object.defineProperty(navigator, 'keyboard', {configurable:true, value:{}});
                const disposeUnsupported = installShortcutCapture(button, status);
                button.click();
                await new Promise(resolve => setTimeout(resolve, 0));
                const unsupported = {state:status.dataset.captureState,
                    message:status.textContent, button:button.textContent};
                button.click();
                await new Promise(resolve => setTimeout(resolve, 0));
                const unsupportedExited = status.dataset.captureState;
                disposeUnsupported();
                document.documentElement.requestFullscreen = undefined;
                const disposeUnavailable = installShortcutCapture(button, status);
                button.click();
                const unavailable = {state:status.dataset.captureState,
                    message:status.textContent};
                disposeUnavailable();
                button.remove(); status.remove();
                return {initial, locked, exited, deniedState, retried, disposed,
                    unsupported, unsupportedExited, unavailable};
            }''')
            assert result['initial'] == 'normal'
            assert result['locked']['state'] == 'locked'
            assert 'OS may still reserve' in result['locked']['message']
            assert set(result['locked']['codes']) == {'KeyW', 'KeyN', 'KeyS',
                                                     'KeyB', 'KeyP', 'KeyA', 'KeyE',
                                                     'ArrowLeft', 'ArrowRight'}
            assert result['exited'] == {'state': 'normal', 'unlocks': 1}
            assert result['deniedState']['state'] == 'fullscreen-without-lock'
            assert 'permission denied' in result['deniedState']['message']
            assert result['deniedState']['retry'] == 'Retry capture'
            assert result['deniedState']['exitVisible']
            assert result['retried'] == 'locked'
            assert result['disposed'] == {'state': 'normal', 'unlocks': 2}
            assert result['unsupported']['state'] == 'fullscreen-without-lock'
            assert 'unavailable' in result['unsupported']['message']
            assert result['unsupported']['button'] == 'Exit fullscreen'
            assert result['unsupportedExited'] == 'normal'
            assert result['unavailable']['state'] == 'unavailable'
            assert 'Application fullscreen is unavailable' in result['unavailable']['message']
            browser.close()
    finally:
        editor.close()


def test_embedded_editor_offers_same_session_top_level_link():
    editor = view(Atoms('He'), notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(f'<iframe src="{editor.url}" title="Embedded editor"></iframe>')
            frame = page.frame_locator('iframe')
            link = frame.locator('.shortcut-capture-open-full')
            link.wait_for(state='attached')
            assert link.is_visible() is False  # View menu starts collapsed.
            assert link.get_attribute('href') == editor.url
            assert link.get_attribute('target') == '_blank'
            assert frame.locator('#editor-shortcut-status').get_attribute('data-capture-state') == 'normal'
            assert frame.locator('#editor-fullscreen-editing').is_hidden()
            browser.close()
    finally:
        editor.close()
