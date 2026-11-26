"""Desktop editing from actual pointers, controls and keyboard chords."""

import os
from pathlib import Path

import pytest
from ase import Atoms
from ase.constraints import FixAtoms
from playwright.sync_api import sync_playwright

from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


@pytest.fixture
def editing_page():
    atoms = Atoms("CuOCu", positions=[[-3, 0, 0], [0, 0, 0], [3, 0, 0]],
                  cell=[12, 8, 6], constraint=FixAtoms(indices=[0]), info={"energy_eV": -3.5})
    editor = view(atoms, notebook=True, open_browser=False, viz_only=False, block=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1480, "height": 930})
            page.goto(editor.url)
            page.wait_for_function("window.__ASE_APP__?.collaborationReady")
            page.evaluate("""() => {
                const a = window.__ASE_APP__;
                a.setAIAxisView('+Z');
                a.renderer.renderNow();
            }""")
            yield page
            browser.close()
    finally:
        editor.close()


def atom_point(page, index):
    point = page.evaluate("""i => {
        const r = window.__ASE_APP__.renderer;
        const rect = r.domElement.getBoundingClientRect();
        const projection = r.interactionProjectionContext(rect.x + rect.width / 2, rect.y + rect.height / 2);
        const point = r.projectWorldToClient(r.toVisualAtomPosition(r.getAtomPosition(i)), projection);
        return [point.x, point.y];
    }""", index)
    return point


def scene_state(page):
    return page.evaluate("""() => {
        const a = window.__ASE_APP__;
        return {selection: a.selectedAtomIndices(), camera: a.renderer.camera.position.toArray(),
            count: a.loadedFrameCount(), frame: a.state.atoms.metadata.current_frame};
    }""")


def capture(page, name):
    directory = os.environ.get("V_ASE_INTERACTION_EVIDENCE_DIR")
    if directory:
        page.screenshot(path=Path(directory) / name, animations="disabled")


def test_context_pointer_scope_selection_and_pan(editing_page):
    page = editing_page
    page.evaluate("window.__ASE_APP__.applySelectionAction({references:[0,1]})")
    point = atom_point(page, 2)
    before = scene_state(page)
    menu = page.locator("#viewport-context-menu")
    page.mouse.click(*point, button="right")
    menu.wait_for()
    assert menu.locator('[data-context-scope="pointer"]').get_attribute("aria-label") == "Cu #2"
    assert menu.locator('[data-context-scope="selected"]').get_attribute("aria-label") == "Selected atoms (2)"
    assert scene_state(page) == before
    capture(page, "context-pointer-selection.png")
    edit_labels = menu.locator('[data-context-scope="selected"]').get_by_role("menuitem", name="Edit labels…")
    targets = edit_labels.evaluate("""button => {
        const rect = button.getBoundingClientRect();
        return document.elementsFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
            .map(el => [el.closest('#viewport-context-menu')?.id, el.tagName, el.id,
                getComputedStyle(el).pointerEvents]);
    }""")
    assert targets[0][0] == "viewport-context-menu", targets
    edit_labels.click()
    assert page.locator("#selected-atom-label").evaluate("el => el === document.activeElement")
    assert scene_state(page)["selection"] == [0, 1]

    page.mouse.click(*point, button="right")
    menu.locator('[data-context-scope="pointer"]').get_by_role("menuitem", name="Edit label…").click()
    assert scene_state(page)["selection"] == [2]
    assert page.locator("#selected-atom-label").evaluate("el => el === document.activeElement")
    page.mouse.click(*point, button="right")
    assert menu.locator('[data-context-scope="selected"]').count() == 0
    menu.get_by_role("menuitem", name="Fix position").click()
    page.wait_for_function("window.__ASE_APP__.state.atoms.constraints.fixed_indices.includes(2)")
    page.mouse.click(*point, button="right")
    menu.get_by_role("menuitem", name="Release fixed position").click()
    page.wait_for_function("!window.__ASE_APP__.state.atoms.constraints.fixed_indices.includes(2)")
    page.evaluate("window.__ASE_APP__.applySelectionAction({references:[0,1]})")
    chord = "Meta" if page.evaluate("window.__ASE_APP__.shortcutPlatform") == "mac" else "Control"
    page.keyboard.press(f"{chord}+Shift+p")
    assert page.locator("#selected-atom-label").evaluate("el => el === document.activeElement")
    assert scene_state(page)["selection"] == [0, 1]
    page.evaluate("window.__ASE_APP__.applySelectionAction({references:[]})")

    box = page.evaluate("window.__ASE_APP__.renderer.domElement.getBoundingClientRect().toJSON()")
    x, y = box["right"] - 24, box["bottom"] - 88
    page.mouse.click(x, y, button="right")
    background = menu.locator('[data-context-scope="pointer"]')
    background.get_by_role("menuitem", name="Add atoms & molecules…").wait_for()
    assert not background.get_by_role("menuitem", name="Hide atoms", exact=True).count()
    assert not background.get_by_role("menuitem", name="Show atoms", exact=True).count()
    assert page.locator('[data-scene-id="atoms"] .scene-visibility').is_visible()
    capture(page, "context-blank.png")
    assert menu.bounding_box()["x"] + menu.bounding_box()["width"] <= box["right"]
    page.keyboard.press("Escape")
    assert menu.is_hidden()
    assert page.evaluate("document.activeElement === window.__ASE_APP__.renderer.domElement")
    page.keyboard.press("Shift+F10")
    menu.wait_for()
    page.keyboard.press("ArrowDown")
    assert menu.locator("button:focus").count() == 1
    page.keyboard.press("Escape")
    page.mouse.move(*point)
    page.mouse.down(button="right")
    page.mouse.move(point[0] - 74, point[1] - 31, steps=5)
    page.mouse.up(button="right")
    assert menu.is_hidden()
    assert scene_state(page)["camera"] != before["camera"]


