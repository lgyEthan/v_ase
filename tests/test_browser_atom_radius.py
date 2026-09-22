"""Real renderer coverage for mapped atom sizes and bulk measurement intent."""

import os

import numpy as np
import pytest
from ase import Atoms
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.viewer import find_free_port, view
from tests.ui_navigation import open_editor_route
from v_ase.atom_radius import normalize_atom_radius_mapping


def test_optimizer_frames_use_displayed_coordinates_and_not_loaded_property_arrays():
    atoms = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    atoms.new_array("fraction", np.array([0.25, 0.75]))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            result = page.evaluate("""async () => {
                const app=window.__ASE_APP__;
                app.state.display.atomRadiusMapping={enabled:true,field:'array::fraction::scalar',
                    valueTransform:'identity',rangeMode:'manual',min:0,max:1,
                    minMultiplier:0,maxMultiplier:1,exponent:1,scope:'all',indices:[]};
                await app.updateAtomRadiusMapping();
                const loaded=[...app.renderer.atomRadiusFactors];
                app.state.relaxTrajectory.frames=[[[0,0,0],[3,0,0]]];
                app.state.relaxTrajectory.frame=0;
                app.state.displayedTimelineSource='relax';
                app.state.atoms.positions=[[0,0,0],[3,0,0]];
                app.renderer.updatePositions(app.state.atoms.positions);
                await app.updateAtomRadiusMapping();
                const missing=[...app.renderer.atomRadiusFactors];
                const status=document.getElementById('atom-radius-mapping-status').textContent;
                app.state.display.atomRadiusMapping={...app.state.display.atomRadiusMapping,
                    field:'position:x',min:0,max:4};
                await app.updateAtomRadiusMapping();
                return {loaded,missing,status,coordinates:[...app.renderer.atomRadiusFactors]};
            }""")
            assert result['loaded'] == pytest.approx([0.25, 0.75])
            assert result['missing'] == pytest.approx([1, 1])
            assert 'Optimizer frame has no stored value' in result['status']
            assert result['coordinates'] == pytest.approx([0, 0.75])
            browser.close()
    finally:
        editor.close()


