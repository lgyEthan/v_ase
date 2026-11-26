"""Editing trajectory labels and deleting frames keep per-frame data aligned."""

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from playwright.sync_api import sync_playwright

from tests.ui_navigation import open_editor_route
from v_ase.io import atom_labels, set_atom_labels
from v_ase.project import read_project_archive, write_project_archive
from v_ase.server import sessions
from v_ase.session import EditorSession
from v_ase.viewer import find_free_port, view


def frame(elements, labels, energy):
    atoms = Atoms(elements, positions=[[1.7 * i, 0, 0] for i in range(len(labels))])
    set_atom_labels(atoms, labels)
    atoms.new_array('sample_index', np.arange(len(atoms)) + int(100 * energy))
    atoms.calc = SinglePointCalculator(atoms, energy=energy, forces=np.full((len(atoms), 3), energy / 10))
    return atoms


def load_project(page, source):
    page.evaluate("""name => window.__ASE_APP__.loadStructureFile(
        {name}, '', ':', 'edit', {path:name, throwErrors:true})""", source.name)
    open_editor_route(page, 'appearance')


@pytest.fixture
def project_page(tmp_path):
    seed = frame('CuO', ['Cu', 'O'], .1)
    editor = view(seed, notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    sessions[editor.session_id].config['launch_directory'] = str(tmp_path)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1460, 'height': 920})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            yield page
            browser.close()
    finally:
        editor.close()


def select_first(page):
    page.evaluate("""() => {const app = window.__ASE_APP__;
        app.state.selected = new Set([0]); app.updateSelectionVisuals(); app.updateUI();}""")


def expect_scope(page, allowed, reason=''):
    page.wait_for_function("""allowed => {
        const field = document.getElementById('selected-frame-scope-value');
        return !field.closest('[hidden]') && !field.disabled && field.options[0].disabled !== allowed;
    }""", arg=allowed)
    if reason:
        assert reason in page.locator('#selected-frame-scope-reason').inner_text()


def delete_current(page):
    page.locator('#trajectory-panel').click(button='right')
    page.get_by_role('menuitem', name='Delete current frame').click()
    page.get_by_role('button', name='Delete frame', exact=True).click()
    page.wait_for_function("document.querySelector('#busy-overlay').classList.contains('hidden')")


