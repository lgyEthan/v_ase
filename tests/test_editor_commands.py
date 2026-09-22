"""Platform modifier policy is independent of the host running pytest."""

from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view


def test_shared_command_registry_matches_ten_exact_platform_chords():
    editor = view(Atoms('H', positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            result = page.evaluate('''async () => {
                const commands = await import('/static/editor_commands.js');
                const ids = Object.keys(commands.EDITOR_COMMANDS);
                const matched = {};
                for (const platform of ['mac', 'windows', 'linux']) {
                    matched[platform] = ids.map(id => {
                        const command = commands.EDITOR_COMMANDS[id];
                        const apple = platform === 'mac';
                        const event = {code:command.code,key:command.code.slice(3),
                            shiftKey:command.shift,metaKey:apple,ctrlKey:!apple,
                            altKey:false,isComposing:false,keyCode:0,
                            getModifierState:()=>false};
                        return {
                            id, label:commands.editorShortcutLabel(id,platform),
                            aria:commands.editorAriaShortcut(id,platform),
                            positive:commands.commandIdForEvent(event,platform),
                            wrongShift:commands.commandIdForEvent({...event,shiftKey:!command.shift},platform),
                            wrongModifier:commands.commandIdForEvent({...event,
                                metaKey:!apple,ctrlKey:apple},platform),
                            both:commands.commandIdForEvent({...event,metaKey:true,ctrlKey:true},platform),
                            alt:commands.commandIdForEvent({...event,altKey:true},platform),
                            composing:commands.commandIdForEvent({...event,isComposing:true},platform),
                            altGraph:commands.commandIdForEvent({...event,
                                getModifierState:key=>key==='AltGraph'},platform),
                            fallback:commands.commandIdForEvent({...event,code:''},platform),
                            unidentified:commands.commandIdForEvent({...event,code:'Unidentified'},platform)
                        };
                    });
                }
                const arrow = {code:'ArrowLeft',key:'ArrowLeft',shiftKey:false,
                    metaKey:false,ctrlKey:false,altKey:false,isComposing:false,
                    keyCode:0,getModifierState:()=>false};
                const navigation = {
                    left:commands.viewportNavigationForEvent(arrow),
                    right:commands.viewportNavigationForEvent({...arrow,code:'ArrowRight'}),
                    up:commands.viewportNavigationForEvent({...arrow,code:'ArrowUp'}),
                    down:commands.viewportNavigationForEvent({...arrow,code:'ArrowDown'}),
                    previous:commands.viewportNavigationForEvent({...arrow,altKey:true}),
                    next:commands.viewportNavigationForEvent({...arrow,code:'ArrowRight',altKey:true}),
                    altUp:commands.viewportNavigationForEvent({...arrow,code:'ArrowUp',altKey:true}),
                    shifted:commands.viewportNavigationForEvent({...arrow,shiftKey:true}),
                    ctrl:commands.viewportNavigationForEvent({...arrow,ctrlKey:true}),
                    meta:commands.viewportNavigationForEvent({...arrow,metaKey:true}),
                    composing:commands.viewportNavigationForEvent({...arrow,isComposing:true}),
                    altGraph:commands.viewportNavigationForEvent({...arrow,
                        getModifierState:key=>key==='AltGraph'})
                };
                return {matched,
                    lockCodes:commands.editorLockCodes(),
                    navigation,
                    mac:commands.resolveShortcutPlatform({navigatorPlatform:'MacIntel'}),
                    win:commands.resolveShortcutPlatform({navigatorPlatform:'Win32'}),
                    linux:commands.resolveShortcutPlatform({navigatorPlatform:'Linux x86_64'}),
                    search:commands.editorShortcutSearchTerms('appearance','mac')};
            }''')
            assert result['mac'] == 'mac'
            assert result['win'] == 'windows'
            assert result['linux'] == 'linux'
            assert set(result['lockCodes']) == {'KeyW', 'KeyN', 'KeyS', 'KeyB',
                                                'KeyP', 'KeyA', 'KeyE', 'KeyO',
                                                'ArrowLeft', 'ArrowRight'}
            assert result['navigation'] == {
                'left': {'kind': 'camera', 'direction': 'left'},
                'right': {'kind': 'camera', 'direction': 'right'},
                'up': {'kind': 'camera', 'direction': 'up'},
                'down': {'kind': 'camera', 'direction': 'down'},
                'previous': {'kind': 'frame', 'delta': -1},
                'next': {'kind': 'frame', 'delta': 1},
                'altUp': None, 'shifted': None, 'ctrl': None, 'meta': None,
                'composing': None, 'altGraph': None,
            }
            assert 'Command Shift P' in result['search']
            for platform, cases in result['matched'].items():
                assert len(cases) == 10
                for case in cases:
                    assert case['positive'] == case['id']
                    assert case['wrongShift'] != case['id']
                    assert case['wrongModifier'] is None
                    assert case['both'] is None
                    assert case['alt'] is None
                    assert case['composing'] is None
                    assert case['altGraph'] is None
                    assert case['fallback'] == case['id']
                    assert case['unidentified'] == case['id']
                    assert case['aria'].startswith('Meta+' if platform == 'mac' else 'Control+')
            browser.close()
    finally:
        editor.close()
