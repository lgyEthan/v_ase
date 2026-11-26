"""Playback, matching, render shape and replacement through desktop-sized UI."""

import base64
import csv
from io import BytesIO
from pathlib import Path

import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.io import write
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from v_ase._version import __version__
from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


@pytest.fixture
def trajectory_workbench(tmp_path, monkeypatch):
    monkeypatch.setenv('V_ASE_CONFIG_DIR', str(tmp_path / 'preferences'))
    frames = []
    for index, energy in enumerate((-7.0, -6.55, -6.94)):
        frame = Atoms("Cu2O", positions=[[0, 0, 0], [2, 1, .2], [.8, 1.7, (7.75, 0, .25)[index]]],
                      cell=[8, 8, 8], pbc=True)
        if index == 1:
            frame = frame[[2, 1, 0]]
        frame.info["path_length_A"] = [0, .24, .71][index]
        forces = [[0, 0, .18 - index * .12] if symbol == 'O' else [0, 0, 0] for symbol in frame.symbols]
        frame.calc = SinglePointCalculator(frame, energy=energy, forces=forces)
        frames.append(frame)
    editor = view(frames, notebook=False, open_browser=False, block=False, port=find_free_port(),
                  close_on_disconnect=False, viz_only=False, document_name="NEB review.traj")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
            page = context.new_page()
            page.goto(editor.url)
            iframe = page.locator("iframe").first
            iframe.wait_for()
            frame = iframe.element_handle().content_frame()
            frame.wait_for_function("window.__ASE_APP__?.workspaceRecoveryAcknowledged")
            yield page, frame
            browser.close()
    finally:
        editor.close()


def normalized_graph_rect(frame):
    return frame.locator(".trajectory-energy-overlay").evaluate("""overlay => {
        const {width, height} = overlay.parentElement.getBoundingClientRect();
        return [overlay.offsetLeft / width, overlay.offsetTop / height,
            overlay.offsetWidth / width, overlay.offsetHeight / height];
    }""")


def test_home_end_seek_timeline_and_pause_playback(trajectory_workbench):
    _, frame = trajectory_workbench
    canvas = frame.locator('#app-viewport > canvas')
    canvas.press('End')
    frame.wait_for_function('window.__ASE_APP__.timelineFrameIndex() === 2')
    frame.locator('#btn-play').click()
    canvas.press('Home')
    frame.wait_for_function('window.__ASE_APP__.timelineFrameIndex() === 0 && !window.__ASE_APP__.state.trajectoryTimer')
    frame.locator('#frame-slider').press('End')
    frame.wait_for_function('window.__ASE_APP__.timelineFrameIndex() === 2')


def test_scene_bond_count_tracks_topology_while_bonds_are_hidden():
    frames = [Atoms('H3', positions=[[0, 0, 0], [dist, 0, 0], [4, 0, 0]]) for dist in (.75, 2)]
    editor = view(frames, notebook=False, open_browser=False, block=False,
                  port=find_free_port(), close_on_disconnect=False, initial_frame=0)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(editor.url)
            pane = page.locator('#document-panes iframe').first
            pane.wait_for()
            frame = pane.element_handle().content_frame()
            frame.wait_for_function('window.__ASE_APP__?.workspaceRecoveryAcknowledged')
            frame.evaluate('''() => window.v_aseAI.apply({display:{showBonds:true, bondMode:'pairwise',
                pairwiseBondCutoffs:{'H-H':1}, pairwiseBondRanges:{'H-H':{enabled:true,max:1}}}})''')
            row = page.locator('#workspace-scene-list [data-scene-id="bonds"]')
            eye = row.get_by_role('checkbox')
            count = row.locator('.scene-count')
            expect(count).to_have_text('1')

            eye.uncheck()
            frame.wait_for_function('!window.__ASE_APP__.renderer.displayOptions.showBonds')
            expect(count).to_have_text('1')
            assert frame.evaluate('window.__ASE_APP__.renderer.bondGroup.children.length') == 0
            row.locator('.scene-select').click()
            expect(count).to_have_text('1')

            frame.locator('#app-viewport > canvas').press('End')
            expect(count).to_have_text('0')
            cutoff = frame.locator('#pairwise-bond-list input[type="number"]')
            cutoff.fill('2.25')
            cutoff.press('Enter')
            expect(count).to_have_text('2')
            assert frame.evaluate('window.__ASE_APP__.renderer.bondGroup.children.length') == 0

            frame.evaluate("() => window.v_aseAI.apply({display:{labelVisible:{H:false}}})")
            expect(count).to_have_text('0')
            frame.evaluate("() => window.v_aseAI.apply({display:{labelVisible:{H:true}}})")
            expect(count).to_have_text('2')

            eye.check()
            frame.wait_for_function('window.__ASE_APP__.renderer.bondPairs.length === 2')
            expect(count).to_have_text('2')
            browser.close()
    finally:
        editor.close()


