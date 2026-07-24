import base64
import io
import math
import hashlib
import subprocess
import time

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule
from ase.constraints import FixAtoms
from ase.io import write
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.session import sessions
from v_ase.io import set_atom_type_labels
from v_ase.viewer import find_free_port, view


def _expand_inspector(page):
    if page.locator('body').evaluate("element => element.classList.contains('inspector-collapsed')"):
        page.click('#btn-inspector-collapse')
        page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
        page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 336")


def _open_panel(page, panel):
    details = page.locator(f'[data-panel="{panel}"]')
    if not details.evaluate("element => element.open"):
        details.locator('summary').click()


def test_empty_workspace_opens_a_complete_trajectory_from_the_browser(tmp_path):
    first = molecule("H2O")
    first.set_cell([8.0, 8.0, 8.0])
    first.set_pbc(True)
    second = first.copy()
    second.positions += [0.4, 0.0, 0.0]
    source = tmp_path / "browser_movie.extxyz"
    write(source, [first, second], format="extxyz")
    replacement = Atoms(
        "OC",
        positions=[[0.0, 0.0, 0.0], [1.25, 0.0, 0.0]],
        cell=[9.0, 9.0, 9.0],
        pbc=True,
    )
    replacement_source = tmp_path / "replacement.extxyz"
    write(replacement_source, replacement, format="extxyz")

    port = find_free_port()
    editor = view(
        Atoms(),
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 0")

            assert page.locator('#empty-workspace').is_visible()
            assert page.locator('#btn-empty-open').is_visible()
            assert page.locator('#btn-export-pickle').is_disabled()

            page.set_input_files('#structure-file', str(source))
            assert page.locator('#open-file-name').inner_text() == source.name
            assert page.locator('#open-file-format').input_value() == ''
            assert page.locator('#open-file-index').input_value() == ':'
            page.click('#open-file-confirm')

            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 3")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2")
            page.wait_for_function("document.getElementById('busy-overlay').classList.contains('hidden')")
            assert not page.locator('#empty-workspace').is_visible()
            assert not page.locator('#btn-export-pickle').is_disabled()
            assert page.locator('#frame-label').inner_text() == '1 / 2'

            inherited_before = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const current = app.designSettingsSnapshot();
                app.applyDesignSettings({
                    ...current,
                    antiAliasing: false,
                    sphereQuality: 'high',
                    moveIncrement: 0.15,
                    rotateIncrementDeg: 7.5,
                    display: {
                        ...current.display,
                        showBonds: true,
                        showGrid: false,
                        bondMode: 'element',
                        atomRadiusScale: 1.35,
                        elementColors: {H: '#d9d9d9', O: '#2a6fdf'},
                        elementRadii: {H: 0.31, O: 0.77},
                        elementVisible: {H: false, O: true},
                        elementBondCutoffs: {'H-H': 0.8, 'H-O': 1.4, 'O-O': 1.8},
                        supercell: [2, 1, 1],
                        projectionMode: 'orthographic',
                        viewportBackground: 'white',
                        atomDisplayMode: '2d',
                        viewRotationStepDeg: 22.5,
                        lightingMode: 'rendered',
                        sunIntensity: 4.25,
                        sunPosition: [12, -5, 15],
                        sunTarget: [1, 2, 3],
                        atomicScalePixelsPerAngstrom: 36
                    },
                    camera: {
                        projection: 'orthographic',
                        position: [9, -11, 7],
                        target: [1, 2, 0.5],
                        up: [0, 0, 1],
                        near: 0.01,
                        far: 5000,
                        ortho_scale: 10,
                        zoom: 1
                    }
                });
                return app.designSettingsSnapshot();
            }""")

            page.set_input_files('#structure-file', str(replacement_source))
            assert page.locator('#open-file-name').inner_text() == replacement_source.name
            page.click('#open-file-confirm')
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app?.state?.atoms?.metadata?.natoms === 2
                    && app.state.atoms.symbols.join(',') === 'O,C'
                    && document.getElementById('busy-overlay').classList.contains('hidden');
            }""")
            inherited_after = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const snapshot = app.designSettingsSnapshot();
                return {
                    snapshot,
                    oColor: app.renderer.atomVisualColor(0).toLowerCase(),
                    cColor: app.renderer.atomVisualColor(1).toLowerCase()
                };
            }""")
            after = inherited_after["snapshot"]
            assert after["display"]["showBonds"] is True
            assert after["display"]["showGrid"] is False
            assert after["display"]["bondMode"] == "element"
            assert after["display"]["atomRadiusScale"] == pytest.approx(1.35)
            assert after["display"]["supercell"] == [2, 1, 1]
            assert after["display"]["viewportBackground"] == "white"
            assert after["display"]["atomDisplayMode"] == "2d"
            assert after["display"]["viewRotationStepDeg"] == pytest.approx(22.5)
            assert after["display"]["lightingMode"] == "rendered"
            assert after["display"]["sunIntensity"] == pytest.approx(4.25)
            assert after["display"]["sunPosition"] == [12, -5, 15]
            assert after["display"]["sunTarget"] == [1, 2, 3]
            assert after["display"]["elementColors"] == {"O": "#2a6fdf"}
            assert after["display"]["elementRadii"]["O"] == pytest.approx(0.77)
            assert "H" not in after["display"]["elementRadii"]
            assert after["display"]["elementVisible"] == {"O": True, "C": True}
            assert after["display"]["elementBondCutoffs"]["O-O"] == pytest.approx(1.8)
            assert "H-O" not in after["display"]["elementBondCutoffs"]
            assert set(after["display"]["elementBondCutoffs"]) == {"C-C", "C-O", "O-O"}
            assert inherited_after["oColor"] == "#2a6fdf"
            assert inherited_after["cColor"] != "#2a6fdf"
            assert after["antiAliasing"] is False
            assert after["sphereQuality"] == "high"
            assert after["moveIncrement"] == pytest.approx(0.15)
            assert after["rotateIncrementDeg"] == pytest.approx(7.5)
            assert after["camera"]["projection"] == inherited_before["camera"]["projection"]
            assert after["camera"]["position"] == pytest.approx(inherited_before["camera"]["position"])
            assert after["camera"]["target"] == pytest.approx(inherited_before["camera"]["target"])
            assert after["display"]["atomicScalePixelsPerAngstrom"] == pytest.approx(
                inherited_before["display"]["atomicScalePixelsPerAngstrom"]
            )
            browser.close()
    finally:
        editor.close()


def test_rotate_direction_commensurate_snap_and_panel_focus_workflow():
    lattice = 2.46
    atoms = Atoms(
        "C4",
        scaled_positions=[
            [0.0, 0.0, 0.25],
            [1 / 3, 2 / 3, 0.25],
            [0.0, 0.0, 0.75],
            [2 / 3, 1 / 3, 0.75],
        ],
        cell=[
            [lattice, 0.0, 0.0],
            [0.5 * lattice, 0.5 * 3 ** 0.5 * lattice, 0.0],
            [0.0, 0.0, 18.0],
        ],
        pbc=[True, True, False],
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")

            canvas = page.locator('#app-viewport canvas')
            canvas.focus()
            page.keyboard.press('Control+a')
            page.wait_for_function("window.__ASE_APP__.state.selected.size === 4")

            # Tab opens a collapsed panel.  Once open, Tab remains available
            # for native form navigation; Escape commits, closes, and returns
            # keyboard focus to the viewport.
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
            page.click('[data-inspector-group="structure"]')
            page.fill('#rotate-increment', '5')
            page.keyboard.press('Tab')
            assert not page.locator('body').evaluate(
                "element => element.classList.contains('inspector-collapsed')"
            )
            page.keyboard.press('Escape')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            assert page.evaluate("document.activeElement?.tagName") == 'CANVAS'
            assert page.evaluate("window.__ASE_APP__.state.selected.size") == 4
            page.keyboard.press('r')
            assert page.evaluate("window.__ASE_APP__.transform.mode") == 'ROTATE'
            page.keyboard.press('Escape')

            # From +Z, free R and R+Z must apply the same visible clockwise
            # motion for the same clockwise pointer path.
            rotation = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                document.getElementById('rotate-increment').value = '0';
                app.readTransformSettings();
                app.alignViewToAxis('Z');
                const run = (axis) => {
                    app.enterTransformMode('ROTATE');
                    if (axis) app.transform.setAxis(axis, app.renderer.camera);
                    const pivot = app.state.rotationScreenPivot;
                    app.updateRotationFromPointer(pivot.x + 100, pivot.y);
                    app.updateRotationFromPointer(pivot.x, pivot.y + 100);
                    app.applyTransformPreview();
                    const positions = app.currentPositionsFromScene();
                    const angle = app.transform.rotationAngle;
                    app.cancelTransform();
                    return { positions, angle };
                };
                return { free: run(null), locked: run('Z') };
            }""")
            assert rotation["free"]["angle"] == pytest.approx(-math.pi / 2, abs=1e-5)
            assert rotation["locked"]["angle"] == pytest.approx(-math.pi / 2, abs=1e-5)
            assert np.asarray(rotation["free"]["positions"]) == pytest.approx(
                np.asarray(rotation["locked"]["positions"]), abs=1e-5
            )

            # Enable the cell-boundary search through the actual panel, then
            # run R+Z and wait for the backend result and rendered guide.
            canvas.focus()
            page.keyboard.press('Tab')
            page.click('[data-inspector-group="structure"]')
            page.check('#chk-commensurate-guide')
            page.keyboard.press('Escape')
            page.keyboard.press('r')
            page.keyboard.press('z')
            page.wait_for_function("window.__ASE_APP__.state.commensurateCandidates.length >= 60")
            page.wait_for_function("window.__ASE_APP__.renderer.commensurateGuideGroup.children.length > 0")
            labels = page.evaluate("""() => window.__ASE_APP__.renderer.commensurateGuideGroup.children
                .filter(object => object.isSprite)
                .map(object => object.material.map.image.getContext('2d') ? object.userData : null)
                .length""")
            assert labels > 0
            candidate_status = page.locator('#commensurate-status').inner_text()
            assert 'boundary strain' in candidate_status
            assert 'N=' in candidate_status

            snapped = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.transform.buffer = '21.2';
                app.transform.rotationAngle = app.renderer.THREE
                    ? app.renderer.THREE.MathUtils.degToRad(21.2)
                    : 21.2 * Math.PI / 180;
                app.applyTransformPreview();
                return {
                    candidate: app.state.commensurateSnappedCandidate,
                    readout: app.state.transformReadout,
                    sprites: app.renderer.commensurateGuideGroup.children.filter(object => object.isSprite).length
                };
            }""")
            assert snapped["candidate"]["targetAngleDeg"] == pytest.approx(21.7867893, abs=1e-5)
            assert "MATCH" in snapped["readout"]
            assert snapped["sprites"] > 0
            assert '21.79 deg' in page.locator('#cmd-val').inner_text()
            assert page.locator('#commensurate-candidates-readout').is_visible()
            assert page.locator('#commensurate-candidates-values .commensurate-candidate-chip').count() >= 3
            assert '21.79 deg' in page.locator(
                '#commensurate-candidates-values .commensurate-candidate-chip.active'
            ).inner_text()
            assert page.locator('#commensurate-status').inner_text().startswith('Snapped: 21.786789 deg')

            unsnapped = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.commensurateSnap = false;
                app.transform.buffer = '21.2';
                app.transform.rotationAngle = 21.2 * Math.PI / 180;
                app.applyTransformPreview();
                return {
                    candidate: app.state.commensurateSnappedCandidate,
                    readout: app.state.transformReadout
                };
            }""")
            assert unsnapped["candidate"] is None
            assert unsnapped["readout"].startswith('21.20 deg')
            page.keyboard.press('Escape')

            # The toolbar icon follows the supplied matte-sphere / lit-sphere
            # visual states rather than the former flashlight glyph.
            assert page.locator('#btn-lighting-toggle .render-sphere-off').count() == 1
            assert page.locator('#btn-lighting-toggle .render-sphere-on').count() == 1
            palette = page.evaluate("""() => {
                const sample = document.createElement('div');
                sample.style.background = 'var(--field)';
                document.body.appendChild(sample);
                const result = {
                    field: getComputedStyle(sample).backgroundColor,
                    calculator: getComputedStyle(document.getElementById('calc-device')).backgroundColor,
                    offHighlight: getComputedStyle(document.querySelector('.render-stop-off-highlight')).stopColor,
                    onLight: getComputedStyle(document.querySelector('.render-stop-on-light')).stopColor,
                    onHighlight: getComputedStyle(document.querySelector('.render-stop-on-highlight')).stopColor
                };
                sample.remove();
                return result;
            }""")
            assert palette["calculator"] == palette["field"]
            assert palette["offHighlight"] == "rgb(195, 204, 200)"
            assert palette["onLight"] == "rgb(138, 229, 211)"
            assert palette["onHighlight"] == "rgb(255, 240, 196)"
            page.click('#btn-lighting-toggle')
            page.select_option('#lighting-mode', 'studio-shadow')
            page.wait_for_function("document.getElementById('lighting-widget').dataset.mode === 'studio-shadow'")
            assert page.locator('.render-sphere-on').evaluate("element => getComputedStyle(element).display") == 'block'
            assert page.locator('.render-sphere-shadow').evaluate("element => getComputedStyle(element).display") == 'block'
            browser.close()
    finally:
        editor.close()