def test_live_radius_mapping_updates_exact_glyph_sizes_without_changing_bonds():
    atoms = Atoms("H4", positions=[[0, 0, 0], [2, 0, 0], [4, 0, 0], [6, 0, 0]])
    atoms.new_array("fraction", np.array([0, 0.125, 0.5, 1], dtype=np.float64))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")
            before = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {radii: [0,1,2,3].map(i => app.renderer.atomVisualRadius(i)),
                    bonds: JSON.stringify(app.renderer.bondPairs)};
            }""")
            page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.atomRadiusMapping = {
                    enabled: true, field: 'array::fraction::scalar',
                    valueTransform: 'identity', rangeMode: 'manual', min: 0, max: 1,
                    minMultiplier: 0, maxMultiplier: 1, exponent: 1,
                    scope: 'all', indices: []
                };
                await app.updateAtomRadiusMapping();
                app.syncAtomRadiusMappingControls();
            }""")
            after = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {radii: [0,1,2,3].map(i => app.renderer.atomVisualRadius(i)),
                    factors: [...app.renderer.atomRadiusFactors],
                    visible: [0,1,2,3].map(i => app.renderer.atomMeshByIndex.get(i).visible),
                    bonds: JSON.stringify(app.renderer.bondPairs),
                    status: app.atomRadiusRuntime.status};
            }""")
            assert after["factors"] == pytest.approx([0, 0.125, 0.5, 1])
            assert after["radii"] == pytest.approx([size * factor for size, factor in zip(before["radii"], after["factors"])])
            assert after["visible"] == [False, True, True, True]
            assert after["bonds"] == before["bonds"]
            assert after["status"] == "ready"
            focused = page.evaluate("window.__ASE_APP__.aiAppearanceSnapshot()")
            assert focused["atomRadiusMapping"]["field"] == "array::fraction::scalar"
            assert focused["atomRadiusMappingState"]["status"] == "ready"
            assert focused["atomRadiusMappingState"]["appliedAtoms"] == 4
            if os.environ.get("V_ASE_UI_QA_SCREENSHOT"):
                open_editor_route(page, 'appearance')
                page.screenshot(path=os.environ["V_ASE_UI_QA_SCREENSHOT"], full_page=True)
            browser.close()
    finally:
        editor.close()


def test_radius_mapping_can_be_enabled_from_a_fresh_visible_form():
    atoms = Atoms("H4", positions=[[0, 0, 0], [2, 0, 0], [4, 0, 0], [6, 0, 0]])
    atoms.new_array("fraction", np.array([0, 0.25, 0.5, 1], dtype=np.float64))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")
            open_editor_route(page, 'appearance')
            page.check('#chk-atom-radius-mapping')
            assert page.locator('#atom-radius-mapping-field').is_visible()
            assert page.locator('#atom-radius-mapping-status').is_visible()
            page.locator('#atom-radius-mapping-field option[value="array::fraction::scalar"]').wait_for(state='attached')
            page.select_option('#atom-radius-mapping-field', 'array::fraction::scalar')
            page.wait_for_function("window.__ASE_APP__.atomRadiusRuntime.status === 'ready'")
            state = page.evaluate("""() => ({
                enabled: window.__ASE_APP__.state.display.atomRadiusMapping.enabled,
                field: window.__ASE_APP__.state.display.atomRadiusMapping.field,
                factors: [...window.__ASE_APP__.renderer.atomRadiusFactors]
            })""")
            assert state['enabled'] is True
            assert state['field'] == 'array::fraction::scalar'
            assert state['factors'] == pytest.approx([0.25, 0.5, 0.75, 1.25])
            browser.close()
    finally:
        editor.close()


def test_restored_display_settings_refresh_or_clear_effective_radius_factors():
    atoms = Atoms("H4", positions=[[0, 0, 0], [2, 0, 0], [4, 0, 0], [6, 0, 0]])
    atoms.new_array("fraction", np.array([0, 0.25, 0.5, 1], dtype=np.float64))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const snapshot = app.designSettingsSnapshot();
                window.__radiusTestSnapshot = snapshot;
                app.applyDesignSettings({...snapshot, display: {...snapshot.display,
                    atomRadiusMapping: {enabled: true, field: 'array::fraction::scalar',
                        valueTransform: 'identity', rangeMode: 'manual', min: 0, max: 1,
                        minMultiplier: 0, maxMultiplier: 1, exponent: 1,
                        scope: 'all', indices: []}}});
            }""")
            page.wait_for_function("window.__ASE_APP__.atomRadiusRuntime.status === 'ready'")
            assert page.evaluate("[...window.__ASE_APP__.renderer.atomRadiusFactors]") == pytest.approx([0, .25, .5, 1])
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const snapshot = app.designSettingsSnapshot();
                app.applyDesignSettings({...snapshot, display: {...snapshot.display,
                    atomRadiusMapping: {...snapshot.display.atomRadiusMapping, enabled: false}}});
            }""")
            page.wait_for_function("window.__ASE_APP__.renderer.atomRadiusFactors === null")
            page.evaluate("window.__ASE_APP__.applyDesignSettings(window.__radiusTestSnapshot)")
            page.wait_for_function("window.__ASE_APP__.state.display.atomRadiusMapping.enabled === false")
            assert page.evaluate("window.__ASE_APP__.renderer.atomRadiusFactors") is None
            browser.close()
    finally:
        editor.close()


def test_box_selection_suppresses_geometry_but_ordered_selection_keeps_it():
    atoms = Atoms("H3", positions=[[0, 0, 0], [1, 0, 0], [1, 1, 0]])
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            bulk = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.applySelectionAction({references: [0,1,2], origin: 'pointer-box'});
                return {text: app.getSelectionMeasureText(), summary: app.getSelectionMeasureSummary(),
                    label: document.querySelector('#selection-measure-readout .selection-measure-label').textContent,
                    kind: document.getElementById('measurement-overlay').dataset.measureKind,
                    paths: document.querySelectorAll('.measure-connector').length};
            }""")
            assert "3 atoms selected" in bulk["text"]
            assert "angle" not in bulk["text"].lower()
            assert "3 atoms selected" in bulk["summary"]
            assert bulk["kind"] == "none"
            assert bulk["label"] == "SELECT"
            assert bulk["paths"] == 0
            ordered = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.applySelectionAction({references: [0], origin: 'pointer-single', measurement: 'ordered'});
                app.applySelectionAction({references: [1], mode: 'toggle', origin: 'pointer-single', measurement: 'ordered'});
                app.applySelectionAction({references: [2], mode: 'toggle', origin: 'pointer-single', measurement: 'ordered'});
                return {text: app.getSelectionMeasureText(),
                    label: document.querySelector('#selection-measure-readout .selection-measure-label').textContent,
                    kind: document.getElementById('measurement-overlay').dataset.measureKind};
            }""")
            assert "angle(a1-a2-a3)" in ordered["text"]
            assert ordered["kind"] == "angle"
            assert ordered["label"] == "MEASURE"
            browser.close()
    finally:
        editor.close()


def test_periodic_toggle_deduplicates_editable_identity_and_invalid_semantic_selection_is_atomic():
    atoms = Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]], cell=[4, 4, 4], pbc=True)
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), viz_only=False,
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            result = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.supercell = [3, 1, 1];
                app.renderer.setDisplayOptions({supercell: [3, 1, 1]});
                app.applySelectionAction({references: [0, {index: 0, cellOffset: [1, 0, 0]}],
                    mode: 'toggle', origin: 'pointer-box'});
                const selectedAfterBox = [...app.state.selected];
                app.applySelectionAction({references: [0, 1], origin: 'semantic', measurement: 'ordered'});
                const before = {keys: [...app.state.selectionOrder], intent: JSON.stringify(app.state.measurementIntent)};
                let error = '';
                try { await app.aiApply({selection: {references: [{index: 999, cellOffset: [0, 0, 0]}]}}); }
                catch (failure) { error = failure.message; }
                return {selectedAfterBox, before, after: {
                    keys: [...app.state.selectionOrder], intent: JSON.stringify(app.state.measurementIntent)}, error};
            }""")
            assert result["selectedAfterBox"] == [0]
            assert "invalid or unavailable" in result["error"]
            assert result["after"] == result["before"]
            browser.close()
    finally:
        editor.close()