def test_scene_overlays_follow_new_water_trajectory_and_saved_results():
    editor = view(Atoms('Cu', positions=[[5, 5, 5]]), notebook=True, open_browser=False, block=False,
                  port=find_free_port(), close_on_disconnect=False)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            page.evaluate('async () => window.__ASE_APP__.ready')
            row = lambda name: page.locator(f'#objects-list [data-scene-id="{name}"]')
            overlays = page.locator('#objects-list [data-scene-group="overlays"]')
            expect(row('polyhedra')).to_be_visible()
            overlays.locator('summary').click()
            expect(row('polyhedra')).to_be_hidden()
            for name in ('water', 'trajectory-energy', 'displacements', 'forces'):
                assert row(name).count() == 0
            page.get_by_role('button', name='Edit structure', exact=True).click()
            page.wait_for_function('!window.__ASE_APP__.state.vizOnly')
            for element, position in [('O', [0, 0, 0]), ('H', [.96, 0, 0]), ('H', [-.23, .93, 0])]:
                page.evaluate("([element, position]) => window.v_aseAI.apply({operation:{name:'add-atom', element, position}})",
                              [element, position])
            row('water').wait_for(state='attached')
            expect(row('water')).to_be_hidden()
            overlays.locator('summary').click()
            expect(row('water')).to_be_visible()
            assert row('displacements').count() == 0

            page.evaluate('() => window.__ASE_APP__.duplicateTrajectoryFrame()')
            row('displacements').wait_for(state='attached')
            page.wait_for_function('window.__ASE_APP__.trajectoryOverlayRequest?.data?.energy === false')
            assert row('trajectory-energy').count() == 0
            session = sessions[editor.session_id]
            other = session.trajectory_frames[1 - session.current_frame]
            other.calc = SinglePointCalculator(other, energy=-4.5, forces=[[.1, 0, 0]] * len(other))
            session.invalidate_scientific_content(all_frames=True)
            page.evaluate('() => window.__ASE_APP__.refresh()')
            row('trajectory-energy').wait_for(state='attached')
            row('forces').wait_for(state='attached')
            browser.close()
    finally:
        editor.close()


def test_floating_graph_resize_snaps_the_dragged_edges(trajectory_workbench):
    page, frame = trajectory_workbench
    page.set_viewport_size({'width': 1600, 'height': 980})
    frame.evaluate("window.__ASE_APP__.openEditorRoute('rdf')")
    frame.locator('#btn-rdf-calculate').click()
    frame.locator('#btn-analysis-float').click()
    energy = frame.locator('.trajectory-energy-overlay')
    analysis = frame.locator('#analysis-floating')

    def place(energy_frame, analysis_frame):
        frame.evaluate("""([energyFrame, analysisFrame]) => {
            const app = window.__ASE_APP__;
            const { clientWidth: w, clientHeight: h } = app.renderer.container;
            const layout = ([x,y,width,height]) => ({x:x/w,y:y/h,width:width/w,height:height/h});
            app.state.display.analysisPlots.rdf.layout = layout(analysisFrame);
            app.layoutAnalysisPlot();
            app.setEnergyOverlay({...app.energyOverlaySettings(),
                visible:true, layout:layout(energyFrame)});
        }""", [energy_frame, analysis_frame])
        energy.locator('.energy-chart-marker').wait_for()

    def grip_start(grip):
        box = grip.bounding_box()
        x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        return x, y

    def right(graph):
        box = graph.bounding_box()
        return box['x'] + box['width']

    def bottom(graph):
        box = graph.bounding_box()
        return box['y'] + box['height']

    # The right edges are close on opening, with a visible gap between the graphs.
    place([100, 80, 410, 170], [100, 340, 405, 205])
    original = analysis.bounding_box()
    assert right(energy) - right(analysis) == pytest.approx(5, abs=.1)
    grip = analysis.locator('#analysis-floating-resize')
    x, y = grip_start(grip)
    page.mouse.move(x, y + 20)
    page.mouse.up()
    assert right(energy) - right(analysis) == pytest.approx(5, abs=.1)

    x, y = grip_start(grip)
    page.mouse.move(x + 2, y)
    assert right(analysis) == pytest.approx(right(energy), abs=.1)
    page.mouse.move(x + 16, y)
    assert right(analysis) == pytest.approx(right(energy), abs=.1)
    page.mouse.move(x + 26, y)
    assert right(analysis) == pytest.approx(right(energy) + 21, abs=.1)
    page.mouse.move(x + 4, y)
    page.mouse.up()
    assert right(analysis) == pytest.approx(right(energy), abs=.1)
    assert analysis.bounding_box()['x'] == pytest.approx(original['x'], abs=.1)
    assert analysis.bounding_box()['y'] == pytest.approx(original['y'], abs=.1)
    frame.evaluate("window.__ASE_APP__.layoutAnalysisPlot()")
    assert right(analysis) == pytest.approx(right(energy), abs=.1)

    # In the other direction, the energy graph can match the analysis graph's bottom edge.
    place([535, 70, 270, 199], [70, 70, 380, 230])
    original = energy.bounding_box()
    x, y = grip_start(energy.locator('.energy-overlay-resize'))
    page.mouse.move(x, y + 27)
    page.mouse.up()
    assert bottom(energy) == pytest.approx(bottom(analysis), abs=.1)
    assert energy.bounding_box()['width'] == pytest.approx(original['width'], abs=.1)
    assert energy.bounding_box()['y'] == pytest.approx(original['y'], abs=.1)