def test_export_preview_is_screen_fixed_and_matches_the_png_render():
    atoms = molecule("H2O")
    atoms.set_cell([12.0, 10.0, 8.0])
    atoms.center()
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            _expand_inspector(page)
            page.click('[data-inspector-group="output"]')
            page.fill('#image-width', '1600')
            page.fill('#image-height', '800')
            page.click('#btn-preview-image')
            page.wait_for_function("window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[0] === 1600")

            initial = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const frame = document.getElementById('export-preview-frame').getBoundingClientRect();
                const inspector = document.getElementById('inspector').getBoundingClientRect();
                const topBar = document.getElementById('top-bar').getBoundingClientRect();
                const commandBar = document.getElementById('command-bar').getBoundingClientRect();
                const preview = app.renderer.lastExportPreview;
                const direct = app.renderer.exportCameraSetup(1600, 800, app.imagePreviewOptions());
                return {
                    pressed: document.getElementById('btn-preview-image').getAttribute('aria-pressed'),
                    hidden: document.getElementById('export-preview-frame').classList.contains('hidden'),
                    frame: [frame.left, frame.top, frame.width, frame.height],
                    safeBounds: [topBar.bottom, inspector.left, commandBar.top],
                    frameAspect: frame.width / frame.height,
                    output: preview.outputSize,
                    render: preview.renderSize,
                    offset: preview.offset,
                    content: [
                        preview.contentRect.left,
                        preview.contentRect.bottom,
                        preview.contentRect.width,
                        preview.contentRect.height
                    ],
                    previewProjection: preview.cameraProjection,
                    directProjection: direct.camera.projectionMatrix.elements.slice(),
                    previewCount: app.renderer.previewRenderCount
                };
            }""")
            assert initial["pressed"] == "true"
            assert initial["hidden"] is False
            assert initial["frameAspect"] == pytest.approx(2.0, abs=0.004)
            assert initial["output"] == [1600, 800]
            assert initial["frame"][1] >= initial["safeBounds"][0]
            assert initial["frame"][0] + initial["frame"][2] <= initial["safeBounds"][1]
            assert initial["frame"][1] + initial["frame"][3] <= initial["safeBounds"][2]
            assert initial["previewProjection"] == pytest.approx(initial["directProjection"])
            assert initial["render"] == [1600, 800]
            assert initial["offset"] == [0, 0]
            assert initial["content"][2:] == pytest.approx(initial["frame"][2:], abs=1.0)

            page.fill('#image-width', '800')
            page.fill('#image-height', '1600')
            page.wait_for_function("window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[1] === 1600")
            portrait = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const frame = document.getElementById('export-preview-frame').getBoundingClientRect();
                const preview = app.renderer.lastExportPreview;
                return {
                    aspect: frame.width / frame.height,
                    render: preview.renderSize,
                    offset: preview.offset,
                    content: [preview.contentRect.width, preview.contentRect.height],
                    frame: [frame.width, frame.height]
                };
            }""")
            assert portrait["aspect"] == pytest.approx(0.5, abs=0.004)
            assert portrait["render"] == [800, 1600]
            assert portrait["offset"] == [0, 0]
            assert portrait["content"] == pytest.approx(portrait["frame"], abs=1.0)

            # A square output changes the cloned camera gate instead of
            # letterboxing the live viewport inside the preview frame.
            page.fill('#image-width', '1920')
            page.fill('#image-height', '1920')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.join(',') === '1920,1920'"
            )
            square = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const preview = app.renderer.lastExportPreview;
                const setup = app.renderer.exportCameraSetup(1920, 1920, app.imagePreviewOptions());
                const camera = setup.camera;
                return {
                    render: preview.renderSize,
                    offset: preview.offset,
                    cameraAspect: camera.isPerspectiveCamera
                        ? camera.aspect
                        : Math.abs((camera.right - camera.left) / (camera.top - camera.bottom)),
                    content: [preview.contentRect.width, preview.contentRect.height],
                    frame: [preview.frameRect.width, preview.frameRect.height]
                };
            }""")
            assert square["render"] == [1920, 1920]
            assert square["offset"] == [0, 0]
            assert square["cameraAspect"] == pytest.approx(1.0)
            assert square["content"] == pytest.approx(square["frame"], abs=1.0)

            page.fill('#image-width', '1600')
            page.fill('#image-height', '800')
            page.wait_for_function("window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[0] === 1600")

            # Zoom affects the export camera and atoms inside the frame, but
            # the preview rectangle itself stays fixed in screen coordinates.
            zoomed = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                camera.zoom *= 0.62;
                camera.updateProjectionMatrix();
                app.renderer.requestRender();
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                const frame = document.getElementById('export-preview-frame').getBoundingClientRect();
                return {
                    frame: [frame.left, frame.top, frame.width, frame.height],
                    projection: app.renderer.lastExportPreview.cameraProjection,
                    previewCount: app.renderer.previewRenderCount
                };
            }""")
            assert zoomed["frame"] == pytest.approx(initial["frame"], abs=0.01)
            assert zoomed["projection"] != pytest.approx(initial["previewProjection"])
            assert zoomed["previewCount"] > initial["previewCount"]

            page.click('[data-inspector-group="display"]')
            page.fill('#atomic-scale', '40')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 40) < 0.02")
            scale_40 = page.evaluate("""() => ({
                zoom: window.__ASE_APP__.renderer.camera.zoom,
                scale: window.__ASE_APP__.renderer.currentPixelsPerAngstrom()
            })""")
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")
            scale_80 = page.evaluate("""() => ({
                zoom: window.__ASE_APP__.renderer.camera.zoom,
                scale: window.__ASE_APP__.renderer.currentPixelsPerAngstrom(),
                input: Number(document.getElementById('atomic-scale').value),
                span: document.getElementById('atomic-scale-span').textContent
            })""")
            assert scale_40["scale"] == pytest.approx(40, abs=0.02)
            assert scale_80["scale"] == pytest.approx(80, abs=0.02)
            assert scale_80["zoom"] == pytest.approx(scale_40["zoom"] * 2, rel=2e-3)
            assert scale_80["input"] == pytest.approx(80, abs=0.02)
            assert "Viewport span:" in scale_80["span"]

            page.locator('#atomic-scale').press('Tab')
            wheel_sync = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.controls.doZoom(-120);
                return {
                    scale: app.renderer.currentPixelsPerAngstrom(),
                    input: Number(document.getElementById('atomic-scale').value)
                };
            }""")
            assert wheel_sync["scale"] > 80
            assert wheel_sync["input"] == pytest.approx(wheel_sync["scale"], rel=2e-3)
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")

            persisted = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const snapshot = app.designSettingsSnapshot();
                app.renderer.setPixelsPerAngstrom(35);
                app.applyDesignSettings(snapshot);
                return {
                    scale: app.renderer.currentPixelsPerAngstrom(),
                    saved: snapshot.display.atomicScalePixelsPerAngstrom,
                    framing: snapshot.display.imageFramingMode,
                    hasLegacyScale: Object.hasOwn(snapshot.display, 'imagePixelsPerAngstrom')
                };
            }""")
            assert persisted["scale"] == pytest.approx(80, abs=0.02)
            assert persisted["saved"] == pytest.approx(80, abs=0.02)
            assert persisted["framing"] == "viewport"
            assert persisted["hasLegacyScale"] is False

            page.select_option('#projection-mode', 'perspective')
            page.wait_for_function("window.__ASE_APP__.renderer.camera.isPerspectiveCamera")
            page.fill('#atomic-scale', '50')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 50) < 0.02")
            perspective_50 = page.evaluate(
                "window.__ASE_APP__.renderer.camera.position.distanceTo(window.__ASE_APP__.renderer.controls.target)"
            )
            page.fill('#atomic-scale', '100')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 100) < 0.02")
            perspective_100 = page.evaluate(
                "window.__ASE_APP__.renderer.camera.position.distanceTo(window.__ASE_APP__.renderer.controls.target)"
            )
            assert perspective_100 == pytest.approx(perspective_50 * 0.5, rel=2e-3)
            page.select_option('#projection-mode', 'orthographic')
            page.wait_for_function("window.__ASE_APP__.renderer.camera.isOrthographicCamera")
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")
            page.click('[data-inspector-group="output"]')

            physical = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const profile = app.currentImageExportProfile();
                app.setImageExportProfile({
                    ...profile,
                    options: {
                        ...profile.options,
                        scaleMode: 'physical',
                        pixelsPerAngstrom: 80
                    }
                });
                app.renderer.renderNow();
                const setup = app.renderer.exportCameraSetup(1600, 800, app.imagePreviewOptions());
                const camera = setup.camera;
                const result = {
                    mode: app.renderer.lastExportPreview.scaleMode,
                    pixelsPerAngstrom: app.renderer.lastExportPreview.pixelsPerAngstrom,
                    span: [
                        (camera.right - camera.left) / camera.zoom,
                        (camera.top - camera.bottom) / camera.zoom
                    ],
                    projection: app.renderer.lastExportPreview.cameraProjection,
                    directProjection: camera.projectionMatrix.elements.slice()
                };
                app.setImageExportProfile({
                    ...profile,
                    options: { ...profile.options, scaleMode: 'viewport' }
                });
                app.renderer.renderNow();
                return result;
            }""")
            assert physical["mode"] == "physical"
            assert physical["pixelsPerAngstrom"] == pytest.approx(80)
            assert physical["span"] == pytest.approx([20.0, 10.0])
            assert physical["projection"] == pytest.approx(physical["directProjection"])

            # Use the actual CSS frame dimensions as output pixels, then compare
            # the rendered inset and PNG. Both must share camera and scene state.
            frame_width = round(zoomed["frame"][2])
            frame_height = round(zoomed["frame"][3])
            page.fill('#image-width', str(frame_width))
            page.fill('#image-height', str(frame_height))
            page.wait_for_function(
                "([w, h]) => window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[0] === w && "
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[1] === h",
                arg=[frame_width, frame_height],
            )
            comparison = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.showGrid = false;
                app.state.display.showAxes = false;
                app.renderer.setDisplayOptions(app.state.display, { rebuild: false });
                app.syncImageExportPreview();
                app.renderer.renderNow();

                const renderer = app.renderer;
                const rect = renderer.lastExportPreview.frameRect;
                const width = renderer.lastExportPreview.outputSize[0];
                const height = renderer.lastExportPreview.outputSize[1];
                const sourceUrl = renderer.domElement.toDataURL('image/png');
                const loadImage = url => new Promise((resolve, reject) => {
                    const image = new Image();
                    image.onload = () => resolve(image);
                    image.onerror = reject;
                    image.src = url;
                });
                const source = await loadImage(sourceUrl);
                const ratioX = source.naturalWidth / renderer.domElement.clientWidth;
                const ratioY = source.naturalHeight / renderer.domElement.clientHeight;
                const previewCanvas = document.createElement('canvas');
                previewCanvas.width = width;
                previewCanvas.height = height;
                const previewContext = previewCanvas.getContext('2d', { willReadFrequently: true });
                previewContext.drawImage(
                    source,
                    rect.left * ratioX,
                    rect.top * ratioY,
                    rect.width * ratioX,
                    rect.height * ratioY,
                    0,
                    0,
                    width,
                    height
                );

                const options = app.imagePreviewOptions();
                const exportedUrl = renderer.exportPNG(width, height, options);
                const exported = await loadImage(exportedUrl);
                const exportCanvas = document.createElement('canvas');
                exportCanvas.width = width;
                exportCanvas.height = height;
                const exportContext = exportCanvas.getContext('2d', { willReadFrequently: true });
                exportContext.drawImage(exported, 0, 0);
                const previewPixels = previewContext.getImageData(0, 0, width, height).data;
                const exportPixels = exportContext.getImageData(0, 0, width, height).data;
                let total = 0;
                let maximum = 0;
                for (let index = 0; index < previewPixels.length; index += 1) {
                    const difference = Math.abs(previewPixels[index] - exportPixels[index]);
                    total += difference;
                    maximum = Math.max(maximum, difference);
                }
                return {
                    meanAbsoluteDifference: total / previewPixels.length,
                    maximumDifference: maximum,
                    size: [width, height],
                    frame: [rect.left, rect.top, rect.width, rect.height],
                    outputAspect: width / height,
                    frameAspect: rect.width / rect.height
                };
            }""")
            assert comparison["size"] == [frame_width, frame_height]
            assert comparison["frameAspect"] == pytest.approx(comparison["outputAspect"], abs=0.004)
            assert comparison["meanAbsoluteDifference"] < 1.0

            # The preview uses the existing demand renderer and must not create
            # a hidden animation loop while the scene is idle.
            idle_start = page.evaluate("window.__ASE_APP__.renderer.previewRenderCount")
            time.sleep(0.3)
            idle_end = page.evaluate("window.__ASE_APP__.renderer.previewRenderCount")
            assert idle_end == idle_start

            page.click('#btn-preview-image')
            page.wait_for_function("window.__ASE_APP__.renderer.domElement.dataset.exportPreview === 'false'")
            assert page.locator('#export-preview-frame').is_hidden()
            browser.close()
    finally:
        editor.close()


