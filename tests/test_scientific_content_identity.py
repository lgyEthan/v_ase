"""Dirty identity covers the archive's science rather than only the visible frame."""

import asyncio
import json
import zipfile
import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms
from ase.io.cube import write_cube
from playwright.sync_api import sync_playwright

from v_ase.session import EditorSession, append_session_frames
from v_ase.session import sessions
from v_ase.project import write_project_archive, read_project_archive
from v_ase.volumetric import VolumetricData
from v_ase.viewer import find_free_port, view
from v_ase.server import (create_volumetric_difference, delete_volumetric_dataset,
                          append_structure_path, update_calculator)


def _frames():
    return [Atoms('H2', positions=[[0, 0, 0], [x, 0, 0]]) for x in (2.0, 3.0)]


def test_offscreen_frame_edit_navigation_and_undo_redo_restore_content_identity():
    frames = _frames()
    session = EditorSession('content-frames', frames[0].copy(), frames[0].copy(),
                            original_frames=[frame.copy() for frame in frames],
                            trajectory_frames=[frame.copy() for frame in frames],
                            config={'viz_only': False})
    saved = session.scientific_content_identity()
    session.set_frame(1)
    assert session.scientific_content_identity() == saved
    session.push_history()
    session.working_atoms.positions[1, 0] = 3.5
    session.sync_current_frame()
    edited = session.scientific_content_identity()
    assert edited != saved
    session.set_frame(0)
    assert session.scientific_content_identity() == edited
    session.undo()
    assert session.scientific_content_identity() == saved
    session.redo()
    assert session.scientific_content_identity() == edited


def test_content_identity_covers_constraints_arrays_frame_append_and_volumes():
    frames = _frames()
    session = EditorSession('content-other', frames[0].copy(), frames[0].copy(),
                            original_frames=[frame.copy() for frame in frames],
                            trajectory_frames=[frame.copy() for frame in frames],
                            config={'viz_only': True})
    saved = session.scientific_content_identity()
    session.push_history()
    session.working_atoms.set_constraint(FixAtoms(indices=[0]))
    session.sync_current_frame()
    constrained = session.scientific_content_identity()
    assert constrained != saved
    session.undo()
    assert session.scientific_content_identity() == saved
    session.push_history()
    session.working_atoms.new_array('quality', np.array([0.2, 0.8]))
    session.sync_current_frame()
    assert session.scientific_content_identity() != saved
    session.undo()
    assert session.scientific_content_identity() == saved
    append_session_frames(session, [Atoms('H2', positions=[[0, 0, 0], [4, 0, 0]])])
    assert session.scientific_content_identity() != saved
    session.volumetric_datasets = [VolumetricData('charge', np.ones((2, 2, 2)), np.eye(3))]
    session.invalidate_scientific_content(auxiliary=True)
    with_volume = session.scientific_content_identity()
    session.volumetric_datasets[0].values[0, 0, 0] = 3
    session.invalidate_scientific_content(auxiliary=True)
    assert session.scientific_content_identity() != with_volume


def test_virtual_trajectory_offscreen_identity_survives_frame_navigation():
    class Source:
        frame_count = 2
        def __init__(self, frames):
            self.frames = frames
        def read_atoms(self, index):
            return self.frames[index].copy()
    frames = _frames()
    session = EditorSession('content-virtual', frames[0].copy(), frames[0].copy(),
                            trajectory_source=Source(frames),
                            config={'viz_only': True})
    saved = session.scientific_content_identity()
    session.set_frame(1)
    assert session.scientific_content_identity() == saved
    # A virtual source can be edited through a materializing operation.
    session.trajectory_frames = [frame.copy() for frame in frames]
    session.trajectory_source = None
    session.invalidate_scientific_content(all_frames=True)
    session.push_history()
    session.working_atoms.positions[1, 0] = 4
    session.sync_current_frame()
    assert session.scientific_content_identity() != saved
    session.set_frame(0)
    assert session.scientific_content_identity() != saved