def test_frame_removal_rechecks_scope_and_current_only_labels_round_trip(project_page, tmp_path):
    page = project_page
    frames = [
        frame('CuCuO', ['Cu', 'Cu_2', 'O'], 1.0),
        frame('CuO', ['Cu', 'O'], 2.0),
        frame('CuCuN', ['Cu', 'Cu_2', 'N'], 3.0),
        frame('CuCuO', ['Cu_other', 'Cu_2', 'O'], 4.0),
        frame('CuCuO', ['Cu', 'Cu_another', 'O'], 5.0),
    ]
    source = tmp_path / 'mixed.vase'
    seed = EditorSession('mixed', frames[0], frames[0], trajectory_frames=frames)
    write_project_archive(source, seed, {'display': {'atomColors': {'0': '#1a2b3c'},
        'atomMaterials': {'0': 'metal'},
        'atomBondStyles': {'0': {'opacity': .4}}, 'energyOverlay': {'visible': True}}})
    load_project(page, source)
    select_first(page)
    expect_scope(page, False, 'different atom count')

    page.evaluate('window.__ASE_APP__.loadFrame(1)')
    for reason in ('different element composition', 'different labels'):
        delete_current(page)
        expect_scope(page, False, reason)
    delete_current(page)
    expect_scope(page, True)
    assert page.locator('#selected-frame-scope-value').input_value() == 'all'
    assert page.evaluate('window.__ASE_APP__.state.atoms.metadata.energy') == 5.0
    page.wait_for_function("document.querySelector('.trajectory-energy-overlay')?.dataset.frame === '1'")
    page.evaluate('window.__ASE_APP__.performUndo()')
    expect_scope(page, False, 'different labels')
    page.evaluate('window.__ASE_APP__.performRedo()')
    expect_scope(page, True)

    page.locator('#selected-frame-scope-value').select_option('current')
    page.evaluate('window.__ASE_APP__.calculateRdf()')
    assert page.evaluate('Boolean(window.__ASE_APP__.state.rdfResult)')
    label = page.locator('#selected-atom-label')
    label.fill('Cu_sub')
    label.press('Enter')
    page.get_by_role('button', name='Cancel', exact=True).click()
    page.wait_for_function('!window.__ASE_APP__.selectedAppearanceEditor.labelPending')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'Cu'
    assert page.evaluate('Boolean(window.__ASE_APP__.state.rdfResult)')
    label.fill('Cu_sub')
    label.press('Enter')
    page.get_by_role('button', name='Apply to this frame').click()
    page.wait_for_function("""() => !window.__ASE_APP__.selectedAppearanceEditor.labelPending
        && window.__ASE_APP__.state.atoms.symbols[0] === 'Cu_sub'""")
    expect_scope(page, False, 'different labels')
    assert not page.evaluate('Boolean(window.__ASE_APP__.state.rdfResult)')
    page.locator('#selected-atom-color').fill('#cc3333')
    assert page.evaluate('window.__ASE_APP__.renderer.atomVisualColor(0)') == '#cc3333'
    page.evaluate('window.__ASE_APP__.loadFrame(0)')
    assert page.evaluate('window.__ASE_APP__.renderer.atomVisualColor(0)') == '#1a2b3c'
    page.evaluate('window.__ASE_APP__.loadFrame(1)')
    assert page.evaluate('window.__ASE_APP__.renderer.atomVisualColor(0)') == '#cc3333'
    assert page.evaluate('window.__ASE_APP__.state.atoms.forces[0]') == [.5, .5, .5]
    page.evaluate("window.__ASE_APP__.aiApply({mode:'view'})")
    page.evaluate("window.__ASE_APP__.aiApply({mode:'edit'})")
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols[0]') == 'Cu_sub'
    page.evaluate('window.__ASE_APP__.loadFrame(0)')
    assert page.evaluate('window.__ASE_APP__.renderer.atomMaterialPreset(0)') == 'metal'
    page.evaluate('window.__ASE_APP__.loadFrame(1)')
    assert page.evaluate('window.__ASE_APP__.saveDocument()')

    reopened = read_project_archive(source)
    assert [atom_labels(atoms) for atoms in reopened.frames] == [
        ['Cu', 'Cu_2', 'O'], ['Cu_sub', 'Cu_another', 'O']]
    assert [atoms.get_potential_energy() for atoms in reopened.frames] == [1.0, 5.0]
    assert reopened.frames[1].arrays['sample_index'].tolist() == [500, 501, 502]
    assert reopened.frames[1].get_forces()[0].tolist() == [.5, .5, .5]
    assert reopened.settings['display']['selectedAppearanceFrameScope'] == 'current'
    load_project(page, source)
    select_first(page)
    expect_scope(page, False, 'different labels')
    delete_current(page)
    assert page.locator('#selected-frame-scope').is_hidden()
    assert page.evaluate('window.__ASE_APP__.state.atoms.metadata.energy') == 1.0
    assert page.evaluate('window.__ASE_APP__.currentTrajectoryFrame()') == 0


