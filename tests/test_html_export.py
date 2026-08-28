import base64
import asyncio
import io
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
from v_ase.project import read_project_archive, read_project_html
from v_ase.server import load_visual_settings
from v_ase.session import EditorSession, sessions
from v_ase.viewer import find_free_port, view


def _embedded_base64(html, element_id):
    match = re.search(
        rf'<script id="{re.escape(element_id)}"[^>]*>([^<]+)</script>',
        html,
    )
    assert match, f"Missing embedded payload {element_id}"
    return "".join(match.group(1).split())


class _BodyRequest:
    def __init__(self, body):
        self._body = body

    async def body(self):
        return self._body


def _html_export_fixture(
    *, embed_project=True, atom_colorscale=False, custom_colormap=False,
    view_identity=False,
):
    first = Atoms(
        "CuO",
        positions=[[0.0, 0.0, 0.0], [1.8, 0.0, 0.0]],
        cell=[[5.0, 0.0, 0.0], [0.4, 5.5, 0.0], [0.0, 0.0, 7.0]],
        pbc=True,
    )
    first.set_constraint(FixedPlane(1, [0, 0, 1]))
    set_atom_labels(first, ["Cu_surface", "O_ads"])
    first.new_array("mlip_uncertainty", np.array([0.15, 0.85]))
    first.calc = SinglePointCalculator(
        first,
        energy=-1.25,
        forces=np.zeros((2, 3)),
    )
    second = first.copy()
    second.positions[1] = [2.05, 0.25, 0.0]
    second.arrays["mlip_uncertainty"][:] = [0.25, 0.95]
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
            "labelOpacities": {"Cu_surface": 0.45, "O_ads": 1.0},
            "labelMaterials": {"Cu_surface": "metal", "O_ads": "standard"},
            "atomRadiusScales": {"1": 1.3},
            "atomColors": {"1": "#44aa88"},
            "atomOpacities": {"1": 0.7},
            "atomMaterials": {"1": "rubber"},
            "atomBondStyles": {"1": {"material": "rubber", "opacity": 0.7}},
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
    if atom_colorscale:
        settings["display"].update({
            "atomColorScaleEnabled": True,
            "atomColorScaleField": "array::mlip_uncertainty::scalar",
            "atomColorScaleMap": "viridis",
            "atomColorScaleReverse": False,
            "atomColorScaleScope": "selected",
            "atomColorScaleAutoRange": True,
            "atomColorScaleRangeMode": "trajectory",
            "atomColorScaleMin": 0.15,
            "atomColorScaleMax": 0.95,
            "atomColorScaleGamma": 2.0,
        })
        if custom_colormap:
            settings["display"].update({
                "atomColorScaleMap": "custom",
                "atomColorScaleCustomMap": {
                    "mode": "discrete",
                    "stops": [
                        {"position": 0, "color": "#112233"},
                        {"position": 0.5, "color": "#44AA88"},
                        {"position": 1, "color": "#FFDD55"},
                    ],
                },
            })
    if view_identity:
        settings["viewIdentityOverrides"] = {
            "schema": "v_ase.view_identity.v1",
            "scope": "trajectory",
            "labels": ["Cu_substrate", "O_surface"],
        }
    poster_buffer = io.BytesIO()
    Image.new("RGB", (640, 360), (242, 246, 244)).save(
        poster_buffer,
        format="PNG",
        optimize=True,
    )
    poster_data_url = (
        "data:image/png;base64,"
        + base64.b64encode(poster_buffer.getvalue()).decode("ascii")
    )
    response = export_html_response(
        session,
        {
            "positions": second.positions.tolist(),
            "settings": settings,
            "selection": [1],
            "document_name": "CuO trajectory.extxyz",
            "embed_project": embed_project,
            "poster_data_url": poster_data_url,
            "export_profile": {
                "kind": "html",
                "width": 1920,
                "height": 1080,
                "options": {
                    "includeGrid": False,
                    "includeAxes": True,
                    "includeCell": True,
                    "transparentBackground": False,
                    "backgroundColor": "#ffffff",
                },
                "composition": {
                    "schema": "v_ase.export-composition.v1",
                    "width": 1920,
                    "height": 1080,
                    "aspect": 16 / 9,
                    "options": {
                        "includeGrid": False,
                        "includeAxes": True,
                        "includeCell": True,
                    },
                    "camera": settings["camera"],
                },
            },
        },
    )
    return response, second, settings