def test_real_volumetric_endpoints_change_identity_without_manual_invalidation(tmp_path):
    atoms = Atoms('H', positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)
    first = VolumetricData('first', np.ones((3, 3, 3)), atoms.cell.array)
    second = VolumetricData('second', np.full((3, 3, 3), 0.25), atoms.cell.array)
    session = EditorSession('content-volume-endpoints', atoms.copy(), atoms.copy(),
                            volumetric_datasets=[first, second])
    sessions[session.session_id] = session
    try:
        baseline = session.scientific_content_identity()
        combined = asyncio.run(create_volumetric_difference(session.session_id, {
            'dataset_ids': [first.dataset_id, second.dataset_id],
            'coefficients': [1, -1], 'name': 'difference'
        }))
        after_combine = session.scientific_content_identity()
        assert after_combine != baseline
        assert combined['scientific_content_identity'] == after_combine
        removed = asyncio.run(delete_volumetric_dataset(session.session_id, {
            'dataset_id': second.dataset_id
        }))
        after_delete = session.scientific_content_identity()
        assert after_delete != after_combine
        assert removed['scientific_content_identity'] == after_delete
        archive = tmp_path / 'volumes.vase'
        write_project_archive(archive, session, {'display': {}})
        reopened = read_project_archive(archive)
        assert {dataset.name for dataset in reopened.volumetric_datasets} == {'first', 'difference'}
    finally:
        sessions.pop(session.session_id, None)


def test_real_volumetric_path_append_changes_identity(tmp_path):
    atoms = Atoms('H', positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)
    source = tmp_path / 'charge.cube'
    with source.open('w') as handle:
        write_cube(handle, atoms, data=np.ones((3, 3, 3)))
    session = EditorSession('content-volume-append', atoms.copy(), atoms.copy(),
                            config={'launch_directory': str(tmp_path)})
    sessions[session.session_id] = session
    try:
        baseline = session.scientific_content_identity()
        response = asyncio.run(append_structure_path(session.session_id, {
            'path': source.name, 'expected_source_kind': 'volumetric'
        }))
        assert len(session.volumetric_datasets) == 1
        assert response['metadata']['scientific_content_identity'] != baseline
        assert response['metadata']['scientific_content_identity'] == session.scientific_content_identity()
    finally:
        sessions.pop(session.session_id, None)


def test_calculator_identity_is_stable_across_frame_browsing_and_matches_override_archive(tmp_path):
    frames = _frames()
    session = EditorSession('content-calculator', frames[0].copy(), frames[0].copy(),
                            trajectory_frames=[frame.copy() for frame in frames],
                            original_frames=[frame.copy() for frame in frames],
                            config={'viz_only': False})
    sessions[session.session_id] = session
    try:
        baseline = session.scientific_content_identity()
        changed = asyncio.run(update_calculator(session.session_id, {'k_repulsion': 2}))
        configured = changed['metadata']['scientific_content_identity']
        assert configured != baseline
        session.set_frame(1)
        assert session.scientific_content_identity() == configured
        session.set_frame(0)
        assert session.scientific_content_identity() == configured
        default_cutoff = session.working_atoms.calc.cutoff_distance
        override = asyncio.run(update_calculator(session.session_id, {
            'cutoff_distance': default_cutoff
        }))
        explicit = override['metadata']['scientific_content_identity']
        assert explicit != configured
        archive = tmp_path / 'calculator.vase'
        write_project_archive(archive, session, {'display': {}})
        with zipfile.ZipFile(archive) as payload:
            manifest = json.loads(payload.read('manifest.json'))
        assert manifest['structure']['portable_calculator_config_included'] is True
        assert all(entry['parameters']['cutoff_distance'] == pytest.approx(default_cutoff)
                   for entry in manifest['calculator_results']['frames'])
    finally:
        sessions.pop(session.session_id, None)


