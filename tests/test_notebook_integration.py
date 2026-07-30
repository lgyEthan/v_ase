import inspect
from pathlib import Path

import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright

from v_ase.viewer import (
    find_free_port,
    get_notebook_display_mode,
    resolve_notebook_display,
    set_notebook_display_mode,
    view,
)


ROOT = Path(__file__).resolve().parents[1]


def test_view_uses_automatic_notebook_detection_by_default():
    assert inspect.signature(view).parameters["notebook"].default is None


def test_notebook_display_mode_supports_magic_targets_and_explicit_overrides():
    previous = get_notebook_display_mode()
    try:
        assert set_notebook_display_mode("inline") == "inline"
        assert resolve_notebook_display(None) is True
        assert resolve_notebook_display("browser") is False
        assert resolve_notebook_display(False) is False
        assert set_notebook_display_mode("browser") == "browser"
        assert resolve_notebook_display(None) is False
        with pytest.raises(ValueError, match="auto, inline, or browser"):
            set_notebook_display_mode("popup")
    finally:
        set_notebook_display_mode(previous)


def test_jupyter_kernel_renders_view_inline_without_browser_workspace():
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")

    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "\n".join([
                    "from ase import Atoms",
                    "from v_ase.visualize import view",
                    "from v_ase.viewer import get_notebook_display_mode",
                ])
            ),
            nbformat.v4.new_code_cell(
                "\n".join([
                    "%v_ase inline",
                    "editor = view(",
                    "    Atoms('CO', positions=[[0, 0, 0], [1.15, 0, 0]]),",
                    "    block=False,",
                    "    close_on_disconnect=False,",
                    ")",
                    "print('INLINE_EDITOR', type(editor).__name__, '/workspace' not in editor.url)",
                    "editor",
                ])
            ),
            nbformat.v4.new_code_cell(
                "\n".join([
                    "%v_ase browser",
                    "browser_editor = view(",
                    "    Atoms('H', positions=[[0, 0, 0]]),",
                    "    block=False,",
                    "    open_browser=False,",
                    "    close_on_disconnect=False,",
                    ")",
                    "print('BROWSER_EDITOR', '/workspace' in browser_editor.url, get_notebook_display_mode())",
                ])
            ),
            nbformat.v4.new_code_cell(
                "\n".join([
                    "editor.close()",
                    "browser_editor.close()",
                    "%v_ase auto",
                ])
            ),
        ],
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
    )
    client = nbclient.NotebookClient(
        notebook,
        timeout=90,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    executed = client.execute(cwd=str(ROOT))
    outputs = executed.cells[1].outputs
    html_outputs = [
        output.get("data", {}).get("text/html", "")
        for output in outputs
        if output.output_type in {"display_data", "execute_result"}
    ]
    text_outputs = [
        output.get("text", "")
        for output in outputs
        if output.output_type == "stream"
    ]
    assert len([html for html in html_outputs if html]) == 1
    assert any(
        "<iframe" in html
        and "127.0.0.1:" in html
        and "/api/notebook/view/" in html
        and "/workspace" not in html
        for html in html_outputs
    )
    assert any("INLINE_EDITOR ASEEditor True" in text for text in text_outputs)
    browser_text = [
        output.get("text", "")
        for output in executed.cells[2].outputs
        if output.output_type == "stream"
    ]
    assert any("BROWSER_EDITOR True browser" in text for text in browser_text)


def test_notebook_view_endpoint_is_rendered_and_orbits_in_place():
    editor = view(
        Atoms(
            "CO",
            positions=[[0.0, 0.0, 0.0], [1.15, 0.0, 0.0]],
            cell=[6.0, 6.0, 6.0],
            pbc=True,
        ),
        notebook=True,
        block=False,
        port=find_free_port(),
        close_on_disconnect=False,
        open_browser=False,
    )
    try:
        assert "/api/notebook/view/" in editor.notebook_url
        assert "/workspace" not in editor.notebook_url
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 960, "height": 640})
            page.goto(editor.notebook_url, wait_until="load")
            page.locator("html[data-v-ase-ready='true']").wait_for(state="attached")
            assert page.locator(".view-only-badge").inner_text() == "VIEW ONLY"
            assert page.locator("html").get_attribute("data-v-ase-atom-count") == "2"
            assert page.locator("#viewer-frame canvas").is_visible()
            assert page.locator(".inspector").count() == 0

            before = page.evaluate(
                "window.v_aseStandalone.renderer.camera.quaternion.toArray()"
            )
            canvas = page.locator("#viewer-frame canvas").bounding_box()
            assert canvas
            page.mouse.move(
                canvas["x"] + canvas["width"] * 0.5,
                canvas["y"] + canvas["height"] * 0.5,
            )
            page.mouse.down(button="left")
            page.mouse.move(
                canvas["x"] + canvas["width"] * 0.68,
                canvas["y"] + canvas["height"] * 0.58,
                steps=6,
            )
            page.mouse.up(button="left")
            after = page.evaluate(
                "window.v_aseStandalone.renderer.camera.quaternion.toArray()"
            )
            assert after != pytest.approx(before)
            browser.close()
    finally:
        editor.close()
