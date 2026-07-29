import base64
import json
from pathlib import Path
import re

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.constraints import FixedPlane
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.export import HTML_VIEW_SCHEMA, export_html_response
from v_ase.io import set_atom_labels
from v_ase.project import read_project_archive
from v_ase.session import EditorSession
from v_ase.viewer import find_free_port, view


def _embedded_base64(html, element_id):
    match = re.search(
        rf'<script id="{re.escape(element_id)}"[^>]*>([^<]+)</script>',
        html,
    )
    assert match, f"Missing embedded payload {element_id}"
    return "".join(match.group(1).split())


def _html_export_fixture():
    first = Atoms(
        "CuO",
        positions=[[0.0, 0.0, 0.0], [1.8, 0.0, 0.0]],
        cell=[[5.0, 0.0, 0.0], [0.4, 5.5, 0.0], [0.0, 0.0, 7.0]],
        pbc=True,
    )
    first.set_constraint(FixedPlane(1, [0, 0, 1]))
    set_atom_labels(first, ["Cu_surface", "O_ads"])
    first.calc = SinglePointCalculator(
        first,
        energy=-1.25,
        forces=np.zeros((2, 3)),
    )
    second = first.copy()
    second.positions[1] = [2.05, 0.25, 0.0]
    second.calc = SinglePointCalculator(
        second,
        energy=-1.40,
        forces=np.full((2, 3), 0.1),
    )
    session = EditorSession(
        "html-export",
        first.copy(),
        second.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=1,
        config={"viz_only": True, "document_name": "CuO trajectory.extxyz"},
    )
    session.working_atoms = second.copy()
    session.trajectory_frames[0].calc = SinglePointCalculator(
        session.trajectory_frames[0],
        energy=-1.25,
        forces=np.zeros((2, 3)),
    )
    session.trajectory_frames[1].calc = SinglePointCalculator(
        session.trajectory_frames[1],
        energy=-1.40,
        forces=np.full((2, 3), 0.1),
    )
    session.working_atoms.calc = SinglePointCalculator(
        session.working_atoms,
        energy=-1.40,
        forces=np.full((2, 3), 0.1),
    )
    settings = {
        "schema": "v_ase.visual_settings.v3",
        "display": {
            "showBonds": True,
            "showCell": True,
            "showAxes": False,
            "showGrid": False,
            "showOverlays": True,
            "bondMode": "pairwise",
            "pairwiseBondRanges": {
                "Cu_surface-O_ads": {"enabled": True, "min": 0.0, "max": 2.4},
            },
            "atomRadiusScale": 0.6,
            "labelColors": {"Cu_surface": "#c98a43", "O_ads": "#e1262f"},
            "labelMaterials": {"Cu_surface": "metal", "O_ads": "standard"},
            "supercell": [2, 1, 1],
            "translation": [0.2, 0.0, 0.0],
            "translationMode": "cartesian",
            "projectionMode": "orthographic",
            "viewportBackground": "white",
            "lightingMode": "studio-shadow",
            "sunIntensity": 2.4,
            "sunPosition": [8, -10, 14],
            "sunTarget": [0, 0, 0],
            "showDisplacements": True,
            "displacementReferenceMode": "previous",
            "displacementMic": True,
            "displacementStyle": "3d",
            "displacementScale": 1.0,
            "displacementThickness": 0.08,
            "displacementColor": "#e58b2a",
        },
        "camera": {
            "position": [7.5, -8.0, 6.5],
            "target": [1.0, 0.5, 0.0],
            "up": [0.0, 0.0, 1.0],
            "projection": "orthographic",
            "fov": 50.0,
            "zoom": 1.0,
            "ortho_scale": 8.5,
            "near": 0.1,
            "far": 1000.0,
            "aspect": 16 / 9,
        },
        "applyConstraints": True,
        "antiAliasing": True,
        "sphereQuality": "high",
    }
    response = export_html_response(
        session,
        {
            "positions": second.positions.tolist(),
            "settings": settings,
            "selection": [1],
            "document_name": "CuO trajectory.extxyz",
        },
    )
    return response, second, settings


def test_html_export_is_self_contained_and_embeds_lossless_vase(tmp_path):
    response, second, settings = _html_export_fixture()
    html = response.body.decode("utf-8")
    assert response.media_type == "text/html"
    assert response.headers["x-v-ase-view-schema"] == HTML_VIEW_SCHEMA
    assert response.headers["x-v-ase-frame-count"] == "2"
    assert 'data-v-ase-mode="view-only"' in html
    assert "VIEW ONLY" in html
    assert "Download .vase" in html
    assert "<script src=" not in html
    assert "<link rel=\"stylesheet\"" not in html
    assert "connect-src 'none'" in html
    assert "{{" not in html and "}}" not in html

    scene = json.loads(base64.b64decode(
        _embedded_base64(html, "v-ase-scene-data")
    ).decode("utf-8"))
    assert scene["schema"] == HTML_VIEW_SCHEMA
    assert scene["currentFrame"] == 1
    assert scene["selection"] == [1]
    assert len(scene["frames"]) == 2
    assert scene["settings"]["display"]["labelMaterials"]["Cu_surface"] == "metal"
    assert scene["settings"]["camera"]["position"] == settings["camera"]["position"]
    assert scene["displacements"][0] is None
    assert scene["displacements"][1]["status"] == "ok"
    np.testing.assert_allclose(scene["displacements"][1]["vectors"][1], [0.25, 0.25, 0.0])

    archive = tmp_path / "embedded.vase"
    archive.write_bytes(base64.b64decode(
        _embedded_base64(html, "v-ase-project-data")
    ))
    project = read_project_archive(archive)
    assert project.current_frame == 1
    assert len(project.frames) == 2
    assert project.settings["display"]["supercell"] == [2, 1, 1]
    assert project.settings["display"]["translation"] == [0.2, 0.0, 0.0]
    np.testing.assert_allclose(project.frames[1].positions, second.positions)
    assert project.frames[1].constraints
    assert project.frames[1].get_potential_energy() == pytest.approx(-1.40)


