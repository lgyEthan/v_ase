"""Human controls for scoped trajectory edits, cancellation and complete undo."""
import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms
from playwright.sync_api import sync_playwright
from v_ase.session import sessions
from v_ase.viewer import view, find_free_port


@pytest.fixture
def edit_page():
    frames = [Atoms(symbols, positions=[[i, 0, 0] for i in range(len(Atoms(symbols)))],
                    cell=np.array([[4, 0, 0], [-1, 5, 0], [0, -1, 6]]) * scale, pbc=True)
              for symbols, scale in [('HOC', 1), ('LiNaF', 2), ('He', 3)]]
    for atoms in frames:
        atoms.set_constraint(FixAtoms(indices=[0]))
        atoms.set_array('existence', np.arange(len(atoms), dtype=float) + .2)
    editor = view(frames, notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 960})
            page.add_init_script("Object.defineProperty(navigator,'platform',{value:'Win32'});Object.defineProperty(navigator,'userAgentData',{value:{platform:'Windows'}});")
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            yield page, sessions[editor.session_id], frames
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('scope', ['current', 'all'])
def test_delete_dialog_cancel_scope_and_keyboard_undo(edit_page, scope):
    page, session, before = edit_page
    page.evaluate("window.__ASE_APP__.applySelectionAction({references:[1,2],origin:'semantic'});window.__ASE_APP__.renderer.domElement.focus()")
    page.keyboard.press('Delete')
    page.locator('#delete-frames-current').wait_for()
    page.keyboard.press('Escape')
    page.wait_for_function('window.__ASE_APP__.deletionPending === false')
    assert [len(a) for a in session.trajectory_frames] == [3, 3, 1]
    assert not session.history
    page.evaluate('window.__ASE_APP__.renderer.domElement.focus()')
    page.keyboard.press('Delete')
    page.locator(f'#delete-frames-{scope}').click()
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions.length===1')
    assert [len(a) for a in session.trajectory_frames] == ([1, 1, 1] if scope == 'all' else [1, 3, 1])
    # Focus is still on a button after confirming: structural Undo must work.
    page.keyboard.press('Control+z')
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions.length===3')
    assert all(np.array_equal(a.positions, b.positions) for a, b in zip(session.trajectory_frames, before))
    assert [a.arrays['existence'].tolist() for a in session.trajectory_frames] == [a.arrays['existence'].tolist() for a in before]
    page.keyboard.press('Control+Shift+z')
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions.length===1')
    assert [len(a) for a in session.trajectory_frames] == ([1, 1, 1] if scope == 'all' else [1, 3, 1])


def test_physical_translation_ui_uses_fractional_cells_and_no_optimizer(edit_page):
    page, session, before = edit_page
    page.evaluate("window.__ASE_APP__.openEditorRoute('build-rigid');window.__ASE_APP__.applySelectionAction({references:[0,2],origin:'semantic'})")
    assert page.locator('#rigid-translation-controls').is_visible()
    assert not page.locator('#registry-translation-space').is_visible()
    page.locator('#rigid-translation-target').select_option('selected')
    page.locator('#rigid-translation-coordinates').select_option('fractional')
    page.locator('#rigid-translation-frames').select_option('all')
    for axis, value in zip('xyz', ['.2', '-.1', '.3']):
        page.locator(f'#rigid-translation-{axis}').fill(value)
    page.locator('#btn-rigid-translate').click()
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions[0][0] > .8')
    for actual, original in zip(session.trajectory_frames, before):
        expected = original.positions.copy()
        indices = [i for i in [0, 2] if i < len(original)]
        expected[indices] += np.array([.2, -.1, .3]) @ original.cell.array
        assert np.allclose(actual.positions, expected)
        assert np.array_equal(actual.cell, original.cell)
    assert not session.is_relaxing and not session.registry_relaxation
    page.keyboard.press('Control+z')
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions[0][0]===0')
    assert all(np.array_equal(a.positions, b.positions) for a, b in zip(session.trajectory_frames, before))
    page.locator('#rigid-translation-frames').select_option('current')
    page.locator('#rigid-translation-coordinates').select_option('cartesian')
    page.locator('#btn-rigid-translate').click()
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions[0][0]===.2')
    assert np.array_equal(session.trajectory_frames[1].positions, before[1].positions)
    assert np.array_equal(session.trajectory_frames[2].positions, before[2].positions)