def test_duplicate_frame_after_live_edit_then_append_and_undo(editing_page):
    page = editing_page
    page.evaluate("""async () => {
        const a = window.__ASE_APP__;
        const data = await a.api.applyPositions([[-3,0,0],[0,0.75,0],[3,0,0]]);
        a.setAtomsData(data);
    }""")
    chord = "Meta" if page.evaluate("window.__ASE_APP__.shortcutPlatform") == "mac" else "Control"
    page.press("body", f"{chord}+t")
    page.wait_for_function("""() => {
        const a = window.__ASE_APP__;
        return a.loadedFrameCount() === 2 && a.state.atoms.metadata.current_frame === 1;
    }""")
    assert page.locator("#frame-label").inner_text() == "2 / 2"
    assert page.get_by_text("Created frame 2 of 2.", exact=True).is_visible()
    page.evaluate("""async () => {
        const a = window.__ASE_APP__;
        const data = await a.api.applyPositions([[-3,0,0],[0,1.5,0],[3,0,0]]);
        a.setAtomsData(data);
        await a.loadFrame(0);
    }""")
    page.press("body", f"{chord}+Shift+t")
    page.wait_for_function("window.__ASE_APP__.loadedFrameCount() === 3")
    assert page.locator("#frame-label").inner_text() == "3 / 3"
    frames = page.evaluate("""async () => {
        const a = window.__ASE_APP__, values = [];
        for (let i = 0; i < a.loadedFrameCount(); i++) {
            await a.loadFrame(i);
            values.push(a.state.atoms.positions[1][1]);
        }
        return values;
    }""")
    assert frames == [0.75, 1.5, 0.75]
    page.evaluate("window.__ASE_APP__.performUndo()")
    page.wait_for_function("window.__ASE_APP__.loadedFrameCount() === 2")
    assert page.locator("#frame-label").inner_text() == "1 / 2"