def test_image_export_modal_is_the_authoritative_retina_preview(tmp_path):
    atoms = molecule("C6H6")
    atoms.set_cell([12.0, 12.0, 8.0])
    atoms.center()
    atoms.set_pbc(True)
    atoms = atoms.repeat((2, 2, 1))
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        show_bonds=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                accept_downloads=True,
            )
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 48")
            _expand_inspector(page)
            page.click('[data-inspector-group="output"]')
            page.fill('#image-width', '1280')
            page.fill('#image-height', '720')
            page.uncheck('#export-include-cell')
            page.wait_for_function(
                "window.__ASE_APP__.state.imageExportProfile?.options?.includeCell === false"
            )
            page.click('#btn-preview-image')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.join(',') === '1280,720'"
            )

            page.click('#btn-export-image')
            assert page.locator('#export-cell').is_checked() is False
            page.fill('#export-width', '640')
            page.fill('#export-height', '640')
            page.uncheck('#export-grid')
            page.uncheck('#export-axes')
            page.select_option('#export-sphere-quality', 'medium')
            page.fill('#export-smoothness-scale', '1.30')
            page.select_option('#export-render-mode', 'studio-shadow')
            page.fill('#export-sun-intensity', '3.75')
            page.fill('#export-sun-position-0', '11.5')
            page.fill('#export-sun-position-1', '-7.25')
            page.fill('#export-sun-position-2', '16.0')
            page.fill('#export-sun-target-0', '1.25')
            page.fill('#export-sun-target-1', '0.50')
            page.fill('#export-sun-target-2', '-0.75')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.exportPreview?.width === 640 && "
                "window.__ASE_APP__.renderer.exportPreview?.height === 640 && "
                "window.__ASE_APP__.renderer.exportPreview?.options?.renderMode === 'studio-shadow'"
            )

            live = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const cellVisibleBefore = app.renderer.cellGroup.visible;
                const sceneState = app.renderer.beginExportScene(app.state.imageExportProfile.options);
                const cellVisibleDuring = app.renderer.cellGroup.visible;
                sceneState.restore();
                app.renderer.renderNow();
                return {
                    panelSize: [
                        Number(document.getElementById('image-width').value),
                        Number(document.getElementById('image-height').value)
                    ],
                    frameSize: [
                        Number(document.getElementById('export-preview-frame').dataset.outputWidth),
                        Number(document.getElementById('export-preview-frame').dataset.outputHeight)
                    ],
                    profile: app.state.imageExportProfile,
                    preview: app.renderer.exportPreview,
                    previewProjection: app.renderer.lastExportPreview.cameraProjection,
                    directProjection: app.renderer.exportCameraSetup(
                        640,
                        640,
                        app.state.imageExportProfile.options
                    ).camera.projectionMatrix.elements.slice(),
                    cellVisibility: [
                        cellVisibleBefore,
                        cellVisibleDuring,
                        app.renderer.cellGroup.visible
                    ]
                };
            }""")
            assert live["panelSize"] == [640, 640]
            assert live["frameSize"] == [640, 640]
            assert live["profile"]["width"] == 640
            assert live["profile"]["height"] == 640
            assert live["profile"]["options"] == live["preview"]["options"]
            assert live["profile"]["options"]["includeGrid"] is False
            assert live["profile"]["options"]["includeAxes"] is False
            assert live["profile"]["options"]["includeCell"] is False
            assert live["cellVisibility"] == [True, False, True]
            assert live["profile"]["options"]["sphereQuality"] == "medium"
            assert live["profile"]["options"]["sphereQualityScale"] == pytest.approx(1.3)
            assert live["profile"]["options"]["renderModeSelection"] == "studio-shadow"
            assert live["profile"]["options"]["sunIntensity"] == pytest.approx(3.75)
            assert live["profile"]["options"]["sunPosition"] == pytest.approx([11.5, -7.25, 16.0])
            assert live["profile"]["options"]["sunTarget"] == pytest.approx([1.25, 0.5, -0.75])
            assert live["previewProjection"] == pytest.approx(live["directProjection"])

            with page.expect_download(timeout=60_000) as download_info:
                page.click('#modal-export-image')
            download = download_info.value
            output = tmp_path / download.suggested_filename
            download.save_as(output)
            page.wait_for_function(
                "document.getElementById('modal-container').classList.contains('hidden') && "
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.join(',') === '640,640'"
            )

            exported = Image.open(output).convert('RGBA')
            assert exported.size == (640, 640)
            contract = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.renderNow();
                return {
                    profile: app.state.imageExportProfile,
                    preview: app.renderer.lastExportPreview,
                    capture: app.renderer.lastExportCapture
                };
            }""")
            assert contract["capture"]["outputSize"] == [640, 640]
            assert contract["capture"]["options"] == contract["profile"]["options"]
            assert contract["preview"]["options"] == contract["profile"]["options"]
            assert contract["capture"]["cameraProjection"] == pytest.approx(
                contract["preview"]["cameraProjection"]
            )
            assert contract["capture"]["cameraPosition"] == pytest.approx(
                contract["preview"]["cameraPosition"]
            )
            assert contract["capture"]["cameraQuaternion"] == pytest.approx(
                contract["preview"]["cameraQuaternion"]
            )

            preview_url = page.evaluate("""async () => {
                const renderer = window.__ASE_APP__.renderer;
                renderer.renderNow();
                const rect = renderer.lastExportPreview.frameRect;
                const sourceUrl = renderer.domElement.toDataURL('image/png');
                const source = await new Promise((resolve, reject) => {
                    const image = new Image();
                    image.onload = () => resolve(image);
                    image.onerror = reject;
                    image.src = sourceUrl;
                });
                const ratioX = source.naturalWidth / renderer.domElement.clientWidth;
                const ratioY = source.naturalHeight / renderer.domElement.clientHeight;
                const canvas = document.createElement('canvas');
                canvas.width = 640;
                canvas.height = 640;
                const context = canvas.getContext('2d');
                context.drawImage(
                    source,
                    rect.left * ratioX,
                    rect.top * ratioY,
                    rect.width * ratioX,
                    rect.height * ratioY,
                    0,
                    0,
                    640,
                    640
                );
                return canvas.toDataURL('image/png');
            }""")
            preview_bytes = base64.b64decode(preview_url.split(',', 1)[1])
            preview = Image.open(io.BytesIO(preview_bytes)).convert('RGBA')
            preview_pixels = np.asarray(preview, dtype=np.int16)
            export_pixels = np.asarray(exported, dtype=np.int16)
            absolute_difference = np.abs(preview_pixels - export_pixels)
            assert absolute_difference.mean() < 3.0
            assert np.quantile(absolute_difference, 0.99) < 24

            page.click('#btn-export-image')
            page.fill('#export-width', '768')
            page.fill('#export-height', '432')
            page.check('#export-transparent')
            page.select_option('#export-render-mode', 'modeling')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.exportPreview?.width === 768 && "
                "window.__ASE_APP__.renderer.exportPreview?.height === 432 && "
                "window.__ASE_APP__.renderer.exportPreview?.options?.transparentBackground === true"
            )
            with page.expect_download(timeout=60_000) as transparent_download_info:
                page.click('#modal-export-image')
            transparent_download = transparent_download_info.value
            transparent_output = tmp_path / f"transparent-{transparent_download.suggested_filename}"
            transparent_download.save_as(transparent_output)
            transparent_image = Image.open(transparent_output).convert('RGBA')
            assert transparent_image.size == (768, 432)
            transparent_pixels = np.asarray(transparent_image)
            assert transparent_pixels[0, 0, 3] == 0
            transparent_contract = page.evaluate("""() => ({
                profile: window.__ASE_APP__.state.imageExportProfile,
                preview: window.__ASE_APP__.renderer.lastExportPreview,
                capture: window.__ASE_APP__.renderer.lastExportCapture
            })""")
            assert transparent_contract["profile"]["options"]["transparentBackground"] is True
            assert transparent_contract["capture"]["options"] == transparent_contract["profile"]["options"]
            assert transparent_contract["preview"]["options"] == transparent_contract["profile"]["options"]
            assert transparent_contract["capture"]["cameraProjection"] == pytest.approx(
                transparent_contract["preview"]["cameraProjection"]
            )

            context.close()
            browser.close()
    finally:
        editor.close()