def test_html_export_is_self_contained_and_embeds_lossless_vase(tmp_path):
    response, second, settings = _html_export_fixture()
    html = response.body.decode("utf-8")
    assert response.media_type == "text/html"
    assert response.headers["x-v-ase-view-schema"] == HTML_VIEW_SCHEMA
    assert response.headers["x-v-ase-frame-count"] == "2"
    assert response.headers["x-v-ase-embedded-project"] == "true"
    assert 'data-v-ase-mode="view-only"' in html
    assert "VIEW ONLY" in html
    assert "Download .vase" in html
    assert "<script src=" not in html
    assert "<link rel=\"stylesheet\"" not in html
    assert "connect-src 'none'" in html
    assert "{{" not in html and "}}" not in html
    assert 'id="standalone-poster"' in html
    assert 'src="data:image/png;base64,' in html
    assert "aspect-ratio:1920/1080" in html

    scene = json.loads(base64.b64decode(
        _embedded_base64(html, "v-ase-scene-data")
    ).decode("utf-8"))
    assert scene["schema"] == HTML_VIEW_SCHEMA
    assert scene["hasEmbeddedProject"] is True
    assert scene["currentFrame"] == 1
    assert scene["selection"] == [1]
    assert len(scene["frames"]) == 2
    assert scene["settings"]["display"]["labelMaterials"]["Cu_surface"] == "metal"
    assert scene["settings"]["display"]["labelOpacities"]["Cu_surface"] == pytest.approx(0.45)
    assert scene["settings"]["display"]["atomRadiusScales"] == {"1": 1.3}
    assert scene["settings"]["display"]["atomColors"] == {"1": "#44aa88"}
    assert scene["settings"]["display"]["atomOpacities"] == {"1": 0.7}
    assert scene["settings"]["display"]["atomMaterials"] == {"1": "rubber"}
    assert scene["settings"]["display"]["atomBondStyles"] == {
        "1": {"material": "rubber", "opacity": 0.7}
    }
    assert scene["settings"]["camera"]["position"] == settings["camera"]["position"]
    assert scene["hasPoster"] is True
    assert scene["exportProfile"]["width"] == 1920
    assert scene["exportProfile"]["height"] == 1080
    assert scene["exportProfile"]["options"]["includeGrid"] is False
    assert scene["exportProfile"]["options"]["includeAxes"] is True
    assert scene["exportProfile"]["options"]["includeCell"] is True
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