def test_label_row_rename_merge_and_delete_follow_names_across_different_indices(project_page, tmp_path):
    page = project_page
    frames = [frame('CuCuO', ['Cu', 'Cu_2', 'O'], 1.0),
              frame('CuO', ['Cu_2', 'O'], 2.0), frame('Cu', ['Cu'], 3.0)]
    frames[-1].set_cell([8, 8, 8])
    frames[-1].pbc = True
    source = tmp_path / 'rows.vase'
    seed = EditorSession('rows', frames[0], frames[0], trajectory_frames=frames)
    write_project_archive(source, seed, {'display': {
        'retainedLabels': ['Unused'], 'labelColors': {'Cu': '#ab3422', 'Cu_2': '#dadada'},
        'pairwiseBondRanges': {'Cu_2-O': {'enabled': True, 'max': 2.1}},
        'polyhedraRules': [{'centers': {'labels': ['Cu_2']}, 'ligands': {'elements': ['O']}}]}})
    load_project(page, source)
    open_editor_route(page, 'rdf')
    page.locator('#rdf-pair-mode').select_option('all')
    page.locator('#btn-rdf-calculate').click()
    page.locator('#btn-analysis-float').click()
    page.locator('#btn-analysis-appearance').click()
    page.locator('#graph-series').select_option('Cu_2|O')
    page.locator('#energy-line-color').fill('#8b205a')
    limits = page.locator('#energy-graph-axes')
    limits.locator('xpath=..').locator('summary').click()
    limits.get_by_role('spinbutton', name='X minimum', exact=True).fill('1.5')
    graph = page.locator('#analysis-floating #rdf-plot')
    page.wait_for_function("document.getElementById('rdf-plot')._fullLayout.xaxis.range[0] === 1.5")
    current_curve = graph.evaluate("plot => plot.data.find(trace => trace.name === 'Cu_2 - O').y")
    fetches = []
    page.on('request', lambda request: fetches.append(request.url) if '/api/analysis/rdf/' in request.url else None)
    open_editor_route(page, 'appearance')
    row_label = lambda name: page.locator(f'input[data-atom-label="{name}"][data-appearance-field="label"]')
    row_label('Cu_2').fill('Cu_sub')
    row_label('Cu_2').press('Enter')
    row_label('Cu_sub').wait_for()
    page.wait_for_function("window.__ASE_APP__.state.atoms.symbols[1] === 'Cu_sub'")
    assert page.evaluate("window.__ASE_APP__.state.display.labelColors.Cu_sub") == '#dadada'
    assert page.evaluate("window.__ASE_APP__.state.display.pairwiseBondRanges['Cu_sub-O'].max") == pytest.approx(2.1)
    assert page.evaluate("window.__ASE_APP__.state.display.polyhedraRules[0].centers.labels") == ['Cu_sub']
    graph.get_by_text('Cu_sub - O', exact=True).wait_for()
    assert graph.evaluate("plot => plot.data.find(trace => trace.name === 'Cu_sub - O').y") == current_curve
    assert graph.evaluate("plot => plot.data.find(trace => trace.name === 'Cu_sub - O').line.color") == '#8b205a'
    assert graph.evaluate('plot => plot._fullLayout.xaxis.range[0]') == 1.5
    assert page.locator('#analysis-drawer').is_hidden()
    assert not fetches
    page.locator('#btn-analysis-appearance').click()
    assert page.locator('#graph-series').input_value() == 'Cu_sub|O'
    page.locator('#btn-rdf-calculate').click()
    page.wait_for_function("!document.body.dataset.busy && document.getElementById('rdf-status').dataset.state === 'ready'")
    assert fetches
    assert graph.evaluate('plot => plot._fullLayout.xaxis.range[0]') == 1.5
    open_editor_route(page, 'appearance')
    page.evaluate('window.__ASE_APP__.loadFrame(1)')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['Cu_sub', 'O']

    page.evaluate('window.__ASE_APP__.loadFrame(2)')
    for name in ['Unused', 'Cu_sub']:
        details = row_label(name).locator('xpath=../..')
        details.evaluate('row => { row.open = true; }')
        if name == 'Cu_sub':
            assert details.get_by_text('Used in other frames').is_visible()
        details.get_by_role('button', name='Delete label').click()
        if name == 'Cu_sub':
            page.locator('#label-delete-target').fill('Cu')
            page.locator('#label-delete-confirm').click()
        row_label(name).wait_for(state='detached')
    page.evaluate('window.__ASE_APP__.loadFrame(1)')
    assert page.evaluate('window.__ASE_APP__.state.atoms.symbols') == ['Cu', 'O']
    assert page.evaluate('window.__ASE_APP__.state.display.labelColors.Cu') == '#ab3422'