def test_trajectory_video_export_downloads_preview_matched_mov(tmp_path):
    first = molecule("H2O")
    first.set_cell([10.0, 10.0, 10.0])
    first.center()
    frames = [first]
    for shift in (0.35, 0.70):
        frame = first.copy()
        frame.positions[1:, 0] += shift
        frames.append(frame)

    port = find_free_port()
    editor = view(
        frames,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800}, accept_downloads=True)
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 3")

            options = {
                "width": 320,
                "height": 256,
                "fps": 6,
                "format": "mov",
                "transparentBackground": False,
                "backgroundColor": "#ffffff",
                "includeGrid": False,
                "includeAxes": False,
                "scaleMode": "viewport",
                "pixelsPerAngstrom": 70,
                "sphereQuality": "medium",
                "sphereQualityScale": 1,
                "renderMode": "modeling",
                "sunIntensity": 2.2,
                "sunPosition": [8, -10, 14],
                "sunTarget": [0, 0, 0],
            }
            with page.expect_download(timeout=60_000) as download_info:
                page.evaluate("options => window.__ASE_APP__.exportTrajectoryVideo(options)", options)
            download = download_info.value
            output = tmp_path / download.suggested_filename
            download.save_as(output)

            assert output.suffix == ".mov"
            assert output.stat().st_size > 1000
            state = page.evaluate("""() => ({
                frame: window.__ASE_APP__.state.atoms.metadata.current_frame,
                captureActive: window.__ASE_APP__.renderer.exportCaptureActive,
                canvasWidth: window.__ASE_APP__.renderer.domElement.width,
                canvasHeight: window.__ASE_APP__.renderer.domElement.height
            })""")
            assert state["frame"] == 0
            assert state["captureActive"] is False
            assert state["canvasWidth"] > 320
            assert state["canvasHeight"] > 240

            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            probe = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            assert "h264" in probe.stderr.lower()
            assert "320x256" in probe.stderr

            decoded = imageio_ffmpeg.read_frames(str(output), pix_fmt="rgb24")
            metadata = next(decoded)
            decoded_frames = list(decoded)
            assert metadata["size"] == (320, 256)
            assert len(decoded_frames) == 3
            assert len({hashlib.sha1(frame).hexdigest() for frame in decoded_frames}) == 3

            first_frame = tmp_path / "video-first-frame.png"
            subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(output), "-frames:v", "1", str(first_frame),
                ],
                check=True,
                capture_output=True,
            )
            from PIL import Image

            with Image.open(first_frame).convert("RGB") as image:
                assert image.size == (320, 256)
                corner = image.getpixel((2, 2))
            assert min(corner) >= 245
            browser.close()
    finally:
        editor.close()