def test_zero_radius_instanced_atom_reappears_after_visibility_refresh():
    atoms = Atoms("H256", positions=np.column_stack((np.arange(256) % 16,
                                                     np.arange(256) // 16,
                                                     np.zeros(256))))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 256")
            state = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const zeros = new Float32Array(256).fill(1);
                zeros[0] = 0;
                renderer.setAtomRadiusFactors(zeros);
                renderer.applyAtomVisibility();
                const hidden = renderer.atomInstanceRefs.get(0).matrix[renderer.atomInstanceRefs.get(0).matrixOffset];
                renderer.setAtomRadiusFactors(new Float32Array(256).fill(1));
                const ref = renderer.atomInstanceRefs.get(0);
                return {instanced: renderer.useInstancedAtoms, hidden,
                    proxyVisible: ref.proxy.visible, scale: ref.matrix[ref.matrixOffset],
                    radius: renderer.atomVisualRadius(0)};
            }""")
            assert state['instanced'] is True
            assert state['hidden'] == 0
            assert state['proxyVisible'] is True
            assert state['scale'] == pytest.approx(state['radius'])
            browser.close()
    finally:
        editor.close()


def test_delayed_radius_fit_cannot_overwrite_newer_field_choice():
    atoms = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    atoms.new_array("fraction", np.array([0.0, 1.0]))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            state = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const original = app.atomScalarStore.values.bind(app.atomScalarStore);
                let release;
                app.atomScalarStore.values = (field, options) => field === 'array::fraction::scalar'
                    ? new Promise(resolve => { release = () => resolve({
                        values: new Float32Array([0, 1]), atoms: 2,
                        frames: 1, startFrame: 0
                    }); })
                    : original(field, options);
                const base = {enabled: true, valueTransform: 'identity',
                    rangeMode: 'current', min: 0, max: 1,
                    minMultiplier: 0, maxMultiplier: 1,
                    exponent: 1, scope: 'all', indices: []};
                const slow = app.fitAtomRadiusMappingRange('current', {
                    ...base, field: 'array::fraction::scalar'
                });
                const fast = await app.fitAtomRadiusMappingRange('current', {
                    ...base, field: 'position:x'
                });
                release();
                const superseded = await slow;
                app.atomScalarStore.values = original;
                return {fast, superseded, field: app.state.display.atomRadiusMapping.field,
                    max: app.state.display.atomRadiusMapping.max,
                    factors: [...app.renderer.atomRadiusFactors]};
            }""")
            assert state['fast'] is True
            assert state['superseded'] is False
            assert state['field'] == 'position:x'
            assert state['max'] == pytest.approx(2)
            assert state['factors'] == pytest.approx([0, 1])
            browser.close()
    finally:
        editor.close()


