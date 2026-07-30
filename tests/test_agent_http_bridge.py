"""End-to-end checks for the vendor-neutral HTTP command bridge."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import sys

import numpy as np
import pytest
import requests
from ase import Atoms
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.ai import ai_handshake
from v_ase.viewer import find_free_port, view


def _post_command(url: str, method: str, params=None, *, expected_status: int = 200):
    response = requests.post(
        url,
        json={"method": method, "params": {} if params is None else params},
        timeout=30,
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def test_http_bridge_controls_the_same_live_workspace_without_page_evaluation(tmp_path):
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

            capabilities = _post_command(command_url, "capabilities")["result"]
            assert capabilities["schemaUrl"].endswith("/api/ai/schema")
            assert "vector" in capabilities["operationParameters"]["move-selection"]["required"]
            assert "embedProject" in capabilities["exportParameters"]["html"]["optional"]
            assert {
                "wrap",
                "move-selection",
                "rotate-selection",
                "set-constraints",
                "refresh-displacements",
            }.issubset(capabilities["operations"])
            assert {"image", "html", "project", "settings"}.issubset(
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

            schema = _post_command(command_url, "schema")["result"]
            assert schema["control_schema"]["title"] == "v_ase live semantic control"
            assert schema["operation_parameters"]["rotate-selection"]["mode"] == "edit"
            assert "includeCell" in schema["export_parameters"]["blender"]["optional"]

            changed = _post_command(
                command_url,
                "apply",
                {
                    "expectedRevision": initial["collaboration"]["revision"],
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
            )["result"]
            assert changed["positions"][1] == pytest.approx(
                [0.84, 0.2, 0.0],
                abs=1e-8,
            )
            assert changed["selection"][0]["index"] == 1

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