def test_sidebar_sun_renderer_export_and_periodic_bond_contract():
    atoms = Atoms(
        "HH",
        positions=[[0.35, 0.0, 0.0], [9.65, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            initial = page.evaluate("""() => ({
                periodic: window.__ASE_APP__.state.display.showPeriodicBonds,
                bonds: window.__ASE_APP__.renderer.bondPairs.length,
                lighting: window.__ASE_APP__.renderer.lightingOptions.lightingMode,
                shadows: window.__ASE_APP__.renderer.renderer.shadowMap.enabled
            })""")
            assert initial == {
                "periodic": False,
                "bonds": 0,
                "lighting": "modeling",
                "shadows": False,
            }

            assert page.locator('body').evaluate("element => element.classList.contains('inspector-collapsed')")
            assert page.locator('#btn-inspector-collapse').get_attribute('aria-expanded') == 'false'
            assert page.locator('#btn-inspector-collapse').get_attribute('title') == 'Expand control panel'
            assert page.locator('#btn-inspector-collapse .inspector-edge-chevron').count() == 1
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            assert page.locator('#inspector').evaluate("element => Math.round(element.getBoundingClientRect().width)") == 0

            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 336")
            assert page.locator('#btn-inspector-collapse').get_attribute('aria-expanded') == 'true'
            assert page.locator('#btn-inspector-collapse').get_attribute('title') == 'Collapse control panel'
            edge_geometry = page.evaluate("""() => {
                const button = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                return {
                    buttonRight: button.right,
                    panelLeft: panel.left,
                    verticalCenterDelta: Math.abs(
                        (button.top + button.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert edge_geometry['buttonRight'] == pytest.approx(edge_geometry['panelLeft'], abs=1.5)
            assert edge_geometry['verticalCenterDelta'] <= 1.5

            page.click('[data-inspector-group="display"]')
            assert page.locator('[data-panel="view"]').is_visible()
            assert not page.locator('[data-panel="structure-info"]').is_visible()
            for panel in ('view', 'appearance', 'bonding'):
                assert page.locator(f'[data-panel="{panel}"]').evaluate("element => element.open")
            page.click('[data-inspector-group="output"]')
            assert page.locator('[data-panel="project"]').is_visible()
            assert page.locator('[data-panel="settings"]').is_visible()
            assert 'complete working structure' in page.locator('[data-panel="project"] .panel-note').inner_text()
            assert 'coordinates' in page.locator('[data-panel="settings"] .panel-note').inner_text()
            page.click('[data-inspector-group="display"]')
            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Escape')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")

            _open_panel(page, 'bonding')
            page.check('#chk-periodic-bonds')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")
            assert page.locator('#app-viewport canvas').get_attribute('data-periodic-bonds') == 'true'

            lighting_icon = page.locator('#btn-lighting-toggle .render-light-icon')
            assert lighting_icon.is_visible()
            icon_box = lighting_icon.bounding_box()
            assert icon_box is not None
            assert icon_box['width'] == pytest.approx(31, abs=1)
            assert icon_box['height'] == pytest.approx(29, abs=1)
            viewport_tools = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const calculator = document.getElementById('calc-controls').getBoundingClientRect();
                const actionGroup = document.querySelector('.action-group').getBoundingClientRect();
                return {
                    triggerLeft: trigger.left,
                    calculatorRight: calculator.right,
                    contained: trigger.left >= actionGroup.left && trigger.right <= actionGroup.right,
                    headerCenterDelta: Math.abs(
                        (trigger.top + trigger.height / 2) -
                        (actionGroup.top + actionGroup.height / 2)
                    )
                };
            }""")
            assert viewport_tools['triggerLeft'] >= viewport_tools['calculatorRight'] + 5
            assert viewport_tools['contained'] is True
            assert viewport_tools['headerCenterDelta'] <= 2
            page.click('#btn-lighting-toggle')
            lighting_panel_geometry = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const card = document.getElementById('lighting-card').getBoundingClientRect();
                const header = document.getElementById('top-bar').getBoundingClientRect();
                return {
                    triggerRight: trigger.right,
                    cardRight: card.right,
                    cardTop: card.top,
                    headerBottom: header.bottom
                };
            }""")
            assert lighting_panel_geometry['cardRight'] == pytest.approx(lighting_panel_geometry['triggerRight'], abs=1.5)
            assert lighting_panel_geometry['cardTop'] >= lighting_panel_geometry['headerBottom'] + 5
            page.select_option('#lighting-mode', 'studio-shadow')
            page.check('#chk-sun-gizmo')
            page.fill('#sun-position-x', '3')
            page.fill('#sun-position-y', '-3')
            page.fill('#sun-position-z', '4')
            page.wait_for_function("window.__ASE_APP__.renderer.sunGizmoGroup.visible")
            shadow_state = page.evaluate("""() => ({
                mode: window.__ASE_APP__.renderer.lightingOptions.lightingMode,
                shadowMap: window.__ASE_APP__.renderer.renderer.shadowMap.enabled,
                sunShadow: window.__ASE_APP__.renderer.studioSunLight.castShadow,
                modelingLights: window.__ASE_APP__.renderer.modelingLightGroup.visible,
                studioLights: window.__ASE_APP__.renderer.studioLightGroup.visible
            })""")
            assert shadow_state == {
                "mode": "studio-shadow",
                "shadowMap": True,
                "sunShadow": True,
                "modelingLights": False,
                "studioLights": True,
            }
            page.click('#btn-lighting-close')

            handle = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const point = app.renderer.sunGizmoGroup.userData.positionHandle.position.clone();
                point.project(app.renderer.camera);
                const rect = app.renderer.domElement.getBoundingClientRect();
                return {
                    x: rect.left + (point.x + 1) * rect.width / 2,
                    y: rect.top + (-point.y + 1) * rect.height / 2
                };
            }""")
            before_drag = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            page.mouse.move(handle["x"], handle["y"])
            page.mouse.down()
            page.mouse.move(handle["x"] + 44, handle["y"] - 28, steps=6)
            page.mouse.up()
            after_direct_drag = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice(),
                selected: window.__ASE_APP__.state.sunSelected,
                rendererSelected: window.__ASE_APP__.renderer.sunGizmoSelected
            })""")
            assert after_direct_drag["position"] == pytest.approx(before_drag["position"])
            assert after_direct_drag["target"] == pytest.approx(before_drag["target"])
            assert after_direct_drag["selected"] == "source"
            assert after_direct_drag["rendererSelected"] == "source"

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('2')
            page.keyboard.press('Enter')
            after_move = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice(),
                mode: window.__ASE_APP__.transform.mode
            })""")
            assert after_move["position"] == pytest.approx([
                before_drag["position"][0] + 2,
                before_drag["position"][1],
                before_drag["position"][2],
            ])
            assert after_move["target"] == pytest.approx([
                before_drag["target"][0] + 2,
                before_drag["target"][1],
                before_drag["target"][2],
            ])
            assert after_move["mode"] == 'IDLE'

            direction_before_rotate = [
                after_move["target"][axis] - after_move["position"][axis]
                for axis in range(3)
            ]
            page.keyboard.press('r')
            page.keyboard.press('z')
            page.keyboard.type('90')
            page.keyboard.press('Enter')
            after_rotate = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            direction_after_rotate = [
                after_rotate["target"][axis] - after_rotate["position"][axis]
                for axis in range(3)
            ]
            assert after_rotate["position"] == pytest.approx(after_move["position"])
            assert direction_after_rotate == pytest.approx([
                -direction_before_rotate[1],
                direction_before_rotate[0],
                direction_before_rotate[2],
            ])

            page.keyboard.press('r')
            page.keyboard.press('z')
            mouse_rotation = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const before = app.renderer.lightingOptions.sunTarget.map(
                    (value, axis) => value - app.renderer.lightingOptions.sunPosition[axis]
                );
                const pivot = app.state.rotationScreenPivot;
                app.updateRotationFromPointer(pivot.x + 90, pivot.y);
                app.updateRotationFromPointer(pivot.x, pivot.y + 90);
                app.applyTransformPreview();
                const after = app.renderer.lightingOptions.sunTarget.map(
                    (value, axis) => value - app.renderer.lightingOptions.sunPosition[axis]
                );
                return {
                    before,
                    after,
                    pointerAngle: app.transform.rotationAngle,
                    sunAngle: app.sunTransformRotation().angle,
                };
            }""")
            assert mouse_rotation["pointerAngle"] == pytest.approx(-1.57079632679, abs=1e-5)
            assert mouse_rotation["sunAngle"] == pytest.approx(1.57079632679, abs=1e-5)
            assert mouse_rotation["after"] == pytest.approx([
                -mouse_rotation["before"][1],
                mouse_rotation["before"][0],
                mouse_rotation["before"][2],
            ])
            page.keyboard.press('Escape')

            page.evaluate("window.__ASE_APP__.setSunSelected('target')")
            target_selection = page.evaluate("""() => ({
                selected: window.__ASE_APP__.state.sunSelected,
                rendererSelected: window.__ASE_APP__.renderer.sunGizmoSelected
            })""")
            assert target_selection == {"selected": "target", "rendererSelected": "target"}

            page.keyboard.press('g')
            page.keyboard.press('y')
            page.keyboard.type('3')
            page.keyboard.press('Enter')
            after_target_move = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            assert after_target_move["position"] == pytest.approx(after_rotate["position"])
            assert after_target_move["target"] == pytest.approx([
                after_rotate["target"][0],
                after_rotate["target"][1] + 3,
                after_rotate["target"][2],
            ])

            direction_before_target_rotate = [
                after_target_move["target"][axis] - after_target_move["position"][axis]
                for axis in range(3)
            ]
            page.keyboard.press('r')
            target_rotate_pivot = page.evaluate("window.__ASE_APP__.transform.pivot.toArray()")
            assert target_rotate_pivot == pytest.approx(after_target_move["position"])
            page.keyboard.press('z')
            page.keyboard.type('90')
            page.keyboard.press('Enter')
            after_target_rotate = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            direction_after_target_rotate = [
                after_target_rotate["target"][axis] - after_target_rotate["position"][axis]
                for axis in range(3)
            ]
            assert after_target_rotate["position"] == pytest.approx(after_target_move["position"])
            assert direction_after_target_rotate == pytest.approx([
                -direction_before_target_rotate[1],
                direction_before_target_rotate[0],
                direction_before_target_rotate[2],
            ])

            page.keyboard.press('g')
            page.keyboard.press('z')
            page.keyboard.type('2')
            page.keyboard.press('Escape')
            after_cancel = page.evaluate("window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()")
            assert after_cancel == pytest.approx(after_target_rotate["target"])

            directional_shadow = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const originalPositions = window.__ASE_APP__.state.atoms.positions.map(position => position.slice());
                const shiftedPositions = originalPositions.map(([x, y, z]) => [x + 120, y - 80, z + 45]);
                renderer.updatePositions(shiftedPositions);
                renderer.fitSunShadowCamera();
                const bounds = renderer.lightingStructureBounds();
                const center = bounds.getCenter(renderer.studioSunTarget.position.clone());
                const semanticDirection = renderer.studioSunTarget.position.clone()
                    .fromArray(renderer.lightingOptions.sunTarget)
                    .sub(renderer.studioSunLight.position.clone().fromArray(renderer.lightingOptions.sunPosition))
                    .normalize();
                const effectiveDirection = renderer.studioSunTarget.position.clone()
                    .sub(renderer.studioSunLight.position).normalize();
                const camera = renderer.studioSunLight.shadow.camera;
                camera.updateMatrixWorld(true);
                const inside = renderer.boxCorners(bounds).every(corner => {
                    const point = corner.clone().applyMatrix4(camera.matrixWorldInverse);
                    return point.x >= camera.left && point.x <= camera.right &&
                        point.y >= camera.bottom && point.y <= camera.top &&
                        -point.z >= camera.near && -point.z <= camera.far;
                });
                const result = {
                    directional: renderer.studioSunLight.isDirectionalLight,
                    center: center.toArray(),
                    effectiveTarget: renderer.studioSunTarget.position.toArray(),
                    semanticDirection: semanticDirection.toArray(),
                    effectiveDirection: effectiveDirection.toArray(),
                    inside
                };
                renderer.updatePositions(originalPositions);
                return result;
            }""")
            assert directional_shadow["directional"] is True
            assert max(abs(value) for value in directional_shadow["center"]) > 40
            assert directional_shadow["effectiveTarget"] == pytest.approx(directional_shadow["center"])
            assert directional_shadow["effectiveDirection"] == pytest.approx(
                directional_shadow["semanticDirection"]
            )
            assert directional_shadow["inside"] is True
            lighting_export = page.evaluate("window.__ASE_APP__.currentLightingForExport()")
            assert lighting_export["mode"] == "studio-shadow"
            assert lighting_export["intensity"] == pytest.approx(2.2)
            assert lighting_export["position"] == pytest.approx(after_target_rotate["position"])
            assert lighting_export["target"] == pytest.approx(after_target_rotate["target"])
            assert lighting_export["color"] == pytest.approx([1.0, 0.960784, 0.87451])

            export_contract = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const liveCamera = renderer.camera;
                const before = {
                    position: liveCamera.position.toArray(),
                    projection: liveCamera.projectionMatrix.elements.slice()
                };
                const viewport = renderer.exportCameraSetup(640, 640, { scaleMode: 'viewport' });
                const physical = renderer.exportCameraSetup(1000, 500, {
                    scaleMode: 'physical',
                    pixelsPerAngstrom: 100
                });
                const originalGeometry = renderer.atomMeshes.children[0].geometry;
                const dataUrl = renderer.exportPNG(640, 360, {
                    renderMode: 'studio-shadow',
                    sunIntensity: 2.6,
                    sunPosition: [4, -5, 7],
                    sunTarget: [0, 0, 0],
                    includeGrid: false,
                    includeAxes: false,
                    scaleMode: 'viewport',
                    sphereQuality: 'ultra',
                    sphereQualityScale: 1.5
                });
                return {
                    prefix: dataUrl.slice(0, 22),
                    dataUrl,
                    cloned: viewport.camera !== liveCamera,
                    viewportAspect: viewport.camera.isPerspectiveCamera
                        ? viewport.camera.aspect
                        : Math.abs(
                            (viewport.camera.right - viewport.camera.left) /
                            (viewport.camera.top - viewport.camera.bottom)
                        ),
                    viewportRender: [viewport.renderWidth, viewport.renderHeight],
                    viewportOffset: [viewport.offsetX, viewport.offsetY],
                    physicalSpan: [
                        (physical.camera.right - physical.camera.left) / physical.camera.zoom,
                        (physical.camera.top - physical.camera.bottom) / physical.camera.zoom
                    ],
                    geometryRestored: renderer.atomMeshes.children[0].geometry === originalGeometry,
                    after: {
                        position: liveCamera.position.toArray(),
                        projection: liveCamera.projectionMatrix.elements.slice()
                    },
                    before
                };
            }""")
            assert export_contract["prefix"] == "data:image/png;base64,"
            assert export_contract["cloned"] is True
            assert export_contract["viewportAspect"] == pytest.approx(1.0)
            assert export_contract["viewportRender"] == [640, 640]
            assert export_contract["viewportOffset"] == [0, 0]
            assert export_contract["physicalSpan"] == pytest.approx([10.0, 5.0])
            assert export_contract["geometryRestored"] is True
            assert export_contract["after"]["position"] == pytest.approx(
                export_contract["before"]["position"]
            )
            assert export_contract["after"]["projection"] == pytest.approx(
                export_contract["before"]["projection"]
            )
            exported_size = page.evaluate("""async dataUrl => {
                const image = new Image();
                const loaded = new Promise((resolve, reject) => {
                    image.onload = resolve;
                    image.onerror = reject;
                });
                image.src = dataUrl;
                await loaded;
                return [image.naturalWidth, image.naturalHeight];
            }""", export_contract["dataUrl"])
            assert exported_size == [640, 360]

            page.click('[data-inspector-group="display"]')
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")
            page.click('[data-inspector-group="output"]')
            page.click('#btn-export-image')
            assert page.locator('#export-framing-mode').is_visible()
            assert page.locator('#export-pixels-per-angstrom').count() == 0
            page.select_option('#export-framing-mode', 'physical')
            page.fill('#export-width', '1600')
            page.fill('#export-height', '800')
            assert 'View > Atomic scale (80.00 px/Å)' in page.locator('#export-scale-note').inner_text()
            assert '20.00 Å × 10.00 Å' in page.locator('#export-scale-note').inner_text()
            page.select_option('#export-sphere-quality', 'auto')
            page.fill('#export-smoothness-scale', '1.5')
            assert '48 sphere segments' in page.locator('#export-smoothness-note').inner_text()
            page.click('#modal-close')

            page.click('#btn-lighting-toggle')
            page.select_option('#lighting-mode', 'modeling')
            page.wait_for_function("!window.__ASE_APP__.renderer.renderer.shadowMap.enabled")
            page.wait_for_timeout(100)
            start = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            time.sleep(0.35)
            end = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            assert end == start

            page.click('#btn-lighting-close')
            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            mobile_collapsed = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const handle = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                const actionGroup = document.querySelector('.action-group').getBoundingClientRect();
                return {
                    panelWidth: panel.width,
                    handleRight: handle.right,
                    viewportWidth: window.innerWidth,
                    triggerRight: trigger.right,
                    handleLeft: handle.left,
                    handleOverlap: !(
                        trigger.right <= handle.left ||
                        trigger.left >= handle.right ||
                        trigger.bottom <= handle.top ||
                        trigger.top >= handle.bottom
                    ),
                    triggerContained: trigger.left >= actionGroup.left && trigger.right <= actionGroup.right,
                    headerCenterDelta: Math.abs(
                        (trigger.top + trigger.height / 2) -
                        (actionGroup.top + actionGroup.height / 2)
                    ),
                    handleVerticalCenterDelta: Math.abs(
                        (handle.top + handle.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert mobile_collapsed['panelWidth'] == pytest.approx(0, abs=1)
            assert mobile_collapsed['handleRight'] == pytest.approx(mobile_collapsed['viewportWidth'], abs=1)
            assert mobile_collapsed['handleOverlap'] is False
            assert mobile_collapsed['triggerContained'] is True
            assert mobile_collapsed['headerCenterDelta'] <= 2
            assert mobile_collapsed['handleVerticalCenterDelta'] <= 1.5

            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 345.5")
            mobile_expanded = page.evaluate("""() => {
                const handle = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                return {
                    handleRight: handle.right,
                    panelLeft: panel.left,
                    panelWidth: panel.width,
                    verticalCenterDelta: Math.abs(
                        (handle.top + handle.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert mobile_expanded['panelWidth'] == pytest.approx(346, abs=1)
            assert mobile_expanded['handleRight'] == pytest.approx(mobile_expanded['panelLeft'], abs=1)
            assert mobile_expanded['verticalCenterDelta'] <= 1.5

            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_cell_local_bonds_clip_at_the_displayed_supercell_boundary():
    atoms = Atoms(
        "HHHH",
        scaled_positions=[
            [0.95, 0.20, 0.25],
            [0.05, 0.20, 0.25],
            [0.70, 0.95, 0.75],
            [0.70, 0.05, 0.75],
        ],
        cell=[[4.0, 0.0, 0.0], [1.2, 3.6, 0.0], [0.0, 0.0, 8.0]],
        pbc=[True, True, False],
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")

            # The two nearest H-H images lie across +a and +b. A single
            # displayed cell correctly clips both at its outer boundary.
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 0")
            assert page.locator('#app-viewport canvas').get_attribute(
                'data-supercell-bridge-bond-count'
            ) == '0'

            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            page.fill('#super-x', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[0] === 2")
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas').dataset.supercellBridgeBondCount === '1'"
            )
            doubled = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.supercellGroup.children.filter(
                    child => child.userData.supercellBonds
                );
                return {
                    basePairs: renderer.bondPairs.length,
                    records: renderer.supercellBridgeBondRecords.map(record => ({
                        i: record.i,
                        j: record.j,
                        imageOffset: record.imageOffset
                    })),
                    bridgeSegments: meshes.reduce((sum, mesh) => sum +
                        mesh.userData.bondInstances.filter(instance => instance.bridge).length, 0),
                    totalSegments: meshes.reduce((sum, mesh) => sum + mesh.count, 0)
                };
            }""")
            assert doubled == {
                "basePairs": 0,
                "records": [{"i": 0, "j": 1, "imageOffset": [1, 0, 0]}],
                "bridgeSegments": 2,
                "totalSegments": 2,
            }

            # Three cells contain two internal boundaries. There is no third
            # bond through the outer edge of the displayed supercell.
            page.fill('#super-x', '3')
            page.keyboard.press('Tab')
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas').dataset.supercellBridgeBondCount === '2'"
            )
            tripled = page.evaluate("""() => {
                const meshes = window.__ASE_APP__.renderer.supercellGroup.children.filter(
                    child => child.userData.supercellBonds
                );
                return {
                    bridgeSegments: meshes.reduce((sum, mesh) => sum +
                        mesh.userData.bondInstances.filter(instance => instance.bridge).length, 0),
                    totalSegments: meshes.reduce((sum, mesh) => sum + mesh.count, 0)
                };
            }""")
            assert tripled == {"bridgeSegments": 4, "totalSegments": 4}

            # A 2x2x1 display contains two internal a-boundary bonds (one per
            # b row) and two internal b-boundary bonds (one per a column).
            page.fill('#super-x', '2')
            page.fill('#super-y', '2')
            page.keyboard.press('Tab')
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas').dataset.supercellBridgeBondCount === '4'"
            )
            doubled_xy = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.supercellGroup.children.filter(
                    child => child.userData.supercellBonds
                );
                return {
                    records: renderer.supercellBridgeBondRecords.map(record => ({
                        i: record.i,
                        j: record.j,
                        imageOffset: record.imageOffset
                    })),
                    bridgeSegments: meshes.reduce((sum, mesh) => sum +
                        mesh.userData.bondInstances.filter(instance => instance.bridge).length, 0),
                    totalSegments: meshes.reduce((sum, mesh) => sum + mesh.count, 0)
                };
            }""")
            assert doubled_xy == {
                "records": [
                    {"i": 0, "j": 1, "imageOffset": [1, 0, 0]},
                    {"i": 2, "j": 3, "imageOffset": [0, 1, 0]},
                ],
                "bridgeSegments": 8,
                "totalSegments": 8,
            }
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_interactive_bonds_reinfer_live_and_cutoffs_survive_structure_updates():
    atoms = Atoms(
        "HH",
        positions=[[0.0, 0.0, 0.0], [0.7, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=False,
    )
    set_atom_type_labels(atoms, ["H_left", "H_right"])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            _expand_inspector(page)
            page.click('[data-inspector-group="display"]')
            _open_panel(page, 'bonding')
            page.select_option('#bond-mode', 'element')
            cutoff = page.locator('.element-bond-cutoff[data-pair-key="H_left-H_right"]')
            assert cutoff.count() == 1
            cutoff.fill('0.90')
            page.wait_for_function(
                "Math.abs(window.__ASE_APP__.state.display.elementBondCutoffs['H_left-H_right'] - 0.9) < 1e-9"
            )
            cutoff.fill('0')
            page.wait_for_function(
                "window.__ASE_APP__.state.display.elementBondCutoffs['H_left-H_right'] === 0 && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )
            cutoff.fill('0.90')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            page.evaluate("""() => {
                document.activeElement?.blur();
                const app = window.__ASE_APP__;
                app.state.selected.clear();
                app.state.selected.add(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('1.0')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'MOVE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )

            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.evaluate("async () => { await window.__ASE_APP__.pendingApply; }")
            persisted = page.evaluate("""() => ({
                mode: window.__ASE_APP__.state.display.bondMode,
                cutoff: window.__ASE_APP__.state.display.elementBondCutoffs['H_left-H_right'],
                input: Number(document.querySelector('[data-pair-key="H_left-H_right"]').value),
                bonds: window.__ASE_APP__.renderer.bondPairs.length
            })""")
            assert persisted == {
                "mode": "element",
                "cutoff": 0.9,
                "input": 0.9,
                "bonds": 0,
            }

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('-1.0')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'MOVE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 1"
            )
            page.keyboard.press('Escape')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'IDLE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )

            relabeled = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.elementBondCutoffs['H_left-H_right'] = 1.23;
                app.renameElementTypeForVisualization('H_left', 'H_custom', [0], 'H', {preserveAppearance: true});
                return {
                    labels: [...app.state.atoms.symbols],
                    order: [...app.state.typeOrder],
                    cutoff: app.state.display.elementBondCutoffs['H_custom-H_right'],
                    rendererCutoff: app.renderer.bondCutoffForPair(0, 1),
                    input: Number(document.querySelector('[data-pair-key="H_custom-H_right"]')?.value),
                };
            }""")
            assert relabeled == {
                "labels": ["H_custom", "H_right"],
                "order": ["H_custom", "H_right"],
                "cutoff": 1.23,
                "rendererCutoff": 1.23,
                "input": 1.23,
            }
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_bond_style_thickness_and_color_modes_render_and_persist():
    atoms = Atoms(
        "HO",
        positions=[[0.0, 0.0, 0.0], [2.4, 0.0, 0.0]],
        cell=[[8.0, 0.0, 0.0], [1.2, 8.0, 0.0], [0.3, 0.5, 8.0]],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            _expand_inspector(page)
            page.click('[data-inspector-group="display"]')
            _open_panel(page, 'bonding')
            page.select_option('#bond-mode', 'manual')
            page.fill('#bond-pairs', '0-1')
            page.click('#btn-bond-apply')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            default_bond = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.bondGroup.children;
                return {
                    styles: meshes.map(mesh => mesh.geometry.type),
                    segments: meshes.reduce((sum, mesh) => sum + mesh.userData.bondSegments.length, 0),
                    colors: meshes.map(mesh => `#${mesh.material.color.getHexString()}`).sort(),
                    expected: [renderer.atomVisualColor(0), renderer.atomVisualColor(1)]
                        .map(color => color.toLowerCase()).sort()
                };
            }""")
            assert default_bond["styles"] == ["CylinderGeometry", "CylinderGeometry"]
            assert default_bond["segments"] == 2
            assert default_bond["colors"] == default_bond["expected"]

            page.select_option('#bond-style', 'flat')
            page.select_option('#bond-color-mode', 'custom')
            page.fill('#bond-thickness', '0.24')
            page.fill('#bond-custom-color', '#18a7d8')
            page.locator('#bond-pairs').click()
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                return app.state.display.bondStyle === 'flat'
                    && app.state.display.bondColorMode === 'custom'
                    && Math.abs(app.state.display.bondThickness - 0.24) < 1e-9
                    && app.state.display.bondCustomColor === '#18a7d8'
                    && mesh.geometry.type === 'PlaneGeometry'
                    && mesh.userData.bondSegments.length === 1
                    && mesh.userData.bondColor === '#18a7d8'
                    && mesh.material.color.getHexString() === '18a7d8';
            }""")
            flat_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                const matrix = Array.from(mesh.instanceMatrix.array.slice(0, 16));
                return {
                    thickness: Math.hypot(matrix[0], matrix[1], matrix[2]),
                    output: document.getElementById('bond-thickness-value').innerText,
                    customVisible: !document.getElementById('bond-custom-color-row').classList.contains('hidden'),
                    color: `#${mesh.material.color.getHexString()}`,
                    matrix
                };
            }""")
            assert flat_state["thickness"] == pytest.approx(0.24, abs=1e-5)
            assert flat_state["output"] == "0.24 A"
            assert flat_state["customVisible"] is True
            assert flat_state["color"] == "#18a7d8"

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.controls.rotate(42, -27);
                app.renderer.renderNow();
            }""")
            rotated_matrix = page.evaluate(
                "Array.from(window.__ASE_APP__.renderer.bondGroup.children[0].instanceMatrix.array.slice(0, 16))"
            )
            assert rotated_matrix != flat_state["matrix"]

            page.select_option('#bond-color-mode', 'split')
            page.wait_for_function("""() => {
                const meshes = window.__ASE_APP__.renderer.bondGroup.children;
                return meshes.length === 2
                    && meshes.reduce((sum, mesh) => sum + mesh.userData.bondSegments.length, 0) === 2;
            }""")
            split_colors = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    actual: renderer.bondGroup.children
                        .map(mesh => `#${mesh.material.color.getHexString()}`).sort(),
                    expected: [renderer.atomVisualColor(0), renderer.atomVisualColor(1)]
                        .map(color => color.toLowerCase()).sort()
                };
            }""")
            assert split_colors["actual"] == split_colors["expected"]

            page.click('[data-inspector-group="structure"]')
            page.fill('#super-x', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[0] === 2")
            page.fill('#super-y', '2')
            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[1] === 2")
            page.fill('#super-z', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[2] === 2")
            assert page.evaluate("window.__ASE_APP__.state.display.supercell") == [2, 2, 2]
            repeated = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const children = renderer.supercellGroup.children;
                const atoms = children.filter(child => child.userData.supercellInstanced);
                const bonds = children.filter(child => child.userData.supercellBonds);
                return {
                    atomInstances: atoms.reduce((sum, mesh) => sum + mesh.count, 0),
                    bondInstances: bonds.reduce((sum, mesh) => sum + mesh.count, 0),
                    atomMeshes: atoms.length,
                    bondMeshes: bonds.length,
                    atomTransparent: atoms.some(mesh => mesh.material.transparent),
                    atomOpacity: atoms.map(mesh => mesh.material.opacity),
                    selectableChildren: window.__ASE_APP__.renderer.atomMeshes.children.length,
                    exactBaseMaterials: atoms.every(mesh => mesh.userData.atomIndices.every(index =>
                        mesh.material === renderer.atomMeshByIndex.get(index).material
                    )),
                };
            }""")
            assert repeated["atomInstances"] == 14
            assert repeated["bondInstances"] == 14
            assert repeated["atomMeshes"] >= 1
            assert repeated["bondMeshes"] == 2
            assert repeated["atomTransparent"] is False
            assert all(opacity == 1 for opacity in repeated["atomOpacity"])
            assert repeated["exactBaseMaterials"] is True
            assert repeated["selectableChildren"] == 2
            repeated_hover = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const Vector3 = renderer.camera.position.constructor;
                const target = new Vector3(8, 0, 0);
                renderer.camera.position.set(13, -20, 7);
                renderer.camera.up.set(0, 0, 1);
                renderer.controls.target.copy(target);
                renderer.camera.lookAt(target);
                renderer.camera.updateMatrixWorld(true);
                renderer.scene.updateMatrixWorld(true);
                const screen = target.clone().project(renderer.camera);
                const pointer = {
                    clientX: (screen.x + 1) * 0.5 * window.innerWidth,
                    clientY: (1 - screen.y) * 0.5 * window.innerHeight,
                };
                return {
                    hover: app.selection.pickHover(pointer, renderer.atomMeshes, renderer.supercellGroup),
                    selectable: app.selection.pick(pointer, renderer.atomMeshes),
                    clientX: pointer.clientX,
                    clientY: pointer.clientY,
                };
            }""")
            assert repeated_hover["hover"] == {
                "kind": "replica",
                "index": 0,
                "cellOffset": [1, 0, 0],
                "key": "replica:0:1,0,0",
            }
            assert repeated_hover["selectable"] is None
            page.mouse.move(repeated_hover["clientX"], repeated_hover["clientY"])
            page.wait_for_function("window.__ASE_APP__.state.hoveredIndex === 0")
            assert "#0@[1,0,0] H" in page.locator('#hover-readout').inner_text()
            for control in ('#super-x', '#super-y', '#super-z'):
                page.fill(control, '1')
                page.keyboard.press('Tab')
            page.wait_for_function(
                "window.__ASE_APP__.state.display.supercell.every(value => value === 1)"
            )

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.selected.clear();
                app.state.selected.add(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('0.1')
            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.evaluate("async () => { await window.__ASE_APP__.pendingApply; }")
            persisted = page.evaluate("""() => ({
                style: window.__ASE_APP__.state.display.bondStyle,
                thickness: window.__ASE_APP__.state.display.bondThickness,
                colorMode: window.__ASE_APP__.state.display.bondColorMode,
                customColor: window.__ASE_APP__.state.display.bondCustomColor,
                styleControl: document.getElementById('bond-style').value,
                thicknessControl: Number(document.getElementById('bond-thickness').value),
                colorControl: document.getElementById('bond-color-mode').value
            })""")
            assert persisted == {
                "style": "flat",
                "thickness": 0.24,
                "colorMode": "split",
                "customColor": "#18a7d8",
                "styleControl": "flat",
                "thicknessControl": 0.24,
                "colorControl": "split",
            }
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_viz_only_replica_selection_measurements_and_atomic_label_commit():
    atoms = Atoms(
        "Cu2",
        positions=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    set_atom_type_labels(atoms, ["Cu", "Cu2"])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 820})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            _expand_inspector(page)
            page.click('[data-inspector-group="display"]')
            _open_panel(page, 'appearance')
            type_palette = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const labels = ['Cu', 'Cu2'];
                return {
                    types: labels.map(label => document.querySelector(`[data-element-type="${label}"]`).value),
                    controls: labels.map(label => document.querySelector(`[data-element-color="${label}"]`).value.toLowerCase()),
                    rendered: [0, 1].map(index => app.renderer.atomVisualColor(index).toLowerCase())
                };
            }""")
            assert type_palette["types"] == ["Cu", "Cu"]
            assert type_palette["controls"][0] == type_palette["controls"][1]
            assert type_palette["rendered"][0] == type_palette["rendered"][1]
            assert type_palette["controls"] == type_palette["rendered"]

            label_input = page.locator('[data-element-name="Cu2"]')
            label_input.fill('Cu')
            label_input.press('Enter')
            page.wait_for_function("""() => {
                const labels = window.__ASE_APP__.state.atoms.symbols;
                return labels[0] === 'Cu' && labels[1] === 'Cu_2';
            }""")
            toasts = page.locator('#toast-container .toast').all_inner_texts()
            assert sum('already exists' in text for text in toasts) == 1
            assert sum('Renamed Cu2 to Cu_2' in text for text in toasts) == 1
            assert all('atoms found' not in text for text in toasts)

            page.click('[data-inspector-group="structure"]')
            for control, value in (('#super-x', '2'), ('#super-y', '2'), ('#super-z', '1')):
                page.fill(control, value)
                page.keyboard.press('Tab')
            page.wait_for_function("""() =>
                window.__ASE_APP__.state.display.supercell.join(',') === '2,2,1' &&
                window.__ASE_APP__.renderer.supercellSelectionReferences().length === 6
            """)
            replica_material = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const base = renderer.atomMeshByIndex.get(0);
                const replica = renderer.supercellGroup.children.find(mesh =>
                    mesh.userData.supercellInstanced && mesh.userData.atomIndices.includes(0)
                );
                return {
                    useInstancedAtoms: renderer.useInstancedAtoms,
                    sameMaterial: base.material === replica.material,
                    baseColor: base.material.color.getHexString(),
                    replicaColor: replica.material.color.getHexString(),
                    baseEmissive: base.material.emissive.getHexString(),
                    replicaEmissive: replica.material.emissive.getHexString(),
                    baseRoughness: base.material.roughness,
                    replicaRoughness: replica.material.roughness,
                    hasInstanceColor: Boolean(replica.instanceColor)
                };
            }""")
            assert replica_material["useInstancedAtoms"] is False
            assert replica_material["sameMaterial"] is True
            assert replica_material["replicaColor"] == replica_material["baseColor"]
            assert replica_material["replicaEmissive"] == replica_material["baseEmissive"]
            assert replica_material["replicaRoughness"] == replica_material["baseRoughness"]
            assert replica_material["hasInstanceColor"] is False

            points = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const Vector3 = renderer.camera.position.constructor;
                renderer.camera.position.set(2, 2, 20);
                renderer.camera.up.set(0, 1, 0);
                renderer.controls.target.set(2, 2, 0);
                renderer.camera.lookAt(renderer.controls.target);
                renderer.camera.updateMatrixWorld(true);
                renderer.scene.updateMatrixWorld(true);
                const rect = renderer.domElement.getBoundingClientRect();
                const project = values => {
                    const point = new Vector3(...values).project(renderer.camera);
                    return {
                        x: rect.left + (point.x + 1) * rect.width / 2,
                        y: rect.top + (1 - point.y) * rect.height / 2,
                    };
                };
                return {
                    xReplica: project([4, 0, 0]),
                    base: project([0, 0, 0]),
                    yReplica: project([0, 4, 0]),
                };
            }""")
            page.mouse.click(points['xReplica']['x'], points['xReplica']['y'])
            page.keyboard.down('Shift')
            page.mouse.click(points['base']['x'], points['base']['y'])
            page.mouse.click(points['yReplica']['x'], points['yReplica']['y'])
            page.keyboard.up('Shift')
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 3")
            page.click('[data-inspector-group="inspect"]')
            _open_panel(page, 'selection')

            selected = page.evaluate("""() => ({
                count: window.__ASE_APP__.selectionCount(),
                indices: document.getElementById('selected-indices').innerText,
                centerLines: [...document.getElementById('selected-center').children]
                    .map(line => line.textContent),
                centerLineDelta: (() => {
                    const lines = [...document.getElementById('selected-center').children];
                    return lines.length === 2
                        ? lines[1].getBoundingClientRect().top - lines[0].getBoundingClientRect().top
                        : 0;
                })(),
                measure: document.getElementById('selected-measure').innerText,
                measureSummary: document.getElementById('selection-measure-value').innerText,
                measureVisible: !document.getElementById('selection-measure-readout').classList.contains('hidden'),
                replicaOutlines: window.__ASE_APP__.renderer.replicaSelectionOutlines.children
                    .reduce((sum, mesh) => sum + mesh.count, 0),
            })""")
            assert selected['count'] == 3
            assert selected['indices'] == '0@[1,0,0], 0, 0@[0,1,0]'
            assert selected['centerLines'] == [
                '1.333, 1.333, 0.000 A',
                '(frac 0.3333, 0.3333, 0.0000)',
            ]
            assert selected['centerLineDelta'] > 5
            assert 'angle(0@[1,0,0]-0-0@[0,1,0]) = 90.00 deg' in selected['measure']
            assert selected['measureSummary'] == 'Angle 90.00 deg | D1 4.0000 A | D2 4.0000 A'
            assert selected['measureVisible'] is True
            assert selected['replicaOutlines'] == 2

            page.mouse.move(points['yReplica']['x'], points['yReplica']['y'])
            page.wait_for_function("window.__ASE_APP__.state.hoveredReference?.key === 'replica:0:0,1,0'")
            hover_text = page.locator('#hover-readout').inner_text()
            assert '#0@[0,1,0] Cu' in hover_text
            assert 'measure=' not in hover_text
            assert page.locator('#selection-measure-value').inner_text() == selected['measureSummary']

            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Control+a')
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 8")
            assert page.locator('#prop-selected').inner_text() == '8'
            assert page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const selected = app.selection.boxSelect(
                    {left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight},
                    app.renderer.atomMeshes,
                    app.renderer.camera,
                    app.renderer.supercellGroup,
                    true
                );
                return [...selected].filter(value => value?.kind === 'replica').length;
            }""") == 6
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)


def test_camera_toolbar_white_background_and_flat_2d_display():
    atoms = molecule("H2O")
    atoms.set_cell([8.0, 8.0, 8.0])
    atoms.set_pbc(True)
    atoms.set_constraint(FixAtoms(indices=[0]))
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            console_errors = []
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            page.wait_for_function("window.__ASE_APP__?.renderer?.bondPairs?.length === 2")

            toolbar_geometry = page.evaluate("""() => {
                const calc = document.getElementById('calc-controls').getBoundingClientRect();
                const toolbar = document.getElementById('view-toolbar').getBoundingClientRect();
                const arrows = [...document.querySelectorAll('[data-view-rotate]')];
                return {
                    calcCenterY: calc.top + calc.height / 2,
                    toolbarCenterY: toolbar.top + toolbar.height / 2,
                    toolbarVisible: toolbar.width > 0 && toolbar.height > 0,
                    toolbarLeft: toolbar.left,
                    toolbarRight: toolbar.right,
                    viewportWidth: window.innerWidth,
                    arrowCount: arrows.length,
                    arrowText: arrows.map(button => button.textContent.trim()),
                    popupExists: Boolean(
                        document.getElementById('btn-view-toggle')
                        || document.getElementById('view-card')
                    )
                };
            }""")
            assert toolbar_geometry["toolbarVisible"] is True
            assert toolbar_geometry["toolbarCenterY"] == pytest.approx(
                toolbar_geometry["calcCenterY"], abs=1
            )
            assert toolbar_geometry["toolbarLeft"] >= 0
            assert toolbar_geometry["toolbarRight"] <= toolbar_geometry["viewportWidth"]
            assert toolbar_geometry["arrowCount"] == 6
            assert toolbar_geometry["arrowText"] == [""] * 6
            assert toolbar_geometry["popupExists"] is False

            _expand_inspector(page)
            page.click('[data-inspector-group="display"]')
            page.select_option("#viewport-background", "white")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.viewportBackground === 'white'"
            )
            white_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const grid = app.renderer.gridGroup.children[0];
                return {
                    background: `#${app.renderer.scene.background.getHexString()}`,
                    clear: `#${app.renderer.renderer.getClearColor(
                        new app.renderer.scene.background.constructor()
                    ).getHexString()}`,
                    dataset: app.renderer.domElement.dataset.viewportBackground,
                    sidebar: document.getElementById('viewport-background').value,
                    gridOpacity: grid.material.opacity
                };
            }""")
            assert white_state == {
                "background": "#ffffff",
                "clear": "#ffffff",
                "dataset": "white",
                "sidebar": "white",
                "gridOpacity": pytest.approx(0.72),
            }

            page.select_option("#atom-display-mode", "2d")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.atomDisplayMode === '2d'"
            )
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.bondStyle === 'flat'"
            )
            flat_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    mode: app.state.display.atomDisplayMode,
                    requestedBondStyle: app.state.display.bondStyle,
                    effectiveBondStyle: app.renderer.effectiveBondStyle(),
                    atomMaterials: app.renderer.atomMeshes.children.map(
                        mesh => mesh.material.type
                    ),
                    fixedFlatMaterialCount: app.renderer.atomMeshes.children.filter(
                        mesh => mesh.userData.fixed
                            && mesh.material.userData.fixedEtchedFlatApplied === true
                    ).length,
                    outlineMaterialCount: app.renderer.atomMeshes.children.filter(
                        mesh => mesh.material.userData.flatOutlineEnabled === true
                    ).length,
                    atomMeshCount: app.renderer.atomMeshes.children.length,
                    bondGeometry: app.renderer.bondGroup.children.map(
                        mesh => mesh.geometry.type
                    ),
                    sidebar: document.getElementById('atom-display-mode').value
                };
            }""")
            assert flat_state["mode"] == "2d"
            assert flat_state["requestedBondStyle"] == "cylinder"
            assert flat_state["effectiveBondStyle"] == "flat"
            assert set(flat_state["atomMaterials"]) == {"MeshBasicMaterial"}
            assert flat_state["fixedFlatMaterialCount"] == 1
            assert flat_state["outlineMaterialCount"] == flat_state["atomMeshCount"]
            assert set(flat_state["bondGeometry"]) == {"PlaneGeometry"}
            assert flat_state["sidebar"] == "2d"
            page.wait_for_timeout(150)
            assert not [
                message
                for message in console_errors
                if "Shader Error" in message or "WebGLProgram" in message
            ]

            page.select_option("#viewport-background", "dark")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.viewportBackground === 'dark'"
            )
            assert page.evaluate("""() => window.__ASE_APP__.renderer.atomMeshes.children.every(
                mesh => mesh.material.userData.flatOutlineEnabled === false
            )""") is True

            page.select_option("#viewport-background", "white")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.viewportBackground === 'white'"
            )
            page.select_option("#atom-display-mode", "3d")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.atomDisplayMode === '3d'"
            )
            solid_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    atomMaterials: app.renderer.atomMeshes.children.map(
                        mesh => mesh.material.type
                    ),
                    bondGeometry: app.renderer.bondGroup.children.map(
                        mesh => mesh.geometry.type
                    )
                };
            }""")
            assert set(solid_state["atomMaterials"]) == {"MeshStandardMaterial"}
            assert set(solid_state["bondGeometry"]) == {"CylinderGeometry"}

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                const target = app.renderer.controls.target;
                const distance = Math.max(camera.position.distanceTo(target), 4);
                camera.position.set(target.x, target.y, target.z + distance);
                camera.up.set(0, 1, 0);
                app.completeCameraViewChange('test-top-view');
            }""")
            page.fill("#view-rotate-step", "45")
            before_rotation = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const target = renderer.controls.target.clone();
                const point = target.clone().add({x: 1, y: 0, z: 0});
                const projected = point.project(renderer.camera);
                return {
                    positions: JSON.stringify(app.state.atoms.positions),
                    cameraPosition: renderer.camera.position.toArray(),
                    target: target.toArray(),
                    projected: [
                        projected.x * renderer.domElement.clientWidth,
                        projected.y * renderer.domElement.clientHeight
                    ]
                };
            }""")
            assert math.degrees(math.atan2(
                before_rotation["projected"][1],
                before_rotation["projected"][0],
            )) == pytest.approx(0, abs=1e-5)

            page.click('[data-view-rotate="roll-ccw"]')
            rotated = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const target = renderer.controls.target.clone();
                const point = target.clone().add({x: 1, y: 0, z: 0});
                const projected = point.project(renderer.camera);
                return {
                    positions: JSON.stringify(app.state.atoms.positions),
                    cameraPosition: renderer.camera.position.toArray(),
                    cameraUp: renderer.camera.up.toArray(),
                    projected: [
                        projected.x * renderer.domElement.clientWidth,
                        projected.y * renderer.domElement.clientHeight
                    ],
                    step: app.state.display.viewRotationStepDeg,
                    saved: app.designSettingsSnapshot().display
                };
            }""")
            assert rotated["positions"] == before_rotation["positions"]
            assert rotated["cameraPosition"] == pytest.approx(
                before_rotation["cameraPosition"], abs=1e-8
            )
            assert rotated["cameraUp"] == pytest.approx(
                [math.sqrt(0.5), math.sqrt(0.5), 0], abs=1e-7
            )
            assert math.degrees(math.atan2(
                rotated["projected"][1],
                rotated["projected"][0],
            )) == pytest.approx(45, abs=1e-5)
            assert rotated["step"] == pytest.approx(45)
            assert rotated["saved"]["viewportBackground"] == "white"
            assert rotated["saved"]["atomDisplayMode"] == "3d"
            assert rotated["saved"]["viewRotationStepDeg"] == pytest.approx(45)

            page.click('[data-view-rotate="roll-cw"]')
            camera_after_roll_pair = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    position: renderer.camera.position.toArray(),
                    up: renderer.camera.up.toArray()
                };
            }""")
            assert camera_after_roll_pair["position"] == pytest.approx(
                before_rotation["cameraPosition"], abs=1e-8
            )
            assert camera_after_roll_pair["up"] == pytest.approx([0, 1, 0], abs=1e-8)

            for first, inverse, component, expected_sign in (
                ("left", "right", 0, -1),
                ("right", "left", 0, 1),
                ("up", "down", 1, 1),
                ("down", "up", 1, -1),
            ):
                page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const camera = app.renderer.camera;
                    const target = app.renderer.controls.target;
                    const distance = Math.max(camera.position.distanceTo(target), 4);
                    camera.position.set(target.x, target.y, target.z + distance);
                    camera.up.set(0, 1, 0);
                    app.completeCameraViewChange('test-top-view');
                }""")
                camera_before_pair = page.evaluate("""() => {
                    const renderer = window.__ASE_APP__.renderer;
                    return {
                        position: renderer.camera.position.toArray(),
                        up: renderer.camera.up.toArray()
                    };
                }""")
                page.click(f'[data-view-rotate="{first}"]')
                moved_direction = page.evaluate("""() => {
                    const renderer = window.__ASE_APP__.renderer;
                    return renderer.camera.position.clone()
                        .sub(renderer.controls.target).normalize().toArray();
                }""")
                assert moved_direction[component] * expected_sign > 0.6
                page.click(f'[data-view-rotate="{inverse}"]')
                camera_after_pair = page.evaluate("""() => {
                    const renderer = window.__ASE_APP__.renderer;
                    return {
                        position: renderer.camera.position.toArray(),
                        up: renderer.camera.up.toArray()
                    };
                }""")
                assert camera_after_pair["position"] == pytest.approx(
                    camera_before_pair["position"], abs=1e-8
                )
                assert camera_after_pair["up"] == pytest.approx(
                    camera_before_pair["up"], abs=1e-8
                )

            assert page.evaluate(
                "JSON.stringify(window.__ASE_APP__.state.atoms.positions)"
            ) == before_rotation["positions"]
            browser.close()
    finally:
        sessions.pop(editor.session_id, None)
