"""Live label appearance, merging and a single undo for the initial split."""
import pytest
from tests.test_browser_camera_property_persistence import page
from tests.ui_navigation import open_editor_route


def select(page, indices):
    page.evaluate('''indices => {const a=window.__ASE_APP__;a.state.selected=new Set(indices);
        a.updateSelectionVisuals();a.updateUI();}''', indices)


@pytest.mark.parametrize('mode', ['view', 'edit'])
def test_live_label_color_radius_and_undo(page, mode):
    page.evaluate('mode => window.__ASE_APP__.aiApply({mode})', mode)
    open_editor_route(page, 'appearance')
    select(page, [0])
    before = page.evaluate('''() => {const a=window.__ASE_APP__;return {
        labels:[...a.state.atoms.symbols],radius:a.state.display.labelRadii.H,display:structuredClone(a.state.display)};}''')
    assert page.locator('#appearance-material').count() == 0
    assert page.locator('#btn-apply-selected-label').count() == 0
    page.fill('#selected-atom-color', '#33aa77')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'H_2'
    assert page.evaluate('window.__ASE_APP__.renderer.displayOptions.labelColors.H_2') == '#33aa77'
    assert page.input_value('[data-atom-label="H_2"][data-appearance-field="color"]') == '#33aa77'
    page.evaluate('window.__ASE_APP__.performUndo()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == before['labels']
    assert page.evaluate('window.__ASE_APP__.state.display.labelColors.H_2 || null') is None
    page.evaluate('window.__ASE_APP__.performRedo()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'H_2'
    select(page, [0])
    # After a new selection gesture a separate label is allocated, and its actual
    # radius (not a hidden index multiplier) is immediately reflected in the table.
    page.fill('#selected-atom-radius-scale-number', '2')
    page.locator('#selected-atom-radius-scale-number').press('Tab')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    state = page.evaluate('''() => {const a=window.__ASE_APP__,label=a.state.atoms.symbols[0];
        return {label,radius:a.state.display.labelRadii[label],override:a.state.display.atomRadiusScales?.[0]};}''')
    assert state['radius'] == pytest.approx(before['radius'] * 2)
    assert state.get('override') is None
    assert float(page.input_value(f'[data-atom-label="{state["label"]}"][data-appearance-field="radius"]')) == pytest.approx(state['radius'], abs=.001)


def test_existing_label_confirmation_inherits_every_setting(page):
    page.evaluate("window.__ASE_APP__.aiApply({mode:'edit'})")
    open_editor_route(page, 'appearance')
    page.evaluate('''() => {const a=window.__ASE_APP__;Object.assign(a.state.display.labelRadii,{C:1.8});
        Object.assign(a.state.display.labelColors,{C:'#123456'});Object.assign(a.state.display.labelOpacities,{C:.4});
        Object.assign(a.state.display.labelMaterials,{C:'metal'});a.renderAppearanceRows();}''')
    select(page, [0])
    page.fill('#selected-atom-label', 'C')
    page.locator('#selected-atom-label').press('Enter')
    page.click('#modal-confirm-action')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    result = page.evaluate('''() => {const a=window.__ASE_APP__;return {label:a.state.atoms.symbols[0],
        element:a.state.atoms.chemical_symbols[0],color:a.atomManualColor(0),material:a.atomMaterialPreset(0),
        opacity:a.atomManualOpacity(0),radius:a.state.display.labelRadii.C};}''')
    assert result == dict(label='C', element='H', color='#123456', material='metal', opacity=.4, radius=1.8)
    page.evaluate('window.__ASE_APP__.performUndo()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'H'


def test_cancel_label_draft_and_merge_then_edit_do_not_change_target_atoms(page):
    open_editor_route(page, 'appearance')
    select(page, [0])
    page.fill('#selected-atom-label', 'abandoned')
    page.locator('#selected-atom-label').press('Escape')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'H'
    page.fill('#selected-atom-label', 'C')
    page.locator('#selected-atom-label').press('Enter')
    page.click('#modal-cancel-confirm')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'H'
    page.fill('#selected-atom-label', 'C')
    page.locator('#selected-atom-label').press('Enter')
    page.click('#modal-confirm-action')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    inherited = page.evaluate('window.__ASE_APP__.atomManualColor(2)')
    page.fill('#selected-atom-color', '#11cc77')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['H_2', 'O', 'C']
    assert page.evaluate('window.__ASE_APP__.atomManualColor(2)') == inherited
    page.evaluate('window.__ASE_APP__.performUndo()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'C'


def test_multiple_elements_split_together_with_collision_and_one_undo(page):
    page.evaluate("window.__ASE_APP__.aiApply({mode:'edit'})")
    open_editor_route(page, 'appearance')
    select(page, [2])
    page.fill('#selected-atom-label','H_2')
    page.locator('#selected-atom-label').press('Tab')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    select(page, [0, 1])
    page.select_option('#selected-atom-material','rubber')
    page.evaluate('window.__ASE_APP__.settleScientificMutations()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['H_3','O_2','H_2']
    assert page.evaluate('window.__ASE_APP__.renderer.displayOptions.labelMaterials.O_2') == 'rubber'
    page.evaluate('window.__ASE_APP__.performUndo()')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['H','O','H_2']
    page.evaluate('window.__ASE_APP__.performRedo()')
    page.evaluate('window.__ASE_APP__.loadFrame(1)')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['H_3']
    page.evaluate('window.__ASE_APP__.loadFrame(2)')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['H_3','O_2','H_2']
    assert page.evaluate('window.__ASE_APP__.state.atoms.chemical_symbols') == ['C','O','H']