def test_energy_overlay_seeks_moves_resizes_and_exports_offline(trajectory_workbench, tmp_path):
    page, frame = trajectory_workbench
    assert page.locator(".document-brand .document-version").inner_text() == __version__
    overlays = page.locator('#workspace-scene-list [data-scene-group="overlays"]')
    expect(overlays.locator('[data-scene-id="polyhedra"]')).to_be_visible()
    energy_row = overlays.locator('[data-scene-id="trajectory-energy"]')
    energy_row.locator(".scene-visibility").click()
    graph = frame.locator(".trajectory-energy-overlay")
    graph.locator(".energy-chart-marker").wait_for()
    assert "ΔE" in graph.locator("output").inner_text()

    frame.locator("#btn-play").click()
    frame.wait_for_function("document.querySelector('.trajectory-energy-overlay').dataset.frame !== '0'")
    frame.locator("#btn-play").click()
    graph.locator("canvas").press("End")
    frame.wait_for_function("document.querySelector('.trajectory-energy-overlay').dataset.frame === '2'")
    assert frame.locator("#frame-label").inner_text() == "3 / 3"
    assert frame.locator("#val-energy").inner_text() == "-6.9400"
    chart = graph.locator("canvas")
    chart.click(position={"x": 60, "y": 36})
    frame.wait_for_function("document.querySelector('.trajectory-energy-overlay').dataset.frame === '0'")
    expect(frame.locator('#graph-settings')).to_be_visible()
    expect(frame.locator('#graph-series')).to_have_value('samples')

    starting_rect = normalized_graph_rect(frame)
    for selector, delta in ((".energy-overlay-header", (85, 55)), (".energy-overlay-resize", (38, 23))):
        box = graph.locator(selector).bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + delta[0], y + delta[1], steps=4)
        page.mouse.up()
    moved_rect = normalized_graph_rect(frame)
    assert all(after > before for before, after in zip(starting_rect, moved_rect))

    energy_row.locator(".scene-select").click()
    frame.locator("#energy-line-color").fill("#4a80ce")
    frame.locator("#energy-marker-color").fill("#d8485c")
    frame.locator("#energy-line-width").fill("3.25")
    frame.locator("#btn-save-energy-preset").click()
    frame.locator("#energy-preset-name").fill("NEB line")
    frame.locator("#energy-preset-save").click()
    frame.wait_for_function("document.getElementById('energy-presets').value === 'NEB line'")
    frame.locator("#energy-line-width").fill("1")
    frame.locator("#energy-presets").select_option("")
    frame.locator("#energy-presets").select_option("NEB line")
    assert frame.locator("#energy-line-width").input_value() == "3.25"
    axes = frame.locator("#energy-graph-axes")
    axes.locator("xpath=..").locator("summary").click()
    for name, value in [("X minimum", "-0.03"), ("X maximum", "9"),
                        ("Y minimum", "-0.2"), ("Y maximum", "0.2")]:
        axes.get_by_role("spinbutton", name=name, exact=True).fill(value)
    assert frame.evaluate("""() => {const {xmin,xmax,low,high} = window.__ASE_APP__.trajectoryEnergyOverlay.plot;
        return [xmin,xmax,low,high];}""") == [-.03, 9, -.2, .2]

    export = tmp_path / "NEB energy.html"
    frame.evaluate("""async () => {
        const app = window.__ASE_APP__;
        const profile = app.currentImageExportProfile();
        const rendered = await app.renderHtmlCompositionPreview(profile, {poster: true});
        const blob = await app.api.exportHtml(app.backendPositionsPayload(),
            app.designSettingsSnapshot({includeIdentityOverrides: true}), true, [], 'NEB energy',
            true, rendered.contract, rendered.url);
        const anchor = document.createElement('a');
        anchor.href = URL.createObjectURL(blob);
        anchor.download = 'energy.html';
        // Delay the download until the test has attached its listener.
        window.__downloadEnergy = () => anchor.click();
    }""")
    with page.expect_download() as event:
        frame.evaluate("window.__downloadEnergy()")
    event.value.save_as(export)
    offline = page.context.new_page()
    requests = []
    offline.on("request", lambda request: requests.append(request.url) if request.url.startswith("http") else None)
    offline.goto(export.as_uri())
    standalone_graph = offline.locator(".trajectory-energy-overlay")
    standalone_graph.locator(".energy-chart-marker").wait_for()
    assert normalized_graph_rect(offline) == pytest.approx(moved_rect, abs=.004)
    assert offline.evaluate("window.v_aseStandalone.scene.settings.display.energyOverlay.axes") == {
        'xMin': -.03, 'xMax': 9, 'yMin': -.2, 'yMax': .2,
    }
    standalone_graph.locator("canvas").press("End")
    assert offline.locator("#frame-label").inner_text() == "3 / 3"
    assert standalone_graph.get_attribute("data-frame") == "2"
    assert not requests


