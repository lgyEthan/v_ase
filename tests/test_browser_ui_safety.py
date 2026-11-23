"""A form interaction must not leave destructive keys on the scientific canvas."""
import json

import pytest
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, FixedPlane
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view


@pytest.fixture
def safety_page():
    atoms = Atoms('OHH', positions=[[0, 0, 0], [.95, 0, 0], [-.2, .9, 0]], cell=[6, 6, 6])
    atoms.set_constraint([FixAtoms(indices=[0]), FixedLine(1, [0, 1, 0]), FixedPlane(2, [0, 0, 1])])
    editor = view(atoms, notebook=True, block=False, viz_only=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            p = browser.new_page(viewport={'width': 1440, 'height': 960})
            p.goto(editor.url)
            p.wait_for_function('window.__ASE_APP__?.collaborationReady')
            p.evaluate("window.__ASE_APP__.openEditorRoute('appearance')")
            yield p
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('mode', ['view', 'edit'])
@pytest.mark.parametrize('field', ['select', 'visible'])
def test_label_checkbox_keeps_focus_and_blocks_canvas_delete(safety_page, mode, field):
    p = safety_page
    p.evaluate('async m=>await window.__ASE_APP__.aiApply({mode:m})', mode)
    p.evaluate("window.__ASE_APP__.openEditorRoute('appearance')")
    before = p.evaluate('JSON.stringify({p:window.__ASE_APP__.state.atoms.positions,c:window.__ASE_APP__.state.atoms.constraints})')
    selector = f'[data-appearance-field="{field}"][data-atom-label="H"]'
    p.locator('#app-viewport canvas').focus()
    # HTMLElement.click() does not focus checkboxes. This was the native smoke
    # test's panel activation path, and some platform click paths also retain
    # the previous focus. The control must claim focus before refreshing rows.
    p.locator(selector).evaluate('e=>e.click()')
    assert p.locator(selector).evaluate('e=>e===document.activeElement')
    if field == 'select':
        assert p.evaluate('window.__ASE_APP__.state.selected.size') == 2
    p.evaluate('''()=>{const a=window.__ASE_APP__;window.__deleteCalls=0;
        const original=a.deleteSelection;a.deleteSelection=function(...args){window.__deleteCalls++;return original.apply(this,args);};}''')
    p.keyboard.press('Backspace')
    p.keyboard.press('Delete')
    assert p.evaluate('window.__deleteCalls') == 0
    assert p.evaluate('JSON.stringify({p:window.__ASE_APP__.state.atoms.positions,c:window.__ASE_APP__.state.atoms.constraints})') == before
    assert p.locator(selector).evaluate('e=>e===document.activeElement')
    if field == 'select':
        p.keyboard.press('Space')
        assert p.evaluate('window.__ASE_APP__.state.selected.size') == 0
        assert not p.locator(selector).is_checked()
        assert p.locator(selector).evaluate('e=>e===document.activeElement')


def test_deliberate_viewport_delete_and_undo_preserve_constraints(safety_page):
    p = safety_page
    before = p.evaluate('JSON.stringify({p:window.__ASE_APP__.state.atoms.positions,c:window.__ASE_APP__.state.atoms.constraints})')
    p.locator('[data-appearance-field="select"][data-atom-label="H"]').click()
    p.locator('#app-viewport canvas').focus()
    p.keyboard.press('Delete')
    p.wait_for_function('window.__ASE_APP__.state.atoms.positions.length===1')
    p.evaluate('async()=>await window.__ASE_APP__.performUndo()')
    assert p.evaluate('JSON.stringify({p:window.__ASE_APP__.state.atoms.positions,c:window.__ASE_APP__.state.atoms.constraints})') == before


def test_background_refresh_keeps_label_draft_and_caret(safety_page):
    p = safety_page
    field = p.locator('[data-appearance-field="label"][data-atom-label="H"]')
    field.fill('H_surface')
    field.evaluate("e=>e.setSelectionRange(2,5,'forward')")
    before = p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms)')
    p.evaluate('async()=>await window.__ASE_APP__.refresh()')
    assert field.input_value() == 'H_surface'
    assert field.evaluate('e=>e===document.activeElement')
    assert field.evaluate('e=>[e.selectionStart,e.selectionEnd,e.selectionDirection]') == [2, 5, 'forward']
    # A read must neither commit the draft nor change scientific data.
    assert p.evaluate('JSON.stringify(window.__ASE_APP__.state.atoms)') == before
    field.press('Enter')
    p.wait_for_function('window.__ASE_APP__.state.atoms.symbols[1]==="H_surface"')


def test_authoritative_label_change_does_not_restore_an_old_draft(safety_page):
    p = safety_page
    p.locator('[data-appearance-field="label"][data-atom-label="H"]').fill('H_uncommitted')
    p.evaluate("async()=>await window.__ASE_APP__.renameAtomLabel('H','H_committed',null,[1,2])")
    assert p.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['O', 'H_committed', 'H_committed']
    assert p.locator('[data-appearance-field="label"][data-atom-label="H_committed"]').input_value() == 'H_committed'


def test_draft_is_not_rebound_to_changed_atom_membership(safety_page):
    p = safety_page
    p.locator('[data-appearance-field="label"][data-atom-label="H"]').fill('H_uncommitted')
    p.evaluate('''async()=>{const a=window.__ASE_APP__;a.setAtomsData(await a.api.deleteAtoms([2]));}''')
    assert p.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['O', 'H']
    assert p.locator('[data-appearance-field="label"][data-atom-label="H"]').input_value() == 'H'