def test_duplicate_visible_relaxation_image_from_timeline_menu(editing_page):
    page = editing_page
    session = sessions[page.evaluate("window.__ASE_APP__.sessionId")]
    session.push_history()
    session.relaxation_baseline = session.history[-1]
    session.relaxation_mode_active = True
    page.evaluate("""async () => {
        const a = window.__ASE_APP__;
        const image = y => [[-3, 0, 0], [0, y, 0], [3, 0, 0]];
        a.setAtomsData(await a.api.applyPositions(image(1.2)));
        a.state.relaxTrajectory = {frames: [image(0), image(.6), image(1.2)],
            sourceFrame: 0, frame: 0, active: true, finished: true, kind: 'relaxation'};
        a.state.timelineSource = 'relax';
        await a.loadRelaxFrame(1);
    }""")
    page.locator("#frame-label").click(button="right")
    page.locator("#viewport-context-menu").get_by_role("menuitem", name="Duplicate to next frame").click()
    page.wait_for_function("window.__ASE_APP__.loadedFrameCount() === 2")
    assert page.locator("#trajectory-panel").get_attribute("data-primary-source") == "loaded"
    assert page.locator("#frame-label").inner_text() == "2 / 2"
    assert page.evaluate("window.__ASE_APP__.state.atoms.positions[1][1]") == pytest.approx(.6)
    assert session.trajectory_frames[0].positions[1, 1] == pytest.approx(1.2)
    assert not session.relaxation_mode_active
    energies = page.evaluate("window.__ASE_APP__.api.request('/api/trajectory/energy/{session_id}')")
    assert energies["values"] == [-3.5, None]


def test_bonds_apply_live_and_atom_layer_keeps_other_objects(editing_page):
    page = editing_page
    page.evaluate("""() => {
        const a = window.__ASE_APP__;
        a.applyDesignSettings({display: {...a.state.display, showBonds:true, showCell:true,
            showConstraints:true, showAtoms:true, bondMode:'manual', manualBondPairs:[[0,1],[1,2]],
            atomDisplayMode:'2d'}});
        a.openEditorRoute('bonding');
    }""")
    page.locator("#bond-color-mode").select_option("custom")
    page.locator("#bond-custom-color").fill("#336699")
    page.wait_for_function("window.__ASE_APP__.renderer.bondSegmentColor(window.__ASE_APP__.renderer.bondSegmentsForPair(0,1)[0]) === '#336699'")
    pair_editor = page.locator(".bond-pair-appearance")
    if pair_editor.get_attribute("open") is None:
        pair_editor.locator("summary").click()
    page.locator("#bond-pair-style-key").select_option("Cu-O")
    page.locator("#bond-pair-style-enabled").check()
    page.locator("#bond-pair-custom-color").fill("#cc3355")
    page.wait_for_function("window.__ASE_APP__.renderer.bondSegmentColor(window.__ASE_APP__.renderer.bondSegmentsForPair(0,1)[0]) === '#cc3355'")
    assert page.locator("#bond-global-overrides").is_visible()
    page.locator("#bond-custom-color").fill("#287c62")
    page.locator("#btn-use-global-bonds").click()
    page.wait_for_function("window.__ASE_APP__.renderer.bondSegmentColor(window.__ASE_APP__.renderer.bondSegmentsForPair(0,1)[0]) === '#287c62'")
    assert page.locator("#bond-global-overrides").is_hidden()

    page.evaluate("""() => {
        const a = window.__ASE_APP__;
        a.openEditorRoute('export', {focus:'#renderer-atom-display-mode'});
    }""")
    page.locator("#renderer-outline-width").fill("0.085")
    assert page.locator("#renderer-sphere-quality").is_enabled()
    page.wait_for_function("window.__ASE_APP__.renderer.flatOutlineWidthUniform.value === .085")
    capture(page, "flat-render-controls.png")
    page.evaluate("window.__ASE_APP__.performSceneNavigatorAction('atoms','visibility',false)")
    visible = page.evaluate("""() => {
        const a = window.__ASE_APP__, r = a.renderer;
        r.renderNow();
        return [r.atomMeshes.visible, r.bondPairs.length, r.cellGroup.visible,
            r.constraintMarkGroup.children[0]?.count, a.state.atoms.positions.length];
    }""")
    assert visible == [False, 2, True, 2, 3]
    page.evaluate("window.__ASE_APP__.performSceneNavigatorAction('atoms','visibility',true)")
    assert page.evaluate("window.__ASE_APP__.renderer.atomMeshes.visible")