def test_neb_graph_styles_png_csv_and_html_inclusion(trajectory_workbench, tmp_path):
    page, frame = trajectory_workbench
    frame.locator("#btn-match-trajectory").click()
    frame.locator("#trajectory-match-apply").click()
    frame.wait_for_function("document.getElementById('modal-container').classList.contains('hidden')")
    overlays = page.locator('#workspace-scene-list [data-scene-group="overlays"]')
    energy = overlays.locator('[data-scene-id="trajectory-energy"]')
    energy.locator(".scene-visibility").click()
    energy.locator(".scene-select").click()
    graph = frame.locator(".trajectory-energy-overlay")
    graph.locator(".energy-chart-marker").wait_for()
    frame.locator("#energy-data-mode").select_option("markers")
    frame.locator("#energy-marker-shape").select_option("diamond")
    frame.locator("#energy-grid").uncheck()
    frame.locator("#energy-neb-settings > summary").click()
    frame.locator("#energy-neb-fit").check()
    frame.locator("#energy-neb-tangents").check()
    frame.locator("#energy-tangent-scale").fill("1.6")
    frame.locator("#graph-series").select_option("fit")
    frame.locator("#energy-line-style").select_option("dash")
    frame.wait_for_function("document.getElementById('energy-neb-status').textContent.includes('frames 1–3')")
    mic = frame.locator("#energy-neb-mic")
    assert mic.is_checked()
    path_end = "window.__ASE_APP__.trajectoryEnergyOverlay?.data?.neb?.path.at(-1)"
    frame.wait_for_function(f"{path_end} === .5")
    for enabled, distance in ((False, 8), (True, .5), (False, 8)):
        mic.set_checked(enabled)
        frame.wait_for_function(f"{path_end} === {distance}")

    frame.locator("#energy-background-mode").select_option("transparent")
    assert graph.evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"
    with page.expect_download() as image_download:
        frame.locator("#btn-export-energy-image").click()
    with Image.open(image_download.value.path()) as image:
        alpha = image.convert("RGBA").getchannel("A")
        assert alpha.getextrema() == (0, 255)

    with page.expect_download() as csv_download:
        frame.locator("#btn-export-energy-csv").click()
    with csv_download.value.path().open(newline="") as stream:
        records = list(csv.DictReader(stream))
    assert [int(row["frame"]) for row in records if row["series"] == "sample"] == [1, 2, 3]
    assert [float(row["path_A"]) for row in records if row["series"] == "sample"] == [0, 7.75, 8]
    assert sum(row["series"] == "ase_fit" for row in records) == 41
    assert sum(row["series"] == "force_tangent" for row in records) == 6

    frame.locator("#energy-background-mode").select_option("color")
    frame.locator("#energy-background-color").fill("#254466")
    with page.expect_response(lambda response: "/api/preferences/energy-background/" in response.url) as stored:
        frame.locator("#btn-energy-default-background").click()
    assert stored.value.json() == {"backgroundMode": "color", "background": "#254466"}
    assert frame.evaluate("""async () => {
        const defaults = await window.__ASE_APP__.api.fetchUserVisualDefaults();
        return defaults.energyBackground.background;
    }""") == "#254466"

    frame.evaluate("""() => {
        const app = window.__ASE_APP__;
        app.openEditorRoute('render-html');
        app.setAIAxisView('+Z');
        app.setRenderAreaVisible(true);
        app.renderer.renderNow();
    }""")
    frame.locator("#btn-export-html").click()
    include = frame.locator("#html-include-graph")
    assert include.is_checked()
    preview = frame.locator("#html-export-preview")
    frame.wait_for_function("document.getElementById('html-export-preview').dataset.includesGraph === 'true'")
    image = Image.open(BytesIO(base64.b64decode(preview.get_attribute("src").split(",")[1]))).convert("RGB")
    assert dict((color, count) for count, color in image.getcolors(image.width * image.height))[(37, 68, 102)] > 200
    include.uncheck()
    frame.wait_for_function("document.getElementById('html-export-preview').dataset.includesGraph === 'false'")
    no_graph_url = preview.get_attribute("src")
    include.check()
    frame.wait_for_function("document.getElementById('html-export-preview').dataset.includesGraph === 'true'")
    assert preview.get_attribute("src") != no_graph_url

    with page.expect_download() as html_download:
        frame.locator("#html-export-confirm").click()
    output = tmp_path / "phenenergy.html"
    html_download.value.save_as(output)
    offline = page.context.new_page()
    network = []
    offline.on("request", lambda request: network.append(request.url) if request.url.startswith("http") else None)
    offline.goto(output.as_uri())
    offline_graph = offline.locator(".trajectory-energy-overlay")
    offline_graph.locator(".energy-chart-marker").wait_for()
    assert offline.locator("#viewer-frame").get_attribute("data-energy-in-poster") == "true"
    assert offline_graph.evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(37, 68, 102)"
    assert offline.evaluate("window.v_aseStandalone.scene.settings.display.energyOverlay.neb.mic") is False
    assert offline.evaluate("window.v_aseStandalone.scene.trajectoryEnergy.neb.path") == [0, 7.75, 8]
    offline_graph.locator("canvas").press("End")
    assert offline.locator("#frame-label").inner_text() == "3 / 3"
    assert not network

    frame.locator("#btn-export-html").click()
    include.uncheck()
    frame.wait_for_function("document.getElementById('html-export-preview').dataset.includesGraph === 'false'")
    with page.expect_download() as excluded_download:
        frame.locator("#html-export-confirm").click()
    excluded = tmp_path / "structure-only.html"
    excluded_download.value.save_as(excluded)
    offline.goto(excluded.as_uri())
    offline.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
    assert offline.locator(".trajectory-energy-overlay").count() == 0
    assert offline.evaluate("window.v_aseStandalone.scene.trajectoryEnergy") is None
    assert graph.is_visible()