def test_trajectory_radius_fit_scans_each_frame_instead_of_accepting_one_frame_fallback():
    first = Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]])
    first.new_array("fraction", np.array([0.0, 1.0]))
    second = first.copy()
    second.arrays['fraction'][:] = [10.0, 40.0]
    editor = view([first, second], notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2")
            state = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const accepted = await app.fitAtomRadiusMappingRange('trajectory', {
                    enabled: true, field: 'array::fraction::scalar',
                    valueTransform: 'identity', rangeMode: 'trajectory', min: 0, max: 1,
                    minMultiplier: 0, maxMultiplier: 1, exponent: 1,
                    scope: 'all', indices: []
                });
                return {accepted, ...app.state.display.atomRadiusMapping};
            }""")
            assert state['accepted'] is True
            assert state['rangeMode'] == 'trajectory'
            assert state['min'] == pytest.approx(0)
            assert state['max'] == pytest.approx(40)
            browser.close()
    finally:
        editor.close()


def test_position_radius_follows_active_numeric_move_preview_and_cancel():
    atoms = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), viz_only=False,
                  close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.atomRadiusMapping = {
                    enabled: true, field: 'position:x', valueTransform: 'identity',
                    rangeMode: 'manual', min: 0, max: 4,
                    minMultiplier: 0, maxMultiplier: 1, exponent: 1,
                    scope: 'all', indices: []
                };
                await app.updateAtomRadiusMapping();
                app.applySelectionAction({references: [1], origin: 'pointer-single', measurement: 'ordered'});
            }""")
            assert page.evaluate("window.__ASE_APP__.renderer.atomRadiusFactors[1]") == pytest.approx(.5)
            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.press('1')
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.transform.mode === 'MOVE'
                    && Math.abs(app.renderer.atomMeshByIndex.get(1).position.x - 3) < 1e-6
                    && Math.abs(app.renderer.atomRadiusFactors[1] - .75) < 1e-6;
            }""")
            page.keyboard.press('Escape')
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.transform.mode === 'IDLE'
                    && Math.abs(app.renderer.atomRadiusFactors[1] - .5) < 1e-6;
            }""")
            browser.close()
    finally:
        editor.close()


def test_long_global_radius_slider_gesture_is_one_visual_undo():
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True, block=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1")
            count = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const slider = document.getElementById('atom-radius-scale');
                slider.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                slider.value = '0.8'; slider.dispatchEvent(new Event('input', {bubbles: true}));
                await new Promise(resolve => setTimeout(resolve, 230));
                slider.value = '1.0'; slider.dispatchEvent(new Event('input', {bubbles: true}));
                slider.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
                slider.dispatchEvent(new Event('change', {bubbles: true}));
                return app.undoTimeline.filter(action => action.source === 'atom-radius-scale').length;
            }""")
            assert count == 1
            browser.close()
    finally:
        editor.close()


def test_final_radius_style_rejects_zero_mapping_without_partial_change():
    atoms = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    atoms.new_array("fraction", np.array([0.0, 1.0]))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            result = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.atomRadiusMapping = {
                    enabled: true, field: 'array::fraction::scalar',
                    valueTransform: 'identity', rangeMode: 'manual', min: 0, max: 1,
                    minMultiplier: 0, maxMultiplier: 1, exponent: 1,
                    scope: 'all', indices: []
                };
                await app.updateAtomRadiusMapping();
                const before = JSON.stringify(app.state.display.atomRadiusScales);
                let error = '';
                try {
                    app.applyAIAtomStyle({indices: [0, 1], color: '#aa0000', radiusAngstrom: 1});
                } catch (caught) { error = caught.message; }
                return {error, before, after: JSON.stringify(app.state.display.atomRadiusScales),
                    color: app.state.display.atomColors?.[0], radius: app.renderer.atomVisualRadius(0)};
            }""")
            assert "mapped radius factor is zero" in result["error"]
            assert result["before"] == result["after"]
            assert result["color"] is None
            assert result["radius"] == 0
            browser.close()
    finally:
        editor.close()