def test_project_embedded_html_can_be_imported_as_a_visual_preset():
    response, _, settings = _html_export_fixture(embed_project=True)
    session = EditorSession(
        "html-settings-import",
        Atoms("H"),
        Atoms("H"),
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    try:
        loaded = asyncio.run(load_visual_settings(
            session.session_id,
            _BodyRequest(response.body),
        ))
    finally:
        sessions.pop(session.session_id, None)

    assert loaded["schema"] == "v_ase.visual_settings.v3"
    assert loaded["settings"]["display"]["supercell"] == [2, 1, 1]
    assert loaded["settings"]["display"]["lightingMode"] == "studio-shadow"
    assert loaded["settings"]["camera"]["position"] == settings["camera"]["position"]


def test_lightweight_html_omits_project_recovery_and_is_smaller(tmp_path):
    embedded, _, _ = _html_export_fixture(embed_project=True)
    lightweight, _, _ = _html_export_fixture(embed_project=False)
    embedded_html = embedded.body.decode("utf-8")
    lightweight_html = lightweight.body.decode("utf-8")

    assert lightweight.headers["x-v-ase-embedded-project"] == "false"
    assert lightweight.headers["x-v-ase-embedded-project-bytes"] == "0"
    assert len(lightweight.body) < len(embedded.body)
    scene = json.loads(base64.b64decode(
        _embedded_base64(lightweight_html, "v-ase-scene-data")
    ).decode("utf-8"))
    assert scene["hasEmbeddedProject"] is False
    assert scene["projectFilename"] == ""
    assert scene["projectSchema"] is None
    assert '<script id="v-ase-project-data"' in lightweight_html

    embedded_path = tmp_path / "recoverable.html"
    embedded_path.write_bytes(embedded.body)
    project = read_project_html(embedded_path)
    assert len(project.frames) == 2
    assert project.current_frame == 1
    assert project.settings["display"]["supercell"] == [2, 1, 1]

    lightweight_path = tmp_path / "view-only.html"
    lightweight_path.write_bytes(lightweight.body)
    with pytest.raises(ValueError, match="no embedded .vase project"):
        read_project_html(lightweight_path)


def test_html_export_freezes_active_selected_atom_colorscale_for_offline_frames():
    response, _, _ = _html_export_fixture(embed_project=False, atom_colorscale=True)
    html = response.body.decode("utf-8")
    scene = json.loads(base64.b64decode(
        _embedded_base64(html, "v-ase-scene-data")
    ).decode("utf-8"))

    frame_colors = []
    for frame in scene["frames"]:
        scale = frame["metadata"]["atom_color_scale"]
        assert scale["field_id"] == "array::mlip_uncertainty::scalar"
        assert scale["map"] == "viridis"
        assert scale["scope"] == "selected"
        assert scale["range_mode"] == "trajectory"
        assert scale["minimum"] == pytest.approx(0.15)
        assert scale["maximum"] == pytest.approx(0.95)
        assert scale["gamma"] == pytest.approx(2.0)
        assert scale["colors"][0] is None
        assert re.fullmatch(r"#[0-9A-F]{6}", scale["colors"][1])
        frame_colors.append(scale["colors"][1])
    assert frame_colors[0] != frame_colors[1]


def test_html_export_freezes_custom_colormap_definition_and_colors():
    response, _, _ = _html_export_fixture(
        embed_project=False,
        atom_colorscale=True,
        custom_colormap=True,
    )
    scene = json.loads(base64.b64decode(
        _embedded_base64(response.body.decode("utf-8"), "v-ase-scene-data")
    ).decode("utf-8"))
    scale = scene["frames"][0]["metadata"]["atom_color_scale"]
    assert scale["map"] == "custom"
    assert scale["custom_map"]["mode"] == "discrete"
    assert scale["custom_map"]["stops"][1] == {
        "position": 0.5,
        "color": "#44AA88",
    }
    assert scale["colors"][0] is None
    assert scale["colors"][1] in {"#112233", "#44AA88", "#FFDD55"}


def test_html_export_preserves_view_labels_without_changing_ase_elements(tmp_path):
    response, _, _ = _html_export_fixture(
        embed_project=True,
        view_identity=True,
    )
    html = response.body.decode("utf-8")
    scene = json.loads(base64.b64decode(
        _embedded_base64(html, "v-ase-scene-data")
    ).decode("utf-8"))
    assert [frame["symbols"] for frame in scene["frames"]] == [
        ["Cu_substrate", "O_surface"],
        ["Cu_substrate", "O_surface"],
    ]
    assert [frame["chemical_symbols"] for frame in scene["frames"]] == [
        ["Cu", "O"],
        ["Cu", "O"],
    ]

    archive = tmp_path / "identity.vase"
    archive.write_bytes(base64.b64decode(
        _embedded_base64(html, "v-ase-project-data")
    ))
    project = read_project_archive(archive)
    assert project.settings["viewIdentityOverrides"]["labels"] == [
        "Cu_substrate",
        "O_surface",
    ]
    assert project.frames[0].get_chemical_symbols() == ["Cu", "O"]


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
        assert page.locator(".wordmark").count() == 0
        assert page.evaluate(
            "getComputedStyle(document.querySelector('.viewer-toolbar')).opacity"
        ) == "0"
        page.locator("html[data-v-ase-poster='replaced']").wait_for(state="attached")
        assert page.evaluate(
            "getComputedStyle(document.querySelector('.viewer-toolbar')).opacity"
        ) == "0"
        assert page.locator("#inspector").count() == 0
        assert page.locator("#timeline").is_visible()
        assert page.locator("#frame-label").inner_text() == "2 / 2"
        assert page.locator("#download-project").is_visible()
        assert page.evaluate("window.v_aseStandalone.hasEmbeddedProject") is True
        assert page.evaluate("window.v_aseStandalone.scene.frames.length") == 2
        assert page.locator("html").get_attribute("data-v-ase-atom-count") == "2"
        assert page.evaluate(
            "window.v_aseStandalone.scene.settings.display.labelMaterials.Cu_surface"
        ) == "metal"
        assert page.evaluate(
            "window.v_aseStandalone.scene.settings.display.labelOpacities.Cu_surface"
        ) == pytest.approx(0.45)
        assert page.evaluate(
            "window.v_aseStandalone.renderer.displacementData?.status"
        ) == "ok"

        page.mouse.move(40, 40)
        page.locator("html[data-v-ase-ui='visible']").wait_for(state="attached")
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
        rendered_atoms = page.evaluate("""() => {
            const standalone = window.v_aseStandalone;
            const renderer = standalone.renderer;
            const rect = renderer.domElement.getBoundingClientRect();
            renderer.camera.updateMatrixWorld(true);
            const samples = [...renderer.atomMeshByIndex.keys()].map(index => {
                const projected = renderer.getAtomPosition(index)
                    .clone()
                    .project(renderer.camera);
                return {
                    index,
                    ndc: projected.toArray(),
                    pixel: [
                        (projected.x * 0.5 + 0.5) * rect.width,
                        (-projected.y * 0.5 + 0.5) * rect.height
                    ]
                };
            });
            return {
                width: rect.width,
                height: rect.height,
                samples,
                renderCount: Number(renderer.domElement.dataset.renderCount || 0)
            };
        }""")
        assert rendered_atoms["width"] > 500
        assert rendered_atoms["height"] > 250
        assert rendered_atoms["renderCount"] > 0
        assert len(rendered_atoms["samples"]) == 2
        for sample in rendered_atoms["samples"]:
            assert -1 < sample["ndc"][0] < 1
            assert -1 < sample["ndc"][1] < 1
            assert 0 < sample["pixel"][0] < rendered_atoms["width"]
            assert 0 < sample["pixel"][1] < rendered_atoms["height"]

        assert not [
            url for url in network_requests
            if url.startswith(("http://", "https://"))
        ]

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(100)
        mobile_layout = page.evaluate("""() => {
            const toolbar = document.querySelector('.viewer-toolbar').getBoundingClientRect();
            const frame = document.querySelector('#viewer-frame').getBoundingClientRect();
            const timeline = document.querySelector('#timeline').getBoundingClientRect();
            return {
                scrollWidth: document.documentElement.scrollWidth,
                width: window.innerWidth,
                toolbar: [toolbar.left, toolbar.right, toolbar.top, toolbar.bottom],
                frame: [frame.left, frame.right, frame.top, frame.bottom],
                timeline: [timeline.left, timeline.right, timeline.top, timeline.bottom]
            };
        }""")
        assert mobile_layout["scrollWidth"] <= mobile_layout["width"]
        for box in ("toolbar", "frame", "timeline"):
            left, right, top, bottom = mobile_layout[box]
            assert left >= -1 and right <= mobile_layout["width"] + 1
            assert top >= -1 and bottom <= 844 + 1
        browser.close()


def test_lightweight_html_opens_offline_without_project_download(tmp_path):
    response, _, _ = _html_export_fixture(embed_project=False)
    document = tmp_path / "lightweight_view.html"
    document.write_bytes(response.body)

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        page = browser.new_page(viewport={"width": 960, "height": 640})
        page.goto(document.as_uri(), wait_until="load")
        page.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
        assert page.locator("#download-project").is_hidden()
        assert page.evaluate("window.v_aseStandalone.hasEmbeddedProject") is False
        assert page.evaluate("window.v_aseStandalone.projectBytes().length") == 0
        assert page.evaluate(
            "window.v_aseStandalone.scene.frames.length"
        ) == 2
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
            page.fill("#image-width", "900")
            page.fill("#image-height", "900")
            page.click("#btn-preview-image")
            page.wait_for_function(
                "!document.querySelector('#export-preview-frame')?.classList.contains('hidden')"
            )
            preview_frame_box = page.locator("#export-preview-frame").bounding_box()
            assert preview_frame_box
            assert preview_frame_box["width"] / preview_frame_box["height"] == pytest.approx(
                1.0,
                abs=0.01,
            )
            page.click("#btn-export-html")
            page.locator("#html-export-confirm").wait_for(state="visible")
            assert page.locator("#html-embed-project").is_checked() is False
            assert page.locator("#html-include-grid").is_checked() is False
            assert page.locator("#html-include-axes").is_checked() is True
            assert page.locator("#html-include-cell").is_checked() is True
            assert page.locator("#html-export-width").count() == 0
            assert page.locator("#html-export-height").count() == 0
            assert page.locator(".html-composition-readout strong").inner_text() == "900 x 900"
            page.wait_for_function("""() => {
                const figure = document.querySelector('.html-view-preview');
                const image = document.getElementById('html-export-preview');
                return figure && !figure.classList.contains('loading')
                    && image?.src?.startsWith('data:image/png;base64,')
                    && document.getElementById('html-export-preview-caption')
                        ?.textContent.includes('900 x 900');
            }""")
            preview_source = page.locator("#html-export-preview").get_attribute("src")
            assert preview_source and preview_source.startswith("data:image/png;base64,")
            preview_bytes = base64.b64decode(preview_source.split(",", 1)[1])
            preview_path = tmp_path / "html_modal_preview.png"
            preview_path.write_bytes(preview_bytes)
            with Image.open(preview_path) as preview_image:
                assert preview_image.size == (900, 900)
                colors = preview_image.convert("RGB").resize((160, 90)).getcolors(
                    maxcolors=160 * 90
                )
                assert colors is not None and len(colors) > 20
            page.check("#html-embed-project")
            with page.expect_download() as download_info:
                page.click("#html-export-confirm")
            download = download_info.value
            exported = tmp_path / "downloaded_view.html"
            download.save_as(exported)
            assert exported.stat().st_size > 1_000_000

            offline = browser.new_page(viewport={"width": 1280, "height": 800})
            offline.goto(exported.as_uri(), wait_until="load")
            offline.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
            assert offline.locator(".view-only-badge").inner_text() == "VIEW ONLY"
            assert offline.locator(".wordmark").count() == 0
            assert offline.evaluate(
                "getComputedStyle(document.querySelector('.viewer-toolbar')).opacity"
            ) == "0"
            before_box = offline.locator("#viewer-frame").bounding_box()
            assert before_box
            poster_source = offline.locator("#standalone-poster").get_attribute("src")
            assert poster_source and poster_source.startswith("data:image/png;base64,")
            embedded_poster = tmp_path / "offline_embedded_poster.png"
            embedded_poster.write_bytes(base64.b64decode(poster_source.split(",", 1)[1]))
            offline.locator("html[data-v-ase-poster='replaced']").wait_for(
                state="attached"
            )
            after_box = offline.locator("#viewer-frame").bounding_box()
            assert after_box == pytest.approx(before_box)
            assert offline.evaluate(
                "getComputedStyle(document.querySelector('.viewer-toolbar')).opacity"
            ) == "0"
            assert offline.locator("html").get_attribute("data-v-ase-atom-count") == "2"
            assert offline.evaluate("window.v_aseStandalone.scene.frames.length") == 2
            assert offline.evaluate("window.v_aseStandalone.scene.exportProfile.width") == 900
            assert offline.evaluate("window.v_aseStandalone.scene.exportProfile.height") == 900
            assert offline.evaluate(
                "window.v_aseStandalone.scene.exportProfile.options.includeGrid"
            ) is False
            assert offline.evaluate(
                "window.v_aseStandalone.scene.exportProfile.options.includeAxes"
            ) is True
            assert offline.evaluate(
                "window.v_aseStandalone.scene.exportProfile.options.includeCell"
            ) is True
            assert offline.locator("#timeline").is_visible()
            frame_box = offline.locator("#viewer-frame").bounding_box()
            assert frame_box
            assert frame_box["width"] / frame_box["height"] == pytest.approx(1.0, abs=0.01)
            with Image.open(preview_path) as expected, Image.open(embedded_poster) as actual:
                expected_pixels = np.asarray(
                    expected.convert("RGB").resize((256, 256)),
                    dtype=np.int16,
                )
                actual_pixels = np.asarray(
                    actual.convert("RGB").resize((256, 256)),
                    dtype=np.int16,
                )
            assert np.abs(expected_pixels - actual_pixels).mean() < 18
            interactive_frame = tmp_path / "offline_interactive_frame.png"
            offline.locator("#viewer-frame").screenshot(path=str(interactive_frame))
            with Image.open(embedded_poster) as expected, Image.open(interactive_frame) as actual:
                expected_pixels = np.asarray(
                    expected.convert("RGB").resize((256, 256)),
                    dtype=np.int16,
                )
                actual_pixels = np.asarray(
                    actual.convert("RGB").resize((256, 256)),
                    dtype=np.int16,
                )
            assert np.abs(expected_pixels - actual_pixels).mean() < 18
            before_rotation = offline.evaluate(
                "window.v_aseStandalone.renderer.camera.quaternion.toArray()"
            )
            offline_canvas = offline.locator("#viewer-frame canvas").bounding_box()
            assert offline_canvas
            offline.mouse.move(
                offline_canvas["x"] + offline_canvas["width"] * 0.5,
                offline_canvas["y"] + offline_canvas["height"] * 0.5,
            )
            offline.mouse.down(button="left")
            offline.mouse.move(
                offline_canvas["x"] + offline_canvas["width"] * 0.64,
                offline_canvas["y"] + offline_canvas["height"] * 0.58,
                steps=6,
            )
            offline.mouse.up(button="left")
            after_rotation = offline.evaluate(
                "window.v_aseStandalone.renderer.camera.quaternion.toArray()"
            )
            assert after_rotation != pytest.approx(before_rotation)

            page.set_input_files("#project-file", exported)
            page.wait_for_function(
                "window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2"
            )
            assert page.evaluate(
                "window.__ASE_APP__.state.display.supercell.join(',')"
            ) == "1,1,1"

            page.click("#btn-save-project")
            assert page.locator("#modal-content h2").inner_text() == "Save Project"
            assert not page.locator("#project-include-interactive-viewer").is_checked()
            assert page.locator("#project-output-extension").inner_text() == ".vase"
            assert page.locator("#project-output-filename").inner_text().endswith(".vase")
            assert page.locator("#html-rendering-options").is_hidden()
            assert page.locator("#html-export-confirm").inner_text() == "Save .vase"

            with page.expect_download() as compact_download_info:
                page.click("#html-export-confirm")
            compact_download = compact_download_info.value
            compact_project = tmp_path / "unified-save-project.vase"
            compact_download.save_as(compact_project)
            assert compact_download.suggested_filename.endswith(".vase")
            assert compact_project.read_bytes().startswith(b"PK")

            page.click("#btn-save-project")

            page.check("#project-include-interactive-viewer")
            assert page.locator("#project-output-extension").inner_text() == ".html"
            assert page.locator("#project-output-filename").inner_text().endswith(".html")
            assert page.locator("#html-rendering-options").is_visible()
            assert page.locator("#html-embed-project").count() == 0
            assert page.locator("#html-export-confirm").inner_text() == "Save .html"
            page.wait_for_function("""() => {
                const figure = document.querySelector('.html-view-preview');
                const image = document.getElementById('html-export-preview');
                return figure && !figure.classList.contains('loading')
                    && image?.src?.startsWith('data:image/png;base64,');
            }""")
            with page.expect_download() as html_project_download_info:
                page.click("#html-export-confirm")
            html_project_download = html_project_download_info.value
            html_project = tmp_path / "unified-save-project.html"
            html_project_download.save_as(html_project)
            assert html_project_download.suggested_filename.endswith(".html")
            assert html_project.stat().st_size > compact_project.stat().st_size

            saved_html = browser.new_page(viewport={"width": 960, "height": 640})
            saved_html.goto(html_project.as_uri(), wait_until="load")
            saved_html.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
            assert saved_html.evaluate("window.v_aseStandalone.hasEmbeddedProject") is True
            assert saved_html.evaluate("window.v_aseStandalone.projectBytes().length") > 0
            saved_html.close()
            browser.close()
    finally:
        editor.close()


def test_static_html_poster_is_the_only_visible_preview_surface_without_javascript(tmp_path):
    response, _, _ = _html_export_fixture(embed_project=False)
    document = tmp_path / "static_preview.html"
    document.write_bytes(response.body)

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            java_script_enabled=False,
        )
        page = context.new_page()
        page.goto(document.as_uri(), wait_until="load")
        frame = page.locator("#viewer-frame").bounding_box()
        assert frame == pytest.approx({"x": 0, "y": 0, "width": 1280, "height": 720})
        assert page.locator("#standalone-poster").is_visible()
        assert page.locator(".wordmark").count() == 0
        assert page.evaluate(
            "getComputedStyle(document.querySelector('.viewer-toolbar')).opacity"
        ) == "0"
        screenshot = tmp_path / "static_preview.png"
        page.screenshot(path=str(screenshot))
        with Image.open(screenshot) as image:
            assert image.size == (1280, 720)
            border = np.asarray(image.convert("RGB"))
            assert np.array_equal(border[0, 0], border[360, 640])
        context.close()
        browser.close()