def test_match_button_uses_first_frame_and_remains_undoable(trajectory_workbench):
    _, frame = trajectory_workbench
    frame.locator("#btn-frame-next").click()
    frame.wait_for_function("window.__ASE_APP__.state.atoms.chemical_symbols[0] === 'O'")
    frame.locator("#btn-match-trajectory").click()
    assert frame.locator('[name="trajectory-match"]:checked').input_value() == "mic"
    assert frame.locator('[name="trajectory-match"]').count() == 3
    frame.locator("#trajectory-match-apply").click()
    frame.wait_for_function("window.__ASE_APP__.state.atoms.chemical_symbols[0] === 'Cu'")
    assert frame.locator("#frame-label").inner_text() == "2 / 3"
    frame.evaluate("window.__ASE_APP__.performUndo()")
    assert frame.evaluate("window.__ASE_APP__.state.atoms.chemical_symbols[0]") == "O"


def test_drop_replace_structure_only_keeps_current_render_setup(trajectory_workbench, tmp_path):
    page, frame = trajectory_workbench
    snapshot = frame.evaluate("""() => {
        const app = window.__ASE_APP__;
        app.setAIAxisView('+Y');
        app.setRenderAreaVisible(true);
        const settings = app.designSettingsSnapshot();
        settings.display.labelColors.O = '#2266cc';
        app.applyDesignSettings(settings);
        app.markProjectSavedContent();
        return {session: app.sessionId, camera: app.currentCameraForExport(), profile: app.currentImageExportProfile()};
    }""")
    incoming = tmp_path / "incoming.extxyz"
    write(incoming, Atoms("O", positions=[[0, 1, 2]]))
    frame.evaluate("""text => {
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(new File([text], 'incoming.extxyz'));
        document.body.dispatchEvent(new DragEvent('drop', {bubbles:true, cancelable:true, dataTransfer}));
    }""", Path(incoming).read_text())
    option = frame.locator('[name="open-file-mode"][value="structure-only"]')
    option.check()
    assert frame.locator(".open-file-runtime").is_hidden()
    frame.locator("#open-file-confirm").click()
    page.wait_for_function("!window.__vaseFileOpenQueue.running")
    observed = frame.evaluate("""() => {
        const app = window.__ASE_APP__;
        return {session: app.sessionId, camera: app.currentCameraForExport(), profile: app.currentImageExportProfile(),
            coordinates: app.state.atoms.positions, color: app.state.display.labelColors.O, dirty: app.projectFile.dirty};
    }""")
    assert observed["coordinates"] == [[0, 1, 2]]
    assert observed["color"] == "#2266cc" and observed["dirty"]
    assert observed["session"] == snapshot["session"]
    for key in ("position", "target", "up"):
        assert observed["camera"][key] == pytest.approx(snapshot["camera"][key])
    assert observed["profile"] == snapshot["profile"]