def test_exported_html_opens_offline_as_view_only_interactive_trajectory(tmp_path):
    response, _, _ = _html_export_fixture()
    document = tmp_path / "offline_view.html"
    document.write_bytes(response.body)
    network_requests = []

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("request", lambda request: network_requests.append(request.url))
        page.goto(document.as_uri(), wait_until="load")
        page.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
        page.locator(
            "#viewer-frame canvas[data-render-count]:not([data-render-count='0'])"
        ).wait_for(state="attached")

        assert page.locator("#boot-error").is_hidden()
        assert page.locator(".view-only-badge").inner_text() == "VIEW ONLY"
        assert page.locator("#inspector").count() == 0
        assert page.locator("#timeline").is_visible()
        assert page.locator("#frame-label").inner_text() == "2 / 2"
        assert page.locator("#download-project").is_visible()
        assert page.evaluate("window.v_aseStandalone.scene.frames.length") == 2
        assert page.evaluate(
            "window.v_aseStandalone.scene.settings.display.labelMaterials.Cu_surface"
        ) == "metal"
        assert page.evaluate(
            "window.v_aseStandalone.renderer.displacementData?.status"
        ) == "ok"

        page.click("#previous-frame")
        assert page.locator("#frame-label").inner_text() == "1 / 2"
        assert page.evaluate("window.v_aseStandalone.frameIndex") == 0

        before = page.evaluate(
            "window.v_aseStandalone.renderer.camera.quaternion.toArray()"
        )
        canvas = page.locator("#viewer-frame canvas").bounding_box()
        assert canvas
        page.mouse.move(canvas["x"] + canvas["width"] * 0.5, canvas["y"] + canvas["height"] * 0.5)
        page.mouse.down(button="left")
        page.mouse.move(canvas["x"] + canvas["width"] * 0.62, canvas["y"] + canvas["height"] * 0.56)
        page.mouse.up(button="left")
        after = page.evaluate(
            "window.v_aseStandalone.renderer.camera.quaternion.toArray()"
        )
        assert after != pytest.approx(before)

        screenshot = tmp_path / "offline_view.png"
        page.locator("#viewer-frame").screenshot(path=str(screenshot))
        with Image.open(screenshot) as image:
            colors = image.convert("RGB").resize((160, 90)).getcolors(maxcolors=160 * 90)
            assert colors is not None and len(colors) > 20

        assert not [
            url for url in network_requests
            if url.startswith(("http://", "https://"))
        ]

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(100)
        mobile_layout = page.evaluate("""() => {
            const header = document.querySelector('.viewer-header').getBoundingClientRect();
            const frame = document.querySelector('#viewer-frame').getBoundingClientRect();
            const timeline = document.querySelector('#timeline').getBoundingClientRect();
            return {
                scrollWidth: document.documentElement.scrollWidth,
                width: window.innerWidth,
                header: [header.left, header.right, header.top, header.bottom],
                frame: [frame.left, frame.right, frame.top, frame.bottom],
                timeline: [timeline.left, timeline.right, timeline.top, timeline.bottom]
            };
        }""")
        assert mobile_layout["scrollWidth"] <= mobile_layout["width"]
        for box in ("header", "frame", "timeline"):
            left, right, top, bottom = mobile_layout[box]
            assert left >= -1 and right <= mobile_layout["width"] + 1
            assert top >= -1 and bottom <= 844 + 1
        browser.close()


def test_html_export_button_downloads_an_offline_document_that_reopens(tmp_path):
    first = Atoms(
        "CO",
        positions=[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
        cell=[7.0, 7.0, 7.0],
        pbc=True,
    )
    second = first.copy()
    second.positions[1, 1] = 0.35
    port = find_free_port()
    editor = view(
        [first, second],
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
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            if page.locator("body").evaluate(
                "element => element.classList.contains('inspector-collapsed')"
            ):
                page.click("#btn-inspector-collapse")
                page.wait_for_function(
                    "!document.body.classList.contains('inspector-collapsed')"
                )
            page.click('[data-inspector-group="export"]')
            page.wait_for_function(
                "document.querySelector('#btn-export-html')?.getBoundingClientRect().height > 0"
            )
            with page.expect_download() as download_info:
                page.click("#btn-export-html")
            download = download_info.value
            exported = tmp_path / "downloaded_view.html"
            download.save_as(exported)
            assert exported.stat().st_size > 1_000_000

            offline = browser.new_page(viewport={"width": 1280, "height": 800})
            offline.goto(exported.as_uri(), wait_until="load")
            offline.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
            assert offline.locator(".view-only-badge").inner_text() == "VIEW ONLY"
            assert offline.evaluate("window.v_aseStandalone.scene.frames.length") == 2
            assert offline.locator("#timeline").is_visible()
            browser.close()
    finally:
        editor.close()