def test_custom_radius_preset_fits_signed_values_and_rejects_empty_input():
    atoms = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    atoms.new_array("signed", np.array([-20.0, -10.0]))
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            open_editor_route(page, 'appearance')
            page.check('#chk-atom-radius-mapping')
            page.locator('#atom-radius-mapping-field option[value="array::signed::scalar"]').wait_for(state='attached')
            page.select_option('#atom-radius-mapping-field', 'array::signed::scalar')
            page.wait_for_function("window.__ASE_APP__.atomRadiusRuntime.status === 'ready'")
            page.select_option('#atom-radius-mapping-preset', 'custom')
            page.wait_for_function("""() => {
                const m = window.__ASE_APP__.state.display.atomRadiusMapping;
                return m.rangeMode === 'current' && m.min === -20 && m.max === -10;
            }""")
            before = page.evaluate("JSON.stringify(window.__ASE_APP__.state.display.atomRadiusMapping)")
            page.evaluate("""() => {
                const input = document.getElementById('atom-radius-mapping-output-min');
                input.value = '';
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            assert page.evaluate("JSON.stringify(window.__ASE_APP__.state.display.atomRadiusMapping)") == before
            assert "finite value" in page.locator('#atom-radius-mapping-status').inner_text()
            browser.close()
    finally:
        editor.close()


def test_video_radius_samples_interpolate_raw_values_and_restore_source_frame():
    first = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    second = first.copy()
    first.new_array("fraction", np.array([0.0, 1.0]))
    second.new_array("fraction", np.array([1.0, 0.0]))
    editor = view([first, second], notebook=True, block=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2")
            state = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.atomRadiusMapping = {
                    enabled: true, field: 'array::fraction::scalar', valueTransform: 'identity',
                    rangeMode: 'manual', min: 0, max: 1, minMultiplier: 0,
                    maxMultiplier: 1, exponent: 1, scope: 'all', indices: []
                };
                await app.updateAtomRadiusMapping();
                const first = await app.videoFrameSnapshot();
                await app.loadFrame(1);
                const second = await app.videoFrameSnapshot();
                const sample = {positions: Float64Array.from(first.positions), count: 2};
                app.interpolateVideoRadiusScalars(first, second, 0.25, sample);
                app.applyVideoSampleRadiusFactors(sample);
                const interpolated = [...app.renderer.atomRadiusFactors];
                await app.loadFrame(0);
                await app.updateAtomRadiusMapping();
                return {interpolated, restored: [...app.renderer.atomRadiusFactors],
                    frame: app.state.atoms.metadata.current_frame};
            }""")
            assert state["interpolated"] == pytest.approx([0.25, 0.75])
            assert state["restored"] == pytest.approx([0, 1])
            assert state["frame"] == 0
            browser.close()
    finally:
        editor.close()


