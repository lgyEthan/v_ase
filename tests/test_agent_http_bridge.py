"""End-to-end checks for the vendor-neutral HTTP command bridge."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
import time

import numpy as np
import pytest
import requests
from ase import Atoms
from ase.constraints import FixAtoms
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.ai import ai_handshake
from v_ase.io import atom_labels, set_atom_labels
from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


def _post_command(url: str, method: str, params=None, *, expected_status: int = 200):
    response = requests.post(
        url,
        json={"method": method, "params": {} if params is None else params},
        timeout=30,
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def _run_cli_command(url: str, method: str, params=None):
    command = [
        sys.executable,
        "-m",
        "v_ase.cli",
        "api",
        url,
        method,
    ]
    if params is not None:
        command.extend(["--params", json.dumps(params, separators=(",", ":"))])
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)["result"]


def test_external_cli_agent_scatter_repels_and_commits_random_atoms():
    host = Atoms(
        "Cu4O2",
        positions=[
            [0.8, 0.9, 1.1], [4.9, 1.2, 1.6], [2.3, 4.4, 2.2],
            [6.1, 4.9, 3.1], [2.8, 2.5, 4.8], [5.5, 3.0, 5.1],
        ],
        cell=[[7.6, 0.0, 0.0], [1.7, 6.5, 0.0], [-0.6, 1.1, 6.2]],
        pbc=True,
    )
    set_atom_labels(host, ["Cu_host"] * 4 + ["O_host"] * 2)
    host.set_tags([9, 8, 7, 6, 5, 4])
    host.new_array("site_weight", np.asarray([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]))
    host.set_constraint(FixAtoms(indices=[0]))
    baseline_positions = host.positions.copy()
    baseline_arrays = {name: values.copy() for name, values in host.arrays.items()}
    baseline_constraints = [repr(item) for item in host.constraints]

    port = find_free_port()
    editor = view(
        host,
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    handshake = ai_handshake(editor.url)
    command_url = str(handshake["command_url"])

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            page.wait_for_function(
                """sessionId => {
                    const frame = document.querySelector(
                        `iframe[data-session-id="${sessionId}"]`
                    );
                    return Boolean(frame?.contentWindow?.__ASE_APP__);
                }""",
                arg=editor.session_id,
            )
            child = next(
                frame for frame in page.frames if "workspace_child=1" in frame.url
            )

            capabilities = _run_cli_command(command_url, "capabilities")
            assert {
                "scatter-atoms", "relax-added-atoms", "stop-added-atoms",
                "finish-add-atoms", "cancel-add-atoms",
            } <= set(capabilities["operations"])

            initial = _run_cli_command(
                command_url,
                "describe",
                {"includePositions": True},
            )
            scattered = _run_cli_command(command_url, "apply", {
                "expectedRevision": initial["collaboration"]["revision"],
                "mode": "edit",
                "operation": {
                    "name": "scatter-atoms",
                    "entries": [
                        {"element": "Li", "label": "Li_mobile", "count": 7},
                        {"element": "H", "label": "H_probe", "count": 3},
                    ],
                    "regionMode": "cell",
                    "seed": 2021,
                    "freezeExisting": True,
                    "cutoffBasis": "covalent",
                    "cutoffScale": 0.7,
                },
            })
            assert scattered["addAtoms"]["new_count"] == 10
            assert scattered["atomCount"] == len(host) + 10
            child.wait_for_function(
                "window.__ASE_APP__?.renderer?.addAtomsRegionGroup?.visible === true"
            )
            child.wait_for_function(
                f"window.__ASE_APP__?.state?.atoms?.positions?.length === {len(host) + 10}"
            )

            running = _run_cli_command(command_url, "apply", {
                "expectedRevision": scattered["collaboration"]["revision"],
                "operation": {
                    "name": "relax-added-atoms",
                    "pairCutoffs": scattered["addAtoms"]["pair_cutoffs"],
                    "freezeExisting": True,
                    "strength": 2.0,
                    "fmax": 0.1,
                    "steps": 20,
                    "mic": True,
                },
            })
            assert running["addAtoms"]["is_relaxing"] is True

            deadline = time.monotonic() + 20.0
            placed = running
            while placed["addAtoms"]["is_relaxing"] and time.monotonic() < deadline:
                time.sleep(0.1)
                placed = _run_cli_command(
                    command_url,
                    "describe",
                    {"includePositions": False},
                )
            assert placed["addAtoms"]["is_relaxing"] is False
            assert placed["addAtoms"]["status"] != "error"

            committed = _run_cli_command(command_url, "apply", {
                "expectedRevision": placed["collaboration"]["revision"],
                "operation": "finish-add-atoms",
            })
            assert committed["addAtoms"] is None
            assert committed["atomCount"] == len(host) + 10
            assert committed["labels"][-10:] == ["Li_mobile"] * 7 + ["H_probe"] * 3
            child.wait_for_function(
                "window.__ASE_APP__?.renderer?.addAtomsRegionGroup?.visible === false"
            )

            backend = sessions[editor.session_id].working_atoms
            np.testing.assert_array_equal(backend.positions[: len(host)], baseline_positions)
            for name, values in baseline_arrays.items():
                np.testing.assert_array_equal(backend.arrays[name][: len(host)], values)
            assert [repr(item) for item in backend.constraints] == baseline_constraints
            assert atom_labels(backend)[-10:] == ["Li_mobile"] * 7 + ["H_probe"] * 3
            browser.close()
    finally:
        editor.close()


def test_http_bridge_controls_the_same_live_workspace_without_page_evaluation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("V_ASE_CONFIG_DIR", str(tmp_path / "preferences"))
    first = Atoms(
        "H2",
        positions=[[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=True,
    )
    second = first.copy()
    second.positions[1, 1] = 0.15
    port = find_free_port()
    editor = view(
        [first, second],
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    handshake = ai_handshake(editor.url)
    command_url = str(handshake["command_url"])

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")

            ready = _post_command(command_url, "ready")["result"]
            assert ready["ready"] is True
            assert ready["sessionId"] == editor.session_id

            cli_ready = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "v_ase.cli",
                    "api",
                    command_url,
                    "ready",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert json.loads(cli_ready.stdout)["result"]["sessionId"] == editor.session_id

            capabilities = _run_cli_command(command_url, "capabilities")
            assert capabilities["schemaUrl"].endswith("/api/ai/schema")
            assert "expectedRevision" in capabilities["apply"]
            assert "vector" in capabilities["operationParameters"]["move-selection"]["required"]
            assert "embedProject" in capabilities["exportParameters"]["html"]["optional"]
            assert {
                "wrap",
                "move-selection",
                "rotate-selection",
                "set-constraints",
                "refresh-displacements",
                "load-commensurate-guest",
                "remove-commensurate-guest",
                "calculate-commensurate",
                "calculate-registry-map",
                "set-registry-translation",
                "set-interface-theme",
                "set-personal-visual-default",
                "restore-app-visual-defaults",
            }.issubset(capabilities["operations"])
            assert "preferences" in capabilities["state"]
            assert {
                "image",
                "html",
                "project",
                "settings",
                "commensurate-csv",
                "registry-csv",
            }.issubset(
                capabilities["exports"]
            )

            initial = _post_command(
                command_url,
                "describe",
                {"includePositions": True},
            )["result"]
            assert initial["atomCount"] == 2
            assert initial["frameCount"] == 2
            assert initial["calculator"]["attached"] is True
            assert initial["calculator"]["name"] == "Repulsion"
            assert initial["calculator"]["details"]["cutoff_scale"] == pytest.approx(0.7)
            assert initial["preferences"]["interfaceTheme"]["preference"] == "system"
            assert initial["preferences"]["personalVisualDefaults"] is False

            schema = _post_command(command_url, "schema")["result"]
            assert set(capabilities["operations"]) == set(
                schema["operation_parameters"]
            )
            assert set(capabilities["exports"]) == set(schema["export_parameters"])
            assert set(capabilities["operationParameters"]) == set(
                schema["operation_parameters"]
            )
            assert set(capabilities["exportParameters"]) == set(
                schema["export_parameters"]
            )
            assert schema["control_schema"]["title"] == "v_ase live semantic control"
            assert schema["operation_parameters"]["rotate-selection"]["mode"] == "edit"
            assert "includeCell" in schema["export_parameters"]["blender"]["optional"]
            assert schema["operation_parameters"]["load-commensurate-guest"]["required"] == [
                "path"
            ]
            assert "maxAreaRatio" in (
                schema["operation_parameters"]["calculate-commensurate"]["optional"]
            )
            assert schema["operation_parameters"]["calculate-registry-map"]["required"] == [
                "selection-or-indices"
            ]
            assert "hkl" in schema["operation_parameters"]["calculate-registry-map"]["optional"]
            assert "hkl" in schema["operation_parameters"]["start-registry-relaxation"]["optional"]
            assert schema["operation_parameters"]["set-registry-translation"]["required"] == [
                "active-registry-relaxation",
                "coordinates",
            ]
            assert "maxAreaRatio" in (
                schema["export_parameters"]["commensurate-csv"]["optional"]
            )
            assert "gridX" in schema["export_parameters"]["registry-csv"]["optional"]
            assert "hkl" in schema["export_parameters"]["registry-csv"]["optional"]
            assert schema["operation_parameters"]["set-interface-theme"]["required"] == [
                "theme"
            ]
            assert schema["operation_parameters"]["restore-app-visual-defaults"][
                "required"
            ] == ["confirm"]
            assert schema["operation_parameters"]["add-volumetric-plane"]["required"] == [
                "datasetId",
                "hkl",
            ]
            assert schema["operation_parameters"]["update-volumetric-planes"][
                "required"
            ] == ["planeIds"]

            themed = _post_command(
                command_url,
                "apply",
                {"operation": {"name": "set-interface-theme", "theme": "dark"}},
            )["result"]
            assert themed["preferences"]["interfaceTheme"]["preference"] == "dark"

            personalized = _post_command(
                command_url,
                "apply",
                {
                    "display": {
                        "atomRadiusScale": 0.83,
                        "atomDisplayMode": "2d",
                        "bondStyle": "flat",
                    },
                    "operation": {"name": "set-personal-visual-default"},
                },
            )["result"]
            assert personalized["preferences"]["personalVisualDefaults"] is True

            rejected_restore = _post_command(
                command_url,
                "apply",
                {
                    "operation": {
                        "name": "restore-app-visual-defaults",
                        "confirm": False,
                    }
                },
                expected_status=422,
            )
            assert "confirm" in rejected_restore["detail"]

            restored = _post_command(
                command_url,
                "apply",
                {
                    "operation": {
                        "name": "restore-app-visual-defaults",
                        "confirm": True,
                    }
                },
            )["result"]
            assert restored["preferences"]["personalVisualDefaults"] is False
            assert restored["display"]["atomRadiusScale"] == pytest.approx(0.6)
            assert restored["display"]["atomDisplayMode"] == "3d"

            changed = _run_cli_command(
                command_url,
                "apply",
                {
                    "expectedRevision": restored["collaboration"]["revision"],
                    "mode": "edit",
                    "display": {
                        "showGrid": False,
                        "showAxes": True,
                        "showCell": True,
                        "viewportBackground": "white",
                    },
                    "camera": {"axis": "+Z", "fit": "structure"},
                    "selection": {"clear": True, "indices": [1]},
                    "operation": {
                        "name": "move-selection",
                        "vector": [0.1, 0.2, 0.0],
                        "applyConstraints": True,
                    },
                },
            )
            assert changed["positions"][1] == pytest.approx(
                [0.84, 0.2, 0.0],
                abs=1e-8,
            )
            assert changed["selection"][0]["index"] == 1

            child = next(
                frame for frame in page.frames if "workspace_child=1" in frame.url
            )
            child.wait_for_function(
                "() => document.getElementById('prop-selected')?.textContent === '1'"
            )
            assert child.locator('[data-runtime-mode="edit"]').get_attribute(
                "aria-pressed"
            ) == "true"
            assert child.locator("#chk-axes").is_checked()
            assert child.locator("#chk-cell").is_checked()
            assert not child.locator("#chk-grid").is_checked()
            assert child.locator("#selected-indices").inner_text().strip() == "1"

            stale = _post_command(
                command_url,
                "apply",
                {
                    "expectedRevision": initial["collaboration"]["revision"],
                    "camera": {"axis": "-Z"},
                },
                expected_status=422,
            )
            assert "Collaboration revision conflict" in stale["detail"]

            rendered = _post_command(
                command_url,
                "render",
                {
                    "format": "png",
                    "width": 320,
                    "height": 240,
                    "options": {
                        "includeGrid": False,
                        "includeAxes": True,
                        "includeCell": True,
                        "backgroundColor": "#ffffff",
                    },
                },
            )["result"]
            assert rendered["width"] == 320
            assert rendered["height"] == 240
            image_bytes = base64.b64decode(rendered["dataUrl"].split(",", 1)[1])
            with Image.open(io.BytesIO(image_bytes)) as image:
                assert image.size == (320, 240)
                pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
            assert float(pixels.std()) > 2.0

            cli_image_path = tmp_path / "agent-http-render.png"
            try:
                cli_render = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "v_ase.cli",
                        "api",
                        command_url,
                        "render",
                        "--params",
                        json.dumps({
                            "format": "png",
                            "width": 160,
                            "height": 120,
                            "options": {
                                "includeGrid": False,
                                "includeAxes": True,
                                "includeCell": True,
                            },
                        }),
                        "--save",
                        str(cli_image_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                cli_payload = json.loads(cli_render.stdout)["result"]
                assert cli_payload["saved_bytes"] == cli_image_path.stat().st_size
                with Image.open(cli_image_path) as cli_image:
                    assert cli_image.size == (160, 120)
            finally:
                cli_image_path.unlink(missing_ok=True)

            html_export = _post_command(
                command_url,
                "export",
                {
                    "format": "html",
                    "width": 320,
                    "height": 240,
                    "embedProject": False,
                    "options": {
                        "includeGrid": False,
                        "includeAxes": True,
                        "includeCell": True,
                    },
                },
            )["result"]
            assert html_export["filename"].endswith(".html")
            assert html_export["mimeType"].startswith("text/html")
            html_bytes = base64.b64decode(html_export["dataUrl"].split(",", 1)[1])
            assert b"v_ase" in html_bytes

            documents = _post_command(command_url, "documents")["result"]
            assert documents["activeSessionId"] == editor.session_id
            assert len(documents["documents"]) == 1

            created = _post_command(command_url, "newDocument")["result"]
            assert created["sessionId"] != editor.session_id
            documents = _post_command(command_url, "documents")["result"]
            assert len(documents["documents"]) == 2
            assert documents["activeSessionId"] == created["sessionId"]

            activated = _post_command(
                command_url,
                "activate",
                {"sessionId": editor.session_id},
            )["result"]
            assert activated["sessionId"] == editor.session_id

            document_command_url = (
                f"http://127.0.0.1:{port}/api/ai/command/session/{editor.session_id}"
            )
            direct = _post_command(
                document_command_url,
                "describe",
                {"includePositions": False},
            )["result"]
            assert direct["document"] == initial["document"]
            assert "positions" not in direct
            browser.close()
    finally:
        editor.close()
