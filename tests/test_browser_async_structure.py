"""Delayed structure reads must not roll back newer edits or optimizer events."""
import threading

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule
from ase.calculators.calculator import Calculator, all_changes
from ase.constraints import FixAtoms
from playwright.sync_api import sync_playwright

from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


@pytest.fixture
def live_document():
    atoms = molecule('H2O')
    atoms.positions += [3, 3, 4]
    atoms = Atoms('Cu', positions=[[1, 1, 1]]) + atoms
    atoms.set_cell([8, 8, 12])
    atoms.pbc = [True, True, False]
    atoms.set_constraint(FixAtoms(indices=[0]))
    port = find_free_port()
    editor = view(atoms, notebook=True, block=False, viz_only=False,
                  port=port, close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            page.evaluate('async () => await window.__ASE_APP__.ready')
            yield page, sessions[editor.session_id]
            browser.close()
    finally:
        editor.close()


def defer_structure_read(page):
    page.evaluate('''async () => {
        const app=window.__ASE_APP__;
        const snapshot=await app.api.fetchAtoms();
        const fetch=app.api.fetchAtoms.bind(app.api);
        let release;
        const gate=new Promise(resolve=>release=resolve);
        app.api.fetchAtoms=async()=>{await gate;return snapshot;};
        window.delayedStructureRead=app.refresh();
        window.releaseStructureRead=async()=>{
            release();await window.delayedStructureRead;app.api.fetchAtoms=fetch;
        };
    }''')


@pytest.mark.parametrize('release_after', ['preview', 'commit', 'cancel'])
def test_delayed_structure_read_cannot_discard_molecule_rotation(live_document, release_after):
    page, backend = live_document
    original = backend.working_atoms.positions.copy()
    page.evaluate("async () => await window.v_aseAI.apply({selection:{indices:[1,2,3]}})")
    defer_structure_read(page)
    page.locator('#app-viewport canvas').focus()
    page.keyboard.press('r')
    page.keyboard.press('z')
    page.keyboard.type('30')
    preview = page.evaluate('() => window.__ASE_APP__.currentPositionsFromScene()')
    assert not np.allclose(preview[1:], original[1:])
    if release_after == 'commit':
        page.keyboard.press('Enter')
        page.evaluate('async () => await window.__ASE_APP__.pendingApply')
    elif release_after == 'cancel':
        page.keyboard.press('Escape')
    page.evaluate('async () => await window.releaseStructureRead()')
    restored = page.evaluate('() => window.__ASE_APP__.currentPositionsFromScene()')
    expected = original if release_after == 'cancel' else preview
    np.testing.assert_allclose(restored, expected, atol=1e-12)
    if release_after == 'preview':
        page.keyboard.press('Enter')
        page.evaluate('async () => await window.__ASE_APP__.pendingApply')
    np.testing.assert_allclose(backend.working_atoms.positions, expected, atol=1e-12)
    np.testing.assert_array_equal(backend.working_atoms.positions[0], original[0])
    original_distances = np.linalg.norm(original[1:, None] - original[None, 1:], axis=2)
    final = backend.working_atoms.positions[1:]
    np.testing.assert_allclose(np.linalg.norm(final[:, None] - final[None, :], axis=2), original_distances)


@pytest.mark.parametrize('display', [
    {'atomDisplayMode': '2d'},
    {'labelOpacities': {'H': 0.5}},
])
@pytest.mark.parametrize('finish', ['commit', 'cancel'])
def test_display_rebuild_preserves_rotation_until_commit(live_document, display, finish):
    page, backend = live_document
    original = backend.working_atoms.positions.copy()
    page.evaluate("async () => await window.v_aseAI.apply({selection:{indices:[1,2,3]}})")
    page.locator('#app-viewport canvas').focus()
    page.keyboard.press('r')
    page.keyboard.press('z')
    page.keyboard.type('30')
    preview = page.evaluate('() => window.__ASE_APP__.currentPositionsFromScene()')
    assert not np.allclose(preview, original)
    page.evaluate('(display) => window.__ASE_APP__.applyDesignSettings({display})', display)
    np.testing.assert_allclose(
        page.evaluate('() => window.__ASE_APP__.currentPositionsFromScene()'), preview, atol=1e-12)
    np.testing.assert_array_equal(backend.working_atoms.positions, original)
    if finish == 'commit':
        page.keyboard.press('Enter')
        page.evaluate('async () => await window.__ASE_APP__.pendingApply')
    else:
        page.keyboard.press('Escape')
    expected = preview if finish == 'commit' else original
    np.testing.assert_allclose(backend.working_atoms.positions, expected, atol=1e-12)
    np.testing.assert_allclose(
        page.evaluate('() => window.__ASE_APP__.currentPositionsFromScene()'), expected, atol=1e-12)


class PausedCalculator(Calculator):
    implemented_properties = ['energy', 'forces']

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def calculate(self, atoms=None, properties=None, system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        self.started.set()
        if not self.release.wait(10):
            raise RuntimeError('The test did not release its calculator')
        self.results = {'energy': 0., 'forces': np.zeros((len(atoms), 3))}


@pytest.mark.parametrize('completed_first_run', [False, True])
def test_delayed_structure_read_cannot_restart_finished_registry_optimization(live_document, completed_first_run):
    page, backend = live_document
    page.evaluate('''async () => await window.v_aseAI.apply({operation:{
        name:'start-registry-relaxation',indices:[1,2,3],hkl:[0,0,1]}})''')
    if completed_first_run:
        page.evaluate('async () => await window.__ASE_APP__.runRegistryRelaxation({fmax:1000,steps:2})')
        page.wait_for_function('window.__ASE_APP__.state.registryRelaxation?.status === "converged"')
        page.evaluate('''() => {
            const app = window.__ASE_APP__;
            const send = app.api.runRegistryRelaxation.bind(app.api);
            app.api.runRegistryRelaxation = async (payload) => {
                const previous = app.state.registryRelaxation;
                await app.refresh();
                const refreshed = app.state.registryRelaxation;
                window.receivedPreviousRun = refreshed !== previous && refreshed.run_id === previous.run_id;
                return await send(payload);
            };
        }''')
    calculator = PausedCalculator()
    backend.registry_relaxation.baseline_atoms.calc = calculator
    try:
        page.evaluate('''() => {window.registryRun=window.__ASE_APP__.runRegistryRelaxation({fmax:1000,steps:2});}''')
        assert calculator.started.wait(5)
        page.evaluate('async () => await window.registryRun')
        if completed_first_run:
            assert page.evaluate('window.receivedPreviousRun')
        assert page.evaluate('window.__ASE_APP__.state.registryRelaxation.is_relaxing')
        defer_structure_read(page)
        calculator.release.set()
        page.wait_for_function('window.__ASE_APP__.state.registryRelaxation?.status === "converged"')
        page.evaluate('async () => await window.releaseStructureRead()')
        result = page.evaluate('() => window.__ASE_APP__.state.registryRelaxation')
        assert result['is_relaxing'] is False
        assert result['status'] == 'converged'
        assert backend.registry_relaxation.is_relaxing is False
    finally:
        calculator.release.set()


def test_registry_completion_before_run_response_remains_finished(live_document):
    page, backend = live_document
    page.evaluate('''async () => await window.v_aseAI.apply({operation:{
        name:'start-registry-relaxation',indices:[1,2,3],hkl:[0,0,1]}})''')
    calculator = PausedCalculator()
    backend.registry_relaxation.baseline_atoms.calc = calculator
    page.evaluate('''() => {
        const app=window.__ASE_APP__;
        const run=app.api.runRegistryRelaxation.bind(app.api);
        let release;
        const gate=new Promise(resolve=>release=resolve);
        app.api.runRegistryRelaxation=async payload=>{
            const summary=await run(payload);
            window.registryStartResponse=summary;
            await gate;
            return summary;
        };
        window.releaseRegistryStart=release;
        window.registryRun=app.runRegistryRelaxation({fmax:1000,steps:2});
    }''')
    try:
        assert calculator.started.wait(5)
        page.wait_for_function('window.registryStartResponse?.is_relaxing')
        calculator.release.set()
        page.wait_for_function('window.__ASE_APP__.state.registryRelaxation?.status === "converged"')
        page.evaluate('async () => {window.releaseRegistryStart();await window.registryRun;}')
        assert page.evaluate('window.__ASE_APP__.state.registryRelaxation.is_relaxing') is False
        assert page.evaluate('window.__ASE_APP__.state.relaxTrajectory.finished') is True
    finally:
        calculator.release.set()


@pytest.mark.parametrize('kind', ['add-atoms', 'registry', 'relaxation'])
def test_cleared_trajectory_rejects_queued_optimizer_events(live_document, kind):
    page, backend = live_document
    if kind == 'add-atoms':
        page.evaluate('''async () => await window.v_aseAI.apply({operation:{
            name:'scatter-atoms',entries:[{element:'H',label:'H_added',count:2}],
            regions:[{id:'test',role:'allow',bounds:[0,.5,0,.5,0,.5]}],
            seed:42,freezeExisting:true}})''')
    elif kind == 'registry':
        page.evaluate('''async () => await window.v_aseAI.apply({operation:{
            name:'start-registry-relaxation',indices:[1,2,3],hkl:[0,0,1]}})''')
    original = backend.working_atoms.positions.copy()
    page.evaluate('''() => {
        const app=window.__ASE_APP__, deliver=app.ws.onmessage;
        window.bufferedOptimizerEvents=[];
        app.ws.onmessage=event=>{
            if(/^(add_atoms_|registry_)?relax_(step|finished)$/.test(JSON.parse(event.data).type)) {
                window.bufferedOptimizerEvents.push(event);
            } else deliver(event);
        };
        window.deliverBufferedOptimizerEvents=()=>{
            app.ws.onmessage=deliver;
            for(const event of window.bufferedOptimizerEvents) deliver(event);
        };
    }''')
    operation = 'run-registry-relaxation' if kind == 'registry' else 'start-relaxation'
    page.evaluate('''async (name) => await window.v_aseAI.apply({operation:{name,fmax:.001,steps:3}})''', operation)
    page.wait_for_function('''window.bufferedOptimizerEvents.some(event=>
        JSON.parse(event.data).type.endsWith('relax_finished'))''')
    page.evaluate('''async () => await window.v_aseAI.apply({operation:{
        name:'clear-relaxation-trajectory',retain:'initial'}})''')
    page.evaluate('() => window.deliverBufferedOptimizerEvents()')
    state = page.evaluate('''() => ({frames:window.__ASE_APP__.state.relaxTrajectory.frames,
        positions:window.__ASE_APP__.state.atoms.positions})''')
    assert state['frames'] == []
    np.testing.assert_array_equal(state['positions'], original)
    np.testing.assert_array_equal(backend.working_atoms.positions, original)
    page.evaluate('''async (name) => await window.v_aseAI.apply({operation:{name,fmax:.001,steps:3}})''', operation)
    page.wait_for_function('window.__ASE_APP__.state.relaxTrajectory.finished === true')
    assert page.evaluate('window.__ASE_APP__.state.relaxTrajectory.frames.length') >= 2
    np.testing.assert_allclose(
        page.evaluate('window.__ASE_APP__.state.atoms.positions'), backend.working_atoms.positions, atol=1e-12)