def test_frozen_radius_scope_tracks_duplicate_delete_and_undo_identity():
    atoms = Atoms("H3", positions=[[0, 0, 0], [1, 0, 0], [2, 0, 0]])
    editor = view(atoms, notebook=True, block=False, viz_only=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            result = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.atomRadiusMapping = {
                    enabled: true, field: 'position:x', valueTransform: 'identity',
                    rangeMode: 'manual', min: 0, max: 3, minMultiplier: 0,
                    maxMultiplier: 1, exponent: 1, scope: 'indices', indices: [1]
                };
                await app.updateAtomRadiusMapping();
                app.applySelectionAction({references:[1],origin:'semantic'});
                app.copySelection();
                await app.pasteSelection({throwErrors:true});
                const duplicated = [...app.state.display.atomRadiusMapping.indices];
                const duplicateCount = app.state.atoms.positions.length;
                app.applySelectionAction({references:[1],origin:'semantic'});
                await app.deleteSelection();
                const deleted = [...app.state.display.atomRadiusMapping.indices];
                await app.performUndo();
                const restored = [...app.state.display.atomRadiusMapping.indices];
                return {duplicated, deleted, restored, duplicateCount,
                    enabled: app.state.display.atomRadiusMapping.enabled};
            }""")
            assert result == {"duplicated": [1, 3], "deleted": [2], "duplicateCount": 4,
                              "restored": [1, 3], "enabled": True}
            browser.close()
    finally:
        editor.close()


def test_color_and_radius_share_one_scalar_request_and_bounded_cache():
    atoms = Atoms("H4", positions=[[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]])
    atoms.new_array("fraction", np.array([0.0, 0.25, 0.5, 1.0]))
    editor = view(atoms, notebook=True, block=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")
            result = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const field = 'array::fraction::scalar';
                app.state.display.atomColorScaleField = field;
                app.state.display.atomRadiusMapping = {
                    enabled: true, field, valueTransform: 'identity', rangeMode: 'manual',
                    min: 0, max: 1, minMultiplier: 0, maxMultiplier: 1, exponent: 1,
                    scope: 'all', indices: []
                };
                let requests = 0;
                const original = app.api.fetchAtomScalarValues.bind(app.api);
                app.api.fetchAtomScalarValues = async (...args) => {
                    requests += 1;
                    return await original(...args);
                };
                await Promise.all([
                    app.atomColorScaleValuesForCurrentFrame(),
                    app.updateAtomRadiusMapping()
                ]);
                const networkRequests = requests;
                const factors = [...app.renderer.atomRadiusFactors];
                app.atomScalarStore.invalidate();
                app.api.fetchAtomScalarValues = async () => ({
                    values: new Float32Array(4 * 1024 * 1024),
                    frames: 1, startFrame: 0, atoms: 4
                });
                for (let index = 0; index < 3; index += 1) {
                    await app.atomScalarStore.values(`synthetic-${index}`);
                }
                return {requests: networkRequests, bytes: app.atomScalarStore.valueCacheBytes,
                    entries: app.atomScalarStore.valueCache.size,
                    factors};
            }""")
            assert result["requests"] == 1
            assert result["bytes"] <= 32 * 1024 * 1024
            assert result["entries"] == 2
            assert result["factors"] == pytest.approx([0, 0.25, 0.5, 1])
            browser.close()
    finally:
        editor.close()


def test_semantic_radius_operation_fits_and_reports_focused_effective_state():
    atoms = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    atoms.new_array("fraction", np.array([10.0, 20.0]))
    editor = view(atoms, notebook=True, block=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            result = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                await window.v_aseAI.apply({operation: {
                    name: 'set-atom-radius-mapping', field: 'array::fraction::scalar',
                    rangeMode: 'current', minMultiplier: 0, maxMultiplier: 1,
                    scope: 'all'
                }});
                return {mapping: app.aiAppearanceSnapshot().atomRadiusMapping,
                    state: app.aiAppearanceSnapshot().atomRadiusMappingState,
                    factors: [...app.renderer.atomRadiusFactors]};
            }""")
            assert result["mapping"]["min"] == pytest.approx(10)
            assert result["mapping"]["max"] == pytest.approx(20)
            assert result["mapping"]["rangeMode"] == "current"
            assert result["state"]["status"] == "ready"
            assert result["factors"] == pytest.approx([0, 1])
            browser.close()
    finally:
        editor.close()


def test_js_and_python_radius_validation_have_same_invalid_fallback():
    cases = [
        {"field": None}, {"min": ""}, {"max": None},
        {"valueTransform": "other"}, {"rangeMode": "other"},
        {"scope": "other"}, {"indices": [-1]},
    ]
    base = {
        "enabled": True, "field": "position:x", "rangeMode": "manual",
        "min": 0, "max": 1, "minMultiplier": 0, "maxMultiplier": 1,
        "exponent": 1, "scope": "all", "indices": [],
    }
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(editor.url)
            actual = page.evaluate("""async cases => {
                const {normalizeAtomRadiusMapping} = await import('/static/radius_mapping.js?v=0.4.0');
                return cases.map(value => {
                    const loose = normalizeAtomRadiusMapping(value);
                    let strictError = '';
                    try { normalizeAtomRadiusMapping(value, {strict:true}); }
                    catch (error) { strictError = error.message; }
                    return {mapping: loose.mapping, strictError};
                });
            }""", [{**base, **change} for change in cases])
            for item, change in zip(actual, cases):
                value = {**base, **change}
                assert item["mapping"] == normalize_atom_radius_mapping(value)
                with pytest.raises(ValueError) as error:
                    normalize_atom_radius_mapping(value, strict=True)
                assert item["strictError"] == str(error.value)
            browser.close()
    finally:
        editor.close()