def test_semantic_inactive_field_removal_is_dirty_and_requires_close_decision():
    atoms = Atoms('H', positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)
    fields = [VolumetricData(name, np.full((3, 3, 3), value), atoms.cell.array)
              for name, value in [('first', 1.0), ('second', 2.0)]]
    editor = view(atoms, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False, volumetric_datasets=fields)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.volumetricDatasets()?.length === 2')
            result = page.evaluate('''async id => {
                const app = window.__ASE_APP__;
                app.applyDisplayOptions();
                app.markProjectSavedContent();
                const saved = app.projectScientificSignature();
                await app.aiApplyOperation({name:'remove-volumetric', datasetId:id});
                const current = app.projectScientificSignature();
                window.__vaseCloseDecision = app.confirmDocumentClose();
                return {saved, current, dirty:app.updateProjectDirtyState()};
            }''', fields[1].dataset_id)
            assert result['current'] != result['saved']
            assert result['dirty'] is True
            page.locator('#modal-keep-editing').click()
            assert page.evaluate('window.__vaseCloseDecision') is False
            browser.close()
    finally:
        editor.close()


def test_pending_field_delete_cannot_close_before_partial_identity_is_adopted():
    atoms = Atoms('H', positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)
    fields = [VolumetricData(name, np.full((3, 3, 3), value), atoms.cell.array)
              for name, value in [('first', 1.0), ('second', 2.0)]]
    editor = view(atoms, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False, volumetric_datasets=fields)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.volumetricDatasets()?.length === 2')
            page.evaluate('''id => {
                const app=window.__ASE_APP__;
                app.applyDisplayOptions();
                app.markProjectSavedContent();
                const original=window.fetch.bind(window);
                const gate=new Promise(resolve=>{window.__releaseDelete=resolve});
                window.fetch=(input,options)=>String(input).includes('/api/volumetric/delete/')
                    ? gate.then(()=>original(input,options)) : original(input,options);
                window.__deleteDone=app.aiApplyOperation({
                    name:'remove-volumetric',datasetId:id
                });
                window.__closeResult='pending';
                app.confirmDocumentClose().then(value=>window.__closeResult=value);
            }''', fields[1].dataset_id)
            state = page.evaluate('''() => ({
                pending:window.__ASE_APP__.pendingScientificRequests.size,
                dirty:window.__ASE_APP__.updateProjectDirtyState(),
                close:window.__closeResult
            })''')
            assert state == {'pending': 1, 'dirty': True, 'close': 'pending'}
            page.evaluate('window.__releaseDelete()')
            page.locator('#modal-keep-editing').click()
            page.wait_for_function('window.__closeResult === false')
            assert page.evaluate('''async () => {
                await window.__deleteDone;
                const app=window.__ASE_APP__;
                return app.projectScientificSignature()
                    !==app.projectFile.savedScientificSignature && app.projectFile.dirty;
            }''') is True
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('streamed', [False, True])
def test_binary_trajectory_offscreen_edit_keeps_browser_dirty_then_undo_cleans(monkeypatch, tmp_path, streamed):
    monkeypatch.setattr('v_ase.server.MAX_INLINE_TRAJECTORY_CACHE_VALUES', 0)
    editor = view(_frames(), notebook=True, viz_only=False, block=False,
                  port=find_free_port(), close_on_disconnect=False,
                  stream_trajectory=streamed)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2')
            page.evaluate('''async () => {
                const app=window.__ASE_APP__;
                await app.loadFrame(0);
                app.applyDisplayOptions();
                app.markProjectSavedContent();
                await app.loadFrame(1);
                app.applySelectionAction({references:[1],origin:'semantic'});
                app.enterTransformMode('MOVE');
                app.transform.setAxis('X',app.renderer.camera);
                app.transform.buffer='0.5';
                app.applyTransformPreview();
                await app.commitTransform();
                await app.pendingApply;
                await app.loadFrame(0);
            }''')
            page.wait_for_function('window.__ASE_APP__.projectFile.dirty === true')
            state = page.evaluate('''() => {
                const app=window.__ASE_APP__;
                return {dirty:app.projectFile.dirty,
                    saved:app.projectFile.savedScientificSignature,
                    current:app.projectScientificSignature(),
                    revision:app.projectFile.structureRevision,
                    positions:app.state.atoms.positions,
                    meta:app.state.atoms.metadata.scientific_content_identity};
            }''')
            assert state['dirty'] is True, (state['saved'], state['current'], state['revision'])
            archive = tmp_path / 'offscreen.vase'
            write_project_archive(archive, sessions[editor.session_id], {'display': {}})
            reopened = read_project_archive(archive)
            assert reopened.frames[1].positions[1, 0] == pytest.approx(3.5)
            page.evaluate('window.__ASE_APP__.performUndo()')
            undo_state = page.evaluate('''() => {
                const app=window.__ASE_APP__;
                return {dirty:app.projectFile.dirty,
                    scientificSame:app.projectScientificSignature()===app.projectFile.savedScientificSignature,
                    visualSame:app.projectVisualSignature()===app.projectFile.savedVisualSignature,
                    current:app.projectScientificSignature(),saved:app.projectFile.savedScientificSignature,
                    visualDiff:Object.keys(JSON.parse(app.projectVisualSignature()).display).filter(key=>
                        JSON.stringify(JSON.parse(app.projectVisualSignature()).display[key])
                        !==JSON.stringify(JSON.parse(app.projectFile.savedVisualSignature).display[key])),
                    frame:app.state.atoms.metadata.current_frame};
            }''')
            assert undo_state['dirty'] is False, undo_state['visualDiff']
            page.evaluate('window.__ASE_APP__.performRedo()')
            assert page.evaluate('window.__ASE_APP__.projectFile.dirty') is True
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('streamed', [False, True])
@pytest.mark.parametrize('atom_count', [3, 260])
def test_binary_frame_navigation_edits_and_exports_preserve_double_coordinates(tmp_path, monkeypatch, streamed, atom_count):
    import base64
    import pickle
    monkeypatch.setattr('v_ase.server.MAX_INLINE_TRAJECTORY_CACHE_VALUES', 0)
    base = np.arange(atom_count * 3, dtype=float).reshape(atom_count, 3) / 17 + 3.37
    frames = [Atoms('H' * atom_count, positions=base + offset) for offset in (0.0, 0.1, 0.2)]
    editor = view(frames, notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False, stream_trajectory=streamed)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            exported = page.evaluate('''async () => {
                const app=window.__ASE_APP__;
                await app.loadFrame(1);
                app.applySelectionAction({references:[1],origin:'semantic'});
                await app.aiApplyOperation({name:'move-selection',vector:[0.125,0,0]});
                await app.loadFrame(2);
                app.state.display.atomRadiusScale=0.8;
                app.applyDisplayOptions();
                const pickle=await app.aiExport({format:'pickle'});
                const project=await app.aiExport({format:'project'});
                return {pickle:pickle.dataUrl, project:project.dataUrl};
            }''')
            saved_atom = pickle.loads(base64.b64decode(exported['pickle'].split(',', 1)[1]))
            np.testing.assert_array_equal(saved_atom.positions, frames[2].positions)
            archive = tmp_path / 'precision.vase'
            archive.write_bytes(base64.b64decode(exported['project'].split(',', 1)[1]))
            reopened = read_project_archive(archive)
            np.testing.assert_array_equal(reopened.frames[0].positions, frames[0].positions)
            expected = frames[1].positions.copy()
            expected[1, 0] += 0.125
            np.testing.assert_array_equal(reopened.frames[1].positions, expected)
            np.testing.assert_array_equal(reopened.frames[2].positions, frames[2].positions)
            browser.close()
    finally:
        editor.close()