@pytest.mark.parametrize("framing", ["viewport", "physical"])
def test_selected_camera_axis_resize_and_ratio_lock(trajectory_workbench, framing):
    _, frame = trajectory_workbench
    frame.evaluate("""() => {
        const app = window.__ASE_APP__;
        app.setAIAxisView('+Z');
        app.setRenderAreaVisible(true);
        app.captureRenderAreaCamera();
        app.setRenderAreaSelected(true);
        app.openEditorRoute('export');
    }""")
    frame.locator("#renderer-framing-mode").select_option(framing)
    width = frame.locator("#image-width")
    height = frame.locator("#image-height")
    fixed = frame.locator("#renderer-fix-ratio")
    assert not fixed.is_checked()
    before_width, before_height = int(width.input_value()), int(height.input_value())
    canvas = frame.locator("#app-viewport > canvas")
    canvas.focus()
    for key in ("s", "x", "2"):
        canvas.press(key)
    assert int(width.input_value()) == 2 * before_width
    assert int(height.input_value()) == before_height
    canvas.press("Escape")
    assert int(width.input_value()) == before_width

    for view_axis, scale_axis in (("+Z", "y"), ("+Y", "z")):
        frame.evaluate("""axis => {
            const app = window.__ASE_APP__;
            app.setAIAxisView(axis);
            app.captureRenderAreaCamera();
            app.setRenderAreaSelected(true);
        }""", view_axis)
        for key in ("s", scale_axis, "2"):
            canvas.press(key)
        assert int(width.input_value()) == before_width
        assert int(height.input_value()) == 2 * before_height
        canvas.press("Escape")
    frame.evaluate("""() => {
        const app = window.__ASE_APP__;
        app.setAIAxisView('+Z');
        app.captureRenderAreaCamera();
        app.setRenderAreaSelected(true);
    }""")

    fixed.check()
    canvas.focus()
    for key in ("s", "x", "2"):
        canvas.press(key)
    assert int(width.input_value()) == 2 * before_width
    assert int(height.input_value()) == 2 * before_height
    canvas.press("Enter")
    height.fill(str(before_height))
    assert int(width.input_value()) == before_width
